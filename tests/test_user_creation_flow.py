import unittest
from unittest.mock import AsyncMock, Mock, patch

from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.models.user import UserRole
from app.routers import auth
from app.services import user_service


class TempPasswordTests(unittest.TestCase):
    def test_generate_temp_password_returns_hex_token(self):
        password = user_service.generate_temp_password()

        self.assertEqual(len(password), 8)
        self.assertRegex(password, r"^[0-9a-f]{8}$")


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
        self.assertEqual(user.password_hash, "hashed-temp")
        self.assertEqual(len(temp_password), 8)
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
    async def test_first_login_password_change_skips_current_password_check(self):
        request = Request({"type": "http", "method": "POST", "path": "/change-password", "headers": []})
        current_user = Mock(
            id=99,
            password_hash="old-hash",
            must_change_password=True,
        )
        persisted_user = Mock()
        session = AsyncMock()
        result = Mock()
        result.scalar_one.return_value = persisted_user
        session.execute.return_value = result
        session_manager = FakeSessionContext(session)

        with patch("app.routers.auth.verify_password") as verify_password, patch(
            "app.routers.auth.hash_password", return_value="new-hash"
        ), patch("app.database.AsyncSessionLocal", return_value=session_manager):
            response = await auth.change_password(
                request=request,
                db=AsyncMock(),
                current_password="",
                new_password="betterpass",
                confirm_password="betterpass",
                current_user=current_user,
            )

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "/dashboard")
        self.assertEqual(persisted_user.password_hash, "new-hash")
        self.assertFalse(persisted_user.must_change_password)
        session.commit.assert_awaited_once()
        verify_password.assert_not_called()


if __name__ == "__main__":
    unittest.main()
