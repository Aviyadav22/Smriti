# Drafting Agent V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the Drafting Agent from 7 to 17 document types, add court-specific formatting, wire BNS/BNSS/BSA mappings, build research-to-draft bridge, and add 4 differentiating features (overruled shield, citation graph suggestions, statute text injection, companion affidavit).

**Architecture:** No graph structure changes. Add data modules (court profiles, templates, prompts) and wire existing infrastructure (amendment_service, treatment.py, Neo4j graph, Pinecone statutes) into existing drafting nodes. New `/drafting/from-research` and updated `/drafting/templates` endpoints.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, SQLAlchemy (async), Pinecone, Neo4j, python-docx, ReportLab

**Design doc:** `docs/plans/2026-04-02-drafting-agent-v2-design.md`

**Test runner:** `cd backend && python -m pytest tests/unit/<test_file>.py -v`

---

## Task 1: Extend DocumentTemplate Dataclass with V2 Fields

**Files:**
- Modify: `backend/app/core/drafting/templates.py:13-33` (DocumentTemplate dataclass)
- Modify: `backend/app/core/drafting/templates.py:36-189` (all 7 existing TEMPLATES entries)
- Test: `backend/tests/unit/test_drafting_templates.py`

**Step 1: Write the failing tests**

Add to `backend/tests/unit/test_drafting_templates.py`:

```python
# Add after the existing TestTemplates class (line ~159)

class TestTemplateV2Fields:
    """V2 fields: category, argument_style, requires_affidavit."""

    def test_every_template_has_category(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert hasattr(template, "category"), f"TEMPLATES['{doc_type}'] missing 'category'"
            assert template.category in (
                "criminal", "civil", "constitutional", "family", "commercial", "transactional",
            ), f"TEMPLATES['{doc_type}'].category='{template.category}' is invalid"

    def test_every_template_has_argument_style(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert hasattr(template, "argument_style"), f"TEMPLATES['{doc_type}'] missing 'argument_style'"
            assert template.argument_style in ("irac", "crac"), (
                f"TEMPLATES['{doc_type}'].argument_style='{template.argument_style}' must be 'irac' or 'crac'"
            )

    def test_every_template_has_requires_affidavit(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert hasattr(template, "requires_affidavit"), f"TEMPLATES['{doc_type}'] missing 'requires_affidavit'"
            assert isinstance(template.requires_affidavit, bool)

    def test_bail_application_is_crac_and_requires_affidavit(self) -> None:
        t = TEMPLATES["bail_application"]
        assert t.category == "criminal"
        assert t.argument_style == "crac"
        assert t.requires_affidavit is True

    def test_legal_notice_is_irac_and_no_affidavit(self) -> None:
        t = TEMPLATES["legal_notice"]
        assert t.category == "transactional"
        assert t.argument_style == "irac"
        assert t.requires_affidavit is False
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_drafting_templates.py::TestTemplateV2Fields -v`
Expected: FAIL — `AttributeError: 'DocumentTemplate' has no attribute 'category'`

**Step 3: Add V2 fields to DocumentTemplate and update existing 7 templates**

In `backend/app/core/drafting/templates.py`, add 3 fields to the dataclass (after `prompt_key` at line 33):

```python
    category: str              # "criminal", "civil", "constitutional", "family", "commercial", "transactional"
    argument_style: str        # "irac" (factual) or "crac" (advocacy, conclusion-first)
    requires_affidavit: bool   # Whether to auto-generate a companion affidavit
```

Then add these 3 fields to each of the 7 existing template entries:

| Template | category | argument_style | requires_affidavit |
|----------|----------|---------------|-------------------|
| bail_application | "criminal" | "crac" | True |
| writ_petition_226 | "constitutional" | "crac" | True |
| writ_petition_32 | "constitutional" | "crac" | True |
| written_statement | "civil" | "irac" | False |
| legal_notice | "transactional" | "irac" | False |
| appeal | "constitutional" | "crac" | True |
| interim_application | "civil" | "crac" | True |

**Step 4: Fix the existing template count test**

In `test_drafting_templates.py`, the test `test_all_seven_templates_exist_in_templates_dict` (line 45-46) does a strict `==` check on keys. It will still pass since we haven't added new templates yet. Leave it for now — it will be updated in Task 3.

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_drafting_templates.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/core/drafting/templates.py backend/tests/unit/test_drafting_templates.py
git commit -m "feat(drafting): add V2 fields to DocumentTemplate (category, argument_style, requires_affidavit)"
```

---

## Task 2: Create Court Profiles Module

**Files:**
- Create: `backend/app/core/drafting/court_profiles.py`
- Create: `backend/tests/unit/test_court_profiles.py`

**Step 1: Write the failing tests**

Create `backend/tests/unit/test_court_profiles.py`:

```python
"""Tests for court formatting profiles."""
from __future__ import annotations

import pytest

from app.core.drafting.court_profiles import (
    COURT_PROFILES,
    CourtProfile,
    get_court_profile,
)


class TestCourtProfile:
    def test_supreme_court_profile_exists(self) -> None:
        profile = COURT_PROFILES["supreme_court"]
        assert isinstance(profile, CourtProfile)
        assert profile.court_id == "supreme_court"

    def test_supreme_court_has_correct_formatting(self) -> None:
        p = COURT_PROFILES["supreme_court"]
        assert p.font_size_body == 14
        assert p.line_spacing == 1.5
        assert p.margin_left_cm == 4.0
        assert p.margin_right_cm == 4.0
        assert p.margin_top_cm == 2.0
        assert p.margin_bottom_cm == 2.0
        assert p.paper_size == "A4"
        assert p.requires_synopsis is True
        assert p.print_both_sides is True

    def test_delhi_hc_profile_exists(self) -> None:
        p = COURT_PROFILES["delhi_hc"]
        assert p.font_size_body == 14
        assert p.line_spacing == 2.0

    def test_bombay_hc_uses_legal_paper(self) -> None:
        p = COURT_PROFILES["bombay_hc"]
        assert p.paper_size == "legal"

    def test_default_profile_exists(self) -> None:
        p = COURT_PROFILES["default"]
        assert p.font_size_body == 12
        assert p.paper_size == "A4"

    def test_all_eight_profiles_exist(self) -> None:
        expected = {
            "supreme_court", "delhi_hc", "bombay_hc", "madras_hc",
            "karnataka_hc", "calcutta_hc", "nclt", "default",
        }
        assert set(COURT_PROFILES.keys()) == expected

    def test_profiles_are_frozen(self) -> None:
        p = COURT_PROFILES["supreme_court"]
        with pytest.raises((AttributeError, TypeError)):
            p.font_size_body = 10  # type: ignore[misc]


