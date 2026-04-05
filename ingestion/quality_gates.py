"""Quality gate checks for turbo ingestion pipeline.

5-layer quality defense system:
  Layer 1: Trial run validation (50 cases)
  Layer 2: Progressive rollout gates
  Layer 3: Automated metadata validation (between Phase 2 -> 3)
  Layer 4: Per-case validation (during Phase 3)
  Layer 5: Post-batch spot check (after each rollout step)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Result of a quality gate check."""

    passed: bool
    checks: dict[str, Any]
    failures: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "failures": self.failures,
            "warnings": self.warnings,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")
        logger.info("Quality report saved to %s", path)


# ---------------------------------------------------------------------------
# Layer 3: Metadata quality gate (between Phase 2 and Phase 3)
# ---------------------------------------------------------------------------


def validate_batch_metadata(metadata_results: dict[str, dict]) -> QualityReport:
    """Validate batch metadata results before spending credits on embeddings.

    Catches:
    - Missing/empty required fields
    - Cross-contamination (same metadata across cases -- the 4K bug)
    - Suspiciously low field coverage
    """
    total = len(metadata_results)
    if total == 0:
        return QualityReport(
            passed=False, checks={"total": 0},
            failures=["No metadata results to validate"], warnings=[],
        )

    checks: dict[str, Any] = {"total_cases": total}
    failures: list[str] = []
    warnings: list[str] = []

    # --- Field coverage ---
    required_fields = ["title", "citation", "year", "court", "judge"]
    for field in required_fields:
        count = sum(1 for m in metadata_results.values() if m.get(field))
        pct = count / total
        checks[f"has_{field}"] = f"{count}/{total} ({pct:.1%})"
        if pct < 0.85:
            failures.append(f"Only {pct:.1%} of cases have '{field}' (need >=85%)")
        elif pct < 0.95:
            warnings.append(f"{pct:.1%} of cases have '{field}' (below 95%)")

    # --- Uniqueness check (catches cross-contamination bug) ---
    titles = [m.get("title", "") for m in metadata_results.values() if m.get("title")]
    unique_titles = len(set(titles))
    checks["unique_titles"] = f"{unique_titles}/{len(titles)}"
    if len(titles) > 10 and unique_titles < len(titles) * 0.85:
        failures.append(
            f"Only {unique_titles}/{len(titles)} unique titles -- "
            f"possible cross-contamination!"
        )

    citations = [m.get("citation", "") for m in metadata_results.values() if m.get("citation")]
    unique_citations = len(set(citations))
    checks["unique_citations"] = f"{unique_citations}/{len(citations)}"
    if len(citations) > 10 and unique_citations < len(citations) * 0.80:
        failures.append(
            f"Only {unique_citations}/{len(citations)} unique citations -- "
            f"possible cross-contamination!"
        )

    ratios = [m.get("ratio_decidendi", "") for m in metadata_results.values() if m.get("ratio_decidendi")]
    unique_ratios = len(set(ratios))
    checks["unique_ratios"] = f"{unique_ratios}/{len(ratios)}"
    if len(ratios) > 10 and unique_ratios < len(ratios) * 0.80:
        failures.append(
            f"Only {unique_ratios}/{len(ratios)} unique ratio_decidendi -- "
            f"possible cross-contamination!"
        )

    # --- Year sanity ---
    years = [m.get("year") for m in metadata_results.values() if m.get("year")]
    if years:
        int_years = [int(y) for y in years if str(y).isdigit()]
        if int_years:
            checks["year_range"] = f"{min(int_years)}-{max(int_years)}"
            out_of_range = [y for y in int_years if y < 1947 or y > 2027]
            if out_of_range:
                warnings.append(f"{len(out_of_range)} cases have year outside 1947-2027")

    # --- Duplicate detection (exact same metadata blob) ---
    meta_hashes = [json.dumps(m, sort_keys=True) for m in metadata_results.values()]
    unique_blobs = len(set(meta_hashes))
    checks["unique_metadata_blobs"] = f"{unique_blobs}/{total}"
    if total > 10 and unique_blobs < total * 0.90:
        failures.append(
            f"Only {unique_blobs}/{total} unique metadata blobs -- "
            f"cases may have identical metadata!"
        )

    passed = len(failures) == 0
    return QualityReport(passed=passed, checks=checks, failures=failures, warnings=warnings)


