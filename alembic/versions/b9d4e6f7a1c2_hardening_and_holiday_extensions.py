"""hardening and holiday extensions

Revision ID: b9d4e6f7a1c2
Revises: a8c1d2e3f4b5
Create Date: 2026-05-04 13:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b9d4e6f7a1c2"
down_revision = "a8c1d2e3f4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notifications", sa.Column("dedup_key", sa.String(length=255), nullable=True))
    op.create_foreign_key("fk_notifications_user_id_users", "notifications", "users", ["user_id"], ["id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"], unique=False)
    op.create_index("ix_notifications_dedup_key", "notifications", ["dedup_key"], unique=True)
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"], unique=False)

    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_holidays_id", "holidays", ["id"], unique=False)
    op.create_index("ix_holidays_school_id", "holidays", ["school_id"], unique=False)
    op.create_index("ix_holidays_class_id", "holidays", ["class_id"], unique=False)
    op.create_index("ix_holidays_date", "holidays", ["date"], unique=False)
    op.create_index("ix_holidays_created_by", "holidays", ["created_by"], unique=False)
    op.create_index("ix_holidays_school_class_date", "holidays", ["school_id", "class_id", "date"], unique=False)

    op.create_index("ix_student_fees_student_status", "student_fees", ["student_id", "status"], unique=False)
    op.create_unique_constraint("uq_student_fees_student_period_range", "student_fees", ["student_id", "period_start", "period_end"])
    op.create_index("ix_timetable_slots_class_day", "timetable_slots", ["class_id", "day_of_week"], unique=False)
    op.create_index("ix_timetable_slots_teacher_day", "timetable_slots", ["teacher_id", "day_of_week"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_timetable_slots_class_day", table_name="timetable_slots")
    op.drop_index("ix_timetable_slots_teacher_day", table_name="timetable_slots")
    op.drop_constraint("uq_student_fees_student_period_range", "student_fees", type_="unique")
    op.drop_index("ix_student_fees_student_status", table_name="student_fees")

    op.drop_index("ix_holidays_school_class_date", table_name="holidays")
    op.drop_index("ix_holidays_created_by", table_name="holidays")
    op.drop_index("ix_holidays_date", table_name="holidays")
    op.drop_index("ix_holidays_class_id", table_name="holidays")
    op.drop_index("ix_holidays_school_id", table_name="holidays")
    op.drop_index("ix_holidays_id", table_name="holidays")
    op.drop_table("holidays")

    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_index("ix_notifications_dedup_key", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_constraint("fk_notifications_user_id_users", "notifications", type_="foreignkey")
    op.drop_column("notifications", "dedup_key")
    op.drop_column("notifications", "is_read")
    op.drop_column("notifications", "user_id")
