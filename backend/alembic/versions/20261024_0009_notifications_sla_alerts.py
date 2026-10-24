"""Notifications list index and SLA alert markers on tickets.

Revision ID: 20261024_0009
Revises: 20261023_0008
Create Date: 2026-10-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261024_0009"
down_revision: Union[str, None] = "20261023_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("sla_warned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True))
    # A person's notifications, newest first, is the only list query.
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_column("tickets", "sla_breached_at")
    op.drop_column("tickets", "sla_warned_at")
