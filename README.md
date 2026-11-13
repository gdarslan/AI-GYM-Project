# AI-GYM-Project

A gym-tracking app with a personalised AI coach. Users log workouts; the app calculates their progress
(volume per muscle group, neglected muscles, strength trends), and the AI coach explains it in answer to their
questions. A separate experiment tests whether a trained model predicts calories better than the MET formula.

## Project structure

| Path | Contents |
|---|---|
| `app/main.py` | FastAPI backend: users, exercises, workouts, progress, demo users |
| `app/db.py` | SQLite database tables; loads the exercise library from free-exercise-db |
| `app/schemas.py` | Input validation (impossible values are rejected) |
| `app/streamlit_app.py` | The screens: profile, log workout, history, progress, coach |
| `src/progress.py` | Progress calculations (plain code, no AI): volume, neglected muscles, recovery, strength |
| `src/coach.py` | The AI coach: builds the context, calls the local model (Ollama), logs every answer |
| `prompts/` | Coach prompts, one file per version |
| `src/calories.py` | Calorie estimate with the MET formula |
| `src/personas.py` | Made-up test users with known training patterns |
| `data/` | Raw and processed datasets (not committed), see [data/README.md](data/README.md) |
| `src/download_free_exercise_db.py` | Downloads a pinned snapshot of free-exercise-db into `data/raw/` |
| `src/data_prep.py` | Cleaning and conversion functions for each dataset |
| `src/build_processed.py` | Rebuilds every file in `data/processed/` from `data/raw/` |
| `notebooks/calorie_model_starter.ipynb` | Data inspection, MET-formula baseline, Linear Regression and Random Forest |
| `notebooks/coach_feasibility.ipynb` | Feasibility test of the AI coach with a local model (Ollama) |
| `notebooks/Sprint-Docs-Notes/` | Sprint notes and data notes (Word documents) |
| `tests/` | pytest tests for the data pipeline, progress calculations and API |

## Setup

Requires Python 3.11.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Data

The datasets are not in the repository. Download them and rebuild the processed files as described in
[data/README.md](data/README.md). In short:

```bash
python -m src.download_free_exercise_db   # the Kaggle datasets are downloaded by hand
python -m src.build_processed
```

All commands are run from the project root.

## Run the app

Needs `data/processed/free_exercise_db.csv` (see Data above). On Windows, double-click `start_app.bat`.
Or open two terminals in the project root:

```bash
python -m uvicorn app.main:app --reload          # 1. the API, docs at http://localhost:8000/docs
python -m streamlit run app/streamlit_app.py     # 2. the screens, opens in the browser
```

Click **Demo user** in the sidebar for a made-up user with 4 weeks of training. The database is stored in
`data/app.db` (not committed).

The Coach page needs [Ollama](https://ollama.com) running with the model downloaded once:
`ollama pull llama3.2:3b`. Every coach question and answer is logged to `logs/coach_log.jsonl` (not committed)
for the evaluation.

## Tests

```bash
python -m pytest
```
