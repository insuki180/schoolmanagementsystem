"""Attendance schemas."""

from pydantic import BaseModel
from datetime import date, datetime


class AttendanceMarkRequest(BaseModel):
    class_id: int
    date: date
    absent_student_ids: list[int] = []


class AttendanceRecord(BaseModel):
    id: int
    student_id: int
    student_name: str | None = None
    date: date
    is_present: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}
