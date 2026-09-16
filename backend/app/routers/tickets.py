from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..deps import get_current_org, get_current_user, require_roles
from ..models import ActivityLog, Organization, Ticket, User
from ..schemas import AwaitingCustomerUpdate, ManualTicketCreate, ReassignRequest, ReplyCreate, TicketStatusUpdate
from ..serializers import reply_to_dict, ticket_to_dict
from ..services import gemini_service, smtp_service
from ..services.ticket_service import (
    add_reply,
    create_ticket_from_message,
    escalate_ticket,
    get_org_settings,
    resolve_brand_name,
    resolve_ticket,
    send_assignment_ack_email,
    send_closed_notification,
    set_awaiting_customer,
)

router = APIRouter(prefix="/api", tags=["tickets"])

# Which target statuses each role may set, and whether they're restricted to their own assigned tickets.
# "Closed" is OrgAdmin-only — a Resolver/EscalationAuthority can't force-close a ticket; it's
# otherwise only reached via customer confirmation or the auto-close grace period.
ROLE_ALLOWED_STATUSES = {
    "OrgAdmin": {"Open", "In Progress", "Resolved", "Escalated", "Closed"},
    "Resolver": {"In Progress", "Resolved"},
    "EscalationAuthority": {"In Progress", "Resolved"},
}


async def _load_ticket(db: AsyncSession, ticket_id: str, org_id: str) -> Ticket:
    """Callers use this both for the initial load AND to reload after mutating the ticket
    (status change, reply, escalation, ...) within the same request/session. Without
    `populate_existing`, SQLAlchemy's identity map treats an already-loaded `logs`/`replies`
    collection as still fresh and won't re-run `selectinload` for it — so a second call in
    the same request would silently return the pre-mutation activity log / reply list (and,
    downstream, a stale `needsAttention` computed from it)."""
    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.replies), selectinload(Ticket.logs), selectinload(Ticket.assignee),
            selectinload(Ticket.section),
        )
        .where(Ticket.id == ticket_id, Ticket.org_id == org_id)
        .execution_options(populate_existing=True)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.get("/tickets")
async def list_tickets(
    search: str | None = None,
    tstatus: str | None = None,
    category: str | None = None,
    sla: bool | None = None,
    needsAttention: bool | None = None,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Ticket)
        .options(
            selectinload(Ticket.replies), selectinload(Ticket.logs), selectinload(Ticket.assignee),
            selectinload(Ticket.section),
        )
        .where(Ticket.org_id == org.id)
        .order_by(Ticket.created_at.desc())
    )
    if user.role in ("Resolver", "EscalationAuthority"):
        query = query.where(Ticket.assigned_to == user.id)
    if tstatus and tstatus != "All":
        query = query.where(Ticket.status == tstatus)
    if category and category != "All":
        query = query.where(Ticket.category == category)
    if sla:
        query = query.where(Ticket.sla_breached.is_(True))

    result = await db.execute(query)
    tickets = result.scalars().all()

    if search and search.strip():
        q = search.strip().lower()
        tickets = [
            t for t in tickets
            if q in t.id.lower() or q in (t.customer_name or "").lower()
            or q in (t.customer_mobile or "").lower() or q in (t.subject or "").lower()
        ]

    ticket_dicts = [ticket_to_dict(t) for t in tickets]
    if needsAttention:
        ticket_dicts = [d for d in ticket_dicts if d["needsAttention"]]

    return {"tickets": ticket_dicts}


