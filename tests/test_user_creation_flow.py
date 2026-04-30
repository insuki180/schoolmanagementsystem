import unittest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from fastapi import HTTPException

from app.models.student import Student
from app.models.user import User, UserRole
from app.routers import auth
from app.services import user_service


class TempPasswordTests(unittest.TestCase):
    def test_generate_temp_password_returns_alphanumeric_string_with_required_length(self):
        password = user_service.generate_temp_password()

        self.assertGreaterEqual(len(password), 10)
        self.assertLessEqual(len(password), 12)
        self.assertRegex(password, r"^[A-Za-z0-9]+$")


class CreateSchoolAdminTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_school_admin_generates_temp_password_and_forces_reset(self):
        db = Mock()
        db.flush = AsyncMock()

        with patch("app.services.user_service.hash_password", return_value="hashed-temp") as hash_password:
            user, temp_password = await user_service.create_school_admin(
                db, "Admin User", "admin@example.com", 7, "1234567890"
            )

        self.assertEqual(user.name, "Admin User")
        self.assertEqual(user.email, "admin@example.com")
        self.assertEqual(user.role, UserRole.SCHOOL_ADMIN)
        self.assertEqual(user.school_id, 7)
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.is_temp_password)
        self.assertEqual(user.password_hash, "hashed-temp")
        self.assertGreaterEqual(len(temp_password), 10)
        self.assertLessEqual(len(temp_password), 12)
        hash_password.assert_called_once_with(temp_password)
        db.add.assert_called_once()
        db.flush.assert_awaited()


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class ChangePasswordFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_temp_password_change_clears_temp_flags_after_verifying_current_password(self):
        request = Request({"type": "http", "method": "POST", "path": "/change-password", "headers": []})
        current_user = Mock(
            id=99,
            password_hash="old-hash",
            must_change_password=True,
            is_temp_password=True,
        )
        persisted_user = Mock(must_change_password=True, is_temp_password=True)
        db = AsyncMock()
        result = Mock()
        result.scalar_one.return_value = persisted_user
        db.execute.return_value = result

        with patch(
            "app.routers.auth._read_change_password_payload",
            AsyncMock(return_value=("old-password", "betterpass", "betterpass")),
        ), patch("app.routers.auth.verify_password", side_effect=[True, False]) as verify_password, patch(
            "app.routers.auth.hash_password", return_value="new-hash"
        ):
            response = await auth.change_password(
                request=request,
                db=db,
                current_user=current_user,
            )

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "/dashboard")
        self.assertEqual(persisted_user.password_hash, "new-hash")
        self.assertFalse(persisted_user.must_change_password)
        self.assertFalse(persisted_user.is_temp_password)
        db.flush.assert_awaited_once()
        self.assertEqual(verify_password.call_count, 2)


class LoginResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_json_login_returns_force_password_change_for_temp_password_user(self):
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/login",
            "headers": [(b"accept", b"application/json")],
        })
        user = User(
            id=7,
            name="Teacher User",
            email="teacher@example.com",
            password_hash="hash",
            role=UserRole.TEACHER,
            school_id=4,
            must_change_password=True,
            is_temp_password=True,
        )

        with patch("app.routers.auth._read_login_payload", AsyncMock(return_value=("teacher@example.com", "Temp12345"))), patch(
            "app.routers.auth.authenticate_user",
            AsyncMock(return_value=user),
        ), patch("app.routers.auth.create_access_token", return_value="signed-token"):
            response = await auth.login(request=request, db=AsyncMock())

        self.assertIsInstance(response, JSONResponse)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(payload["token"], "signed-token")
        self.assertTrue(payload["forcePasswordChange"])

    async def test_json_login_returns_normal_flow_after_password_update(self):
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/login",
            "headers": [(b"accept", b"application/json")],
        })
        user = User(
            id=8,
            name="Teacher User",
            email="teacher@example.com",
            password_hash="hash",
            role=UserRole.TEACHER,
            school_id=4,
            must_change_password=False,
            is_temp_password=False,
        )

        with patch("app.routers.auth._read_login_payload", AsyncMock(return_value=("teacher@example.com", "Secure123"))), patch(
            "app.routers.auth.authenticate_user",
            AsyncMock(return_value=user),
        ), patch("app.routers.auth.create_access_token", return_value="signed-token"):
            response = await auth.login(request=request, db=AsyncMock())

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(payload["token"], "signed-token")
        self.assertFalse(payload["forcePasswordChange"])


