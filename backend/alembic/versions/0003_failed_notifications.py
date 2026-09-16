"""add failed_notifications table (retry queue for transient email/WhatsApp send failures)

Revision ID: 0003_failed_notifications
Revises: 0002_phase1to3_columns
Create Date: 2026-08-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_failed_notifications"
down_revision: Union[str, None] = "0002_phase1to3_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "failed_notifications" in inspector.get_table_names():
        return  # created fresh by 0001's create_all on a brand-new database

    op.create_table(
        "failed_notifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ticket_id", sa.String(64), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.String(1000), nullable=False, server_default=""),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "failed_notifications" in inspector.get_table_names():
        op.drop_table("failed_notifications")
