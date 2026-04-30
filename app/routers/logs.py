"""Audit log routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.dependencies import DBSession, get_current_user
from app.models.audit_log import AuditLog
from app.models.class_ import Class
from app.models.school import School
from app.models.user import User, UserRole

router = APIRouter(tags=["logs"])
templates = Jinja2Templates(directory="app/templates")


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "application/json" in accept


def _parse_int_filter(value: int | str | None) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_role_filter(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    allowed = {role.value for role in UserRole}
    return normalized if normalized in allowed else None


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    db: DBSession,
    current_user: User = Depends(get_current_user),
    school_id: int | str | None = None,
    class_id: int | str | None = None,
    role: str | None = None,
):
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to access logs.")

    selected_school_id = _parse_int_filter(school_id)
    selected_class_id = _parse_int_filter(class_id)
    selected_role = _normalize_role_filter(role)

    schools = []
    classes = []

    if current_user.role == UserRole.SUPER_ADMIN:
        school_result = await db.execute(select(School).order_by(School.name))
        schools = list(school_result.scalars().all())
        class_query = select(Class).order_by(Class.name)
        if selected_school_id is not None:
            class_query = class_query.where(Class.school_id == selected_school_id)
        class_result = await db.execute(class_query)
        classes = list(class_result.scalars().all())
    else:
        selected_school_id = current_user.school_id
        school_result = await db.execute(
            select(School).where(School.id == current_user.school_id)
        )
        school = school_result.scalar_one_or_none()
        schools = [school] if school else []
        class_result = await db.execute(
            select(Class)
            .where(Class.school_id == current_user.school_id)
            .order_by(Class.name)
        )
        classes = list(class_result.scalars().all())

    query = select(AuditLog)

    if current_user.role == UserRole.SCHOOL_ADMIN:
        query = query.where(AuditLog.school_id == current_user.school_id)

    if selected_school_id is not None and current_user.role == UserRole.SUPER_ADMIN:
        query = query.where(AuditLog.school_id == selected_school_id)

    if selected_class_id is not None:
        query = query.where(AuditLog.class_id == selected_class_id)

    if selected_role is not None:
        query = query.where(AuditLog.role == selected_role)

    query = query.order_by(AuditLog.timestamp.desc())
    result = await db.execute(query)
    logs = list(result.scalars().all())

    if _wants_json(request):
        return JSONResponse([
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if getattr(log.timestamp, "isoformat", None) else str(log.timestamp),
                "action": log.action,
                "performed_by": log.performed_by,
                "target_user": log.target_user,
                "role": log.role,
                "school_id": log.school_id,
                "class_id": log.class_id,
            }
            for log in logs
        ])

    return templates.TemplateResponse(
        "logs/index.html",
        {
            "request": request,
            "user": current_user,
            "schools": schools,
            "classes": classes,
            "selected_school_id": selected_school_id,
            "selected_class_id": selected_class_id,
            "selected_role": selected_role,
            "logs": logs,
        },
    )
