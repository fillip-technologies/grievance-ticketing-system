import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_org, get_current_user, require_roles
from ..models import Organization, OrganizationSettings, User
from ..schemas import AuthResponse, OrganizationSettingsUpdate, OrgRegisterRequest, UserOut
from ..security import create_access_token, hash_password
from ..serializers import org_settings_to_dict, organization_to_dict, user_to_dict

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "organization"
    return base[:60]


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base = _slugify(name)
    slug = base
    for _ in range(20):
        existing = await db.execute(select(Organization).where(Organization.slug == slug))
        if existing.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{secrets.token_hex(2)}"
    return f"{base}-{secrets.token_hex(4)}"


def _default_ticket_prefix(slug: str) -> str:
    """Derived from the org's slug so two orgs are unlikely to share a default prefix —
    e.g. "rajgir-jungle-safari" -> "RAJGIR-2026-". Purely cosmetic/readability: actual
    ticket-ID uniqueness across orgs is enforced in ticket_service.next_ticket_number
    regardless of what this ends up being, so a residual collision here is harmless."""
    code = re.sub(r"[^A-Za-z0-9]", "", slug.split("-")[0]).upper()[:8] or "ORG"
    return f"{code}-2026-"


@router.post("/register", response_model=AuthResponse)
async def register_organization(payload: OrgRegisterRequest, db: AsyncSession = Depends(get_db)):
    email = payload.adminEmail.lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    slug = await _unique_slug(db, payload.orgName)
    org = Organization(name=payload.orgName.strip(), slug=slug)
    db.add(org)
    await db.flush()

    db.add(OrganizationSettings(org_id=org.id, ticket_prefix=_default_ticket_prefix(slug)))

    admin = User(
        org_id=org.id,
        email=email,
        name=payload.adminName.strip(),
        mobile=payload.adminMobile.strip(),
        role="OrgAdmin",
        password_hash=hash_password(payload.adminPassword),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    await db.refresh(admin, attribute_names=["org"])

    token = create_access_token(admin.id)
    return AuthResponse(token=token, user=UserOut(**user_to_dict(admin)))


@router.get("/me")
async def get_my_organization(
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OrganizationSettings).where(OrganizationSettings.org_id == org.id))
    org_settings = result.scalar_one_or_none()
    if org_settings is None:
        org_settings = OrganizationSettings(org_id=org.id)
        db.add(org_settings)
        await db.commit()
        await db.refresh(org_settings)

    payload = organization_to_dict(org)
    payload["settings"] = org_settings_to_dict(org_settings)
    return payload


@router.put("/me")
async def update_my_organization(
    payload: OrganizationSettingsUpdate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OrganizationSettings).where(OrganizationSettings.org_id == org.id))
    org_settings = result.scalar_one_or_none()
    if org_settings is None:
        org_settings = OrganizationSettings(org_id=org.id)
        db.add(org_settings)

    org_settings.ticket_prefix = payload.ticketPrefix or org_settings.ticket_prefix
    org_settings.auto_send_receipt = payload.autoSendReceipt
    org_settings.auto_assign_resolver = payload.autoAssignResolver
    org_settings.sender_display_name = payload.senderDisplayName.strip()
    org_settings.support_sla_hours = payload.supportSlaHours
    org_settings.enquiry_sla_hours = payload.enquirySlaHours
    org_settings.re_escalation_hours = payload.reEscalationHours
    org_settings.auto_close_after_days = payload.autoCloseAfterDays
    org_settings.smtp_host = payload.smtpHost
    org_settings.smtp_port = payload.smtpPort
    org_settings.smtp_username = payload.smtpUsername
    org_settings.smtp_from_email = payload.smtpFromEmail

    if payload.clearSmtpPassword:
        org_settings.smtp_password = ""
    elif payload.smtpPassword:
        org_settings.smtp_password = payload.smtpPassword

    if payload.clearGeminiKey:
        org_settings.gemini_api_key = ""
    elif payload.geminiApiKey:
        org_settings.gemini_api_key = payload.geminiApiKey

    org_settings.whatsapp_phone_number_id = payload.whatsappPhoneNumberId

    if payload.clearWhatsappAccessToken:
        org_settings.whatsapp_access_token = ""
    elif payload.whatsappAccessToken:
        org_settings.whatsapp_access_token = payload.whatsappAccessToken

    if payload.clearWhatsappAppSecret:
        org_settings.whatsapp_app_secret = ""
    elif payload.whatsappAppSecret:
        org_settings.whatsapp_app_secret = payload.whatsappAppSecret

    # "or existing" fallback (not unconditional assignment) so a save from a form that doesn't
    # own these fields — e.g. the main Org Settings save — can't blank out what was configured
    # on the SMS channel tab.
    org_settings.sms_provider = payload.smsProvider or org_settings.sms_provider
    org_settings.sms_api_url = payload.smsApiUrl or org_settings.sms_api_url
    org_settings.sms_sender_id = payload.smsSenderId or org_settings.sms_sender_id

    if payload.clearSmsApiKey:
        org_settings.sms_api_key = ""
    elif payload.smsApiKey:
        org_settings.sms_api_key = payload.smsApiKey

    org_settings.business_hours_enabled = payload.businessHoursEnabled
    org_settings.business_start_hour = payload.businessStartHour
    org_settings.business_end_hour = payload.businessEndHour
    org_settings.business_days = payload.businessDays or org_settings.business_days
    org_settings.timezone = payload.timezone or org_settings.timezone
    org_settings.holiday_dates = payload.holidayDates

    await db.commit()
    await db.refresh(org_settings)
    return {"success": True, "settings": org_settings_to_dict(org_settings)}


@router.post("/me/regenerate-key")
async def regenerate_webhook_key(
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    from ..models import gen_api_key

    org.webhook_api_key = gen_api_key()
    await db.commit()
    return {"success": True, "webhookApiKey": org.webhook_api_key}


