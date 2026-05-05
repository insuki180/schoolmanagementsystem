"""Notification routes — send, view, and parent absence responses."""

from datetime import date

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role, get_current_user
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.class_ import Class
from app.services.notification_service import (
    get_notifications_for_parent,
    get_notifications_for_school,
    send_notification,
    send_personal_notification,
)
from app.services.absence_response_service import (
    get_parent_absence_alerts,
    get_visible_absence_responses,
    save_absence_response,
)
from app.services.attendance_service import create_attendance_message
from app.services.permissions import can_view_student, is_parent
from app.services.school_scope import resolve_school_scope

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
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
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
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
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


@router.post("/personal")
async def send_personal(
    db: DBSession,
    student_id: int = Form(...),
    title: str = Form(...),
    message: str = Form(...),
    school_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    if not await can_view_student(current_user, db, student_id):
        raise HTTPException(status_code=403, detail="You do not have access to this student.")

    school = await resolve_school_scope(
        db,
        current_user,
        school_id,
        required_for_super_admin=current_user.role == UserRole.SUPER_ADMIN,
    )
    effective_school_id = school.id if school else current_user.school_id

    try:
        await send_personal_notification(
            db,
            title=title,
            message=message,
            school_id=effective_school_id,
            sent_by=current_user.id,
            student_id=student_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RedirectResponse(
        url=f"/students/{student_id}/details?school_id={effective_school_id}&success=Notification+sent+successfully",
        status_code=303,
    )


@router.get("", response_class=HTMLResponse)
async def list_notifications(request: Request, db: DBSession,
    school_id: int | None = None,
    current_user: User = Depends(get_current_user)):
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role == "parent":
        notifications = await get_notifications_for_parent(db, current_user.id, current_user.school_id)
        absence_alerts = await get_parent_absence_alerts(db, current_user)
        absence_responses = []
    elif role == "super_admin":
        school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
        result = await db.execute(
            select(Notification)
            .where(Notification.school_id == school.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        notifications = list(result.scalars().all())
        absence_alerts = []
        absence_responses = await get_visible_absence_responses(db, current_user, school_id=school.id)
    else:
        notifications = await get_notifications_for_school(db, current_user.school_id)
        absence_alerts = []
        absence_responses = await get_visible_absence_responses(db, current_user)

    return templates.TemplateResponse("notifications/list.html", {
        "request": request, "user": current_user,
        "notifications": notifications,
        "absence_alerts": absence_alerts,
        "absence_responses": absence_responses,
        "active_school_id": school_id if role == "super_admin" else current_user.school_id,
    })


@router.get("/view/{notification_id}", response_class=HTMLResponse)
async def notification_detail(
    request: Request,
    notification_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role == "parent":
        allowed_ids = {item.id for item in await get_notifications_for_parent(db, current_user.id, current_user.school_id)}
        if notification.id not in allowed_ids:
            raise HTTPException(status_code=403, detail="You do not have access to this notification.")
    elif role != "super_admin" and notification.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to this notification.")

    return templates.TemplateResponse(
        "notifications/detail.html",
        {
            "request": request,
            "user": current_user,
            "notification": notification,
        },
    )


@router.get("/absence/{student_id}/{absence_date}", response_class=HTMLResponse)
async def absence_response_page(
    request: Request,
    student_id: int,
    absence_date: str,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    if not await can_view_student(current_user, db, student_id):
        raise HTTPException(status_code=403, detail="You can only respond for your own child.")

    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    response_date = date.fromisoformat(absence_date)
    alerts = await get_parent_absence_alerts(db, current_user)
    alert = next((item for item in alerts if item["student"].id == student_id and item["date"] == response_date), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Absence notification not found.")

    return templates.TemplateResponse("notifications/absence_response.html", {
        "request": request,
        "user": current_user,
        "student": student,
        "absence_date": response_date,
        "existing_response": alert["response"],
        "error": None,
    })


@router.post("/absence/{student_id}/{absence_date}")
async def submit_absence_response(
    request: Request,
    student_id: int,
    absence_date: str,
    db: DBSession,
    message: str = Form(...),
    leave_days: int = Form(0),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    try:
        await save_absence_response(
            db,
            student_id=student_id,
            absence_date=date.fromisoformat(absence_date),
            message=message,
            leave_days=leave_days or None,
            parent_user=current_user,
        )
        await create_attendance_message(
            db,
            student_id=student_id,
            attendance_date=date.fromisoformat(absence_date),
            sender=current_user,
            message=message,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RedirectResponse(url="/notifications", status_code=303)
