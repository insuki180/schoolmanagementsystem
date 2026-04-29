"""Helpers for the parent dashboard and profile management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class, ClassSubject
from app.models.notification import Notification
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User
from app.services.contact_utils import get_whatsapp_link
from app.services.permissions import can_view_student


@dataclass
class TeacherContact:
    name: str
    subject: str
    phone_number: str
    whatsapp_link: str


async def update_student_profile(
    db: AsyncSession,
    *,
    parent_user: User,
    student_id: int,
    blood_group: str | None,
    address: str | None,
) -> Student:
    if not await can_view_student(parent_user, db, student_id):
        raise PermissionError("You can only update your own child's details.")

    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise ValueError("Student not found.")

    student.blood_group = (blood_group or "").strip() or None
    student.address = (address or "").strip() or None
    await db.flush()
    return student


async def get_teacher_contacts_for_student(db: AsyncSession, student: Student) -> dict:
    class_result = await db.execute(select(Class).where(Class.id == student.class_id))
    class_ = class_result.scalar_one_or_none()
    if not class_:
        return {"class_teacher": None, "subject_teachers": []}

    class_teacher = None
    if class_.class_teacher_id:
        teacher_result = await db.execute(select(User).where(User.id == class_.class_teacher_id))
        teacher = teacher_result.scalar_one_or_none()
    else:
        teacher = None
    if teacher:
        class_teacher = TeacherContact(
            name=teacher.name,
            subject="Class Teacher",
            phone_number=teacher.phone_number or "",
            whatsapp_link=get_whatsapp_link(teacher.phone_number),
        )

    assignment_result = await db.execute(
        select(ClassSubject, User, Subject)
        .join(User, User.id == ClassSubject.teacher_id)
        .join(Subject, Subject.id == ClassSubject.subject_id)
        .where(ClassSubject.class_id == class_.id)
        .order_by(ClassSubject.subject_id)
    )
    subject_teachers = []
    seen = set()
    for assignment, teacher, subject in assignment_result.all():
        key = (teacher.id, subject.id)
        if key in seen:
            continue
        seen.add(key)
        subject_teachers.append(
            TeacherContact(
                name=teacher.name,
                subject=subject.name,
                phone_number=teacher.phone_number or "",
                whatsapp_link=get_whatsapp_link(teacher.phone_number),
            )
        )

    return {"class_teacher": class_teacher, "subject_teachers": subject_teachers}


def build_parent_notification_cards(
    *,
    notifications: list[Notification],
    absence_alerts: list[dict],
    student_id: int | None = None,
) -> list[dict]:
    cards = []
    for alert in absence_alerts:
        if student_id is not None and alert["student"].id != student_id:
            continue
        cards.append(
            {
                "title": "Absent Notification",
                "message": f"{alert['student'].name} was marked absent in {alert['class_name']}.",
                "date": alert["date"],
                "action_label": "View / Reply",
                "url": f"/notifications/absence/{alert['student'].id}/{alert['date'].isoformat()}",
                "kind": "absence",
            }
        )
    for notification in notifications:
        cards.append(
            {
                "title": notification.title,
                "message": notification.message,
                "date": notification.created_at,
                "action_label": "View / Reply",
                "url": f"/notifications/view/{notification.id}",
                "kind": "notification",
            }
        )
    def sort_key(item):
        value = item["date"]
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        return datetime.min

    cards.sort(key=sort_key, reverse=True)
    return cards
