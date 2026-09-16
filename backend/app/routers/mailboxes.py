from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_org, require_roles
from ..models import Mailbox, Organization, User
from ..schemas import MailboxCreate, MailboxStatusUpdate
from ..serializers import mailbox_to_dict
from ..services import smtp_service
from ..services.email_ingest_service import poll_mailbox
from ..services.ticket_service import get_org_settings, resolve_brand_name

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])


async def _get_org_mailbox(db: AsyncSession, mailbox_id: str, org_id: str) -> Mailbox:
    mb = await db.get(Mailbox, mailbox_id)
    if mb is None or mb.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    return mb


@router.get("")
async def list_mailboxes(org: Organization = Depends(get_current_org), user: User = Depends(require_roles("OrgAdmin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.org_id == org.id).order_by(Mailbox.email_address))
    return {"mailboxes": [mailbox_to_dict(mb) for mb in result.scalars().all()]}


@router.post("")
async def create_mailbox(
    payload: MailboxCreate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    email = payload.emailAddress.strip().lower()
    domain = email.split("@")[1] if "@" in email else "domain.com"
    host = payload.incomingHost.strip() or f"mail.{domain}"

    mb = Mailbox(
        org_id=org.id,
        email_address=email,
        display_name=payload.displayName.strip(),
        server_type=payload.serverType,
        incoming_host=host,
        port=payload.port,
        incoming_username=payload.incomingUsername.strip() or email,
        incoming_password=payload.incomingPassword,
        incoming_use_ssl=payload.incomingUseSsl,
        outgoing_smtp_host=payload.outgoingSmtpHost.strip() or host,
        outgoing_smtp_port=payload.outgoingSmtpPort,
        smtp_use_ssl=payload.smtpUseSsl,
        smtp_username=payload.smtpUsername.strip() or email,
        smtp_password=payload.smtpPassword,
        auto_dispatch=payload.autoDispatch,
        status="Connected",
    )
    db.add(mb)
    await db.commit()
    await db.refresh(mb)
    return {"mailbox": mailbox_to_dict(mb)}


@router.delete("/{mailbox_id}")
async def delete_mailbox(mailbox_id: str, org: Organization = Depends(get_current_org), user: User = Depends(require_roles("OrgAdmin")), db: AsyncSession = Depends(get_db)):
    mb = await _get_org_mailbox(db, mailbox_id, org.id)
    await db.delete(mb)
    await db.commit()
    return {"success": True}


@router.patch("/{mailbox_id}/status")
async def update_mailbox_status(
    mailbox_id: str,
    payload: MailboxStatusUpdate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    mb = await _get_org_mailbox(db, mailbox_id, org.id)
    mb.status = payload.status
    await db.commit()
    return {"mailbox": mailbox_to_dict(mb)}


@router.post("/{mailbox_id}/test-receipt")
async def test_receipt(
    mailbox_id: str,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    mb = await _get_org_mailbox(db, mailbox_id, org.id)
    cfg = smtp_service.from_mailbox(mb)
    if not cfg.configured:
        return {"success": False, "smtpServer": f"{cfg.host}:{cfg.port}", "message": "Outgoing SMTP is not configured for this mailbox yet."}

    org_settings = await get_org_settings(db, org.id)
    brand_name = resolve_brand_name(org, org_settings)
    result = await run_in_threadpool(
        smtp_service.send_email, cfg, "customer.test@example.com", f"[SMTP Test] {brand_name} Receipt",
        smtp_service.build_test_receipt_email(brand_name), brand_name,
    )
    result["smtpServer"] = f"{cfg.host}:{cfg.port}"
    return result


@router.post("/{mailbox_id}/sync-now")
async def sync_mailbox_now(
    mailbox_id: str,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    mb = await _get_org_mailbox(db, mailbox_id, org.id)
    result = await poll_mailbox(db, mb)
    await db.refresh(mb)
    return {"result": result, "mailbox": mailbox_to_dict(mb)}
