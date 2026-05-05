"""Timetable APIs for viewing and editing class schedules."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession, get_current_user
from app.models.class_ import Class
from app.models.student import Student
from app.models.timetable import TimetableSlot
from app.models.user import User, UserRole
from app.schemas.timetable import TimetableSlotCreateRequest
from app.services.permissions import is_super_admin
from app.services.timetable_service import (
    get_teacher_timetable,
    group_timetable_slots_by_day,
    validate_timetable_slot_conflict,
)

router = APIRouter(prefix="/timetable", tags=["timetable"])


async def _get_class_or_404(db, class_id: int) -> Class:
    result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found.")
    return class_


def _serialize_slot(slot: TimetableSlot) -> dict:
    return {
        "id": slot.id,
        "class_id": slot.class_id,
        "day": slot.day_of_week,
        "period_number": slot.period_number,
        "subject": slot.subject_name,
        "teacher_id": slot.teacher_id,
        "teacher": getattr(getattr(slot, "teacher", None), "name", None),
        "start_time": slot.start_time.isoformat(),
        "time": {"start": slot.start_time.isoformat(), "end": slot.end_time.isoformat()},
    }


@router.get("/class/{class_id}")
async def get_timetable(
    class_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    class_ = await _get_class_or_404(db, class_id)
    if current_user.role == UserRole.PARENT:
        child_result = await db.execute(select(Student).where(Student.parent_id == current_user.id, Student.class_id == class_id))
        if child_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="You do not have access to this timetable.")
    elif not is_super_admin(current_user) and class_.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to this timetable.")

    result = await db.execute(
        select(TimetableSlot)
        .where(TimetableSlot.class_id == class_id)
        .order_by(TimetableSlot.day_of_week, TimetableSlot.period_number, TimetableSlot.start_time)
    )
    return [_serialize_slot(slot) for slot in result.scalars().all()]


@router.post("/class/{class_id}")
async def create_timetable_slot(
    class_id: int,
    payload: TimetableSlotCreateRequest,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    class_ = await _get_class_or_404(db, class_id)
    if class_.class_teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the class teacher can edit this timetable.")
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")
    try:
        await validate_timetable_slot_conflict(
            db,
            class_id=class_id,
            teacher_id=payload.teacher_id,
            day_of_week=payload.day_of_week,
            period_number=payload.period_number,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slot = TimetableSlot(
        class_id=class_id,
        day_of_week=payload.day_of_week,
        period_number=payload.period_number,
        subject_name=payload.subject_name.strip(),
        teacher_id=payload.teacher_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(slot)
    await db.flush()
    return _serialize_slot(slot)


@router.get("/teacher/{teacher_id}")
async def get_teacher_timetable_view(
    teacher_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.PARENT:
        raise HTTPException(status_code=403, detail="You do not have access to this timetable.")
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN) and current_user.id != teacher_id:
        raise HTTPException(status_code=403, detail="You do not have access to this timetable.")

    slots = await get_teacher_timetable(db, teacher_id=teacher_id)
    if current_user.role == UserRole.SCHOOL_ADMIN:
        for slot in slots:
            class_ = await _get_class_or_404(db, slot.class_id)
            if class_.school_id != current_user.school_id:
                raise HTTPException(status_code=403, detail="You do not have access to this timetable.")
    grouped = group_timetable_slots_by_day(slots)
    return {
        "teacher_id": teacher_id,
        "slots": [_serialize_slot(slot) for slot in slots],
        "grouped_by_day": [
            {
                "day": bucket["day"],
                "slots": [_serialize_slot(slot) for slot in bucket["slots"]],
            }
            for bucket in grouped
        ],
    }
