"""Smart Alert — detect students with high absence rates."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance
from app.models.class_ import Class
from app.models.holiday import Holiday
from app.models.student import Student
from app.models.user import User
from app.services.contact_utils import get_whatsapp_link
from app.services.notification_service import build_notification_dedup_key, send_notification


def _gap_is_holiday_only(previous_date: date, current_date: date, holiday_dates: set[date]) -> bool:
    cursor = previous_date + timedelta(days=1)
    while cursor < current_date:
        if cursor not in holiday_dates:
            return False
        cursor += timedelta(days=1)
    return True


def calculate_consecutive_absence_streak(
    attendance_records: list[dict],
    *,
    holiday_dates: set[date] | None = None,
) -> tuple[int, date | None]:
    holiday_dates = holiday_dates or set()
    ordered_records = sorted(attendance_records, key=lambda row: row["date"])
    current_streak = 0
    best_streak = 0
    latest_absence_date = None
    previous_absence_date = None

    for record in ordered_records:
        record_date = record["date"]
        if record.get("is_present", False):
            current_streak = 0
            previous_absence_date = None
            continue

        if previous_absence_date is None:
            current_streak = 1
        elif (record_date - previous_absence_date).days == 1 or _gap_is_holiday_only(
            previous_absence_date,
            record_date,
            holiday_dates,
        ):
            current_streak += 1
        else:
            current_streak = 1

        previous_absence_date = record_date
        if current_streak >= best_streak:
            best_streak = current_streak
            latest_absence_date = record_date

    return best_streak, latest_absence_date


def detect_consecutive_absence_alerts(rows: list[dict], *, streak_length: int = 3, holiday_dates: set[date] | None = None) -> list[dict]:
    holiday_dates = holiday_dates or set()
    alerts = []
    for row in rows:
        attendance_records = row.get("attendance_records")
        if not attendance_records:
            attendance_records = [
                {"date": absence_date, "is_present": False}
                for absence_date in sorted(set(row.get("dates", [])))
            ]
        if not attendance_records:
            continue
        row_holiday_dates = row.get("holiday_dates", holiday_dates)
        best_streak, streak_end = calculate_consecutive_absence_streak(
            attendance_records,
            holiday_dates=row_holiday_dates,
        )
        if best_streak >= streak_length:
            alerts.append(
                {
                    **row,
                    "dates": [record["date"] for record in attendance_records if not record.get("is_present", False)],
                    "streak_length": best_streak,
                    "latest_absence_date": streak_end,
                }
            )
    return alerts


async def check_absence_alerts(db: AsyncSession, school_id: int) -> list[dict]:
    alerts = await get_consecutive_absence_alerts(
        db,
        school_id=school_id,
        streak_length=3,
        lookback_days=30,
    )
    return [
        {
            "student_id": alert["student_id"],
            "student_name": alert["student_name"],
            "class_id": alert["class_id"],
            "parent_id": alert["parent_id"],
            "absent_count": alert["streak_length"],
            "latest_absence_date": alert["latest_absence_date"],
        }
        for alert in alerts
    ]


async def get_consecutive_absence_alerts(
    db: AsyncSession,
    *,
    class_ids: list[int] | None = None,
    school_id: int | None = None,
    streak_length: int = 3,
    lookback_days: int = 30,
) -> list[dict]:
    window_start = date.today() - timedelta(days=lookback_days)
    query = (
        select(Attendance, Student, Class, User)
        .join(Student, Student.id == Attendance.student_id)
        .join(Class, Class.id == Student.class_id)
        .join(User, User.id == Student.parent_id)
        .where(
            Attendance.date >= window_start,
        )
        .order_by(Student.id, Attendance.date)
    )
    if school_id is not None:
        query = query.where(Student.school_id == school_id)
    if class_ids:
        query = query.where(Student.class_id.in_(class_ids))

    result = await db.execute(query)
    holiday_query = select(Holiday.class_id, Holiday.date).where(Holiday.date >= window_start, Holiday.date <= date.today())
    if school_id is not None:
        holiday_query = holiday_query.where(Holiday.school_id == school_id)
    if class_ids:
        holiday_query = holiday_query.where((Holiday.class_id == None) | (Holiday.class_id.in_(class_ids)))
    holiday_result = await db.execute(holiday_query)
    school_holiday_dates: set[date] = set()
    class_holiday_dates: dict[int, set[date]] = defaultdict(set)
    for class_id, holiday_date in holiday_result.all():
        if class_id is None:
            school_holiday_dates.add(holiday_date)
        else:
            class_holiday_dates[class_id].add(holiday_date)

    grouped: dict[int, dict] = {}
    for attendance, student, class_, parent in result.all():
        item = grouped.setdefault(
            student.id,
            {
                "student_id": student.id,
                "student_name": student.name,
                "class_id": student.class_id,
                "class_name": class_.name,
                "parent_id": student.parent_id,
                "parent_phone": parent.phone_number or "",
                "whatsapp_link": get_whatsapp_link(parent.phone_number),
                "dates": [],
                "attendance_records": [],
            },
        )
        item["attendance_records"].append(
            {
                "date": attendance.date,
                "is_present": attendance.is_present,
            }
        )
        if not attendance.is_present:
            item["dates"].append(attendance.date)

    for item in grouped.values():
        item["holiday_dates"] = school_holiday_dates | class_holiday_dates.get(item["class_id"], set())

    return detect_consecutive_absence_alerts(list(grouped.values()), streak_length=streak_length)


async def generate_absence_notifications(db: AsyncSession, school_id: int, sent_by: int) -> int:
    """Generate notifications for students with high absence rates."""
    alerts = await check_absence_alerts(db, school_id)
    count = 0

    for alert in alerts:
        dedup_key = build_notification_dedup_key(
            student_id=alert["student_id"],
            reference_date=date.today(),
            notification_type="absence_alert",
        )
        notification = await send_notification(
            db,
            title="⚠️ Attendance Alert",
            message=(
                f"{alert['student_name']} has been absent for {alert['absent_count']} consecutive working days. "
                "Please contact the school if needed."
            ),
            school_id=school_id,
            sent_by=sent_by,
            dedup_key=dedup_key,
            is_school_wide=False,
        )
        if notification:
            count += 1

    if count > 0:
        await db.flush()

    return count
