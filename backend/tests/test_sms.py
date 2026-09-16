"""Coverage for the SMS notification channel: org settings plumbing (save/load/don't-wipe-on-
unrelated-save), the /api/sms/send-test endpoint, and the ack/resolution triggers actually
dispatching through sms_service when configured — mirroring how WhatsApp is tested implicitly
elsewhere via the shared _send_ack_and_assignment_notifications/resolve_ticket pipeline.
"""

import json

from tests.conftest import auth_headers, register_org


def _full_settings_payload(**overrides):
    """A complete OrganizationSettingsUpdate payload (the API expects the full form on every
    save) with sensible defaults, so tests only need to specify what they're changing."""
    base = {
        "ticketPrefix": "TKT-2026-",
        "autoSendReceipt": True,
        "supportSlaHours": 48,
        "enquirySlaHours": 6,
        "reEscalationHours": 4,
        "smtpHost": "", "smtpPort": 465, "smtpUsername": "", "smtpPassword": "", "smtpFromEmail": "",
        "geminiApiKey": "",
        "whatsappPhoneNumberId": "", "whatsappAccessToken": "", "whatsappAppSecret": "",
        "businessHoursEnabled": False, "businessStartHour": 9, "businessEndHour": 18,
        "businessDays": "1,2,3,4,5", "timezone": "UTC", "holidayDates": "",
    }
    base.update(overrides)
    return base


def test_sms_settings_save_and_load(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    resp = client.put(
        "/api/organizations/me",
        json=_full_settings_payload(
            smsProvider="Acme SMS", smsApiUrl="https://sms.example.com/send", smsSenderId="GRVDSK", smsApiKey="secret-key-123",
        ),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["smsProvider"] == "Acme SMS"
    assert settings["smsApiUrl"] == "https://sms.example.com/send"
    assert settings["smsSenderId"] == "GRVDSK"
    assert settings["hasSmsApiKey"] is True

    got = client.get("/api/organizations/me", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["settings"]["smsProvider"] == "Acme SMS"


def test_unrelated_settings_save_does_not_wipe_sms_config(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    client.put(
        "/api/organizations/me",
        json=_full_settings_payload(smsProvider="Acme SMS", smsApiUrl="https://sms.example.com/send", smsSenderId="GRVDSK", smsApiKey="secret-key-123"),
        headers=headers,
    )

    # A save that only touches SLA hours and omits the sms* fields (as a real "Org Settings"
    # tab save would, since it doesn't own the SMS channel fields) must not blank them out.
    resp = client.put("/api/organizations/me", json=_full_settings_payload(supportSlaHours=72), headers=headers)
    assert resp.status_code == 200, resp.text
    settings = resp.json()["settings"]
    assert settings["supportSlaHours"] == 72
    assert settings["smsProvider"] == "Acme SMS"
    assert settings["smsApiUrl"] == "https://sms.example.com/send"
    assert settings["hasSmsApiKey"] is True  # blank smsApiKey in this save must not clear it


def test_sms_send_test_when_not_configured(client):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    resp = client.post("/api/sms/send-test", json={"toMobile": "+911234567890"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is False
    assert "not configured" in body["message"].lower()


def test_sms_send_test_when_configured(client, monkeypatch):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    client.put(
        "/api/organizations/me",
        json=_full_settings_payload(smsProvider="Acme SMS", smsApiUrl="https://sms.example.com/send", smsSenderId="GRVDSK", smsApiKey="secret-key-123"),
        headers=headers,
    )

    class _FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return json.dumps({"messageId": "fake-123"}).encode("utf-8")

    def _fake_urlopen(req, timeout=20):
        assert req.full_url == "https://sms.example.com/send"
        return _FakeResponse()

    monkeypatch.setattr("app.services.sms_service.urllib.request.urlopen", _fake_urlopen)

    resp = client.post("/api/sms/send-test", json={"toMobile": "+911234567890"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["messageId"] == "fake-123"


def test_manual_ticket_sends_sms_ack_when_configured(client, monkeypatch):
    reg = register_org(client)
    headers = auth_headers(reg["token"])

    client.put(
        "/api/organizations/me",
        json=_full_settings_payload(smsProvider="Acme SMS", smsApiUrl="https://sms.example.com/send", smsSenderId="GRVDSK", smsApiKey="secret-key-123"),
        headers=headers,
    )

    class _FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return json.dumps({"messageId": "ack-1"}).encode("utf-8")

    monkeypatch.setattr("app.services.sms_service.urllib.request.urlopen", lambda req, timeout=20: _FakeResponse())

    resp = client.post(
        "/api/tickets/manual",
        json={"customerName": "Ravi Kumar", "customerMobile": "+919876543210", "message": "Refund not received for cancelled booking"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    ticket = resp.json()["ticket"]
    assert any(log["action"] == "SMS Acknowledgement Sent" for log in ticket["activityLogs"])
    # Brand name defaults to the org's own name (no Sender Display Name configured in this test).
    org_name = reg["user"]["orgName"]
    assert any(org_name in r["text"] for r in ticket["replies"] if r["sender"] == "AI Auto-Receipt Sentinel")
