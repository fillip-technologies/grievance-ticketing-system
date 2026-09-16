from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_org, require_roles
from ..models import Organization, OrganizationSettings, Section, Ticket, User
from ..schemas import TeamMemberCreate, TeamMemberUpdate
from ..security import generate_temp_password, hash_password
from ..serializers import team_member_to_dict
from ..services import smtp_service
from ..services.ticket_service import resolve_brand_name

router = APIRouter(prefix="/api/team", tags=["team"])


async def _section_names(db: AsyncSession, org_id: str) -> dict[str, str]:
    result = await db.execute(select(Section.id, Section.name).where(Section.org_id == org_id))
    return dict(result.all())


async def _validate_section(db: AsyncSession, org_id: str, section_id: str | None) -> None:
    if section_id is None:
        return
    section = await db.get(Section, section_id)
    if section is None or section.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section not found for this organization.")


@router.get("")
async def list_team(
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.org_id == org.id, User.role.in_(["Resolver", "EscalationAuthority"])).order_by(User.created_at)
    )
    members = result.scalars().all()

    counts_result = await db.execute(
        select(Ticket.assigned_to, func.count(Ticket.id))
        .where(Ticket.org_id == org.id, Ticket.status.in_(["Open", "In Progress", "Escalated"]))
        .group_by(Ticket.assigned_to)
    )
    counts = dict(counts_result.all())
    section_names = await _section_names(db, org.id)

    return {
        "team": [
            team_member_to_dict(m, counts.get(m.id, 0), section_names.get(m.section_id))
            for m in members
        ]
    }


@router.post("")
async def create_team_member(
    payload: TeamMemberCreate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    await _validate_section(db, org.id, payload.sectionId)

    temp_password = generate_temp_password()
    member = User(
        org_id=org.id,
        email=email,
        name=payload.name.strip(),
        mobile=payload.mobile.strip(),
        role=payload.role,
        escalation_level=payload.escalationLevel if payload.role == "EscalationAuthority" else 1,
        section_id=payload.sectionId if payload.role == "Resolver" else None,
        password_hash=hash_password(temp_password),
        must_reset_password=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    settings_result = await db.execute(select(OrganizationSettings).where(OrganizationSettings.org_id == org.id))
    org_settings = settings_result.scalar_one_or_none()
    email_sent = False
    if org_settings:
        cfg = smtp_service.from_org_settings(org_settings)
        if cfg.configured:
            brand_name = resolve_brand_name(org, org_settings)
            body = smtp_service.build_team_invite_email(member.name, org.name, member.role, member.email, temp_password, brand_name)
            result = await run_in_threadpool(
                smtp_service.send_email, cfg, member.email, f"You've been added to {org.name}", body, brand_name,
            )
            email_sent = bool(result.get("success"))

    section_names = await _section_names(db, org.id)
    return {
        "member": team_member_to_dict(member, 0, section_names.get(member.section_id)),
        "temporaryPassword": temp_password,
        "inviteEmailSent": email_sent,
    }


@router.patch("/{user_id}")
async def update_team_member(
    user_id: str,
    payload: TeamMemberUpdate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    member = await db.get(User, user_id)
    if member is None or member.org_id != org.id or member.role not in ("Resolver", "EscalationAuthority"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    if payload.isActive is not None:
        member.is_active = payload.isActive
    if payload.role is not None:
        member.role = payload.role
        if member.role != "Resolver":
            member.section_id = None  # only Resolvers belong to a section
    if payload.escalationLevel is not None:
        member.escalation_level = payload.escalationLevel

    if payload.clearSection:
        member.section_id = None
    elif payload.sectionId is not None:
        await _validate_section(db, org.id, payload.sectionId)
        member.section_id = payload.sectionId

    await db.commit()
    await db.refresh(member)
    section_names = await _section_names(db, org.id)
    return {"member": team_member_to_dict(member, 0, section_names.get(member.section_id))}


@router.delete("/{user_id}")
async def delete_team_member(
    user_id: str,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    member = await db.get(User, user_id)
    if member is None or member.org_id != org.id or member.role not in ("Resolver", "EscalationAuthority"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    # Tickets keep their history — Ticket.assigned_to is ON DELETE SET NULL, so any tickets
    # currently assigned to this member simply fall back to unassigned instead of failing.
    await db.delete(member)
    await db.commit()
    return {"success": True}