class TestGetCourtProfile:
    def test_exact_match(self) -> None:
        p = get_court_profile("supreme_court")
        assert p.court_id == "supreme_court"

    def test_alias_sc(self) -> None:
        p = get_court_profile("SC")
        assert p.court_id == "supreme_court"

    def test_alias_supreme_court_text(self) -> None:
        p = get_court_profile("Supreme Court")
        assert p.court_id == "supreme_court"

    def test_alias_delhi_high_court(self) -> None:
        p = get_court_profile("Delhi High Court")
        assert p.court_id == "delhi_hc"

    def test_alias_dhc(self) -> None:
        p = get_court_profile("DHC")
        assert p.court_id == "delhi_hc"

    def test_alias_bombay_hc(self) -> None:
        p = get_court_profile("Bombay HC")
        assert p.court_id == "bombay_hc"

    def test_alias_nclt(self) -> None:
        p = get_court_profile("NCLT")
        assert p.court_id == "nclt"

    def test_unknown_court_returns_default(self) -> None:
        p = get_court_profile("Allahabad High Court")
        assert p.court_id == "default"

    def test_empty_string_returns_default(self) -> None:
        p = get_court_profile("")
        assert p.court_id == "default"

    def test_case_insensitive(self) -> None:
        p = get_court_profile("DELHI HIGH COURT")
        assert p.court_id == "delhi_hc"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_court_profiles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.drafting.court_profiles'`

**Step 3: Implement court_profiles.py**

Create `backend/app/core/drafting/court_profiles.py`:

```python
"""Court-specific formatting profiles for Indian legal document export.

Each profile encodes the margin, font, spacing, and structural requirements
for a specific court or tribunal per their latest practice directions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class CourtProfile:
    """Immutable formatting profile for a specific court."""

    court_id: str
    display_name: str
    paper_size: str           # "A4" or "legal"
    font_name: str            # Always "Times New Roman" for Indian courts
    font_size_body: int
    font_size_heading: int
    font_size_quote: int
    line_spacing: float
    margin_top_cm: float
    margin_bottom_cm: float
    margin_left_cm: float
    margin_right_cm: float
    header_format: str
    requires_synopsis: bool
    requires_affidavit: bool
    numbering_style: str      # "arabic" or "roman"
    print_both_sides: bool


COURT_PROFILES: Final[dict[str, CourtProfile]] = {
    "supreme_court": CourtProfile(
        court_id="supreme_court",
        display_name="Supreme Court of India",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=14,
        font_size_heading=16,
        font_size_quote=12,
        line_spacing=1.5,
        margin_top_cm=2.0,
        margin_bottom_cm=2.0,
        margin_left_cm=4.0,
        margin_right_cm=4.0,
        header_format="IN THE HON'BLE SUPREME COURT OF INDIA",
        requires_synopsis=True,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=True,
    ),
    "delhi_hc": CourtProfile(
        court_id="delhi_hc",
        display_name="High Court of Delhi",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=14,
        font_size_heading=16,
        font_size_quote=12,
        line_spacing=2.0,
        margin_top_cm=2.54,
        margin_bottom_cm=1.91,
        margin_left_cm=3.18,
        margin_right_cm=3.18,
        header_format="IN THE HIGH COURT OF DELHI AT NEW DELHI",
        requires_synopsis=True,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "bombay_hc": CourtProfile(
        court_id="bombay_hc",
        display_name="High Court of Bombay",
        paper_size="legal",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=3.81,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT OF JUDICATURE AT BOMBAY",
        requires_synopsis=True,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "madras_hc": CourtProfile(
        court_id="madras_hc",
        display_name="High Court of Madras",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT OF JUDICATURE AT MADRAS",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "karnataka_hc": CourtProfile(
        court_id="karnataka_hc",
        display_name="High Court of Karnataka",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT OF KARNATAKA AT BENGALURU",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "calcutta_hc": CourtProfile(
        court_id="calcutta_hc",
        display_name="High Court of Calcutta",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT AT CALCUTTA",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "nclt": CourtProfile(
        court_id="nclt",
        display_name="National Company Law Tribunal",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="BEFORE THE NATIONAL COMPANY LAW TRIBUNAL, {bench} BENCH",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "default": CourtProfile(
        court_id="default",
        display_name="Default",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE COURT OF {court}",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
}


# Alias map: normalized string → court_id
_COURT_ALIASES: Final[dict[str, str]] = {
    "supreme court": "supreme_court",
    "supreme court of india": "supreme_court",
    "sc": "supreme_court",
    "sci": "supreme_court",
    "hon'ble supreme court": "supreme_court",
    "delhi high court": "delhi_hc",
    "delhi hc": "delhi_hc",
    "dhc": "delhi_hc",
    "high court of delhi": "delhi_hc",
    "bombay high court": "bombay_hc",
    "bombay hc": "bombay_hc",
    "bhc": "bombay_hc",
    "high court of bombay": "bombay_hc",
    "mumbai high court": "bombay_hc",
    "madras high court": "madras_hc",
    "madras hc": "madras_hc",
    "mhc": "madras_hc",
    "high court of madras": "madras_hc",
    "chennai high court": "madras_hc",
    "karnataka high court": "karnataka_hc",
    "karnataka hc": "karnataka_hc",
    "khc": "karnataka_hc",
    "high court of karnataka": "karnataka_hc",
    "bangalore high court": "karnataka_hc",
    "bengaluru high court": "karnataka_hc",
    "calcutta high court": "calcutta_hc",
    "calcutta hc": "calcutta_hc",
    "chc": "calcutta_hc",
    "high court of calcutta": "calcutta_hc",
    "kolkata high court": "calcutta_hc",
    "nclt": "nclt",
    "nclat": "nclt",
    "national company law tribunal": "nclt",
}


def get_court_profile(target_court: str) -> CourtProfile:
    """Look up a court profile by name or alias.

    Performs case-insensitive fuzzy matching against COURT_ALIASES.
    Returns the ``default`` profile for unrecognized courts.
    """
    if not target_court or not target_court.strip():
        return COURT_PROFILES["default"]

    normalized = target_court.strip().lower()

    # Direct match on court_id
    if normalized in COURT_PROFILES:
        return COURT_PROFILES[normalized]

    # Alias match
    court_id = _COURT_ALIASES.get(normalized)
    if court_id:
        return COURT_PROFILES[court_id]

    # Fallback
    return COURT_PROFILES["default"]
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_court_profiles.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/drafting/court_profiles.py backend/tests/unit/test_court_profiles.py
git commit -m "feat(drafting): add court formatting profiles for SC, 5 HCs, NCLT"
```

