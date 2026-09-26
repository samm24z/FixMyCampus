"""Create the initial FixMyCampus database schema.

Revision ID: 20260927_0001
Revises:
Create Date: 2026-09-27
"""

from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260927_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "roles",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("permissions", postgresql.JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_roles_name"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_roles_code", "roles", ["code"])

    # head_user_id is added as a constraint after users because users also
    # reference departments through department_id.
    op.create_table(
        "departments",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("head_user_id", _uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_departments_name"),
        sa.UniqueConstraint("code", name="uq_departments_code"),
    )
    op.create_index("ix_departments_name", "departments", ["name"])
    op.create_index("ix_departments_code", "departments", ["code"])

    op.create_table(
        "users",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("department_id", _uuid(), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_foreign_key(
        "fk_departments_head_user_id_users",
        "departments",
        "users",
        ["head_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "categories",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_department_id", _uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_categories_name"),
        sa.UniqueConstraint("code", name="uq_categories_code"),
        sa.ForeignKeyConstraint(["default_department_id"], ["departments.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_categories_name", "categories", ["name"])
    op.create_index("ix_categories_code", "categories", ["code"])

    op.create_table(
        "tickets",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("suggested_category", sa.String(100), nullable=True),
        sa.Column("confirmed_category", sa.String(100), nullable=True),
        sa.Column("suggested_department_id", _uuid(), nullable=True),
        sa.Column("confirmed_department_id", _uuid(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by", _uuid(), nullable=False),
        sa.Column("assigned_to", _uuid(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("ticket_number", name="uq_tickets_ticket_number"),
        sa.ForeignKeyConstraint(["suggested_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("ticket_number", "title", "category", "priority", "location", "status", "created_by", "assigned_to", "sla_deadline"):
        op.create_index(f"ix_tickets_{column}", "tickets", [column])

    op.create_table(
        "ticket_comments",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])
    op.create_index("ix_ticket_comments_user_id", "ticket_comments", ["user_id"])

    op.create_table(
        "ticket_attachments",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", _uuid(), nullable=False),
        sa.Column("uploaded_by", _uuid(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
    op.create_index("ix_ticket_attachments_uploaded_by", "ticket_attachments", ["uploaded_by"])

    op.create_table(
        "ticket_status_history",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", _uuid(), nullable=False),
        sa.Column("changed_by", _uuid(), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_status_history_ticket_id", "ticket_status_history", ["ticket_id"])
    op.create_index("ix_ticket_status_history_changed_by", "ticket_status_history", ["changed_by"])

    op.create_table(
        "ticket_assignments",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", _uuid(), nullable=False),
        sa.Column("assigned_by", _uuid(), nullable=False),
        sa.Column("assigned_to", _uuid(), nullable=False),
        sa.Column("department_id", _uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
    )
    for column in ("ticket_id", "assigned_by", "assigned_to", "department_id"):
        op.create_index(f"ix_ticket_assignments_{column}", "ticket_assignments", [column])

    op.create_table(
        "ticket_feedback",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("ticket_id", name="uq_ticket_feedback_ticket_id"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_feedback_ticket_id", "ticket_feedback", ["ticket_id"])
    op.create_index("ix_ticket_feedback_user_id", "ticket_feedback", ["user_id"])

    op.create_table(
        "ticket_duplicates",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("primary_ticket_id", _uuid(), nullable=False),
        sa.Column("duplicate_ticket_id", _uuid(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("detected_by", sa.String(50), nullable=False),
        sa.Column("verified_by", _uuid(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["primary_ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["duplicate_ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("primary_ticket_id", "duplicate_ticket_id"):
        op.create_index(f"ix_ticket_duplicates_{column}", "ticket_duplicates", [column])

    op.create_table(
        "sla_rules",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("department_id", _uuid(), nullable=True),
        sa.Column("target_resolution_hours", sa.Integer(), nullable=False),
        sa.Column("escalation_threshold_hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("category", "priority", "department_id", name="uq_sla_rule_cat_prio_dept"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sla_rules_category", "sla_rules", ["category"])
    op.create_index("ix_sla_rules_priority", "sla_rules", ["priority"])
    op.create_index("ix_sla_rules_department_id", "sla_rules", ["department_id"])

    op.create_table(
        "notifications",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("ticket_id", _uuid(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_ticket_id", "notifications", ["ticket_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

    op.create_table(
        "audit_logs",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", _uuid(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", _uuid(), nullable=False),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("user_id", "action", "entity_type", "entity_id"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_checksum", sa.String(64), nullable=True),
        sa.Column("uploaded_by", _uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_knowledge_documents_title", "knowledge_documents", ["title"])
    op.create_index("ix_knowledge_documents_category", "knowledge_documents", ["category"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", _uuid(), primary_key=True, nullable=False),
        sa.Column("document_id", _uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_constraint("fk_departments_head_user_id_users", "departments", type_="foreignkey")
    for table in (
        "knowledge_chunks",
        "knowledge_documents",
        "audit_logs",
        "notifications",
        "sla_rules",
        "ticket_duplicates",
        "ticket_feedback",
        "ticket_assignments",
        "ticket_status_history",
        "ticket_attachments",
        "ticket_comments",
        "tickets",
        "categories",
        "users",
        "departments",
        "roles",
    ):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")