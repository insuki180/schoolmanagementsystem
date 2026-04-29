"""Class model with teacher and subject mapping relationships."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# Many-to-many: teachers <-> classes
teacher_classes = Table(
    "teacher_classes",
    Base.metadata,
    Column("teacher_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("class_id", Integer, ForeignKey("classes.id"), primary_key=True),
)


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    class_teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    school = relationship("School", back_populates="classes")
    students = relationship("Student", back_populates="class_", lazy="selectin")
    teachers = relationship(
        "User",
        secondary=teacher_classes,
        back_populates="taught_classes",
        lazy="selectin",
    )
    class_teacher = relationship("User", foreign_keys=[class_teacher_id], back_populates="homeroom_classes")
    subject_assignments = relationship(
        "ClassSubject",
        back_populates="class_",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Class(id={self.id}, name='{self.name}')>"


class ClassSubject(Base):
    __tablename__ = "class_subjects"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_class_subject_assignment"),
    )

    class_ = relationship("Class", back_populates="subject_assignments")
    subject = relationship("Subject", back_populates="class_assignments")
    teacher = relationship("User", back_populates="subject_assignments")
