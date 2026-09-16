"""idempotent column backfill for a database whose tables pre-date this migration setup

The baseline migration (0001) creates any *missing* table but — like the create_all() it
replaces — never ALTERs a table that already exists. A database that was already running
this app before Phases 1-3 (WhatsApp outbound, business-hours SLA, awaiting-customer pause)
would have all 9 tables already, so 0001 would skip every one of them and this app would
then crash reading columns that don't exist yet. This migration adds exactly those columns,
guarded by an existence check, so it's a no-op on a database that got them from a fresh 0001
create_all and a real fix on one that didn't.

Revision ID: 0002_phase1to3_columns
Revises: 0001_baseline
Create Date: 2026-08-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_phase1to3_columns"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column_name, column_def, server_default_sql)
_COLUMNS = [
    ("organization_settings", "whatsapp_access_token", sa.String(1000), "''"),
    ("organization_settings", "whatsapp_phone_number_id", sa.String(64), "''"),
    ("organization_settings", "whatsapp_app_secret", sa.String(500), "''"),
    ("organization_settings", "business_hours_enabled", sa.Boolean(), "false"),
    ("organization_settings", "business_start_hour", sa.Integer(), "9"),
    ("organization_settings", "business_end_hour", sa.Integer(), "18"),
    ("organization_settings", "business_days", sa.String(32), "'1,2,3,4,5'"),
    ("organization_settings", "timezone", sa.String(64), "'UTC'"),
    ("organization_settings", "holiday_dates", sa.String(2000), "''"),
    ("tickets", "awaiting_customer", sa.Boolean(), "false"),
    ("tickets", "awaiting_customer_since", sa.DateTime(timezone=True), None),
    ("tickets", "sla_warning_sent_at", sa.DateTime(timezone=True), None),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, column_name, column_type, server_default in _COLUMNS:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column_name in existing:
            continue  # already present — created fresh by 0001, nothing to do
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
