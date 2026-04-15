"""
Full data reset script — wipes ALL data from PostgreSQL, Pinecone, Neo4j, and SQLite tracker.
Usage: cd backend && .venv/Scripts/python scripts/reset_all_data.py
"""

import asyncio
import os
import shutil
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import contextlib

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def reset_postgresql():
    """Truncate all tables in PostgreSQL."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

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
            with contextlib.suppress(Exception):
                await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

    await engine.dispose()


async def reset_pinecone():
    """Delete all vectors from Pinecone index."""
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index = pc.Index(host=os.environ["PINECONE_HOST"])

        stats = index.describe_index_stats()
        total_before = stats.get("total_vector_count", 0)

        if total_before > 0:
            index.delete(delete_all=True)

            namespaces = stats.get("namespaces", {})
            for ns in namespaces:
                if ns:
                    index.delete(delete_all=True, namespace=ns)

        stats = index.describe_index_stats()
    except Exception:
        pass


async def reset_neo4j():
    """Delete all nodes and relationships from Neo4j."""
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )

        async with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
            result = await session.run("MATCH (n) RETURN count(n) as count")
            record = await result.single()

            # Delete in batches
            deleted = True
            while deleted:
                result = await session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) as deleted"
                )
                record = await result.single()
                deleted = record["deleted"] > 0
                if deleted:
                    pass

            result = await session.run("MATCH (n) RETURN count(n) as count")
            record = await result.single()

        await driver.close()
    except Exception:
        pass


def reset_sqlite_tracker():
    """Delete the SQLite ingestion tracker database."""
    tracker_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "ingest_tracker.db"))
    if os.path.exists(tracker_path):
        os.remove(tracker_path)
    else:
        pass


def reset_local_pdfs():
    """Delete locally stored PDFs."""
    pdf_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "pdfs"))
    if os.path.exists(pdf_path):
        sum(1 for _ in os.scandir(pdf_path) if _.is_file() or _.is_dir())
        shutil.rmtree(pdf_path)
        os.makedirs(pdf_path, exist_ok=True)
    else:
        pass


async def main():

    await reset_postgresql()
    await reset_pinecone()
    await reset_neo4j()
    reset_sqlite_tracker()
    reset_local_pdfs()



if __name__ == "__main__":
    asyncio.run(main())
