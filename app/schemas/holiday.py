"""Holiday request schemas."""

from datetime import date

from pydantic import BaseModel, Field


class HolidayCreateRequest(BaseModel):
    school_id: int
    class_id: int | None = None
    date: date | None = None
    dates: list[date] = Field(default_factory=list)
    title: str
    description: str | None = None
    recurring_weeks: int = Field(default=0, ge=0)
