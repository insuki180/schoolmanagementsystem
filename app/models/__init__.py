"""SQLAlchemy ORM models — import all models here for Alembic discovery."""

from app.models.school import School
from app.models.user import User
from app.models.class_ import Class, ClassSubject, teacher_classes
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.holiday import Holiday
from app.models.attendance import Attendance
from app.models.notification import Notification, notification_classes
from app.models.mark import Mark
from app.models.absence_response import AbsenceResponse
from app.models.audit_log import AuditLog
from app.models.attendance_message import AttendanceMessage
from app.models.finance import FeeLedger, FeeStructure, FeeType, StudentFee, StudentFeeConfig
from app.models.timetable import TimetableSlot

__all__ = [
    "School",
    "User",
    "Class",
    "ClassSubject",
    "teacher_classes",
    "Student",
    "Subject",
    "Exam",
    "Holiday",
    "Attendance",
    "Notification",
    "notification_classes",
    "Mark",
    "AbsenceResponse",
    "AttendanceMessage",
    "AuditLog",
    "StudentFeeConfig",
    "FeeLedger",
    "FeeStructure",
    "FeeType",
    "StudentFee",
    "TimetableSlot",
]
