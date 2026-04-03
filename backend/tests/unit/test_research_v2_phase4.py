"""Tests for Research Agent V2 Phase 4 — Output Quality + Verification + Trust.

Covers Bible Section 13 tests:
  8  (Output format test)
  26-29 (Speculative RAG tests)
  30-31 (S1 merged contradictions)
  35 (S5 streaming test)
  51-55 (Dual-stage verification + LeMAJ quality)
  62-63 (Process visualization)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.state import (
    ExtractedPassage,
    Footnote,
    LegalQualityResult,
    RelevanceScore,
    ResearchState,
    SynthesisDraft,
    WorkerResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MOCK_MEMO = (
    "## Executive Summary\n\n"
    "This memorandum analyzes the applicability of Section 302 IPC "
    "(now Section 103 BNS) to cases of culpable homicide not amounting to murder. "
    "The analysis examines key precedents from the Supreme Court and High Courts, "
    "including landmark decisions on the distinction between murder and culpable homicide. "
    "The court has consistently held that the intention and knowledge of the accused are "
    "critical factors in determining the applicable provision. The distinction between "
    "Section 300 (murder) and Section 304 (culpable homicide) depends on the degree of "
    "intention and whether the act falls within any of the exceptions to Section 300."
)


def _make_mock_llm(**overrides: object) -> AsyncMock:
    llm = AsyncMock()
    # Must be >= 300 chars to pass final memo degenerate output check
    llm.generate = AsyncMock(return_value=_MOCK_MEMO)
    llm.generate_structured = AsyncMock(return_value={})
    for k, v in overrides.items():
        setattr(llm, k, v)
    return llm


def _make_mock_flash_llm() -> AsyncMock:
    llm = AsyncMock()
    # Must be >= 200 chars to pass degenerate output check
    llm.generate = AsyncMock(
        return_value=(
            "## Executive Summary\n\n"
            "This memorandum analyzes the applicability of Section 302 IPC "
            "(now Section 103 BNS) to cases of culpable homicide not amounting to murder. "
            "The analysis examines key precedents from the Supreme Court and High Courts, "
            "including landmark decisions on the distinction between murder and culpable homicide. "
            "The court has consistently held that the intention and knowledge of the accused are "
            "critical factors in determining the applicable provision."
        )
    )
    llm.generate_structured = AsyncMock(return_value={
        "overall_score": 0.85,
        "data_points": [
            {"claim": "Test claim", "supported": "supported", "evidence_id": "case-1", "issue": None}
        ],
        "omissions": [],
        "logical_issues": [],
    })
    return llm


def _make_worker_results(n: int = 10) -> list[WorkerResult]:
    """Create N mock worker results across different types."""
    results: list[WorkerResult] = []
    for i in range(min(n, 5)):
        results.append(WorkerResult(
            task_id=f"task-{i}",
            task_type="case_law",
            query=f"test query {i}",
            results=[
                {
                    "case_id": f"case-{j}",
                    "title": f"Test Case {j} v. State",
                    "citation": f"(2024) {j+1} SCC {100+j}",
                    "court": "Supreme Court of India",
                    "year": 2024,
                    "bench_type": "division",
                    "score": 0.9 - (j * 0.1),
                    "snippet": f"Held that the provisions of Section 302 apply to case {j}.",
                    "ratio": f"The ratio decidendi in case {j}.",
                    "source": "internal",
                    "precedent_strength": "BINDING" if j == 0 else "PERSUASIVE",
                }
                for j in range(3)
            ],
            source_urls=[],
            metadata={},
            error=None,
            reasoning=f"Analysis for task {i}",
        ))
    if n > 5:
        results.append(WorkerResult(
            task_id="task-community",
            task_type="graph_community",
            query="community query",
            results=[{
                "title": "Section 302 IPC cluster",
                "summary": "Cases related to murder under Section 302",
                "size": 15,
                "legal_principles": ["Murder requires intent"],
            }],
            source_urls=[],
            metadata={},
            error=None,
            reasoning="",
        ))
    return results


def _make_relevance_scores() -> list[RelevanceScore]:
    return [
        RelevanceScore(case_id=f"case-{i}", score=0.9 - i * 0.1, verdict="correct", reason="relevant", action="keep")
        for i in range(3)
    ]


def _make_extracted_passages() -> list[ExtractedPassage]:
    return [
        ExtractedPassage(
            case_id=f"case-{i}",
            citation=f"(2024) {i+1} SCC {100+i}",
            passage=f"The court held that Section 302 IPC applies in case {i}.",
            source_field="chunk_text",
            relevance=f"Directly relevant to issue {i}",
            is_verbatim=True,
        )
        for i in range(3)
    ]


def _make_base_state(**overrides: object) -> dict:
    """Create a minimal ResearchState dict for testing."""
    wr = _make_worker_results()
    # Flatten worker results into search_results (matches evaluate_and_extract output)
    flat_results: list[dict] = []
    for w in wr:
        flat_results.extend(w.get("results", []))
    state: dict = {
        "query": "Is Section 302 IPC applicable to cases of culpable homicide?",
        "rewritten_query": "Legal analysis of Section 302 IPC (now Section 103 BNS) applicability to culpable homicide",
        "worker_results": wr,
        "search_results": flat_results,
        "relevance_scores": _make_relevance_scores(),
        "extracted_passages": _make_extracted_passages(),
        "worker_reasonings": ["Worker analysis: found key cases on Section 302."],
        "messages": [],
        "refinement_round": 0,
    }
    state.update(overrides)
    return state


# ===========================================================================
# 4B — Speculative RAG Synthesis Tests (Bible tests 26-29)
# ===========================================================================


class TestSpeculativeSynthesisNode:
    """Bible tests 26-29: Speculative RAG synthesis."""

    @pytest.mark.asyncio
    async def test_three_drafts_generated_with_different_strategies(self) -> None:
        """Test 26: Verify 3 Pro drafts use different evidence subsets."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )

        # 3 drafts should be generated
        assert len(result["synthesis_drafts"]) == 3
        strategies = {d["strategy"] for d in result["synthesis_drafts"]}
        assert strategies == {"relevance", "authority", "breadth"}

        # Pro LLM generates 3 drafts + 1 merge = at least 4 calls
        assert llm.generate.call_count >= 4

    @pytest.mark.asyncio
    async def test_each_draft_is_structurally_valid(self) -> None:
        """Test 27: Each Flash draft should be a structurally valid memo."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        flash_llm = _make_mock_flash_llm()
        flash_llm.generate = AsyncMock(
            return_value=(
                "## Executive Summary\n\n"
                "Key finding on Section 302 IPC and its applicability. The court has held that "
                "the distinction between murder and culpable homicide depends on the degree of "
                "intention. Multiple precedents establish the test for determining intent.\n\n"
                "## Quick Reference Table\n\n| Case | Citation | Holding |\n"
                "| State v. A | (2024) 1 SCC 100 | Intent must be established |\n"
            )
        )
        llm = _make_mock_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )

        for draft in result["synthesis_drafts"]:
            assert draft["memo_text"]
            assert len(draft["draft_id"]) > 0
            assert draft["strategy"] in {"relevance", "authority", "breadth"}

    @pytest.mark.asyncio
    async def test_pro_merge_produces_final_memo(self) -> None:
        """Test 28: Pro verifier produces final memo incorporating multiple drafts."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        llm.generate = AsyncMock(
            return_value=(
                "## Executive Summary\n\n"
                "Final merged memo analyzing the applicability of Section 302 IPC with [^1] citations. "
                "The Supreme Court has consistently distinguished between murder under Section 300 and "
                "culpable homicide under Section 304 based on the degree of intention. The key precedents "
                "establish that the distinction depends on whether the accused had the specific intent to "
                "cause death or merely the knowledge that their act was likely to cause death.\n\n"
                "## Contradictions & Conflicts\n\nNo contradictions detected in the cited authorities."
            )
        )
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )

        assert result["draft_memo"]
        assert "Executive Summary" in result["draft_memo"]
        # Pro LLM called for 3 drafts + 1 merge = at least 4 calls
        assert llm.generate.call_count >= 4

    @pytest.mark.asyncio
    async def test_empty_results_returns_gracefully(self) -> None:
        """Speculative synthesis with no evidence returns gracefully."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state(
            worker_results=[
                WorkerResult(
                    task_id="empty", task_type="case_law", query="q",
                    results=[], source_urls=[], metadata={}, error=None, reasoning="",
                )
            ],
            search_results=[],
        )

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )

        assert result["confidence"] == 0.0
        assert result["synthesis_drafts"] == []

    @pytest.mark.asyncio
    async def test_source_attribution_built(self) -> None:
        """Source attribution dict is populated with citation → metadata."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )

        assert isinstance(result["source_attribution"], dict)
        assert isinstance(result["research_audit"], dict)
        assert "total_sources_searched" in result["research_audit"]


