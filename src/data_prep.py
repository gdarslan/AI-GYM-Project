"""Convert raw datasets into the format the calorie model is trained on."""
from pathlib import Path

import pandas as pd

# Column order of the training data (exercise.csv + calories.csv), without User_ID and Body_Temp
TRAINING_COLUMNS = ["Gender", "Age", "Height", "Weight", "Duration", "Heart_Rate", "Calories"]


def load_training_data(raw_dir: Path) -> pd.DataFrame:
    """exercise.csv + calories.csv joined 1-to-1 on User_ID, Gender in lowercase.

    All rows are kept: there are no missing or impossible values, and the outliers are
    realistic (see Sprint 2 data notes). Body_Temp is kept here; models choose their features.
    """
    folder = Path(raw_dir) / "fmendes-DAT263x-demos"
    df = pd.read_csv(folder / "exercise.csv").merge(
        pd.read_csv(folder / "calories.csv"), on="User_ID", how="inner", validate="one_to_one")
    df["Gender"] = df["Gender"].str.lower()
    return df[["User_ID", *TRAINING_COLUMNS[:-1], "Body_Temp", "Calories"]]


def convert_gym_members(gym: pd.DataFrame) -> pd.DataFrame:
    """Gym Members -> training format: units in cm / kg / minutes, training column names.

    Gym Members has no body temperature, so the result has no Body_Temp column.
    """
    out = pd.DataFrame({
        "Gender": gym["Gender"].str.lower(),
        "Age": gym["Age"],
        "Height": (gym["Height (m)"] * 100).round(1),          # m -> cm
        "Weight": gym["Weight (kg)"],
        "Duration": (gym["Session_Duration (hours)"] * 60).round(1),  # hours -> minutes
        "Heart_Rate": gym["Avg_BPM"],                          # average over the session
        "Calories": gym["Calories_Burned"],
    })
    return out[TRAINING_COLUMNS]


def clean_exercisedb(raw: pd.DataFrame) -> pd.DataFrame:
    """ExerciseDB snapshot -> one row per distinct exercise.

    Names are lowercased (the API mixes "Band Leg Extension" and "band leg extension"), and
    rows that are identical apart from exercise_id are dropped, keeping the first by id.
    """
    df = raw.copy()
    df["name"] = df["name"].str.strip().str.lower()
    content = ["name", "body_parts", "target_muscles", "secondary_muscles", "equipment"]
    df = df.sort_values("exercise_id").drop_duplicates(subset=content, keep="first")
    return df.sort_values(["name", "exercise_id"]).reset_index(drop=True)


def clean_megagym(raw: pd.DataFrame) -> pd.DataFrame:
    """megaGym -> backup muscle table: one primary muscle per exercise (no secondary muscles).

    `BodyPart` actually holds the primary muscle (e.g. Quadriceps, Lats), so it is renamed.
    The rating columns are dropped: 65% missing, many 0s, and "Average" is given even to 0 ratings.
    Exact duplicate rows (9) are dropped. Missing equipment (32 rows) and descriptions are left empty.
    """
    df = raw.drop(columns=["Unnamed: 0", "Rating", "RatingDesc"]).rename(columns={
        "Title": "name", "Desc": "description", "Type": "type", "BodyPart": "primary_muscle",
        "Equipment": "equipment", "Level": "level"})
    for col in ["name", "type", "primary_muscle", "equipment", "level"]:
        df[col] = df[col].str.strip().str.lower()
    df = df.drop_duplicates()
    return df.sort_values(["name", "primary_muscle"]).reset_index(drop=True)