---

## Task 3: Add 10 New Document Templates

**Files:**
- Modify: `backend/app/core/drafting/templates.py:36-189` (add 10 new entries)
- Modify: `backend/tests/unit/test_drafting_templates.py:28-36` (update expected doc types)

**Step 1: Update the test expectations**

In `backend/tests/unit/test_drafting_templates.py`, update `_EXPECTED_DOC_TYPES` (line 28-36) to include all 17:

```python
_EXPECTED_DOC_TYPES = {
    # V1
    "bail_application",
    "writ_petition_226",
    "writ_petition_32",
    "written_statement",
    "legal_notice",
    "appeal",
    "interim_application",
    # V2
    "anticipatory_bail",
    "quashing_petition_482",
    "demand_notice_138",
    "plaint",
    "reply_to_notice",
    "slp",
    "divorce_petition",
    "maintenance_application",
    "consumer_complaint",
    "affidavit",
}
```

Add V2-specific template tests:

```python
class TestV2Templates:
    def test_anticipatory_bail_sections(self) -> None:
        t = TEMPLATES["anticipatory_bail"]
        assert "apprehension_of_arrest" in t.sections
        assert "grounds_for_anticipatory_bail" in t.sections
        assert "conditions_offered" in t.sections
        assert t.category == "criminal"
        assert t.argument_style == "crac"

    def test_slp_has_synopsis_and_questions_of_law(self) -> None:
        t = TEMPLATES["slp"]
        assert "synopsis" in t.sections
        assert "list_of_dates" in t.sections
        assert "questions_of_law" in t.sections
        assert t.category == "constitutional"

    def test_plaint_has_jurisdiction_and_limitation(self) -> None:
        t = TEMPLATES["plaint"]
        assert "jurisdiction_and_valuation" in t.sections
        assert "limitation" in t.sections
        assert "cause_of_action" in t.sections
        assert t.category == "civil"

    def test_demand_notice_138_has_cheque_fields(self) -> None:
        t = TEMPLATES["demand_notice_138"]
        assert "cheque_number" in t.required_fields
        assert "cheque_amount" in t.required_fields
        assert "return_date" in t.required_fields

    def test_divorce_petition_has_marriage_details(self) -> None:
        t = TEMPLATES["divorce_petition"]
        assert "marriage_date" in t.required_fields
        assert "grounds_for_divorce" in t.required_fields
        assert t.category == "family"

    def test_affidavit_no_affidavit_required(self) -> None:
        t = TEMPLATES["affidavit"]
        assert t.requires_affidavit is False  # an affidavit doesn't need a companion affidavit

    def test_all_17_templates_exist(self) -> None:
        assert len(TEMPLATES) == 17
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_drafting_templates.py -v`
Expected: FAIL — missing 10 template keys

**Step 3: Add the 10 new templates to templates.py**

Add 10 new entries to the `TEMPLATES` dict after the existing 7. Each entry follows the exact same pattern as existing templates but includes the 3 new V2 fields. Templates are defined in the design doc Section 4. Key template definitions:

- `anticipatory_bail`: sections = (court_header, case_details, facts_of_the_case, apprehension_of_arrest, grounds_for_anticipatory_bail, legal_provisions, precedents_relied_upon, conditions_offered, prayer, verification)
- `quashing_petition_482`: sections = (court_header, parties, synopsis_and_list_of_dates, facts, grounds_for_quashing, legal_provisions, precedents_relied_upon, prayer, verification)
- `demand_notice_138`: sections = (header, sender_details, recipient_details, reference, transaction_details, cheque_details, dishonour_details, demand, consequences, dispatch_clause, signature)
- `plaint`: sections = (court_header, parties, jurisdiction_and_valuation, facts_of_the_case, cause_of_action, limitation, legal_grounds, precedents_relied_upon, documents_relied_upon, prayer, verification)
- `reply_to_notice`: sections = (header, recipient_details, sender_details, reference, preliminary_objections, para_wise_reply, denial_of_claims, counter_claims, closing, signature)
- `slp`: sections = (synopsis, list_of_dates, questions_of_law, court_header, parties, impugned_order, facts, grounds_for_leave, precedents_relied_upon, prayer, verification)
- `divorce_petition`: sections = (court_header, parties, marriage_details, facts_of_the_case, grounds_for_divorce, legal_provisions, precedents_relied_upon, prayer, verification)
- `maintenance_application`: sections = (court_header, parties, relationship_details, facts_of_the_case, income_and_means, grounds_for_maintenance, legal_provisions, precedents_relied_upon, prayer, verification)
- `consumer_complaint`: sections = (court_header, parties, facts_of_the_case, deficiency_or_defect, loss_or_damage, legal_provisions, precedents_relied_upon, prayer, verification)
- `affidavit`: sections = (deponent_identification, oath_clause, statement_of_facts, verification, notary_block)

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_drafting_templates.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/drafting/templates.py backend/tests/unit/test_drafting_templates.py
git commit -m "feat(drafting): add 10 new document templates (17 total)"
```

---

## Task 4: Add 11 New Prompt Constants

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (add after line ~3391, before IRAC_STRUCTURE_INSTRUCTION)
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py:49-56` (update _PROMPT_MAP)
- Modify: `backend/tests/unit/test_drafting_templates.py:18-25` (update _VALID_PROMPT_MAP)

