"""Core complaint-lifecycle orchestration: ticket numbering, round-robin resolver
assignment, and every lifecycle email (acknowledgement -> assignment -> resolved /
escalated). Used by the webhook/whatsapp/email-ingest intake paths and by the
SLA scheduler.
"""

from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import ActivityLog, Mailbox, Organization, OrganizationSettings, Section, Ticket, TicketReply, User
from . import gemini_service, notification_retry_service, sla_calendar, sms_service, smtp_service, whatsapp_service

# Below this, the AI classifier itself is telling us it's unsure — the ticket still gets
# created and routed normally (never blocking intake), but is flagged for a human to
# double-check the category/urgency instead of trusting a coin-flip classification.
LOW_CONFIDENCE_THRESHOLD = 0.6

# A same-issue verdict below this confidence is treated as "probably a different issue" —
# reusing the wrong ticket (merging two unrelated complaints) is worse than occasionally
# creating a duplicate, so this leans conservative. See find_reusable_open_ticket.
SAME_ISSUE_CONFIDENCE_THRESHOLD = 0.55

# How many of the customer's most recent non-Closed tickets are checked as reuse candidates.
REUSE_CANDIDATE_LIMIT = 5


def resolve_brand_name(org: Organization, org_settings: OrganizationSettings) -> str:
    """The name shown as the email From display name and in WhatsApp/SMS message text.
    An org can set its own (Org Settings -> Sender Display Name); otherwise falls back to
    the organization's own registered name instead of a hardcoded platform brand."""
    return (org_settings.sender_display_name or "").strip() or org.name


async def get_active_sections(db: AsyncSession, org_id: str) -> list[Section]:
    """Active admin-defined routing sections for this org, fed to the AI classifier so it can
    match an inbound message against them (see gemini_service._build_classify_prompt /
    _match_section) in addition to the built-in Support/Enquiry categorization."""
    result = await db.execute(
        select(Section).where(Section.org_id == org_id, Section.is_active.is_(True)).order_by(Section.created_at)
    )
    return list(result.scalars().all())


def sections_payload(sections: list[Section]) -> list[dict]:
    """Shape expected by gemini_service's classify_intent/process_email_message/
    process_whatsapp_message `sections` argument."""
    return [{"name": s.name, "description": s.description} for s in sections]


async def resolve_section(db: AsyncSession, org_id: str, name: str | None) -> Section | None:
    """Looks up an active section by the (already-normalized, classifier-provided) name. A
    section the classifier wasn't offered, or that's since been deactivated/renamed, resolves
    to None rather than erroring — the ticket just falls back to the general pool."""
    if not name:
        return None
    result = await db.execute(
        select(Section).where(Section.org_id == org_id, Section.is_active.is_(True), Section.name == name)
    )
    return result.scalar_one_or_none()


async def get_org_settings(db: AsyncSession, org_id: str) -> OrganizationSettings:
    result = await db.execute(select(OrganizationSettings).where(OrganizationSettings.org_id == org_id))
    org_settings = result.scalar_one_or_none()
    if org_settings is None:
        org_settings = OrganizationSettings(org_id=org_id)
        db.add(org_settings)
        await db.commit()
        await db.refresh(org_settings)
    return org_settings


async def next_ticket_number(db: AsyncSession, org_settings: OrganizationSettings) -> str:
    """Collision-free, per-organization sequential complaint ID.

    Takes a row-level lock (SELECT ... FOR UPDATE) on the org's settings row before
    reading/incrementing next_ticket_seq, so two concurrent intakes (e.g. an IMAP poll
    and a webhook hit landing at the same instant) can never be handed the same number.
    The lock is released at the next commit; callers must commit soon after calling this.

    `Ticket.id` (which this number becomes) is a *global* primary key, not scoped per
    org — and `ticket_prefix` defaults identically ("TKT-2026-") for every new org, so
    without this check the second organization to ever register would collide with the
    first org's ticket #1001 on its very first complaint. This re-checks global
    uniqueness and skips forward past any collision, so a shared/duplicate prefix
    (whether from the shared default or an OrgAdmin manually setting one) degrades to
    "some numbers get skipped" instead of a hard failure.
    """
    locked = (
        await db.execute(
            select(OrganizationSettings).where(OrganizationSettings.id == org_settings.id).with_for_update()
        )
    ).scalar_one()

    while True:
        number = f"{locked.ticket_prefix}{locked.next_ticket_seq}"
        locked.next_ticket_seq += 1
        collision = (await db.execute(select(Ticket.id).where(Ticket.id == number))).scalar_one_or_none()
        if collision is None:
            break

    db.add(locked)
    await db.flush()
    # Keep the caller's in-memory object consistent with what was just persisted.
    org_settings.next_ticket_seq = locked.next_ticket_seq
    org_settings.ticket_prefix = locked.ticket_prefix
    return number


def priority_from_urgency(category: str, urgency: str) -> str:
    if urgency == "Critical":
        return "Critical"
    if urgency == "High":
        return "High"
    if category == "Support":
        return "High"
    return "Low"


async def pick_round_robin_resolver(
    db: AsyncSession, org_id: str, org_settings: OrganizationSettings, section: "Section | None" = None,
) -> User | None:
    """Workload-aware round robin: narrows to whichever active Resolver(s) currently carry
    the fewest open/in-progress tickets, then round-robins among that tied set. Pure
    round-robin (ignoring workload) could hand a Critical ticket to someone already
    drowning in 20 open tickets just because they're "next" — this keeps the fairness
    property of round robin while not piling onto an already-overloaded resolver.

    When `section` is given, only resolvers dedicated to that section are considered, and the
    round-robin cursor lives on the Section itself (not org_settings) — see Section in
    models.py. Otherwise, only resolvers with NO section (the general pool) are considered, so
    a section-dedicated resolver never receives a generic Support/Enquiry ticket by accident.
    """
    query = select(User).where(User.org_id == org_id, User.role == "Resolver", User.is_active.is_(True))
    query = query.where(User.section_id == section.id) if section else query.where(User.section_id.is_(None))
    result = await db.execute(query.order_by(User.created_at, User.id))
    resolvers = result.scalars().all()
    if not resolvers:
        return None

    counts_result = await db.execute(
        select(Ticket.assigned_to, func.count(Ticket.id))
        .where(
            Ticket.org_id == org_id,
            Ticket.assigned_to.in_([r.id for r in resolvers]),
            Ticket.status.in_(["Open", "In Progress"]),
        )
        .group_by(Ticket.assigned_to)
    )
    workload = dict(counts_result.all())
    min_load = min(workload.get(r.id, 0) for r in resolvers)
    candidates = [r for r in resolvers if workload.get(r.id, 0) == min_load]

    ids = [r.id for r in candidates]
    cursor_holder = section if section else org_settings
    if cursor_holder.last_assigned_resolver_id in ids:
        idx = ids.index(cursor_holder.last_assigned_resolver_id)
        chosen = candidates[(idx + 1) % len(candidates)]
    else:
        chosen = candidates[0]

    cursor_holder.last_assigned_resolver_id = chosen.id
    db.add(cursor_holder)
    return chosen


async def get_escalation_authority(db: AsyncSession, org_id: str, level: int = 1) -> User | None:
    """Picks the active EscalationAuthority configured at the given ladder tier
    (1 = first-line, 2 = next tier up, ...). Orgs that never set tiers put everyone
    at the default level 1, so a single-authority setup keeps working unchanged."""
    result = await db.execute(
        select(User)
        .where(
            User.org_id == org_id,
            User.role == "EscalationAuthority",
            User.is_active.is_(True),
            User.escalation_level == level,
        )
        .order_by(User.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _reload_ticket(db: AsyncSession, ticket_id: str) -> Ticket:
    # populate_existing: without it, SQLAlchemy's identity map would skip re-running
    # selectinload for a `logs`/`replies` collection it already considers loaded, silently
    # returning a pre-mutation snapshot within the same session (see tickets.py::_load_ticket).
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.replies), selectinload(Ticket.logs), selectinload(Ticket.assignee),
            selectinload(Ticket.section),
        )
        .where(Ticket.id == ticket_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def create_ticket(db: AsyncSession, org: Organization, data: dict) -> Ticket:
    """Runs the full intake pipeline: classify -> ID -> assign -> ack email -> resolver email."""
    org_settings = await get_org_settings(db, org.id)
    number = await next_ticket_number(db, org_settings)

    category = data.get("category") or "Support"
    urgency = data.get("urgency") or ("High" if category == "Support" else "Low")
    customer_name = data.get("customerName") or "Customer"
    subject = data.get("subject") or (
        f"Grievance Support Request - {customer_name}" if category == "Support" else f"General Enquiry - {customer_name}"
    )
    summary = data.get("summary") or (data.get("message") or "")[:160]
    due_hours = org_settings.support_sla_hours if category == "Support" else org_settings.enquiry_sla_hours
    now = datetime.now(timezone.utc)

    # Help Desk intake lets an admin backdate a ticket to when the call actually happened
    # (e.g. logging it a bit after the fact) so the SLA clock starts from the real call time,
    # not from whenever the form got submitted. Every other intake path (email/WhatsApp/webhook)
    # omits this, so `occurred_at` defaults to "now" exactly as before.
    occurred_at = now
    occurred_raw = data.get("occurredAt")
    if occurred_raw:
        try:
            parsed = datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            # Never let a mis-picked future date push the SLA clock forward or predate the ticket
            # after "now" — clamp to now instead of trusting arbitrary client input.
            occurred_at = min(parsed, now)
        except (ValueError, TypeError):
            occurred_at = now

    due_at = sla_calendar.compute_due_at(occurred_at, due_hours, org_settings)

    # Section-routed tickets always auto-assign within that section's Resolver pool — that's
    # the entire point of a section, independent of the org's general auto_assign_resolver
    # toggle. A ticket with no section match falls back to the existing toggle-gated behavior.
    section_id = data.get("sectionId")
    section = await db.get(Section, section_id) if section_id else None
    if section:
        resolver = await pick_round_robin_resolver(db, org.id, org_settings, section=section)
    elif org_settings.auto_assign_resolver:
        resolver = await pick_round_robin_resolver(db, org.id, org_settings)
    else:
        resolver = None

    ticket = Ticket(
        id=number,
        org_id=org.id,
        mailbox_id=data.get("mailboxId"),
        assigned_to=resolver.id if resolver else None,
        section_id=section.id if section else None,
        customer_name=customer_name,
        customer_mobile=data.get("customerMobile") or "",
        customer_email=data.get("customerEmail"),
        external_reference=(data.get("externalReference") or "").strip() or None,
        subject=subject,
        description=(data.get("message") or "").strip(),
        category=category,
        status="Open",
        priority=priority_from_urgency(category, urgency),
        channel=data.get("channel", "Portal"),
        confidence_score=float(data.get("confidenceScore", 0.9) or 0.9),
        sla_breached=False,
        urgency=urgency,
        ai_summary=summary,
        created_at=occurred_at,
        due_at=due_at,
    )
    db.add(ticket)
    await db.flush()

    db.add(
        ActivityLog(
            ticket_id=ticket.id,
            actor="AI Dispatch Engine",
            action=f"Complaint {number} Registered & Classified",
            details=f"Classified as {category} ({urgency} urgency) via {ticket.channel}. Confidence "
            f"{round(ticket.confidence_score * 100)}%.",
        )
    )
    if ticket.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        # The classifier itself flagged this as a coin-flip — surface it instead of letting
        # a possibly-wrong category/urgency silently drive SLA/routing with no human check.
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Dispatch Engine",
                action="Needs Review — Low Classification Confidence",
                details=f"Confidence was only {round(ticket.confidence_score * 100)}% (below the "
                f"{round(LOW_CONFIDENCE_THRESHOLD * 100)}% review threshold) — the category/urgency above may be "
                "wrong. Please verify manually.",
            )
        )
    if section:
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Dispatch Engine",
                action=f"Routed to Section \"{section.name}\"",
                details=f"Message matched the \"{section.name}\" section and was routed to its Resolver pool.",
            )
        )
    if resolver:
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="Round-Robin Dispatcher",
                action=f"Assigned to Resolver {resolver.name}",
                details=(
                    f"Auto-assigned to {resolver.name} ({resolver.email}) via round-robin"
                    + (f" within the \"{section.name}\" section." if section else ".")
                ),
            )
        )
    elif section:
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="Round-Robin Dispatcher",
                action=f"Unassigned — No Resolver in \"{section.name}\"",
                details=f"This ticket was routed to the \"{section.name}\" section, but no active Resolver is "
                "assigned to it yet. Add one in Team Management, or assign this ticket manually.",
            )
        )
    elif not org_settings.auto_assign_resolver:
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="Round-Robin Dispatcher",
                action="Unassigned — Auto-Assignment Disabled",
                details="Automatic resolver assignment is turned off for this organization; assign a "
                "resolver manually from the ticket.",
            )
        )
    else:
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="Round-Robin Dispatcher",
                action="Unassigned — no active Resolver",
                details="No active Resolver is configured for this organization yet. Add one in Team Management.",
            )
        )

    if data.get("mailboxId"):
        mb = await db.get(Mailbox, data["mailboxId"])
        if mb:
            mb.total_tickets_ingested = (mb.total_tickets_ingested or 0) + 1
            db.add(mb)

    await db.commit()
    await db.refresh(ticket)

    await _send_ack_and_assignment_notifications(db, org, ticket, org_settings, resolver)

    return await _reload_ticket(db, ticket.id)


