"""
Comprehensive quality audit of ALL cases in the PostgreSQL database.
Checks CRITICAL, HIGH, and MEDIUM issues for every case.
"""

import re
from collections import Counter, defaultdict

import psycopg2

DATABASE_URL = (
    "postgresql://smriti:E9tGr2mSXTi1h36LwsmLKbRVooPmlZbYIY5FnYmuzWg=@76.13.185.172:5432/smriti"
)

# ── helpers ──────────────────────────────────────────────────────────────

OCR_TITLE_PATTERNS = [
    (r"\b0F\b", 'title has "0F" instead of "OF"'),
    (r"\b0R\b", 'title has "0R" instead of "OR"'),
    (r"\b1N\b", 'title has "1N" instead of "IN"'),
]

VERB_WORDS = {
    "is",
    "was",
    "were",
    "shall",
    "should",
    "hold",
    "held",
    "has",
    "have",
    "had",
    "may",
    "can",
    "will",
    "would",
    "could",
    "must",
    "being",
    "been",
    "provide",
    "provides",
    "provided",
    "said",
    "says",
    "stated",
    "states",
    "filed",
    "contended",
    "submitted",
    "argued",
    "observed",
    "directed",
    "ordered",
    "granted",
    "dismissed",
    "allowed",
    "rejected",
    "upheld",
}


def has_control_chars(s):
    if not s:
        return False
    return any(ord(c) < 32 and c not in ("\n", "\r", "\t") for c in s)


def has_garbled_nonascii(s):
    if not s:
        return False
    garbled = 0
    for c in s:
        o = ord(c)
        if 128 <= o < 256 and c not in (
            "é",
            "è",
            "ê",
            "ë",
            "ñ",
            "ü",
            "ö",
            "ä",
            "§",
            "°",
            "–",
            "—",
            """, """,
            '"',
            '"',
        ):
            garbled += 1
    return garbled > 2


def is_act_garbage(entry):
    """Check if an acts_cited entry is garbage."""
    if not entry or len(entry.strip()) < 3:
        return True, "too short"
    e = entry.strip()
    # sentence fragment: contains verbs
    words_lower = set(e.lower().split())
    verb_hits = words_lower & VERB_WORDS
    if len(verb_hits) >= 1 and len(e.split()) > 4:
        return True, f"sentence fragment (verb: {', '.join(verb_hits)})"
    # spaces in middle of words: "Cen tral", "Cootract"
    if re.search(r"[a-z]\s[a-z]{1,3}\s[a-z]", e, re.IGNORECASE) and len(e) > 15:
        # Check more carefully - could be normal words
        pass
    # case title leaking
    if " v. " in e or " versus " in e.lower() or " v/s " in e.lower():
        return True, "case title leaked into act"
    # starts with COURT or CRIMINAL (all caps section headers)
    if re.match(r"^(COURT|CRIMINAL|CIVIL|BENCH|JUDGE|HON)", e) and e == e.upper():
        return True, "section header leaked"
    # OCR garbled
    if has_garbled_nonascii(e):
        return True, "OCR garbled chars"
    return False, None


def is_bare_citation(entry):
    """Check if a cases_cited entry is a bare citation without party names."""
    if not entry:
        return False
    e = entry.strip()
    # Has party names if it contains "v." or "versus"
    if " v. " in e or " v " in e or "versus" in e.lower() or " v/s " in e.lower():
        return False
    # It's a bare citation if it matches common citation patterns without names
    bare_patterns = [
        r"^\(\d{4}\)\s+\d+\s+SCC",
        r"^\d{4}\s+\(\d+\)\s+SCC",
        r"^\d{4}\s+SCC\s+",
        r"^AIR\s+\d{4}",
        r"^\d{4}\s+AIR\s+",
        r"^\(\d{4}\)\s+\d+\s+SCR",
        r"^\d{4}:\w+:\d+",  # neutral citation
        r"^\d{4}\s+\d+\s+SCR",
        r"^\d{4}\s+Supp",
        r"^MANU/",
    ]
    return any(re.match(pat, e) for pat in bare_patterns)