**Step 1: Add prompt constants to prompts.py**

Add 11 new prompt constants following the exact same pattern as existing ones (lines 3100-3391). Each prompt:
- Sets an expert Indian legal drafter persona
- Defines section structure matching the template sections
- Lists drafting rules (no hallucination, cite both old/new codes, proper conventions)
- References key jurisprudence for that document type

New constants:
1. `DRAFT_ANTICIPATORY_BAIL_SYSTEM` (~35 lines)
2. `DRAFT_QUASHING_PETITION_SYSTEM` (~40 lines)
3. `DRAFT_DEMAND_NOTICE_138_SYSTEM` (~30 lines)
4. `DRAFT_PLAINT_SYSTEM` (~45 lines)
5. `DRAFT_REPLY_TO_NOTICE_SYSTEM` (~25 lines)
6. `DRAFT_SLP_SYSTEM` (~50 lines)
7. `DRAFT_DIVORCE_PETITION_SYSTEM` (~35 lines)
8. `DRAFT_MAINTENANCE_APPLICATION_SYSTEM` (~30 lines)
9. `DRAFT_CONSUMER_COMPLAINT_SYSTEM` (~30 lines)
10. `DRAFT_AFFIDAVIT_SYSTEM` (~20 lines)
11. `DRAFT_AFFIDAVIT_COMPANION_SYSTEM` (~25 lines) — for auto-generating companion affidavits

Refer to design doc Section 9 for key content of each prompt.

**Step 2: Update _PROMPT_MAP in drafting_nodes.py**

In `backend/app/core/agents/nodes/drafting_nodes.py`, add imports (line ~31) and extend `_PROMPT_MAP` (line 49-56):

```python
# Add to imports:
from app.core.legal.prompts import (
    # ... existing imports ...
    DRAFT_ANTICIPATORY_BAIL_SYSTEM,
    DRAFT_QUASHING_PETITION_SYSTEM,
    DRAFT_DEMAND_NOTICE_138_SYSTEM,
    DRAFT_PLAINT_SYSTEM,
    DRAFT_REPLY_TO_NOTICE_SYSTEM,
    DRAFT_SLP_SYSTEM,
    DRAFT_DIVORCE_PETITION_SYSTEM,
    DRAFT_MAINTENANCE_APPLICATION_SYSTEM,
    DRAFT_CONSUMER_COMPLAINT_SYSTEM,
    DRAFT_AFFIDAVIT_SYSTEM,
)

# Add to _PROMPT_MAP:
_PROMPT_MAP: dict[str, str] = {
    # V1
    "DRAFT_BAIL_APPLICATION_SYSTEM": DRAFT_BAIL_APPLICATION_SYSTEM,
    "DRAFT_WRIT_PETITION_SYSTEM": DRAFT_WRIT_PETITION_SYSTEM,
    "DRAFT_WRITTEN_STATEMENT_SYSTEM": DRAFT_WRITTEN_STATEMENT_SYSTEM,
    "DRAFT_LEGAL_NOTICE_SYSTEM": DRAFT_LEGAL_NOTICE_SYSTEM,
    "DRAFT_APPEAL_SYSTEM": DRAFT_APPEAL_SYSTEM,
    "DRAFT_APPLICATION_SYSTEM": DRAFT_APPLICATION_SYSTEM,
    # V2
    "DRAFT_ANTICIPATORY_BAIL_SYSTEM": DRAFT_ANTICIPATORY_BAIL_SYSTEM,
    "DRAFT_QUASHING_PETITION_SYSTEM": DRAFT_QUASHING_PETITION_SYSTEM,
    "DRAFT_DEMAND_NOTICE_138_SYSTEM": DRAFT_DEMAND_NOTICE_138_SYSTEM,
    "DRAFT_PLAINT_SYSTEM": DRAFT_PLAINT_SYSTEM,
    "DRAFT_REPLY_TO_NOTICE_SYSTEM": DRAFT_REPLY_TO_NOTICE_SYSTEM,
    "DRAFT_SLP_SYSTEM": DRAFT_SLP_SYSTEM,
    "DRAFT_DIVORCE_PETITION_SYSTEM": DRAFT_DIVORCE_PETITION_SYSTEM,
    "DRAFT_MAINTENANCE_APPLICATION_SYSTEM": DRAFT_MAINTENANCE_APPLICATION_SYSTEM,
    "DRAFT_CONSUMER_COMPLAINT_SYSTEM": DRAFT_CONSUMER_COMPLAINT_SYSTEM,
    "DRAFT_AFFIDAVIT_SYSTEM": DRAFT_AFFIDAVIT_SYSTEM,
}
```

**Step 3: Update _VALID_PROMPT_MAP in test file**

