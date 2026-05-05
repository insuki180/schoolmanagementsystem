"""User management routes — create admins, teachers, students+parents."""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role
from app.models.user import User, UserRole
from app.models.school import School
from app.models.class_ import Class
from app.models.student import Student
from app.schemas.auth import ResetPasswordRequest
from app.schemas.user import StudentUpdateRequest, TeacherUpdateRequest
from app.services.audit_service import create_log
from app.services.user_service import (
    create_school_admin,
    create_teacher,
    create_student_and_parent,
    get_users_by_school,
    get_user_by_id,
    reset_user_password,
    update_student_profile_by_school_admin,
    update_teacher_profile,
)

router = APIRouter(prefix="/users", tags=["users"])
management_router = APIRouter(tags=["users"])
templates = Jinja2Templates(directory="app/templates")


def _parse_user_id(raw_user_id: str) -> int:
    try:
        return int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid user ID.") from exc


@router.get("/create-admin", response_class=HTMLResponse)
async def create_admin_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))):
    result = await db.execute(select(School).order_by(School.name))
    return templates.TemplateResponse("users/create_admin.html", {
        "request": request, "user": current_user,
        "schools": result.scalars().all(), "error": None, "credentials": None,
    })


@router.post("/create-admin")
async def create_admin(request: Request, db: DBSession,
    name: str = Form(...), email: str = Form(...),
    phone: str = Form(""), school_id: int = Form(...),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))):
    try:
        admin, temp_password = await create_school_admin(
            db, name, email, school_id, phone or None
        )
        result = await db.execute(select(School).order_by(School.name))
        return templates.TemplateResponse("users/create_admin.html", {
            "request": request, "user": current_user,
            "schools": result.scalars().all(), "error": None,
            "credentials": {
                "login_id": admin.email,
                "temp_password": temp_password,
                "message": "School admin created successfully.",
            },
        })
    except Exception as e:
        result = await db.execute(select(School).order_by(School.name))
        return templates.TemplateResponse("users/create_admin.html", {
            "request": request, "user": current_user,
            "schools": result.scalars().all(), "error": str(e), "credentials": None,
        })


@router.get("/create-teacher", response_class=HTMLResponse)
async def create_teacher_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    return templates.TemplateResponse("users/create_teacher.html", {
        "request": request, "user": current_user,
        "classes": result.scalars().all(), "error": None, "credentials": None,
    })


@router.post("/create-teacher")
async def create_teacher_action(request: Request, db: DBSession,
    name: str = Form(...), email: str = Form(...),
    phone: str = Form(...),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    form = await request.form()
    class_ids = [int(v) for k, v in form.multi_items() if k == "class_ids"]
    try:
        teacher, temp_password = await create_teacher(
            db, name, email, current_user.school_id, class_ids, phone or None
        )
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("users/create_teacher.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": None,
            "credentials": {
                "login_id": teacher.email,
                "temp_password": temp_password,
                "message": "Teacher created successfully.",
            },
        })
    except Exception as e:
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("users/create_teacher.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": str(e), "credentials": None,
        })


@router.get("/teachers", response_class=HTMLResponse)
async def manage_teachers_page(
    request: Request,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN)),
):
    teachers = await get_users_by_school(db, current_user.school_id, UserRole.TEACHER)
    return templates.TemplateResponse("users/manage_teachers.html", {
        "request": request,
        "user": current_user,
        "teachers": teachers,
    })


@management_router.post("/admin/reset-password")
async def super_admin_reset_password(
    payload: ResetPasswordRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    target_user_id = _parse_user_id(payload.userId)
    temp_password = await reset_user_password(
        db,
        acting_user=current_user,
        target_user_id=target_user_id,
    )
    target_user = await get_user_by_id(db, target_user_id)
    if target_user:
        await create_log(
            db=db,
            action="PASSWORD_RESET",
            performed_by=current_user.id,
            target_user=target_user.id,
            school_id=target_user.school_id,
            role=target_user.role.value if hasattr(target_user.role, "value") else str(target_user.role),
        )
    return JSONResponse({"tempPassword": temp_password})


@management_router.post("/school-admin/reset-password")
async def school_admin_reset_password(
    payload: ResetPasswordRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN)),
):
    target_user_id = _parse_user_id(payload.userId)
    temp_password = await reset_user_password(
        db,
        acting_user=current_user,
        target_user_id=target_user_id,
    )
    target_user = await get_user_by_id(db, target_user_id)
    if target_user:
        await create_log(
            db=db,
            action="PASSWORD_RESET",
            performed_by=current_user.id,
            target_user=target_user.id,
            school_id=target_user.school_id,
            role=target_user.role.value if hasattr(target_user.role, "value") else str(target_user.role),
        )
    return JSONResponse({"tempPassword": temp_password})


