"""Outbound SMTP: sends the acknowledgement / assignment / resolution / escalation
emails that drive the visible complaint pipeline. All network calls here are
synchronous (smtplib) — callers MUST wrap them with
`fastapi.concurrency.run_in_threadpool` so they don't block the event loop.
"""

import html as html_module
import re
import smtplib
import ssl
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import Any

from ..config import get_settings

settings = get_settings()


class SmtpConfig:
    def __init__(self, host: str, port: int, username: str, password: str, from_email: str, use_ssl: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_ssl = use_ssl

    @property
    def configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.from_email)


def from_org_settings(org_settings: Any) -> SmtpConfig:
    """Org SMTP settings, falling back field-by-field to the platform .env SMTP account."""
    port = org_settings.smtp_port or settings.smtp_port
    return SmtpConfig(
        host=org_settings.smtp_host or settings.smtp_host,
        port=port,
        username=org_settings.smtp_username or settings.smtp_username,
        password=org_settings.smtp_password or settings.smtp_password,
        from_email=org_settings.smtp_from_email or org_settings.smtp_username or settings.smtp_from_email,
        use_ssl=(port == 465) if port else settings.smtp_ssl,
    )


def from_mailbox(mailbox: Any) -> SmtpConfig:
    host = mailbox.outgoing_smtp_host or mailbox.incoming_host or settings.smtp_host
    port = mailbox.outgoing_smtp_port or settings.smtp_port
    return SmtpConfig(
        host=host,
        port=port,
        username=mailbox.smtp_username or settings.smtp_username,
        password=mailbox.smtp_password or settings.smtp_password,
        from_email=mailbox.email_address or settings.smtp_from_email,
        use_ssl=mailbox.smtp_use_ssl if mailbox.smtp_use_ssl is not None else (port == 465),
    )


def _connect(cfg: SmtpConfig) -> smtplib.SMTP:
    if cfg.use_ssl or cfg.port == 465:
        server = smtplib.SMTP_SSL(cfg.host, cfg.port, context=ssl.create_default_context(), timeout=20)
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=20)
        server.starttls(context=ssl.create_default_context())
    server.login(cfg.username, cfg.password)
    return server


