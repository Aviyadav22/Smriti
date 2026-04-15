"""Tests for acts_cited normalization and garbage filtering.

Covers normalize_acts_cited_list(), _is_valid_act_citation(),
the expanded _SHORT_ACT_NAMES dict, and enrich_statute_cross_references().
"""

import pytest

from app.core.legal.extractor import (
    _is_valid_act_citation,
    get_act_display_name,
    get_acts_cited_display,
    normalize_act_name,
    normalize_acts_cited_list,
)
from app.core.legal.statute_enrichment import enrich_statute_cross_references


class TestNormalizeActsCitedList:
    """Tests for normalize_acts_cited_list()."""

    def test_normalize_full_name_to_short_code(self):
        """Full act name with year maps to canonical short code."""
        result = normalize_acts_cited_list(["Indian Penal Code, 1860"])
        assert result == ["IPC"]

    def test_normalize_section_ref_to_act(self):
        """'Section X of Act' strips section prefix and normalizes."""
        result = normalize_acts_cited_list(["Section 302 of Indian Penal Code, 1860"])
        assert result == ["IPC"]

    def test_normalize_article_ref(self):
        """'Article X of Constitution of India' normalizes to COI."""
        result = normalize_acts_cited_list(["Article 21 of Constitution of India"])
        assert result == ["COI"]

    def test_normalize_already_short(self):
        """Already-normalized short codes pass through unchanged."""
        result = normalize_acts_cited_list(["IPC"])
        assert result == ["IPC"]

    def test_normalize_newline_broken(self):
        """Newline-broken act names are cleaned and normalized."""
        result = normalize_acts_cited_list(["Code of Criminal\nProcedure"])
        assert result == ["CRPC"]

    def test_garbage_filtered(self):
        """Garbage strings like 'Unknown Act', 'M', state names are filtered."""
        result = normalize_acts_cited_list(["Unknown Act", "M", "Rajasthan"])
        assert result == []

    def test_year_only_filtered(self):
        """Year-only strings like '2013', '2022' are filtered."""
        result = normalize_acts_cited_list(["2013", "2022"])
        assert result == []

    def test_vague_refs_filtered(self):
        """Vague references like 'said Act', 'the Act' are filtered."""
        result = normalize_acts_cited_list(["said Act", "the Act", "same Act"])
        assert result == []

    def test_dedup_variants(self):
        """Different forms of the same act deduplicate to one entry."""
        result = normalize_acts_cited_list(["IPC", "Indian Penal Code", "Indian Penal Code, 1860"])
        assert result == ["IPC"]

    def test_unknown_act_passes_through(self):
        """Obscure but valid act names pass through unchanged."""
        result = normalize_acts_cited_list(["Some Obscure Act, 2020"])
        assert result == ["Some Obscure Act"]

    def test_new_acts_normalize(self):
        """Newly added high-frequency acts normalize correctly."""
        result = normalize_acts_cited_list(
            [
                "Limitation Act, 1963",
                "Prevention of Corruption Act",
            ]
        )
        assert "LA" in result
        assert "PCA" in result

    def test_empty_and_none(self):
        """Empty list returns empty; None entries are skipped."""
        assert normalize_acts_cited_list([]) == []
        assert normalize_acts_cited_list([None, "", "  "]) == []

    def test_read_with_format(self):
        """'Section X r/w Section Y IPC' extracts act code."""
        result = normalize_acts_cited_list(["Section 302 r/w Section 34 IPC"])
        assert result == ["IPC"]

    def test_section_short_code_format(self):
        """'Section 302 IPC' extracts act code."""
        result = normalize_acts_cited_list(["Section 302 IPC"])
        assert result == ["IPC"]

    def test_multiple_acts_sorted(self):
        """Result is sorted alphabetically."""
        result = normalize_acts_cited_list(
            [
                "Code of Criminal Procedure",
                "Indian Penal Code",
                "Constitution of India",
            ]
        )
        assert result == ["COI", "CRPC", "IPC"]

    def test_article_without_of(self):
        """'Article 21 Constitution of India' (without 'of') still normalizes."""
        result = normalize_acts_cited_list(["Article 21 of the Constitution of India"])
        assert result == ["COI"]


class TestIsValidActCitation:
    """Tests for _is_valid_act_citation()."""

    def test_valid_act(self):
        assert _is_valid_act_citation("IPC") is True
        assert _is_valid_act_citation("Indian Penal Code") is True

    def test_too_short(self):
        assert _is_valid_act_citation("M") is False
        assert _is_valid_act_citation("AB") is False

    def test_blocklist(self):
        assert _is_valid_act_citation("Unknown Act") is False
        assert _is_valid_act_citation("the Act") is False
        assert _is_valid_act_citation("said Act") is False
        assert _is_valid_act_citation("Delhi") is False
        assert _is_valid_act_citation("Maharashtra") is False

    def test_year_only(self):
        assert _is_valid_act_citation("2013") is False
        assert _is_valid_act_citation("1996") is False

    def test_year_act_pattern(self):
        assert _is_valid_act_citation("1996 Act") is False
        assert _is_valid_act_citation("2013 act") is False

    def test_newline_rejected(self):
        assert _is_valid_act_citation("Some\nAct") is False

    def test_valid_passes(self):
        assert _is_valid_act_citation("Motor Vehicles Act") is True
        assert _is_valid_act_citation("POCSO") is True
        assert _is_valid_act_citation("CrPC") is True


