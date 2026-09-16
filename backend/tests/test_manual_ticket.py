"""Coverage for the Help Desk (phone call) manual ticket intake endpoint: an OrgAdmin fills in
what a caller told them, and it should run through the exact same classify/assign/SLA pipeline
as an emailed complaint — see app/routers/tickets.py::create_manual_ticket.
"""

from datetime import datetime, timedelta, timezone

from tests.conftest import auth_headers, register_org, unique_slug


def _parse(dt_str: str) -> datetime:
    """The test DB is SQLite, which doesn't round-trip tzinfo — normalize to aware UTC
    regardless of whether the serialized value came back with an offset or not."""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_manual_ticket_is_classified_assigned_and_tagged_phone_channel(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    resolver_email = f"resolver-{unique_slug('u')}@example.com"
    team_resp = client.post(
        "/api/team", json={"name": "Rahul Resolver", "email": resolver_email, "role": "Resolver"}, headers=headers,
    )
    assert team_resp.status_code == 200, team_resp.text
    resolver_id = team_resp.json()["member"]["id"]

    # Auto-assignment is off by default (tickets land unassigned for manual assignment) —
    # opt in here since this test specifically covers the round-robin assignment logic.
    settings_resp = client.put(
        "/api/organizations/me",
        json={
            "ticketPrefix": "TKT-2026-", "autoSendReceipt": True, "autoAssignResolver": True,
            "supportSlaHours": 48, "enquirySlaHours": 6, "reEscalationHours": 4,
            "smtpHost": "", "smtpPort": 465, "smtpUsername": "", "smtpPassword": "", "smtpFromEmail": "",
            "geminiApiKey": "", "whatsappPhoneNumberId": "", "whatsappAccessToken": "", "whatsappAppSecret": "",
            "businessHoursEnabled": False, "businessStartHour": 9, "businessEndHour": 18,
            "businessDays": "1,2,3,4,5", "timezone": "UTC", "holidayDates": "",
        },
        headers=headers,
    )
    assert settings_resp.status_code == 200, settings_resp.text

    resp = client.post(
        "/api/tickets/manual",
        json={
            "customerName": "Suresh Nair",
            "customerMobile": "+919876543210",
            "customerEmail": "suresh@example.com",
            "message": "Caller says he paid for a safari ticket but the money was deducted and he "
            "never got the confirmation. He wants a refund.",
            "externalReference": "RS-4821",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    ticket = resp.json()["ticket"]

    assert ticket["channel"] == "Phone"
    assert ticket["category"] == "Support"  # keyword fallback: "deducted", "refund"
    assert ticket["customerName"] == "Suresh Nair"
    assert ticket["externalReference"] == "RS-4821"
    assert ticket["assignedTo"] == resolver_id  # round-robin picked the only Resolver
    assert ticket["status"] == "Open"
    assert ticket["dueBy"] is not None
    assert ticket["id"].endswith("-1001")


def test_manual_ticket_can_be_backdated_to_when_the_call_happened(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    called_at = datetime.now(timezone.utc) - timedelta(hours=5)
    resp = client.post(
        "/api/tickets/manual",
        json={
            "customerName": "Late Logger",
            "customerMobile": "+919999999999",
            "message": "Logging a call from earlier today about a delayed refund",
            "occurredAt": called_at.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    ticket = resp.json()["ticket"]
    ticket_created = _parse(ticket["createdAt"])
    assert abs((ticket_created - called_at).total_seconds()) < 5

    # SLA due date must be computed from the backdated call time, not from "now" —
    # default SLA hours are 48 (Support) / 6 (Enquiry), business-hours calendar disabled.
    sla_hours = 48 if ticket["category"] == "Support" else 6
    due = _parse(ticket["dueBy"])
    expected_due = called_at + timedelta(hours=sla_hours)
    assert abs((due - expected_due).total_seconds()) < 5


def test_manual_ticket_future_occurred_at_is_clamped_to_now(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    future = datetime.now(timezone.utc) + timedelta(days=1)
    resp = client.post(
        "/api/tickets/manual",
        json={
            "customerName": "Time Traveler",
            "customerMobile": "+918888888888",
            "message": "Should not be allowed to backdate into the future",
            "occurredAt": future.isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    ticket_created = _parse(resp.json()["ticket"]["createdAt"])
    assert ticket_created <= datetime.now(timezone.utc)


def test_manual_ticket_requires_a_message(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    resp = client.post(
        "/api/tickets/manual",
        json={"customerName": "Anon Caller", "customerMobile": "+911234567890", "message": "   "},
        headers=headers,
    )
    assert resp.status_code == 400


def test_manual_ticket_is_org_admin_only(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    resolver_email = f"resolver-{unique_slug('u')}@example.com"
    team_resp = client.post(
        "/api/team", json={"name": "Riya Resolver", "email": resolver_email, "role": "Resolver"}, headers=headers,
    )
    assert team_resp.status_code == 200, team_resp.text
    temp_password = team_resp.json()["temporaryPassword"]

    login = client.post("/api/auth/login", json={"email": resolver_email, "password": temp_password})
    assert login.status_code == 200, login.text
    resolver_headers = auth_headers(login.json()["token"])

    resp = client.post(
        "/api/tickets/manual",
        json={"customerName": "Someone", "customerMobile": "+911234567890", "message": "issue"},
        headers=resolver_headers,
    )
    assert resp.status_code == 403


def test_manual_ticket_requires_auth(client):
    resp = client.post(
        "/api/tickets/manual",
        json={"customerName": "Someone", "customerMobile": "+911234567890", "message": "issue"},
    )
    assert resp.status_code == 401
