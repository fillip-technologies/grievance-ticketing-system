from typing import Any

from .models import (
    ActivityLog,
    Mailbox,
    Organization,
    OrganizationSettings,
    Section,
    Ticket,
    TicketReply,
    User,
)


def user_to_dict(user: User) -> dict[str, Any]:
    org = user.org if user.org_id else None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "mobile": user.mobile,
        "role": user.role,
        "escalationLevel": user.escalation_level,
        "sectionId": user.section_id,
        "isActive": user.is_active,
        "mustResetPassword": user.must_reset_password,
        "orgId": user.org_id,
        "orgName": org.name if org else None,
        "orgSlug": org.slug if org else None,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
    }


def team_member_to_dict(user: User, open_ticket_count: int = 0, section_name: str | None = None) -> dict[str, Any]:
    d = user_to_dict(user)
    d["openTicketCount"] = open_ticket_count
    d["sectionName"] = section_name
    return d


def section_to_dict(s: Section, resolver_count: int = 0) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "isActive": s.is_active,
        "resolverCount": resolver_count,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
    }


def organization_to_dict(org: Organization, ticket_count: int = 0, user_count: int = 0) -> dict[str, Any]:
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "status": org.status,
        "webhookApiKey": org.webhook_api_key,
        "createdAt": org.created_at.isoformat() if org.created_at else None,
        "ticketCount": ticket_count,
        "userCount": user_count,
    }


def mailbox_to_dict(mb: Mailbox) -> dict[str, Any]:
    return {
        "id": mb.id,
        "emailAddress": mb.email_address,
        "displayName": mb.display_name,
        "serverType": mb.server_type,
        "incomingHost": mb.incoming_host,
        "port": mb.port,
        "incomingUsername": mb.incoming_username,
        "hasIncomingPassword": bool(mb.incoming_password),
        "incomingUseSsl": mb.incoming_use_ssl,
        "outgoingSmtpHost": mb.outgoing_smtp_host,
        "outgoingSmtpPort": mb.outgoing_smtp_port,
        "smtpUseSsl": mb.smtp_use_ssl,
        "smtpUsername": mb.smtp_username,
        "hasSmtpPassword": bool(mb.smtp_password),
        "autoDispatch": mb.auto_dispatch,
        "status": mb.status,
        "lastSyncError": mb.last_sync_error,
        "lastSyncedAt": mb.last_synced_at.isoformat() if mb.last_synced_at else None,
        "totalTicketsIngested": mb.total_tickets_ingested,
    }


def reply_to_dict(r: TicketReply) -> dict[str, Any]:
    return {
        "id": r.id,
        "sender": r.sender,
        "isAgent": r.is_agent,
        "text": r.text,
        "timestamp": r.created_at.isoformat() if r.created_at else None,
    }


def log_to_dict(l: ActivityLog) -> dict[str, Any]:
    return {
        "id": l.id,
        "timestamp": l.created_at.isoformat() if l.created_at else None,
        "actor": l.actor,
        "action": l.action,
        "details": l.details,
    }


# Substrings of ActivityLog.action that mean "the pipeline tried to notify someone and
# couldn't", or explicitly flagged itself as uncertain — surfaced to the OrgAdmin/resolver
# as a "needs attention" ticket instead of silently logged where nobody will ever read it.
_ATTENTION_ACTION_MARKERS = (
    "Failed",
    "OrgAdmin Action Needed",
    "Skipped — No Contact Email",
    "Needs Review",
)


def _compute_attention(t: Ticket) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not t.customer_email:
        reasons.append("No contact email captured — the complainant cannot be notified automatically.")

    seen_actions: set[str] = set()
    for log in getattr(t, "logs", []) or []:
        if any(marker in (log.action or "") for marker in _ATTENTION_ACTION_MARKERS):
            if log.action not in seen_actions:
                seen_actions.add(log.action)
                reasons.append(f"{log.action}: {log.details}" if log.details else log.action)

    return (bool(reasons), reasons)


