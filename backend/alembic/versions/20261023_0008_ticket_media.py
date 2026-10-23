"""Ticket photo uploads: draft attachments, media metadata and report location.

Revision ID: 20261023_0008
Revises: 20261019_0007
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20261023_0008"
down_revision: Union[str, None] = "20261019_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drafts are uploaded before a ticket exists, so ticket_id can be empty until the ticket is filed.
    op.alter_column(
        "ticket_attachments",
        "ticket_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column("ticket_attachments", "file_path", new_column_name="storage_key")
    op.add_column("ticket_attachments", sa.Column("kind", sa.String(10), nullable=False, server_default="image"))
    op.add_column("ticket_attachments", sa.Column("status", sa.String(20), nullable=False, server_default="draft"))
    op.add_column("ticket_attachments", sa.Column("thumb_key", sa.String(500), nullable=True))
    op.add_column("ticket_attachments", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("ticket_attachments", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("ticket_attachments", sa.Column("duration_s", sa.Float(), nullable=True))
    op.add_column("ticket_attachments", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column("ticket_attachments", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ticket_attachments", sa.Column("gps_lat", sa.Float(), nullable=True))
    op.add_column("ticket_attachments", sa.Column("gps_lng", sa.Float(), nullable=True))
    op.add_column("ticket_attachments", sa.Column("gps_accuracy_m", sa.Float(), nullable=True))
    op.add_column("ticket_attachments", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_ticket_attachments_status", "ticket_attachments", ["status"])
    op.create_index("ix_ticket_attachments_sha256", "ticket_attachments", ["sha256"])
    op.create_index("ix_ticket_attachments_expires_at", "ticket_attachments", ["expires_at"])

    op.add_column("tickets", sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("report_lat", sa.Float(), nullable=True))
    op.add_column("tickets", sa.Column("report_lng", sa.Float(), nullable=True))
    op.add_column("tickets", sa.Column("report_accuracy_m", sa.Float(), nullable=True))
    op.add_column("tickets", sa.Column("location_source", sa.String(20), nullable=True))


def downgrade() -> None:
    for column in ("location_source", "report_accuracy_m", "report_lng", "report_lat", "observed_at"):
        op.drop_column("tickets", column)

    op.drop_index("ix_ticket_attachments_expires_at", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_sha256", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_status", table_name="ticket_attachments")
    for column in (
        "expires_at",
        "gps_accuracy_m",
        "gps_lng",
        "gps_lat",
        "captured_at",
        "sha256",
        "duration_s",
        "height",
        "width",
        "thumb_key",
        "status",
        "kind",
    ):
        op.drop_column("ticket_attachments", column)
    op.alter_column("ticket_attachments", "storage_key", new_column_name="file_path")

    # Rows without a ticket cannot satisfy NOT NULL; drop the unfiled drafts first.
    op.execute("DELETE FROM ticket_attachments WHERE ticket_id IS NULL")
    op.alter_column(
        "ticket_attachments",
        "ticket_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
