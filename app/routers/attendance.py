"""Attendance routes — mark and view attendance."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from datetime import date
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.class_ import Class, teacher_classes
from app.models.student import Student
from app.services.attendance_service import (
    bulk_mark_attendance, get_attendance_history, get_today_attendance
)

router = APIRouter(prefix="/attendance", tags=["attendance"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def attendance_index(
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN)),
):
    return RedirectResponse(url="/attendance/mark", status_code=303)


@router.get("/mark", response_class=HTMLResponse)
async def mark_attendance_page(request: Request, db: DBSession,
    class_id: int = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    # Get classes
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role == "teacher":
        result = await db.execute(
            select(Class).join(teacher_classes).where(
                teacher_classes.c.teacher_id == current_user.id).order_by(Class.name))
    else:
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    classes = result.scalars().all()

    students = []
    selected_class = None
    if class_id:
        selected_class = class_id
        students = await get_today_attendance(db, class_id)

    return templates.TemplateResponse("attendance/mark.html", {
        "request": request, "user": current_user,
        "classes": classes, "students": students,
        "selected_class": selected_class, "today": date.today().isoformat(),
        "success": None, "error": None,
    })


@router.post("/mark")
async def mark_attendance(request: Request, db: DBSession,
    class_id: int = Form(...), att_date: str = Form(...),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    form = await request.form()
    absent_ids = [int(v) for k, v in form.multi_items() if k == "absent"]
    parsed_date = date.fromisoformat(att_date)
    count = await bulk_mark_attendance(db, class_id, parsed_date, absent_ids, current_user.id)

    # Reload page with success
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role == "teacher":
        result = await db.execute(
            select(Class).join(teacher_classes).where(
                teacher_classes.c.teacher_id == current_user.id).order_by(Class.name))
    else:
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    classes = result.scalars().all()
    students = await get_today_attendance(db, class_id)

    return templates.TemplateResponse("attendance/mark.html", {
        "request": request, "user": current_user,
        "classes": classes, "students": students,
        "selected_class": class_id, "today": att_date,
        "success": f"Attendance saved for {count} students!", "error": None,
    })


@router.get("/history/{student_id}", response_class=HTMLResponse)
async def attendance_history(request: Request, student_id: int, db: DBSession,
    current_user: User = Depends(get_current_user)):
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        return RedirectResponse(url="/dashboard", status_code=303)

    records = await get_attendance_history(db, student_id, days=60)
    total = len(records)
    present = sum(1 for r in records if r.is_present)
    pct = round(present / total * 100, 1) if total > 0 else 0

    return templates.TemplateResponse("attendance/history.html", {
        "request": request, "user": current_user,
        "student": student, "records": records,
        "total": total, "present": present, "pct": pct,
    })
