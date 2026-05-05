"""Class management routes."""

import logging

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.dependencies import DBSession, require_role, get_current_user
from app.models.user import User, UserRole
from app.models.class_ import Class, ClassSubject
from app.models.student import Student
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.mark import Mark
from app.models.absence_response import AbsenceResponse
from app.services.permissions import can_view_student, get_allowed_classes, is_school_admin, is_super_admin
from app.services.school_scope import resolve_school_scope

router = APIRouter(prefix="/classes", tags=["classes"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


@router.get("", response_class=HTMLResponse)
async def list_classes(request: Request, db: DBSession,
    school_id: int | None = None,
    current_user: User = Depends(get_current_user)):
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
    effective_school_id = school.id if school else None
    classes = await get_allowed_classes(db, current_user, school_id=effective_school_id)
    role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    return templates.TemplateResponse("classes/list.html", {
        "request": request, "user": current_user, "classes": classes,
        "can_create": role in {"school_admin", "super_admin"} and effective_school_id is not None,
        "error": None,
        "active_school_id": effective_school_id,
    })


@router.post("")
async def create_class(request: Request, db: DBSession,
    name: str = Form(...),
    school_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN))):
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
    effective_school_id = school.id if school else current_user.school_id
    if effective_school_id is None:
        raise HTTPException(status_code=400, detail="Super admin must create classes from a school-specific workflow.")
    cls = Class(name=name, school_id=effective_school_id)
    db.add(cls)
    await db.flush()
    return RedirectResponse(url=f"/classes?school_id={effective_school_id}", status_code=303)


@router.get("/{class_id}", response_class=HTMLResponse)
@router.get("/{class_id}/students", response_class=HTMLResponse)
async def class_detail(request: Request, class_id: int, db: DBSession,
    school_id: int | None = None,
    current_user: User = Depends(get_current_user)):
    logger.info(
        "Fetching class detail: class_id=%s requested_school_id=%s user_id=%s role=%s",
        class_id,
        school_id,
        current_user.id,
        current_user.role.value if hasattr(current_user.role, "value") else current_user.role,
    )
    cls_result = await db.execute(
        select(Class)
        .options(
            selectinload(Class.students),
            selectinload(Class.teachers),
            selectinload(Class.subject_assignments).selectinload(ClassSubject.subject),
            selectinload(Class.subject_assignments).selectinload(ClassSubject.teacher),
        )
        .where(Class.id == class_id)
    )
    cls = cls_result.scalar_one_or_none()
    if not cls:
        logger.warning("Class detail lookup failed: class_id=%s not found", class_id)
        return RedirectResponse(url="/classes", status_code=303)
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=is_super_admin(current_user))
    effective_school_id = school.id if school else None
    if effective_school_id is not None and cls.school_id != effective_school_id:
        logger.warning(
            "Class detail denied by school scope: class_id=%s class_school_id=%s effective_school_id=%s user_id=%s",
            class_id,
            cls.school_id,
            effective_school_id,
            current_user.id,
        )
        raise HTTPException(status_code=403, detail="You do not have access to this class.")
    if not is_super_admin(current_user) and cls.school_id != current_user.school_id and current_user.role != UserRole.PARENT:
        logger.warning(
            "Class detail denied by role scope: class_id=%s class_school_id=%s user_school_id=%s user_id=%s role=%s",
            class_id,
            cls.school_id,
            current_user.school_id,
            current_user.id,
            current_user.role.value if hasattr(current_user.role, "value") else current_user.role,
        )
        raise HTTPException(status_code=403, detail="You do not have access to this class.")

    # Students
    students_result = await db.execute(
        select(Student).where(Student.class_id == class_id).order_by(Student.name))
    students = students_result.scalars().all()
    student_ids = [s.id for s in students]

    # Attendance %
    att_pct = 0
    if student_ids:
        total = await db.execute(
            select(func.count(Attendance.id)).where(Attendance.student_id.in_(student_ids)))
        present = await db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.student_id.in_(student_ids), Attendance.is_present == True))
        t, p = total.scalar() or 0, present.scalar() or 0
        att_pct = round(p / t * 100, 1) if t > 0 else 0

    # Avg marks
    avg_marks = 0
    if student_ids:
        avg_r = await db.execute(
            select(func.avg(Mark.marks_obtained)).where(Mark.student_id.in_(student_ids)))
        avg_marks = round(float(avg_r.scalar() or 0), 1)

    teacher_query = select(User).where(User.role.in_([UserRole.TEACHER, UserRole.CLASS_TEACHER]))
    subject_query = select(Subject)
    if not is_super_admin(current_user):
        teacher_query = teacher_query.where(User.school_id == cls.school_id)
        subject_query = subject_query.where(Subject.school_id == cls.school_id)
    teachers_result = await db.execute(teacher_query.order_by(User.name))
    subjects_result = await db.execute(subject_query.order_by(Subject.name))
    assignments_result = await db.execute(
        select(ClassSubject).where(ClassSubject.class_id == class_id).order_by(ClassSubject.subject_id)
    )
    response_result = await db.execute(
        select(AbsenceResponse, Student)
        .join(Student, Student.id == AbsenceResponse.student_id)
        .where(Student.class_id == class_id)
        .order_by(AbsenceResponse.date.desc())
    )
    absence_responses = [
        {"response": response, "student": student}
        for response, student in response_result.all()
    ]

    logger.info(
        "Class detail loaded: class_id=%s school_id=%s student_count=%s assignment_count=%s absence_response_count=%s",
        cls.id,
        cls.school_id,
        len(students),
        len(cls.subject_assignments),
        len(absence_responses),
    )

    return templates.TemplateResponse("classes/detail.html", {
        "request": request, "user": current_user,
        "class": cls, "students": students,
        "attendance_pct": att_pct, "avg_marks": avg_marks,
        "teachers": teachers_result.scalars().all(),
        "subjects": subjects_result.scalars().all(),
        "subject_assignments": assignments_result.scalars().all(),
        "absence_responses": absence_responses,
        "can_manage_mapping": is_school_admin(current_user) or is_super_admin(current_user),
        "active_school_id": cls.school_id,
    })