async def create_ticket_from_message(
    db: AsyncSession,
    org: Organization,
    message: str,
    customer_name: str | None,
    customer_mobile: str | None,
    customer_email: str | None,
    channel: str,
    external_reference: str | None = None,
    occurred_at: str | None = None,
) -> Ticket:
    """Shared "free-text complaint -> classified ticket" pipeline: runs the message through
    Gemini classification (falling back to the rule-based classifier when no key is
    configured — see gemini_service.classify_intent) and hands the result to create_ticket().

    Used by the external intake webhook (ai.py) and by the authenticated Help Desk form
    (tickets.py) — a caller who phones in and has their issue typed up by an admin is
    classified/assigned/SLA'd exactly the same way as one who emails in.

    `occurred_at` (ISO 8601 string, optional) lets the Help Desk form backdate a ticket to when
    the call actually happened instead of when the admin finished typing it up — see
    create_ticket()'s handling of data["occurredAt"].
    """
    org_settings = await get_org_settings(db, org.id)
    sections = await get_active_sections(db, org.id)
    classification = await run_in_threadpool(
        gemini_service.classify_intent, message, org_settings.gemini_api_key or None, customer_email,
        sections_payload(sections),
    )

    category = classification["category"]
    confidence = float(classification["confidence_score"] or 0.9)
    urgency = classification.get("urgency") or ("High" if category == "Support" else "Low")
    section = await resolve_section(db, org.id, classification.get("section"))

    data = {
        "category": category,
        "urgency": urgency,
        "subject": classification.get("subject") or None,
        "summary": classification.get("summary") or None,
        "confidenceScore": confidence,
        "channel": channel,
        "message": message,
        "customerName": classification.get("extracted_name") or customer_name or "Customer",
        "customerMobile": classification.get("extracted_mobile") or customer_mobile or "",
        "customerEmail": classification.get("extracted_email") or customer_email,
        "externalReference": external_reference,
        "occurredAt": occurred_at,
        "sectionId": section.id if section else None,
    }

    return await create_ticket(db, org, data)


async def find_reusable_open_ticket(
    db: AsyncSession, org_id: str, customer_email: str | None, customer_mobile: str | None, message: str,
    api_key: str | None,
) -> Ticket | None:
    """A customer who re-contacts about the same unresolved issue without hitting Reply (a
    fresh compose, or a mail client that stripped threading headers) shouldn't get a brand-new
    ticket. Looks at this customer's most recent non-Closed tickets and asks the AI classifier
    (falling back to keyword overlap — see gemini_service.classify_is_same_issue) whether the
    new message describes the same issue as any of them. Only called for Email/WhatsApp intake
    — Help Desk and the webhook intake are staff/site-initiated, not a customer re-contacting.
    """
    if not customer_email and not customer_mobile:
        return None

    conditions = []
    if customer_email:
        conditions.append(Ticket.customer_email == customer_email)
    if customer_mobile:
        conditions.append(Ticket.customer_mobile == customer_mobile)

    result = await db.execute(
        select(Ticket)
        .where(Ticket.org_id == org_id, Ticket.status != "Closed", or_(*conditions))
        .order_by(Ticket.created_at.desc())
        .limit(REUSE_CANDIDATE_LIMIT)
    )
    for candidate in result.scalars().all():
        verdict = await run_in_threadpool(
            gemini_service.classify_is_same_issue, message, candidate.subject, candidate.ai_summary, api_key,
        )
        if verdict.get("same_issue") and verdict.get("confidence", 0) >= SAME_ISSUE_CONFIDENCE_THRESHOLD:
            return candidate

    return None


