"""Demo seed script for a production-like school environment."""

from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta

from sqlalchemy import func, insert, select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.absence_response import AbsenceResponse
from app.models.attendance import Attendance
from app.models.class_ import Class, ClassSubject, teacher_classes
from app.models.exam import Exam
from app.models.mark import Mark
from app.models.notification import Notification, notification_classes
from app.models.school import School
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.auth_service import hash_password

settings = get_settings()

SUBJECT_NAMES = ["English", "Mathematics", "Science", "Social"]
TEACHER_NAMES = [
    "Rajesh Kumar", "Suresh Reddy", "Anjali Sharma", "Priya Nair", "Ravi Teja",
    "Sneha Iyer", "Karthik Varma", "Meena Joshi", "Arjun Mehta", "Deepa Menon",
    "Harish Patel", "Nisha Rao", "Vikram Singh", "Lakshmi Pillai", "Manoj Verma",
    "Divya Krishnan", "Amitabh Das", "Sunita Rani", "Ganesh Bhat", "Pavitra Shetty",
    "Rohit Kulkarni", "Shalini Kapoor", "Madhav Jain", "Keerthi Ramesh", "Pradeep Yadav",
    "Bhavana Desai", "Nitin Chawla", "Farah Ali", "Sanjay Mishra", "Asha Thomas",
    "Vivek Anand", "Komal Arora", "Naveen Gowda", "Rekha Bansal", "Imran Khan",
    "Geetha Namboodiri", "Suraj Tiwari", "Harini Subramanian", "Dinesh Rawat", "Pallavi Sethi",
    "Mohan Rao", "Ritika Malhotra", "Ashwin Prasad", "Neha Kulshrestha", "Tarun Sinha",
    "Supriya Bose", "Lokesh Chandra", "Vidya Narayan", "Saket Dubey", "Preeti Saxena",
]
STUDENT_NAMES = [
    "Aarav Sharma", "Vivaan Reddy", "Aditya Kumar", "Sai Kiran", "Rahul Verma",
    "Ananya Gupta", "Diya Nair", "Kavya Reddy", "Pooja Sharma", "Meera Iyer",
    "Ishaan Patel", "Vihaan Joshi", "Arnav Singh", "Krishna Rao", "Rohan Das",
    "Aanya Menon", "Nitya Kapoor", "Saanvi Shetty", "Myra Bhat", "Ritika Jain",
    "Dev Mehta", "Yash Kulkarni", "Aryan Pillai", "Pranav Mishra", "Kabir Chawla",
    "Sanvi Thomas", "Navya Arora", "Tanvi Krishnan", "Ira Narayan", "Tara Bose",
    "Harsh Vyas", "Kunal Sinha", "Varun Desai", "Shivam Tiwari", "Nikhil Anand",
    "Aditi Rao", "Khushi Verma", "Suhana Ali", "Manya Rawat", "Pallak Sethi",
    "Dhruv Patel", "Laksh Mehra", "Ritesh Bansal", "Akhil Gowda", "Naman Dubey",
    "Riya Sharma", "Ishita Nair", "Palak Reddy", "Mahi Iyer", "Srishti Gupta",
    "Vedant Kumar", "Sarvesh Yadav", "Omkar Bhat", "Atharv Das", "Arya Menon",
    "Nandini Joshi", "Prisha Kapoor", "Veda Shetty", "Charvi Jain", "Janvi Bose",
    "Rudra Singh", "Ayaan Chandra", "Tejas Prasad", "Nirvaan Mishra", "Samar Kulkarni",
    "Avantika Pillai", "Mahika Thomas", "Kiara Narayan", "Anvi Desai", "Esha Arora",
    "Parth Mehta", "Reyansh Rao", "Manav Verma", "Saket Patel", "Tanishq Reddy",
    "Diya Kapoor", "Mira Sharma", "Anika Iyer", "Ishani Nair", "Pihu Gupta",
    "Raghav Kumar", "Ansh Das", "Krish Chawla", "Yuvan Anand", "Arpit Tiwari",
    "Tanya Menon", "Riddhi Bhat", "Kritika Joshi", "Sana Ali", "Aarohi Bose",
    "Vansh Jain", "Aarush Rawat", "Abeer Sinha", "Moksh Gowda", "Devansh Dubey",
    "Navya Sharma", "Trisha Reddy", "Mitali Verma", "Pari Kapoor", "Mehak Iyer",
]
PARENT_NAMES = [
    "Ravi Sharma", "Lakshmi Reddy", "Sunil Kumar", "Kavitha Nair", "Mahesh Verma",
    "Shweta Gupta", "Prakash Iyer", "Sujatha Rao", "Naveen Patel", "Pallavi Joshi",
    "Ramesh Singh", "Deepika Menon", "Sandeep Kapoor", "Bharti Shetty", "Ganesh Bhat",
    "Aparna Jain", "Venkatesh Das", "Rekha Thomas", "Harish Arora", "Neelima Bose",
    "Murali Pillai", "Savita Kulkarni", "Dilip Mishra", "Anita Desai", "Kiran Chawla",
    "Madhavi Narayan", "Arvind Anand", "Shilpa Tiwari", "Rohini Mehta", "Farooq Ali",
    "Lokesh Rawat", "Meghana Sinha", "Suresh Gowda", "Padmini Dubey", "Rahul Bansal",
    "Vidya Krishnan", "Ajay Yadav", "Nandita Prasad", "Sanjana Malhotra", "Pradeep Saxena",
]
ABSENCE_MESSAGES = [
    "Fever, will return tomorrow",
    "Family function leave",
    "Not feeling well",
    "Doctor advised rest for two days",
    "Traveling with family, will join after leave",
]
BLOOD_GROUPS = ["A+", "B+", "O+", "AB+", "A-", "B-", "O-"]

