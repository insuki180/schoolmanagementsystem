"""Finance models for legacy student fees and periodic fee structures."""

from datetime import date, datetime
import enum

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class FeeType(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    YEARLY = "yearly"


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


class FeeStructure(Base):
    __tablename__ = "fee_structures"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    fee_type = Column(Enum(FeeType), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    effective_from = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_fee_structures_class_type_effective", "class_id", "fee_type", "effective_from"),
    )

    class_ = relationship("Class", back_populates="fee_structures")


class StudentFee(Base):
    __tablename__ = "student_fees"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    fee_type = Column(Enum(FeeType), nullable=False, index=True)
    amount_due = Column(Float, nullable=False)
    amount_paid = Column(Float, nullable=False, default=0.0)
    carry_forward = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="DUE")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_student_fees_student_period", "student_id", "period_start"),
        Index("ix_student_fees_class_period", "class_id", "period_start"),
        Index("ix_student_fees_student_status", "student_id", "status"),
        UniqueConstraint("student_id", "period_start", "period_end", name="uq_student_fees_student_period_range"),
    )

    student = relationship("Student", back_populates="student_fees")
    class_ = relationship("Class", back_populates="student_fees")