async def send_closed_notification(db: AsyncSession, ticket: Ticket, reason: str) -> None:
    """Short closing acknowledgement, reused for all three closing paths — customer-confirmed
    (append_inbound_reply), auto-closed (auto_close_unconfirmed_resolved_tickets), and
    admin-closed (routers/tickets.py::update_status)."""
    org = await db.get(Organization, ticket.org_id)
    org_settings = await get_org_settings(db, ticket.org_id)
    brand_name = resolve_brand_name(org, org_settings)

    cfg = smtp_service.from_org_settings(org_settings)
    if ticket.customer_email and cfg.configured:
        html_body = smtp_service.build_closed_email(ticket.id, ticket.customer_name, ticket.subject, reason, brand_name)
        subject = "Ticket Closed"
        result = await run_in_threadpool(smtp_service.send_email, cfg, ticket.customer_email, subject, html_body, brand_name)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="AI Auto-Receipt Sentinel",
                action="Closed Email Sent" if result.get("success") else "Closed Email Failed",
                details=result.get("message", ""),
            )
        )
        if not result.get("success") and result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "email", ticket.customer_email, subject, html_body,
                result.get("message", ""), ticket_id=ticket.id,
            )

    wa_cfg = whatsapp_service.from_org_settings(org_settings)
    if ticket.customer_mobile and wa_cfg.configured:
        wa_body = whatsapp_service.build_closed_message(ticket.id, ticket.customer_name, ticket.subject, reason)
        wa_result = await run_in_threadpool(whatsapp_service.send_text, wa_cfg, ticket.customer_mobile, wa_body)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="AI Auto-Receipt Sentinel",
                action="WhatsApp Closed Notice Sent" if wa_result.get("success") else "WhatsApp Closed Notice Failed",
                details=wa_result.get("message", ""),
            )
        )
        if not wa_result.get("success") and wa_result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "whatsapp", ticket.customer_mobile, "", wa_body,
                wa_result.get("message", ""), ticket_id=ticket.id,
            )

    await db.commit()


async def append_inbound_reply(db: AsyncSession, ticket: Ticket, sender_label: str, text: str, api_key: str | None = None) -> None:
    """Channel-agnostic handling of a customer's follow-up message on an existing ticket
    (email reply, WhatsApp message, or a reused-ticket match from find_reusable_open_ticket).

    - Resolved ticket: asks the AI whether the reply confirms the fix (see
      gemini_service.classify_resolution_reply). A clear confirmation closes the ticket; a
      clear denial OR an ambiguous reply both reopen it for human review — an ambiguous
      reply must never silently close a ticket.
    - Escalated ticket: unconditionally reopens to Open (unaffected by this change — it
      isn't a resolution yet).
    - Otherwise: just logs the reply, no status change.
    """
    db.add(TicketReply(ticket_id=ticket.id, sender=sender_label, is_agent=False, text=text))

    if ticket.status == "Resolved":
        verdict = await run_in_threadpool(
            gemini_service.classify_resolution_reply, text, ticket.subject, ticket.ai_summary, api_key,
        )
        confirms = verdict.get("confirms_resolved")
        if confirms is True:
            now = datetime.now(timezone.utc)
            ticket.status = "Closed"
            ticket.closed_at = now
            db.add(ticket)
            db.add(
                ActivityLog(
                    ticket_id=ticket.id, actor=sender_label,
                    action="Closed — Customer Confirmed Resolution",
                    details="Customer's reply confirmed the issue is resolved.",
                )
            )
            await db.commit()
            await send_closed_notification(db, ticket, "the customer confirmed the issue is resolved")
            return
        else:
            reason = "the reply indicated the issue is still not fixed" if confirms is False else "the reply was ambiguous"
            ticket.status = "Open"
            ticket.resolved_at = None
            db.add(ticket)
            db.add(
                ActivityLog(
                    ticket_id=ticket.id, actor=sender_label,
                    action="Reopened from Resolved — customer replied",
                    details=f"{reason.capitalize()}; ticket moved back to Open for re-review.",
                )
            )
    elif ticket.status == "Escalated":
        ticket.status = "Open"
        ticket.resolved_at = None
        db.add(ticket)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor=sender_label,
                action="Reopened from Escalated — customer replied",
                details="Customer reply received; ticket moved back to Open for re-review.",
            )
        )
    else:
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor=sender_label,
                action="Customer Replied",
                details=f"New inbound message from {sender_label} appended to ticket {ticket.id}.",
            )
        )

    if ticket.awaiting_customer:
        await db.commit()  # persist the reply/status change before set_awaiting_customer commits its own
        await set_awaiting_customer(db, ticket, False, sender_label)
    else:
        await db.commit()


async def auto_close_unconfirmed_resolved_tickets(db: AsyncSession) -> int:
    """Scheduler job: a Resolved ticket the customer never replied to auto-closes after the
    org's grace period (default 3 days — OrganizationSettings.auto_close_after_days), so
    "Resolved" isn't a dead end that silently sits there forever."""
    now = datetime.now(timezone.utc)
    settings_cache: dict[str, OrganizationSettings] = {}
    count = 0

    async def _settings_for(org_id: str) -> OrganizationSettings:
        if org_id not in settings_cache:
            settings_cache[org_id] = await get_org_settings(db, org_id)
        return settings_cache[org_id]

    result = await db.execute(select(Ticket).where(Ticket.status == "Resolved", Ticket.resolved_at.isnot(None)))
    for ticket in result.scalars().all():
        org_settings = await _settings_for(ticket.org_id)
        grace = timedelta(days=org_settings.auto_close_after_days)
        if _as_aware_utc(ticket.resolved_at) + grace > now:
            continue

        ticket.status = "Closed"
        ticket.closed_at = now
        db.add(ticket)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="SLA Sentinel",
                action="Closed — Auto-closed after grace period",
                details=f"No customer response {org_settings.auto_close_after_days} day(s) after being marked "
                "Resolved; auto-closed.",
            )
        )
        await db.commit()
        await send_closed_notification(db, ticket, f"{org_settings.auto_close_after_days} days passed with no reply")
        count += 1

    return count