DEMO_PASSWORD = "demo123"


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".", value.lower()).strip(".")
    return normalized or "user"


def phone_number_for(index: int) -> str:
    return f"9{800000000 + index:09d}"


def build_mark_score(*, student_index: int, subject_index: int, class_index: int) -> float:
    return float(60 + ((class_index * 11 + student_index * 7 + subject_index * 9) % 41))


def build_demo_blueprint() -> dict:
    class_names = [f"Grade {idx}" for idx in range(1, 11)]
    return {
        "school": {
            "name": "Sunrise High School",
            "address": "45 Lake View Road, Hyderabad",
            "phone": "9840012345",
            "logo_url": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?auto=format&fit=crop&w=240&q=80",
        },
        "class_names": class_names,
        "subjects": SUBJECT_NAMES,
        "teachers": {
            "class_teachers": TEACHER_NAMES[:10],
            "subject_teachers": TEACHER_NAMES[10:50],
        },
        "students_per_class": STUDENT_NAMES[:10],
    }


async def get_or_create_user(
    db,
    *,
    name: str,
    email: str,
    role: UserRole,
    school_id: int | None,
    phone_number: str | None,
    password_hash: str,
    must_change_password: bool,
    is_active: bool = True,
) -> tuple[User, bool]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    created = False
    if not user:
        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            school_id=school_id,
            phone_number=phone_number,
            must_change_password=must_change_password,
            is_active=is_active,
        )
        db.add(user)
        await db.flush()
        created = True
    else:
        user.name = name
        user.role = role
        user.school_id = school_id
        user.phone_number = phone_number
        user.must_change_password = must_change_password
        user.is_active = is_active
    return user, created


async def seed():
    """Create a complete demo school with academic activity."""
    import app.models  # noqa: F401

    blueprint = build_demo_blueprint()
    password_hash = hash_password(DEMO_PASSWORD)
    print("Using admin password length:", len(settings.SUPER_ADMIN_PASSWORD))
    safe_password = settings.SUPER_ADMIN_PASSWORD[:50]

    async with AsyncSessionLocal() as db:
        super_admin, created_super = await get_or_create_user(
            db,
            name=settings.SUPER_ADMIN_NAME,
            email=settings.SUPER_ADMIN_EMAIL,
            role=UserRole.SUPER_ADMIN,
            school_id=None,
            phone_number=None,
            password_hash=hash_password(safe_password),
            must_change_password=False,
            is_active=True,
        )
        if created_super:
            print(f"Created Super Admin: {settings.SUPER_ADMIN_EMAIL}")
        else:
            print(f"Super Admin already exists: {settings.SUPER_ADMIN_EMAIL}")

        school_result = await db.execute(select(School).where(School.name == blueprint["school"]["name"]))
        school = school_result.scalar_one_or_none()
        if not school:
            school = School(**blueprint["school"])
            db.add(school)
            await db.flush()
            print(f"Created school: {school.name}")
        else:
            school.address = blueprint["school"]["address"]
            school.phone = blueprint["school"]["phone"]
            school.logo_url = blueprint["school"]["logo_url"]

        school_admin, _ = await get_or_create_user(
            db,
            name="Meera Narayan",
            email="principal@sunrisehigh.demo",
            role=UserRole.SCHOOL_ADMIN,
            school_id=school.id,
            phone_number="9840011111",
            password_hash=password_hash,
            must_change_password=False,
            is_active=True,
        )

        subject_result = await db.execute(select(Subject).where(Subject.school_id == school.id))
        subject_map = {subject.name: subject for subject in subject_result.scalars().all()}
        missing_subjects = [
            Subject(name=name, school_id=school.id)
            for name in blueprint["subjects"]
            if name not in subject_map
        ]
        if missing_subjects:
            db.add_all(missing_subjects)
            await db.flush()
            for subject in missing_subjects:
                subject_map[subject.name] = subject

        class_result = await db.execute(select(Class).where(Class.school_id == school.id))
        class_map = {class_.name: class_ for class_ in class_result.scalars().all()}
        for class_name in blueprint["class_names"]:
            if class_name not in class_map:
                class_ = Class(name=class_name, school_id=school.id)
                db.add(class_)
                await db.flush()
                class_map[class_name] = class_

        class_teacher_users: dict[str, User] = {}
        subject_teacher_users: dict[tuple[str, str], User] = {}
        teacher_class_rows: set[tuple[int, int]] = set()

        for idx, class_name in enumerate(blueprint["class_names"], start=1):
            teacher_name = blueprint["teachers"]["class_teachers"][idx - 1]
            teacher_email = f"{slugify(teacher_name)}.grade{idx}.teacher@sunrise.demo"
            teacher, _ = await get_or_create_user(
                db,
                name=teacher_name,
                email=teacher_email,
                role=UserRole.TEACHER,
                school_id=school.id,
                phone_number=phone_number_for(idx),
                password_hash=password_hash,
                must_change_password=True,
                is_active=True,
            )
            class_teacher_users[class_name] = teacher
            class_map[class_name].class_teacher_id = teacher.id
            teacher_class_rows.add((teacher.id, class_map[class_name].id))

        for class_index, class_name in enumerate(blueprint["class_names"]):
            for subject_index, subject_name in enumerate(blueprint["subjects"]):
                teacher_name = blueprint["teachers"]["subject_teachers"][class_index * len(blueprint["subjects"]) + subject_index]
                teacher_email = f"{slugify(teacher_name)}.{slugify(class_name)}.{slugify(subject_name)}@sunrise.demo"
                teacher, _ = await get_or_create_user(
                    db,
                    name=teacher_name,
                    email=teacher_email,
                    role=UserRole.TEACHER,
                    school_id=school.id,
                    phone_number=phone_number_for(100 + class_index * 10 + subject_index),
                    password_hash=password_hash,
                    must_change_password=True,
                    is_active=True,
                )
                subject_teacher_users[(class_name, subject_name)] = teacher
                teacher_class_rows.add((teacher.id, class_map[class_name].id))

        await db.flush()

        existing_teacher_class_rows = set(
            (
                row[0],
                row[1],
            )
            for row in (
                await db.execute(
                    select(teacher_classes.c.teacher_id, teacher_classes.c.class_id).join(
                        Class, Class.id == teacher_classes.c.class_id
                    ).where(Class.school_id == school.id)
                )
            ).all()
        )
        missing_teacher_class_rows = [
            {"teacher_id": teacher_id, "class_id": class_id}
            for teacher_id, class_id in teacher_class_rows
            if (teacher_id, class_id) not in existing_teacher_class_rows
        ]
        if missing_teacher_class_rows:
            await db.execute(insert(teacher_classes), missing_teacher_class_rows)

        assignment_result = await db.execute(
            select(ClassSubject).join(Class, Class.id == ClassSubject.class_id).where(Class.school_id == school.id)
        )
        assignment_map = {(row.class_id, row.subject_id): row for row in assignment_result.scalars().all()}
        for class_name in blueprint["class_names"]:
            class_ = class_map[class_name]
            for subject_name in blueprint["subjects"]:
                subject = subject_map[subject_name]
                teacher = subject_teacher_users[(class_name, subject_name)]
                key = (class_.id, subject.id)
                if key not in assignment_map:
                    assignment = ClassSubject(class_id=class_.id, subject_id=subject.id, teacher_id=teacher.id)
                    db.add(assignment)
                    assignment_map[key] = assignment
                else:
                    assignment_map[key].teacher_id = teacher.id
        await db.flush()

        student_result = await db.execute(
            select(Student).where(Student.school_id == school.id)
        )
        student_map = {
            (student.name, student.class_id, student.parent_id): student
            for student in student_result.scalars().all()
        }
        parent_by_email: dict[str, User] = {}
        student_objects: list[Student] = []

        for class_index, class_name in enumerate(blueprint["class_names"], start=1):
            class_ = class_map[class_name]
            for student_index in range(10):
                name_idx = ((class_index - 1) * 10 + student_index) % len(STUDENT_NAMES)
                parent_idx = ((class_index - 1) * 10 + student_index) % len(PARENT_NAMES)
                student_name = STUDENT_NAMES[name_idx]
                parent_name = PARENT_NAMES[parent_idx]
                email = f"{slugify(student_name)}.g{class_index}.{student_index + 1}.parent@sunrise.demo"
                parent = parent_by_email.get(email)
                if not parent:
                    parent, _ = await get_or_create_user(
                        db,
                        name=parent_name,
                        email=email,
                        role=UserRole.PARENT,
                        school_id=school.id,
                        phone_number=phone_number_for(500 + (class_index - 1) * 10 + student_index),
                        password_hash=password_hash,
                        must_change_password=False,
                        is_active=True,
                    )
                    parent_by_email[email] = parent

                student_key = (student_name, class_.id, parent.id)
                student = student_map.get(student_key)
                if not student:
                    student = Student(
                        name=student_name,
                        class_id=class_.id,
                        parent_id=parent.id,
                        school_id=school.id,
                        blood_group=BLOOD_GROUPS[(class_index + student_index) % len(BLOOD_GROUPS)],
                        address=f"House {10 + student_index}, Lane {class_index}, Hyderabad",
                    )
                    db.add(student)
                    await db.flush()
                    student_map[student_key] = student
                else:
                    student.blood_group = BLOOD_GROUPS[(class_index + student_index) % len(BLOOD_GROUPS)]
                    student.address = f"House {10 + student_index}, Lane {class_index}, Hyderabad"
                student_objects.append(student)

        exam_result = await db.execute(
            select(Exam).where(Exam.school_id == school.id, Exam.name == "Unit Test 1")
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            exam = Exam(name="Unit Test 1", school_id=school.id, date=date.today() - timedelta(days=2))
            db.add(exam)
            await db.flush()
        else:
            exam.date = date.today() - timedelta(days=2)

        student_lookup = {student.id: student for student in student_objects}

        attendance_result = await db.execute(
            select(Attendance.student_id, Attendance.date).join(Student, Student.id == Attendance.student_id).where(Student.school_id == school.id)
        )
        existing_attendance = {(student_id, att_date) for student_id, att_date in attendance_result.all()}
        response_result = await db.execute(
            select(AbsenceResponse.student_id, AbsenceResponse.date).join(Student, Student.id == AbsenceResponse.student_id).where(Student.school_id == school.id)
        )
        existing_responses = {(student_id, response_date) for student_id, response_date in response_result.all()}

        attendance_rows: list[Attendance] = []
        absence_rows: list[AbsenceResponse] = []
        for class_index, class_name in enumerate(blueprint["class_names"]):
            class_ = class_map[class_name]
            class_students = [student for student in student_objects if student.class_id == class_.id]
            marker_id = class_teacher_users[class_name].id
            for day_offset in range(7):
                att_date = date.today() - timedelta(days=day_offset)
                for student_index, student in enumerate(class_students):
                    is_present = ((class_index + student_index + day_offset) % 5) != 0
                    att_key = (student.id, att_date)
                    if att_key not in existing_attendance:
                        attendance_rows.append(
                            Attendance(
                                student_id=student.id,
                                date=att_date,
                                is_present=is_present,
                                marked_by=marker_id,
                            )
                        )
                        existing_attendance.add(att_key)
                    if not is_present and att_key not in existing_responses:
                        absence_rows.append(
                            AbsenceResponse(
                                student_id=student.id,
                                date=att_date,
                                message=ABSENCE_MESSAGES[(student_index + day_offset) % len(ABSENCE_MESSAGES)],
                                is_read=True,
                                created_by_parent=student.parent_id,
                                leave_days=1 + ((class_index + student_index + day_offset) % 2),
                            )
                        )
                        existing_responses.add(att_key)

        if attendance_rows:
            db.add_all(attendance_rows)
        if absence_rows:
            db.add_all(absence_rows)

        mark_result = await db.execute(
            select(Mark.student_id, Mark.subject_id, Mark.exam_id).join(Student, Student.id == Mark.student_id).where(Student.school_id == school.id)
        )
        existing_marks = {(student_id, subject_id, exam_id) for student_id, subject_id, exam_id in mark_result.all()}
        mark_rows: list[Mark] = []
        for class_index, class_name in enumerate(blueprint["class_names"]):
            class_ = class_map[class_name]
            class_students = [student for student in student_objects if student.class_id == class_.id]
            for student_index, student in enumerate(class_students):
                for subject_index, subject_name in enumerate(blueprint["subjects"]):
                    subject = subject_map[subject_name]
                    mark_key = (student.id, subject.id, exam.id)
                    if mark_key in existing_marks:
                        continue
                    teacher = subject_teacher_users[(class_name, subject_name)]
                    mark_rows.append(
                        Mark(
                            student_id=student.id,
                            subject_id=subject.id,
                            exam_id=exam.id,
                            marks_obtained=build_mark_score(
                                student_index=student_index,
                                subject_index=subject_index,
                                class_index=class_index,
                            ),
                            max_marks=100.0,
                            entered_by=teacher.id,
                        )
                    )
                    existing_marks.add(mark_key)
        if mark_rows:
            db.add_all(mark_rows)

        notification_result = await db.execute(
            select(Notification).where(Notification.school_id == school.id)
        )
        existing_notifications = {
            (notification.title, notification.target_student_id, notification.is_school_wide): notification
            for notification in notification_result.scalars().all()
        }
        created_notifications: list[Notification] = []

        schoolwide_data = [
            ("Holiday Notice", "Dear Parents, school will remain closed on Friday for a local holiday.", True, None),
            ("Exam Announcement", "Unit Test 1 starts this week. Please review the timetable and revision notes.", True, None),
        ]
        for title, message, is_school_wide, target_student_id in schoolwide_data:
            key = (title, target_student_id, is_school_wide)
            if key not in existing_notifications:
                notification = Notification(
                    title=title,
                    message=message,
                    school_id=school.id,
                    sent_by=school_admin.id,
                    target_student_id=target_student_id,
                    is_school_wide=is_school_wide,
                )
                db.add(notification)
                created_notifications.append(notification)
                existing_notifications[key] = notification

        attendance_alert_key = ("Attendance Alert", None, False)
        if attendance_alert_key not in existing_notifications:
            notification = Notification(
                title="Attendance Alert",
                message="Please review recent absences in Grade 5 and connect with parents as needed.",
                school_id=school.id,
                sent_by=school_admin.id,
                is_school_wide=False,
            )
            notification.target_classes = [class_map["Grade 5"]]
            db.add(notification)
            created_notifications.append(notification)
            existing_notifications[attendance_alert_key] = notification

        personal_student = next((student for student in student_objects if student.class_id == class_map["Grade 5"].id), student_objects[0])
        personal_key = ("Personal Progress Note", personal_student.id, False)
        if personal_key not in existing_notifications:
            notification = Notification(
                title="Personal Progress Note",
                message=f"{personal_student.name} has shown strong improvement in class participation this week.",
                school_id=school.id,
                sent_by=class_teacher_users["Grade 5"].id,
                target_student_id=personal_student.id,
                is_school_wide=False,
            )
            db.add(notification)
            created_notifications.append(notification)
            existing_notifications[personal_key] = notification

        await db.commit()

        total_classes = (
            await db.execute(select(func.count(Class.id)).where(Class.school_id == school.id))
        ).scalar() or 0
        total_students = (
            await db.execute(select(func.count(Student.id)).where(Student.school_id == school.id))
        ).scalar() or 0
        total_teachers = (
            await db.execute(
                select(func.count(User.id)).where(
                    User.school_id == school.id,
                    User.role == UserRole.TEACHER,
                )
            )
        ).scalar() or 0
        total_attendance = (
            await db.execute(
                select(func.count(Attendance.id))
                .join(Student, Student.id == Attendance.student_id)
                .where(Student.school_id == school.id)
            )
        ).scalar() or 0
        total_marks = (
            await db.execute(
                select(func.count(Mark.id))
                .join(Student, Student.id == Mark.student_id)
                .where(Student.school_id == school.id)
            )
        ).scalar() or 0

        print("Demo seed completed successfully!")
        print(f"School: {school.name}")
        print(f"School admin login: {school_admin.email} / {DEMO_PASSWORD}")
        print(f"Sample teacher login: {class_teacher_users['Grade 1'].email} / {DEMO_PASSWORD}")
        sample_parent_email = f"{slugify(STUDENT_NAMES[0])}.g1.1.parent@sunrise.demo"
        print(f"Sample parent login: {sample_parent_email} / {DEMO_PASSWORD}")
        print(f"total classes: {total_classes}")
        print(f"total students: {total_students}")
        print(f"total teachers: {total_teachers}")
        print(f"total attendance records: {total_attendance}")
        print(f"total marks records: {total_marks}")


if __name__ == "__main__":
    asyncio.run(seed())
