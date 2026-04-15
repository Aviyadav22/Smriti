#!/usr/bin/env python3
"""Trial ingestion + quality audit for Indian Supreme Court judgments.

Ingests a small random sample per year via the Vertex AI batch pipeline,
then runs comprehensive quality audit to identify year-specific issues
BEFORE committing to bulk ingestion.

Uses the same 4-phase pipeline as batch_ingest_vertex.py:
  Phase 1: Text extraction + GCS upload (with random sampling)
  Phase 2: Batch metadata extraction via Vertex AI (50% cheaper)
  Phase 3: Online processing per case (chunk, embed, store, graph)
  Audit:   Comprehensive per-year quality analysis + cross-year report

Usage:
    python scripts/trial_ingest.py --year-from 2019 --year-to 2025
    python scripts/trial_ingest.py --year-from 2019 --year-to 2025 --sample-size 5
    python scripts/trial_ingest.py --audit-only
    python scripts/trial_ingest.py --dry-run --year-from 1950 --year-to 2025
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import signal
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env so GOOGLE_APPLICATION_CREDENTIALS is available via os.environ
# (pydantic-settings only populates its own fields, not os.environ)
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import asyncpg  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.ingestion.anonymizer import anonymize_text  # noqa: E402
from app.core.ingestion.pdf import extract_and_score  # noqa: E402
from app.core.ingestion.pipeline import _compute_text_hash  # noqa: E402
from app.core.legal.extractor import _is_valid_act_citation  # noqa: E402
from scripts.batch_ingest_vertex import (  # noqa: E402
    BATCH_RUNS_DIR,
    GCS_BUCKET,
    ManifestEntry,
    _get_gcs_client,
    _make_shutdown_handler,
    _shutdown_event,
    phase2_batch_metadata,
    phase3_process_cases,
)
from scripts.ingest_s3 import (  # noqa: E402
    _match_pdf_to_metadata,
    download_year_data,
    extract_tar,
    load_parquet_metadata,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRIAL_REPORTS_DIR = Path("trial_reports")
DATA_DIR = Path("data")

logger = logging.getLogger("trial_ingest")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(_handler)

# Fields to check for metadata completeness
_AUDIT_FIELDS = [
    "title", "citation", "court", "year", "decision_date",
    "petitioner", "respondent", "author_judge", "disposal_nature",
    "case_type", "bench_type", "coram_size", "ratio_decidendi",
    "keywords", "acts_cited", "cases_cited", "headnotes",
    "outcome_summary", "jurisdiction", "is_reportable",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class YearReport:
    year: int
    sample_size: int
    case_ids: list[str] = field(default_factory=list)
    field_fill_rates: dict[str, float] = field(default_factory=dict)
    overall_completeness: float = 0.0
    confidence: dict[str, float] = field(default_factory=dict)
    chunks: dict[str, float] = field(default_factory=dict)
    acts_quality: dict[str, Any] = field(default_factory=dict)
    cases_cited_quality: dict[str, int] = field(default_factory=dict)
    temporal_guard: dict[str, Any] = field(default_factory=dict)
    text_length: dict[str, float] = field(default_factory=dict)
    vector_coverage: dict[str, float] = field(default_factory=dict)
    health_score: float = 0.0
    anomalies: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 1: Text Extraction + GCS Upload (with random sampling)
# ---------------------------------------------------------------------------


async def trial_phase1_with_sampling(
    year: int,
    sample_size: int,
    seed: int = 42,
    dry_run: bool = False,
) -> tuple[str, list[ManifestEntry]]:
    """Phase 1 with random sampling: download, extract, sample, upload to GCS.

    Returns (run_id, manifest).
    """
    run_id = f"trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{year}"
    run_dir = BATCH_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== TRIAL PHASE 1: year=%d, sample=%d ===", year, sample_size)

    # Download S3 data
    s3_data_dir = DATA_DIR / "s3_cache"
    s3_data_dir.mkdir(parents=True, exist_ok=True)
    tar_path, parquet_path = download_year_data(year, s3_data_dir)

    if not tar_path:
        logger.warning("No tar file for year %d, skipping", year)
        return run_id, []

    # Extract PDFs
    extract_dir = s3_data_dir / f"year={year}" / "pdfs"
    pdf_paths = extract_tar(tar_path, extract_dir)
    if not pdf_paths:
        logger.warning("No PDFs extracted for year %d", year)
        return run_id, []

    # Load parquet metadata
    metadata_map: dict[str, dict] = {}
    if parquet_path and parquet_path.exists():
        metadata_map = load_parquet_metadata(parquet_path)

    stem_index: dict[str, str] = {}
    for key in metadata_map:
        stem = Path(str(key)).stem
        stem_index[stem] = key

    # Random sampling
    rng = random.Random(seed)
    if len(pdf_paths) > sample_size:
        pdf_paths = rng.sample(pdf_paths, sample_size)
    logger.info("Selected %d/%d PDFs for trial", len(pdf_paths), sample_size)

    if dry_run:
        for pdf in pdf_paths:
            parquet_meta = _match_pdf_to_metadata(pdf, metadata_map, stem_index)
            title = parquet_meta.get("title", "???")[:60]
            logger.info("  [DRY-RUN] %s → %s", pdf.name, title)
        return run_id, []

    # GCS client for PDF upload
    gcs_client = _get_gcs_client()
    bucket = gcs_client.bucket(GCS_BUCKET)

    manifest: list[ManifestEntry] = []
    skipped = 0

    for i, pdf_path in enumerate(pdf_paths):
        if _shutdown_event.is_set():
            break

        logger.info("[%d/%d] Extracting: %s", i + 1, len(pdf_paths), pdf_path.name)
        try:
            quality = await extract_and_score(str(pdf_path))
        except (OSError, RuntimeError) as exc:
            logger.warning("Extraction failed: %s — %s", pdf_path.name, exc)
            skipped += 1
            continue

        if not quality.text or quality.char_count < 50:
            logger.warning("Insufficient text: %s (%d chars)", pdf_path.name, quality.char_count)
            skipped += 1
            continue

        full_text, _ = anonymize_text(quality.text)
        text_hash = _compute_text_hash(full_text)

        # Dedup: skip if already fully ingested
        from sqlalchemy import text as sa_text

        from app.db.postgres import async_session_factory

        async with async_session_factory() as db:
            existing = await db.execute(
                sa_text("SELECT id, chunk_count FROM cases WHERE text_hash = :hash"),
                {"hash": text_hash},
            )
            row = existing.fetchone()
            if row and row[1] and row[1] > 0:
                logger.info("  Skipping (already ingested): %s", pdf_path.name)
                skipped += 1
                continue

        parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map, stem_index)
        case_id = str(uuid.uuid4())

        # Upload PDF to GCS
        gcs_uri = f"gs://{GCS_BUCKET}/pdfs/{case_id}.pdf"
        try:
            blob = bucket.blob(f"pdfs/{case_id}.pdf")
            blob.upload_from_filename(str(pdf_path))
        except Exception as upload_exc:
            logger.warning("GCS upload failed: %s — %s", pdf_path.name, upload_exc)
            gcs_uri = f"local://{pdf_path}"

        entry = ManifestEntry(
            case_id=case_id,
            pdf_local_path=str(pdf_path),
            gcs_pdf_uri=gcs_uri,
            text_hash=text_hash,
            full_text=full_text,
            parquet_meta=parquet_meta,
            quality_tier=quality.tier,
            page_count=quality.page_count,
            page_map=quality.page_map,
            char_count=quality.char_count,
        )
        manifest.append(entry)

    # Save manifest
    manifest_data = [
        {
            "case_id": e.case_id,
            "pdf_local_path": e.pdf_local_path,
            "gcs_pdf_uri": e.gcs_pdf_uri,
            "text_hash": e.text_hash,
            "quality_tier": e.quality_tier,
            "page_count": e.page_count,
            "page_map": e.page_map,
            "char_count": e.char_count,
            "parquet_meta": {
                k: (str(v) if v is not None and not isinstance(v, (str, int, float, bool, list)) else v)
                for k, v in e.parquet_meta.items()
            },
        }
        for e in manifest
    ]
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2, default=str), encoding="utf-8")

    texts_dir = run_dir / "texts"
    texts_dir.mkdir(exist_ok=True)
    for entry in manifest:
        (texts_dir / f"{entry.case_id}.txt").write_text(entry.full_text, encoding="utf-8")

    logger.info("Phase 1 done: %d in manifest, %d skipped", len(manifest), skipped)
    return run_id, manifest


# ---------------------------------------------------------------------------
# Multi-year ingestion loop
# ---------------------------------------------------------------------------


async def run_trial_years(
    year_from: int,
    year_to: int,
    sample_size: int,
    seed: int,
    dry_run: bool,
    rpm_limit: int,
    concurrency: int,
    output_dir: Path,
    year_step: int = 1,
) -> dict[int, list[str]]:
    """Run trial ingestion across multiple years using mega-batch approach.

    Instead of submitting one batch job per year (61 jobs, each with 10-15 min
    polling overhead), we:
      1. Run Phase 1 for ALL years first (extract + sample + upload)
      2. Submit ONE mega batch job for all cases (~15-20 min total)
      3. Run Phase 3 for all cases with concurrency

    Returns {year: [case_ids]}.
    """
    trial_case_ids: dict[int, list[str]] = {}
    # Track which manifest entries belong to which year
    year_manifests: dict[int, tuple[str, list[ManifestEntry]]] = {}

    years = list(range(year_from, year_to + 1, year_step))

    # ── Phase 1: Extract + sample ALL years ──────────────────────────
    logger.info("=" * 60)
    logger.info("MEGA-BATCH PHASE 1: Extracting %d years (%d-%d, step=%d)",
                len(years), year_from, year_to, year_step)
    logger.info("=" * 60)

    import gc
    import shutil

    for year in years:
        if _shutdown_event.is_set():
            logger.warning("Shutdown requested — stopping Phase 1 loop")
            break

        logger.info("--- Phase 1: Year %d ---", year)
        run_id, manifest = await trial_phase1_with_sampling(
            year, sample_size, seed=seed, dry_run=dry_run,
        )

        # Free extracted PDFs from disk after each year to prevent OOM
        year_pdf_dir = DATA_DIR / "s3_cache" / f"year={year}" / "pdfs"
        if year_pdf_dir.exists():
            shutil.rmtree(year_pdf_dir, ignore_errors=True)
        gc.collect()

        if not manifest:
            logger.info("No cases for year %d, skipping", year)
            trial_case_ids[year] = []
            continue

        if dry_run:
            trial_case_ids[year] = []
            continue

        year_manifests[year] = (run_id, manifest)

    if dry_run or not year_manifests:
        return trial_case_ids

    # ── Phase 2: ONE mega batch job for all cases ────────────────────
    all_entries: list[ManifestEntry] = []
    for year in sorted(year_manifests):
        _, manifest = year_manifests[year]
        all_entries.extend(manifest)

    logger.info("=" * 60)
    logger.info(
        "MEGA-BATCH PHASE 2: Submitting %d cases from %d years in ONE batch job",
        len(all_entries), len(year_manifests),
    )
    logger.info("=" * 60)

    # Create a mega run directory
    mega_run_id = f"trial_mega_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    mega_run_dir = BATCH_RUNS_DIR / mega_run_id
    mega_run_dir.mkdir(parents=True, exist_ok=True)

    # Save combined manifest
    mega_manifest_data = [
        {
            "case_id": e.case_id,
            "pdf_local_path": e.pdf_local_path,
            "gcs_pdf_uri": e.gcs_pdf_uri,
            "text_hash": e.text_hash,
            "quality_tier": e.quality_tier,
            "page_count": e.page_count,
            "page_map": e.page_map,
            "char_count": e.char_count,
            "parquet_meta": {
                k: (str(v) if v is not None and not isinstance(v, (str, int, float, bool, list)) else v)
                for k, v in e.parquet_meta.items()
            },
        }
        for e in all_entries
    ]
    (mega_run_dir / "manifest.json").write_text(
        json.dumps(mega_manifest_data, indent=2, default=str), encoding="utf-8",
    )

    # Save texts for Phase 3 resume
    texts_dir = mega_run_dir / "texts"
    texts_dir.mkdir(exist_ok=True)
    for entry in all_entries:
        (texts_dir / f"{entry.case_id}.txt").write_text(entry.full_text, encoding="utf-8")

    # Submit ONE batch job
    try:
        metadata_results = await phase2_batch_metadata(mega_run_id, all_entries)
    except (RuntimeError, KeyboardInterrupt) as exc:
        logger.error("Mega batch Phase 2 failed: %s", exc)
        # Save what we have so far
        _save_trial_state(trial_case_ids, output_dir)
        return trial_case_ids

    if _shutdown_event.is_set():
        _save_trial_state(trial_case_ids, output_dir)
        return trial_case_ids

    # ── Free Phase 1/2 memory before Phase 3 (prevent OOM) ──────────
    # Clear any remaining extracted PDF directories
    s3_cache_dir = DATA_DIR / "s3_cache"
    if s3_cache_dir.exists():
        for year_dir in s3_cache_dir.iterdir():
            pdf_dir = year_dir / "pdfs" if year_dir.is_dir() else None
            if pdf_dir and pdf_dir.exists():
                shutil.rmtree(pdf_dir, ignore_errors=True)
        logger.info("Cleared extracted PDF directories from s3_cache")
    gc.collect()
    logger.info("GC collected before Phase 3 — freed memory from Phase 1/2")

    # ── Phase 3: Process all cases with concurrency ──────────────────
    logger.info("=" * 60)
    logger.info(
        "MEGA-BATCH PHASE 3: Processing %d cases (concurrency=%d, rpm=%d)",
        len(all_entries), concurrency, rpm_limit,
    )
    logger.info("=" * 60)

    statuses = await phase3_process_cases(
        mega_run_id, all_entries, metadata_results,
        rpm_limit=rpm_limit, concurrency=concurrency,
    )

    # Map results back to years
    entry_year_map: dict[str, int] = {}
    for year, (_, manifest) in year_manifests.items():
        for entry in manifest:
            entry_year_map[entry.case_id] = year

    for year in sorted(year_manifests):
        _, manifest = year_manifests[year]
        success_ids = [
            e.case_id for e in manifest
            if statuses.get(e.case_id) == "success"
        ]
        failed = len(manifest) - len(success_ids)
        logger.info(
            "Year %d: %d success, %d failed",
            year, len(success_ids), failed,
        )
        trial_case_ids[year] = success_ids

    _save_trial_state(trial_case_ids, output_dir)
    return trial_case_ids


def _save_trial_state(trial_case_ids: dict[int, list[str]], output_dir: Path) -> None:
    """Save trial case IDs for audit-only re-runs."""
    tag = f"trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / f"{tag}_case_ids.json"
    state_path.write_text(
        json.dumps({"tag": tag, "case_ids": trial_case_ids}, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Trial case IDs saved to %s", state_path)


# ---------------------------------------------------------------------------
# Quality Audit
# ---------------------------------------------------------------------------


def _get_dsn() -> str:
    url = settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def audit_year(year: int, case_ids: list[str], conn: asyncpg.Connection) -> YearReport:
    """Run comprehensive quality audit on a year's trial cases."""
    report = YearReport(year=year, sample_size=len(case_ids), case_ids=case_ids)

    if not case_ids:
        report.anomalies.append("no cases ingested")
        return report

    # Fetch all case data in one query
    rows = await conn.fetch(
        """
        SELECT id::text, title, citation, court, year, decision_date,
               petitioner, respondent, author_judge, disposal_nature,
               case_type, bench_type, coram_size, ratio_decidendi,
               keywords, acts_cited, cases_cited, headnotes,
               outcome_summary, jurisdiction, is_reportable,
               extraction_confidence, chunk_count, ingestion_status,
               char_length(full_text) as text_length
        FROM cases WHERE id = ANY($1::uuid[])
        """,
        case_ids,
    )

    if not rows:
        report.anomalies.append("cases not found in DB")
        return report

    n = len(rows)

    # 1. Metadata completeness
    for fld in _AUDIT_FIELDS:
        count = 0
        for r in rows:
            val = r[fld]
            if val is not None:
                if isinstance(val, (list,)):
                    count += 1 if len(val) > 0 else 0
                elif isinstance(val, str):
                    count += 1 if val.strip() else 0
                else:
                    count += 1
        report.field_fill_rates[fld] = round(count / n, 2)
    report.overall_completeness = round(
        sum(report.field_fill_rates.values()) / len(_AUDIT_FIELDS), 2
    )

    # 2. Extraction confidence
    confs = [r["extraction_confidence"] for r in rows if r["extraction_confidence"] is not None]
    if confs:
        report.confidence = {
            "avg": round(sum(confs) / len(confs), 3),
            "min": round(min(confs), 3),
            "max": round(max(confs), 3),
        }
        if report.confidence["avg"] < 0.75:
            report.anomalies.append(f"low-conf (avg={report.confidence['avg']})")

    # 3. Chunk count
    chunks = [r["chunk_count"] for r in rows if r["chunk_count"] is not None]
    if chunks:
        report.chunks = {
            "avg": round(sum(chunks) / len(chunks), 1),
            "min": min(chunks),
            "max": max(chunks),
        }
        zero_chunks = [r["id"] for r in rows if not r["chunk_count"]]
        if zero_chunks:
            report.anomalies.append(f"{len(zero_chunks)} cases with 0 chunks")

    # 4. Acts quality
    total_acts = 0
    garbage_count = 0
    garbage_examples: list[str] = []
    for r in rows:
        acts = r["acts_cited"] or []
        for act in acts:
            total_acts += 1
            if not _is_valid_act_citation(act):
                garbage_count += 1
                if len(garbage_examples) < 5:
                    garbage_examples.append(act)
    report.acts_quality = {
        "total": total_acts,
        "garbage": garbage_count,
        "examples": garbage_examples,
    }
    if garbage_count > 0:
        report.anomalies.append(f"{garbage_count} garbage acts")

    # 5. Cases cited quality
    newlines = 0
    self_cites = 0
    bare_dockets = 0
    for r in rows:
        cases = r["cases_cited"] or []
        citation = r["citation"] or ""
        own_norm = re.sub(r"\s+", " ", citation.strip().lower()) if citation else ""
        for c in cases:
            if "\n" in c or "\r" in c:
                newlines += 1
            if own_norm and re.sub(r"\s+", " ", c.strip().lower()) == own_norm:
                self_cites += 1
            if re.match(r"^\d{3,5}\s+[Oo]f\s+\d{4}$", c.strip()):
                bare_dockets += 1
    report.cases_cited_quality = {
        "newlines": newlines,
        "self_citations": self_cites,
        "bare_dockets": bare_dockets,
    }
    issues = newlines + self_cites + bare_dockets
    if issues > 0:
        report.anomalies.append(f"{issues} cases_cited issues")

    # 6. Temporal guard (pre-2024 with BNS/BNSS/BSA)
    violations = 0
    offenders: list[str] = []
    new_codes = {"BNS", "BNSS", "BSA"}
    for r in rows:
        if r["year"] and r["year"] < 2024:
            acts = set(r["acts_cited"] or [])
            found = acts & new_codes
            if found:
                violations += 1
                offenders.append(r["id"])
    report.temporal_guard = {"violations": violations, "offending_case_ids": offenders}
    if violations > 0:
        report.anomalies.append(f"{violations} temporal guard violations")

    # 7. Text length
    lengths = [r["text_length"] for r in rows if r["text_length"] is not None]
    if lengths:
        report.text_length = {
            "avg": round(sum(lengths) / len(lengths)),
            "min": min(lengths),
            "max": max(lengths),
        }
        short = [r["id"] for r in rows if r["text_length"] and r["text_length"] < 500]
        if short:
            report.anomalies.append(f"{len(short)} cases with <500 chars text")

    # 8. Health score
    report.health_score = compute_health_score(report)

    return report


