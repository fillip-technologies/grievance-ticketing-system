import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..deps import get_current_org, get_current_user, get_org_by_api_key
from ..models import Organization, Ticket, User
from ..schemas import IntakeRequest, SmsTestRequest, SmtpSendRequest, SmtpVerifyRequest, VerifyKeyRequest, VoiceRequest, WhatsAppTestRequest
from ..serializers import ticket_to_dict
from ..services import gemini_service, sms_service, smtp_service, whatsapp_service
from ..services.ticket_service import (
    append_inbound_reply,
    create_ticket,
    create_ticket_from_message,
    find_reusable_open_ticket,
    get_active_sections,
    get_org_settings,
    resolve_brand_name,
    resolve_section,
    sections_payload,
)

router = APIRouter(prefix="/api", tags=["ai"])


# ---------- Shared intake pipeline ----------
async def _process_intake(db: AsyncSession, org: Organization, message: str, customer_name: str | None, customer_mobile: str | None, customer_email: str | None, channel: str) -> dict:
    ticket = await create_ticket_from_message(db, org, message, customer_name, customer_mobile, customer_email, channel)

    return {
        "ticketNumber": ticket.id,
        "category": ticket.category,
        "confidence_score": ticket.confidence_score,
        "subject": ticket.subject,
        "summary": ticket.ai_summary or message[:160],
        "urgency": ticket.urgency,
        "extracted_name": ticket.customer_name,
        "extracted_mobile": ticket.customer_mobile,
        "extracted_email": ticket.customer_email,
        "autoDispatched": True,
        "ticket": ticket_to_dict(ticket),
    }


@router.post("/webhook/external/{api_key}/intake")
async def external_webhook_intake(api_key: str, payload: IntakeRequest, db: AsyncSession = Depends(get_db)):
    """Real external intake endpoint — point your website form / Zapier / CRM webhook here."""
    org = await get_org_by_api_key(api_key, db)
    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content is required.")
    return await _process_intake(db, org, payload.message, payload.customerName, payload.customerMobile, payload.customerEmail, payload.channel)


# ---------- WhatsApp ----------
def _parse_whatsapp_body(body: dict) -> tuple[str, str, str]:
    message_text = customer_mobile = customer_name = ""
    if not isinstance(body, dict):
        return message_text, customer_mobile, customer_name

    if body.get("object") == "whatsapp_business_account" and body.get("entry"):
        entry = body["entry"][0] or {}
        changes = entry.get("changes") or []
        val = changes[0].get("value", {}) if changes else {}
        messages = val.get("messages") or []
        contacts = val.get("contacts") or []
        if messages:
            msg = messages[0]
            message_text = (msg.get("text") or {}).get("body") or msg.get("caption") or "Incoming WhatsApp Media/Query"
            customer_mobile = f"+{msg['from']}" if msg.get("from") else ""
        if contacts:
            customer_name = (contacts[0].get("profile") or {}).get("name") or ""
    elif body.get("Body"):
        message_text = body["Body"]
        customer_mobile = str(body.get("From") or "").replace("whatsapp:", "")
        customer_name = body.get("ProfileName") or ""
    else:
        message_text = body.get("message") or body.get("text") or ""
        customer_mobile = body.get("customerMobile") or body.get("from") or ""
        customer_name = body.get("customerName") or body.get("name") or ""

    return message_text, customer_mobile, customer_name


