"""Audit quality of cases ingested in a trial run."""
import asyncio
import asyncpg

DATABASE_URL = "postgresql://smriti:E9tGr2mSXTi1h36LwsmLKbRVooPmlZbYIY5FnYmuzWg=@76.13.185.172:5432/smriti"

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
    "title", "citation", "court", "year", "decision_date",
    "petitioner", "respondent", "author_judge", "judge",
    "disposal_nature", "case_type", "bench_type", "coram_size",
    "ratio_snippet", "keywords", "acts_cited", "cases_cited",
    "headnotes_snippet", "outcome_snippet",
    "jurisdiction", "is_reportable", "extraction_confidence",
    "chunk_count", "ingestion_status", "text_length",
]


def is_populated(val):
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    if isinstance(val, (list,)) and len(val) == 0:
        return False
    return True


async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(QUERY)
    await conn.close()

    if not rows:
        print("NO CASES FOUND in the specified time window.")
        return

    print(f"\n{'='*120}")
    print(f"INGESTION QUALITY AUDIT — {len(rows)} cases found")
    print(f"{'='*120}\n")

    # ── Per-case summary table ──
    print(f"{'#':>3} {'Year':>5} {'Conf':>5} {'Chunks':>6} {'TextLen':>8} {'Acts':>5} {'Cases':>6} {'Status':>10}  {'Title (truncated)'}")
    print(f"{'-'*3} {'-'*5} {'-'*5} {'-'*6} {'-'*8} {'-'*5} {'-'*6} {'-'*10}  {'-'*50}")

    issues = []
    field_populated = {f: 0 for f in FIELDS_TO_CHECK}

    for i, r in enumerate(rows, 1):
        rec = dict(r)

        # Count populated fields
        for f in FIELDS_TO_CHECK:
            if is_populated(rec.get(f)):
                field_populated[f] += 1

        acts_count = len(rec["acts_cited"]) if rec["acts_cited"] else 0
        cases_count = len(rec["cases_cited"]) if rec["cases_cited"] else 0
        conf = rec["extraction_confidence"] or 0.0
        title_short = (rec["title"] or "???")[:55]
        status = rec["ingestion_status"] or "?"
        chunks = rec["chunk_count"] or 0
        tlen = rec["text_length"] or 0

        print(f"{i:>3} {rec['year'] or '?':>5} {conf:>5.2f} {chunks:>6} {tlen:>8} {acts_count:>5} {cases_count:>6} {status:>10}  {title_short}")

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
    print(f"\n{'='*120}")
    print("FIELD COMPLETENESS")
    print(f"{'='*120}")
    print(f"{'Field':<25} {'Populated':>10} {'Total':>7} {'%':>7}")
    print(f"{'-'*25} {'-'*10} {'-'*7} {'-'*7}")

    for f in FIELDS_TO_CHECK:
        pct = (field_populated[f] / total) * 100
        marker = " !!!" if pct < 80 else ""
        print(f"{f:<25} {field_populated[f]:>10} {total:>7} {pct:>6.1f}%{marker}")

    overall = sum(field_populated.values()) / (len(FIELDS_TO_CHECK) * total) * 100
    print(f"\nOVERALL COMPLETENESS: {overall:.1f}%")

    # ── Quality issues ──
    print(f"\n{'='*120}")
    print(f"QUALITY ISSUES ({len(issues)} found)")
    print(f"{'='*120}")
    if issues:
        for iss in issues:
            print(iss)
    else:
        print("  None! All cases look good.")

    # ── Detail dump for each case ──
    print(f"\n{'='*120}")
    print("DETAILED CASE DATA")
    print(f"{'='*120}")
    for i, r in enumerate(rows, 1):
        rec = dict(r)
        print(f"\n--- Case #{i} ---")
        print(f"  ID:            {rec['id']}")
        print(f"  Title:         {rec['title']}")
        print(f"  Citation:      {rec['citation']}")
        print(f"  Court:         {rec['court']}")
        print(f"  Year:          {rec['year']}")
        print(f"  Decision Date: {rec['decision_date']}")
        print(f"  Petitioner:    {rec['petitioner']}")
        print(f"  Respondent:    {rec['respondent']}")
        print(f"  Author Judge:  {rec['author_judge']}")
        print(f"  Judges:        {rec['judge']}")
        print(f"  Disposal:      {rec['disposal_nature']}")
        print(f"  Case Type:     {rec['case_type']}")
        print(f"  Bench Type:    {rec['bench_type']}")
        print(f"  Coram Size:    {rec['coram_size']}")
        print(f"  Jurisdiction:  {rec['jurisdiction']}")
        print(f"  Reportable:    {rec['is_reportable']}")
        print(f"  Confidence:    {rec['extraction_confidence']}")
        print(f"  Chunks:        {rec['chunk_count']}")
        print(f"  Text Length:   {rec['text_length']}")
        print(f"  Status:        {rec['ingestion_status']}")
        print(f"  Keywords:      {rec['keywords']}")
        print(f"  Acts Cited:    {rec['acts_cited']}")
        print(f"  Cases Cited:   {rec['cases_cited']}")
        print(f"  Ratio:         {rec['ratio_snippet']}")
        print(f"  Headnotes:     {rec['headnotes_snippet']}")
        print(f"  Outcome:       {rec['outcome_snippet']}")


if __name__ == "__main__":
    asyncio.run(main())
