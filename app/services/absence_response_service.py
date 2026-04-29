"""Parent absence response workflows."""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.absence_response import AbsenceResponse
from app.models.attendance import Attendance
from app.models.class_ import Class, ClassSubject, teacher_classes
from app.models.student import Student
from app.models.user import User
from app.services.permissions import can_view_student, is_parent, is_school_admin, is_super_admin, is_teacher


async def save_absence_response(
    db: AsyncSession,
    *,
    student_id: int,
    absence_date: date,
    message: str,
    leave_days: int | None,
    parent_user: User,
) -> AbsenceResponse:
    """Create or update the parent's explanation for an absence."""
    if not is_parent(parent_user):
        raise PermissionError("Only parents can submit absence responses.")
    if not await can_view_student(parent_user, db, student_id):
        raise PermissionError("You can only respond for your own child.")

    attendance_result = await db.execute(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.date == absence_date,
            Attendance.is_present == False,
        )
    )
    attendance = attendance_result.scalar_one_or_none()
    if not attendance:
        raise ValueError("Absence record not found for this student and date.")

    response_result = await db.execute(
        select(AbsenceResponse).where(
            AbsenceResponse.student_id == student_id,
            AbsenceResponse.date == absence_date,
        )
    )
    response = response_result.scalar_one_or_none()
    if not response:
        response = AbsenceResponse(
            student_id=student_id,
            date=absence_date,
            created_by_parent=parent_user.id,
        )
        db.add(response)

    response.message = message.strip()
    response.is_read = True
    response.leave_days = leave_days
    await db.flush()
    return response


async def get_parent_absence_alerts(db: AsyncSession, parent_user: User) -> list[dict]:
    """Return absence items for a parent's children, with response status."""
    result = await db.execute(
        select(Attendance, Student, Class, AbsenceResponse)
        .join(Student, Student.id == Attendance.student_id)
        .join(Class, Class.id == Student.class_id)
        .outerjoin(
            AbsenceResponse,
            and_(
                AbsenceResponse.student_id == Attendance.student_id,
                AbsenceResponse.date == Attendance.date,
            ),
        )
        .where(
            Student.parent_id == parent_user.id,
            Attendance.is_present == False,
        )
        .order_by(Attendance.date.desc())
    )

    alerts = []
    for attendance, student, class_, response in result.all():
        alerts.append(
            {
                "student": student,
                "class_name": class_.name,
                "date": attendance.date,
                "response": response,
                "requires_response": response is None,
            }
        )
    return alerts


async def get_visible_absence_responses(db: AsyncSession, viewer: User) -> list[dict]:
    """Return responses visible to admins and teachers."""
    query = (
        select(AbsenceResponse, Student, Class, User)
        .join(Student, Student.id == AbsenceResponse.student_id)
        .join(Class, Class.id == Student.class_id)
        .join(User, User.id == AbsenceResponse.created_by_parent)
        .order_by(AbsenceResponse.date.desc(), Student.name)
    )

    if is_super_admin(viewer):
        pass
    elif is_school_admin(viewer):
        query = query.where(Student.school_id == viewer.school_id)
    elif is_teacher(viewer):
        query = query.where(
            Student.school_id == viewer.school_id,
            (
                (Class.class_teacher_id == viewer.id)
                | Class.id.in_(
                    select(ClassSubject.class_id).where(ClassSubject.teacher_id == viewer.id)
                )
                | Class.id.in_(
                    select(teacher_classes.c.class_id).where(teacher_classes.c.teacher_id == viewer.id)
                )
            ),
        )
    else:
        return []

    result = await db.execute(query)
    rows = []
    for response, student, class_, parent in result.all():
        rows.append(
            {
                "response": response,
                "student": student,
                "class_name": class_.name,
                "parent": parent,
            }
        )
    return rows
