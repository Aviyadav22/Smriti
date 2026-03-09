"""Tests for statute cross-reference expansion in search queries.

Verifies that old-law references (IPC, CrPC, Evidence Act) are expanded to
include new-law equivalents (BNS, BNSS, BSA) and vice versa.
"""

from __future__ import annotations

import pytest

from app.core.search.query import expand_statute_references


def _expanded_str(query: str) -> str:
    """Helper: call expand_statute_references and join into a single string
    matching the old " OR " format for assertion convenience."""
    original, terms = expand_statute_references(query)
    if terms:
        return " OR ".join([original, *terms])
    return original


# ---------------------------------------------------------------------------
# IPC -> BNS (forward)
# ---------------------------------------------------------------------------


class TestIPCToBNSExpansion:
    """Old IPC references should expand to include BNS equivalents."""

    def test_section_302_ipc_expands_to_bns_103(self) -> None:
        result = _expanded_str("Section 302 IPC")
        assert "Section 103 BNS" in result
        assert "Section 302 IPC" in result

    def test_section_420_ipc_expands_to_bns_318_4(self) -> None:
        result = _expanded_str("Section 420 IPC")
        assert "Section 318(4) BNS" in result

    def test_section_with_indian_penal_code_full_name(self) -> None:
        result = _expanded_str("Section 376 Indian Penal Code")
        assert "Section 63 BNS" in result

    def test_section_498a_ipc(self) -> None:
        result = _expanded_str("Section 498A IPC")
        assert "Section 85 BNS" in result

    def test_case_insensitive_ipc(self) -> None:
        result = _expanded_str("section 302 ipc")
        assert "Section 103 BNS" in result

    def test_section_34_ipc(self) -> None:
        result = _expanded_str("Section 34 IPC")
        assert "Section 3(5) BNS" in result

    def test_section_with_of_the_prefix(self) -> None:
        result = _expanded_str("Section 307 of the IPC")
        assert "Section 109 BNS" in result

    def test_multiple_ipc_sections(self) -> None:
        result = _expanded_str("Section 302 IPC and Section 120B IPC")
        assert "Section 103 BNS" in result
        assert "Section 61 BNS" in result


# ---------------------------------------------------------------------------
# BNS -> IPC (reverse)
# ---------------------------------------------------------------------------


class TestBNSToIPCExpansion:
    """New BNS references should expand to include IPC equivalents."""

    def test_section_103_bns_expands_to_ipc_302(self) -> None:
        result = _expanded_str("Section 103 BNS")
        assert "Section 302 IPC" in result
        assert "Section 103 BNS" in result

    def test_section_318_bns_expands_to_ipc_415(self) -> None:
        """BNS 318 is the base cheating section, which maps back to IPC 415."""
        result = _expanded_str("Section 318 BNS")
        assert "Section 415 IPC" in result

    def test_bharatiya_nyaya_sanhita_full_name(self) -> None:
        result = _expanded_str("Section 63 Bharatiya Nyaya Sanhita")
        assert "Section 376 IPC" in result

    def test_case_insensitive_bns(self) -> None:
        result = _expanded_str("section 103 bns")
        assert "Section 302 IPC" in result


# ---------------------------------------------------------------------------
# CrPC -> BNSS (forward)
# ---------------------------------------------------------------------------


class TestCrPCToBNSSExpansion:
    """Old CrPC references should expand to include BNSS equivalents."""

    def test_section_438_crpc(self) -> None:
        result = _expanded_str("Section 438 CrPC")
        assert "Section 482 BNSS" in result

    def test_section_482_crpc(self) -> None:
        result = _expanded_str("Section 482 CrPC")
        assert "Section 528 BNSS" in result

    def test_section_154_code_of_criminal_procedure(self) -> None:
        result = _expanded_str("Section 154 Code of Criminal Procedure")
        assert "Section 173 BNSS" in result

    def test_section_125_crpc(self) -> None:
        result = _expanded_str("Section 125 CrPC")
        assert "Section 144 BNSS" in result


# ---------------------------------------------------------------------------
# BNSS -> CrPC (reverse)
# ---------------------------------------------------------------------------


class TestBNSSToCrPCExpansion:
    """New BNSS references should expand to include CrPC equivalents."""

    def test_section_482_bnss(self) -> None:
        result = _expanded_str("Section 482 BNSS")
        assert "Section 438 CrPC" in result

    def test_section_528_bnss(self) -> None:
        result = _expanded_str("Section 528 BNSS")
        assert "Section 482 CrPC" in result

    def test_bharatiya_nagarik_suraksha_sanhita_full_name(self) -> None:
        result = _expanded_str(
            "Section 173 Bharatiya Nagarik Suraksha Sanhita"
        )
        assert "Section 154 CrPC" in result


# ---------------------------------------------------------------------------
# Evidence Act -> BSA (forward)
# ---------------------------------------------------------------------------


class TestEvidenceToBSAExpansion:
    """Old Evidence Act references should expand to include BSA equivalents."""

    def test_section_65b_evidence_act(self) -> None:
        result = _expanded_str("Section 65B Indian Evidence Act")
        assert "Section 63 BSA" in result

    def test_section_45_evidence_act(self) -> None:
        result = _expanded_str("Section 45 Evidence Act")
        assert "Section 39 BSA" in result

    def test_section_27_iea(self) -> None:
        result = _expanded_str("Section 27 IEA")
        assert "Section 25 BSA" in result


# ---------------------------------------------------------------------------
# BSA -> Evidence Act (reverse)
# ---------------------------------------------------------------------------


