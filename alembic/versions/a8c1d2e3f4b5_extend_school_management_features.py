"""extend school management features

Revision ID: a8c1d2e3f4b5
Revises: 9b2f6d1c4a7e
Create Date: 2026-05-04 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a8c1d2e3f4b5"
down_revision = "9b2f6d1c4a7e"
branch_labels = None
depends_on = None


fee_type_enum = sa.Enum("monthly", "quarterly", "half_yearly", "yearly", name="feetype")


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'class_teacher'")

    fee_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "fee_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("fee_type", fee_type_enum, nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_fee_structures_id", "fee_structures", ["id"], unique=False)
    op.create_index("ix_fee_structures_class_id", "fee_structures", ["class_id"], unique=False)
    op.create_index("ix_fee_structures_fee_type", "fee_structures", ["fee_type"], unique=False)
    op.create_index("ix_fee_structures_effective_from", "fee_structures", ["effective_from"], unique=False)
    op.create_index(
        "ix_fee_structures_class_type_effective",
        "fee_structures",
        ["class_id", "fee_type", "effective_from"],
        unique=False,
    )

    op.create_table(
        "student_fees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("fee_type", fee_type_enum, nullable=False),
        sa.Column("amount_due", sa.Float(), nullable=False),
        sa.Column("amount_paid", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carry_forward", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DUE"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_student_fees_id", "student_fees", ["id"], unique=False)
    op.create_index("ix_student_fees_student_id", "student_fees", ["student_id"], unique=False)
    op.create_index("ix_student_fees_class_id", "student_fees", ["class_id"], unique=False)
    op.create_index("ix_student_fees_period_start", "student_fees", ["period_start"], unique=False)
    op.create_index("ix_student_fees_period_end", "student_fees", ["period_end"], unique=False)
    op.create_index("ix_student_fees_fee_type", "student_fees", ["fee_type"], unique=False)
    op.create_index("ix_student_fees_student_period", "student_fees", ["student_id", "period_start"], unique=False)
    op.create_index("ix_student_fees_class_period", "student_fees", ["class_id", "period_start"], unique=False)

    op.create_table(
        "attendance_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("sender_role", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_attendance_messages_id", "attendance_messages", ["id"], unique=False)
    op.create_index("ix_attendance_messages_student_id", "attendance_messages", ["student_id"], unique=False)
    op.create_index("ix_attendance_messages_attendance_date", "attendance_messages", ["attendance_date"], unique=False)
    op.create_index(
        "ix_attendance_messages_student_date",
        "attendance_messages",
        ["student_id", "attendance_date"],
        unique=False,
    )

    op.create_table(
        "timetable_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("subject_name", sa.String(length=200), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_timetable_slots_id", "timetable_slots", ["id"], unique=False)
    op.create_index("ix_timetable_slots_class_id", "timetable_slots", ["class_id"], unique=False)
    op.create_index("ix_timetable_slots_teacher_id", "timetable_slots", ["teacher_id"], unique=False)
    op.create_index("ix_timetable_slots_day_of_week", "timetable_slots", ["day_of_week"], unique=False)
    op.create_index(
        "ix_timetable_slots_class_day_period",
        "timetable_slots",
        ["class_id", "day_of_week", "period_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_timetable_slots_class_day_period", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_day_of_week", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_teacher_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_class_id", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_id", table_name="timetable_slots")
    op.drop_table("timetable_slots")

    op.drop_index("ix_attendance_messages_student_date", table_name="attendance_messages")
    op.drop_index("ix_attendance_messages_attendance_date", table_name="attendance_messages")
    op.drop_index("ix_attendance_messages_student_id", table_name="attendance_messages")
    op.drop_index("ix_attendance_messages_id", table_name="attendance_messages")
    op.drop_table("attendance_messages")

    op.drop_index("ix_student_fees_class_period", table_name="student_fees")
    op.drop_index("ix_student_fees_student_period", table_name="student_fees")
    op.drop_index("ix_student_fees_fee_type", table_name="student_fees")
    op.drop_index("ix_student_fees_period_end", table_name="student_fees")
    op.drop_index("ix_student_fees_period_start", table_name="student_fees")
    op.drop_index("ix_student_fees_class_id", table_name="student_fees")
    op.drop_index("ix_student_fees_student_id", table_name="student_fees")
    op.drop_index("ix_student_fees_id", table_name="student_fees")
    op.drop_table("student_fees")

    op.drop_index("ix_fee_structures_class_type_effective", table_name="fee_structures")
    op.drop_index("ix_fee_structures_effective_from", table_name="fee_structures")
    op.drop_index("ix_fee_structures_fee_type", table_name="fee_structures")
    op.drop_index("ix_fee_structures_class_id", table_name="fee_structures")
    op.drop_index("ix_fee_structures_id", table_name="fee_structures")
    op.drop_table("fee_structures")
