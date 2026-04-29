"""add parent contact and student profile fields

Revision ID: d3a9c5b1e7f2
Revises: b7f3b2e1c4d5
Create Date: 2026-04-29 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a9c5b1e7f2"
down_revision: Union[str, Sequence[str], None] = "b7f3b2e1c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.execute(
        "UPDATE users "
        "SET phone_number = REGEXP_REPLACE(COALESCE(phone, ''), '\\D', '', 'g') "
        "WHERE phone_number IS NULL AND phone IS NOT NULL"
    )
    op.add_column("students", sa.Column("blood_group", sa.String(length=20), nullable=True))
    op.add_column("students", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "address")
    op.drop_column("students", "blood_group")
    op.drop_column("users", "phone_number")
