"""Audit all cases ingested today (2026-03-31) for quality issues."""
import asyncio
import re
from datetime import date

import asyncpg

DATABASE_URL = "postgresql://smriti:E9tGr2mSXTi1h36LwsmLKbRVooPmlZbYIY5FnYmuzWg=@76.13.185.172:5432/smriti"

QUERY = """
SELECT id, title, citation, court, year, decision_date,
       petitioner, respondent, author_judge, judge,
       disposal_nature, case_type, bench_type, coram_size,
       ratio_decidendi, keywords, acts_cited, cases_cited,
       headnotes, outcome_summary, jurisdiction, is_reportable,
       extraction_confidence, case_number,
       char_length(full_text) as text_length,
       opinion_type, judicial_tone
FROM cases
WHERE created_at >= $1
ORDER BY year, title
"""

VERB_PATTERNS = re.compile(
    r'\b(hold|held|accordance|submitted|contended|argued|stated|observed|opined|'
    r'directed|ordered|dismissed|allowed|granted|upheld|reversed|modified|'
    r'set aside|quashed|maintaining|considering|examined|analyzed)\b',
    re.IGNORECASE
)


def check_ocr_title(title):
    issues = []
    if not title:
        issues.append("title is NULL/empty")
        return issues
    if " 0F " in title or " 0f " in title:
        idx = title.upper().find(" 0F ")
        issues.append(f"title has OCR artifact '0F' instead of 'OF': ...{title[max(0,idx-10):idx+12]}...")
    if re.search(r'[^\x20-\x7E\u0900-\u097F.,&()/\\:;\-\'@#$%^*!?\[\]{{}}|~`+= ]', title):
        garbled = [c for c in title if not re.match(r'[\x20-\x7E\u0900-\u097F.,&()/\\:;\-\'@#$%^*!?\[\]{}|~`+= ]', c)]
        if garbled:
            issues.append(f"title has garbled chars: {garbled[:5]}")
    return issues


def check_acts_cited(acts):
    issues = []
    if not acts:
        return issues
    for act in acts:
        if not act or len(act.strip()) < 3:
            continue
        if VERB_PATTERNS.search(act) and len(act) > 40:
            display = act[:80] + "..." if len(act) > 80 else act
            issues.append(f"acts_cited has sentence fragment: '{display}'")
        words = act.split()
        if len(words) >= 4:
            short_words = [w for w in words if len(w) <= 2 and w.isalpha()]
            if len(short_words) >= 3:
                issues.append(f"acts_cited may have OCR garbage: '{act[:80]}'")
    return issues


def check_cases_cited(cases):
    issues = []
    if not cases:
        return issues
    seen_names = {}
    for c in cases:
        if not c:
            continue
        name_part = re.split(r'\(\d{4}\)|\[\d{4}\]|\d{4}\s', c)[0].strip().lower()
        name_part = re.sub(r'[^a-z\s]', '', name_part).strip()
        if len(name_part) > 5:
            if name_part in seen_names:
                issues.append(f"cases_cited duplicate: '{c[:60]}' vs '{seen_names[name_part][:60]}'")
            else:
                seen_names[name_part] = c
        if re.match(r'^\s*\(\d{4}\)\s+\d+\s+\w+\s+\d+\s*$', c) or re.match(r'^\s*\d{4}\s+\(\d+\)\s+\w+\s+\d+\s*$', c):
            issues.append(f"cases_cited bare ref without case name: '{c}'")
    return issues


def check_bench_coram(bench_type, coram_size):
    issues = []
    if not bench_type or not coram_size:
        return issues
    bt = bench_type.lower()
    cs = coram_size
    if bt == 'division bench' and cs < 2:
        issues.append(f"bench_type '{bench_type}' but coram_size={cs}")
    if bt == 'constitution bench' and cs < 5:
        issues.append(f"bench_type '{bench_type}' but coram_size={cs}")
    if bt == 'full bench' and cs < 3:
        issues.append(f"bench_type '{bench_type}' but coram_size={cs}")
    if bt == 'single bench' and cs > 1:
        issues.append(f"bench_type '{bench_type}' but coram_size={cs}")
    return issues


def check_case_type_number(case_type, case_number):
    issues = []
    if not case_type or not case_number:
        return issues
    ct = case_type.lower()
    cn = case_number.lower()
    if 'criminal' in ct and 'civil' in cn:
        issues.append(f"case_type '{case_type}' but case_number '{case_number}' suggests civil")
    if 'civil' in ct and 'criminal' in cn:
        issues.append(f"case_type '{case_type}' but case_number '{case_number}' suggests criminal")
    return issues


