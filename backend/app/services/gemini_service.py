import json
import re

from ..config import get_settings

settings = get_settings()

GRIEVANCE_KEYWORDS = (
    "issue", "broken", "failed", "fail", "complaint", "error",
    "not working", "deducted", "refund", "urgent", "outage", "down",
    "offline", "breach", "delay", "crash", "bug", "unable to", "not received",
    "missing", "problem", "wrong", "damaged", "cancel",
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9.\-_+]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{8,}\d)")
NAME_LABEL_RE = re.compile(r"(?:name|full name|customer name)\s*[:\-]\s*([A-Za-z][A-Za-z .'-]{1,60})", re.IGNORECASE)


def _extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text or "")
    return match.group(0) if match else None


def _extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text or "")
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return match.group(0).strip() if 8 <= len(digits) <= 15 else None


def _extract_name(text: str) -> str | None:
    match = NAME_LABEL_RE.search(text or "")
    return match.group(1).strip() if match else None


def _is_grievance(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in GRIEVANCE_KEYWORDS)


_STOPWORDS = {
    "that", "this", "with", "from", "your", "have", "will", "about", "into", "their", "them",
    "which", "there", "when", "what", "would", "could", "should", "please", "regarding", "related",
}


def _match_section(msg: str, sections: list[dict] | None) -> str | None:
    """Best-effort keyword overlap between the message and each section's name/description —
    used by the no-API-key fallback path. Requires at least one real hit (the section name
    itself, or a description word) so an org with vague/empty descriptions doesn't get
    everything misrouted to whichever section happens to share a common word."""
    if not sections:
        return None
    lower = msg.lower()
    best_name, best_score = None, 0
    for sec in sections:
        name = (sec.get("name") or "").strip()
        if not name:
            continue
        desc = sec.get("description") or ""
        keywords = {name.lower()} | {
            w for w in re.findall(r"[a-zA-Z]{4,}", desc.lower()) if w not in _STOPWORDS
        }
        score = sum(1 for k in keywords if k in lower)
        if score > best_score:
            best_score, best_name = score, name
    return best_name


def rule_based_classification(
    msg: str,
    reason: str = "Fallback Engine",
    name: str | None = None,
    mobile: str | None = None,
    email: str | None = None,
    sections: list[dict] | None = None,
) -> dict:
    """No-API-key fallback: keyword classification + best-effort regex field extraction
    so the platform still produces usable tickets from real inbound email/WhatsApp text.
    """
    has_signal = _is_grievance(msg)
    category = "Support" if has_signal else "Enquiry"
    first_line = (msg.splitlines()[0] if msg.splitlines() else msg)[:80].strip()
    # A keyword hit is a real (if crude) signal; "no keyword matched" is not evidence this
    # is actually an Enquiry — it's just the fallback's default when it has nothing to go
    # on, and should read as genuinely low-confidence so it gets a human review flag
    # instead of silently posing as a normal 72%-confidence classification.
    confidence = 0.72 if has_signal else 0.45
    return {
        "category": category,
        "confidence_score": confidence,
        "subject": first_line or (f"{category} Ticket"),
        "summary": (msg[:160] + ("..." if len(msg) > 160 else "")).strip(),
        "urgency": "High" if category == "Support" else "Low",
        "extracted_name": name or _extract_name(msg),
        "extracted_mobile": mobile or _extract_phone(msg),
        "extracted_email": email or _extract_email(msg),
        "section": _match_section(msg, sections),
        "note": f"Processed via {reason} (no Gemini API key configured — using keyword/regex rules)",
    }


def _make_client(api_key: str | None = None):
    from google import genai  # lazy import to keep startup fast

    key = (api_key or "").strip() or settings.gemini_api_key
    if not key:
        return None
    return genai.Client(api_key=key)


def _gemini_json(client, model: str, contents: str, system_instruction: str) -> dict | None:
    if client is None:
        return None
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
            },
        )
        raw = (response.text or "").strip()
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"[gemini] {model} call failed: {exc}")
        return None


def _normalize_category(value) -> str:
    s = str(value or "").lower()
    if "enquir" in s or "inquir" in s:
        return "Enquiry"
    return "Support"


