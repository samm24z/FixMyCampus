"""AI suggestion fields, grouping of repeat reports, vector index.

Revision ID: 20261019_0006
Revises: 20261008_0005
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261019_0006"
down_revision: Union[str, None] = "20261008_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("suggested_priority", sa.String(20), nullable=True))
    op.add_column("tickets", sa.Column("ai_reason", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("ai_source", sa.String(20), nullable=True))
    op.add_column("tickets", sa.Column("ai_status", sa.String(20), nullable=True))
    op.add_column("tickets", sa.Column("ai_analyzed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("parent_ticket_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("tickets", sa.Column("report_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("tickets", sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key(
        "fk_tickets_parent_ticket_id", "tickets", "tickets", ["parent_ticket_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tickets_parent_ticket_id", "tickets", ["parent_ticket_id"])
    op.execute("CREATE INDEX ix_tickets_embedding_hnsw ON tickets USING hnsw (embedding vector_cosine_ops)")
    op.create_unique_constraint(
        "uq_ticket_duplicates_pair", "ticket_duplicates", ["primary_ticket_id", "duplicate_ticket_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_ticket_duplicates_pair", "ticket_duplicates", type_="unique")
    op.execute("DROP INDEX IF EXISTS ix_tickets_embedding_hnsw")
    op.drop_index("ix_tickets_parent_ticket_id", table_name="tickets")
    op.drop_constraint("fk_tickets_parent_ticket_id", "tickets", type_="foreignkey")
    for column in (
        "escalation_level", "report_count", "parent_ticket_id", "ai_analyzed_at",
        "ai_status", "ai_source", "ai_reason", "suggested_priority",
    ):
        op.drop_column("tickets", column)
