# India-Specific Audit Fixes (U1–U4) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 India-specific risks: Hindi FTS skip, HC citation format gaps, BNS dual-tagging at ingestion, PII anonymization for sensitive cases.

**Architecture:** Four independent features sharing one migration (015). U1 modifies the search layer to skip FTS for Hindi. U2 expands citation regex patterns. U3 adds a new statute enrichment module called at ingestion. U4 adds a new anonymizer module called at ingestion. All follow existing interface+provider patterns.

**Tech Stack:** Python 3.12, FastAPI, PostgreSQL (tsvector, GIN), regex, pytest

---

### Task 1: U4 — PII Anonymizer Module (Tests)

**Files:**
- Create: `backend/tests/unit/test_anonymizer.py`

**Step 1: Write the failing tests**

```python
"""Tests for PII anonymization in ingested judgment text."""

import pytest

from app.core.ingestion.anonymizer import anonymize_text, detect_sensitive_case
from app.core.ingestion.metadata import CaseMetadata


class TestAnonymizeText:
    """Test PII pattern masking in judgment text."""

    def test_masks_aadhaar_number(self):
        text = "The applicant's Aadhaar number is 1234 5678 9012."
        result, modified = anonymize_text(text)
        assert "[AADHAAR REDACTED]" in result
        assert "1234 5678 9012" not in result
        assert modified is True

    def test_masks_aadhaar_without_spaces(self):
        text = "Aadhaar: 123456789012"
        result, modified = anonymize_text(text)
        assert "[AADHAAR REDACTED]" in result
        assert modified is True

    def test_masks_pan_number(self):
        text = "PAN of the accused: ABCDE1234F"
        result, modified = anonymize_text(text)
        assert "[PAN REDACTED]" in result
        assert "ABCDE1234F" not in result
        assert modified is True

    def test_masks_mobile_number_with_prefix(self):
        text = "Contact: +91-9876543210"
        result, modified = anonymize_text(text)
        assert "[PHONE REDACTED]" in result
        assert "9876543210" not in result
        assert modified is True

    def test_masks_mobile_number_bare(self):
        text = "Phone: 9876543210"
        result, modified = anonymize_text(text)
        assert "[PHONE REDACTED]" in result
        assert modified is True

    def test_no_modification_when_clean(self):
        text = "The Supreme Court held that Article 21 applies."
        result, modified = anonymize_text(text)
        assert result == text
        assert modified is False

    def test_masks_multiple_pii_types(self):
        text = "Aadhaar 1234 5678 9012, PAN ABCDE1234F, Phone +919876543210"
        result, modified = anonymize_text(text)
        assert "[AADHAAR REDACTED]" in result
        assert "[PAN REDACTED]" in result
        assert "[PHONE REDACTED]" in result
        assert modified is True

    def test_preserves_section_numbers(self):
        """Section numbers like '302' should NOT be masked as Aadhaar."""
        text = "Section 302 of the Indian Penal Code"
        result, modified = anonymize_text(text)
        assert "302" in result
        assert modified is False

    def test_preserves_year_numbers(self):
        """Years like '2024' should NOT be masked."""
        text = "The judgment was delivered on 15.01.2024"
        result, modified = anonymize_text(text)
        assert "2024" in result


class TestDetectSensitiveCase:
    """Test sensitive case detection for POCSO/sexual assault."""

    def test_detects_pocso_in_acts_cited(self):
        meta = CaseMetadata(
            acts_cited=["Protection of Children from Sexual Offences Act"]
        )
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_pocso_short_name(self):
        meta = CaseMetadata(acts_cited=["POCSO Act"])
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_ipc_376_sexual_offence(self):
        meta = CaseMetadata(
            acts_cited=["Indian Penal Code, Section 376"],
            case_type="Criminal",
        )
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_bns_equivalent_sexual_offence(self):
        meta = CaseMetadata(
            acts_cited=["Bharatiya Nyaya Sanhita, Section 65"],
            case_type="Criminal",
        )
        assert detect_sensitive_case("Some text", meta) is True

    def test_detects_keyword_prosecutrix(self):
        meta = CaseMetadata()
        text = "The prosecutrix stated in her testimony that"
        assert detect_sensitive_case(text, meta) is True

    def test_detects_keyword_minor_victim(self):
        meta = CaseMetadata()
        text = "the minor victim was aged 14 years"
        assert detect_sensitive_case(text, meta) is True

    def test_detects_identity_disclosure_phrase(self):
        meta = CaseMetadata()
        text = "the identity of the victim cannot be disclosed"
        assert detect_sensitive_case(text, meta) is True

    def test_not_sensitive_civil_case(self):
        meta = CaseMetadata(
            acts_cited=["Code of Civil Procedure"],
            case_type="Civil",
        )
        assert detect_sensitive_case("Property dispute matter", meta) is False

    def test_not_sensitive_empty_metadata(self):
        meta = CaseMetadata()
        assert detect_sensitive_case("Appeal allowed.", meta) is False
```

