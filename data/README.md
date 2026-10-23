# Data

Raw files live in `data/raw/` and are **not committed** (see `.gitignore`).
A dataset may only be committed once its licence is confirmed to allow redistribution.

| Folder in `data/raw/` | Source | Licence (checked 2026-10-23) | Redistribution allowed? |
|---|---|---|---|
| `fmendes-DAT263x-demos/` | https://www.kaggle.com/datasets/fmendes/fmendesdat263xdemos | **Unknown** – no licence given on Kaggle, and no description of how the data was collected | **No** – keep local only |
| `Gym-Members-Exercise-Dataset/` | https://www.kaggle.com/datasets/valakhorasani/gym-members-exercise-dataset | Apache 2.0 | Yes, with attribution and a copy of the licence |
| `Gym-Exercise-Dataset/` (megaGym) | https://www.kaggle.com/datasets/niharika41298/gym-exercise-data | CC0: Public Domain (the author says it was scraped from various internet sources) | Yes |
| `ExerciseDB/` | https://oss.exercisedb.dev/api/v1/exercises (downloaded 2026-10-23 with `python -m src.download_exercisedb`) | API code: AGPL-3.0. Data: covered by separate terms of use (https://dub.sh/exercisedb-api-tos), which could not be retrieved automatically – **check by hand** | **No** until the terms are checked |

Licences were read from the Kaggle dataset metadata (`licenseName`) and the ExerciseDB repository.
None of the raw files are committed yet, including the ones whose licence would allow it.

To reproduce: download each dataset from its source into the folder named above (ExerciseDB: `python -m src.download_exercisedb`),
then rebuild `data/processed/` with `python -m src.build_processed`.

## Processed files (`data/processed/`)

| File | Built from | Rows | Used for |
|---|---|---|---|
| `calories_training.csv` | exercise.csv + calories.csv | 15,000 | training the calorie model |
| `gym_members_training_format.csv` | Gym Members | 973 | transfer test (no body temperature) |
| `exercisedb_exercises.csv` | ExerciseDB | 1,290 | muscle mapping for the heatmap (main) |
| `megagym_exercises.csv` | megaGym | 2,909 | muscle mapping (backup: one primary muscle per exercise, no secondary muscles) |

Cleaning choices are documented in `src/data_prep.py` and in `notebooks/Sprint-Docs-Notes/`.
