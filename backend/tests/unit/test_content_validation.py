"""Tests for post-extraction content validation."""

import pytest

from app.core.ingestion.metadata import (
    CaseMetadata,
    _validate_metadata_against_text,
)


class TestValidateMetadataAgainstText:
    """Tests for _validate_metadata_against_text()."""

    def test_keywords_matching_text_kept(self):
        text = (
            "This case concerns murder under Section 302 of IPC and bail jurisprudence. "
            "The accused was charged with murder of the deceased on the night of 15th January. "
            "The trial court convicted the accused and sentenced him to life imprisonment. "
            "The High Court confirmed the conviction and the matter is now before this Court. "
        )
        meta = CaseMetadata(keywords=["murder", "bail jurisprudence", "Section 302 IPC"])
        result = _validate_metadata_against_text(meta, text)
        assert result.keywords == ["murder", "bail jurisprudence", "Section 302 IPC"]

    def test_keywords_not_in_text_removed(self):
        text = (
            "This case concerns land acquisition under the Land Acquisition Act. "
            "The petitioner challenged the notification issued under Section 4 of the Act. "
            "The State Government acquired the land for a public purpose. "
            "The compensation awarded by the Collector was found to be inadequate. "
        )
        meta = CaseMetadata(
            keywords=["land acquisition", "eminent domain", "custodial death", "bail"],
        )
        result = _validate_metadata_against_text(meta, text)
        assert "land acquisition" in result.keywords
        assert "custodial death" not in result.keywords
        assert "bail" not in result.keywords  # "bail" is 4 chars, treated as a token, not in text

    def test_ratio_sharing_tokens_with_text_kept(self):
        text = (
            "The court held that the right to life under Article 21 includes the right to livelihood. "
            "This fundamental right cannot be curtailed except by procedure established by law. "
            "The petitioner was deprived of livelihood without due process. "
            "The State failed to demonstrate any compelling interest. "
        )
        meta = CaseMetadata(
            ratio_decidendi="The right to life under Article 21 encompasses the right to livelihood",
        )
        result = _validate_metadata_against_text(meta, text)
        assert result.ratio_decidendi is not None

    def test_ratio_not_matching_text_nulled(self):
        text = (
            "This case concerns excise duty on manufactured goods under Central Excise Act. "
            "The assessee claimed exemption under Notification No 12 of 2012. "
            "The Tribunal held that the goods fell under Tariff Heading 8471. "
            "The Revenue challenged this classification before the High Court. "
        )
        meta = CaseMetadata(
            ratio_decidendi="The doctrine of res judicata bars a second suit on the same cause of action in family law matters",
        )
        result = _validate_metadata_against_text(meta, text)
        assert result.ratio_decidendi is None

    def test_short_text_skips_validation(self):
        meta = CaseMetadata(keywords=["anything"], ratio_decidendi="anything")
        result = _validate_metadata_against_text(meta, "Short.")
        assert result.keywords == ["anything"]
        assert result.ratio_decidendi == "anything"
