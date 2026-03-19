# Ingestion Pipeline V2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 22 new metadata fields, PDF page mapping, and enriched Neo4j edges/nodes to the ingestion pipeline — future-proofing for Strategy Simulation, Judge Analytics V2, and Document Generation.

**Architecture:** Two-pass design. Pass 1 (Flash) extracts all fields at ingestion time. Pass 2 (Pro) re-extracts 8 complex reasoning fields on-demand via a separate script. PDF page mapping is captured during existing extraction at zero LLM cost.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic migrations, Gemini 2.5 Flash/Pro, Pinecone, Neo4j, PostgreSQL 16, pytest

**Design doc:** `docs/plans/2026-03-20-ingestion-v2-design.md`

---

## Task 1: Database Migration — Add 23 New Columns + Indexes

**Files:**
- Create: `backend/migrations/versions/021_ingestion_v2_fields.py`

**Step 1: Create migration file**

```bash
cd backend && alembic revision -m "ingestion v2 fields"
```

Rename the generated file to `021_ingestion_v2_fields.py` and set:
- `revision = "021"`
- `down_revision = "020"`

**Step 2: Write the migration**

```python
"""Ingestion V2: 22 new metadata fields + page_map + enrichment_status."""

revision = "021"
down_revision = "020"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

def upgrade() -> None:
    # Group A: Judge Behavior Modeling
    op.add_column("cases", sa.Column("arguments_raised", JSONB, nullable=True))
    op.add_column("cases", sa.Column("relief_granted", sa.Text, nullable=True))
    op.add_column("cases", sa.Column("relief_sought", sa.Text, nullable=True))
    op.add_column("cases", sa.Column("sentence_details", JSONB, nullable=True))
    op.add_column("cases", sa.Column("damages_awarded", JSONB, nullable=True))
    op.add_column("cases", sa.Column("judicial_tone", sa.String(30), nullable=True))
    op.add_column("cases", sa.Column("key_observations", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("hearing_count", sa.Integer, nullable=True))

    # Group B: Citation Intelligence
    op.add_column("cases", sa.Column("citation_treatments", JSONB, nullable=True))
    op.add_column("cases", sa.Column("distinguished_cases", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("overruled_cases", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("legal_principles_applied", ARRAY(sa.String), nullable=True))

    # Group C: Procedural Intelligence
    op.add_column("cases", sa.Column("procedural_history", JSONB, nullable=True))
    op.add_column("cases", sa.Column("interim_orders", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("filing_date", sa.Date, nullable=True))
    op.add_column("cases", sa.Column("urgency_indicators", ARRAY(sa.String), nullable=True))

    # Group D: Party & Case Intelligence
    op.add_column("cases", sa.Column("party_counsel", JSONB, nullable=True))
    op.add_column("cases", sa.Column("issue_classification", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("fact_pattern_tags", ARRAY(sa.String), nullable=True))

    # Group E: Output Quality
    op.add_column("cases", sa.Column("operative_order", sa.Text, nullable=True))
    op.add_column("cases", sa.Column("conditions_imposed", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("costs_awarded", JSONB, nullable=True))

    # PDF Deep-Linking
    op.add_column("cases", sa.Column("page_map", JSONB, nullable=True))

    # Enrichment Tracking
    op.add_column("cases", sa.Column("enrichment_status", sa.String(20), nullable=False, server_default="flash_only"))

    # Indexes
    op.create_index("ix_cases_judicial_tone", "cases", ["judicial_tone"])
    op.create_index("ix_cases_filing_date", "cases", ["filing_date"])
    op.create_index("ix_cases_fact_pattern_tags", "cases", ["fact_pattern_tags"], postgresql_using="gin")
    op.create_index("ix_cases_issue_classification", "cases", ["issue_classification"], postgresql_using="gin")
    op.create_index("ix_cases_legal_principles", "cases", ["legal_principles_applied"], postgresql_using="gin")
    op.create_index("ix_cases_distinguished", "cases", ["distinguished_cases"], postgresql_using="gin")
    op.create_index("ix_cases_overruled", "cases", ["overruled_cases"], postgresql_using="gin")
    op.create_index("ix_cases_party_counsel", "cases", ["party_counsel"], postgresql_using="gin", postgresql_ops={"party_counsel": "jsonb_path_ops"})
    op.create_index("ix_cases_enrichment_status", "cases", ["enrichment_status"])


def downgrade() -> None:
    op.drop_index("ix_cases_enrichment_status")
    op.drop_index("ix_cases_party_counsel")
    op.drop_index("ix_cases_overruled")
    op.drop_index("ix_cases_distinguished")
    op.drop_index("ix_cases_legal_principles")
    op.drop_index("ix_cases_issue_classification")
    op.drop_index("ix_cases_fact_pattern_tags")
    op.drop_index("ix_cases_filing_date")
    op.drop_index("ix_cases_judicial_tone")

    for col in [
        "enrichment_status", "page_map",
        "costs_awarded", "conditions_imposed", "operative_order",
        "fact_pattern_tags", "issue_classification", "party_counsel",
        "urgency_indicators", "filing_date", "interim_orders", "procedural_history",
        "legal_principles_applied", "overruled_cases", "distinguished_cases", "citation_treatments",
        "hearing_count", "key_observations", "judicial_tone", "damages_awarded",
        "sentence_details", "relief_sought", "relief_granted", "arguments_raised",
    ]:
        op.drop_column("cases", col)
```

**Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/migrations/versions/021_ingestion_v2_fields.py
git commit -m "migration(021): add 22 ingestion V2 fields + page_map + enrichment_status"
```

---

## Task 2: SQLAlchemy Model — Add New Columns to Case

**Files:**
- Modify: `backend/app/models/case.py:110-116` (insert after `anonymization_flags`, before `__table_args__`)

**Step 1: Write failing test**

Create a test that verifies the new columns exist on the model.

File: `backend/tests/unit/test_case_model_v2.py`

```python
"""Tests for Case model V2 columns."""
import pytest
from app.models.case import Case


