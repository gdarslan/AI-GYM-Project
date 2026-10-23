# Data

Raw files live in `data/raw/` and are **not committed** (see `.gitignore`).
A dataset may only be committed once its licence is confirmed to allow redistribution.

| Folder in `data/raw/` | Source | Licence (checked 2026-10-23) | Redistribution allowed? |
|---|---|---|---|
| `fmendes-DAT263x-demos/` | https://www.kaggle.com/datasets/fmendes/fmendesdat263xdemos | **Unknown** – no licence given on Kaggle, and no description of how the data was collected | **No** – keep local only |
| `Gym-Members-Exercise-Dataset/` | https://www.kaggle.com/datasets/valakhorasani/gym-members-exercise-dataset | Apache 2.0 | Yes, with attribution and a copy of the licence |
| `Gym-Exercise-Dataset/` (megaGym) | https://www.kaggle.com/datasets/niharika41298/gym-exercise-data | CC0: Public Domain (the author says it was scraped from various internet sources) | Yes |
| `free-exercise-db/` | https://github.com/yuhonas/free-exercise-db, pinned to commit `f00c92c` (downloaded 2026-10-23 with `python -m src.download_free_exercise_db`) | The Unlicense (public domain) | Yes |

Licences were read from the Kaggle dataset metadata (`licenseName`) and the GitHub repository licence.

**ExerciseDB was dropped (2026-10-23).** It was first used for the muscle mapping, but its terms of use
(https://exercisedb.notion.site/ExerciseDB-API-Terms-of-Use-226983b728ca8090bf7be79564e4b356, read via a search-result
excerpt because the page blocks automated access) say the data belongs to AscendAPI, access is tied to a paid
subscription, and the data may not be stored. A saved snapshot would break those terms, so it was replaced by
free-exercise-db.

None of the raw files are committed yet, including the ones whose licence would allow it.

To reproduce: download each dataset from its source into the folder named above (free-exercise-db: `python -m src.download_free_exercise_db`),
then rebuild `data/processed/` with `python -m src.build_processed`.

## Processed files (`data/processed/`)

| File | Built from | Rows | Used for |
|---|---|---|---|
| `calories_training.csv` | exercise.csv + calories.csv | 15,000 | training the calorie model |
| `gym_members_training_format.csv` | Gym Members | 973 | transfer test (no body temperature) |
| `free_exercise_db.csv` | free-exercise-db | 876 | muscle mapping for the heatmap (main: primary and secondary muscles) |
| `megagym_exercises.csv` | megaGym | 2,909 | muscle mapping (backup: one primary muscle per exercise, same muscle names as the main table) |

Cleaning choices are documented in `src/data_prep.py` and in `notebooks/Sprint-Docs-Notes/`.
