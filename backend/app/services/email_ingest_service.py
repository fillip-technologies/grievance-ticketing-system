"""Real IMAP polling: turns unseen inbox mail (e.g. a Google Form "new submission"
notification) into classified complaint tickets. All imaplib calls are synchronous
and run off the event loop via `run_in_threadpool`.
"""

import contextlib
import email
import html as html_module
import imaplib
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parseaddr

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import IngestedEmail, Mailbox, Organization, Ticket
from . import gemini_service
from .ticket_service import (
    append_inbound_reply,
    create_ticket,
    find_reusable_open_ticket,
    get_active_sections,
    get_org_settings,
    resolve_section,
    sections_payload,
)


# ---------- Auto-generated mail detection ----------
# Prevents mail loops: our own ack/resolution/escalation emails bounce or trigger an
# out-of-office reply, land back in the same (or a differently-configured) inbox, and
# without this guard would be ingested as a brand-new complaint — which sends its own
# ack, which can bounce again, forever.
_AUTO_SUBJECT_RE = re.compile(
    r"(out.of.office|automatic reply|auto-?reply|undeliver|delivery status notification|"
    r"mail delivery (failed|subsystem)|returned mail|failure notice|delivery has failed|"
    r"message (blocked|not delivered)|address not found|delivery incomplete|"
    r"non-?delivery report)",
    re.IGNORECASE,
)
_BOUNCE_SENDER_RE = re.compile(
    r"^(mailer-daemon|postmaster|mail-daemon|mailer_daemon|no-?reply|do-?not-?reply|bounce[s+]?)@",
    re.IGNORECASE,
)


def _classify_automated(msg: email.message.Message, subject: str, from_addr: str, mailbox: Mailbox) -> str | None:
    """Returns a human-readable skip reason if this message looks auto-generated /
    a mail-loop risk, else None (meaning: process it as a normal complaint)."""
    auto_submitted = (msg.get("Auto-Submitted") or "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return f"Auto-Submitted: {auto_submitted}"

    precedence = (msg.get("Precedence") or "").strip().lower()
    if precedence in ("bulk", "junk", "list", "auto_reply"):
        return f"Precedence: {precedence}"

    if msg.get("X-Autoreply") or msg.get("X-Autorespond") or msg.get("X-Auto-Response-Suppress"):
        return "Auto-responder header present"

    content_type = (msg.get_content_type() or "").lower()
    if content_type in ("multipart/report", "message/delivery-status", "message/disposition-notification"):
        return f"Delivery/report content-type: {content_type}"

    own_address = (mailbox.email_address or "").strip().lower()
    if own_address and from_addr == own_address:
        return "Sender is this mailbox's own address (mail loop guard)"

    if from_addr and _BOUNCE_SENDER_RE.match(from_addr):
        return f"Bounce/no-reply sender: {from_addr}"

    if subject and _AUTO_SUBJECT_RE.search(subject):
        return f"Subject matches auto-generated pattern: {subject[:80]!r}"

    return None


def _imap_connect(mailbox: Mailbox) -> imaplib.IMAP4:
    username = mailbox.incoming_username or mailbox.smtp_username or mailbox.email_address
    password = mailbox.incoming_password or mailbox.smtp_password
    if mailbox.incoming_use_ssl:
        conn = imaplib.IMAP4_SSL(mailbox.incoming_host, mailbox.port or 993, timeout=20)
    else:
        conn = imaplib.IMAP4(mailbox.incoming_host, mailbox.port or 143, timeout=20)
        conn.starttls()
    conn.login(username, password)
    conn.select("INBOX")
    return conn


def _decode_subject(raw: str | None) -> str:
    if not raw:
        return ""
    out = []
    for text, enc in decode_header(raw):
        out.append(text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text)
    return "".join(out).strip()


def _decode_payload(part: email.message.Message) -> str:
    try:
        raw = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def _html_to_text(html_body: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_body, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_MSGID_RE = re.compile(r"<[^<>\s]+>")


def _extract_message_ids(raw: str | None) -> list[str]:
    """Parses an In-Reply-To or References header into a list of <message-id> tokens."""
    if not raw:
        return []
    return _MSGID_RE.findall(raw)


def _get_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        plain = html_part = None
        for part in msg.walk():
            if "attachment" in str(part.get("Content-Disposition") or ""):
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain" and plain is None:
                plain = _decode_payload(part)
            elif ctype == "text/html" and html_part is None:
                html_part = _decode_payload(part)
        if plain and plain.strip():
            return plain.strip()
        if html_part:
            return _html_to_text(html_part)
        return ""
    payload = _decode_payload(msg)
    return _html_to_text(payload) if msg.get_content_type() == "text/html" else payload.strip()


def _fetch_unseen_sync(mailbox: Mailbox) -> list[dict]:
    """Blocking IMAP work: connect, list UNSEEN, parse (does not mark \\Seen)."""
    messages: list[dict] = []
    conn = _imap_connect(mailbox)
    try:
        typ, data = conn.uid("search", None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return messages
        uids = data[0].split()
        for uid in uids:
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            typ, msg_data = conn.uid("fetch", uid_str, "(BODY.PEEK[])")
            if typ != "OK" or not msg_data or not msg_data[0] or not isinstance(msg_data[0], tuple):
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            message_id = (msg.get("Message-ID") or "").strip() or f"<no-id-{uid_str}-{mailbox.id}>"
            subject = _decode_subject(msg.get("Subject"))
            from_name, from_addr = parseaddr(msg.get("From") or "")
            from_addr = from_addr.strip().lower() if from_addr else ""
            thread_ids = _extract_message_ids(msg.get("In-Reply-To")) + _extract_message_ids(msg.get("References"))
            messages.append(
                {
                    "uid": uid_str,
                    "message_id": message_id,
                    "subject": subject,
                    "from_addr": from_addr,
                    "from_name": from_name.strip(),
                    "body": _get_body(msg)[:8000],
                    "thread_ids": thread_ids,
                    "skip_reason": _classify_automated(msg, subject, from_addr, mailbox),
                }
            )
    finally:
        with contextlib.suppress(Exception):
            conn.close()
        with contextlib.suppress(Exception):
            conn.logout()
    return messages


def _mark_seen_sync(mailbox: Mailbox, uids: list[str]) -> None:
    if not uids:
        return
    conn = _imap_connect(mailbox)
    try:
        for uid in uids:
            with contextlib.suppress(Exception):
                conn.uid("store", uid, "+FLAGS", "(\\Seen)")
    finally:
        with contextlib.suppress(Exception):
            conn.close()
        with contextlib.suppress(Exception):
            conn.logout()


_SUBJECT_TAG_RE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9\-]{2,63})\]")


