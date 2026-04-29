"""add academic permissions and absence responses

Revision ID: b7f3b2e1c4d5
Revises: a44b9c2f1e8f
Create Date: 2026-04-29 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f3b2e1c4d5"
down_revision: Union[str, Sequence[str], None] = "a44b9c2f1e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("classes", sa.Column("class_teacher_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_classes_class_teacher_id_users",
        "classes",
        "users",
        ["class_teacher_id"],
        ["id"],
    )

    op.create_table(
        "class_subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_id", "subject_id", name="uq_class_subject_assignment"),
    )
    op.create_index(op.f("ix_class_subjects_id"), "class_subjects", ["id"], unique=False)

    op.create_table(
        "absence_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_by_parent", sa.Integer(), nullable=False),
        sa.Column("leave_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_parent"], ["users.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "date", name="uq_absence_response_student_date"),
    )
    op.create_index(op.f("ix_absence_responses_id"), "absence_responses", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_absence_responses_id"), table_name="absence_responses")
    op.drop_table("absence_responses")
    op.drop_index(op.f("ix_class_subjects_id"), table_name="class_subjects")
    op.drop_table("class_subjects")
    op.drop_constraint("fk_classes_class_teacher_id_users", "classes", type_="foreignkey")
    op.drop_column("classes", "class_teacher_id")
