"""User management service — CRUD operations for all user roles."""

import secrets
import string

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.class_ import Class
from app.services.auth_service import hash_password
from app.services.contact_utils import validate_phone_number


def generate_temp_password() -> str:
    """Generate a temporary password using upper/lowercase letters and digits."""
    alphabet = string.ascii_letters + string.digits
    length = 10 + secrets.randbelow(3)
    return "".join(secrets.choice(alphabet) for _ in range(length))


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
        is_temp_password=True,
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
        is_temp_password=True,
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
            is_temp_password=True,
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
        if role == UserRole.TEACHER:
            query = query.where(cast(User.role, String).in_([UserRole.TEACHER.value, UserRole.CLASS_TEACHER.value]))
        else:
            query = query.where(User.role == role)
    query = query.order_by(User.name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def reset_user_password(
    db: AsyncSession,
    *,
    acting_user: User,
    target_user_id: int,
) -> str:
    """Reset a user's password with role and school scoping."""
    target_user = await get_user_by_id(db, target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if acting_user.role == UserRole.SUPER_ADMIN:
        pass
    elif acting_user.role == UserRole.SCHOOL_ADMIN:
        if target_user.school_id != acting_user.school_id:
            raise HTTPException(status_code=403, detail="You cannot reset passwords outside your school.")
        if target_user.role not in {UserRole.TEACHER, UserRole.CLASS_TEACHER, UserRole.PARENT}:
            raise HTTPException(status_code=403, detail="You can only reset teacher and parent passwords.")
    else:
        raise HTTPException(status_code=403, detail="You do not have permission to reset passwords.")

    temp_password = generate_temp_password()
    target_user.password_hash = hash_password(temp_password)
    target_user.is_temp_password = True
    target_user.must_change_password = True
    await db.flush()
    return temp_password


async def update_teacher_profile(
    db: AsyncSession,
    *,
    acting_user: User,
    teacher_id: int,
    name: str,
    phone: str | None,
) -> User:
    """Update a teacher within the acting school admin's school."""
    if acting_user.role != UserRole.SCHOOL_ADMIN:
        raise HTTPException(status_code=403, detail="Only school admins can update teachers.")

    teacher = await get_user_by_id(db, teacher_id)
    if not teacher or teacher.role not in (UserRole.TEACHER, UserRole.CLASS_TEACHER):
        raise HTTPException(status_code=404, detail="Teacher not found.")
    if teacher.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot update teachers outside your school.")

    teacher.name = name.strip()
    teacher.phone_number = validate_phone_number(phone, required=True)
    await db.flush()
    return teacher


async def update_student_profile_by_school_admin(
    db: AsyncSession,
    *,
    acting_user: User,
    student_id: int,
    name: str,
    class_id: int,
    parent_phone: str | None,
) -> Student:
    """Update a student and parent contact details within a school admin's school."""
    if acting_user.role != UserRole.SCHOOL_ADMIN:
        raise HTTPException(status_code=403, detail="Only school admins can update students.")

    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    if student.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot update students outside your school.")

    class_result = await db.execute(
        select(Class).where(
            Class.id == class_id,
            Class.school_id == acting_user.school_id,
        )
    )
    class_ = class_result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found.")

    parent_result = await db.execute(select(User).where(User.id == student.parent_id))
    parent = parent_result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found.")

    student.name = name.strip()
    student.class_id = class_.id
    parent.phone_number = validate_phone_number(parent_phone, required=True)
    await db.flush()
    return student