def ticket_to_dict(t: Ticket) -> dict[str, Any]:
    assignee = getattr(t, "assignee", None)
    section = getattr(t, "section", None)
    needs_attention, attention_reasons = _compute_attention(t)
    return {
        "id": t.id,
        "orgId": t.org_id,
        "customerName": t.customer_name,
        "customerMobile": t.customer_mobile,
        "customerEmail": t.customer_email,
        "externalReference": t.external_reference,
        "subject": t.subject,
        "description": t.description,
        "category": t.category,
        "sectionId": t.section_id,
        "sectionName": section.name if section else None,
        "status": t.status,
        "priority": t.priority,
        "channel": t.channel,
        "confidenceScore": t.confidence_score,
        "slaBreached": t.sla_breached,
        "escalationLevel": t.escalation_level,
        "escalatedAt": t.escalated_at.isoformat() if t.escalated_at else None,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
        "dueBy": t.due_at.isoformat() if t.due_at else None,
        "resolvedAt": t.resolved_at.isoformat() if t.resolved_at else None,
        "closedAt": t.closed_at.isoformat() if t.closed_at else None,
        "assignedTo": t.assigned_to,
        "assignedToName": assignee.name if assignee else None,
        "assignedToRole": assignee.role if assignee else None,
        "aiSummary": t.ai_summary,
        "urgency": t.urgency,
        "mailboxId": t.mailbox_id,
        "awaitingCustomer": t.awaiting_customer,
        "awaitingCustomerSince": t.awaiting_customer_since.isoformat() if t.awaiting_customer_since else None,
        "needsAttention": needs_attention,
        "attentionReasons": attention_reasons,
        "activityLogs": [log_to_dict(l) for l in t.logs],
        "replies": [reply_to_dict(r) for r in t.replies],
    }


def public_ticket_to_dict(t: Ticket, org_name: str) -> dict[str, Any]:
    """Complainant-facing view via the public tracking page — deliberately excludes
    internal fields (description, ai_summary, activityLogs, assignee identity) that were
    never meant for the customer to see, showing only status + the reply thread they
    already received by email/WhatsApp."""
    return {
        "id": t.id,
        "orgName": org_name,
        "subject": t.subject,
        "category": t.category,
        "status": t.status,
        "slaBreached": t.sla_breached,
        "escalationLevel": t.escalation_level,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
        "dueBy": t.due_at.isoformat() if t.due_at else None,
        "resolvedAt": t.resolved_at.isoformat() if t.resolved_at else None,
        "closedAt": t.closed_at.isoformat() if t.closed_at else None,
        "replies": [
            {
                "fromSupport": r.is_agent,
                "text": r.text,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
            }
            for r in t.replies
        ],
    }


def org_settings_to_dict(s: OrganizationSettings) -> dict[str, Any]:
    return {
        "ticketPrefix": s.ticket_prefix,
        "autoSendReceipt": s.auto_send_receipt,
        "autoAssignResolver": s.auto_assign_resolver,
        "senderDisplayName": s.sender_display_name,
        "supportSlaHours": s.support_sla_hours,
        "enquirySlaHours": s.enquiry_sla_hours,
        "reEscalationHours": s.re_escalation_hours,
        "autoCloseAfterDays": s.auto_close_after_days,
        "smtpHost": s.smtp_host,
        "smtpPort": s.smtp_port,
        "smtpUsername": s.smtp_username,
        "hasSmtpPassword": bool(s.smtp_password),
        "smtpFromEmail": s.smtp_from_email,
        "hasGeminiKey": bool(s.gemini_api_key),
        "whatsappPhoneNumberId": s.whatsapp_phone_number_id,
        "hasWhatsappAccessToken": bool(s.whatsapp_access_token),
        "hasWhatsappAppSecret": bool(s.whatsapp_app_secret),
        "smsProvider": s.sms_provider,
        "smsApiUrl": s.sms_api_url,
        "smsSenderId": s.sms_sender_id,
        "hasSmsApiKey": bool(s.sms_api_key),
        "businessHoursEnabled": s.business_hours_enabled,
        "businessStartHour": s.business_start_hour,
        "businessEndHour": s.business_end_hour,
        "businessDays": s.business_days,
        "timezone": s.timezone,
        "holidayDates": s.holiday_dates,
    }