class TestCaseModelV2Columns:
    """Verify all 23 new columns exist on the Case model."""

    @pytest.mark.parametrize("col", [
        "arguments_raised", "relief_granted", "relief_sought",
        "sentence_details", "damages_awarded", "judicial_tone",
        "key_observations", "hearing_count",
        "citation_treatments", "distinguished_cases", "overruled_cases",
        "legal_principles_applied",
        "procedural_history", "interim_orders", "filing_date", "urgency_indicators",
        "party_counsel", "issue_classification", "fact_pattern_tags",
        "operative_order", "conditions_imposed", "costs_awarded",
        "page_map", "enrichment_status",
    ])
    def test_column_exists(self, col: str):
        assert hasattr(Case, col), f"Case model missing column: {col}"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_case_model_v2.py -v
```

Expected: FAIL — columns don't exist yet.

**Step 3: Add columns to Case model**

Modify `backend/app/models/case.py`. Insert after line 110 (`anonymization_flags`), before `__table_args__`:

```python
    # --- Migration 021 columns (Ingestion V2) ---
    # Group A: Judge Behavior Modeling
    arguments_raised: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    relief_granted: Mapped[str | None] = mapped_column(Text, nullable=True)
    relief_sought: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentence_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    damages_awarded: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    judicial_tone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    key_observations: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    hearing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Group B: Citation Intelligence
    citation_treatments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    distinguished_cases: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    overruled_cases: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    legal_principles_applied: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Group C: Procedural Intelligence
    procedural_history: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    interim_orders: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    urgency_indicators: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Group D: Party & Case Intelligence
    party_counsel: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    issue_classification: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    fact_pattern_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Group E: Output Quality
    operative_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions_imposed: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    costs_awarded: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # PDF Deep-Linking
    page_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Enrichment Tracking
    enrichment_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="flash_only")
```

Add missing imports at the top of `case.py` if not already present: `Date`, `date` (from datetime), `JSONB` (from sqlalchemy.dialects.postgresql).

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_case_model_v2.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models/case.py backend/tests/unit/test_case_model_v2.py
git commit -m "feat: add 23 V2 columns to Case model"
```

---

## Task 3: CaseMetadata Dataclass — Add New Fields

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py:117` (insert after `anonymization_flags`)

**Step 1: Write failing test**

File: `backend/tests/unit/test_metadata_v2.py`

```python
"""Tests for CaseMetadata V2 fields."""
import pytest
from app.core.ingestion.metadata import CaseMetadata


class TestCaseMetadataV2Fields:
    """Verify new fields exist and have correct defaults."""

    def test_new_fields_have_none_defaults(self):
        meta = CaseMetadata()
        assert meta.arguments_raised is None
        assert meta.relief_granted is None
        assert meta.relief_sought is None
        assert meta.sentence_details is None
        assert meta.damages_awarded is None
        assert meta.judicial_tone is None
        assert meta.key_observations is None
        assert meta.hearing_count is None
        assert meta.citation_treatments is None
        assert meta.distinguished_cases is None
        assert meta.overruled_cases is None
        assert meta.legal_principles_applied is None
        assert meta.procedural_history is None
        assert meta.interim_orders is None
        assert meta.filing_date is None
        assert meta.urgency_indicators is None
        assert meta.party_counsel is None
        assert meta.issue_classification is None
        assert meta.fact_pattern_tags is None
        assert meta.operative_order is None
        assert meta.conditions_imposed is None
        assert meta.costs_awarded is None

    def test_enrichment_status_defaults_to_flash_only(self):
        meta = CaseMetadata()
        assert meta.enrichment_status == "flash_only"

    def test_arguments_raised_can_store_structured_data(self):
        meta = CaseMetadata(
            arguments_raised=[
                {
                    "party": "petitioner",
                    "argument_type": "constitutional",
                    "argument_summary": "Violation of Article 21",
                    "statutory_basis": "Article 21",
                    "accepted": True,
                }
            ]
        )
        assert len(meta.arguments_raised) == 1
        assert meta.arguments_raised[0]["accepted"] is True

    def test_citation_treatments_structure(self):
        meta = CaseMetadata(
            citation_treatments=[
                {
                    "cited_case": "AIR 1973 SC 1461",
                    "treatment": "followed",
                    "context": "Applied the basic structure doctrine",
                    "paragraph": 42,
                }
            ]
        )
        assert meta.citation_treatments[0]["treatment"] == "followed"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_metadata_v2.py -v
```

Expected: FAIL — fields don't exist on CaseMetadata.

**Step 3: Add fields to CaseMetadata dataclass**

Modify `backend/app/core/ingestion/metadata.py`. Insert after line 117 (`anonymization_flags`):

```python
    # --- Ingestion V2 fields ---
    # Group A: Judge Behavior Modeling
    arguments_raised: list[dict] | None = None
    relief_granted: str | None = None
    relief_sought: str | None = None
    sentence_details: dict | None = None
    damages_awarded: dict | None = None
    judicial_tone: str | None = None
    key_observations: list[str] | None = None
    hearing_count: int | None = None
    # Group B: Citation Intelligence
    citation_treatments: list[dict] | None = None
    distinguished_cases: list[str] | None = None
    overruled_cases: list[str] | None = None
    legal_principles_applied: list[str] | None = None
    # Group C: Procedural Intelligence
    procedural_history: list[dict] | None = None
    interim_orders: list[str] | None = None
    filing_date: str | None = None
    urgency_indicators: list[str] | None = None
    # Group D: Party & Case Intelligence
    party_counsel: list[dict] | None = None
    issue_classification: list[str] | None = None
    fact_pattern_tags: list[str] | None = None
    # Group E: Output Quality
    operative_order: str | None = None
    conditions_imposed: list[str] | None = None
    costs_awarded: dict | None = None
    # Enrichment tracking
    enrichment_status: str = "flash_only"
