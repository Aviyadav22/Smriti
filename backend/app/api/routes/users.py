"""User profile endpoints: get and update current user."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.audit import create_audit_log
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    created_at: str


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@router.get(
    "/users/me",
    dependencies=[Depends(rate_limit_dependency("60/minute"))],
)
async def get_profile(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Return the authenticated user's profile."""
    uid = uuid.UUID(current_user.sub)
    result = await db.execute(
        text("SELECT id, email, name, role, created_at FROM users WHERE id = :uid"),
        {"uid": uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfileResponse(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )


@router.put(
    "/users/me",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Update the authenticated user's display name."""
    uid = uuid.UUID(current_user.sub)
    await db.execute(
        text("UPDATE users SET name = :name, updated_at = NOW() WHERE id = :uid"),
        {"name": body.name.strip(), "uid": uid},
    )
    await db.commit()

    await create_audit_log(
        db=db,
        action="profile.updated",
        user_id=current_user.sub,
        resource_type="user",
        resource_id=current_user.sub,
        metadata={"field": "name"},
    )

    # Return updated profile
    result = await db.execute(
        text("SELECT id, email, name, role, created_at FROM users WHERE id = :uid"),
        {"uid": uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfileResponse(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )
