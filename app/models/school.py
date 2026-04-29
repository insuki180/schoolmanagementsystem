"""School model."""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    logo_url = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="school", lazy="selectin")
    classes = relationship("Class", back_populates="school", lazy="selectin")
    exams = relationship("Exam", back_populates="school", lazy="selectin")
    subjects = relationship("Subject", back_populates="school", lazy="selectin")
    notifications = relationship("Notification", back_populates="school", lazy="selectin")
    students = relationship("Student", back_populates="school", lazy="selectin")

    def __repr__(self):
        return f"<School(id={self.id}, name='{self.name}')>"
