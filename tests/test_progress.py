from datetime import date

import pandas as pd
import pytest

from src.personas import legs_neglected
from src.progress import estimated_1rm, neglected_muscles, progress_summary

TODAY = date(2026, 11, 9)

EXERCISES = pd.DataFrame([
    ("barbell bench press - medium grip", "chest", "shoulders; triceps"),
    ("standing military press", "shoulders", "triceps"),
    ("triceps pushdown", "triceps", ""),
    ("bent over barbell row", "middle back", "biceps; lats; shoulders"),
    ("seated cable rows", "middle back", "biceps; lats; shoulders"),
    ("barbell curl", "biceps", "forearms"),
    ("barbell squat", "quadriceps", "calves; glutes; hamstrings; lower back"),
    ("romanian deadlift", "hamstrings", "calves; glutes; lower back"),
    ("leg press", "quadriceps", "calves; glutes; hamstrings"),
    ("pushups", "chest", "shoulders; triceps"),
], columns=["name", "primary_muscles", "secondary_muscles"])


def persona_log(persona):
    return pd.DataFrame([{"date": w["date"], **s} for w in persona["workouts"] for s in w["sets"]])


@pytest.fixture
def summary():
    return progress_summary(persona_log(legs_neglected(TODAY)), EXERCISES, TODAY)


def test_epley():
    assert estimated_1rm(100, 0) == 100
    assert estimated_1rm(90, 10) == pytest.approx(120)


def test_neglected_legs_are_found(summary):
    days = summary["days_since_last_trained"]
    for muscle in ["quadriceps", "hamstrings", "glutes", "calves", "lower back"]:
        assert days[muscle] == 17
    assert days["chest"] == 3
    assert summary["volume_share_pct_last_2_weeks"]["quadriceps"] == 0.0
    assert summary["volume_share_pct"]["quadriceps"] > 0
    assert "quadriceps" in neglected_muscles(summary)
    assert "chest" not in neglected_muscles(summary)


def test_strength_trends(summary):
    trends = summary["strength_trends"]
    assert trends["barbell bench press - medium grip"]["trend"] == "improving"
    assert trends["barbell bench press - medium grip"]["est_1rm_last_week_kg"] == pytest.approx(98.2)
    assert trends["barbell squat"]["trend"] == "not done recently"
    assert [ex for ex, t in trends.items() if t["trend"] == "stalled"] == ["standing military press"]


def test_frequency(summary):
    assert summary["workouts"] == 12
    assert summary["workouts_per_week"] == 3.0


def test_volume_shares_add_up(summary):
    # abdominals and other unlisted muscles (forearms) take the rest
    assert sum(summary["volume_share_pct"].values()) <= 100.1


def test_empty_log():
    empty = pd.DataFrame(columns=["date", "exercise", "reps", "weight_kg"])
    out = progress_summary(empty, EXERCISES, TODAY)
    assert out["workouts"] == 0


def test_bodyweight_exercise_has_no_strength_trend():
    log = pd.DataFrame([{"date": "2026-11-05", "exercise": "pushups", "reps": 20, "weight_kg": 0}])
    out = progress_summary(log, EXERCISES, TODAY)
    assert out["strength_trends"] == {}
    assert out["days_since_last_trained"]["chest"] == 4


def test_unknown_exercise_is_an_error():
    log = pd.DataFrame([{"date": "2026-11-05", "exercise": "made up lift", "reps": 5, "weight_kg": 50}])
    with pytest.raises(ValueError, match="made up lift"):
        progress_summary(log, EXERCISES, TODAY)
