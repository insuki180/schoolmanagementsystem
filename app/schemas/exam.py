"""Exam schemas."""

from pydantic import BaseModel
from datetime import date, datetime


class ExamCreateRequest(BaseModel):
    name: str
    date: date | None = None


class ExamResponse(BaseModel):
    id: int
    name: str
    school_id: int
    date: date | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
