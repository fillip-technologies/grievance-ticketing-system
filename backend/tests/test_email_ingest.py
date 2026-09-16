"""Mail-loop / bounce / auto-reply detection — pure function, no DB needed."""

import email

from app.models import Mailbox
from app.services.email_ingest_service import _classify_automated


def _mailbox(address="support@rajgirsafari.com"):
    return Mailbox(email_address=address)


def _parse(raw: str):
    return email.message_from_string(raw)


def test_genuine_complaint_is_not_flagged():
    msg = _parse("From: user@gmail.com\nSubject: Money deducted but no ticket\n\nPaid but got nothing.")
    assert _classify_automated(msg, "Money deducted but no ticket", "user@gmail.com", _mailbox()) is None


def test_out_of_office_reply_is_flagged():
    msg = _parse("From: user@gmail.com\nSubject: Automatic reply: Out of Office\n\nAway until Monday.")
    reason = _classify_automated(msg, "Automatic reply: Out of Office", "user@gmail.com", _mailbox())
    assert reason is not None


def test_mailer_daemon_bounce_is_flagged():
    msg = _parse("From: mailer-daemon@gmail.com\nSubject: Delivery Status Notification (Failure)\n\nbounce")
    reason = _classify_automated(msg, "Delivery Status Notification (Failure)", "mailer-daemon@gmail.com", _mailbox())
    assert reason is not None


def test_self_loop_is_flagged():
    """Our own outbound ack landing back in the same inbox must never spawn a new ticket."""
    mb = _mailbox("support@rajgirsafari.com")
    msg = _parse("From: support@rajgirsafari.com\nSubject: [TKT-2026-1001] Complaint Registered\n\nack body")
    reason = _classify_automated(msg, "[TKT-2026-1001] Complaint Registered", "support@rajgirsafari.com", mb)
    assert reason is not None


def test_auto_submitted_header_is_flagged():
    msg = _parse("From: user@gmail.com\nSubject: Re: your ticket\nAuto-Submitted: auto-replied\n\nbody")
    reason = _classify_automated(msg, "Re: your ticket", "user@gmail.com", _mailbox())
    assert reason is not None


def test_precedence_bulk_is_flagged():
    msg = _parse("From: newsletter@example.com\nSubject: Weekly Digest\nPrecedence: bulk\n\nbody")
    reason = _classify_automated(msg, "Weekly Digest", "newsletter@example.com", _mailbox())
    assert reason is not None


def test_extract_ticket_id_from_subject_tag():
    from app.services.email_ingest_service import _extract_ticket_id_from_subject
    assert _extract_ticket_id_from_subject("Re: [TKT-2026-1042] Still broken") == "TKT-2026-1042"
    assert _extract_ticket_id_from_subject("No tag here") is None
