"""Initial schema

Revision ID: 20260406_0001
Revises: 
Create Date: 2026-04-06 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260406_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("repo_url", sa.String(length=500), nullable=False),
        sa.Column("repo_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("last_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_projects_repo_url", "projects", ["repo_url"], unique=False)
    op.create_index("ix_projects_created_at", "projects", ["created_at"], unique=False)

    op.create_table(
        "user_projects",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "project_id"),
    )
    op.create_index("ix_user_projects_user", "user_projects", ["user_id"], unique=False)
    op.create_index("ix_user_projects_project", "user_projects", ["project_id"], unique=False)
    op.create_index("ix_user_projects_role", "user_projects", ["role"], unique=False)

    op.create_table(
        "otps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_otps_email", "otps", ["email"], unique=False)
    op.create_index("ix_otps_expires", "otps", ["expires_at"], unique=False)

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("repo_url", sa.String(length=500), nullable=False),
        sa.Column("repo_name", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=True),
        sa.Column("total_issues", sa.Integer(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=True),
        sa.Column("total_lines", sa.Integer(), nullable=True),
        sa.Column("languages", sa.Text(), nullable=True),
        sa.Column("issues", sa.Text(), nullable=True),
        sa.Column("file_tree", sa.Text(), nullable=True),
        sa.Column("ollama_findings", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("repo_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_analysis_status", "analysis_results", ["status"], unique=False)
    op.create_index("ix_analysis_project", "analysis_results", ["project_id"], unique=False)
    op.create_index("ix_analysis_created", "analysis_results", ["created_at"], unique=False)
    op.create_index("ix_analysis_repo_url", "analysis_results", ["repo_url"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_repo_url", table_name="analysis_results")
    op.drop_index("ix_analysis_created", table_name="analysis_results")
    op.drop_index("ix_analysis_project", table_name="analysis_results")
    op.drop_index("ix_analysis_status", table_name="analysis_results")
    op.drop_table("analysis_results")

    op.drop_index("ix_otps_expires", table_name="otps")
    op.drop_index("ix_otps_email", table_name="otps")
    op.drop_table("otps")

    op.drop_index("ix_user_projects_role", table_name="user_projects")
    op.drop_index("ix_user_projects_project", table_name="user_projects")
    op.drop_index("ix_user_projects_user", table_name="user_projects")
    op.drop_table("user_projects")

    op.drop_index("ix_projects_created_at", table_name="projects")
    op.drop_index("ix_projects_repo_url", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
