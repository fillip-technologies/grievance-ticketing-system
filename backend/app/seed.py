from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import User
from .security import hash_password

settings = get_settings()


async def ensure_superadmin(db: AsyncSession) -> User:
    """Seeds exactly one platform Super Admin. Idempotent across restarts."""
    result = await db.execute(select(User).where(User.email == settings.superadmin_email))
    admin = result.scalar_one_or_none()

    if admin is None:
        admin = User(
            org_id=None,
            email=settings.superadmin_email,
            name=settings.superadmin_name,
            role="SuperAdmin",
            password_hash=hash_password(settings.superadmin_password),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

    return admin
