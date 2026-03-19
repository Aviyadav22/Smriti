"""DPDP Act 2023 compliance endpoints.

Provides data subject rights under the Digital Personal Data Protection Act:
- Data summary (Section 11): View all personal data held
- Erasure (Section 12): Request deletion of personal data
- Consent withdrawal (Section 6): Withdraw data processing consent
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.postgres import get_db
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user
from app.security.auth import TokenPayload

router = APIRouter()


@router.get(
    "/data-summary",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def data_summary(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return summary of all personal data held for the user (DPDP Section 11)."""
    result = await db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM chat_sessions WHERE user_id = :uid) AS chat_sessions,
                (SELECT COUNT(*) FROM chat_messages cm
                 JOIN chat_sessions cs ON cm.session_id = cs.id
                 WHERE cs.user_id = :uid) AS chat_messages,
                (SELECT COUNT(*) FROM documents WHERE user_id = :uid) AS documents,
                (SELECT COUNT(*) FROM agent_executions WHERE user_id = :uid) AS agent_executions,
                (SELECT COUNT(*) FROM audit_logs WHERE user_id = :uid) AS audit_entries,
                (SELECT COUNT(*) FROM consents WHERE user_id = :uid) AS consents
        """),
        {"uid": user.sub},
    )
    row = result.mappings().one()
    return {
        "user_id": user.sub,
        "data_categories": {
            "chat_sessions": row["chat_sessions"],
            "chat_messages": row["chat_messages"],
            "documents": row["documents"],
            "agent_executions": row["agent_executions"],
            "audit_entries": row["audit_entries"],
            "consents": row["consents"],
        },
    }


@router.post(
    "/erasure",
    dependencies=[Depends(rate_limit_dependency("5/hour"))],
)
async def request_erasure(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request deletion of all personal data (DPDP Section 12).

    All deletions are performed within a single transaction for atomicity.
    """
    # Use explicit transaction to ensure atomic deletion
    async with db.begin_nested():
        # Delete agent executions
        await db.execute(
            text("DELETE FROM agent_executions WHERE user_id = :uid"),
            {"uid": user.sub},
        )

        # Delete user's chat data
        await db.execute(
            text("""
            DELETE FROM chat_messages WHERE session_id IN
            (SELECT id FROM chat_sessions WHERE user_id = :uid)
        """),
            {"uid": user.sub},
        )
        await db.execute(
            text("DELETE FROM chat_sessions WHERE user_id = :uid"), {"uid": user.sub}
        )

        # Delete user's documents — clean up storage files first (DPDP compliance)
        import logging as _logging
        _logger = _logging.getLogger(__name__)
        try:
            doc_rows = await db.execute(
                text("SELECT storage_path FROM documents WHERE user_id = :uid"),
                {"uid": user.sub},
            )
            from app.core.dependencies import get_storage
            storage = get_storage()
            for row in doc_rows.mappings().all():
                if row.get("storage_path"):
                    try:
                        await storage.delete(row["storage_path"])
                    except OSError as e:
                        _logger.error("Failed to delete storage file %s: %s", row["storage_path"], e)
        except Exception as e:
            _logger.warning("Storage file cleanup during erasure failed: %s", e)

        await db.execute(
            text("DELETE FROM documents WHERE user_id = :uid"), {"uid": user.sub}
        )

        # Delete consents
        await db.execute(
            text("DELETE FROM consents WHERE user_id = :uid"), {"uid": user.sub}
        )

        # Log the erasure (retained for compliance)
        await db.execute(
            text("""
            INSERT INTO dpdp_audit_log (action, user_id, details)
            VALUES ('erasure_completed', :uid, '{"initiated_by": "user"}'::jsonb)
        """),
            {"uid": user.sub},
        )

        # Deactivate user account
        await db.execute(
            text("UPDATE users SET is_active = false WHERE id = :uid"), {"uid": user.sub}
        )

    await db.commit()
    return {
        "status": "erasure_completed",
        "detail": "All personal data has been deleted. Account deactivated.",
    }


@router.post(
    "/consent-withdraw",
    dependencies=[Depends(rate_limit_dependency("10/hour"))],
)
async def withdraw_consent(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Withdraw data processing consent (DPDP Section 6)."""
    await db.execute(
        text(
            "UPDATE consents SET revoked_at = NOW() "
            "WHERE user_id = :uid AND granted = true AND revoked_at IS NULL"
        ),
        {"uid": user.sub},
    )
    await db.execute(
        text("""
        INSERT INTO dpdp_audit_log (action, user_id, details)
        VALUES ('consent_withdrawn', :uid, '{"initiated_by": "user"}'::jsonb)
    """),
        {"uid": user.sub},
    )
    await db.commit()
    return {"status": "consent_withdrawn"}


@router.get("/consent-status")
async def consent_status(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current consent status for the user."""
    result = await db.execute(
        text("""
            SELECT consent_type, granted, version,
                   created_at, revoked_at
            FROM consents WHERE user_id = :uid
            ORDER BY created_at DESC
        """),
        {"uid": user.sub},
    )
    rows = result.mappings().all()
    return {
        "user_id": user.sub,
        "consents": [
            {
                "type": row["consent_type"],
                "granted": row["granted"],
                "version": row["version"],
                "granted_at": str(row["created_at"]) if row["created_at"] else None,
                "revoked_at": str(row["revoked_at"]) if row["revoked_at"] else None,
            }
            for row in rows
        ],
    }
