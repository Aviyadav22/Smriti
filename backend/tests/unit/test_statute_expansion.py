"""Tests for statute cross-reference expansion in search queries.

Verifies that old-law references (IPC, CrPC, Evidence Act) are expanded to
include new-law equivalents (BNS, BNSS, BSA) and vice versa.
"""

from __future__ import annotations

import pytest

from app.core.search.query import expand_statute_references


# ---------------------------------------------------------------------------
# IPC -> BNS (forward)
# ---------------------------------------------------------------------------


class TestIPCToBNSExpansion:
    """Old IPC references should expand to include BNS equivalents."""

    def test_section_302_ipc_expands_to_bns_103(self) -> None:
        result = expand_statute_references("Section 302 IPC")
        assert "Section 103 BNS" in result
        assert "Section 302 IPC" in result

    def test_section_420_ipc_expands_to_bns_318(self) -> None:
        result = expand_statute_references("Section 420 IPC")
        assert "Section 318 BNS" in result

    def test_section_with_indian_penal_code_full_name(self) -> None:
        result = expand_statute_references("Section 376 Indian Penal Code")
        assert "Section 63 BNS" in result

    def test_section_498a_ipc(self) -> None:
        result = expand_statute_references("Section 498A IPC")
        assert "Section 85 BNS" in result

    def test_case_insensitive_ipc(self) -> None:
        result = expand_statute_references("section 302 ipc")
        assert "Section 103 BNS" in result

    def test_section_34_ipc(self) -> None:
        result = expand_statute_references("Section 34 IPC")
        assert "Section 3(5) BNS" in result

    def test_section_with_of_the_prefix(self) -> None:
        result = expand_statute_references("Section 307 of the IPC")
        assert "Section 109 BNS" in result

    def test_multiple_ipc_sections(self) -> None:
        result = expand_statute_references("Section 302 IPC and Section 120B IPC")
        assert "Section 103 BNS" in result
        assert "Section 61 BNS" in result


# ---------------------------------------------------------------------------
# BNS -> IPC (reverse)
# ---------------------------------------------------------------------------


class TestBNSToIPCExpansion:
    """New BNS references should expand to include IPC equivalents."""

    def test_section_103_bns_expands_to_ipc_302(self) -> None:
        result = expand_statute_references("Section 103 BNS")
        assert "Section 302 IPC" in result
        assert "Section 103 BNS" in result

    def test_section_318_bns_expands_to_ipc_420(self) -> None:
        result = expand_statute_references("Section 318 BNS")
        assert "Section 420 IPC" in result

    def test_bharatiya_nyaya_sanhita_full_name(self) -> None:
        result = expand_statute_references("Section 63 Bharatiya Nyaya Sanhita")
        assert "Section 376 IPC" in result

    def test_case_insensitive_bns(self) -> None:
        result = expand_statute_references("section 103 bns")
        assert "Section 302 IPC" in result


# ---------------------------------------------------------------------------
# CrPC -> BNSS (forward)
# ---------------------------------------------------------------------------


class TestCrPCToBNSSExpansion:
    """Old CrPC references should expand to include BNSS equivalents."""

    def test_section_438_crpc(self) -> None:
        result = expand_statute_references("Section 438 CrPC")
        assert "Section 482 BNSS" in result

    def test_section_482_crpc(self) -> None:
        result = expand_statute_references("Section 482 CrPC")
        assert "Section 528 BNSS" in result

    def test_section_154_code_of_criminal_procedure(self) -> None:
        result = expand_statute_references("Section 154 Code of Criminal Procedure")
        assert "Section 173 BNSS" in result

    def test_section_125_crpc(self) -> None:
        result = expand_statute_references("Section 125 CrPC")
        assert "Section 144 BNSS" in result


# ---------------------------------------------------------------------------
# BNSS -> CrPC (reverse)
# ---------------------------------------------------------------------------


class TestBNSSToCrPCExpansion:
    """New BNSS references should expand to include CrPC equivalents."""

    def test_section_482_bnss(self) -> None:
        result = expand_statute_references("Section 482 BNSS")
        assert "Section 438 CrPC" in result

    def test_section_528_bnss(self) -> None:
        result = expand_statute_references("Section 528 BNSS")
        assert "Section 482 CrPC" in result

    def test_bharatiya_nagarik_suraksha_sanhita_full_name(self) -> None:
        result = expand_statute_references(
            "Section 173 Bharatiya Nagarik Suraksha Sanhita"
        )
        assert "Section 154 CrPC" in result


# ---------------------------------------------------------------------------
# Evidence Act -> BSA (forward)
# ---------------------------------------------------------------------------


class TestEvidenceToBSAExpansion:
    """Old Evidence Act references should expand to include BSA equivalents."""

    def test_section_65b_evidence_act(self) -> None:
        result = expand_statute_references("Section 65B Indian Evidence Act")
        assert "Section 63 BSA" in result

    def test_section_45_evidence_act(self) -> None:
        result = expand_statute_references("Section 45 Evidence Act")
        assert "Section 39 BSA" in result

    def test_section_27_iea(self) -> None:
        result = expand_statute_references("Section 27 IEA")
        assert "Section 25 BSA" in result


# ---------------------------------------------------------------------------
# BSA -> Evidence Act (reverse)
# ---------------------------------------------------------------------------


class TestBSAToEvidenceExpansion:
    """New BSA references should expand to include Evidence Act equivalents."""

    def test_section_63_bsa(self) -> None:
        result = expand_statute_references("Section 63 BSA")
        assert "Section 65B IEA" in result

    def test_bharatiya_sakshya_adhiniyam_full_name(self) -> None:
        result = expand_statute_references("Section 39 Bharatiya Sakshya Adhiniyam")
        assert "Section 45 IEA" in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestStatuteExpansionEdgeCases:
    """Edge cases and no-match scenarios."""

    def test_no_expansion_for_plain_query(self) -> None:
        query = "right to bail in murder cases"
        result = expand_statute_references(query)
        assert result == query

    def test_no_expansion_for_unknown_section(self) -> None:
        query = "Section 999 IPC"
        result = expand_statute_references(query)
        assert result == query

    def test_preserves_original_query(self) -> None:
        query = "Section 302 IPC murder conviction"
        result = expand_statute_references(query)
        assert result.startswith(query)
        assert "Section 103 BNS" in result

    def test_or_separator_format(self) -> None:
        result = expand_statute_references("Section 302 IPC")
        assert " OR " in result

    def test_empty_query(self) -> None:
        result = expand_statute_references("")
        assert result == ""

    def test_section_number_not_matched_without_act_name(self) -> None:
        """Bare section numbers without act names should not be expanded."""
        result = expand_statute_references("Section 302")
        assert result == "Section 302"
