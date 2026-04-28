"""Mark model with unique constraint on student + subject + exam."""

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Mark(Base):
    __tablename__ = "marks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    marks_obtained = Column(Float, nullable=False)
    max_marks = Column(Float, nullable=False, default=100.0)
    entered_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "exam_id", name="uq_mark_student_subject_exam"),
        Index("ix_marks_student_exam", "student_id", "exam_id"),
    )

    # Relationships
    student = relationship("Student", back_populates="marks")
    subject = relationship("Subject", back_populates="marks")
    exam = relationship("Exam", back_populates="marks")
    entered_by_user = relationship("User", foreign_keys=[entered_by])

    def __repr__(self):
        return f"<Mark(student={self.student_id}, subject={self.subject_id}, marks={self.marks_obtained})>"
