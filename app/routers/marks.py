"""Marks routes — role-scoped entry and viewing."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.dependencies import DBSession, get_current_user, require_role
from app.models.class_ import Class
from app.models.exam import Exam
from app.models.mark import Mark
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.mark_service import bulk_upsert_marks, get_student_marks
from app.services.permissions import (
    can_edit_marks,
    can_view_student,
    get_allowed_classes,
    get_allowed_subjects_for_class,
    is_school_admin,
    is_super_admin,
)
from app.services.school_scope import resolve_school_scope

router = APIRouter(prefix="/marks", tags=["marks"])
templates = Jinja2Templates(directory="app/templates")


def _available_schools(request: Request, school) -> list:
    schools = list(getattr(request.state, "school_options", []) or [])
    if school and not schools:
        schools = [school]
    return schools


@router.get("", response_class=HTMLResponse)
async def marks_page(
    request: Request,
    db: DBSession,
    class_id: int | None = None,
    subject_id: int | None = None,
    exam_id: int | None = None,
    school_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    school = None
    if school_id is not None or current_user.role != UserRole.SUPER_ADMIN:
        school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=False)

    selected_school_id = school.id if school else None
    schools = _available_schools(request, school)
    classes = await get_allowed_classes(db, current_user, school_id=selected_school_id)
    allowed_class_ids = {cls.id for cls in classes}

    if class_id and class_id not in allowed_class_ids:
        raise HTTPException(status_code=403, detail="You do not have access to this class.")

    selected_class = None
    if class_id:
        selected_class = next((cls for cls in classes if cls.id == class_id), None)

    subjects = []
    exams = []
    if selected_class:
        subjects = await get_allowed_subjects_for_class(db, current_user, selected_class.id)
    elif selected_school_id is not None and is_super_admin(current_user):
        subject_result = await db.execute(
            select(Subject).where(Subject.school_id == selected_school_id).order_by(Subject.name)
        )
        subjects = list(subject_result.scalars().all())
    elif selected_school_id is not None and is_school_admin(current_user):
        subject_result = await db.execute(
            select(Subject).where(Subject.school_id == selected_school_id).order_by(Subject.name)
        )
        subjects = list(subject_result.scalars().all())
    if selected_school_id is not None:
        exams_result = await db.execute(
            select(Exam).where(Exam.school_id == selected_school_id).order_by(Exam.name)
        )
        exams = list(exams_result.scalars().all())
    allowed_subject_ids = {subject.id for subject in subjects}

    students = []
    error = None
    if class_id and subject_id and subject_id not in allowed_subject_ids:
        error = "You do not have permission to enter marks for that subject."
    elif selected_school_id is not None and class_id:
        result = await db.execute(
            select(Student)
            .where(Student.class_id == class_id, Student.school_id == selected_school_id)
            .order_by(Student.name)
        )
        students_list = result.scalars().all()
        for s in students_list:
            existing_mark = None
            if subject_id and exam_id:
                mark_result = await db.execute(
                    select(Mark).where(
                        Mark.student_id == s.id, Mark.subject_id == subject_id,
                        Mark.exam_id == exam_id))
                existing_mark = mark_result.scalar_one_or_none()
            students.append({
                "id": s.id, "name": s.name,
                "existing_marks": existing_mark.marks_obtained if existing_mark else "",
                "max_marks": existing_mark.max_marks if existing_mark else 100,
            })

    return templates.TemplateResponse(
        "marks/entry.html",
        {
            "request": request,
            "user": current_user,
            "schools": schools,
            "classes": classes,
            "subjects": subjects,
            "exams": exams,
            "students": students,
            "selected_school_id": selected_school_id,
            "selected_class": class_id,
            "selected_subject": subject_id,
            "selected_exam": exam_id,
            "success": None,
            "error": error,
        },
    )


@router.get("/entry")
async def marks_index(
    school_id: int | None = None,
    class_id: int | None = None,
    subject_id: int | None = None,
    exam_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    params: list[str] = []
    if school_id is not None:
        params.append(f"school_id={school_id}")
    if class_id is not None:
        params.append(f"class_id={class_id}")
    if subject_id is not None:
        params.append(f"subject_id={subject_id}")
    if exam_id is not None:
        params.append(f"exam_id={exam_id}")
    target = "/marks"
    if params:
        target = f"{target}?{'&'.join(params)}"
    return RedirectResponse(url=target, status_code=303)


@router.post("/entry")
async def marks_entry(request: Request, db: DBSession,
    class_id: int = Form(...), subject_id: int = Form(...), exam_id: int = Form(...), school_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN))):
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
    selected_school_id = school.id if school else None
    classes = await get_allowed_classes(db, current_user, school_id=selected_school_id)
    allowed_class_ids = {cls.id for cls in classes}
    if class_id not in allowed_class_ids:
        raise HTTPException(status_code=403, detail="You do not have access to this class.")
    if not await can_edit_marks(current_user, db, class_id, subject_id):
        raise HTTPException(status_code=403, detail="You do not have permission to edit marks for this class/subject.")

    form = await request.form()
    entries = []
    for key, value in form.multi_items():
        if key.startswith("marks_") and value:
            student_id = int(key.replace("marks_", ""))
            max_key = f"max_{student_id}"
            max_marks = float(form.get(max_key, 100))
            entries.append({
                "student_id": student_id,
                "marks_obtained": float(value),
                "max_marks": max_marks,
            })

    if entries:
        count = await bulk_upsert_marks(db, subject_id, exam_id, entries, current_user.id)

    return RedirectResponse(
        url=f"/marks?school_id={selected_school_id}&class_id={class_id}&subject_id={subject_id}&exam_id={exam_id}",
        status_code=303)


@router.get("/view/{student_id}", response_class=HTMLResponse)
async def view_marks(request: Request, student_id: int, db: DBSession,
    current_user: User = Depends(get_current_user)):
    if not await can_view_student(current_user, db, student_id):
        raise HTTPException(status_code=403, detail="You do not have permission to view this student's marks.")

    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        return RedirectResponse(url="/dashboard", status_code=303)

    marks = await get_student_marks(db, student_id)
    marks_data = []
    for m in marks:
        sub = await db.execute(select(Subject).where(Subject.id == m.subject_id))
        exam = await db.execute(select(Exam).where(Exam.id == m.exam_id))
        s = sub.scalar_one_or_none()
        e = exam.scalar_one_or_none()
        marks_data.append({
            "subject": s.name if s else "N/A",
            "exam": e.name if e else "N/A",
            "obtained": m.marks_obtained,
            "max": m.max_marks,
            "pct": round(m.marks_obtained / m.max_marks * 100, 1) if m.max_marks > 0 else 0,
        })

    cls_result = await db.execute(select(Class).where(Class.id == student.class_id))
    cls = cls_result.scalar_one_or_none()

    return templates.TemplateResponse("marks/view.html", {
        "request": request, "user": current_user,
        "student": student, "class_name": cls.name if cls else "N/A",
        "marks": marks_data,
    })
