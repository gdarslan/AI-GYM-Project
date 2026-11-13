"""Gym Coach API. Run from the project root:  python -m uvicorn app.main:app --reload

Interactive docs: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import DB_URL, EXERCISES_CSV, Exercise, User, Workout, WorkoutSet, init_db, make_engine
from app.schemas import CoachIn, CoachOut, ExerciseOut, SetOut, UserIn, UserOut, WorkoutIn, WorkoutOut
from src import coach
from src.calories import estimate_kcal
from src.personas import PERSONAS
from src.progress import exercise_history, new_records, progress_summary

LOG_COLUMNS = ["date", "exercise", "reps", "weight_kg"]


def create_app(db_url: str = DB_URL, exercises_csv: Path = EXERCISES_CSV, llm: coach.LLMClient | None = None,
               coach_log: Path | None = coach.LOG_FILE) -> FastAPI:
    engine = make_engine(db_url)

    @asynccontextmanager
    async def lifespan(_):
        init_db(engine, exercises_csv)     # tables + exercise library, on startup
        yield

    api = FastAPI(title="AI Gym Coach", lifespan=lifespan)
    api.state.Session = sessionmaker(engine)
    api.state.llm = llm or coach.OllamaClient()
    api.state.coach_log = coach_log
    add_routes(api)
    return api


def get_session(request: Request):
    with request.app.state.Session() as s:
        yield s


def get_user(user_id: int, s: Session) -> User:
    user = s.get(User, user_id)
    if user is None:
        raise HTTPException(404, f"User {user_id} not found")
    return user


def workout_out(w: Workout, records: list[str] | None = None) -> WorkoutOut:
    return WorkoutOut(id=w.id, date=w.date, duration_min=w.duration_min, rpe=w.rpe,
                      sets=[SetOut(exercise_id=st.exercise_id, exercise=st.exercise.name, set_number=st.set_number,
                                   reps=st.reps, weight_kg=st.weight_kg) for st in w.sets],
                      total_volume_kg=sum(st.reps * st.weight_kg for st in w.sets),
                      estimated_kcal=estimate_kcal(w.user.weight_kg, w.duration_min, w.rpe),
                      new_records=records or [])


def set_rows(workouts) -> pd.DataFrame:
    """One row per set, the input format of src/progress.py."""
    return pd.DataFrame([{"date": w.date, "exercise": st.exercise.name, "reps": st.reps, "weight_kg": st.weight_kg}
                         for w in workouts for st in w.sets], columns=LOG_COLUMNS)


def user_progress(s: Session, user: User, today: date | None = None, weeks: int = 4) -> dict:
    log = set_rows(user.workouts)
    exercises = pd.DataFrame(
        [(e.name, e.primary_muscles, e.secondary_muscles)
         for e in s.scalars(select(Exercise).where(Exercise.name.in_(set(log["exercise"]))))],
        columns=["name", "primary_muscles", "secondary_muscles"])
    return progress_summary(log, exercises, today or date.today(), weeks)


def add_workout(s: Session, user: User, data: WorkoutIn) -> Workout:
    ids = {st.exercise_id for st in data.sets}
    known = set(s.scalars(select(Exercise.id).where(Exercise.id.in_(ids))))
    if ids - known:
        raise HTTPException(422, f"Unknown exercise ids: {sorted(ids - known)}")
    workout = Workout(user=user, date=data.date, duration_min=data.duration_min, rpe=data.rpe,
                      sets=[WorkoutSet(exercise_id=st.exercise_id, set_number=i + 1, reps=st.reps,
                                       weight_kg=st.weight_kg) for i, st in enumerate(data.sets)])
    s.add(workout)
    return workout


def add_routes(api: FastAPI) -> None:
    @api.get("/health")
    def health():
        return {"status": "ok"}

    # ---- users ----
    @api.post("/users", response_model=UserOut, status_code=201)
    def create_user(data: UserIn, s: Session = Depends(get_session)):
        user = User(**data.model_dump())
        s.add(user)
        s.commit()
        return user

    @api.get("/users", response_model=list[UserOut])
    def list_users(s: Session = Depends(get_session)):
        return s.scalars(select(User).order_by(User.id)).all()

    @api.get("/users/{user_id}", response_model=UserOut)
    def read_user(user_id: int, s: Session = Depends(get_session)):
        return get_user(user_id, s)

    @api.put("/users/{user_id}", response_model=UserOut)
    def update_user(user_id: int, data: UserIn, s: Session = Depends(get_session)):
        user = get_user(user_id, s)
        for field, value in data.model_dump().items():
            setattr(user, field, value)
        s.commit()
        return user

    @api.delete("/users/{user_id}", status_code=204)
    def delete_user(user_id: int, s: Session = Depends(get_session)):
        """Right to erasure: removes the user with all their workouts and sets."""
        s.delete(get_user(user_id, s))
        s.commit()

    # ---- exercises ----
    @api.get("/exercises", response_model=list[ExerciseOut])
    def search_exercises(search: str = "", limit: int = 20, s: Session = Depends(get_session)):
        q = select(Exercise).order_by(Exercise.name).limit(min(limit, 100))
        for word in search.lower().split():
            q = q.where(or_(Exercise.name.contains(word), Exercise.primary_muscles.contains(word)))
        return s.scalars(q).all()

    # ---- workouts ----
    @api.post("/users/{user_id}/workouts", response_model=WorkoutOut, status_code=201)
    def log_workout(user_id: int, data: WorkoutIn, s: Session = Depends(get_session)):
        user = get_user(user_id, s)
        earlier = set_rows([w for w in user.workouts if w.date < data.date])
        workout = add_workout(s, user, data)
        s.commit()
        return workout_out(workout, new_records(earlier, set_rows([workout])))

    @api.get("/users/{user_id}/workouts", response_model=list[WorkoutOut])
    def list_workouts(user_id: int, s: Session = Depends(get_session)):
        user = get_user(user_id, s)
        return [workout_out(w) for w in sorted(user.workouts, key=lambda w: w.date, reverse=True)]

    @api.delete("/users/{user_id}/workouts/{workout_id}", status_code=204)
    def delete_workout(user_id: int, workout_id: int, s: Session = Depends(get_session)):
        workout = s.get(Workout, workout_id)
        if workout is None or workout.user_id != user_id:
            raise HTTPException(404, "Workout not found")
        s.delete(workout)
        s.commit()

    # ---- progress ----
    @api.get("/users/{user_id}/progress")
    def progress(user_id: int, today: date | None = None, weeks: int = 4, s: Session = Depends(get_session)):
        return user_progress(s, get_user(user_id, s), today, weeks)

    @api.get("/users/{user_id}/exercise-history/{exercise_id}")
    def history_of_exercise(user_id: int, exercise_id: str, s: Session = Depends(get_session)):
        """Every session of one exercise, oldest first: sets, best estimated 1RM and volume."""
        user = get_user(user_id, s)
        exercise = s.get(Exercise, exercise_id)
        if exercise is None:
            raise HTTPException(404, "Exercise not found")
        return exercise_history(set_rows(user.workouts), exercise.name)

    # ---- AI coach ----
    @api.post("/users/{user_id}/coach", response_model=CoachOut)
    def ask_coach(user_id: int, data: CoachIn, request: Request, s: Session = Depends(get_session)):
        """The code calculates the progress; the language model explains it. No personal details are sent."""
        user = get_user(user_id, s)
        context = coach.build_context(user.goal, user.experience, user_progress(s, user))
        llm = request.app.state.llm
        try:
            answer = coach.ask(data.question, context, llm, [t.model_dump() for t in data.history],
                               log_file=request.app.state.coach_log)
        except coach.CoachUnavailable as e:
            raise HTTPException(503, str(e))
        return CoachOut(answer=answer, model=llm.model, prompt_version=coach.PROMPT_VERSION, context=context)

    # ---- privacy ----
    @api.get("/users/{user_id}/export")
    def export_user(user_id: int, s: Session = Depends(get_session)):
        """Right of access: everything the app stores about this user, as JSON."""
        user = get_user(user_id, s)
        return {"exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "profile": UserOut.model_validate(user).model_dump(),
                "workouts": [workout_out(w).model_dump(mode="json", exclude={"new_records"})
                             for w in sorted(user.workouts, key=lambda w: w.date)]}

    # ---- demo data ----
    @api.post("/demo-users/{persona}", response_model=UserOut, status_code=201)
    def create_demo_user(persona: str, s: Session = Depends(get_session)):
        """Creates a made-up user with 4 weeks of workouts (see src/personas.py)."""
        if persona not in PERSONAS:
            raise HTTPException(404, f"Unknown persona. Options: {sorted(PERSONAS)}")
        p = PERSONAS[persona]()
        names = {st["exercise"] for w in p["workouts"] for st in w["sets"]}
        ids = {e.name: e.id for e in s.scalars(select(Exercise).where(Exercise.name.in_(names)))}
        user = User(**p["profile"])
        s.add(user)
        for w in p["workouts"]:
            add_workout(s, user, WorkoutIn(
                date=w["date"], duration_min=w["duration_min"], rpe=w["rpe"],
                sets=[{"exercise_id": ids[st["exercise"]], "reps": st["reps"], "weight_kg": st["weight_kg"]}
                      for st in w["sets"]]))
        s.commit()
        return user


app = create_app()
