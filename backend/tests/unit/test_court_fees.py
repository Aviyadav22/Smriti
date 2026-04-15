"""Tests for court fee estimator."""

from app.core.legal.court_fees import estimate_court_fee


class TestEstimateCourtFee:
    def test_delhi_district_civil(self) -> None:
        result = estimate_court_fee(
            suit_valuation=1000000, state="Delhi", court_level="district_civil"
        )
        assert result.fee_amount == 75000.0  # 7.5%
        assert result.fee_type == "ad_valorem"

    def test_maharashtra_high_court(self) -> None:
        result = estimate_court_fee(suit_valuation=500000, state="Mumbai", court_level="high_court")
        assert result.fee_amount == 50000.0  # 10%
        assert result.state == "maharashtra"

    def test_fixed_fee_for_bail(self) -> None:
        result = estimate_court_fee(suit_valuation=0, state="Delhi", doc_type="bail_application")
        assert result.fee_amount == 0.0
        assert result.fee_type == "fixed"

    def test_fixed_fee_for_slp(self) -> None:
        result = estimate_court_fee(suit_valuation=0, state="Delhi", doc_type="slp")
        assert result.fee_amount == 2000.0
        assert result.fee_type == "fixed"

    def test_consumer_complaint_no_fee(self) -> None:
        result = estimate_court_fee(
            suit_valuation=500000, state="Delhi", court_level="consumer_district"
        )
        assert result.fee_amount == 0.0

    def test_unknown_state(self) -> None:
        result = estimate_court_fee(suit_valuation=100000, state="Assam")
        assert result.fee_type == "unknown"
        assert "not available" in result.notes

    def test_state_alias_resolution(self) -> None:
        r1 = estimate_court_fee(suit_valuation=100000, state="Bangalore")
        r2 = estimate_court_fee(suit_valuation=100000, state="Karnataka")
        assert r1.fee_amount == r2.fee_amount
