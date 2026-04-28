"""User management routes — create admins, teachers, students+parents."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role
from app.models.user import User, UserRole
from app.models.school import School
from app.models.class_ import Class
from app.services.user_service import create_school_admin, create_teacher, create_student_and_parent

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/create-admin", response_class=HTMLResponse)
async def create_admin_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))):
    result = await db.execute(select(School).order_by(School.name))
    return templates.TemplateResponse("users/create_admin.html", {
        "request": request, "user": current_user,
        "schools": result.scalars().all(), "error": None, "success": None,
    })


@router.post("/create-admin")
async def create_admin(request: Request, db: DBSession,
    name: str = Form(...), email: str = Form(...), password: str = Form(...),
    phone: str = Form(""), school_id: int = Form(...),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))):
    try:
        await create_school_admin(db, name, email, password, school_id, phone or None)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        result = await db.execute(select(School).order_by(School.name))
        return templates.TemplateResponse("users/create_admin.html", {
            "request": request, "user": current_user,
            "schools": result.scalars().all(), "error": str(e), "success": None,
        })


@router.get("/create-teacher", response_class=HTMLResponse)
async def create_teacher_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    return templates.TemplateResponse("users/create_teacher.html", {
        "request": request, "user": current_user,
        "classes": result.scalars().all(), "error": None, "success": None,
    })


@router.post("/create-teacher")
async def create_teacher_action(request: Request, db: DBSession,
    name: str = Form(...), email: str = Form(...), password: str = Form(...),
    phone: str = Form(""),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    form = await request.form()
    class_ids = [int(v) for k, v in form.multi_items() if k == "class_ids"]
    try:
        await create_teacher(db, name, email, password, current_user.school_id, class_ids, phone or None)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("users/create_teacher.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": str(e), "success": None,
        })


@router.get("/create-student", response_class=HTMLResponse)
async def create_student_page(request: Request, db: DBSession,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    result = await db.execute(
        select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
    return templates.TemplateResponse("students/create.html", {
        "request": request, "user": current_user,
        "classes": result.scalars().all(), "error": None, "success": None,
    })


@router.post("/create-student")
async def create_student_action(request: Request, db: DBSession,
    student_name: str = Form(...), class_id: int = Form(...),
    parent_name: str = Form(...), parent_email: str = Form(...),
    parent_phone: str = Form(""),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    try:
        student, parent = await create_student_and_parent(
            db, student_name, class_id, parent_name, parent_email,
            parent_phone or None, current_user.school_id)
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("students/create.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": None,
            "success": f"Student '{student_name}' created. Parent login: {parent_email} / parent123",
        })
    except Exception as e:
        result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))
        return templates.TemplateResponse("students/create.html", {
            "request": request, "user": current_user,
            "classes": result.scalars().all(), "error": str(e), "success": None,
        })