async def _send_ack_and_assignment_notifications(
    db: AsyncSession, org: Organization, ticket: Ticket, org_settings: OrganizationSettings, resolver: User | None
) -> None:
    """Two-stage customer notification: a thank-you goes out immediately regardless of
    assignment, and a separate "your request is being handled" email goes out only once a
    resolver is actually attached to the ticket — here, that means auto-assignment picked one
    at creation time. When auto-assignment is off (or no Resolver exists yet), that second
    email fires later from `send_assignment_ack` when an OrgAdmin manually assigns one."""
    cfg = smtp_service.from_org_settings(org_settings)
    wa_cfg = whatsapp_service.from_org_settings(org_settings)
    sms_cfg = sms_service.from_org_settings(org_settings)
    due_iso = ticket.due_at.isoformat() if ticket.due_at else None
    brand_name = resolve_brand_name(org, org_settings)

    ticket_sla_hours = org_settings.support_sla_hours if ticket.category == "Support" else org_settings.enquiry_sla_hours

    if org_settings.auto_send_receipt and ticket.customer_email and cfg.configured:
        html_body = smtp_service.build_thank_you_email(
            ticket.id, ticket.customer_name, ticket.category, ticket.subject, ticket.ai_summary, due_iso,
            ticket_sla_hours, brand_name,
        )
        subject = "Thank you for reaching out to us"
        result = await run_in_threadpool(smtp_service.send_email, cfg, ticket.customer_email, subject, html_body, brand_name)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="Thank-You Email Sent" if result.get("success") else "Thank-You Email Failed",
                details=result.get("message", ""),
            )
        )
        if result.get("success"):
            db.add(TicketReply(
                ticket_id=ticket.id, sender="AI Auto-Receipt Sentinel", is_agent=True,
                text=smtp_service.html_to_text(html_body),
            ))
        elif result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "email", ticket.customer_email, subject, html_body,
                result.get("message", ""), ticket_id=ticket.id,
            )
    elif org_settings.auto_send_receipt and not ticket.customer_email:
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="Thank-You Email Skipped — No Contact Email",
                details="No email address could be captured for this complainant, so no acknowledgement could "
                "be sent. Add one manually on the ticket if available.",
            )
        )

    if org_settings.auto_send_receipt and ticket.customer_mobile and wa_cfg.configured:
        wa_body = whatsapp_service.build_ack_message(
            ticket.id, ticket.customer_name, ticket.category, ticket.urgency, ticket.ai_summary, ticket_sla_hours,
            brand_name,
        )
        wa_result = await run_in_threadpool(whatsapp_service.send_text, wa_cfg, ticket.customer_mobile, wa_body)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="WhatsApp Acknowledgement Sent" if wa_result.get("success") else "WhatsApp Acknowledgement Failed",
                details=wa_result.get("message", ""),
            )
        )
        if wa_result.get("success"):
            db.add(TicketReply(ticket_id=ticket.id, sender="AI Auto-Receipt Sentinel", is_agent=True, text=wa_body))
        elif wa_result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "whatsapp", ticket.customer_mobile, "", wa_body,
                wa_result.get("message", ""), ticket_id=ticket.id,
            )

    if org_settings.auto_send_receipt and ticket.customer_mobile and sms_cfg.configured:
        sms_body = sms_service.build_ack_message(ticket.id, ticket.customer_name, ticket.category, ticket_sla_hours, brand_name)
        sms_result = await run_in_threadpool(sms_service.send_text, sms_cfg, ticket.customer_mobile, sms_body)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="SMS Acknowledgement Sent" if sms_result.get("success") else "SMS Acknowledgement Failed",
                details=sms_result.get("message", ""),
            )
        )
        if sms_result.get("success"):
            db.add(TicketReply(ticket_id=ticket.id, sender="AI Auto-Receipt Sentinel", is_agent=True, text=sms_body))
        elif sms_result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "sms", ticket.customer_mobile, "", sms_body,
                sms_result.get("message", ""), ticket_id=ticket.id,
            )

    if resolver and resolver.email and cfg.configured:
        html_body = smtp_service.build_resolver_assignment_email(
            ticket.id, resolver.name, ticket.customer_name, ticket.category, ticket.subject,
            ticket.description, ticket.ai_summary, ticket.urgency, due_iso, brand_name,
        )
        subject = f"[{ticket.id}] New Ticket Assigned To You"
        result = await run_in_threadpool(smtp_service.send_email, cfg, resolver.email, subject, html_body, brand_name)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="Round-Robin Dispatcher",
                action="Resolver Notification Sent" if result.get("success") else "Resolver Notification Failed",
                details=result.get("message", ""),
            )
        )
        if not result.get("success") and result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "email", resolver.email, subject, html_body,
                result.get("message", ""), ticket_id=ticket.id,
            )

    # Auto-assignment picked a resolver in the same request — the customer's "being handled"
    # email can go out right away instead of waiting for a manual assignment later.
    if resolver and org_settings.auto_send_receipt and ticket.customer_email and cfg.configured:
        await send_assignment_ack_email(db, ticket, org_settings, cfg, brand_name, ticket_sla_hours)

    await db.commit()


