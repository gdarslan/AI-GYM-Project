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
# exercises that are not logged as sets x reps x kg: (id, name, primary, secondary, equipment, category)
OTHER_KINDS = [
    ("Bicycling_Stationary", "bicycling, stationary", "quadriceps", "calves; glutes; hamstrings", "machine", "cardio"),
    ("Plank", "plank", "abdominals", "", "body only", "strength"),
    ("Pushups", "pushups", "chest", "shoulders; triceps", "body only", "strength"),
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
    pd.DataFrame([(i, n, p, s, "barbell", "beginner", "strength") for i, n, p, s in EXERCISES]
                 + [(i, n, p, s, eq, "beginner", cat) for i, n, p, s, eq, cat in OTHER_KINDS],
                 columns=["exercise_id", "name", "primary_muscles", "secondary_muscles",
                          "equipment", "level", "category"]).to_csv(csv, index=False)
    return TestClient(create_app("sqlite://", csv, llm=llm, descriptions_csv=None))


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
    assert set(by_muscle) == {"barbell squat", "leg press", "bicycling, stationary"}


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
    assert set(r.json()["context"]) == {"goal", "experience", "key_findings", "next_session", "consistency",
                                        "progress"}

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


def test_coach_conversation_is_saved_and_continued(client, llm):
    h = demo_headers(client)
    first = client.post("/me/coach", headers=h, json={"question": "Am I improving?"}).json()
    assert first["latency_ms"] >= 0
    client.post("/me/coach", headers=h, json={"question": "On which lift?", "conversation_id": first["conversation_id"]})
    # the second call got the first question and answer as history, from the database
    assert [m["role"] for m in llm.calls[1]] == ["system", "user", "assistant", "user"]
    convs = client.get("/me/conversations", headers=h).json()
    assert len(convs) == 1 and convs[0]["messages"] == 4 and convs[0]["title"] == "Am I improving?"
    msgs = client.get(f"/me/conversations/{first['conversation_id']}", headers=h).json()
    answer = msgs[1]
    assert answer["role"] == "assistant" and answer["model"] == "fake-model" and answer["prompt_version"] == "v3"
    assert answer["context"]["key_findings"]["neglected_muscles"]["quadriceps"] == 17


def test_coach_feedback_and_quality_summary(client):
    h = demo_headers(client)
    mid = client.post("/me/coach", headers=h, json={"question": "Am I improving?"}).json()["message_id"]
    r = client.put(f"/me/coach/messages/{mid}/feedback", headers=h,
                   json={"rating": -1, "reason": "wrong facts", "comment": "military press is not improving"})
    assert r.status_code == 200 and r.json()["reason"] == "wrong facts"
    client.put(f"/me/coach/messages/{mid}/feedback", headers=h, json={"rating": 1})      # rating again replaces it
    assert client.put(f"/me/coach/messages/{mid}/feedback", headers=h, json={"rating": 5}).status_code == 422
    admin = make_admin(client)
    quality = client.get("/admin/coach-quality", headers=admin).json()
    assert quality == [{"model": "fake-model", "prompt_version": "v3", "answers": 1, "rated": 1, "helpful": 1,
                        "not_helpful": 0, "avg_latency_ms": quality[0]["avg_latency_ms"], "reasons": {}}]
    assert "military press" not in str(quality)                       # totals only, never the content


def test_conversations_are_private(client):
    a, b = demo_headers(client), demo_headers(client)
    first = client.post("/me/coach", headers=a, json={"question": "Am I improving?"}).json()
    cid, mid = first["conversation_id"], first["message_id"]
    assert client.get(f"/me/conversations/{cid}", headers=b).status_code == 404
    assert client.post("/me/coach", headers=b, json={"question": "Hi", "conversation_id": cid}).status_code == 404
    assert client.put(f"/me/coach/messages/{mid}/feedback", headers=b, json={"rating": 1}).status_code == 404
    assert client.delete(f"/me/conversations/{cid}", headers=b).status_code == 404
    assert client.delete(f"/me/conversations/{cid}", headers=a).status_code == 204
    assert client.get("/me/conversations", headers=a).json() == []


def test_conversations_in_export_and_deleted_with_account(client):
    h = auth(client)
    client.post("/me/workouts", headers=h, json=workout())
    client.post("/me/coach", headers=h, json={"question": "Am I improving?"})
    assert client.get("/me/export", headers=h).json()["coach_conversations"][0]["title"] == "Am I improving?"
    client.post("/me/delete", headers=h, json={"password": PASSWORD})
    from app.db import CoachMessage
    with client.app.state.Session() as s:
        assert s.scalars(select(CoachMessage)).all() == []


def test_exercise_descriptions_from_megagym(tmp_path):
    desc = tmp_path / "megagym.csv"
    pd.DataFrame([("barbell squat", "A compound lower-body movement with a barbell on the back."),
                  ("unknown lift", "Not in the library, so not used.")],
                 columns=["name", "description"]).to_csv(desc, index=False)
    csv = tmp_path / "exercises.csv"
    pd.DataFrame([(i, n, p, s, "barbell", "beginner", "strength") for i, n, p, s in EXERCISES],
                 columns=["exercise_id", "name", "primary_muscles", "secondary_muscles",
                          "equipment", "level", "category"]).to_csv(csv, index=False)
    with TestClient(create_app("sqlite://", csv, llm=FakeLLM(), descriptions_csv=desc)) as c:
        found = {e["name"]: e["description"] for e in c.get("/exercises", params={"limit": 100}).json()}
    assert found["barbell squat"].startswith("A compound")
    assert found["leg press"] is None


def test_coach_falls_back_to_the_numbers_without_a_model(tmp_path):
    with make_client(tmp_path, FakeLLM(fail=True)) as c:
        h = demo_headers(c)
        r = c.post("/me/coach", headers=h, json={"question": "Which muscles am I neglecting?"})
        weekly = c.post("/me/coach/weekly-summary", headers=h)
        quality = c.get("/admin/coach-quality", headers=make_admin(c)).json()
    assert r.status_code == 200 and weekly.status_code == 200
    body = r.json()
    assert body["model"] == "template (AI coach offline)" and body["prompt_version"] == "template"
    assert "not available" in body["answer"] and "quadriceps (17 days)" in body["answer"]
    assert "standing military press" in body["answer"]                 # stalled lift and next-session target
    assert {q["model"] for q in quality} == {"template (AI coach offline)"}   # kept apart from real answers


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
    from app.db import ACTIVITIES_CSV
    classes = len(pd.read_csv(ACTIVITIES_CSV))
    assert len(client.get("/exercises", params={"limit": 1000}).json()) == len(EXERCISES) + len(OTHER_KINDS) + classes


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


def test_next_session_targets_and_coach_context(client):
    h = demo_headers(client)
    targets = {t["exercise"]: t for t in client.get("/me/next-session", headers=h).json()}
    assert "barbell squat" not in targets                          # not done for 17 days
    assert targets["standing military press"]["weight_kg"] == 40.0   # stalled at 45 kg: about 90%
    bench = targets["barbell bench press - medium grip"]
    assert (bench["weight_kg"], bench["reps"]) == (77.5, 9)            # 8 reps in an 8-12 range: one more rep
    context = client.post("/me/coach", headers=h, json={"question": "What next?"}).json()["context"]
    assert any(t["exercise"] == "standing military press" for t in context["next_session"])
    assert context["consistency"]["weekly_target"] == 3


def test_weekly_target_and_consistency(client):
    h = auth(client)
    assert client.get("/me", headers=h).json()["weekly_target"] == 3
    client.put("/me", headers=h, json=PROFILE | {"weekly_target": 1})
    client.post("/me/workouts", headers=h, json=workout())
    c = client.get("/me/progress", headers=h).json()["consistency"]
    assert c == {"weekly_target": 1, "this_week": 1, "week_streak": 1}
    assert client.put("/me", headers=h, json=PROFILE | {"weekly_target": 8}).status_code == 422


def test_new_user_has_too_little_data(client):
    h = auth(client)
    client.post("/me/workouts", headers=h, json=workout())
    p = client.get("/me/progress", headers=h).json()
    assert p["enough_data"] is False
    context = client.post("/me/coach", headers=h, json={"question": "What am I neglecting?"}).json()["context"]
    assert context["key_findings"]["enough_data"] is False
    assert context["key_findings"]["neglected_muscles"] == {}         # one day of history: nothing is "neglected"


def test_weekly_summary_is_saved_as_a_conversation(client, llm):
    h = demo_headers(client)
    r = client.post("/me/coach/weekly-summary", headers=h)
    assert r.status_code == 200
    assert "weekly summary" in llm.calls[0][-1]["content"].lower()
    conv = client.get("/me/conversations", headers=h).json()[0]
    assert conv["title"].startswith("Weekly summary") and conv["id"] == r.json()["conversation_id"]


def test_each_exercise_has_a_kind(client):
    kinds = {e["name"]: e["kind"] for e in client.get("/exercises", params={"limit": 1000}).json()}
    assert kinds["bicycling, stationary"] == "cardio" and kinds["plank"] == "timed"
    assert kinds["pushups"] == "bodyweight" and kinds["barbell squat"] == "weighted"


def test_cardio_holds_and_bodyweight_are_logged_their_own_way(client):
    h = auth(client)                                                     # body weight 78 kg
    r = client.post("/me/workouts", headers=h, json=workout(duration_min=60, rpe=7, sets=[
        {"exercise_id": "Bicycling_Stationary", "duration_s": 1800, "level": 8},
        {"exercise_id": "Plank", "duration_s": 45}, {"exercise_id": "Plank", "duration_s": 45},
        {"exercise_id": "Pushups", "reps": 15}]))
    assert r.status_code == 201, r.text
    w = r.json()
    bike = w["sets"][0]
    assert (bike["kind"], bike["reps"], bike["duration_s"], bike["level"]) == ("cardio", 0, 1800, 8)
    assert w["total_volume_kg"] == round(15 * 0.65 * 78, 1)            # push-ups count part of body weight
    # 30 min cycling at level 8 (MET 8.0, Compendium 01228) + 30 min resistance at RPE 7 (MET 5.0, 02061), 78 kg
    assert w["estimated_kcal"] == round(8.0 * 78 * 0.5 + 5.0 * 78 * 0.5)
    p = client.get("/me/progress", headers=h).json()
    assert p["cardio_minutes"] == 30 and p["days_since_last_trained"]["quadriceps"] == 0


@pytest.mark.parametrize("bad_set, message", [
    ({"exercise_id": "Bicycling_Stationary", "reps": 10}, "minutes"),
    ({"exercise_id": "Plank", "reps": 3}, "seconds"),
    ({"exercise_id": "Pushups", "duration_s": 60}, "rep"),
])
def test_wrong_fields_for_the_kind_are_rejected(client, bad_set, message):
    r = client.post("/me/workouts", headers=auth(client), json=workout(sets=[bad_set]))
    assert r.status_code == 422 and message in r.json()["detail"]


def test_yoga_is_a_class_with_its_own_met(client):
    yoga = next(e for e in client.get("/exercises", params={"search": "yoga hatha"}).json())
    assert (yoga["kind"], yoga["met"]) == ("activity", 2.3) and "02150" in yoga["description"]
    h = auth(client)                                                       # 78 kg
    w = client.post("/me/workouts", headers=h, json=workout(duration_min=60, rpe=3, sets=[
        {"exercise_id": "Activity_Yoga_Hatha", "duration_s": 3600}])).json()
    assert w["estimated_kcal"] == round(2.3 * 78)                        # not the weight-training MET
    assert client.get("/me/progress", headers=h).json()["class_minutes"] == 60
    r = client.post("/me/workouts", headers=h, json=workout(sets=[{"exercise_id": "Activity_Yoga_Hatha", "reps": 10}]))
    assert r.status_code == 422 and "minutes" in r.json()["detail"]


def test_session_without_weights_is_not_counted_as_weight_training(client):
    h = auth(client)
    w = client.post("/me/workouts", headers=h, json=workout(duration_min=30, rpe=8, sets=[
        {"exercise_id": "Plank", "duration_s": 60}, {"exercise_id": "Plank", "duration_s": 60}])).json()
    assert w["estimated_kcal"] == round(2.3 * 78 * 0.5)                  # light stretching MET, whatever the RPE
