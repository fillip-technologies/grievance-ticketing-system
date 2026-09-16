"""add tickets.external_reference (caller-quoted reference/booking number for help-desk tickets)

Supports the Help Desk phone-call intake form: when an admin logs a call, the caller may quote
a reference to an earlier order/booking/ticket in another system. This is distinct from our own
`tickets.id`, which is always system-generated.

Revision ID: 0004_ticket_external_reference
Revises: 0003_failed_notifications
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_ticket_external_reference"
down_revision: Union[str, None] = "0003_failed_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("tickets")}
    if "external_reference" in existing:
        return  # already present — created fresh by 0001's create_all on a brand-new database
    op.add_column("tickets", sa.Column("external_reference", sa.String(255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("tickets")}
    if "external_reference" in existing:
        op.drop_column("tickets", "external_reference")