def _extract_ticket_id_from_subject(subject: str | None) -> str | None:
    """Our outbound emails are subject-tagged '[TKT-2026-1001] ...'; a reply usually
    keeps that tag (often prefixed with 'Re:'/'Fwd:'). Returns the first bracketed token."""
    if not subject:
        return None
    match = _SUBJECT_TAG_RE.search(subject)
    return match.group(1) if match else None


async def _find_thread_ticket(db: AsyncSession, mailbox: Mailbox, m: dict) -> Ticket | None:
    """Resolves an inbound email to an existing ticket it's replying to, if any —
    first via In-Reply-To/References Message-ID lineage, then via the '[TKT-...]' subject tag.
    """
    thread_ids = m.get("thread_ids") or []
    if thread_ids:
        result = await db.execute(
            select(IngestedEmail).where(
                IngestedEmail.mailbox_id == mailbox.id,
                IngestedEmail.message_id.in_(thread_ids),
                IngestedEmail.ticket_id.isnot(None),
            )
        )
        hit = result.scalars().first()
        if hit and hit.ticket_id:
            ticket = await db.get(Ticket, hit.ticket_id)
            if ticket and ticket.org_id == mailbox.org_id:
                return ticket

    tag = _extract_ticket_id_from_subject(m.get("subject"))
    if tag:
        ticket = await db.get(Ticket, tag)
        if ticket and ticket.org_id == mailbox.org_id:
            return ticket

    return None