**Step 2: Run test to verify it fails**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_anonymizer.py -v --tb=short 2>&1 | head -30`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.ingestion.anonymizer'`

---

### Task 2: U4 — PII Anonymizer Module (Implementation)

**Files:**
- Create: `backend/app/core/ingestion/anonymizer.py`

**Step 1: Write minimal implementation**

```python
"""PII anonymization for sensitive Indian court judgments.

Masks Aadhaar numbers, PAN numbers, and phone numbers in judgment text.
Detects POCSO / sexual assault cases for metadata flagging.
"""

from __future__ import annotations

import re

from app.core.ingestion.metadata import CaseMetadata

# ---------------------------------------------------------------------------
# PII masking patterns (adapted from logging_config.py but with distinct
# replacement labels so the audit trail shows *what* was masked)
# ---------------------------------------------------------------------------

# Aadhaar: 12 digits optionally space-separated in groups of 4.
# Require word boundary to avoid matching section numbers or years.
_AADHAAR_RE = re.compile(r"\b(\d{4})\s(\d{4})\s(\d{4})\b")
_AADHAAR_NOSPACE_RE = re.compile(r"\b\d{12}\b")

# PAN: AAAAA9999A (exactly 5 upper + 4 digits + 1 upper)
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

# Indian mobile: 10 digits starting 6-9, optional +91/91/0 prefix
_PHONE_RE = re.compile(
    r"(?:\+91[\s-]?|91[\s-]?|0)?[6-9]\d{9}\b"
)

# ---------------------------------------------------------------------------
# Sensitive case detection
# ---------------------------------------------------------------------------

# IPC sections related to sexual offences / child exploitation
_SENSITIVE_IPC_SECTIONS = frozenset({
    "354", "354A", "354B", "354C", "354D",
    "363", "366", "366A", "366B",
    "370", "372", "373",
    "375", "376", "376A", "376AB", "376B", "376C", "376D", "376DA", "376DB",
    "509",
})

# BNS equivalents (post-July 2024)
_SENSITIVE_BNS_SECTIONS = frozenset({
    "63", "64", "65", "66", "67", "68", "69", "70",
    "74", "75", "76", "77", "78", "79",
})

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
        (cleaned_text, was_modified) — was_modified is True if any PII was found.
    """
    original = full_text
    flags: list[str] = []

    result = _AADHAAR_RE.sub("[AADHAAR REDACTED]", full_text)
    result = _AADHAAR_NOSPACE_RE.sub("[AADHAAR REDACTED]", result)
    if result != full_text:
        flags.append("aadhaar_masked")
    prev = result

    result = _PAN_RE.sub("[PAN REDACTED]", result)
    if result != prev:
        flags.append("pan_masked")
    prev = result

    result = _PHONE_RE.sub("[PHONE REDACTED]", result)
    if result != prev:
        flags.append("phone_masked")

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
    if _SENSITIVE_KEYWORDS_RE.search(full_text):
        return True

    return False
```

**Step 2: Run tests to verify they pass**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_anonymizer.py -v --tb=short`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add backend/app/core/ingestion/anonymizer.py backend/tests/unit/test_anonymizer.py
git commit -m "feat(U4): add PII anonymizer for sensitive case detection and masking"
```

---

### Task 3: U3 — Statute Enrichment Module (Tests)

**Files:**
- Create: `backend/tests/unit/test_statute_enrichment.py`

**Step 1: Write the failing tests**