async def send_assignment_ack_email(
    db: AsyncSession, ticket: Ticket, org_settings: OrganizationSettings, cfg, brand_name: str, ticket_sla_hours: int,
) -> None:
    """Stage B of the customer notification lifecycle — sent the moment a resolver is
    actually attached to the ticket, whether that happens at creation (auto-assignment on)
    or later via a manual assignment (see routers/tickets.py::reassign_ticket)."""
    due_iso = ticket.due_at.isoformat() if ticket.due_at else None
    html_body = smtp_service.build_assignment_ack_email(
        ticket.id, ticket.customer_name, ticket.category, ticket.subject, due_iso, ticket_sla_hours, brand_name,
    )
    subject = "Your request is being handled"
    result = await run_in_threadpool(smtp_service.send_email, cfg, ticket.customer_email, subject, html_body, brand_name)
    db.add(
        ActivityLog(
            ticket_id=ticket.id,
            actor="Round-Robin Dispatcher",
            action="Assignment Notice Sent to Customer" if result.get("success") else "Assignment Notice to Customer Failed",
            details=result.get("message", ""),
        )
    )
    if result.get("success"):
        db.add(TicketReply(
            ticket_id=ticket.id, sender="AI Auto-Receipt Sentinel", is_agent=True,
            text=smtp_service.html_to_text(html_body),
        ))
    elif result.get("retryable"):
        await notification_retry_service.record_failure(
            db, ticket.org_id, "email", ticket.customer_email, subject, html_body,
            result.get("message", ""), ticket_id=ticket.id,
        )


async def resolve_ticket(db: AsyncSession, org: Organization, ticket: Ticket, org_settings: OrganizationSettings) -> None:
    """Send the 'your complaint is resolved' notification on every channel the complainant
    gave a contact for. Caller has already set status/resolved_at."""
    brand_name = resolve_brand_name(org, org_settings)
    cfg = smtp_service.from_org_settings(org_settings)
    if ticket.customer_email and cfg.configured:
        html_body = smtp_service.build_resolved_email(
            ticket.id, ticket.customer_name, ticket.subject, brand_name,
            auto_close_days=org_settings.auto_close_after_days,
        )
        subject = "Your Complaint Has Been Resolved"
        result = await run_in_threadpool(smtp_service.send_email, cfg, ticket.customer_email, subject, html_body, brand_name)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="Resolution Email Sent" if result.get("success") else "Resolution Email Failed",
                details=result.get("message", ""),
            )
        )
        if not result.get("success") and result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "email", ticket.customer_email, subject, html_body,
                result.get("message", ""), ticket_id=ticket.id,
            )

    wa_cfg = whatsapp_service.from_org_settings(org_settings)
    if ticket.customer_mobile and wa_cfg.configured:
        wa_body = whatsapp_service.build_resolved_message(
            ticket.id, ticket.customer_name, ticket.subject, auto_close_days=org_settings.auto_close_after_days,
        )
        wa_result = await run_in_threadpool(whatsapp_service.send_text, wa_cfg, ticket.customer_mobile, wa_body)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="WhatsApp Resolution Notice Sent" if wa_result.get("success") else "WhatsApp Resolution Notice Failed",
                details=wa_result.get("message", ""),
            )
        )
        if not wa_result.get("success") and wa_result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "whatsapp", ticket.customer_mobile, "", wa_body,
                wa_result.get("message", ""), ticket_id=ticket.id,
            )

    sms_cfg = sms_service.from_org_settings(org_settings)
    if ticket.customer_mobile and sms_cfg.configured:
        sms_body = sms_service.build_resolved_message(ticket.id, ticket.subject, brand_name)
        sms_result = await run_in_threadpool(sms_service.send_text, sms_cfg, ticket.customer_mobile, sms_body)
        db.add(
            ActivityLog(
                ticket_id=ticket.id,
                actor="AI Auto-Receipt Sentinel",
                action="SMS Resolution Notice Sent" if sms_result.get("success") else "SMS Resolution Notice Failed",
                details=sms_result.get("message", ""),
            )
        )
        if not sms_result.get("success") and sms_result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "sms", ticket.customer_mobile, "", sms_body,
                sms_result.get("message", ""), ticket_id=ticket.id,
            )

    if (ticket.customer_email and cfg.configured) or (ticket.customer_mobile and wa_cfg.configured) or (ticket.customer_mobile and sms_cfg.configured):
        await db.commit()


async def _notify_org_admins(db: AsyncSession, org_id: str, cfg, subject: str, body: str, from_display: str) -> None:
    """Best-effort alert to every active OrgAdmin — used when the automated pipeline hits
    something it needs a human to fix (e.g. a missing Escalation Authority tier)."""
    if not cfg.configured:
        return
    result = await db.execute(
        select(User).where(User.org_id == org_id, User.role == "OrgAdmin", User.is_active.is_(True))
    )
    for admin in result.scalars().all():
        if admin.email:
            await run_in_threadpool(smtp_service.send_email, cfg, admin.email, subject, body, from_display)


