"""Allow system-made status changes (e.g. auto-close) with no acting user.

Revision ID: 20261008_0005
Revises: 20260930_0004
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261008_0005"
down_revision: Union[str, None] = "20260930_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("ticket_status_history", "changed_by", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM ticket_status_history WHERE changed_by IS NULL")
    op.alter_column("ticket_status_history", "changed_by", nullable=False)
