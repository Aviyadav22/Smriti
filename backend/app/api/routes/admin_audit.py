"""Admin audit log endpoints: query and filter audit logs."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter()


class AuditLogEntry(BaseModel):
    id: int
    user_id: str | None
    user_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    metadata: dict | None
    created_at: str


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


@router.get(
    "",
    dependencies=[
        Depends(rate_limit_dependency("60/minute")),
        Depends(require_role("admin")),
    ],
)
async def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    action: str | None = None,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Query audit logs with optional filters (admin only)."""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 50
    offset = (page - 1) * page_size

    where_clauses = []
    params: dict = {"limit": page_size, "offset": offset}

    if action:
        where_clauses.append("a.action = :action")
        params["action"] = action

    if user_id:
        where_clauses.append("a.user_id = :user_id")
        params["user_id"] = user_id

    if date_from:
        where_clauses.append("a.created_at >= :date_from::timestamptz")
        params["date_from"] = date_from

    if date_to:
        where_clauses.append("a.created_at <= :date_to::timestamptz")
        params["date_to"] = date_to

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Total count
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM audit_logs a{where_sql}"),
        params,
    )
    total = count_result.scalar_one()

    # Fetch logs with user email join
    result = await db.execute(
        text(
            f"SELECT a.id, a.user_id, u.email AS user_email, a.action, "
            f"a.resource_type, a.resource_id, a.ip_address, a.user_agent, "
            f"a.metadata, a.created_at "
            f"FROM audit_logs a "
            f"LEFT JOIN users u ON a.user_id::uuid = u.id"
            f"{where_sql} "
            f"ORDER BY a.created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = result.mappings().all()

    logs = [
        AuditLogEntry(
            id=row["id"],
            user_id=str(row["user_id"]) if row["user_id"] else None,
            user_email=row["user_email"],
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            metadata=row["metadata"],
            created_at=row["created_at"].isoformat() if row["created_at"] else "",
        )
        for row in rows
    ]

    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        page_size=page_size,
    )
