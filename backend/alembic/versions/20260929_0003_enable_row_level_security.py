"""Enable row-level security on every application table.

Supabase exposes the ``public`` schema through its auto-generated REST API using the
public ``anon`` key. Our tables hold password hashes, and all access control is done in
FastAPI, so we lock the tables down: with RLS on and no policies, ``anon``/``authenticated``
see nothing, while the backend's owner role (``postgres``) bypasses RLS and is unaffected.
Harmless on plain PostgreSQL.

Revision ID: 20260929_0003
Revises: 20260929_0002
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260929_0003"
down_revision: Union[str, None] = "20260929_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "roles", "users", "departments", "categories", "tickets", "ticket_comments",
    "ticket_attachments", "ticket_status_history", "ticket_assignments", "ticket_feedback",
    "ticket_duplicates", "sla_rules", "notifications", "audit_logs",
    "knowledge_documents", "knowledge_chunks", "alembic_version",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
