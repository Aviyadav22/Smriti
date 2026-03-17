"""Async retry queue for failed citation graph builds."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_graph_failure(
    db: AsyncSession, case_id: str, error: str,
) -> None:
    """Record a failed graph build for later retry."""
    await db.execute(
        text(
            "INSERT INTO graph_build_queue (case_id, error, retry_count, created_at) "
            "VALUES (:case_id, :error, 0, NOW()) "
            "ON CONFLICT (case_id) DO UPDATE SET "
            "error = :error, retry_count = graph_build_queue.retry_count, updated_at = NOW()"
        ),
        {"case_id": case_id, "error": error[:500]},
    )
    await db.commit()


async def get_pending_retries(
    db: AsyncSession, max_retries: int = 3,
) -> list[tuple[str, int]]:
    """Return (case_id, retry_count) pairs pending graph rebuild."""
    result = await db.execute(
        text(
            "SELECT case_id, retry_count FROM graph_build_queue "
            "WHERE retry_count < :max_retries "
            "ORDER BY created_at ASC"
        ),
        {"max_retries": max_retries},
    )
    return [(row[0], row[1]) for row in result.fetchall()]


async def mark_retry_success(db: AsyncSession, case_id: str) -> None:
    """Remove a case from the retry queue after successful graph build."""
    await db.execute(
        text("DELETE FROM graph_build_queue WHERE case_id = :case_id"),
        {"case_id": case_id},
    )
    await db.commit()


async def increment_retry_count(db: AsyncSession, case_id: str) -> None:
    """Increment retry count after a failed attempt."""
    await db.execute(
        text(
            "UPDATE graph_build_queue SET retry_count = retry_count + 1, "
            "updated_at = NOW() WHERE case_id = :case_id"
        ),
        {"case_id": case_id},
    )
    await db.commit()
