"""Retry queue for notification sends that failed for a transient reason (network blip,
SMTP timeout, Meta API hiccup — see the `retryable` flag on smtp_service.send_email /
whatsapp_service.send_text results). A "not configured" failure is never queued here since
retrying it can't possibly succeed without an admin fixing the configuration first.

Exponential backoff, capped attempts. Polled by the scheduler alongside the SLA check — no
new infrastructure (no Redis/Celery) needed, consistent with the rest of this project.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ActivityLog, FailedNotification, Organization, OrganizationSettings
from . import sms_service, smtp_service, whatsapp_service

logger = logging.getLogger("grievance_desk.notification_retry")

# Minutes until the next attempt, indexed by (attempts_so_far - 1); last value repeats for
# any further attempts beyond the list length.
_BACKOFF_MINUTES = [2, 5, 15, 60, 240]


def _next_attempt_at(attempts: int) -> datetime:
    idx = min(max(attempts, 1) - 1, len(_BACKOFF_MINUTES) - 1)
    return datetime.now(timezone.utc) + timedelta(minutes=_BACKOFF_MINUTES[idx])


async def record_failure(
    db: AsyncSession, org_id: str, channel: str, to_address: str, subject: str, body: str,
    error: str, ticket_id: str | None = None,
) -> None:
    """Called right after an inline send fails with `retryable: True` — queues a background
    retry instead of letting that one attempt be the only chance the notification ever gets."""
    db.add(
        FailedNotification(
            org_id=org_id, ticket_id=ticket_id, channel=channel, to_address=to_address,
            subject=subject, body=body, attempts=1, last_error=(error or "")[:990],
            next_attempt_at=_next_attempt_at(1),
        )
    )
    await db.commit()


async def retry_pending(db: AsyncSession) -> dict:
    """Scheduler job: attempts every due, unresolved queued notification once. Delivered ->
    resolved+delivered. Still failing and out of retries (or now non-retryable) -> resolved
    (gives up) with a ticket-visible log entry. Otherwise -> backs off and tries again later.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(FailedNotification).where(
            FailedNotification.resolved.is_(False), FailedNotification.next_attempt_at <= now,
        )
    )
    pending = result.scalars().all()
    if not pending:
        return {"attempted": 0, "delivered": 0, "gave_up": 0}

    settings_cache: dict[str, OrganizationSettings] = {}
    brand_cache: dict[str, str] = {}

    async def _org_settings(org_id: str) -> OrganizationSettings:
        if org_id not in settings_cache:
            from .ticket_service import get_org_settings  # local import: avoids a circular import at module load
            settings_cache[org_id] = await get_org_settings(db, org_id)
        return settings_cache[org_id]

    async def _brand_name(org_id: str, org_settings: OrganizationSettings) -> str:
        if org_id not in brand_cache:
            from .ticket_service import resolve_brand_name  # local import: avoids a circular import at module load
            org = await db.get(Organization, org_id)
            brand_cache[org_id] = resolve_brand_name(org, org_settings)
        return brand_cache[org_id]

    delivered = gave_up = 0

    for fn in pending:
        org_settings = await _org_settings(fn.org_id)

        if fn.channel == "email":
            cfg = smtp_service.from_org_settings(org_settings)
            brand_name = await _brand_name(fn.org_id, org_settings)
            send_result = (
                await run_in_threadpool(smtp_service.send_email, cfg, fn.to_address, fn.subject, fn.body, brand_name)
                if cfg.configured else {"success": False, "retryable": False, "message": "No longer configured."}
            )
        elif fn.channel == "sms":
            cfg = sms_service.from_org_settings(org_settings)
            send_result = (
                await run_in_threadpool(sms_service.send_text, cfg, fn.to_address, fn.body)
                if cfg.configured else {"success": False, "retryable": False, "message": "No longer configured."}
            )
        else:
            cfg = whatsapp_service.from_org_settings(org_settings)
            send_result = (
                await run_in_threadpool(whatsapp_service.send_text, cfg, fn.to_address, fn.body)
                if cfg.configured else {"success": False, "retryable": False, "message": "No longer configured."}
            )

        if send_result.get("success"):
            fn.resolved = True
            fn.delivered = True
            db.add(fn)
            if fn.ticket_id:
                db.add(
                    ActivityLog(
                        ticket_id=fn.ticket_id, actor="Notification Retry Sentinel",
                        action=f"{fn.channel.title()} Delivered on Retry",
                        details=f"Succeeded on attempt {fn.attempts + 1}, sent to {fn.to_address}.",
                    )
                )
            delivered += 1
        else:
            fn.attempts += 1
            fn.last_error = (send_result.get("message") or "")[:990]
            out_of_retries = fn.attempts >= fn.max_attempts or not send_result.get("retryable", True)
            if out_of_retries:
                fn.resolved = True
                if fn.ticket_id:
                    db.add(
                        ActivityLog(
                            ticket_id=fn.ticket_id, actor="Notification Retry Sentinel",
                            action=f"{fn.channel.title()} Notification Failed Permanently",
                            details=f"Gave up after {fn.attempts} attempt(s): {fn.last_error}",
                        )
                    )
                gave_up += 1
            else:
                fn.next_attempt_at = _next_attempt_at(fn.attempts)
            db.add(fn)

        await db.commit()

    return {"attempted": len(pending), "delivered": delivered, "gave_up": gave_up}