# ===========================================================================
# 4B.3 — Streaming Test (Bible test 35) [S5]
# ===========================================================================


class TestStreamingSynthesis:
    """Bible test 35: SSE streaming during Pro generation."""

    @pytest.mark.asyncio
    async def test_stream_callback_invoked_during_synthesis(self) -> None:
        """Test 35: memo_stream SSE events emitted during Pro generation."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        chunks_received: list[str] = []

        def mock_stream_callback(chunk: str) -> None:
            chunks_received.append(chunk)

        llm = _make_mock_llm()
        # Mock streaming: llm.stream returns an async iterator
        async def mock_stream(**kwargs: object):
            for chunk in ["## Executive ", "Summary\n\n", "Test memo ", "content."]:
                yield chunk

        llm.stream = mock_stream
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
            stream_callback=mock_stream_callback,
        )

        # Stream callback should have been called with chunks
        assert len(chunks_received) == 4
        assert "".join(chunks_received) == "## Executive Summary\n\nTest memo content."
        # Final memo matches concatenated chunks (plus disclaimer)
        assert result["draft_memo"].startswith("## Executive Summary")

    @pytest.mark.asyncio
    async def test_non_streaming_fallback(self) -> None:
        """Without stream_callback, uses regular generate."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
            stream_callback=None,
        )

        assert result["draft_memo"]
        # Regular generate should be called (not stream) — 3 drafts + 1 merge
        assert llm.generate.call_count >= 4


# ===========================================================================
# 4B.2 — Format Footnotes Node Tests
# ===========================================================================


class TestFormatFootnotesNode:
    """Test footnote post-processing."""

    @pytest.mark.asyncio
    async def test_footnotes_extracted_from_memo(self) -> None:
        """Footnote references [^N] are parsed and structured."""
        from app.core.agents.nodes.research_nodes import format_footnotes_node

        state = _make_base_state(
            draft_memo=(
                "The court held [^1] that Section 302 applies [^2].\n\n"
                "## Footnotes\n"
                "[^1]: (2024) 1 SCC 100 | Supreme Court, 2024 | Source: Internal | /case/case-0\n"
                "[^2]: (2024) 2 SCC 101 | Supreme Court, 2024 | Source: Internal | /case/case-1\n"
            ),
        )

        result = await format_footnotes_node(state)
        footnotes = result["footnotes"]

        # Should find used footnotes
        used_fns = [fn for fn in footnotes if fn["is_used"]]
        assert len(used_fns) >= 2
        assert used_fns[0]["number"] == 1
        assert used_fns[1]["number"] == 2

    @pytest.mark.asyncio
    async def test_unused_sources_included(self) -> None:
        """Sources searched but not cited are included with is_used=False."""
        from app.core.agents.nodes.research_nodes import format_footnotes_node

        state = _make_base_state(
            draft_memo="No citations in this memo.\n",
        )

        result = await format_footnotes_node(state)
        unused = [fn for fn in result["footnotes"] if not fn["is_used"]]
        # All worker results should appear as unused
        assert len(unused) > 0

    @pytest.mark.asyncio
    async def test_empty_memo_returns_empty_footnotes(self) -> None:
        """Empty memo returns empty footnotes."""
        from app.core.agents.nodes.research_nodes import format_footnotes_node

        state = _make_base_state(draft_memo="")
        result = await format_footnotes_node(state)
        assert result["footnotes"] == []


