"""The coach evaluation scores answers against each persona's expected facts, so those facts must be true."""
from datetime import date

import pandas as pd

from src.personas import PERSONAS, cardio_mixed, new_beginner, overtrainer, plateau
from src.progress import consistency, neglected_muscles, next_session_targets, progress_summary

TODAY = date(2026, 11, 9)
LIBRARY = pd.DataFrame([
    ("barbell squat", "quadriceps", "calves; glutes; hamstrings; lower back", "weighted"),
    ("pushups", "chest", "shoulders; triceps", "bodyweight"),
    ("bent over barbell row", "middle back", "biceps; lats; shoulders", "weighted"),
    ("barbell bench press - medium grip", "chest", "shoulders; triceps", "weighted"),
    ("standing military press", "shoulders", "triceps", "weighted"),
    ("romanian deadlift", "hamstrings", "calves; glutes; lower back", "weighted"),
    ("triceps pushdown", "triceps", "", "weighted"),
    ("dumbbell flyes", "chest", "", "weighted"),
    ("goblet squat", "quadriceps", "calves; glutes; hamstrings; shoulders", "weighted"),
    ("dumbbell bench press", "chest", "shoulders; triceps", "weighted"),
    ("seated cable rows", "middle back", "biceps; lats; shoulders", "weighted"),
    ("barbell curl", "biceps", "forearms", "weighted"),
    ("leg press", "quadriceps", "calves; glutes; hamstrings", "weighted"),
    ("bicycling, stationary", "quadriceps", "calves; glutes; hamstrings", "cardio"),
    ("rowing, stationary", "quadriceps", "biceps; calves; glutes; hamstrings; lower back; middle back", "cardio"),
    ("plank", "abdominals", "", "timed"),
], columns=["name", "primary_muscles", "secondary_muscles", "kind"])


def analyse(persona):
    p = persona(TODAY)
    log = pd.DataFrame([{"date": w["date"], "duration_s": None, "level": None, **s}
                        for w in p["workouts"] for s in w["sets"]])
    summary = progress_summary(log, LIBRARY, TODAY, body_weight_kg=p["profile"]["weight_kg"])
    targets = {t["exercise"]: t for t in next_session_targets(log, LIBRARY, p["profile"]["goal"], TODAY,
                                                               body_weight_kg=p["profile"]["weight_kg"])}
    return p, summary, targets, log


def test_every_persona_uses_known_exercises():
    for persona in PERSONAS.values():
        names = {s["exercise"] for w in persona(TODAY)["workouts"] for s in w["sets"]}
        assert names <= set(LIBRARY["name"]), names - set(LIBRARY["name"])


def test_new_beginner():
    _, s, t, _ = analyse(new_beginner)
    assert s["workouts"] == 2 and s["enough_data"] is False and neglected_muscles(s) == []
    assert t["barbell squat"]["target"] == "3 × 9 @ 40 kg"
    assert t["pushups"]["target"] == "3 × 11 @ bodyweight"


def test_plateau():
    _, s, t, _ = analyse(plateau)
    stalled = {ex for ex, v in s["strength_trends"].items() if v["trend"] == "stalled"}
    assert stalled == {"barbell squat", "romanian deadlift", "barbell bench press - medium grip",
                       "standing military press", "bent over barbell row"}
    assert t["barbell squat"]["target"] == "3 × 6 @ 90 kg"
    assert t["barbell bench press - medium grip"]["target"] == "3 × 6 @ 72.5 kg"
    assert s["days_since_last_trained"]["abdominals"] is None


def test_overtrainer():
    _, s, _, log = analyse(overtrainer)
    assert s["workouts"] == 14
    assert s["recovery_guideline"]["chest"] == "recovering" and s["recovery_guideline"]["triceps"] == "recovering"
    assert {"quadriceps", "hamstrings", "lats", "middle back"} <= set(neglected_muscles(s))
    assert consistency(log["date"], 3, TODAY)["week_streak"] == 2


def test_cardio_mixed():
    _, s, t, _ = analyse(cardio_mixed)
    assert s["cardio_minutes"] == 280 and s["cardio_sessions"] == 8
    assert t["bicycling, stationary"]["target"] == "45 min @ level 6"
    assert t["rowing, stationary"]["target"] == "35 min @ level 7"
    assert t["plank"]["target"] == "3 × 50 s"
    assert t["goblet squat"]["target"] == "3 × 11 @ 18 kg"
    assert not [ex for ex, v in s["strength_trends"].items() if v["trend"] == "stalled"]