def verify_smtp(cfg: SmtpConfig) -> dict:
    import time

    if not cfg.configured:
        return {
            "success": False,
            "message": "SMTP is not configured. Set host/username/password/from-email first.",
            "config": False,
        }

    start = time.monotonic()
    try:
        server = _connect(cfg)
        server.quit()
        latency = int((time.monotonic() - start) * 1000)
        return {
            "success": True,
            "message": f"250 {cfg.host} ESMTP - Outgoing SMTP Server Ready & Authenticated",
            "smtpServer": f"{cfg.host}:{cfg.port}",
            "protocol": "SMTPS (SSL/TLS)" if cfg.use_ssl or cfg.port == 465 else "SMTP (STARTTLS)",
            "authenticatedUser": cfg.username,
            "latencyMs": latency,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": f"SMTP Handshake/Auth failed: {exc}"}


def send_email(cfg: SmtpConfig, to_email: str, subject: str, html_body: str, from_display: str = "Support Team") -> dict:
    # `retryable` distinguishes "will never succeed until an admin fixes something" (missing
    # config, no recipient) from "might succeed on its own next time" (network blip, SMTP
    # server hiccup) — used by notification_retry_service to decide what's worth re-queuing.
    if not cfg.configured:
        return {
            "success": False, "retryable": False,
            "message": "SMTP is not configured for this organization; email was not sent (ticket still saved).",
        }
    if not to_email:
        return {"success": False, "retryable": False, "message": "No recipient email address on file."}

    # multipart/alternative: a plain-text fallback (auto-derived from our own HTML template)
    # plus the styled HTML part — mail clients that can't/won't render HTML fall back cleanly.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((from_display, cfg.from_email))
    msg["To"] = to_email
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText(html_to_text(html_body), "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = _connect(cfg)
        server.sendmail(cfg.from_email, [to_email], msg.as_string())
        server.quit()
        return {"success": True, "message": "250 2.0.0 OK Message queued and dispatched successfully", "sentTo": to_email}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "retryable": True, "message": f"Failed to dispatch via SMTP: {exc}"}


def _fmt_due(due_by: str | None) -> str:
    if not due_by:
        return ""
    try:
        dt = datetime.fromisoformat(due_by.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %I:%M %p UTC")
    except ValueError:
        return ""


def _fmt_hours_label(hours: int | float | None) -> str:
    if not hours and hours != 0:
        return "the target window"
    hours = int(hours)
    if hours <= 0:
        return "the target window"
    if hours == 1:
        return "1 Hour"
    if hours % 24 == 0:
        days = hours // 24
        return f"{days} Day{'s' if days != 1 else ''}"
    return f"{hours} Hours"


def ticket_portal_url(ticket_number: str) -> str:
    """Deep link into the SPA that opens this ticket directly (App.jsx reads ?ticket=). For
    internal recipients only (resolver/escalation authority/org admin), who are logged in —
    see public_tracker_url() for the customer-facing equivalent."""
    base = settings.frontend_url.rstrip("/")
    return f"{base}/?ticket={ticket_number}"


def public_tracker_url() -> str:
    """The unauthenticated /track page customers use to check status by Ticket ID + contact.
    Used for every customer-facing "Track This Ticket" button — customers have no login, so
    ticket_portal_url()'s ?ticket= deep link (which requires an authenticated session) would
    just land them on the login screen."""
    return settings.public_tracker_url


# ---------- HTML email shell ----------
# All templates below render through this shared shell so every outbound email looks like one
# consistent, professional system rather than ad-hoc plain text. `send_email()` auto-derives a
# plain-text fallback from the HTML via `html_to_text()`, so no template needs a separate
# plain-text version.

def _esc(value: Any) -> str:
    return html_module.escape(str(value if value is not None else ""), quote=True)


def _email_shell(brand_name: str, heading: str, body_html: str, accent: str = "#4f46e5") -> str:
    brand = _esc(brand_name or "Support Team")
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<title>{_esc(heading)}</title></head>'
        '<body style="margin:0;padding:0;background-color:#f1f5f9;'
        'font-family:Segoe UI,Helvetica,Arial,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#f1f5f9;padding:24px 12px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;'
        'overflow:hidden;border:1px solid #e2e8f0;">'
        f'<tr><td style="background-color:{accent};padding:20px 28px;">'
        f'<span style="color:#ffffff;font-size:16px;font-weight:700;letter-spacing:0.2px;">{brand}</span>'
        '</td></tr>'
        '<tr><td style="padding:28px;">'
        f'<h1 style="margin:0 0 16px 0;font-size:17px;color:#0f172a;line-height:1.4;">{_esc(heading)}</h1>'
        f'<div style="font-size:14px;line-height:1.65;color:#1e293b;">{body_html}</div>'
        '</td></tr>'
        '<tr><td style="padding:16px 28px;background-color:#f8fafc;border-top:1px solid #e2e8f0;">'
        f'<p style="margin:0;font-size:11px;color:#94a3b8;">This is an automated message from {brand}. '
        'Please avoid replying directly unless instructed above.</p>'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _info_box(rows: list[tuple[str, str]]) -> str:
    trs = "".join(
        '<tr>'
        f'<td style="padding:6px 0;color:#64748b;font-size:12px;width:40%;vertical-align:top;">{_esc(k)}</td>'
        f'<td style="padding:6px 0;color:#0f172a;font-size:13px;font-weight:600;">{_esc(v)}</td>'
        '</tr>'
        for k, v in rows
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
        f'padding:4px 16px;margin:16px 0;">{trs}</table>'
    )


def _button(url: str, label: str, accent: str = "#4f46e5") -> str:
    return (
        '<p style="margin:20px 0 4px 0;">'
        f'<a href="{_esc(url)}" style="display:inline-block;background-color:{accent};color:#ffffff;'
        'text-decoration:none;padding:10px 22px;border-radius:8px;font-size:13px;font-weight:600;">'
        f'{_esc(label)}</a></p>'
    )


def _p(text: str) -> str:
    return f'<p style="margin:0 0 14px 0;">{text}</p>'


def html_to_text(html_body: str) -> str:
    """Best-effort tag-stripper producing a readable plain-text rendition of our own simple
    HTML email templates. Used for (a) the multipart/alternative text/plain fallback part and
    (b) the copy stored in TicketReply/ActivityLog, so the in-app ticket thread and the public
    tracker never show raw HTML markup."""
    text = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", html_body)
    text = re.sub(r"(?i)<a\s[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", r"\2 (\1)", text)
    text = re.sub(r"(?is)</td>\s*<td[^>]*>", ": ", text)  # "label" + ": " + "value" on one line
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|h1|h2|h3|table)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    out: list[str] = []
    blank_run = 0
    for ln in lines:
        if ln == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        out.append(ln)
    return "\n".join(out).strip()


# ---------- Email templates ----------

def build_thank_you_email(
    ticket_number: str, customer_name: str, category: str, subject: str, summary: str | None,
    due_by: str | None, sla_hours: int | None, brand_name: str,
) -> str:
    """Stage A — sent immediately when a ticket is created, regardless of whether/when it
    gets assigned to a resolver. Confirms receipt and gives tracking info without claiming
    anyone is already working on it (see build_assignment_ack_email for that)."""
    due_hours_label = _fmt_hours_label(sla_hours)
    fmt = _fmt_due(due_by)
    body = (
        _p(f"Hello {_esc(customer_name or 'there')},")
        + _p("Thank you for reaching out to us. We have received your request and it has been logged.")
        + _info_box([
            ("Ticket ID", ticket_number),
            ("Category", category),
            ("Subject", subject),
            ("Target response window", f"Within {due_hours_label}" + (f" (by {fmt})" if fmt else "")),
        ])
        + _p("We will keep you informed as we work on this.")
        + _p(f"Please use Ticket ID <strong>{_esc(ticket_number)}</strong> in any further correspondence.")
    )
    return _email_shell(brand_name, "We've received your request", body)


def build_assignment_ack_email(
    ticket_number: str, customer_name: str, category: str, subject: str, due_by: str | None,
    sla_hours: int | None, brand_name: str,
) -> str:
    """Stage B — sent the moment a resolver is actually assigned to the ticket (either
    immediately at creation, if auto-assignment is on, or later when an OrgAdmin manually
    assigns one). Deliberately does not name the resolver to the customer."""
    due_hours_label = _fmt_hours_label(sla_hours)
    fmt = _fmt_due(due_by)
    portal_url = public_tracker_url()
    body = (
        _p(f"Hello {_esc(customer_name or 'there')},")
        + _p(
            f"Good news — your request (Ticket ID: <strong>{_esc(ticket_number)}</strong>) "
            "is now being looked after by a member of our support team."
        )
        + _info_box([
            ("Ticket ID", ticket_number),
            ("Subject", subject),
            ("Target resolution window", f"Within {due_hours_label}" + (f" (by {fmt})" if fmt else "")),
        ])
        + _p("We will keep you informed as we work towards a resolution.")
        + _button(portal_url, "Track This Ticket")
        + _p("Thank you for your patience.")
    )
    return _email_shell(brand_name, "Your request is now being handled", body)


def build_resolver_assignment_email(
    ticket_number: str, resolver_name: str, customer_name: str, category: str, subject: str,
    description: str, summary: str | None, urgency: str, due_by: str | None, brand_name: str,
) -> str:
    fmt = _fmt_due(due_by)
    portal_url = ticket_portal_url(ticket_number)
    body = (
        _p(f"Hello {_esc(resolver_name)},")
        + _p(f"A new <strong>{_esc(category)}</strong> ticket has been assigned to you.")
        + _info_box([
            ("Ticket ID", ticket_number),
            ("Customer", customer_name),
            ("Subject", subject),
            ("Urgency", urgency),
            ("SLA due by", fmt or "N/A"),
        ])
        + _p(f"<strong>AI Summary:</strong> {_esc(summary or subject)}")
        + _p(f"<strong>Full message:</strong><br>{_esc(description).replace(chr(10), '<br>')}")
        + _button(portal_url, "Open This Ticket")
        + _p(
            "Move it to “In Progress” and resolve it before the SLA window closes — after that it "
            "will auto-escalate to the Escalation Authority."
        )
    )
    return _email_shell(brand_name, "New ticket assigned to you", body)


def build_resolved_email(
    ticket_number: str, customer_name: str, subject: str, brand_name: str,
    auto_close_days: int | None = None,
) -> str:
    grace_note = (
        _p(
            f"If this resolves your issue, no action is needed. We'll automatically close this ticket in "
            f"{_esc(auto_close_days)} day{'s' if auto_close_days != 1 else ''} if we don't hear back."
        )
        if auto_close_days
        else ""
    )
    portal_url = public_tracker_url()
    body = (
        _p(f"Hello {_esc(customer_name or 'there')},")
        + _p(
            f"We're writing to confirm that your complaint (Ticket ID: <strong>{_esc(ticket_number)}</strong>) "
            f"regarding “{_esc(subject)}” has been marked <strong>Resolved</strong> by our team."
        )
        + grace_note
        + _p(
            f"If it's not fixed, just reply to this email or use Ticket ID "
            f"<strong>{_esc(ticket_number)}</strong> and we'll reopen it for review."
        )
        + _button(portal_url, "View Ticket History")
        + _p("Thank you for your patience.")
    )
    return _email_shell(brand_name, "Your complaint has been resolved", body, accent="#059669")


def build_closed_email(ticket_number: str, customer_name: str, subject: str, reason: str, brand_name: str) -> str:
    """Short closing acknowledgement, reused for all three closing paths: customer-confirmed,
    auto-closed after the grace period, and admin-closed. `reason` is a short plain-English
    clause describing which one, e.g. "the customer confirmed the issue is resolved"."""
    portal_url = public_tracker_url()
    body = (
        _p(f"Hello {_esc(customer_name or 'there')},")
        + _p(
            f"Your complaint (Ticket ID: <strong>{_esc(ticket_number)}</strong>) regarding "
            f"“{_esc(subject)}” has now been <strong>Closed</strong>, since {_esc(reason)}."
        )
        + _p(
            f"If you need anything further, just reply referencing Ticket ID "
            f"<strong>{_esc(ticket_number)}</strong> and we'll take another look."
        )
        + _button(portal_url, "View Ticket History")
        + _p("Thank you for your patience.")
    )
    return _email_shell(brand_name, "Your ticket has been closed", body, accent="#64748b")


def build_escalation_customer_email(
    ticket_number: str, customer_name: str, subject: str, brand_name: str, is_re_escalation: bool = False,
    authority_assigned: bool = True,
) -> str:
    """`authority_assigned=False` means no EscalationAuthority is configured at the target tier —
    the wording must not claim a specific senior person is reviewing it when nobody has been notified.
    """
    portal_url = public_tracker_url()
    greeting = _p(f"Hello {_esc(customer_name or 'there')},")
    closing = (
        _p(
            f"We sincerely apologize for the delay. You'll receive another update as soon as it's resolved — "
            f"please use Ticket ID <strong>{_esc(ticket_number)}</strong> in any follow-up."
        )
        + _button(portal_url, "Track This Ticket")
        + _p("Thank you for your patience.")
    )
    if not authority_assigned:
        heading = "Your complaint is taking longer than expected"
        opening = _p(
            f"Your complaint (Ticket ID: <strong>{_esc(ticket_number)}</strong>) regarding "
            f"“{_esc(subject)}” has passed our target resolution window. It has been flagged "
            "internally for priority follow-up and our team has been notified to expedite it."
        )
    elif is_re_escalation:
        heading = "Your complaint has been escalated further"
        opening = _p(
            f"Your complaint (Ticket ID: <strong>{_esc(ticket_number)}</strong>) regarding "
            f"“{_esc(subject)}” remains unresolved, so it has now been escalated to a more senior "
            "authority on our team for immediate attention."
        )
    else:
        heading = "Your complaint has been escalated"
        opening = _p(
            f"We were unable to resolve your complaint (Ticket ID: <strong>{_esc(ticket_number)}</strong>) "
            f"regarding “{_esc(subject)}” within our target resolution window. To ensure it gets the "
            "attention it needs, it has been escalated to a senior authority on our team."
        )
    return _email_shell(brand_name, heading, greeting + opening + closing, accent="#dc2626")


def build_escalation_authority_email(
    ticket_number: str, customer_name: str, category: str, subject: str, summary: str | None,
    description: str, original_due_by: str | None, brand_name: str,
) -> str:
    fmt = _fmt_due(original_due_by)
    portal_url = ticket_portal_url(ticket_number)
    body = (
        _p(
            f"The following <strong>{_esc(category)}</strong> ticket has breached its SLA window (originally "
            f"due {_esc(fmt or 'earlier')}) and has been escalated to you for immediate attention."
        )
        + _info_box([
            ("Ticket ID", ticket_number),
            ("Customer", customer_name),
            ("Subject", subject),
        ])
        + _p(f"<strong>AI Summary:</strong> {_esc(summary or subject)}")
        + _p(f"<strong>Full message:</strong><br>{_esc(description).replace(chr(10), '<br>')}")
        + _button(portal_url, "Open This Ticket")
        + _p(
            "Please resolve it as a priority. The customer has already been notified that their complaint was "
            "escalated to you."
        )
    )
    return _email_shell(brand_name, "SLA breach — ticket escalated to you", body, accent="#dc2626")


def build_sla_warning_email(
    ticket_number: str, resolver_name: str, subject: str, due_by: str | None, remaining_label: str, brand_name: str,
) -> str:
    fmt = _fmt_due(due_by)
    portal_url = ticket_portal_url(ticket_number)
    body = (
        _p(f"Hello {_esc(resolver_name)},")
        + _p(
            f"Ticket <strong>{_esc(ticket_number)}</strong> (“{_esc(subject)}”) is approaching its "
            f"SLA deadline — about <strong>{_esc(remaining_label)}</strong> remaining"
            + (f" (due {_esc(fmt)})" if fmt else "") + "."
        )
        + _button(portal_url, "Open This Ticket", accent="#d97706")
        + _p("Resolve it before the window closes to avoid an automatic escalation.")
    )
    return _email_shell(brand_name, "SLA deadline approaching", body, accent="#d97706")


def build_admin_alert_email(org_name: str, ticket_number: str, subject: str, reason: str, brand_name: str) -> str:
    """Sent to active OrgAdmins when the pipeline can't fully do its job on a ticket
    (e.g. no Escalation Authority configured at the tier it needs) so a human notices."""
    portal_url = ticket_portal_url(ticket_number)
    body = (
        _p(f"Ticket <strong>{_esc(ticket_number)}</strong> (“{_esc(subject)}”) needs configuration attention:")
        + _p(_esc(reason))
        + _button(portal_url, "Open This Ticket", accent="#d97706")
        + _p(
            "Add or activate the required team member in Team Management so future escalations reach a real "
            "person automatically."
        )
    )
    return _email_shell(brand_name, f"Action needed — {org_name}", body, accent="#d97706")


def build_test_receipt_email(brand_name: str) -> str:
    body = _p(f"This is a test receipt dispatched from {_esc(brand_name)} to verify outgoing SMTP delivery.")
    return _email_shell(brand_name, "SMTP Test Receipt", body)


def build_team_invite_email(name: str, org_name: str, role: str, email: str, temp_password: str, brand_name: str) -> str:
    body = (
        _p(f"Hello {_esc(name)},")
        + _p(f"You've been added as a <strong>{_esc(role)}</strong> on the {_esc(org_name)} workspace.")
        + _info_box([
            ("Login email", email),
            ("Temporary password", temp_password),
        ])
        + _p(
            "Please log in and change your password as soon as possible. Tickets assigned to you will appear "
            "in your queue automatically."
        )
    )
    return _email_shell(brand_name, f"Welcome to {org_name}", body)


# NOTE: the WhatsApp message templates used to live here as `build_whatsapp_auto_reply`.
# They now live in `whatsapp_service.py` (build_ack_message / build_resolved_message /
# build_escalated_message) alongside the code that actually dispatches them via the
# Meta Cloud API, instead of being built here and never sent.
