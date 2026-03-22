"""Dynamic amendment map service with Redis caching.

Provides bidirectional old↔new section lookups, reading from the
``amendment_maps`` PostgreSQL table and caching in Redis.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import TypedDict

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.legal.constants import (
    CRPC_TO_BNSS_MAP,
    EVIDENCE_TO_BSA_MAP,
    IPC_TO_BNS_MAP,
)

logger = logging.getLogger(__name__)

CACHE_KEY = "amendment_maps:all"
CACHE_TTL = 3600  # 1 hour


class AmendmentEntry(TypedDict):
    old_act: str
    new_act: str
    old_section: str
    new_section: str
    effective_date: str | None
    notes: str | None


async def seed_amendment_maps(db: AsyncSession) -> int:
    """Seed amendment_maps table from hardcoded constants.

    Returns the number of rows inserted.  Skips rows that already exist.
    """
    maps = [
        ("IPC", "BNS", IPC_TO_BNS_MAP, date(2024, 7, 1)),
        ("CrPC", "BNSS", CRPC_TO_BNSS_MAP, date(2024, 7, 1)),
        ("IEA", "BSA", EVIDENCE_TO_BSA_MAP, date(2024, 7, 1)),
    ]
    count = 0
    for old_act, new_act, section_map, eff_date in maps:
        for old_sec, new_sec in section_map.items():
            # Upsert-style: only insert if not already present
            exists = await db.execute(
                text(
                    "SELECT 1 FROM amendment_maps "
                    "WHERE old_act = :oa AND new_act = :na AND old_section = :os AND new_section = :ns"
                ),
                {"oa": old_act, "na": new_act, "os": old_sec, "ns": new_sec},
            )
            if exists.scalar() is None:
                await db.execute(
                    text(
                        "INSERT INTO amendment_maps (old_act, new_act, old_section, new_section, effective_date) "
                        "VALUES (:oa, :na, :os, :ns, :ed)"
                    ),
                    {"oa": old_act, "na": new_act, "os": old_sec, "ns": new_sec, "ed": eff_date},
                )
                count += 1
    await db.commit()
    logger.info("Seeded %d amendment map rows", count)
    return count


async def _load_all(db: AsyncSession) -> list[AmendmentEntry]:
    """Load all amendment map entries from DB."""
    result = await db.execute(
        select(
            text("old_act"),
            text("new_act"),
            text("old_section"),
            text("new_section"),
            text("effective_date"),
            text("notes"),
        ).select_from(text("amendment_maps"))
    )
    entries: list[AmendmentEntry] = []
    for row in result:
        entries.append(
            AmendmentEntry(
                old_act=row[0],
                new_act=row[1],
                old_section=row[2],
                new_section=row[3],
                effective_date=str(row[4]) if row[4] else None,
                notes=row[5],
            )
        )
    return entries


async def get_amendment_maps(
    db: AsyncSession,
    redis=None,
) -> list[AmendmentEntry]:
    """Get all amendment map entries, using Redis cache if available."""
    if redis:
        try:
            cached = await redis.get(CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    entries = await _load_all(db)

    if redis:
        try:
            await redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(entries))
        except Exception:
            pass

    return entries


def build_lookup(
    entries: list[AmendmentEntry],
) -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str], list[str]]]:
    """Build bidirectional lookup dicts from amendment entries.

    Returns:
        (old_to_new, new_to_old) — each maps (act, section) → list of sections.
    """
    old_to_new: dict[tuple[str, str], list[str]] = {}
    new_to_old: dict[tuple[str, str], list[str]] = {}
    for e in entries:
        key_old = (e["old_act"], e["old_section"])
        key_new = (e["new_act"], e["new_section"])
        old_to_new.setdefault(key_old, []).append(e["new_section"])
        new_to_old.setdefault(key_new, []).append(e["old_section"])
    return old_to_new, new_to_old