@management_router.get("/school-admin/teacher/{teacher_id}/edit", response_class=HTMLResponse)
async def edit_teacher_page(
    request: Request,
    teacher_id: int,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN)),
):
    teacher = await get_user_by_id(db, teacher_id)
    if not teacher or teacher.role not in (UserRole.TEACHER, UserRole.CLASS_TEACHER):
        return RedirectResponse(url="/dashboard?msg=Teacher%20not%20found", status_code=303)
    if teacher.school_id != current_user.school_id:
        return RedirectResponse(url="/dashboard?msg=Access%20denied", status_code=303)

    return templates.TemplateResponse("users/edit_teacher.html", {
        "request": request,
        "user": current_user,
        "teacher": teacher,
    })


@management_router.get("/school-admin/student/{student_id}/edit", response_class=HTMLResponse)
async def edit_student_page(
    request: Request,
    student_id: int,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN)),
):
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        return RedirectResponse(url="/dashboard?msg=Student%20not%20found", status_code=303)
    if student.school_id != current_user.school_id:
        return RedirectResponse(url="/dashboard?msg=Access%20denied", status_code=303)

    parent_result = await db.execute(select(User).where(User.id == student.parent_id))
    parent = parent_result.scalar_one_or_none()
    classes_result = await db.execute(
        select(Class)
        .where(Class.school_id == current_user.school_id)
        .order_by(Class.name)
    )
    return templates.TemplateResponse("students/edit.html", {
        "request": request,
        "user": current_user,
        "student": student,
        "parent": parent,
        "classes": classes_result.scalars().all(),
    })


@management_router.put("/school-admin/teacher/{teacher_id}")
async def school_admin_update_teacher(
    teacher_id: int,
    payload: TeacherUpdateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN)),
):
    teacher = await update_teacher_profile(
        db,
        acting_user=current_user,
        teacher_id=teacher_id,
        name=payload.name,
        phone=payload.phone,
    )
    return JSONResponse({
        "id": teacher.id,
        "name": teacher.name,
        "phone": teacher.phone_number,
    })


@management_router.put("/school-admin/student/{student_id}")
async def school_admin_update_student(
    student_id: int,
    payload: StudentUpdateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN)),
):
    student = await update_student_profile_by_school_admin(
        db,
        acting_user=current_user,
        student_id=student_id,
        name=payload.name,
        class_id=payload.class_id,
        parent_phone=payload.parent_phone,
    )
    parent_result = await db.execute(select(User).where(User.id == student.parent_id))
    parent = parent_result.scalar_one_or_none()
    return JSONResponse({
        "id": student.id,
        "name": student.name,
        "classId": student.class_id,
        "parentPhone": parent.phone_number if parent else "",
    })


@router.get("/create-student", response_class=HTMLResponse)
async def create_student_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    return templates.TemplateResponse("students/create.html", {
        "request": request, "user": current_user,
        "classes": result.scalars().all(), "error": None, "credentials": None,
    })


@router.post("/create-student")
async def create_student_action(request: Request, db: DBSession,
    student_name: str = Form(...), class_id: int = Form(...),
    parent_name: str = Form(...), parent_email: str = Form(...),
    parent_phone: str = Form(...),
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    try:
        student, parent, temp_password = await create_student_and_parent(
            db, student_name, class_id, parent_name, parent_email,
            parent_phone or None, current_user.school_id)
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("students/create.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": None, "student": student,
            "credentials": {
                "login_id": parent.email,
                "temp_password": temp_password,
                "message": f"Student '{student_name}' created successfully.",
                "account_status": "Parent account linked to an existing login."
                if temp_password is None else
                "Parent account created with a temporary password.",
            },
        })
    except Exception as e:
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("students/create.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": str(e), "credentials": None,
        })