```python
"""Tests for ingestion-time statute cross-reference enrichment."""

import pytest

from app.core.legal.statute_enrichment import enrich_statute_cross_references


class TestEnrichStatuteCrossReferences:
    """Test bidirectional IPC<->BNS, CrPC<->BNSS, IEA<->BSA enrichment."""

    def test_ipc_302_adds_bns_103(self):
        acts = ["Indian Penal Code, Section 302"]
        result = enrich_statute_cross_references(acts)
        assert "Indian Penal Code, Section 302" in result
        assert "Bharatiya Nyaya Sanhita, Section 103" in result

    def test_bns_103_adds_ipc_302(self):
        acts = ["Bharatiya Nyaya Sanhita, Section 103"]
        result = enrich_statute_cross_references(acts)
        assert "Bharatiya Nyaya Sanhita, Section 103" in result
        assert "Indian Penal Code, Section 302" in result

    def test_crpc_438_adds_bnss_482(self):
        acts = ["Code of Criminal Procedure, Section 438"]
        result = enrich_statute_cross_references(acts)
        assert "Code of Criminal Procedure, Section 438" in result
        assert "Bharatiya Nagarik Suraksha Sanhita, Section 482" in result

    def test_bnss_482_adds_crpc_438(self):
        acts = ["Bharatiya Nagarik Suraksha Sanhita, Section 482"]
        result = enrich_statute_cross_references(acts)
        assert "Code of Criminal Procedure, Section 438" in result

    def test_evidence_65b_adds_bsa_63(self):
        acts = ["Indian Evidence Act, Section 65B"]
        result = enrich_statute_cross_references(acts)
        assert "Bharatiya Sakshya Adhiniyam, Section 63" in result

    def test_bsa_63_adds_evidence_65b(self):
        acts = ["Bharatiya Sakshya Adhiniyam, Section 63"]
        result = enrich_statute_cross_references(acts)
        assert "Indian Evidence Act, Section 65B" in result

    def test_non_criminal_acts_unchanged(self):
        acts = ["Constitution of India, Article 21", "Arbitration and Conciliation Act"]
        result = enrich_statute_cross_references(acts)
        assert result == sorted(acts)

    def test_empty_list(self):
        assert enrich_statute_cross_references([]) == []

    def test_no_duplicates(self):
        acts = [
            "Indian Penal Code, Section 302",
            "Bharatiya Nyaya Sanhita, Section 103",  # already present
        ]
        result = enrich_statute_cross_references(acts)
        # Should not have duplicates
        assert len(result) == len(set(result))

    def test_multiple_sections_enriched(self):
        acts = [
            "Indian Penal Code, Section 302",
            "Indian Penal Code, Section 376",
            "Code of Criminal Procedure, Section 482",
        ]
        result = enrich_statute_cross_references(acts)
        assert "Bharatiya Nyaya Sanhita, Section 103" in result
        assert "Bharatiya Nyaya Sanhita, Section 63" in result  # IPC 376 -> BNS 63
        assert "Bharatiya Nagarik Suraksha Sanhita, Section 528" in result

    def test_with_year_suffix_ignored(self):
        """Entries like 'Indian Penal Code, 1860' without a section should pass through."""
        acts = ["Indian Penal Code, 1860"]
        result = enrich_statute_cross_references(acts)
        assert "Indian Penal Code, 1860" in result

    def test_short_name_ipc(self):
        """Short name 'IPC' in acts_cited should be recognized."""
        acts = ["IPC, Section 420"]
        result = enrich_statute_cross_references(acts)
        assert any("BNS" in a or "Bharatiya Nyaya Sanhita" in a for a in result)
```

**Step 2: Run test to verify it fails**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_statute_enrichment.py -v --tb=short 2>&1 | head -20`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.legal.statute_enrichment'`

---

### Task 4: U3 — Statute Enrichment Module (Implementation)

**Files:**
- Create: `backend/app/core/legal/statute_enrichment.py`

**Step 1: Write minimal implementation**

