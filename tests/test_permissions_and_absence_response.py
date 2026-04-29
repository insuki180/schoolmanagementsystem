import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models.class_ import Class
from app.models.user import User, UserRole
from app.services.absence_response_service import get_visible_absence_responses, save_absence_response
from app.services.permissions import can_edit_marks, can_mark_attendance


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def all(self):
        return list(self._rows)


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_subject_teacher_cannot_edit_other_subject(self):
        teacher = User(id=7, role=UserRole.TEACHER, school_id=2, name="Teacher", email="t@example.com", password_hash="x")
        class_ = Class(id=3, name="Grade 1", school_id=2, class_teacher_id=None)

        with patch("app.services.permissions._get_class", AsyncMock(return_value=class_)), patch(
            "app.services.permissions._teacher_has_subject_assignment",
            AsyncMock(return_value=False),
        ), patch(
            "app.services.permissions._class_has_subject_mappings",
            AsyncMock(return_value=True),
        ), patch(
            "app.services.permissions._teacher_has_legacy_class_access",
            AsyncMock(return_value=True),
        ):
            allowed = await can_edit_marks(teacher, AsyncMock(), class_id=3, subject_id=99)

        self.assertFalse(allowed)

    async def test_class_teacher_can_edit_all_subjects_in_class(self):
        teacher = User(id=9, role=UserRole.TEACHER, school_id=2, name="Teacher", email="t2@example.com", password_hash="x")
        class_ = Class(id=5, name="Grade 2", school_id=2, class_teacher_id=9)

        with patch("app.services.permissions._get_class", AsyncMock(return_value=class_)):
            allowed = await can_edit_marks(teacher, AsyncMock(), class_id=5, subject_id=1)

        self.assertTrue(allowed)

    async def test_teacher_cannot_mark_attendance_outside_assigned_class(self):
        teacher = User(id=11, role=UserRole.TEACHER, school_id=4, name="Teacher", email="t3@example.com", password_hash="x")
        class_ = Class(id=8, name="Grade 3", school_id=4, class_teacher_id=None)

        with patch("app.services.permissions._get_class", AsyncMock(return_value=class_)), patch(
            "app.services.permissions._teacher_has_subject_assignment",
            AsyncMock(return_value=False),
        ), patch(
            "app.services.permissions._teacher_has_legacy_class_access",
            AsyncMock(return_value=False),
        ):
            allowed = await can_mark_attendance(teacher, AsyncMock(), class_id=8)

        self.assertFalse(allowed)

    async def test_parent_cannot_edit_marks(self):
        parent = User(id=13, role=UserRole.PARENT, school_id=4, name="Parent", email="p@example.com", password_hash="x")
        class_ = Class(id=10, name="Grade 4", school_id=4, class_teacher_id=None)

        with patch("app.services.permissions._get_class", AsyncMock(return_value=class_)):
            allowed = await can_edit_marks(parent, AsyncMock(), class_id=10, subject_id=2)

        self.assertFalse(allowed)


class AbsenceResponseWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_submits_absence_reason_and_it_is_saved(self):
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=SimpleNamespace(student_id=5, date=date(2026, 4, 29), is_present=False)),
                FakeResult(scalar=None),
            ]
        )
        db.flush = AsyncMock()
        db.add = Mock()
        parent = User(id=21, role=UserRole.PARENT, school_id=3, name="Parent", email="parent@example.com", password_hash="x")

        with patch("app.services.absence_response_service.can_view_student", AsyncMock(return_value=True)):
            response = await save_absence_response(
                db,
                student_id=5,
                absence_date=date(2026, 4, 29),
                message="Child was sick and needs 2 days rest.",
                leave_days=2,
                parent_user=parent,
            )

        self.assertEqual(response.student_id, 5)
        self.assertEqual(response.message, "Child was sick and needs 2 days rest.")
        self.assertEqual(response.leave_days, 2)
        self.assertTrue(response.is_read)
        self.assertEqual(response.created_by_parent, 21)
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    async def test_school_admin_can_view_absence_responses(self):
        db = Mock()
        response = SimpleNamespace(date=date(2026, 4, 29), message="Medical leave", leave_days=1)
        student = SimpleNamespace(name="Alice")
        class_ = SimpleNamespace(name="Grade 1")
        parent = SimpleNamespace(name="Parent User")
        db.execute = AsyncMock(return_value=FakeResult(rows=[(response, student, class_, parent)]))

        admin = User(id=31, role=UserRole.SCHOOL_ADMIN, school_id=7, name="Admin", email="admin@example.com", password_hash="x")
        rows = await get_visible_absence_responses(db, admin)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student"].name, "Alice")
        self.assertEqual(rows[0]["response"].message, "Medical leave")


if __name__ == "__main__":
    unittest.main()
