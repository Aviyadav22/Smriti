"""Monitor ingestion progress and health across all stores.

Run alongside ingest_s3.py to track progress:
    python scripts/monitor_ingestion.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.db.postgres import async_session_factory, engine  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def check_all() -> dict:
    """Check all stores and return status dict."""
    status = {}

    # PostgreSQL
    try:
        async with async_session_factory() as s:
            total = (await s.execute(text("SELECT count(*) FROM cases"))).scalar()
            complete = (await s.execute(
                text("SELECT count(*) FROM cases WHERE ingestion_status = 'complete'")
            )).scalar()
            needs_review = (await s.execute(
                text("SELECT count(*) FROM cases WHERE ingestion_status = 'needs_review'")
            )).scalar()
            failed = (await s.execute(
                text("SELECT count(*) FROM cases WHERE ingestion_status = 'failed'")
            )).scalar()
            no_fts = (await s.execute(
                text("SELECT count(*) FROM cases WHERE searchable_text IS NULL")
            )).scalar()
            null_type = (await s.execute(
                text("SELECT count(*) FROM cases WHERE case_type IS NULL")
            )).scalar()
            null_court = (await s.execute(
                text("SELECT count(*) FROM cases WHERE court IS NULL")
            )).scalar()
            statutes = (await s.execute(text("SELECT count(*) FROM statutes"))).scalar()
        status["pg"] = {
            "total": total, "complete": complete, "needs_review": needs_review,
            "failed": failed, "no_fts": no_fts, "null_type": null_type,
            "null_court": null_court, "statutes": statutes,
        }
    except Exception as e:
        status["pg"] = {"error": str(e)}

    # Pinecone
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        idx = pc.Index(host=settings.pinecone_host)
        stats = idx.describe_index_stats()
        status["pinecone"] = {
            "total_vectors": stats.total_vector_count,
            "fullness": stats.index_fullness,
        }
    except Exception as e:
        status["pinecone"] = {"error": str(e)}

    # Neo4j
    try:
        from app.core.providers.graph.neo4j_store import Neo4jGraph
        g = Neo4jGraph()
        cases = (await g.query("MATCH (c:Case) RETURN count(c) as cnt"))[0]["cnt"]
        rels = (await g.query("MATCH ()-[r]->() RETURN count(r) as cnt"))[0]["cnt"]
        await g.close()
        status["neo4j"] = {"case_nodes": cases, "relationships": rels}
    except Exception as e:
        status["neo4j"] = {"error": str(e)}

    return status


async def monitor_loop():
    """Run monitoring loop every 5 minutes."""
    prev_total = 0
    prev_time = time.time()
    iteration = 0

    print("=" * 70)
    print("  INGESTION MONITOR — checking every 5 minutes")
    print("=" * 70)

    while True:
        iteration += 1
        now = time.time()
        elapsed = now - prev_time

        try:
            status = await check_all()
        except Exception as e:
            print(f"\n[{time.strftime('%H:%M:%S')}] Monitor error: {e}")
            await asyncio.sleep(300)
            continue

        pg = status.get("pg", {})
        pc = status.get("pinecone", {})
        neo = status.get("neo4j", {})

        total = pg.get("total", 0)
        rate = (total - prev_total) / (elapsed / 60) if elapsed > 0 and prev_total > 0 else 0

        print(f"\n[{time.strftime('%H:%M:%S')}] === Check #{iteration} ===")

        if "error" in pg:
            print(f"  PG ERROR: {pg['error']}")
        else:
            print(f"  PG: {total} cases (complete={pg['complete']}, "
                  f"review={pg['needs_review']}, failed={pg['failed']})")
            print(f"      null_type={pg['null_type']}, null_court={pg['null_court']}, "
                  f"no_fts={pg['no_fts']}")
            if rate > 0:
                remaining = 6000 - total
                eta_min = remaining / rate if rate > 0 else float("inf")
                print(f"      Rate: {rate:.1f} cases/min | "
                      f"ETA: {eta_min:.0f} min ({eta_min/60:.1f} hrs)")

        if "error" in pc:
            print(f"  PC ERROR: {pc['error']}")
        else:
            print(f"  Pinecone: {pc['total_vectors']} vectors, "
                  f"fullness={pc['fullness']}")
            if pc.get("fullness", 0) > 0.8:
                print("  ⚠ WARNING: Pinecone index >80% full!")

        if "error" in neo:
            print(f"  Neo4j ERROR: {neo['error']}")
        else:
            print(f"  Neo4j: {neo['case_nodes']} case nodes, "
                  f"{neo['relationships']} relationships")

        prev_total = total
        prev_time = now

        # Stop if target reached
        if total >= 6000:
            print(f"\n{'=' * 70}")
            print(f"  TARGET REACHED: {total} cases ingested!")
            print(f"{'=' * 70}")
            break

        await asyncio.sleep(300)  # 5 minutes

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(monitor_loop())
