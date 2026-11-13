from datetime import date

import pandas as pd
import pytest

from src.personas import legs_neglected
from src.calories import estimate_kcal, met_for_rpe
from src.progress import (consistency, estimated_1rm, exercise_history, exercise_kind, neglected_muscles,
                          new_records, next_session_targets, progress_summary, recovery_status)

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


def test_recovery_guideline(summary):
    assert recovery_status({"chest": 0, "quadriceps": 1, "lats": 2, "abdominals": None}) == {
        "chest": "recovering", "quadriceps": "recovering", "lats": "ready"}
    assert summary["recovery_guideline"]["chest"] == "ready"      # trained 3 days ago


def test_exercise_history_per_day():
    log = pd.DataFrame([("2026-11-01", "barbell curl", 8, 30), ("2026-11-01", "barbell curl", 6, 32.5),
                        ("2026-11-05", "barbell curl", 8, 32.5), ("2026-11-05", "barbell squat", 5, 100)],
                       columns=["date", "exercise", "reps", "weight_kg"])
    h = exercise_history(log, "barbell curl")
    assert [d["date"] for d in h] == ["2026-11-01", "2026-11-05"]
    assert h[0]["best_est_1rm_kg"] == pytest.approx(39.0)          # max(30 x (1+8/30), 32.5 x 1.2)
    assert h[1]["volume_kg"] == 260


def test_new_records():
    cols = ["date", "exercise", "reps", "weight_kg"]
    earlier = pd.DataFrame([("2026-11-01", "barbell curl", 8, 30)], columns=cols)
    better = pd.DataFrame([("2026-11-05", "barbell curl", 8, 32.5)], columns=cols)
    same = pd.DataFrame([("2026-11-05", "barbell curl", 8, 30)], columns=cols)
    new_lift = pd.DataFrame([("2026-11-05", "barbell squat", 5, 100)], columns=cols)
    assert new_records(earlier, better) == ["barbell curl"]
    assert new_records(earlier, same) == []
    assert new_records(earlier, new_lift) == []


def test_calorie_estimate():
    assert [met_for_rpe(r) for r in (None, 1, 4, 5, 7, 8, 10)] == [5.0, 3.5, 3.5, 5.0, 5.0, 6.0, 6.0]
    assert estimate_kcal(80, 90, 8) == 720                         # 6.0 x 80 kg x 1.5 h
    assert estimate_kcal(80, None, 8) is None


def test_neglect_needs_ten_days_of_history():
    log = pd.DataFrame([{"date": "2026-11-05", "exercise": "barbell bench press - medium grip", "reps": 8,
                         "weight_kg": 60}])
    out = progress_summary(log, EXERCISES, TODAY)
    assert out["days_of_history"] == 4 and out["enough_data"] is False
    assert neglected_muscles(out) == []          # started 4 days ago: legs are not "neglected" yet


def targets_for(rows, goal="build muscle"):
    log = pd.DataFrame(rows, columns=["date", "exercise", "reps", "weight_kg"])
    return {t["exercise"]: t for t in next_session_targets(log, EXERCISES, goal, TODAY)}


def test_double_progression():
    bench, squat = "barbell bench press - medium grip", "barbell squat"
    t = targets_for([("2026-11-06", bench, 12, 60), ("2026-11-06", bench, 12, 60),
                     ("2026-11-06", squat, 7, 100)])
    assert (t[bench]["weight_kg"], t[bench]["reps"]) == (62.5, 8)     # top of 8-12: upper body +2.5 kg
    assert (t[squat]["weight_kg"], t[squat]["reps"]) == (100, 8)      # below the range: same weight, reach 8
    strength = targets_for([("2026-11-06", squat, 6, 100)], goal="get stronger")
    assert (strength[squat]["weight_kg"], strength[squat]["reps"]) == (105, 4)    # lower body: +5 kg
    bodyweight = targets_for([("2026-11-06", "pushups", 15, 0)])
    assert (bodyweight["pushups"]["weight_kg"], bodyweight["pushups"]["reps"]) == (0, 16)


