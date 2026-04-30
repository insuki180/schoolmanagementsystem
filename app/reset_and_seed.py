"""Reset the database while preserving the super admin, then seed realistic demo data."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import insert, select, text

import app.models  # noqa: F401
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.absence_response import AbsenceResponse
from app.models.attendance import Attendance
from app.models.audit_log import AuditLog
from app.models.class_ import Class, ClassSubject, teacher_classes
from app.models.exam import Exam
from app.models.finance import FeeLedger, StudentFeeConfig
from app.models.mark import Mark
from app.models.notification import Notification
from app.models.school import School
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.seed import ABSENCE_MESSAGES, PARENT_NAMES, STUDENT_NAMES, SUBJECT_NAMES, TEACHER_NAMES
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_PASSWORD = "demo123"
CURRENT_YEAR_START = date(date.today().year, 1, 1)
ATTENDANCE_DAYS = 10
EXAM_SPECS = [
    ("Term 1 Assessment", date(date.today().year, 8, 20)),
    ("Term 2 Assessment", date(date.today().year, 12, 5)),
]
SCHOOL_BLUEPRINTS = [
    {
        "slug": "greenfield",
        "name": "Greenfield Public School",
        "address": "18 Park Lane, Hyderabad",
        "phone": "9876501001",
        "grades": [1, 2, 3, 4, 5, 6],
        "sections": ["A", "B"],
        "monthly_fee_base": 1850.0,
        "admin_name": "Neelima Varghese",
        "admin_email": "admin.greenfield@demo.school",
    },
    {
        "slug": "riverdale",
        "name": "Riverdale Academy",
        "address": "77 Riverside Avenue, Bengaluru",
        "phone": "9876502002",
        "grades": [3, 4, 5, 6, 7, 8],
        "sections": ["A", "B"],
        "monthly_fee_base": 2250.0,
        "admin_name": "Arunesh Rao",
        "admin_email": "admin.riverdale@demo.school",
    },
]


@dataclass
class SeedSummary:
    schools: int = 0
    classes: int = 0
    teachers: int = 0
    parents: int = 0
    students: int = 0
    attendance_records: int = 0
    marks: int = 0
    fee_configs: int = 0
    fee_payments: int = 0
    audit_logs: int = 0


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".", value.lower()).strip(".")
    return normalized or "user"


def build_phone(seed_number: int) -> str:
    return f"9{700000000 + seed_number:09d}"


def months_since(start: date, end: date) -> int:
    return ((end.year - start.year) * 12) + (end.month - start.month) + 1


def build_mark_score(*, school_index: int, class_index: int, student_index: int, subject_index: int, exam_index: int) -> float:
    base = 58 + (school_index * 5) + (class_index * 3)
    variance = ((student_index * 11) + (subject_index * 7) + (exam_index * 13)) % 36
    return float(min(100, base + variance))


def split_payment_amount(total_amount: float, *, seed_number: int) -> list[float]:
    if total_amount <= 0:
        return []
    if total_amount < 1000:
        return [round(total_amount, 2)]

    first = round(total_amount * (0.45 + ((seed_number % 3) * 0.1)), 2)
    second = round(total_amount - first, 2)
    if second <= 0:
        return [round(total_amount, 2)]
    return [first, second]


def payment_dates_for_year(seed_number: int) -> list[date]:
    month_one = 2 + (seed_number % 3)
    month_two = min(11, month_one + 4)
    return [
        date(date.today().year, month_one, 10 + (seed_number % 7)),
        date(date.today().year, month_two, 14 + (seed_number % 9)),
    ]


async def preserve_or_create_super_admin(db) -> User:
    result = await db.execute(
        select(User).where(User.role == UserRole.SUPER_ADMIN).order_by(User.id)
    )
    super_admin = result.scalars().first()
    safe_password = settings.SUPER_ADMIN_PASSWORD[:50]
    if not super_admin:
        super_admin = User(
            name=settings.SUPER_ADMIN_NAME,
            email=settings.SUPER_ADMIN_EMAIL,
            password_hash=hash_password(safe_password),
            role=UserRole.SUPER_ADMIN,
            school_id=None,
            must_change_password=False,
            is_temp_password=False,
            is_active=True,
        )
        db.add(super_admin)
        await db.flush()
        logger.info("Created missing super admin: id=%s email=%s", super_admin.id, super_admin.email)
        return super_admin

    logger.info("Preserving existing super admin: id=%s email=%s", super_admin.id, super_admin.email)
    super_admin.name = settings.SUPER_ADMIN_NAME
    super_admin.email = settings.SUPER_ADMIN_EMAIL
    super_admin.password_hash = hash_password(safe_password)
    super_admin.school_id = None
    super_admin.must_change_password = False
    super_admin.is_temp_password = False
    super_admin.is_active = True
    await db.flush()
    return super_admin


async def reset_database_preserving_super_admin(db) -> User:
    super_admin = await preserve_or_create_super_admin(db)
    logger.info("Resetting database while preserving super admin id=%s", super_admin.id)

    delete_statements = [
        "TRUNCATE TABLE notification_classes RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE fee_ledger RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE student_fee_configs RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE marks RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE attendance RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE absence_responses RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE class_subjects RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE teacher_classes RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE notifications RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE audit_logs RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE students RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE exams RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE subjects RESTART IDENTITY CASCADE",
        "TRUNCATE TABLE classes RESTART IDENTITY CASCADE",
    ]
    for statement in delete_statements:
        await db.execute(text(statement))

    await db.execute(
        text("DELETE FROM users WHERE role::text <> 'SUPER_ADMIN'")
    )
    await db.execute(text("TRUNCATE TABLE schools RESTART IDENTITY CASCADE"))
    await db.flush()
    return super_admin


async def seed_school_dataset(db, super_admin: User, blueprint: dict, school_index: int, summary: SeedSummary):
    password_hash = hash_password(DEFAULT_PASSWORD)
    school = School(
        name=blueprint["name"],
        address=blueprint["address"],
        phone=blueprint["phone"],
        logo_url=None,
    )
    db.add(school)
    await db.flush()
    summary.schools += 1

    school_admin = User(
        name=blueprint["admin_name"],
        email=blueprint["admin_email"],
        password_hash=password_hash,
        role=UserRole.SCHOOL_ADMIN,
        school_id=school.id,
        phone_number=build_phone(1000 + school_index),
        must_change_password=False,
        is_temp_password=False,
        is_active=True,
    )
    db.add(school_admin)
    await db.flush()

    subjects = []
    for subject_name in SUBJECT_NAMES:
        subject = Subject(name=subject_name, school_id=school.id)
        subjects.append(subject)
        db.add(subject)
    await db.flush()
    subject_map = {subject.name: subject for subject in subjects}

    exams = []
    for exam_name, exam_date in EXAM_SPECS:
        exam = Exam(name=exam_name, school_id=school.id, date=exam_date)
        exams.append(exam)
        db.add(exam)
    await db.flush()

    teacher_class_rows: list[dict] = []
    students_by_class: dict[int, list[Student]] = defaultdict(list)
    class_objects: dict[int, Class] = {}
    home_teacher_by_class_id: dict[int, User] = {}
    subject_teacher_ids_by_class_id: dict[int, dict[str, int]] = {}
    sample_targets: dict[str, list[User | Student]] = {"teachers": [], "parents": [], "students": []}

    teacher_name_offset = school_index * 40
    parent_offset = school_index * 300
    student_offset = school_index * 300

    for grade_offset, grade in enumerate(blueprint["grades"], start=1):
        for section_index, section in enumerate(blueprint["sections"], start=1):
            class_name = f"Grade {grade} - {section}"
            class_ = Class(name=class_name, school_id=school.id)
            db.add(class_)
            await db.flush()
            summary.classes += 1
            class_objects[class_.id] = class_

            home_teacher_name = TEACHER_NAMES[(teacher_name_offset + (grade_offset - 1) * 4 + (section_index - 1) * 2) % len(TEACHER_NAMES)]
            support_teacher_name = TEACHER_NAMES[(teacher_name_offset + (grade_offset - 1) * 4 + (section_index - 1) * 2 + 1) % len(TEACHER_NAMES)]
            home_teacher = User(
                name=home_teacher_name,
                email=f"teacher.{blueprint['slug']}.g{grade}{section.lower()}.home@demo.school",
                password_hash=password_hash,
                role=UserRole.TEACHER,
                school_id=school.id,
                phone_number=build_phone(2000 + school_index * 100 + grade_offset * 10 + section_index),
                must_change_password=False,
                is_temp_password=False,
                is_active=True,
            )
            support_teacher = User(
                name=support_teacher_name,
                email=f"teacher.{blueprint['slug']}.g{grade}{section.lower()}.support@demo.school",
                password_hash=password_hash,
                role=UserRole.TEACHER,
                school_id=school.id,
                phone_number=build_phone(3000 + school_index * 100 + grade_offset * 10 + section_index),
                must_change_password=False,
                is_temp_password=False,
                is_active=True,
            )
            db.add_all([home_teacher, support_teacher])
            await db.flush()
            summary.teachers += 2
            sample_targets["teachers"].extend([home_teacher, support_teacher])

            class_.class_teacher_id = home_teacher.id
            home_teacher_by_class_id[class_.id] = home_teacher

            teacher_class_rows.extend(
                [
                    {"teacher_id": home_teacher.id, "class_id": class_.id},
                    {"teacher_id": support_teacher.id, "class_id": class_.id},
                ]
            )

            subject_teacher_pairs = {
                "English": home_teacher.id,
                "Social": home_teacher.id,
                "Mathematics": support_teacher.id,
                "Science": support_teacher.id,
            }
            subject_teacher_ids_by_class_id[class_.id] = subject_teacher_pairs
            for subject_name, teacher_id in subject_teacher_pairs.items():
                db.add(
                    ClassSubject(
                        class_id=class_.id,
                        subject_id=subject_map[subject_name].id,
                        teacher_id=teacher_id,
                    )
                )

            student_count = 30 + ((grade + section_index + school_index) % 11)
            monthly_fee = round(blueprint["monthly_fee_base"] + (grade * 110) + ((section_index - 1) * 50), 2)

            for student_number in range(1, student_count + 1):
                student_seed = student_offset + (grade_offset - 1) * 60 + (section_index - 1) * 35 + student_number
                parent_seed = parent_offset + (grade_offset - 1) * 60 + (section_index - 1) * 35 + student_number

                student_name = STUDENT_NAMES[student_seed % len(STUDENT_NAMES)]
                parent_name = PARENT_NAMES[parent_seed % len(PARENT_NAMES)]
                parent = User(
                    name=parent_name,
                    email=f"parent.{blueprint['slug']}.g{grade}{section.lower()}.{student_number:02d}@demo.school",
                    password_hash=password_hash,
                    role=UserRole.PARENT,
                    school_id=school.id,
                    phone_number=build_phone(4000 + school_index * 1000 + grade_offset * 100 + section_index * 40 + student_number),
                    must_change_password=False,
                    is_temp_password=False,
                    is_active=True,
                )
                db.add(parent)
                await db.flush()
                summary.parents += 1
                sample_targets["parents"].append(parent)

                student = Student(
                    name=student_name,
                    class_id=class_.id,
                    parent_id=parent.id,
                    school_id=school.id,
                    blood_group=["A+", "B+", "O+", "AB+", "A-", "B-", "O-"][(student_seed + grade_offset) % 7],
                    address=f"House {student_number}, {section} Block, Grade {grade}, {blueprint['name']}",
                )
                db.add(student)
                await db.flush()
                summary.students += 1
                students_by_class[class_.id].append(student)
                sample_targets["students"].append(student)

                db.add(
                    StudentFeeConfig(
                        student_id=student.id,
                        monthly_fee=monthly_fee,
                        effective_from=CURRENT_YEAR_START,
                        status="active",
                    )
                )
                summary.fee_configs += 1

                months_elapsed = months_since(CURRENT_YEAR_START, date.today())
                finance_pattern = (student_seed + school_index + grade_offset + section_index) % 4
                if finance_pattern == 0:
                    total_paid = monthly_fee * months_elapsed
                elif finance_pattern == 1:
                    total_paid = (monthly_fee * max(months_elapsed - 1, 0)) + (monthly_fee * 0.5)
                elif finance_pattern == 2:
                    total_paid = monthly_fee * (months_elapsed + 1)
                else:
                    total_paid = monthly_fee * max(months_elapsed - 2, 0)

                payment_chunks = split_payment_amount(total_paid, seed_number=student_seed)
                payment_days = payment_dates_for_year(student_seed)
                for payment_index, amount in enumerate(payment_chunks):
                    db.add(
                        FeeLedger(
                            student_id=student.id,
                            amount_paid=amount,
                            payment_date=payment_days[min(payment_index, len(payment_days) - 1)],
                            payment_mode=["cash", "upi", "bank_transfer"][payment_index % 3],
                            note=f"{['Full fee', 'Fee installment', 'Advance payment'][finance_pattern % 3]} for {class_name}",
                            created_by=school_admin.id,
                        )
                    )
                    summary.fee_payments += 1

    if teacher_class_rows:
        await db.execute(insert(teacher_classes), teacher_class_rows)

    for class_index, (class_id, class_students) in enumerate(students_by_class.items(), start=1):
        class_teacher = home_teacher_by_class_id[class_id]
        subjects_for_class = list(subject_map.values())
        for day_offset in range(ATTENDANCE_DAYS):
            attendance_date = date.today() - timedelta(days=day_offset)
            for student_index, student in enumerate(class_students, start=1):
                is_present = ((school_index + class_index + student_index + day_offset) % 6) != 0
                db.add(
                    Attendance(
                        student_id=student.id,
                        date=attendance_date,
                        is_present=is_present,
                        marked_by=class_teacher.id,
                    )
                )
                summary.attendance_records += 1

                if not is_present and ((student_index + day_offset) % 2 == 0):
                    db.add(
                        AbsenceResponse(
                            student_id=student.id,
                            date=attendance_date,
                            message=ABSENCE_MESSAGES[(student_index + day_offset + class_index) % len(ABSENCE_MESSAGES)],
                            is_read=True,
                            created_by_parent=student.parent_id,
                            leave_days=1 + ((student_index + day_offset) % 2),
                        )
                    )

        for exam_index, exam in enumerate(exams):
            for student_index, student in enumerate(class_students, start=1):
                for subject_index, subject in enumerate(subjects_for_class):
                    teacher_id = subject_teacher_ids_by_class_id[class_id][subject.name]
                    db.add(
                        Mark(
                            student_id=student.id,
                            subject_id=subject.id,
                            exam_id=exam.id,
                            marks_obtained=build_mark_score(
                                school_index=school_index,
                                class_index=class_index,
                                student_index=student_index,
                                subject_index=subject_index,
                                exam_index=exam_index,
                            ),
                            max_marks=100.0,
                            entered_by=teacher_id,
                        )
                    )
                    summary.marks += 1

    schoolwide_notification = Notification(
        title="Fee Reminder",
        message=f"{blueprint['name']} monthly fee ledger has been refreshed for the current term.",
        school_id=school.id,
        sent_by=school_admin.id,
        is_school_wide=True,
    )
    class_notification = Notification(
        title="Attendance Follow-up",
        message="Parents are requested to review recent attendance updates for their section.",
        school_id=school.id,
        sent_by=school_admin.id,
        is_school_wide=False,
    )
    class_notification.target_classes = [class_objects[next(iter(class_objects.keys()))]]
    personal_student = sample_targets["students"][0]
    personal_notification = Notification(
        title="Progress Note",
        message=f"{personal_student.name} has shown strong improvement in classroom participation.",
        school_id=school.id,
        sent_by=school_admin.id,
        target_student_id=personal_student.id,
        is_school_wide=False,
    )
    db.add_all([schoolwide_notification, class_notification, personal_notification])

    teacher_target = sample_targets["teachers"][0]
    parent_target = sample_targets["parents"][0]
    db.add_all(
        [
            AuditLog(
                action="PASSWORD_RESET",
                performed_by=super_admin.id,
                target_user=teacher_target.id,
                school_id=school.id,
                role=teacher_target.role.value,
            ),
            AuditLog(
                action="PASSWORD_RESET",
                performed_by=school_admin.id,
                target_user=parent_target.id,
                school_id=school.id,
                role=parent_target.role.value,
            ),
        ]
    )
    summary.audit_logs += 2


async def seed_realistic_data():
    logging.basicConfig(level=logging.INFO)
    summary = SeedSummary()
    async with AsyncSessionLocal() as db:
        super_admin = await reset_database_preserving_super_admin(db)
        for school_index, blueprint in enumerate(SCHOOL_BLUEPRINTS, start=1):
            await seed_school_dataset(db, super_admin, blueprint, school_index, summary)
        await db.commit()

    logger.info("Seed summary: %s", summary)
    print("Database reset and reseed complete.")
    print(f"Super admin login: {settings.SUPER_ADMIN_EMAIL} / {settings.SUPER_ADMIN_PASSWORD}")
    for blueprint in SCHOOL_BLUEPRINTS:
        print(f"School admin login: {blueprint['admin_email']} / {DEFAULT_PASSWORD}")
    print("Teacher sample login: teacher.greenfield.g1a.home@demo.school / demo123")
    print("Parent sample login: parent.greenfield.g1a.01@demo.school / demo123")
    print(
        "Summary -> "
        f"schools={summary.schools}, classes={summary.classes}, teachers={summary.teachers}, "
        f"parents={summary.parents}, students={summary.students}, attendance={summary.attendance_records}, "
        f"marks={summary.marks}, fee_configs={summary.fee_configs}, fee_payments={summary.fee_payments}, "
        f"audit_logs={summary.audit_logs}"
    )


if __name__ == "__main__":
    asyncio.run(seed_realistic_data())