async def poll_mailbox(db: AsyncSession, mailbox: Mailbox) -> dict:
    if not mailbox.incoming_host or not (mailbox.incoming_password or mailbox.smtp_password):
        return {"fetched": 0, "created": 0, "error": "IMAP is not configured for this mailbox yet."}

    try:
        parsed_messages = await run_in_threadpool(_fetch_unseen_sync, mailbox)
    except Exception as exc:  # noqa: BLE001
        mailbox.status = "Error"
        mailbox.last_sync_error = str(exc)[:490]
        db.add(mailbox)
        await db.commit()
        return {"fetched": 0, "created": 0, "error": str(exc)}

    org = await db.get(Organization, mailbox.org_id)
    org_settings = await get_org_settings(db, mailbox.org_id)
    sections = await get_active_sections(db, mailbox.org_id)

    processed_uids: list[str] = []
    created_count = 0
    skipped_count = 0
    for m in parsed_messages:
        existing = await db.execute(
            select(IngestedEmail).where(
                IngestedEmail.mailbox_id == mailbox.id, IngestedEmail.message_id == m["message_id"]
            )
        )
        if existing.scalar_one_or_none():
            processed_uids.append(m["uid"])
            continue

        if m.get("skip_reason"):
            # Auto-reply / bounce / mail-loop risk — mark seen and move on without creating a
            # ticket or replying to it, but still record it so a re-poll can't reprocess it.
            db.add(IngestedEmail(mailbox_id=mailbox.id, message_id=m["message_id"], ticket_id=None))
            await db.commit()
            processed_uids.append(m["uid"])
            skipped_count += 1
            continue

        sender = m.get("from_name") or m.get("from_addr") or "Customer"
        body_text = m.get("body") or m.get("subject") or ""

        thread_ticket = await _find_thread_ticket(db, mailbox, m)
        if thread_ticket:
            await append_inbound_reply(db, thread_ticket, sender, body_text, org_settings.gemini_api_key or None)
            db.add(IngestedEmail(mailbox_id=mailbox.id, message_id=m["message_id"], ticket_id=thread_ticket.id))
            await db.commit()
            processed_uids.append(m["uid"])
            continue

        reusable_ticket = None
        if m.get("from_addr"):
            reusable_ticket = await find_reusable_open_ticket(
                db, mailbox.org_id, m["from_addr"], None, body_text, org_settings.gemini_api_key or None,
            )
        if reusable_ticket:
            await append_inbound_reply(db, reusable_ticket, sender, body_text, org_settings.gemini_api_key or None)
            db.add(IngestedEmail(mailbox_id=mailbox.id, message_id=m["message_id"], ticket_id=reusable_ticket.id))
            await db.commit()
            processed_uids.append(m["uid"])
            continue

        classification = await run_in_threadpool(
            gemini_service.process_email_message,
            m["subject"],
            m["body"],
            m["from_addr"],
            org_settings.gemini_api_key or None,
            sections_payload(sections),
        )
        category = classification["category"]
        section = await resolve_section(db, mailbox.org_id, classification.get("section"))
        data = {
            "category": category,
            "urgency": classification.get("urgency") or ("High" if category == "Support" else "Low"),
            "subject": classification.get("subject") or m["subject"] or "Email Complaint",
            "summary": classification.get("summary") or m["body"][:160],
            "confidenceScore": classification.get("confidence_score", 0.85),
            "channel": "Email",
            "message": m["body"] or m["subject"],
            "customerName": classification.get("extracted_name") or m["from_name"] or "Customer",
            "customerMobile": classification.get("extracted_mobile") or "",
            "customerEmail": classification.get("extracted_email") or m["from_addr"] or None,
            "mailboxId": mailbox.id,
            "sectionId": section.id if section else None,
        }
        try:
            ticket = await create_ticket(db, org, data)
        except Exception as exc:  # noqa: BLE001
            mailbox.last_sync_error = f"Failed to create ticket from email: {exc}"[:490]
            db.add(mailbox)
            await db.commit()
            continue

        db.add(IngestedEmail(mailbox_id=mailbox.id, message_id=m["message_id"], ticket_id=ticket.id))
        await db.commit()
        processed_uids.append(m["uid"])
        created_count += 1

    if processed_uids:
        with contextlib.suppress(Exception):
            await run_in_threadpool(_mark_seen_sync, mailbox, processed_uids)

    mailbox.last_synced_at = datetime.now(timezone.utc)
    mailbox.status = "Connected"
    mailbox.last_sync_error = ""
    db.add(mailbox)
    await db.commit()

    return {"fetched": len(parsed_messages), "created": created_count, "skipped": skipped_count}


async def poll_all_mailboxes(db: AsyncSession) -> dict:
    result = await db.execute(select(Mailbox).where(Mailbox.status == "Connected", Mailbox.auto_dispatch.is_(True)))
    mailboxes = result.scalars().all()
    totals = {"mailboxes": 0, "fetched": 0, "created": 0, "skipped": 0}
    for mb in mailboxes:
        r = await poll_mailbox(db, mb)
        totals["mailboxes"] += 1
        totals["fetched"] += r.get("fetched", 0)
        totals["skipped"] += r.get("skipped", 0)
        totals["created"] += r.get("created", 0)
    return totals
