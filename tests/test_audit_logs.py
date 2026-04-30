import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.models.user import User, UserRole
from app.routers import logs
from app.services import audit_service


class FakeResult:
    def __init__(self, scalars=None):
        self._scalars = scalars or []

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._scalars[0] if self._scalars else None

    def all(self):
        return list(self._scalars)


def build_request(path: str, *, accept: str = "application/json") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [(b"accept", accept.encode("utf-8"))],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


class AuditServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_log_stores_expected_fields(self):
        db = Mock()
        db.flush = AsyncMock()

        log = await audit_service.create_log(
            db=db,
            action="PASSWORD_RESET",
            performed_by=1,
            target_user=2,
            school_id=3,
            class_id=None,
            role="teacher",
        )

        self.assertEqual(log.action, "PASSWORD_RESET")
        self.assertEqual(log.performed_by, 1)
        self.assertEqual(log.target_user, 2)
        self.assertEqual(log.school_id, 3)
        self.assertIsNone(log.class_id)
        self.assertEqual(log.role, "teacher")
        db.add.assert_called_once()
        db.flush.assert_awaited_once()


class LogsRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_super_admin_sees_all_logs(self):
        current_user = User(
            id=1,
            name="Root",
            email="root@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),
                FakeResult([]),
                FakeResult(
                    [
                        SimpleNamespace(
                            id=1,
                            action="PASSWORD_RESET",
                            performed_by=9,
                            target_user=10,
                            school_id=2,
                            class_id=None,
                            role="teacher",
                            timestamp="2026-04-30T10:00:00",
                        )
                    ]
                ),
            ]
        )

        response = await logs.logs_page(
            request=build_request("/logs"),
            db=db,
            current_user=current_user,
            school_id=None,
            class_id=None,
            role=None,
        )

        self.assertIsInstance(response, JSONResponse)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["action"], "PASSWORD_RESET")
        self.assertEqual(payload[0]["school_id"], 2)

    async def test_school_admin_only_sees_own_school_logs(self):
        current_user = User(
            id=2,
            name="Admin",
            email="admin@example.com",
            password_hash="x",
            role=UserRole.SCHOOL_ADMIN,
            school_id=5,
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult([]),
                FakeResult([]),
                FakeResult(
                    [
                        SimpleNamespace(
                            id=2,
                            action="PASSWORD_RESET",
                            performed_by=2,
                            target_user=15,
                            school_id=5,
                            class_id=None,
                            role="parent",
                            timestamp="2026-04-30T10:00:00",
                        )
                    ]
                ),
            ]
        )

        response = await logs.logs_page(
            request=build_request("/logs"),
            db=db,
            current_user=current_user,
            school_id=999,
            class_id=None,
            role="PARENT",
        )

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["school_id"], 5)
        self.assertEqual(payload[0]["role"], "parent")

    async def test_teacher_is_denied_logs_access(self):
        current_user = User(
            id=3,
            name="Teacher",
            email="teacher@example.com",
            password_hash="x",
            role=UserRole.TEACHER,
            school_id=5,
        )

        with self.assertRaises(HTTPException) as exc:
            await logs.logs_page(
                request=build_request("/logs"),
                db=AsyncMock(),
                current_user=current_user,
                school_id=None,
                class_id=None,
                role=None,
            )

        self.assertEqual(exc.exception.status_code, 403)


class PasswordResetAuditHookTests(unittest.IsolatedAsyncioTestCase):
    async def test_super_admin_password_reset_creates_audit_log(self):
        current_user = User(
            id=1,
            name="Root",
            email="root@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
        )
        target_user = User(
            id=9,
            name="Teacher",
            email="teacher@example.com",
            password_hash="old-hash",
            role=UserRole.TEACHER,
            school_id=4,
        )

        with patch(
            "app.routers.users.reset_user_password",
            AsyncMock(return_value="TempPass123"),
        ), patch(
            "app.routers.users.get_user_by_id",
            AsyncMock(return_value=target_user),
        ), patch(
            "app.routers.users.create_log",
            AsyncMock(),
        ) as create_log_mock:
            response = await __import__("app.routers.users", fromlist=[""]).super_admin_reset_password(
                payload=SimpleNamespace(userId="9"),
                db=AsyncMock(),
                current_user=current_user,
            )

        self.assertIsInstance(response, JSONResponse)
        create_log_mock.assert_awaited_once()
        self.assertEqual(create_log_mock.await_args.kwargs["action"], "PASSWORD_RESET")
        self.assertEqual(create_log_mock.await_args.kwargs["performed_by"], 1)
        self.assertEqual(create_log_mock.await_args.kwargs["target_user"], 9)


if __name__ == "__main__":
    unittest.main()
