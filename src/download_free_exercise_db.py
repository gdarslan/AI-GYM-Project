"""Download free-exercise-db once and save it as a raw CSV.

Source: https://github.com/yuhonas/free-exercise-db (The Unlicense - public domain).
The download is pinned to one commit, so the same snapshot can always be fetched again.
Run from the project root:  python -m src.download_free_exercise_db
The file is a snapshot: it is not overwritten unless --force is given.
"""
import argparse
import json
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

COMMIT = "f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5"   # main on 2026-09-27
URL = f"https://raw.githubusercontent.com/yuhonas/free-exercise-db/{COMMIT}/dist/exercises.json"
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "free-exercise-db" / "free_exercise_db.csv"


def fetch() -> list[dict]:
    with urllib.request.urlopen(URL, timeout=60) as resp:
        return json.load(resp)


def to_table(exercises: list[dict], download_date: str) -> pd.DataFrame:
    join = "; ".join
    return pd.DataFrame({
        "exercise_id": [e["id"] for e in exercises],
        "name": [e["name"] for e in exercises],
        "primary_muscles": [join(e["primaryMuscles"]) for e in exercises],
        "secondary_muscles": [join(e["secondaryMuscles"]) for e in exercises],
        "equipment": [e["equipment"] or "" for e in exercises],
        "level": [e["level"] for e in exercises],
        "force": [e["force"] or "" for e in exercises],
        "mechanic": [e["mechanic"] or "" for e in exercises],
        "category": [e["category"] for e in exercises],
        "download_date": download_date,
        "source_commit": COMMIT,
    })


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="overwrite an existing snapshot")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        raise SystemExit(f"{OUT} already exists - the download is a one-off snapshot. Use --force to replace it.")

    table = to_table(fetch(), date.today().isoformat())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False)
    print(f"Saved {len(table)} exercises to {OUT}")


if __name__ == "__main__":
    main()
