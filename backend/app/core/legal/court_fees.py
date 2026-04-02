"""Court fee estimator for Indian courts.

Provides state-wise court fee calculations based on suit valuation,
court level, and case type. Covers 5 major states.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class CourtFeeResult:
    state: str
    court_level: str
    suit_valuation: float
    fee_amount: float
    fee_type: str  # "ad_valorem" or "fixed"
    notes: str = ""


# Simplified court fee rates for 5 states
# Real rates are more complex with slabs — this is a pragmatic approximation
_FEE_RATES: Final[dict[str, dict[str, float]]] = {
    "delhi": {
        "district_civil": 0.075,  # 7.5% of suit valuation (ad valorem)
        "high_court": 0.075,
        "consumer_district": 0.0,  # No court fee for consumer complaints
        "consumer_state": 0.0,
    },
    "maharashtra": {
        "district_civil": 0.10,  # ~10% (Maharashtra Court Fees Act)
        "high_court": 0.10,
        "consumer_district": 0.0,
        "consumer_state": 0.0,
    },
    "karnataka": {
        "district_civil": 0.075,
        "high_court": 0.075,
        "consumer_district": 0.0,
        "consumer_state": 0.0,
    },
    "tamil_nadu": {
        "district_civil": 0.075,
        "high_court": 0.075,
        "consumer_district": 0.0,
        "consumer_state": 0.0,
    },
    "west_bengal": {
        "district_civil": 0.10,
        "high_court": 0.10,
        "consumer_district": 0.0,
        "consumer_state": 0.0,
    },
}

_FIXED_FEES: Final[dict[str, float]] = {
    "writ_petition": 500.0,
    "bail_application": 0.0,
    "anticipatory_bail": 0.0,
    "criminal_appeal": 500.0,
    "slp": 2000.0,
    "divorce_petition": 500.0,
    "maintenance_application": 0.0,
    "legal_notice": 0.0,
}

_STATE_ALIASES: Final[dict[str, str]] = {
    "delhi": "delhi", "ncr": "delhi", "new delhi": "delhi",
    "maharashtra": "maharashtra", "mumbai": "maharashtra", "bombay": "maharashtra", "pune": "maharashtra",
    "karnataka": "karnataka", "bangalore": "karnataka", "bengaluru": "karnataka",
    "tamil nadu": "tamil_nadu", "tamil_nadu": "tamil_nadu", "chennai": "tamil_nadu", "madras": "tamil_nadu",
    "west bengal": "west_bengal", "west_bengal": "west_bengal", "kolkata": "west_bengal", "calcutta": "west_bengal",
}


def estimate_court_fee(
    *,
    suit_valuation: float,
    state: str,
    court_level: str = "district_civil",
    doc_type: str = "",
) -> CourtFeeResult:
    """Estimate court fee for a given suit.

    Args:
        suit_valuation: Value of the suit in INR
        state: State name or alias
        court_level: "district_civil", "high_court", "consumer_district", "consumer_state"
        doc_type: Document type for fixed-fee lookups

    Returns:
        CourtFeeResult with estimated fee
    """
    # Check fixed fees first
    if doc_type in _FIXED_FEES:
        return CourtFeeResult(
            state=state,
            court_level=court_level,
            suit_valuation=suit_valuation,
            fee_amount=_FIXED_FEES[doc_type],
            fee_type="fixed",
            notes=f"Fixed fee for {doc_type}",
        )

    # Resolve state
    normalized_state = _STATE_ALIASES.get(state.strip().lower(), "")
    if not normalized_state:
        return CourtFeeResult(
            state=state,
            court_level=court_level,
            suit_valuation=suit_valuation,
            fee_amount=0.0,
            fee_type="unknown",
            notes=f"Court fee rates not available for '{state}'. Supported: Delhi, Maharashtra, Karnataka, Tamil Nadu, West Bengal.",
        )

    rates = _FEE_RATES.get(normalized_state, {})
    rate = rates.get(court_level, 0.075)  # Default 7.5%

    fee = suit_valuation * rate
    return CourtFeeResult(
        state=normalized_state,
        court_level=court_level,
        suit_valuation=suit_valuation,
        fee_amount=round(fee, 2),
        fee_type="ad_valorem",
        notes=f"{rate*100:.1f}% of suit valuation",
    )