def test_stalled_lift_gets_a_lighter_week():
    t = {x["exercise"]: x for x in next_session_targets(persona_log(legs_neglected(TODAY)), EXERCISES,
                                                        "build muscle", TODAY)}
    assert (t["standing military press"]["weight_kg"], t["standing military press"]["reps"]) == (40.0, 12)
    assert "barbell squat" not in t                                  # not done recently


def test_week_streak():
    dates = [w["date"] for w in legs_neglected(TODAY)["workouts"]]     # Mon, Wed, Fri for four weeks
    assert consistency(dates, 3, TODAY) == {"weekly_target": 3, "this_week": 0, "week_streak": 4}
    assert consistency(dates, 4, TODAY)["week_streak"] == 0
    assert consistency(dates + [TODAY], 1, TODAY) == {"weekly_target": 1, "this_week": 1, "week_streak": 5}


def test_exercise_kind_from_the_dataset():
    assert exercise_kind("bicycling", "cardio", "other") == "cardio"
    assert exercise_kind("hamstring stretch", "stretching", "body only") == "timed"
    assert exercise_kind("plank", "strength", "body only") == "timed"            # a hold, by its name
    assert exercise_kind("pushups", "strength", "body only") == "bodyweight"
    assert exercise_kind("barbell squat", "strength", "barbell") == "weighted"


KIND_EXERCISES = pd.DataFrame([
    ("pushups", "chest", "shoulders; triceps", "bodyweight"),
    ("bicycling, stationary", "quadriceps", "calves", "cardio"),
    ("plank", "abdominals", "", "timed"),
], columns=["name", "primary_muscles", "secondary_muscles", "kind"])


def kind_log(rows):
    return pd.DataFrame(rows, columns=["date", "exercise", "reps", "weight_kg", "duration_s", "level"])


def test_bodyweight_counts_part_of_body_weight():
    log = kind_log([("2026-11-02", "pushups", 10, 0, None, None), ("2026-11-06", "pushups", 15, 0, None, None)])
    out = progress_summary(log, KIND_EXERCISES, TODAY, body_weight_kg=80)
    assert out["volume_share_pct"]["chest"] > 0
    assert out["strength_trends"]["pushups"]["est_1rm_last_week_kg"] == round(52 * 1.5, 1)   # 0.65 x 80 kg


def test_cardio_and_holds_add_time_not_volume():
    log = kind_log([("2026-11-06", "bicycling, stationary", 0, 0, 2400, 6), ("2026-11-06", "plank", 0, 0, 60, None)])
    out = progress_summary(log, KIND_EXERCISES, TODAY, body_weight_kg=80)
    assert out["cardio_minutes"] == 40 and out["cardio_sessions"] == 1
    assert out["days_since_last_trained"]["quadriceps"] == 3 and out["strength_trends"] == {}


def test_targets_for_cardio_and_holds():
    log = kind_log([("2026-11-06", "bicycling, stationary", 0, 0, 1800, 6),
                    ("2026-11-06", "plank", 0, 0, 45, None), ("2026-11-06", "plank", 0, 0, 50, None)])
    t = {x["exercise"]: x for x in next_session_targets(log, KIND_EXERCISES, "build muscle", TODAY)}
    assert (t["bicycling, stationary"]["minutes"], t["bicycling, stationary"]["level"]) == (35, 6)
    assert t["plank"]["target"] == "2 × 50 s"                              # shortest hold + 5 s
    long_ride = kind_log([("2026-11-06", "bicycling, stationary", 0, 0, 2700, 6)])
    t = next_session_targets(long_ride, KIND_EXERCISES, "build muscle", TODAY)[0]
    assert (t["minutes"], t["level"]) == (45, 7)                           # 45 minutes: one level harder
