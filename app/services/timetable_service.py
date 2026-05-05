"""Timetable validation and retrieval helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import time

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timetable import TimetableSlot


def _normalize_time(value: time | str) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(value)


def group_timetable_slots_by_day(slots: list[TimetableSlot]) -> list[dict]:
    grouped: dict[int, list[TimetableSlot]] = defaultdict(list)
    for slot in sorted(slots, key=lambda row: (row.day_of_week, row.period_number, row.start_time)):
        grouped[slot.day_of_week].append(slot)
    return [
        {"day": day_of_week, "slots": day_slots}
        for day_of_week, day_slots in grouped.items()
    ]


async def validate_timetable_slot_conflict(
    db: AsyncSession,
    *,
    class_id: int,
    teacher_id: int,
    day_of_week: int,
    period_number: int | None = None,
    start_time: time | str,
    end_time: time | str,
    exclude_slot_id: int | None = None,
) -> None:
    start = _normalize_time(start_time)
    end = _normalize_time(end_time)
    if period_number is not None:
        class_period_query = select(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.day_of_week == day_of_week,
            TimetableSlot.period_number == period_number,
        )
        teacher_period_query = select(TimetableSlot).where(
            TimetableSlot.teacher_id == teacher_id,
            TimetableSlot.day_of_week == day_of_week,
            TimetableSlot.period_number == period_number,
        )
        if exclude_slot_id is not None:
            class_period_query = class_period_query.where(TimetableSlot.id != exclude_slot_id)
            teacher_period_query = teacher_period_query.where(TimetableSlot.id != exclude_slot_id)

        class_period_result = await db.execute(class_period_query.limit(1))
        if class_period_result.first():
            raise ValueError("This class already has a subject assigned for the selected period.")

        teacher_period_result = await db.execute(teacher_period_query.limit(1))
        if teacher_period_result.first():
            raise ValueError("This teacher is already assigned to another class for the selected period.")

    overlap = and_(
        TimetableSlot.day_of_week == day_of_week,
        TimetableSlot.start_time < end,
        TimetableSlot.end_time > start,
    )

    class_query = select(TimetableSlot).where(TimetableSlot.class_id == class_id, overlap)
    teacher_query = select(TimetableSlot).where(TimetableSlot.teacher_id == teacher_id, overlap)
    if exclude_slot_id is not None:
        class_query = class_query.where(TimetableSlot.id != exclude_slot_id)
        teacher_query = teacher_query.where(TimetableSlot.id != exclude_slot_id)

    class_result = await db.execute(class_query.limit(1))
    if class_result.first():
        raise ValueError("This class already has a timetable slot that overlaps with the selected time.")

    teacher_result = await db.execute(teacher_query.limit(1))
    if teacher_result.first():
        raise ValueError("This teacher is already assigned to another class during the selected time.")


async def get_teacher_timetable(db: AsyncSession, *, teacher_id: int) -> list[TimetableSlot]:
    result = await db.execute(
        select(TimetableSlot)
        .where(TimetableSlot.teacher_id == teacher_id)
        .order_by(TimetableSlot.day_of_week, TimetableSlot.period_number, TimetableSlot.start_time)
    )
    return list(result.scalars().all())
