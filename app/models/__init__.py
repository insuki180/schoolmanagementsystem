"""SQLAlchemy ORM models — import all models here for Alembic discovery."""

from app.models.school import School
from app.models.user import User
from app.models.class_ import Class, teacher_classes
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.attendance import Attendance
from app.models.notification import Notification, notification_classes
from app.models.mark import Mark

__all__ = [
    "School",
    "User",
    "Class",
    "teacher_classes",
    "Student",
    "Subject",
    "Exam",
    "Attendance",
    "Notification",
    "notification_classes",
    "Mark",
]
