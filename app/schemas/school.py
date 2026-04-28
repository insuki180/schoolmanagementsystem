"""School schemas."""

from pydantic import BaseModel
from datetime import datetime


class SchoolCreateRequest(BaseModel):
    name: str
    address: str | None = None
    phone: str | None = None


class SchoolResponse(BaseModel):
    id: int
    name: str
    address: str | None
    phone: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
