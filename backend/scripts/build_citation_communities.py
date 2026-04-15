"""Build citation graph communities using Louvain algorithm + LLM summarization.

Run after ingestion to pre-compute community summaries.
Stores results back in Neo4j as Community nodes + BELONGS_TO edges,
and embeds summaries into Pinecone for semantic retrieval.

Usage: python -m scripts.build_citation_communities
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import networkx as nx
from sqlalchemy import select

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import TYPE_CHECKING

from app.core.agents.nodes.worker_nodes import _detect_communities
from app.core.agents.state import CommunitySummary
from app.core.legal.prompts import COMMUNITY_SUMMARY_SCHEMA, COMMUNITY_SUMMARY_SYSTEM
from app.db.postgres import async_session_factory

if TYPE_CHECKING:
    from app.core.interfaces import EmbeddingProvider, GraphStore, LLMProvider, VectorStore

logger = logging.getLogger(__name__)


# --- Step 1: Export citation graph from Neo4j to NetworkX ---


async def export_citation_graph(graph_store: GraphStore) -> nx.DiGraph:
    """Export all Case nodes + CITES edges from Neo4j."""
    result = await graph_store.query(
        """
        MATCH (a:Case)-[r:CITES]->(b:Case)
        RETURN a.id AS source, b.id AS target, r.treatment AS treatment
        """,
    )
    G = nx.DiGraph()
    for record in result:
        G.add_edge(
            str(record["source"]),
            str(record["target"]),
            treatment=record.get("treatment"),
        )
    logger.info("Exported citation graph: %d nodes, %d edges", len(G.nodes), len(G.edges))
    return G


# --- Step 2: Run Leiden community detection ---
# _detect_communities is imported from worker_nodes (shared implementation)


# --- Step 3: Generate community summaries via LLM ---


async def summarize_community(
    community_id: str,
    case_ids: list[str],
    db,
    flash_llm: LLMProvider,
) -> CommunitySummary:
    """Generate a summary for a citation community.

    Loads case metadata (title, citation, court, year, ratio) for top cases,
    asks Flash to identify the common legal theme + key principles.
    """
    from app.models.case import Case

    # Load case metadata for community members (top 20 by citation count)
    result = await db.execute(select(Case).where(Case.id.in_(case_ids[:20])))
    case_data = [
        f"- {c.title} ({c.citation}, {c.court}, {c.year})\n  Ratio: {(c.ratio_decidendi or '')[:300]}"
        for c in result.scalars()
    ]

    if not case_data:
        return CommunitySummary(
            community_id=community_id,
            title=f"Community {community_id}",
            summary="No case data available for summarization.",
            key_cases=case_ids[:5],
            legal_principles=[],
            size=len(case_ids),
        )

    summary_response = await flash_llm.generate_structured(
        f"Community of {len(case_ids)} cases. Top cases:\n" + "\n".join(case_data),
        system=COMMUNITY_SUMMARY_SYSTEM,
        output_schema=COMMUNITY_SUMMARY_SCHEMA,
    )

    return CommunitySummary(
        community_id=community_id,
        title=summary_response.get("title", f"Community {community_id}"),
        summary=summary_response.get("summary", ""),
        key_cases=case_ids[:5],
        legal_principles=summary_response.get("legal_principles", []),
        size=len(case_ids),
    )


# --- Step 4: Store communities in Neo4j ---


async def store_communities(
    communities: dict[str, CommunitySummary],
    case_communities: dict[str, str],
    graph_store: GraphStore,
) -> None:
    """Create Community nodes + BELONGS_TO edges in Neo4j."""
    for comm_id, summary in communities.items():
        await graph_store.query(
            """
            MERGE (c:Community {id: $comm_id})
            SET c.title = $title,
                c.summary = $summary,
                c.legal_principles = $principles,
                c.size = $size,
                c.updated_at = datetime()
            """,
            params={
                "comm_id": comm_id,
                "title": summary["title"],
                "summary": summary["summary"],
                "principles": summary["legal_principles"],
                "size": summary["size"],
            },
        )

    for case_id, comm_id in case_communities.items():
        await graph_store.query(
            """
            MATCH (case:Case {id: $case_id}), (comm:Community {id: $comm_id})
            MERGE (case)-[:BELONGS_TO]->(comm)
            """,
            params={"case_id": case_id, "comm_id": comm_id},
        )

    logger.info(
        "Stored %d communities, %d BELONGS_TO edges",
        len(communities),
        len(case_communities),
    )


# --- Step 5: Embed community summaries for semantic retrieval ---


async def embed_community_summaries(
    communities: dict[str, CommunitySummary],
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
) -> None:
    """Embed community summaries into Pinecone for semantic retrieval.

    Uses document_type: "community" metadata filter.
    """
    texts = [f"{s['title']}\n{s['summary']}" for s in communities.values()]
    if not texts:
        return

    embeddings = await embedder.embed_batch(texts)
    vectors = [
        {
            "id": f"community:{comm_id}",
            "values": emb,
            "metadata": {
                "document_type": "community",
                "vector_type": "community",
                "community_id": comm_id,
                "title": summary["title"],
                "text": summary["summary"][:2000],
                "size": summary["size"],
                "legal_principles": "; ".join(summary["legal_principles"]),
            },
        }
        for (comm_id, summary), emb in zip(communities.items(), embeddings, strict=False)
    ]
    await vector_store.upsert(vectors)
    logger.info("Embedded %d community summaries into Pinecone", len(vectors))


# --- Main orchestration ---


async def build_communities(
    graph_store: GraphStore,
    flash_llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    resolution: float = 1.0,
) -> None:
    """Full pipeline: export → detect → summarize → store → embed."""
    # Step 1: Export
    G = await export_citation_graph(graph_store)
    if len(G.nodes) == 0:
        logger.warning("No citation graph found — skipping community detection")
        return

    # Step 2: Detect communities
    undirected = G.to_undirected()
    node_to_community = _detect_communities(undirected, resolution=resolution)
    logger.info("Detected communities for %d nodes", len(node_to_community))

    # Group cases by community
    community_cases: dict[str, list[str]] = {}
    for case_id, comm_id in node_to_community.items():
        comm_key = str(comm_id)
        community_cases.setdefault(comm_key, []).append(case_id)

    # Filter out tiny communities (< 3 cases)
    community_cases = {k: v for k, v in community_cases.items() if len(v) >= 3}
    logger.info("Communities with 3+ cases: %d", len(community_cases))

    # Step 3: Summarize each community
    summaries: dict[str, CommunitySummary] = {}
    async with async_session_factory() as db:
        for comm_id, case_ids in community_cases.items():
            try:
                summary = await summarize_community(comm_id, case_ids, db, flash_llm)
                summaries[comm_id] = summary
            except Exception as exc:
                logger.warning("Failed to summarize community %s: %s", comm_id, exc)

    logger.info("Generated %d community summaries", len(summaries))

    # Step 4: Store in Neo4j
    case_to_community = {
        case_id: comm_id for comm_id, case_ids in community_cases.items() for case_id in case_ids
    }
    await store_communities(summaries, case_to_community, graph_store)

    # Step 5: Embed summaries
    await embed_community_summaries(summaries, embedder, vector_store)

    logger.info("Community build complete: %d communities", len(summaries))


async def main() -> None:
    """Entry point for CLI usage."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from app.core.dependencies import (
        get_embedder,
        get_flash_llm,
        get_graph_store,
        get_vector_store,
    )

    await build_communities(
        graph_store=get_graph_store(),
        flash_llm=get_flash_llm(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
    )


if __name__ == "__main__":
    asyncio.run(main())