```

Also update the `llm_only_fields` tuple (line 654-659) to include ALL new field names:

```python
llm_only_fields = (
    "case_number", "is_reportable", "headnotes", "outcome_summary",
    "coram_size", "lower_court", "lower_court_case_number", "appeal_from",
    "opinion_type", "dissenting_judges", "concurring_judges", "split_ratio",
    "petitioner_type", "respondent_type", "is_pil", "companion_cases",
    # V2 fields
    "arguments_raised", "relief_granted", "relief_sought", "sentence_details",
    "damages_awarded", "judicial_tone", "key_observations", "hearing_count",
    "citation_treatments", "distinguished_cases", "overruled_cases",
    "legal_principles_applied", "procedural_history", "interim_orders",
    "filing_date", "urgency_indicators", "party_counsel", "issue_classification",
    "fact_pattern_tags", "operative_order", "conditions_imposed", "costs_awarded",
)
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_metadata_v2.py tests/unit/test_metadata.py -v
```

Expected: ALL PASS (new tests pass, existing tests still pass).

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/tests/unit/test_metadata_v2.py
git commit -m "feat: add 22 V2 fields to CaseMetadata dataclass"
```

---

## Task 4: LLM Prompts — Add Extraction Rules 22-29 and Schema Properties

**Files:**
- Modify: `backend/app/core/legal/prompts.py:73` (add rules after rule 21)
- Modify: `backend/app/core/legal/prompts.py:615` (add schema properties after companion_cases)
- Modify: `backend/app/core/legal/prompts.py:116` (add field names to user prompt)

**Step 1: Write failing test**

File: `backend/tests/unit/test_metadata_v2_prompts.py`

```python
"""Tests for V2 metadata extraction prompts."""
import json
import pytest
from app.core.legal.prompts import (
    METADATA_EXTRACTION_SYSTEM,
    METADATA_EXTRACTION_USER,
    METADATA_OUTPUT_SCHEMA,
)


class TestV2PromptFields:
    """Verify V2 fields are present in extraction prompts."""

    @pytest.mark.parametrize("field", [
        "arguments_raised", "relief_granted", "relief_sought",
        "judicial_tone", "operative_order", "citation_treatments",
        "party_counsel", "legal_principles_applied", "fact_pattern_tags",
        "issue_classification", "procedural_history", "filing_date",
        "sentence_details", "damages_awarded", "key_observations",
        "hearing_count", "distinguished_cases", "overruled_cases",
        "interim_orders", "urgency_indicators", "conditions_imposed",
        "costs_awarded",
    ])
    def test_field_in_schema(self, field: str):
        props = METADATA_OUTPUT_SCHEMA["properties"]
        assert field in props, f"Missing schema property: {field}"

    def test_system_prompt_mentions_arguments(self):
        assert "ARGUMENTS" in METADATA_EXTRACTION_SYSTEM

    def test_system_prompt_mentions_operative_order(self):
        assert "OPERATIVE ORDER" in METADATA_EXTRACTION_SYSTEM

    def test_system_prompt_mentions_judicial_tone(self):
        assert "JUDICIAL TONE" in METADATA_EXTRACTION_SYSTEM

    def test_system_prompt_mentions_citation_treatments(self):
        assert "CITATION TREATMENTS" in METADATA_EXTRACTION_SYSTEM

    def test_schema_arguments_raised_is_array(self):
        prop = METADATA_OUTPUT_SCHEMA["properties"]["arguments_raised"]
        assert prop["type"] == "array"

    def test_schema_judicial_tone_has_enum(self):
        prop = METADATA_OUTPUT_SCHEMA["properties"]["judicial_tone"]
        assert "enum" in prop
        assert "neutral" in prop["enum"]
        assert "stern" in prop["enum"]
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_metadata_v2_prompts.py -v
```

Expected: FAIL — fields not in schema/prompts yet.

**Step 3: Update METADATA_EXTRACTION_SYSTEM**

Add after line 72 (rule 21 about COMPANION CASES), before the closing `"""`:

```
22. ARGUMENTS RAISED: Extract each distinct legal argument raised by each party.
    Classify argument_type from: constitutional, statutory_interpretation, procedural,
    factual, precedent_based, policy, equity, jurisdictional, limitation, evidence.
    Mark accepted=true if the court upheld it, false if rejected, null if unclear.
    Include statutory_basis (e.g., "Section 302 IPC") where applicable.

23. RELIEF: Extract relief_sought (what petitioner asked for) and relief_granted
    (what court actually ordered) as separate fields. For criminal cases, extract
    sentence_details with offense, sentence_type (imprisonment/fine/death/life),
    quantum (e.g., "7 years"), fine_amount, conditions. For civil monetary awards,
    extract damages_awarded with amount, currency ("INR"), type (compensatory/punitive/nominal/costs).

24. OPERATIVE ORDER: Extract the exact operative portion of the judgment verbatim.
    This usually starts with phrases like "In view of the above", "The appeal is hereby",
    "In the result", "For the reasons stated above". Copy the text exactly as written.

25. CITATION TREATMENTS: For EACH cited case, identify HOW it was used: followed,
    applied, referred_to, distinguished, overruled, approved, doubted, explained,
    not_followed. Include 1-2 sentence context of HOW it was used and the paragraph
    number where the citation appears.

26. COUNSEL: Extract names of advocates appearing for each party. Identify Senior
    Advocates (marked "Sr. Adv." or preceded by "Mr./Ms."), AG/SG/ASG, Amicus Curiae,
    and Advocate-on-Record. Use designation enum: senior_advocate, advocate, aag, ag,
    sg, asg, amicus, advocate_on_record.

27. JUDICIAL TONE: Classify the overall tone from language used. neutral = standard
    judicial language. stern = harsh language, admonishments. sympathetic = expressions
    of concern for parties. critical = criticism of lower courts/government. academic =
    extensive doctrinal analysis. reformist = policy recommendations, law reform suggestions.

28. LEGAL PRINCIPLES & FACT PATTERNS: Extract named legal doctrines applied (e.g.,
    "doctrine of basic structure", "Wednesbury unreasonableness", "last seen doctrine").
    Tag the case with 1-5 factual pattern categories (e.g., "land_dispute", "dowry_death",
    "bail_application", "service_matter", "corporate_fraud", "environmental_clearance",
    "motor_accident", "medical_negligence", "property_partition", "tax_evasion").

29. PROCEDURAL HISTORY & MISC: Extract the chain of courts the case passed through as
    procedural_history (court, case_number, date, outcome, judge). Extract filing_date
    (when case was filed, NOT decided). Extract interim_orders (stay orders, interim relief).
    Extract hearing_count (number of hearings mentioned). Extract urgency_indicators
    ("urgent hearing", "suo motu", "expedited", "day-to-day hearing"). Extract
    conditions_imposed (bail conditions, compliance timelines). Extract costs_awarded
    (amount, to_whom, reason). Extract key_observations (max 5 notable obiter dicta).
    Extract issue_classification as hierarchical tags (e.g., "fundamental_rights.article_21").
```

