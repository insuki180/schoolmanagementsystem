"""Student detail routes for roster drill-down."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import DBSession, get_current_user
from app.models.user import User
from app.services.permissions import can_view_student, is_parent
from app.services.student_view_service import get_student_details_context

router = APIRouter(prefix="/students", tags=["students"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{student_id}/details", response_class=HTMLResponse)
async def student_details(
    request: Request,
    student_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
):
    if is_parent(current_user):
        raise HTTPException(status_code=403, detail="You do not have access to this student.")
    if not await can_view_student(current_user, db, student_id):
        raise HTTPException(status_code=403, detail="You do not have access to this student.")

    context = await get_student_details_context(db, student_id=student_id)
    if not context:
        raise HTTPException(status_code=404, detail="Student not found.")

    return templates.TemplateResponse(
        "students/details.html",
        {
            "request": request,
            "user": current_user,
            **context,
            "success": request.query_params.get("success"),
        },
    )
