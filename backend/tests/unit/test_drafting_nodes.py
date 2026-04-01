"""Tests for Drafting Agent node functions."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.drafting_nodes import (
    assemble_document_node,
    draft_sections_node,
    gather_provisions_node,
    generate_affidavit_node,
    resolve_template_node,
    revise_section_node,
    verify_final_node,
    verify_precedents_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Create a minimal DraftingState dict with defaults."""
    base = {
        "doc_type": "bail_application",
        "case_facts": "The accused was arrested on 01.01.2024 for offences under S.420 IPC.",
        "relevant_precedents": [],
        "additional_context": {
            "accused_name": "Ram Kumar",
            "fir_number": "FIR No. 123/2024",
            "police_station": "PS Sadar",
            "offences_charged": "S.420, S.468 IPC",
        },
        "target_court": "Delhi High Court",
        "template": {},
        "statutory_provisions": [],
        "verified_precedents": [],
        "section_drafts": {},
        "full_draft": "",
        "revision_feedback": "",

        "messages": [],
        "iteration": 0,
        "error": "",
    }
    base.update(overrides)
    return base


def _make_llm(**overrides) -> AsyncMock:
    """Create a mock LLMProvider."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="")
    llm.generate_structured = AsyncMock(return_value={})
    for k, v in overrides.items():
        setattr(llm, k, v)
    return llm


# ---------------------------------------------------------------------------
# resolve_template_node
# ---------------------------------------------------------------------------


class TestResolveTemplateNode:
    @pytest.mark.asyncio
    async def test_returns_template_dict_for_valid_doc_type(self) -> None:
        state = _make_state(doc_type="bail_application")
        result = await resolve_template_node(state)

        assert "template" in result
        template = result["template"]
        assert template["doc_type"] == "bail_application"
        assert template["display_name"] == "Bail Application (S.439 CrPC)"
        assert isinstance(template["sections"], tuple)
        assert len(template["sections"]) > 0
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_doc_type(self) -> None:
        state = _make_state(doc_type="")
        result = await resolve_template_node(state)

        assert "error" in result
        assert "Missing required field" in result["error"]
        assert "doc_type" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_doc_type(self) -> None:
        state = _make_state(doc_type="nonexistent_document_type")
        result = await resolve_template_node(state)

        assert "error" in result
        assert "Unknown document type" in result["error"]
        assert "nonexistent_document_type" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_required_fields(self) -> None:
        # bail_application requires accused_name, fir_number, police_station, offences_charged
        state = _make_state(
            doc_type="bail_application",
            additional_context={
                "accused_name": "Ram Kumar",
                # fir_number, police_station, offences_charged are missing
            },
        )
        result = await resolve_template_node(state)

        assert "error" in result
        assert "Missing required fields" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_template_with_all_expected_keys(self) -> None:
        state = _make_state(doc_type="writ_petition_226")
        result = await resolve_template_node(state)

        # writ_petition_226 needs petitioner_details, respondent_details, fundamental_right_violated
        # but state has bail_application context -- should raise missing fields error
        assert "error" in result

    @pytest.mark.asyncio
    async def test_returns_template_for_writ_petition_with_correct_fields(self) -> None:
        state = _make_state(
            doc_type="writ_petition_226",
            additional_context={
                "petitioner_details": "Ram Lal, resident of Delhi",
                "respondent_details": "State of Delhi",
                "fundamental_right_violated": "Article 21",
            },
        )
        result = await resolve_template_node(state)

        assert "template" in result
        assert result["template"]["doc_type"] == "writ_petition_226"
        assert "error" not in result


# ---------------------------------------------------------------------------
# gather_provisions_node
# ---------------------------------------------------------------------------


class TestGatherProvisionsNode:
    @pytest.mark.asyncio
    async def test_returns_provisions_from_llm(self) -> None:
        provisions_json = (
            '[{"act": "Code of Criminal Procedure, 1973", '
            '"section": "S.439", '
            '"description": "Bail by High Court or Sessions Court", '
            '"current": true}]'
        )
        llm = _make_llm()
        llm.generate = AsyncMock(return_value=provisions_json)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("CrPC",)]
        db = AsyncMock()
        db.execute.return_value = mock_result

        state = _make_state(
            template={
                "display_name": "Bail Application (S.439 CrPC)",
                "statutory_basis": "Section 439, Code of Criminal Procedure, 1973",
            },
        )

        result = await gather_provisions_node(state, llm, db)

        assert "statutory_provisions" in result
        provisions = result["statutory_provisions"]
        assert len(provisions) == 1
        assert provisions[0]["act"] == "Code of Criminal Procedure, 1973"
        assert provisions[0]["section"] == "S.439"
        assert provisions[0]["current"] is True

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_case_facts(self) -> None:
        llm = _make_llm()
        db = AsyncMock()
        state = _make_state(case_facts="")

        result = await gather_provisions_node(state, llm, db)

        assert result == {"statutory_provisions": []}
        llm.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_db_exception_gracefully(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(return_value="[]")
        db = AsyncMock()
        db.execute.side_effect = RuntimeError("DB connection error")

        state = _make_state(
            template={
                "display_name": "Bail Application",
                "statutory_basis": "Section 439, CrPC",
            },
        )

        # Should not raise; DB failure is swallowed and LLM still queried
        result = await gather_provisions_node(state, llm, db)

        assert "statutory_provisions" in result
        assert result["statutory_provisions"] == []

    @pytest.mark.asyncio
    async def test_validates_provision_keys(self) -> None:
        """Each provision must have act, section, description, current keys."""
        provisions_json = (
            '[{"act": "IPC", "section": "420", "description": "Cheating", "current": true},'
            '{"missing_fields": true}]'
        )
        llm = _make_llm()
        llm.generate = AsyncMock(return_value=provisions_json)

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        state = _make_state(
            template={"display_name": "Test", "statutory_basis": "IPC"},
        )

        result = await gather_provisions_node(state, llm, db)

        # Both entries should be present (second gets empty defaults)
        provisions = result["statutory_provisions"]
        assert len(provisions) == 2
        assert provisions[0]["act"] == "IPC"
        assert provisions[0]["section"] == "420"
        # Second entry has missing keys filled with defaults
        assert provisions[1]["act"] == ""
        assert provisions[1]["section"] == ""
        assert provisions[1]["current"] is True


# ---------------------------------------------------------------------------
# verify_precedents_node
# ---------------------------------------------------------------------------


class TestVerifyPrecedentsNode:
    @pytest.mark.asyncio
    async def test_tags_precedents_as_verified_or_unverified(self) -> None:
        precedents = [
            {"citation": "(2017) 10 SCC 1", "title": "Verified Case"},
            {"citation": "(2099) 1 SCC 999", "title": "Unverified Case"},
        ]
        state = _make_state(relevant_precedents=precedents)

        with patch(
            "app.core.agents.nodes.drafting_nodes.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify:
            # Only the first citation is "verified"
            mock_verify.return_value = (["(2017) 10 SCC 1"], ["(2099) 1 SCC 999"])

            db = AsyncMock()
            result = await verify_precedents_node(state, db)

        assert "verified_precedents" in result
        verified = result["verified_precedents"]
        assert len(verified) == 2

        verified_map = {p["citation"]: p for p in verified}
        assert verified_map["(2017) 10 SCC 1"]["verified"] is True
        assert verified_map["(2099) 1 SCC 999"]["verified"] is False

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_precedents(self) -> None:
        state = _make_state(relevant_precedents=[])
        db = AsyncMock()
        result = await verify_precedents_node(state, db)

        assert result == {"verified_precedents": []}

    @pytest.mark.asyncio
    async def test_skips_precedents_without_citation(self) -> None:
        """Precedents without a citation key should still appear but be unverified."""
        precedents = [
            {"title": "No Citation Case"},
        ]
        state = _make_state(relevant_precedents=precedents)

        with patch(
            "app.core.agents.nodes.drafting_nodes.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = ([], [])
            db = AsyncMock()
            result = await verify_precedents_node(state, db)

        # The call to verify_citations_against_db is skipped (no citations to verify)
        # The precedent still appears but with verified=False
        verified = result["verified_precedents"]
        assert len(verified) == 1
        assert verified[0]["verified"] is False

    @pytest.mark.asyncio
    async def test_handles_verify_exception_gracefully(self) -> None:
        precedents = [{"citation": "(2020) 5 SCC 100", "title": "Test Case"}]
        state = _make_state(relevant_precedents=precedents)

        with patch(
            "app.core.agents.nodes.drafting_nodes.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.side_effect = RuntimeError("DB error")
            db = AsyncMock()
            result = await verify_precedents_node(state, db)

        # Should not raise; precedent is tagged as unverified
        verified = result["verified_precedents"]
        assert len(verified) == 1
        assert verified[0]["verified"] is False


# ---------------------------------------------------------------------------
# draft_sections_node
# ---------------------------------------------------------------------------


class TestDraftSectionsNode:
    @pytest.mark.asyncio
    async def test_drafts_all_template_sections(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(return_value="Draft content for section.")

        state = _make_state(
            template={
                "sections": ["facts_of_the_case", "grounds_for_bail", "prayer"],
                "display_name": "Bail Application",
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
            },
        )

        result = await draft_sections_node(state, llm)

        assert "section_drafts" in result
        drafts = result["section_drafts"]
        assert set(drafts.keys()) == {"facts_of_the_case", "grounds_for_bail", "prayer"}
        assert llm.generate.await_count == 3
        for section_text in drafts.values():
            # Draft may have citation density warnings appended
            assert section_text.startswith("Draft content for section.")

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_sections(self) -> None:
        llm = _make_llm()
        state = _make_state(template={"sections": []})

        result = await draft_sections_node(state, llm)

        assert result == {"section_drafts": {}}
        llm.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_llm_exception_for_individual_section(self) -> None:
        call_count = 0

        async def flaky_generate(**kwargs) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("LLM timeout")
            return "Good draft content."

        llm = _make_llm()
        llm.generate = flaky_generate

        state = _make_state(
            template={
                "sections": ["facts_of_the_case", "grounds_for_bail", "prayer"],
                "display_name": "Bail Application",
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
            },
        )

        result = await draft_sections_node(state, llm)

        drafts = result["section_drafts"]
        # All three sections should be present
        assert set(drafts.keys()) == {"facts_of_the_case", "grounds_for_bail", "prayer"}
        # Second section should have an error placeholder
        assert "[Error drafting" in drafts["grounds_for_bail"]
        # Other sections succeed
        assert drafts["facts_of_the_case"] == "Good draft content."
        assert drafts["prayer"] == "Good draft content."

    @pytest.mark.asyncio
    async def test_uses_fallback_system_prompt_for_unknown_prompt_key(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(return_value="Draft text.")

        state = _make_state(
            template={
                "sections": ["facts"],
                "display_name": "Unknown Document",
                "prompt_key": "UNKNOWN_PROMPT_KEY",
            },
        )

        # Should not raise; fallback generic prompt is used
        result = await draft_sections_node(state, llm)
        assert "section_drafts" in result
        assert "facts" in result["section_drafts"]

    @pytest.mark.asyncio
    async def test_includes_case_facts_in_prompt(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(return_value="Section text.")

        state = _make_state(
            case_facts="The accused was found near the crime scene.",
            template={
                "sections": ["facts_of_the_case"],
                "display_name": "Bail Application",
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
            },
        )

        await draft_sections_node(state, llm)

        call_kwargs = llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "accused" in prompt


# ---------------------------------------------------------------------------
# assemble_document_node
# ---------------------------------------------------------------------------


class TestAssembleDocumentNode:
    @pytest.mark.asyncio
    async def test_assembles_sections_into_full_draft(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(return_value="Formatted full document.")

        state = _make_state(
            template={
                "sections": ["facts_of_the_case", "prayer"],
                "display_name": "Bail Application",
                "court_header": "IN THE HIGH COURT OF {court}",
            },
            section_drafts={
                "facts_of_the_case": "Ram Kumar was arrested.",
                "prayer": "It is humbly prayed that bail be granted.",
            },
            target_court="Delhi High Court",
        )

        result = await assemble_document_node(state, llm)

        assert "full_draft" in result
        assert result["full_draft"].startswith("Formatted full document.")
        llm.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_section_drafts(self) -> None:
        llm = _make_llm()
        state = _make_state(section_drafts={})

        result = await assemble_document_node(state, llm)

        assert result == {"full_draft": ""}
        llm.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_includes_court_header_in_prompt(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(return_value="Full document.")

        state = _make_state(
            template={
                "sections": ["facts"],
                "display_name": "Bail Application",
                "court_header": "IN THE HIGH COURT OF {court}",
            },
            section_drafts={"facts": "Some facts."},
            target_court="Bombay High Court",
        )

        await assemble_document_node(state, llm)

        call_kwargs = llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Bombay High Court" in prompt

    @pytest.mark.asyncio
    async def test_falls_back_to_raw_text_on_llm_failure(self) -> None:
        llm = _make_llm()
        llm.generate = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        state = _make_state(
            template={
                "sections": ["facts_of_the_case", "prayer"],
                "display_name": "Bail Application",
                "court_header": "IN THE HIGH COURT OF {court}",
            },
            section_drafts={
                "facts_of_the_case": "Ram Kumar was arrested.",
                "prayer": "It is humbly prayed that bail be granted.",
            },
            target_court="Delhi High Court",
        )

        result = await assemble_document_node(state, llm)

        assert "full_draft" in result
        # Should fall back to raw assembled text, not raise
        assert "Ram Kumar was arrested" in result["full_draft"]
        assert "bail be granted" in result["full_draft"]

    @pytest.mark.asyncio
    async def test_assembles_sections_in_template_order(self) -> None:
        llm = _make_llm()
        captured_prompts: list[str] = []

        async def capture_generate(**kwargs) -> str:
            captured_prompts.append(kwargs.get("prompt", ""))
            return "Assembled document."

        llm.generate = capture_generate

        state = _make_state(
            template={
                "sections": ["court_header", "facts", "prayer"],
                "display_name": "Legal Document",
                "court_header": "",
            },
            section_drafts={
                "prayer": "Prayer content.",
                "court_header": "Header content.",
                "facts": "Facts content.",
            },
        )

        await assemble_document_node(state, llm)

        prompt = captured_prompts[0]
        # Verify sections appear in the correct template order in the prompt
        header_pos = prompt.index("COURT_HEADER") if "COURT_HEADER" in prompt else -1
        facts_pos = prompt.index("FACTS") if "FACTS" in prompt else -1
        prayer_pos = prompt.index("PRAYER") if "PRAYER" in prompt else -1
        assert header_pos < facts_pos < prayer_pos


# ---------------------------------------------------------------------------
# revise_section_node
# ---------------------------------------------------------------------------


class TestReviseSectionNode:
    @pytest.mark.asyncio
    async def test_revises_target_section(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Revised grounds for bail content."

        state = _make_state(
            revision_feedback="grounds_for_bail: Please strengthen the bail grounds.",
            template={
                "sections": ["facts_of_the_case", "grounds_for_bail", "prayer"],
                "display_name": "Bail Application",
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
                "court_header": "IN THE HIGH COURT OF {court}",
            },
            section_drafts={
                "facts_of_the_case": "Original facts.",
                "grounds_for_bail": "Original grounds.",
                "prayer": "Original prayer.",
            },
            full_draft="Original full draft.",
        )

        result = await revise_section_node(state, llm)

        assert "section_drafts" in result
        # Reassembly is now handled by the assemble node, not revise
        assert "full_draft" not in result
        # Target section is updated
        assert result["section_drafts"]["grounds_for_bail"] == "Revised grounds for bail content."
        # Other sections unchanged
        assert result["section_drafts"]["facts_of_the_case"] == "Original facts."

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_no_feedback(self) -> None:
        llm = _make_llm()
        state = _make_state(
            revision_feedback="",
            section_drafts={"facts": "Some facts."},
            full_draft="Existing full draft.",
        )

        result = await revise_section_node(state, llm)

        assert result["section_drafts"] == {"facts": "Some facts."}
        assert "full_draft" not in result
        llm.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_detects_section_from_feedback_text(self) -> None:
        """When feedback mentions a section name (not prefixed), that section is targeted."""
        llm = _make_llm()
        llm.generate.return_value = "Improved prayer section."

        state = _make_state(
            revision_feedback="Please rewrite the prayer section to be more specific.",
            template={
                "sections": ["facts_of_the_case", "grounds_for_bail", "prayer"],
                "display_name": "Bail Application",
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
                "court_header": "",
            },
            section_drafts={
                "facts_of_the_case": "Facts.",
                "grounds_for_bail": "Grounds.",
                "prayer": "Original prayer.",
            },
            full_draft="Original full draft.",
        )

        result = await revise_section_node(state, llm)

        # "prayer" section should be the one revised
        assert result["section_drafts"]["prayer"] == "Improved prayer section."

    @pytest.mark.asyncio
    async def test_defaults_to_first_section_when_section_unknown(self) -> None:
        """When feedback does not match any section name, default to first section."""
        llm = _make_llm()
        llm.generate.return_value = "Revised first section."

        state = _make_state(
            revision_feedback="Make it more persuasive overall.",
            template={
                "sections": ["facts_of_the_case", "prayer"],
                "display_name": "Bail Application",
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
                "court_header": "",
            },
            section_drafts={
                "facts_of_the_case": "Original facts.",
                "prayer": "Original prayer.",
            },
            full_draft="Original full draft.",
        )

        result = await revise_section_node(state, llm)

        # First section (facts_of_the_case) should be revised
        assert result["section_drafts"]["facts_of_the_case"] == "Revised first section."


# ---------------------------------------------------------------------------
# verify_final_node
# ---------------------------------------------------------------------------


class TestVerifyFinalNode:
    @pytest.mark.asyncio
    async def test_passes_through_clean_draft(self) -> None:
        state = _make_state(full_draft="A clean legal document with no citations.")
        db = AsyncMock()

        with patch(
            "app.core.agents.nodes.common.verify_case_ids",
            new_callable=AsyncMock,
        ) as mock_verify_ids, patch(
            "app.core.agents.nodes.common.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify_cites:
            mock_verify_ids.return_value = set()
            mock_verify_cites.return_value = ([], [])

            result = await verify_final_node(state, db)

        assert "full_draft" in result
        assert "Citation Verification Warning" not in result["full_draft"]
        assert "Human-Readable Citation Warning" not in result["full_draft"]
        assert "Ungrounded Citation Warning" not in result["full_draft"]

    @pytest.mark.asyncio
    async def test_appends_warning_for_invalid_uuid(self) -> None:
        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        state = _make_state(
            full_draft=f"This document relies on case {uid} for the proposition."
        )
        db = AsyncMock()

        with patch(
            "app.core.agents.nodes.common.verify_case_ids",
            new_callable=AsyncMock,
        ) as mock_verify_ids, patch(
            "app.core.agents.nodes.common.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify_cites:
            # UUID not found in DB
            mock_verify_ids.return_value = set()
            mock_verify_cites.return_value = ([], [])

            result = await verify_final_node(state, db)

        assert "Citation Verification Warning" in result["full_draft"]
        assert uid in result["full_draft"]

    @pytest.mark.asyncio
    async def test_appends_warning_for_unverified_human_readable_citation(self) -> None:
        state = _make_state(
            full_draft="The court relied on (2099) 1 SCC 999 in this matter."
        )
        db = AsyncMock()

        with patch(
            "app.core.agents.nodes.common.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify_cites:
            # Citation not found in DB
            mock_verify_cites.return_value = ([], ["(2099) 1 SCC 999"])

            result = await verify_final_node(state, db)

        assert "Human-Readable Citation Warning" in result["full_draft"]
        assert "(2099) 1 SCC 999" in result["full_draft"]

    @pytest.mark.asyncio
    async def test_appends_ungrounded_warning_for_citations_not_in_precedents(self) -> None:
        state = _make_state(
            full_draft="The court relied on (2017) 10 SCC 1 in this matter.",
            verified_precedents=[
                {"citation": "(2020) 5 SCC 200", "title": "Different Case", "verified": True},
            ],
        )
        db = AsyncMock()

        with patch(
            "app.core.agents.nodes.common.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify_cites:
            # Citation found in DB (human-readable check passes)
            mock_verify_cites.return_value = (["(2017) 10 SCC 1"], [])

            result = await verify_final_node(state, db)

        # (2017) 10 SCC 1 is not in verified_precedents, so grounding check flags it
        assert "Ungrounded Citation Warning" in result["full_draft"]
        assert "(2017) 10 SCC 1" in result["full_draft"]

    @pytest.mark.asyncio
    async def test_no_ungrounded_warning_when_citation_in_precedents(self) -> None:
        state = _make_state(
            full_draft="The court relied on (2017) 10 SCC 1 in this matter.",
            verified_precedents=[
                {"citation": "(2017) 10 SCC 1", "title": "Grounded Case", "verified": True},
            ],
        )
        db = AsyncMock()

        with patch(
            "app.core.agents.nodes.common.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify_cites:
            mock_verify_cites.return_value = (["(2017) 10 SCC 1"], [])

            result = await verify_final_node(state, db)

        assert "Ungrounded Citation Warning" not in result["full_draft"]

    @pytest.mark.asyncio
    async def test_returns_empty_full_draft_unchanged(self) -> None:
        state = _make_state(full_draft="")
        db = AsyncMock()
        result = await verify_final_node(state, db)
        assert result == {"full_draft": ""}


# ---------------------------------------------------------------------------
# resolve_template_node — V2 (court profiles + primary code)
# ---------------------------------------------------------------------------


class TestResolveTemplateV2:
    @pytest.mark.asyncio
    async def test_resolve_template_sets_court_profile(self) -> None:
        state = _make_state(target_court="Supreme Court")
        result = await resolve_template_node(state)
        assert "court_profile" in result
        assert result["court_profile"]["court_id"] == "supreme_court"

    @pytest.mark.asyncio
    async def test_resolve_template_default_court_profile(self) -> None:
        state = _make_state(target_court="")
        result = await resolve_template_node(state)
        assert result["court_profile"]["court_id"] == "default"

    @pytest.mark.asyncio
    async def test_resolve_template_sets_primary_code_new(self) -> None:
        state = _make_state(additional_context={
            "accused_name": "Test", "fir_number": "123/2025",
            "police_station": "Test PS", "offences_charged": "S.420 IPC",
            "fir_date": "2025-01-15",
        })
        result = await resolve_template_node(state)
        assert result["primary_code"] == "new"

    @pytest.mark.asyncio
    async def test_resolve_template_sets_primary_code_old(self) -> None:
        state = _make_state(additional_context={
            "accused_name": "Test", "fir_number": "123/2023",
            "police_station": "Test PS", "offences_charged": "S.420 IPC",
            "fir_date": "2023-06-01",
        })
        result = await resolve_template_node(state)
        assert result["primary_code"] == "old"


# ---------------------------------------------------------------------------
# gather_provisions_node — V2 (amendment mappings)
# ---------------------------------------------------------------------------


class TestGatherProvisionsV2:
    @pytest.mark.asyncio
    async def test_provisions_include_new_code_mapping(self) -> None:
        """S.438 CrPC should get new_code_section=482, new_code_act=BNSS."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps([
            {"act": "CrPC", "section": "438", "description": "Anticipatory bail", "current": True},
        ])
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=lambda: [])

        state = _make_state(
            template={"display_name": "Test", "statutory_basis": "S.438 CrPC"},
            primary_code="new",
        )
        result = await gather_provisions_node(state, mock_llm, mock_db)
        provisions = result["statutory_provisions"]
        assert len(provisions) >= 1
        found = [p for p in provisions if p.get("section") == "438"]
        assert len(found) == 1
        assert found[0].get("new_code_section") == "482"
        assert found[0].get("new_code_act") == "BNSS"


