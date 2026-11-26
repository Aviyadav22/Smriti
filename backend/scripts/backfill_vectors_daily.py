#!/usr/bin/env python3
"""Embed every case that has no vectors yet, a slice per day.

Free OpenRouter models allow 1000 requests a day per account, shared with live
traffic (and with ContraRed when it uses the same key). Each day this embeds at
most --per-day cases, never dipping below --reserve requests left on the key,
then sleeps until the quota resets at midnight UTC. It exits once every case
has vectors. One case is usually one embedding request (100 chunks per batch).

Usage (inside the backend container, scripts mounted):
    python scripts/backfill_vectors_daily.py --per-day 600 --reserve 300 --rpm-limit 15
    python scripts/backfill_vectors_daily.py --once --per-day 20      # one slice, then exit
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncpg  # noqa: E402
import httpx  # noqa: E402

from backfill_missing_vectors import main as backfill  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_daily")


async def missing_case_ids(limit: int) -> list[str]:
    from app.core.config import settings

    conn = await asyncpg.connect(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        rows = await conn.fetch(
            "SELECT c.id::text FROM cases c "
            "WHERE NOT EXISTS (SELECT 1 FROM case_vectors v WHERE v.case_id = c.id) "
            "ORDER BY c.year DESC NULLS LAST, c.id LIMIT $1",
            limit,
        )
        return [r[0] for r in rows]
    finally:
        await conn.close()


async def requests_left() -> int | None:
    """Free-model requests left today on the key, or None if unknown."""
    from app.core.config import settings

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url}/key",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
            resp.raise_for_status()
            return resp.json()["data"]["free_model_daily_requests"]["remaining"]
    except Exception as exc:  # the key endpoint is a nicety, not a requirement
        logger.warning("Could not read the daily quota: %s", exc)
        return None


def seconds_until_reset() -> float:
    now = dt.datetime.now(dt.timezone.utc)
    tomorrow = (now + dt.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return (tomorrow - now).total_seconds()


async def run(per_day: int, reserve: int, rpm_limit: int, once: bool) -> None:
    while True:
        left = await requests_left()
        budget = per_day if left is None else min(per_day, left - reserve)
        if budget > 0:
            ids = await missing_case_ids(budget)
            if not ids:
                logger.info("Every case has vectors. Done.")
                return
            logger.info("Embedding %d cases today (%s requests left on the key)", len(ids), left)
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(ids, f)
            await backfill(f.name, concurrency=1, rpm_limit=rpm_limit)
            Path(f.name).unlink(missing_ok=True)
        else:
            logger.info("Only %s requests left today (reserve %d); waiting for the reset", left, reserve)
        if once:
            return
        if not await missing_case_ids(1):
            logger.info("Every case has vectors. Done.")
            return
        wait = seconds_until_reset()
        logger.info("Sleeping %.1f hours until the daily quota resets", wait / 3600)
        await asyncio.sleep(wait)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--per-day", type=int, default=600, help="Max cases to embed per UTC day")
    parser.add_argument("--reserve", type=int, default=300, help="Requests to leave for live traffic")
    parser.add_argument("--rpm-limit", type=int, default=15, help="Embedding requests per minute")
    parser.add_argument("--once", action="store_true", help="Run one slice and exit")
    args = parser.parse_args()
    asyncio.run(run(args.per_day, args.reserve, args.rpm_limit, args.once))
