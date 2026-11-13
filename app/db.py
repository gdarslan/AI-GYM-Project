"""Database connection and tables (SQLite through SQLAlchemy).

The database file lives at data/app.db (not committed). Set GYM_DB_URL to use another database.
"""
import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
EXERCISES_CSV = ROOT / "data" / "processed" / "free_exercise_db.csv"
DB_URL = os.environ.get("GYM_DB_URL", f"sqlite:///{ROOT / 'data' / 'app.db'}")


class Base(DeclarativeBase):
    pass


class User(Base):
    """No name or e-mail: the app only stores what the progress analysis and coach need."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(10))
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    goal: Mapped[str] = mapped_column(String(30))
    experience: Mapped[str] = mapped_column(String(15))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    workouts: Mapped[list["Workout"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Exercise(Base):
    """Exercise library, loaded from free-exercise-db (data/processed/free_exercise_db.csv)."""
    __tablename__ = "exercises"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    primary_muscles: Mapped[str] = mapped_column(String(200))
    secondary_muscles: Mapped[str] = mapped_column(String(200), default="")
    equipment: Mapped[str] = mapped_column(String(50), default="")
    level: Mapped[str] = mapped_column(String(20), default="")
    category: Mapped[str] = mapped_column(String(30), default="")


class Workout(Base):
    __tablename__ = "workouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user: Mapped[User] = relationship(back_populates="workouts")
    sets: Mapped[list["WorkoutSet"]] = relationship(back_populates="workout", cascade="all, delete-orphan",
                                                    order_by="WorkoutSet.set_number")


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"))
    set_number: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float] = mapped_column(Float)
    workout: Mapped[Workout] = relationship(back_populates="sets")
    exercise: Mapped[Exercise] = relationship()


def make_engine(url: str = DB_URL, **kwargs):
    return create_engine(url, connect_args={"check_same_thread": False}, **kwargs)


def init_db(engine, exercises_csv: Path = EXERCISES_CSV) -> None:
    """Create the tables and load the exercise library once."""
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    with Session() as s:
        if s.scalar(select(func.count()).select_from(Exercise)):
            return
        if not Path(exercises_csv).exists():
            raise FileNotFoundError(f"{exercises_csv} is missing. Run: python -m src.build_processed")
        df = pd.read_csv(exercises_csv, keep_default_na=False)
        s.add_all(Exercise(id=r.exercise_id, name=r.name, primary_muscles=r.primary_muscles,
                           secondary_muscles=r.secondary_muscles, equipment=r.equipment,
                           level=r.level, category=r.category) for r in df.itertuples())
        s.commit()
