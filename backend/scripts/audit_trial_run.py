"""Audit quality of cases ingested in a trial run."""

import asyncio

import asyncpg

DATABASE_URL = (
    "postgresql://smriti:E9tGr2mSXTi1h36LwsmLKbRVooPmlZbYIY5FnYmuzWg=@76.13.185.172:5432/smriti"
)

QUERY = """
SELECT
    id, title, citation, court, year, decision_date,
    petitioner, respondent, author_judge, judge,
    disposal_nature, case_type, bench_type, coram_size,
    LEFT(ratio_decidendi, 100) AS ratio_snippet,
    keywords, acts_cited, cases_cited,
    LEFT(headnotes, 100) AS headnotes_snippet,
    LEFT(outcome_summary, 100) AS outcome_snippet,
    jurisdiction, is_reportable, extraction_confidence,
    chunk_count, ingestion_status,
    char_length(full_text) AS text_length
FROM cases
WHERE created_at >= '2026-03-31 10:30:00'::timestamptz
  AND created_at <= '2026-03-31 11:30:00'::timestamptz
ORDER BY year, title
"""

FIELDS_TO_CHECK = [
    "title",
    "citation",
    "court",
    "year",
    "decision_date",
    "petitioner",
    "respondent",
    "author_judge",
    "judge",
    "disposal_nature",
    "case_type",
    "bench_type",
    "coram_size",
    "ratio_snippet",
    "keywords",
    "acts_cited",
    "cases_cited",
    "headnotes_snippet",
    "outcome_snippet",
    "jurisdiction",
    "is_reportable",
    "extraction_confidence",
    "chunk_count",
    "ingestion_status",
    "text_length",
]


def is_populated(val):
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    return not (isinstance(val, list) and len(val) == 0)


async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(QUERY)
    await conn.close()

    if not rows:
        return

    # ── Per-case summary table ──

    issues = []
    field_populated = {f: 0 for f in FIELDS_TO_CHECK}

    for i, r in enumerate(rows, 1):
        rec = dict(r)

        # Count populated fields
        for f in FIELDS_TO_CHECK:
            if is_populated(rec.get(f)):
                field_populated[f] += 1

        len(rec["acts_cited"]) if rec["acts_cited"] else 0
        len(rec["cases_cited"]) if rec["cases_cited"] else 0
        conf = rec["extraction_confidence"] or 0.0
        title_short = (rec["title"] or "???")[:55]
        rec["ingestion_status"] or "?"
        chunks = rec["chunk_count"] or 0
        tlen = rec["text_length"] or 0

        # Flag issues
        case_label = f"Case #{i} ({title_short[:30]}...)"
        if conf < 0.5:
            issues.append(f"  LOW CONFIDENCE ({conf:.2f}): {case_label}")
        if not rec["title"]:
            issues.append(f"  MISSING TITLE: {case_label}")
        if not rec["citation"]:
            issues.append(f"  MISSING CITATION: {case_label}")
        if not rec["petitioner"]:
            issues.append(f"  MISSING PETITIONER: {case_label}")
        if not rec["respondent"]:
            issues.append(f"  MISSING RESPONDENT: {case_label}")
        if not rec["author_judge"]:
            issues.append(f"  MISSING AUTHOR_JUDGE: {case_label}")
        if not rec["acts_cited"] or len(rec["acts_cited"]) == 0:
            issues.append(f"  NO ACTS CITED: {case_label}")
        if chunks == 0:
            issues.append(f"  ZERO CHUNKS: {case_label}")
        if tlen < 1000:
            issues.append(f"  VERY SHORT TEXT ({tlen} chars): {case_label}")
        if not rec["ratio_snippet"]:
            issues.append(f"  MISSING RATIO DECIDENDI: {case_label}")
        if not rec["headnotes_snippet"]:
            issues.append(f"  MISSING HEADNOTES: {case_label}")
        if not rec["outcome_snippet"]:
            issues.append(f"  MISSING OUTCOME SUMMARY: {case_label}")
        if not rec["decision_date"]:
            issues.append(f"  MISSING DECISION_DATE: {case_label}")
        if not rec["disposal_nature"]:
            issues.append(f"  MISSING DISPOSAL_NATURE: {case_label}")

    # ── Field completeness ──
    total = len(rows)

    for f in FIELDS_TO_CHECK:
        (field_populated[f] / total) * 100

    sum(field_populated.values()) / (len(FIELDS_TO_CHECK) * total) * 100

    # ── Quality issues ──
    if issues:
        for _iss in issues:
            pass
    else:
        pass

    # ── Detail dump for each case ──
    for i, r in enumerate(rows, 1):
        rec = dict(r)


if __name__ == "__main__":
    asyncio.run(main())
