from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

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
USER = {"age": 24, "gender": "male", "height_cm": 180, "weight_kg": 78,
        "goal": "build muscle", "experience": "intermediate"}


@pytest.fixture
def client(tmp_path):
    csv = tmp_path / "exercises.csv"
    pd.DataFrame([(i, n, p, s, "barbell", "beginner", "strength") for i, n, p, s in EXERCISES],
                 columns=["exercise_id", "name", "primary_muscles", "secondary_muscles",
                          "equipment", "level", "category"]).to_csv(csv, index=False)
    with TestClient(create_app("sqlite://", csv)) as c:
        yield c


def workout(day=None, **overrides):
    w = {"date": str(day or date.today()), "duration_min": 60, "rpe": 7,
         "sets": [{"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": 70},
                  {"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": 70}]}
    return w | overrides


def test_create_and_read_user(client):
    r = client.post("/users", json=USER)
    assert r.status_code == 201
    uid = r.json()["id"]
    assert client.get(f"/users/{uid}").json() == USER | {"id": uid}
    assert client.get("/users/999").status_code == 404


@pytest.mark.parametrize("field, value", [("age", 5), ("weight_kg", 1000), ("goal", "be famous"),
                                          ("gender", "unknown")])
def test_impossible_user_values_rejected(client, field, value):
    assert client.post("/users", json=USER | {field: value}).status_code == 422


def test_log_workout_and_history(client):
    uid = client.post("/users", json=USER).json()["id"]
    r = client.post(f"/users/{uid}/workouts", json=workout())
    assert r.status_code == 201
    sets = r.json()["sets"]
    assert [s["set_number"] for s in sets] == [1, 2]
    assert sets[0]["exercise"] == "barbell bench press - medium grip"
    assert len(client.get(f"/users/{uid}/workouts").json()) == 1


@pytest.mark.parametrize("change", [
    {"rpe": 11},
    {"sets": []},
    {"date": str(date.today() + timedelta(days=1))},
    {"sets": [{"exercise_id": "Barbell_Bench_Press", "reps": 0, "weight_kg": 70}]},
    {"sets": [{"exercise_id": "Barbell_Bench_Press", "reps": 8, "weight_kg": -5}]},
    {"sets": [{"exercise_id": "Not_An_Exercise", "reps": 8, "weight_kg": 70}]},
])
def test_impossible_workouts_rejected(client, change):
    uid = client.post("/users", json=USER).json()["id"]
    assert client.post(f"/users/{uid}/workouts", json=workout(**change)).status_code == 422
    assert client.get(f"/users/{uid}/workouts").json() == []


def test_exercise_search(client):
    names = [e["name"] for e in client.get("/exercises", params={"search": "bench"}).json()]
    assert names == ["barbell bench press - medium grip"]
    by_muscle = [e["name"] for e in client.get("/exercises", params={"search": "quadriceps"}).json()]
    assert set(by_muscle) == {"barbell squat", "leg press"}


def test_delete_user_removes_all_their_data(client):
    uid = client.post("/users", json=USER).json()["id"]
    other = client.post("/users", json=USER).json()["id"]
    client.post(f"/users/{uid}/workouts", json=workout())
    client.post(f"/users/{other}/workouts", json=workout())

    assert client.delete(f"/users/{uid}").status_code == 204
    assert client.get(f"/users/{uid}").status_code == 404
    assert client.get(f"/users/{uid}/workouts").status_code == 404
    assert len(client.get(f"/users/{other}/workouts").json()) == 1   # other users untouched


def test_user_cannot_delete_someone_elses_workout(client):
    a = client.post("/users", json=USER).json()["id"]
    b = client.post("/users", json=USER).json()["id"]
    wid = client.post(f"/users/{a}/workouts", json=workout()).json()["id"]
    assert client.delete(f"/users/{b}/workouts/{wid}").status_code == 404
    assert len(client.get(f"/users/{a}/workouts").json()) == 1


def test_demo_user_progress(client):
    uid = client.post("/demo-users/legs_neglected").json()["id"]
    p = client.get(f"/users/{uid}/progress").json()
    assert p["workouts"] == 12
    assert p["days_since_last_trained"]["quadriceps"] == 17
    assert p["strength_trends"]["standing military press"]["trend"] == "stalled"


def test_progress_without_workouts(client):
    uid = client.post("/users", json=USER).json()["id"]
    assert client.get(f"/users/{uid}/progress").json()["workouts"] == 0
