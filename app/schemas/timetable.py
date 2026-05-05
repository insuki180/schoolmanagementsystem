"""Timetable request schemas."""

from datetime import time

from pydantic import BaseModel, Field


class TimetableSlotCreateRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    period_number: int = Field(ge=1)
    subject_name: str
    teacher_id: int
    start_time: time
    end_time: time
