"""CSV student import/export routes."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.dependencies import DBSession, require_role
from app.models.school import School
from app.models.user import User, UserRole
from app.services.permissions import get_allowed_classes
from app.services.student_csv_service import (
    TEMPLATE_HEADERS,
    build_template_csv,
    export_students_for_user,
    get_credentials_export,
    import_students_from_csv,
)

router = APIRouter(tags=["student-imports"])
templates = Jinja2Templates(directory="app/templates")


def _is_super_admin(user: User) -> bool:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return role == UserRole.SUPER_ADMIN.value


@router.get("/import/students", response_class=HTMLResponse)
async def student_import_page(
    request: Request,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
):
    schools = []
    if _is_super_admin(current_user):
        result = await db.execute(select(School).order_by(School.name))
        schools = list(result.scalars().all())
    elif current_user.school:
        schools = [current_user.school]
    else:
        result = await db.execute(select(School).where(School.id == current_user.school_id))
        school = result.scalar_one_or_none()
        if school:
            schools = [school]

    classes = await get_allowed_classes(db, current_user)

    return templates.TemplateResponse(
        "users/student_import.html",
        {
            "request": request,
            "user": current_user,
            "schools": schools,
            "classes": classes,
            "template_headers": TEMPLATE_HEADERS,
            "summary": None,
            "error": None,
        },
    )


@router.get("/import/students/template")
async def download_student_import_template(
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
):
    content = build_template_csv()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students_import_template.csv"'},
    )


@router.post("/import/students", response_class=HTMLResponse)
async def import_students(
    request: Request,
    db: DBSession,
    csv_file: UploadFile = File(...),
    school_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
):
    schools = []
    if _is_super_admin(current_user):
        result = await db.execute(select(School).order_by(School.name))
        schools = list(result.scalars().all())
    elif current_user.school:
        schools = [current_user.school]
    else:
        result = await db.execute(select(School).where(School.id == current_user.school_id))
        school = result.scalar_one_or_none()
        if school:
            schools = [school]
    classes = await get_allowed_classes(db, current_user)

    if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
        return templates.TemplateResponse(
            "users/student_import.html",
            {
                "request": request,
                "user": current_user,
                "schools": schools,
                "classes": classes,
                "template_headers": TEMPLATE_HEADERS,
                "summary": None,
                "error": "Please upload a CSV file.",
            },
            status_code=400,
        )

    try:
        csv_text = (await csv_file.read()).decode("utf-8-sig")
        summary = await import_students_from_csv(
            db,
            current_user=current_user,
            csv_text=csv_text,
            school_id=school_id,
        )
        error = None
    except ValueError as exc:
        summary = None
        error = str(exc)

    return templates.TemplateResponse(
        "users/student_import.html",
        {
            "request": request,
            "user": current_user,
            "schools": schools,
            "classes": classes,
            "template_headers": TEMPLATE_HEADERS,
            "summary": summary,
            "error": error,
        },
        status_code=200 if error is None else 400,
    )


@router.get("/import/students/credentials/{token}")
async def download_import_credentials(
    token: str,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
):
    content = get_credentials_export(token)
    if content is None:
        raise HTTPException(status_code=404, detail="Credentials export not found.")

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="student_import_credentials.csv"'},
    )


@router.get("/export/students")
async def export_students(
    db: DBSession,
    school_id: int | None = None,
    class_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.SCHOOL_ADMIN)),
):
    try:
        content = await export_students_for_user(
            db,
            current_user,
            school_id=school_id,
            class_id=class_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students_export.csv"'},
    )
