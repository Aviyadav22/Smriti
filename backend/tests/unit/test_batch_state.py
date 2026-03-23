"""Tests for BatchStateDB — SQLite state tracking for batch ingestion."""

import json
import pytest
from pathlib import Path

from scripts.batch_state import BatchStateDB


class TestBatchStateDB:
    @pytest.fixture
    def db(self, tmp_path: Path) -> BatchStateDB:
        return BatchStateDB(tmp_path / "test_batch_state.db")

    def test_insert_doc(self, db: BatchStateDB):
        db.insert_doc(
            doc_key="year=2023/test.pdf",
            year=2023,
            file_uri="files/abc123",
            text_hash="sha256hex",
            full_text_len=50000,
            parquet_meta={"title": "Test Case"},
            pdf_path="/data/test.pdf",
            api_key_index=0,
        )
        doc = db.get_doc("year=2023/test.pdf")
        assert doc is not None
        assert doc["file_uri"] == "files/abc123"
        assert doc["status"] == "uploaded"

    def test_insert_doc_idempotent(self, db: BatchStateDB):
        """Second insert with same key is ignored."""
        db.insert_doc("k", 2023, "f1", "h", 100, {}, "/p", 0)
        db.insert_doc("k", 2023, "f2", "h", 100, {}, "/p", 0)
        doc = db.get_doc("k")
        assert doc["file_uri"] == "f1"  # first insert wins

    def test_update_status(self, db: BatchStateDB):
        db.insert_doc("k", 2023, "f", "h", 100, {}, "/p", 0)
        db.update_doc_status("k", "submitted", batch_job_name="batches/xyz")
        doc = db.get_doc("k")
        assert doc["status"] == "submitted"
        assert doc["batch_job_name"] == "batches/xyz"

    def test_store_result(self, db: BatchStateDB):
        db.insert_doc("k", 2023, "f", "h", 100, {}, "/p", 0)
        result = {"title": "Extracted Title"}
        db.store_result("k", result)
        doc = db.get_doc("k")
        assert doc["status"] == "completed"
        assert json.loads(doc["llm_result"]) == result

    def test_mark_error(self, db: BatchStateDB):
        db.insert_doc("k", 2023, "f", "h", 100, {}, "/p", 0)
        db.mark_error("k", "batch failed: quota exceeded")
        doc = db.get_doc("k")
        assert doc["status"] == "error"
        assert "quota" in doc["error"]

    def test_get_docs_by_status(self, db: BatchStateDB):
        db.insert_doc("a", 2023, "f1", "h1", 100, {}, "/a", 0)
        db.insert_doc("b", 2023, "f2", "h2", 200, {}, "/b", 0)
        db.store_result("a", {"title": "A"})
        completed = db.get_docs_by_status("completed")
        assert len(completed) == 1
        assert completed[0]["doc_key"] == "a"

    def test_insert_job(self, db: BatchStateDB):
        db.insert_job("batches/j1", api_key_index=0, doc_count=100)
        job = db.get_job("batches/j1")
        assert job["status"] == "pending"
        assert job["doc_count"] == 100

    def test_update_job_status(self, db: BatchStateDB):
        db.insert_job("batches/j1", 0, 50)
        db.update_job_status("batches/j1", "succeeded")
        job = db.get_job("batches/j1")
        assert job["status"] == "succeeded"
        assert job["completed_at"] is not None

    def test_get_pending_jobs(self, db: BatchStateDB):
        db.insert_job("batches/j1", 0, 50)
        db.insert_job("batches/j2", 1, 60)
        db.update_job_status("batches/j1", "succeeded")
        pending = db.get_pending_jobs()
        assert len(pending) == 1
        assert pending[0]["job_name"] == "batches/j2"

    def test_get_docs_for_year(self, db: BatchStateDB):
        db.insert_doc("year=2022/a.pdf", 2022, "f1", "h1", 100, {}, "/a", 0)
        db.insert_doc("year=2023/b.pdf", 2023, "f2", "h2", 200, {}, "/b", 0)
        docs_2023 = db.get_docs_by_status("uploaded", year=2023)
        assert len(docs_2023) == 1
