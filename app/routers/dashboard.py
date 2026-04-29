"""Dashboard routes — role-based views."""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from app.dependencies import DBSession, get_current_user
from app.models.user import User, UserRole
from app.models.school import School
from app.models.class_ import Class
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.notification import Notification
from app.models.mark import Mark
from app.services.notification_service import get_notifications_for_parent
from app.services.absence_response_service import get_parent_absence_alerts
from app.services.parent_portal_service import (
    build_parent_notification_cards,
    get_teacher_contacts_for_student,
    update_student_profile,
)
from app.services.permissions import can_view_student
from datetime import date

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    """Render role-appropriate dashboard."""
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role

    if role == "super_admin":
        return await super_admin_dashboard(request, db, current_user)
    elif role == "school_admin":
        return await school_admin_dashboard(request, db, current_user)
    elif role == "teacher":
        return await teacher_dashboard(request, db, current_user)
    elif role == "parent":
        return await parent_dashboard(request, db, current_user)

    return templates.TemplateResponse("auth/login.html", {
        "request": request, "error": "Unknown role"
    })


async def super_admin_dashboard(request: Request, db, current_user: User):
    """Super Admin: school overview."""
    result = await db.execute(select(School).order_by(School.name))
    schools = result.scalars().all()

    school_stats = []
    for school in schools:
        # Count users
        user_count = await db.execute(
            select(func.count(User.id)).where(User.school_id == school.id)
        )
        # Count students
        student_count = await db.execute(
            select(func.count(Student.id)).where(Student.school_id == school.id)
        )
        school_stats.append({
            "school": school,
            "user_count": user_count.scalar() or 0,
            "student_count": student_count.scalar() or 0,
        })

    return templates.TemplateResponse("dashboard/super_admin.html", {
        "request": request,
        "user": current_user,
        "school_stats": school_stats,
    })


async def school_admin_dashboard(request: Request, db, current_user: User):
    """School Admin: class overview with stats."""
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name)
    )
    classes = result.scalars().all()

    class_stats = []
    for cls in classes:
        # Student count
        student_count = await db.execute(
            select(func.count(Student.id)).where(Student.class_id == cls.id)
        )
        # Attendance % (last 30 days)
        student_ids_result = await db.execute(
            select(Student.id).where(Student.class_id == cls.id)
        )
        student_ids = [r[0] for r in student_ids_result.all()]

        att_pct = 0
        if student_ids:
            total = await db.execute(
                select(func.count(Attendance.id)).where(Attendance.student_id.in_(student_ids))
            )
            present = await db.execute(
                select(func.count(Attendance.id)).where(
                    Attendance.student_id.in_(student_ids),
                    Attendance.is_present == True,
                )
            )
            t = total.scalar() or 0
            p = present.scalar() or 0
            att_pct = round(p / t * 100, 1) if t > 0 else 0

        # Avg marks
        avg_marks = 0
        if student_ids:
            avg_result = await db.execute(
                select(func.avg(Mark.marks_obtained)).where(Mark.student_id.in_(student_ids))
            )
            avg_marks = round(float(avg_result.scalar() or 0), 1)

        class_stats.append({
            "class": cls,
            "student_count": student_count.scalar() or 0,
            "attendance_pct": att_pct,
            "avg_marks": avg_marks,
        })

    # Recent notifications
    notifs = await db.execute(
        select(Notification)
        .where(Notification.school_id == current_user.school_id)
        .order_by(Notification.created_at.desc())
        .limit(5)
    )

    return templates.TemplateResponse("dashboard/admin.html", {
        "request": request,
        "user": current_user,
        "class_stats": class_stats,
        "recent_notifications": notifs.scalars().all(),
    })


async def teacher_dashboard(request: Request, db, current_user: User):
    """Teacher: quick actions + class summary."""
    # Get assigned classes
    from app.models.class_ import teacher_classes
    result = await db.execute(
        select(Class)
        .join(teacher_classes, teacher_classes.c.class_id == Class.id)
        .where(teacher_classes.c.teacher_id == current_user.id)
        .order_by(Class.name)
    )
    classes = result.scalars().all()

    # Today's attendance status
    today = date.today()
    class_attendance = []
    for cls in classes:
        student_count = await db.execute(
            select(func.count(Student.id)).where(Student.class_id == cls.id)
        )
        marked = await db.execute(
            select(func.count(Attendance.id))
            .join(Student, Student.id == Attendance.student_id)
            .where(Student.class_id == cls.id, Attendance.date == today)
        )
        class_attendance.append({
            "class": cls,
            "student_count": student_count.scalar() or 0,
            "marked_today": (marked.scalar() or 0) > 0,
        })

    # Recent notifications
    notifs = await db.execute(
        select(Notification)
        .where(Notification.school_id == current_user.school_id)
        .order_by(Notification.created_at.desc())
        .limit(5)
    )

    return templates.TemplateResponse("dashboard/teacher.html", {
        "request": request,
        "user": current_user,
        "classes": class_attendance,
        "recent_notifications": notifs.scalars().all(),
    })


async def parent_dashboard(request: Request, db, current_user: User):
    """Parent: notifications + attendance + marks."""
    # Get children
    result = await db.execute(
        select(Student).where(Student.parent_id == current_user.id)
    )
    children = result.scalars().all()

    # Recent attendance for each child
    children_data = []
    for child in children:
        att_result = await db.execute(
            select(Attendance)
            .where(Attendance.student_id == child.id)
            .order_by(Attendance.date.desc())
            .limit(10)
        )
        attendance = att_result.scalars().all()

        marks_result = await db.execute(
            select(Mark).where(Mark.student_id == child.id)
        )
        marks = marks_result.scalars().all()

        # Get class name
        class_result = await db.execute(
            select(Class).where(Class.id == child.class_id)
        )
        cls = class_result.scalar_one_or_none()
        contacts = await get_teacher_contacts_for_student(db, child)

        children_data.append({
            "student": child,
            "class_name": cls.name if cls else "N/A",
            "attendance": attendance,
            "marks": marks,
            "teacher_contacts": contacts,
            "notification_cards": [],
        })

    # Get notifications
    notifications = await get_notifications_for_parent(db, current_user.id, current_user.school_id)
    absence_alerts = await get_parent_absence_alerts(db, current_user)
    for child_data in children_data:
        child_data["notification_cards"] = build_parent_notification_cards(
            notifications=notifications,
            absence_alerts=absence_alerts,
            student_id=child_data["student"].id,
        )

    return templates.TemplateResponse("dashboard/parent.html", {
        "request": request,
        "user": current_user,
        "children": children_data,
        "notifications": notifications,
        "absence_alerts": absence_alerts,
    })


@router.post("/parent/student/update")
async def parent_update_student(
    request: Request,
    db: DBSession,
    student_id: int = Form(...),
    blood_group: str = Form(""),
    address: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role != "parent":
        raise HTTPException(status_code=403, detail="Only parents can update student details.")

    try:
        await update_student_profile(
            db,
            parent_user=current_user,
            student_id=student_id,
            blood_group=blood_group,
            address=address,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RedirectResponse(url="/dashboard", status_code=303)
