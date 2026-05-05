"""Finance routes and pages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.dependencies import DBSession, get_current_user, require_role
from app.models.school import School
from app.models.student import Student
from app.models.user import User, UserRole
from app.models.finance import FeeType
from app.schemas.finance import (
    FeeConfigCreateRequest,
    FeeGenerateRequest,
    FeePaymentCreateRequest,
    FeeStructureCreateRequest,
)
from app.services.finance_service import (
    add_fee_payment,
    create_fee_config,
    create_fee_structure,
    generate_student_fees,
    get_finance_scope,
    get_finance_summary_for_students,
    get_due_student_fees,
    get_student_fee_summary,
    get_student_finance_details,
    pay_student_fees,
)
from app.services.permissions import is_super_admin

router = APIRouter(prefix="/finance", tags=["finance"])
api_router = APIRouter(prefix="/fees", tags=["fees"])
templates = Jinja2Templates(directory="app/templates")


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "application/json" in accept


def _available_schools(request: Request, selected_school_id: int | None) -> list:
    schools = list(getattr(request.state, "school_options", []) or [])
    if schools:
        return schools
    if selected_school_id is None:
        return []
    return [School(id=selected_school_id, name="Selected School")]


@router.get("", response_class=HTMLResponse)
async def finance_dashboard(
    request: Request,
    db: DBSession,
    month: str | None = None,
    school_id: int | None = None,
    class_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    scope = await get_finance_scope(
        db,
        acting_user=current_user,
        school_id=school_id,
        class_id=class_id,
    )
    summary = await get_finance_summary_for_students(db, students=scope.students, month=month)

    return templates.TemplateResponse(
        "finance/dashboard.html",
        {
            "request": request,
            "user": current_user,
            "schools": _available_schools(request, scope.selected_school_id),
            "classes": scope.classes,
            "selected_school_id": scope.selected_school_id,
            "selected_class_id": scope.selected_class_id,
            "selected_month": month,
            "summary": summary,
            "pending_rows": summary["pending_rows"],
            "can_add_payments": current_user.role in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN),
        },
    )


@router.get("/students", response_class=HTMLResponse)
async def finance_students_page(
    request: Request,
    db: DBSession,
    month: str | None = None,
    school_id: int | None = None,
    class_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    scope = await get_finance_scope(
        db,
        acting_user=current_user,
        school_id=school_id,
        class_id=class_id,
    )
    summary = await get_finance_summary_for_students(db, students=scope.students, month=month)
    rows = summary["rows"]

    return templates.TemplateResponse(
        "finance/students.html",
        {
            "request": request,
            "user": current_user,
            "schools": _available_schools(request, scope.selected_school_id),
            "classes": scope.classes,
            "selected_school_id": scope.selected_school_id,
            "selected_class_id": scope.selected_class_id,
            "selected_month": month,
            "rows": rows,
            "can_add_payments": current_user.role in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN),
            "can_configure_fees": current_user.role in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN),
        },
    )


@router.post("/config")
async def add_fee_config(
    payload: FeeConfigCreateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    config = await create_fee_config(
        db,
        acting_user=current_user,
        student_id=payload.student_id,
        monthly_fee=payload.monthly_fee,
        effective_from=payload.effective_from,
        status=payload.status,
    )
    return JSONResponse(
        {
            "id": config.id,
            "student_id": config.student_id,
            "monthly_fee": config.monthly_fee,
            "effective_from": config.effective_from.isoformat(),
            "status": config.status,
        }
    )


@router.post("/payment")
async def add_payment(
    payload: FeePaymentCreateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    payment = await add_fee_payment(
        db,
        acting_user=current_user,
        student_id=payload.student_id,
        amount_paid=payload.amount_paid,
        payment_date=payload.payment_date,
        payment_mode=payload.payment_mode,
        note=payload.note,
    )
    return JSONResponse(
        {
            "id": payment.id,
            "student_id": payment.student_id,
            "amount_paid": payment.amount_paid,
            "payment_date": payment.payment_date.isoformat(),
            "payment_mode": payment.payment_mode,
            "note": payment.note or "",
            "created_by": payment.created_by,
        }
    )


@router.get("/student/{student_id}")
async def finance_student_details(
    student_id: int,
    db: DBSession,
    month: str | None = None,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if current_user.role == UserRole.SCHOOL_ADMIN and student.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to this student.")
    if current_user.role in (UserRole.CLASS_TEACHER, UserRole.TEACHER) and student.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to this student.")

    details = await get_student_finance_details(db, student_id=student_id, through_month=month)
    return JSONResponse(details)


@router.get("/summary")
async def finance_summary(
    db: DBSession,
    month: str | None = None,
    school_id: int | None = None,
    class_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    scope = await get_finance_scope(
        db,
        acting_user=current_user,
        school_id=school_id,
        class_id=class_id,
    )
    summary = await get_finance_summary_for_students(db, students=scope.students, month=month)
    return JSONResponse(
        {
            "total_expected": summary["total_expected"],
            "total_collected": summary["total_collected"],
            "total_pending": summary["total_pending"],
            "pending_count": summary["pending_count"],
        }
    )


@router.get("/pending")
async def finance_pending(
    db: DBSession,
    month: str | None = None,
    school_id: int | None = None,
    class_id: int | None = None,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    scope = await get_finance_scope(
        db,
        acting_user=current_user,
        school_id=school_id,
        class_id=class_id,
    )
    summary = await get_finance_summary_for_students(db, students=scope.students, month=month)
    return JSONResponse(
        [
            {
                "student_id": row["student"].id,
                "student_name": row["student"].name,
                "class_name": row["student"].class_.name if row["student"].class_ else "N/A",
                "monthly_fee": row["monthly_fee"],
                "paid": row["paid"],
                "due": row["due"],
                "status": row["status"],
            }
            for row in summary["pending_rows"]
        ]
    )


@api_router.post("/structure")
async def add_fee_structure(
    payload: FeeStructureCreateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    structure = await create_fee_structure(
        db,
        acting_user=current_user,
        class_id=payload.class_id,
        fee_type=FeeType(payload.fee_type),
        amount=payload.amount,
        effective_from=payload.effective_from,
    )
    return JSONResponse(
        {
            "id": structure.id,
            "class_id": structure.class_id,
            "fee_type": structure.fee_type.value,
            "amount": structure.amount,
            "effective_from": structure.effective_from.isoformat(),
        }
    )


@api_router.post("/generate")
async def generate_fees(
    payload: FeeGenerateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    result = await generate_student_fees(
        db,
        acting_user=current_user,
        class_id=payload.class_id,
        fee_type=FeeType(payload.fee_type),
        through_date=payload.through_date,
        student_id=payload.student_id,
    )
    return JSONResponse(
        {
            "created_count": len(result.created),
            "existing_count": len(result.existing),
            "rows": [
                {
                    "student_id": row.student_id,
                    "class_id": row.class_id,
                    "period_start": row.period_start.isoformat(),
                    "period_end": row.period_end.isoformat(),
                    "fee_type": row.fee_type.value if hasattr(row.fee_type, "value") else row.fee_type,
                    "amount_due": row.amount_due,
                    "carry_forward": row.carry_forward,
                    "status": row.status,
                }
                for row in result.created
            ],
        }
    )


@api_router.post("/pay")
async def pay_fees(
    payload: FeePaymentCreateRequest,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    result = await pay_student_fees(
        db,
        acting_user=current_user,
        student_id=payload.student_id,
        amount_paid=payload.amount_paid,
        payment_date=payload.payment_date,
        payment_mode=payload.payment_mode,
        note=payload.note,
    )
    payment = result["payment"]
    return JSONResponse(
        {
            "payment_id": payment.id,
            "student_id": payment.student_id,
            "amount_paid": payment.amount_paid,
            "payment_date": payment.payment_date.isoformat(),
            "payment_mode": payment.payment_mode,
            "remaining_advance": result["remaining_advance"],
        }
    )


@api_router.get("/student/{student_id}")
async def student_fees(
    student_id: int,
    db: DBSession,
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_user.role in (UserRole.SCHOOL_ADMIN, UserRole.CLASS_TEACHER, UserRole.TEACHER) and student.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="You do not have access to this student.")
    return JSONResponse(await get_student_fee_summary(db, student_id=student_id))


@api_router.get("/due")
async def due_fees(
    db: DBSession,
    class_id: int | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.CLASS_TEACHER, UserRole.TEACHER, UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN)),
):
    rows = await get_due_student_fees(db, acting_user=current_user, class_id=class_id)
    return JSONResponse(rows)
