"""Threaded attendance messages between school staff and parents."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship

from app.database import Base


class AttendanceMessage(Base):
    __tablename__ = "attendance_messages"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    sender_role = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_attendance_messages_student_date", "student_id", "attendance_date"),
    )

    student = relationship("Student", back_populates="attendance_messages")
