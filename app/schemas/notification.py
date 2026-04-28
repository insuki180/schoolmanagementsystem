"""Notification schemas."""

from pydantic import BaseModel
from datetime import datetime


class NotificationSendRequest(BaseModel):
    title: str
    message: str
    class_ids: list[int] = []
    is_school_wide: bool = False


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    is_school_wide: bool
    created_at: datetime | None
    sent_by_name: str | None = None

    model_config = {"from_attributes": True}