class TestBSAToEvidenceExpansion:
    """New BSA references should expand to include Evidence Act equivalents."""

    def test_section_63_bsa(self) -> None:
        result = _expanded_str("Section 63 BSA")
        assert "Section 65B IEA" in result

    def test_bharatiya_sakshya_adhiniyam_full_name(self) -> None:
        result = _expanded_str("Section 39 Bharatiya Sakshya Adhiniyam")
        assert "Section 45 IEA" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestStatuteExpansionEdgeCases:
    """Edge cases and no-match scenarios."""

    def test_no_expansion_for_plain_query(self) -> None:
        query = "right to bail in murder cases"
        original, terms = expand_statute_references(query)
        assert original == query
        assert terms == []

    def test_no_expansion_for_unknown_section(self) -> None:
        query = "Section 999 IPC"
        original, terms = expand_statute_references(query)
        assert original == query
        assert terms == []

    def test_preserves_original_query(self) -> None:
        query = "Section 302 IPC murder conviction"
        original, terms = expand_statute_references(query)
        assert original == query
        assert "Section 103 BNS" in terms

    def test_returns_tuple(self) -> None:
        original, terms = expand_statute_references("Section 302 IPC")
        assert isinstance(original, str)
        assert isinstance(terms, list)
        assert len(terms) > 0

    def test_empty_query(self) -> None:
        original, terms = expand_statute_references("")
        assert original == ""
        assert terms == []

    def test_section_with_sub_section_parens(self) -> None:
        """IPC 420 maps to BNS 318(4); ensure parenthesised sub-section appears."""
        original, terms = expand_statute_references("Section 420 IPC")
        assert "Section 318(4) BNS" in terms

    def test_section_number_not_matched_without_act_name(self) -> None:
        """Bare section numbers without act names should not be expanded."""
        original, terms = expand_statute_references("Section 302")
        assert original == "Section 302"
        assert terms == []


# ---------------------------------------------------------------------------
# Expanded mapping coverage tests
# ---------------------------------------------------------------------------


class TestExpandedIPCMappings:
    """Tests for newly added IPC->BNS mappings covering property, person,
    public order, forgery and general exceptions."""

    def test_ipc_378_theft_to_bns_303(self) -> None:
        result = _expanded_str("Section 378 IPC")
        assert "Section 303 BNS" in result

    def test_ipc_463_forgery_to_bns_336(self) -> None:
        result = _expanded_str("Section 463 IPC")
        assert "Section 336 BNS" in result

    def test_ipc_299_culpable_homicide_to_bns_100(self) -> None:
        result = _expanded_str("Section 299 IPC")
        assert "Section 100 BNS" in result

    def test_ipc_141_unlawful_assembly_to_bns_189(self) -> None:
        result = _expanded_str("Section 141 IPC")
        assert "Section 189 BNS" in result

    def test_ipc_489a_counterfeiting_to_bns_179(self) -> None:
        result = _expanded_str("Section 489A IPC")
        assert "Section 179 BNS" in result

    def test_ipc_96_private_defence_to_bns_34(self) -> None:
        result = _expanded_str("Section 96 IPC")
        assert "Section 34 BNS" in result

    def test_ipc_354d_stalking_to_bns_78(self) -> None:
        result = _expanded_str("Section 354D IPC")
        assert "Section 78 BNS" in result

    def test_ipc_405_cbt_to_bns_316(self) -> None:
        result = _expanded_str("Section 405 IPC")
        assert "Section 316 BNS" in result

    def test_ipc_441_trespass_to_bns_329(self) -> None:
        result = _expanded_str("Section 441 IPC")
        assert "Section 329 BNS" in result

    def test_ipc_107_abetment_to_bns_45(self) -> None:
        result = _expanded_str("Section 107 IPC")
        assert "Section 45 BNS" in result


class TestExpandedCrPCMappings:
    """Tests for newly added CrPC->BNSS mappings."""

    def test_crpc_41a_notice_of_appearance_to_bnss_35_3(self) -> None:
        result = _expanded_str("Section 41A CrPC")
        assert "Section 35(3) BNSS" in result

    def test_crpc_436_bail_to_bnss_478(self) -> None:
        result = _expanded_str("Section 436 CrPC")
        assert "Section 478 BNSS" in result

    def test_crpc_173_chargesheet_to_bnss_193(self) -> None:
        result = _expanded_str("Section 173 CrPC")
        assert "Section 193 BNSS" in result

    def test_crpc_227_discharge_to_bnss_260(self) -> None:
        result = _expanded_str("Section 227 CrPC")
        assert "Section 260 BNSS" in result

    def test_crpc_397_revision_to_bnss_436(self) -> None:
        result = _expanded_str("Section 397 CrPC")
        assert "Section 436 BNSS" in result


class TestExpandedIEAMappings:
    """Tests for newly added IEA->BSA mappings."""

    def test_iea_6_res_gestae_to_bsa_5(self) -> None:
        result = _expanded_str("Section 6 IEA")
        assert "Section 5 BSA" in result

    def test_iea_101_burden_of_proof_to_bsa_95(self) -> None:
        result = _expanded_str("Section 101 IEA")
        assert "Section 95 BSA" in result

    def test_iea_154_hostile_witness_to_bsa_146(self) -> None:
        result = _expanded_str("Section 154 IEA")
        assert "Section 146 BSA" in result

    def test_iea_74_public_documents_to_bsa_68(self) -> None:
        result = _expanded_str("Section 74 IEA")
        assert "Section 68 BSA" in result

    def test_iea_106_burden_of_knowledge_to_bsa_100(self) -> None:
        result = _expanded_str("Section 106 IEA")
        assert "Section 100 BSA" in result
