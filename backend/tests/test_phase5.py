"""Phase 5: workload-aware routing, low-confidence review flag, suggested replies,
and the public complaint-tracking endpoint.
"""

from tests.conftest import auth_headers, register_org, unique_slug


def test_low_confidence_classification_is_flagged_for_review(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    # Directly hit the internal webhook with an ambiguous, keyword-free message so the
    # rule-based fallback classifier (GEMINI_API_KEY="" in tests) lands well under threshold.
    intake = client.post(
        "/api/webhook/intake",
        json={"message": "hey there just checking in", "customerEmail": "c@example.com"},
        headers=headers,
    )
    assert intake.status_code == 200, intake.text
    ticket = intake.json()["ticket"]
    assert ticket["confidenceScore"] < 0.6
    assert ticket["needsAttention"] is True
    assert any("Needs Review" in r or "Confidence" in r for r in ticket["attentionReasons"])


def test_workload_aware_routing_prefers_least_loaded_resolver(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    r1 = client.post("/api/team", json={"name": "Resolver A", "email": f"a-{unique_slug('u')}@example.com", "role": "Resolver"}, headers=headers).json()["member"]
    r2 = client.post("/api/team", json={"name": "Resolver B", "email": f"b-{unique_slug('u')}@example.com", "role": "Resolver"}, headers=headers).json()["member"]

    # First two tickets round-robin normally across the two empty resolvers.
    t1 = client.post("/api/webhook/intake", json={"message": "issue one", "customerEmail": "c1@example.com"}, headers=headers).json()["ticket"]
    t2 = client.post("/api/webhook/intake", json={"message": "issue two", "customerEmail": "c2@example.com"}, headers=headers).json()["ticket"]
    assert {t1["assignedTo"], t2["assignedTo"]} == {r1["id"], r2["id"]}

    # Resolve whichever resolver got t1, so they now have 0 open tickets vs the other's 1.
    resolved_resolver_id = t1["assignedTo"]
    client.post(f"/api/tickets/{t1['id']}/status", json={"status": "Resolved"}, headers=headers)

    # The next ticket must go to the resolver with fewer open tickets, not "whoever is next".
    t3 = client.post("/api/webhook/intake", json={"message": "issue three", "customerEmail": "c3@example.com"}, headers=headers).json()["ticket"]
    assert t3["assignedTo"] == resolved_resolver_id


def test_suggest_reply_returns_a_usable_fallback_draft(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post("/api/webhook/intake", json={"message": "Refund not processed for order 4471", "customerEmail": "c@example.com"}, headers=headers).json()
    ticket_id = intake["ticketNumber"]

    resp = client.post(f"/api/tickets/{ticket_id}/suggest-reply", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reply"].strip()
    assert "Fallback Template" in body["source"]  # no Gemini key in test env


def test_public_tracking_requires_matching_contact(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    intake = client.post(
        "/api/webhook/intake",
        json={"message": "Ticket not received after payment", "customerEmail": "public-track@example.com", "customerMobile": "+919876543210"},
        headers=headers,
    ).json()
    ticket_id = intake["ticketNumber"]

    # Right ID, wrong contact -> 404 (never leaks which part was wrong).
    wrong = client.post("/api/public/track", json={"ticketId": ticket_id, "contact": "someone-else@example.com"})
    assert wrong.status_code == 404

    # Right ID, right email -> full status.
    ok = client.post("/api/public/track", json={"ticketId": ticket_id, "contact": "Public-Track@example.com"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["id"] == ticket_id
    assert body["status"] == "Open"
    assert "description" not in body  # internal field must not leak to the public view

    # Right ID, right mobile in a different format -> still matches (last-10-digits compare).
    ok2 = client.post("/api/public/track", json={"ticketId": ticket_id, "contact": "09876543210"})
    assert ok2.status_code == 200, ok2.text


def test_public_tracking_unknown_ticket_id_404s(client):
    resp = client.post("/api/public/track", json={"ticketId": "NOPE-2026-9999", "contact": "x@example.com"})
    assert resp.status_code == 404
