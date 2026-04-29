import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models.notification import Notification
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.contact_utils import get_whatsapp_link
from app.services.student_view_service import (
    get_student_absence_history,
    get_student_details_context,
)
from app.services.notification_service import send_personal_notification


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return list(self._rows)


class StudentDetailsTests(unittest.IsolatedAsyncioTestCase):
    async def test_student_details_context_includes_parent_and_whatsapp(self):
        student = Student(
            id=5,
            name="Alice",
            class_id=3,
            parent_id=8,
            school_id=1,
            blood_group="O+",
            address="42 Main Street",
        )
        parent = SimpleNamespace(id=8, name="Jane Doe", phone_number="+1 555 123 4567")
        class_ = SimpleNamespace(id=3, name="Grade 1")
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=student),
                FakeResult(scalar=parent),
                FakeResult(scalar=class_),
            ]
        )

        with patch("app.services.student_view_service.get_teacher_contacts_for_student", AsyncMock(return_value={"class_teacher": None, "subject_teachers": []})):
            context = await get_student_details_context(db, student_id=5)

        self.assertEqual(context["student"].name, "Alice")
        self.assertEqual(context["class_name"], "Grade 1")
        self.assertEqual(context["parent"].name, "Jane Doe")
        self.assertEqual(context["parent_whatsapp"], get_whatsapp_link(parent.phone_number))

    async def test_absence_history_includes_parent_reply_and_leave_duration(self):
        student = Student(id=5, name="Alice", class_id=3, parent_id=8, school_id=1)
        attendance = SimpleNamespace(date=date(2026, 4, 20), is_present=False)
        response = SimpleNamespace(message="Fever for two days", leave_days=2, is_read=True)
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=student),
                FakeResult(rows=[(attendance, response)]),
            ]
        )

        history = await get_student_absence_history(db, student_id=5)

        self.assertEqual(history["student"].id, 5)
        self.assertEqual(history["rows"][0]["status"], "Absent")
        self.assertEqual(history["rows"][0]["parent_reply"], "Fever for two days")
        self.assertEqual(history["rows"][0]["leave_duration"], 2)


class PersonalNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_personal_notification_targets_student(self):
        db = Mock()
        db.flush = AsyncMock()
        db.add = Mock()
        student = Student(id=9, name="Bob", class_id=4, parent_id=12, school_id=3)
        db.execute = AsyncMock(return_value=FakeResult(scalar=student))

        notification = await send_personal_notification(
            db,
            title="Private Note",
            message="Please meet the class teacher tomorrow.",
            school_id=3,
            sent_by=2,
            student_id=9,
        )

        self.assertIsInstance(notification, Notification)
        self.assertEqual(notification.target_student_id, 9)
        self.assertFalse(notification.is_school_wide)
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    async def test_send_personal_notification_respects_school_filter(self):
        db = Mock()
        db.flush = AsyncMock()
        db.add = Mock()
        student = Student(id=9, name="Bob", class_id=4, parent_id=12, school_id=3)
        db.execute = AsyncMock(return_value=FakeResult(scalar=student))

        with self.assertRaises(ValueError):
            await send_personal_notification(
                db,
                title="Private Note",
                message="Please meet the class teacher tomorrow.",
                school_id=7,
                sent_by=2,
                student_id=9,
            )

        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
