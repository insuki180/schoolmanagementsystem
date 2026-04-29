"""Student roster detail and attendance history helpers."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.absence_response import AbsenceResponse
from app.models.attendance import Attendance
from app.models.class_ import Class
from app.models.student import Student
from app.models.user import User
from app.services.contact_utils import get_whatsapp_link
from app.services.parent_portal_service import get_teacher_contacts_for_student


async def get_student_details_context(db: AsyncSession, *, student_id: int) -> dict | None:
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        return None

    parent_result = await db.execute(select(User).where(User.id == student.parent_id))
    parent = parent_result.scalar_one_or_none()
    class_result = await db.execute(select(Class).where(Class.id == student.class_id))
    class_ = class_result.scalar_one_or_none()
    teacher_contacts = await get_teacher_contacts_for_student(db, student)

    return {
        "student": student,
        "class_name": class_.name if class_ else "",
        "parent": parent,
        "parent_whatsapp": get_whatsapp_link(parent.phone_number if parent else None),
        "teacher_contacts": teacher_contacts,
    }


async def get_student_absence_history(db: AsyncSession, *, student_id: int) -> dict | None:
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        return None

    result = await db.execute(
        select(Attendance, AbsenceResponse)
        .outerjoin(
            AbsenceResponse,
            and_(
                AbsenceResponse.student_id == Attendance.student_id,
                AbsenceResponse.date == Attendance.date,
            ),
        )
        .where(
            Attendance.student_id == student_id,
            Attendance.is_present == False,
        )
        .order_by(Attendance.date.desc())
    )

    rows = []
    for attendance, response in result.all():
        rows.append(
            {
                "date": attendance.date,
                "status": "Absent",
                "parent_reply": response.message if response else "",
                "leave_duration": response.leave_days if response else None,
                "response": response,
            }
        )

    return {
        "student": student,
        "rows": rows,
    }
