"""Attendance routes — role-scoped marking and visibility."""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from datetime import date
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.student import Student
from app.services.attendance_service import (
    bulk_mark_attendance, get_attendance_history, get_today_attendance
)
from app.services.permissions import can_mark_attendance, can_view_student, get_allowed_classes
from app.services.school_scope import resolve_school_scope
from app.services.student_view_service import get_student_absence_history

router = APIRouter(prefix="/attendance", tags=["attendance"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def attendance_index(
    school_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    target = "/attendance/mark"
    if school_id is not None:
        target = f"{target}?school_id={school_id}"
    return RedirectResponse(url=target, status_code=303)


@router.get("/mark", response_class=HTMLResponse)
async def mark_attendance_page(request: Request, db: DBSession,
    class_id: int = None,
    school_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN))):
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
    effective_school_id = school.id if school else None
    classes = await get_allowed_classes(db, current_user, school_id=effective_school_id)
    allowed_class_ids = {cls.id for cls in classes}

    students = []
    selected_class = None
    if class_id:
        if class_id not in allowed_class_ids or not await can_mark_attendance(current_user, db, class_id):
            raise HTTPException(status_code=403, detail="You do not have permission to mark attendance for this class.")
        selected_class = class_id
        students = await get_today_attendance(db, class_id)

    return templates.TemplateResponse("attendance/mark.html", {
        "request": request, "user": current_user,
        "classes": classes, "students": students,
        "selected_class": selected_class, "today": date.today().isoformat(),
        "success": None, "error": None,
        "active_school_id": effective_school_id,
    })


@router.post("/mark")
async def mark_attendance(request: Request, db: DBSession,
    class_id: int = Form(...), att_date: str = Form(...), school_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN))):
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
    effective_school_id = school.id if school else None
    classes = await get_allowed_classes(db, current_user, school_id=effective_school_id)
    allowed_class_ids = {cls.id for cls in classes}
    if class_id not in allowed_class_ids:
        raise HTTPException(status_code=403, detail="You do not have permission to mark attendance for this class.")
    if not await can_mark_attendance(current_user, db, class_id):
        raise HTTPException(status_code=403, detail="You do not have permission to mark attendance for this class.")

    form = await request.form()
    absent_ids = [int(v) for k, v in form.multi_items() if k == "absent"]
    parsed_date = date.fromisoformat(att_date)
    count = await bulk_mark_attendance(db, class_id, parsed_date, absent_ids, current_user.id)

    # Reload page with success
    students = await get_today_attendance(db, class_id)

    return templates.TemplateResponse("attendance/mark.html", {
        "request": request, "user": current_user,
        "classes": classes, "students": students,
        "selected_class": class_id, "today": att_date,
        "success": f"Attendance saved for {count} students!", "error": None,
        "active_school_id": effective_school_id,
    })


@router.get("/history/{student_id}", response_class=HTMLResponse)
async def attendance_history(request: Request, student_id: int, db: DBSession,
    current_user: User = Depends(get_current_user)):
    if not await can_view_student(current_user, db, student_id):
        raise HTTPException(status_code=403, detail="You do not have permission to view this attendance history.")

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
        "absence_rows": [],
    })


@router.get("/{student_id}/history", response_class=HTMLResponse)
async def attendance_history_with_leaves(
    request: Request,
    student_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    if not await can_view_student(current_user, db, student_id):
        raise HTTPException(status_code=403, detail="You do not have permission to view this attendance history.")

    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        return RedirectResponse(url="/dashboard", status_code=303)

    records = await get_attendance_history(db, student_id, days=60)
    total = len(records)
    present = sum(1 for r in records if r.is_present)
    pct = round(present / total * 100, 1) if total > 0 else 0
    absence_history = await get_student_absence_history(db, student_id=student_id)

    return templates.TemplateResponse("attendance/history.html", {
        "request": request,
        "user": current_user,
        "student": student,
        "records": records,
        "total": total,
        "present": present,
        "pct": pct,
        "absence_rows": absence_history["rows"] if absence_history else [],
    })
