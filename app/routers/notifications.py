"""Notification routes — send and view."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.class_ import Class
from app.services.notification_service import (
    send_notification, get_notifications_for_school, get_notifications_for_parent
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
templates = Jinja2Templates(directory="app/templates")

NOTIFICATION_TEMPLATES = [
    {"title": "Holiday Notice", "message": "Dear Parents, please note that the school will remain closed on the mentioned date. Thank you."},
    {"title": "Exam Schedule", "message": "Dear Parents, exams are scheduled to begin soon. Please ensure your child prepares well."},
    {"title": "Fee Reminder", "message": "This is a reminder to clear any pending fee dues at the earliest. Thank you."},
    {"title": "Parent-Teacher Meeting", "message": "You are invited to attend the Parent-Teacher Meeting. Your participation is important."},
    {"title": "General Announcement", "message": ""},
]


@router.get("/send", response_class=HTMLResponse)
async def send_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    return templates.TemplateResponse("notifications/send.html", {
        "request": request, "user": current_user,
        "classes": result.scalars().all(), "templates": NOTIFICATION_TEMPLATES,
        "success": None, "error": None,
    })


@router.post("/send")
async def send(request: Request, db: DBSession,
    title: str = Form(...), message: str = Form(...),
    is_school_wide: bool = Form(False),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    form = await request.form()
    class_ids = [int(v) for k, v in form.multi_items() if k == "class_ids"]
    school_wide = "is_school_wide" in form

    await send_notification(
        db, title, message, current_user.school_id,
        current_user.id, class_ids if not school_wide else None, school_wide)

    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    return templates.TemplateResponse("notifications/send.html", {
        "request": request, "user": current_user,
        "classes": result.scalars().all(), "templates": NOTIFICATION_TEMPLATES,
        "success": "Notification sent successfully!", "error": None,
    })


@router.get("", response_class=HTMLResponse)
async def list_notifications(request: Request, db: DBSession,
    current_user: User = Depends(get_current_user)):
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role == "parent":
        notifications = await get_notifications_for_parent(db, current_user.id, current_user.school_id)
    else:
        notifications = await get_notifications_for_school(db, current_user.school_id)

    return templates.TemplateResponse("notifications/list.html", {
        "request": request, "user": current_user,
        "notifications": notifications,
    })
