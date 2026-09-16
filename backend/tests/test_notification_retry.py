"""Retry queue for transient send failures."""

from datetime import datetime, timedelta, timezone

import pytest

from app.database import AsyncSessionLocal
from app.models import ActivityLog, FailedNotification, Organization, OrganizationSettings, Ticket
from app.services import notification_retry_service


@pytest.mark.asyncio
async def test_record_failure_queues_a_row(client):
    async with AsyncSessionLocal() as db:
        org = Organization(name="Retry Test Org", slug="retry-test-org-1")
        db.add(org)
        await db.flush()
        db.add(OrganizationSettings(org_id=org.id))
        await db.commit()

        await notification_retry_service.record_failure(
            db, org.id, "email", "customer@example.com", "Subject", "Body", "SMTP timeout",
        )

        from sqlalchemy import select
        result = await db.execute(select(FailedNotification).where(FailedNotification.org_id == org.id))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].attempts == 1
        assert rows[0].resolved is False
        # SQLite (this test's backend) reads DateTime(timezone=True) back as naive, unlike
        # Postgres — compare naive-to-naive rather than assume tz-awareness round-trips.
        stored = rows[0].next_attempt_at
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert (stored.replace(tzinfo=None) if stored.tzinfo else stored) > now_naive


@pytest.mark.asyncio
async def test_retry_pending_skips_notifications_not_yet_due(client):
    async with AsyncSessionLocal() as db:
        org = Organization(name="Retry Test Org 2", slug="retry-test-org-2")
        db.add(org)
        await db.flush()
        db.add(OrganizationSettings(org_id=org.id))
        await db.commit()

        db.add(
            FailedNotification(
                org_id=org.id, channel="email", to_address="c@example.com", subject="s", body="b",
                attempts=1, last_error="x", next_attempt_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        await db.commit()

        result = await notification_retry_service.retry_pending(db)
        assert result == {"attempted": 0, "delivered": 0, "gave_up": 0}


@pytest.mark.asyncio
async def test_retry_pending_gives_up_when_smtp_stays_unconfigured(client):
    """SMTP is unconfigured throughout the test suite (SMTP_HOST=""), so a due retry must
    resolve as a permanent give-up rather than loop forever."""
    async with AsyncSessionLocal() as db:
        org = Organization(name="Retry Test Org 3", slug="retry-test-org-3")
        db.add(org)
        await db.flush()
        settings_row = OrganizationSettings(org_id=org.id)
        db.add(settings_row)
        await db.flush()
        ticket = Ticket(
            id=f"RETRY-{org.id[:8]}-1001", org_id=org.id, customer_name="X", customer_email="c@example.com",
            subject="s", description="d", category="Support", status="Open", priority="High",
            channel="Portal", confidence_score=0.9, urgency="High",
        )
        db.add(ticket)
        await db.commit()

        db.add(
            FailedNotification(
                org_id=org.id, ticket_id=ticket.id, channel="email", to_address="c@example.com",
                subject="s", body="b", attempts=1, last_error="x",
                next_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # already due
            )
        )
        await db.commit()

        result = await notification_retry_service.retry_pending(db)
        assert result["attempted"] == 1
        assert result["delivered"] == 0
        assert result["gave_up"] == 1  # "not configured" is non-retryable -> gives up immediately

        from sqlalchemy import select
        logs = (await db.execute(select(ActivityLog).where(ActivityLog.ticket_id == ticket.id))).scalars().all()
        assert any("Failed Permanently" in log.action for log in logs)