```python
"""Ingestion-time statute cross-reference enrichment.

Adds bidirectional old-law <-> new-law references to acts_cited metadata
so that Pinecone filter queries find cases regardless of which statute
version was originally cited.
"""

from __future__ import annotations

import re

from app.core.legal.constants import (
    CRPC_TO_BNSS_MAP,
    EVIDENCE_TO_BSA_MAP,
    IPC_TO_BNS_MAP,
)

# Mapping: (old_name_patterns, old_full_name, new_full_name, forward_map)
_ENRICHMENT_RULES: list[tuple[list[str], str, str, dict[str, str]]] = [
    (
        ["Indian Penal Code", "IPC", "I.P.C."],
        "Indian Penal Code",
        "Bharatiya Nyaya Sanhita",
        IPC_TO_BNS_MAP,
    ),
    (
        ["Code of Criminal Procedure", "CrPC", "Cr.P.C."],
        "Code of Criminal Procedure",
        "Bharatiya Nagarik Suraksha Sanhita",
        CRPC_TO_BNSS_MAP,
    ),
    (
        ["Indian Evidence Act", "Evidence Act", "IEA"],
        "Indian Evidence Act",
        "Bharatiya Sakshya Adhiniyam",
        EVIDENCE_TO_BSA_MAP,
    ),
]

# Pre-compute reverse maps and new-name patterns
_REVERSE_RULES: list[tuple[list[str], str, str, dict[str, str]]] = []
for _old_patterns, _old_name, _new_name, _fwd_map in _ENRICHMENT_RULES:
    _rev_map = {v: k for k, v in _fwd_map.items()}
    _REVERSE_RULES.append(([_new_name], _new_name, _old_name, _rev_map))

# Section extraction regex: "Section 302", "Section 65B", "Section 3(5)"
_SECTION_RE = re.compile(r"Section\s+([\w()]+)", re.IGNORECASE)


def enrich_statute_cross_references(acts_cited: list[str]) -> list[str]:
    """Add cross-references for old<->new criminal statutes.

    For each IPC/CrPC/IEA reference with a section number, adds the
    corresponding BNS/BNSS/BSA equivalent and vice versa.

    Args:
        acts_cited: List of act reference strings from metadata.

    Returns:
        Deduplicated, sorted list with both old and new statute references.
    """
    if not acts_cited:
        return []

    enriched: set[str] = set(acts_cited)

    for entry in acts_cited:
        entry_upper = entry.upper()

        # Try forward rules (old -> new)
        for name_patterns, _old_name, new_name, fwd_map in _ENRICHMENT_RULES:
            if any(p.upper() in entry_upper for p in name_patterns):
                section_match = _SECTION_RE.search(entry)
                if section_match:
                    section = section_match.group(1)
                    mapped = fwd_map.get(section) or fwd_map.get(section.upper())
                    if mapped:
                        enriched.add(f"{new_name}, Section {mapped}")
                break  # Only one rule should match per entry

        # Try reverse rules (new -> old)
        for name_patterns, _new_name, old_name, rev_map in _REVERSE_RULES:
            if any(p.upper() in entry_upper for p in name_patterns):
                section_match = _SECTION_RE.search(entry)
                if section_match:
                    section = section_match.group(1)
                    mapped = rev_map.get(section) or rev_map.get(section.upper())
                    if mapped:
                        enriched.add(f"{old_name}, Section {mapped}")
                break

    return sorted(enriched)
```

**Step 2: Run tests to verify they pass**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_statute_enrichment.py -v --tb=short`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add backend/app/core/legal/statute_enrichment.py backend/tests/unit/test_statute_enrichment.py
git commit -m "feat(U3): add ingestion-time statute cross-reference enrichment (IPC<->BNS, CrPC<->BNSS, IEA<->BSA)"
```

---

### Task 5: U2 — HC Citation Format Expansion (Tests)

**Files:**
- Modify: `backend/tests/unit/test_extractor.py`

**Step 1: Add failing tests for new reporters and catch-all**

Append to the existing test file:

