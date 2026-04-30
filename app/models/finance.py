"""Finance models for fee configuration and payment ledger."""

from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class StudentFeeConfig(Base):
    __tablename__ = "student_fee_configs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    monthly_fee = Column(Float, nullable=False)
    effective_from = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="fee_configs")


class FeeLedger(Base):
    __tablename__ = "fee_ledger"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    amount_paid = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today, index=True)
    payment_mode = Column(String(50), nullable=False)
    note = Column(String(500), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="fee_ledger_entries")
    creator = relationship("User", lazy="selectin")
