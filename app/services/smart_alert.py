"""Smart Alert — detect students with high absence rates."""

from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.notification import Notification


async def check_absence_alerts(db: AsyncSession, school_id: int) -> list[dict]:
    """
    Check for students absent ≥3 days in the last 5 school days.
    Returns list of alert dicts with student info.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=7)  # Look back 7 calendar days for ~5 school days

    # Find students with ≥3 absences in the window
    result = await db.execute(
        select(
            Attendance.student_id,
            func.count(Attendance.id).label("absent_count")
        )
        .join(Student, Student.id == Attendance.student_id)
        .where(
            Student.school_id == school_id,
            Attendance.is_present == False,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .group_by(Attendance.student_id)
        .having(func.count(Attendance.id) >= 3)
    )

    alerts = []
    for row in result:
        student_result = await db.execute(
            select(Student).where(Student.id == row.student_id)
        )
        student = student_result.scalar_one_or_none()
        if student:
            alerts.append({
                "student_id": student.id,
                "student_name": student.name,
                "class_id": student.class_id,
                "parent_id": student.parent_id,
                "absent_count": row.absent_count,
            })

    return alerts


async def generate_absence_notifications(db: AsyncSession, school_id: int, sent_by: int) -> int:
    """Generate notifications for students with high absence rates."""
    alerts = await check_absence_alerts(db, school_id)
    count = 0

    for alert in alerts:
        notification = Notification(
            title="⚠️ Attendance Alert",
            message=f"{alert['student_name']} has been absent {alert['absent_count']} times in the last 5 school days. Please contact the school if needed.",
            school_id=school_id,
            sent_by=sent_by,
            is_school_wide=False,
        )
        db.add(notification)
        count += 1

    if count > 0:
        await db.flush()

    return count
