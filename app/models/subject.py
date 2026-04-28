"""Subject model — managed per school."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)

    # Relationships
    school = relationship("School", back_populates="subjects")
    marks = relationship("Mark", back_populates="subject", lazy="selectin")

    def __repr__(self):
        return f"<Subject(id={self.id}, name='{self.name}')>"
