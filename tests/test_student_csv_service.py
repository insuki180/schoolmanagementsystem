import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models.user import User, UserRole
from app.services.student_csv_service import (
    TEMPLATE_HEADERS,
    build_template_csv,
    export_students_for_user,
    import_students_from_csv,
)


class FakeResult:
    def __init__(self, scalar=None, scalars=None, rows=None):
        self._scalar = scalar
        self._scalars = scalars or []
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows if self._rows else self._scalars)


class CsvTemplateTests(unittest.TestCase):
    def test_template_contains_required_headers(self):
        content = build_template_csv().strip()
        self.assertEqual(content, ",".join(TEMPLATE_HEADERS))


class StudentImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_csv_creates_student_and_parent(self):
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=SimpleNamespace(id=7, name="Demo School")),
                FakeResult(scalars=[SimpleNamespace(id=3, name="Grade 1")]),
                FakeResult(scalars=[]),
                FakeResult(rows=[]),
            ]
        )
        db.flush = AsyncMock()
        db.add = Mock()
        current_user = User(
            id=10,
            name="School Admin",
            email="admin@example.com",
            password_hash="x",
            role=UserRole.SCHOOL_ADMIN,
            school_id=7,
        )
        csv_text = "class_name,student_name,parent_name,parent_phone,parent_email\nGrade 1,Alice,Jane,1234567890,jane@example.com\n"

        with patch("app.services.student_csv_service.hash_password", return_value="hashed-temp"):
            summary = await import_students_from_csv(db, current_user=current_user, csv_text=csv_text)

        self.assertEqual(summary["total_rows"], 1)
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(len(summary["failed_rows"]), 0)
        self.assertEqual(summary["credentials_rows"][0]["parent_login"], "jane@example.com")
        self.assertEqual(len(summary["credentials_rows"][0]["temp_password"]), 8)
        self.assertEqual(db.add.call_count, 2)
        self.assertEqual(db.flush.await_count, 2)

    async def test_invalid_class_row_is_reported(self):
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=SimpleNamespace(id=7, name="Demo School")),
                FakeResult(scalars=[]),
                FakeResult(scalars=[]),
                FakeResult(rows=[]),
            ]
        )
        db.flush = AsyncMock()
        db.add = Mock()
        current_user = User(
            id=11,
            name="School Admin",
            email="admin@example.com",
            password_hash="x",
            role=UserRole.SCHOOL_ADMIN,
            school_id=7,
        )
        csv_text = "class_name,student_name,parent_name,parent_phone,parent_email\nUnknown,John,Parent,1234567890,parent@example.com\n"

        summary = await import_students_from_csv(db, current_user=current_user, csv_text=csv_text)

        self.assertEqual(summary["success_count"], 0)
        self.assertEqual(len(summary["failed_rows"]), 1)
        self.assertIn("not found", summary["failed_rows"][0].reason)
        db.add.assert_not_called()

    async def test_duplicate_rows_are_handled_safely(self):
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=SimpleNamespace(id=7, name="Demo School")),
                FakeResult(scalars=[SimpleNamespace(id=3, name="Grade 1")]),
                FakeResult(scalars=[]),
                FakeResult(rows=[]),
            ]
        )
        db.flush = AsyncMock()
        db.add = Mock()
        current_user = User(
            id=12,
            name="School Admin",
            email="admin@example.com",
            password_hash="x",
            role=UserRole.SCHOOL_ADMIN,
            school_id=7,
        )
        csv_text = (
            "class_name,student_name,parent_name,parent_phone,parent_email\n"
            "Grade 1,Alice,Jane,1234567890,jane@example.com\n"
            "Grade 1,Alice,Jane,1234567890,jane@example.com\n"
        )

        with patch("app.services.student_csv_service.hash_password", return_value="hashed-temp"):
            summary = await import_students_from_csv(db, current_user=current_user, csv_text=csv_text)

        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(len(summary["failed_rows"]), 1)
        self.assertIn("Duplicate row", summary["failed_rows"][0].reason)


class StudentExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_super_admin_export_requires_school_and_class_filters(self):
        db = Mock()
        current_user = User(
            id=20,
            name="Super Admin",
            email="super@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
            school_id=None,
        )

        with self.assertRaises(ValueError) as ctx:
            await export_students_for_user(db, current_user, school_id=None, class_id=None)

        self.assertIn("select a school", str(ctx.exception).lower())

    async def test_export_students_returns_csv_for_selected_school_and_class(self):
        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                FakeResult(scalar=SimpleNamespace(id=3, name="Grade 1", school_id=7)),
                FakeResult(rows=[("Alice", "Grade 1", "Jane", "123", "jane@example.com")]),
            ]
        )
        current_user = User(
            id=20,
            name="Super Admin",
            email="super@example.com",
            password_hash="x",
            role=UserRole.SUPER_ADMIN,
            school_id=None,
        )

        content = await export_students_for_user(db, current_user, school_id=7, class_id=3)

        self.assertIn("student_name,class_name,parent_name,parent_phone,parent_email", content)
        self.assertIn("Alice,Grade 1,Jane,123,jane@example.com", content)
        sql = str(db.execute.await_args.args[0])
        self.assertIn("students.school_id", sql)
        self.assertIn("students.class_id", sql)

    async def test_school_admin_export_is_school_scoped(self):
        captured = {}

        async def execute(statement):
            statements = captured.setdefault("sql", [])
            statements.append(str(statement))
            if len(statements) == 1:
                return FakeResult(scalar=SimpleNamespace(id=4, name="Grade 2", school_id=9))
            return FakeResult(rows=[])

        db = Mock()
        db.execute = execute
        current_user = User(
            id=21,
            name="School Admin",
            email="admin@example.com",
            password_hash="x",
            role=UserRole.SCHOOL_ADMIN,
            school_id=9,
        )

        await export_students_for_user(db, current_user, school_id=None, class_id=4)

        combined_sql = "\n".join(captured["sql"])
        self.assertIn("students.school_id", combined_sql)
        self.assertIn("students.class_id", combined_sql)


if __name__ == "__main__":
    unittest.main()
