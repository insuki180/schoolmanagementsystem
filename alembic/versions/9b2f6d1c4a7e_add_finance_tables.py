"""add finance tables

Revision ID: 9b2f6d1c4a7e
Revises: c4e8a1b7d2f6
Create Date: 2026-04-30 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b2f6d1c4a7e"
down_revision = "c4e8a1b7d2f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_fee_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("monthly_fee", sa.Float(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_student_fee_configs_id", "student_fee_configs", ["id"], unique=False)
    op.create_index("ix_student_fee_configs_student_id", "student_fee_configs", ["student_id"], unique=False)
    op.create_index("ix_student_fee_configs_effective_from", "student_fee_configs", ["effective_from"], unique=False)

    op.create_table(
        "fee_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("amount_paid", sa.Float(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_mode", sa.String(length=50), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_fee_ledger_id", "fee_ledger", ["id"], unique=False)
    op.create_index("ix_fee_ledger_student_id", "fee_ledger", ["student_id"], unique=False)
    op.create_index("ix_fee_ledger_payment_date", "fee_ledger", ["payment_date"], unique=False)


def downgrade():
    op.drop_index("ix_fee_ledger_payment_date", table_name="fee_ledger")
    op.drop_index("ix_fee_ledger_student_id", table_name="fee_ledger")
    op.drop_index("ix_fee_ledger_id", table_name="fee_ledger")
    op.drop_table("fee_ledger")

    op.drop_index("ix_student_fee_configs_effective_from", table_name="student_fee_configs")
    op.drop_index("ix_student_fee_configs_student_id", table_name="student_fee_configs")
    op.drop_index("ix_student_fee_configs_id", table_name="student_fee_configs")
    op.drop_table("student_fee_configs")