```python
class TestExpandedHCReporters:
    """Test newly added HC reporter patterns."""

    def test_lnind_citation(self):
        text = "2020 LNIND 145"
        citations = extract_citations(text)
        assert any(c.reporter == "LNIND" and c.year == 2020 for c in citations)

    def test_cdj_citation(self):
        text = "(2021) CDJ 300"
        citations = extract_citations(text)
        assert any(c.reporter == "CDJ" and c.year == 2021 for c in citations)

    def test_bomlr_citation(self):
        text = "2019 BomLR 450"
        citations = extract_citations(text)
        assert any(c.reporter.upper() == "BOMLR" and c.year == 2019 for c in citations)

    def test_calwn_citation(self):
        text = "(2022) CalWN 120"
        citations = extract_citations(text)
        assert any(c.reporter.upper() == "CALWN" and c.year == 2022 for c in citations)

    def test_wlr_citation(self):
        text = "2023 WLR 88"
        citations = extract_citations(text)
        assert any(c.reporter == "WLR" and c.year == 2023 for c in citations)

    def test_mplj_citation(self):
        text = "(2020) 2 MPLJ 300"
        citations = extract_citations(text)
        assert any(c.reporter == "MPLJ" and c.year == 2020 for c in citations)


class TestGenericReporterCatchAll:
    """Test catch-all pattern for unknown reporter formats."""

    def test_unknown_reporter_caught(self):
        text = "2023 XYZLR 456"
        citations = extract_citations(text)
        assert any(c.reporter == "Unknown" and c.year == 2023 for c in citations)

    def test_catch_all_does_not_duplicate_known(self):
        """Known reporters should NOT produce an extra Unknown citation."""
        text = "(2020) 3 SCC 145"
        citations = extract_citations(text)
        assert not any(c.reporter == "Unknown" for c in citations)

    def test_catch_all_capped_at_10(self):
        """At most 10 catch-all matches per document."""
        lines = [f"2020 REP{i} {100 + i}" for i in range(20)]
        text = "\n".join(lines)
        citations = extract_citations(text)
        unknown_count = sum(1 for c in citations if c.reporter == "Unknown")
        assert unknown_count <= 10
```

**Step 2: Run tests to verify they fail**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_extractor.py::TestExpandedHCReporters -v --tb=short 2>&1 | head -20`
Expected: FAIL (new reporters not in pattern)

---

### Task 6: U2 — HC Citation Format Expansion (Implementation)

**Files:**
- Modify: `backend/app/core/legal/extractor.py:128-137` (HC_REPORTER_PATTERN)
- Modify: `backend/app/core/legal/extractor.py:357-617` (extract_citations function — add catch-all at the end)

**Step 1: Expand HC_REPORTER_PATTERN**

In `extractor.py`, replace the HC_REPORTER_PATTERN definition (lines 132-137):

```python
# ILR, MLJ, KLT, BLR, GLR, ALJ, DLT, ALD, CLT, PLR, DRJ, KHC, RLW,
# LNIND, CDJ, BomLR, CalWN, WLC, JLJ, AIJEL, CriLJ, FLR, GujLR, MPLJ, OLR, WLR
# Matches: "2020 ILR 145" or "(2020) 3 ILR 145" or "(2020) ILR 145"
HC_REPORTER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(\d{4})\s+|\((\d{4})\)\s+(?:\d+\s+)?)"
    r"(ILR|MLJ|KLT|BLR|GLR|ALJ|DLT|ALD|CLT|PLR|DRJ|KHC|RLW"
    r"|LNIND|CDJ|BomLR|CalWN|WLC|JLJ|AIJEL|CriLJ|FLR|GujLR|MPLJ|OLR|WLR)"
    r"\s+(\d+)",
    re.IGNORECASE,
)
```

**Step 2: Add GENERIC_REPORTER_PATTERN and catch-all logic**

Add pattern after LLJ_PATTERN (after line 190):

```python
# --- Generic catch-all for unknown reporter formats ---