def _normalize_confidence(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.92
    if v <= 0:
        return 0.92
    if v > 1:
        v = v / 100.0
    return round(v, 2)


CLASSIFY_SYSTEM_PROMPT = (
    'You are a complaint-intake routing assistant for a customer support desk. Analyze this message '
    '(which may be a raw email, a website form notification, or a chat message) and categorize its primary '
    'intent as exactly "Support" (issues, bugs, grievances, payment problems) or "Enquiry" (general info, '
    'pricing, partnership). Extract the actual complainant/customer\'s name, email address, and phone number '
    'from the message body if present (for form-notification emails, extract the values the customer typed '
    'into the form, not the sender of the notification). Respond strictly with a JSON object with keys: '
    '"category", "confidence_score" (0-1), "subject" (a short human-readable subject line), "summary" '
    '(1-2 sentence summary), "urgency" ("Low"|"Medium"|"High"|"Critical"), "extracted_name", '
    '"extracted_mobile", "extracted_email".'
)


def _build_classify_prompt(sections: list[dict] | None) -> str:
    if not sections:
        return CLASSIFY_SYSTEM_PROMPT
    section_lines = "\n".join(f'- "{s["name"]}": {s.get("description") or "no description given"}' for s in sections)
    return (
        CLASSIFY_SYSTEM_PROMPT
        + "\n\nThis organization has also defined the following custom routing sections, each handled by its "
        "own dedicated team, in addition to the general Support/Enquiry categorization above:\n"
        f"{section_lines}\n\n"
        'If the message clearly falls within one of these sections\' stated scope, add a "section" key to '
        'your JSON response set to that section\'s exact name as given above. If it does not clearly match '
        'any of them, set "section" to null. Still classify "category" as Support or Enquiry as usual '
        "regardless of whether a section matched."
    )


def _normalize_section(value, sections: list[dict] | None) -> str | None:
    """Only trust a section name Gemini was actually offered — never let a hallucinated or
    since-renamed section name flow through to a DB lookup."""
    if not value or not sections:
        return None
    value = str(value).strip().lower()
    for sec in sections:
        if (sec.get("name") or "").strip().lower() == value:
            return sec["name"]
    return None


def _run_classification(
    message: str, api_key: str | None, reason: str, name: str | None = None, mobile: str | None = None,
    email: str | None = None, sections: list[dict] | None = None,
) -> dict:
    client = _make_client(api_key)
    parsed = (
        _gemini_json(client, settings.gemini_model, f'Message:\n"""\n{message.strip()}\n"""', _build_classify_prompt(sections))
        if client else None
    )

    if not parsed:
        return rule_based_classification(message, reason, name=name, mobile=mobile, email=email, sections=sections)

    category = _normalize_category(parsed.get("category"))
    return {
        "category": category,
        "confidence_score": _normalize_confidence(parsed.get("confidence_score")),
        "subject": (parsed.get("subject") or "").strip() or None,
        "summary": (parsed.get("summary") or "").strip() or None,
        "urgency": str(parsed.get("urgency") or ("High" if category == "Support" else "Low")),
        "extracted_name": parsed.get("extracted_name") or name or None,
        "extracted_mobile": parsed.get("extracted_mobile") or mobile or _extract_phone(message),
        "extracted_email": parsed.get("extracted_email") or email or _extract_email(message),
        "section": _normalize_section(parsed.get("section"), sections),
        "note": "Processed via Gemini AI",
    }


def classify_intent(
    message: str, api_key: str | None = None, customer_email: str | None = None, sections: list[dict] | None = None,
) -> dict:
    return _run_classification(message, api_key, "Missing API Key / Rule Engine", email=customer_email, sections=sections)


def process_email_message(
    subject: str, body: str, from_addr: str | None, api_key: str | None = None, sections: list[dict] | None = None,
) -> dict:
    """Classification entry point for real IMAP-ingested emails (subject + body combined)."""
    combined = f"Subject: {subject}\n\n{body}".strip()
    result = _run_classification(combined, api_key, "Fallback Email Engine", email=from_addr, sections=sections)
    if not result.get("subject"):
        result["subject"] = subject[:120] or "Email Complaint"
    return result


def process_whatsapp_message(
    message: str, customer_name: str = "", customer_mobile: str = "", api_key: str | None = None,
    sections: list[dict] | None = None,
) -> dict:
    return _run_classification(
        message, api_key, "Fallback WhatsApp Engine", name=customer_name or None, mobile=customer_mobile or None,
        sections=sections,
    )


def voice_command(transcript: str, current_tab: str = "dashboard", api_key: str | None = None) -> dict:
    client = _make_client(api_key)
    if client is None:
        return {"action": "UNKNOWN", "spokenResponseHindi": "वॉइस कमांड इंजन कॉन्फ़िगर नहीं है।", "spokenResponseEnglish": "Voice command engine not configured."}

    prompt = (
        'You are the AI Voice Assistant for "Grievance Desk", a complaint-resolution dashboard.\n'
        f'User Transcript: "{transcript}"\n'
        f'Current Dashboard Tab: "{current_tab or "dashboard"}"\n'
        "Parse the command into JSON dashboard actions. Actions: NAVIGATE, FILTER_CATEGORY, "
        "FILTER_STATUS, SEARCH, RESET_FILTERS, TOGGLE_SLA, DOWNLOAD_CSV, UNKNOWN.\n"
        'Return ONLY valid JSON: {"action": "...", "tab": "dashboard|analytics|channels|settings|team", '
        '"category": "Support|Enquiry|All", "status": "Open|In Progress|Escalated|Resolved|All", '
        '"searchQuery": string|null, "spokenResponseHindi": "...", "spokenResponseEnglish": "..."}'
    )

    parsed = None
    try:
        response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        raw = (response.text or "").strip()
        raw = re.sub(r"```json", "", raw)
        raw = re.sub(r"```", "", raw).strip()
        parsed = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"[gemini] voice command failed: {exc}")

    if not parsed or not parsed.get("action"):
        return {"action": "UNKNOWN", "spokenResponseHindi": "क्षमा करें, कमांड समझ नहीं आई।", "spokenResponseEnglish": "Sorry, command not recognized."}

    parsed["spokenResponseHindi"] = parsed.get("spokenResponseHindi") or ""
    parsed["spokenResponseEnglish"] = parsed.get("spokenResponseEnglish") or ""
    return parsed


