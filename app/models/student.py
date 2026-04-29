"""Student model — linked to a class and a parent user."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    blood_group = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Constraints
    __table_args__ = (
        Index("ix_student_parent_class", "parent_id", "class_id"),
    )

    # Relationships
    class_ = relationship("Class", back_populates="students")
    parent = relationship("User", back_populates="children")
    school = relationship("School", back_populates="students")
    attendance_records = relationship("Attendance", back_populates="student", lazy="selectin")
    marks = relationship("Mark", back_populates="student", lazy="selectin")
    absence_responses = relationship("AbsenceResponse", back_populates="student", lazy="selectin")

    def __repr__(self):
        return f"<Student(id={self.id}, name='{self.name}')>"
