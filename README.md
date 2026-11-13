# AI-GYM-Project

A gym-tracking app with a personalised AI coach. Users log workouts; the app calculates their progress
(volume per muscle group, neglected muscles, strength trends), and the AI coach explains it in answer to their
questions. A separate experiment tests whether a trained model predicts calories better than the MET formula.

## Project structure

| Path | Contents |
|---|---|
| `app/main.py` | FastAPI backend: login, my account and data, workouts, progress, coach, admin |
| `app/db.py` | SQLite tables: accounts, sessions, audit log, workouts, exercises, coach conversations, messages and feedback |
| `app/security.py` | Password hashing (PBKDF2), password rules and session tokens |
| `app/schemas.py` | Input validation (impossible values are rejected) |
| `app/streamlit_app.py` | The screens: login, progress, log workout, history, coach, profile, privacy, admin |
| `app/ui.py`, `app/assets/` | The look: red-and-black theme, logo, banner and the muscle body map (all drawn as SVG) |
| `app/create_admin.py` | Command to create the first admin |
| `src/progress.py` | Progress calculations (plain code, no AI): volume, neglected muscles, recovery, strength, next-session targets, weekly streak. Exercises are logged by kind, worked out from free-exercise-db's category and equipment: weights (sets × reps × kg), bodyweight (sets × reps, ≈65% of body weight counts as load), holds and stretches (sets × seconds) and cardio (minutes at a level) |
| `src/coach.py` | The AI coach: builds the context, calls the local model (Ollama), logs every answer |
| `prompts/` | Coach prompts, one file per version (v1 numbers only, v2 + key findings, v3 + next-session targets, consistency and a rule for users with little data; v3 is used) |
| `src/calories.py` | Calorie estimate with the MET formula |
| `src/personas.py` | Made-up test users with known training patterns |
| `data/` | Raw and processed datasets (not committed), see [data/README.md](data/README.md) |
| `src/download_free_exercise_db.py` | Downloads a pinned snapshot of free-exercise-db into `data/raw/` |
| `src/data_prep.py` | Cleaning and conversion functions for each dataset |
| `src/build_processed.py` | Rebuilds every file in `data/processed/` from `data/raw/` |
| `notebooks/calorie_model_starter.ipynb` | Data inspection, MET-formula baseline, Linear Regression and Random Forest |
| `notebooks/coach_feasibility.ipynb` | Feasibility test of the AI coach with a local model (Ollama) |
| `notebooks/Sprint-Docs-Notes/` | Sprint notes and data notes (Word documents) |
| `tests/` | pytest tests for the data pipeline, progress calculations, API, login, privacy rules and admin rights |
| `documents/` | Project reports (Word) |
| `start_app.bat` | Starts the API and the screens with one double-click (Windows) |

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

The app opens on a login screen: create an account, log in, or **Try the demo** (a made-up user with 4 weeks of
training, deleted at logout). The database is stored in `data/app.db` (not committed).

**Admin:** there is no way to become admin through the website. Create the first admin on this computer with
`python -m app.create_admin` (it can also promote an existing account); admins can then promote others on the
Admin page. Admins manage accounts but cannot see anyone's workouts or body data.

**Privacy and security:** explicit consent for training data at sign-up and a separate, optional consent for the
AI coach; download and delete your data on the *Privacy & account* page; passwords hashed with PBKDF2-SHA256
(600,000 rounds); session tokens stored hashed and valid for 8 hours; 5 wrong passwords lock an account for
15 minutes; admin actions in an audit log; the app is only reachable from this computer (`.streamlit/config.toml`,
and the API listens on localhost).

The Coach page needs [Ollama](https://ollama.com) running with the model downloaded once:
`ollama pull llama3.2:3b`. Conversations are saved per account with the model, prompt version, response time and the
exact data the model was given, and users can rate each answer. Admins see only totals per model and prompt version
(*Coach quality* on the Admin page). Conversations are deleted with the account.

## Tests

```bash
python -m pytest
```