def _fallback_reply(customer_name: str, category: str, subject: str) -> str:
    """No-API-key / call-failed fallback: a generic but genuinely usable draft, not a
    placeholder — the resolver edits it before sending either way."""
    return (
        f"Dear {customer_name or 'Valued Customer'},\n\n"
        f"Thank you for reaching out about \"{subject}\". We've reviewed your {category.lower()} "
        "and our team is actively working on it.\n\n"
        "[Add the specific update or resolution here before sending.]\n\n"
        "Please let us know if you have any further questions.\n\n"
        "Regards,\nSupport Team"
    )


SUGGEST_REPLY_SYSTEM_PROMPT = (
    "You are a customer support agent drafting a reply to a customer complaint/enquiry. Write a "
    "professional, empathetic, concise reply (3-6 sentences) addressing their specific issue using the "
    "ticket details given. Do not invent facts not present in the ticket (no promised dates, refund amounts, "
    "or outcomes that aren't stated) — if a concrete resolution isn't known, say the team is actively working "
    "on it. Respond with plain text only, no markdown, no subject line, ready to send as-is."
)


def suggest_reply(
    customer_name: str, category: str, subject: str, description: str, ai_summary: str | None,
    prior_replies: list[str] | None = None, api_key: str | None = None,
) -> dict:
    """Drafts a reply for a resolver to review/edit before sending — never sent automatically."""
    client = _make_client(api_key)
    if client is None:
        return {"reply": _fallback_reply(customer_name, category, subject), "source": "Fallback Template (no Gemini key)"}

    thread = "\n".join(f"- {r}" for r in (prior_replies or [])[-5:]) or "(no prior replies yet)"
    prompt = (
        f"Customer: {customer_name}\nCategory: {category}\nSubject: {subject}\n"
        f"Original message: {description}\nAI summary: {ai_summary or subject}\n"
        f"Recent reply thread:\n{thread}\n\nDraft the next reply to the customer."
    )
    try:
        response = client.models.generate_content(
            model=settings.gemini_model, contents=prompt,
            config={"system_instruction": SUGGEST_REPLY_SYSTEM_PROMPT},
        )
        text = (response.text or "").strip()
        if text:
            return {"reply": text, "source": "Gemini AI"}
    except Exception as exc:  # noqa: BLE001
        print(f"[gemini] suggest_reply failed: {exc}")

    return {"reply": _fallback_reply(customer_name, category, subject), "source": "Fallback Template (Gemini call failed)"}


_CONFIRM_KEYWORDS = (
    "thanks", "thank you", "resolved", "fixed", "works now", "working now", "all good",
    "sorted", "solved", "appreciate", "great", "perfect", "no further issue", "closed",
)
_DENY_KEYWORDS = (
    "still not", "still broken", "still doesn't", "still does not", "not fixed", "not resolved",
    "same issue", "same problem", "didn't work", "did not work", "doesn't work", "does not work",
    "reopen", "worse", "again",
)


def _rule_based_resolution_reply(message: str) -> dict:
    lower = (message or "").lower()
    if any(k in lower for k in _DENY_KEYWORDS):
        return {"confirms_resolved": False, "confidence": 0.6}
    if any(k in lower for k in _CONFIRM_KEYWORDS):
        return {"confirms_resolved": True, "confidence": 0.6}
    return {"confirms_resolved": None, "confidence": 0.4}


