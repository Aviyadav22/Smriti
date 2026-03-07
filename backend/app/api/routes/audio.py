"""Audio digest endpoints for case summaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

router = APIRouter()


@router.post("/{case_id}/audio/generate", status_code=202)
async def generate_audio_digest(
    case_id: str,
    language: str = Query("en", pattern="^(en|hi)$", description="Language code"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Trigger async audio digest generation for a case."""
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


@router.get("/{case_id}/audio/status")
async def get_audio_status(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check audio digest availability for a case."""
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


@router.get("/{case_id}/audio")
async def stream_audio(
    case_id: str,
    language: str = Query("en", pattern="^(en|hi)$"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream the audio digest MP3 file."""
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

    from app.core.providers.storage.local_storage import LocalStorage

    storage = LocalStorage()
    if not await storage.exists(row["audio_storage_path"]):
        raise HTTPException(status_code=404, detail="Audio file not found")

    async def audio_generator():
        async for chunk in storage.retrieve_chunked(row["audio_storage_path"]):
            yield chunk

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")
