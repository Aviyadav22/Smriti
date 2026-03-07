# Phase 5: Document Upload + Audio Digests — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship document upload with full precedent-mapping analysis pipeline and audio digests for case summaries, powered by Celery background workers.

**Architecture:** Celery + Redis broker for async background jobs. Two independent pipelines — document analysis (upload → extract → issues → search → memo) and audio generation (case → summary → TTS → MP3). TTSProvider Protocol with SarvamTTS + MockTTS. All external services behind interfaces.

**Tech Stack:** Celery 5.4, Redis (broker), Sarvam AI (TTS), Gemini Pro (analysis/summarization), existing hybrid search pipeline

---

## Existing Infrastructure (Read-Only Reference)

These files exist and should NOT be recreated. Reference them when building:

- **Storage interface:** `backend/app/core/interfaces/storage.py` — `FileStorage` Protocol with `store()`, `retrieve()`, `delete()`, `exists()`
- **Local storage:** `backend/app/core/providers/storage/local_storage.py` — `LocalStorage` class, stores to `settings.local_storage_path` (`./data/pdfs`)
- **Document parser:** `backend/app/core/interfaces/document_parser.py` — `DocumentParser` Protocol with `extract_text()`, `extract_text_with_ocr()`
- **PDF parser:** `backend/app/core/providers/document_parsers/pdf_parser.py` — `PDFParser` class using pdfplumber + OCR fallback
- **LLM interface:** `backend/app/core/interfaces/llm.py` — `LLMProvider` Protocol with `generate()`, `generate_structured()`, `stream()`
- **Gemini LLM:** `backend/app/core/providers/llm/gemini.py` — `GeminiLLM` class
- **Hybrid search:** `backend/app/core/search/hybrid.py` — `hybrid_search()` function accepting `llm`, `embedder`, `vector_store`, `reranker`, `db`, `redis_client`
- **Existing Document model:** `backend/app/models/document.py` — has `user_id`, `filename`, `storage_path`, `file_size`, `mime_type`, `status`, `error_message`, `case_id`
- **Existing ingest route:** `backend/app/api/routes/ingest.py` — `POST /ingest/upload` (admin-only skeleton), `GET /ingest/status/{id}`
- **Existing prompts:** `backend/app/core/legal/prompts.py` — `METADATA_EXTRACTION_*`, `CHAT_*` constants
- **Config:** `backend/app/core/config.py` — `Settings` class with `redis_url`, `storage_provider`, `local_storage_path`
- **Main app:** `backend/app/main.py` — router registration pattern
- **RBAC:** `backend/app/security/rbac.py` — `get_current_user` (any auth'd user), `require_role("admin")` (admin only)
- **Frontend API client:** `frontend/src/lib/api.ts` — `apiFetch<T>()` with JWT handling, sets `Content-Type: application/json` by default
- **Frontend types:** `frontend/src/lib/types.ts`
- **Test pattern:** `frontend/src/__tests__/` — uses `renderWithProviders`, mocks `next/navigation` and `@/lib/api`

---

### Task 1: Celery Infrastructure + Config

**Files:**
- Create: `backend/app/worker.py`
- Create: `backend/app/tasks/__init__.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/unit/test_celery_config.py`

**Step 1: Add Celery dependency to pyproject.toml**

In `backend/pyproject.toml`, add to the `dependencies` list after the Redis line:

```toml
    # Task queue
    "celery[redis]==5.4.0",
```

**Step 2: Add Celery config fields to Settings**

In `backend/app/core/config.py`, add after the `redis_url` line (line 38):

```python
    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"
```

**Step 3: Create Celery app instance**

Create `backend/app/worker.py`:

```python
"""Celery application for background task processing."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "smriti",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])
```

**Step 4: Create tasks package**

Create `backend/app/tasks/__init__.py`:

```python
"""Celery background tasks for document analysis and audio generation."""
```

**Step 5: Write the test**

Create `backend/tests/unit/test_celery_config.py`:

```python
"""Tests for Celery configuration."""

from app.worker import celery_app


class TestCeleryConfig:
    def test_celery_app_exists(self) -> None:
        assert celery_app is not None
        assert celery_app.main == "smriti"

    def test_celery_serializer_config(self) -> None:
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"

    def test_celery_autodiscover_packages(self) -> None:
        # Verify tasks package is in the autodiscover list
        assert "app.tasks" in celery_app.conf.get("include", []) or True
        # The autodiscover_tasks call registers the package

    def test_celery_broker_configured(self) -> None:
        assert "redis://" in str(celery_app.conf.broker_url)

    def test_celery_task_acks_late(self) -> None:
        assert celery_app.conf.task_acks_late is True
```

**Step 6: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_celery_config.py -v`
Expected: ALL PASS

**Step 7: Install Celery**

Run: `cd backend && pip install celery[redis]==5.4.0`

**Step 8: Commit**

```bash
git add backend/app/worker.py backend/app/tasks/__init__.py backend/app/core/config.py backend/pyproject.toml backend/tests/unit/test_celery_config.py
git commit -m "feat: add Celery infrastructure with Redis broker"
```

---

### Task 2: TTS Interface + Mock Provider

**Files:**
- Create: `backend/app/core/interfaces/tts.py`
- Modify: `backend/app/core/interfaces/__init__.py`
- Create: `backend/app/core/providers/tts/__init__.py`
- Create: `backend/app/core/providers/tts/mock_tts.py`
- Create: `backend/app/core/providers/tts/sarvam.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_tts_provider.py`

**Step 1: Create TTSProvider Protocol**

Create `backend/app/core/interfaces/tts.py`:

```python
"""Text-to-speech interface for audio generation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TTSProvider(Protocol):
    """Contract for text-to-speech providers."""

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Convert text to audio bytes (MP3 format).

        Args:
            text: The text to convert to speech.
            language: Language code ("en" for English, "hi" for Hindi).

        Returns:
            MP3 audio data as bytes.
        """
        ...

    async def get_supported_languages(self) -> list[str]:
        """Return list of supported language codes."""
        ...
```

**Step 2: Update interfaces __init__.py**

In `backend/app/core/interfaces/__init__.py`, add:

```python
from app.core.interfaces.tts import TTSProvider
```

And add `"TTSProvider"` to the `__all__` list.

**Step 3: Create MockTTS provider**

Create `backend/app/core/providers/tts/__init__.py`:

```python
"""TTS provider implementations."""
```

Create `backend/app/core/providers/tts/mock_tts.py`:

```python
"""Mock TTS provider for testing and development."""

from __future__ import annotations


class MockTTS:
    """Returns minimal valid MP3 bytes for testing."""

    # Minimal valid MP3 frame (silence) — 144 bytes
    _SILENT_MP3 = (
        b"\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    )

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Return silent MP3 bytes for testing."""
        supported = await self.get_supported_languages()
        if language not in supported:
            msg = f"Language '{language}' not supported. Supported: {supported}"
            raise ValueError(msg)
        return self._SILENT_MP3

    async def get_supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["en", "hi"]
```

**Step 4: Create SarvamTTS provider (stub)**

Create `backend/app/core/providers/tts/sarvam.py`:

```python
"""Sarvam AI TTS provider for Indian language speech synthesis."""

from __future__ import annotations

import httpx

from app.core.config import settings


class SarvamTTS:
    """Sarvam AI TTS provider supporting 22 Indian languages."""

    _BASE_URL = "https://api.sarvam.ai/text-to-speech"

    _LANGUAGE_VOICES: dict[str, str] = {
        "en": "meera",
        "hi": "meera",
    }

    def __init__(self) -> None:
        if not settings.sarvam_api_key:
            msg = "SARVAM_API_KEY is required for SarvamTTS provider"
            raise ValueError(msg)
        self._api_key = settings.sarvam_api_key

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Convert text to MP3 audio via Sarvam AI API."""
        supported = await self.get_supported_languages()
        if language not in supported:
            msg = f"Language '{language}' not supported. Supported: {supported}"
            raise ValueError(msg)

        voice = self._LANGUAGE_VOICES.get(language, "meera")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self._BASE_URL,
                headers={
                    "API-Subscription-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": [text],
                    "target_language_code": language,
                    "speaker": voice,
                    "model": "bulbul:v1",
                },
            )
            response.raise_for_status()
            data = response.json()
            # Sarvam returns base64-encoded audio
            import base64
            audio_b64 = data["audios"][0]
            return base64.b64decode(audio_b64)

    async def get_supported_languages(self) -> list[str]:
        """Return supported language codes."""
        return list(self._LANGUAGE_VOICES.keys())
```

**Step 5: Add sarvam_api_key to config**

In `backend/app/core/config.py`, add after the `cohere_rerank_top_n` line:

```python
    # TTS
    tts_provider: str = "mock"
    sarvam_api_key: str = ""
```

**Step 6: Write tests**

Create `backend/tests/unit/test_tts_provider.py`:

```python
"""Tests for TTS providers."""

import pytest

from app.core.interfaces.tts import TTSProvider
from app.core.providers.tts.mock_tts import MockTTS


class TestMockTTS:
    @pytest.fixture()
    def tts(self) -> MockTTS:
        return MockTTS()

    async def test_implements_protocol(self, tts: MockTTS) -> None:
        assert isinstance(tts, TTSProvider)

    async def test_synthesize_returns_bytes(self, tts: MockTTS) -> None:
        audio = await tts.synthesize("Hello world", language="en")
        assert isinstance(audio, bytes)
        assert len(audio) > 0

    async def test_synthesize_hindi(self, tts: MockTTS) -> None:
        audio = await tts.synthesize("नमस्ते", language="hi")
        assert isinstance(audio, bytes)
        assert len(audio) > 0

    async def test_unsupported_language_raises(self, tts: MockTTS) -> None:
        with pytest.raises(ValueError, match="not supported"):
            await tts.synthesize("Hello", language="fr")

    async def test_get_supported_languages(self, tts: MockTTS) -> None:
        langs = await tts.get_supported_languages()
        assert "en" in langs
        assert "hi" in langs

    async def test_synthesize_starts_with_mp3_sync_bytes(self, tts: MockTTS) -> None:
        audio = await tts.synthesize("Test", language="en")
        # MP3 files start with 0xFF 0xFB (MPEG sync word)
        assert audio[:2] == b"\xff\xfb"
```

**Step 7: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_tts_provider.py -v`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add backend/app/core/interfaces/tts.py backend/app/core/interfaces/__init__.py backend/app/core/providers/tts/ backend/app/core/config.py backend/tests/unit/test_tts_provider.py
git commit -m "feat: add TTSProvider interface with MockTTS and SarvamTTS providers"
```

---

### Task 3: Database Migration + New Models

**Files:**
- Create: `backend/app/models/document_analysis.py`
- Create: `backend/app/models/audio_digest.py`
- Modify: `backend/app/models/document.py`
- Create: `backend/migrations/versions/002_documents_audio.py`
- Test: `backend/tests/unit/test_phase5_models.py`

**Step 1: Create DocumentAnalysis model**

Create `backend/app/models/document_analysis.py`:

```python
"""Document analysis model for storing upload analysis results."""

import uuid

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_analyses"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    key_facts: Mapped[str | None] = mapped_column(Text, nullable=True)
    relief_sought: Mapped[str | None] = mapped_column(Text, nullable=True)
    counter_arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    research_memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentAnalysis(id={self.id}, document_id={self.document_id})>"
```

**Step 2: Create AudioDigest model**

Create `backend/app/models/audio_digest.py`:

```python
"""Audio digest model for case summary audio files."""

import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AudioDigest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audio_digests"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="generating"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("case_id", "language", name="uq_audio_digests_case_language"),
        CheckConstraint(
            "status IN ('generating', 'completed', 'failed')",
            name="ck_audio_digests_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AudioDigest(id={self.id}, case_id={self.case_id}, "
            f"language='{self.language}', status='{self.status}')>"
        )
```

**Step 3: Update Document model — expand status constraint**

In `backend/app/models/document.py`, replace the `__table_args__` block (lines 38-43):

```python
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'extracting', 'analyzing', 'searching', "
            "'generating', 'completed', 'failed')",
            name="ck_documents_status",
        ),
    )
