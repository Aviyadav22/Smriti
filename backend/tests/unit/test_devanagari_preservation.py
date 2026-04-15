"""Tests for Devanagari/Hindi text preservation (G5).

Verifies that ZWNJ (U+200C) and ZWJ (U+200D) are preserved during
text cleaning, as they are structurally meaningful in Devanagari script.
Also verifies that Hindi legal text passes through cleaning intact.
"""

from __future__ import annotations

from app.core.ingestion.pdf import clean_extracted_text


class TestDevanagariZWJPreservation:
    """ZWNJ/ZWJ must be preserved — they control Devanagari conjunct formation."""

    def test_zwnj_preserved(self):
        """Zero-Width Non-Joiner (U+200C) must be preserved for Hindi."""
        # ZWNJ prevents conjunct formation: क + ् + \u200C + ष = क्‌ष (not क्ष)
        text = "क\u094d\u200cष"
        result = clean_extracted_text(text)
        assert "\u200c" in result, "ZWNJ should be preserved for Devanagari"

    def test_zwj_preserved(self):
        """Zero-Width Joiner (U+200D) must be preserved for Hindi."""
        # ZWJ forces conjunct formation
        text = "क\u094d\u200dष"
        result = clean_extracted_text(text)
        assert "\u200d" in result, "ZWJ should be preserved for Devanagari"

    def test_zwsp_removed(self):
        """Zero-Width Space (U+200B) should still be removed."""
        text = "Hello\u200bWorld"
        result = clean_extracted_text(text)
        assert "\u200b" not in result

    def test_bom_removed(self):
        """BOM (U+FEFF) should still be removed."""
        text = "\ufeffSome text"
        result = clean_extracted_text(text)
        assert "\ufeff" not in result


class TestHindiTextPreservation:
    """Hindi legal text should pass through cleaning intact."""

    def test_basic_hindi_legal_text_preserved(self):
        """Common Hindi legal phrases should survive cleaning."""
        text = (
            "उच्चतम न्यायालय ने कहा कि याचिकाकर्ता की अपील "
            "भारतीय दंड संहिता की धारा 302 के तहत खारिज की जाती है।"
        )
        result = clean_extracted_text(text)
        assert "उच्चतम न्यायालय" in result
        assert "याचिकाकर्ता" in result
        assert "धारा 302" in result

    def test_mixed_hindi_english_preserved(self):
        """Mixed Hindi-English legal text should survive cleaning."""
        text = (
            "The Hon'ble Supreme Court (उच्चतम न्यायालय) observed that "
            "Section 302 (धारा 302) of the IPC (भारतीय दंड संहिता) "
            "prescribes punishment for murder (हत्या)."
        )
        result = clean_extracted_text(text)
        assert "उच्चतम न्यायालय" in result
        assert "Section 302" in result
        assert "भारतीय दंड संहिता" in result

    def test_devanagari_with_matras_preserved(self):
        """Devanagari text with vowel signs (matras) should be preserved."""
        text = "संविधान के अनुच्छेद 21 के अंतर्गत प्रत्येक व्यक्ति को जीवन का अधिकार है।"
        result = clean_extracted_text(text)
        assert "संविधान" in result
        assert "अनुच्छेद 21" in result
        assert "अधिकार" in result

    def test_devanagari_numerals_preserved(self):
        """Devanagari numeral characters should be preserved."""
        text = "धारा ३०२ के अंतर्गत अपील"
        result = clean_extracted_text(text)
        assert "३०२" in result

    def test_nfkc_does_not_mangle_devanagari(self):
        """NFKC normalization should not alter valid Devanagari text."""
        # Pre-composed vs. decomposed Devanagari — NFKC should normalize safely
        text = "न्यायालय"  # Court in Hindi
        result = clean_extracted_text(text)
        assert "न्यायालय" in result
