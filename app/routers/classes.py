"""Class management routes."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.class_ import Class
from app.models.student import Student
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.mark import Mark

router = APIRouter(prefix="/classes", tags=["classes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_classes(request: Request, db: DBSession,
    current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    classes = result.scalars().all()
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    return templates.TemplateResponse("classes/list.html", {
        "request": request, "user": current_user, "classes": classes,
        "can_create": role == "school_admin", "error": None,
    })


@router.post("")
async def create_class(request: Request, db: DBSession,
    name: str = Form(...),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    cls = Class(name=name, school_id=current_user.school_id)
    db.add(cls)
    await db.flush()
    return RedirectResponse(url="/classes", status_code=303)


@router.get("/{class_id}", response_class=HTMLResponse)
async def class_detail(request: Request, class_id: int, db: DBSession,
    current_user: User = Depends(get_current_user)):
    cls_result = await db.execute(select(Class).where(Class.id == class_id))
    cls = cls_result.scalar_one_or_none()
    if not cls:
        return RedirectResponse(url="/classes", status_code=303)

    # Students
    students_result = await db.execute(
        select(Student).where(Student.class_id == class_id).order_by(Student.name))
    students = students_result.scalars().all()
    student_ids = [s.id for s in students]

    # Attendance %
    att_pct = 0
    if student_ids:
        total = await db.execute(
            select(func.count(Attendance.id)).where(Attendance.student_id.in_(student_ids)))
        present = await db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.student_id.in_(student_ids), Attendance.is_present == True))
        t, p = total.scalar() or 0, present.scalar() or 0
        att_pct = round(p / t * 100, 1) if t > 0 else 0

    # Avg marks
    avg_marks = 0
    if student_ids:
        avg_r = await db.execute(
            select(func.avg(Mark.marks_obtained)).where(Mark.student_id.in_(student_ids)))
        avg_marks = round(float(avg_r.scalar() or 0), 1)

    return templates.TemplateResponse("classes/detail.html", {
        "request": request, "user": current_user,
        "class": cls, "students": students,
        "attendance_pct": att_pct, "avg_marks": avg_marks,
    })


@router.post("/subjects")
async def create_subject(request: Request, db: DBSession,
    name: str = Form(...),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    subject = Subject(name=name, school_id=current_user.school_id)
    db.add(subject)
    await db.flush()
    return RedirectResponse(url="/classes", status_code=303)