def compute_health_score(r: YearReport) -> float:
    """Compute weighted 0.0-1.0 health score."""
    score = 0.0

    # Metadata completeness: 30%
    score += r.overall_completeness * 0.30

    # Confidence: 25%
    conf_avg = r.confidence.get("avg", 0.0)
    score += min(conf_avg / 0.9, 1.0) * 0.25  # normalize: 0.9+ = perfect

    # Acts quality: 15%
    total_acts = r.acts_quality.get("total", 0)
    garbage = r.acts_quality.get("garbage", 0)
    acts_clean = 1.0 - (garbage / max(total_acts, 1))
    score += acts_clean * 0.15

    # Cases cited quality: 10%
    cq = r.cases_cited_quality
    total_issues = cq.get("newlines", 0) + cq.get("self_citations", 0) + cq.get("bare_dockets", 0)
    cite_clean = 1.0 if total_issues == 0 else max(0.0, 1.0 - total_issues * 0.1)
    score += cite_clean * 0.10

    # Text quality: 10%
    text_min = r.text_length.get("min", 0)
    text_ok = 1.0 if text_min >= 500 else 0.5
    score += text_ok * 0.10

    # Temporal guard: 10%
    guard_ok = 1.0 if r.temporal_guard.get("violations", 0) == 0 else 0.0
    score += guard_ok * 0.10

    return round(score, 2)