In `backend/tests/unit/test_drafting_templates.py`, update `_VALID_PROMPT_MAP` (line 18-25) to include all 16 entries.

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_templates.py tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/legal/prompts.py backend/app/core/agents/nodes/drafting_nodes.py backend/tests/unit/test_drafting_templates.py
git commit -m "feat(drafting): add 11 new prompt constants for V2 document types"
```

---

## Task 5: Update DraftingState with V2 Fields

**Files:**
- Modify: `backend/app/core/agents/state.py:254-271`

**Step 1: Add V2 fields**

Add after line 271 (after `error: str`):

```python
    # V2 fields:
    court_profile: dict          # resolved CourtProfile as dict
    research_context: dict       # extracted from research session (empty if standalone)
    affidavit_draft: str         # auto-generated companion affidavit
    suggested_precedents: list[dict]  # graph-suggested precedents from citation graph
    primary_code: str            # "old" or "new" — IPC vs BNS as primary
```

**Step 2: Run existing drafting tests to verify backwards compatibility**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py tests/unit/test_drafting_graph.py -v`
Expected: ALL PASS (TypedDict allows missing keys, existing code uses `.get()`)

**Step 3: Commit**

```bash
git add backend/app/core/agents/state.py
git commit -m "feat(drafting): add V2 fields to DraftingState"
```

---

## Task 6: Wire Court Profiles into resolve_template_node

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py:64-85` (resolve_template_node)
- Modify: `backend/tests/unit/test_drafting_nodes.py`

**Step 1: Write the failing test**

Add to `backend/tests/unit/test_drafting_nodes.py`:

```python
class TestResolveTemplateV2:
    @pytest.mark.asyncio
    async def test_resolve_template_sets_court_profile(self) -> None:
        state = _make_state(target_court="Supreme Court")
        result = await resolve_template_node(state)
        assert "court_profile" in result
        assert result["court_profile"]["court_id"] == "supreme_court"

    @pytest.mark.asyncio
    async def test_resolve_template_default_court_profile(self) -> None:
        state = _make_state(target_court="")
        result = await resolve_template_node(state)
        assert result["court_profile"]["court_id"] == "default"

    @pytest.mark.asyncio
    async def test_resolve_template_sets_primary_code_new(self) -> None:
        state = _make_state(additional_context={
            "accused_name": "Test",
            "fir_number": "123/2025",
            "police_station": "Test PS",
            "offences_charged": "S.420 IPC",
            "fir_date": "2025-01-15",
        })
        result = await resolve_template_node(state)
        assert result["primary_code"] == "new"

    @pytest.mark.asyncio
    async def test_resolve_template_sets_primary_code_old(self) -> None:
        state = _make_state(additional_context={
            "accused_name": "Test",
            "fir_number": "123/2023",
            "police_station": "Test PS",
            "offences_charged": "S.420 IPC",
            "fir_date": "2023-06-01",
        })
        result = await resolve_template_node(state)
        assert result["primary_code"] == "old"
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py::TestResolveTemplateV2 -v`
Expected: FAIL — `court_profile` not in result

**Step 3: Implement**

In `backend/app/core/agents/nodes/drafting_nodes.py`, modify `resolve_template_node` (line 64-85):

1. Add import at top: `from app.core.drafting.court_profiles import get_court_profile`
2. After `return {"template": asdict(template)}` (line 85), replace with:

```python
    from dataclasses import asdict as dc_asdict
    court_profile = get_court_profile(state.get("target_court", ""))
    primary_code = _determine_primary_code(
        state.get("case_facts", ""),
        state.get("additional_context", {}) or {},
    )
    return {
        "template": asdict(template),
        "court_profile": dc_asdict(court_profile),
        "primary_code": primary_code,
    }
```

3. Add helper function before the node:

```python
def _determine_primary_code(case_facts: str, additional_context: dict) -> str:
    """Return 'old' or 'new' based on FIR/filing date vs July 1 2024 cutoff."""
    from datetime import date, datetime

    cutoff = date(2024, 7, 1)
    for key in ("fir_date", "filing_date", "offence_date"):
        raw = additional_context.get(key, "")
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(raw, fmt).date()
                if parsed < cutoff:
                    return "old"
                return "new"
            except ValueError:
                continue
    return "new"
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/tests/unit/test_drafting_nodes.py
git commit -m "feat(drafting): wire court profiles and primary code detection into resolve_template"
```

---

## Task 7: Wire Amendment Service into gather_provisions_node

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py:93-171` (gather_provisions_node)

**Step 1: Write the failing test**

```python
class TestGatherProvisionsV2:
    @pytest.mark.asyncio
    async def test_provisions_include_new_code_mapping(self) -> None:
        """When a provision is S.438 CrPC, the result should include S.482 BNSS."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps([
            {"act": "CrPC", "section": "438", "description": "Anticipatory bail", "current": True},
        ])
        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock(fetchall=lambda: [])

        state = _make_state(
            template={"display_name": "Test", "statutory_basis": "S.438 CrPC"},
            primary_code="new",
        )
        result = await gather_provisions_node(state, mock_llm, mock_db)
        provisions = result["statutory_provisions"]
        assert len(provisions) >= 1
        # Should have new_code_section attached
        p = provisions[0]
        assert p.get("new_code_section") == "482" or p.get("new_code_act") == "BNSS"
```

**Step 2: Implement amendment mapping post-processing**

In `gather_provisions_node`, after the `validated` list is built (line ~171), add:

```python
    # Post-process: attach old↔new code mappings
    from app.core.legal.amendment_service import build_lookup_from_constants
    old_to_new, new_to_old = build_lookup_from_constants()
    act_abbrev_to_new = {"IPC": "BNS", "CrPC": "BNSS", "IEA": "BSA"}
    act_abbrev_to_old = {"BNS": "IPC", "BNSS": "CrPC", "BSA": "IEA"}

    for prov in validated:
        act = prov.get("act", "")
        sec = prov.get("section", "")
        key = (act, sec)
        if key in old_to_new:
            prov["new_code_section"] = old_to_new[key][0]
            prov["new_code_act"] = act_abbrev_to_new.get(act, "")
        elif key in new_to_old:
            prov["old_code_section"] = new_to_old[key][0]
            prov["old_code_act"] = act_abbrev_to_old.get(act, "")
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/tests/unit/test_drafting_nodes.py
git commit -m "feat(drafting): wire amendment_service into gather_provisions for dual-citation"
```

---

## Task 8: Add CRAC Mode and Amendment Context to draft_sections_node

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py:228-314` (draft_sections_node)

**Step 1: Write the failing test**

```python
class TestDraftSectionsV2:
    @pytest.mark.asyncio
    async def test_crac_prompt_used_for_advocacy_template(self) -> None:
        """Templates with argument_style='crac' should inject CRAC instruction."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Draft content"
        state = _make_state(
            template={
                "display_name": "Bail Application",
                "sections": ["grounds_for_bail"],
                "prompt_key": "DRAFT_BAIL_APPLICATION_SYSTEM",
                "argument_style": "crac",
            },
            verified_precedents=[],
            statutory_provisions=[],
            primary_code="new",
        )
        await draft_sections_node(state, mock_llm)
        # Check that the prompt passed to LLM contains CRAC instruction
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt", "") or call_args.args[0] if call_args.args else ""
        assert "CONCLUSION" in prompt.upper() or "CRAC" in prompt.upper() or "Lead with" in prompt
```

**Step 2: Implement CRAC mode and amendment context**

In `draft_sections_node`, modify the `_draft_one` inner function (line ~273):

1. Read `argument_style` from template: `argument_style = template.get("argument_style", "irac")`
2. Build argument structure instruction:

```python
    if argument_style == "crac":
        structure_instruction = (
            "Structure each key point using CRAC: "
            "Lead with your CONCLUSION (your position), then state the RULE "
            "(statute/precedent), APPLY it to these facts, restate your CONCLUSION."
        )
    else:
        structure_instruction = (
            "Structure each key point using IRAC: "
            "ISSUE (legal question), RULE (statute/precedent), APPLICATION "
            "(to these facts), CONCLUSION (your position)."
        )
```

3. Build amendment context string from `state.get("primary_code", "new")` and relevant provisions.
4. Inject both into the per-section prompt.

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/tests/unit/test_drafting_nodes.py
git commit -m "feat(drafting): add CRAC argument mode and amendment context injection"
```

---

## Task 9: Wire Overruled Precedent Shield into verify_precedents_node

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py:179-220` (verify_precedents_node)
- Modify: `backend/app/core/agents/drafting.py:118-120` (pass graph_store to closure)

**Step 1: Write the failing test**

```python
class TestVerifyPrecedentsV2:
    @pytest.mark.asyncio
    async def test_overruled_precedent_tagged(self) -> None:
        mock_db = AsyncMock()
        # Simulate citation found in DB
        mock_db.execute.return_value = MagicMock(
            fetchall=lambda: [("Case v Case", "case-123")]
        )
        mock_graph = AsyncMock()
        mock_graph.get_neighbors.return_value = {
            "nodes": [{"text": "This case was expressly overruled in XYZ v ABC"}]
        }

        state = _make_state(
            relevant_precedents=[
                {"citation": "Case v Case", "title": "Case v Case (2020)"}
            ],
        )
        result = await verify_precedents_node(state, mock_db, mock_graph)
        precs = result["verified_precedents"]
        assert len(precs) == 1
        assert precs[0].get("treatment") in ("overruled", "good_law", "distinguished", "doubted")
```

**Step 2: Implement**

1. Add `graph_store` parameter to `verify_precedents_node` signature
2. After verifying citations against DB, for each verified precedent:
   - Get case_id from DB result
   - Call `graph_store.get_neighbors(case_id, relationship="CITES", direction="both", depth=1)` (if graph_store is not None)
   - Run `has_overruling_language()` on neighbor text
   - Tag `treatment: "good_law" | "overruled" | "distinguished" | "doubted"`
3. If graph_store is None (unit tests), skip treatment detection and tag as `"good_law"`

4. In `backend/app/core/agents/drafting.py` (line 118-120), pass `graph_store` to the verify_precedents closure:

```python
    async def verify_precedents(state: DraftingState) -> dict:
        async with async_session_factory() as session:
            return await verify_precedents_node(state, session, graph_store)
```

Where `graph_store` is a new parameter to `build_drafting_graph()`.

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py tests/unit/test_drafting_graph.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/app/core/agents/drafting.py backend/tests/unit/test_drafting_nodes.py
git commit -m "feat(drafting): add overruled precedent shield via citation treatment detection"
```

---

## Task 10: Add Citation Graph Suggestions to gather_provisions_node

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py` (gather_provisions_node)
- Modify: `backend/app/core/agents/drafting.py` (pass graph_store + vector_store to closure)

**Step 1: Implement**

After the amendment mapping post-processing in `gather_provisions_node`, add a step that:
1. Takes verified precedent case_ids (from state)
2. Calls `get_citation_neighbors()` (from `common.py`) to get 2-hop neighbors
3. Filters to top 5 related, non-overruled cases
4. Returns as `suggested_precedents` in the result dict

The `gather_provisions` closure in `drafting.py` needs `graph_store` passed in.

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/app/core/agents/drafting.py
git commit -m "feat(drafting): add citation graph-based precedent suggestions"
```

---

## Task 11: Add Statutory Text Injection to draft_sections_node

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py` (draft_sections_node)
- Modify: `backend/app/core/agents/drafting.py` (pass vector_store + embedder to closure)

**Step 1: Implement**

In `draft_sections_node`, for substantive sections (grounds, legal_provisions, precedents_relied_upon):
1. After LLM generates draft text, extract statute references via `extract_acts_cited()` from `extractor.py`
2. For each extracted act+section, query the vector_store for `vector_type=statute` matches
3. If found, append the actual section text as an indented block quote
4. This requires `vector_store` and `embedder` to be passed into the node

The closure in `drafting.py` passes these dependencies. The vector search uses the existing `embedder.embed()` + `vector_store.search()` pattern used throughout the codebase.

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/app/core/agents/drafting.py
git commit -m "feat(drafting): inject actual statute text from Pinecone into draft sections"
```

---

## Task 12: Add Companion Affidavit Generation

**Files:**
- Modify: `backend/app/core/agents/nodes/drafting_nodes.py` (add new function)
- Modify: `backend/app/core/agents/drafting.py` (add affidavit sub-step after assemble)

**Step 1: Write the failing test**

```python
class TestAffidavitGeneration:
    @pytest.mark.asyncio
    async def test_affidavit_generated_when_required(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "I solemnly affirm and state..."
        state = _make_state(
            template={"requires_affidavit": True, "display_name": "Bail Application"},
            full_draft="Full draft content here.",
            case_facts="Accused was arrested on 01.01.2025.",
            additional_context={"accused_name": "John Doe"},
            target_court="Delhi High Court",
        )
        result = await generate_affidavit_node(state, mock_llm)
        assert "affidavit_draft" in result
        assert result["affidavit_draft"].strip()

    @pytest.mark.asyncio
    async def test_no_affidavit_when_not_required(self) -> None:
        mock_llm = AsyncMock()
        state = _make_state(
            template={"requires_affidavit": False, "display_name": "Legal Notice"},
            full_draft="Notice content.",
        )
        result = await generate_affidavit_node(state, mock_llm)
        assert result["affidavit_draft"] == ""
```

**Step 2: Implement generate_affidavit_node**

New function in `drafting_nodes.py`:

```python
async def generate_affidavit_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Generate a companion affidavit if the template requires one."""
    template = state.get("template", {})
    if not template.get("requires_affidavit", False):
        return {"affidavit_draft": ""}

    case_facts = state.get("case_facts", "")
    additional_context = state.get("additional_context", {}) or {}
    target_court = state.get("target_court", "")

    # Build deponent info from additional_context
    deponent_name = (
        additional_context.get("accused_name", "")
        or additional_context.get("petitioner_details", "")
        or additional_context.get("applicant_details", "")
        or additional_context.get("complainant_details", "")
        or additional_context.get("deponent_name", "")
        or "[DEPONENT NAME]"
    )

    prompt = (
        f"Generate a supporting affidavit for a {template.get('display_name', 'legal document')}.\n\n"
        f"Deponent: {deponent_name}\n"
        f"Court: {target_court or 'Not specified'}\n\n"
        f"Case Facts:\n{case_facts}\n\n"
        "Follow standard Indian affidavit format:\n"
        "1. Deponent identification (name, age, S/o or D/o, address, occupation)\n"
        "2. 'I do hereby solemnly affirm and state on oath as follows:'\n"
        "3. Numbered paragraphs of facts (matching main document)\n"
        "4. Knowledge vs. belief distinction per paragraph\n"
        "5. Verification clause with place and date\n"
        "6. Deponent signature line\n"
        "7. 'BEFORE ME' notary/oath commissioner block\n"
    )

    try:
        affidavit = await llm.generate(
            prompt=prompt,
            system=DRAFT_AFFIDAVIT_COMPANION_SYSTEM,
            temperature=0.1,
            max_tokens=4096,
        )
        return {"affidavit_draft": affidavit.strip()}
    except Exception:
        logger.warning("Failed to generate companion affidavit", exc_info=True)
        return {"affidavit_draft": ""}
