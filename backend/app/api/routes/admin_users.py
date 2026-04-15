"""Admin user management endpoints: list, update role, activate/deactivate."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.audit import create_audit_log
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ROLES = {"admin", "researcher", "viewer"}


class AdminUserSummary(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    is_active: bool
    last_login_at: str | None
    created_at: str


class AdminUserListResponse(BaseModel):
    users: list[AdminUserSummary]
    total: int
    page: int
    page_size: int


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get(
    "",
    dependencies=[
        Depends(rate_limit_dependency("60/minute")),
        Depends(require_role("admin")),
    ],
)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    role: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    """List all users with pagination and optional filters."""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
    offset = (page - 1) * page_size

    where_clauses = []
    params: dict = {"limit": page_size, "offset": offset}

    if search:
        where_clauses.append("(LOWER(email) LIKE :search OR LOWER(name) LIKE :search)")
        params["search"] = f"%{search.lower()}%"

    if role and role in VALID_ROLES:
        where_clauses.append("role = :role")
        params["role"] = role

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Get total count
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM users{where_sql}"),
        params,
    )
    total = count_result.scalar_one()

    # Get paginated users
    result = await db.execute(
        text(
            f"SELECT id, email, name, role, is_active, last_login_at, created_at "
            f"FROM users{where_sql} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = result.mappings().all()

    users = [
        AdminUserSummary(
            id=str(row["id"]),
            email=row["email"],
            name=row["name"],
            role=row["role"],
            is_active=row["is_active"],
            last_login_at=row["last_login_at"].isoformat() if row["last_login_at"] else None,
            created_at=row["created_at"].isoformat() if row["created_at"] else "",
        )
        for row in rows
    ]

    return AdminUserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/{user_id}",
    dependencies=[
        Depends(rate_limit_dependency("20/minute")),
        Depends(require_role("admin")),
    ],
)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserSummary:
    """Update a user's role or active status (admin only)."""
    try:
        target_uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    # Prevent self-demotion
    if user_id == current_user.sub and body.role and body.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    # Prevent self-deactivation
    if user_id == current_user.sub and body.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Validate role
    if body.role and body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}"
        )

    # Check target user exists
    result = await db.execute(
        text("SELECT id, role, is_active FROM users WHERE id = :uid"),
        {"uid": target_uid},
    )
    target = result.mappings().one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Build update
    updates = []
    audit_changes: dict = {}

    if body.role is not None and body.role != target["role"]:
        updates.append("role = :new_role")
        audit_changes["role"] = {"from": target["role"], "to": body.role}

    if body.is_active is not None and body.is_active != target["is_active"]:
        updates.append("is_active = :new_active")
        audit_changes["is_active"] = {"from": target["is_active"], "to": body.is_active}

    if not updates:
        raise HTTPException(status_code=422, detail="No changes provided")

    updates.append("updated_at = NOW()")
    update_params: dict = {"uid": target_uid}
    if body.role is not None:
        update_params["new_role"] = body.role
    if body.is_active is not None:
        update_params["new_active"] = body.is_active

    await db.execute(
        text(f"UPDATE users SET {', '.join(updates)} WHERE id = :uid"),
        update_params,
    )
    await db.commit()

    await create_audit_log(
        db=db,
        action="admin.user_updated",
        user_id=current_user.sub,
        resource_type="user",
        resource_id=user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata=audit_changes,
    )

    # Return updated user
    result = await db.execute(
        text(
            "SELECT id, email, name, role, is_active, last_login_at, created_at "
            "FROM users WHERE id = :uid"
        ),
        {"uid": target_uid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    return AdminUserSummary(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        is_active=row["is_active"],
        last_login_at=row["last_login_at"].isoformat() if row["last_login_at"] else None,
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )
