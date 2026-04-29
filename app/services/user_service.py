"""User management service — CRUD operations for all user roles."""

import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.class_ import Class
from app.services.auth_service import hash_password
from app.services.contact_utils import validate_phone_number


def generate_temp_password() -> str:
    """Generate a short temporary password for first login."""
    return secrets.token_hex(4)


async def create_school_admin(
    db: AsyncSession, name: str, email: str,
    school_id: int, phone: str | None = None
) -> tuple[User, str]:
    """Create a school admin user."""
    temp_password = generate_temp_password()
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(temp_password),
        phone_number=validate_phone_number(phone),
        role=UserRole.SCHOOL_ADMIN,
        school_id=school_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    return user, temp_password


async def create_teacher(
    db: AsyncSession, name: str, email: str,
    school_id: int, class_ids: list[int] = None, phone: str | None = None
) -> tuple[User, str]:
    """Create a teacher and assign to classes."""
    temp_password = generate_temp_password()
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(temp_password),
        phone_number=validate_phone_number(phone, required=True),
        role=UserRole.TEACHER,
        school_id=school_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()

    # Assign classes
    if class_ids:
        result = await db.execute(
            select(Class).where(Class.id.in_(class_ids), Class.school_id == school_id)
        )
        classes = result.scalars().all()
        user.taught_classes = list(classes)
        await db.flush()

    return user, temp_password


async def create_student_and_parent(
    db: AsyncSession, student_name: str, class_id: int,
    parent_name: str, parent_email: str, parent_phone: str | None,
    school_id: int
) -> tuple[Student, User, str | None]:
    """Create a student and auto-create or link parent account."""
    normalized_phone = validate_phone_number(parent_phone, required=True)
    # Check if parent already exists
    result = await db.execute(select(User).where(User.email == parent_email))
    parent = result.scalar_one_or_none()
    temp_password = None

    if not parent:
        # Create parent account with default password
        temp_password = generate_temp_password()
        parent = User(
            name=parent_name,
            email=parent_email,
            password_hash=hash_password(temp_password),
            phone_number=normalized_phone,
            role=UserRole.PARENT,
            school_id=school_id,
            must_change_password=True,
        )
        db.add(parent)
        await db.flush()
    elif not parent.phone_number:
        parent.phone_number = normalized_phone

    # Create student
    student = Student(
        name=student_name,
        class_id=class_id,
        parent_id=parent.id,
        school_id=school_id,
    )
    db.add(student)
    await db.flush()

    return student, parent, temp_password


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get a user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_users_by_school(db: AsyncSession, school_id: int, role: UserRole | None = None) -> list[User]:
    """Get all users for a school, optionally filtered by role."""
    query = select(User).where(User.school_id == school_id)
    if role:
        query = query.where(User.role == role)
    query = query.order_by(User.name)
    result = await db.execute(query)
    return list(result.scalars().all())
