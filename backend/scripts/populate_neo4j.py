#!/usr/bin/env python3
"""Populate Neo4j citation graph from PostgreSQL case data.

Reads all cases from PostgreSQL and creates:
  - Case nodes with properties (id, title, citation, court, year, etc.)
  - CITES edges between cases based on cases_cited arrays
  - Act nodes and INTERPRETS edges from acts_cited arrays
  - Judge nodes with DECIDED_BY and AUTHORED_BY edges

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


def _extract_act_name(act_string: str) -> str | None:
    """Extract act name from citation like 'Section 302 of Indian Penal Code, 1860'.

    Handles formats:
    - "Section X of Act Name, Year"
    - "Act Name, Year"
    - "Order X Rule Y of Act Name"
    """
    if not act_string or not act_string.strip():
        return None

    name = act_string.strip()

    # Remove "Section X of " prefix
    name = re.sub(r'^Section\s+\S+\s+of\s+', '', name, flags=re.IGNORECASE).strip()
    # Remove "Order X Rule Y of " prefix
    name = re.sub(r'^Order\s+\S+\s+Rule\s+\S+\s+of\s+', '', name, flags=re.IGNORECASE).strip()
    # Remove "Article X of " prefix
    name = re.sub(r'^Article\s+\S+\s+of\s+', '', name, flags=re.IGNORECASE).strip()

    return name if name else None


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
        try:
            await session.run(
                "CREATE CONSTRAINT judge_name_unique IF NOT EXISTS "
                "FOR (j:Judge) REQUIRE j.name IS UNIQUE"
            )
        except Exception:
            pass
        try:
            await session.run(
                "CREATE CONSTRAINT act_name_unique IF NOT EXISTS "
                "FOR (a:Act) REQUIRE a.name IS UNIQUE"
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
    """Create CITES edges between cases with treatment property.

    Returns (created, unresolved).
    """
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
            "MERGE (a)-[r:CITES]->(b) "
            "SET r.treatment = COALESCE(r.treatment, 'referred_to')",
            edges=edges,
        )
    return len(edges), unresolved


async def batch_create_act_nodes(
    driver, database: str, cases: list[dict], dry_run: bool = False
) -> tuple[int, int]:
    """Create Act nodes and INTERPRETS edges.

    Returns (unique_act_count, edge_count).
    """
    act_edges: list[dict[str, str]] = []
    unique_acts: set[str] = set()

    for case in cases:
        acts = case.get("acts_cited") or []
        source_id = str(case["id"])
        for act_str in acts:
            if not act_str or not isinstance(act_str, str):
                continue
            act_name = _extract_act_name(act_str)
            if act_name:
                unique_acts.add(act_name)
                act_edges.append({"case_id": source_id, "act_name": act_name})

    if dry_run or not unique_acts:
        return len(unique_acts), len(act_edges)

    # Create Act nodes
    async with driver.session(database=database) as session:
        await session.run(
            "UNWIND $acts AS name MERGE (a:Act {name: name})",
            acts=list(unique_acts),
        )

    # Create INTERPRETS edges
    if act_edges:
        async with driver.session(database=database) as session:
            await session.run(
                "UNWIND $edges AS e "
                "MATCH (c:Case {id: e.case_id}), (a:Act {name: e.act_name}) "
                "MERGE (c)-[:INTERPRETS]->(a)",
                edges=act_edges,
            )

    return len(unique_acts), len(act_edges)


async def batch_create_judge_nodes(
    driver, database: str, cases: list[dict], dry_run: bool = False
) -> tuple[int, int]:
    """Create Judge nodes and DECIDED_BY/AUTHORED_BY edges.

    Returns (unique_judge_count, decided_by_edge_count).
    """
    judge_edges: list[dict[str, str]] = []
    author_edges: list[dict[str, str]] = []
    unique_judges: set[str] = set()

    for case in cases:
        case_id = str(case["id"])
        judges = case.get("judge") or []
        author = case.get("author_judge")

        for judge_name in judges:
            if judge_name and judge_name.strip():
                name = judge_name.strip()
                unique_judges.add(name)
                judge_edges.append({"case_id": case_id, "judge_name": name})

        if author and author.strip():
            author_name = author.strip()
            unique_judges.add(author_name)
            author_edges.append({"case_id": case_id, "judge_name": author_name})

    if dry_run or not unique_judges:
        return len(unique_judges), len(judge_edges)

    # Create Judge nodes
    async with driver.session(database=database) as session:
        await session.run(
            "UNWIND $judges AS name MERGE (j:Judge {name: name})",
            judges=list(unique_judges),
        )

    # Create DECIDED_BY edges
    if judge_edges:
        async with driver.session(database=database) as session:
            await session.run(
                "UNWIND $edges AS e "
                "MATCH (c:Case {id: e.case_id}), (j:Judge {name: e.judge_name}) "
                "MERGE (c)-[:DECIDED_BY]->(j)",
                edges=judge_edges,
            )

    # Create AUTHORED_BY edges
    if author_edges:
        async with driver.session(database=database) as session:
            await session.run(
                "UNWIND $edges AS e "
                "MATCH (c:Case {id: e.case_id}), (j:Judge {name: e.judge_name}) "
                "MERGE (c)-[:AUTHORED_BY]->(j)",
                edges=author_edges,
            )

    return len(unique_judges), len(judge_edges)


async def update_cited_by_counts(driver, database: str) -> None:
    """Update cited_by_count on each node based on incoming CITES edges."""
    async with driver.session(database=database) as session:
        await session.run(
            "MATCH (c:Case) "
            "SET c.cited_by_count = size([(x)-[:CITES]->(c) | x])"
        )
    logger.info("Updated cited_by_count for all nodes")


async def sync_cited_by_counts_to_pg(
    driver, database: str, conn
) -> int:
    """Sync cited_by_count from Neo4j back to PostgreSQL.

    Returns the number of rows updated.
    """
    async with driver.session(database=database) as session:
        result = await session.run(
            "MATCH (c:Case) WHERE c.cited_by_count > 0 "
            "RETURN c.id AS id, c.cited_by_count AS count"
        )
        records = [record async for record in result]

    if not records:
        logger.info("No cited_by_count data to sync to PostgreSQL")
        return 0

    # Batch update PostgreSQL
    updated = 0
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        # Build VALUES list for batch update
        values = ", ".join(
            f"('{r['id']}', {r['count']})" for r in batch
        )
        await conn.execute(
            f"UPDATE cases SET cited_by_count = v.count "
            f"FROM (VALUES {values}) AS v(id, count) "
            f"WHERE cases.id::text = v.id"
        )
        updated += len(batch)

    logger.info("Synced cited_by_count to PostgreSQL for %d cases", updated)
    return updated


async def get_neo4j_stats(driver, database: str) -> dict:
    """Get current Neo4j statistics."""
    async with driver.session(database=database) as session:
        node_result = await session.run("MATCH (n:Case) RETURN count(n) AS cnt")
        node_record = await node_result.single()
        node_count = node_record["cnt"] if node_record else 0

        edge_result = await session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS cnt")
        edge_record = await edge_result.single()
        edge_count = edge_record["cnt"] if edge_record else 0

        judge_result = await session.run("MATCH (j:Judge) RETURN count(j) AS cnt")
        judge_record = await judge_result.single()
        judge_count = judge_record["cnt"] if judge_record else 0

        act_result = await session.run("MATCH (a:Act) RETURN count(a) AS cnt")
        act_record = await act_result.single()
        act_count = act_record["cnt"] if act_record else 0

        interprets_result = await session.run(
            "MATCH ()-[r:INTERPRETS]->() RETURN count(r) AS cnt"
        )
        interprets_record = await interprets_result.single()
        interprets_count = interprets_record["cnt"] if interprets_record else 0

        decided_by_result = await session.run(
            "MATCH ()-[r:DECIDED_BY]->() RETURN count(r) AS cnt"
        )
        decided_by_record = await decided_by_result.single()
        decided_by_count = decided_by_record["cnt"] if decided_by_record else 0

        authored_by_result = await session.run(
            "MATCH ()-[r:AUTHORED_BY]->() RETURN count(r) AS cnt"
        )
        authored_by_record = await authored_by_result.single()
        authored_by_count = authored_by_record["cnt"] if authored_by_record else 0

    return {
        "nodes": node_count,
        "edges": edge_count,
        "judges": judge_count,
        "acts": act_count,
        "interprets_edges": interprets_count,
        "decided_by_edges": decided_by_count,
        "authored_by_edges": authored_by_count,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def _get_neo4j_case_ids(driver, database: str) -> set[str]:
    """Return the set of Case node IDs currently in Neo4j."""
    async with driver.session(database=database) as session:
        result = await session.run("MATCH (c:Case) WHERE c.id IS NOT NULL RETURN c.id AS cid")
        records = [record async for record in result]
    return {str(r["cid"]) for r in records}


async def populate(
    batch_size: int = 200, dry_run: bool = False, incremental: bool = False,
) -> None:
    """Main population pipeline.

    Args:
        batch_size: Number of cases per batch.
        dry_run: Preview without writing.
        incremental: Only process cases not already in Neo4j (skip clear).
    """
    dsn = get_pg_dsn()
    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    conn = await asyncpg.connect(dsn, statement_cache_size=0)

    try:
        # Test Neo4j connection
        logger.info("Testing Neo4j connection...")
        stats = await get_neo4j_stats(driver, database)
        logger.info(
            "Neo4j connected. Current: %d Case nodes, %d CITES edges, "
            "%d Judge nodes, %d Act nodes",
            stats["nodes"], stats["edges"], stats["judges"], stats["acts"],
        )

        # In incremental mode, collect existing IDs and skip clearing
        existing_ids: set[str] = set()
        if incremental:
            existing_ids = await _get_neo4j_case_ids(driver, database)
            logger.info(
                "Incremental mode: %d cases already in Neo4j, will skip them",
                len(existing_ids),
            )
        elif stats["nodes"] > 0 and not dry_run:
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
        total_acts = 0
        total_act_edges = 0
        total_judges = 0
        total_judge_edges = 0
        start_time = time.time()

        for offset in range(0, total_cases, batch_size):
            batch_start = time.time()
            cases = await fetch_cases(conn, offset, batch_size)

            if not cases:
                break

            # In incremental mode, filter out cases already in Neo4j
            if incremental and existing_ids:
                cases = [c for c in cases if str(c["id"]) not in existing_ids]
                if not cases:
                    continue

            # Create nodes
            created = await batch_create_nodes(driver, database, cases, dry_run=dry_run)
            total_nodes += created

            # Create CITES edges
            edges_created, unresolved = await batch_create_edges(
                driver, database, cases, citation_map, title_map, dry_run=dry_run
            )
            total_edges += edges_created
            total_unresolved += unresolved

            # Create Act nodes and INTERPRETS edges
            act_count, act_edge_count = await batch_create_act_nodes(
                driver, database, cases, dry_run=dry_run
            )
            total_acts += act_count
            total_act_edges += act_edge_count

            # Create Judge nodes and DECIDED_BY/AUTHORED_BY edges
            judge_count, judge_edge_count = await batch_create_judge_nodes(
                driver, database, cases, dry_run=dry_run
            )
            total_judges += judge_count
            total_judge_edges += judge_edge_count

            elapsed = time.time() - batch_start
            progress = min(offset + batch_size, total_cases)
            logger.info(
                "Batch %d-%d/%d: %d nodes, %d edges (%d unresolved), "
                "%d acts, %d judges [%.1fs]",
                offset + 1, progress, total_cases,
                created, edges_created, unresolved,
                act_count, judge_count, elapsed,
            )

        # Update cited_by_count on Neo4j nodes, then sync back to PostgreSQL
        if not dry_run and total_edges > 0:
            logger.info("Updating cited_by_count on all nodes...")
            await update_cited_by_counts(driver, database)
            logger.info("Syncing cited_by_count to PostgreSQL...")
            await sync_cited_by_counts_to_pg(driver, database, conn)

        total_time = time.time() - start_time
        prefix = "[DRY RUN] " if dry_run else ""
        logger.info(
            "%sPopulation complete: %d Case nodes, %d CITES edges "
            "(%d unresolved), %d Act nodes (%d INTERPRETS edges), "
            "%d Judge nodes (%d DECIDED_BY edges) in %.1fs",
            prefix, total_nodes, total_edges, total_unresolved,
            total_acts, total_act_edges,
            total_judges, total_judge_edges, total_time,
        )

        if not dry_run:
            stats = await get_neo4j_stats(driver, database)
            logger.info(
                "Final Neo4j stats: %d Case nodes, %d CITES edges, "
                "%d Judge nodes, %d Act nodes, "
                "%d INTERPRETS, %d DECIDED_BY, %d AUTHORED_BY",
                stats["nodes"], stats["edges"],
                stats["judges"], stats["acts"],
                stats["interprets_edges"], stats["decided_by_edges"],
                stats["authored_by_edges"],
            )

    finally:
        await conn.close()
        await driver.close()


async def show_stats() -> None:
    """Show current Neo4j statistics."""
    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    try:
        stats = await get_neo4j_stats(driver, database)
        logger.info(
            "Neo4j: %d Case nodes, %d CITES edges, "
            "%d Judge nodes, %d Act nodes, "
            "%d INTERPRETS, %d DECIDED_BY, %d AUTHORED_BY",
            stats["nodes"], stats["edges"],
            stats["judges"], stats["acts"],
            stats["interprets_edges"], stats["decided_by_edges"],
            stats["authored_by_edges"],
        )
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
    parser.add_argument(
        "--incremental", action="store_true",
        help="Only process cases not already in Neo4j (skip graph clearing)",
    )

    args = parser.parse_args()

    if args.stats:
        asyncio.run(show_stats())
    else:
        asyncio.run(populate(
            batch_size=args.batch,
            dry_run=args.dry_run,
            incremental=args.incremental,
        ))


if __name__ == "__main__":
    main()
