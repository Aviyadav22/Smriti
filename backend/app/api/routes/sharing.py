"""Memo sharing API routes — create, view, revoke, and public access."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.postgres import get_db
from app.models.agent_execution import AgentExecution
from app.models.shared_memo import SharedMemo
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.security.auth import TokenPayload

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateShareRequest(BaseModel):
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


# ---------------------------------------------------------------------------
# POST /agents/research/{execution_id}/share — create or return existing share
# ---------------------------------------------------------------------------


@router.post(
    "/agents/research/{execution_id}/share",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def create_share(
    execution_id: str,
    body: CreateShareRequest | None = None,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a shareable link for a completed research memo."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    # Validate ownership and completion
    result = await db.execute(select(AgentExecution).where(AgentExecution.id == exec_uuid))
    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found.")
    if str(execution.user_id) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied.")
    if execution.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed executions can be shared.")

    # Check for existing active share (upsert behavior)
    existing = await db.execute(
        select(SharedMemo).where(
            SharedMemo.execution_id == exec_uuid,
            SharedMemo.is_active.is_(True),
        )
    )
    existing_share = existing.scalar_one_or_none()

    if existing_share is not None:
        return {
            "share_id": str(existing_share.id),
            "share_token": existing_share.share_token,
            "share_url": f"/shared/{existing_share.share_token}",
            "expires_at": str(existing_share.expires_at) if existing_share.expires_at else None,
        }

    # Create new share
    token = secrets.token_urlsafe(16)
    expires_at = None
    if body and body.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)

    new_share = SharedMemo(
        execution_id=exec_uuid,
        user_id=uuid.UUID(user.sub),
        share_token=token,
        expires_at=expires_at,
    )
    db.add(new_share)
    await db.commit()
    await db.refresh(new_share)

    return {
        "share_id": str(new_share.id),
        "share_token": new_share.share_token,
        "share_url": f"/shared/{new_share.share_token}",
        "expires_at": str(new_share.expires_at) if new_share.expires_at else None,
    }


# ---------------------------------------------------------------------------
# GET /agents/research/{execution_id}/share — check share status
# ---------------------------------------------------------------------------


@router.get(
    "/agents/research/{execution_id}/share",
    dependencies=[Depends(rate_limit_dependency("60/minute"))],
)
async def get_share_status(
    execution_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if a share exists for the given execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    result = await db.execute(
        select(SharedMemo).where(
            SharedMemo.execution_id == exec_uuid,
            SharedMemo.user_id == uuid.UUID(user.sub),
            SharedMemo.is_active.is_(True),
        )
    )
    share = result.scalar_one_or_none()

    if share is None:
        return {"shared": False}

    return {
        "shared": True,
        "share_token": share.share_token,
        "share_url": f"/shared/{share.share_token}",
        "view_count": share.view_count,
        "created_at": str(share.created_at),
    }


# ---------------------------------------------------------------------------
# DELETE /agents/research/{execution_id}/share — revoke share
# ---------------------------------------------------------------------------


@router.delete(
    "/agents/research/{execution_id}/share",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def revoke_share(
    execution_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke (deactivate) a shared memo link."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    result = await db.execute(
        select(SharedMemo).where(
            SharedMemo.execution_id == exec_uuid,
            SharedMemo.user_id == uuid.UUID(user.sub),
            SharedMemo.is_active.is_(True),
        )
    )
    share = result.scalar_one_or_none()

    if share is None:
        raise HTTPException(status_code=404, detail="No active share found for this execution.")

    share.is_active = False
    await db.commit()

    return {"revoked": True, "share_id": str(share.id)}


# ---------------------------------------------------------------------------
# GET /shared/{token} — public endpoint (no auth)
# ---------------------------------------------------------------------------


@router.get(
    "/shared/{token}",
    dependencies=[Depends(rate_limit_dependency("60/minute"))],
)
async def get_shared_memo(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve a shared memo by its public token. No authentication required."""
    # Validate token format (token_urlsafe(16) produces ~22 chars)
    if not token or len(token) > 32:
        raise HTTPException(status_code=404, detail="Shared memo not found.")

    result = await db.execute(
        select(SharedMemo).where(
            SharedMemo.share_token == token,
            SharedMemo.is_active.is_(True),
        )
    )
    share = result.scalar_one_or_none()

    if share is None:
        raise HTTPException(status_code=404, detail="Shared memo not found.")

    # Check expiry
    if share.expires_at and share.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=404, detail="Shared memo has expired.")

    # Increment view count
    share.view_count = (share.view_count or 0) + 1
    await db.commit()

    # Fetch execution result_data
    exec_result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == share.execution_id)
    )
    execution = exec_result.scalar_one_or_none()

    if execution is None or execution.result_data is None:
        raise HTTPException(status_code=404, detail="Memo content not available.")

    result_data = execution.result_data
    return {
        "title": result_data.get("title", ""),
        "memo": result_data.get("memo", ""),
        "footnotes": result_data.get("footnotes", []),
        "confidence": result_data.get("confidence"),
        "agent_type": execution.agent_type,
    }
