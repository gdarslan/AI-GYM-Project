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