**Step 4: Update METADATA_OUTPUT_SCHEMA**

Add after the `companion_cases` property (line ~615), inside the `"properties"` dict:

```python
"arguments_raised": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "party": {"type": "string", "enum": ["petitioner", "respondent", "intervenor", "amicus"]},
            "argument_type": {"type": "string", "enum": [
                "constitutional", "statutory_interpretation", "procedural",
                "factual", "precedent_based", "policy", "equity",
                "jurisdictional", "limitation", "evidence"
            ]},
            "argument_summary": {"type": "string"},
            "statutory_basis": {"type": "string", "nullable": True},
            "accepted": {"type": "boolean", "nullable": True}
        }
    }
},
"relief_sought": {"type": "string", "nullable": True},
"relief_granted": {"type": "string", "nullable": True},
"sentence_details": {
    "type": "object",
    "nullable": True,
    "properties": {
        "offense": {"type": "string"},
        "sentence_type": {"type": "string", "enum": ["imprisonment", "fine", "death", "life", "acquittal", "compensation"]},
        "quantum": {"type": "string", "nullable": True},
        "fine_amount": {"type": "string", "nullable": True},
        "conditions": {"type": "string", "nullable": True}
    }
},
"damages_awarded": {
    "type": "object",
    "nullable": True,
    "properties": {
        "amount": {"type": "string"},
        "currency": {"type": "string"},
        "type": {"type": "string", "enum": ["compensatory", "punitive", "nominal", "costs"]}
    }
},
"judicial_tone": {
    "type": "string",
    "enum": ["neutral", "stern", "sympathetic", "critical", "academic", "reformist"],
    "nullable": True
},
"key_observations": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Max 5 notable obiter dicta or observations by the judge"
},
"hearing_count": {"type": "integer", "nullable": True},
"citation_treatments": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "cited_case": {"type": "string"},
            "treatment": {"type": "string", "enum": [
                "followed", "applied", "referred_to", "distinguished",
                "overruled", "approved", "doubted", "explained", "not_followed"
            ]},
            "context": {"type": "string"},
            "paragraph": {"type": "integer", "nullable": True}
        }
    }
},
"distinguished_cases": {"type": "array", "items": {"type": "string"}},
"overruled_cases": {"type": "array", "items": {"type": "string"}},
"legal_principles_applied": {"type": "array", "items": {"type": "string"}},
"procedural_history": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "court": {"type": "string"},
            "case_number": {"type": "string", "nullable": True},
            "date": {"type": "string", "nullable": True},
            "outcome": {"type": "string", "nullable": True},
            "judge": {"type": "string", "nullable": True}
        }
    }
},
"interim_orders": {"type": "array", "items": {"type": "string"}},
"filing_date": {"type": "string", "nullable": True, "description": "ISO 8601 date when case was filed"},
"urgency_indicators": {"type": "array", "items": {"type": "string"}},
"party_counsel": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "party": {"type": "string"},
            "counsel_name": {"type": "string"},
            "designation": {"type": "string", "enum": [
                "senior_advocate", "advocate", "aag", "ag", "sg",
                "asg", "amicus", "advocate_on_record"
            ]}
        }
    }
},
"issue_classification": {"type": "array", "items": {"type": "string"}},
"fact_pattern_tags": {
    "type": "array",
    "items": {"type": "string"},
    "description": "1-5 factual pattern tags from standard taxonomy"
},
"operative_order": {"type": "string", "nullable": True},
"conditions_imposed": {"type": "array", "items": {"type": "string"}},
"costs_awarded": {
    "type": "object",
    "nullable": True,
    "properties": {
        "amount": {"type": "string", "nullable": True},
        "to_whom": {"type": "string", "nullable": True},
        "reason": {"type": "string", "nullable": True}
    }
},
```

Also add all 22 field names to the `"required"` list in the schema.

**Step 5: Update METADATA_EXTRACTION_USER**

Add the new field names to the field list section (after line 116, after `companion_cases`).

**Step 6: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_metadata_v2_prompts.py tests/unit/test_agent_prompts.py -v
```

Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/app/core/legal/prompts.py backend/tests/unit/test_metadata_v2_prompts.py
git commit -m "feat: add V2 extraction rules 22-29 and schema properties to prompts"
```

---

