"""Document upload, listing, and analysis endpoints."""

from __future__ import annotations

import contextlib
import logging
import re
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import text

from app.core.dependencies import get_storage
from app.db.postgres import get_db
from app.security.audit import create_audit_log
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.security.auth import TokenPayload

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _sanitize_filename(filename: str | None) -> str:
    """Sanitize uploaded filename to prevent path traversal and injection."""
    if not filename:
        return "upload.pdf"
    safe = Path(filename).name
    safe = re.sub(r"[^a-zA-Z0-9\-_. ]", "_", safe)
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    return safe[:200]


def _validate_pdf_content(content: bytes) -> None:
    """Validate that content is actually a PDF via magic bytes and size."""
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit",
        )


@router.post("/upload", status_code=202, dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Upload a PDF document for analysis. Any authenticated user."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    doc_id = str(uuid.uuid4())
    content = await file.read()

    # Validate PDF magic bytes and enforce size limit on actual content
    _validate_pdf_content(content)

    safe_filename = _sanitize_filename(file.filename)
    storage = get_storage()
    tmp_path: str | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        storage_path = await storage.store(tmp_path, f"documents/{doc_id}/{safe_filename}")
    finally:
        if tmp_path:
            with contextlib.suppress(OSError):
                Path(tmp_path).unlink(missing_ok=True)

    await db.execute(
        text(
            "INSERT INTO documents (id, user_id, filename, storage_path, file_size, status) "
            "VALUES (:id, :user_id, :filename, :storage_path, :file_size, 'pending')"
        ),
        {
            "id": doc_id,
            "user_id": current_user.sub,
            "filename": safe_filename,
            "storage_path": storage_path,
            "file_size": len(content),
        },
    )
    await db.commit()

    from app.tasks.document_tasks import analyze_document

    analyze_document.delay(doc_id)

    return {
        "document_id": doc_id,
        "filename": safe_filename,
        "status": "pending",
        "message": "Document uploaded and queued for analysis",
    }


@router.get("", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """List current user's uploaded documents."""
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM documents WHERE user_id = :user_id"),
        {"user_id": current_user.sub},
    )
    total = count_result.scalar_one_or_none() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        text(
            "SELECT id, filename, status, processing_step, file_size, "
            "created_at, updated_at, error_message "
            "FROM documents WHERE user_id = :user_id "
            "ORDER BY created_at DESC OFFSET :offset LIMIT :limit"
        ),
        {"user_id": current_user.sub, "offset": offset, "limit": page_size},
    )
    docs = [dict(row) for row in result.mappings().all()]

    total_pages = max(1, (total + page_size - 1) // page_size)

    return {
        "documents": docs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/{document_id}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Get document details with analysis results."""
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    result = await db.execute(
        text(
            "SELECT id, filename, status, processing_step, file_size, "
            "error_message, created_at, updated_at, "
            "processing_started_at, processing_completed_at "
            "FROM documents WHERE id = :id AND user_id = :user_id"
        ),
        {"id": document_id, "user_id": current_user.sub},
    )
    doc = result.mappings().one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    response = dict(doc)

    if doc["status"] == "completed":
        analysis_result = await db.execute(
            text(
                "SELECT issues, parties, key_facts, relief_sought, "
                "counter_arguments, research_memo "
                "FROM document_analyses WHERE document_id = :doc_id"
            ),
            {"doc_id": document_id},
        )
        analysis = analysis_result.mappings().one_or_none()
        if analysis:
            response["analysis"] = dict(analysis)

    return response


@router.delete("/{document_id}", dependencies=[Depends(rate_limit_dependency("20/minute"))])
async def delete_document(
    document_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Delete a document and its analysis. Owner only."""
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    result = await db.execute(
        text("SELECT id, storage_path FROM documents " "WHERE id = :id AND user_id = :user_id"),
        {"id": document_id, "user_id": current_user.sub},
    )
    doc = result.mappings().one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage = get_storage()
    try:
        await storage.delete(doc["storage_path"])
    except OSError as e:
        logger.error("Failed to delete storage file %s: %s", doc["storage_path"], e)
        # Continue with database deletion — orphaned file is better than orphaned DB record

    await db.execute(
        text("DELETE FROM documents WHERE id = :id"),
        {"id": document_id},
    )
    await db.commit()

    await create_audit_log(
        db=db,
        action="document.delete",
        user_id=current_user.sub,
        resource_type="document",
        resource_id=document_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"status": "deleted"}


@router.get("/{document_id}/memo", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_research_memo(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Get the research memo for a document."""
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    doc_result = await db.execute(
        text("SELECT id FROM documents WHERE id = :id AND user_id = :user_id"),
        {"id": document_id, "user_id": current_user.sub},
    )
    if not doc_result.mappings().one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        text("SELECT research_memo FROM document_analyses WHERE document_id = :doc_id"),
        {"doc_id": document_id},
    )
    row = result.mappings().one_or_none()
    if not row or not row["research_memo"]:
        raise HTTPException(status_code=404, detail="Research memo not available yet")

    return {"memo": row["research_memo"]}
