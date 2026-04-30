"""Finance business logic and fee allocation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.class_ import Class
from app.models.finance import FeeLedger, StudentFeeConfig
from app.models.school import School
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.permissions import get_allowed_classes, is_school_admin, is_super_admin


TWOPLACES = Decimal("0.01")


@dataclass
class FinanceScope:
    students: list[Student]
    classes: list[Class]
    school: School | None
    selected_school_id: int | None
    selected_class_id: int | None


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _parse_month(value: str | None) -> date:
    if value:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    today = date.today()
    return date(today.year, today.month, 1)


def _format_month(value: date) -> str:
    return value.strftime("%Y-%m")


def _add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _latest_month(a: date, b: date) -> date:
    return a if a >= b else b


def _active_configs(configs) -> list:
    return [config for config in configs if (getattr(config, "status", "active") or "active").lower() == "active"]


def _fee_for_month(configs, month: date) -> Decimal | None:
    matching = [
        config
        for config in configs
        if _month_start(config.effective_from) <= month
    ]
    if not matching:
        return None
    latest = matching[-1]
    return _decimal(latest.monthly_fee)


def compute_fee_breakdown(
    *,
    fee_configs,
    payments,
    through_month: str | None = None,
):
    active_configs = sorted(_active_configs(fee_configs), key=lambda item: item.effective_from)
    if not active_configs:
        return []

    start_month = _month_start(active_configs[0].effective_from)
    end_month = _parse_month(through_month)
    latest_payment_month = max((_month_start(payment.payment_date) for payment in payments), default=end_month)
    end_month = _latest_month(end_month, latest_payment_month)

    remaining_paid = sum((_decimal(payment.amount_paid) for payment in payments), Decimal("0.00"))
    rows = []
    cursor = start_month

    while cursor <= end_month:
        fee = _fee_for_month(active_configs, cursor)
        if fee is None:
            cursor = _add_month(cursor)
            continue

        allocated = min(remaining_paid, fee)
        remaining_paid = (remaining_paid - allocated).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        balance = (fee - allocated).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        if allocated == Decimal("0.00"):
            status = "DUE"
        elif balance == Decimal("0.00"):
            status = "PAID"
        else:
            status = "PARTIAL"

        rows.append(
            {
                "month": _format_month(cursor),
                "amount_due": float(fee),
                "amount_paid": float(allocated),
                "balance": float(balance),
                "status": status,
            }
        )
        cursor = _add_month(cursor)

    while remaining_paid > Decimal("0.00"):
        fee = _fee_for_month(active_configs, cursor) or _decimal(active_configs[-1].monthly_fee)
        allocated = min(remaining_paid, fee)
        remaining_paid = (remaining_paid - allocated).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        balance = (fee - allocated).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        rows.append(
            {
                "month": _format_month(cursor),
                "amount_due": float(fee),
                "amount_paid": float(allocated),
                "balance": float(balance),
                "status": "ADVANCE",
            }
        )
        cursor = _add_month(cursor)

    return rows


async def get_student_finance_details(
    db: AsyncSession,
    *,
    student_id: int,
    through_month: str | None = None,
):
    student_result = await db.execute(
        select(Student)
        .options(selectinload(Student.class_), selectinload(Student.parent))
        .where(Student.id == student_id)
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    configs_result = await db.execute(
        select(StudentFeeConfig)
        .where(StudentFeeConfig.student_id == student_id)
        .order_by(StudentFeeConfig.effective_from, StudentFeeConfig.id)
    )
    fee_configs = list(configs_result.scalars().all())

    ledger_result = await db.execute(
        select(FeeLedger)
        .where(FeeLedger.student_id == student_id)
        .order_by(FeeLedger.payment_date, FeeLedger.id)
    )
    ledger = list(ledger_result.scalars().all())
    breakdown = compute_fee_breakdown(
        fee_configs=fee_configs,
        payments=ledger,
        through_month=through_month,
    )
    current_month = _format_month(_parse_month(through_month))
    current_row = next((row for row in breakdown if row["month"] == current_month), None)
    latest_config = fee_configs[-1] if fee_configs else None

    return {
        "student": student,
        "class_name": student.class_.name if student.class_ else "N/A",
        "parent_name": student.parent.name if student.parent else "N/A",
        "monthly_fee": float(_decimal(latest_config.monthly_fee)) if latest_config else 0.0,
        "current_status": current_row["status"] if current_row else "UNCONFIGURED",
        "current_due": current_row["balance"] if current_row else 0.0,
        "ledger": [
            {
                "id": entry.id,
                "amount_paid": entry.amount_paid,
                "payment_date": entry.payment_date.isoformat(),
                "payment_mode": entry.payment_mode,
                "note": entry.note or "",
                "created_by": entry.created_by,
            }
            for entry in ledger
        ],
        "breakdown": breakdown,
    }


async def create_fee_config(
    db: AsyncSession,
    *,
    acting_user: User,
    student_id: int,
    monthly_fee: float,
    effective_from: date,
    status: str = "active",
):
    if acting_user.role not in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to configure fees.")

    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if is_school_admin(acting_user) and student.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot configure fees outside your school.")

    config = StudentFeeConfig(
        student_id=student_id,
        monthly_fee=monthly_fee,
        effective_from=effective_from,
        status=(status or "active").lower(),
    )
    db.add(config)
    await db.flush()
    return config


async def add_fee_payment(
    db: AsyncSession,
    *,
    acting_user: User,
    student_id: int,
    amount_paid: float,
    payment_date: date,
    payment_mode: str,
    note: str | None,
):
    if acting_user.role not in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Only school admins and super admins can add payments.")

    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if is_school_admin(acting_user) and student.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot add payments outside your school.")

    payment = FeeLedger(
        student_id=student_id,
        amount_paid=amount_paid,
        payment_date=payment_date,
        payment_mode=payment_mode.strip(),
        note=(note or "").strip() or None,
        created_by=acting_user.id,
    )
    db.add(payment)
    await db.flush()
    return payment


async def get_finance_scope(
    db: AsyncSession,
    *,
    acting_user: User,
    school_id: int | None = None,
    class_id: int | None = None,
):
    selected_school_id = school_id
    school = None
    classes = await get_allowed_classes(db, acting_user, school_id=school_id if is_super_admin(acting_user) else None)
    allowed_class_ids = {class_.id for class_ in classes}

    if is_school_admin(acting_user):
        selected_school_id = acting_user.school_id
    elif acting_user.role == UserRole.TEACHER:
        selected_school_id = acting_user.school_id

    if selected_school_id is not None:
        school_result = await db.execute(select(School).where(School.id == selected_school_id))
        school = school_result.scalar_one_or_none()

    if class_id and class_id not in allowed_class_ids:
        raise HTTPException(status_code=403, detail="You do not have access to this class.")

    query = (
        select(Student)
        .options(selectinload(Student.class_), selectinload(Student.parent))
        .order_by(Student.name)
    )

    if class_id is not None:
        query = query.where(Student.class_id == class_id)
    elif acting_user.role == UserRole.TEACHER and allowed_class_ids:
        query = query.where(Student.class_id.in_(allowed_class_ids))
    elif selected_school_id is not None:
        query = query.where(Student.school_id == selected_school_id)

    if selected_school_id is not None and acting_user.role != UserRole.TEACHER:
        query = query.where(Student.school_id == selected_school_id)

    result = await db.execute(query)
    students = list(result.scalars().unique().all())

    if acting_user.role == UserRole.TEACHER:
        classes = [class_ for class_ in classes if class_.id in allowed_class_ids]
    elif selected_school_id is not None:
        classes = [class_ for class_ in classes if class_.school_id == selected_school_id]

    return FinanceScope(
        students=students,
        classes=classes,
        school=school,
        selected_school_id=selected_school_id,
        selected_class_id=class_id,
    )


async def build_student_fee_row(
    db: AsyncSession,
    *,
    student: Student,
    month: str | None = None,
):
    details = await get_student_finance_details(db, student_id=student.id, through_month=month)
    current_month = _format_month(_parse_month(month))
    current_row = next((row for row in details["breakdown"] if row["month"] == current_month), None)
    return {
        "student": student,
        "monthly_fee": details["monthly_fee"],
        "paid": current_row["amount_paid"] if current_row else 0.0,
        "due": current_row["balance"] if current_row else details["monthly_fee"],
        "status": current_row["status"] if current_row else "UNCONFIGURED",
        "details": details,
    }


async def get_finance_summary_for_students(
    db: AsyncSession,
    *,
    students: list[Student],
    month: str | None = None,
):
    total_expected = Decimal("0.00")
    total_collected = Decimal("0.00")
    total_pending = Decimal("0.00")
    pending_rows = []

    for student in students:
        row = await build_student_fee_row(db, student=student, month=month)
        total_expected += _decimal(row["monthly_fee"])
        total_collected += _decimal(row["paid"])
        total_pending += _decimal(row["due"])
        if row["status"] in {"DUE", "PARTIAL"}:
            pending_rows.append(row)

    return {
        "total_expected": float(total_expected),
        "total_collected": float(total_collected),
        "total_pending": float(total_pending),
        "pending_rows": pending_rows,
        "pending_count": len(pending_rows),
    }
