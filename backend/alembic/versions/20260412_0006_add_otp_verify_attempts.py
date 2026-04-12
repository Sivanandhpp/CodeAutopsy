"""Add verify_attempts to otps table

Revision ID: 20260412_0006
Revises: 20260407_0005
Create Date: 2026-04-12 01:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260412_0006"
down_revision = "20260407_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "otps",
        sa.Column(
            "verify_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("otps", "verify_attempts")
