"""Background jobs: IMAP mailbox polling + SLA breach escalation.
Runs in-process (APScheduler AsyncIOScheduler) — no extra infra beyond the
existing docker-compose services.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import get_settings
from .database import AsyncSessionLocal
from .services.email_ingest_service import poll_all_mailboxes
from .services.leader_lock import leader_only
from .services.notification_retry_service import retry_pending
from .services.ticket_service import auto_close_unconfirmed_resolved_tickets, check_sla_warnings, escalate_overdue_tickets

logger = logging.getLogger("grievance_desk.scheduler")
settings = get_settings()

scheduler = AsyncIOScheduler()


async def _job_poll_mailboxes() -> None:
    async with AsyncSessionLocal() as db:
        try:
            async with leader_only(db, "poll_mailboxes") as acquired:
                if not acquired:
                    return
                result = await poll_all_mailboxes(db)
                if result.get("created") or result.get("skipped"):
                    logger.info(
                        "Mailbox poll: %s ticket(s) created, %s auto-generated message(s) skipped, from %s mailbox(es).",
                        result["created"], result.get("skipped", 0), result["mailboxes"],
                    )
        except Exception:  # noqa: BLE001
            logger.exception("Mailbox polling job failed")


async def _job_escalate_overdue() -> None:
    async with AsyncSessionLocal() as db:
        try:
            async with leader_only(db, "escalate_overdue") as acquired:
                if not acquired:
                    return
                count = await escalate_overdue_tickets(db)
                if count:
                    logger.info("SLA sentinel: escalated %s overdue ticket(s).", count)

                warned = await check_sla_warnings(db)
                if warned:
                    logger.info("SLA sentinel: warned %s ticket assignee(s) approaching their SLA window.", warned)
        except Exception:  # noqa: BLE001
            logger.exception("SLA escalation/warning job failed")


async def _job_auto_close_resolved() -> None:
    async with AsyncSessionLocal() as db:
        try:
            async with leader_only(db, "auto_close_resolved") as acquired:
                if not acquired:
                    return
                count = await auto_close_unconfirmed_resolved_tickets(db)
                if count:
                    logger.info("Auto-close sentinel: closed %s unconfirmed Resolved ticket(s).", count)
        except Exception:  # noqa: BLE001
            logger.exception("Auto-close job failed")


async def _job_retry_notifications() -> None:
    async with AsyncSessionLocal() as db:
        try:
            async with leader_only(db, "retry_notifications") as acquired:
                if not acquired:
                    return
                result = await retry_pending(db)
                if result.get("attempted"):
                    logger.info(
                        "Notification retry: %s attempted, %s delivered, %s gave up.",
                        result["attempted"], result["delivered"], result["gave_up"],
                    )
        except Exception:  # noqa: BLE001
            logger.exception("Notification retry job failed")


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _job_poll_mailboxes, "interval", seconds=settings.imap_poll_interval_seconds,
        id="poll_mailboxes", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _job_escalate_overdue, "interval", seconds=settings.sla_check_interval_seconds,
        id="escalate_overdue", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _job_retry_notifications, "interval", seconds=settings.sla_check_interval_seconds,
        id="retry_notifications", max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _job_auto_close_resolved, "interval", seconds=settings.sla_check_interval_seconds,
        id="auto_close_resolved", max_instances=1, coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: mailbox poll every %ss, SLA check every %ss.",
        settings.imap_poll_interval_seconds, settings.sla_check_interval_seconds,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


