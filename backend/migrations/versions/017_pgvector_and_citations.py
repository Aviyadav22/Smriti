"""Add pgvector extension, case_vectors table, and citations table.

Revision ID: 017
Revises: 016
Create Date: 2026-03-18

Changes:
1. Enable pgvector extension (CREATE EXTENSION IF NOT EXISTS vector)
2. Create case_vectors table with HNSW index for similarity search
3. Create citations table for citation graph (replaces Neo4j when GRAPH_PROVIDER=postgresql)
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. pgvector extension
    # ----------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ----------------------------------------------------------------
    # 2. case_vectors table (used when VECTOR_PROVIDER=pgvector)
    # ----------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS case_vectors (
            id TEXT PRIMARY KEY,
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            embedding vector(1536) NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # HNSW index for approximate nearest neighbor search (cosine distance).
    # m=16, ef_construction=64 balances recall vs build speed.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_case_vectors_hnsw
        ON case_vectors USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # B-tree index for case_id lookups (deletion, filtering).
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_case_vectors_case_id
        ON case_vectors (case_id)
    """)

    # GIN index on JSONB metadata for filter queries.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_case_vectors_metadata
        ON case_vectors USING gin (metadata jsonb_path_ops)
    """)

    # ----------------------------------------------------------------
    # 3. citations table (used when GRAPH_PROVIDER=postgresql)
    # ----------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS citations (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            source_case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            target_citation TEXT NOT NULL,
            target_case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
            treatment TEXT NOT NULL DEFAULT 'CITED',
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (source_case_id, target_citation)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_citations_target
        ON citations (target_citation)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_citations_target_case
        ON citations (target_case_id)
        WHERE target_case_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_citations_source
        ON citations (source_case_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_citations_treatment
        ON citations (treatment)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS citations")
    op.execute("DROP TABLE IF EXISTS case_vectors")
    # Don't drop the vector extension — other tables may use it.
