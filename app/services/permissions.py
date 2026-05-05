"""Central permission helpers for academic actions and visibility."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.absence_response import AbsenceResponse
from app.models.class_ import Class, ClassSubject, teacher_classes
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User, UserRole


@dataclass
class StudentScope:
    student: Student
    class_: Class


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def is_super_admin(user: User) -> bool:
    return _role_value(user) == UserRole.SUPER_ADMIN.value


def is_school_admin(user: User) -> bool:
    return _role_value(user) == UserRole.SCHOOL_ADMIN.value


def is_teacher(user: User) -> bool:
    return _role_value(user) == UserRole.TEACHER.value


def is_class_teacher(user: User) -> bool:
    return _role_value(user) == UserRole.CLASS_TEACHER.value


def is_teacher_like(user: User) -> bool:
    return is_teacher(user) or is_class_teacher(user)


def is_parent(user: User) -> bool:
    return _role_value(user) == UserRole.PARENT.value


async def _get_class(db: AsyncSession, class_id: int) -> Class | None:
    result = await db.execute(select(Class).where(Class.id == class_id))
    return result.scalar_one_or_none()


async def _get_student_scope(db: AsyncSession, student_id: int) -> StudentScope | None:
    result = await db.execute(
        select(Student, Class)
        .join(Class, Class.id == Student.class_id)
        .where(Student.id == student_id)
    )
    row = result.first()
    if not row:
        return None
    return StudentScope(student=row[0], class_=row[1])


async def _teacher_has_subject_assignment(
    db: AsyncSession,
    teacher_id: int,
    class_id: int,
    subject_id: int | None = None,
) -> bool:
    query = select(
        exists().where(
            and_(
                ClassSubject.teacher_id == teacher_id,
                ClassSubject.class_id == class_id,
            )
        )
    )
    if subject_id is not None:
        query = select(
            exists().where(
                and_(
                    ClassSubject.teacher_id == teacher_id,
                    ClassSubject.class_id == class_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        )
    return bool((await db.execute(query)).scalar())


async def _teacher_has_legacy_class_access(db: AsyncSession, teacher_id: int, class_id: int) -> bool:
    query = select(
        exists().where(
            and_(
                teacher_classes.c.teacher_id == teacher_id,
                teacher_classes.c.class_id == class_id,
            )
        )
    )
    return bool((await db.execute(query)).scalar())


async def _class_has_subject_mappings(db: AsyncSession, class_id: int) -> bool:
    query = select(func.count(ClassSubject.id)).where(ClassSubject.class_id == class_id)
    return ((await db.execute(query)).scalar() or 0) > 0


async def get_allowed_classes(
    db: AsyncSession,
    user: User,
    school_id: int | None = None,
) -> list[Class]:
    if is_super_admin(user):
        query = select(Class).order_by(Class.name)
        if school_id is not None:
            query = query.where(Class.school_id == school_id)
    elif is_school_admin(user):
        query = select(Class).where(Class.school_id == user.school_id).order_by(Class.name)
    elif is_teacher_like(user):
        query = (
            select(Class)
            .where(
                or_(
                    Class.class_teacher_id == user.id,
                    exists().where(
                        and_(
                            teacher_classes.c.teacher_id == user.id,
                            teacher_classes.c.class_id == Class.id,
                        )
                    ),
                    exists().where(
                        and_(
                            ClassSubject.teacher_id == user.id,
                            ClassSubject.class_id == Class.id,
                        )
                    ),
                )
            )
            .order_by(Class.name)
        )
        if school_id is not None:
            query = query.where(Class.school_id == school_id)
    else:
        return []

    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_allowed_subjects_for_class(db: AsyncSession, user: User, class_id: int) -> list[Subject]:
    class_ = await _get_class(db, class_id)
    if not class_:
        return []

    if is_super_admin(user) or (is_school_admin(user) and class_.school_id == user.school_id):
        query = select(Subject).where(Subject.school_id == class_.school_id).order_by(Subject.name)
        result = await db.execute(query)
        return list(result.scalars().all())

    if not is_teacher_like(user):
        return []

    if class_.class_teacher_id == user.id:
        result = await db.execute(
            select(Subject).where(Subject.school_id == class_.school_id).order_by(Subject.name)
        )
        return list(result.scalars().all())

    has_mappings = await _class_has_subject_mappings(db, class_id)
    if not has_mappings and await _teacher_has_legacy_class_access(db, user.id, class_id):
        result = await db.execute(
            select(Subject).where(Subject.school_id == class_.school_id).order_by(Subject.name)
        )
        return list(result.scalars().all())

    result = await db.execute(
        select(Subject)
        .join(ClassSubject, ClassSubject.subject_id == Subject.id)
        .where(
            ClassSubject.class_id == class_id,
            ClassSubject.teacher_id == user.id,
        )
        .order_by(Subject.name)
    )
    return list(result.scalars().unique().all())


async def can_edit_marks(user: User, db: AsyncSession, class_id: int, subject_id: int) -> bool:
    class_ = await _get_class(db, class_id)
    if not class_:
        return False

    if is_super_admin(user):
        return True
    if is_school_admin(user):
        return class_.school_id == user.school_id
    if not is_teacher_like(user):
        return False
    if class_.school_id != user.school_id:
        return False
    if class_.class_teacher_id == user.id:
        return True
    if await _teacher_has_subject_assignment(db, user.id, class_id, subject_id):
        return True
    if not await _class_has_subject_mappings(db, class_id):
        return await _teacher_has_legacy_class_access(db, user.id, class_id)
    return False


async def can_mark_attendance(user: User, db: AsyncSession, class_id: int) -> bool:
    class_ = await _get_class(db, class_id)
    if not class_:
        return False

    if is_super_admin(user):
        return True
    if is_school_admin(user):
        return class_.school_id == user.school_id
    if not is_teacher(user):
        return False
    if class_.school_id != user.school_id:
        return False
    if class_.class_teacher_id == user.id:
        return True
    if await _teacher_has_subject_assignment(db, user.id, class_id):
        return True
    return await _teacher_has_legacy_class_access(db, user.id, class_id)


async def can_view_student(user: User, db: AsyncSession, student_id: int) -> bool:
    scope = await _get_student_scope(db, student_id)
    if not scope:
        return False

    student = scope.student
    class_ = scope.class_

    if is_super_admin(user):
        return True
    if is_school_admin(user):
        return student.school_id == user.school_id
    if is_parent(user):
        return student.parent_id == user.id
    if not is_teacher_like(user) or class_.school_id != user.school_id:
        return False
    if class_.class_teacher_id == user.id:
        return True
    if await _teacher_has_subject_assignment(db, user.id, class_.id):
        return True
    return await _teacher_has_legacy_class_access(db, user.id, class_.id)


async def can_view_absence_response(user: User, db: AsyncSession, response: AbsenceResponse) -> bool:
    return await can_view_student(user, db, response.student_id)
