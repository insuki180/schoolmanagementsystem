"""User schemas — creation and response."""

from pydantic import BaseModel
from datetime import datetime


class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    role: str
    school_id: int | None = None


class SchoolAdminCreateRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    school_id: int


class TeacherCreateRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    class_ids: list[int] = []


class StudentCreateRequest(BaseModel):
    student_name: str
    class_id: int
    parent_name: str
    parent_email: str
    parent_phone: str | None = None


class TeacherUpdateRequest(BaseModel):
    name: str
    phone: str


class StudentUpdateRequest(BaseModel):
    name: str
    class_id: int
    parent_phone: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    role: str
    school_id: int | None
    is_active: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}
