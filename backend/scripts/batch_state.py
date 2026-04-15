"""SQLite state tracking for batch ingestion phases.

⚠️  DEPRECATED — Part of the batch ingestion pipeline (batch_ingest.py)
which was evaluated and found to produce lower quality metadata than the
standard pipeline. See batch_ingest.py docstring for details.

Tracks individual documents through: uploaded → submitted → completed → processed
Tracks batch jobs through: pending → succeeded → failed
Separate DB from ingest_tracker.db to avoid any interference with the main pipeline.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class BatchStateDB:
    """SQLite-backed state for batch ingestion orchestration."""

    def __init__(self, db_path: Path | str = Path("data/batch_state.db")) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS batch_docs (
                doc_key TEXT PRIMARY KEY,
                year INTEGER,
                file_uri TEXT,
                text_hash TEXT,
                full_text_len INTEGER,
                parquet_meta TEXT,
                pdf_path TEXT,
                api_key_index INTEGER,
                batch_job_name TEXT,
                status TEXT DEFAULT 'uploaded',
                llm_result TEXT,
                error TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS batch_jobs (
                job_name TEXT PRIMARY KEY,
                api_key_index INTEGER,
                status TEXT DEFAULT 'pending',
                doc_count INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );
        """)
        self._conn.commit()

    # --- Document operations ---

    def insert_doc(
        self,
        doc_key: str,
        year: int,
        file_uri: str,
        text_hash: str,
        full_text_len: int,
        parquet_meta: dict,
        pdf_path: str,
        api_key_index: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO batch_docs "
                "(doc_key, year, file_uri, text_hash, full_text_len, parquet_meta, pdf_path, api_key_index) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_key,
                    year,
                    file_uri,
                    text_hash,
                    full_text_len,
                    json.dumps(parquet_meta),
                    pdf_path,
                    api_key_index,
                ),
            )
            self._conn.commit()

    def get_doc(self, doc_key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM batch_docs WHERE doc_key = ?", (doc_key,)
            ).fetchone()
            return dict(row) if row else None

    def update_doc_status(
        self, doc_key: str, status: str, *, batch_job_name: str | None = None
    ) -> None:
        with self._lock:
            if batch_job_name:
                self._conn.execute(
                    "UPDATE batch_docs SET status = ?, batch_job_name = ? WHERE doc_key = ?",
                    (status, batch_job_name, doc_key),
                )
            else:
                self._conn.execute(
                    "UPDATE batch_docs SET status = ? WHERE doc_key = ?",
                    (status, doc_key),
                )
            self._conn.commit()

    def store_result(self, doc_key: str, result: dict) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE batch_docs SET llm_result = ?, status = 'completed' WHERE doc_key = ?",
                (json.dumps(result), doc_key),
            )
            self._conn.commit()

    def mark_error(self, doc_key: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE batch_docs SET status = 'error', error = ? WHERE doc_key = ?",
                (error, doc_key),
            )
            self._conn.commit()

    def get_docs_by_status(self, status: str, *, year: int | None = None) -> list[dict]:
        with self._lock:
            if year is not None:
                rows = self._conn.execute(
                    "SELECT * FROM batch_docs WHERE status = ? AND year = ?",
                    (status, year),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM batch_docs WHERE status = ?", (status,)
                ).fetchall()
            return [dict(r) for r in rows]

    # --- Job operations ---

    def insert_job(self, job_name: str, api_key_index: int, doc_count: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO batch_jobs (job_name, api_key_index, doc_count) VALUES (?, ?, ?)",
                (job_name, api_key_index, doc_count),
            )
            self._conn.commit()

    def get_job(self, job_name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM batch_jobs WHERE job_name = ?", (job_name,)
            ).fetchone()
            return dict(row) if row else None

    def update_job_status(self, job_name: str, status: str) -> None:
        with self._lock:
            completed = "datetime('now')" if status in ("succeeded", "failed") else "NULL"
            self._conn.execute(
                f"UPDATE batch_jobs SET status = ?, completed_at = {completed} WHERE job_name = ?",
                (status, job_name),
            )
            self._conn.commit()

    def get_pending_jobs(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM batch_jobs WHERE status = 'pending'"
            ).fetchall()
            return [dict(r) for r in rows]
