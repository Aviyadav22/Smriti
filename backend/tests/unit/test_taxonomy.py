"""Tests for the canonical legal taxonomy module."""

from __future__ import annotations

from app.core.legal.taxonomy import (
    LEGAL_TAXONOMY,
    NORMALIZATION_MAP,
    get_all_subtopics,
    get_categories,
    get_category_for_tag,
    get_taxonomy_prompt_text,
    normalize_issue_tags,
)


class TestLegalTaxonomy:
    """Verify taxonomy structure and integrity."""

    EXPECTED_CATEGORIES = [
        "Criminal Law",
        "Constitutional Law",
        "Civil Procedure",
        "Land & Property",
        "Tax Law",
        "Labour & Service",
        "Arbitration",
        "Family Law",
        "Insolvency",
        "Company Law",
        "Contract & Commercial",
        "Environmental Law",
        "Evidence",
        "Motor Accident & Tort",
        "Consumer Protection",
        "Administrative Law",
        "Election Law",
        "Regulatory Law",
    ]

    def test_has_18_categories(self) -> None:
        assert len(LEGAL_TAXONOMY) == 18

    def test_all_expected_categories_present(self) -> None:
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in LEGAL_TAXONOMY, f"Missing category: {cat}"

    def test_each_category_has_subtopics(self) -> None:
        for cat, subtopics in LEGAL_TAXONOMY.items():
            assert len(subtopics) >= 4, f"{cat} has fewer than 4 subtopics"
            assert len(subtopics) <= 16, f"{cat} has more than 16 subtopics"

    def test_tags_are_dot_separated(self) -> None:
        for cat, subtopics in LEGAL_TAXONOMY.items():
            for tag in subtopics:
                assert "." in tag, f"Tag '{tag}' in '{cat}' is not dot-separated"

    def test_tags_are_lowercase_with_underscores(self) -> None:
        for _cat, subtopics in LEGAL_TAXONOMY.items():
            for tag in subtopics:
                assert tag == tag.lower(), f"Tag '{tag}' contains uppercase"
                assert " " not in tag, f"Tag '{tag}' contains spaces"

    def test_no_duplicate_tags_across_categories(self) -> None:
        all_tags: list[str] = []
        for subtopics in LEGAL_TAXONOMY.values():
            all_tags.extend(subtopics.keys())
        assert len(all_tags) == len(set(all_tags)), "Duplicate tags found"

    def test_normalization_map_targets_are_canonical(self) -> None:
        """Every normalization target should exist in the taxonomy."""
        all_tags = {tag for subtopics in LEGAL_TAXONOMY.values() for tag in subtopics}
        for variant, canonical in NORMALIZATION_MAP.items():
            assert canonical in all_tags, (
                f"Normalization target '{canonical}' (from '{variant}') " f"not found in taxonomy"
            )


class TestNormalizeIssueTags:
    """Test normalize_issue_tags function."""

    def test_variant_normalized(self) -> None:
        result = normalize_issue_tags(["criminal.murder"])
        assert result == ["criminal_law.murder"]

    def test_canonical_unchanged(self) -> None:
        result = normalize_issue_tags(["criminal_law.murder"])
        assert result == ["criminal_law.murder"]

    def test_multiple_tags(self) -> None:
        result = normalize_issue_tags(
            [
                "criminal.murder",
                "fundamental_rights.article_21",
            ]
        )
        assert result == ["criminal_law.murder", "constitutional_law.article_21"]

    def test_unknown_preserved(self) -> None:
        result = normalize_issue_tags(["unknown_domain.something"])
        assert result == ["unknown_domain.something"]

    def test_empty_list(self) -> None:
        assert normalize_issue_tags([]) == []

    def test_none_input(self) -> None:
        assert normalize_issue_tags(None) == []

    def test_deduplication_after_normalization(self) -> None:
        """Two different variants mapping to the same canonical tag."""
        result = normalize_issue_tags(
            [
                "criminal_procedure.bail",
                "criminal.bail",
            ]
        )
        assert result == ["criminal_law.bail"]

    def test_deduplication_variant_and_canonical(self) -> None:
        """A variant and its canonical target in the same list."""
        result = normalize_issue_tags(
            [
                "criminal.murder",
                "criminal_law.murder",
            ]
        )
        assert result == ["criminal_law.murder"]

    def test_preserves_order(self) -> None:
        result = normalize_issue_tags(
            [
                "constitutional.article_21",
                "criminal.murder",
            ]
        )
        assert result == ["constitutional_law.article_21", "criminal_law.murder"]

    def test_bail_pre_arrest_normalized(self) -> None:
        result = normalize_issue_tags(["criminal_law.bail.pre_arrest_bail"])
        assert result == ["criminal_law.anticipatory_bail"]

    def test_service_variants(self) -> None:
        result = normalize_issue_tags(
            [
                "service.appointment",
                "service_law.promotion",
            ]
        )
        assert result == ["labour_service.recruitment", "labour_service.promotion"]


class TestGetCategoryForTag:
    """Test get_category_for_tag function."""

    def test_known_tag(self) -> None:
        assert get_category_for_tag("criminal_law.murder") == "Criminal Law"

    def test_known_tag_constitutional(self) -> None:
        assert get_category_for_tag("constitutional_law.article_14") == "Constitutional Law"

    def test_unknown_tag(self) -> None:
        assert get_category_for_tag("totally_unknown.tag") is None

    def test_prefix_matching(self) -> None:
        """A tag not in taxonomy but with a known prefix should match."""
        result = get_category_for_tag("criminal_law.some_new_offence")
        assert result == "Criminal Law"

    def test_prefix_matching_labour(self) -> None:
        result = get_category_for_tag("labour_service.some_new_topic")
        assert result == "Labour & Service"

    def test_no_dot_unknown(self) -> None:
        assert get_category_for_tag("randomstring") is None


class TestGetAllSubtopics:
    """Test get_all_subtopics function."""

    def test_returns_subtopics(self) -> None:
        result = get_all_subtopics("Criminal Law")
        assert len(result) > 0
        assert "criminal_law.murder" in result
        assert result["criminal_law.murder"] == "Murder"

    def test_unknown_category_returns_empty(self) -> None:
        assert get_all_subtopics("Nonexistent Category") == {}

    def test_returns_copy(self) -> None:
        """Modifying the result should not affect the taxonomy."""
        result = get_all_subtopics("Criminal Law")
        result["criminal_law.fake"] = "Fake"
        assert "criminal_law.fake" not in LEGAL_TAXONOMY["Criminal Law"]


class TestGetCategories:
    """Test get_categories function."""

    def test_returns_all_18(self) -> None:
        cats = get_categories()
        assert len(cats) == 18

    def test_first_is_criminal_law(self) -> None:
        assert get_categories()[0] == "Criminal Law"

    def test_returns_list_of_strings(self) -> None:
        cats = get_categories()
        assert all(isinstance(c, str) for c in cats)


class TestGetTaxonomyPromptText:
    """Test get_taxonomy_prompt_text function."""

    def test_contains_all_categories(self) -> None:
        text = get_taxonomy_prompt_text()
        for cat in LEGAL_TAXONOMY:
            assert f"## {cat}" in text

    def test_contains_tags_and_labels(self) -> None:
        text = get_taxonomy_prompt_text()
        assert "- criminal_law.murder: Murder" in text
        assert "- constitutional_law.article_14: Article 14" in text

    def test_returns_string(self) -> None:
        assert isinstance(get_taxonomy_prompt_text(), str)

    def test_not_empty(self) -> None:
        assert len(get_taxonomy_prompt_text()) > 100
