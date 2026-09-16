"""flip organization_settings.auto_assign_resolver to default off

0006 shipped this column defaulting to true (preserving prior blind-round-robin behavior).
The actual product requirement is the opposite: new tickets should be left unassigned for the
OrgAdmin to assign manually unless an org explicitly opts back into auto-assignment.

The app never relies on the column's DB-level server_default for new rows — every insert goes
through the SQLAlchemy model (models.py's `default=False`, changed alongside this migration),
so this migration only needs to backfill existing rows. Deliberately not using
`op.alter_column(..., server_default=...)` here: it emits a raw `ALTER COLUMN ... SET DEFAULT`
which Postgres supports but SQLite does not (no `ALTER COLUMN` at all outside batch mode), and
this project's test suite runs the exact same migration path against SQLite — see
0005_sms_settings.py's docstring for the same add/drop-only constraint.

Revision ID: 0007_auto_assign_default_off
Revises: 0006_auto_assign_and_branding
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_auto_assign_default_off"
down_revision: Union[str, None] = "0006_auto_assign_and_branding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bound parameter (not a literal 0/1 or bare `false`) so the DBAPI driver applies the
    # correct type adaptation on both backends — Postgres rejects a bare integer literal
    # against a boolean column, and older SQLite builds don't accept the TRUE/FALSE keywords.
    op.get_bind().execute(sa.text("UPDATE organization_settings SET auto_assign_resolver = :v"), {"v": False})


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE organization_settings SET auto_assign_resolver = :v"), {"v": True})
