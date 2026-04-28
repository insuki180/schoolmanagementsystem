"""Marks routes — entry and viewing."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.class_ import Class, teacher_classes
from app.models.student import Student
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.mark import Mark
from app.services.mark_service import bulk_upsert_marks, get_student_marks

router = APIRouter(prefix="/marks", tags=["marks"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def marks_index(
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN)),
):
    return RedirectResponse(url="/marks/entry", status_code=303)


@router.get("/entry", response_class=HTMLResponse)
async def marks_entry_page(request: Request, db: DBSession,
    class_id: int = None, subject_id: int = None, exam_id: int = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role == "teacher":
        cls_result = await db.execute(
            select(Class).join(teacher_classes).where(
                teacher_classes.c.teacher_id == current_user.id).order_by(Class.name))
    else:
        cls_result = await db.execute(
            select(Class).where(Class.school_id == current_user.school_id).order_by(Class.name))

    subjects_result = await db.execute(
        select(Subject).where(Subject.school_id == current_user.school_id).order_by(Subject.name))
    exams_result = await db.execute(
        select(Exam).where(Exam.school_id == current_user.school_id).order_by(Exam.name))

    students = []
    if class_id:
        result = await db.execute(
            select(Student).where(Student.class_id == class_id).order_by(Student.name))
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

    return templates.TemplateResponse("marks/entry.html", {
        "request": request, "user": current_user,
        "classes": cls_result.scalars().all(),
        "subjects": subjects_result.scalars().all(),
        "exams": exams_result.scalars().all(),
        "students": students,
        "selected_class": class_id, "selected_subject": subject_id,
        "selected_exam": exam_id,
        "success": None, "error": None,
    })


@router.post("/entry")
async def marks_entry(request: Request, db: DBSession,
    class_id: int = Form(...), subject_id: int = Form(...), exam_id: int = Form(...),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN))):
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
        url=f"/marks/entry?class_id={class_id}&subject_id={subject_id}&exam_id={exam_id}",
        status_code=303)


@router.get("/view/{student_id}", response_class=HTMLResponse)
async def view_marks(request: Request, student_id: int, db: DBSession,
    current_user: User = Depends(get_current_user)):
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
