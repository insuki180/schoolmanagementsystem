"""Holiday request schemas."""

import datetime as dt

from pydantic import BaseModel, Field


class HolidayCreateRequest(BaseModel):
    school_id: int
    class_id: int | None = None
    date: dt.date | None = None
    dates: list[dt.date] = Field(default_factory=list)
    title: str
    description: str | None = None
    recurring_weeks: int = Field(default=0, ge=0)
