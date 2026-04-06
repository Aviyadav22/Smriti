"""Turbo Ingestion Orchestrator — 4-account parallel ingestion for 35K cases.

Manages the full lifecycle:
  --setup          Validate accounts, test credentials, check DB capacity
  --trial          Run 50-case trial on one account (Layer 1 quality check)
  --extract-all    Phase 1 only: extract all 35K cases (no API cost)
  --run            Full progressive rollout across all 4 accounts
  --resume         Resume from last checkpoint
  --status         Show progress across all workers
  --quality-check  Run post-batch quality checks
  --retry-failed   Retry failed cases from previous runs

See TURBO_INGESTION_DESIGN.md for full architecture and execution playbook.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure backend is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

INGESTION_DIR = Path(__file__).resolve().parent
ACCOUNTS_DIR = INGESTION_DIR / "accounts"
LOGS_DIR = INGESTION_DIR / "logs"
RUNS_DIR = INGESTION_DIR / "runs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [orchestrator] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(str(LOGS_DIR / "orchestrator.log"), mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("turbo_orchestrator")

# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------

ACCOUNTS = ["a", "b", "c", "d"]

# Progressive rollout steps
ROLLOUT_STEPS = {
    "trial": 50,
    "small": 500,
    "medium": 2000,
    "full": None,  # Remaining cases
}


def _get_account_env(account: str) -> dict[str, str]:
    """Load environment variables for a specific account."""
    env_file = ACCOUNTS_DIR / f"env_{account}"
    if not env_file.exists():
        raise FileNotFoundError(f"Account env file not found: {env_file}")

    env = {**os.environ}
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()

    # Resolve credential path to absolute
    creds = env.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds and not Path(creds).is_absolute():
        env["GOOGLE_APPLICATION_CREDENTIALS"] = str(INGESTION_DIR / creds)

    env["WORKER_ID"] = account
    return env


def _get_account_creds_path(account: str) -> Path:
    return ACCOUNTS_DIR / f"account_{account}.json"


# ---------------------------------------------------------------------------
# Setup & Validation
# ---------------------------------------------------------------------------


async def cmd_setup() -> None:
    """Validate all accounts and infrastructure."""
    logger.info("=" * 60)
    logger.info("TURBO INGESTION SETUP VALIDATION")
    logger.info("=" * 60)

    # Check account files exist
    for acc in ACCOUNTS:
        creds = _get_account_creds_path(acc)
        env_file = ACCOUNTS_DIR / f"env_{acc}"
        creds_ok = creds.exists()
        env_ok = env_file.exists()
        status = "OK" if (creds_ok and env_ok) else "MISSING"
        logger.info(
            "Account %s: creds=%s env=%s [%s]",
            acc, "YES" if creds_ok else "NO", "YES" if env_ok else "NO", status,
        )

    # Test database connectivity
    logger.info("--- Database Connectivity ---")

    try:
        from app.db.postgres import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                __import__("sqlalchemy").text("SELECT count(*) FROM cases")
            )
            count = result.scalar()
            logger.info("PostgreSQL: OK (%d existing cases)", count)
    except Exception as exc:
        logger.error("PostgreSQL: FAILED — %s", exc)

    try:
        from app.core.dependencies import get_vector_store

        vs = get_vector_store()
        stats = await vs.describe_index_stats()
        total = stats.get("total_vector_count", 0)
        logger.info("Pinecone: OK (%d vectors, limit 1M)", total)
        if total > 900_000:
            logger.warning("Pinecone: APPROACHING LIMIT (%d/1M)", total)
    except Exception as exc:
        logger.error("Pinecone: FAILED — %s", exc)

    try:
        from app.core.dependencies import get_graph_store

        gs = get_graph_store()
        count = await gs.count_nodes()
        logger.info("Neo4j: OK (%d nodes, limit 200K)", count)
    except Exception as exc:
        logger.error("Neo4j: FAILED — %s", exc)

    # Test Vertex AI connectivity for each account
    logger.info("--- Vertex AI Account Tests ---")
    for acc in ACCOUNTS:
        try:
            env = _get_account_env(acc)
            creds_path = env.get("GOOGLE_APPLICATION_CREDENTIALS", "")
            project = env.get("GEMINI_VERTEXAI_PROJECT", "")
            if not creds_path or not Path(creds_path).exists():
                logger.warning("Account %s: No credentials file", acc)
                continue

            # Quick test: list models via Vertex AI
            # Use repr() for Windows path safety (backslash escaping)
            result = subprocess.run(
                [sys.executable, "-c",
                 f"import os; "
                 f"os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = {repr(creds_path)}; "
                 f"from google import genai; "
                 f"client = genai.Client(vertexai=True, project={repr(project)}, location='us-central1'); "
                 f"models = list(client.models.list()); "
                 f"print(f'OK - {{len(models)}} models available')"
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                logger.info("Account %s (%s): %s", acc, project, result.stdout.strip())
            else:
                logger.error("Account %s: FAILED — %s", acc, result.stderr[:200])
        except Exception as exc:
            logger.error("Account %s: FAILED — %s", acc, exc)

    logger.info("=" * 60)
    logger.info("Setup validation complete. Fix any FAILED items before proceeding.")


# ---------------------------------------------------------------------------
# Trial Run
# ---------------------------------------------------------------------------


async def cmd_trial(account: str, limit: int = 50) -> None:
    """Run a trial of N cases on a single account with full quality checks."""
    logger.info("=" * 60)
    logger.info("TRIAL RUN: %d cases on account %s", limit, account)
    logger.info("=" * 60)

    run_id = f"trial_{account}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    env = _get_account_env(account)
    log_file = LOGS_DIR / f"trial_{account}.log"

    # Run the batch pipeline for N cases
    cmd = [
        sys.executable, str(BACKEND_DIR / "scripts" / "batch_ingest_vertex.py"),
        "--all",
        "--limit", str(limit),
        "--rpm-limit", "30",
        "--concurrency", "2",
    ]

    logger.info("Launching trial: %s", " ".join(cmd))
    logger.info("Log file: %s", log_file)

    with open(log_file, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(BACKEND_DIR),
        )

    # Wait for completion
    logger.info("Trial running (PID %d). Waiting for completion...", proc.pid)
    proc.wait()

    if proc.returncode != 0:
        logger.error("Trial FAILED with exit code %d. Check %s", proc.returncode, log_file)
        return

    logger.info("Trial pipeline complete. Running quality checks...")

    # Run quality checks
    from quality_gates import post_batch_spot_check, check_capacity_limits

    # Get case IDs from the latest run
    batch_runs_dir = BACKEND_DIR / "data" / "batch_runs"
    latest_run = max(batch_runs_dir.iterdir(), key=lambda p: p.stat().st_mtime)
    progress_file = latest_run / "progress.json"

    if progress_file.exists():
        progress = json.loads(progress_file.read_text(encoding="utf-8"))
        completed = progress.get("completed", [])
        logger.info("Trial completed %d cases. Running spot check...", len(completed))

        report = await post_batch_spot_check(completed, sample_size=min(10, len(completed)))
        report.save(run_dir / "quality_report.json")

        if report.passed:
            logger.info("TRIAL PASSED. Quality report:")
        else:
            logger.error("TRIAL FAILED. Quality report:")

        for key, val in report.checks.items():
            if key != "case_results":
                logger.info("  %s: %s", key, val)
        for f in report.failures:
            logger.error("  FAILURE: %s", f)
        for w in report.warnings:
            logger.warning("  WARNING: %s", w)

        # Capacity check
        cap_report = await check_capacity_limits()
        cap_report.save(run_dir / "capacity_report.json")
        for key, val in cap_report.checks.items():
            logger.info("  %s: %s", key, val)
    else:
        logger.error("No progress file found. Trial may not have completed successfully.")


# ---------------------------------------------------------------------------
# Extract All (Phase 1 only)
# ---------------------------------------------------------------------------


async def cmd_extract_all(limit: int = 35000) -> None:
    """Run Phase 1 text extraction for all cases (no API cost)."""
    logger.info("=" * 60)
    logger.info("PHASE 1: Extracting all cases (limit=%d)", limit)
    logger.info("=" * 60)

    env = _get_account_env("a")  # Any account works — Phase 1 doesn't use Vertex AI
    log_file = LOGS_DIR / "extract_all.log"

    cmd = [
        sys.executable, str(BACKEND_DIR / "scripts" / "batch_ingest_vertex.py"),
        "--all",
        "--limit", str(limit),
        "--dry-run",  # Phase 1 only
    ]

    logger.info("Launching extraction: %s", " ".join(cmd))

    with open(log_file, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(BACKEND_DIR),
        )

    proc.wait()

    if proc.returncode == 0:
        logger.info("Phase 1 extraction complete. Check %s for details.", log_file)
    else:
        logger.error("Phase 1 FAILED (exit code %d). Check %s", proc.returncode, log_file)


# ---------------------------------------------------------------------------
# Full Run (Progressive Rollout)
# ---------------------------------------------------------------------------


def _split_years_for_accounts(accounts: list[str]) -> dict[str, str]:
    """Split year ranges across accounts balanced by estimated case count.

    S3 dataset case counts vary wildly by year:
      1950-1970: ~200-400/year
      1971-2000: ~300-700/year
      2001-2018: ~500-800/year
      2019-2025: ~700-1100/year

    We split so each account gets roughly equal total cases, not equal year spans.
    """
    # Approximate case counts per year range (from S3 parquet metadata)
    year_counts: list[tuple[int, int]] = [
        # (year, approx_case_count)
        *[(y, 300) for y in range(1950, 1970)],   # ~6K total
        *[(y, 500) for y in range(1970, 1990)],   # ~10K total
        *[(y, 600) for y in range(1990, 2010)],   # ~12K total
        *[(y, 900) for y in range(2010, 2026)],   # ~14.4K total
    ]
    total_cases = sum(c for _, c in year_counts)
    target_per_account = total_cases // len(accounts)

    assignment: dict[str, str] = {}
    acc_idx = 0
    chunk_start = year_counts[0][0]
    running_total = 0

    for year, count in year_counts:
        running_total += count
        if running_total >= target_per_account and acc_idx < len(accounts) - 1:
            assignment[accounts[acc_idx]] = f"{chunk_start}-{year}"
            acc_idx += 1
            chunk_start = year + 1
            running_total = 0

    # Last account gets the remainder
    assignment[accounts[acc_idx]] = f"{chunk_start}-{year_counts[-1][0]}"

    return assignment


async def cmd_run(step: str, accounts: list[str] | None = None) -> None:
    """Run progressive rollout step across all (or specified) accounts."""
    if accounts is None:
        accounts = ACCOUNTS

    limit = ROLLOUT_STEPS.get(step)
    if limit is None and step == "full":
        limit = 50000  # High enough to capture remaining
    elif limit is None:
        logger.error("Unknown step: %s. Use: trial, small, medium, full", step)
        return

    logger.info("=" * 60)
    logger.info("PROGRESSIVE ROLLOUT: step=%s, limit=%d, accounts=%s", step, limit, accounts)
    logger.info("=" * 60)

    # Pre-flight capacity check
    from quality_gates import check_capacity_limits

    cap_report = await check_capacity_limits()
    if not cap_report.passed:
        logger.error("CAPACITY CHECK FAILED. Cannot proceed:")
        for f in cap_report.failures:
            logger.error("  %s", f)
        return

    # Assign year ranges to accounts
    year_assignments = _split_years_for_accounts(accounts)
    for acc, year_range in year_assignments.items():
        logger.info("Account %s → years %s", acc, year_range)

    run_id = f"turbo_{step}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save run config
    config = {
        "run_id": run_id,
        "step": step,
        "limit_per_account": limit,
        "accounts": accounts,
        "year_assignments": year_assignments,
        "started_at": datetime.now().isoformat(),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Launch workers in parallel
    workers: dict[str, subprocess.Popen] = {}

    # Turbo performance settings via environment
    turbo_env_overrides = {
        "GEMINI_THINKING_BUDGET": "0",  # CRITICAL: disables thinking tokens (~6x cost savings)
        "EMBED_SUB_BATCH": "20",
        "EMBED_CONCURRENCY": "8",
        "EMBED_SLEEP": "0.3",
        "DATABASE_POOL_SIZE": "20",
        "PINECONE_UPSERT_BATCH": "300",
    }

    for acc in accounts:
        env = _get_account_env(acc)
        env.update(turbo_env_overrides)

        year_range = year_assignments[acc]
        start_year, end_year = year_range.split("-")
        log_file = LOGS_DIR / f"worker_{acc}.log"

        # Write a per-worker wrapper that processes only its assigned years
        # with a GLOBAL case counter that stops across all years when limit reached.
        worker_script = run_dir / f"worker_{acc}.py"
        worker_script.write_text(
            f"""import subprocess, sys, json
from pathlib import Path

GLOBAL_LIMIT = {limit}
global_count = 0

for yr in range({start_year}, {int(end_year) + 1}):
    remaining = GLOBAL_LIMIT - global_count
    if remaining <= 0:
        print(f"Global limit reached ({{global_count}}/{{GLOBAL_LIMIT}}). Stopping.", flush=True)
        break
    print(f"=== Year {{yr}} (global: {{global_count}}/{{GLOBAL_LIMIT}}, remaining: {{remaining}}) ===", flush=True)
    ret = subprocess.run([
        sys.executable, {repr(str(BACKEND_DIR / 'scripts' / 'batch_ingest_vertex.py'))},
        "--year", str(yr),
        "--limit", str(remaining),
        "--rpm-limit", "150",
        "--concurrency", "8",
    ], cwd={repr(str(BACKEND_DIR))})
    if ret.returncode != 0:
        print(f"Year {{yr}} failed (exit {{ret.returncode}})", flush=True)
    # Count completed cases from latest batch run progress
    batch_dir = Path({repr(str(BACKEND_DIR))}) / "data" / "batch_runs"
    if batch_dir.exists():
        for d in sorted(batch_dir.iterdir(), reverse=True):
            prog = d / "progress.json"
            if prog.exists() and str(yr) in d.name:
                try:
                    data = json.loads(prog.read_text())
                    new_completed = len(data.get("completed", []))
                    global_count += new_completed
                    print(f"  Year {{yr}}: {{new_completed}} cases completed (global: {{global_count}})", flush=True)
                except Exception:
                    pass
                break
