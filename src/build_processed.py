"""Rebuild every file in data/processed/ from the raw files in data/raw/.

Run from the project root:  python -m src.build_processed
The output only depends on the raw files, so running it again gives identical files.
"""
from pathlib import Path

import pandas as pd

from src.data_prep import clean_exercisedb, convert_gym_members, load_training_data

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def build(raw_dir: Path = RAW, out_dir: Path = PROCESSED) -> dict[str, pd.DataFrame]:
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    tables = {
        "calories_training.csv": load_training_data(raw_dir),
        "gym_members_training_format.csv": convert_gym_members(
            pd.read_csv(raw_dir / "Gym-Members-Exercise-Dataset" / "gym_members_exercise_tracking.csv")),
        "exercisedb_exercises.csv": clean_exercisedb(
            pd.read_csv(raw_dir / "ExerciseDB" / "exercisedb_exercises.csv", keep_default_na=False)),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=False, lineterminator="\n")
    return tables


if __name__ == "__main__":
    for name, table in build().items():
        print(f"{name:35s} {table.shape[0]:>6} rows x {table.shape[1]} columns")
