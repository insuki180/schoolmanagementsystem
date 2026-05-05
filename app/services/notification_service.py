"""Notification service — send and retrieve notifications."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.notification import Notification
from app.models.class_ import Class
from app.models.student import Student


def build_notification_dedup_key(*, student_id: int, reference_date, notification_type: str) -> str:
    date_value = reference_date.isoformat() if hasattr(reference_date, "isoformat") else str(reference_date)
    return f"{student_id}:{date_value}:{notification_type}"


async def send_notification(
    db: AsyncSession, title: str, message: str, school_id: int,
    sent_by: int, class_ids: list[int] = None, is_school_wide: bool = False,
    dedup_key: str | None = None,
) -> Notification:
    """Create and send a notification to specific classes or school-wide."""
    if dedup_key:
        existing_result = await db.execute(
            select(Notification).where(Notification.dedup_key == dedup_key)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return existing

    target_classes = []
    if class_ids and not is_school_wide:
        result = await db.execute(
            select(Class).where(Class.id.in_(class_ids), Class.school_id == school_id)
        )
        target_classes = list(result.scalars().all())

    notification = Notification(
        title=title,
        message=message,
        school_id=school_id,
        sent_by=sent_by,
        is_school_wide=is_school_wide,
        dedup_key=dedup_key,
        target_classes=target_classes,
    )
    db.add(notification)
    await db.flush()

    return notification


async def get_notifications_for_school(
    db: AsyncSession, school_id: int, limit: int = 50
) -> list[Notification]:
    """Get recent notifications for a school."""
    result = await db.execute(
        select(Notification)
        .where(Notification.school_id == school_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_notifications_for_parent(
    db: AsyncSession, parent_id: int, school_id: int
) -> list[Notification]:
    """Get notifications relevant to a parent (school-wide + class + personal)."""
    result = await db.execute(
        select(Student.id, Student.class_id).where(Student.parent_id == parent_id)
    )
    child_rows = result.all()
    child_ids = [row[0] for row in child_rows]
    child_class_ids = [row[1] for row in child_rows]

    # Get school-wide notifications
    school_wide = await db.execute(
        select(Notification)
        .where(
            Notification.school_id == school_id,
            Notification.is_school_wide == True,
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = list(school_wide.scalars().all())

    # Get class-specific notifications
    if child_class_ids:
        from app.models.notification import notification_classes
        class_notifs = await db.execute(
            select(Notification)
            .join(notification_classes)
            .where(
                Notification.school_id == school_id,
                notification_classes.c.class_id.in_(child_class_ids),
            )
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        notifications.extend(class_notifs.scalars().all())

    if child_ids:
        personal = await db.execute(
            select(Notification)
            .where(
                Notification.school_id == school_id,
                Notification.target_student_id.in_(child_ids),
            )
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        notifications.extend(personal.scalars().all())

    # Deduplicate and sort
    seen = set()
    unique = []
    for n in notifications:
        if n.id not in seen:
            seen.add(n.id)
            unique.append(n)

    unique.sort(key=lambda x: x.created_at or "", reverse=True)
    return unique[:50]


async def send_personal_notification(
    db: AsyncSession,
    *,
    title: str,
    message: str,
    school_id: int | None,
    sent_by: int,
    student_id: int,
) -> Notification:
    """Create a notification for one student only."""
    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    if not student or (school_id is not None and student.school_id != school_id):
        raise ValueError("Student not found for this school.")

    notification = Notification(
        title=title,
        message=message,
        school_id=school_id,
        sent_by=sent_by,
        target_student_id=student_id,
        is_school_wide=False,
    )
    db.add(notification)
    await db.flush()
    return notification
