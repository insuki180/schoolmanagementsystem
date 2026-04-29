"""School management routes — school list, creation, and analytics."""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, case
from app.dependencies import DBSession, get_current_user
from app.models.user import User, UserRole
from app.models.school import School
from app.models.class_ import Class
from app.models.student import Student
from app.models.mark import Mark
from app.models.attendance import Attendance

router = APIRouter(prefix="/schools", tags=["schools"])
templates = Jinja2Templates(directory="app/templates")


def _school_summary_query():
    student_counts = (
        select(
            Student.school_id.label("school_id"),
            func.count(Student.id).label("total_students"),
        )
        .group_by(Student.school_id)
        .subquery()
    )
    teacher_counts = (
        select(
            User.school_id.label("school_id"),
            func.count(User.id).label("total_teachers"),
        )
        .where(User.role == UserRole.TEACHER)
        .group_by(User.school_id)
        .subquery()
    )
    class_counts = (
        select(
            Class.school_id.label("school_id"),
            func.count(Class.id).label("total_classes"),
        )
        .group_by(Class.school_id)
        .subquery()
    )
    marks_avg = (
        select(
            Student.school_id.label("school_id"),
            func.avg(Mark.marks_obtained).label("average_marks"),
        )
        .join(Student, Student.id == Mark.student_id)
        .group_by(Student.school_id)
        .subquery()
    )
    attendance_avg = (
        select(
            Student.school_id.label("school_id"),
            (
                100.0
                * func.sum(case((Attendance.is_present.is_(True), 1), else_=0))
                / func.nullif(func.count(Attendance.id), 0)
            ).label("attendance_pct"),
        )
        .join(Student, Student.id == Attendance.student_id)
        .group_by(Student.school_id)
        .subquery()
    )

    return (
        select(
            School,
            func.coalesce(student_counts.c.total_students, 0).label("total_students"),
            func.coalesce(teacher_counts.c.total_teachers, 0).label("total_teachers"),
            func.coalesce(class_counts.c.total_classes, 0).label("total_classes"),
            func.coalesce(marks_avg.c.average_marks, 0.0).label("average_marks"),
            func.coalesce(attendance_avg.c.attendance_pct, 0.0).label("attendance_pct"),
        )
        .outerjoin(student_counts, student_counts.c.school_id == School.id)
        .outerjoin(teacher_counts, teacher_counts.c.school_id == School.id)
        .outerjoin(class_counts, class_counts.c.school_id == School.id)
        .outerjoin(marks_avg, marks_avg.c.school_id == School.id)
        .outerjoin(attendance_avg, attendance_avg.c.school_id == School.id)
    )


async def _get_school_or_403(db, current_user: User, school_id: int):
    if current_user.role == UserRole.SCHOOL_ADMIN and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="You can only access your school.")
    query = _school_summary_query().where(School.id == school_id)
    if current_user.role == UserRole.SCHOOL_ADMIN:
        query = query.where(School.id == current_user.school_id)
    result = await db.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="School not found")
    return row


@router.get("", response_class=HTMLResponse)
async def list_schools(
    request: Request,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """List all schools or redirect school admins to their analytics page."""
    if current_user.role == UserRole.SCHOOL_ADMIN:
        return RedirectResponse(url=f"/schools/{current_user.school_id}", status_code=303)
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="You don't have permission to access this resource.")

    result = await db.execute(_school_summary_query().order_by(School.name))
    schools = [
        {
            "school": school,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "average_marks": round(float(average_marks or 0), 1),
            "attendance_pct": round(float(attendance_pct or 0), 1),
        }
        for school, total_students, total_teachers, total_classes, average_marks, attendance_pct in result.all()
    ]
    return templates.TemplateResponse("schools/list.html", {
        "request": request,
        "user": current_user,
        "schools": schools,
    })


@router.post("", response_class=HTMLResponse)
async def create_school(
    request: Request,
    db: DBSession,
    name: str = Form(...),
    logo_url: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    """Create a new school."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="You don't have permission to access this resource.")
    school = School(
        name=name,
        logo_url=logo_url or None,
        address=address or None,
        phone=phone or None,
    )
    db.add(school)
    await db.flush()
    return RedirectResponse(url="/schools", status_code=303)


@router.get("/{school_id}", response_class=HTMLResponse)
async def school_detail(
    school_id: int,
    request: Request,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Detailed analytics view for a school."""
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN):
        raise HTTPException(status_code=403, detail="You don't have permission to access this resource.")

    summary = await _get_school_or_403(db, current_user, school_id)

    class_students = (
        select(
            Student.class_id.label("class_id"),
            func.count(Student.id).label("student_count"),
        )
        .group_by(Student.class_id)
        .subquery()
    )
    class_marks = (
        select(
            Student.class_id.label("class_id"),
            func.avg(Mark.marks_obtained).label("average_marks"),
        )
        .join(Student, Student.id == Mark.student_id)
        .group_by(Student.class_id)
        .subquery()
    )
    class_attendance = (
        select(
            Student.class_id.label("class_id"),
            (
                100.0
                * func.sum(case((Attendance.is_present.is_(True), 1), else_=0))
                / func.nullif(func.count(Attendance.id), 0)
            ).label("attendance_pct"),
        )
        .join(Student, Student.id == Attendance.student_id)
        .group_by(Student.class_id)
        .subquery()
    )

    class_result = await db.execute(
        select(
            Class,
            func.coalesce(class_students.c.student_count, 0).label("student_count"),
            func.coalesce(class_marks.c.average_marks, 0.0).label("average_marks"),
            func.coalesce(class_attendance.c.attendance_pct, 0.0).label("attendance_pct"),
        )
        .outerjoin(class_students, class_students.c.class_id == Class.id)
        .outerjoin(class_marks, class_marks.c.class_id == Class.id)
        .outerjoin(class_attendance, class_attendance.c.class_id == Class.id)
        .where(Class.school_id == school_id)
        .order_by(Class.name)
    )

    class_rows = class_result.all()
    class_breakdown = [
        {
            "class": cls,
            "student_count": student_count,
            "average_marks": round(float(average_marks or 0), 1),
            "attendance_pct": round(float(attendance_pct or 0), 1),
        }
        for cls, student_count, average_marks, attendance_pct in class_rows
    ]

    school, total_students, total_teachers, total_classes, average_marks, attendance_pct = summary
    return templates.TemplateResponse("schools/detail.html", {
        "request": request,
        "user": current_user,
        "school": school,
        "summary": {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "average_marks": round(float(average_marks or 0), 1),
            "attendance_pct": round(float(attendance_pct or 0), 1),
        },
        "class_breakdown": class_breakdown,
    })
