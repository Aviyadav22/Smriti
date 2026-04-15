"""Audio digest endpoints for case summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.db.postgres import get_db
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.security.auth import TokenPayload

router = APIRouter()


def _validate_uuid(value: str, name: str = "ID") -> None:
    """Validate that a string is a valid UUID format."""
    import uuid
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {name} format")


@router.post("/{case_id}/audio/generate", status_code=202, dependencies=[Depends(rate_limit_dependency("5/minute"))])
async def generate_audio_digest(
    case_id: str,
    language: str = Query("en", pattern="^(en|hi)$", description="Language code"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Trigger async audio digest generation for a case."""
    _validate_uuid(case_id, "case_id")

    case_result = await db.execute(
        text("SELECT id FROM cases WHERE id = :id"),
        {"id": case_id},
    )
    if not case_result.mappings().one_or_none():
        raise HTTPException(status_code=404, detail="Case not found")

    existing = await db.execute(
        text(
            "SELECT status FROM audio_digests "
            "WHERE case_id = :case_id AND language = :lang"
        ),
        {"case_id": case_id, "lang": language},
    )
    row = existing.mappings().one_or_none()
    if row and row["status"] == "completed":
        return {"status": "already_exists", "case_id": case_id, "language": language}
    if row and row["status"] == "generating":
        return {"status": "generating", "case_id": case_id, "language": language}

    from app.tasks.audio_tasks import generate_audio

    generate_audio.delay(case_id, language)

    return {
        "status": "queued",
        "case_id": case_id,
        "language": language,
        "message": "Audio digest generation started",
    }


@router.get("/{case_id}/audio/status", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_audio_status(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check audio digest availability for a case."""
    _validate_uuid(case_id, "case_id")

    result = await db.execute(
        text(
            "SELECT language, status, duration_seconds "
            "FROM audio_digests WHERE case_id = :case_id"
        ),
        {"case_id": case_id},
    )
    rows = result.mappings().all()

    available = [r["language"] for r in rows if r["status"] == "completed"]
    generating = [r["language"] for r in rows if r["status"] == "generating"]

    return {
        "case_id": case_id,
        "available": available,
        "generating": generating,
        "digests": [dict(r) for r in rows],
    }


@router.get("/{case_id}/audio", dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def stream_audio(
    case_id: str,
    language: str = Query("en", pattern="^(en|hi)$"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream the audio digest MP3 file."""
    _validate_uuid(case_id, "case_id")

    result = await db.execute(
        text(
            "SELECT audio_storage_path, status FROM audio_digests "
            "WHERE case_id = :case_id AND language = :lang"
        ),
        {"case_id": case_id, "lang": language},
    )
    row = result.mappings().one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Audio digest not found")
    if row["status"] != "completed":
        raise HTTPException(status_code=404, detail="Audio digest not ready yet")

    from app.core.dependencies import get_storage

    storage = get_storage()
    if not await storage.exists(row["audio_storage_path"]):
        raise HTTPException(status_code=404, detail="Audio file not found")

    async def audio_generator():
        async for chunk in storage.retrieve_chunked(row["audio_storage_path"]):
            yield chunk

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")
