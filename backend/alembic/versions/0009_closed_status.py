"""add tickets.closed_at + organization_settings.auto_close_after_days

Supports the new customer-confirmed "Closed" ticket status: closed_at records when a
ticket actually closed (customer-confirmed, auto-closed after the grace period, or
manually closed by an OrgAdmin), and auto_close_after_days is the per-org grace period
before an unconfirmed Resolved ticket auto-closes — see ticket_service.py.

Revision ID: 0009_closed_status
Revises: 0008_sections
Create Date: 2026-09-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_closed_status"
down_revision: Union[str, None] = "0008_sections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    ticket_columns = {c["name"] for c in inspector.get_columns("tickets")}
    if "closed_at" not in ticket_columns:
        op.add_column("tickets", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    settings_columns = {c["name"] for c in inspector.get_columns("organization_settings")}
    if "auto_close_after_days" not in settings_columns:
        op.add_column(
            "organization_settings",
            sa.Column("auto_close_after_days", sa.Integer(), nullable=False, server_default="3"),
        )


def downgrade() -> None:
    # See 0008_sections.downgrade()'s note: not attempted, since `alembic downgrade base`
    # continues to 0001's downgrade() which drops these tables entirely anyway.
    pass
