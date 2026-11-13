"""Request and response shapes. Input checks live here, so impossible values never reach the database."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Gender = Literal["male", "female", "other"]
Goal = Literal["build muscle", "get stronger", "lose fat", "general fitness"]
Experience = Literal["beginner", "intermediate", "advanced"]


class UserIn(BaseModel):
    age: int = Field(ge=16, le=100)
    gender: Gender
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    goal: Goal
    experience: Experience


class UserOut(UserIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


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


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    primary_muscles: str
    secondary_muscles: str
    equipment: str