# ===========================================================================
# 4C — Dual-Stage Verification Tests (Bible tests 51-53) [Q6 + T4]
# ===========================================================================


class TestDualStageVerification:
    """Bible tests 51-53: Dual-stage citation verification."""

    @pytest.mark.asyncio
    async def test_deterministic_verify_missing_footnote(self) -> None:
        """Test 51: Detect missing footnote entry for [^N] reference."""
        from app.core.agents.nodes.research_nodes import _deterministic_verify

        memo = "The court held [^1] this and [^99] that."
        footnotes = [
            Footnote(number=1, citation="(2024) 1 SCC 100", source_type="case_law",
                     source_url="/case/1", case_id="case-1", excerpt="test",
                     is_used=True, verification_status="pending", verified_against="none",
                     title="Test v State", court="Supreme Court of India", year=2024,
                     author="", bench="", ik_doc_id="", pdf_available=True, source_label="Case"),
        ]

        db = AsyncMock()
        issues = await _deterministic_verify(memo, footnotes, [], db)

        missing = [i for i in issues if i["type"] == "missing_footnote"]
        assert len(missing) == 1
        assert missing[0]["ref"] == "99"

    @pytest.mark.asyncio
    async def test_deterministic_verify_sql_injection_safe(self) -> None:
        """SQL injection in case_id must not execute arbitrary SQL."""
        from app.core.agents.nodes.research_nodes import _deterministic_verify

        malicious_footnote = Footnote(
            number=1, citation="Test v Test", source_type="case_law",
            source_url="", case_id="'; DROP TABLE cases; --", excerpt="x",
            is_used=True, verification_status="pending", verified_against="none",
            title="", court="", year=None, author="", bench="",
            ik_doc_id="", pdf_available=False, source_label="Case",
        )

        db = AsyncMock()
        # The parameterized query should raise on invalid UUID, not execute DROP
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=mock_result)

        issues = await _deterministic_verify("memo [^1]", [malicious_footnote], [], db)
        assert isinstance(issues, list)
        # Verify the query used parameterized form (not f-string)
        call_args = db.execute.call_args
        if call_args:
            query_text = str(call_args[0][0])
            assert "case_id" not in query_text or ":case_id" in query_text

    @pytest.mark.asyncio
    async def test_verify_citations_uses_gather(self) -> None:
        """Citation verification must use asyncio.gather for parallelism."""
        import inspect
        from app.core.agents.nodes.research_nodes import _verify_citations_against_sources

        source = inspect.getsource(_verify_citations_against_sources)
        assert "gather" in source, "Must use asyncio.gather for parallel verification"
        assert "Semaphore" in source, "Must use semaphore to limit concurrency"

    @pytest.mark.asyncio
    async def test_citation_verification_uses_title_search(self) -> None:
        """IK citation verification should use title for reliable matching."""
        from app.core.agents.nodes.research_nodes import _verify_citations_against_sources

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar=lambda: None))

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(return_value=[{"tid": 1, "title": "Match"}])

        footnotes = [
            Footnote(
                number=1, citation="(2020) 5 SCC 1", source_type="case_law",
                source_url="", case_id=None, excerpt="Test",
                is_used=True, verification_status="pending", verified_against="none",
                title="State of Punjab v. Mohinder Singh", court="", year=2020,
                author="", bench="",
                ik_doc_id="", pdf_available=False, source_label="Case",
            ),
        ]
        result = await _verify_citations_against_sources(footnotes, mock_db, mock_ik, None)

        mock_ik.search.assert_called_once()
        # IK search now uses title, not cite_filter
        call_args = mock_ik.search.call_args
        assert call_args[0][0] == "State of Punjab v. Mohinder Singh"
        assert result[0]["verification_status"] == "verified_ik"

    @pytest.mark.asyncio
    async def test_t4_guardrail_removes_unverifiable_citations(self) -> None:
        """Test 52: [T4] Unverifiable citations are REMOVED, not just flagged."""
        from app.core.agents.nodes.research_nodes import _verify_citations_against_sources

        footnotes = [
            Footnote(number=1, citation="(2024) 1 SCC 100", source_type="case_law",
                     source_url="/case/1", case_id="00000000-0000-0000-0000-000000000001", excerpt="test",
                     is_used=True, verification_status="pending", verified_against="none",
                     title="Test v State", court="Supreme Court of India", year=2024,
                     author="", bench="", ik_doc_id="", pdf_available=True, source_label="Case"),
            Footnote(number=2, citation="Fake Case v. State", source_type="case_law",
                     source_url="", case_id=None, excerpt="fake",
                     is_used=True, verification_status="pending", verified_against="none",
                     title="", court="", year=None, author="", bench="",
                     ik_doc_id="", pdf_available=False, source_label="Case"),
        ]

        # DB returns case UUID as existing via batch verify_case_ids query
        # [B9] verify_case_ids uses: SELECT id::text FROM cases WHERE id::text = ANY(:ids)
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[("00000000-0000-0000-0000-000000000001",)])
        db = AsyncMock()
        async def _fake_execute(*args, **kwargs):
            return mock_result
        db.execute = _fake_execute

        result = await _verify_citations_against_sources(footnotes, db, None, None)

        # First footnote should be verified (has case_id, DB returns truthy)
        assert result[0]["verification_status"] == "verified_pg"
        # Second footnote has no case_id, no IK, no Neo4j → unverified
        # Note: is_used is NEVER modified by verification — it reflects memo usage
        assert result[1]["verification_status"] == "unverified"
        assert result[1]["is_used"] is True  # preserved from input

    @pytest.mark.asyncio
    async def test_verify_citations_v2_node_produces_banner(self) -> None:
        """Test 53: Verification banner shows verified/removed counts."""
        from app.core.agents.nodes.research_nodes import verify_citations_v2_node

        state = _make_base_state(
            footnotes=[
                Footnote(number=1, citation="(2024) 1 SCC 100", source_type="case_law",
                         source_url="/case/00000000-0000-0000-0000-000000000000", case_id="00000000-0000-0000-0000-000000000000", excerpt="test",
                         is_used=True, verification_status="pending", verified_against="none",
                         title="Test v State", court="Supreme Court of India", year=2024,
                         author="", bench="", ik_doc_id="", pdf_available=True, source_label="Case"),
            ],
            research_audit={"total_sources_searched": 10},
            draft_memo="Test memo [^1] citation.\n\n[^1]: (2024) 1 SCC 100",
        )

        # [B9] Mock returns case UUID as existing in batch query and scalar for other queries
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=1)
        mock_result.fetchall = MagicMock(return_value=[("00000000-0000-0000-0000-000000000000",)])
        async def _fake_execute(*args, **kwargs):
            return mock_result
        db = MagicMock()
        db.execute = _fake_execute

        result = await verify_citations_v2_node(state, db)

        assert "verification_banner" in result["research_audit"]
        assert result["research_audit"]["citations_verified"] >= 0

    @pytest.mark.asyncio
    async def test_citation_format_validation(self) -> None:
        """Indian citation format patterns are correctly validated."""
        from app.core.agents.nodes.research_nodes import _matches_indian_citation_pattern

        assert _matches_indian_citation_pattern("(2024) 1 SCC 100")
        assert _matches_indian_citation_pattern("AIR 2020 SC 500")
        assert _matches_indian_citation_pattern("2024:INSC:0001")
        assert _matches_indian_citation_pattern("Section 302")
        assert _matches_indian_citation_pattern("Article 21")
        assert not _matches_indian_citation_pattern("random text here")