## Task 5: Metadata Extraction — Remove Truncation, Send Full Text

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py:141-159` (remove truncation logic)

**Step 1: Write failing test**

File: add to `backend/tests/unit/test_metadata_v2.py`

```python
class TestFullTextExtraction:
    """Verify truncation is removed and full text is sent to LLM."""

    @pytest.mark.asyncio
    async def test_long_text_not_truncated(self):
        """Text longer than 50K chars should NOT be truncated."""
        from unittest.mock import AsyncMock
        from app.core.ingestion.metadata import extract_metadata_llm

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {"title": "Test"}

        long_text = "A" * 100_000  # 100K chars
        await extract_metadata_llm(long_text, mock_llm)

        # Verify LLM was called with full text (not truncated)
        call_args = mock_llm.generate_structured.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt") or call_args[0][0]
        # The prompt should contain the full text, not a truncated version
        assert len(prompt) >= 100_000
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_metadata_v2.py::TestFullTextExtraction -v
```

Expected: FAIL — text is truncated.

**Step 3: Remove truncation logic**

In `metadata.py`, replace lines 141-159 (the truncation block) with:

```python
    # V2: Send full text to LLM (Gemini 1M context supports this).
    # Average SC judgment = ~60K chars = ~20K tokens, well within limits.
    truncated = text
```

This preserves the variable name `truncated` used downstream without renaming everything.

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_metadata_v2.py tests/unit/test_metadata.py -v
```

Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/tests/unit/test_metadata_v2.py
git commit -m "feat: send full judgment text to LLM (remove 50K truncation)"
```

---

## Task 6: PDF Page Mapping — Track Page Boundaries During Extraction

**Files:**
- Modify: `backend/app/core/ingestion/pdf.py:369-432` (`_extract_pdf_text_sync`)
- Modify: `backend/app/core/ingestion/pdf.py:71-78` (`TextQuality` dataclass)
- Modify: `backend/app/core/ingestion/pdf.py:599` (`extract_and_score`)

**Step 1: Write failing test**

File: `backend/tests/unit/test_pdf_page_map.py`

```python
"""Tests for PDF page mapping."""
import pytest
from app.core.ingestion.pdf import TextQuality


class TestTextQualityPageMap:
    """Verify TextQuality includes page_map."""

    def test_page_map_field_exists(self):
        tq = TextQuality(
            text="test", char_count=4, tier="high",
            ocr_used=False, legal_keyword_count=0, page_count=1,
            page_map=[{"page_number": 1, "char_start": 0, "char_end": 4}],
        )
        assert len(tq.page_map) == 1
        assert tq.page_map[0]["page_number"] == 1

    def test_page_map_default_empty(self):
        tq = TextQuality(
            text="test", char_count=4, tier="high",
            ocr_used=False, legal_keyword_count=0, page_count=1,
        )
        assert tq.page_map == []

    def test_page_map_char_ranges_are_contiguous(self):
        page_map = [
            {"page_number": 1, "char_start": 0, "char_end": 100},
            {"page_number": 2, "char_start": 100, "char_end": 250},
            {"page_number": 3, "char_start": 250, "char_end": 400},
        ]
        for i in range(1, len(page_map)):
            assert page_map[i]["char_start"] == page_map[i - 1]["char_end"]
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_pdf_page_map.py -v
```

Expected: FAIL — `page_map` not a field on `TextQuality`.

**Step 3: Add page_map to TextQuality**

Modify `backend/app/core/ingestion/pdf.py` line 71-78:

```python
@dataclass
class TextQuality:
    """Quality assessment of extracted text."""
    text: str
    char_count: int
    tier: str  # "high", "medium", "low"
    ocr_used: bool
    legal_keyword_count: int
    page_count: int
    page_map: list[dict] = field(default_factory=list)  # NEW
```

Add `from dataclasses import dataclass, field` if only `dataclass` is imported.

**Step 4: Track page boundaries in `_extract_pdf_text_sync`**

Modify `_extract_pdf_text_sync` (line 369). After `_smart_page_join` at line 430, add page boundary tracking. The key insight: we need to track page boundaries BEFORE `_smart_page_join` and `clean_extracted_text` transform the text.

Add a new function before `_extract_pdf_text_sync`:

```python
def _build_page_map(page_texts: list[str], joined_text: str) -> list[dict]:
    """Build a page-number-to-character-offset map.

    Uses fuzzy matching: finds each page's first 50 chars in the joined text
    to handle join transformations (smart_page_join, clean_extracted_text).
    Falls back to sequential estimation if exact match fails.
    """
    page_map: list[dict] = []
    search_start = 0

    for i, page_text in enumerate(page_texts):
        page_num = i + 1
        # Find the start of this page's content in the joined text
        # Use first 50 non-whitespace chars as anchor
        anchor = page_text.strip()[:50]
        if not anchor:
            continue

        pos = joined_text.find(anchor, search_start)
        if pos == -1:
            # Fallback: estimate from previous page's end
            pos = page_map[-1]["char_end"] if page_map else 0

        # Find where this page's content ends
        # Use last 50 chars as end anchor
        end_anchor = page_text.strip()[-50:]
        end_pos = joined_text.find(end_anchor, pos)
        if end_pos != -1:
            end_pos += len(end_anchor)
        else:
            # Estimate: pos + original page length (rough)
            end_pos = min(pos + len(page_text), len(joined_text))

        page_map.append({
            "page_number": page_num,
            "char_start": pos,
            "char_end": end_pos,
        })
        search_start = pos + 1

    return page_map
```

Modify `_extract_pdf_text_sync` return to include page_map:

Change return type from `tuple[str, int]` to `tuple[str, int, list[dict]]`:

```python
def _extract_pdf_text_sync(file_path: str) -> tuple[str, int, list[dict]]:
```

After line 431 (`result = clean_extracted_text(result)`), add:

```python
    page_map = _build_page_map(page_texts, result)
    return result, total_pages, page_map
