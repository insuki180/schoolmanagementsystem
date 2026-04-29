"""add school logo url

Revision ID: a44b9c2f1e8f
Revises: 5dade0b7023a
Create Date: 2026-04-29 09:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a44b9c2f1e8f"
down_revision: Union[str, Sequence[str], None] = "5dade0b7023a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("logo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("schools", "logo_url")