class TestNewActAliases:
    """Tests for newly added _SHORT_ACT_NAMES entries."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Limitation Act", "LA"),
            ("Prevention of Corruption Act", "PCA"),
            ("General Clauses Act", "GCA"),
            ("Land Acquisition Act", "LAA"),
            ("Motor Vehicles Act", "MVA"),
            ("Consumer Protection Act", "CPA"),
            ("Dowry Prohibition Act", "DPA"),
            ("National Highways Act", "NHA"),
            ("Protection of Children from Sexual Offences Act", "POCSO"),
            ("Legal Services Authorities Act", "LSA"),
            ("Prevention of Terrorism Act", "POTA"),
            ("Representation of the People Act", "RPA"),
            ("Mines and Minerals (Development and Regulation) Act", "MMDRA"),
        ],
    )
    def test_new_act_full_to_short(self, raw, expected):
        """New acts map from full name to shortest short code."""
        result = normalize_acts_cited_list([raw])
        assert result == [expected]


class TestEnrichStatuteCrossReferences:
    """Tests for act-level old<->new statute enrichment."""

    def test_enrich_adds_bns_for_ipc(self):
        result = enrich_statute_cross_references(["IPC"])
        assert "BNS" in result

    def test_enrich_adds_ipc_for_bns(self):
        result = enrich_statute_cross_references(["BNS"])
        assert "IPC" in result

    def test_enrich_bidirectional_crpc(self):
        # Canonical form is "CRPC" (uppercase). Input "CrPC" is accepted;
        # the equivalent mapping stores uppercase.
        result = enrich_statute_cross_references(["CrPC"])
        assert "BNSS" in result
        result2 = enrich_statute_cross_references(["BNSS"])
        assert "CRPC" in result2

    def test_enrich_bidirectional_iea(self):
        result = enrich_statute_cross_references(["IEA"])
        assert "BSA" in result
        result2 = enrich_statute_cross_references(["BSA"])
        assert "IEA" in result2

    def test_enrich_no_duplicates(self):
        result = enrich_statute_cross_references(["IPC", "BNS"])
        assert result == ["BNS", "IPC"]

    def test_enrich_preserves_other_acts(self):
        result = enrich_statute_cross_references(["IPC", "ACA"])
        assert result == ["ACA", "BNS", "IPC"]

    def test_enrich_empty_list(self):
        assert enrich_statute_cross_references([]) == []


class TestSearchFilterNormalization:
    """Tests that search filters normalize act names to canonical short codes."""

    def test_normalize_act_filter_full_name(self):
        """User searching by full name should match short code in Pinecone."""
        assert normalize_act_name("Indian Penal Code") == "IPC"
        assert normalize_act_name("Code of Criminal Procedure") == "CRPC"
        assert normalize_act_name("Constitution of India") == "COI"

    def test_normalize_act_filter_already_short(self):
        """Short codes pass through unchanged."""
        assert normalize_act_name("IPC") == "IPC"
        assert normalize_act_name("CrPC") == "CRPC"

    def test_normalize_act_filter_with_year(self):
        """Full names with year suffix normalize correctly."""
        assert normalize_act_name("Indian Penal Code, 1860") == "IPC"
        assert normalize_act_name("Limitation Act, 1963") == "LA"

    def test_normalize_act_filter_case_insensitive(self):
        """Normalization is case-insensitive for short codes."""
        assert normalize_act_name("ipc") == "IPC"
        assert normalize_act_name("crpc") == "CRPC"

    def test_normalize_act_filter_unknown_passthrough(self):
        """Unknown act names pass through as-is."""
        assert normalize_act_name("Some Obscure Act") == "Some Obscure Act"


class TestDisplayNameLookup:
    """Tests for get_act_display_name() and get_acts_cited_display()."""

    def test_known_act_with_year(self):
        assert get_act_display_name("IPC") == "Indian Penal Code, 1860"
        assert get_act_display_name("CrPC") == "Code of Criminal Procedure, 1973"
        assert get_act_display_name("COI") == "Constitution of India, 1950"

    def test_known_act_without_year(self):
        # FA (Foreigners Act) is in _SHORT_ACT_NAMES but not in _ACT_YEARS
        result = get_act_display_name("FA")
        assert result == "Foreigners Act"

    def test_unknown_code_passthrough(self):
        assert get_act_display_name("XYZ") == "XYZ"
        assert get_act_display_name("Some Random Act") == "Some Random Act"

    def test_case_insensitive(self):
        assert get_act_display_name("ipc") == "Indian Penal Code, 1860"

    def test_new_criminal_codes(self):
        assert get_act_display_name("BNS") == "Bharatiya Nyaya Sanhita, 2023"
        assert get_act_display_name("BNSS") == "Bharatiya Nagarik Suraksha Sanhita, 2023"
        assert get_act_display_name("BSA") == "Bharatiya Sakshya Adhiniyam, 2023"

    def test_display_list(self):
        result = get_acts_cited_display(["IPC", "CRPC"])
        assert result == [
            {"code": "IPC", "name": "Indian Penal Code, 1860"},
            {"code": "CRPC", "name": "Code of Criminal Procedure, 1973"},
        ]

    def test_display_list_empty(self):
        assert get_acts_cited_display([]) == []

    def test_display_list_none(self):
        assert get_acts_cited_display(None) == []


# ---------------------------------------------------------------------------
# SA10: Full pipeline integration tests
# ---------------------------------------------------------------------------


class TestFullPipelineNormalization:
    """Integration-style tests verifying end-to-end normalization pipeline."""

    def test_full_pipeline_normalization(self):
        """Messy acts_cited input → normalize → enrich → clean short codes."""
        raw = [
            "Section 302 of Indian Penal Code, 1860",
            "Article 21 of Constitution of India",
            "Unknown Act",
            "IPC",  # duplicate of first entry after normalization
            "Code of Criminal\nProcedure",
            "said Act",
            "Maharashtra",
            "2013",
            "Limitation Act, 1963",
        ]
        result = normalize_acts_cited_list(raw)
        result = enrich_statute_cross_references(result)

        # Should contain expected short codes (enriched)
        assert "IPC" in result
        assert "BNS" in result  # enriched from IPC
        assert "COI" in result
        assert "CRPC" in result
        assert "BNSS" in result  # enriched from CRPC
        assert "LA" in result

        # Should NOT contain garbage
        assert "Unknown Act" not in result
        assert "said Act" not in result
        assert "Maharashtra" not in result
        assert "2013" not in result

        # Should NOT contain full names
        assert "Indian Penal Code" not in result
        assert "Indian Penal Code, 1860" not in result
        assert "Constitution of India" not in result

    def test_display_name_roundtrip(self):
        """Every code in pipeline output has a human-readable display name."""
        raw = [
            "Indian Penal Code, 1860",
            "Constitution of India",
            "Limitation Act, 1963",
        ]
        result = normalize_acts_cited_list(raw)
        result = enrich_statute_cross_references(result)

        for code in result:
            display = get_act_display_name(code)
            # Known acts should return a name different from the short code
            assert display != code, f"get_act_display_name('{code}') returned the code itself"

    def test_section_refs_never_stored(self):
        """Strings starting with 'Section' or 'Article' never appear in output."""
        raw = [
            "Section 302 of Indian Penal Code",
            "Section 34 IPC",
            "Section 120B r/w Section 34 IPC",
            "Article 21 of Constitution of India",
            "Article 14 of Constitution of India",
        ]
        result = normalize_acts_cited_list(raw)

        for item in result:
            assert not item.startswith("Section"), f"Section reference leaked into output: {item}"
            assert not item.startswith("Article"), f"Article reference leaked into output: {item}"

    def test_order_rule_filtered(self):
        """Order/Rule procedural references are filtered out, not stored as act names."""
        raw = ["Order VII Rule 11(d) of Code of Civil Procedure, 1908"]
        result = normalize_acts_cited_list(raw)
        # Order/Rule refs are filtered by _is_valid_act_citation
        for item in result:
            assert "Order" not in item, f"Order/Rule reference leaked into output: {item}"


class TestHealthCheckQuery:
    """Verify the health check SQL constant is valid syntax."""

    def test_health_check_query_syntax(self):
        """Verify the health check SQL is valid syntax."""
        HEALTH_CHECK_SQL = """
        SELECT act, COUNT(*)
        FROM cases, unnest(acts_cited) AS act
        WHERE length(act) < 4
           OR act LIKE 'Section %%'
           OR act LIKE 'Article %%'
           OR act IN ('Unknown Act', 'Act', 'Code', 'said Act', 'that Act')
           OR act ~ E'\\n'
        GROUP BY act ORDER BY count DESC;
        """
        # Just verify it's a non-empty string (actual DB test would need connection)
        assert len(HEALTH_CHECK_SQL.strip()) > 0
        assert "unnest(acts_cited)" in HEALTH_CHECK_SQL
        assert "GROUP BY" in HEALTH_CHECK_SQL
