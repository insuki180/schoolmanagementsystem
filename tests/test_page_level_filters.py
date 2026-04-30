import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from starlette.requests import Request

from app.models.user import User, UserRole
from app.routers.attendance import attendance_page
from app.routers.marks import marks_page


def build_request(path: str) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    request.state.school_options = [
        SimpleNamespace(id=1, name="Alpha School"),
        SimpleNamespace(id=2, name="Beta School"),
    ]
    return request


class AttendancePageFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_attendance_page_stays_empty_until_school_and_class_are_selected(self):
        current_user = User(
            id=1,
            name="Root",
            email="root@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
            school_id=None,
        )

        with patch("app.routers.attendance.get_allowed_classes", AsyncMock(return_value=[])) as get_allowed_classes_mock, patch(
            "app.routers.attendance.get_today_attendance",
            AsyncMock(),
        ) as get_today_attendance_mock:
            response = await attendance_page(
                request=build_request("/attendance"),
                db=AsyncMock(),
                class_id=None,
                school_id=None,
                current_user=current_user,
            )

        self.assertEqual(response.context["students"], [])
        self.assertIsNone(response.context["selected_school_id"])
        self.assertEqual(response.context["classes"], [])
        get_allowed_classes_mock.assert_awaited_once()
        get_today_attendance_mock.assert_not_awaited()

    async def test_attendance_page_loads_students_for_selected_school_and_class(self):
        current_user = User(
            id=2,
            name="Root",
            email="root2@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
            school_id=None,
        )
        classes = [SimpleNamespace(id=11, name="Grade 3", school_id=2)]
        students = [{"student_id": 4, "student_name": "Alice", "is_present": True}]

        with patch(
            "app.routers.attendance.resolve_school_scope",
            AsyncMock(return_value=SimpleNamespace(id=2, name="Beta School")),
        ), patch(
            "app.routers.attendance.get_allowed_classes",
            AsyncMock(return_value=classes),
        ) as get_allowed_classes_mock, patch(
            "app.routers.attendance.can_mark_attendance",
            AsyncMock(return_value=True),
        ), patch(
            "app.routers.attendance.get_today_attendance",
            AsyncMock(return_value=students),
        ) as get_today_attendance_mock:
            response = await attendance_page(
                request=build_request("/attendance"),
                db=AsyncMock(),
                class_id=11,
                school_id=2,
                current_user=current_user,
            )

        self.assertEqual(response.context["students"], students)
        self.assertEqual(response.context["selected_school_id"], 2)
        self.assertEqual(response.context["selected_class"], 11)
        get_allowed_classes_mock.assert_awaited_once()
        get_today_attendance_mock.assert_awaited_once_with(unittest.mock.ANY, 11)


class MarksPageFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_marks_page_stays_empty_until_school_and_class_are_selected(self):
        current_user = User(
            id=3,
            name="Root",
            email="root3@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
            school_id=None,
        )

        with patch("app.routers.marks.get_allowed_classes", AsyncMock(return_value=[])) as get_allowed_classes_mock:
            response = await marks_page(
                request=build_request("/marks"),
                db=AsyncMock(),
                class_id=None,
                subject_id=None,
                exam_id=None,
                school_id=None,
                current_user=current_user,
            )

        self.assertEqual(response.context["students"], [])
        self.assertEqual(response.context["subjects"], [])
        self.assertEqual(response.context["exams"], [])
        self.assertIsNone(response.context["selected_school_id"])
        self.assertEqual(response.context["classes"], [])
        get_allowed_classes_mock.assert_awaited_once()
