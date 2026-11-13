"""Gym Coach API. Run from the project root:  uvicorn app.main:app --reload

Interactive docs: http://localhost:8000/docs
"""
from datetime import date

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import DB_URL, Exercise, User, Workout, WorkoutSet, init_db, make_engine
from app.schemas import ExerciseOut, SetOut, UserIn, UserOut, WorkoutIn, WorkoutOut
from src.personas import PERSONAS
from src.progress import progress_summary


def create_app(db_url: str = DB_URL, engine=None) -> FastAPI:
    engine = engine or make_engine(db_url)
    init_db(engine)
    api = FastAPI(title="AI Gym Coach")
    api.state.Session = sessionmaker(engine)
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


def workout_out(w: Workout) -> WorkoutOut:
    return WorkoutOut(id=w.id, date=w.date, duration_min=w.duration_min, rpe=w.rpe,
                      sets=[SetOut(exercise_id=st.exercise_id, exercise=st.exercise.name, set_number=st.set_number,
                                   reps=st.reps, weight_kg=st.weight_kg) for st in w.sets])


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
        workout = add_workout(s, get_user(user_id, s), data)
        s.commit()
        return workout_out(workout)

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
        user = get_user(user_id, s)
        rows = [{"date": w.date, "exercise": st.exercise.name, "reps": st.reps, "weight_kg": st.weight_kg}
                for w in user.workouts for st in w.sets]
        log = pd.DataFrame(rows, columns=["date", "exercise", "reps", "weight_kg"])
        exercises = pd.DataFrame(
            [(e.name, e.primary_muscles, e.secondary_muscles)
             for e in s.scalars(select(Exercise).where(Exercise.name.in_(set(log["exercise"]))))],
            columns=["name", "primary_muscles", "secondary_muscles"])
        return progress_summary(log, exercises, today or date.today(), weeks)

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
