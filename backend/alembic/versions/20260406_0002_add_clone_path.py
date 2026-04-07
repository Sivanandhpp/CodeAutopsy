"""Add clone_path to analysis_results

Revision ID: 20260406_0002
Revises: 20260406_0001
Create Date: 2026-04-06 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260406_0002"
down_revision = "20260406_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_results",
        sa.Column("clone_path", sa.String(length=500), nullable=True),
    )
    op.execute(
        "UPDATE analysis_results SET clone_path = repo_path "
        "WHERE clone_path IS NULL AND repo_path IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("analysis_results", "clone_path")
