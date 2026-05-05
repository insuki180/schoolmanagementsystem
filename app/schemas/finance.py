"""Finance request/response schemas."""

from datetime import date

from pydantic import BaseModel, Field


class FeeConfigCreateRequest(BaseModel):
    student_id: int
    monthly_fee: float = Field(gt=0)
    effective_from: date
    status: str = "active"


class FeePaymentCreateRequest(BaseModel):
    student_id: int
    amount_paid: float = Field(gt=0)
    payment_date: date
    payment_mode: str
    note: str | None = None


class FeeStructureCreateRequest(BaseModel):
    class_id: int
    fee_type: str
    amount: float = Field(gt=0)
    effective_from: date


class FeeGenerateRequest(BaseModel):
    class_id: int
    fee_type: str
    through_date: date
    student_id: int | None = None
