"""Helpers for resolving the active school scope per request."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.user import User, UserRole


async def resolve_school_scope(
    db: AsyncSession,
    user: User,
    requested_school_id: int | None,
    *,
    required_for_super_admin: bool = False,
) -> School | None:
    """Return the effective school for the current request."""
    if user.role == UserRole.SUPER_ADMIN:
        if requested_school_id is None:
            if required_for_super_admin:
                raise HTTPException(status_code=400, detail="Super admin must select a school first.")
            return None

        school_result = await db.execute(select(School).where(School.id == requested_school_id))
        school = school_result.scalar_one_or_none()
        if not school:
            raise HTTPException(status_code=404, detail="School not found.")
        return school

    if user.school_id is None:
        return None

    if requested_school_id is not None and requested_school_id != user.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to that school.")

    school_result = await db.execute(select(School).where(School.id == user.school_id))
    school = school_result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    return school
