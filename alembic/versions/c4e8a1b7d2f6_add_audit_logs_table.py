"""add audit_logs table

Revision ID: c4e8a1b7d2f6
Revises: f6b2c1d4e8a9
Create Date: 2026-04-30 10:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "c4e8a1b7d2f6"
down_revision = "f6b2c1d4e8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("performed_by", sa.Integer, nullable=False),
        sa.Column("target_user", sa.Integer, nullable=True),
        sa.Column("school_id", sa.Integer, nullable=True),
        sa.Column("class_id", sa.Integer, nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
