"""add organization_settings.auto_assign_resolver and sender_display_name columns

`auto_assign_resolver` lets an org turn off round-robin resolver assignment on new tickets
(any intake channel) and route everything to a manual-assignment queue instead.
`sender_display_name` lets an org's own brand appear as the email "From" name and in
WhatsApp/SMS message text instead of the previous hardcoded "Grievance Desk" — see
ticket_service.resolve_brand_name.

Revision ID: 0006_auto_assign_and_branding
Revises: 0005_sms_settings
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_auto_assign_and_branding"
down_revision: Union[str, None] = "0005_sms_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = [
    ("organization_settings", "auto_assign_resolver", sa.Boolean(), "true"),
    ("organization_settings", "sender_display_name", sa.String(255), "''"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, column_name, column_type, server_default in _COLUMNS:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column_name in existing:
            continue  # already present — created fresh by 0001's create_all on a brand-new database
        op.add_column(
            table,
            sa.Column(column_name, column_type, nullable=True, server_default=server_default),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, column_name, _column_type, _server_default in reversed(_COLUMNS):
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column_name not in existing:
            continue
        op.drop_column(table, column_name)