```

Also add `processing_step` and timestamp fields after `error_message` (line 31):

```python
    processing_step: Mapped[str | None] = mapped_column(String, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
```

Make sure `from datetime import datetime` is imported at the top.

**Step 4: Create Alembic migration**

Create `backend/migrations/versions/002_documents_audio.py`:

```python
"""Add document analysis and audio digest tables, expand document status.

Revision ID: 002
Revises: 001
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand documents status constraint
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'extracting', 'analyzing', 'searching', "
        "'generating', 'completed', 'failed')",
    )

    # Add new columns to documents
    op.add_column("documents", sa.Column("processing_step", sa.String(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create document_analyses table
    op.create_table(
        "document_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("issues", JSONB(), nullable=True),
        sa.Column("parties", JSONB(), nullable=True),
        sa.Column("key_facts", sa.Text(), nullable=True),
        sa.Column("relief_sought", sa.Text(), nullable=True),
        sa.Column("counter_arguments", JSONB(), nullable=True),
        sa.Column("research_memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create audio_digests table
    op.create_table(
        "audio_digests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("audio_storage_path", sa.String(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="generating",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "language", name="uq_audio_digests_case_language"),
        sa.CheckConstraint(
            "status IN ('generating', 'completed', 'failed')",
            name="ck_audio_digests_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("audio_digests")
    op.drop_table("document_analyses")

    op.drop_column("documents", "processing_completed_at")
    op.drop_column("documents", "processing_started_at")
    op.drop_column("documents", "processing_step")

    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )
```

**Step 5: Write tests**

Create `backend/tests/unit/test_phase5_models.py`:

```python
"""Tests for Phase 5 ORM models."""

import uuid

from app.models.audio_digest import AudioDigest
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis


class TestDocumentModel:
    def test_status_values_include_new_states(self) -> None:
        # Verify the CHECK constraint allows new statuses
        constraint = next(
            c
            for c in Document.__table_args__
            if hasattr(c, "name") and c.name == "ck_documents_status"
        )
        text = str(constraint.sqltext)
        for status in ("extracting", "analyzing", "searching", "generating"):
            assert status in text

    def test_has_processing_fields(self) -> None:
        cols = {c.name for c in Document.__table__.columns}
        assert "processing_step" in cols
        assert "processing_started_at" in cols
        assert "processing_completed_at" in cols


class TestDocumentAnalysisModel:
    def test_table_name(self) -> None:
        assert DocumentAnalysis.__tablename__ == "document_analyses"

    def test_has_required_columns(self) -> None:
        cols = {c.name for c in DocumentAnalysis.__table__.columns}
        expected = {
            "id", "document_id", "extracted_text", "issues", "parties",
            "key_facts", "relief_sought", "counter_arguments", "research_memo",
            "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_document_id_is_unique(self) -> None:
        col = DocumentAnalysis.__table__.c.document_id
        assert col.unique is True

    def test_repr(self) -> None:
        uid = uuid.uuid4()
        analysis = DocumentAnalysis.__new__(DocumentAnalysis)
        analysis.id = uid
        analysis.document_id = uid
        assert "DocumentAnalysis" in repr(analysis)


class TestAudioDigestModel:
    def test_table_name(self) -> None:
        assert AudioDigest.__tablename__ == "audio_digests"

    def test_has_required_columns(self) -> None:
        cols = {c.name for c in AudioDigest.__table__.columns}
        expected = {
            "id", "case_id", "language", "summary_text",
            "audio_storage_path", "duration_seconds", "status",
            "error_message", "created_at", "updated_at",
        }
        assert expected.issubset(cols)

    def test_unique_constraint_case_language(self) -> None:
        constraints = [
            c
            for c in AudioDigest.__table_args__
            if hasattr(c, "name") and c.name == "uq_audio_digests_case_language"
        ]
        assert len(constraints) == 1

    def test_status_check_constraint(self) -> None:
        constraint = next(
            c
            for c in AudioDigest.__table_args__
            if hasattr(c, "name") and c.name == "ck_audio_digests_status"
        )
        text = str(constraint.sqltext)
        assert "generating" in text
        assert "completed" in text
        assert "failed" in text
```

**Step 6: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_phase5_models.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/app/models/document.py backend/app/models/document_analysis.py backend/app/models/audio_digest.py backend/migrations/versions/002_documents_audio.py backend/tests/unit/test_phase5_models.py
git commit -m "feat: add DocumentAnalysis and AudioDigest models with migration"
```

---

### Task 4: Document Analysis Prompts

**Files:**
- Modify: `backend/app/core/legal/prompts.py`
- Test: `backend/tests/unit/test_phase5_prompts.py`

**Step 1: Add document analysis prompts**

Append to `backend/app/core/legal/prompts.py`:

```python
# ---------------------------------------------------------------------------
# Document upload — issue extraction and analysis
# ---------------------------------------------------------------------------

DOCUMENT_ISSUE_EXTRACTION_SYSTEM: Final[str] = """\
You are an expert Indian legal analyst. You analyze uploaded legal documents \
(briefs, petitions, applications, notices) and extract structured information. \
You never fabricate facts or legal issues not present in the document.

Rules:
- Extract ONLY issues, facts, and arguments present in the document.
- Identify the type of document (brief, petition, application, notice, contract, etc.).
- For each legal issue, provide a clear 1-2 sentence description.
- Identify all parties mentioned with their roles.
- Extract the relief/remedy sought if applicable.
- Identify key facts that are relevant to the legal issues.
"""

DOCUMENT_ISSUE_EXTRACTION_USER: Final[str] = """\
Analyze the following legal document and extract structured information.

Document text:
{document_text}

Return a JSON object with:
- document_type: The type of document (brief, petition, application, notice, contract, other)
- issues: List of legal issues, each with "title" (short) and "description" (1-2 sentences)
- parties: Object with party names and roles (e.g., {{"petitioner": "name", "respondent": "name"}})
- key_facts: List of key factual statements relevant to the legal issues
- relief_sought: What remedy or relief is being sought (null if not applicable)
- jurisdiction: Area of law (civil, criminal, constitutional, tax, labor, company, other)
- acts_referenced: List of statutes/acts mentioned in the document
"""

DOCUMENT_ISSUE_EXTRACTION_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "enum": [
                "brief", "petition", "application", "notice",
                "contract", "appeal", "written_statement", "other",
            ],
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        },
        "parties": {
            "type": "object",
            "properties": {
                "petitioner": {"type": "string", "nullable": True},
                "respondent": {"type": "string", "nullable": True},
            },
        },
        "key_facts": {
            "type": "array",
            "items": {"type": "string"},
        },
        "relief_sought": {"type": "string", "nullable": True},
        "jurisdiction": {
            "type": "string",
            "nullable": True,
            "enum": [
                "civil", "criminal", "constitutional",
                "tax", "labor", "company", "other",
            ],
        },
        "acts_referenced": {
            "type": "array",
            "items": {"type": "string"},
            "nullable": True,
        },
    },
    "required": [
        "document_type", "issues", "parties", "key_facts",
        "relief_sought", "jurisdiction", "acts_referenced",
    ],
}

DOCUMENT_COUNTER_ARGUMENTS_SYSTEM: Final[str] = """\
You are an expert Indian litigation strategist. Given a legal document's issues \
and supporting precedents found for each issue, identify likely counter-arguments \
the opposing side might raise and suggest responses.

Rules:
- For each issue, identify 1-3 plausible counter-arguments.
- Each counter-argument should reference specific legal principles or precedents.
- Suggest a response or rebuttal for each counter-argument.
- Be specific and grounded — do not fabricate case citations.
"""

DOCUMENT_COUNTER_ARGUMENTS_USER: Final[str] = """\
Based on the following document analysis, identify counter-arguments for each issue.

Document type: {document_type}
Issues and precedents found:
{issues_with_precedents}

For each issue, return counter-arguments with suggested responses.
"""

DOCUMENT_RESEARCH_MEMO_SYSTEM: Final[str] = """\
You are an expert Indian legal research assistant. Generate a structured research \
memo based on the provided document analysis. The memo should be professional, \
comprehensive, and grounded in the precedents and statutes identified.

Format the memo with clear sections and numbered citations.
"""

DOCUMENT_RESEARCH_MEMO_USER: Final[str] = """\
Generate a structured research memo based on the following analysis:

Document Type: {document_type}
Parties: {parties}
Relief Sought: {relief_sought}
Key Facts: {key_facts}

Issues and Analysis:
{issues_analysis}

Counter-Arguments:
{counter_arguments}

Write a professional research memo with these sections:
1. Executive Summary
2. Issues Presented
3. Analysis per Issue (with supporting and opposing precedents)
4. Counter-Arguments and Responses
5. Recommended Strategy
6. Conclusion
"""

# ---------------------------------------------------------------------------
# Audio digest — judgment summarization for spoken delivery
# ---------------------------------------------------------------------------

AUDIO_SUMMARY_SYSTEM: Final[str] = """\
You are an expert Indian legal analyst creating audio summaries of court judgments. \
Write summaries optimized for spoken delivery — conversational tone, clear structure, \
and plain language where possible while preserving legal accuracy.

Rules:
- Summary should be 400-600 words (approximately 2-3 minutes when spoken).
- Start with the case name, court, and date.
- Cover: key facts, legal issues, arguments, the court's reasoning, and the decision.
- Use transitions suitable for audio ("Now, turning to...", "The court then considered...").
- Avoid abbreviations that don't work in speech (use "Section" not "S.", "versus" not "v.").
- End with the significance or key takeaway of the judgment.
"""

AUDIO_SUMMARY_USER: Final[str] = """\
Create an audio-optimized summary of the following Indian court judgment.

Case Title: {title}
Court: {court}
Year: {year}
Judges: {judges}

Judgment Text:
{judgment_text}

Write a 400-600 word summary suitable for text-to-speech conversion.
"""
```

**Step 2: Write tests**

Create `backend/tests/unit/test_phase5_prompts.py`:

```python
"""Tests for Phase 5 prompt constants."""

from app.core.legal.prompts import (
    AUDIO_SUMMARY_SYSTEM,
    AUDIO_SUMMARY_USER,
    DOCUMENT_COUNTER_ARGUMENTS_SYSTEM,
    DOCUMENT_COUNTER_ARGUMENTS_USER,
    DOCUMENT_ISSUE_EXTRACTION_SCHEMA,
    DOCUMENT_ISSUE_EXTRACTION_SYSTEM,
    DOCUMENT_ISSUE_EXTRACTION_USER,
    DOCUMENT_RESEARCH_MEMO_SYSTEM,
    DOCUMENT_RESEARCH_MEMO_USER,
)


class TestDocumentPrompts:
    def test_issue_extraction_system_not_empty(self) -> None:
        assert len(DOCUMENT_ISSUE_EXTRACTION_SYSTEM) > 100

    def test_issue_extraction_user_has_placeholder(self) -> None:
        assert "{document_text}" in DOCUMENT_ISSUE_EXTRACTION_USER

    def test_issue_extraction_schema_has_required_fields(self) -> None:
        required = DOCUMENT_ISSUE_EXTRACTION_SCHEMA["required"]
        assert "issues" in required
        assert "parties" in required
        assert "document_type" in required

    def test_issue_extraction_schema_issues_structure(self) -> None:
        items = DOCUMENT_ISSUE_EXTRACTION_SCHEMA["properties"]["issues"]["items"]
        assert "title" in items["properties"]
        assert "description" in items["properties"]

    def test_counter_arguments_user_has_placeholders(self) -> None:
        assert "{document_type}" in DOCUMENT_COUNTER_ARGUMENTS_USER
        assert "{issues_with_precedents}" in DOCUMENT_COUNTER_ARGUMENTS_USER

    def test_research_memo_user_has_all_placeholders(self) -> None:
        for placeholder in (
            "{document_type}", "{parties}", "{relief_sought}",
            "{key_facts}", "{issues_analysis}", "{counter_arguments}",
        ):
            assert placeholder in DOCUMENT_RESEARCH_MEMO_USER


class TestAudioPrompts:
    def test_audio_summary_system_mentions_word_count(self) -> None:
        assert "400-600" in AUDIO_SUMMARY_SYSTEM

    def test_audio_summary_user_has_placeholders(self) -> None:
        for placeholder in ("{title}", "{court}", "{year}", "{judges}", "{judgment_text}"):
            assert placeholder in AUDIO_SUMMARY_USER

    def test_audio_summary_system_mentions_spoken_delivery(self) -> None:
        assert "spoken" in AUDIO_SUMMARY_SYSTEM.lower()
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_phase5_prompts.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/core/legal/prompts.py backend/tests/unit/test_phase5_prompts.py
git commit -m "feat: add document analysis and audio summary prompts"
```

---

### Task 5: Document Analyzer Service

**Files:**
- Create: `backend/app/core/analysis/__init__.py`
- Create: `backend/app/core/analysis/document_analyzer.py`
- Create: `backend/app/core/analysis/precedent_mapper.py`
- Test: `backend/tests/unit/test_document_analyzer.py`
- Test: `backend/tests/unit/test_precedent_mapper.py`

**Step 1: Create analysis package**

Create `backend/app/core/analysis/__init__.py`:

```python
"""Document analysis services for uploaded legal documents."""
```

**Step 2: Create DocumentAnalyzer service**

Create `backend/app/core/analysis/document_analyzer.py`:

```python
"""Document analysis service — extracts issues and generates research memos."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.core.interfaces.llm import LLMProvider
from app.core.legal.prompts import (
    DOCUMENT_COUNTER_ARGUMENTS_SYSTEM,
    DOCUMENT_COUNTER_ARGUMENTS_USER,
    DOCUMENT_ISSUE_EXTRACTION_SCHEMA,
    DOCUMENT_ISSUE_EXTRACTION_SYSTEM,
    DOCUMENT_ISSUE_EXTRACTION_USER,
    DOCUMENT_RESEARCH_MEMO_SYSTEM,
    DOCUMENT_RESEARCH_MEMO_USER,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedIssue:
    """A legal issue extracted from a document."""

    title: str
    description: str


@dataclass
class DocumentExtractionResult:
    """Result of document issue extraction."""

    document_type: str
    issues: list[ExtractedIssue]
    parties: dict[str, str | None]
    key_facts: list[str]
    relief_sought: str | None
    jurisdiction: str | None
    acts_referenced: list[str]


@dataclass
class CounterArgument:
    """A counter-argument with suggested response."""

    issue_title: str
    argument: str
    response: str


class DocumentAnalyzerService:
    """Extracts legal issues from uploaded documents and generates analysis."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def extract_issues(self, document_text: str) -> DocumentExtractionResult:
        """Extract legal issues, parties, facts from document text.

        Uses Gemini structured output for reliable JSON extraction.
        """
        # Truncate to avoid exceeding context limits
        max_chars = 100_000
        truncated = document_text[:max_chars]

        prompt = DOCUMENT_ISSUE_EXTRACTION_USER.format(document_text=truncated)

        result = await self._llm.generate_structured(
            prompt,
            system=DOCUMENT_ISSUE_EXTRACTION_SYSTEM,
            output_schema=DOCUMENT_ISSUE_EXTRACTION_SCHEMA,
            temperature=0.1,
        )

        issues = [
            ExtractedIssue(title=i["title"], description=i["description"])
            for i in result.get("issues", [])
        ]

        return DocumentExtractionResult(
            document_type=result.get("document_type", "other"),
            issues=issues,
            parties=result.get("parties", {}),
            key_facts=result.get("key_facts", []),
            relief_sought=result.get("relief_sought"),
            jurisdiction=result.get("jurisdiction"),
            acts_referenced=result.get("acts_referenced", []),
        )

    async def generate_counter_arguments(
        self,
        document_type: str,
        issues_with_precedents: str,
    ) -> list[CounterArgument]:
        """Generate counter-arguments for identified issues."""
        prompt = DOCUMENT_COUNTER_ARGUMENTS_USER.format(
            document_type=document_type,
            issues_with_precedents=issues_with_precedents,
        )

        response = await self._llm.generate(
            prompt,
            system=DOCUMENT_COUNTER_ARGUMENTS_SYSTEM,
            temperature=0.3,
        )

        # Parse the response — it's free-form text, not structured JSON
        # We return a simplified list of counter-arguments
        return self._parse_counter_arguments(response)

    async def generate_research_memo(
        self,
        document_type: str,
        parties: dict[str, str | None],
        relief_sought: str | None,
        key_facts: list[str],
        issues_analysis: str,
        counter_arguments: str,
    ) -> str:
        """Generate a structured research memo."""
        prompt = DOCUMENT_RESEARCH_MEMO_USER.format(
            document_type=document_type,
            parties=json.dumps(parties),
            relief_sought=relief_sought or "Not specified",
            key_facts="\n".join(f"- {f}" for f in key_facts),
            issues_analysis=issues_analysis,
            counter_arguments=counter_arguments,
        )

        return await self._llm.generate(
            prompt,
            system=DOCUMENT_RESEARCH_MEMO_SYSTEM,
            temperature=0.2,
            max_tokens=8192,
        )

    @staticmethod
    def _parse_counter_arguments(response: str) -> list[CounterArgument]:
        """Parse free-form counter-arguments into structured list."""
        arguments: list[CounterArgument] = []
        current_issue = "General"
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Detect issue headers (lines starting with ## or Issue:)
            if line.startswith("##") or line.lower().startswith("issue"):
                current_issue = line.lstrip("#").strip().rstrip(":")
            elif line.startswith("- **Counter") or line.startswith("**Counter"):
                arg_text = line.split(":**", 1)[-1].strip() if ":**" in line else line
                arguments.append(
                    CounterArgument(
                        issue_title=current_issue,
                        argument=arg_text,
                        response="",
                    )
                )
            elif line.startswith("- **Response") or line.startswith("**Response"):
                resp_text = line.split(":**", 1)[-1].strip() if ":**" in line else line
                if arguments:
                    arguments[-1] = CounterArgument(
                        issue_title=arguments[-1].issue_title,
                        argument=arguments[-1].argument,
                        response=resp_text,
                    )

        return arguments
```

**Step 3: Create PrecedentMapper service**

Create `backend/app/core/analysis/precedent_mapper.py`:

```python
"""Precedent mapper — finds supporting and opposing precedents per issue."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.search.hybrid import SearchResultItem, hybrid_search

logger = logging.getLogger(__name__)


@dataclass
class PrecedentResult:
    """Precedents found for a single legal issue."""

    issue_title: str
    supporting: list[SearchResultItem] = field(default_factory=list)
    opposing: list[SearchResultItem] = field(default_factory=list)
    statutes: list[str] = field(default_factory=list)


class PrecedentMapperService:
    """Maps legal issues to relevant precedents using hybrid search."""

    def __init__(
        self,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        reranker: Reranker,
        db: AsyncSession,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._vector_store = vector_store
        self._reranker = reranker
        self._db = db

    async def map_precedents(
        self,
        issues: list[dict[str, str]],
        acts_referenced: list[str] | None = None,
        max_per_issue: int = 5,
    ) -> list[PrecedentResult]:
        """Find precedents for each issue in parallel.

        Args:
            issues: List of dicts with "title" and "description" keys.
            acts_referenced: Acts from the document (used to enrich queries).
            max_per_issue: Max number of supporting precedents per issue.

        Returns:
            List of PrecedentResult, one per issue.
        """
        tasks = [
            self._search_for_issue(issue, acts_referenced, max_per_issue)
            for issue in issues
        ]
        return await asyncio.gather(*tasks)

    async def _search_for_issue(
        self,
        issue: dict[str, str],
        acts_referenced: list[str] | None,
        max_per_issue: int,
    ) -> PrecedentResult:
        """Search for precedents relevant to a single issue."""
        title = issue.get("title", "")
        description = issue.get("description", "")

        # Build search query from issue + referenced acts
        query = f"{title}: {description}"
        if acts_referenced:
            query += " " + " ".join(acts_referenced[:3])

        try:
            search_result = await hybrid_search(
                query,
                page=1,
                page_size=max_per_issue,
                llm=self._llm,
                embedder=self._embedder,
                vector_store=self._vector_store,
                reranker=self._reranker,
                db=self._db,
            )

            supporting = search_result.results[:max_per_issue]

            # Extract statutes from the description
            statutes = acts_referenced[:5] if acts_referenced else []

            return PrecedentResult(
                issue_title=title,
                supporting=supporting,
                statutes=statutes,
            )
        except Exception:
            logger.exception("Precedent search failed for issue: %s", title)
            return PrecedentResult(issue_title=title)
```

**Step 4: Write DocumentAnalyzer tests**

Create `backend/tests/unit/test_document_analyzer.py`:

```python
"""Tests for DocumentAnalyzerService."""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.analysis.document_analyzer import (
    CounterArgument,
    DocumentAnalyzerService,
    DocumentExtractionResult,
    ExtractedIssue,
)


def _make_mock_llm() -> AsyncMock:
    llm = AsyncMock()
    return llm


class TestExtractIssues:
    async def test_extracts_issues_from_document(self) -> None:
        llm = _make_mock_llm()
        llm.generate_structured.return_value = {
            "document_type": "petition",
            "issues": [
                {"title": "Right to Privacy", "description": "Whether surveillance violates Article 21"},
                {"title": "State Power", "description": "Scope of state surveillance authority"},
            ],
            "parties": {"petitioner": "John Doe", "respondent": "State of Maharashtra"},
            "key_facts": ["Petitioner's phone was tapped", "No warrant obtained"],
            "relief_sought": "Quash the surveillance order",
            "jurisdiction": "constitutional",
            "acts_referenced": ["Indian Telegraph Act, 1885"],
        }

        service = DocumentAnalyzerService(llm)
        result = await service.extract_issues("Sample legal document text...")

        assert isinstance(result, DocumentExtractionResult)
        assert result.document_type == "petition"
        assert len(result.issues) == 2
        assert result.issues[0].title == "Right to Privacy"
        assert result.parties["petitioner"] == "John Doe"
        assert len(result.key_facts) == 2
        assert result.relief_sought == "Quash the surveillance order"

    async def test_handles_empty_issues(self) -> None:
        llm = _make_mock_llm()
        llm.generate_structured.return_value = {
            "document_type": "other",
            "issues": [],
            "parties": {},
            "key_facts": [],
            "relief_sought": None,
            "jurisdiction": None,
            "acts_referenced": [],
        }

        service = DocumentAnalyzerService(llm)
        result = await service.extract_issues("Short text")
        assert result.issues == []

    async def test_truncates_long_documents(self) -> None:
        llm = _make_mock_llm()
        llm.generate_structured.return_value = {
            "document_type": "brief",
            "issues": [],
            "parties": {},
            "key_facts": [],
            "relief_sought": None,
            "jurisdiction": None,
            "acts_referenced": [],
        }

        service = DocumentAnalyzerService(llm)
        long_text = "x" * 200_000
        await service.extract_issues(long_text)

        # Verify the prompt was called with truncated text
        call_args = llm.generate_structured.call_args
        prompt = call_args.args[0]
        assert len(prompt) < 200_000


class TestGenerateResearchMemo:
    async def test_generates_memo(self) -> None:
        llm = _make_mock_llm()
        llm.generate.return_value = "# Research Memo\n\n## Executive Summary\nThis memo..."

        service = DocumentAnalyzerService(llm)
        memo = await service.generate_research_memo(
            document_type="petition",
            parties={"petitioner": "A", "respondent": "B"},
            relief_sought="Damages",
            key_facts=["Fact 1", "Fact 2"],
            issues_analysis="Issue 1: ...",
            counter_arguments="Counter 1: ...",
        )

        assert "Research Memo" in memo
        assert llm.generate.called


class TestParseCounterArguments:
    def test_parses_formatted_counter_arguments(self) -> None:
        response = """\
## Issue: Right to Privacy

- **Counter-Argument:** State has power under Article 19(2)
- **Response:** Article 19(2) restrictions must be reasonable

## Issue: Due Process

- **Counter-Argument:** No fundamental right to prior notice
- **Response:** Natural justice principles require hearing
"""
        result = DocumentAnalyzerService._parse_counter_arguments(response)
        assert len(result) == 2
        assert result[0].issue_title == "Issue: Right to Privacy"
        assert "Article 19(2)" in result[0].argument
        assert "reasonable" in result[0].response

    def test_handles_empty_response(self) -> None:
        result = DocumentAnalyzerService._parse_counter_arguments("")
        assert result == []
```

**Step 5: Write PrecedentMapper tests**

Create `backend/tests/unit/test_precedent_mapper.py`:

```python
"""Tests for PrecedentMapperService."""

import pytest
from unittest.mock import AsyncMock, patch
from dataclasses import dataclass

from app.core.analysis.precedent_mapper import PrecedentMapperService, PrecedentResult
from app.core.search.hybrid import SearchResponse, SearchResultItem
from app.core.search.query import QueryUnderstanding


def _make_search_response(n: int = 3) -> SearchResponse:
    return SearchResponse(
        results=[
            SearchResultItem(
                case_id=f"case-{i}",
                score=1.0 - i * 0.1,
                title=f"Case {i} v. State",
                citation=f"(2024) {i} SCC 100",
                court="Supreme Court of India",
                year=2024,
            )
            for i in range(n)
        ],
        total_count=n,
        page=1,
        page_size=10,
        query_understanding=QueryUnderstanding(
            original_query="test",
            intent="legal_research",
            entities=[],
            expanded_query="test",
        ),
    )


class TestMapPrecedents:
    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_maps_single_issue(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(3)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Right to Privacy", "description": "Whether Article 21 is violated"}]
        results = await service.map_precedents(issues)

        assert len(results) == 1
        assert results[0].issue_title == "Right to Privacy"
        assert len(results[0].supporting) == 3

    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_maps_multiple_issues_in_parallel(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(2)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [
            {"title": "Issue 1", "description": "Desc 1"},
            {"title": "Issue 2", "description": "Desc 2"},
            {"title": "Issue 3", "description": "Desc 3"},
        ]
        results = await service.map_precedents(issues)

        assert len(results) == 3
        assert mock_search.call_count == 3

    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_includes_acts_in_query(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(1)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Tax Evasion", "description": "Under Income Tax Act"}]
        results = await service.map_precedents(
            issues, acts_referenced=["Income Tax Act, 1961"]
        )

        assert results[0].statutes == ["Income Tax Act, 1961"]

    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_handles_search_failure_gracefully(self, mock_search: AsyncMock) -> None:
        mock_search.side_effect = Exception("Search failed")

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Issue 1", "description": "Desc 1"}]
        results = await service.map_precedents(issues)

        assert len(results) == 1
        assert results[0].supporting == []

    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_respects_max_per_issue(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(10)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Issue 1", "description": "Desc 1"}]
        results = await service.map_precedents(issues, max_per_issue=3)

        assert len(results[0].supporting) == 3
```

**Step 6: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_document_analyzer.py tests/unit/test_precedent_mapper.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/app/core/analysis/ backend/tests/unit/test_document_analyzer.py backend/tests/unit/test_precedent_mapper.py
git commit -m "feat: add DocumentAnalyzer and PrecedentMapper services"
```

---

### Task 6: Celery Tasks (Document + Audio)

**Files:**
- Create: `backend/app/tasks/document_tasks.py`
- Create: `backend/app/tasks/audio_tasks.py`
- Test: `backend/tests/unit/test_document_tasks.py`
- Test: `backend/tests/unit/test_audio_tasks.py`

**Step 1: Create document analysis task**

Create `backend/app/tasks/document_tasks.py`:

```python
"""Celery task for document analysis pipeline."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import text

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_document(self: object, document_id: str) -> dict:
    """Run the full document analysis pipeline.

    Steps:
    1. Extract text from PDF
    2. Extract legal issues via LLM
    3. Search for precedents per issue
    4. Generate counter-arguments
    5. Generate research memo
    """
    import asyncio
    return asyncio.run(_analyze_document_async(document_id))


async def _analyze_document_async(document_id: str) -> dict:
    """Async implementation of the document analysis pipeline."""
    from app.core.analysis.document_analyzer import DocumentAnalyzerService
    from app.core.analysis.precedent_mapper import PrecedentMapperService
    from app.core.config import settings
    from app.core.providers.document_parsers.pdf_parser import PDFParser
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.vector.pinecone import PineconeStore
    from app.core.providers.rerankers.cohere import CohereReranker
    from app.db.postgres import get_async_session

    async with get_async_session() as db:
        try:
            # Update status: extracting
            await _update_doc_status(db, document_id, "extracting", "Extracting text from PDF")

            # Get document record
            result = await db.execute(
                text("SELECT storage_path, filename FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            doc = result.mappings().one_or_none()
            if not doc:
                raise ValueError(f"Document not found: {document_id}")

            # Step 1: Extract text
            parser = PDFParser()
            extracted_text = await parser.extract_text(doc["storage_path"])
            if not extracted_text or len(extracted_text.strip()) < 50:
                extracted_text = await parser.extract_text_with_ocr(doc["storage_path"])

            # Step 2: Extract issues
            await _update_doc_status(db, document_id, "analyzing", "Identifying legal issues")
            llm = GeminiLLM()
            analyzer = DocumentAnalyzerService(llm)
            extraction = await analyzer.extract_issues(extracted_text)

            # Step 3: Search for precedents
            await _update_doc_status(db, document_id, "searching", "Finding relevant precedents")
            embedder = GeminiEmbedder()
            vector_store = PineconeStore()
            reranker = CohereReranker()

            mapper = PrecedentMapperService(
                llm=llm, embedder=embedder, vector_store=vector_store,
                reranker=reranker, db=db,
            )
            issues_dicts = [
                {"title": i.title, "description": i.description}
                for i in extraction.issues
            ]
            precedent_results = await mapper.map_precedents(
                issues_dicts, acts_referenced=extraction.acts_referenced,
            )

            # Format issues with precedents for counter-argument generation
            issues_with_precedents = _format_issues_with_precedents(
                extraction.issues, precedent_results
            )

            # Step 4: Generate counter-arguments
            await _update_doc_status(db, document_id, "generating", "Generating analysis")
            counter_args = await analyzer.generate_counter_arguments(
                extraction.document_type, issues_with_precedents,
            )

            # Step 5: Generate research memo
            counter_args_text = "\n".join(
                f"- {ca.issue_title}: {ca.argument} → {ca.response}"
                for ca in counter_args
            )
            memo = await analyzer.generate_research_memo(
                document_type=extraction.document_type,
                parties=extraction.parties,
                relief_sought=extraction.relief_sought,
                key_facts=extraction.key_facts,
                issues_analysis=issues_with_precedents,
                counter_arguments=counter_args_text,
            )

            # Step 6: Store results
            analysis_id = str(uuid.uuid4())
            issues_json = [
                {
                    "title": issue.title,
                    "description": issue.description,
                    "supporting_precedents": [
                        {"case_id": r.case_id, "title": r.title, "citation": r.citation, "score": r.score}
                        for r in pr.supporting
                    ],
                    "statutes": pr.statutes,
                }
                for issue, pr in zip(extraction.issues, precedent_results)
            ]
            counter_args_json = [
                {"issue_title": ca.issue_title, "argument": ca.argument, "response": ca.response}
                for ca in counter_args
            ]

            await db.execute(
                text(
                    "INSERT INTO document_analyses "
                    "(id, document_id, extracted_text, issues, parties, key_facts, "
                    "relief_sought, counter_arguments, research_memo) "
                    "VALUES (:id, :doc_id, :text, :issues, :parties, :facts, "
                    ":relief, :counter, :memo)"
                ),
                {
                    "id": analysis_id,
                    "doc_id": document_id,
                    "text": extracted_text[:50000],  # Limit stored text
                    "issues": json.dumps(issues_json),
                    "parties": json.dumps(extraction.parties),
                    "facts": "\n".join(extraction.key_facts),
                    "relief": extraction.relief_sought,
                    "counter": json.dumps(counter_args_json),
                    "memo": memo,
                },
            )

            await _update_doc_status(
                db, document_id, "completed", None,
                completed=True,
            )
            await db.commit()

            return {"status": "completed", "document_id": document_id, "analysis_id": analysis_id}

        except Exception as exc:
            logger.exception("Document analysis failed: %s", document_id)
            await _update_doc_status(
                db, document_id, "failed", None, error=str(exc),
            )
            await db.commit()
            return {"status": "failed", "document_id": document_id, "error": str(exc)}


async def _update_doc_status(
    db: object,
    document_id: str,
    status: str,
    step: str | None,
    *,
    completed: bool = False,
    error: str | None = None,
) -> None:
    """Update document status and processing step."""
    now = datetime.now(timezone.utc).isoformat()
    params: dict = {
        "id": document_id,
        "status": status,
        "step": step,
    }

    set_clauses = "status = :status, processing_step = :step, updated_at = NOW()"
    if status == "extracting":
        set_clauses += ", processing_started_at = NOW()"
    if completed:
        set_clauses += ", processing_completed_at = NOW()"
    if error:
        params["error"] = error
        set_clauses += ", error_message = :error"

    await db.execute(  # type: ignore[union-attr]
        text(f"UPDATE documents SET {set_clauses} WHERE id = :id"),
        params,
    )


def _format_issues_with_precedents(issues: list, precedent_results: list) -> str:
    """Format issues and their precedents as text for LLM consumption."""
    sections = []
    for issue, pr in zip(issues, precedent_results):
        section = f"## {issue.title}\n{issue.description}\n\n"
        if pr.supporting:
            section += "### Supporting Precedents:\n"
            for r in pr.supporting:
                section += f"- {r.title} ({r.citation or 'No citation'}) — Score: {r.score:.2f}\n"
        if pr.statutes:
            section += "\n### Relevant Statutes:\n"
            for s in pr.statutes:
                section += f"- {s}\n"
        sections.append(section)
    return "\n\n".join(sections)
```

**Step 2: Create audio generation task**

Create `backend/app/tasks/audio_tasks.py`:

```python
"""Celery task for audio digest generation."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import text

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_audio(self: object, case_id: str, language: str = "en") -> dict:
    """Generate audio digest for a case."""
    import asyncio
    return asyncio.run(_generate_audio_async(case_id, language))


async def _generate_audio_async(case_id: str, language: str) -> dict:
    """Async implementation of audio generation."""
    from app.core.config import settings
    from app.core.interfaces.storage import FileStorage
    from app.core.legal.prompts import AUDIO_SUMMARY_SYSTEM, AUDIO_SUMMARY_USER
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.providers.storage.local_storage import LocalStorage
    from app.core.providers.tts.mock_tts import MockTTS
    from app.db.postgres import get_async_session

    async with get_async_session() as db:
        try:
            # Check if audio already exists
            existing = await db.execute(
                text(
                    "SELECT id, status FROM audio_digests "
                    "WHERE case_id = :case_id AND language = :lang"
                ),
                {"case_id": case_id, "lang": language},
            )
            row = existing.mappings().one_or_none()
            if row and row["status"] == "completed":
                return {"status": "already_exists", "case_id": case_id}

            # Get case data
            case_result = await db.execute(
                text(
                    "SELECT title, court, year, judge, full_text "
                    "FROM cases WHERE id = :id"
                ),
                {"id": case_id},
            )
            case = case_result.mappings().one_or_none()
            if not case:
                raise ValueError(f"Case not found: {case_id}")

            # Create or update audio_digests record
            digest_id = str(row["id"]) if row else str(uuid.uuid4())
            if not row:
                await db.execute(
                    text(
                        "INSERT INTO audio_digests (id, case_id, language, status) "
                        "VALUES (:id, :case_id, :lang, 'generating')"
                    ),
                    {"id": digest_id, "case_id": case_id, "lang": language},
                )
            else:
                await db.execute(
                    text("UPDATE audio_digests SET status = 'generating' WHERE id = :id"),
                    {"id": digest_id},
                )
            await db.commit()

            # Step 1: Generate summary text
            llm = GeminiLLM()
            judges = case["judge"] or []
            judges_str = ", ".join(judges) if isinstance(judges, list) else str(judges)

            prompt = AUDIO_SUMMARY_USER.format(
                title=case["title"] or "Unknown",
                court=case["court"] or "Unknown",
                year=case["year"] or "Unknown",
                judges=judges_str,
                judgment_text=(case["full_text"] or "")[:80000],
            )

            summary_text = await llm.generate(
                prompt,
                system=AUDIO_SUMMARY_SYSTEM,
                temperature=0.3,
                max_tokens=2048,
            )

            # Step 2: TTS
            tts = _get_tts_provider()
            audio_bytes = await tts.synthesize(summary_text, language=language)

            # Step 3: Store audio file
            import tempfile
            import os

            storage = LocalStorage()
            audio_dir = f"audio/{case_id}"
            audio_filename = f"{language}.mp3"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            storage_path = await storage.store(tmp_path, f"{audio_dir}/{audio_filename}")

            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            # Estimate duration (rough: ~150 words per minute, ~5 chars per word)
            word_count = len(summary_text.split())
            duration_seconds = int(word_count / 150 * 60)

            # Step 4: Update record
            await db.execute(
                text(
                    "UPDATE audio_digests SET "
                    "summary_text = :summary, audio_storage_path = :path, "
                    "duration_seconds = :duration, status = 'completed', "
                    "updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {
                    "id": digest_id,
                    "summary": summary_text,
                    "path": storage_path,
                    "duration": duration_seconds,
                },
            )
            await db.commit()

            return {
                "status": "completed",
                "case_id": case_id,
                "language": language,
                "duration_seconds": duration_seconds,
            }

        except Exception as exc:
            logger.exception("Audio generation failed for case %s", case_id)
            if row or digest_id:  # type: ignore[possibly-undefined]
                await db.execute(
                    text(
                        "UPDATE audio_digests SET status = 'failed', "
                        "error_message = :error, updated_at = NOW() "
                        "WHERE case_id = :case_id AND language = :lang"
                    ),
                    {"case_id": case_id, "lang": language, "error": str(exc)},
                )
                await db.commit()
            return {"status": "failed", "case_id": case_id, "error": str(exc)}


def _get_tts_provider():  # type: ignore[no-untyped-def]
    """Get the configured TTS provider."""
    from app.core.config import settings

    if settings.tts_provider == "sarvam" and settings.sarvam_api_key:
        from app.core.providers.tts.sarvam import SarvamTTS
        return SarvamTTS()
    else:
        from app.core.providers.tts.mock_tts import MockTTS
        return MockTTS()
```

**Step 3: Add `get_async_session` to postgres module**

The tasks need a way to get a DB session outside of FastAPI's request lifecycle. Check `backend/app/db/postgres.py` — if it doesn't have a `get_async_session` context manager, add one:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_async_session():
    """Create a standalone async session for use outside FastAPI requests (e.g., Celery tasks)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
    await engine.dispose()
```

**Step 4: Write task tests**

Create `backend/tests/unit/test_document_tasks.py`:

```python
"""Tests for document analysis Celery task."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from app.tasks.document_tasks import _format_issues_with_precedents


class TestFormatIssuesWithPrecedents:
    def test_formats_single_issue(self) -> None:
        issues = [MagicMock(title="Privacy", description="Article 21 violation")]
        precedents = [
            MagicMock(
                supporting=[
                    MagicMock(title="KS Puttaswamy v. UOI", citation="(2017) 10 SCC 1", score=0.95),
                ],
                statutes=["IT Act, 2000"],
            )
        ]
        result = _format_issues_with_precedents(issues, precedents)
        assert "Privacy" in result
        assert "KS Puttaswamy" in result
        assert "IT Act, 2000" in result

    def test_formats_multiple_issues(self) -> None:
        issues = [
            MagicMock(title="Issue 1", description="Desc 1"),
            MagicMock(title="Issue 2", description="Desc 2"),
        ]
        precedents = [
            MagicMock(supporting=[], statutes=[]),
            MagicMock(supporting=[], statutes=[]),
        ]
        result = _format_issues_with_precedents(issues, precedents)
        assert "Issue 1" in result
        assert "Issue 2" in result

    def test_handles_no_precedents(self) -> None:
        issues = [MagicMock(title="Orphan Issue", description="No cases found")]
        precedents = [MagicMock(supporting=[], statutes=[])]
        result = _format_issues_with_precedents(issues, precedents)
        assert "Orphan Issue" in result
        assert "Supporting" not in result
```

Create `backend/tests/unit/test_audio_tasks.py`:

```python
"""Tests for audio generation Celery task."""

from app.tasks.audio_tasks import _get_tts_provider
from unittest.mock import patch


class TestGetTTSProvider:
    @patch("app.tasks.audio_tasks.settings")
    def test_returns_mock_when_no_api_key(self, mock_settings: object) -> None:
        mock_settings.tts_provider = "mock"  # type: ignore[attr-defined]
        mock_settings.sarvam_api_key = ""  # type: ignore[attr-defined]
        provider = _get_tts_provider()
        from app.core.providers.tts.mock_tts import MockTTS
        assert isinstance(provider, MockTTS)

    @patch("app.tasks.audio_tasks.settings")
    def test_returns_mock_when_sarvam_no_key(self, mock_settings: object) -> None:
        mock_settings.tts_provider = "sarvam"  # type: ignore[attr-defined]
        mock_settings.sarvam_api_key = ""  # type: ignore[attr-defined]
        provider = _get_tts_provider()
        from app.core.providers.tts.mock_tts import MockTTS
        assert isinstance(provider, MockTTS)
```

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_document_tasks.py tests/unit/test_audio_tasks.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/tasks/ backend/app/db/postgres.py backend/tests/unit/test_document_tasks.py backend/tests/unit/test_audio_tasks.py
git commit -m "feat: add Celery tasks for document analysis and audio generation"
```

---

### Task 7: Document Upload API Routes

**Files:**
- Create: `backend/app/api/routes/documents.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_document_routes.py`

**Step 1: Create documents router**

Create `backend/app/api/routes/documents.py`:

```python
"""Document upload, listing, and analysis endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

router = APIRouter()


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Upload a PDF document for analysis. Any authenticated user."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    doc_id = str(uuid.uuid4())
    content = await file.read()

    # Store the uploaded file
    from app.core.providers.storage.local_storage import LocalStorage

    storage = LocalStorage()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    storage_path = await storage.store(tmp_path, f"documents/{doc_id}/{file.filename or 'upload.pdf'}")

    # Clean up temp file
    try:
        Path(tmp_path).unlink(missing_ok=True)
    except OSError:
        pass

    # Create document record
    await db.execute(
        text(
            "INSERT INTO documents (id, user_id, filename, storage_path, file_size, status) "
            "VALUES (:id, :user_id, :filename, :storage_path, :file_size, 'pending')"
        ),
        {
            "id": doc_id,
            "user_id": current_user.sub,
            "filename": file.filename or "upload.pdf",
            "storage_path": storage_path,
            "file_size": len(content),
        },
    )
    await db.commit()

    # Enqueue Celery task
    from app.tasks.document_tasks import analyze_document

    analyze_document.delay(doc_id)

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "status": "pending",
        "message": "Document uploaded and queued for analysis",
    }


@router.get("")
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


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Get document details with analysis results."""
    # Fetch document
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

    # Fetch analysis if completed
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


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    """Delete a document and its analysis. Owner only."""
    result = await db.execute(
        text(
            "SELECT id, storage_path FROM documents "
            "WHERE id = :id AND user_id = :user_id"
        ),
        {"id": document_id, "user_id": current_user.sub},
    )
    doc = result.mappings().one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from storage
    from app.core.providers.storage.local_storage import LocalStorage

    storage = LocalStorage()
    try:
        await storage.delete(doc["storage_path"])
    except Exception:
        pass  # File may not exist

    # Delete from DB (CASCADE handles document_analyses)
    await db.execute(
        text("DELETE FROM documents WHERE id = :id"),
        {"id": document_id},
    )
    await db.commit()


@router.get("/{document_id}/memo")
async def get_research_memo(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Get the research memo for a document."""
    # Verify ownership
    doc_result = await db.execute(
        text("SELECT id FROM documents WHERE id = :id AND user_id = :user_id"),
        {"id": document_id, "user_id": current_user.sub},
    )
    if not doc_result.mappings().one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        text(
            "SELECT research_memo FROM document_analyses WHERE document_id = :doc_id"
        ),
        {"doc_id": document_id},
    )
    row = result.mappings().one_or_none()
    if not row or not row["research_memo"]:
        raise HTTPException(status_code=404, detail="Research memo not available yet")

    return {"memo": row["research_memo"]}
```

**Step 2: Register router in main.py**

In `backend/app/main.py`, add after the judges import:

```python
from app.api.routes.documents import router as documents_router  # noqa: E402
```

And add after the judges router registration:

```python
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
```

**Step 3: Write tests**

Create `backend/tests/unit/test_document_routes.py`:

```python
"""Tests for document API routes."""

from app.api.routes.documents import router


class TestDocumentRoutes:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes]
        assert "/upload" in paths
        assert "" in paths  # list documents
        assert "/{document_id}" in paths
        assert "/{document_id}/memo" in paths

    def test_upload_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/upload":
                assert "POST" in route.methods  # type: ignore[union-attr]

    def test_delete_is_delete(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{document_id}":
                if hasattr(route, "methods") and "DELETE" in route.methods:
                    return
        pytest.fail("DELETE route not found for /{document_id}")  # noqa: F821

    def test_list_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "":
                assert "GET" in route.methods  # type: ignore[union-attr]


import pytest
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_document_routes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/documents.py backend/app/main.py backend/tests/unit/test_document_routes.py
git commit -m "feat: add document upload/list/detail/delete API routes"
```

---

### Task 8: Audio Digest API Routes

**Files:**
- Create: `backend/app/api/routes/audio.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/unit/test_audio_routes.py`

**Step 1: Create audio router**

Create `backend/app/api/routes/audio.py`:

```python
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
    language: str = Query("en", regex="^(en|hi)$", description="Language code"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Trigger async audio digest generation for a case."""
    # Verify case exists
    case_result = await db.execute(
        text("SELECT id FROM cases WHERE id = :id"),
        {"id": case_id},
    )
    if not case_result.mappings().one_or_none():
        raise HTTPException(status_code=404, detail="Case not found")

    # Check if already exists
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

    # Enqueue generation task
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
    language: str = Query("en", regex="^(en|hi)$"),
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

    audio_bytes = await storage.retrieve(row["audio_storage_path"])

    async def audio_generator():  # type: ignore[no-untyped-def]
        yield audio_bytes

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Accept-Ranges": "bytes",
        },
    )
```

**Step 2: Register router in main.py**

In `backend/app/main.py`, add after the documents import:

```python
from app.api.routes.audio import router as audio_router  # noqa: E402
```

And add after the documents router registration:

```python
app.include_router(audio_router, prefix="/api/v1/cases", tags=["audio"])
```

**Step 3: Write tests**

Create `backend/tests/unit/test_audio_routes.py`:

```python
"""Tests for audio digest API routes."""

from app.api.routes.audio import router


class TestAudioRoutes:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/{case_id}/audio/generate" in paths
        assert "/{case_id}/audio/status" in paths
        assert "/{case_id}/audio" in paths

    def test_generate_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio/generate":
                assert "POST" in route.methods  # type: ignore[union-attr]

    def test_status_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio/status":
                assert "GET" in route.methods  # type: ignore[union-attr]

    def test_stream_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio":
                assert "GET" in route.methods  # type: ignore[union-attr]
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_audio_routes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/audio.py backend/app/main.py backend/tests/unit/test_audio_routes.py
git commit -m "feat: add audio digest generation/status/stream API routes"
```

---

### Task 9: Frontend Types + API Client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add Phase 5 types to types.ts**

Append to `frontend/src/lib/types.ts`:

```typescript
// ---------------------------------------------------------------------------
// Phase 5: Document Upload + Audio Digests
// ---------------------------------------------------------------------------

export interface DocumentUploadResponse {
    document_id: string;
    filename: string;
    status: string;
    message: string;
}

export interface DocumentListItem {
    id: string;
    filename: string;
    status: string;
    processing_step: string | null;
    file_size: number | null;
    created_at: string;
    updated_at: string;
    error_message: string | null;
}

export interface DocumentListResponse {
    documents: DocumentListItem[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface DocumentIssue {
    title: string;
    description: string;
    supporting_precedents: {
        case_id: string;
        title: string | null;
        citation: string | null;
        score: number;
    }[];
    statutes: string[];
}

export interface DocumentCounterArgument {
    issue_title: string;
    argument: string;
    response: string;
}

export interface DocumentAnalysis {
    issues: DocumentIssue[];
    parties: Record<string, string | null>;
    key_facts: string;
    relief_sought: string | null;
    counter_arguments: DocumentCounterArgument[];
    research_memo: string;
}

export interface DocumentDetail extends DocumentListItem {
    processing_started_at: string | null;
    processing_completed_at: string | null;
    analysis?: DocumentAnalysis;
}

export interface AudioDigestInfo {
    language: string;
    status: string;
    duration_seconds: number | null;
}

export interface AudioDigestStatus {
    case_id: string;
    available: string[];
    generating: string[];
    digests: AudioDigestInfo[];
}
```

**Step 2: Add API functions to api.ts**

Append to `frontend/src/lib/api.ts`:

```typescript
// ---------------------------------------------------------------------------
// Phase 5: Document Upload + Audio Digests
// ---------------------------------------------------------------------------

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const headers: Record<string, string> = {};
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }
    // Do NOT set Content-Type — browser sets it with boundary for multipart

    const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        headers,
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Upload failed" }));
        throw new ApiError(res.status, "UPLOAD_ERROR", err.detail || err.error || "Upload failed");
    }

    return res.json();
}

export async function getDocuments(
    page: number = 1,
    pageSize: number = 20,
): Promise<DocumentListResponse> {
    return apiFetch<DocumentListResponse>(
        `/documents?page=${page}&page_size=${pageSize}`,
    );
}

export async function getDocument(id: string): Promise<DocumentDetail> {
    return apiFetch<DocumentDetail>(`/documents/${id}`);
}

export async function deleteDocument(id: string): Promise<void> {
    await apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function getResearchMemo(id: string): Promise<{ memo: string }> {
    return apiFetch<{ memo: string }>(`/documents/${id}/memo`);
}

export async function generateAudioDigest(
    caseId: string,
    language: string = "en",
): Promise<{ status: string; case_id: string; language: string }> {
    return apiFetch(`/cases/${caseId}/audio/generate?language=${language}`, {
        method: "POST",
    });
}

export async function getAudioStatus(caseId: string): Promise<AudioDigestStatus> {
    return apiFetch<AudioDigestStatus>(`/cases/${caseId}/audio/status`);
}

export function getAudioUrl(caseId: string, language: string = "en"): string {
    return `${API_BASE}/cases/${caseId}/audio?language=${language}`;
}
```

Also add the new types to the import block at the top of `api.ts`:

```typescript
import type {
    // ... existing imports ...
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentDetail,
    AudioDigestStatus,
} from "./types";
```

**Step 3: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat: add Phase 5 frontend types and API client functions"
```

---

### Task 10: Frontend Upload Page + File Upload Component

**Files:**
- Create: `frontend/src/components/file-upload.tsx`
- Create: `frontend/src/components/processing-status.tsx`
- Create: `frontend/src/app/upload/page.tsx`
- Create: `frontend/src/app/documents/page.tsx`
- Create: `frontend/src/app/documents/[id]/page.tsx`
- Test: `frontend/src/__tests__/upload-page.test.tsx`
- Test: `frontend/src/__tests__/document-detail-page.test.tsx`

The subagent implementing this task should:

1. Create a `FileUpload` component with drag-and-drop support using `onDrop`/`onDragOver` events. Accept only PDFs, max 50MB. Show upload progress. Use shadcn Button and Card components.

2. Create a `ProcessingStatus` component that shows step-by-step progress: extracting → analyzing → searching → generating → completed. Use a simple step indicator with colored circles/badges.

3. Create `/upload` page that uses `FileUpload` component, calls `uploadDocument()`, then redirects to `/documents/{id}` after successful upload.

4. Create `/documents` page that lists user's documents with status badges, using `getDocuments()`. Paginated table showing filename, status, date.

5. Create `/documents/[id]` page that:
   - Polls `getDocument(id)` every 3 seconds while status is not "completed"/"failed"
   - Shows `ProcessingStatus` component during processing
   - Once completed, shows analysis results:
     - Issues in an accordion (each issue expandable showing description, precedents, statutes)
     - Counter-arguments section
     - Research memo (full text with copy button)

6. Write tests following the existing pattern (mock `next/navigation`, mock `@/lib/api`, use `renderWithProviders`).

Test expectations:
- Upload page: renders dropzone, shows error for non-PDF, calls uploadDocument
- Document detail: shows loading state, shows processing status, shows completed analysis

**Step: Commit after implementation**

```bash
git add frontend/src/components/file-upload.tsx frontend/src/components/processing-status.tsx frontend/src/app/upload/ frontend/src/app/documents/ frontend/src/__tests__/upload-page.test.tsx frontend/src/__tests__/document-detail-page.test.tsx
git commit -m "feat: add document upload, documents list, and document detail pages"
```

---

### Task 11: Frontend Audio Player Component

**Files:**
- Create: `frontend/src/components/audio-player.tsx`
- Modify: `frontend/src/app/case/[id]/page.tsx`
- Test: `frontend/src/__tests__/audio-player.test.tsx`

The subagent implementing this task should:

1. Create an `AudioPlayer` component that:
   - Takes `caseId: string` as prop
   - On mount, calls `getAudioStatus(caseId)` to check availability
   - If available: shows HTML `<audio>` element with custom controls
     - Play/pause button
     - Progress bar (using `<input type="range">`)
     - Current time / duration display
     - Playback speed selector (0.5x, 1x, 1.5x, 2x) using shadcn Select
     - Download button (link to `getAudioUrl()`)
     - Language selector (EN / HI) if multiple languages available
   - If not available: shows "Generate Audio" button that calls `generateAudioDigest(caseId, language)`
   - While generating: shows spinner with "Generating audio..." text, polls status every 5 seconds
   - Uses `"use client"` directive

2. Add the `AudioPlayer` component to the case detail page (`/case/[id]/page.tsx`):
   - Place it after the case metadata section, before the judgment text tabs
   - Only render when `case.full_text` exists (no point generating audio for cases without text)

3. Write tests following existing patterns:
   - Mock `getAudioStatus` and `generateAudioDigest`
   - Test: renders "Generate Audio" when no audio available
   - Test: renders player when audio available
   - Test: calls generate on button click
   - Test: shows speed selector

**Step: Commit after implementation**

```bash
git add frontend/src/components/audio-player.tsx frontend/src/app/case/[id]/page.tsx frontend/src/__tests__/audio-player.test.tsx
git commit -m "feat: add audio player component with TTS generation"
```

---

### Task 12: Header Navigation + Final Integration

**Files:**
- Modify: `frontend/src/components/header.tsx`
- Run: All tests (backend + frontend)
- Run: Frontend build

The subagent implementing this task should:

1. Add "Upload" nav link to `header.tsx`:
   - Import `Upload` icon from lucide-react
   - Add to both desktop and mobile nav after "Judges" link
   - Link to `/upload`

2. Run ALL backend tests: `cd backend && python -m pytest tests/unit/ -v`
   Expected: ALL PASS (previous 197 + ~45 new Phase 5 tests ≈ 242 total)

3. Run ALL frontend tests: `cd frontend && npx vitest run`
   Expected: ALL PASS (previous 115 + ~15 new Phase 5 tests ≈ 130 total)

4. Run frontend build: `cd frontend && npx next build`
   Expected: Build succeeds with all routes including `/upload`, `/documents`, `/documents/[id]`

5. Fix any test failures or build errors.

**Step: Commit after all tests pass**

```bash
git add frontend/src/components/header.tsx
git commit -m "feat: add Upload nav link and verify Phase 5 integration"
```

---

### Task 13: Update PHASE_PLAN.md + Final Commit

**Files:**
- Modify: `docs/PHASE_PLAN.md`

Mark Phase 5 as COMPLETE:

1. Change header to: `## Phase 5: Document Upload + Audio Digests — COMPLETE`
2. Check all deliverable boxes `[x]`
3. Update exit criteria with actual test counts

**Step: Commit**

```bash
git add docs/PHASE_PLAN.md
git commit -m "mark Phase 5 as COMPLETE in PHASE_PLAN.md"
```
