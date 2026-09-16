"""baseline schema — everything the app had built up under Base.metadata.create_all()

This project ran on `Base.metadata.create_all()` at startup before Alembic was introduced
(Phases 1-3 of the platform build), so there's no earlier migration history to autogenerate
against. This migration creates the full current schema in one step from `Base.metadata`
directly — functionally identical to what `create_all()` was already doing — so it's safe
to stamp as baseline for both a brand-new database and one that was already running under
`create_all()` (see the `alembic_version` check note in downgrade()).

Every schema change from this point forward gets its own migration generated with
`alembic revision --autogenerate -m "..."` instead of relying on create_all.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401  (registers every model's table on Base.metadata)

    bind = op.get_bind()
    Base.metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    from app.database import Base
    from app import models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind, checkfirst=True)
