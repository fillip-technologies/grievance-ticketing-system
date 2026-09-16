"""End-to-end coverage of the exact pipeline described by the platform's spec:
register org -> complaint arrives -> AI classifies it -> Complaint ID generated ->
round-robin assigned -> status lifecycle -> escalation -> needs-attention surfacing.

Runs through the real FastAPI app (see conftest.client) against a throwaway SQLite DB.
"""

from tests.conftest import auth_headers, register_org, unique_slug


def test_register_org_and_login(client):
    reg = register_org(client)
    assert reg["user"]["role"] == "OrgAdmin"
    assert reg["token"]

    login = client.post(
        "/api/auth/login",
        json={"email": reg["user"]["email"], "password": "Sup3rSecret!Pass"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == reg["user"]["email"]


def test_portal_complaint_gets_classified_id_and_assigned(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    # A Resolver must exist for round-robin assignment to have somewhere to send it.
    resolver_email = f"resolver-{unique_slug('u')}@example.com"
    team_resp = client.post(
        "/api/team", json={"name": "Rahul Resolver", "email": resolver_email, "role": "Resolver"}, headers=headers,
    )
    assert team_resp.status_code == 200, team_resp.text
    resolver_id = team_resp.json()["member"]["id"]

    intake = client.post(
        "/api/webhook/intake",
        json={
            "message": "I paid for a jungle safari ticket but the money was deducted and I never received "
            "the ticket confirmation. This is urgent, please refund or resend it.",
            "customerName": "Anita Sharma",
            "customerMobile": "+919812345678",
            "customerEmail": "anita@example.com",
            "channel": "Portal",
        },
        headers=headers,
    )
    assert intake.status_code == 200, intake.text
    data = intake.json()

    assert data["category"] == "Support"  # keyword fallback: "deducted", "refund" trigger Support
    assert data["autoDispatched"] is True
    assert data["ticketNumber"].endswith("-1001")  # org-specific prefix, sequence starts at 1001
    assert data["ticket"]["assignedTo"] == resolver_id  # round-robin picked the only Resolver
    assert data["ticket"]["customerEmail"] == "anita@example.com"
    assert data["ticket"]["status"] == "Open"
    assert data["ticket"]["dueBy"] is not None


def test_enquiry_message_is_classified_as_enquiry(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post(
        "/api/webhook/intake",
        json={
            "message": "What are your park visiting hours and ticket pricing for a family of four?",
            "customerName": "Vikram Rao",
            "customerEmail": "vikram@example.com",
            "channel": "Portal",
        },
        headers=headers,
    )
    assert intake.status_code == 200, intake.text
    assert intake.json()["category"] == "Enquiry"


def test_ticket_numbers_are_sequential_per_org(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    ids = []
    for i in range(3):
        resp = client.post(
            "/api/webhook/intake",
            json={"message": f"Issue number {i}: my payment failed", "customerEmail": f"c{i}@example.com"},
            headers=headers,
        )
        ids.append(resp.json()["ticketNumber"])

    assert len(set(ids)) == 3  # all unique
    seqs = [int(t.rsplit("-", 1)[-1]) for t in ids]
    assert seqs == sorted(seqs)  # strictly increasing
    assert seqs[1] == seqs[0] + 1
    assert seqs[2] == seqs[1] + 1


def test_external_webhook_intake_matches_google_form_use_case(client):
    """Mirrors the exact real-world scenario: a Google Form's 'new submission' notification
    is turned into a POST against the org's public webhook, with no JWT — the same call an
    Apps Script onFormSubmit trigger makes."""
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    org_resp = client.get("/api/organizations/me", headers=headers)
    assert org_resp.status_code == 200
    api_key = org_resp.json()["webhookApiKey"]

    resp = client.post(
        f"/api/webhook/external/{api_key}/intake",
        json={
            "message": "Name: Deepak Kumar\nEmail: deepak@example.com\nIssue: paid via UPI but did not "
            "get the safari e-ticket, ref TXN99213.",
            "customerName": "Deepak Kumar",
            "customerEmail": "deepak@example.com",
            "channel": "Webhook API",
        },
        # no Authorization header — this endpoint is authenticated purely by the api_key in the URL
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ticket"]["customerName"] == "Deepak Kumar"

    # An invalid key must be rejected.
    bad = client.post(f"/api/webhook/external/not-a-real-key/intake", json={"message": "hi"})
    assert bad.status_code == 401


def test_status_lifecycle_resolved(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post(
        "/api/webhook/intake", json={"message": "Refund not received for cancelled booking", "customerEmail": "r@example.com"}, headers=headers,
    )
    ticket_id = intake.json()["ticketNumber"]

    resolved = client.post(f"/api/tickets/{ticket_id}/status", json={"status": "Resolved"}, headers=headers)
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()["ticket"]
    assert body["status"] == "Resolved"
    assert body["resolvedAt"] is not None


def test_manual_escalation_without_authority_flags_needs_attention(client):
    """No EscalationAuthority is configured for this fresh org — escalating should not
    silently vanish; it must show up as needing OrgAdmin attention."""
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post(
        "/api/webhook/intake", json={"message": "System outage, nothing works", "customerEmail": "e@example.com"}, headers=headers,
    )
    ticket_id = intake.json()["ticketNumber"]

    escalated = client.post(f"/api/tickets/{ticket_id}/status", json={"status": "Escalated"}, headers=headers)
    assert escalated.status_code == 200, escalated.text
    body = escalated.json()["ticket"]
    assert body["status"] == "Escalated"
    assert body["escalationLevel"] == 1
    assert body["needsAttention"] is True
    assert any("Escalation Authority" in r for r in body["attentionReasons"])

    listing = client.get("/api/tickets", params={"needsAttention": "true"}, headers=headers)
    assert any(t["id"] == ticket_id for t in listing.json()["tickets"])


def test_missing_contact_email_flags_needs_attention(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post(
        "/api/webhook/intake",
        json={"message": "Payment issue with no way to reach me by email", "customerMobile": "+911234567890"},
        headers=headers,
    )
    assert intake.status_code == 200, intake.text
    ticket = intake.json()["ticket"]
    assert ticket["customerEmail"] is None
    assert ticket["needsAttention"] is True
    assert any("contact email" in r.lower() for r in ticket["attentionReasons"])


def test_awaiting_customer_pauses_and_resumes_sla_clock(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post(
        "/api/webhook/intake", json={"message": "Need more info before we can proceed", "customerEmail": "w@example.com"}, headers=headers,
    )
    ticket_id = intake.json()["ticketNumber"]
    original_due = intake.json()["ticket"]["dueBy"]

    paused = client.post(f"/api/tickets/{ticket_id}/awaiting-customer", json={"awaiting": True}, headers=headers)
    assert paused.status_code == 200, paused.text
    assert paused.json()["ticket"]["awaitingCustomer"] is True

    resumed = client.post(f"/api/tickets/{ticket_id}/awaiting-customer", json={"awaiting": False}, headers=headers)
    assert resumed.status_code == 200, resumed.text
    body = resumed.json()["ticket"]
    assert body["awaitingCustomer"] is False
    # due date should have been pushed forward (>=) by however long it was paused, never pulled back
    assert body["dueBy"] >= original_due


def test_unauthenticated_requests_are_rejected(client):
    resp = client.get("/api/tickets")
    assert resp.status_code == 401
