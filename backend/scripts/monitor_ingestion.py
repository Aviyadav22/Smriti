"""Monitor ingestion progress and health across all stores.

Run alongside ingest_s3.py to track progress:
    python scripts/monitor_ingestion.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.config import settings
from app.db.postgres import async_session_factory, engine


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


    while True:
        iteration += 1
        now = time.time()
        elapsed = now - prev_time

        try:
            status = await check_all()
        except Exception:
            await asyncio.sleep(300)
            continue

        pg = status.get("pg", {})
        pc = status.get("pinecone", {})
        neo = status.get("neo4j", {})

        total = pg.get("total", 0)
        rate = (total - prev_total) / (elapsed / 60) if elapsed > 0 and prev_total > 0 else 0


        if "error" in pg:
            pass
        else:
            if rate > 0:
                remaining = 6000 - total
                remaining / rate if rate > 0 else float("inf")

        if "error" in pc:
            pass
        else:
            if pc.get("fullness", 0) > 0.8:
                pass

        if "error" in neo:
            pass
        else:
            pass

        prev_total = total
        prev_time = now

        # Stop if target reached
        if total >= 6000:
            break

        await asyncio.sleep(300)  # 5 minutes

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(monitor_loop())
