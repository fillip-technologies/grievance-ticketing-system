"""add sections table + users.section_id / tickets.section_id

Lets an OrgAdmin define custom routing sections (e.g. "Sales", "HR") beyond the built-in
Support/Enquiry category. A Resolver can be dedicated to a section (`users.section_id`); the
AI classifier matches inbound messages against the org's active sections and, on a match,
auto-assigns (round robin) to that section's Resolver pool regardless of the general
auto_assign_resolver toggle — see ticket_service.py.

Revision ID: 0008_sections
Revises: 0007_auto_assign_default_off
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_sections"
down_revision: Union[str, None] = "0007_auto_assign_default_off"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "sections" not in inspector.get_table_names():
        op.create_table(
            "sections",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=False, server_default=""),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("last_assigned_resolver_id", sa.String(64), nullable=True),
            sa.UniqueConstraint("org_id", "name", name="uq_section_org_name"),
        )

    # Plain nullable columns, not a DB-enforced FK constraint — same approach as every other
    # additive migration in this project (0002/0005): SQLite can't ALTER TABLE ADD CONSTRAINT
    # outside batch-mode table recreation, which prior migrations here have avoided. The
    # relationship is still declared on the ORM side (models.py); a Section delete nulls out
    # referencing rows at the application layer (see routers/sections.py) instead of relying
    # on ON DELETE SET NULL at the DB level.
    for table, column_name in [("users", "section_id"), ("tickets", "section_id")]:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column_name in existing:
            continue  # already present — created fresh by 0001's create_all on a brand-new database
        op.add_column(table, sa.Column(column_name, sa.String(64), nullable=True))


def downgrade() -> None:
    # Deliberately does not attempt to drop users.section_id / tickets.section_id here: on a
    # database whose tables were created via 0001's create_all() from current ORM metadata
    # (models.py declares this column with a real ForeignKey + index), SQLite bakes both into
    # the table's inline DDL, and even alembic's batch-mode table recreation trips over
    # recreating the now-dangling index. `alembic downgrade base` continues past this revision
    # to 0001's downgrade(), which does `Base.metadata.drop_all()` — dropping `tickets`/`users`
    # (and `sections`) entirely — so surgically removing just this column here would be wasted,
    # fragile work with nothing left standing to observe it. Only drop what 0001 won't reach if
    # downgrade stops exactly here (i.e. the `sections` table itself).
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sections" in inspector.get_table_names():
        op.drop_table("sections")
