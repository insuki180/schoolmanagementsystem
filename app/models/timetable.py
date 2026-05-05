"""Timetable slots for class schedules."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import relationship

from app.database import Base


class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False, index=True)
    period_number = Column(Integer, nullable=False)
    subject_name = Column(String(200), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_timetable_slots_class_day", "class_id", "day_of_week"),
        Index("ix_timetable_slots_class_day_period", "class_id", "day_of_week", "period_number"),
        Index("ix_timetable_slots_teacher_day", "teacher_id", "day_of_week"),
    )

    class_ = relationship("Class", back_populates="timetable_slots")
    teacher = relationship("User", lazy="selectin")