async def _process_whatsapp(db: AsyncSession, org: Organization, message_text: str, customer_name: str, customer_mobile: str) -> dict:
    org_settings = await get_org_settings(db, org.id)

    if customer_mobile:
        reusable_ticket = await find_reusable_open_ticket(
            db, org.id, None, customer_mobile, message_text, org_settings.gemini_api_key or None,
        )
        if reusable_ticket:
            await append_inbound_reply(
                db, reusable_ticket, customer_name or customer_mobile, message_text, org_settings.gemini_api_key or None,
            )
            result = await db.execute(
                select(Ticket)
                .options(
                    selectinload(Ticket.replies), selectinload(Ticket.logs), selectinload(Ticket.assignee),
                    selectinload(Ticket.section),
                )
                .where(Ticket.id == reusable_ticket.id)
                .execution_options(populate_existing=True)
            )
            ticket = result.scalar_one()
            return {
                "success": True,
                "ticketId": ticket.id,
                "channel": "WhatsApp",
                "customerName": ticket.customer_name,
                "customerMobile": ticket.customer_mobile,
                "category": ticket.category,
                "confidence_score": ticket.confidence_score,
                "subject": ticket.subject,
                "summary": ticket.ai_summary,
                "urgency": ticket.urgency,
                "reused": True,
                "timestamp": ticket.created_at.isoformat(),
                "ticket": ticket_to_dict(ticket),
            }

    sections = await get_active_sections(db, org.id)
    classification = await run_in_threadpool(
        gemini_service.process_whatsapp_message, message_text, customer_name, customer_mobile,
        org_settings.gemini_api_key or None, sections_payload(sections),
    )
    category = classification["category"]
    confidence = float(classification["confidence_score"] or 0.85)
    urgency = classification.get("urgency") or ("High" if category == "Support" else "Low")
    due_hours = org_settings.support_sla_hours if category == "Support" else org_settings.enquiry_sla_hours
    final_name = classification.get("extracted_name") or customer_name or "WhatsApp User"
    final_mobile = classification.get("extracted_mobile") or customer_mobile or ""
    section = await resolve_section(db, org.id, classification.get("section"))

    data = {
        "category": category,
        "urgency": urgency,
        "subject": classification.get("subject") or f"{category} Ticket via WhatsApp",
        "summary": classification.get("summary") or message_text[:160],
        "confidenceScore": confidence,
        "channel": "WhatsApp",
        "message": message_text,
        "customerName": final_name,
        "customerMobile": final_mobile,
        "customerEmail": classification.get("extracted_email"),
        "sectionId": section.id if section else None,
    }
    ticket = await create_ticket(db, org, data)

    # create_ticket() has already dispatched the real ack via whatsapp_service if this org has
    # WhatsApp configured (see ticket_service._send_ack_and_assignment_notifications). This is
    # rebuilt here purely so the webhook response can include a preview of what was/would be sent.
    brand_name = resolve_brand_name(org, org_settings)
    auto_reply = whatsapp_service.build_ack_message(
        ticket.id, final_name, category, urgency, classification.get("summary") or message_text[:60], due_hours, brand_name,
    )
    wa_configured = whatsapp_service.from_org_settings(org_settings).configured

    return {
        "success": True,
        "ticketId": ticket.id,
        "channel": "WhatsApp",
        "customerName": final_name,
        "customerMobile": final_mobile,
        "category": category,
        "confidence_score": confidence,
        "subject": ticket.subject,
        "summary": classification.get("summary") or message_text[:160],
        "urgency": urgency,
        "dueHours": due_hours,
        "whatsappAutoReply": auto_reply,
        "whatsappDispatched": wa_configured,
        "timestamp": ticket.created_at.isoformat(),
        "ticket": ticket_to_dict(ticket),
    }


