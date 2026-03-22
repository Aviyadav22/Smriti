#!/usr/bin/env python3
"""Statute ingestion script with circuit breaker and resume support.

Ingests Indian statutes from JSON source files into PostgreSQL, Pinecone, and Neo4j.

Features:
  - Circuit breaker: stops after N consecutive failures to prevent cascade
  - Resume: tracks progress in a JSON file, skips already-ingested files
  - Per-file and per-section error isolation
  - Graceful Ctrl+C handling

Pipeline per source file:
  1. Parse JSON
  2. INSERT into statutes table (ON CONFLICT DO UPDATE)
  3. Generate contextual prefix via Flash (optional)
  4. Embed section_text via embedder
  5. Upsert to Pinecone with document_type metadata
  6. Create Neo4j Statute nodes

Usage:
    python scripts/ingest_statutes.py --source data/statutes/ipc.json
    python scripts/ingest_statutes.py --source data/statutes/ --all
    python scripts/ingest_statutes.py --source data/statutes/ --resume  # resume from last checkpoint
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ingestion.contextual_embeddings import generate_contextual_prefix
from app.core.legal.constants import (
    CRPC_TO_BNSS_MAP,
    EVIDENCE_TO_BSA_MAP,
    IPC_TO_BNS_MAP,
)
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Circuit breaker — stops ingestion after N consecutive failures
# ---------------------------------------------------------------------------

CIRCUIT_BREAKER_THRESHOLD = 10  # consecutive failures before tripping


class CircuitBreaker:
    """Simple circuit breaker that trips after consecutive failures."""

    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD):
        self.threshold = threshold
        self.consecutive_failures = 0
        self.tripped = False

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            self.tripped = True
            logger.error(
                "Circuit breaker TRIPPED after %d consecutive failures — stopping ingestion",
                self.consecutive_failures,
            )

    @property
    def is_open(self) -> bool:
        return self.tripped


# ---------------------------------------------------------------------------
# Resume tracking — persist progress across runs
# ---------------------------------------------------------------------------

PROGRESS_FILE = Path(__file__).resolve().parent.parent / "data" / "statutes" / ".ingest_progress.json"


def load_progress() -> dict:
    """Load ingestion progress from checkpoint file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"completed_files": [], "stats": {}}


