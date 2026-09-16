from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import Organization, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    return user


def require_roles(*roles: str):
    """Dependency factory: 403s unless the current user's role is one of `roles`."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(roles)}.",
            )
        return user

    return _check


async def get_current_org(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    if not user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not attached to an organization.")

    org = await db.get(Organization, user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    if org.status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This organization's account is suspended.")
    return org


async def get_org_by_api_key(api_key: str, db: AsyncSession) -> Organization:
    """Used by external (unauthenticated-by-JWT) webhook routes: /webhook/external/{api_key}/..."""
    result = await db.execute(select(Organization).where(Organization.webhook_api_key == api_key))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook API key.")
    if org.status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This organization's account is suspended.")
    return org
