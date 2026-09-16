"""Unauthenticated complaint-tracking endpoint for the complainant-facing status page —
lets someone check "any update?" themselves instead of emailing the org, using their
Complaint ID plus the same contact detail (email or mobile) they gave at intake as a
lightweight shared-secret (ticket IDs alone are sequential/guessable).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Organization, Ticket
from ..schemas import PublicTrackRequest
from ..serializers import public_ticket_to_dict

router = APIRouter(prefix="/api/public", tags=["public"])

_NOT_FOUND_DETAIL = "No complaint found matching that Complaint ID and contact detail. Double-check both and try again."


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


@router.post("/track")
async def track_complaint(payload: PublicTrackRequest, db: AsyncSession = Depends(get_db)):
    ticket_id = payload.ticketId.strip().upper()
    contact = payload.contact.strip().lower()

    ticket = await db.get(Ticket, ticket_id, options=[selectinload(Ticket.replies)])

    matched = False
    if ticket:
        if ticket.customer_email and ticket.customer_email.strip().lower() == contact:
            matched = True
        else:
            contact_digits = _digits(contact)
            ticket_digits = _digits(ticket.customer_mobile or "")
            # Compare last 10 digits so +91/leading-zero/country-code formatting differences
            # between what was typed at intake and what's typed here don't cause a false miss.
            if contact_digits and ticket_digits and contact_digits[-10:] == ticket_digits[-10:]:
                matched = True

    if not ticket or not matched:
        # Same error either way — don't leak whether the ID exists but the contact was wrong,
        # which would let someone brute-force-confirm valid (sequential) ticket IDs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)

    org = await db.get(Organization, ticket.org_id)
    return public_ticket_to_dict(ticket, org.name if org else "")
