import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models.student import Student
from app.models.user import User, UserRole
from app.services.contact_utils import get_whatsapp_link, validate_phone_number
from app.services.parent_portal_service import (
    build_parent_notification_cards,
    get_teacher_contacts_for_student,
    update_student_profile,
)
from app.services.user_service import create_student_and_parent, create_teacher


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return list(self._rows)


class ContactUtilityTests(unittest.TestCase):
    def test_get_whatsapp_link_builds_wa_me_url(self):
        self.assertEqual(get_whatsapp_link("+1 555 123 4567"), "https://wa.me/15551234567")

    def test_validate_phone_number_rejects_short_values(self):
        with self.assertRaises(ValueError):
            validate_phone_number("123", required=True)


class UserPhoneRequirementTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_requires_phone_number(self):
        db = Mock()
        db.flush = AsyncMock()

        with self.assertRaises(ValueError):
            await create_teacher(db, "Teacher", "teacher@example.com", 1, [], "")

    async def test_parent_requires_phone_number(self):
        db = Mock()
        db.execute = AsyncMock(return_value=FakeResult(scalar=None))
        db.flush = AsyncMock()

        with self.assertRaises(ValueError):
            await create_student_and_parent(
                db,
                "Student",
                1,
                "Parent",
                "parent@example.com",
                "",
                1,
            )


class ParentPortalTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_updates_student_details_saved(self):
        db = Mock()
        student = Student(id=5, name="Alice", class_id=1, parent_id=2, school_id=1)
        db.execute = AsyncMock(return_value=FakeResult(scalar=student))
        db.flush = AsyncMock()
        parent = User(id=2, name="Parent", email="parent@example.com", password_hash="x", role=UserRole.PARENT, school_id=1)

        with patch("app.services.parent_portal_service.can_view_student", AsyncMock(return_value=True)):
            updated = await update_student_profile(
                db,
                parent_user=parent,
                student_id=5,
                blood_group="O+",
                address="42 Main Street",
            )

        self.assertEqual(updated.blood_group, "O+")
        self.assertEqual(updated.address, "42 Main Street")
        db.flush.assert_awaited_once()

    async def test_teacher_contact_list_loads_correctly(self):
        student = Student(id=4, name="Alice", class_id=3, parent_id=2, school_id=1)
        class_ = SimpleNamespace(id=3, class_teacher_id=9)
        class_teacher = SimpleNamespace(id=9, name="Mr. Rao", phone_number="9876543210")
        subject_rows = [
            (
                SimpleNamespace(subject_id=1),
                SimpleNamespace(id=10, name="Ms. Devi", phone_number="9123456789"),
                SimpleNamespace(id=1, name="Science"),
            )
        ]
        db = Mock()
        db.execute = AsyncMock(side_effect=[FakeResult(scalar=class_), FakeResult(scalar=class_teacher), FakeResult(rows=subject_rows)])

        contacts = await get_teacher_contacts_for_student(db, student)

        self.assertEqual(contacts["class_teacher"].name, "Mr. Rao")
        self.assertEqual(contacts["class_teacher"].whatsapp_link, "https://wa.me/9876543210")
        self.assertEqual(contacts["subject_teachers"][0].subject, "Science")

    def test_notification_cards_include_absence_and_notice(self):
        cards = build_parent_notification_cards(
            notifications=[SimpleNamespace(id=7, title="Holiday", message="School closed", created_at=datetime(2026, 4, 29, 10, 0, 0))],
            absence_alerts=[{"student": SimpleNamespace(id=5, name="Alice"), "class_name": "Grade 1", "date": date(2026, 4, 28)}],
            student_id=5,
        )

        self.assertEqual(cards[0]["title"], "Holiday")
        self.assertEqual(cards[1]["title"], "Absent Notification")


if __name__ == "__main__":
    unittest.main()
