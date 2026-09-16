from app.services.leader_lock import _lock_key


def test_lock_key_is_deterministic():
    assert _lock_key("poll_mailboxes") == _lock_key("poll_mailboxes")


def test_lock_key_differs_per_job_name():
    assert _lock_key("poll_mailboxes") != _lock_key("escalate_overdue")


def test_lock_key_fits_signed_64bit_range():
    key = _lock_key("some_job_name")
    assert -(2**63) <= key < 2**63


def test_leader_only_is_noop_passthrough_on_sqlite(client):
    """On the test suite's SQLite backend (and any non-Postgres dialect), leader_only must
    never block a job — there's no multi-replica concern to guard against there."""
    import asyncio

    from app.database import AsyncSessionLocal
    from app.services.leader_lock import leader_only

    async def _check():
        async with AsyncSessionLocal() as db:
            async with leader_only(db, "test_job") as acquired:
                assert acquired is True

    asyncio.run(_check())
