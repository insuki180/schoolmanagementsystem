"""Student schemas."""

from pydantic import BaseModel
from datetime import datetime


class StudentResponse(BaseModel):
    id: int
    name: str
    class_id: int
    parent_id: int
    school_id: int
    created_at: datetime | None

    model_config = {"from_attributes": True}
