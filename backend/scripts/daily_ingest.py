"""Automated daily ingestion wrapper for cron/scheduler use.

Runs incremental ingestion for the current year, then populates Neo4j graph.
Designed to be invoked by cron or Cloud Scheduler:

    # Cron example (daily at 2 AM):
    0 2 * * * cd /app && python scripts/daily_ingest.py >> /var/log/smriti/daily_ingest.log 2>&1

    # Cloud Run Job (via Cloud Scheduler):
    gcloud run jobs execute daily-ingest --region=asia-south1

Usage:
    python scripts/daily_ingest.py              # Current year, resume mode
    python scripts/daily_ingest.py --year 2024  # Specific year
    python scripts/daily_ingest.py --full        # All years (initial load)
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [daily_ingest]: %(message)s",
)
logger = logging.getLogger("daily_ingest")


def _run_ingest(args: argparse.Namespace) -> int:
    """Run the main ingestion script as a subprocess."""
    cmd = [sys.executable, str(Path(__file__).parent / "ingest_s3.py"), "--resume"]

    if args.full:
        # Full ingestion: no year filter
        pass
    elif args.year:
        cmd.extend(["--year", str(args.year)])
    else:
        # Default: current year for daily incremental
        cmd.extend(["--year", str(datetime.now().year)])

    if args.limit:
        cmd.extend(["--limit", str(args.limit)])

    logger.info("Starting ingestion: %s", " ".join(cmd))
    result = subprocess.run(cmd, timeout=args.timeout)
    logger.info("Ingestion exited with code %d", result.returncode)
    return result.returncode


def _run_neo4j_populate(args: argparse.Namespace) -> int:
    """Run incremental Neo4j graph population."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "populate_neo4j.py"),
        "--incremental",
    ]
    logger.info("Starting Neo4j population: %s", " ".join(cmd))
    result = subprocess.run(cmd, timeout=3600)
    logger.info("Neo4j population exited with code %d", result.returncode)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily automated ingestion")
    parser.add_argument("--year", type=int, help="Year to ingest (default: current)")
    parser.add_argument("--full", action="store_true", help="Full ingestion, all years")
    parser.add_argument("--limit", type=int, help="Max documents to process")
    parser.add_argument("--skip-graph", action="store_true", help="Skip Neo4j population step")
    parser.add_argument(
        "--timeout",
        type=int,
        default=14400,
        help="Timeout in seconds for ingestion (default: 4 hours)",
    )
    args = parser.parse_args()

    start = datetime.now()
    logger.info("=== Daily ingestion started at %s ===", start.isoformat())

    # Step 1: Run ingestion
    ingest_code = _run_ingest(args)
    if ingest_code != 0:
        logger.error("Ingestion failed with code %d", ingest_code)
        sys.exit(ingest_code)

    # Step 2: Populate Neo4j (incremental)
    if not args.skip_graph:
        graph_code = _run_neo4j_populate(args)
        if graph_code != 0:
            logger.warning("Neo4j population failed with code %d (non-fatal)", graph_code)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=== Daily ingestion completed in %.0fs ===", elapsed)


if __name__ == "__main__":
    main()