```

Update `extract_pdf_text` (async wrapper, line 435) similarly:

```python
async def extract_pdf_text(file_path: str) -> tuple[str, int, list[dict]]:
```

Update `extract_and_score` (line 599) to pass `page_map` into `TextQuality`:

```python
    text, page_count, page_map = await extract_pdf_text(file_path)
    # ... existing quality scoring ...
    return TextQuality(
        text=text, char_count=len(text), tier=tier,
        ocr_used=ocr_used, legal_keyword_count=kw_count,
        page_count=page_count, page_map=page_map,
    )
```

**Step 5: Update pipeline.py to use page_map**

In `pipeline.py`, `ingest_judgment` calls `extract_and_score` (around line 120). The returned `TextQuality` object now has `page_map`. Pass it through to `_insert_case` via the metadata or params dict. Add `page_map` to the params dict at line ~610:

```python
"page_map": json.dumps(tq.page_map) if tq.page_map else None,
```

And add the column to the SQL INSERT statement.

**Step 6: Run ALL tests**

```bash
cd backend && python -m pytest tests/unit/test_pdf_page_map.py tests/unit/test_ingestion_pipeline.py -v
```

Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/app/core/ingestion/pdf.py backend/app/core/ingestion/pipeline.py backend/tests/unit/test_pdf_page_map.py
git commit -m "feat: track PDF page boundaries for deep-linking"
```

---

## Task 7: Pipeline — Store New Fields in PostgreSQL INSERT

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:557-717` (`_insert_case` function)

**Step 1: Write failing test**

File: add to `backend/tests/unit/test_ingestion_pipeline.py` (or create new file if cleaner)

```python
class TestInsertCaseV2Fields:
    """Verify V2 fields are included in the SQL INSERT."""

    @pytest.mark.asyncio
    async def test_v2_fields_in_params(self):
        """Check that _insert_case builds params with all V2 fields."""
        from app.core.ingestion.metadata import CaseMetadata

        meta = CaseMetadata(
            title="Test Case",
            court="Supreme Court of India",
            judicial_tone="stern",
            arguments_raised=[{"party": "petitioner", "argument_type": "constitutional",
                              "argument_summary": "Art 21 violated", "accepted": True}],
            operative_order="The appeal is allowed.",
            fact_pattern_tags=["bail_application"],
        )
        # Verify these fields exist on the metadata object
        assert meta.judicial_tone == "stern"
        assert meta.arguments_raised[0]["accepted"] is True
        assert meta.operative_order == "The appeal is allowed."
```

**Step 2: Modify `_insert_case`**

Add all 22 new fields to the `params` dict (after line 610). Add the column names to the INSERT INTO column list and VALUES list. Add them to the ON CONFLICT UPDATE block.

The exact additions to `params` dict:

```python
# V2 fields
"arguments_raised": json.dumps(metadata.arguments_raised) if metadata.arguments_raised else None,
"relief_granted": metadata.relief_granted,
"relief_sought": metadata.relief_sought,
"sentence_details": json.dumps(metadata.sentence_details) if metadata.sentence_details else None,
"damages_awarded": json.dumps(metadata.damages_awarded) if metadata.damages_awarded else None,
"judicial_tone": metadata.judicial_tone,
"key_observations": metadata.key_observations,
"hearing_count": metadata.hearing_count,
"citation_treatments": json.dumps(metadata.citation_treatments) if metadata.citation_treatments else None,
"distinguished_cases": metadata.distinguished_cases,
"overruled_cases": metadata.overruled_cases,
"legal_principles_applied": metadata.legal_principles_applied,
"procedural_history": json.dumps(metadata.procedural_history) if metadata.procedural_history else None,
"interim_orders": metadata.interim_orders,
"filing_date": metadata.filing_date,
"urgency_indicators": metadata.urgency_indicators,
"party_counsel": json.dumps(metadata.party_counsel) if metadata.party_counsel else None,
"issue_classification": metadata.issue_classification,
"fact_pattern_tags": metadata.fact_pattern_tags,
"operative_order": metadata.operative_order,
"conditions_imposed": metadata.conditions_imposed,
"costs_awarded": json.dumps(metadata.costs_awarded) if metadata.costs_awarded else None,
"enrichment_status": metadata.enrichment_status,
```

**Step 3: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py -v
```

**Step 4: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat: store V2 metadata fields in PostgreSQL INSERT"
```

---

## Task 8: Pipeline — Enrich Pinecone Metadata per Chunk

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:812-836` (`_upsert_vectors` metadata dict)

**Step 1: Add new fields to Pinecone metadata**

After `"document_type": "case_law"` (line 834), add:

```python
"judicial_tone": metadata.judicial_tone or "",
"fact_pattern_tags": list(metadata.fact_pattern_tags[:5]) if metadata.fact_pattern_tags else [],
"issue_classification": list(metadata.issue_classification[:5]) if metadata.issue_classification else [],
"page_start": 0,   # Will be computed below
"page_end": 0,     # Will be computed below
"char_start": 0,   # Will be computed below
"char_end": 0,     # Will be computed below
```

To compute `page_start`/`page_end`, you need the `page_map`. Pass it as a parameter to `_upsert_vectors` and look up which page each chunk's text appears on:

```python
# Compute page location from page_map
if page_map:
    chunk_text_start = full_text.find(chunk.text[:50]) if full_text else -1
    if chunk_text_start >= 0:
        chunk_text_end = chunk_text_start + len(chunk.text)
        for pm in page_map:
            if pm["char_start"] <= chunk_text_start < pm["char_end"]:
                page_start = pm["page_number"]
                break
        for pm in page_map:
            if pm["char_start"] < chunk_text_end <= pm["char_end"]:
                page_end = pm["page_number"]
                break
```

**Step 2: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py -v
```

**Step 3: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat: add V2 fields + page location to Pinecone chunk metadata"
```

---

