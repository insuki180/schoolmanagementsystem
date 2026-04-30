"""add is_temp_password to users

Revision ID: f6b2c1d4e8a9
Revises: e1f4a7b9c2d3
Create Date: 2026-04-30 09:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "f6b2c1d4e8a9"
down_revision = "e1f4a7b9c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_temp_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE users "
        "SET is_temp_password = TRUE "
        "WHERE must_change_password = TRUE"
    )
    op.alter_column("users", "is_temp_password", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_temp_password")
