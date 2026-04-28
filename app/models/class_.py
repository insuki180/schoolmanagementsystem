"""Class model with many-to-many teacher relationship."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
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

    def __repr__(self):
        return f"<Class(id={self.id}, name='{self.name}')>"