def save_progress(progress: dict) -> None:
    """Save ingestion progress to checkpoint file."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum: int, frame: object) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("Shutdown requested (signal %d) — finishing current file...", signum)


# Map short names to their replacement mappings
_REPLACEMENT_MAPS: dict[str, tuple[dict[str, str], str]] = {
    "IPC": (IPC_TO_BNS_MAP, "BNS"),
    "CrPC": (CRPC_TO_BNSS_MAP, "BNSS"),
    "IEA": (EVIDENCE_TO_BSA_MAP, "BSA"),
}

# Reverse mappings for new codes
_REVERSE_MAPS: dict[str, tuple[dict[str, str], str]] = {}
for old_code, (mapping, new_code) in _REPLACEMENT_MAPS.items():
    reverse = {v: k for k, v in mapping.items()}
    _REVERSE_MAPS[new_code] = (reverse, old_code)


async def upsert_statute(
    db: AsyncSession,
    statute: dict,
) -> str | None:
    """Insert or update a statute section in PostgreSQL.

    Returns the statute ID on success, None on failure.
    """
    try:
        result = await db.execute(
            text("""
                INSERT INTO statutes (
                    act_name, act_short_name, act_number, act_year,
                    part, chapter, section_number, section_title,
                    section_text, explanation, effective_date,
                    effective_from, effective_until, amendment_history,
                    is_repealed, replaced_by, replaces, document_type
                ) VALUES (
                    :act_name, :act_short_name, :act_number, :act_year,
                    :part, :chapter, :section_number, :section_title,
                    :section_text, :explanation, :effective_date,
                    :effective_from, :effective_until, :amendment_history,
                    :is_repealed, :replaced_by, :replaces, :document_type
                )
                ON CONFLICT (act_short_name, section_number)
                DO UPDATE SET
                    section_text = EXCLUDED.section_text,
                    section_title = EXCLUDED.section_title,
                    explanation = EXCLUDED.explanation,
                    replaced_by = EXCLUDED.replaced_by,
                    replaces = EXCLUDED.replaces,
                    is_repealed = EXCLUDED.is_repealed,
                    effective_from = EXCLUDED.effective_from,
                    effective_until = EXCLUDED.effective_until,
                    amendment_history = EXCLUDED.amendment_history
                RETURNING id
            """),
            statute,
        )
        row = result.fetchone()
        return str(row[0]) if row else None
    except Exception as exc:
        logger.error("Failed to upsert statute %s %s: %s",
                     statute.get("act_short_name"), statute.get("section_number"), exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return None


def compute_replacement_fields(
    act_short_name: str,
    section_number: str,
) -> tuple[str, str]:
    """Compute replaced_by and replaces fields from code mappings.

    Returns (replaced_by, replaces) strings.
    """
    replaced_by = ""
    replaces = ""

    # Old code → new code
    if act_short_name in _REPLACEMENT_MAPS:
        mapping, new_code = _REPLACEMENT_MAPS[act_short_name]
        new_section = mapping.get(section_number, "")
        if new_section:
            replaced_by = f"{new_code}, Section {new_section}"

    # New code → old code
    if act_short_name in _REVERSE_MAPS:
        reverse_map, old_code = _REVERSE_MAPS[act_short_name]
        old_section = reverse_map.get(section_number, "")
        if old_section:
            replaces = f"{old_code}, Section {old_section}"

    return replaced_by, replaces


def parse_statute_json(filepath: Path) -> list[dict]:
    """Parse a statute JSON file into statute dicts."""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    statutes: list[dict] = []

    # Handle different JSON formats
    if isinstance(data, list):
        for item in data:
            statutes.append(_normalize_statute(item))
    elif isinstance(data, dict):
        # Could be {sections: [...]} or {act_name: ..., sections: [...]}
        sections = data.get("sections", data.get("provisions", []))
        if isinstance(sections, list):
            act_meta = {k: v for k, v in data.items() if k not in ("sections", "provisions")}
            for item in sections:
                merged = {**act_meta, **item}
                statutes.append(_normalize_statute(merged))

    return statutes


def _normalize_statute(raw: dict) -> dict:
    """Normalize a raw statute dict into our schema format."""
    act_short = raw.get("act_short_name", raw.get("short_name", ""))
    section_num = str(raw.get("section_number", raw.get("section", raw.get("number", ""))))

    replaced_by, replaces = compute_replacement_fields(act_short, section_num)
    # Allow explicit values to override computed ones
    if raw.get("replaced_by"):
        replaced_by = raw["replaced_by"]
    if raw.get("replaces"):
        replaces = raw["replaces"]

    # Parse amendment_history as JSON if string
    amendment_history = raw.get("amendment_history")
    if isinstance(amendment_history, str):
        try:
            amendment_history = json.loads(amendment_history)
        except (json.JSONDecodeError, TypeError):
            amendment_history = None

    return {
        "act_name": raw.get("act_name", raw.get("name", "")),
        "act_short_name": act_short,
        "act_number": raw.get("act_number", raw.get("number_of_act", "")),
        "act_year": int(raw.get("act_year", raw.get("year", 0))),
        "part": raw.get("part", ""),
        "chapter": raw.get("chapter", ""),
        "section_number": section_num,
        "section_title": raw.get("section_title", raw.get("title", "")),
        "section_text": raw.get("section_text", raw.get("text", raw.get("content", ""))),
        "explanation": raw.get("explanation", ""),
        "effective_date": raw.get("effective_date"),
        "effective_from": raw.get("effective_from"),
        "effective_until": raw.get("effective_until"),
        "amendment_history": json.dumps(amendment_history) if amendment_history else None,
        "is_repealed": raw.get("is_repealed", False),
        "replaced_by": replaced_by,
        "replaces": replaces,
        "document_type": raw.get("document_type", "statute"),
    }


async def ingest_statute_file(
    filepath: Path,
    db: AsyncSession,
    embedder: object | None = None,
    vector_store: object | None = None,
    graph_store: object | None = None,
    flash_llm: object | None = None,
    dry_run: bool = False,
    breaker: CircuitBreaker | None = None,
) -> dict:
    """Ingest all statutes from a single file.

    Returns stats dict with counts.
    """
    logger.info("Parsing %s", filepath)
    statutes = parse_statute_json(filepath)
    logger.info("Found %d statute sections in %s", len(statutes), filepath.name)

    stats = {"total": len(statutes), "inserted": 0, "embedded": 0, "graphed": 0, "errors": 0}

    if dry_run:
        for s in statutes[:3]:
            logger.info("  [DRY RUN] %s Section %s: %s",
                        s["act_short_name"], s["section_number"], s["section_title"])
        return stats

    cb = breaker or CircuitBreaker()

    # Batch insert to PostgreSQL
    for statute in statutes:
        if cb.is_open:
            logger.error("Circuit breaker open — aborting PostgreSQL inserts for %s", filepath.name)
            break
        sid = await upsert_statute(db, statute)
        if sid:
            stats["inserted"] += 1
            cb.record_success()
        else:
            stats["errors"] += 1
            cb.record_failure()

    if not cb.is_open:
        await db.commit()
    logger.info("PostgreSQL: %d/%d inserted", stats["inserted"], stats["total"])

    # Embed and upsert to Pinecone (if embedder + vector_store available)
    if embedder and vector_store and not cb.is_open:
        batch_size = 20
        texts = [s["section_text"] for s in statutes if s["section_text"]]

        # Optionally contextualize
        if flash_llm:
            contextualized: list[str] = []
            for s in statutes:
                if not s["section_text"]:
                    continue
                try:
                    ctx = await generate_contextual_prefix(
                        s["section_text"],
                        {
                            "act_name": s["act_name"],
                            "section_number": s["section_number"],
                            "section_title": s["section_title"],
                            "chapter": s["chapter"],
                            "replaces": s["replaces"],
                            "replaced_by": s["replaced_by"],
                        },
                        flash_llm,
                        document_type="statute",
                    )
                    contextualized.append(ctx)
                except Exception:
                    contextualized.append(s["section_text"])
            texts = contextualized

        for i in range(0, len(texts), batch_size):
            if cb.is_open:
                break
            batch_texts = texts[i:i + batch_size]
            batch_statutes = [s for s in statutes if s["section_text"]][i:i + batch_size]
            try:
                embeddings = await embedder.embed_batch(batch_texts)
                vectors = []
                for s, emb in zip(batch_statutes, embeddings):
                    vid = f"statute:{s['act_short_name']}:{s['section_number']}"
                    vectors.append({
                        "id": vid,
                        "values": emb,
                        "metadata": {
                            "document_type": s["document_type"],
                            "act_name": s["act_name"],
                            "act_short_name": s["act_short_name"],
                            "section_number": s["section_number"],
                            "section_title": s["section_title"] or "",
                            "text": s["section_text"][:2000],
                            "replaced_by": s["replaced_by"],
                            "replaces": s["replaces"],
                        },
                    })
                await vector_store.upsert(vectors)
                stats["embedded"] += len(vectors)
                cb.record_success()
            except Exception as exc:
                logger.error("Pinecone upsert batch failed: %s", exc)
                cb.record_failure()

        logger.info("Pinecone: %d/%d embedded", stats["embedded"], stats["total"])

    # Create Neo4j nodes (if graph_store available)
    if graph_store and not cb.is_open:
        for s in statutes:
            if cb.is_open:
                break
            try:
                await graph_store.create_node(
                    "Statute",
                    {
                        "id": f"statute:{s['act_short_name']}:{s['section_number']}",
                        "act_name": s["act_name"],
                        "act_short_name": s["act_short_name"],
                        "section_number": s["section_number"],
                        "section_title": s["section_title"] or "",
                        "document_type": s["document_type"],
                        "replaced_by": s["replaced_by"],
                        "replaces": s["replaces"],
                    },
                )
                stats["graphed"] += 1
                cb.record_success()
            except Exception as exc:
                logger.error("Neo4j node creation failed for %s %s: %s",
                             s["act_short_name"], s["section_number"], exc)
                cb.record_failure()

        logger.info("Neo4j: %d/%d graphed", stats["graphed"], stats["total"])

    return stats


async def main(args: argparse.Namespace) -> None:
    """Main entry point with circuit breaker and resume support."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    source = Path(args.source)
    files: list[Path] = []

    if source.is_dir():
        files = sorted(source.glob("*.json"))
        if not files:
            logger.error("No JSON files found in %s", source)
            return
    elif source.is_file():
        files = [source]
    else:
        logger.error("Source not found: %s", source)
        return

    # Resume support: skip already-completed files
    progress = load_progress() if args.resume else {"completed_files": [], "stats": {}}
    completed_set = set(progress.get("completed_files", []))
    if args.resume and completed_set:
        original_count = len(files)
        files = [f for f in files if f.name not in completed_set]
        logger.info("Resume mode: skipping %d already-completed files, %d remaining",
                     original_count - len(files), len(files))

    if not files:
        logger.info("All files already ingested. Use without --resume to re-ingest.")
        return

    logger.info("Ingesting %d statute file(s)", len(files))

    # Initialize dependencies
    embedder = None
    vector_store = None
    graph_store = None
    flash_llm = None

    if not args.db_only:
        try:
            from app.core.dependencies import get_embedder, get_vector_store
            embedder = get_embedder()
            vector_store = get_vector_store()
        except Exception as exc:
            logger.warning("Could not initialize embedder/vector_store: %s", exc)

        try:
            from app.core.dependencies import get_graph_store
            graph_store = get_graph_store()
        except Exception as exc:
            logger.warning("Could not initialize graph_store: %s", exc)

        if args.contextualize:
            try:
                from app.core.dependencies import get_flash_llm
                flash_llm = get_flash_llm()
            except Exception as exc:
                logger.warning("Could not initialize flash_llm: %s", exc)

    total_stats = {"total": 0, "inserted": 0, "embedded": 0, "graphed": 0, "errors": 0}
    breaker = CircuitBreaker()
    start_time = time.monotonic()

    async with async_session_factory() as db:
        for i, filepath in enumerate(files):
            # Check shutdown and circuit breaker
            if _shutdown_requested:
                logger.warning("Shutdown requested — saving progress and exiting")
                break
            if breaker.is_open:
                logger.error("Circuit breaker open — stopping ingestion")
                break

            file_start = time.monotonic()
            logger.info("[%d/%d] Ingesting %s", i + 1, len(files), filepath.name)

            try:
                stats = await ingest_statute_file(
                    filepath, db,
                    embedder=embedder,
                    vector_store=vector_store,
                    graph_store=graph_store,
                    flash_llm=flash_llm,
                    dry_run=args.dry_run,
                    breaker=breaker,
                )
                for k in total_stats:
                    total_stats[k] += stats[k]

                # Record file completion
                elapsed = time.monotonic() - file_start
                logger.info("[%d/%d] %s done in %.1fs — %d inserted, %d errors",
                            i + 1, len(files), filepath.name, elapsed,
                            stats["inserted"], stats["errors"])

                # Save progress checkpoint
                if not args.dry_run:
                    progress["completed_files"].append(filepath.name)
                    progress["stats"][filepath.name] = stats
                    save_progress(progress)

            except Exception as exc:
                logger.error("File-level failure for %s: %s", filepath.name, exc)
                breaker.record_failure()
                total_stats["errors"] += 1

    elapsed_total = time.monotonic() - start_time
    logger.info("=== DONE ===")
    logger.info("Total: %d sections, %d inserted, %d embedded, %d graphed, %d errors (%.1fs)",
                total_stats["total"], total_stats["inserted"],
                total_stats["embedded"], total_stats["graphed"], total_stats["errors"],
                elapsed_total)

    if breaker.is_open:
        logger.error("Ingestion stopped early due to circuit breaker. Run with --resume to continue.")
    if _shutdown_requested:
        logger.warning("Ingestion interrupted. Run with --resume to continue from checkpoint.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Indian statutes")
    parser.add_argument("--source", required=True, help="Path to JSON file or directory")
    parser.add_argument("--db-only", action="store_true", help="Only insert to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no writes")
    parser.add_argument("--contextualize", action="store_true",
                        help="Generate contextual prefixes via Flash LLM")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint, skipping completed files")
    asyncio.run(main(parser.parse_args()))