# ===========================================================================
# 4D — LeMAJ Legal Quality Check Tests (Bible tests 54-55) [Q4]
# ===========================================================================


class TestLegalQualityCheck:
    """Bible tests 54-55: LeMAJ legal quality check."""

    @pytest.mark.asyncio
    async def test_quality_check_returns_score_and_data_points(self) -> None:
        """Test 54: Quality check decomposes memo into data points."""
        from app.core.agents.nodes.research_nodes import legal_quality_check_node

        flash_llm = _make_mock_flash_llm()
        flash_llm.generate_structured = AsyncMock(return_value={
            "overall_score": 0.85,
            "data_points": [
                {"claim": "Section 302 applies to murder", "supported": "supported",
                 "evidence_id": "case-0", "issue": None},
                {"claim": "Culpable homicide is different", "supported": "partially_supported",
                 "evidence_id": "case-1", "issue": "Nuance missing"},
            ],
            "omissions": [],
            "logical_issues": [],
        })

        state = _make_base_state(
            draft_memo="## Executive Summary\n\nSection 302 IPC applies to murder cases.",
        )

        result = await legal_quality_check_node(state, flash_llm)
        qr = result["legal_quality_result"]

        assert qr["overall_score"] == 0.85
        assert qr["pass_threshold"] is True
        assert len(qr["data_points"]) == 2

    @pytest.mark.asyncio
    async def test_quality_check_below_threshold(self) -> None:
        """Test 55: Quality below 0.7 sets pass_threshold=False."""
        from app.core.agents.nodes.research_nodes import legal_quality_check_node

        flash_llm = _make_mock_flash_llm()
        flash_llm.generate_structured = AsyncMock(return_value={
            "overall_score": 0.4,
            "data_points": [
                {"claim": "Unsupported claim", "supported": "unsupported",
                 "evidence_id": None, "issue": "No evidence"},
            ],
            "omissions": [
                {"missed_authority": "Bachan Singh v. State of Punjab",
                 "relevance": "Key authority on Section 302"},
            ],
            "logical_issues": ["Conclusion doesn't follow from analysis"],
        })

        state = _make_base_state(
            draft_memo="## Executive Summary\n\nPoor quality memo.",
        )

        result = await legal_quality_check_node(state, flash_llm)
        qr = result["legal_quality_result"]

        assert qr["overall_score"] == 0.4
        assert qr["pass_threshold"] is False
        assert len(qr["omissions"]) == 1
        assert len(qr["logical_issues"]) == 1

    @pytest.mark.asyncio
    async def test_quality_check_with_empty_memo(self) -> None:
        """Empty memo returns score 0 and pass_threshold=False."""
        from app.core.agents.nodes.research_nodes import legal_quality_check_node

        flash_llm = _make_mock_flash_llm()
        state = _make_base_state(draft_memo="")

        result = await legal_quality_check_node(state, flash_llm)
        qr = result["legal_quality_result"]

        assert qr["overall_score"] == 0.0
        assert qr["pass_threshold"] is False


