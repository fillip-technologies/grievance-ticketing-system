"""Outbound WhatsApp Business Cloud API (Meta) — sends the registered/resolved/escalated
notifications back to WhatsApp complainants, mirroring the SMTP email lifecycle in
`ticket_service.py`. Also verifies inbound webhook signatures.

All network calls here are synchronous (urllib) — callers MUST wrap them with
`fastapi.concurrency.run_in_threadpool` so they don't block the event loop, same
convention as smtp_service.py.
"""

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("grievance_desk.whatsapp")


class WhatsAppConfig:
    def __init__(self, phone_number_id: str, access_token: str, app_secret: str = "", api_version: str = "v20.0"):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.app_secret = app_secret
        self.api_version = api_version or "v20.0"

    @property
    def configured(self) -> bool:
        return bool(self.phone_number_id and self.access_token)


def from_org_settings(org_settings: Any) -> WhatsAppConfig:
    """Org WhatsApp settings, falling back field-by-field to the platform .env account."""
    return WhatsAppConfig(
        phone_number_id=org_settings.whatsapp_phone_number_id or settings.whatsapp_phone_number_id,
        access_token=org_settings.whatsapp_access_token or settings.whatsapp_access_token,
        app_secret=org_settings.whatsapp_app_secret or settings.whatsapp_app_secret,
        api_version=settings.whatsapp_api_version,
    )


def _normalize_recipient(mobile: str) -> str:
    """Meta's Cloud API wants digits only (no '+', spaces, or punctuation)."""
    return "".join(ch for ch in (mobile or "") if ch.isdigit())


def send_text(cfg: WhatsAppConfig, to_mobile: str, body: str) -> dict:
    # `retryable` distinguishes "will never succeed until an admin fixes something" (missing
    # config, no recipient) from "might succeed on its own next time" (network blip, Meta API
    # hiccup) — used by notification_retry_service to decide what's worth re-queuing.
    if not cfg.configured:
        return {
            "success": False, "retryable": False,
            "message": "WhatsApp Business API is not configured for this organization; message was not sent.",
        }
    to = _normalize_recipient(to_mobile)
    if not to:
        return {"success": False, "retryable": False, "message": "No valid WhatsApp mobile number on file."}

    url = f"https://graph.facebook.com/{cfg.api_version}/{cfg.phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg.access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            message_id = ((data.get("messages") or [{}])[0]).get("id")
            return {"success": True, "message": "WhatsApp message sent.", "messageId": message_id, "sentTo": to}
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
            detail = (err_body.get("error") or {}).get("message") or str(exc)
        except Exception:  # noqa: BLE001
            detail = str(exc)
        # 400/401/403/404 mean the request or credentials are wrong and won't fix themselves
        # (bad token, invalid recipient, ...); anything else (5xx, 429 rate-limit) is worth retrying.
        retryable = exc.code not in (400, 401, 403, 404)
        return {"success": False, "retryable": retryable, "message": f"WhatsApp API error ({exc.code}): {detail}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "retryable": True, "message": f"Failed to dispatch WhatsApp message: {exc}"}


def verify_signature(app_secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    """Verifies Meta's X-Hub-Signature-256 header (HMAC-SHA256 of the raw request body,
    keyed with the Meta App Secret). Returns True if no secret is configured yet, since
    that's the "not set up" state rather than a tamper attempt — callers should surface
    that distinction separately (see ai.py) rather than silently accepting forever."""
    if not app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, provided)


# ---------- Message templates (plain text — Cloud API "text" message type) ----------

def build_ack_message(
    ticket_number: str, customer_name: str, category: str, urgency: str, summary: str, due_hours: int, brand_name: str,
) -> str:
    return (
        f"{brand_name}\n\n"
        f"Hello {customer_name},\n"
        f"Your message has been registered as complaint *{ticket_number}*.\n\n"
        f"Category: {category}\n"
        f"Urgency: {urgency}\n"
        f"Summary: {(summary or '')[:100]}\n"
        f"Expected resolution: within {due_hours} hours\n\n"
        "An assigned agent will follow up. Thank you for contacting us!"
    )


def build_resolved_message(ticket_number: str, customer_name: str, subject: str, auto_close_days: int | None = None) -> str:
    grace_note = (
        f"\n\nIf this resolves your issue, no action is needed — we'll automatically close it in "
        f"{auto_close_days} day{'s' if auto_close_days != 1 else ''} if we don't hear back."
        if auto_close_days
        else ""
    )
    return (
        f"Hello {customer_name},\n\n"
        f"Good news — your complaint *{ticket_number}* (\"{subject}\") has been marked *Resolved* by our team."
        f"{grace_note}\n\n"
        f"If it's not fixed, just reply here or reference {ticket_number} and we'll reopen it."
    )


def build_closed_message(ticket_number: str, customer_name: str, subject: str, reason: str) -> str:
    """Short closing acknowledgement, reused for all three closing paths (customer-confirmed,
    auto-closed, admin-closed) — mirrors smtp_service.build_closed_email."""
    return (
        f"Hello {customer_name},\n\n"
        f"Your complaint *{ticket_number}* (\"{subject}\") has now been *Closed*, since {reason}.\n\n"
        f"If you need anything further, just reply here referencing {ticket_number} and we'll take another look."
    )


def build_escalated_message(ticket_number: str, customer_name: str, subject: str, authority_assigned: bool) -> str:
    if authority_assigned:
        return (
            f"Hello {customer_name},\n\n"
            f"Your complaint *{ticket_number}* (\"{subject}\") has passed our target resolution window and has "
            "been escalated to a senior authority on our team for immediate attention.\n\n"
            "We apologize for the delay — you'll get another update as soon as it's resolved."
        )
    return (
        f"Hello {customer_name},\n\n"
        f"Your complaint *{ticket_number}* (\"{subject}\") is taking longer than expected. It has been flagged "
        "internally for priority follow-up.\n\n"
        "We apologize for the delay — you'll get another update as soon as it's resolved."
    )
