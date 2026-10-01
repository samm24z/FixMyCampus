"""Add a database sequence for ticket numbers.

Ticket numbers were previously derived from ``count(*) + 1``, which races under
concurrent creates and collides after any deletion. The sequence starts at 1000
so it never overlaps the seeded demo tickets (TICK-2026-0101 .. 0104).

Revision ID: 20260929_0002
Revises: 20260927_0001
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260929_0002"
down_revision: Union[str, None] = "20260927_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START WITH 1000")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS ticket_number_seq")
