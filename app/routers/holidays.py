"""Holiday APIs."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import DBSession, get_current_user
from app.models.user import User, UserRole
from app.schemas.holiday import HolidayCreateRequest
from app.services.holiday_service import create_holidays, delete_holiday, list_holidays

router = APIRouter(prefix="/holidays", tags=["holidays"])


@router.post("")
async def create_holiday(
    payload: HolidayCreateRequest,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.CLASS_TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to create holidays.")

    dates = set(payload.dates)
    if payload.date is not None:
        dates.add(payload.date)
    if payload.date is not None and payload.recurring_weeks > 0:
        for offset in range(1, payload.recurring_weeks + 1):
            dates.add(payload.date + timedelta(days=7 * offset))
    if not dates:
        raise HTTPException(status_code=400, detail="At least one holiday date is required.")

    holidays = await create_holidays(
        db,
        acting_user=current_user,
        school_id=payload.school_id,
        class_id=payload.class_id,
        dates=sorted(dates),
        title=payload.title,
        description=payload.description,
    )
    return [
        {
            "id": holiday.id,
            "school_id": holiday.school_id,
            "class_id": holiday.class_id,
            "date": holiday.date.isoformat(),
            "title": holiday.title,
            "description": holiday.description,
        }
        for holiday in holidays
    ]


@router.get("")
async def get_holidays(
    school_id: int,
    db: DBSession,
    class_id: int | None = None,
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.PARENT and class_id is None:
        raise HTTPException(status_code=403, detail="Class scope is required for parent holiday access.")
    rows = await list_holidays(db, school_id=school_id, class_id=class_id)
    return [
        {
            "id": holiday.id,
            "school_id": holiday.school_id,
            "class_id": holiday.class_id,
            "date": holiday.date.isoformat(),
            "title": holiday.title,
            "description": holiday.description,
        }
        for holiday in rows
    ]


@router.delete("/{holiday_id}")
async def remove_holiday(
    holiday_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    await delete_holiday(db, holiday_id=holiday_id, acting_user=current_user)
    return {"deleted": True, "holiday_id": holiday_id}
