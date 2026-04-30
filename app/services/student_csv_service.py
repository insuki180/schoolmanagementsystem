"""CSV import/export helpers for bulk student management."""

from __future__ import annotations

import csv
import io
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.models.school import School
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.auth_service import hash_password
from app.services.contact_utils import validate_phone_number


TEMPLATE_HEADERS = [
    "class_name",
    "student_name",
    "parent_name",
    "parent_phone",
    "parent_email",
]

_credential_exports: dict[str, str] = {}


@dataclass
class ImportFailure:
    row_number: int
    row: dict[str, str]
    reason: str


def _normalize(value: str | None) -> str:
    return (value or "").strip()


def _normalize_key(*parts: str | None) -> tuple[str, ...]:
    return tuple(_normalize(part).lower() for part in parts)


def build_template_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(TEMPLATE_HEADERS)
    return output.getvalue()


def build_credentials_csv(rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_name", "parent_login", "temp_password"])
    for row in rows:
        writer.writerow([row["student_name"], row["parent_login"], row["temp_password"]])
    return output.getvalue()


def store_credentials_export(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    token = secrets.token_urlsafe(12)
    _credential_exports[token] = build_credentials_csv(rows)
    return token


def get_credentials_export(token: str) -> str | None:
    return _credential_exports.get(token)


async def _resolve_school_scope(db: AsyncSession, current_user: User, school_id: int | None) -> School:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role == UserRole.SCHOOL_ADMIN.value:
        result = await db.execute(select(School).where(School.id == current_user.school_id))
        school = result.scalar_one_or_none()
        if not school:
            raise ValueError("Your school could not be found.")
        return school

    if role != UserRole.SUPER_ADMIN.value:
        raise ValueError("You do not have permission to import students.")

    if not school_id:
        raise ValueError("Please select a school for this import.")

    result = await db.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school:
        raise ValueError("Selected school does not exist.")
    return school


async def import_students_from_csv(
    db: AsyncSession,
    *,
    current_user: User,
    csv_text: str,
    school_id: int | None = None,
) -> dict:
    school = await _resolve_school_scope(db, current_user, school_id)

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames != TEMPLATE_HEADERS:
        raise ValueError(
            "CSV headers must be exactly: class_name,student_name,parent_name,parent_phone,parent_email"
        )

    classes_result = await db.execute(
        select(Class).where(Class.school_id == school.id).order_by(Class.name)
    )
    classes = list(classes_result.scalars().all())
    classes_by_name = {_normalize(cls.name).lower(): cls for cls in classes}

    rows = list(reader)
    parent_emails = {
        _normalize(row.get("parent_email")).lower()
        for row in rows
        if _normalize(row.get("parent_email"))
    }

    parents_result = await db.execute(
        select(User).where(User.email.in_(parent_emails))
    )
    existing_users_by_email = {
        user.email.lower(): user for user in parents_result.scalars().all()
    }

    existing_students_result = await db.execute(
        select(Student, User.email)
        .join(User, User.id == Student.parent_id)
        .where(Student.school_id == school.id)
    )
    existing_student_keys = {
        _normalize_key(student.name, str(student.class_id), parent_email)
        for student, parent_email in existing_students_result.all()
    }

    seen_file_keys: set[tuple[str, ...]] = set()
    failures: list[ImportFailure] = []
    credentials_rows: list[dict[str, str]] = []
    success_count = 0

    for index, row in enumerate(rows, start=2):
        class_name = _normalize(row.get("class_name"))
        student_name = _normalize(row.get("student_name"))
        parent_name = _normalize(row.get("parent_name"))
        parent_phone = _normalize(row.get("parent_phone"))
        parent_email = _normalize(row.get("parent_email")).lower()

        if not all([class_name, student_name, parent_name, parent_email]):
            failures.append(ImportFailure(index, row, "Missing required fields."))
            continue
        try:
            normalized_parent_phone = validate_phone_number(parent_phone, required=True)
        except ValueError as exc:
            failures.append(ImportFailure(index, row, str(exc)))
            continue

        class_ = classes_by_name.get(class_name.lower())
        if not class_:
            failures.append(ImportFailure(index, row, f"Class '{class_name}' not found in this school."))
            continue

        row_key = _normalize_key(student_name, str(class_.id), parent_email)
        if row_key in seen_file_keys:
            failures.append(ImportFailure(index, row, "Duplicate row in uploaded CSV."))
            continue
        if row_key in existing_student_keys:
            failures.append(ImportFailure(index, row, "Student already exists for this class and parent email."))
            continue

        parent_user = existing_users_by_email.get(parent_email)
        temp_password = ""
        if parent_user:
            if parent_user.role != UserRole.PARENT:
                failures.append(ImportFailure(index, row, "Parent email already belongs to another user role."))
                continue
            if not parent_user.phone_number:
                parent_user.phone_number = normalized_parent_phone
        else:
            temp_password = secrets.token_hex(4)
            parent_user = User(
                name=parent_name,
                email=parent_email,
                phone_number=normalized_parent_phone,
                password_hash=hash_password(temp_password),
                role=UserRole.PARENT,
                school_id=school.id,
                must_change_password=True,
            )
            db.add(parent_user)
            await db.flush()
            existing_users_by_email[parent_email] = parent_user

        student = Student(
            name=student_name,
            class_id=class_.id,
            parent_id=parent_user.id,
            school_id=school.id,
        )
        db.add(student)
        await db.flush()

        seen_file_keys.add(row_key)
        existing_student_keys.add(row_key)
        success_count += 1
        credentials_rows.append(
            {
                "student_name": student_name,
                "parent_login": parent_email,
                "temp_password": temp_password,
            }
        )

    return {
        "school": school,
        "total_rows": len(rows),
        "success_count": success_count,
        "failed_rows": failures,
        "credentials_rows": credentials_rows,
        "credentials_token": store_credentials_export(credentials_rows),
    }


async def export_students_for_user(
    db: AsyncSession,
    current_user: User,
    *,
    school_id: int | None = None,
    class_id: int | None = None,
) -> str:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role == UserRole.SCHOOL_ADMIN.value:
        effective_school_id = current_user.school_id
    elif role == UserRole.SUPER_ADMIN.value:
        if school_id is None:
            raise ValueError("Please select a school before exporting students.")
        effective_school_id = school_id
    else:
        raise ValueError("You do not have permission to export students.")

    if class_id is None:
        raise ValueError("Please select a class before exporting students.")

    class_result = await db.execute(
        select(Class).where(
            Class.id == class_id,
            Class.school_id == effective_school_id,
        )
    )
    class_record = class_result.scalar_one_or_none()
    if not class_record:
        raise ValueError("Selected class does not belong to the selected school.")

    result = await db.execute(
        select(
            Student.name,
            Class.name,
            User.name,
            User.phone_number,
            User.email,
        )
        .join(Class, Class.id == Student.class_id)
        .join(User, User.id == Student.parent_id)
        .where(
            Student.school_id == effective_school_id,
            Student.class_id == class_id,
        )
        .order_by(Class.name, Student.name)
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_name", "class_name", "parent_name", "parent_phone", "parent_email"])
    for student_name, class_name, parent_name, parent_phone, parent_email in result.all():
        writer.writerow([student_name, class_name, parent_name, parent_phone or "", parent_email])
    return output.getvalue()
