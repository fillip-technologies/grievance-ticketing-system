"""add organization_settings.sms_* columns (generic SMS gateway config)

Mirrors the WhatsApp org-settings columns added in 0002 — a generic HTTP SMS API isn't
picked yet, so these are added ahead of time and stay inert (sms_service treats a missing
api_url/api_key/sender_id as "not configured", same as unconfigured SMTP/WhatsApp) until an
OrgAdmin fills them in.

Revision ID: 0005_sms_settings
Revises: 0004_ticket_external_reference
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_sms_settings"
down_revision: Union[str, None] = "0004_ticket_external_reference"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = [
    ("organization_settings", "sms_provider", sa.String(64), "''"),
    ("organization_settings", "sms_api_url", sa.String(500), "''"),
    ("organization_settings", "sms_api_key", sa.String(500), "''"),
    ("organization_settings", "sms_sender_id", sa.String(64), "''"),
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