@router.get("/webhook/external/{api_key}/whatsapp")
async def whatsapp_verify(api_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Meta/Twilio webhook verification handshake. Point your WhatsApp Business API console here."""
    org = await get_org_by_api_key(api_key, db)
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == org.webhook_api_key:
        return int(challenge) if challenge and challenge.isdigit() else challenge
    return {"status": "WhatsApp Intake Webhook Ready", "org": org.name}


@router.post("/webhook/external/{api_key}/whatsapp")
async def whatsapp_receive(api_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    org = await get_org_by_api_key(api_key, db)

    raw_body = await request.body()
    org_settings = await get_org_settings(db, org.id)
    wa_cfg = whatsapp_service.from_org_settings(org_settings)
    if wa_cfg.app_secret:
        signature = request.headers.get("X-Hub-Signature-256")
        if not whatsapp_service.verify_signature(wa_cfg.app_secret, raw_body, signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature.")

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = json.loads(raw_body or b"{}")
    else:
        body = dict(await request.form())
    message_text, customer_mobile, customer_name = _parse_whatsapp_body(body)
    if not message_text.strip():
        # Meta pings this URL with empty/status payloads too; ack quietly instead of erroring.
        return {"status": "ignored", "reason": "no message content"}
    return await _process_whatsapp(db, org, message_text, customer_name, customer_mobile)


# ---------- Voice ----------
@router.post("/ai-voice-command")
async def ai_voice(payload: VoiceRequest, user: User = Depends(get_current_user), org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    org_settings = await get_org_settings(db, org.id)
    return await run_in_threadpool(gemini_service.voice_command, payload.transcript, payload.currentTab, org_settings.gemini_api_key or None)


# ---------- Gemini key verify ----------
@router.post("/settings/verify-key")
async def verify_key(payload: VerifyKeyRequest, user: User = Depends(get_current_user), org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    org_settings = await get_org_settings(db, org.id)
    key = (payload.apiKey or "").strip() or org_settings.gemini_api_key
    return await run_in_threadpool(gemini_service.verify_api_key, key)


# ---------- SMTP ----------
@router.post("/smtp/verify")
async def smtp_verify(payload: SmtpVerifyRequest, user: User = Depends(get_current_user), org: Organization = Depends(get_current_org)):
    email = payload.emailAddress.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid email address is required.")
    host = payload.host.strip() or f"smtp.{email.split('@')[1]}"
    cfg = smtp_service.SmtpConfig(host=host, port=payload.port or 465, username=email, password=payload.password, from_email=email, use_ssl=payload.ssl)
    return await run_in_threadpool(smtp_service.verify_smtp, cfg)


@router.post("/smtp/send-receipt")
async def smtp_send_receipt(payload: SmtpSendRequest, user: User = Depends(get_current_user), org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)):
    org_settings = await get_org_settings(db, org.id)
    cfg = smtp_service.from_org_settings(org_settings)
    if payload.host:
        cfg.host = payload.host
    if payload.port:
        cfg.port = payload.port
    if payload.fromEmail:
        cfg.from_email = payload.fromEmail

    brand_name = resolve_brand_name(org, org_settings)
    body = payload.body or smtp_service.build_thank_you_email(
        payload.ticketNumber or "TKT-SMTP-TEST", payload.customerName, "Support", payload.subject, None, None, None, brand_name,
    )
    result = await run_in_threadpool(smtp_service.send_email, cfg, payload.toEmail, payload.subject, body, brand_name)
    result["messageId"] = f"<{payload.ticketNumber or 'receipt'}-{int(time.time())}@grievancedesk.local>"
    result["smtpServer"] = f"{cfg.host}:{cfg.port}"
    return result


# ---------- WhatsApp Business API test ----------
@router.post("/whatsapp/send-test")
async def whatsapp_send_test(
    payload: WhatsAppTestRequest, user: User = Depends(get_current_user), org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)
):
    org_settings = await get_org_settings(db, org.id)
    cfg = whatsapp_service.from_org_settings(org_settings)
    brand_name = resolve_brand_name(org, org_settings)
    body = payload.body.strip() or (
        f"This is a test message from {brand_name} confirming your WhatsApp Business API configuration is working."
    )
    result = await run_in_threadpool(whatsapp_service.send_text, cfg, payload.toMobile, body)
    return result


# ---------- SMS test send ----------
@router.post("/sms/send-test")
async def sms_send_test(
    payload: SmsTestRequest, user: User = Depends(get_current_user), org: Organization = Depends(get_current_org), db: AsyncSession = Depends(get_db)
):
    org_settings = await get_org_settings(db, org.id)
    cfg = sms_service.from_org_settings(org_settings)
    brand_name = resolve_brand_name(org, org_settings)
    body = payload.body.strip() or (
        f"This is a test message from {brand_name} confirming your SMS gateway configuration is working."
    )
    result = await run_in_threadpool(sms_service.send_text, cfg, payload.toMobile, body)
    return result