RESOLUTION_REPLY_SYSTEM_PROMPT = (
    "You are triaging a customer's reply to a support ticket that was just marked Resolved. Decide whether "
    "the customer's reply clearly CONFIRMS the issue is fixed, clearly DENIES it (still broken/unresolved), "
    "or is AMBIGUOUS/unrelated to resolution status. Respond strictly with a JSON object: "
    '{"confirms_resolved": true|false|null, "confidence": 0-1}. Use null for confirms_resolved when the '
    "reply doesn't clearly confirm or deny (e.g. a new unrelated question, or genuinely unclear wording)."
)


def classify_resolution_reply(
    message: str, ticket_subject: str, ticket_summary: str | None, api_key: str | None = None,
) -> dict:
    """Used when a customer replies to a ticket that's currently Resolved: does the reply
    confirm the fix, deny it, or is it ambiguous? Ambiguous/deny both reopen the ticket —
    only a clear confirmation closes it. See ticket_service.append_inbound_reply."""
    client = _make_client(api_key)
    contents = (
        f"Ticket subject: {ticket_subject}\nTicket summary: {ticket_summary or ticket_subject}\n\n"
        f'Customer reply:\n"""\n{(message or "").strip()}\n"""'
    )
    parsed = _gemini_json(client, settings.gemini_model, contents, RESOLUTION_REPLY_SYSTEM_PROMPT) if client else None
    if not parsed or "confirms_resolved" not in parsed:
        return _rule_based_resolution_reply(message)

    value = parsed.get("confirms_resolved")
    confirms = value if isinstance(value, bool) else None
    return {"confirms_resolved": confirms, "confidence": _normalize_confidence(parsed.get("confidence"))}


SAME_ISSUE_SYSTEM_PROMPT = (
    "You are deduplicating support tickets. A customer who already has an open ticket has sent another "
    "message. Decide whether the new message describes the SAME underlying issue as the existing open "
    "ticket (so it should be appended there instead of opening a new ticket), or a DIFFERENT issue. "
    'Respond strictly with a JSON object: {"same_issue": true|false, "confidence": 0-1}.'
)


def _rule_based_same_issue(new_message: str, candidate_subject: str, candidate_summary: str | None) -> dict:
    """Word-overlap fallback: compares the new message against the candidate ticket's subject
    + AI summary. Requires a real overlap of non-trivial words, not just any shared token."""
    reference = f"{candidate_subject or ''} {candidate_summary or ''}".lower()
    ref_words = {w for w in re.findall(r"[a-zA-Z]{4,}", reference) if w not in _STOPWORDS}
    if not ref_words:
        return {"same_issue": False, "confidence": 0.3}
    msg_words = {w for w in re.findall(r"[a-zA-Z]{4,}", (new_message or "").lower()) if w not in _STOPWORDS}
    if not msg_words:
        return {"same_issue": False, "confidence": 0.3}
    overlap = ref_words & msg_words
    score = len(overlap) / max(1, len(ref_words))
    return {"same_issue": score >= 0.3, "confidence": round(min(0.5 + score * 0.4, 0.9), 2)}


def classify_is_same_issue(
    new_message: str, candidate_subject: str, candidate_summary: str | None, api_key: str | None = None,
) -> dict:
    """Used to decide whether a fresh, non-threaded email/WhatsApp message from a known
    customer is a duplicate report of an already-open ticket. See
    ticket_service.find_reusable_open_ticket."""
    client = _make_client(api_key)
    contents = (
        f"Existing open ticket — subject: {candidate_subject}\nsummary: {candidate_summary or candidate_subject}\n\n"
        f'New message from the same customer:\n"""\n{(new_message or "").strip()}\n"""'
    )
    parsed = _gemini_json(client, settings.gemini_model, contents, SAME_ISSUE_SYSTEM_PROMPT) if client else None
    if not parsed or "same_issue" not in parsed:
        return _rule_based_same_issue(new_message, candidate_subject, candidate_summary)

    return {
        "same_issue": bool(parsed.get("same_issue")),
        "confidence": _normalize_confidence(parsed.get("confidence")),
    }


def verify_api_key(api_key: str | None) -> dict:
    key = (api_key or "").strip() or settings.gemini_api_key
    if not key:
        return {
            "success": False,
            "message": "No API Key provided or found in environment variables.",
            "hasEnvKey": bool(settings.gemini_api_key),
        }

    from google import genai
    import time

    client = genai.Client(api_key=key)
    start = time.monotonic()
    try:
        response = client.models.generate_content(model=settings.gemini_model, contents="Respond with OK if connected.")
        latency = int((time.monotonic() - start) * 1000)
        return {
            "success": True,
            "message": "Gemini API Key verified and active!",
            "model": settings.gemini_model,
            "latencyMs": latency,
            "responseSample": (response.text or "OK").strip(),
            "source": "Environment Secret" if key == settings.gemini_api_key else "Custom Configured Key",
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": str(exc) or "Invalid Gemini API Key or Quota Limit Exceeded."}
