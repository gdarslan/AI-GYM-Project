"""Request and response shapes. Input checks live here, so impossible values never reach the database."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Gender = Literal["male", "female", "other"]
Goal = Literal["build muscle", "get stronger", "lose fat", "general fitness"]
Experience = Literal["beginner", "intermediate", "advanced"]
Role = Literal["user", "admin"]
USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,30}$"
CONSENT_VERSION = "1.0"          # bump when the privacy notice changes, so users can be asked again


# ---------------- profile and accounts ----------------
class ProfileIn(BaseModel):
    age: int = Field(ge=16, le=100)
    gender: Gender
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    goal: Goal
    experience: Experience


class RegisterIn(ProfileIn):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(max_length=128)
    consent_health_data: bool          # required: must be true
    consent_ai_coach: bool = False     # optional


class LoginIn(BaseModel):
    username: str = Field(max_length=30)
    password: str = Field(max_length=128)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)


class PasswordConfirmIn(BaseModel):
    password: str = Field(max_length=128)


class ConsentIn(BaseModel):
    ai_coach: bool


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: Role
    is_demo: bool
    created_at: datetime | None
    consent_health_at: datetime | None
    consent_ai_coach: bool
    consent_version: str | None
    age: int | None
    gender: Gender | None
    height_cm: float | None
    weight_kg: float | None
    goal: Goal | None
    experience: Experience | None


class TokenOut(BaseModel):
    token: str
    expires_at: datetime
    user: MeOut


# ---------------- workouts ----------------
class SetIn(BaseModel):
    exercise_id: str
    reps: int = Field(ge=1, le=100)
    weight_kg: float = Field(ge=0, le=500)    # 0 = bodyweight


class WorkoutIn(BaseModel):
    date: date
    duration_min: int | None = Field(default=None, ge=1, le=300)
    rpe: int | None = Field(default=None, ge=1, le=10)
    sets: list[SetIn] = Field(min_length=1, max_length=100)

    @field_validator("date")
    @classmethod
    def not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("workout date cannot be in the future")
        return v


class SetOut(BaseModel):
    exercise_id: str
    exercise: str
    set_number: int
    reps: int
    weight_kg: float


class WorkoutOut(BaseModel):
    id: int
    date: date
    duration_min: int | None
    rpe: int | None
    sets: list[SetOut]
    total_volume_kg: float
    estimated_kcal: int | None          # MET formula, see src/calories.py
    new_records: list[str] = []         # only filled when a workout is logged


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    primary_muscles: str
    secondary_muscles: str
    equipment: str


# ---------------- coach ----------------
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class CoachIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default=[], max_length=20)


class CoachOut(BaseModel):
    answer: str
    model: str
    prompt_version: str
    context: dict                        # exactly what the model was given


# ---------------- admin ----------------
class AccountOut(BaseModel):
    """What an admin sees: account details only, never body or training data."""
    id: int
    username: str
    role: Role
    is_demo: bool
    created_at: datetime | None
    last_login_at: datetime | None
    locked: bool
    workouts: int


class RoleIn(BaseModel):
    role: Role


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    time: datetime
    actor: str
    action: str
    target: str
