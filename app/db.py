"""Database connection and tables (SQLite through SQLAlchemy).

The database file lives at data/app.db (not committed). Set GYM_DB_URL to use another database.
"""
import os
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, create_engine,
                        func, inspect, select, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from src.progress import exercise_kind

ROOT = Path(__file__).resolve().parents[1]
EXERCISES_CSV = ROOT / "data" / "processed" / "free_exercise_db.csv"
DESCRIPTIONS_CSV = ROOT / "data" / "processed" / "megagym_exercises.csv"     # descriptions (CC0)
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
    weekly_target: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)   # training days a week

    workouts: Mapped[list["Workout"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["CoachConversation"]] = relationship(back_populates="user",
                                                                    cascade="all, delete-orphan")

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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)     # from megaGym where the name matches

    @property
    def kind(self) -> str:
        """weighted, bodyweight, timed or cardio: how the exercise is logged (see src/progress.py)."""
        return exercise_kind(self.name, self.category, self.equipment)


class Workout(Base):
    __tablename__ = "workouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    focus: Mapped[str | None] = mapped_column(String(80), nullable=True)      # e.g. "chest, arms"
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
    reps: Mapped[int] = mapped_column(Integer)                              # 0 for timed exercises and cardio
    weight_kg: Mapped[float] = mapped_column(Float)                         # extra weight for bodyweight exercises
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)  # holds and cardio
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)       # cardio, 1-10
    workout: Mapped[Workout] = relationship(back_populates="sets")
    exercise: Mapped[Exercise] = relationship()


class CoachConversation(Base):
    """One chat with the AI coach. Deleted with the account."""
    __tablename__ = "coach_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    title: Mapped[str] = mapped_column(String(120))                        # the first question
    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["CoachMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan",
                                                          order_by="CoachMessage.id")


class CoachMessage(Base):
    """A question or an answer. Answers keep what is needed to trace and compare them: the model, the prompt
    version, how long it took, and exactly what the model was given (no personal details are in it)."""
    __tablename__ = "coach_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("coach_conversations.id"), index=True)
    time: Mapped[datetime] = mapped_column(DateTime)
    role: Mapped[str] = mapped_column(String(10))                          # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON
    conversation: Mapped[CoachConversation] = relationship(back_populates="messages")
    feedback: Mapped["CoachFeedback | None"] = relationship(back_populates="message", cascade="all, delete-orphan",
                                                            uselist=False)


class CoachFeedback(Base):
    """A user's rating of one answer: real-use evidence of how good the coach is."""
    __tablename__ = "coach_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("coach_messages.id"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)                           # +1 helpful, -1 not helpful
    reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    message: Mapped[CoachMessage] = relationship(back_populates="feedback")


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


# Columns added after the first release: (table, column, SQL type). New columns are always optional, so existing
# rows stay valid and no data has to be moved.
ADDED_COLUMNS = [("workouts", "start_time", "TIME"), ("workouts", "focus", "VARCHAR(80)"),
                 ("exercises", "description", "TEXT"), ("users", "weekly_target", "INTEGER"),
                 ("workout_sets", "duration_s", "INTEGER"), ("workout_sets", "level", "INTEGER")]


def add_missing_columns(engine) -> list[str]:
    """Bring an existing database up to date without losing its data."""
    added = []
    with engine.begin() as conn:
        for table, column, sql_type in ADDED_COLUMNS:
            if not inspect(conn).has_table(table):
                continue
            existing = {c["name"] for c in inspect(conn).get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
                added.append(f"{table}.{column}")
    return added


def load_descriptions(s, descriptions_csv: Path | None = DESCRIPTIONS_CSV) -> int:
    """Copy megaGym descriptions onto library exercises with the same name, once. Returns how many."""
    if not descriptions_csv or not Path(descriptions_csv).exists():
        return 0
    if s.scalar(select(func.count()).select_from(Exercise).where(Exercise.description.is_not(None))):
        return 0
    mg = pd.read_csv(descriptions_csv, keep_default_na=False)
    mg = mg[mg["description"].str.len() > 20].drop_duplicates("name")
    texts = dict(zip(mg["name"], mg["description"]))
    count = 0
    for e in s.scalars(select(Exercise).where(Exercise.name.in_(list(texts)))):
        e.description = texts[e.name]
        count += 1
    s.commit()
    return count


def init_db(engine, exercises_csv: Path = EXERCISES_CSV, descriptions_csv: Path | None = DESCRIPTIONS_CSV) -> None:
    """Create the tables, update older databases, and load the exercise library once."""
    backup = backup_outdated_db(engine)
    if backup:
        print(f"Old database without logins moved to {backup}; a new one is created.")
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    Session = sessionmaker(engine)
    with Session() as s:
        if s.scalar(select(func.count()).select_from(Exercise)):
            load_descriptions(s, descriptions_csv)
            return
        if not Path(exercises_csv).exists():
            raise FileNotFoundError(f"{exercises_csv} is missing. Run: python -m src.build_processed")
        df = pd.read_csv(exercises_csv, keep_default_na=False)
        s.add_all(Exercise(id=r.exercise_id, name=r.name, primary_muscles=r.primary_muscles,
                           secondary_muscles=r.secondary_muscles, equipment=r.equipment,
                           level=r.level, category=r.category) for r in df.itertuples())
        s.commit()
        load_descriptions(s, descriptions_csv)