async def audit_all_years(
    trial_case_ids: dict[int, list[str]],
) -> dict[int, YearReport]:
    """Run audit for all trial years."""
    dsn = _get_dsn()
    conn = await asyncpg.connect(dsn, timeout=30)
    reports: dict[int, YearReport] = {}

    try:
        for year in sorted(trial_case_ids.keys()):
            case_ids = trial_case_ids[year]
            if not case_ids:
                reports[year] = YearReport(
                    year=year, sample_size=0,
                    anomalies=["no cases ingested"],
                )
                continue
            reports[year] = await audit_year(year, case_ids, conn)
    finally:
        await conn.close()

    return reports


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def print_report_table(
    reports: dict[int, YearReport],
    tag: str,
    sample_size: int,
) -> None:
    """Print year-by-year comparison table to console."""
    total_cases = sum(r.sample_size for r in reports.values())
    years_with_data = [y for y, r in reports.items() if r.case_ids]

    print()
    print("=" * 85)
    print(f"  Trial Ingestion Report: {tag}")
    print(f"  Years: {min(reports.keys())}-{max(reports.keys())} | "
          f"Sample: {sample_size}/year | Total: {total_cases} cases")
    print("=" * 85)
    print()
    print(f"  {'Year':<6} {'Health':>7} {'Fields%':>8} {'Conf':>6} "
          f"{'Chunks':>7} {'Acts.Err':>9} {'TxtLen':>8} {'Anomalies'}")
    print(f"  {'-' * 6} {'-' * 7} {'-' * 8} {'-' * 6} "
          f"{'-' * 7} {'-' * 9} {'-' * 8} {'-' * 25}")

    flagged: list[tuple[int, list[str]]] = []

    for year in sorted(reports.keys()):
        r = reports[year]
        if not r.case_ids:
            print(f"  {year:<6} {'—':>7} {'—':>8} {'—':>6} "
                  f"{'—':>7} {'—':>9} {'—':>8} no data")
            continue

        health = f"{r.health_score:.2f}"
        fields_pct = f"{r.overall_completeness * 100:.0f}%"
        conf = f"{r.confidence.get('avg', 0):.2f}"
        chunks_avg = f"{r.chunks.get('avg', 0):.0f}"
        acts_err = str(r.acts_quality.get("garbage", 0))
        txt_len = f"{r.text_length.get('avg', 0) / 1000:.1f}K"
        anomaly_str = ", ".join(r.anomalies[:3]) if r.anomalies else ""

        print(f"  {year:<6} {health:>7} {fields_pct:>8} {conf:>6} "
              f"{chunks_avg:>7} {acts_err:>9} {txt_len:>8} {anomaly_str}")

        if r.health_score < 0.75 and r.case_ids:
            flagged.append((year, r.anomalies))

    print()
    if flagged:
        print("  FLAGGED YEARS (health < 0.75):")
        for year, anomalies in flagged:
            print(f"    {year}: {', '.join(anomalies)}")
    else:
        print("  All years healthy (score >= 0.75)")
    print()


