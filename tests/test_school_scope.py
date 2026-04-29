import unittest
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException

from app.models.user import User, UserRole
from app.services.permissions import get_allowed_classes
from app.services.school_scope import resolve_school_scope


class FakeResult:
    def __init__(self, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._scalars)

    def unique(self):
        return self


class SchoolScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_super_admin_must_select_school_when_required(self):
        user = User(
            id=1,
            role=UserRole.SUPER_ADMIN,
            school_id=None,
            name="Root",
            email="root@example.com",
            password_hash="x",
        )

        with self.assertRaises(HTTPException) as ctx:
            await resolve_school_scope(AsyncMock(), user, None, required_for_super_admin=True)

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_school_admin_cannot_scope_to_other_school(self):
        user = User(
            id=2,
            role=UserRole.SCHOOL_ADMIN,
            school_id=8,
            name="Admin",
            email="admin@example.com",
            password_hash="x",
        )

        with self.assertRaises(HTTPException) as ctx:
            await resolve_school_scope(AsyncMock(), user, 11, required_for_super_admin=True)

        self.assertEqual(ctx.exception.status_code, 403)

    async def test_school_admin_uses_own_school_by_default(self):
        user = User(
            id=3,
            role=UserRole.SCHOOL_ADMIN,
            school_id=5,
            name="Admin",
            email="admin2@example.com",
            password_hash="x",
        )
        db = Mock()
        db.execute = AsyncMock(return_value=FakeResult(scalar=type("School", (), {"id": 5, "name": "North"})()))

        school = await resolve_school_scope(db, user, None, required_for_super_admin=True)

        self.assertEqual(school.id, 5)


class AllowedClassesTests(unittest.IsolatedAsyncioTestCase):
    async def test_super_admin_class_query_is_filtered_by_school_id(self):
        user = User(
            id=4,
            role=UserRole.SUPER_ADMIN,
            school_id=None,
            name="Root",
            email="root2@example.com",
            password_hash="x",
        )
        db = Mock()
        db.execute = AsyncMock(return_value=FakeResult(scalars=[]))

        await get_allowed_classes(db, user, school_id=9)

        query = db.execute.await_args.args[0]
        self.assertIn("classes.school_id", str(query))


if __name__ == "__main__":
    unittest.main()
