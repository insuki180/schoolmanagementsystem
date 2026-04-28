"""Attendance service — bulk marking, history, and summaries."""

from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.attendance import Attendance
from app.models.student import Student


from sqlalchemy.dialects.postgresql import insert

async def bulk_mark_attendance(
    db: AsyncSession, class_id: int, att_date: date,
    absent_student_ids: list[int], marked_by: int
) -> int:
    """
    Mark attendance for an entire class.
    All students default to present; only absent IDs are marked absent.
    Uses PostgreSQL UPSERT logic.
    Returns count of records created/updated.
    """
    # Get all students in the class
    result = await db.execute(
        select(Student.id).where(Student.class_id == class_id)
    )
    student_ids = [row[0] for row in result.all()]
    
    if not student_ids:
        return 0

    values = [
        {
            "student_id": s_id,
            "date": att_date,
            "is_present": s_id not in absent_student_ids,
            "marked_by": marked_by,
        }
        for s_id in student_ids
    ]

    stmt = insert(Attendance).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["student_id", "date"],
        set_={"is_present": stmt.excluded.is_present, "marked_by": stmt.excluded.marked_by}
    )

    await db.execute(stmt)
    await db.flush()
    return len(values)


async def get_attendance_history(
    db: AsyncSession, student_id: int, days: int = 30
) -> list[Attendance]:
    """Get attendance history for a student over the last N days."""
    start_date = date.today() - timedelta(days=days)
    result = await db.execute(
        select(Attendance)
        .where(
            Attendance.student_id == student_id,
            Attendance.date >= start_date,
        )
        .order_by(Attendance.date.desc())
    )
    return list(result.scalars().all())


async def get_class_attendance_summary(
    db: AsyncSession, class_id: int
) -> dict:
    """Get attendance summary stats for a class."""
    # Get all students in class
    result = await db.execute(
        select(Student).where(Student.class_id == class_id)
    )
    students = result.scalars().all()
    student_ids = [s.id for s in students]

    if not student_ids:
        return {"total_students": 0, "attendance_pct": 0}

    # Count total records and present records
    total_result = await db.execute(
        select(func.count(Attendance.id)).where(
            Attendance.student_id.in_(student_ids)
        )
    )
    total_records = total_result.scalar() or 0

    present_result = await db.execute(
        select(func.count(Attendance.id)).where(
            Attendance.student_id.in_(student_ids),
            Attendance.is_present == True,
        )
    )
    present_records = present_result.scalar() or 0

    pct = round((present_records / total_records * 100), 1) if total_records > 0 else 0

    return {
        "total_students": len(students),
        "total_records": total_records,
        "present_records": present_records,
        "attendance_pct": pct,
    }


async def get_today_attendance(db: AsyncSession, class_id: int) -> list[dict]:
    """Get today's attendance status for all students in a class."""
    today = date.today()
    result = await db.execute(
        select(Student).where(Student.class_id == class_id).order_by(Student.name)
    )
    students = result.scalars().all()

    attendance_data = []
    for student in students:
        att_result = await db.execute(
            select(Attendance).where(
                Attendance.student_id == student.id,
                Attendance.date == today,
            )
        )
        att = att_result.scalar_one_or_none()
        attendance_data.append({
            "student_id": student.id,
            "student_name": student.name,
            "is_present": att.is_present if att else None,  # None = not yet marked
            "already_marked": att is not None,
        })

    return attendance_data
