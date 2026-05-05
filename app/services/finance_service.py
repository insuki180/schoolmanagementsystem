"""Finance business logic and fee allocation helpers."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.class_ import Class
from app.models.finance import FeeLedger, FeeStructure, FeeType, StudentFee, StudentFeeConfig
from app.models.school import School
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.permissions import get_allowed_classes, is_school_admin, is_super_admin, is_teacher_like


TWOPLACES = Decimal("0.01")
logger = logging.getLogger(__name__)


@dataclass
class FinanceScope:
    students: list[Student]
    classes: list[Class]
    school: School | None
    selected_school_id: int | None
    selected_class_id: int | None


@dataclass
class PrefetchedFinanceData:
    configs_by_student: dict[int, list[StudentFeeConfig]]
    ledger_by_student: dict[int, list[FeeLedger]]


@dataclass
class FeeGenerationResult:
    created: list[StudentFee]
    existing: list[StudentFee]


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


def _period_months(fee_type: FeeType | str) -> int:
    value = fee_type.value if isinstance(fee_type, FeeType) else str(fee_type)
    mapping = {
        FeeType.MONTHLY.value: 1,
        FeeType.QUARTERLY.value: 3,
        FeeType.HALF_YEARLY.value: 6,
        FeeType.YEARLY.value: 12,
    }
    if value not in mapping:
        raise ValueError(f"Unsupported fee type: {value}")
    return mapping[value]


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _advance_period_start(value: date, months: int) -> date:
    total_month = value.month - 1 + months
    year = value.year + (total_month // 12)
    month = total_month % 12 + 1
    return date(year, month, 1)


def _period_end_from_start(value: date, months: int) -> date:
    end_start = _advance_period_start(value, months - 1)
    return _last_day_of_month(end_start.year, end_start.month)


def build_fee_periods(
    *,
    fee_type: FeeType | str,
    effective_from: date,
    through_date: date,
) -> list[tuple[date, date]]:
    months = _period_months(fee_type)
    periods = []
    cursor = _month_start(effective_from)
    limit = _month_start(through_date)
    while cursor <= limit:
        periods.append((cursor, _period_end_from_start(cursor, months)))
        cursor = _advance_period_start(cursor, months)
    return periods


def _compute_student_fee_status(student_fee: StudentFee) -> str:
    balance = Decimal(str(student_fee.amount_due or 0)) - Decimal(str(student_fee.amount_paid or 0))
    if Decimal(str(student_fee.amount_paid or 0)) <= Decimal("0.00"):
        return "DUE"
    if balance <= Decimal("0.00"):
        return "PAID"
    return "PARTIAL"


def allocate_payment_to_student_fees(student_fees: list[StudentFee], *, payment_amount: float) -> float:
    remaining = _decimal(payment_amount)
    for student_fee in sorted(student_fees, key=lambda row: (row.period_start, row.id or 0)):
        outstanding = _decimal(student_fee.amount_due) - _decimal(student_fee.amount_paid)
        if outstanding <= Decimal("0.00"):
            student_fee.status = "PAID"
            continue
        allocation = min(outstanding, remaining)
        if allocation <= Decimal("0.00"):
            break
        student_fee.amount_paid = float((_decimal(student_fee.amount_paid) + allocation).quantize(TWOPLACES, rounding=ROUND_HALF_UP))
        remaining = (remaining - allocation).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        student_fee.status = _compute_student_fee_status(student_fee)
    return float(remaining)


def allocate_advance_payment_to_periods(
    *,
    current_fees: list[StudentFee],
    remaining_amount: float,
    class_id: int,
    student_id: int,
    fee_amount: float,
    fee_type: FeeType | str,
) -> list[StudentFee]:
    remaining = _decimal(remaining_amount)
    created_periods: list[StudentFee] = []
    if remaining <= Decimal("0.00"):
        return created_periods

    latest_fee = max(current_fees, key=lambda row: (row.period_start, getattr(row, "id", 0)))
    months = _period_months(fee_type)
    next_start = _advance_period_start(latest_fee.period_start, months)

    while remaining > Decimal("0.00"):
        due = _decimal(fee_amount)
        paid = min(remaining, due)
        remaining = (remaining - paid).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        status = "ADVANCE" if paid == due else "PARTIAL"
        fee_row = SimpleNamespace(
            id=None,
            student_id=student_id,
            class_id=class_id,
            period_start=next_start,
            period_end=_period_end_from_start(next_start, months),
            fee_type=fee_type,
            amount_due=float(due),
            amount_paid=float(paid),
            carry_forward=0.0,
            status=status,
        )
        created_periods.append(fee_row)
        next_start = _advance_period_start(next_start, months)
    return created_periods


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
        logger.debug("Finance breakdown requested without active configs; returning empty breakdown.")
        return []

    start_month = _month_start(active_configs[0].effective_from)
    end_month = _parse_month(through_month)
    latest_payment_month = max((_month_start(payment.payment_date) for payment in payments), default=end_month)
    end_month = _latest_month(end_month, latest_payment_month)

    remaining_paid = sum((_decimal(payment.amount_paid) for payment in payments), Decimal("0.00"))
    logger.debug(
        "Computing finance breakdown: config_count=%s payment_count=%s start_month=%s end_month=%s total_paid=%s",
        len(active_configs),
        len(payments),
        start_month.isoformat(),
        end_month.isoformat(),
        float(remaining_paid),
    )
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

    prefetched = await _load_finance_data_for_students(db, [student_id])
    return _build_finance_details_payload(
        student=student,
        fee_configs=prefetched.configs_by_student.get(student_id, []),
        ledger=prefetched.ledger_by_student.get(student_id, []),
        through_month=through_month,
    )


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
    elif acting_user.role in (UserRole.TEACHER, UserRole.CLASS_TEACHER):
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
    elif acting_user.role in (UserRole.TEACHER, UserRole.CLASS_TEACHER) and allowed_class_ids:
        query = query.where(Student.class_id.in_(allowed_class_ids))
    elif selected_school_id is not None:
        query = query.where(Student.school_id == selected_school_id)

    if selected_school_id is not None and acting_user.role not in (UserRole.TEACHER, UserRole.CLASS_TEACHER):
        query = query.where(Student.school_id == selected_school_id)

    result = await db.execute(query)
    students = list(result.scalars().unique().all())

    if acting_user.role in (UserRole.TEACHER, UserRole.CLASS_TEACHER):
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
    prefetched: PrefetchedFinanceData | None = None,
):
    if prefetched is None:
        prefetched = await _load_finance_data_for_students(db, [student.id])
    details = _build_finance_details_payload(
        student=student,
        fee_configs=prefetched.configs_by_student.get(student.id, []),
        ledger=prefetched.ledger_by_student.get(student.id, []),
        through_month=month,
    )
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
    if not students:
        return {
            "total_expected": 0.0,
            "total_collected": 0.0,
            "total_pending": 0.0,
            "pending_rows": [],
            "pending_count": 0,
            "rows": [],
        }

    prefetched = await _load_finance_data_for_students(db, [student.id for student in students])
    total_expected = Decimal("0.00")
    total_collected = Decimal("0.00")
    total_pending = Decimal("0.00")
    pending_rows = []
    rows = []

    for student in students:
        row = await build_student_fee_row(db, student=student, month=month, prefetched=prefetched)
        rows.append(row)
        total_expected += _decimal(row["monthly_fee"])
        total_collected += _decimal(row["paid"])
        total_pending += _decimal(row["due"])
        if row["status"] in {"DUE", "PARTIAL"}:
            pending_rows.append(row)

    summary = {
        "total_expected": float(total_expected),
        "total_collected": float(total_collected),
        "total_pending": float(total_pending),
        "pending_rows": pending_rows,
        "pending_count": len(pending_rows),
        "rows": rows,
    }
    logger.info(
        "Finance summary computed: student_count=%s pending_count=%s total_expected=%s total_collected=%s total_pending=%s",
        len(students),
        summary["pending_count"],
        summary["total_expected"],
        summary["total_collected"],
        summary["total_pending"],
    )
    return summary


async def _load_finance_data_for_students(
    db: AsyncSession,
    student_ids: list[int],
) -> PrefetchedFinanceData:
    if not student_ids:
        return PrefetchedFinanceData(configs_by_student={}, ledger_by_student={})

    configs_result = await db.execute(
        select(StudentFeeConfig)
        .where(StudentFeeConfig.student_id.in_(student_ids))
        .order_by(StudentFeeConfig.student_id, StudentFeeConfig.effective_from, StudentFeeConfig.id)
    )
    ledger_result = await db.execute(
        select(FeeLedger)
        .where(FeeLedger.student_id.in_(student_ids))
        .order_by(FeeLedger.student_id, FeeLedger.payment_date, FeeLedger.id)
    )

    configs_by_student = defaultdict(list)
    for config in configs_result.scalars().all():
        configs_by_student[config.student_id].append(config)

    ledger_by_student = defaultdict(list)
    for entry in ledger_result.scalars().all():
        ledger_by_student[entry.student_id].append(entry)

    return PrefetchedFinanceData(
        configs_by_student=dict(configs_by_student),
        ledger_by_student=dict(ledger_by_student),
    )


def _build_finance_details_payload(
    *,
    student: Student,
    fee_configs: list[StudentFeeConfig],
    ledger: list[FeeLedger],
    through_month: str | None = None,
):
    breakdown = compute_fee_breakdown(
        fee_configs=fee_configs,
        payments=ledger,
        through_month=through_month,
    )
    logger.debug(
        "Loaded student finance details: student_id=%s config_count=%s payment_count=%s breakdown_rows=%s",
        student.id,
        len(fee_configs),
        len(ledger),
        len(breakdown),
    )
    current_month = _format_month(_parse_month(through_month))
    current_row = next((row for row in breakdown if row["month"] == current_month), None)
    latest_config = fee_configs[-1] if fee_configs else None

    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "class_id": student.class_id,
            "parent_id": student.parent_id,
            "school_id": student.school_id,
        },
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


async def create_fee_structure(
    db: AsyncSession,
    *,
    acting_user: User,
    class_id: int,
    fee_type: FeeType | str,
    amount: float,
    effective_from: date,
) -> FeeStructure:
    if acting_user.role not in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to configure fee structures.")

    class_result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = class_result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found.")
    if is_school_admin(acting_user) and class_.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot configure fees outside your school.")

    structure = FeeStructure(
        class_id=class_id,
        fee_type=fee_type,
        amount=amount,
        effective_from=effective_from,
    )
    db.add(structure)
    await db.flush()
    return structure


async def generate_student_fees(
    db: AsyncSession,
    *,
    acting_user: User,
    class_id: int,
    fee_type: FeeType | str,
    through_date: date,
    student_id: int | None = None,
) -> FeeGenerationResult:
    class_result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = class_result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found.")
    if acting_user.role not in (UserRole.SCHOOL_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="You do not have permission to generate student fees.")
    if is_school_admin(acting_user) and class_.school_id != acting_user.school_id:
        raise HTTPException(status_code=403, detail="You cannot generate fees outside your school.")

    fee_type_value = fee_type.value if isinstance(fee_type, FeeType) else fee_type
    structure_result = await db.execute(
        select(FeeStructure)
        .where(FeeStructure.class_id == class_id, FeeStructure.fee_type == fee_type_value)
        .order_by(FeeStructure.effective_from.desc(), FeeStructure.id.desc())
    )
    structure = structure_result.scalars().first()
    if not structure:
        raise HTTPException(status_code=404, detail="No fee structure found for the selected class and fee type.")

    student_query = select(Student).where(Student.class_id == class_id).order_by(Student.id)
    if student_id is not None:
        student_query = student_query.where(Student.id == student_id)
    students_result = await db.execute(student_query)
    students = list(students_result.scalars().all())
    if not students:
        raise HTTPException(status_code=404, detail="No students found for fee generation.")

    periods = build_fee_periods(
        fee_type=fee_type_value,
        effective_from=structure.effective_from,
        through_date=through_date,
    )

    created: list[StudentFee] = []
    existing: list[StudentFee] = []

    for student in students:
        existing_result = await db.execute(
            select(StudentFee)
            .where(
                StudentFee.student_id == student.id,
                StudentFee.fee_type == fee_type_value,
            )
            .order_by(StudentFee.period_start, StudentFee.id)
        )
        current_fees = list(existing_result.scalars().all())
        indexed_fees = {(row.period_start, row.period_end): row for row in current_fees}
        carry_forward = 0.0
        if current_fees:
            latest = current_fees[-1]
            carry_forward = max(float(latest.amount_due) - float(latest.amount_paid), 0.0)

        for period_start, period_end in periods:
            if (period_start, period_end) in indexed_fees:
                existing.append(indexed_fees[(period_start, period_end)])
                continue
            student_fee = StudentFee(
                student_id=student.id,
                class_id=class_id,
                period_start=period_start,
                period_end=period_end,
                fee_type=fee_type_value,
                amount_due=float(_decimal(structure.amount) + _decimal(carry_forward)),
                amount_paid=0.0,
                carry_forward=float(_decimal(carry_forward)),
                status="DUE",
            )
            db.add(student_fee)
            created.append(student_fee)
            carry_forward = float(_decimal(student_fee.amount_due))

    await db.flush()
    return FeeGenerationResult(created=created, existing=existing)


async def pay_student_fees(
    db: AsyncSession,
    *,
    acting_user: User,
    student_id: int,
    amount_paid: float,
    payment_date: date,
    payment_mode: str,
    note: str | None,
) -> dict:
    payment = await add_fee_payment(
        db,
        acting_user=acting_user,
        student_id=student_id,
        amount_paid=amount_paid,
        payment_date=payment_date,
        payment_mode=payment_mode,
        note=note,
    )

    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    fees_result = await db.execute(
        select(StudentFee)
        .where(StudentFee.student_id == student_id)
        .order_by(StudentFee.period_start, StudentFee.id)
    )
    student_fees = list(fees_result.scalars().all())
    remaining = allocate_payment_to_student_fees(student_fees, payment_amount=amount_paid)

    if remaining > 0 and student_fees:
        latest_fee = student_fees[-1]
        structure_result = await db.execute(
            select(FeeStructure)
            .where(FeeStructure.class_id == student.class_id, FeeStructure.fee_type == latest_fee.fee_type)
            .order_by(FeeStructure.effective_from.desc(), FeeStructure.id.desc())
        )
        structure = structure_result.scalars().first()
        fee_amount = structure.amount if structure else latest_fee.amount_due
        future_rows = allocate_advance_payment_to_periods(
            current_fees=student_fees,
            remaining_amount=remaining,
            class_id=student.class_id,
            student_id=student_id,
            fee_amount=fee_amount,
            fee_type=latest_fee.fee_type,
        )
        for row in future_rows:
            advance_fee = StudentFee(
                student_id=row.student_id,
                class_id=row.class_id,
                period_start=row.period_start,
                period_end=row.period_end,
                fee_type=row.fee_type,
                amount_due=row.amount_due,
                amount_paid=row.amount_paid,
                carry_forward=max(float(row.amount_due) - float(row.amount_paid), 0.0),
                status=row.status,
            )
            db.add(advance_fee)
            student_fees.append(advance_fee)
        remaining = 0.0

    for row in student_fees:
        row.carry_forward = max(float(row.amount_due) - float(row.amount_paid), 0.0)
        if row.status != "ADVANCE":
            row.status = _compute_student_fee_status(row)
    await db.flush()
    return {
        "payment": payment,
        "remaining_advance": remaining,
        "student_fees": student_fees,
    }


async def get_student_fee_summary(db: AsyncSession, *, student_id: int) -> dict:
    student_result = await db.execute(
        select(Student)
        .options(selectinload(Student.class_), selectinload(Student.parent))
        .where(Student.id == student_id)
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    fees_result = await db.execute(
        select(StudentFee)
        .where(StudentFee.student_id == student_id)
        .order_by(StudentFee.period_start.desc(), StudentFee.id.desc())
    )
    fees = list(fees_result.scalars().all())
    return {
        "student_id": student.id,
        "student_name": student.name,
        "class_id": student.class_id,
        "class_name": student.class_.name if student.class_ else "N/A",
        "rows": [
            {
                "id": row.id,
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "fee_type": row.fee_type.value if isinstance(row.fee_type, FeeType) else row.fee_type,
                "amount_due": row.amount_due,
                "amount_paid": row.amount_paid,
                "carry_forward": row.carry_forward,
                "status": row.status,
            }
            for row in fees
        ],
    }


async def get_due_student_fees(
    db: AsyncSession,
    *,
    acting_user: User,
    class_id: int | None = None,
) -> list[dict]:
    query = (
        select(StudentFee, Student)
        .join(Student, Student.id == StudentFee.student_id)
        .where(StudentFee.status.in_(["DUE", "PARTIAL"]))
        .order_by(StudentFee.period_start, Student.name)
    )
    if acting_user.role == UserRole.SCHOOL_ADMIN:
        query = query.where(Student.school_id == acting_user.school_id)
    elif is_teacher_like(acting_user):
        allowed_classes = await get_allowed_classes(db, acting_user)
        query = query.where(StudentFee.class_id.in_([class_.id for class_ in allowed_classes] or [-1]))
    if class_id is not None:
        query = query.where(StudentFee.class_id == class_id)

    result = await db.execute(query)
    return [
        {
            "student_id": student.id,
            "student_name": student.name,
            "class_id": fee.class_id,
            "fee_type": fee.fee_type.value if isinstance(fee.fee_type, FeeType) else fee.fee_type,
            "period_start": fee.period_start.isoformat(),
            "period_end": fee.period_end.isoformat(),
            "amount_due": fee.amount_due,
            "amount_paid": fee.amount_paid,
            "carry_forward": fee.carry_forward,
            "status": fee.status,
        }
        for fee, student in result.all()
    ]
