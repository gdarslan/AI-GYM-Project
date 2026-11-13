"""Database connection and tables (SQLite through SQLAlchemy).

The database file lives at data/app.db (not committed). Set GYM_DB_URL to use another database.
"""
import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer, String, create_engine, func, inspect,
                        select)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
EXERCISES_CSV = ROOT / "data" / "processed" / "free_exercise_db.csv"
DB_URL = os.environ.get("GYM_DB_URL", f"sqlite:///{ROOT / 'data' / 'app.db'}")
ROLES = ("user", "admin")


class Base(DeclarativeBase):
    pass


class User(Base):
    """An account. No name or e-mail: a self-chosen username is enough to log in (data minimisation)."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(10), default="user")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Consent (GDPR art. 9: workout and body data can count as health data, so explicit consent is required)
    consent_health_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_ai_coach: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Training profile: empty for an admin-only account
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(15), nullable=True)

    workouts: Mapped[list["Workout"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def has_profile(self) -> bool:
        return self.goal is not None


class AuthSession(Base):
    """A login. Only the SHA-256 hash of the token is stored."""
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user: Mapped[User] = relationship(back_populates="sessions")


class AuditLog(Base):
    """Admin actions and account events. Stores usernames, never training data."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime)
    actor: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(60), default="")


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


def make_engine(url: str = DB_URL):
    if url == "sqlite://":       # in-memory (tests): one shared connection, or each request sees an empty db
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, connect_args={"check_same_thread": False})


def backup_outdated_db(engine) -> Path | None:
    """A database from before logins existed cannot be used: keep it as a backup and start a new one."""
    path = engine.url.database
    if not path or not Path(path).exists():
        return None
    columns = {c["name"] for c in inspect(engine).get_columns("users")} if inspect(engine).has_table("users") else None
    if columns is None or "password_hash" in columns:
        return None
    engine.dispose()
    backup = Path(path).with_name(f"app_backup_before_login_{datetime.now():%Y%m%d_%H%M%S}.db")
    Path(path).rename(backup)
    return backup


def init_db(engine, exercises_csv: Path = EXERCISES_CSV) -> None:
    """Create the tables and load the exercise library once."""
    backup = backup_outdated_db(engine)
    if backup:
        print(f"Old database without logins moved to {backup}; a new one is created.")
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
