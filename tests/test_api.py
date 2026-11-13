from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import AuthSession, User
from app.main import create_app
from src.coach import CoachUnavailable

EXERCISES = [
    ("Barbell_Bench_Press", "barbell bench press - medium grip", "chest", "shoulders; triceps"),
    ("Standing_Military_Press", "standing military press", "shoulders", "triceps"),
    ("Triceps_Pushdown", "triceps pushdown", "triceps", ""),
    ("Bent_Over_Barbell_Row", "bent over barbell row", "middle back", "biceps; lats; shoulders"),
    ("Seated_Cable_Rows", "seated cable rows", "middle back", "biceps; lats; shoulders"),
    ("Barbell_Curl", "barbell curl", "biceps", "forearms"),
    ("Barbell_Squat", "barbell squat", "quadriceps", "calves; glutes; hamstrings; lower back"),
    ("Romanian_Deadlift", "romanian deadlift", "hamstrings", "calves; glutes; lower back"),
    ("Leg_Press", "leg press", "quadriceps", "calves; glutes; hamstrings"),
]
PROFILE = {"age": 24, "gender": "male", "height_cm": 180, "weight_kg": 78,
           "goal": "build muscle", "experience": "intermediate"}
PASSWORD = "correct horse battery"


class FakeLLM:
    """Stands in for Ollama: records what it was sent and gives a fixed answer."""
    model = "fake-model"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def chat(self, messages):
        if self.fail:
            raise CoachUnavailable("Ollama is not reachable")
        self.calls.append(messages)
        return "Train your legs."


def make_client(tmp_path, llm):
    csv = tmp_path / "exercises.csv"
    pd.DataFrame([(i, n, p, s, "barbell", "beginner", "strength") for i, n, p, s in EXERCISES],
                 columns=["exercise_id", "name", "primary_muscles", "secondary_muscles",
                          "equipment", "level", "category"]).to_csv(csv, index=False)
    return TestClient(create_app("sqlite://", csv, llm=llm, coach_log=tmp_path / "coach_log.jsonl"))


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(tmp_path, llm):
    with make_client(tmp_path, llm) as c:
        yield c


def register(client, username="alice", password=PASSWORD, ai_coach=True, **changes):
    body = {"username": username, "password": password, "consent_health_data": True,
            "consent_ai_coach": ai_coach, **PROFILE, **changes}
    return client.post("/auth/register", json=body)


def auth(client, username="alice", **kw):
    """Register and return the Authorization header."""
    r = register(client, username, **kw)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def make_admin(client, username="boss"):
    headers = auth(client, username)
    with client.app.state.Session() as s:
        s.scalar(select(User).where(User.username == username)).role = "admin"
        s.commit()
    return headers


def workout(day=None, **overrides):
    w = {"date": str(day or date.today()), "duration_min": 60, "rpe": 7,
         "sets": [{"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": 70},
                  {"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": 70}]}
    return w | overrides


# ---------------- registration and login ----------------
def test_register_and_me(client):
    r = register(client)
    assert r.status_code == 201
    me = client.get("/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert me["username"] == "alice" and me["role"] == "user"
    assert me["consent_health_at"] is not None and me["consent_ai_coach"] is True
    assert "password_hash" not in me and "password" not in me


def test_register_requires_health_consent(client):
    assert register(client, consent_health_data=False).status_code == 422


@pytest.mark.parametrize("password", ["short", "password1", "alice-is-strong"])
def test_weak_passwords_rejected(client, password):
    assert register(client, password=password).status_code == 422


def test_username_must_be_unique_ignoring_case(client):
    register(client, "Alice")
    assert register(client, "alice").status_code == 409


@pytest.mark.parametrize("field, value", [("age", 5), ("weight_kg", 1000), ("goal", "be famous"),
                                          ("username", "a b"), ("username", "x")])
def test_impossible_registration_values_rejected(client, field, value):
    assert register(client, **{field: value}).status_code == 422


def test_password_is_stored_hashed(client):
    register(client)
    with client.app.state.Session() as s:
        stored = s.scalar(select(User.password_hash).where(User.username == "alice"))
    assert PASSWORD not in stored and stored.startswith("pbkdf2_sha256$")


def test_login_and_logout(client):
    register(client)
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong password"}).status_code == 401
    assert client.post("/auth/login", json={"username": "nobody", "password": PASSWORD}).status_code == 401
    r = client.post("/auth/login", json={"username": "ALICE", "password": PASSWORD})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).status_code == 401


