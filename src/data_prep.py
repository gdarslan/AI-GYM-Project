"""Convert raw datasets into the format the calorie model is trained on."""
import pandas as pd

# Column order of the training data (exercise.csv + calories.csv), without User_ID and Body_Temp
TRAINING_COLUMNS = ["Gender", "Age", "Height", "Weight", "Duration", "Heart_Rate", "Calories"]


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
