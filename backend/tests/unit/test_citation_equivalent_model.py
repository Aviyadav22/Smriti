"""Tests for the CaseCitationEquivalent model."""
import pytest
from app.models.case_citation_equivalent import CaseCitationEquivalent


class TestCaseCitationEquivalentModel:
    def test_model_has_required_fields(self):
        """Model must have all required columns."""
        columns = {c.name for c in CaseCitationEquivalent.__table__.columns}
        assert "id" in columns
        assert "case_id" in columns
        assert "reporter" in columns
        assert "citation_text" in columns
        assert "year" in columns

    def test_table_name(self):
        assert CaseCitationEquivalent.__tablename__ == "case_citation_equivalents"

    def test_reporter_values(self):
        """Reporter should accept standard Indian citation reporters."""
        equiv = CaseCitationEquivalent(
            case_id="abc-123",
            reporter="SCC",
            citation_text="(2023) 5 SCC 123",
            year=2023,
        )
        assert equiv.reporter == "SCC"

    def test_citation_text_stored(self):
        equiv = CaseCitationEquivalent(
            case_id="abc-123",
            reporter="AIR",
            citation_text="AIR 2023 SC 456",
            year=2023,
        )
        assert equiv.citation_text == "AIR 2023 SC 456"