async def escalate_ticket(
    db: AsyncSession, org: Organization, ticket: Ticket, org_settings: OrganizationSettings,
    reason: str = "SLA breach", target_level: int | None = None,
) -> None:
    """Marks a ticket Escalated at the given ladder tier, reassigns to that tier's
    Escalation Authority (if any), and emails both sides. `target_level` defaults to
    one tier above the ticket's current level, so re-escalation climbs the ladder
    instead of re-notifying the same person forever."""
    brand_name = resolve_brand_name(org, org_settings)
    level = target_level if target_level is not None else (ticket.escalation_level or 0) + 1
    authority = await get_escalation_authority(db, ticket.org_id, level=level)
    is_re_escalation = ticket.escalation_level and ticket.escalation_level > 0

    now = datetime.now(timezone.utc)
    ticket.status = "Escalated"
    ticket.sla_breached = True
    ticket.escalation_level = level
    ticket.escalated_at = now
    if authority:
        ticket.assigned_to = authority.id
    db.add(ticket)

    tier_label = f"tier {level}"
    db.add(
        ActivityLog(
            ticket_id=ticket.id,
            actor="SLA Sentinel",
            action=f"Escalated to {tier_label} ({reason})" + (f" — {authority.name}" if authority else " — no Escalation Authority configured at this tier"),
            details=(
                f"SLA window expired at {ticket.due_at.isoformat() if ticket.due_at else 'unknown'}. "
                + (f"Reassigned to {authority.name} ({authority.email})." if authority else f"No active Escalation Authority is configured at tier {level} for this organization.")
            ),
        )
    )
    await db.commit()

    cfg = smtp_service.from_org_settings(org_settings)
    if ticket.customer_email and cfg.configured:
        body = smtp_service.build_escalation_customer_email(
            ticket.id, ticket.customer_name, ticket.subject, brand_name, is_re_escalation, authority_assigned=bool(authority),
        )
        subject = "Your Complaint Has Been Escalated" + (" Further" if is_re_escalation else "")
        result = await run_in_threadpool(smtp_service.send_email, cfg, ticket.customer_email, subject, body, brand_name)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="SLA Sentinel",
                action="Escalation Email Sent to Customer" if result.get("success") else "Escalation Email to Customer Failed",
                details=result.get("message", ""),
            )
        )
        if not result.get("success") and result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "email", ticket.customer_email, subject, body,
                result.get("message", ""), ticket_id=ticket.id,
            )

    wa_cfg = whatsapp_service.from_org_settings(org_settings)
    if ticket.customer_mobile and wa_cfg.configured:
        wa_body = whatsapp_service.build_escalated_message(ticket.id, ticket.customer_name, ticket.subject, authority_assigned=bool(authority))
        wa_result = await run_in_threadpool(whatsapp_service.send_text, wa_cfg, ticket.customer_mobile, wa_body)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="SLA Sentinel",
                action="WhatsApp Escalation Notice Sent" if wa_result.get("success") else "WhatsApp Escalation Notice Failed",
                details=wa_result.get("message", ""),
            )
        )
        if not wa_result.get("success") and wa_result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "whatsapp", ticket.customer_mobile, "", wa_body,
                wa_result.get("message", ""), ticket_id=ticket.id,
            )

    if authority and authority.email and cfg.configured:
        due_iso = ticket.due_at.isoformat() if ticket.due_at else None
        body = smtp_service.build_escalation_authority_email(
            ticket.id, ticket.customer_name, ticket.category, ticket.subject, ticket.ai_summary, ticket.description,
            due_iso, brand_name,
        )
        subject = f"[SLA BREACH] {ticket.id} needs your attention (tier {level})"
        result = await run_in_threadpool(smtp_service.send_email, cfg, authority.email, subject, body, brand_name)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="SLA Sentinel",
                action="Escalation Notified to Authority" if result.get("success") else "Escalation Notification to Authority Failed",
                details=result.get("message", ""),
            )
        )
        if not result.get("success") and result.get("retryable"):
            await notification_retry_service.record_failure(
                db, ticket.org_id, "email", authority.email, subject, body,
                result.get("message", ""), ticket_id=ticket.id,
            )
    elif not authority:
        # Nobody is configured at this tier — flag it for an OrgAdmin instead of letting the
        # breach go silently unhandled (the customer email above already avoided overclaiming).
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="SLA Sentinel",
                action="OrgAdmin Action Needed — No Escalation Authority Configured",
                details=f"Ticket escalated to tier {level} but no active Escalation Authority exists at that "
                "tier. Add one in Team Management so future breaches reach a real person.",
            )
        )
        alert_body = smtp_service.build_admin_alert_email(
            org.name, ticket.id, ticket.subject,
            f"It breached its SLA and escalated to tier {level}, but no active Escalation Authority is "
            f"configured at that tier, so nobody was notified to act on it.",
            brand_name,
        )
        await _notify_org_admins(
            db, ticket.org_id, cfg, f"[Action Needed] {ticket.id} escalated with no authority configured",
            alert_body, brand_name,
        )

    await db.commit()


async def escalate_overdue_tickets(db: AsyncSession) -> int:
    """Scheduler job, two passes:
    1. First-tier escalation — every Open/In Progress ticket past its SLA `due_at`.
    2. Ladder climb — every already-Escalated ticket that's sat unresolved past
       `re_escalation_hours` since its last escalation gets bumped to the next tier,
       but only when a higher-tier authority actually exists (otherwise it's already
       with the highest configured authority and re-notifying every cycle would just spam them).
    """
    now = datetime.now(timezone.utc)
    settings_cache: dict[str, OrganizationSettings] = {}
    org_cache: dict[str, Organization] = {}
    count = 0

    async def _settings_for(org_id: str) -> OrganizationSettings:
        if org_id not in settings_cache:
            settings_cache[org_id] = await get_org_settings(db, org_id)
        return settings_cache[org_id]

    async def _org_for(org_id: str) -> Organization:
        if org_id not in org_cache:
            org_cache[org_id] = await db.get(Organization, org_id)
        return org_cache[org_id]

    result = await db.execute(
        select(Ticket).where(
            Ticket.status.in_(["Open", "In Progress"]), Ticket.due_at.isnot(None), Ticket.due_at < now,
            Ticket.awaiting_customer.is_(False),
        )
    )
    for ticket in result.scalars().all():
        await escalate_ticket(db, await _org_for(ticket.org_id), ticket, await _settings_for(ticket.org_id), reason="SLA breach")
        count += 1

    result = await db.execute(select(Ticket).where(Ticket.status == "Escalated", Ticket.escalated_at.isnot(None)))
    for ticket in result.scalars().all():
        org_settings = await _settings_for(ticket.org_id)
        reescalate_after = timedelta(hours=org_settings.re_escalation_hours)
        if _as_aware_utc(ticket.escalated_at) + reescalate_after > now:
            continue
        next_level = (ticket.escalation_level or 0) + 1
        next_authority = await get_escalation_authority(db, ticket.org_id, level=next_level)
        if not next_authority:
            continue  # already with the highest configured tier — nothing further to climb to
        await escalate_ticket(
            db, await _org_for(ticket.org_id), ticket, org_settings,
            reason="Still unresolved after escalation", target_level=next_level,
        )
        count += 1

    return count