@router.post("/tickets/manual")
async def create_manual_ticket(
    payload: ManualTicketCreate,
    user: User = Depends(require_roles("OrgAdmin")),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Help Desk intake: an OrgAdmin logs a phone call on the caller's behalf. Runs through the
    exact same classify/assign/SLA/notify pipeline as an emailed or WhatsApp complaint —
    just entered by an admin instead of written by the customer."""
    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please describe the caller's issue.")

    ticket = await create_ticket_from_message(
        db,
        org,
        payload.message,
        payload.customerName,
        payload.customerMobile,
        payload.customerEmail,
        channel="Phone",
        external_reference=payload.externalReference,
        occurred_at=payload.occurredAt,
    )
    return {"ticket": ticket_to_dict(ticket)}


@router.post("/tickets/{ticket_id}/status")
async def update_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    ticket = await _load_ticket(db, ticket_id, org.id)

    allowed = ROLE_ALLOWED_STATUSES.get(user.role, set())
    if payload.status not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Your role cannot set status to {payload.status}.")
    if user.role in ("Resolver", "EscalationAuthority") and ticket.assigned_to != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This ticket is not assigned to you.")

    previous = ticket.status
    org_settings = await get_org_settings(db, org.id)

    if payload.status == previous:
        return {"ticket": ticket_to_dict(ticket)}

    if payload.status == "Escalated":
        await escalate_ticket(db, org, ticket, org_settings, reason="Manually escalated")
    elif payload.status == "Resolved":
        ticket.status = "Resolved"
        ticket.resolved_at = datetime.now(timezone.utc)
        db.add(ticket)
        db.add(ActivityLog(ticket_id=ticket.id, actor=f"{user.name} ({user.role})", action="Status Updated to Resolved", details=f"Updated status from {previous} to Resolved."))
        await db.commit()
        await resolve_ticket(db, org, ticket, org_settings)
    elif payload.status == "Closed":
        ticket.status = "Closed"
        ticket.closed_at = datetime.now(timezone.utc)
        db.add(ticket)
        db.add(ActivityLog(ticket_id=ticket.id, actor=f"{user.name} ({user.role})", action="Closed — Manually closed by OrgAdmin", details=f"Updated status from {previous} to Closed by {user.name}."))
        await db.commit()
        await send_closed_notification(db, ticket, f"it was manually closed by {user.name}")
    else:
        ticket.status = payload.status
        if payload.status not in ("Resolved", "Closed"):
            ticket.resolved_at = None
        db.add(ticket)
        db.add(ActivityLog(ticket_id=ticket.id, actor=f"{user.name} ({user.role})", action=f"Status Updated to {payload.status}", details=f"Updated status from {previous} to {payload.status}."))
        await db.commit()

    ticket = await _load_ticket(db, ticket_id, org.id)
    return {"ticket": ticket_to_dict(ticket)}


@router.post("/tickets/{ticket_id}/awaiting-customer")
async def update_awaiting_customer(
    ticket_id: str,
    payload: AwaitingCustomerUpdate,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Pauses/resumes the SLA clock — for when a resolver is blocked waiting on the
    customer (e.g. asked for a screenshot) and shouldn't have the ticket auto-escalate
    on them for time that wasn't in their control."""
    ticket = await _load_ticket(db, ticket_id, org.id)
    if user.role in ("Resolver", "EscalationAuthority") and ticket.assigned_to != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This ticket is not assigned to you.")

    await set_awaiting_customer(db, ticket, payload.awaiting, f"{user.name} ({user.role})")

    ticket = await _load_ticket(db, ticket_id, org.id)
    return {"ticket": ticket_to_dict(ticket)}


@router.post("/tickets/{ticket_id}/reassign")
async def reassign_ticket(
    ticket_id: str,
    payload: ReassignRequest,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "OrgAdmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an Org Admin can reassign tickets.")

    ticket = await _load_ticket(db, ticket_id, org.id)
    target = await db.get(User, payload.userId)
    if target is None or target.org_id != org.id or target.role not in ("Resolver", "EscalationAuthority"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user must be an active team member of this organization.")

    was_unassigned = ticket.assigned_to is None
    ticket.assigned_to = target.id
    db.add(ticket)
    db.add(ActivityLog(ticket_id=ticket.id, actor=f"{user.name} ({user.role})", action=f"Reassigned to {target.name}", details=f"Manually reassigned by {user.name}."))
    await db.commit()

    org_settings = await get_org_settings(db, org.id)
    brand_name = resolve_brand_name(org, org_settings)
    cfg = smtp_service.from_org_settings(org_settings)
    if target.email and cfg.configured:
        due_iso = ticket.due_at.isoformat() if ticket.due_at else None
        body = smtp_service.build_resolver_assignment_email(
            ticket.id, target.name, ticket.customer_name, ticket.category, ticket.subject, ticket.description,
            ticket.ai_summary, ticket.urgency, due_iso, brand_name,
        )
        await run_in_threadpool(
            smtp_service.send_email, cfg, target.email, f"[{ticket.id}] Ticket Reassigned To You", body, brand_name,
        )

    # First real assignment (this is the path that fires when auto-assignment is off, or no
    # Resolver existed yet at intake time) — tell the customer their request is now being
    # handled. Later reassignments to a different resolver only notify the new resolver above.
    if was_unassigned and ticket.customer_email and org_settings.auto_send_receipt and cfg.configured:
        ticket_sla_hours = org_settings.support_sla_hours if ticket.category == "Support" else org_settings.enquiry_sla_hours
        await send_assignment_ack_email(db, ticket, org_settings, cfg, brand_name, ticket_sla_hours)
        await db.commit()

    ticket = await _load_ticket(db, ticket_id, org.id)
    return {"ticket": ticket_to_dict(ticket)}


@router.post("/tickets/{ticket_id}/replies")
async def add_agent_reply(
    ticket_id: str,
    payload: ReplyCreate,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    ticket = await _load_ticket(db, ticket_id, org.id)
    if user.role in ("Resolver", "EscalationAuthority") and ticket.assigned_to != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This ticket is not assigned to you.")

    reply = await add_reply(db, ticket, f"{user.name} ({user.role})", payload.text)

    smtp_result = None
    if ticket.customer_email:
        org_settings = await get_org_settings(db, org.id)
        cfg = smtp_service.from_org_settings(org_settings)
        if cfg.configured:
            smtp_result = await run_in_threadpool(smtp_service.send_email, cfg, ticket.customer_email, ticket.subject, payload.text)
        else:
            smtp_result = {"success": False, "message": "SMTP not configured; reply saved in-app only."}

    ticket = await _load_ticket(db, ticket_id, org.id)
    return {"ticket": ticket_to_dict(ticket), "reply": reply_to_dict(reply), "smtp": smtp_result}


@router.post("/tickets/{ticket_id}/suggest-reply")
async def suggest_reply(
    ticket_id: str,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Drafts a reply for the resolver to review and edit — never sent automatically."""
    ticket = await _load_ticket(db, ticket_id, org.id)
    if user.role in ("Resolver", "EscalationAuthority") and ticket.assigned_to != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This ticket is not assigned to you.")

    org_settings = await get_org_settings(db, org.id)
    prior_replies = [r.text for r in ticket.replies if r.is_agent]
    result = await run_in_threadpool(
        gemini_service.suggest_reply,
        ticket.customer_name, ticket.category, ticket.subject, ticket.description, ticket.ai_summary,
        prior_replies, org_settings.gemini_api_key or None,
    )
    return result