def test_session_tokens_are_stored_hashed(client):
    token = register(client).json()["token"]
    with client.app.state.Session() as s:
        stored = s.scalars(select(AuthSession.token_hash)).all()
    assert token not in stored and len(stored) == 1


def test_account_locks_after_five_wrong_passwords(client):
    register(client)
    for _ in range(5):
        client.post("/auth/login", json={"username": "alice", "password": "wrong password"})
    r = client.post("/auth/login", json={"username": "alice", "password": PASSWORD})
    assert r.status_code == 429                      # locked, even with the right password


def test_expired_session_rejected(client):
    headers = auth(client)
    with client.app.state.Session() as s:
        for session in s.scalars(select(AuthSession)):
            session.expires_at = session.expires_at - timedelta(days=1)
        s.commit()
    assert client.get("/me", headers=headers).status_code == 401


@pytest.mark.parametrize("method, path", [("get", "/me"), ("get", "/me/workouts"), ("get", "/me/progress"),
                                          ("get", "/me/export"), ("post", "/me/coach"), ("get", "/admin/users")])
def test_endpoints_need_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_change_password_signs_out_other_sessions(client):
    first = auth(client)
    second = {"Authorization": "Bearer " + client.post(
        "/auth/login", json={"username": "alice", "password": PASSWORD}).json()["token"]}
    r = client.put("/me/password", headers=first, json={"current_password": PASSWORD,
                                                         "new_password": "a much better passphrase"})
    assert r.status_code == 204
    assert client.get("/me", headers=first).status_code == 200      # this session stays
    assert client.get("/me", headers=second).status_code == 401     # the other one is signed out
    assert client.post("/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 401


# ---------------- workouts and progress ----------------
def test_log_workout_and_history(client):
    h = auth(client)
    r = client.post("/me/workouts", headers=h, json=workout())
    assert r.status_code == 201
    sets = r.json()["sets"]
    assert [s["set_number"] for s in sets] == [1, 2]
    assert sets[0]["exercise"] == "barbell bench press - medium grip"
    assert r.json()["total_volume_kg"] == 2 * 8 * 70
    assert r.json()["estimated_kcal"] == 390          # MET 5.0 (RPE 7) x 78 kg x 1 hour
    assert len(client.get("/me/workouts", headers=h).json()) == 1


@pytest.mark.parametrize("change", [
    {"rpe": 11},
    {"sets": []},
    {"date": str(date.today() + timedelta(days=1))},
    {"sets": [{"exercise_id": "Barbell_Bench_Press", "reps": 0, "weight_kg": 70}]},
    {"sets": [{"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": -5}]},
    {"sets": [{"exercise_id": "Not_An_Exercise", "reps": 8, "weight_kg": 70}]},
])
def test_impossible_workouts_rejected(client, change):
    h = auth(client)
    assert client.post("/me/workouts", headers=h, json=workout(**change)).status_code == 422
    assert client.get("/me/workouts", headers=h).json() == []


def test_users_only_see_their_own_workouts(client):
    a, b = auth(client, "alice"), auth(client, "bob")
    wid = client.post("/me/workouts", headers=a, json=workout()).json()["id"]
    assert client.get("/me/workouts", headers=b).json() == []
    assert client.delete(f"/me/workouts/{wid}", headers=b).status_code == 404
    assert len(client.get("/me/workouts", headers=a).json()) == 1


def test_new_personal_record(client):
    h = auth(client)
    bench = lambda kg: [{"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": kg}]
    today = date.today()
    first = client.post("/me/workouts", headers=h, json=workout(today - timedelta(days=4), sets=bench(70))).json()
    assert first["new_records"] == []
    better = client.post("/me/workouts", headers=h, json=workout(today - timedelta(days=2), sets=bench(75))).json()
    assert better["new_records"] == ["barbell bench press - medium grip"]
    worse = client.post("/me/workouts", headers=h, json=workout(today, sets=bench(60))).json()
    assert worse["new_records"] == []


def test_exercise_history(client):
    h = auth(client)
    client.post("/me/workouts", headers=h, json=workout())
    hist = client.get("/me/exercise-history/Barbell_Bench_Press", headers=h).json()
    assert len(hist) == 1 and hist[0]["best_est_1rm_kg"] == pytest.approx(88.7)
    assert client.get("/me/exercise-history/Nope", headers=h).status_code == 404


def test_exercise_search_is_public(client):
    names = [e["name"] for e in client.get("/exercises", params={"search": "bench"}).json()]
    assert names == ["barbell bench press - medium grip"]
    by_muscle = [e["name"] for e in client.get("/exercises", params={"search": "quadriceps"}).json()]
    assert set(by_muscle) == {"barbell squat", "leg press"}


@pytest.mark.parametrize("path, params", [("/me/progress", {"weeks": 0}), ("/me/progress", {"weeks": -3}),
                                           ("/me/progress", {"weeks": 53}), ("/exercises", {"limit": -1}),
                                           ("/exercises", {"limit": 0}), ("/exercises", {"limit": 1001})])
def test_out_of_range_query_values_rejected(client, path, params):
    h = auth(client)
    client.post("/me/workouts", headers=h, json=workout())      # a workout today: weeks=0 used to divide by zero
    assert client.get(path, headers=h, params=params).status_code == 422


def test_progress_without_workouts(client):
    assert client.get("/me/progress", headers=auth(client)).json()["workouts"] == 0


# ---------------- demo accounts ----------------
def test_demo_account_has_data_and_disappears_at_logout(client):
    r = client.post("/auth/demo")
    assert r.status_code == 201 and r.json()["user"]["is_demo"]
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    p = client.get("/me/progress", headers=h).json()
    assert p["workouts"] == 12 and p["days_since_last_trained"]["quadriceps"] == 17
    client.post("/auth/logout", headers=h)
    with client.app.state.Session() as s:
        assert s.scalar(select(User).where(User.is_demo)) is None


# ---------------- privacy ----------------
def test_export_contains_only_own_data_and_no_password(client):
    a, b = auth(client, "alice"), auth(client, "bob")
    client.post("/me/workouts", headers=a, json=workout())
    client.post("/me/workouts", headers=b, json=workout())
    data = client.get("/me/export", headers=a).json()
    assert data["account"]["username"] == "alice"
    assert len(data["workouts"]) == 1
    assert "password" not in str(data)


def test_delete_account_needs_password_and_removes_everything(client):
    a, b = auth(client, "alice"), auth(client, "bob")
    client.post("/me/workouts", headers=a, json=workout())
    client.post("/me/workouts", headers=b, json=workout())
    assert client.post("/me/delete", headers=a, json={"password": "wrong password"}).status_code == 403
    assert client.post("/me/delete", headers=a, json={"password": PASSWORD}).status_code == 204
    assert client.get("/me", headers=a).status_code == 401           # sessions are gone too
    assert client.post("/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 401
    assert len(client.get("/me/workouts", headers=b).json()) == 1     # other users untouched


def test_ai_coach_needs_its_own_consent(client):
    h = auth(client, ai_coach=False)
    assert client.post("/me/coach", headers=h, json={"question": "Hi"}).status_code == 403
    assert client.put("/me/consent", headers=h, json={"ai_coach": True}).json()["consent_ai_coach"] is True
    assert client.post("/me/coach", headers=h, json={"question": "Hi"}).status_code == 200
    client.put("/me/consent", headers=h, json={"ai_coach": False})
    assert client.post("/me/coach", headers=h, json={"question": "Hi"}).status_code == 403


# ---------------- AI coach ----------------
def demo_headers(client):
    return {"Authorization": f"Bearer {client.post('/auth/demo').json()['token']}"}


def test_coach_gets_progress_but_no_personal_details(client, llm):
    h = demo_headers(client)
    username = client.get("/me", headers=h).json()["username"]
    r = client.post("/me/coach", headers=h, json={"question": "Which muscles am I neglecting?"})
    assert r.status_code == 200 and r.json()["answer"] == "Train your legs."
    assert set(r.json()["context"]) == {"goal", "experience", "key_findings", "progress"}

    system = llm.calls[0][0]["content"]
    assert '"quadriceps": 17' in system                        # the computed numbers are there
    for personal in ['"age"', '"gender"', '"height_cm"', '"weight_kg"', '"username"', username]:
        assert personal not in system


def test_coach_key_findings_are_calculated_by_code(client):
    findings = client.post("/me/coach", headers=demo_headers(client),
                           json={"question": "What next?"}).json()["context"]["key_findings"]
    assert findings["neglected_muscles"]["quadriceps"] == 17
    assert findings["stalled_lifts"] == ["standing military press"]
    assert "triceps pushdown" in findings["improving_lifts"]
    assert "barbell squat" in findings["lifts_not_done_recently"]


def test_coach_prompt_v1_has_no_key_findings():
    from src.coach import build_context
    summary = {"workouts": 1, "days_since_last_trained": {}, "strength_trends": {}}
    assert "key_findings" not in build_context("build muscle", "beginner", summary, version="v1")
    assert "key_findings" in build_context("build muscle", "beginner", summary, version="v2")


def test_coach_follow_up_includes_history(client, llm):
    history = [{"role": "user", "content": "Am I improving?"}, {"role": "assistant", "content": "Yes."}]
    client.post("/me/coach", headers=demo_headers(client), json={"question": "On which lift?", "history": history})
    assert [m["role"] for m in llm.calls[0]] == ["system", "user", "assistant", "user"]


def test_coach_logs_every_answer(client, tmp_path):
    client.post("/me/coach", headers=demo_headers(client), json={"question": "Am I improving?"})
    lines = (tmp_path / "coach_log.jsonl").read_text().splitlines()
    assert len(lines) == 1 and '"Am I improving?"' in lines[0]


def test_coach_unavailable_gives_clear_error(tmp_path):
    with make_client(tmp_path, FakeLLM(fail=True)) as c:
        r = c.post("/me/coach", headers=auth(c), json={"question": "Hi"})
    assert r.status_code == 503 and "Ollama" in r.json()["detail"]


def test_empty_question_rejected(client):
    assert client.post("/me/coach", headers=auth(client), json={"question": ""}).status_code == 422


# ---------------- admin ----------------
def test_admin_pages_are_for_admins_only(client):
    h = auth(client)
    for path in ["/admin/users", "/admin/stats", "/admin/audit"]:
        assert client.get(path, headers=h).status_code == 403


def test_admin_sees_accounts_but_no_training_or_body_data(client):
    admin = make_admin(client)
    h = auth(client, "alice")
    client.post("/me/workouts", headers=h, json=workout())
    users = client.get("/admin/users", headers=admin).json()
    alice = next(u for u in users if u["username"] == "alice")
    assert alice["workouts"] == 1
    for private in ["age", "weight_kg", "height_cm", "gender", "goal", "sets", "password_hash"]:
        assert private not in alice
    assert client.get("/admin/stats", headers=admin).json()["accounts"] == 2


def test_admin_can_promote_unlock_and_delete_with_audit_trail(client):
    admin = make_admin(client)
    auth(client, "alice")
    alice_id = next(u["id"] for u in client.get("/admin/users", headers=admin).json() if u["username"] == "alice")
    for _ in range(5):
        client.post("/auth/login", json={"username": "alice", "password": "wrong password"})
    assert client.post("/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 429
    client.post(f"/admin/users/{alice_id}/unlock", headers=admin)
    assert client.post("/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 200

    assert client.put(f"/admin/users/{alice_id}/role", headers=admin, json={"role": "admin"}).json()["role"] == "admin"
    assert client.delete(f"/admin/users/{alice_id}", headers=admin).status_code == 204
    actions = [(a["action"], a["target"]) for a in client.get("/admin/audit", headers=admin).json()]
    assert ("delete_account", "alice") in actions and ("unlock", "alice") in actions
    assert ("set_role_admin", "alice") in actions and ("account_locked", "") in actions


def test_there_is_always_an_admin(client):
    admin = make_admin(client)
    me = client.get("/me", headers=admin).json()
    assert client.put(f"/admin/users/{me['id']}/role", headers=admin, json={"role": "user"}).status_code == 409
    assert client.post("/me/delete", headers=admin, json={"password": PASSWORD}).status_code == 409
    assert client.delete(f"/admin/users/{me['id']}", headers=admin).status_code == 409


def test_workout_keeps_start_time_and_focus(client):
    h = auth(client)
    r = client.post("/me/workouts", headers=h, json=workout(start_time="18:30", focus="chest, arms"))
    assert r.status_code == 201
    w = client.get("/me/workouts", headers=h).json()[0]
    assert w["start_time"] == "18:30:00" and w["focus"] == "chest, arms"
    assert client.post("/me/workouts", headers=h, json=workout(focus="x" * 81)).status_code == 422


def test_whole_exercise_library_can_be_listed(client):
    assert len(client.get("/exercises", params={"limit": 1000}).json()) == len(EXERCISES)


def test_older_database_gets_new_columns_without_losing_data(tmp_path):
    """A database made before start_time and focus existed is updated in place."""
    import sqlite3
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER, date DATE, "
                      "duration_min INTEGER, rpe INTEGER); INSERT INTO workouts VALUES (1, 1, '2026-11-01', 60, 7);")
    con.close()
    from app.db import add_missing_columns, make_engine
    assert add_missing_columns(make_engine(f"sqlite:///{db}")) == ["workouts.start_time", "workouts.focus"]
    con = sqlite3.connect(db)
    assert con.execute("SELECT date, start_time, focus FROM workouts").fetchall() == [("2026-11-01", None, None)]
    con.close()
