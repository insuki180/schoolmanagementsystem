"""Exam model — created by School Admin, unique per school."""

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Constraints
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_exam_school_name"),
    )

    # Relationships
    school = relationship("School", back_populates="exams")
    marks = relationship("Mark", back_populates="exam", lazy="selectin")

    def __repr__(self):
        return f"<Exam(id={self.id}, name='{self.name}')>"