```

**Step 3: Wire into graph**

In `backend/app/core/agents/drafting.py`, modify the `assemble` closure to also call `generate_affidavit_node` after assembly:

```python
    async def assemble(state: DraftingState) -> dict:
        result = await assemble_document_node(state, llm)
        # Generate companion affidavit if required
        affidavit_result = await generate_affidavit_node(
            {**state, **result}, llm
        )
        result.update(affidavit_result)
        return result
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/drafting_nodes.py backend/app/core/agents/drafting.py backend/tests/unit/test_drafting_nodes.py
git commit -m "feat(drafting): add companion affidavit auto-generation"
```

---

## Task 13: Update Export Engine with Court Profile Support

**Files:**
- Modify: `backend/app/core/drafting/export.py:71-160` (export_to_docx)
- Modify: `backend/app/core/drafting/export.py:167-268` (export_to_pdf)

**Step 1: Write the failing test**

Create tests in a new test class or add to existing test file:

```python
# In backend/tests/unit/test_drafting_v2.py (new file)

import pytest
from app.core.drafting.court_profiles import COURT_PROFILES
from app.core.drafting.export import export_to_docx, export_to_pdf
from app.core.drafting.templates import get_template


class TestExportWithCourtProfile:
    @pytest.mark.asyncio
    async def test_docx_export_with_sc_profile(self) -> None:
        template = get_template("bail_application")
        profile = COURT_PROFILES["supreme_court"]
        content = "## FACTS\n\nThe accused was arrested."
        result = await export_to_docx(content, template, court_profile=profile)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_docx_export_with_affidavit(self) -> None:
        template = get_template("bail_application")
        content = "## FACTS\n\nThe accused was arrested."
        affidavit = "## AFFIDAVIT\n\nI solemnly affirm..."
        result = await export_to_docx(content, template, affidavit=affidavit)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_pdf_export_with_sc_profile(self) -> None:
        template = get_template("bail_application")
        profile = COURT_PROFILES["supreme_court"]
        content = "## FACTS\n\nThe accused was arrested."
        result = await export_to_pdf(content, template, court_profile=profile)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_export_backwards_compatible_without_profile(self) -> None:
        template = get_template("bail_application")
        content = "## FACTS\n\nTest content."
        result = await export_to_docx(content, template)
        assert isinstance(result, bytes)
```

**Step 2: Implement court-profile-driven export**

Modify `export_to_docx` and `export_to_pdf` signatures to accept optional `court_profile` and `affidavit` params. Use profile values for margins, fonts, spacing. Append affidavit after page break if provided. Fall back to current hardcoded values when `court_profile` is None.

Key changes in `export_to_docx`:
- Import `CourtProfile` from `court_profiles`
- Convert cm margins to Inches: `Inches(profile.margin_left_cm / 2.54)`
- Use `Pt(profile.font_size_body)` for body font
- Use `Pt(profile.font_size_heading)` for heading font
- Set line spacing via `paragraph_format.line_spacing`
- If affidavit provided, add section break + affidavit content

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_drafting_v2.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/core/drafting/export.py backend/tests/unit/test_drafting_v2.py
git commit -m "feat(drafting): court-profile-driven export with affidavit support"
```

