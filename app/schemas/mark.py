"""Mark schemas."""

from pydantic import BaseModel
from datetime import datetime


class MarkEntry(BaseModel):
    student_id: int
    marks_obtained: float
    max_marks: float = 100.0


class MarkEntryRequest(BaseModel):
    class_id: int
    subject_id: int
    exam_id: int
    entries: list[MarkEntry]


class MarkResponse(BaseModel):
    id: int
    student_id: int
    student_name: str | None = None
    subject_id: int
    subject_name: str | None = None
    exam_id: int
    exam_name: str | None = None
    marks_obtained: float
    max_marks: float
    created_at: datetime | None

    model_config = {"from_attributes": True}
