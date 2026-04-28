"""Attendance model with unique constraint on student_id + date."""

from sqlalchemy import Column, Integer, Boolean, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    date = Column(Date, nullable=False)
    is_present = Column(Boolean, default=True, nullable=False)
    marked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
        Index("ix_attendance_student_date", "student_id", "date"),
    )

    # Relationships
    student = relationship("Student", back_populates="attendance_records")
    marked_by_user = relationship("User", foreign_keys=[marked_by])

    def __repr__(self):
        return f"<Attendance(student={self.student_id}, date={self.date}, present={self.is_present})>"
