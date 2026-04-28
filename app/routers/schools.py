"""School management routes — Super Admin only."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role
from app.models.user import User, UserRole
from app.models.school import School

router = APIRouter(prefix="/schools", tags=["schools"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_schools(
    request: Request,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    """List all schools."""
    result = await db.execute(select(School).order_by(School.name))
    schools = result.scalars().all()
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
    address: str = Form(""),
    phone: str = Form(""),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    """Create a new school."""
    school = School(name=name, address=address or None, phone=phone or None)
    db.add(school)
    await db.flush()
    return RedirectResponse(url="/schools", status_code=303)