---

## Task 14: Update API — Templates Endpoint and Export

**Files:**
- Modify: `backend/app/api/routes/agents.py:1057-1073` (get_drafting_templates)
- Modify: `backend/app/api/routes/agents.py:1081-1143` (export_draft)

**Step 1: Update templates endpoint to return categories**

Replace the existing `get_drafting_templates` (line 1057-1073) with:

```python
@router.get("/drafting/templates", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_drafting_templates(
    user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Return available document templates grouped by category."""
    from collections import defaultdict
    categories: dict[str, list[dict]] = defaultdict(list)
    category_names = {
        "criminal": "Criminal Litigation",
        "civil": "Civil Litigation",
        "constitutional": "Constitutional / Supreme Court",
        "family": "Family Law",
        "commercial": "Commercial",
        "transactional": "Notices & General",
    }
    for t in TEMPLATES.values():
        categories[t.category].append({
            "doc_type": t.doc_type,
            "display_name": t.display_name,
            "sections": t.sections,
            "required_fields": t.required_fields,
            "statutory_basis": t.statutory_basis,
            "category": t.category,
            "requires_affidavit": t.requires_affidavit,
        })
    return {
        "categories": [
            {"id": cat, "display_name": category_names.get(cat, cat), "templates": templates}
            for cat, templates in categories.items()
        ]
    }
```

**Step 2: Update export endpoint to accept include_affidavit**

In `export_draft` (line 1081), add query param `include_affidavit: bool = Query(True)`. Read affidavit from `result_data.get("affidavit_draft", "")`. Read court_profile from `result_data.get("court_profile", None)`. Pass both to export functions.

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_auth_routes.py -v` (or relevant route tests)
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/api/routes/agents.py
git commit -m "feat(drafting): update templates endpoint with categories, export with affidavit"
```

---

## Task 15: Add Research-to-Draft Bridge Endpoint

**Files:**
- Modify: `backend/app/api/routes/agents.py` (add new endpoint after export)

**Step 1: Add request model and endpoint**

```python
class DraftFromResearchRequest(BaseModel):
    research_execution_id: str = Field(..., min_length=1, max_length=50)
    doc_type: str = Field(..., min_length=1, max_length=50)
    target_court: str = Field(default="", max_length=200)
    additional_context: dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", pattern="^(en|hi)$")

    @field_validator("additional_context")
    @classmethod
    def validate_additional_context(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 10:
            raise ValueError("Maximum 10 additional_context keys allowed")
        return v
```

The endpoint:
1. Loads the research `AgentExecution` by `research_execution_id`
2. Validates it belongs to the user and is completed
3. Extracts `grounding_citations` → `relevant_precedents`, `query` → `case_facts`, `statute_sections` + `arguments` → `research_context`
4. Validates `doc_type` and required fields
5. Creates a new drafting `AgentExecution`
6. Builds and runs the drafting graph with pre-populated state
7. Returns SSE stream

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_auth_routes.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/app/api/routes/agents.py
git commit -m "feat(drafting): add /drafting/from-research endpoint for research-to-draft bridge"
```

---

## Task 16: Update build_drafting_graph to Pass New Dependencies

**Files:**
- Modify: `backend/app/core/agents/drafting.py:66-220`
- Modify: `backend/app/api/routes/agents.py:671-687` (drafting graph construction)

**Step 1: Add graph_store parameter to build_drafting_graph**

Add `graph_store: Any | None = None` to the function signature. Pass it into the closures that need it (verify_precedents, gather_provisions).

**Step 2: Update all call sites**

In `agents.py`, where `build_drafting_graph()` is called (lines 672, 927, 1514), add `graph_store=graph_store`.

**Step 3: Run full drafting test suite**

Run: `cd backend && python -m pytest tests/unit/test_drafting_nodes.py tests/unit/test_drafting_graph.py tests/unit/test_drafting_templates.py tests/unit/test_drafting_v2.py tests/unit/test_court_profiles.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/app/core/agents/drafting.py backend/app/api/routes/agents.py
git commit -m "feat(drafting): pass graph_store through drafting graph for V2 features"
```

---

## Task 17: Update Frontend Drafting Page

**Files:**
- Modify: `frontend/src/app/agents/drafting/page.tsx`

**Step 1: Update template selector**

Replace flat dropdown with category-grouped selector. Fetch from updated `/drafting/templates` endpoint. Show categories as collapsible groups with templates listed under each.

**Step 2: Add affidavit preview**

When the draft checkpoint shows `affidavit_draft`, display it in a separate collapsible section below the main draft.

**Step 3: Add "Draft from Research" button**

On the research results page (`frontend/src/app/agents/research/` or similar), add a button that navigates to the drafting page with `research_execution_id` as a query parameter. The drafting page reads this param and calls `/drafting/from-research` instead of `/run`.

**Step 4: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS (or update test snapshots as needed)

**Step 5: Commit**

```bash
git add frontend/src/app/agents/drafting/page.tsx
git commit -m "feat(drafting): category-grouped template selector, affidavit preview, research bridge UI"
```

---

## Task 18: Final Integration Test and Cleanup

**Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest tests/unit/ -v --tb=short`
Expected: ALL PASS (~2200+ tests)

**Step 2: Run full frontend test suite**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS (~311+ tests)

**Step 3: Verify no regressions in existing 7 templates**

Run: `cd backend && python -m pytest tests/unit/test_drafting_templates.py tests/unit/test_drafting_nodes.py tests/unit/test_drafting_graph.py -v`
Expected: ALL PASS

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore(drafting): V2 integration cleanup and test verification"
```