# ---------------------------------------------------------------------------
# Layer 3b: Content quality gate (audit-driven checks)
# ---------------------------------------------------------------------------

_REPORTER_PREAMBLE_PATTERNS = [
    "SUPREME COURT REPORTS",
    "SCC Online",
    "ALL INDIA REPORTER",
    "PETITIONER:",
    "RESPONDENT:",
    "CITATION:",
    "DATE OF JUDGMENT:",
]


def validate_content_quality(metadata_results: dict[str, dict]) -> QualityReport:
    """Validate content quality issues identified in the metadata audit.

    Catches:
    - Header bloat (>5K chars in first chunk text or description)
    - NULL description / outcome_summary rates
    - Editorial contamination in headnotes
    - Verbose ratio_decidendi (>1500 chars)
    - Low confidence without remediation
    """
    total = len(metadata_results)
    if total == 0:
        return QualityReport(
            passed=True, checks={"total": 0},
            failures=[], warnings=[],
        )

    checks: dict[str, Any] = {"total_cases": total}
    failures: list[str] = []
    warnings: list[str] = []

    null_description = 0
    null_outcome = 0
    verbose_ratio = 0
    low_confidence = 0
    header_bloat = 0
    editorial_headnotes = 0

    for case_id, meta in metadata_results.items():
        # NULL description
        if not meta.get("case_description") and not meta.get("description"):
            null_description += 1

        # NULL outcome_summary
        if not meta.get("outcome_summary"):
            null_outcome += 1

        # Verbose ratio (>1500 chars)
        ratio = meta.get("ratio_decidendi", "")
        if ratio and len(ratio) > 1500:
            verbose_ratio += 1

        # Low confidence
        conf = meta.get("extraction_confidence", 1.0)
        if isinstance(conf, (int, float)) and conf < 0.6:
            low_confidence += 1

        # Header bloat: check if title or description contains reporter preamble
        title = meta.get("title", "") or ""
        for pattern in _REPORTER_PREAMBLE_PATTERNS:
            if pattern in title.upper():
                header_bloat += 1
                break

        # Editorial headnotes check
        headnotes = meta.get("headnotes", "")
        if headnotes:
            hn_str = headnotes if isinstance(headnotes, str) else str(headnotes)
            if any(kw in hn_str.lower() for kw in [
                "held -", "held that the court", "per ", "it was contended",
                "reporter's note", "[ed.", "result of the case",
            ]):
                editorial_headnotes += 1

    # Report rates
    desc_pct = null_description / total
    outcome_pct = null_outcome / total
    ratio_pct = verbose_ratio / total
    conf_pct = low_confidence / total
    bloat_pct = header_bloat / total
    editorial_pct = editorial_headnotes / total

    checks["null_description"] = f"{null_description}/{total} ({desc_pct:.1%})"
    checks["null_outcome_summary"] = f"{null_outcome}/{total} ({outcome_pct:.1%})"
    checks["verbose_ratio"] = f"{verbose_ratio}/{total} ({ratio_pct:.1%})"
    checks["low_confidence"] = f"{low_confidence}/{total} ({conf_pct:.1%})"
    checks["header_bloat_in_title"] = f"{header_bloat}/{total} ({bloat_pct:.1%})"
    checks["editorial_headnotes"] = f"{editorial_headnotes}/{total} ({editorial_pct:.1%})"

    # Thresholds — FAIL if rates exceed acceptable limits
    if desc_pct > 0.15:
        failures.append(
            f"NULL description rate {desc_pct:.1%} exceeds 15% threshold"
        )
    elif desc_pct > 0.08:
        warnings.append(f"NULL description rate {desc_pct:.1%} is elevated (>8%)")

    if outcome_pct > 0.15:
        failures.append(
            f"NULL outcome_summary rate {outcome_pct:.1%} exceeds 15% threshold"
        )
    elif outcome_pct > 0.08:
        warnings.append(f"NULL outcome_summary rate {outcome_pct:.1%} is elevated (>8%)")

    if ratio_pct > 0.10:
        warnings.append(f"Verbose ratio rate {ratio_pct:.1%} is elevated (>10%)")

    if conf_pct > 0.20:
        failures.append(
            f"Low confidence rate {conf_pct:.1%} exceeds 20% threshold"
        )
    elif conf_pct > 0.10:
        warnings.append(f"Low confidence rate {conf_pct:.1%} is elevated (>10%)")

    if bloat_pct > 0.10:
        warnings.append(
            f"Header bloat in titles {bloat_pct:.1%} is elevated (>10%)"
        )

    if editorial_pct > 0.20:
        warnings.append(
            f"Editorial headnote contamination {editorial_pct:.1%} is elevated (>20%)"
        )

    passed = len(failures) == 0
    return QualityReport(passed=passed, checks=checks, failures=failures, warnings=warnings)


