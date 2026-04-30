"""Audit log model for administrative actions."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    action = Column(String(50), nullable=False)
    performed_by = Column(Integer, nullable=False)
    target_user = Column(Integer, nullable=True)
    school_id = Column(Integer, nullable=True)
    class_id = Column(Integer, nullable=True)
    role = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
