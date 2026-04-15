"""PII anonymization for sensitive Indian court judgments.

Masks Aadhaar numbers, PAN numbers, and phone numbers in judgment text.
Detects POCSO / sexual assault cases for metadata flagging.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ingestion.metadata import CaseMetadata

# ---------------------------------------------------------------------------
# PII masking patterns (adapted from logging_config.py but with distinct
# replacement labels so the audit trail shows *what* was masked)
# ---------------------------------------------------------------------------

# Aadhaar: 12 digits optionally space-separated in groups of 4.
# Require word boundary to avoid matching section numbers or years.
_AADHAAR_RE = re.compile(r"\b(\d{4})\s(\d{4})\s(\d{4})\b")
_AADHAAR_NOSPACE_RE = re.compile(r"\b\d{12}\b")

# PAN: AAAPA9999A — 4th char must be a valid entity-type code to avoid
# matching legal strings like POCSO2020A or CRIME1234B.
_PAN_RE = re.compile(r"\b[A-Z]{3}[ABCFGHJLPT][A-Z]\d{4}[A-Z]\b")

# Indian mobile: 10 digits starting 6-9, optional +91/91/0 prefix.
# Split into prefixed (anchored by prefix) and bare (anchored by \b) variants
# to avoid matching 10-digit substrings inside longer strings.
_PHONE_RE = re.compile(r"(?:\+91[\s-]?|91[\s-]?|0)[6-9]\d{9}\b" r"|\b[6-9]\d{9}\b")

# ---------------------------------------------------------------------------
# Sensitive case detection
# ---------------------------------------------------------------------------

# IPC sections related to sexual offences / child exploitation
_SENSITIVE_IPC_SECTIONS = frozenset(
    {
        "354",
        "354A",
        "354B",
        "354C",
        "354D",
        "363",
        "366",
        "366A",
        "366B",
        "370",
        "372",
        "373",
        "375",
        "376",
        "376A",
        "376AB",
        "376B",
        "376C",
        "376D",
        "376DA",
        "376DB",
        "509",
    }
)

# BNS equivalents (post-July 2024)
_SENSITIVE_BNS_SECTIONS = frozenset(
    {
        "63",
        "64",
        "65",
        "66",
        "67",
        "68",
        "69",
        "70",
        "74",
        "75",
        "76",
        "77",
        "78",
        "79",
    }
)

_SENSITIVE_KEYWORDS_RE = re.compile(
    r"\b("
    r"prosecutrix|minor\s+victim|POCSO"
    r"|sexual\s+assault\s+on\s+minor"
    r"|identity\s+of\s+the\s+victim"
    r"|name\s+of\s+the\s+victim\s+cannot\s+be\s+disclosed"
    r")\b",
    re.IGNORECASE,
)


def anonymize_text(full_text: str) -> tuple[str, bool]:
    """Mask PII patterns in judgment text.

    Returns:
        (cleaned_text, was_modified) -- was_modified is True if any PII was found.
    """
    original = full_text

    # Order matters:
    # 1. Spaced Aadhaar first (e.g. "1234 5678 9012") — cannot overlap with phone
    # 2. Phone next — before bare 12-digit Aadhaar, so +919876543210 is not eaten
    # 3. Bare 12-digit Aadhaar last
    result = _AADHAAR_RE.sub("[AADHAAR REDACTED]", full_text)
    result = _PHONE_RE.sub("[PHONE REDACTED]", result)
    result = _AADHAAR_NOSPACE_RE.sub("[AADHAAR REDACTED]", result)

    result = _PAN_RE.sub("[PAN REDACTED]", result)

    return result, result != original


def detect_sensitive_case(full_text: str, metadata: CaseMetadata) -> bool:
    """Detect if a case involves POCSO / sexual offences requiring anonymization.

    Checks acts_cited for POCSO / sexual offence statutes and scans
    text for sensitive keywords (prosecutrix, minor victim, etc.).
    """
    acts = metadata.acts_cited or []
    acts_lower = " ".join(acts).lower()

    # Check for POCSO
    if "pocso" in acts_lower or "protection of children from sexual offences" in acts_lower:
        return True

    # Check for sensitive IPC/BNS sections
    for act_entry in acts:
        entry_upper = act_entry.upper()
        for sec in _SENSITIVE_IPC_SECTIONS:
            if f"SECTION {sec}" in entry_upper and (
                "INDIAN PENAL CODE" in entry_upper or "IPC" in entry_upper
            ):
                return True
        for sec in _SENSITIVE_BNS_SECTIONS:
            if f"SECTION {sec}" in entry_upper and (
                "BHARATIYA NYAYA SANHITA" in entry_upper or "BNS" in entry_upper
            ):
                return True

    # Check text for sensitive keywords
    return bool(_SENSITIVE_KEYWORDS_RE.search(full_text))