# ---------------------------------------------------------------------------
# Layer 4: Per-case validation (during Phase 3)
# ---------------------------------------------------------------------------


def validate_case_before_upsert(
    case_id: str,
    chunks: list,
    embeddings: list[list[float]],
    metadata: dict,
    prev_case_metadata: dict | None = None,
) -> tuple[bool, list[str]]:
    """Validate a single case before upserting to vector DB.

    Returns (is_valid, list_of_issues).
    """
    issues: list[str] = []

    # Chunk count sanity
    if len(chunks) == 0:
        issues.append("Zero chunks produced")
    elif len(chunks) > 500:
        issues.append(f"Suspiciously high chunk count: {len(chunks)}")

    # Embedding dimension check
    for i, emb in enumerate(embeddings[:3]):  # Spot check first 3
        if len(emb) != 1536:
            issues.append(f"Embedding {i} has {len(emb)} dims (expected 1536)")
            break

    # Embedding count matches chunks
    if len(embeddings) != len(chunks):
        issues.append(
            f"Chunk/embedding mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings"
        )

    # Metadata not empty
    if not metadata.get("title"):
        issues.append("Missing title in metadata")

    # Cross-contamination check: compare with previous case
    if prev_case_metadata:
        if (
            metadata.get("title") == prev_case_metadata.get("title")
            and metadata.get("citation") == prev_case_metadata.get("citation")
            and metadata.get("title")  # Only flag if non-empty
        ):
            issues.append(
                f"CROSS-CONTAMINATION: metadata identical to previous case! "
                f"title='{metadata.get('title')}'"
            )

    is_valid = len(issues) == 0
    if not is_valid:
        logger.warning("Case %s validation failed: %s", case_id, "; ".join(issues))

    return is_valid, issues


# ---------------------------------------------------------------------------
# Layer 5: Post-batch spot check
# ---------------------------------------------------------------------------


