"""add personal notification target student

Revision ID: e1f4a7b9c2d3
Revises: d3a9c5b1e7f2
Create Date: 2026-04-29 20:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f4a7b9c2d3"
down_revision = "d3a9c5b1e7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("target_student_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_notifications_target_student_id_students",
        "notifications",
        "students",
        ["target_student_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_notifications_target_student_id_students", "notifications", type_="foreignkey")
    op.drop_column("notifications", "target_student_id")