# Matches: "2020 XYZ 145" or "(2020) 3 XYZ 145" where XYZ is 2-6 letter abbreviation.
# Runs LAST in extract_citations() to avoid duplicating known patterns.
# Capped at 10 matches per document.
GENERIC_REPORTER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(\d{4})\s+|\((\d{4})\)\s+(?:\d+\s+)?)"
    r"([A-Z][A-Za-z]{1,5})"
    r"\s+(\d+)"
)
```

Then modify `extract_citations()` function. At the top of the function, add a `seen_spans` set. After each `_add()` call, record the match span. At the end (before `return citations`), add the catch-all loop:

Replace the `extract_citations` function to track spans. Add `seen_spans: set[tuple[int, int]] = set()` after `seen_raw`. After each pattern's for-loop `_add()` call, also do `seen_spans.add((match.start(), match.end()))`.

Then before the `return citations` line, add:

```python
    # --- Catch-all for unknown reporters --- runs LAST, skips known spans ---
    catch_all_count = 0
    for match in GENERIC_REPORTER_PATTERN.finditer(text):
        if catch_all_count >= 10:
            break
        # Skip if this span overlaps any already-matched span
        m_start, m_end = match.start(), match.end()
        if any(
            not (m_end <= s_start or m_start >= s_end)
            for s_start, s_end in seen_spans
        ):
            continue
        year = match.group(1) or match.group(2)
        reporter_name = match.group(3)
        # Skip common English words that could false-match
        if reporter_name.upper() in {
            "THE", "AND", "FOR", "NOT", "BUT", "WAS", "HAS", "HAD",
            "ARE", "HIS", "HER", "ITS", "ANY", "ALL", "MAY", "CAN",
            "ACT", "THAT", "THIS", "WITH", "FROM", "BEEN", "HAVE",
            "ALSO", "SUCH", "UPON", "INTO", "OVER", "SAID", "CASE",
            "COURT", "ORDER", "UNDER", "SHALL", "STATE", "INDIA",
            "WHICH", "WHERE", "WOULD", "COULD", "SHOULD",
        }:
            continue
        _add(Citation(
            reporter="Unknown",
            year=int(year),
            volume=None,
            page=match.group(4),
            court=None,
            raw_text=match.group(0),
        ))
        seen_spans.add((m_start, m_end))
        catch_all_count += 1
```

**Step 3: Run tests to verify they pass**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_extractor.py -v --tb=short`
Expected: All existing + new tests PASS

**Step 4: Commit**

```bash
git add backend/app/core/legal/extractor.py backend/tests/unit/test_extractor.py
git commit -m "feat(U2): expand HC reporter patterns + add catch-all for unknown citation formats"
```

---

### Task 7: U1 — Hindi FTS Skip (Tests)

**Files:**
- Create: `backend/tests/unit/test_hindi_fts_skip.py`

**Step 1: Write the failing tests**

```python
"""Tests for Hindi FTS skip behavior in search layer."""

import pytest

from app.core.search.fulltext import search_fulltext


class TestHindiFTSSkip:
    """When language='hi', FTS should return empty immediately."""

    @pytest.mark.asyncio
    async def test_hindi_fts_returns_empty(self):
        """Hindi queries should skip FTS entirely."""
        # search_fulltext with language="hi" should return [] without DB call
        result = await search_fulltext(
            "धारा 302 भारतीय दंड संहिता",
            language="hi",
            db=None,  # Should never touch DB
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_english_fts_requires_db(self):
        """English queries should NOT skip FTS (will fail without DB, proving it tries)."""
        with pytest.raises(Exception):
            await search_fulltext(
                "Section 302 IPC",
                language="en",
                db=None,  # Will fail because it tries to use DB
            )

    @pytest.mark.asyncio
    async def test_default_language_is_english(self):
        """Default language should be 'en' (backward compatible)."""
        with pytest.raises(Exception):
            await search_fulltext(
                "murder conviction",
                db=None,  # Will fail because default is English -> needs DB
            )
```

**Step 2: Run tests to verify they fail**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_hindi_fts_skip.py -v --tb=short 2>&1 | head -20`
Expected: FAIL (language param not accepted yet)

---

### Task 8: U1 — Hindi FTS Skip (Implementation)

**Files:**
- Modify: `backend/app/core/search/fulltext.py:38-44` (add language param)
- Modify: `backend/app/core/search/hybrid.py:123-135` (add language param)
- Modify: `backend/app/api/routes/search.py:64-68` (pass language)

**Step 1: Modify `search_fulltext` to accept language parameter**

In `fulltext.py`, update the function signature (line 38-44):

```python
async def search_fulltext(
    query: str,
    *,
    filters: SearchFilters | None = None,
    limit: int = 20,
    db: AsyncSession,
    language: str = "en",
) -> list[FTSResult]:
```

Add early return after line 51 (`if not query.strip(): return []`):

```python
    # Hindi/Devanagari text cannot be tokenized by PostgreSQL's English
    # tsvector. Skip FTS and rely on vector search for Hindi queries.
    if language == "hi":
        return []
