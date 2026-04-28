"""Marks service — bulk entry, upsert, and summaries."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.mark import Mark
from app.models.student import Student


from sqlalchemy.dialects.postgresql import insert

async def bulk_upsert_marks(
    db: AsyncSession, subject_id: int, exam_id: int,
    entries: list[dict], entered_by: int
) -> int:
    """
    Bulk insert or update marks.
    Each entry: {"student_id": int, "marks_obtained": float, "max_marks": float}
    If record exists for student+subject+exam → UPDATE, else → INSERT.
    """
    if not entries:
        return 0

    values = [
        {
            "student_id": entry["student_id"],
            "subject_id": subject_id,
            "exam_id": exam_id,
            "marks_obtained": entry["marks_obtained"],
            "max_marks": entry.get("max_marks", 100.0),
            "entered_by": entered_by,
        }
        for entry in entries
    ]

    stmt = insert(Mark).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["student_id", "subject_id", "exam_id"],
        set_={
            "marks_obtained": stmt.excluded.marks_obtained,
            "max_marks": stmt.excluded.max_marks,
            "entered_by": stmt.excluded.entered_by,
        }
    )

    await db.execute(stmt)
    await db.flush()
    return len(values)


async def get_student_marks(db: AsyncSession, student_id: int) -> list[Mark]:
    """Get all marks for a student, ordered by exam."""
    result = await db.execute(
        select(Mark)
        .where(Mark.student_id == student_id)
        .order_by(Mark.exam_id, Mark.subject_id)
    )
    return list(result.scalars().all())


async def get_class_marks_summary(
    db: AsyncSession, class_id: int, exam_id: int | None = None
) -> dict:
    """Get marks summary for a class."""
    # Get student IDs in class
    result = await db.execute(
        select(Student.id).where(Student.class_id == class_id)
    )
    student_ids = [row[0] for row in result.all()]

    if not student_ids:
        return {"avg_marks": 0, "total_students": 0}

    query = select(func.avg(Mark.marks_obtained)).where(
        Mark.student_id.in_(student_ids)
    )
    if exam_id:
        query = query.where(Mark.exam_id == exam_id)

    avg_result = await db.execute(query)
    avg = avg_result.scalar() or 0

    return {
        "avg_marks": round(float(avg), 1),
        "total_students": len(student_ids),
    }
