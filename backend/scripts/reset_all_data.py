"""
Full data reset script — wipes ALL data from PostgreSQL, Pinecone, Neo4j, and SQLite tracker.
Usage: cd backend && .venv/Scripts/python scripts/reset_all_data.py
"""

import asyncio
import os
import sys
import shutil

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def reset_postgresql():
    """Truncate all tables in PostgreSQL."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    print("\n=== RESETTING POSTGRESQL ===")
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        # Truncate all tables with CASCADE
        tables = [
            "cases",          # cascades: case_sections, case_citation_equivalents, case_vectors, citations, graph_build_queue, audio_digests
            "users",          # cascades: chat_sessions (-> chat_messages), documents (-> document_analyses), agent_executions, consents, audit_logs
            "statutes",
            "dpdp_audit_log",
        ]
        for table in tables:
            try:
                await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                print(f"  + Truncated {table}")
            except Exception as e:
                print(f"  x Failed to truncate {table}: {e}")

    await engine.dispose()
    print("PostgreSQL reset complete.")


async def reset_pinecone():
    """Delete all vectors from Pinecone index."""
    print("\n=== RESETTING PINECONE ===")
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index(host=os.environ["PINECONE_HOST"])

        stats = index.describe_index_stats()
        total_before = stats.get("total_vector_count", 0)
        print(f"  Vectors before: {total_before}")

        if total_before > 0:
            index.delete(delete_all=True)
            print("  + Deleted all vectors from default namespace")

            namespaces = stats.get("namespaces", {})
            for ns in namespaces:
                if ns:
                    index.delete(delete_all=True, namespace=ns)
                    print(f"  + Deleted all vectors from namespace '{ns}'")

        stats = index.describe_index_stats()
        print(f"  Vectors after: {stats.get('total_vector_count', 0)}")
        print("Pinecone reset complete.")
    except Exception as e:
        print(f"  x Pinecone reset failed: {e}")


async def reset_neo4j():
    """Delete all nodes and relationships from Neo4j."""
    print("\n=== RESETTING NEO4J ===")
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )

        async with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
            result = await session.run("MATCH (n) RETURN count(n) as count")
            record = await result.single()
            print(f"  Nodes before: {record['count']}")

            # Delete in batches
            deleted = True
            while deleted:
                result = await session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) as deleted"
                )
                record = await result.single()
                deleted = record["deleted"] > 0
                if deleted:
                    print(f"  Deleted batch of {record['deleted']} nodes")

            result = await session.run("MATCH (n) RETURN count(n) as count")
            record = await result.single()
            print(f"  Nodes after: {record['count']}")

        await driver.close()
        print("Neo4j reset complete.")
    except Exception as e:
        print(f"  x Neo4j reset failed: {e}")


def reset_sqlite_tracker():
    """Delete the SQLite ingestion tracker database."""
    print("\n=== RESETTING SQLITE TRACKER ===")
    tracker_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "ingest_tracker.db"))
    if os.path.exists(tracker_path):
        os.remove(tracker_path)
        print(f"  + Deleted {tracker_path}")
    else:
        print(f"  - Not found (already clean)")
    print("SQLite tracker reset complete.")


def reset_local_pdfs():
    """Delete locally stored PDFs."""
    print("\n=== RESETTING LOCAL PDF STORAGE ===")
    pdf_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "pdfs"))
    if os.path.exists(pdf_path):
        count = sum(1 for _ in os.scandir(pdf_path) if _.is_file() or _.is_dir())
        shutil.rmtree(pdf_path)
        os.makedirs(pdf_path, exist_ok=True)
        print(f"  + Deleted {count} items from {pdf_path}")
    else:
        print(f"  - Not found")
    print("Local PDF storage reset complete.")


async def main():
    print("=" * 60)
    print("  SMRITI FULL DATA RESET")
    print("=" * 60)

    await reset_postgresql()
    await reset_pinecone()
    await reset_neo4j()
    reset_sqlite_tracker()
    reset_local_pdfs()

    print("\n" + "=" * 60)
    print("  ALL DATA STORES RESET COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