```

**Step 2: Modify `hybrid_search` to accept and use language**

In `hybrid.py`, update the function signature (line 123-135) — add `language: str = "en"` parameter:

```python
async def hybrid_search(
    query: str,
    *,
    filters: SearchFilters | None = None,
    page: int = 1,
    page_size: int | None = None,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
    redis_client=None,
    language: str = "en",
) -> SearchResponse:
```

In the `else` block (lines 200-246), modify the parallel retrieval to skip FTS for Hindi:

Replace lines 200-226:

```python
    else:
        # Parallel retrieval — vector + FTS
        vector_task = _vector_search(
            search_query,
            embedder=embedder,
            vector_store=vector_store,
            filters=merged_filters,
        )

        if language == "hi":
            # Hindi: skip FTS entirely, vector-only search
            vector_results = await vector_task
            fts_results: list[FTSResult] = []
        else:
            fts_task = search_fulltext(
                fts_query,
                filters=merged_filters,
                limit=settings.search_fts_top_k,
                db=db,
                language=language,
            )

            gather_results = await asyncio.gather(
                vector_task, fts_task, return_exceptions=True
            )
            vector_results = (
                gather_results[0]
                if not isinstance(gather_results[0], Exception)
                else []
            )
            fts_results = (
                gather_results[1]
                if not isinstance(gather_results[1], Exception)
                else []
            )
            if isinstance(gather_results[0], Exception):
                logger.warning("Vector search failed, using FTS only: %s", gather_results[0])
            if isinstance(gather_results[1], Exception):
                logger.warning("FTS failed, using vector only: %s", gather_results[1])
```

Also update the strategy weights section (lines 236-241) — force `vector_heavy` for Hindi:

```python
        strategy_weights: dict[str, list[float]] = {
            "keyword_heavy": [1.0, 2.0],
            "vector_heavy": [2.0, 1.0],
            "balanced": [1.0, 1.0],
        }
        # Hindi: force vector-heavy since FTS is skipped
        if language == "hi":
            weights = [2.0, 0.0]
        else:
            weights = strategy_weights.get(strategy)
```

Also update the `exact_match` FTS fallback (line 190-195) to pass language:

```python
        fts_results = await search_fulltext(
            fts_query,
            filters=merged_filters,
            limit=settings.search_fts_top_k,
            db=db,
            language=language,
        )
```

**Step 3: Modify search route to pass language**

In `search.py`, update the `hybrid_search()` call (find the call around lines 100-120) to include `language=language`:

Add `language=language` to the keyword arguments of `hybrid_search(...)`.

Also, after the language detection block (line 64-68), capture the detected language:

```python
    detected_language = "en"
    if language == "hi":
        translator = get_translator()
        detected_lang = await translator.detect_language(q)
        if detected_lang == "hi":
            q = await translator.translate(q, source="hi", target="en")
            detected_language = "hi"
```

Then pass `language=detected_language` to `hybrid_search()`.

**Step 4: Run tests**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/test_hindi_fts_skip.py tests/unit/test_hindi_search.py -v --tb=short`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/search/fulltext.py backend/app/core/search/hybrid.py backend/app/api/routes/search.py backend/tests/unit/test_hindi_fts_skip.py
git commit -m "feat(U1): skip FTS for Hindi queries, rely on vector search only"
```

---

### Task 9: Pipeline Integration (U3 + U4)

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:44,103,182`
- Modify: `backend/app/core/ingestion/metadata.py:77-115`

**Step 1: Add fields to CaseMetadata**

In `metadata.py`, add to the `CaseMetadata` dataclass (after line 114):

```python
    # U4: Anonymization tracking
    is_anonymized: bool = False
    anonymization_flags: list[str] | None = None
```

**Step 2: Add imports to pipeline.py**

Add to the imports section (after line 44):

```python
from app.core.ingestion.anonymizer import anonymize_text, detect_sensitive_case
from app.core.legal.statute_enrichment import enrich_statute_cross_references
```

**Step 3: Insert anonymization after text extraction**

In `pipeline.py`, after line 103 (`full_text = quality.text`), add:

```python
    # ------------------------------------------------------------------
    # 1a. PII ANONYMIZATION (masks Aadhaar/PAN/phone before any storage)
    # ------------------------------------------------------------------
    full_text, pii_masked = anonymize_text(full_text)
```

**Step 4: Insert enrichment + detection after regex acts supplementation**

After line 182 (`provenance["acts_cited"] = "llm+regex"`), add:

