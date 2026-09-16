"""Outbound SMS — sends the acknowledgement/resolution notifications back to the
complainant's phone number, mirroring the WhatsApp/email lifecycle in `ticket_service.py`.

No specific SMS gateway has been picked yet, so this talks to a *generic* HTTP JSON API:
POST {api_url} with {"apiKey", "senderId", "to", "message"} and a Bearer Authorization
header carrying the API key. Once a real provider is chosen, only `send_text()`'s request
shape needs to change — everything else (config plumbing, org settings, retry queue,
ack/resolution triggers) is already wired up and provider-agnostic.

All network calls here are synchronous (urllib) — callers MUST wrap them with
`fastapi.concurrency.run_in_threadpool` so they don't block the event loop, same
convention as smtp_service.py / whatsapp_service.py.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger("grievance_desk.sms")


class SmsConfig:
    def __init__(self, provider: str, api_url: str, api_key: str, sender_id: str):
        self.provider = provider
        self.api_url = api_url
        self.api_key = api_key
        self.sender_id = sender_id

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key and self.sender_id)


def from_org_settings(org_settings: Any) -> SmsConfig:
    """Org SMS settings, falling back field-by-field to the platform .env SMS account."""
    return SmsConfig(
        provider=org_settings.sms_provider or settings.sms_provider,
        api_url=org_settings.sms_api_url or settings.sms_api_url,
        api_key=org_settings.sms_api_key or settings.sms_api_key,
        sender_id=org_settings.sms_sender_id or settings.sms_sender_id,
    )


def send_text(cfg: SmsConfig, to_mobile: str, body: str) -> dict:
    # `retryable` distinguishes "will never succeed until an admin fixes something" (missing
    # config, no recipient) from "might succeed on its own next time" (network blip, gateway
    # hiccup) — used by notification_retry_service to decide what's worth re-queuing.
    if not cfg.configured:
        return {
            "success": False, "retryable": False,
            "message": "SMS gateway is not configured for this organization; message was not sent.",
        }
    if not to_mobile:
        return {"success": False, "retryable": False, "message": "No mobile number on file."}

    payload = {
        "apiKey": cfg.api_key,
        "senderId": cfg.sender_id,
        "to": to_mobile,
        "message": body[:1600],  # generous cap; most gateways split long texts into segments themselves
    }
    req = urllib.request.Request(
        cfg.api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"raw": raw}
            message_id = data.get("messageId") or data.get("id")
            return {"success": True, "message": "SMS sent.", "messageId": message_id, "sentTo": to_mobile}
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            detail = str(exc)
        # 400/401/403/404 mean the request or credentials are wrong and won't fix themselves
        # (bad key, invalid recipient, wrong URL, ...); anything else (5xx, 429 rate-limit) is
        # worth retrying.
        retryable = exc.code not in (400, 401, 403, 404)
        return {"success": False, "retryable": retryable, "message": f"SMS gateway error ({exc.code}): {detail[:300]}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "retryable": True, "message": f"Failed to dispatch SMS: {exc}"}


# ---------- Message templates (kept short/plain — no markdown, unlike WhatsApp) ----------

def build_ack_message(ticket_number: str, customer_name: str, category: str, due_hours: int, brand_name: str) -> str:
    return (
        f"Hi {customer_name}, your {category.lower()} complaint has been registered. "
        f"Ticket ID: {ticket_number}. Expected resolution within {due_hours} hrs. - {brand_name}"
    )


def build_resolved_message(ticket_number: str, subject: str, brand_name: str) -> str:
    return (
        f"Your complaint {ticket_number} (\"{subject[:60]}\") has been marked Resolved. "
        f"Reply/reference {ticket_number} if this isn't fully sorted. - {brand_name}"
    )
