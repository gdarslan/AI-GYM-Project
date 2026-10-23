import pandas as pd
import pytest

from src.data_prep import TRAINING_COLUMNS, convert_gym_members


def test_convert_gym_members_units_and_names():
    gym = pd.DataFrame({
        "Age": [56], "Gender": ["Male"], "Weight (kg)": [88.3], "Height (m)": [1.71],
        "Max_BPM": [180], "Avg_BPM": [157], "Resting_BPM": [60],
        "Session_Duration (hours)": [1.5], "Calories_Burned": [1313.0], "Workout_Type": ["Yoga"],
    })
    out = convert_gym_members(gym)

    assert list(out.columns) == TRAINING_COLUMNS
    row = out.iloc[0]
    assert row["Gender"] == "male"
    assert row["Height"] == pytest.approx(171.0)
    assert row["Duration"] == pytest.approx(90.0)
    assert row["Weight"] == 88.3
    assert row["Heart_Rate"] == 157
    assert row["Calories"] == 1313.0


def test_free_exercise_db_download_and_clean():
    from src.data_prep import clean_free_exercise_db
    from src.download_free_exercise_db import to_table

    raw = to_table([
        {"id": "Barbell_Curl", "name": "Barbell Curl", "primaryMuscles": ["biceps"],
         "secondaryMuscles": ["forearms"], "equipment": "barbell", "level": "beginner",
         "force": "pull", "mechanic": "isolation", "category": "strength"},
        {"id": "Ab_Roller", "name": "Ab Roller ", "primaryMuscles": ["abdominals"],
         "secondaryMuscles": ["shoulders", "lats"], "equipment": None, "level": "intermediate",
         "force": None, "mechanic": None, "category": "strength"},
    ], "2026-10-23")
    assert raw.loc[1, "secondary_muscles"] == "shoulders; lats"
    assert raw.loc[1, "equipment"] == ""

    out = clean_free_exercise_db(raw)
    assert list(out["name"]) == ["ab roller", "barbell curl"]          # lowercased, stripped, sorted
    assert "download_date" not in out.columns


def test_megagym_clean_renames_and_drops_ratings():
    from src.data_prep import clean_megagym

    raw = pd.DataFrame({
        "Unnamed: 0": [0, 1, 2], "Title": ["Push-Up", "Push-Up", "Squat"], "Desc": [None, None, "x"],
        "Type": ["Strength"] * 3, "BodyPart": ["Chest", "Chest", "Quadriceps"],
        "Equipment": ["Body Only", "Body Only", None], "Level": ["Beginner"] * 3,
        "Rating": [0.0, 0.0, 8.1], "RatingDesc": [None, None, "Average"],
    })
    out = clean_megagym(raw)
    assert list(out.columns) == ["name", "description", "type", "primary_muscle", "equipment", "level"]
    assert len(out) == 2                                             # exact duplicate dropped
    assert set(out["primary_muscle"]) == {"chest", "quadriceps"}
