"""User management routes — create admins, teachers, students+parents."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role
from app.models.user import User, UserRole
from app.models.school import School
from app.models.class_ import Class
from app.services.user_service import (
    create_school_admin,
    create_teacher,
    create_student_and_parent,
    get_users_by_school,
)

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")


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


@router.get("/create-student", response_class=HTMLResponse)
async def create_student_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.TEACHER))):
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
    current_user: User = Depends(require_role(UserRole.TEACHER))):
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