# ---------------------------------------------------------------------------
# draft_sections_node — V2 (CRAC + amendment context)
# ---------------------------------------------------------------------------


class TestDraftSectionsV2:
    @pytest.mark.asyncio
    async def test_crac_instruction_used_for_advocacy_template(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Draft content here"
        state = _make_state(
            template={
                "display_name": "Bail Application",
                "sections": ["grounds_for_bail"],
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
                "argument_style": "crac",
            },
            verified_precedents=[],
            statutory_provisions=[],
            primary_code="new",
        )
        await draft_sections_node(state, mock_llm)
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "CRAC" in prompt or "CONCLUSION" in prompt or "Lead with" in prompt

    @pytest.mark.asyncio
    async def test_irac_instruction_used_for_factual_template(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Draft content here"
        state = _make_state(
            doc_type="plaint",
            template={
                "display_name": "Plaint",
                "sections": ["facts_of_the_case"],
                "prompt_key": "DRAFT_PLAINT_SYSTEM",
                "argument_style": "irac",
            },
            verified_precedents=[],
            statutory_provisions=[],
            primary_code="new",
        )
        await draft_sections_node(state, mock_llm)
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "IRAC" in prompt or "ISSUE" in prompt

    @pytest.mark.asyncio
    async def test_new_code_context_injected(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Draft content"
        state = _make_state(
            template={
                "display_name": "Test",
                "sections": ["grounds"],
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
                "argument_style": "crac",
            },
            verified_precedents=[],
            statutory_provisions=[],
            primary_code="new",
        )
        await draft_sections_node(state, mock_llm)
        prompt = mock_llm.generate.call_args.kwargs.get("prompt", "")
        assert "BNS/BNSS/BSA" in prompt or "post-1 July 2024" in prompt


# ---------------------------------------------------------------------------
# verify_precedents_node — V2 (overruled precedent shield)
# ---------------------------------------------------------------------------


class TestVerifyPrecedentsV2:
    @pytest.mark.asyncio
    async def test_overruled_precedent_tagged(self) -> None:
        mock_graph = AsyncMock()
        mock_graph.get_neighbors.return_value = {
            "nodes": [{"text": "The decision in X v Y was expressly overruled by this Court."}]
        }
        state = _make_state(
            relevant_precedents=[
                {"citation": "2020 SCC 123", "title": "X v Y", "case_id": "case-1"}
            ],
        )

        with patch(
            "app.core.agents.nodes.drafting_nodes.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = (["2020 SCC 123"], [])
            db = AsyncMock()
            result = await verify_precedents_node(state, db, mock_graph)

        assert result["verified_precedents"][0]["treatment"] == "overruled"

    @pytest.mark.asyncio
    async def test_good_law_precedent_tagged(self) -> None:
        mock_graph = AsyncMock()
        mock_graph.get_neighbors.return_value = {
            "nodes": [{"text": "Following the ratio in X v Y, we hold that..."}]
        }
        state = _make_state(
            relevant_precedents=[
                {"citation": "2020 SCC 123", "title": "X v Y", "case_id": "case-1"}
            ],
        )

        with patch(
            "app.core.agents.nodes.drafting_nodes.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = (["2020 SCC 123"], [])
            db = AsyncMock()
            result = await verify_precedents_node(state, db, mock_graph)

        assert result["verified_precedents"][0]["treatment"] == "good_law"

    @pytest.mark.asyncio
    async def test_no_graph_store_defaults_to_good_law(self) -> None:
        state = _make_state(
            relevant_precedents=[
                {"citation": "2020 SCC 123", "title": "X v Y"}
            ],
        )

        with patch(
            "app.core.agents.nodes.drafting_nodes.verify_citations_against_db",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = ([], [])
            db = AsyncMock()
            result = await verify_precedents_node(state, db, None)

        assert result["verified_precedents"][0]["treatment"] == "good_law"


# ---------------------------------------------------------------------------
# gather_provisions_node — V2 (citation graph suggestions)
# ---------------------------------------------------------------------------


class TestGatherProvisionsCitationGraph:
    @pytest.mark.asyncio
    async def test_suggests_precedents_from_graph(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "[]"
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=lambda: [])

        mock_graph = AsyncMock()

        state = _make_state(
            template={"display_name": "Test", "statutory_basis": "S.438 CrPC"},
            relevant_precedents=[
                {"case_id": "case-1", "citation": "2020 SCC 1", "title": "A v B"},
            ],
        )

        with patch(
            "app.core.agents.nodes.common.get_citation_neighbors",
            new_callable=AsyncMock,
        ) as mock_neighbors:
            mock_neighbors.return_value = [
                {"case_id": "case-2", "title": "C v D", "citation": "2021 SCC 5"},
            ]
            result = await gather_provisions_node(state, mock_llm, mock_db, mock_graph)

        assert "suggested_precedents" in result
        assert len(result["suggested_precedents"]) == 1
        assert result["suggested_precedents"][0]["source"] == "citation_graph"

    @pytest.mark.asyncio
    async def test_no_suggestions_without_graph_store(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "[]"
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=lambda: [])

        state = _make_state(
            template={"display_name": "Test", "statutory_basis": "S.438 CrPC"},
            relevant_precedents=[
                {"case_id": "case-1", "citation": "2020 SCC 1", "title": "A v B"},
            ],
        )

        result = await gather_provisions_node(state, mock_llm, mock_db, None)

        assert "suggested_precedents" not in result


# ---------------------------------------------------------------------------
# draft_sections_node — V2 (statute text injection)
# ---------------------------------------------------------------------------


class TestDraftSectionsStatuteInjection:
    @pytest.mark.asyncio
    async def test_statute_text_injected_for_substantive_section(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Under Section 438 CrPC, the accused seeks anticipatory bail."

        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [0.1] * 1536

        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [
            {"text": "Section 438. Direction for grant of bail to person apprehending arrest."}
        ]

        state = _make_state(
            template={
                "display_name": "Bail Application",
                "sections": ["grounds_for_bail"],
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
            },
            verified_precedents=[],
            statutory_provisions=[],
        )

        result = await draft_sections_node(state, mock_llm, mock_vector_store, mock_embedder)

        draft = result["section_drafts"]["grounds_for_bail"]
        assert "Section 438" in draft
        assert "Direction for grant of bail" in draft

    @pytest.mark.asyncio
    async def test_no_injection_for_non_substantive_section(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Prayer text referencing Section 438 CrPC."

        mock_embedder = AsyncMock()
        mock_vector_store = AsyncMock()

        state = _make_state(
            template={
                "display_name": "Bail Application",
                "sections": ["prayer"],
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
            },
            verified_precedents=[],
            statutory_provisions=[],
        )

        result = await draft_sections_node(state, mock_llm, mock_vector_store, mock_embedder)

        # embedder/vector_store should not have been called for non-substantive "prayer"
        mock_embedder.embed.assert_not_awaited()
        mock_vector_store.search.assert_not_awaited()


# ---------------------------------------------------------------------------
# generate_affidavit_node
# ---------------------------------------------------------------------------


class TestAffidavitGeneration:
    @pytest.mark.asyncio
    async def test_affidavit_generated_when_required(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "I solemnly affirm and state on oath..."
        state = _make_state(
            template={"requires_affidavit": True, "display_name": "Bail Application"},
            full_draft="Full draft content here.",
            additional_context={
                "accused_name": "John Doe",
                "fir_number": "1",
                "police_station": "PS",
                "offences_charged": "420",
            },
            target_court="Delhi High Court",
        )
        result = await generate_affidavit_node(state, mock_llm)
        assert "affidavit_draft" in result
        assert result["affidavit_draft"].strip()

    @pytest.mark.asyncio
    async def test_no_affidavit_when_not_required(self) -> None:
        mock_llm = AsyncMock()
        state = _make_state(
            template={"requires_affidavit": False, "display_name": "Legal Notice"},
            full_draft="Notice content.",
        )
        result = await generate_affidavit_node(state, mock_llm)
        assert result["affidavit_draft"] == ""
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_affidavit_uses_deponent_name(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Affidavit text"
        state = _make_state(
            template={"requires_affidavit": True, "display_name": "Writ Petition"},
            full_draft="Draft.",
            additional_context={
                "petitioner_details": "Ram Kumar",
                "respondent_details": "State",
                "fundamental_right_violated": "Art.21",
            },
        )
        result = await generate_affidavit_node(state, mock_llm)
        prompt = mock_llm.generate.call_args.kwargs.get("prompt", "")
        assert "Ram Kumar" in prompt
