"""Tests for Hindi legal glossary."""

from __future__ import annotations

from app.core.drafting.hindi_glossary import (
    LEGAL_GLOSSARY,
    apply_hindi_terms,
    get_court_header_hindi,
    get_hindi_term,
)


class TestLegalGlossary:
    def test_glossary_has_substantial_entries(self) -> None:
        assert len(LEGAL_GLOSSARY) >= 100

    def test_contains_key_court_terms(self) -> None:
        assert "Supreme Court of India" in LEGAL_GLOSSARY
        assert "High Court" in LEGAL_GLOSSARY
        assert "District Court" in LEGAL_GLOSSARY

    def test_contains_party_designations(self) -> None:
        assert "Petitioner" in LEGAL_GLOSSARY
        assert "Respondent" in LEGAL_GLOSSARY
        assert "Accused" in LEGAL_GLOSSARY

    def test_contains_document_types(self) -> None:
        assert "Bail Application" in LEGAL_GLOSSARY
        assert "Writ Petition" in LEGAL_GLOSSARY
        assert "Affidavit" in LEGAL_GLOSSARY

    def test_contains_statutes(self) -> None:
        assert "Constitution of India" in LEGAL_GLOSSARY
        assert "Bharatiya Nyaya Sanhita" in LEGAL_GLOSSARY

    def test_hindi_values_are_devanagari(self) -> None:
        for english, hindi in LEGAL_GLOSSARY.items():
            assert any(
                "\u0900" <= ch <= "\u097f" for ch in hindi
            ), f"Hindi for '{english}' does not contain Devanagari: '{hindi}'"


class TestApplyHindiTerms:
    def test_replaces_single_term(self) -> None:
        result = apply_hindi_terms("The Petitioner filed a Bail Application")
        assert "\u092f\u093e\u091a\u093f\u0915\u093e\u0915\u0930\u094d\u0924\u093e" in result
        assert "\u091c\u092e\u093e\u0928\u0924 \u0906\u0935\u0947\u0926\u0928" in result

    def test_case_insensitive(self) -> None:
        result = apply_hindi_terms("the petitioner")
        assert "\u092f\u093e\u091a\u093f\u0915\u093e\u0915\u0930\u094d\u0924\u093e" in result

    def test_preserves_non_legal_text(self) -> None:
        result = apply_hindi_terms("Hello World 12345")
        assert result == "Hello World 12345"

    def test_replaces_longer_phrases_first(self) -> None:
        result = apply_hindi_terms("Supreme Court of India")
        assert (
            "\u0938\u0930\u094d\u0935\u094b\u091a\u094d\u091a \u0928\u094d\u092f\u093e\u092f\u093e\u0932\u092f"
            in result
        )


class TestGetHindiTerm:
    def test_exact_match(self) -> None:
        assert (
            get_hindi_term("Petitioner")
            == "\u092f\u093e\u091a\u093f\u0915\u093e\u0915\u0930\u094d\u0924\u093e"
        )

    def test_case_insensitive(self) -> None:
        assert (
            get_hindi_term("petitioner")
            == "\u092f\u093e\u091a\u093f\u0915\u093e\u0915\u0930\u094d\u0924\u093e"
        )

    def test_unknown_term_returns_none(self) -> None:
        assert get_hindi_term("xyznonexistent") is None


class TestCourtHeaderHindi:
    def test_supreme_court_hindi(self) -> None:
        header = get_court_header_hindi("supreme_court")
        assert "\u0938\u0930\u094d\u0935\u094b\u091a\u094d\u091a" in header

    def test_delhi_hc_hindi(self) -> None:
        header = get_court_header_hindi("delhi_hc")
        assert "\u0926\u093f\u0932\u094d\u0932\u0940" in header

    def test_unknown_court_returns_default(self) -> None:
        header = get_court_header_hindi("unknown_court")
        assert "\u0928\u094d\u092f\u093e\u092f\u093e\u0932\u092f" in header