## Task 9: Pipeline — Enrich Neo4j Graph with New Nodes & Edges

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:843-916` (`_build_citation_graph`)

**Step 1: Write failing test**

File: add to `backend/tests/unit/test_ingestion_pipeline.py` or new file.

```python
class TestNeo4jV2Enrichment:
    """Verify V2 Neo4j nodes and edges are created."""

    def test_citation_treatment_context_extracted(self):
        """citation_treatments should provide context for CITES edges."""
        treatments = [
            {"cited_case": "AIR 1973 SC 1461", "treatment": "followed",
             "context": "Applied basic structure", "paragraph": 42},
        ]
        assert treatments[0]["context"] == "Applied basic structure"
```

**Step 2: Enhance `_build_citation_graph`**

After creating Case node + CITES edges (existing logic), add:

```python
    # --- V2: Enriched CITES edges with treatment context ---
    if metadata.citation_treatments:
        for ct in metadata.citation_treatments:
            cited = ct.get("cited_case", "")
            if not cited:
                continue
            treatment = ct.get("treatment", "referred_to")
            context = ct.get("context", "")
            paragraph = ct.get("paragraph")
            # Update existing CITES edge with richer data
            try:
                await graph_store.query(
                    "MATCH (a:Case {id: $case_id})-[r:CITES]->(b:Case) "
                    "WHERE b.citation CONTAINS $cited_fragment "
                    "SET r.context = $context, r.paragraph = $paragraph",
                    {"case_id": case_id, "cited_fragment": cited[:50],
                     "context": context[:500], "paragraph": paragraph},
                )
            except Exception:
                logger.debug("Could not enrich CITES edge for %s", cited)

    # --- V2: Counsel nodes ---
    if metadata.party_counsel:
        for pc in metadata.party_counsel:
            name = pc.get("counsel_name", "").strip()
            if not name:
                continue
            try:
                await graph_store.query(
                    "MERGE (c:Counsel {name: $name}) "
                    "SET c.designation = $designation "
                    "WITH c "
                    "MATCH (case:Case {id: $case_id}) "
                    "MERGE (case)-[:REPRESENTED_BY {party: $party}]->(c)",
                    {"name": name, "designation": pc.get("designation", "advocate"),
                     "party": pc.get("party", ""), "case_id": case_id},
                )
            except Exception:
                logger.debug("Could not create Counsel node for %s", name)

    # --- V2: LegalPrinciple nodes ---
    if metadata.legal_principles_applied:
        for principle in metadata.legal_principles_applied[:10]:
            try:
                await graph_store.query(
                    "MERGE (p:LegalPrinciple {name: $name}) "
                    "WITH p "
                    "MATCH (case:Case {id: $case_id}) "
                    "MERGE (case)-[:APPLIES_PRINCIPLE]->(p)",
                    {"name": principle.strip(), "case_id": case_id},
                )
            except Exception:
                logger.debug("Could not create LegalPrinciple node for %s", principle)

    # --- V2: Issue nodes ---
    if metadata.issue_classification:
        for tag in metadata.issue_classification[:10]:
            try:
                await graph_store.query(
                    "MERGE (i:Issue {tag: $tag}) "
                    "WITH i "
                    "MATCH (case:Case {id: $case_id}) "
                    "MERGE (case)-[:ADDRESSES]->(i)",
                    {"tag": tag.strip(), "case_id": case_id},
                )
            except Exception:
                logger.debug("Could not create Issue node for %s", tag)
```

**Step 3: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py -v
```

**Step 4: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat: create Counsel, LegalPrinciple, Issue nodes in Neo4j during ingestion"
```

---

## Task 10: FTS Trigger — Add New Fields to Searchable Text

**Files:**
- Modify: `backend/migrations/versions/021_ingestion_v2_fields.py` (add trigger update to existing migration)

**Step 1: Add trigger update to migration 021**

Add to the `upgrade()` function in migration 021:

```python
    # Update FTS trigger to include new fields
    op.execute("""
        CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.case_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.operative_order, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.legal_principles_applied, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.issue_classification, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(left(NEW.full_text, 100000), '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
```

**Step 2: Commit**

```bash
git add backend/migrations/versions/021_ingestion_v2_fields.py
git commit -m "feat: update FTS trigger with operative_order, legal_principles, issue_classification"
```

---

## Task 11: Pass 2 Enrichment Script

**Files:**
- Create: `backend/scripts/enrich_pro.py`

**Step 1: Create the enrichment script**

```python
"""Pass 2 enrichment: re-extract complex fields using Gemini Pro.

Usage:
    python scripts/enrich_pro.py --judge "D.Y. Chandrachud"
    python scripts/enrich_pro.py --section "302 IPC"
    python scripts/enrich_pro.py --case-type "Criminal Appeal"
    python scripts/enrich_pro.py --all --limit 100
    python scripts/enrich_pro.py --case-id <uuid>
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text
from app.core.config import settings
from app.core.dependencies import get_llm
from app.core.legal.prompts import METADATA_EXTRACTION_SYSTEM, METADATA_OUTPUT_SCHEMA
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)

# Only the 8 complex fields that benefit from Pro
PRO_FIELDS = [
    "arguments_raised", "citation_treatments", "judicial_tone",
    "legal_principles_applied", "procedural_history", "issue_classification",
    "fact_pattern_tags", "operative_order",
]

PRO_EXTRACTION_SYSTEM = """You are re-analyzing a previously processed Indian court judgment.
Focus ONLY on extracting these 8 fields with maximum accuracy:
1. arguments_raised — every distinct argument with accepted/rejected classification
2. citation_treatments — HOW each cited case was treated (followed/distinguished/overruled etc)
3. judicial_tone — overall tone classification
4. legal_principles_applied — named legal doctrines
5. procedural_history — chain of courts
6. issue_classification — hierarchical legal issue tags
7. fact_pattern_tags — factual pattern categories
8. operative_order — verbatim operative portion

Use the full judgment text provided. Be thorough and precise."""

