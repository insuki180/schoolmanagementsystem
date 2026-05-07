"""FastAPI dependencies — auth guards, DB session, role checks."""

from typing import Annotated
from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.services.auth_service import decode_access_token
from app.models.school import School
from app.models.user import User, UserRole
from app.services.navigation_service import build_role_navigation
from sqlalchemy import select
from sqlalchemy.orm import selectinload


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Extract and validate JWT from cookie. Returns the authenticated User."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    # Fetch full user from DB
    result = await db.execute(
        select(User)
        .options(selectinload(User.school))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    request.state.user = user
    request.state.nav_config = build_role_navigation(user.role.value)
    request.state.school_options = []
    request.state.active_school_id = None

    if user.role == UserRole.SUPER_ADMIN:
        schools_result = await db.execute(select(School).order_by(School.name))
        request.state.school_options = list(schools_result.scalars().all())
    elif user.school_id:
        school_result = await db.execute(select(School).where(School.id == user.school_id))
        school = school_result.scalar_one_or_none()
        if school:
            request.state.school_options = [school]

    return user


def require_role(*roles: UserRole):
    """Dependency factory that checks if the current user has one of the required roles."""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource.",
            )
        return current_user
    return role_checker


# Type aliases for cleaner route signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
