from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import AuthResponse, ChangePasswordRequest, LoginRequest, UserOut
from ..security import create_access_token, hash_password, verify_password
from ..serializers import user_to_dict

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")
    if user.org_id:
        await db.refresh(user, attribute_names=["org"])
        if user.org and user.org.status != "Active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This organization's account is suspended.")

    token = create_access_token(user.id)
    return AuthResponse(token=token, user=UserOut(**user_to_dict(user)))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(**user_to_dict(user))


@router.post("/change-password", response_model=UserOut)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Self-service password change — also clears must_reset_password so an invited
    Resolver/EscalationAuthority isn't nagged again once they've set their own password."""
    if not verify_password(payload.currentPassword, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")
    if payload.newPassword == payload.currentPassword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different from the current password.")

    user.password_hash = hash_password(payload.newPassword)
    user.must_reset_password = False
    db.add(user)
    await db.commit()
    await db.refresh(user)
    if user.org_id:
        await db.refresh(user, attribute_names=["org"])
    return UserOut(**user_to_dict(user))
