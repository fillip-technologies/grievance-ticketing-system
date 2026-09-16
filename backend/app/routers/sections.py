from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_org, require_roles
from ..models import Organization, Section, Ticket, User
from ..schemas import SectionCreate, SectionUpdate
from ..serializers import section_to_dict

router = APIRouter(prefix="/api/sections", tags=["sections"])


async def _resolver_counts(db: AsyncSession, org_id: str) -> dict[str, int]:
    result = await db.execute(
        select(User.section_id, func.count(User.id))
        .where(
            User.org_id == org_id, User.role == "Resolver", User.is_active.is_(True),
            User.section_id.isnot(None),
        )
        .group_by(User.section_id)
    )
    return dict(result.all())


@router.get("")
async def list_sections(
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Section).where(Section.org_id == org.id).order_by(Section.created_at))
    sections = result.scalars().all()
    counts = await _resolver_counts(db, org.id)
    return {"sections": [section_to_dict(s, counts.get(s.id, 0)) for s in sections]}


@router.post("")
async def create_section(
    payload: SectionCreate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section name is required.")

    existing = await db.execute(select(Section).where(Section.org_id == org.id, Section.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f'A section named "{name}" already exists.')

    section = Section(org_id=org.id, name=name, description=(payload.description or "").strip())
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return {"section": section_to_dict(section, 0)}


@router.patch("/{section_id}")
async def update_section(
    section_id: str,
    payload: SectionUpdate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    section = await db.get(Section, section_id)
    if section is None or section.org_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section name cannot be blank.")
        if name != section.name:
            existing = await db.execute(
                select(Section).where(Section.org_id == org.id, Section.name == name, Section.id != section.id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f'A section named "{name}" already exists.')
        section.name = name
    if payload.description is not None:
        section.description = payload.description.strip()
    if payload.isActive is not None:
        section.is_active = payload.isActive

    db.add(section)
    await db.commit()
    await db.refresh(section)
    counts = await _resolver_counts(db, org.id)
    return {"section": section_to_dict(section, counts.get(section.id, 0))}


@router.delete("/{section_id}")
async def delete_section(
    section_id: str,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_roles("OrgAdmin")),
    db: AsyncSession = Depends(get_db),
):
    section = await db.get(Section, section_id)
    if section is None or section.org_id != org.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    # No DB-enforced FK on users.section_id / tickets.section_id (see migration 0008 — SQLite
    # can't ALTER TABLE ADD CONSTRAINT outside batch-mode recreation) — null out referencing
    # rows here instead of relying on ON DELETE SET NULL at the DB level.
    await db.execute(update(User).where(User.section_id == section.id).values(section_id=None))
    await db.execute(update(Ticket).where(Ticket.section_id == section.id).values(section_id=None))
    await db.delete(section)
    await db.commit()
    return {"success": True}
