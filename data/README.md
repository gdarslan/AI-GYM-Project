# Data

Raw files live in `data/raw/` and processed files in `data/processed/`. Neither is committed (see `.gitignore`):
processed files are rebuilt from the raw files by code, and a raw dataset may only be committed once its licence
is confirmed to allow redistribution. No raw files are committed yet, including the ones whose licence would allow it.

## Raw datasets (`data/raw/`)

| Folder | Expected files | Source | Licence (checked 2026-10-23) | Redistribution allowed? |
|---|---|---|---|---|
| `fmendes-DAT263x-demos/` | `exercise.csv`, `calories.csv` | [Kaggle: fmendes/fmendesdat263xdemos](https://www.kaggle.com/datasets/fmendes/fmendesdat263xdemos) | **Unknown**: no licence is given on Kaggle, and there is no description of how the data was collected | **No**, keep local only |
| `Gym-Members-Exercise-Dataset/` | `gym_members_exercise_tracking.csv` | [Kaggle: valakhorasani/gym-members-exercise-dataset](https://www.kaggle.com/datasets/valakhorasani/gym-members-exercise-dataset) | Apache 2.0 | Yes, with attribution and a copy of the licence |
| `Gym-Exercise-Dataset/` (megaGym) | `megaGymDataset.csv` | [Kaggle: niharika41298/gym-exercise-data](https://www.kaggle.com/datasets/niharika41298/gym-exercise-data) | CC0: Public Domain (the author says it was scraped from various internet sources) | Yes |
| `free-exercise-db/` | `free_exercise_db.csv` | [GitHub: yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db), pinned to commit `f00c92c` | The Unlicense (public domain) | Yes |

Licences were read from the Kaggle dataset metadata (`licenseName`) and from the GitHub repository licence.

### Why ExerciseDB is not used

ExerciseDB was first used for the muscle mapping and was dropped on 2026-10-23. Its
[terms of use](https://exercisedb.notion.site/ExerciseDB-API-Terms-of-Use-226983b728ca8090bf7be79564e4b356)
say the data belongs to AscendAPI, access is tied to a paid subscription, and the data may not be stored, so keeping a
saved snapshot would break them. (The terms were read from a search-result excerpt because the page blocks automated
access.) free-exercise-db replaces it.

## Reproducing the data

Run from the project root:

1. Download the three Kaggle datasets and unzip each into the folder named in the table above.
2. Download free-exercise-db: `python -m src.download_free_exercise_db`.
   It saves a one-off snapshot and refuses to overwrite it unless `--force` is given.
3. Build the processed files: `python -m src.build_processed`.
   The output depends only on the raw files, so running it again gives identical files.

## Processed files (`data/processed/`)

| File | Built from | Rows | Used for |
|---|---|---|---|
| `calories_training.csv` | `exercise.csv` + `calories.csv` | 15,000 | Training the calorie models (secondary experiment) |
| `gym_members_training_format.csv` | Gym Members | 973 | Transfer test (has no body temperature) |
| `free_exercise_db.csv` | free-exercise-db | 876 | The app's exercise library and muscle mapping for the progress analysis (primary and secondary muscles) |
| `megagym_exercises.csv` | megaGym | 2,909 | Exercise descriptions in the app (190 library exercises with the same name) and backup muscle mapping |

The cleaning choices are documented in `src/data_prep.py` and in `notebooks/Sprint-Docs-Notes/`.
