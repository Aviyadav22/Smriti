"""Tests for Research Agent V2 Phase 2 — Data Expansion + Ingestion.

Covers Bible Section 13 tests:
  14-15 (Contextual Embeddings)
  56-58 (RAPTOR Hierarchical Summaries)
  59-61 (Code Mapping)
  72 (Statute ingestion)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.contextual_embeddings import (
    batch_contextualize_chunks,
    generate_contextual_prefix,
)
from app.core.ingestion.section_summarizer import (
    build_pinecone_summary_vectors,
    generate_section_summaries,
)
from app.core.search.query import expand_statute_references
from app.models.statute import Statute

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flash_llm(**overrides: object) -> AsyncMock:
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="Generated prefix for context.")
    for k, v in overrides.items():
        setattr(llm, k, v)
    return llm


# ===========================================================================
# Bible Tests 14-15: Contextual Embeddings
# ===========================================================================


class TestGenerateContextualPrefix:
    """Bible test 14 — verify prefix generation."""

    @pytest.mark.asyncio
    async def test_returns_prefix_plus_original(self) -> None:
        """Output should contain both context prefix and original chunk."""
        llm = _make_flash_llm()
        llm.generate.return_value = (
            "This is from Kesavananda Bharati (1973) regarding basic structure."
        )

        chunk = "The court held that Parliament cannot amend the basic structure."
        meta = {
            "title": "Kesavananda Bharati",
            "citation": "(1973) 4 SCC 225",
            "court": "SC",
            "year": 1973,
        }

        result = await generate_contextual_prefix(chunk, meta, llm, "case_law")

        # Must contain context prefix at start
        assert result.startswith("This is from Kesavananda")
        # Must contain original chunk text
        assert chunk in result
        # Must have separator
        assert "\n\n" in result

    @pytest.mark.asyncio
    async def test_statute_prefix(self) -> None:
        """Bible test 15 — IPC Section 302 gets appropriate prefix."""
        llm = _make_flash_llm()
        llm.generate.return_value = (
            "This is Section 302 (Punishment for murder) of the Indian Penal Code, "
            "1860, now replaced by Section 103 of BNS, 2023."
        )

        chunk = "Whoever commits murder shall be punished with death or imprisonment for life."
        meta = {
            "act_name": "Indian Penal Code, 1860",
            "section_number": "302",
            "section_title": "Punishment for murder",
            "chapter": "XVI — Of Offences Affecting the Human Body",
            "replaced_by": "BNS, Section 103",
        }

        result = await generate_contextual_prefix(chunk, meta, llm, "statute")

        assert "Section 302" in result
        assert "BNS" in result or "replaced" in result
        assert chunk in result

    @pytest.mark.asyncio
    async def test_passes_metadata_to_llm(self) -> None:
        llm = _make_flash_llm()
        meta = {"title": "Test Case", "citation": "(2020) 1 SCC 1", "court": "SC", "year": 2020}

        await generate_contextual_prefix("chunk text", meta, llm, "case_law")

        call_kwargs = llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Test Case" in prompt
        assert "(2020) 1 SCC 1" in prompt

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self) -> None:
        llm = _make_flash_llm()
        llm.generate.side_effect = RuntimeError("LLM down")

        result = await generate_contextual_prefix("original text", {}, llm)
        assert result == "original text"


class TestBatchContextualizeChunks:
    """Bible test 14 (batch variant)."""

    @pytest.mark.asyncio
    async def test_adds_contextualized_text_key(self) -> None:
        llm = _make_flash_llm()
        llm.generate.return_value = "Context prefix."

        chunks = [
            {"text": "First chunk text"},
            {"text": "Second chunk text"},
        ]
        meta = {"title": "Test"}

        result = await batch_contextualize_chunks(chunks, meta, llm)

        assert len(result) == 2
        for chunk in result:
            assert "contextualized_text" in chunk
            assert "text" in chunk  # Original preserved
            assert chunk["text"] in chunk["contextualized_text"]

    @pytest.mark.asyncio
    async def test_preserves_original_text(self) -> None:
        llm = _make_flash_llm()
        llm.generate.return_value = "Prefix."

        chunks = [{"text": "Original content here"}]
        result = await batch_contextualize_chunks(chunks, {}, llm)

        assert result[0]["text"] == "Original content here"

    @pytest.mark.asyncio
    async def test_handles_failure_gracefully(self) -> None:
        llm = _make_flash_llm()
        llm.generate.side_effect = RuntimeError("LLM error")

        chunks = [{"text": "Fallback text"}]
        result = await batch_contextualize_chunks(chunks, {}, llm)

        assert result[0]["contextualized_text"] == "Fallback text"


# ===========================================================================
# Bible Tests 56-58: RAPTOR Hierarchical Summaries
# ===========================================================================


class TestGenerateSectionSummaries:
    """Bible test 56 — section summary generation."""

    @pytest.mark.asyncio
    async def test_produces_summaries_for_each_section(self) -> None:
        """Feed a case with 5 sections, verify 5 Level-1 summaries."""
        llm = _make_flash_llm()
        call_count = 0

        async def mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            section_type = kwargs.get("prompt", "").split("\n")[0]
            return f"Summary of {section_type}"

        llm.generate = mock_generate

        sections = [
            {"section_type": "FACTS", "content": "x" * 300},
            {"section_type": "ISSUES", "content": "y" * 300},
            {"section_type": "HOLDINGS", "content": "z" * 300},
            {"section_type": "ARGUMENTS", "content": "w" * 300},
            {"section_type": "ANALYSIS", "content": "v" * 300},
        ]

        summaries = await generate_section_summaries("case123", sections, llm)

        assert len(summaries) == 5
        assert call_count == 5
        for s in summaries:
            assert s["case_id"] == "case123"
            assert s["summary_level"] == 1
            assert s["summary_text"] != ""
            assert s["section_type"] in ("FACTS", "ISSUES", "HOLDINGS", "ARGUMENTS", "ANALYSIS")

    @pytest.mark.asyncio
    async def test_skips_short_sections(self) -> None:
        llm = _make_flash_llm()
        sections = [
            {"section_type": "FACTS", "content": "Short"},  # < 200 chars
            {"section_type": "HOLDINGS", "content": "x" * 300},
        ]

        summaries = await generate_section_summaries("case123", sections, llm)
        assert len(summaries) == 1
        assert summaries[0]["section_type"] == "HOLDINGS"

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self) -> None:
        llm = _make_flash_llm()
        llm.generate.side_effect = RuntimeError("LLM error")

        sections = [{"section_type": "FACTS", "content": "x" * 300}]
        summaries = await generate_section_summaries("case123", sections, llm)
        assert len(summaries) == 0

    @pytest.mark.asyncio
    async def test_empty_sections_returns_empty(self) -> None:
        llm = _make_flash_llm()
        summaries = await generate_section_summaries("case123", [], llm)
        assert summaries == []


class TestBuildPineconeSummaryVectors:
    """Bible test 57 — Pinecone storage for summaries."""

    def test_builds_correct_vector_records(self) -> None:
        summaries = [
            {
                "case_id": "c1",
                "section_type": "HOLDINGS",
                "summary_text": "Summary text",
                "summary_level": 1,
            },
        ]
        embeddings = [[0.1, 0.2, 0.3]]
        base_meta = {"title": "Test Case", "citation": "(2020) 1 SCC 1"}

        records = build_pinecone_summary_vectors("c1", summaries, embeddings, base_meta)

        assert len(records) == 1
        r = records[0]
        assert r["id"] == "c1_summary_HOLDINGS"
        assert r["values"] == [0.1, 0.2, 0.3]
        assert r["metadata"]["summary_level"] == 1
        assert r["metadata"]["section_type"] == "HOLDINGS"
        assert r["metadata"]["document_type"] == "case_law"
        assert r["metadata"]["text"] == "Summary text"
        assert r["metadata"]["title"] == "Test Case"


# ===========================================================================
# Bible Tests 59-61: Code Mapping
# ===========================================================================


class TestCodeMappingBidirectional:
    """Bible test 59 — bidirectional old↔new code lookup."""

    def test_ipc_to_bns_expansion(self) -> None:
        """Query 'Section 302 IPC' should also produce 'Section 103 BNS'."""
        query, expanded = expand_statute_references("Section 302 IPC")
        bns_terms = [t for t in expanded if "BNS" in t]
        assert len(bns_terms) >= 1
        assert any("103" in t for t in bns_terms)

    def test_bns_to_ipc_reverse(self) -> None:
        """Query 'Section 103 BNS' should also produce 'Section 302 IPC'."""
        query, expanded = expand_statute_references("Section 103 BNS")
        ipc_terms = [t for t in expanded if "IPC" in t]
        assert len(ipc_terms) >= 1
        assert any("302" in t for t in ipc_terms)

    def test_crpc_to_bnss(self) -> None:
        """Query with CrPC reference should expand to BNSS."""
        query, expanded = expand_statute_references("Section 438 CrPC")
        bnss_terms = [t for t in expanded if "BNSS" in t]
        assert len(bnss_terms) >= 1

    def test_evidence_to_bsa(self) -> None:
        """Query with IEA reference should expand to BSA."""
        # Find a known mapping
        from app.core.legal.constants import EVIDENCE_TO_BSA_MAP

        if EVIDENCE_TO_BSA_MAP:
            first_key = next(iter(EVIDENCE_TO_BSA_MAP))
            query, expanded = expand_statute_references(f"Section {first_key} IEA")
            bsa_terms = [t for t in expanded if "BSA" in t]
            assert len(bsa_terms) >= 1

    def test_no_expansion_for_unrelated_query(self) -> None:
        """Query without statute references should not expand."""
        query, expanded = expand_statute_references("anticipatory bail principles")
        assert expanded == []


class TestCodeMappingCompleteness:
    """Bible test 60 — mapping completeness (spot-check)."""

    def test_ipc_has_substantial_mappings(self) -> None:
        from app.core.legal.constants import IPC_TO_BNS_MAP

        assert len(IPC_TO_BNS_MAP) >= 100  # We have 327

    def test_crpc_has_substantial_mappings(self) -> None:
        from app.core.legal.constants import CRPC_TO_BNSS_MAP

        assert len(CRPC_TO_BNSS_MAP) >= 50  # We have 153

    def test_evidence_has_substantial_mappings(self) -> None:
        from app.core.legal.constants import EVIDENCE_TO_BSA_MAP

        assert len(EVIDENCE_TO_BSA_MAP) >= 50  # We have 87

    def test_ipc_302_maps_to_bns_103(self) -> None:
        from app.core.legal.constants import IPC_TO_BNS_MAP

        assert IPC_TO_BNS_MAP.get("302") == "103"

    def test_ipc_420_maps_to_bns(self) -> None:
        from app.core.legal.constants import IPC_TO_BNS_MAP

        assert "420" in IPC_TO_BNS_MAP

    def test_ipc_498a_maps_to_bns(self) -> None:
        from app.core.legal.constants import IPC_TO_BNS_MAP

        assert "498A" in IPC_TO_BNS_MAP


class TestCodeMappingSynthesisInstruction:
    """Bible test 61 — synthesis prompt includes dual-code instruction."""

    def test_synthesis_prompt_mentions_dual_codes(self) -> None:
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_SYSTEM

        assert (
            "old and new code" in RESEARCH_SYNTHESIZE_SYSTEM.lower()
            or "BNS" in RESEARCH_SYNTHESIZE_SYSTEM
        )


# ===========================================================================
# Bible Test 72: Statute model + schema validation
# ===========================================================================


class TestStatuteModel:
    """Bible test 72 — verify statutes table structure."""

    def test_statute_model_exists(self) -> None:
        assert Statute.__tablename__ == "statutes"

    def test_statute_has_required_columns(self) -> None:
        columns = {c.name for c in Statute.__table__.columns}
        expected = {
            "id",
            "act_name",
            "act_short_name",
            "act_number",
            "act_year",
            "part",
            "chapter",
            "section_number",
            "section_title",
            "section_text",
            "explanation",
            "effective_date",
            "is_repealed",
            "replaced_by",
            "replaces",
            "document_type",
            "searchable_text",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_statute_unique_constraint(self) -> None:
        constraints = [
            c.name for c in Statute.__table__.constraints if hasattr(c, "name") and c.name
        ]
        assert "uq_statutes_act_section" in constraints

    def test_statute_has_fts_index(self) -> None:
        indexes = {idx.name for idx in Statute.__table__.indexes}
        assert "ix_statutes_fts" in indexes

    def test_statute_has_act_index(self) -> None:
        indexes = {idx.name for idx in Statute.__table__.indexes}
        assert "ix_statutes_act" in indexes


# ===========================================================================
# Statute Ingestion Script Tests
# ===========================================================================


class TestStatuteIngestionHelpers:
    """Test ingestion script helpers."""

    def test_compute_replacement_fields_ipc(self) -> None:
        from scripts.ingest_statutes import compute_replacement_fields

        replaced_by, replaces = compute_replacement_fields("IPC", "302")
        assert "BNS" in replaced_by
        assert "103" in replaced_by
        assert replaces == ""  # IPC is old code, not replacing anything

    def test_compute_replacement_fields_bns(self) -> None:
        from scripts.ingest_statutes import compute_replacement_fields

        replaced_by, replaces = compute_replacement_fields("BNS", "103")
        assert replaced_by == ""  # BNS is new code
        assert "IPC" in replaces
        assert "302" in replaces

    def test_compute_replacement_fields_unknown(self) -> None:
        from scripts.ingest_statutes import compute_replacement_fields

        replaced_by, replaces = compute_replacement_fields("CPC", "20")
        assert replaced_by == ""
        assert replaces == ""

    def test_normalize_statute(self) -> None:
        from scripts.ingest_statutes import _normalize_statute

        raw = {
            "act_name": "Indian Penal Code, 1860",
            "act_short_name": "IPC",
            "section_number": "302",
            "section_title": "Punishment for murder",
            "section_text": "Whoever commits murder...",
            "act_year": 1860,
        }
        result = _normalize_statute(raw)

        assert result["act_name"] == "Indian Penal Code, 1860"
        assert result["section_number"] == "302"
        assert "BNS" in result["replaced_by"]
        assert result["document_type"] == "statute"


# ===========================================================================
# Bible Test 74: RAPTOR Ingestion Test
# ===========================================================================


class TestRaptorIngestionPipeline:
    """Bible test 74 — verify RAPTOR summaries stored in Pinecone after ingestion."""

    @pytest.mark.asyncio
    async def test_summaries_have_correct_metadata(self) -> None:
        """After ingestion, summary vectors should have summary_level metadata."""
        from app.core.ingestion.section_summarizer import (
            build_pinecone_summary_vectors,
            generate_section_summaries,
        )

        llm = _make_flash_llm()
        llm.generate.return_value = "The court established the rarest-of-rare doctrine."

        sections = [
            {"section_type": "HOLDINGS", "content": "x" * 300},
            {"section_type": "FACTS", "content": "y" * 300},
        ]

        summaries = await generate_section_summaries("case_raptor_1", sections, llm)
        embeddings = [[0.1] * 1536 for _ in summaries]
        base_meta = {
            "title": "Bachan Singh",
            "citation": "(1980) 2 SCC 684",
            "court": "SC",
            "year": 1980,
        }

        vectors = build_pinecone_summary_vectors("case_raptor_1", summaries, embeddings, base_meta)

        assert len(vectors) == 2
        for v in vectors:
            assert v["metadata"]["summary_level"] == 1
            assert v["metadata"]["document_type"] == "case_law"
            assert "case_raptor_1" in v["id"]
            assert v["metadata"]["court"] == "SC"
            assert len(v["values"]) == 1536

    @pytest.mark.asyncio
    async def test_level1_and_level2_distinction(self) -> None:
        """Summary vectors at Level-1 should be distinct from Level-0 chunk vectors."""
        from app.core.ingestion.section_summarizer import build_pinecone_summary_vectors

        summaries = [
            {
                "case_id": "c1",
                "section_type": "HOLDINGS",
                "summary_text": "Summary",
                "summary_level": 1,
            },
        ]
        embeddings = [[0.5] * 10]

        vectors = build_pinecone_summary_vectors("c1", summaries, embeddings)

        # Summary vector ID should NOT look like a chunk vector (case_id_N)
        assert vectors[0]["id"] == "c1_summary_HOLDINGS"
        # Should have summary_level in metadata
        assert vectors[0]["metadata"]["summary_level"] == 1

    def test_summary_vector_ids_unique_per_section(self) -> None:
        """Each section type should get a unique vector ID."""
        from app.core.ingestion.section_summarizer import build_pinecone_summary_vectors

        summaries = [
            {
                "case_id": "c2",
                "section_type": "FACTS",
                "summary_text": "Facts summary",
                "summary_level": 1,
            },
            {
                "case_id": "c2",
                "section_type": "HOLDINGS",
                "summary_text": "Holdings summary",
                "summary_level": 1,
            },
            {
                "case_id": "c2",
                "section_type": "ANALYSIS",
                "summary_text": "Analysis summary",
                "summary_level": 1,
            },
        ]
        embeddings = [[0.1] * 10, [0.2] * 10, [0.3] * 10]

        vectors = build_pinecone_summary_vectors("c2", summaries, embeddings)

        ids = [v["id"] for v in vectors]
        assert len(set(ids)) == 3  # All unique
        assert "c2_summary_FACTS" in ids
        assert "c2_summary_HOLDINGS" in ids
        assert "c2_summary_ANALYSIS" in ids


# ===========================================================================
# Pipeline Integration Tests (contextual embeddings + RAPTOR)
# ===========================================================================


class TestContextualEmbeddingPipelineIntegration:
    """Test that contextual embeddings integrate with the pipeline flow."""

    @pytest.mark.asyncio
    async def test_contextualized_text_longer_than_original(self) -> None:
        """Contextual prefix should make text longer (prefix + separator + original)."""
        llm = _make_flash_llm()
        llm.generate.return_value = "This case discusses murder under Section 302 IPC."

        chunk = "The accused was found guilty."
        meta = {"title": "Test", "citation": "(2020) 1 SCC 1"}

        result = await generate_contextual_prefix(chunk, meta, llm, "case_law")
        assert len(result) > len(chunk)

    @pytest.mark.asyncio
    async def test_batch_contextual_preserves_count(self) -> None:
        """Batch contextual should return same number of chunks as input."""
        llm = _make_flash_llm()
        llm.generate.return_value = "Context prefix."

        chunks = [{"text": f"Chunk {i}"} for i in range(5)]
        result = await batch_contextualize_chunks(chunks, {}, llm)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_pipeline_flow_order(self) -> None:
        """Verify the expected flow: chunk -> contextualize -> embed -> upsert."""
        llm = _make_flash_llm()
        llm.generate.return_value = "Context."

        # Simulate pipeline: chunks -> contextual -> texts for embedding
        chunks = [{"text": "Original chunk text"}]
        contextualized = await batch_contextualize_chunks(chunks, {"title": "Test"}, llm)

        # The text for embedding should be the contextualized version
        embed_text = contextualized[0]["contextualized_text"]
        assert "Context." in embed_text
        assert "Original chunk text" in embed_text

        # The display text should be the original
        display_text = contextualized[0]["text"]
        assert display_text == "Original chunk text"
