"""Alembic migration correctness — run as real subprocesses (not in-process) since
`get_settings()` is lru_cached at first import and won't pick up a different DATABASE_URL
within the same Python process. This also matches how migrations actually run in
production: `alembic upgrade head` as its own step, not a function call inside the app.
"""

import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

APP_TABLES = {
    "organizations", "organization_settings", "users", "mailboxes",
    "ingested_emails", "tickets", "ticket_replies", "activity_logs",
}

_NEW_COLUMNS = {
    "organization_settings": {
        "whatsapp_access_token", "whatsapp_phone_number_id", "whatsapp_app_secret",
        "business_hours_enabled", "business_start_hour", "business_end_hour",
        "business_days", "timezone", "holiday_dates",
    },
    "tickets": {"awaiting_customer", "awaiting_customer_since", "sla_warning_sent_at"},
}


def _run_alembic(*args: str, db_path: Path) -> subprocess.CompletedProcess:
    env = {"DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}
    import os
    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR), env=full_env, capture_output=True, text=True, timeout=60,
    )


def _table_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_fresh_database_gets_full_schema(tmp_path):
    db_path = tmp_path / f"fresh_{uuid.uuid4().hex}.db"
    result = _run_alembic("upgrade", "head", db_path=db_path)
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert APP_TABLES.issubset(tables)
    assert "alembic_version" in tables

    for table, cols in _NEW_COLUMNS.items():
        assert cols.issubset(_table_columns(db_path, table)), f"{table} missing new columns"


def test_downgrade_drops_everything(tmp_path):
    db_path = tmp_path / f"downgrade_{uuid.uuid4().hex}.db"
    up = _run_alembic("upgrade", "head", db_path=db_path)
    assert up.returncode == 0, up.stderr

    down = _run_alembic("downgrade", "base", db_path=db_path)
    assert down.returncode == 0, down.stderr

    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert not APP_TABLES.intersection(tables)


def test_upgrade_backfills_columns_on_a_pre_existing_database(tmp_path):
    """The critical upgrade path: a database that already had these tables *before* the
    whatsapp/business-hours/awaiting-customer columns existed must not break — 0001 skips
    the already-there tables (checkfirst=True) and 0002 must add exactly the missing columns.

    Simulated entirely via subprocesses (not by importing app.database in-process): the
    settings cache (`get_settings()` is `lru_cache`d) would otherwise keep binding to
    whatever DATABASE_URL this test process saw first, ignoring the tmp_path DB.
    """
    db_path = tmp_path / f"old_{uuid.uuid4().hex}.db"

    # 1. Get a fully-current, correctly-stamped database...
    first = _run_alembic("upgrade", "head", db_path=db_path)
    assert first.returncode == 0, first.stderr

    # 2. ...then roll it back to look like a database from before this migration setup
    #    existed: the Phase 1-3 columns are gone, and there's no alembic_version bookkeeping.
    conn = sqlite3.connect(db_path)
    for table, cols in _NEW_COLUMNS.items():
        for col in cols:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
    conn.execute("DROP TABLE alembic_version")
    conn.commit()
    for table, cols in _NEW_COLUMNS.items():
        assert not cols.intersection(_table_columns(db_path, table))
    conn.close()

    # 3. Upgrading this "old" database must backfill exactly the missing columns, not error.
    result = _run_alembic("upgrade", "head", db_path=db_path)
    assert result.returncode == 0, result.stderr

    for table, cols in _NEW_COLUMNS.items():
        assert cols.issubset(_table_columns(db_path, table)), f"{table} was not backfilled"

    conn = sqlite3.connect(db_path)
    version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    conn.close()
    assert version == "0009_closed_status"  # current head — bump this when adding a new migration