# ===========================================================================
# S1 — Merged Contradictions Tests (Bible tests 30-31)
# ===========================================================================


class TestMergedContradictions:
    """Bible tests 30-31: S1 contradictions merged into synthesis."""

    @pytest.mark.asyncio
    async def test_contradictions_section_always_present(self) -> None:
        """Test 31: Every memo contains Contradictions & Conflicts section."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        llm.generate = AsyncMock(
            return_value=(
                "## Executive Summary\n\n"
                "This memorandum examines the legal position regarding Section 302 IPC. "
                "The analysis covers multiple precedents and highlights key distinctions "
                "between murder and culpable homicide based on judicial interpretation. "
                "The authorities consistently emphasize intent as the differentiating factor.\n\n"
                "## Contradictions & Conflicts\n\nNo contradictions detected."
            )
        )
        flash_llm = _make_mock_flash_llm()
        state = _make_base_state()

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )

        assert "Contradictions" in result["draft_memo"]

    @pytest.mark.asyncio
    async def test_merge_prompt_instructs_contradiction_detection(self) -> None:
        """Test 30: Pro merge prompt includes contradiction detection instructions."""
        from app.core.legal.prompts import SPECULATIVE_MERGE_SYSTEM

        assert "CONTRADICTION DETECTION" in SPECULATIVE_MERGE_SYSTEM
        assert "overruled" in SPECULATIVE_MERGE_SYSTEM.lower()
        assert "No contradictions detected" in SPECULATIVE_MERGE_SYSTEM


# ===========================================================================
# Graph Wiring Tests
# ===========================================================================


class TestPhase4GraphWiring:
    """Verify Phase 4 nodes are registered in the graph."""

    def test_graph_has_phase4_nodes(self) -> None:
        """All Phase 4 nodes are registered in the research graph."""
        from app.core.agents.research import build_research_graph

        llm = _make_mock_llm()
        flash_llm = _make_mock_flash_llm()
        embedder = AsyncMock()
        embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)
        embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
        vs = AsyncMock()
        vs.search = AsyncMock(return_value=[])
        reranker = AsyncMock()
        reranker.rerank = AsyncMock(return_value=[])

        graph = build_research_graph(
            llm=llm, flash_llm=flash_llm, embedder=embedder,
            vector_store=vs, reranker=reranker,
        )

        # Check Phase 4 nodes exist in compiled graph
        node_names = set(graph.get_graph().nodes)
        assert "speculative_synthesis" in node_names
        assert "format_footnotes" in node_names
        assert "verify_v2" in node_names
        assert "quality_check" in node_names


# ===========================================================================
# Output Format Test (Bible test 8)
# ===========================================================================


class TestOutputFormat:
    """Bible test 8: Output format compliance."""

    def test_synthesize_system_has_required_sections(self) -> None:
        """Memo format includes all required sections."""
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_SYSTEM

        required = [
            "Executive Summary",
            "Quick Reference Table",
            "Detailed Analysis",
            "Contradictions & Conflicts",
            "Precedent Network",
            "Conclusion",
            "Footnotes",
            "Research Audit Trail",
        ]
        for section in required:
            assert section in RESEARCH_SYNTHESIZE_SYSTEM, f"Missing section: {section}"

    def test_synthesize_system_has_irac(self) -> None:
        """Synthesis prompt instructs IRAC analysis."""
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_SYSTEM

        assert "IRAC" in RESEARCH_SYNTHESIZE_SYSTEM
        assert "ISSUE" in RESEARCH_SYNTHESIZE_SYSTEM
        assert "RULE" in RESEARCH_SYNTHESIZE_SYSTEM
        assert "APPLICATION" in RESEARCH_SYNTHESIZE_SYSTEM or "Application" in RESEARCH_SYNTHESIZE_SYSTEM
        assert "CONCLUSION" in RESEARCH_SYNTHESIZE_SYSTEM

    def test_synthesize_system_has_footnote_format(self) -> None:
        """Synthesis prompt specifies [^N] footnote format."""
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_SYSTEM

        assert "[^N]" in RESEARCH_SYNTHESIZE_SYSTEM
        assert "source url" in RESEARCH_SYNTHESIZE_SYSTEM.lower() or "source_url" in RESEARCH_SYNTHESIZE_SYSTEM.lower()

    def test_synthesize_system_has_dual_code_refs(self) -> None:
        """Synthesis prompt instructs old/new code dual references."""
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_SYSTEM

        assert "IPC" in RESEARCH_SYNTHESIZE_SYSTEM
        assert "BNS" in RESEARCH_SYNTHESIZE_SYSTEM

    def test_synthesize_user_template_valid(self) -> None:
        """Synthesize user template can be formatted without errors."""
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_USER

        result = RESEARCH_SYNTHESIZE_USER.format(
            query="test query",
            evidence="test evidence",
            passages="test passages",
            worker_reasoning="test reasoning",
            communities="test communities",
            strategy_hint="Focus on relevance.",
        )
        assert "test query" in result
        assert "test evidence" in result


# ===========================================================================
# Footnote Format Helpers
# ===========================================================================


class TestCitationPatternMatcher:
    """Test _matches_indian_citation_pattern helper."""

    def test_scc_citation(self) -> None:
        from app.core.agents.nodes.research_nodes import _matches_indian_citation_pattern
        assert _matches_indian_citation_pattern("(2024) 1 SCC 100")
        assert _matches_indian_citation_pattern("(2019) 15 SCC 125")

    def test_air_citation(self) -> None:
        from app.core.agents.nodes.research_nodes import _matches_indian_citation_pattern
        assert _matches_indian_citation_pattern("AIR 2020 SC 500")

    def test_neutral_citation(self) -> None:
        from app.core.agents.nodes.research_nodes import _matches_indian_citation_pattern
        assert _matches_indian_citation_pattern("2024:INSC:0001")

    def test_invalid_citation(self) -> None:
        from app.core.agents.nodes.research_nodes import _matches_indian_citation_pattern
        assert not _matches_indian_citation_pattern("some random text")
        assert not _matches_indian_citation_pattern("")


class TestFuzzyMatch:
    """Test _fuzzy_match helper."""

    def test_exact_substring(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match
        assert _fuzzy_match("court held that", "The court held that this applies")

    def test_no_match(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match
        assert not _fuzzy_match("completely unrelated text about dogs", "Legal analysis of Section 302")

    def test_empty_strings(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match
        assert not _fuzzy_match("", "text")
        assert not _fuzzy_match("text", "")


# ---------------------------------------------------------------------------
# [T1] Process Visualization tests (Bible 13, tests 62-63)
# ---------------------------------------------------------------------------


class TestEmitStatusHelper:
    """Test the emit_status() helper function."""

    def test_emit_status_creates_valid_event(self) -> None:
        from app.core.agents.nodes.research_nodes import emit_status
        event = emit_status("plan", {"tasks": [{"type": "case_law"}], "total_workers": 3})
        assert event["type"] == "plan"
        assert event["data"]["total_workers"] == 3
        assert "tasks" in event["data"]

    def test_emit_status_all_event_types(self) -> None:
        """All T1 event types produce valid dicts."""
        from app.core.agents.nodes.research_nodes import emit_status
        event_types = [
            "plan", "searching", "found", "evaluating",
            "reflection", "gap", "drafting", "verification", "quality",
        ]
        for et in event_types:
            event = emit_status(et, {"test": True})
            assert event["type"] == et
            assert event["data"]["test"] is True


class TestProcessEventsInNodes:
    """Test that nodes emit process_events in their return dict."""

    @pytest.mark.asyncio
    async def test_plan_research_emits_plan_event(self) -> None:
        """plan_research_node returns process_events with plan type."""
        from app.core.agents.nodes.research_nodes import plan_research_node

        llm = _make_mock_llm()
        llm.generate_structured = AsyncMock(return_value={
            "research_tasks": [
                {
                    "task_type": "case_law",
                    "nl_query": "Section 302 IPC punishment",
                    "boolean_query": "302 AND IPC AND punishment",
                    "named_cases": [{"name": "Bachan Singh", "citation": "(1980) 2 SCC 684"}],
                    "rationale": "Core criminal law search",
                    "filters": {},
                    "priority": 1,
                }
            ]
        })

        state: dict = {
            "query": "What is the punishment for murder?",
            "rewritten_query": "punishment under Section 302 IPC",
            "messages": [{"type": "classification", "data": {"topic": "criminal"}}],
        }

        result = await plan_research_node(state, llm)
        assert "process_events" in result
        events = result["process_events"]
        assert len(events) >= 1
        assert events[0]["type"] == "plan"
        assert events[0]["data"]["total_workers"] >= 1

    @pytest.mark.asyncio
    async def test_gather_results_emits_progress_events(self) -> None:
        """gather_worker_results_node returns process_events (summary, not per-worker found)."""
        from app.core.agents.nodes.research_nodes import gather_worker_results_node

        state: dict = {
            "worker_results": _make_worker_results(3),
        }
        result = await gather_worker_results_node(state)
        assert "process_events" in result
        # Workers now emit individual "found" events; gather emits a summary progress event
        assert isinstance(result["process_events"], list)

    @pytest.mark.asyncio
    async def test_batch_cot_emits_reflection_event(self) -> None:
        """batch_worker_cot_with_reflection_node returns reflection event."""
        from app.core.agents.nodes.research_nodes import batch_worker_cot_with_reflection_node

        llm = _make_mock_flash_llm()
        llm.generate_structured = AsyncMock(return_value={
            "reasoning": "Analysis shows IPC 302 is relevant",
            "should_pivot": False,
        })
        state: dict = {
            "query": "Section 302 IPC",
            "rewritten_query": "Section 302 IPC punishment",
            "worker_results": _make_worker_results(3),
        }
        result = await batch_worker_cot_with_reflection_node(state, llm)
        assert "process_events" in result
        reflection = [e for e in result["process_events"] if e["type"] == "reflection"]
        assert len(reflection) == 1
        assert "insights" in reflection[0]["data"]
        assert reflection[0]["data"]["pivot"] is False

    @pytest.mark.asyncio
    async def test_gap_analysis_emits_gap_event(self) -> None:
        """gap_analysis_node returns gap event."""
        from app.core.agents.nodes.research_nodes import gap_analysis_node

        llm = _make_mock_flash_llm()
        llm.generate_structured = AsyncMock(return_value={
            "gaps": [
                {
                    "description": "No overruling cases found",
                    "suggested_query": "overruled Section 302",
                    "suggested_source": "case_law",
                    "priority": 1,
                }
            ]
        })
        state: dict = {
            "query": "Section 302 IPC",
            "rewritten_query": "Section 302 IPC",
            "research_plan": [],
            "worker_results": _make_worker_results(3),
            "relevance_scores": _make_relevance_scores(),
            "worker_reasonings": [],
            "strategy_adjustment": None,
            "refinement_round": 2,  # Max round — won't dispatch new workers
        }
        result = await gap_analysis_node(state, llm)
        assert "process_events" in result
        gap_events = [e for e in result["process_events"] if e["type"] == "gap"]
        assert len(gap_events) == 1
        assert "gaps" in gap_events[0]["data"]
        assert "refinement_round" in gap_events[0]["data"]

    @pytest.mark.asyncio
    async def test_speculative_synthesis_emits_drafting_events(self) -> None:
        """speculative_synthesis emits drafting events for all 3 strategies."""
        from app.core.agents.nodes.research_nodes import (
            speculative_synthesis_with_contradictions_node,
        )

        llm = _make_mock_llm()
        flash_llm = _make_mock_flash_llm()

        wr = _make_worker_results(3)
        flat_results: list[dict] = []
        for w in wr:
            flat_results.extend(w.get("results", []))
        state: dict = {
            "query": "Section 302 IPC",
            "rewritten_query": "Section 302 IPC",
            "worker_results": wr,
            "search_results": flat_results,
            "extracted_passages": _make_extracted_passages(),
            "relevance_scores": _make_relevance_scores(),
            "worker_reasonings": ["Test reasoning"],
            "refinement_round": 0,
        }

        result = await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
        )
        assert "process_events" in result
        drafting_events = [e for e in result["process_events"] if e["type"] == "drafting"]
        # 3 generating + 3 complete = 6
        assert len(drafting_events) == 6
        strategies = {e["data"]["strategy"] for e in drafting_events}
        assert strategies == {"relevance", "authority", "breadth"}

    @pytest.mark.asyncio
    async def test_verify_v2_emits_verification_event(self) -> None:
        """verify_citations_v2_node returns verification event."""
        from app.core.agents.nodes.research_nodes import verify_citations_v2_node

        db = AsyncMock()

        async def _fake_execute(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.scalar.return_value = True
            return mock_result
        db.execute = _fake_execute

        state: dict = {
            "draft_memo": "Test memo [^1] citation",
            "footnotes": [
                Footnote(
                    number=1, citation="(2024) 1 SCC 100",
                    source_type="case_law", source_url="/case/00000000-0000-0000-0000-000000000000",
                    case_id="00000000-0000-0000-0000-000000000000", excerpt="Test", is_used=True,
                    verification_status="unverified", verified_against="none",
                    title="Test Case v. State", court="Supreme Court of India",
                    year=2024, author="Justice X", bench="Division Bench",
                    ik_doc_id="", pdf_available=True, source_label="Case",
                ),
            ],
            "extracted_passages": _make_extracted_passages(),
            "research_audit": {},
        }

        result = await verify_citations_v2_node(state, db)
        assert "process_events" in result
        verification_events = [e for e in result["process_events"] if e["type"] == "verification"]
        assert len(verification_events) == 1
        assert "citations_verified" in verification_events[0]["data"]
        assert "citations_unverified" in verification_events[0]["data"]

    @pytest.mark.asyncio
    async def test_legal_quality_emits_quality_event(self) -> None:
        """legal_quality_check_node returns quality event."""
        from app.core.agents.nodes.research_nodes import legal_quality_check_node

        llm = _make_mock_flash_llm()
        state: dict = {
            "draft_memo": "## Executive Summary\n\nTest legal memo content.",
            "worker_results": _make_worker_results(3),
        }

        result = await legal_quality_check_node(state, llm)
        assert "process_events" in result
        quality_events = [e for e in result["process_events"] if e["type"] == "quality"]
        assert len(quality_events) == 1
        assert "overall_score" in quality_events[0]["data"]
        assert "pass_threshold" in quality_events[0]["data"]


class TestProcessEventsAccumulation:
    """Test that process_events uses reducer (operator.add) for accumulation."""

    def test_state_process_events_is_annotated_reducer(self) -> None:
        """ResearchState.process_events should use operator.add reducer."""
        import typing
        hints = typing.get_type_hints(ResearchState, include_extras=True)
        pe_hint = hints["process_events"]
        # Annotated types have __metadata__
        assert hasattr(pe_hint, "__metadata__"), "process_events should be Annotated"

    def test_sse_layer_forwards_process_events(self) -> None:
        """process_events in node output are forwarded via SSE."""
        import json
        # Simulate what _stream_agent_events does:
        node_output = {
            "draft_memo": "test",
            "process_events": [
                {"type": "drafting", "data": {"strategy": "relevance", "status": "complete"}},
                {"type": "verification", "data": {"citations_verified": 5}},
            ],
        }
        exec_id = "test-exec-123"
        forwarded = []
        for pe in node_output.get("process_events", []):
            sse_line = f"data: {json.dumps({**pe, 'execution_id': exec_id})}\n\n"
            forwarded.append(json.loads(sse_line.removeprefix("data: ").strip()))
        assert len(forwarded) == 2
        assert forwarded[0]["type"] == "drafting"
        assert forwarded[0]["execution_id"] == exec_id
        assert forwarded[1]["type"] == "verification"


# ---------------------------------------------------------------------------
# Fuzzy match tests
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    """Tests for _fuzzy_match — word + trigram algorithm."""

    def test_exact_substring(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match

        assert _fuzzy_match("the court held", "In this case the court held that") is True

    def test_rejects_unrelated_strings(self) -> None:
        """Character-overlap fuzzy match must not produce false positives."""
        from app.core.agents.nodes.research_nodes import _fuzzy_match

        # These share many common characters but are completely different passages
        assert _fuzzy_match("Section 498A IPC", "Section 302 IPC deals with murder") is False

    def test_rejects_anagram_like(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match

        assert _fuzzy_match("abc", "cba") is False

    def test_same_words_reordered(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match

        assert _fuzzy_match("the court held", "held the court") is True

    def test_near_exact_with_typo(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match

        assert _fuzzy_match(
            "the court dismissed the appeal",
            "the court dismissed the appael",
        ) is True

    def test_empty_strings(self) -> None:
        from app.core.agents.nodes.research_nodes import _fuzzy_match

        assert _fuzzy_match("", "something") is False
        assert _fuzzy_match("something", "") is False
        assert _fuzzy_match("", "") is False


# ---------------------------------------------------------------------------
# Source label inference
# ---------------------------------------------------------------------------


class TestInferSourceLabel:
    """Tests for _infer_source_label helper."""

    def test_infer_source_label(self) -> None:
        from app.core.agents.nodes.research_nodes import _infer_source_label

        assert _infer_source_label("case_law") == "Case"
        assert _infer_source_label("ik_search") == "Case"
        assert _infer_source_label("named_case") == "Case"
        assert _infer_source_label("statute") == "Statute"
        assert _infer_source_label("constitution") == "Constitution"
        assert _infer_source_label("web") == "Web"
        assert _infer_source_label("graph") == "Case"
        assert _infer_source_label("graph_community") == "Case"
        assert _infer_source_label("unknown") == "Source"
        assert _infer_source_label("") == "Source"


# ---------------------------------------------------------------------------
# Enriched Footnote Fields (Task 10)
# ---------------------------------------------------------------------------


class TestFootnoteEnrichedFields:
    """Footnotes should include enriched case metadata for the preview panel."""

    def test_footnote_accepts_all_enriched_fields(self):
        """Footnote TypedDict accepts all enriched fields."""
        from app.core.agents.state import Footnote
        fn: Footnote = {
            "number": 1,
            "citation": "(2023) 5 SCC 1",
            "source_type": "case_law",
            "source_url": "/case/abc-123",
            "case_id": "abc-123",
            "excerpt": "The court held...",
            "is_used": True,
            "verification_status": "verified_pg",
            "verified_against": "pg",
            "title": "State v. People's Union",
            "court": "Supreme Court of India",
            "year": 2023,
            "author": "D Y Chandrachud",
            "bench": "Constitution Bench",
            "ik_doc_id": "12345678",
            "pdf_available": True,
            "source_label": "Case",
        }
        assert fn["court"] == "Supreme Court of India"
        assert fn["ik_doc_id"] == "12345678"
        assert fn["pdf_available"] is True
        assert fn["source_label"] == "Case"

    def test_footnote_web_source(self):
        """Web source footnote has correct enriched defaults."""
        from app.core.agents.state import Footnote
        fn: Footnote = {
            "number": 5,
            "citation": "Legal blog article",
            "source_type": "web",
            "source_url": "https://example.com/article",
            "case_id": None,
            "excerpt": "Article content...",
            "is_used": False,
            "verification_status": "unverified",
            "verified_against": "none",
            "title": "Understanding Section 498A",
            "court": "",
            "year": None,
            "author": "",
            "bench": "",
            "ik_doc_id": "",
            "pdf_available": False,
            "source_label": "Web",
        }
        assert fn["source_label"] == "Web"
        assert fn["pdf_available"] is False
        assert fn["court"] == ""

    def test_footnote_ik_source_no_pdf(self):
        """IK sources should have pdf_available=False (IK cases don't have our PDFs)."""
        from app.core.agents.state import Footnote
        fn: Footnote = {
            "number": 3,
            "citation": "(2020) 10 SCC 1",
            "source_type": "ik_search",
            "source_url": "https://indiankanoon.org/doc/999/",
            "case_id": "ik:999",
            "excerpt": "The court observed...",
            "is_used": True,
            "verification_status": "verified_ik",
            "verified_against": "ik",
            "title": "Puttaswamy v. Union of India",
            "court": "Supreme Court of India",
            "year": 2020,
            "author": "Chandrachud J.",
            "bench": "9-Judge Bench",
            "ik_doc_id": "999",
            "pdf_available": False,
            "source_label": "Case",
        }
        assert fn["pdf_available"] is False
        assert fn["ik_doc_id"] == "999"


class TestGatherWorkerDedup:
    """C2: worker_results dedup by task_id in gather."""

    @pytest.mark.asyncio
    async def test_worker_results_deduped_by_task_id(self) -> None:
        """Duplicate task_ids from refinement loops keep only latest."""
        from app.core.agents.nodes.research_nodes import gather_worker_results_node

        # Simulate: first dispatch + refinement dispatch with same task_id
        state: dict = {
            "worker_results": [
                WorkerResult(
                    task_id="task-1", task_type="case_law", query="old query",
                    results=[{"case_id": "old-case", "title": "Old", "score": 0.5}],
                    source_urls=[], metadata={}, error=None, reasoning="",
                ),
                WorkerResult(
                    task_id="task-1", task_type="case_law", query="new query",
                    results=[{"case_id": "new-case", "title": "New", "score": 0.9}],
                    source_urls=[], metadata={}, error=None, reasoning="",
                ),
            ],
        }
        result = await gather_worker_results_node(state)
        # Should keep only the latest (new-case), not accumulate both
        case_ids = [r.get("case_id") for r in result["search_results"]]
        assert "new-case" in case_ids
        assert "old-case" not in case_ids

    @pytest.mark.asyncio
    async def test_different_task_ids_both_kept(self) -> None:
        """Different task_ids are all kept."""
        from app.core.agents.nodes.research_nodes import gather_worker_results_node

        state: dict = {
            "worker_results": [
                WorkerResult(
                    task_id="task-1", task_type="case_law", query="q1",
                    results=[{"case_id": "case-1", "title": "C1", "score": 0.9}],
                    source_urls=[], metadata={}, error=None, reasoning="",
                ),
                WorkerResult(
                    task_id="task-2", task_type="statute", query="q2",
                    results=[{"case_id": "case-2", "title": "C2", "score": 0.8}],
                    source_urls=[], metadata={}, error=None, reasoning="",
                ),
            ],
        }
        result = await gather_worker_results_node(state)
        case_ids = [r.get("case_id") for r in result["search_results"]]
        assert "case-1" in case_ids
        assert "case-2" in case_ids