def check_bench_coram_mismatch(bench_type, coram_size):
    if not bench_type or not coram_size:
        return False
    bt = bench_type.lower()
    cs = coram_size
    if bt == "division bench" and cs < 2:
        return True
    if bt == "single judge" and cs > 1:
        return True
    if bt == "constitution bench" and cs < 5:
        return True
    return bool(bt == "full bench" and cs < 3)


def check_case_type_vs_number(case_type, case_number):
    if not case_type or not case_number:
        return False
    ct = case_type.lower()
    cn = case_number.lower()
    # civil vs criminal contradiction
    if "criminal" in ct and "civil" in cn and "criminal" not in cn:
        return True
    return bool("civil" in ct and "criminal" in cn and "civil" not in cn)


# ── main ─────────────────────────────────────────────────────────────────


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    query = """
    SELECT id, title, citation, court, year, decision_date,
           petitioner, respondent, author_judge, judge,
           disposal_nature, case_type, bench_type, coram_size,
           ratio_decidendi, keywords, acts_cited, cases_cited,
           headnotes, outcome_summary, jurisdiction, is_reportable,
           extraction_confidence, case_number,
           char_length(full_text) as text_length,
           created_at
    FROM cases ORDER BY year, title
    """
    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    # Issue tracking
    critical_counts = Counter()
    high_counts = Counter()
    medium_counts = Counter()
    case_issues = {}  # case_id -> list of (severity, issue_name, detail)
    garbage_acts = []  # (case_id, year, title, act_entry, reason)
    bare_cite_cases = []  # (case_id, year, title, bare_count, total_count)
    low_confidence_cases = []  # (case_id, year, title, confidence)
    year_stats = defaultdict(
        lambda: {
            "count": 0,
            "confidence_sum": 0,
            "confidence_count": 0,
            "ratio_populated": 0,
            "clean_acts": 0,
            "clean_cites": 0,
        }
    )
    date_stats = defaultdict(lambda: Counter())  # created_date -> severity counter
    all_titles = []  # for cross-contamination check

    # First pass: collect all titles for cross-contamination
    for row in rows:
        r = dict(zip(columns, row, strict=False))
        if r["title"]:
            all_titles.append((r["id"], r["year"], r["title"][:80]))

    # Main audit loop
    for row in rows:
        r = dict(zip(columns, row, strict=False))
        cid = r["id"]
        issues = []
        year = r["year"]
        created_date = r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else "unknown"

        # ── CRITICAL ─────────────────────────────────────────────────

        # OCR artifacts in title
        if r["title"]:
            for pat, desc in OCR_TITLE_PATTERNS:
                if re.search(pat, r["title"]):
                    issues.append(("CRITICAL", desc, r["title"][:60]))
                    critical_counts[desc] += 1

        # Garbled non-ASCII in title
        if has_garbled_nonascii(r["title"]):
            issues.append(("CRITICAL", "title has garbled non-ASCII", r["title"][:60]))
            critical_counts["title has garbled non-ASCII"] += 1

        # Control chars in title
        if has_control_chars(r["title"]):
            issues.append(("CRITICAL", "title has control chars", repr(r["title"][:60])))
            critical_counts["title has control chars"] += 1

        # Year vs decision_date mismatch
        if r["year"] and r["decision_date"]:
            dd_year = r["decision_date"].year
            if abs(r["year"] - dd_year) > 0:
                issues.append(
                    (
                        "CRITICAL",
                        "year != decision_date year",
                        f"year={r['year']}, decision_date={r['decision_date']}",
                    )
                )
                critical_counts["year != decision_date year"] += 1

        # case_type vs case_number contradiction
        if check_case_type_vs_number(r["case_type"], r["case_number"]):
            issues.append(
                (
                    "CRITICAL",
                    "case_type contradicts case_number",
                    f"type={r['case_type']}, number={r['case_number']}",
                )
            )
            critical_counts["case_type contradicts case_number"] += 1

        # Low extraction confidence
        if r["extraction_confidence"] is not None and r["extraction_confidence"] < 0.5:
            issues.append(
                (
                    "CRITICAL",
                    "extraction_confidence < 0.5",
                    f"confidence={r['extraction_confidence']:.2f}",
                )
            )
            critical_counts["extraction_confidence < 0.5"] += 1

        # Suspiciously short text
        if r["text_length"] is not None and r["text_length"] < 1000:
            issues.append(("CRITICAL", "text_length < 1000", f"length={r['text_length']}"))
            critical_counts["text_length < 1000"] += 1

        # ── HIGH ─────────────────────────────────────────────────────

        # acts_cited garbage
        acts = r["acts_cited"] or []
        has_garbage_acts = False
        for act in acts:
            is_garbage, reason = is_act_garbage(act)
            if is_garbage:
                has_garbage_acts = True
                garbage_acts.append((cid, year, r["title"][:50] if r["title"] else "", act, reason))
        if has_garbage_acts:
            high_counts["acts_cited has garbage entries"] += 1
            issues.append(("HIGH", "acts_cited has garbage entries", ""))

        # cases_cited bare refs
        cites = r["cases_cited"] or []
        bare_count = sum(1 for c in cites if is_bare_citation(c))
        if bare_count > 0:
            high_counts["cases_cited has bare refs"] += 1
            issues.append(("HIGH", "cases_cited has bare refs", f"{bare_count}/{len(cites)} bare"))
            bare_cite_cases.append(
                (cid, year, r["title"][:50] if r["title"] else "", bare_count, len(cites))
            )

        # cases_cited duplicates
        if cites:
            normalized = [c.strip().lower() for c in cites if c]
            if len(normalized) != len(set(normalized)):
                high_counts["cases_cited has duplicates"] += 1
                issues.append(("HIGH", "cases_cited has duplicates", ""))

        # cases_cited contains newlines
        if any("\n" in c for c in cites if c):
            high_counts["cases_cited has newlines"] += 1
            issues.append(("HIGH", "cases_cited has newlines", ""))

        # ratio_decidendi empty
        if not r["ratio_decidendi"] or (
            isinstance(r["ratio_decidendi"], str) and len(r["ratio_decidendi"].strip()) == 0
        ):
            high_counts["ratio_decidendi NULL/empty"] += 1
            issues.append(("HIGH", "ratio_decidendi NULL/empty", ""))
            year_stats[year]["ratio_populated"] += 0  # explicit
        else:
            year_stats[year]["ratio_populated"] += 1

        # outcome_summary empty
        if not r["outcome_summary"] or (
            isinstance(r["outcome_summary"], str) and len(r["outcome_summary"].strip()) == 0
        ):
            high_counts["outcome_summary NULL/empty"] += 1
            issues.append(("HIGH", "outcome_summary NULL/empty", ""))

        # keywords weak
        kw = r["keywords"] or []
        if not kw or len(kw) < 3:
            high_counts["keywords NULL or < 3 entries"] += 1
            issues.append(("HIGH", "keywords NULL or < 3 entries", f"count={len(kw)}"))

        # ── MEDIUM ───────────────────────────────────────────────────

        if not r["author_judge"]:
            medium_counts["author_judge NULL"] += 1
            issues.append(("MEDIUM", "author_judge NULL", ""))

        if not r["headnotes"] or (
            isinstance(r["headnotes"], str) and len(r["headnotes"].strip()) == 0
        ):
            medium_counts["headnotes NULL/empty"] += 1
            issues.append(("MEDIUM", "headnotes NULL/empty", ""))

        if r["is_reportable"] is None:
            medium_counts["is_reportable NULL"] += 1
            issues.append(("MEDIUM", "is_reportable NULL", ""))

        if check_bench_coram_mismatch(r["bench_type"], r["coram_size"]):
            medium_counts["bench_type/coram_size mismatch"] += 1
            issues.append(
                (
                    "MEDIUM",
                    "bench_type/coram_size mismatch",
                    f"bench={r['bench_type']}, coram={r['coram_size']}",
                )
            )

        if not r["petitioner"]:
            medium_counts["petitioner NULL"] += 1
            issues.append(("MEDIUM", "petitioner NULL", ""))

        if not r["respondent"]:
            medium_counts["respondent NULL"] += 1
            issues.append(("MEDIUM", "respondent NULL", ""))

        if not r["disposal_nature"]:
            medium_counts["disposal_nature NULL"] += 1
            issues.append(("MEDIUM", "disposal_nature NULL", ""))

        # ── Track ────────────────────────────────────────────────────

        if issues:
            case_issues[cid] = {
                "year": year,
                "title": r["title"][:50] if r["title"] else "(no title)",
                "issues": issues,
            }

        # Low confidence tracking
        if r["extraction_confidence"] is not None and r["extraction_confidence"] < 0.7:
            low_confidence_cases.append(
                (cid, year, r["title"][:60] if r["title"] else "", r["extraction_confidence"])
            )

        # Year stats
        if year:
            ys = year_stats[year]
            ys["count"] += 1
            if r["extraction_confidence"] is not None:
                ys["confidence_sum"] += r["extraction_confidence"]
                ys["confidence_count"] += 1
            if not has_garbage_acts:
                ys["clean_acts"] += 1
            if bare_count == 0:
                ys["clean_cites"] += 1

        # Date stats
        for sev, _name, _ in issues:
            date_stats[created_date][sev] += 1

    # ══════════════════════════════════════════════════════════════════
    # RESULTS
    # ══════════════════════════════════════════════════════════════════

    total = len(rows)
    cases_with_issues = len(case_issues)
    total - cases_with_issues

    # CRITICAL
    sum(critical_counts.values())
    for _issue, _count in critical_counts.most_common():
        pass

    # HIGH
    sum(high_counts.values())
    for _issue, _count in high_counts.most_common():
        pass

    # MEDIUM
    sum(medium_counts.values())
    for _issue, _count in medium_counts.most_common():
        pass

    # Breakdown by ingestion date
    for date in sorted(date_stats.keys()):
        date_stats[date]

    # TOP 20 worst cases
    worst = sorted(case_issues.items(), key=lambda x: len(x[1]["issues"]), reverse=True)[:20]
    for _i, (cid, info) in enumerate(worst, 1):
        len(info["issues"])
        sum(1 for s, _, _ in info["issues"] if s == "CRITICAL")
        sum(1 for s, _, _ in info["issues"] if s == "HIGH")
        sum(1 for s, _, _ in info["issues"] if s == "MEDIUM")
        for sev, _name, _detail in info["issues"]:
            pass

    # GARBAGE acts_cited samples
    # Sort by how bad they look (sentence fragments first)
    garbage_acts_sorted = sorted(
        garbage_acts, key=lambda x: len(x[3]) if x[3] else 0, reverse=True
    )[:10]
    for _i, (cid, yr, _title, _act_entry, reason) in enumerate(garbage_acts_sorted, 1):
        pass

    # Bare citation cases
    bare_cite_cases.sort(key=lambda x: x[3], reverse=True)
    for _i, (cid, yr, _title, _bare, _total_c) in enumerate(bare_cite_cases[:10], 1):
        pass

    # Low confidence cases
    low_confidence_cases.sort(key=lambda x: x[3])
    for cid, yr, _title, _conf in low_confidence_cases:
        pass

    # YEAR-BY-YEAR quality
    for yr in sorted(year_stats.keys()):
        ys = year_stats[yr]
        cnt = ys["count"]
        ys["confidence_sum"] / ys["confidence_count"] if ys["confidence_count"] > 0 else 0
        ys["ratio_populated"] * 100 / cnt if cnt > 0 else 0
        ys["clean_acts"] * 100 / cnt if cnt > 0 else 0
        ys["clean_cites"] * 100 / cnt if cnt > 0 else 0

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
