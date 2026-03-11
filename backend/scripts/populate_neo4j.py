#!/usr/bin/env python3
"""Populate Neo4j citation graph from PostgreSQL case data.

Reads all cases from PostgreSQL and creates:
  - Case nodes with properties (id, title, citation, court, year, etc.)
  - CITES edges between cases based on cases_cited arrays

Usage:
    cd backend
    python scripts/populate_neo4j.py              # Full run
    python scripts/populate_neo4j.py --batch 500   # Custom batch size
    python scripts/populate_neo4j.py --dry-run     # Preview without writing
    python scripts/populate_neo4j.py --stats       # Show current Neo4j stats
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import asyncpg
from neo4j import AsyncGraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def get_pg_dsn() -> str:
    """Get PostgreSQL DSN, normalized for asyncpg."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set in .env")
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def get_neo4j_driver():
    """Create async Neo4j driver from env vars."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "smriti_dev")
    return AsyncGraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Citation normalization & matching
# ---------------------------------------------------------------------------

def _normalize_citation(s: str) -> str:
    """Normalize citation string for matching.

    Strips dots from reporter abbreviations (S.C.R. -> SCR),
    collapses whitespace, lowercases.
    """
    # Remove dots between single letters: S.C.R. -> SCR, A.I.R. -> AIR
    s = re.sub(r'(?<=[A-Za-z])\.(?=[A-Za-z])', '', s)
    # Remove trailing dot after abbreviation
    s = re.sub(r'(?<=[A-Z])\.(?=\s|$)', '', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def _extract_citation_patterns(cited_str: str) -> list[str]:
    """Extract matchable citation patterns from a cases_cited entry.

    Input like: 'Gudikanti v. Public Prosecutor [1978] 2 SCR 371 : (1978) 1 SCC 240'
    Returns normalized versions of: '[1978] 2 SCR 371', '(1978) 1 SCC 240'
    """
    patterns = []

    # Pattern 1: [year] volume REPORTER page  (e.g. [1978] 2 SCR 371)
    for m in re.finditer(r'\[(\d{4})\]\s+(\d+)\s+([A-Za-z.]+)\s+(\d+)', cited_str):
        patterns.append(_normalize_citation(m.group(0)))

    # Pattern 2: (year) volume REPORTER page  (e.g. (1978) 1 SCC 240)
    for m in re.finditer(r'\((\d{4})\)\s+(\d+)\s+([A-Za-z.]+)\s+(\d+)', cited_str):
        patterns.append(_normalize_citation(m.group(0)))

    # Pattern 3: (year) REPORTER OnLine COURT page  (e.g. (2023) SCC OnLine SC 951)
    for m in re.finditer(r'\((\d{4})\)\s+([A-Za-z.]+)\s+OnLine\s+([A-Za-z]+)\s+(\d+)', cited_str):
        patterns.append(_normalize_citation(m.group(0)))

    return patterns


def _resolve_citation(
    cited_str: str,
    citation_map: dict[str, str],
    title_map: dict[str, str],
) -> str | None:
    """Try to resolve a cases_cited entry to a case UUID."""
    # 1. Direct match (normalized)
    normalized = _normalize_citation(cited_str)
    if normalized in citation_map:
        return citation_map[normalized]

    lowered = cited_str.strip().lower()
    if lowered in citation_map:
        return citation_map[lowered]

    # 2. Extract embedded citation patterns and match each
    for pattern in _extract_citation_patterns(cited_str):
        if pattern in citation_map:
            return citation_map[pattern]

    # 3. Title-based fallback
    title_match = re.match(r'^(.+?)\s*[\[\(]\d{4}', cited_str)
    if title_match:
        title = title_match.group(1).strip().lower()
        if title in title_map:
            return title_map[title]

    return None


# ---------------------------------------------------------------------------
# PostgreSQL queries (using raw asyncpg)
# ---------------------------------------------------------------------------

async def fetch_cases(conn: asyncpg.Connection, offset: int, limit: int) -> list[dict]:
    """Fetch a batch of cases from PostgreSQL."""
    rows = await conn.fetch(
        "SELECT id, title, citation, case_id, court, year, "
        "  case_type, jurisdiction, bench_type, judge, author_judge, "
        "  decision_date, disposal_nature, cases_cited, acts_cited "
        "FROM cases "
        "ORDER BY id "
        "OFFSET $1 LIMIT $2",
        offset, limit,
    )
    return [dict(r) for r in rows]


async def get_case_count(conn: asyncpg.Connection) -> int:
    """Get total number of cases."""
    return await conn.fetchval("SELECT count(*) FROM cases")


async def build_citation_index(conn: asyncpg.Connection) -> tuple[dict[str, str], dict[str, str]]:
    """Build mappings from citation/title -> case UUID for edge resolution."""
    logger.info("Building citation lookup index from PostgreSQL...")
    citation_map: dict[str, str] = {}

    # Primary: citation column (e.g. "[2024] 9 S.C.R. 770")
    rows = await conn.fetch(
        "SELECT id, citation FROM cases WHERE citation IS NOT NULL"
    )
    for row in rows:
        cit = str(row["citation"]).strip()
        uid = str(row["id"])
        if cit:
            citation_map[cit.lower()] = uid
            citation_map[_normalize_citation(cit)] = uid

    # Secondary: case_id column
    rows = await conn.fetch(
        "SELECT id, case_id FROM cases WHERE case_id IS NOT NULL AND case_id != ''"
    )
    for row in rows:
        cid = str(row["case_id"]).strip()
        if cid:
            citation_map[cid.lower()] = str(row["id"])

    # Tertiary: citation equivalents table
    try:
        rows = await conn.fetch(
            "SELECT case_id, citation FROM case_citation_equivalents "
            "WHERE citation IS NOT NULL"
        )
        for row in rows:
            cit = str(row["citation"]).strip()
            if cit:
                uid = str(row["case_id"])
                citation_map[cit.lower()] = uid
                citation_map[_normalize_citation(cit)] = uid
    except Exception:
        logger.debug("case_citation_equivalents table not available")

    # Title index for fallback matching
    rows = await conn.fetch("SELECT id, title FROM cases WHERE title IS NOT NULL")
    title_map: dict[str, str] = {}
    for row in rows:
        title = str(row["title"]).strip().lower()
        if title:
            title_map[title] = str(row["id"])

    logger.info(
        "Citation index: %d citation entries, %d title entries",
        len(citation_map), len(title_map),
    )
    return citation_map, title_map


# ---------------------------------------------------------------------------
# Neo4j operations
# ---------------------------------------------------------------------------

async def clear_graph(driver, database: str) -> None:
    """Delete all nodes and relationships."""
    async with driver.session(database=database) as session:
        await session.run("MATCH (n) DETACH DELETE n")
    logger.info("Cleared all nodes and relationships from Neo4j")


async def create_constraints(driver, database: str) -> None:
    """Create uniqueness constraints and indexes."""
    async with driver.session(database=database) as session:
        try:
            await session.run(
                "CREATE CONSTRAINT case_id_unique IF NOT EXISTS "
                "FOR (c:Case) REQUIRE c.id IS UNIQUE"
            )
        except Exception:
            pass
        try:
            await session.run(
                "CREATE INDEX case_citation_idx IF NOT EXISTS "
                "FOR (c:Case) ON (c.citation)"
            )
        except Exception:
            pass
    logger.info("Created constraints and indexes")


async def batch_create_nodes(
    driver, database: str, cases: list[dict], dry_run: bool = False
) -> int:
    """Create Case nodes in Neo4j using UNWIND for batch efficiency."""
    if not cases:
        return 0

    nodes = []
    for case in cases:
        node = {
            "id": str(case["id"]),
            "title": case.get("title") or "",
            "citation": case.get("citation") or "",
            "court": case.get("court") or "",
            "year": case.get("year"),
            "case_type": case.get("case_type") or "",
            "jurisdiction": case.get("jurisdiction") or "",
            "bench_type": case.get("bench_type") or "",
            "author_judge": case.get("author_judge") or "",
            "disposal_nature": case.get("disposal_nature") or "",
            "cited_by_count": 0,
        }
        if case.get("decision_date"):
            node["decision_date"] = str(case["decision_date"])
        if case.get("judge"):
            node["judges"] = case["judge"]
        nodes.append(node)

    if dry_run:
        return len(nodes)

    async with driver.session(database=database) as session:
        await session.run(
            "UNWIND $nodes AS props "
            "MERGE (c:Case {id: props.id}) "
            "SET c += props",
            nodes=nodes,
        )
    return len(nodes)


async def batch_create_edges(
    driver,
    database: str,
    cases: list[dict],
    citation_map: dict[str, str],
    title_map: dict[str, str],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Create CITES edges between cases. Returns (created, unresolved)."""
    edges = []
    unresolved = 0
    seen_edges: set[tuple[str, str]] = set()

    for case in cases:
        source_id = str(case["id"])
        cited = case.get("cases_cited") or []

        for citation_str in cited:
            if not citation_str or not isinstance(citation_str, str):
                continue

            target_id = _resolve_citation(citation_str, citation_map, title_map)
            if target_id and target_id != source_id:
                edge_key = (source_id, target_id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({"from_id": source_id, "to_id": target_id})
            else:
                unresolved += 1

    if dry_run or not edges:
        return len(edges), unresolved

    async with driver.session(database=database) as session:
        await session.run(
            "UNWIND $edges AS e "
            "MATCH (a:Case {id: e.from_id}), (b:Case {id: e.to_id}) "
            "MERGE (a)-[:CITES]->(b)",
            edges=edges,
        )
    return len(edges), unresolved


async def update_cited_by_counts(driver, database: str) -> None:
    """Update cited_by_count on each node based on incoming CITES edges."""
    async with driver.session(database=database) as session:
        await session.run(
            "MATCH (c:Case) "
            "SET c.cited_by_count = size([(x)-[:CITES]->(c) | x])"
        )
    logger.info("Updated cited_by_count for all nodes")


async def get_neo4j_stats(driver, database: str) -> dict:
    """Get current Neo4j statistics."""
    async with driver.session(database=database) as session:
        node_result = await session.run("MATCH (n:Case) RETURN count(n) AS cnt")
        node_record = await node_result.single()
        node_count = node_record["cnt"] if node_record else 0

        edge_result = await session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS cnt")
        edge_record = await edge_result.single()
        edge_count = edge_record["cnt"] if edge_record else 0

    return {"nodes": node_count, "edges": edge_count}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def populate(batch_size: int = 200, dry_run: bool = False) -> None:
    """Main population pipeline."""
    dsn = get_pg_dsn()
    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)

    try:
        # Test Neo4j connection
        logger.info("Testing Neo4j connection...")
        stats = await get_neo4j_stats(driver, database)
        logger.info("Neo4j connected. Current: %d nodes, %d edges", stats["nodes"], stats["edges"])

        if stats["nodes"] > 0 and not dry_run:
            logger.warning(
                "Neo4j already has %d nodes. Clearing and repopulating...", stats["nodes"]
            )
            await clear_graph(driver, database)

        if not dry_run:
            await create_constraints(driver, database)

        total_cases = await get_case_count(conn)
        logger.info("Total cases in PostgreSQL: %d", total_cases)

        if total_cases == 0:
            logger.warning("No cases found in PostgreSQL. Nothing to populate.")
            return

        # Build citation index for edge resolution
        citation_map, title_map = await build_citation_index(conn)

        # Process in batches
        total_nodes = 0
        total_edges = 0
        total_unresolved = 0
        start_time = time.time()

        for offset in range(0, total_cases, batch_size):
            batch_start = time.time()
            cases = await fetch_cases(conn, offset, batch_size)

            if not cases:
                break

            # Create nodes
            created = await batch_create_nodes(driver, database, cases, dry_run=dry_run)
            total_nodes += created

            # Create edges
            edges_created, unresolved = await batch_create_edges(
                driver, database, cases, citation_map, title_map, dry_run=dry_run
            )
            total_edges += edges_created
            total_unresolved += unresolved

            elapsed = time.time() - batch_start
            progress = min(offset + batch_size, total_cases)
            logger.info(
                "Batch %d-%d/%d: %d nodes, %d edges (%d unresolved) [%.1fs]",
                offset + 1, progress, total_cases,
                created, edges_created, unresolved, elapsed,
            )

        # Update cited_by_count
        if not dry_run and total_edges > 0:
            logger.info("Updating cited_by_count on all nodes...")
            await update_cited_by_counts(driver, database)

        total_time = time.time() - start_time
        prefix = "[DRY RUN] " if dry_run else ""
        logger.info(
            "%sPopulation complete: %d nodes, %d edges "
            "(%d citations unresolved) in %.1fs",
            prefix, total_nodes, total_edges, total_unresolved, total_time,
        )

        if not dry_run:
            stats = await get_neo4j_stats(driver, database)
            logger.info("Final Neo4j stats: %d nodes, %d edges", stats["nodes"], stats["edges"])

    finally:
        await conn.close()
        await driver.close()


async def show_stats() -> None:
    """Show current Neo4j statistics."""
    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    try:
        stats = await get_neo4j_stats(driver, database)
        logger.info("Neo4j: %d Case nodes, %d CITES edges", stats["nodes"], stats["edges"])
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Populate Neo4j citation graph from PostgreSQL"
    )
    parser.add_argument(
        "--batch", type=int, default=200, help="Batch size (default: 200)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing to Neo4j"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show current Neo4j statistics"
    )

    args = parser.parse_args()

    if args.stats:
        asyncio.run(show_stats())
    else:
        asyncio.run(populate(batch_size=args.batch, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
