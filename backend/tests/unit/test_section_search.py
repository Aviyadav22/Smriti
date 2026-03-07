"""Tests for section-aware search filtering."""
import pytest
from app.core.search.query import SearchFilters


class TestSearchFiltersSection:
    def test_section_filter_field_exists(self):
        """SearchFilters should have a judgment_section field."""
        filters = SearchFilters(judgment_section="HOLDINGS")
        assert filters.judgment_section == "HOLDINGS"

    def test_section_filter_default_none(self):
        filters = SearchFilters()
        assert filters.judgment_section is None
