"""Audit logging for security-sensitive operations.

Records user actions to the ``audit_logs`` database table for compliance
and forensic analysis.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_audit_log(
    db: AsyncSession,
    action: str,
    user_id: str | None,
    resource_type: str,
    resource_id: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, str | int | float | bool | None] | None = None,
) -> None:
    """Insert an audit log entry into the database.

    Args:
        db: Async SQLAlchemy session.
        action: The action performed (e.g., ``"login"``, ``"search"``,
            ``"document.view"``, ``"admin.delete_user"``).
        user_id: The ID of the user who performed the action, or None
            for unauthenticated actions.
        resource_type: The type of resource affected (e.g., ``"user"``,
            ``"document"``, ``"search_query"``).
        resource_id: The ID of the specific resource, or None if not
            applicable.
        ip_address: The client's IP address.
        user_agent: The client's User-Agent header value.
        metadata: Additional key-value data to store with the log entry.
    """
    now = datetime.now(timezone.utc)
    metadata_json = json.dumps(metadata) if metadata else None

    await db.execute(
        text(
            """
            INSERT INTO audit_logs (
                action,
                user_id,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                metadata,
                created_at
            ) VALUES (
                :action,
                :user_id,
                :resource_type,
                :resource_id,
                :ip_address,
                :user_agent,
                :metadata,
                :created_at
            )
            """
        ),
        {
            "action": action,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "metadata": metadata_json,
            "created_at": now,
        },
    )
    await db.commit()
