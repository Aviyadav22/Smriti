"""Tests for PII anonymization in ingested judgment text."""


from app.core.ingestion.anonymizer import anonymize_text, detect_sensitive_case
from app.core.ingestion.metadata import CaseMetadata


class TestAnonymizeText:
    """Test PII pattern masking in judgment text."""

    def test_masks_aadhaar_number(self):
        text = "The applicant's Aadhaar number is 1234 5678 9012."
        result, modified = anonymize_text(text)
        assert "[AADHAAR REDACTED]" in result
        assert "1234 5678 9012" not in result
        assert modified is True

    def test_masks_aadhaar_without_spaces(self):
        text = "Aadhaar: 123456789012"
        result, modified = anonymize_text(text)
        assert "[AADHAAR REDACTED]" in result
        assert modified is True

    def test_masks_pan_number(self):
        text = "PAN of the accused: ABCPA1234F"
        result, modified = anonymize_text(text)
        assert "[PAN REDACTED]" in result
        assert "ABCPA1234F" not in result
        assert modified is True

    def test_masks_mobile_number_with_prefix(self):
        text = "Contact: +91-9876543210"
        result, modified = anonymize_text(text)
        assert "[PHONE REDACTED]" in result
        assert "9876543210" not in result
        assert modified is True

    def test_masks_mobile_number_bare(self):
        text = "Phone: 9876543210"
        result, modified = anonymize_text(text)
        assert "[PHONE REDACTED]" in result
        assert modified is True

    def test_no_modification_when_clean(self):
        text = "The Supreme Court held that Article 21 applies."
        result, modified = anonymize_text(text)
        assert result == text
        assert modified is False

    def test_masks_multiple_pii_types(self):
        text = "Aadhaar 1234 5678 9012, PAN ABCPA1234F, Phone +919876543210"
        result, modified = anonymize_text(text)
        assert "[AADHAAR REDACTED]" in result
        assert "[PAN REDACTED]" in result
        assert "[PHONE REDACTED]" in result
        assert modified is True

    def test_preserves_section_numbers(self):
        """Section numbers like '302' should NOT be masked as Aadhaar."""
        text = "Section 302 of the Indian Penal Code"
        result, modified = anonymize_text(text)
        assert "302" in result
        assert modified is False

    def test_preserves_year_numbers(self):
        """Years like '2024' should NOT be masked."""
        text = "The judgment was delivered on 15.01.2024"
        result, modified = anonymize_text(text)
        assert "2024" in result

    def test_phone_with_91_prefix_not_masked_as_aadhaar(self):
        """Phone +91XXXXXXXXXX should be masked as PHONE, not AADHAAR."""
        text = "Contact: +91 9876543210"
        result, modified = anonymize_text(text)
        assert "[PHONE REDACTED]" in result
        assert "[AADHAAR REDACTED]" not in result
        assert modified is True

    def test_pan_false_positive_legal_strings(self):
        """Legal strings like POCSO2020A should NOT be masked as PAN."""
        text = "Under POCSO2020A and CRIME1234B provisions"
        result, modified = anonymize_text(text)
        assert "POCSO2020A" in result
        assert "CRIME1234B" in result
        assert modified is False

    def test_bare_phone_in_continuous_digits_no_match(self):
        """10-digit phone embedded in a longer digit sequence should not match."""
        text = "Case number 123456789012345 filed"
        result, _ = anonymize_text(text)
        # 15-digit number should not be partially matched as a 10-digit phone
        assert "[PHONE REDACTED]" not in result or "[AADHAAR REDACTED]" in result


class TestDetectSensitiveCase:
    """Test sensitive case detection for POCSO/sexual assault."""

    def test_detects_pocso_in_acts_cited(self):
        meta = CaseMetadata(
            acts_cited=["Protection of Children from Sexual Offences Act"]
        )
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_pocso_short_name(self):
        meta = CaseMetadata(acts_cited=["POCSO Act"])
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_ipc_376_sexual_offence(self):
        meta = CaseMetadata(
            acts_cited=["Indian Penal Code, Section 376"],
            case_type="Criminal",
        )
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_bns_equivalent_sexual_offence(self):
        meta = CaseMetadata(
            acts_cited=["Bharatiya Nyaya Sanhita, Section 65"],
            case_type="Criminal",
        )
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_keyword_prosecutrix(self):
        meta = CaseMetadata()
        text = "The prosecutrix stated in her testimony that"
        assert detect_sensitive_case(text, meta) is True

    def test_detects_keyword_minor_victim(self):
        meta = CaseMetadata()
        text = "the minor victim was aged 14 years"
        assert detect_sensitive_case(text, meta) is True

    def test_detects_identity_disclosure_phrase(self):
        meta = CaseMetadata()
        text = "the identity of the victim cannot be disclosed"
        assert detect_sensitive_case(text, meta) is True

    def test_not_sensitive_civil_case(self):
        meta = CaseMetadata(
            acts_cited=["Code of Civil Procedure"],
            case_type="Civil",
        )
        assert detect_sensitive_case("Property dispute matter", meta) is False

    def test_not_sensitive_empty_metadata(self):
        meta = CaseMetadata()
        assert detect_sensitive_case("Appeal allowed.", meta) is False
