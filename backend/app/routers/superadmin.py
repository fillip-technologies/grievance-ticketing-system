from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import require_roles
from ..models import Organization, Ticket, User
from ..schemas import MailboxStatusUpdate
from ..serializers import organization_to_dict

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


@router.get("/organizations")
async def list_organizations(user: User = Depends(require_roles("SuperAdmin")), db: AsyncSession = Depends(get_db)):
    orgs_result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    orgs = orgs_result.scalars().all()

    ticket_counts = dict((await db.execute(select(Ticket.org_id, func.count(Ticket.id)).group_by(Ticket.org_id))).all())
    user_counts = dict((await db.execute(select(User.org_id, func.count(User.id)).where(User.org_id.isnot(None)).group_by(User.org_id))).all())

    return {
        "organizations": [
            organization_to_dict(org, ticket_counts.get(org.id, 0), user_counts.get(org.id, 0)) for org in orgs
        ]
    }


@router.patch("/organizations/{org_id}/status")
async def update_organization_status(
    org_id: str,
    payload: MailboxStatusUpdate,
    user: User = Depends(require_roles("SuperAdmin")),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if payload.status not in ("Active", "Suspended"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be Active or Suspended")
    org.status = payload.status
    await db.commit()
    return {"organization": organization_to_dict(org)}