class FakeScalarResult:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar


class PasswordResetWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_school_admin_can_reset_teacher_in_same_school(self):
        db = Mock()
        target_user = User(
            id=22,
            name="Teacher User",
            email="teacher@example.com",
            password_hash="old-hash",
            role=UserRole.TEACHER,
            school_id=7,
        )
        db.execute = AsyncMock(return_value=FakeScalarResult(target_user))
        db.flush = AsyncMock()
        acting_user = User(
            id=5,
            name="School Admin",
            email="admin@example.com",
            password_hash="hash",
            role=UserRole.SCHOOL_ADMIN,
            school_id=7,
        )

        with patch("app.services.user_service.hash_password", return_value="new-hash"):
            temp_password = await user_service.reset_user_password(
                db,
                acting_user=acting_user,
                target_user_id=22,
            )

        self.assertGreaterEqual(len(temp_password), 10)
        self.assertLessEqual(len(temp_password), 12)
        self.assertEqual(target_user.password_hash, "new-hash")
        self.assertTrue(target_user.must_change_password)
        self.assertTrue(target_user.is_temp_password)
        db.flush.assert_awaited_once()

    async def test_school_admin_cannot_reset_parent_from_other_school(self):
        db = Mock()
        target_user = User(
            id=33,
            name="Parent User",
            email="parent@example.com",
            password_hash="old-hash",
            role=UserRole.PARENT,
            school_id=9,
        )
        db.execute = AsyncMock(return_value=FakeScalarResult(target_user))
        acting_user = User(
            id=5,
            name="School Admin",
            email="admin@example.com",
            password_hash="hash",
            role=UserRole.SCHOOL_ADMIN,
            school_id=7,
        )

        with self.assertRaises(HTTPException) as exc:
            await user_service.reset_user_password(
                db,
                acting_user=acting_user,
                target_user_id=33,
            )

        self.assertEqual(exc.exception.status_code, 403)


class UserUpdateWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_school_admin_can_update_teacher_profile_in_same_school(self):
        db = Mock()
        teacher = User(
            id=44,
            name="Old Teacher",
            email="teacher@example.com",
            password_hash="hash",
            role=UserRole.TEACHER,
            school_id=3,
            phone_number="1111111",
        )
        db.execute = AsyncMock(return_value=FakeScalarResult(teacher))
        db.flush = AsyncMock()
        acting_user = User(
            id=2,
            name="School Admin",
            email="admin@example.com",
            password_hash="hash",
            role=UserRole.SCHOOL_ADMIN,
            school_id=3,
        )

        updated = await user_service.update_teacher_profile(
            db,
            acting_user=acting_user,
            teacher_id=44,
            name="Updated Teacher",
            phone="9999999999",
        )

        self.assertIs(updated, teacher)
        self.assertEqual(updated.name, "Updated Teacher")
        self.assertEqual(updated.phone_number, "9999999999")
        db.flush.assert_awaited_once()

    async def test_school_admin_can_update_student_and_parent_phone_in_same_school(self):
        db = Mock()
        parent = User(
            id=77,
            name="Parent User",
            email="parent@example.com",
            password_hash="hash",
            role=UserRole.PARENT,
            school_id=3,
            phone_number="2222222",
        )
        student = Student(
            id=55,
            name="Old Student",
            class_id=4,
            parent_id=77,
            school_id=3,
        )
        db.execute = AsyncMock(
            side_effect=[
                FakeScalarResult(student),
                FakeScalarResult(SimpleNamespace(id=8, school_id=3)),
                FakeScalarResult(parent),
            ]
        )
        db.flush = AsyncMock()
        acting_user = User(
            id=2,
            name="School Admin",
            email="admin@example.com",
            password_hash="hash",
            role=UserRole.SCHOOL_ADMIN,
            school_id=3,
        )

        updated = await user_service.update_student_profile_by_school_admin(
            db,
            acting_user=acting_user,
            student_id=55,
            name="Updated Student",
            class_id=8,
            parent_phone="8888888888",
        )

        self.assertIs(updated, student)
        self.assertEqual(updated.name, "Updated Student")
        self.assertEqual(updated.class_id, 8)
        self.assertEqual(parent.phone_number, "8888888888")
        db.flush.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
