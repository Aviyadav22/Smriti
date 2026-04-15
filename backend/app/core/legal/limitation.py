"""Limitation period calculator based on the Limitation Act, 1963.

Provides lookup for common limitation periods and deadline calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final


@dataclass(frozen=True)
class LimitationPeriod:
    article: int
    description: str
    period_years: int
    period_months: int = 0
    period_days: int = 0
    notes: str = ""


# Common articles from the Limitation Act, 1963 Schedule
LIMITATION_SCHEDULE: Final[dict[str, LimitationPeriod]] = {
    # --- Part I: Suits relating to Accounts ---
    "accounts": LimitationPeriod(1, "Suit for accounts", 3),
    # --- Part II: Suits relating to Contracts ---
    "breach_of_contract": LimitationPeriod(55, "Suit for compensation for breach of contract", 3),
    "specific_performance": LimitationPeriod(54, "Suit for specific performance of contract", 3),
    "recovery_of_money": LimitationPeriod(55, "Suit for money payable under contract", 3),
    # --- Part III: Suits relating to Declarations ---
    "declaration": LimitationPeriod(58, "Suit for declaration and consequential relief", 3),
    # --- Part IV: Suits relating to Decrees and Instruments ---
    "execution_of_decree": LimitationPeriod(136, "Application for execution of decree", 12),
    # --- Part V: Suits relating to Immovable Property ---
    "possession_of_property": LimitationPeriod(64, "Suit for possession based on title", 12),
    "recovery_of_possession": LimitationPeriod(65, "Suit for possession after dispossession", 12),
    "rent_recovery": LimitationPeriod(52, "Suit for arrears of rent", 3),
    "injunction": LimitationPeriod(58, "Suit for injunction", 3),
    # --- Part VI: Suits relating to Movable Property ---
    "recovery_of_movable": LimitationPeriod(66, "Suit for recovery of movable property", 3),
    # --- Part VII: Suits relating to Torts ---
    "compensation_tort": LimitationPeriod(36, "Suit for compensation for tort", 1),
    "defamation": LimitationPeriod(75, "Suit for defamation", 1),
    "negligence": LimitationPeriod(36, "Suit for compensation for negligence", 1),
    # --- Criminal / Special Statutes ---
    "cheque_bounce_complaint": LimitationPeriod(
        0,
        "Complaint under S.138 NI Act",
        0,
        1,
        0,
        "Within 1 month of expiry of 15-day notice period",
    ),
    "bail_application": LimitationPeriod(
        0, "Bail application", 0, 0, 0, "No limitation; can be filed anytime during custody"
    ),
    "anticipatory_bail": LimitationPeriod(
        0, "Anticipatory bail", 0, 0, 0, "No limitation; file before arrest"
    ),
    # --- Appeals ---
    "civil_appeal_first": LimitationPeriod(
        116, "First appeal from decree", 0, 0, 90, "90 days from date of decree"
    ),
    "civil_appeal_second": LimitationPeriod(100, "Second appeal (S.100 CPC)", 0, 0, 90, "90 days"),
    "criminal_appeal": LimitationPeriod(
        114, "Criminal appeal", 0, 0, 30, "30 days from date of sentence"
    ),
    "slp_civil": LimitationPeriod(0, "SLP (Civil)", 0, 0, 90, "90 days from HC order"),
    "slp_criminal": LimitationPeriod(0, "SLP (Criminal)", 0, 0, 60, "60 days from HC order"),
    "review_petition": LimitationPeriod(0, "Review petition", 0, 0, 30, "30 days from order"),
    # --- Writs and Special ---
    "writ_petition": LimitationPeriod(
        0, "Writ petition", 0, 0, 0, "No strict limitation; delay is a factor"
    ),
    "consumer_complaint": LimitationPeriod(
        0, "Consumer complaint (CPA 2019)", 2, 0, 0, "2 years from cause of action"
    ),
    "divorce_petition": LimitationPeriod(
        0, "Divorce petition", 0, 0, 0, "No limitation; S.14 HMA 1-year bar after marriage"
    ),
    "maintenance_application": LimitationPeriod(
        0, "Maintenance application (S.125 CrPC)", 0, 0, 0, "No limitation"
    ),
    "insolvency_application": LimitationPeriod(
        0, "IBC S.7/9/10 application", 3, 0, 0, "3 years from date of default"
    ),
    # --- Miscellaneous ---
    "condonation_of_delay": LimitationPeriod(
        0, "Application under S.5 Limitation Act", 0, 0, 0, "Must show sufficient cause"
    ),
    "legal_notice_govt": LimitationPeriod(
        0, "S.80 CPC notice to government", 0, 2, 0, "2-month notice before filing suit"
    ),
}


def calculate_deadline(
    cause_key: str,
    accrual_date: date,
) -> dict:
    """Calculate limitation deadline for a given cause of action.

    Args:
        cause_key: Key from LIMITATION_SCHEDULE
        accrual_date: Date when cause of action arose

    Returns:
        Dict with period info, deadline, and whether current date is within time.
    """
    period = LIMITATION_SCHEDULE.get(cause_key)
    if period is None:
        return {
            "found": False,
            "error": f"Unknown cause key: {cause_key}. Valid keys: {sorted(LIMITATION_SCHEDULE.keys())}",
        }

    # Calculate deadline
    total_days = period.period_years * 365 + period.period_months * 30 + period.period_days
    if total_days == 0:
        return {
            "found": True,
            "article": period.article,
            "description": period.description,
            "period": f"{period.period_years}y {period.period_months}m {period.period_days}d"
            if any([period.period_years, period.period_months, period.period_days])
            else "No fixed limitation",
            "deadline": None,
            "within_time": True,
            "notes": period.notes,
        }

    deadline = accrual_date + timedelta(days=total_days)
    today = date.today()
    within_time = today <= deadline
    days_remaining = (deadline - today).days if within_time else 0

    return {
        "found": True,
        "article": period.article,
        "description": period.description,
        "period": f"{period.period_years}y {period.period_months}m {period.period_days}d",
        "accrual_date": str(accrual_date),
        "deadline": str(deadline),
        "within_time": within_time,
        "days_remaining": days_remaining,
        "notes": period.notes,
    }


def get_limitation_for_doc_type(doc_type: str) -> LimitationPeriod | None:
    """Map a document type to its most relevant limitation period."""
    _DOC_TYPE_MAP = {
        "plaint": "breach_of_contract",
        "appeal": "civil_appeal_first",
        "slp": "slp_civil",
        "consumer_complaint": "consumer_complaint",
        "demand_notice_138": "cheque_bounce_complaint",
        "bail_application": "bail_application",
        "anticipatory_bail": "anticipatory_bail",
        "divorce_petition": "divorce_petition",
        "maintenance_application": "maintenance_application",
        "writ_petition_226": "writ_petition",
        "writ_petition_32": "writ_petition",
        "review_petition": "review_petition",
    }
    key = _DOC_TYPE_MAP.get(doc_type)
    if key:
        return LIMITATION_SCHEDULE.get(key)
    return None