""",
            encoding="utf-8",
        )

        cmd = [sys.executable, str(worker_script)]

        logger.info("Launching worker %s: years %s, limit %d", acc, year_range, limit)
        logger.info("  Command: %s", " ".join(cmd))
        logger.info("  Log: %s", log_file)

        with open(log_file, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
                cwd=str(BACKEND_DIR),
            )
        workers[acc] = proc
        logger.info("  Worker %s started (PID %d)", acc, proc.pid)

    # Save PIDs
    pids = {acc: proc.pid for acc, proc in workers.items()}
    (run_dir / "worker_pids.json").write_text(json.dumps(pids, indent=2), encoding="utf-8")

    # Monitor workers
    logger.info("All %d workers launched. Monitoring...", len(workers))
    completed: set[str] = set()

    while len(completed) < len(workers):
        await asyncio.sleep(30)  # Check every 30 seconds

        for acc, proc in workers.items():
            if acc in completed:
                continue
            ret = proc.poll()
            if ret is not None:
                completed.add(acc)
                status = "OK" if ret == 0 else f"FAILED (exit code {ret})"
                logger.info("Worker %s finished: %s", acc, status)

        # Log progress summary
        running = len(workers) - len(completed)
        if running > 0:
            logger.info(
                "Progress: %d/%d workers complete, %d still running",
                len(completed), len(workers), running,
            )

    # All workers done — run metadata cleanup (OCR repair + GAN discriminator)
    logger.info("=" * 60)
    logger.info("All workers complete. Running metadata cleanup...")
    try:
        cleanup_result = subprocess.run(
            [sys.executable, str(BACKEND_DIR / "scripts" / "cleanup_metadata.py"),
             "--since", datetime.now().strftime("%Y-%m-%d")],
            capture_output=True, text=True, cwd=str(BACKEND_DIR), timeout=300,
        )
        if cleanup_result.returncode == 0:
            logger.info("Metadata cleanup complete")
        else:
            logger.warning("Metadata cleanup had issues: %s", cleanup_result.stderr[:200])
    except Exception as exc:
        logger.warning("Metadata cleanup failed: %s", exc)

    # Run quality checks
    logger.info("=" * 60)
    logger.info("Running post-batch quality checks...")

    # Collect results from each worker
    total_success = 0
    total_failed = 0

    batch_runs_dir = BACKEND_DIR / "data" / "batch_runs"
    all_completed_ids: list[str] = []

    if batch_runs_dir.exists():
        for run_path in sorted(batch_runs_dir.iterdir(), reverse=True):
            progress_file = run_path / "progress.json"
            if progress_file.exists():
                try:
                    progress = json.loads(progress_file.read_text(encoding="utf-8"))
                    ids = progress.get("completed", [])
                    all_completed_ids.extend(ids)
                    statuses = progress.get("statuses", {})
                    success = sum(1 for s in statuses.values() if s == "success")
                    failed = sum(1 for s in statuses.values() if s != "success")
                    total_success += success
                    total_failed += failed
                except (json.JSONDecodeError, KeyError):
                    pass

    logger.info("Total: %d success, %d failed", total_success, total_failed)

    # Post-batch spot check
    if all_completed_ids:
        from quality_gates import post_batch_spot_check

        report = await post_batch_spot_check(all_completed_ids, sample_size=20)
        report.save(run_dir / "quality_report.json")

        if report.passed:
            logger.info("POST-BATCH QUALITY CHECK: PASSED")
        else:
            logger.error("POST-BATCH QUALITY CHECK: FAILED")
            for f in report.failures:
                logger.error("  %s", f)

    config["completed_at"] = datetime.now().isoformat()
    config["total_success"] = total_success
    config["total_failed"] = total_failed
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    logger.info("Run %s complete. Results in %s", run_id, run_dir)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


async def cmd_status() -> None:
    """Show current status across all workers and databases."""
    logger.info("=" * 60)
    logger.info("TURBO INGESTION STATUS")
    logger.info("=" * 60)

    # Check for running workers
    for acc in ACCOUNTS:
        log_file = LOGS_DIR / f"worker_{acc}.log"
        if log_file.exists():
            # Read last few lines for progress
            lines = log_file.read_text(encoding="utf-8").strip().split("\n")
            last_lines = lines[-5:] if len(lines) >= 5 else lines
            logger.info("Worker %s (last activity):", acc)
            for line in last_lines:
                logger.info("  %s", line.strip()[:120])
        else:
            logger.info("Worker %s: No log file found", acc)

    # Database counts
    try:
        from app.db.postgres import async_session_factory
        from sqlalchemy import text as sa_text

        async with async_session_factory() as session:
            result = await session.execute(sa_text("SELECT count(*) FROM cases"))
            logger.info("PostgreSQL cases: %d", result.scalar())
    except Exception as exc:
        logger.error("PostgreSQL: %s", exc)

    try:
        from app.core.dependencies import get_vector_store

        vs = get_vector_store()
        stats = await vs.describe_index_stats()
        logger.info("Pinecone vectors: %d / 1,000,000", stats.get("total_vector_count", 0))
    except Exception as exc:
        logger.error("Pinecone: %s", exc)

    try:
        from app.core.dependencies import get_graph_store

        gs = get_graph_store()
        count = await gs.count_nodes()
        logger.info("Neo4j nodes: %d / 200,000", count)
    except Exception as exc:
        logger.error("Neo4j: %s", exc)


# ---------------------------------------------------------------------------
# Quality Check
# ---------------------------------------------------------------------------


async def cmd_quality_check() -> None:
    """Run quality checks on all completed ingestion runs."""
    logger.info("=" * 60)
    logger.info("QUALITY CHECK")
    logger.info("=" * 60)

    from quality_gates import check_capacity_limits, post_batch_spot_check, validate_content_quality

    # Capacity check
    cap_report = await check_capacity_limits()
    for key, val in cap_report.checks.items():
        logger.info("  %s: %s", key, val)
    for w in cap_report.warnings:
        logger.warning("  %s", w)
    for f in cap_report.failures:
        logger.error("  %s", f)

    # Collect all completed case IDs
    batch_runs_dir = BACKEND_DIR / "data" / "batch_runs"
    all_completed: list[str] = []

    if batch_runs_dir.exists():
        for run_path in sorted(batch_runs_dir.iterdir()):
            progress_file = run_path / "progress.json"
            if progress_file.exists():
                try:
                    progress = json.loads(progress_file.read_text(encoding="utf-8"))
                    all_completed.extend(progress.get("completed", []))
                except (json.JSONDecodeError, KeyError):
                    pass

    if not all_completed:
        logger.info("No completed cases found to check.")
        return

    logger.info("Found %d completed cases. Running spot check on 20 random samples...", len(all_completed))
    report = await post_batch_spot_check(all_completed, sample_size=20)

    report_path = RUNS_DIR / f"quality_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report.save(report_path)

    if report.passed:
        logger.info("QUALITY CHECK: PASSED")
    else:
        logger.error("QUALITY CHECK: FAILED")

    for key, val in report.checks.items():
        if key != "case_results":
            logger.info("  %s: %s", key, val)
    for f in report.failures:
        logger.error("  FAILURE: %s", f)
    for w in report.warnings:
        logger.warning("  WARNING: %s", w)

    # Content quality check (audit-driven: header bloat, NULL rates, editorial headnotes)
    logger.info("")
    logger.info("Running content quality audit on completed metadata...")
    try:
        import asyncpg
        from app.core.config import settings
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        pg_conn = await asyncpg.connect(dsn)

        # Sample up to 500 cases for content quality analysis
        sample_ids = random.sample(all_completed, min(500, len(all_completed)))
        rows = await pg_conn.fetch(
            """SELECT id, title, case_description, outcome_summary,
                      ratio_decidendi, headnotes, extraction_confidence
               FROM cases WHERE id = ANY($1::uuid[])""",
            sample_ids,
        )
        await pg_conn.close()

        meta_for_audit = {
            str(row["id"]): {
                "title": row["title"],
                "case_description": row["case_description"],
                "outcome_summary": row["outcome_summary"],
                "ratio_decidendi": row["ratio_decidendi"],
                "headnotes": row["headnotes"],
                "extraction_confidence": row["extraction_confidence"],
            }
            for row in rows
        }

        content_report = validate_content_quality(meta_for_audit)
        content_path = RUNS_DIR / f"content_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        content_report.save(content_path)

        logger.info("CONTENT QUALITY AUDIT:")
        for key, val in content_report.checks.items():
            logger.info("  %s: %s", key, val)
        for f in content_report.failures:
            logger.error("  FAILURE: %s", f)
        for w in content_report.warnings:
            logger.warning("  WARNING: %s", w)

        if content_report.passed:
            logger.info("CONTENT QUALITY: PASSED")
        else:
            logger.error("CONTENT QUALITY: FAILED — review content_quality report")
    except Exception as exc:
        logger.warning("Content quality audit skipped: %s", exc)


# ---------------------------------------------------------------------------
# Retry Failed
# ---------------------------------------------------------------------------


async def cmd_retry_failed() -> None:
    """Collect and retry all failed cases from previous runs."""
    logger.info("Scanning for failed cases across all runs...")

    batch_runs_dir = BACKEND_DIR / "data" / "batch_runs"
    failed_cases: list[dict[str, Any]] = []

    if batch_runs_dir.exists():
        for run_path in sorted(batch_runs_dir.iterdir()):
            progress_file = run_path / "progress.json"
            if progress_file.exists():
                try:
                    progress = json.loads(progress_file.read_text(encoding="utf-8"))
                    statuses = progress.get("statuses", {})
                    for case_id, status in statuses.items():
                        if status != "success":
                            failed_cases.append({
                                "case_id": case_id,
                                "status": status,
                                "run": run_path.name,
                            })
                except (json.JSONDecodeError, KeyError):
                    pass

    if not failed_cases:
        logger.info("No failed cases found. All good!")
        return

    logger.info("Found %d failed cases across runs:", len(failed_cases))
    # Group by error type
    error_types: dict[str, int] = {}
    for fc in failed_cases:
        err = fc["status"].split(":")[0] if ":" in fc["status"] else fc["status"]
        error_types[err] = error_types.get(err, 0) + 1

    for err, count in sorted(error_types.items(), key=lambda x: -x[1]):
        logger.info("  %s: %d cases", err, count)

    # Save failed cases list
    failed_path = RUNS_DIR / f"failed_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    failed_path.write_text(json.dumps(failed_cases, indent=2), encoding="utf-8")
    logger.info("Failed cases saved to %s", failed_path)
    logger.info(
        "To retry, use --resume with the specific run_id, "
        "or manually re-ingest specific case IDs."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turbo Ingestion Orchestrator — 4-account parallel ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ingestion/turbo_ingest.py --setup
  python ingestion/turbo_ingest.py --trial --account a --limit 50
  python ingestion/turbo_ingest.py --extract-all
  python ingestion/turbo_ingest.py --run --step small
  python ingestion/turbo_ingest.py --run --step full
  python ingestion/turbo_ingest.py --status
  python ingestion/turbo_ingest.py --retry-failed
""",
    )
    parser.add_argument("--setup", action="store_true", help="Validate accounts and infrastructure")
    parser.add_argument("--trial", action="store_true", help="Run trial on one account")
    parser.add_argument("--extract-all", action="store_true", help="Phase 1: extract all cases (no API cost)")
    parser.add_argument("--run", action="store_true", help="Run progressive rollout")
    parser.add_argument("--status", action="store_true", help="Show current progress")
    parser.add_argument("--quality-check", action="store_true", help="Run quality checks")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed cases")

    parser.add_argument("--account", type=str, default="a", choices=ACCOUNTS, help="Account for trial (default: a)")
    parser.add_argument("--step", type=str, default="small", choices=list(ROLLOUT_STEPS.keys()), help="Rollout step")
    parser.add_argument("--limit", type=int, default=50, help="Case limit for trial (default: 50)")
    parser.add_argument(
        "--accounts", type=str, default=None,
        help="Comma-separated accounts to use (default: all). E.g., --accounts a,b",
    )

    args = parser.parse_args()

    # Parse accounts list
    active_accounts = None
    if args.accounts:
        active_accounts = [a.strip() for a in args.accounts.split(",")]

    if args.setup:
        asyncio.run(cmd_setup())
    elif args.trial:
        asyncio.run(cmd_trial(args.account, args.limit))
    elif args.extract_all:
        asyncio.run(cmd_extract_all(args.limit))
    elif args.run:
        asyncio.run(cmd_run(args.step, active_accounts))
    elif args.status:
        asyncio.run(cmd_status())
    elif args.quality_check:
        asyncio.run(cmd_quality_check())
    elif args.retry_failed:
        asyncio.run(cmd_retry_failed())
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception:
        logger.exception("Fatal error in orchestrator")
        sys.exit(1)
