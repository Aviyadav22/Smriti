"""Tests for the CaseSection model."""
from app.models.case_section import CaseSection


class TestCaseSectionModel:
    def test_model_has_required_fields(self):
        columns = {c.name for c in CaseSection.__table__.columns}
        assert "id" in columns
        assert "case_id" in columns
        assert "section_type" in columns
        assert "content" in columns
        assert "section_index" in columns
        assert "summary" in columns

    def test_table_name(self):
        assert CaseSection.__tablename__ == "case_sections"

    def test_section_types(self):
        """Should accept all valid section types."""
        for section_type in ["FACTS", "ISSUES", "ARGUMENTS", "HOLDINGS", "REASONING", "ORDER"]:
            section = CaseSection(
                case_id="abc-123",
                section_type=section_type,
                content="Test content",
                section_index=0,
            )
            assert section.section_type == section_type

    def test_summary_is_optional(self):
        section = CaseSection(
            case_id="abc-123",
            section_type="FACTS",
            content="Test content",
            section_index=0,
        )
        assert section.summary is None
