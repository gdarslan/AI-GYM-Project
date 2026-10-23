"""Download the ExerciseDB v1 exercise list once and save it as a raw CSV.

Source: https://oss.exercisedb.dev/api/v1/exercises (free tier, no API key).
Run from the project root:  python -m src.download_exercisedb
The file is a snapshot: it is not overwritten unless --force is given.
"""
import argparse
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

API_URL = "https://oss.exercisedb.dev/api/v1/exercises"
PAGE_SIZE = 25          # the API returns at most 25 exercises per request
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "ExerciseDB" / "exercisedb_exercises.csv"


def fetch_all(pause_s: float = 1.0) -> list[dict]:
    exercises, after = [], None
    while True:
        url = f"{API_URL}?limit={PAGE_SIZE}" + (f"&after={after}" if after else "")
        # the server rejects Python's default user agent, so name the project instead
        req = urllib.request.Request(url, headers={"User-Agent": "gym-calorie-student-project/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.load(resp)
        exercises += page["data"]
        if not page["meta"]["hasNextPage"]:
            return exercises
        after = page["meta"]["nextCursor"]
        time.sleep(pause_s)  # be polite to the free endpoint


def to_table(exercises: list[dict], download_date: str) -> pd.DataFrame:
    join = "; ".join
    return pd.DataFrame({
        "exercise_id": [e["exerciseId"] for e in exercises],
        "name": [e["name"] for e in exercises],
        "body_parts": [join(e["bodyParts"]) for e in exercises],
        "target_muscles": [join(e["targetMuscles"]) for e in exercises],
        "secondary_muscles": [join(e["secondaryMuscles"]) for e in exercises],
        "equipment": [join(e["equipments"]) for e in exercises],
        "download_date": download_date,
    })


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="overwrite an existing snapshot")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        raise SystemExit(f"{OUT} already exists - the download is a one-off snapshot. Use --force to replace it.")

    exercises = fetch_all()
    table = to_table(exercises, date.today().isoformat())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False)
    print(f"Saved {len(table)} exercises to {OUT}")


if __name__ == "__main__":
    main()