# Build a reduced schema with only PRO_FIELDS
PRO_SCHEMA = {
    "type": "object",
    "properties": {k: v for k, v in METADATA_OUTPUT_SCHEMA["properties"].items() if k in PRO_FIELDS},
    "required": PRO_FIELDS,
}


async def enrich_case(case_id: str, full_text: str, llm) -> dict:
    """Re-extract 8 complex fields using Pro."""
    result = await llm.generate_structured(
        prompt=full_text,
        system=PRO_EXTRACTION_SYSTEM,
        output_schema=PRO_SCHEMA,
    )
    return result


async def run(args):
    llm = get_llm()  # This gets Pro model

    async with async_session_factory() as db:
        # Build filter query
        conditions = ["enrichment_status = 'flash_only'"]
        params: dict = {}

        if args.judge:
            conditions.append("array_to_string(judge, ' ') ILIKE :judge")
            params["judge"] = f"%{args.judge}%"
        if args.section:
            conditions.append("array_to_string(acts_cited, ' ') ILIKE :section")
            params["section"] = f"%{args.section}%"
        if args.case_type:
            conditions.append("case_type = :case_type")
            params["case_type"] = args.case_type
        if args.case_id:
            conditions.append("id = :case_id")
            params["case_id"] = args.case_id

        where = " AND ".join(conditions)
        limit = args.limit or 100

        result = await db.execute(
            sa_text(f"SELECT id, full_text FROM cases WHERE {where} LIMIT :limit"),
            {**params, "limit": limit},
        )
        rows = result.fetchall()
        logger.info("Found %d cases to enrich", len(rows))

        success = 0
        for row in rows:
            case_id, full_text = str(row[0]), row[1]
            if not full_text:
                logger.warning("Case %s has no full_text, skipping", case_id)
                continue

            try:
                enriched = await enrich_case(case_id, full_text, llm)

                # Build UPDATE SET clause for non-None fields
                updates = []
                update_params = {"case_id": case_id}
                for field_name in PRO_FIELDS:
                    value = enriched.get(field_name)
                    if value is not None:
                        if isinstance(value, (dict, list)):
                            update_params[field_name] = json.dumps(value)
                        else:
                            update_params[field_name] = value
                        updates.append(f"{field_name} = :{field_name}")

                updates.append("enrichment_status = 'pro_enriched'")
                update_params["enrichment_status"] = "pro_enriched"

                if updates:
                    await db.execute(
                        sa_text(f"UPDATE cases SET {', '.join(updates)} WHERE id = :case_id"),
                        update_params,
                    )
                    await db.commit()
                    success += 1
                    logger.info("Enriched case %s (%d/%d)", case_id, success, len(rows))

            except Exception as e:
                logger.error("Failed to enrich case %s: %s", case_id, e)
                await db.execute(
                    sa_text("UPDATE cases SET enrichment_status = 'failed' WHERE id = :case_id"),
                    {"case_id": case_id},
                )
                await db.commit()

        logger.info("Done: %d/%d cases enriched", success, len(rows))


def main():
    parser = argparse.ArgumentParser(description="Pass 2: Enrich cases with Gemini Pro")
    parser.add_argument("--judge", help="Filter by judge name (ILIKE)")
    parser.add_argument("--section", help="Filter by section/act in acts_cited (ILIKE)")
    parser.add_argument("--case-type", help="Filter by exact case_type")
    parser.add_argument("--case-id", help="Enrich a single case by UUID")
    parser.add_argument("--all", action="store_true", help="Enrich all flash_only cases")
    parser.add_argument("--limit", type=int, default=100, help="Max cases to process (default: 100)")
    args = parser.parse_args()

    if not (args.judge or args.section or args.case_type or args.case_id or args.all):
        parser.error("Specify at least one filter: --judge, --section, --case-type, --case-id, or --all")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add backend/scripts/enrich_pro.py
git commit -m "feat: add Pass 2 Pro enrichment script for selective re-extraction"
```

---

## Task 12: Run Full Test Suite & Verify No Regressions

**Files:**
- No new files — verification only.

**Step 1: Run all backend unit tests**

```bash
cd backend && python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```

Expected: All existing 1411 tests pass + new tests pass.

**Step 2: Fix any failures**

If any existing test fails due to the new fields (e.g., tests that construct CaseMetadata without the new fields), the defaults ensure backward compatibility. The only risk is tests that check `_extract_pdf_text_sync` return value — those need updating from `tuple[str, int]` to `tuple[str, int, list[dict]]`.

**Step 3: Final commit**

```bash
git add -A
git commit -m "test: verify no regressions from ingestion V2 changes"
```

---

## Summary: Commit Sequence

| # | Commit | Files |
|---|---|---|
| 1 | `migration(021): add 22 V2 fields + page_map + enrichment_status` | migration |
| 2 | `feat: add 23 V2 columns to Case model` | case.py, test |
| 3 | `feat: add 22 V2 fields to CaseMetadata dataclass` | metadata.py, test |
| 4 | `feat: add V2 extraction rules 22-29 and schema properties` | prompts.py, test |
| 5 | `feat: send full judgment text to LLM` | metadata.py, test |
| 6 | `feat: track PDF page boundaries for deep-linking` | pdf.py, pipeline.py, test |
| 7 | `feat: store V2 metadata fields in PostgreSQL INSERT` | pipeline.py |
| 8 | `feat: add V2 fields + page location to Pinecone metadata` | pipeline.py |
| 9 | `feat: create Counsel, LegalPrinciple, Issue nodes in Neo4j` | pipeline.py |
| 10 | `feat: update FTS trigger with V2 fields` | migration |
| 11 | `feat: add Pass 2 Pro enrichment script` | enrich_pro.py |
| 12 | `test: verify no regressions` | — |

**Total: 12 tasks, ~7 files modified, ~3 files created, ~6 test files.**

**Dependencies:** Tasks 1-4 can be done in parallel. Tasks 5-10 depend on Tasks 1-4. Task 11 is independent. Task 12 is last.
