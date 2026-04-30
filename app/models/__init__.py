"""SQLAlchemy ORM models — import all models here for Alembic discovery."""

from app.models.school import School
from app.models.user import User
from app.models.class_ import Class, ClassSubject, teacher_classes
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.attendance import Attendance
from app.models.notification import Notification, notification_classes
from app.models.mark import Mark
from app.models.absence_response import AbsenceResponse
from app.models.audit_log import AuditLog
from app.models.finance import FeeLedger, StudentFeeConfig

__all__ = [
    "School",
    "User",
    "Class",
    "ClassSubject",
    "teacher_classes",
    "Student",
    "Subject",
    "Exam",
    "Attendance",
    "Notification",
    "notification_classes",
    "Mark",
    "AbsenceResponse",
    "AuditLog",
    "StudentFeeConfig",
    "FeeLedger",
]
