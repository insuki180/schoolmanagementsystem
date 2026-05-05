"""Holiday model for school-wide and class-specific holidays."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_holidays_school_class_date", "school_id", "class_id", "date"),
    )

    school = relationship("School", lazy="selectin")
    class_ = relationship("Class", lazy="selectin")
    creator = relationship("User", lazy="selectin")
