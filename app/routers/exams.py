"""Exam routes — create and list exams."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from datetime import date
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.exam import Exam

router = APIRouter(prefix="/exams", tags=["exams"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_exams(request: Request, db: DBSession,
    current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Exam).where(Exam.school_id == current_user.school_id)
        .order_by(Exam.created_at.desc()))
    return templates.TemplateResponse("exams/list.html", {
        "request": request, "user": current_user,
        "exams": result.scalars().all(),
        "can_create": (current_user.role.value if hasattr(current_user.role, 'value') else current_user.role) == "school_admin",
        "error": None, "success": None,
    })


@router.post("")
async def create_exam(request: Request, db: DBSession,
    name: str = Form(...), exam_date: str = Form(""),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN))):
    try:
        exam = Exam(
            name=name, school_id=current_user.school_id,
            date=date.fromisoformat(exam_date) if exam_date else None)
        db.add(exam)
        await db.flush()
        return RedirectResponse(url="/exams", status_code=303)
    except Exception as e:
        result = await db.execute(
            select(Exam).where(Exam.school_id == current_user.school_id)
            .order_by(Exam.created_at.desc()))
        return templates.TemplateResponse("exams/list.html", {
            "request": request, "user": current_user,
            "exams": result.scalars().all(), "can_create": True,
            "error": str(e), "success": None,
        })