@router.post("/subjects")
async def create_subject(request: Request, db: DBSession,
    name: str = Form(...),
    school_id: int | None = Form(None),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN))):
    school = await resolve_school_scope(db, current_user, school_id, required_for_super_admin=True)
    effective_school_id = school.id if school else current_user.school_id
    subject = Subject(name=name, school_id=effective_school_id)
    db.add(subject)
    await db.flush()
    return RedirectResponse(url=f"/classes?school_id={effective_school_id}", status_code=303)


@router.post("/{class_id}/assign-teacher")
async def assign_class_teacher(
    class_id: int,
    db: DBSession,
    class_teacher_id: int = Form(...),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")

    teacher = None
    if class_teacher_id:
        teacher_result = await db.execute(
            select(User).where(
                User.id == class_teacher_id,
                User.role.in_([UserRole.TEACHER, UserRole.CLASS_TEACHER]),
                User.school_id == cls.school_id,
            )
        )
        teacher = teacher_result.scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found for this school.")
        if teacher.role == UserRole.TEACHER:
            teacher.role = UserRole.CLASS_TEACHER
        cls.class_teacher_id = teacher.id
        if teacher not in cls.teachers:
            cls.teachers.append(teacher)
    else:
        cls.class_teacher_id = None
    await db.flush()
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)


@router.post("/{class_id}/assign-subject")
async def assign_subject_teacher(
    class_id: int,
    db: DBSession,
    subject_id: int = Form(...),
    teacher_id: int = Form(...),
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    class_result = await db.execute(select(Class).where(Class.id == class_id))
    cls = class_result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")

    subject_result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == cls.school_id)
    )
    subject = subject_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found for this school.")

    teacher_result = await db.execute(
        select(User).where(
            User.id == teacher_id,
            User.role.in_([UserRole.TEACHER, UserRole.CLASS_TEACHER]),
            User.school_id == cls.school_id,
        )
    )
    teacher = teacher_result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found for this school.")

    assignment_result = await db.execute(
        select(ClassSubject).where(
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    if not assignment:
        assignment = ClassSubject(class_id=class_id, subject_id=subject_id, teacher_id=teacher_id)
        db.add(assignment)
    else:
        assignment.teacher_id = teacher_id

    if teacher not in cls.teachers:
        cls.teachers.append(teacher)
    await db.flush()
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)
