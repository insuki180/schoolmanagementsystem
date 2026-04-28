"""Auth schemas — login, token, password change."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class TokenData(BaseModel):
    user_id: int
    email: str
    role: str
    school_id: int | None = None
