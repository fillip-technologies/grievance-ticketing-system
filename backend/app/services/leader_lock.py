"""Advisory-lock guard so background jobs (mailbox polling, SLA escalation) run on only
one backend replica at a time. APScheduler is in-process with no leader election of its
own — run 2+ backend containers and, without this, every IMAP poll and every SLA
escalation/warning email fires once per replica, duplicating customer-facing emails.

Uses Postgres session-level advisory locks (`pg_try_advisory_lock`), which are held for
the lifetime of the DB connection and auto-released if it drops — no separate expiry or
cleanup logic needed. On non-Postgres dialects (SQLite, used only by the test suite / a
Postgres-less local dev setup) this is a no-op passthrough, since those setups are
inherently single-process anyway.
"""

import hashlib
import logging
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("grievance_desk.leader_lock")


def _lock_key(name: str) -> int:
    """Deterministic key for pg_advisory_lock (bigint / signed 64-bit) from a job name."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=True) % (2**62)


@asynccontextmanager
async def leader_only(db: AsyncSession, job_name: str):
    """`async with leader_only(db, "job_name") as acquired:` — only proceed with the job
    body if `acquired` is True. On Postgres, at most one replica gets True per cycle; on
    everything else, always True."""
    dialect_name = db.bind.dialect.name if db.bind is not None else ""
    if dialect_name != "postgresql":
        yield True
        return

    key = _lock_key(job_name)
    result = await db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
    acquired = bool(result.scalar())
    if not acquired:
        logger.debug("Skipping %r this cycle — another replica holds the lock.", job_name)
    try:
        yield acquired
    finally:
        if acquired:
            await db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