async def add_reply(db: AsyncSession, ticket: Ticket, actor: str, text: str) -> TicketReply:
    reply = TicketReply(ticket_id=ticket.id, sender=actor, is_agent=True, text=text)
    db.add(reply)
    db.add(ActivityLog(ticket_id=ticket.id, actor=actor, action="Agent Reply Sent", details="Sent response to customer."))
    await db.commit()
    await db.refresh(reply)
    return reply


def _as_aware_utc(dt: datetime) -> datetime:
    """Normalizes a datetime to UTC-aware. Postgres (TIMESTAMPTZ, the production target)
    always hands back tz-aware datetimes, but SQLite (used in the test suite / local
    no-Postgres dev) has no native timezone-aware type and reads DateTime(timezone=True)
    columns back as naive — arithmetic against `datetime.now(timezone.utc)` would then
    raise TypeError. Treating a naive value as already-UTC keeps both backends correct."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _fmt_duration(delta: timedelta) -> str:
    total_minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


async def set_awaiting_customer(db: AsyncSession, ticket: Ticket, awaiting: bool, actor: str) -> None:
    """Pauses/resumes the SLA clock for a ticket that's blocked on a customer reply.
    While paused, `escalate_overdue_tickets` skips it entirely regardless of `due_at`.
    On resume, `due_at` is pushed forward by however long it was paused, so the resolver
    doesn't lose SLA time waiting on the customer."""
    now = datetime.now(timezone.utc)
    if awaiting and not ticket.awaiting_customer:
        ticket.awaiting_customer = True
        ticket.awaiting_customer_since = now
        db.add(ticket)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor=actor,
                action="SLA Clock Paused — Awaiting Customer Reply",
                details="SLA breach/escalation checks are paused until the customer replies or an agent resumes the clock.",
            )
        )
        await db.commit()
    elif not awaiting and ticket.awaiting_customer:
        since = _as_aware_utc(ticket.awaiting_customer_since) if ticket.awaiting_customer_since else now
        paused_duration = now - since
        ticket.awaiting_customer = False
        ticket.awaiting_customer_since = None
        if ticket.due_at:
            ticket.due_at = _as_aware_utc(ticket.due_at) + paused_duration
        db.add(ticket)
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor=actor,
                action="SLA Clock Resumed",
                details=f"Paused for {_fmt_duration(paused_duration)}; SLA due date extended by the same amount.",
            )
        )
        await db.commit()


async def check_sla_warnings(db: AsyncSession) -> int:
    """Scheduler job: warns the assignee once a ticket has used up 80% of its SLA window,
    so a breach is a surprise to nobody. Fires at most once per ticket (sla_warning_sent_at)."""
    now = datetime.now(timezone.utc)
    settings_cache: dict[str, OrganizationSettings] = {}
    warned = 0

    async def _settings_for(org_id: str) -> OrganizationSettings:
        if org_id not in settings_cache:
            settings_cache[org_id] = await get_org_settings(db, org_id)
        return settings_cache[org_id]

    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.assignee))
        .where(
            Ticket.status.in_(["Open", "In Progress"]),
            Ticket.awaiting_customer.is_(False),
            Ticket.sla_warning_sent_at.is_(None),
            Ticket.due_at.isnot(None),
        )
    )
    for ticket in result.scalars().all():
        due_at = _as_aware_utc(ticket.due_at)
        created_at = _as_aware_utc(ticket.created_at)
        window = (due_at - created_at).total_seconds()
        if window <= 0:
            continue
        elapsed = (now - created_at).total_seconds()
        if elapsed / window < 0.8:
            continue

        ticket.sla_warning_sent_at = now
        db.add(ticket)
        remaining = _fmt_duration(due_at - now) if due_at > now else "0m (overdue)"
        db.add(
            ActivityLog(
                ticket_id=ticket.id, actor="SLA Sentinel",
                action="SLA Warning — 80% of Window Elapsed",
                details=f"Approaching SLA breach; {remaining} remaining before due date.",
            )
        )

        assignee = ticket.assignee
        if assignee and assignee.email:
            org_settings = await _settings_for(ticket.org_id)
            cfg = smtp_service.from_org_settings(org_settings)
            if cfg.configured:
                org = await db.get(Organization, ticket.org_id)
                brand_name = resolve_brand_name(org, org_settings)
                body = smtp_service.build_sla_warning_email(
                    ticket.id, assignee.name, ticket.subject, ticket.due_at.isoformat(), remaining, brand_name,
                )
                subject = f"[SLA Warning] {ticket.id} — {remaining} remaining"
                result_send = await run_in_threadpool(smtp_service.send_email, cfg, assignee.email, subject, body, brand_name)
                db.add(
                    ActivityLog(
                        ticket_id=ticket.id, actor="SLA Sentinel",
                        action="SLA Warning Sent" if result_send.get("success") else "SLA Warning Failed",
                        details=result_send.get("message", ""),
                    )
                )
        await db.commit()
        warned += 1

    return warned
