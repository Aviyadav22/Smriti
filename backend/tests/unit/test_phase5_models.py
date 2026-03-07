"""Tests for Phase 5 ORM models."""

import uuid

from app.models.audio_digest import AudioDigest
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis


class TestDocumentModel:
    def test_status_values_include_new_states(self) -> None:
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
        analysis = DocumentAnalysis(id=uid, document_id=uid)
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
