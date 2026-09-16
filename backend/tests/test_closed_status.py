"""Coverage for customer-confirmed resolution ("Closed" status) and same-issue ticket reuse.

GEMINI_API_KEY is unset for the whole suite (see conftest.py), so every classification call
here exercises the rule-based fallback paths (gemini_service.rule_based_classification /
_rule_based_resolution_reply / _rule_based_same_issue) rather than a real Gemini call.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import ActivityLog, Organization, OrganizationSettings, Ticket
from app.services.ticket_service import (
    append_inbound_reply,
    auto_close_unconfirmed_resolved_tickets,
    find_reusable_open_ticket,
)
from tests.conftest import auth_headers, register_org, unique_slug


async def _make_org(slug_prefix: str, **settings_kwargs) -> Organization:
    async with AsyncSessionLocal() as db:
        org = Organization(name=f"{slug_prefix} Org", slug=unique_slug(slug_prefix))
        db.add(org)
        await db.flush()
        db.add(OrganizationSettings(org_id=org.id, **settings_kwargs))
        await db.commit()
        await db.refresh(org)
        return org


async def _make_ticket(org_id: str, **overrides) -> Ticket:
    async with AsyncSessionLocal() as db:
        defaults = dict(
            id=f"TKT-TEST-{unique_slug('t')}",
            org_id=org_id,
            customer_name="Test Customer",
            customer_email="repeat@example.com",
            subject="Refund not received for cancelled booking",
            ai_summary="Customer says a refund for a cancelled booking never arrived.",
            description="Refund not received",
            category="Support",
            status="Open",
            priority="High",
            channel="Email",
            confidence_score=0.9,
            urgency="High",
        )
        defaults.update(overrides)
        ticket = Ticket(**defaults)
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket


@pytest.mark.asyncio
async def test_confirming_reply_closes_a_resolved_ticket(client):
    org = await _make_org("confirm-close")
    ticket = await _make_ticket(org.id, status="Resolved", resolved_at=datetime.now(timezone.utc))

    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket.id)
        await append_inbound_reply(db, ticket, "Test Customer", "Thanks, this is all resolved now!")

    async with AsyncSessionLocal() as db:
        reloaded = await db.get(Ticket, ticket.id)
        assert reloaded.status == "Closed"
        assert reloaded.closed_at is not None

        logs = (await db.execute(select(ActivityLog).where(ActivityLog.ticket_id == ticket.id))).scalars().all()
        assert any("Closed" in log.action and "Confirmed" in log.action for log in logs)


@pytest.mark.asyncio
async def test_denying_reply_reopens_and_clears_resolved_at(client):
    org = await _make_org("deny-reopen")
    ticket = await _make_ticket(org.id, status="Resolved", resolved_at=datetime.now(timezone.utc))

    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket.id)
        await append_inbound_reply(db, ticket, "Test Customer", "This is still not fixed, same issue as before.")

    async with AsyncSessionLocal() as db:
        reloaded = await db.get(Ticket, ticket.id)
        assert reloaded.status == "Open"
        assert reloaded.resolved_at is None  # bug fix: resolved_at must not stay stamped after reopen


@pytest.mark.asyncio
async def test_ambiguous_reply_reopens_for_review_never_closes(client):
    org = await _make_org("ambiguous-reopen")
    ticket = await _make_ticket(org.id, status="Resolved", resolved_at=datetime.now(timezone.utc))

    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket.id)
        await append_inbound_reply(db, ticket, "Test Customer", "Also, do you support international shipping?")

    async with AsyncSessionLocal() as db:
        reloaded = await db.get(Ticket, ticket.id)
        assert reloaded.status == "Open"  # never silently closed on unclear input
        assert reloaded.resolved_at is None


@pytest.mark.asyncio
async def test_reply_to_escalated_ticket_reopens_unconditionally(client):
    org = await _make_org("escalated-reopen")
    ticket = await _make_ticket(org.id, status="Escalated", resolved_at=None)

    async with AsyncSessionLocal() as db:
        ticket = await db.get(Ticket, ticket.id)
        await append_inbound_reply(db, ticket, "Test Customer", "Any update?")

    async with AsyncSessionLocal() as db:
        reloaded = await db.get(Ticket, ticket.id)
        assert reloaded.status == "Open"


@pytest.mark.asyncio
async def test_find_reusable_open_ticket_matches_same_issue_by_email(client):
    org = await _make_org("reuse-email")
    ticket = await _make_ticket(
        org.id, customer_email="dupe@example.com", subject="Refund not received for cancelled booking",
        ai_summary="Refund for a cancelled booking never arrived.",
    )

    async with AsyncSessionLocal() as db:
        match = await find_reusable_open_ticket(
            db, org.id, "dupe@example.com", None,
            "Following up again — my refund for the cancelled booking still hasn't arrived.",
            api_key=None,
        )
        assert match is not None
        assert match.id == ticket.id


@pytest.mark.asyncio
async def test_find_reusable_open_ticket_ignores_closed_tickets(client):
    org = await _make_org("reuse-closed")
    await _make_ticket(
        org.id, customer_email="closed@example.com", status="Closed",
        subject="Refund not received for cancelled booking",
        ai_summary="Refund for a cancelled booking never arrived.",
    )

    async with AsyncSessionLocal() as db:
        match = await find_reusable_open_ticket(
            db, org.id, "closed@example.com", None,
            "Following up again — my refund for the cancelled booking still hasn't arrived.",
            api_key=None,
        )
        assert match is None


@pytest.mark.asyncio
async def test_find_reusable_open_ticket_returns_none_for_unrelated_message(client):
    org = await _make_org("reuse-unrelated")
    await _make_ticket(
        org.id, customer_email="other@example.com", subject="Refund not received for cancelled booking",
        ai_summary="Refund for a cancelled booking never arrived.",
    )

    async with AsyncSessionLocal() as db:
        match = await find_reusable_open_ticket(
            db, org.id, "other@example.com", None,
            "Completely different question about your park opening hours on weekends.",
            api_key=None,
        )
        assert match is None


@pytest.mark.asyncio
async def test_auto_close_unconfirmed_resolved_ticket_after_grace_period(client):
    org = await _make_org("auto-close", auto_close_after_days=3)
    old_resolved = datetime.now(timezone.utc) - timedelta(days=4)
    ticket = await _make_ticket(org.id, status="Resolved", resolved_at=old_resolved)

    async with AsyncSessionLocal() as db:
        count = await auto_close_unconfirmed_resolved_tickets(db)
        assert count >= 1

    async with AsyncSessionLocal() as db:
        reloaded = await db.get(Ticket, ticket.id)
        assert reloaded.status == "Closed"
        assert reloaded.closed_at is not None


@pytest.mark.asyncio
async def test_auto_close_skips_tickets_still_within_grace_period(client):
    org = await _make_org("auto-close-fresh", auto_close_after_days=3)
    recent_resolved = datetime.now(timezone.utc) - timedelta(hours=1)
    ticket = await _make_ticket(org.id, status="Resolved", resolved_at=recent_resolved)

    async with AsyncSessionLocal() as db:
        await auto_close_unconfirmed_resolved_tickets(db)

    async with AsyncSessionLocal() as db:
        reloaded = await db.get(Ticket, ticket.id)
        assert reloaded.status == "Resolved"  # too soon — still within the grace period


def test_only_org_admin_can_set_status_to_closed(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    resolver_email = f"resolver-{unique_slug('u')}@example.com"
    team_resp = client.post(
        "/api/team", json={"name": "Riya Resolver", "email": resolver_email, "role": "Resolver"}, headers=headers,
    )
    assert team_resp.status_code == 200, team_resp.text
    temp_password = team_resp.json()["temporaryPassword"]

    manual = client.post(
        "/api/tickets/manual",
        json={"customerName": "Someone", "customerMobile": "+911234567890", "message": "Refund not received"},
        headers=headers,
    )
    assert manual.status_code == 200, manual.text
    ticket_id = manual.json()["ticket"]["id"]

    login = client.post("/api/auth/login", json={"email": resolver_email, "password": temp_password})
    assert login.status_code == 200, login.text
    resolver_headers = auth_headers(login.json()["token"])

    denied = client.post(f"/api/tickets/{ticket_id}/status", json={"status": "Closed"}, headers=resolver_headers)
    assert denied.status_code == 403

    allowed = client.post(f"/api/tickets/{ticket_id}/status", json={"status": "Closed"}, headers=headers)
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()["ticket"]
    assert body["status"] == "Closed"
    assert body["closedAt"] is not None
