"""Tests for citation treatment detection and overruled case support."""

from app.core.legal.precedent_strength import (
    PrecedentStrength,
    classify_precedent_strength,
)
from app.core.legal.treatment import (
    CitationTreatment,
    detect_treatment_in_text,
    has_overruling_language,
)


class TestDetectTreatmentInText:
    def test_detects_overruled_language(self):
        """Should detect 'overruled' in judgment text."""
        text = "The decision in State v. Kumar was expressly overruled by this Court."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.OVERRULED in treatments

    def test_detects_per_incuriam(self):
        """Should detect 'per incuriam' as overruling language."""
        text = "The earlier judgment was rendered per incuriam and cannot be relied upon."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.OVERRULED in treatments

    def test_detects_no_longer_good_law(self):
        """Should detect 'no longer good law' as overruling language."""
        text = "This precedent is no longer good law after the amendment."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.OVERRULED in treatments

    def test_detects_distinguished_language(self):
        """Should detect 'distinguished' in judgment text."""
        text = "The facts in this case are distinguished from the earlier ruling."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.DISTINGUISHED in treatments

    def test_detects_affirmed_language(self):
        """Should detect 'affirmed' in judgment text."""
        text = "The principle laid down in AIR 1998 SC 123 was affirmed by this bench."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.AFFIRMED in treatments

    def test_detects_followed_language(self):
        """Should detect 'followed' in judgment text."""
        text = "We have followed the ratio in the earlier decision."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.FOLLOWED in treatments

    def test_detects_relied_upon(self):
        """Should detect 'relied upon' as followed treatment."""
        text = "The appellant relied upon the judgment in (2005) 3 SCC 100."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.FOLLOWED in treatments

    def test_detects_explained_language(self):
        """Should detect 'explained' in judgment text."""
        text = "The scope of this provision was explained in the earlier case."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.EXPLAINED in treatments

    def test_detects_doubted_language(self):
        """Should detect 'doubted' in judgment text."""
        text = "The correctness of the earlier view was doubted by the Division Bench."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.DOUBTED in treatments

    def test_returns_empty_for_neutral_text(self):
        """Should return empty list when no treatment language is found."""
        text = "The parties entered into a contract on 15th January 2020."
        results = detect_treatment_in_text(text)
        assert results == []

    def test_returns_context_around_match(self):
        """Should include surrounding text context in result."""
        text = "The Supreme Court expressly overruled the earlier decision."
        results = detect_treatment_in_text(text)
        assert len(results) >= 1
        overruled_results = [r for r in results if r.treatment == CitationTreatment.OVERRULED]
        assert len(overruled_results) >= 1
        assert "overruled" in overruled_results[0].cited_text.lower()

    def test_overruled_has_high_confidence(self):
        """Overruled results should have confidence of 0.7."""
        text = "This judgment stands overruled."
        results = detect_treatment_in_text(text)
        overruled_results = [r for r in results if r.treatment == CitationTreatment.OVERRULED]
        assert len(overruled_results) >= 1
        assert overruled_results[0].confidence == 0.7

    def test_followed_has_lower_confidence(self):
        """Followed results should have confidence of 0.5."""
        text = "The ratio was followed in the subsequent case."
        results = detect_treatment_in_text(text)
        followed_results = [r for r in results if r.treatment == CitationTreatment.FOLLOWED]
        assert len(followed_results) >= 1
        assert followed_results[0].confidence == 0.5

    def test_multiple_treatments_in_same_text(self):
        """Should detect multiple different treatments in one text."""
        text = (
            "The court overruled the earlier decision in Case A, "
            "but followed the reasoning in Case B."
        )
        results = detect_treatment_in_text(text)
        treatments = {r.treatment for r in results}
        assert CitationTreatment.OVERRULED in treatments
        assert CitationTreatment.FOLLOWED in treatments

    def test_detects_not_followed(self):
        """Should detect 'not followed' as NOT_FOLLOWED treatment."""
        text = "The ratio in the earlier judgment was not followed by this Court."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.NOT_FOLLOWED in treatments

    def test_detects_declined_to_follow(self):
        """Should detect 'declined to follow' as NOT_FOLLOWED treatment."""
        text = "The Division Bench declined to follow the single judge's view."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.NOT_FOLLOWED in treatments

    def test_detects_refused_to_follow(self):
        """Should detect 'refused to follow' as NOT_FOLLOWED treatment."""
        text = "The High Court refused to follow the earlier precedent."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.NOT_FOLLOWED in treatments

    def test_detects_never_followed(self):
        """Should detect 'never been followed' as NOT_FOLLOWED treatment."""
        text = "This obiter dictum has never been followed by any court."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.NOT_FOLLOWED in treatments

    def test_not_followed_excludes_false_positive_followed(self):
        """'not followed' should NOT also produce a FOLLOWED result."""
        text = "The principle was not followed in subsequent decisions."
        results = detect_treatment_in_text(text)
        treatments = [r.treatment for r in results]
        assert CitationTreatment.NOT_FOLLOWED in treatments
        assert CitationTreatment.FOLLOWED not in treatments

    def test_not_followed_has_high_confidence(self):
        """NOT_FOLLOWED results should have confidence of 0.7."""
        text = "The court declined to follow the earlier ratio."
        results = detect_treatment_in_text(text)
        not_followed = [r for r in results if r.treatment == CitationTreatment.NOT_FOLLOWED]
        assert len(not_followed) >= 1
        assert not_followed[0].confidence == 0.7


class TestHasOverrulingLanguage:
    def test_returns_true_for_overruled(self):
        """Should return True when text contains 'overruled'."""
        assert has_overruling_language("This case was overruled.") is True

    def test_returns_true_for_per_incuriam(self):
        """Should return True for 'per incuriam'."""
        assert has_overruling_language("Rendered per incuriam.") is True

    def test_returns_true_for_no_longer_good_law(self):
        """Should return True for 'no longer good law'."""
        assert has_overruling_language("It is no longer good law.") is True

    def test_returns_false_for_neutral_text(self):
        """Should return False for text without overruling language."""
        assert has_overruling_language("The appeal is dismissed.") is False

    def test_returns_false_for_other_treatments(self):
        """Should return False when only non-overruling treatment found."""
        assert has_overruling_language("The case was distinguished.") is False


class TestClassifyPrecedentStrengthOverruled:
    def test_overruled_true_returns_overruled(self):
        """When overruled=True, should always return OVERRULED regardless of courts."""
        result = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="constitutional",
            target_court="Supreme Court of India",
            target_bench="division",
            overruled=True,
        )
        assert result == PrecedentStrength.OVERRULED

    def test_overruled_true_overrides_binding(self):
        """Overruled flag should override what would normally be BINDING."""
        # Without overruled, SC -> HC is BINDING
        normal = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="division",
            target_court="High Court of Delhi",
            target_bench="single",
            overruled=False,
        )
        assert normal == PrecedentStrength.BINDING

        # With overruled=True, same params should return OVERRULED
        overruled = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="division",
            target_court="High Court of Delhi",
            target_bench="single",
            overruled=True,
        )
        assert overruled == PrecedentStrength.OVERRULED

    def test_overruled_false_follows_normal_logic(self):
        """When overruled=False (default), normal classification applies."""
        result = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="division",
        )
        assert result == PrecedentStrength.BINDING

    def test_overruled_default_is_false(self):
        """The overruled parameter should default to False."""
        # Call without overruled param — should work as before
        result = classify_precedent_strength(
            source_court="High Court of Bombay",
            source_bench="division",
            target_court="High Court of Delhi",
        )
        assert result == PrecedentStrength.PERSUASIVE