```python
    # Enrich acts_cited with old<->new statute cross-references (U3)
    if metadata.acts_cited:
        metadata.acts_cited = enrich_statute_cross_references(metadata.acts_cited)
        provenance["acts_cited"] = provenance.get("acts_cited", "llm") + "+enriched"

    # Detect sensitive cases and set anonymization flags (U4)
    anonymization_flags: list[str] = []
    if pii_masked:
        anonymization_flags.append("pii_masked")
    if detect_sensitive_case(full_text, metadata):
        metadata.is_anonymized = True
        anonymization_flags.append("sensitive_case_detected")
    if anonymization_flags:
        metadata.anonymization_flags = anonymization_flags
```

**Step 5: Run full test suite**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/ -x --tb=short -q 2>&1 | tail -20`
Expected: All tests PASS (no regressions)

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/app/core/ingestion/metadata.py
git commit -m "feat: integrate U3 statute enrichment + U4 PII anonymization into ingestion pipeline"
```

---

### Task 10: Migration 015

**Files:**
- Create: `backend/migrations/versions/015_india_audit_fixes.py`

**Step 1: Write the migration**

```python
"""Add Hindi FTS infrastructure and anonymization tracking columns.

Revision ID: 015
Revises: 014
Create Date: 2026-03-17

Changes:
1. Add hindi_searchable_text TSVECTOR column with 'simple' config trigger
2. Add GIN index on hindi_searchable_text
3. Add is_anonymized BOOLEAN column
4. Add anonymization_flags TEXT[] column
"""

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. Hindi FTS infrastructure (forward-looking)
    # ----------------------------------------------------------------
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS "
        "hindi_searchable_text tsvector"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_hindi_searchable_text "
        "ON cases USING gin (hindi_searchable_text) "
        "WHERE hindi_searchable_text IS NOT NULL"
    )

    # Trigger: populate hindi_searchable_text only when language = 'hindi'
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_hindi_searchable_update() RETURNS trigger AS $$
        BEGIN
            IF NEW.language = 'hindi' THEN
                NEW.hindi_searchable_text :=
                    setweight(to_tsvector('simple', COALESCE(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(NEW.headnotes, '')), 'B') ||
                    setweight(to_tsvector('simple', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                    setweight(to_tsvector('simple', COALESCE(LEFT(NEW.full_text, 500000), '')), 'D');
            ELSE
                NEW.hindi_searchable_text := NULL;
            END IF;
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER cases_hindi_searchable_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_hindi_searchable_update();
    """)

    # ----------------------------------------------------------------
    # 2. Anonymization tracking columns
    # ----------------------------------------------------------------
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS "
        "is_anonymized BOOLEAN DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS "
        "anonymization_flags TEXT[] DEFAULT '{}'"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS cases_hindi_searchable_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_hindi_searchable_update()")
    op.execute("DROP INDEX IF EXISTS idx_cases_hindi_searchable_text")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS hindi_searchable_text")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS is_anonymized")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS anonymization_flags")
```

**Step 2: Commit**

```bash
git add backend/migrations/versions/015_india_audit_fixes.py
git commit -m "feat: add migration 015 — Hindi tsvector infrastructure + anonymization columns"
```

---

### Task 11: Update Case Model

**Files:**
- Modify: `backend/app/models/case.py`

**Step 1: Add new columns to SQLAlchemy model**

Find the `Case` model class and add after existing column definitions:

```python
    hindi_searchable_text: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    is_anonymized: Mapped[bool] = mapped_column(default=False, server_default="false")
    anonymization_flags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
```

**Step 2: Run existing tests to verify no regressions**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/ -x --tb=short -q 2>&1 | tail -10`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add backend/app/models/case.py
git commit -m "feat: add hindi_searchable_text, is_anonymized, anonymization_flags to Case model"
```

---

### Task 12: Full Test Suite Verification

**Step 1: Run complete backend test suite**

Run: `cd d:/Startup/Smriti/backend && python -m pytest tests/unit/ -v --tb=short -q 2>&1 | tail -30`
Expected: All tests PASS (including the 4 env-dependent failures that need encryption_key)

**Step 2: Run frontend tests**

Run: `cd d:/Startup/Smriti/frontend && npm test -- --run 2>&1 | tail -20`
Expected: All 298 frontend tests PASS (no frontend changes in this plan)

**Step 3: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: address test failures from India audit fixes"
```