async def post_batch_spot_check(
    case_ids: list[str],
    sample_size: int = 10,
) -> QualityReport:
    """Query all databases to verify data integrity after a batch.

    Samples N random cases and checks PostgreSQL, Pinecone, and Neo4j.
    """
    import asyncpg
    from pinecone import Pinecone
    from neo4j import GraphDatabase

    sample = random.sample(case_ids, min(sample_size, len(case_ids)))
    checks: dict[str, Any] = {"sample_size": len(sample), "total_cases": len(case_ids)}
    failures: list[str] = []
    warnings: list[str] = []

    # Connect to PostgreSQL
    from app.core.config import settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pg_conn = await asyncpg.connect(dsn)

    # Connect to Pinecone
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    pine_idx = pc.Index(host=os.environ.get("PINECONE_HOST"))

    # Connect to Neo4j
    neo4j_driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI"),
        auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD")),
    )

    case_results: dict[str, dict] = {}

    for case_id in sample:
        result: dict[str, Any] = {"case_id": case_id}

        # Check PostgreSQL
        try:
            row = await pg_conn.fetchrow(
                "SELECT id, title, citation, ratio_decidendi, extraction_confidence "
                "FROM cases WHERE id = $1::uuid",
                case_id,
            )
            result["pg_exists"] = row is not None
            if row:
                result["pg_title"] = row["title"][:50] if row["title"] else None
                result["pg_has_ratio"] = bool(row["ratio_decidendi"])
                result["pg_confidence"] = row["extraction_confidence"]
            else:
                failures.append(f"Case {case_id[:12]}: NOT in PostgreSQL")
        except Exception as exc:
            result["pg_error"] = str(exc)
            warnings.append(f"Case {case_id[:12]}: PG check error: {exc}")

        # Check Pinecone
        try:
            query_result = pine_idx.query(
                vector=[0.0] * 1536,
                top_k=1,
                filter={"case_id": case_id},
                include_metadata=True,
            )
            result["pinecone_has_vectors"] = len(query_result.matches) > 0
            if not result["pinecone_has_vectors"]:
                failures.append(f"Case {case_id[:12]}: NO vectors in Pinecone")
        except Exception as exc:
            result["pinecone_error"] = str(exc)
            warnings.append(f"Case {case_id[:12]}: Pinecone check error: {exc}")

        # Check Neo4j
        try:
            with neo4j_driver.session() as sess:
                neo_result = sess.run(
                    "MATCH (c:Case) WHERE c.id = $cid RETURN count(c) as cnt",
                    cid=case_id,
                )
                exists = neo_result.single()["cnt"] > 0
                result["neo4j_exists"] = exists
                if not exists:
                    warnings.append(f"Case {case_id[:12]}: NOT in Neo4j")
        except Exception as exc:
            result["neo4j_error"] = str(exc)
            warnings.append(f"Case {case_id[:12]}: Neo4j check error: {exc}")

        case_results[case_id] = result

    await pg_conn.close()
    neo4j_driver.close()

    checks["case_results"] = case_results

    # Summary
    pg_ok = sum(1 for r in case_results.values() if r.get("pg_exists"))
    pine_ok = sum(1 for r in case_results.values() if r.get("pinecone_has_vectors"))
    neo4j_ok = sum(1 for r in case_results.values() if r.get("neo4j_exists"))
    checks["pg_pass_rate"] = f"{pg_ok}/{len(sample)}"
    checks["pinecone_pass_rate"] = f"{pine_ok}/{len(sample)}"
    checks["neo4j_pass_rate"] = f"{neo4j_ok}/{len(sample)}"

    if pg_ok < len(sample) * 0.9:
        failures.append(f"PostgreSQL: only {pg_ok}/{len(sample)} cases found")
    if pine_ok < len(sample) * 0.8:
        failures.append(f"Pinecone: only {pine_ok}/{len(sample)} cases have vectors")

    passed = len(failures) == 0
    return QualityReport(passed=passed, checks=checks, failures=failures, warnings=warnings)


# ---------------------------------------------------------------------------
# Capacity check
# ---------------------------------------------------------------------------


async def check_capacity_limits() -> QualityReport:
    """Check if Pinecone/Neo4j are approaching their limits."""
    checks: dict[str, Any] = {}
    failures: list[str] = []
    warnings: list[str] = []

    # Pinecone vector count
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        idx = pc.Index(host=os.environ.get("PINECONE_HOST"))
        stats = idx.describe_index_stats()
        total_vectors = stats.total_vector_count
        checks["pinecone_vectors"] = total_vectors
        checks["pinecone_limit"] = 1_000_000
        checks["pinecone_remaining"] = 1_000_000 - total_vectors

        if total_vectors > 950_000:
            failures.append(f"Pinecone at {total_vectors}/1M vectors -- CRITICAL")
        elif total_vectors > 850_000:
            warnings.append(f"Pinecone at {total_vectors}/1M vectors -- approaching limit")
    except Exception as exc:
        warnings.append(f"Could not check Pinecone: {exc}")

    # Neo4j node count
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI"),
            auth=(os.environ.get("NEO4J_USER"), os.environ.get("NEO4J_PASSWORD")),
        )
        with driver.session() as sess:
            result = sess.run("MATCH (n) RETURN count(n) as cnt")
            count = result.single()["cnt"]
        driver.close()
        checks["neo4j_nodes"] = count
        checks["neo4j_limit"] = 200_000

        if count > 180_000:
            failures.append(f"Neo4j at {count}/200K nodes -- CRITICAL")
        elif count > 150_000:
            warnings.append(f"Neo4j at {count}/200K nodes -- approaching limit")
    except Exception as exc:
        warnings.append(f"Could not check Neo4j: {exc}")

    # PostgreSQL case count
    try:
        import asyncpg
        from app.core.config import settings
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        total = await conn.fetchval("SELECT count(*) FROM cases")
        await conn.close()
        checks["pg_cases"] = total
    except Exception as exc:
        warnings.append(f"Could not check PostgreSQL: {exc}")

    passed = len(failures) == 0
    return QualityReport(passed=passed, checks=checks, failures=failures, warnings=warnings)