def assess_case(r):
    issues = []
    issues.extend(check_ocr_title(r['title']))

    if not r['petitioner']:
        issues.append("petitioner is NULL/empty")
    if not r['respondent']:
        issues.append("respondent is NULL/empty")

    if not r['decision_date']:
        issues.append("decision_date is NULL")
    elif r['year'] and r['decision_date'].year != r['year']:
        issues.append(f"decision_date year ({r['decision_date'].year}) != case year ({r['year']})")

    if not r['judge'] or (isinstance(r['judge'], list) and len(r['judge']) == 0):
        issues.append("judge list is NULL/empty")

    if not r['author_judge']:
        issues.append("author_judge is NULL/empty")

    issues.extend(check_case_type_number(r['case_type'], r['case_number']))
    issues.extend(check_bench_coram(r['bench_type'], r['coram_size']))
    issues.extend(check_acts_cited(r['acts_cited']))
    issues.extend(check_cases_cited(r['cases_cited']))

    if not r['ratio_decidendi']:
        issues.append("ratio_decidendi is NULL/empty")
    elif len(r['ratio_decidendi']) < 50:
        issues.append(f"ratio_decidendi too short ({len(r['ratio_decidendi'])} chars)")

    if not r['outcome_summary']:
        issues.append("outcome_summary is NULL/empty")

    if not r['headnotes'] or (isinstance(r['headnotes'], list) and len(r['headnotes']) == 0):
        issues.append("headnotes is NULL/empty")

    if not r['keywords'] or (isinstance(r['keywords'], list) and len(r['keywords']) == 0):
        issues.append("keywords is NULL/empty")
    elif isinstance(r['keywords'], list) and len(r['keywords']) <= 3:
        issues.append(f"keywords has only {len(r['keywords'])} entries (want >3)")

    if r['text_length'] and r['text_length'] < 5000:
        issues.append(f"text_length={r['text_length']} (potentially incomplete)")

    if not r['citation']:
        issues.append("citation is NULL/empty")
    if not r['court']:
        issues.append("court is NULL/empty")
    if not r['case_type']:
        issues.append("case_type is NULL/empty")
    if not r['extraction_confidence']:
        issues.append("extraction_confidence is NULL")
    elif r['extraction_confidence'] < 0.5:
        issues.append(f"extraction_confidence very low: {r['extraction_confidence']}")

    return issues


def determine_verdict(issues):
    if not issues:
        return "OK", "No issues found"

    ' '.join(issues)
    null_count = sum(1 for i in issues if 'NULL/empty' in i)
    ocr_count = sum(1 for i in issues if 'OCR' in i or 'garbled' in i)

    if null_count >= 5:
        return "RE-INGEST", f"{null_count} NULL/empty fields - likely extraction failure"
    if ocr_count >= 3:
        return "MODIFY", f"{ocr_count} OCR issues - cleanable"
    if len(issues) >= 6:
        return "RE-INGEST", f"{len(issues)} total issues - too many problems"
    if len(issues) >= 1:
        return "MODIFY", f"{len(issues)} issues - fixable"

    return "OK", "No issues"


async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(QUERY, date(2026, 3, 31))

        verdicts = {"OK": [], "MODIFY": [], "RE-INGEST": [], "DELETE": []}

        for _i, row in enumerate(rows, 1):
            r = dict(row)
            issues = assess_case(r)
            verdict, reason = determine_verdict(issues)
            verdicts[verdict].append(r['id'])

            (r['title'] or 'NULL')[:60]
            (r['petitioner'] or 'NULL')[:60]
            (r['respondent'] or 'NULL')[:60]
            len(r['cases_cited']) if r['cases_cited'] else 0
            if r['cases_cited']:
                for _cc in r['cases_cited']:
                    pass
            len(r['headnotes']) if r['headnotes'] else 0
            if r['headnotes']:
                for _hn in r['headnotes']:
                    pass
            (r['ratio_decidendi'] or 'NULL')[:150]
            (r['outcome_summary'] or 'NULL')[:150]

            if issues:
                for _iss in issues:
                    pass
            else:
                pass


        # Summary

        for v in ["OK", "MODIFY", "RE-INGEST", "DELETE"]:
            if verdicts[v]:
                for cid in verdicts[v]:
                    next(
                        ((dict(r)['title'] or '?')[:60] for r in rows if dict(r)['id'] == cid),
                        '?'
                    )

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
