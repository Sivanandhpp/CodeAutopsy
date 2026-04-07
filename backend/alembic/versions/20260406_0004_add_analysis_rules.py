"""Add analysis_rules table

Revision ID: 20260406_0004
Revises: 20260406_0003
Create Date: 2026-04-06 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260406_0004"
down_revision = "20260406_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("defect_family", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("match_type", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fix_hint", sa.Text(), nullable=True),
        sa.Column("cwe_id", sa.String(length=20), nullable=True),
        sa.Column("owasp_ref", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analysis_rules_rule_id", "analysis_rules", ["rule_id"], unique=True)
    op.create_index("ix_analysis_rules_language", "analysis_rules", ["language"], unique=False)
    op.create_index("ix_analysis_rules_family", "analysis_rules", ["defect_family"], unique=False)
    op.create_index("ix_analysis_rules_severity", "analysis_rules", ["severity"], unique=False)
    op.create_index("ix_analysis_rules_active", "analysis_rules", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_rules_active", table_name="analysis_rules")
    op.drop_index("ix_analysis_rules_severity", table_name="analysis_rules")
    op.drop_index("ix_analysis_rules_family", table_name="analysis_rules")
    op.drop_index("ix_analysis_rules_language", table_name="analysis_rules")
    op.drop_index("ix_analysis_rules_rule_id", table_name="analysis_rules")
    op.drop_table("analysis_rules")
