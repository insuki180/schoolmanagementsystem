"""Absence response model for parent follow-up on absences."""

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class AbsenceResponse(Base):
    __tablename__ = "absence_responses"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(Date, nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=True, nullable=False)
    created_by_parent = Column(Integer, ForeignKey("users.id"), nullable=False)
    leave_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_absence_response_student_date"),
    )

    student = relationship("Student", back_populates="absence_responses")
    parent = relationship("User", back_populates="absence_responses")

    def __repr__(self):
        return f"<AbsenceResponse(student_id={self.student_id}, date={self.date})>"
