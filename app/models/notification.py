"""Notification model with many-to-many class targeting and dedup metadata."""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Table, Index
from sqlalchemy.orm import relationship
from datetime import datetime
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    target_student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    is_school_wide = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    dedup_key = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    # Relationships
    school = relationship("School", back_populates="notifications")
    sent_by_user = relationship("User", back_populates="sent_notifications", foreign_keys=[sent_by])
    recipient_user = relationship("User", foreign_keys=[user_id], lazy="selectin", overlaps="received_notifications")
    target_student = relationship("Student", lazy="selectin")
    target_classes = relationship(
        "Class",
        secondary=notification_classes,
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Notification(id={self.id}, title='{self.title}')>"