def save_report(
    reports: dict[int, YearReport],
    tag: str,
    config: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Save JSON report."""
    output_dir.mkdir(parents=True, exist_ok=True)

    avg_health = 0.0
    years_with_data = [r for r in reports.values() if r.case_ids]
    if years_with_data:
        avg_health = round(
            sum(r.health_score for r in years_with_data) / len(years_with_data), 2
        )

    flagged_years = [
        y for y, r in reports.items()
        if r.case_ids and r.health_score < 0.75
    ]

    report_data = {
        "tag": tag,
        "timestamp": datetime.now().isoformat(),
        "config": config,
        "years": {
            str(y): asdict(r) for y, r in sorted(reports.items())
        },
        "summary": {
            "total_cases": sum(r.sample_size for r in reports.values()),
            "avg_health": avg_health,
            "flagged_years": flagged_years,
        },
    }

    report_path = output_dir / f"{tag}.json"
    report_path.write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")
    logger.info("Report saved to %s", report_path)
    return report_path


# ---------------------------------------------------------------------------
# Audit-only: load case IDs from previous trial run
# ---------------------------------------------------------------------------


def load_latest_trial_ids(output_dir: Path) -> dict[int, list[str]]:
    """Load case IDs from the most recent trial run."""
    id_files = sorted(output_dir.glob("*_case_ids.json"), reverse=True)
    if not id_files:
        logger.error("No trial case ID files found in %s", output_dir)
        return {}

    latest = id_files[0]
    logger.info("Loading trial case IDs from %s", latest)
    data = json.loads(latest.read_text(encoding="utf-8"))
    raw = data.get("case_ids", {})
    # Convert string keys to int
    return {int(k): v for k, v in raw.items()}


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------


async def async_main(args: argparse.Namespace) -> None:
    # Install signal handlers
    loop = asyncio.get_running_loop()
    handler = _make_shutdown_handler(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handler)
        except (OSError, ValueError):
            pass

    output_dir = Path(args.output_dir)
    tag = f"trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if args.audit_only:
        # Re-audit existing trial cases
        trial_case_ids = load_latest_trial_ids(output_dir)
        if not trial_case_ids:
            return
    else:
        # Enforce Vertex AI
        if not args.dry_run and not settings.gemini_use_vertexai:
            logger.error(
                "GEMINI_USE_VERTEXAI must be true for trial ingestion. "
                "Set GEMINI_USE_VERTEXAI=true in .env"
            )
            return

        # Run trial ingestion
        trial_case_ids = await run_trial_years(
            year_from=args.year_from,
            year_to=args.year_to,
            sample_size=args.sample_size,
            seed=args.seed,
            dry_run=args.dry_run,
            rpm_limit=args.rpm_limit,
            concurrency=args.concurrency,
            output_dir=output_dir,
            year_step=args.year_step,
        )

        if args.dry_run:
            logger.info("Dry run complete — no cases ingested, no audit needed")
            return

    # Run audit
    logger.info("=" * 60)
    logger.info("RUNNING QUALITY AUDIT")
    logger.info("=" * 60)

    reports = await audit_all_years(trial_case_ids)

    # Print and save report
    config = {
        "year_from": args.year_from if not args.audit_only else min(trial_case_ids.keys()),
        "year_to": args.year_to if not args.audit_only else max(trial_case_ids.keys()),
        "sample_size": args.sample_size,
        "year_step": args.year_step,
        "seed": args.seed,
    }
    print_report_table(reports, tag, args.sample_size)
    save_report(reports, tag, config, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trial ingestion + quality audit via Vertex AI batch pipeline",
    )
    parser.add_argument("--year-from", type=int, help="Start year (inclusive)")
    parser.add_argument("--year-to", type=int, help="End year (inclusive)")
    parser.add_argument("--sample-size", type=int, default=10, help="Cases per year (default: 10)")
    parser.add_argument("--year-step", type=int, default=1, help="Step between years, e.g. 5 = every 5th year (default: 1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--audit-only", action="store_true", help="Skip ingestion, audit existing trial cases")
    parser.add_argument("--dry-run", action="store_true", help="Phase 1 only, no API calls")
    parser.add_argument("--rpm-limit", type=int, default=30, help="Gemini RPM for Phase 3 (default: 30)")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent Phase 3 tasks (default: 1)")
    parser.add_argument("--output-dir", type=str, default="trial_reports", help="Report output dir")

    args = parser.parse_args()

    if not args.audit_only and (args.year_from is None or args.year_to is None):
        parser.error("--year-from and --year-to are required unless --audit-only")

    asyncio.run(async_main(args))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in trial ingestion")
        sys.exit(1)
