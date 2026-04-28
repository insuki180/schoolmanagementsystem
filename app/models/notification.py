"""Notification model with many-to-many class targeting."""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


# Many-to-many: notifications <-> classes
notification_classes = Table(
    "notification_classes",
    Base.metadata,
    Column("notification_id", Integer, ForeignKey("notifications.id"), primary_key=True),
    Column("class_id", Integer, ForeignKey("classes.id"), primary_key=True),
)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    sent_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_school_wide = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    school = relationship("School", back_populates="notifications")
    sent_by_user = relationship("User", back_populates="sent_notifications")
    target_classes = relationship(
        "Class",
        secondary=notification_classes,
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Notification(id={self.id}, title='{self.title}')>"
