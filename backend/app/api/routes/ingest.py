"""Ingestion endpoints for uploading documents."""

import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user, require_role

router = APIRouter()


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """Upload a single PDF for ingestion. Admin only."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.size and file.size > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    doc_id = str(uuid.uuid4())

    # Save uploaded file temporarily
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Create document record
    await db.execute(
        text(
            "INSERT INTO documents (id, user_id, filename, storage_path, file_size, status) "
            "VALUES (:id, :user_id, :filename, :storage_path, :file_size, :status)"
        ),
        {
            "id": doc_id,
            "user_id": current_user.sub,
            "filename": file.filename or "unknown.pdf",
            "storage_path": tmp_path,
            "file_size": len(content),
            "status": "pending",
        },
    )
    await db.commit()

    # TODO: trigger background ingestion task

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "status": "pending",
        "message": "Document queued for processing",
    }


@router.get("/status/{document_id}")
async def get_ingest_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Check ingestion status of a document."""
    result = await db.execute(
        text(
            "SELECT id, filename, status, error_message, case_id, created_at, updated_at "
            "FROM documents WHERE id = :id AND user_id = :user_id"
        ),
        {"id": document_id, "user_id": current_user.sub},
    )
    doc = result.mappings().one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return dict(doc)
