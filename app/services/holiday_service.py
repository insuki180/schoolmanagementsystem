"""Holiday management and holiday-aware attendance helpers."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.models.holiday import Holiday
from app.models.user import User, UserRole
from app.services.notification_service import build_notification_dedup_key, send_notification
from app.services.permissions import is_school_admin


async def create_holidays(
    db: AsyncSession,
    *,
    acting_user: User,
    school_id: int,
    class_id: int | None,
    dates: list[date],
    title: str,
    description: str | None,
) -> list[Holiday]:
    if acting_user.role not in (UserRole.CLASS_TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to create holidays.")
    if is_school_admin(acting_user) and acting_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="You cannot manage holidays outside your school.")
    if acting_user.role == UserRole.CLASS_TEACHER:
        if class_id is None:
            raise HTTPException(status_code=403, detail="Class teachers can only create class-level holidays.")
        class_result = await db.execute(select(Class).where(Class.id == class_id))
        class_ = class_result.scalar_one_or_none()
        if not class_ or class_.class_teacher_id != acting_user.id:
            raise HTTPException(status_code=403, detail="You can only create holidays for your own class.")

    existing_result = await db.execute(
        select(Holiday).where(
            Holiday.school_id == school_id,
            Holiday.class_id == class_id,
            Holiday.date.in_(dates),
        )
    )
    existing_dates = {row.date for row in existing_result.scalars().all()}
    created = []
    for holiday_date in sorted(set(dates)):
        if holiday_date in existing_dates:
            continue
        holiday = Holiday(
            school_id=school_id,
            class_id=class_id,
            date=holiday_date,
            title=title.strip(),
            description=(description or "").strip() or None,
            created_by=acting_user.id,
        )
        db.add(holiday)
        created.append(holiday)

        dedup_key = build_notification_dedup_key(
            student_id=class_id or school_id,
            reference_date=holiday_date,
            notification_type="holiday",
        )
        await send_notification(
            db,
            title=f"Holiday on {holiday_date.isoformat()}",
            message=f"Holiday on {holiday_date.isoformat()}: {title.strip()}",
            school_id=school_id,
            sent_by=acting_user.id,
            class_ids=[class_id] if class_id else None,
            is_school_wide=class_id is None,
            dedup_key=dedup_key,
        )

    await db.flush()
    return created


async def list_holidays(
    db: AsyncSession,
    *,
    school_id: int,
    class_id: int | None = None,
) -> list[Holiday]:
    query = select(Holiday).where(Holiday.school_id == school_id).order_by(Holiday.date, Holiday.id)
    if class_id is not None:
        query = query.where(or_(Holiday.class_id == None, Holiday.class_id == class_id))
    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_holiday(db: AsyncSession, *, holiday_id: int, acting_user: User) -> bool:
    result = await db.execute(select(Holiday).where(Holiday.id == holiday_id))
    holiday = result.scalar_one_or_none()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found.")
    if acting_user.role == UserRole.CLASS_TEACHER and holiday.class_id is not None:
        class_result = await db.execute(select(Class).where(Class.id == holiday.class_id))
        class_ = class_result.scalar_one_or_none()
        if not class_ or class_.class_teacher_id != acting_user.id:
            raise HTTPException(status_code=403, detail="You can only delete holidays for your own class.")
    elif acting_user.role == UserRole.SCHOOL_ADMIN and holiday.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot delete holidays outside your school.")
    elif acting_user.role not in (UserRole.CLASS_TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to delete holidays.")

    await db.execute(delete(Holiday).where(Holiday.id == holiday_id))
    return True


async def get_holiday_dates_for_class(
    db: AsyncSession,
    *,
    school_id: int,
    class_id: int | None,
    start_date: date,
    end_date: date,
) -> set[date]:
    result = await db.execute(
        select(Holiday.date).where(
            Holiday.school_id == school_id,
            Holiday.date >= start_date,
            Holiday.date <= end_date,
            or_(Holiday.class_id == None, Holiday.class_id == class_id),
        )
    )
    return {row[0] for row in result.all()}


async def is_holiday_for_class(
    db: AsyncSession,
    *,
    school_id: int,
    class_id: int | None,
    target_date: date,
) -> bool:
    dates = await get_holiday_dates_for_class(
        db,
        school_id=school_id,
        class_id=class_id,
        start_date=target_date,
        end_date=target_date,
    )
    return target_date in dates
