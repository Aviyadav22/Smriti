"""
Metadata quality audit focused on ingestion issues:
  - Section detection quality (HEADER bloat, mislabeled sections)
  - Editorial content contamination (SCR/SCC reporter headnotes)
  - Field length/quality validation (headnotes, ratio, description)
  - Mid-sentence header starts (over-stripped bleed)

Reads from PostgreSQL, outputs terminal report + CSV.
No writes — purely read-only.

Usage:
    cd backend
    python -m scripts.audit_metadata_quality [--csv audit_results.csv] [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from datetime import datetime

import psycopg2

# Import section detection from the chunker module
sys.path.insert(0, ".")
from app.core.ingestion.chunker import detect_judgment_sections

# ── Database ────────────────────────────────────────────────────────────

DATABASE_URL = (
    "postgresql://smriti:E9tGr2mSXTi1h36LwsmLKbRVooPmlZbYIY5FnYmuzWg="
    "@76.13.185.172:5432/smriti"
)

# ── Patterns for quality checks ─────────────────────────────────────────

# SCR lettered margin markers: standalone A-H on a line
_LETTERED_MARGIN_RE = re.compile(r"^\s*[A-H]\s*$", re.MULTILINE)

# SCR page citation pattern
_SCR_PAGE_RE = re.compile(
    r"\[?\d{4}\]?\s+\d+\s+S\.?\s*C\.?\s*R\.?\s+\d+", re.IGNORECASE
)

# Editorial markers in headnotes content
_EDITORIAL_MARKERS = [
    re.compile(r"result\s+of\s+the\s+case\s*:", re.IGNORECASE),
    re.compile(r"catchwords?\s*:", re.IGNORECASE),
    re.compile(r"cases?\s+referred\s*:", re.IGNORECASE),
    re.compile(r"legislation\s+cited\s*:", re.IGNORECASE),
    re.compile(r"headnotes?\s+prepared\s+by", re.IGNORECASE),
    re.compile(r"reporter'?s?\s+note", re.IGNORECASE),
]

# HEADNOTE/JUDGMENT markers for SCR format detection
_HEADNOTE_MARKER_RE = re.compile(
    r"^\s*(?:HEADNOTE|HEAD\s*NOTE|CATCHWORDS?)\s*$", re.MULTILINE | re.IGNORECASE
)
_JUDGMENT_MARKER_RE = re.compile(
    r"^\s*(?:JUDGMENT|J\s*U\s*D\s*G\s*M\s*E\s*N\s*T)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Testimony indicators (section mislabeling check)
_TESTIMONY_KEYWORDS = [
    "cross-examination", "cross examination", "PW-", "DW-",
    "witness stated", "witness deposed", "deposed that",
    "under examination", "further stated", "I did not",
    "It is wrong to suggest", "video-conferencing",
]


# ── Per-case audit result ───────────────────────────────────────────────

@dataclass
class CaseAuditResult:
    case_id: str = ""
    title: str = ""
    year: int | None = None
    confidence: float | None = None

    # Section detection checks
    header_section_chars: int = 0
    header_bloated: bool = False          # >5000 chars
    header_mid_sentence: bool = False     # starts lowercase
    num_sections_detected: int = 0

    # SCR format detection
    is_scr_format: bool = False           # has lettered margins + SCR citation
    has_headnote_before_judgment: bool = False

    # Editorial contamination
    headnotes_editorial_contaminated: bool = False  # reporter markers in headnotes
    headnotes_verbose: bool = False       # total >3000 chars
    headnotes_null: bool = False

    # Field quality
    ratio_verbose: bool = False           # >2000 chars
    ratio_null: bool = False
    description_mid_sentence: bool = False
    description_null: bool = False
    outcome_summary_null: bool = False

    # Section mislabeling
    arguments_has_testimony: bool = False
    mismatched_sections: int = 0

    # Key fields missing
    missing_critical_fields: list = field(default_factory=list)

    # Low confidence
    low_confidence: bool = False          # <0.6

    @property
    def issue_count(self) -> int:
        count = 0
        for f in dc_fields(self):
            if f.type == "bool":
                if getattr(self, f.name):
                    count += 1
        if self.missing_critical_fields:
            count += 1
        return count

    @property
    def severity(self) -> str:
        if self.header_mid_sentence or self.headnotes_editorial_contaminated or self.low_confidence:
            return "CRITICAL"
        if self.header_bloated or self.headnotes_verbose or self.ratio_verbose or self.arguments_has_testimony:
            return "HIGH"
        if self.issue_count > 0:
            return "MEDIUM"
        return "CLEAN"


# ── Audit logic ─────────────────────────────────────────────────────────

def audit_case(
    case_id: str,
    title: str | None,
    year: int | None,
    confidence: float | None,
    full_text: str | None,
    headnotes: str | None,
    ratio_decidendi: str | None,
    description: str | None,
    outcome_summary: str | None,
    court: str | None,
    judge: list | None,
) -> CaseAuditResult:
    """Run all quality checks on a single case."""
    r = CaseAuditResult(
        case_id=case_id,
        title=(title or "(no title)")[:80],
        year=year,
        confidence=confidence,
    )

    text = full_text or ""

    # ── 1. Section detection ────────────────────────────────────────
    if text:
        sections = detect_judgment_sections(text)
        r.num_sections_detected = len(sections)

        header_sections = [s for s in sections if s.type == "HEADER"]
        if header_sections:
            header_text = header_sections[0].text
            r.header_section_chars = len(header_text)
            r.header_bloated = r.header_section_chars > 5000

            # Mid-sentence start check
            stripped = header_text.lstrip()
            if stripped:
                first_char = stripped[0]
                r.header_mid_sentence = first_char.islower()

        # Section mislabeling: ARGUMENTS with testimony
        arg_sections = [s for s in sections if s.type == "ARGUMENTS"]
        for sec in arg_sections:
            sec_text_lower = sec.text[:3000].lower()
            testimony_hits = sum(
                1 for kw in _TESTIMONY_KEYWORDS if kw.lower() in sec_text_lower
            )
            if testimony_hits >= 2:
                r.arguments_has_testimony = True
                r.mismatched_sections += 1

    # ── 2. SCR format detection ─────────────────────────────────────
    scan_text = text[:20000]
    lettered_count = len(_LETTERED_MARGIN_RE.findall(scan_text))
    has_scr_citation = bool(_SCR_PAGE_RE.search(scan_text))
    r.is_scr_format = lettered_count >= 3 and has_scr_citation

    headnote_match = _HEADNOTE_MARKER_RE.search(scan_text)
    judgment_match = _JUDGMENT_MARKER_RE.search(scan_text)
    if headnote_match and judgment_match and headnote_match.start() < judgment_match.start():
        r.has_headnote_before_judgment = True

    # ── 3. Headnotes quality ────────────────────────────────────────
    if not headnotes or not headnotes.strip():
        r.headnotes_null = True
    else:
        # Try parsing as JSON
        total_len = 0
        hn_text = headnotes
        try:
            hn_list = json.loads(headnotes)
            if isinstance(hn_list, list):
                for item in hn_list:
                    if isinstance(item, dict):
                        prop = item.get("proposition", "")
                        total_len += len(prop)
                        hn_text = prop  # use last for marker check
                    elif isinstance(item, str):
                        total_len += len(item)
                        hn_text = item
        except (json.JSONDecodeError, TypeError):
            total_len = len(headnotes)

        r.headnotes_verbose = total_len > 3000

        # Check for editorial markers in headnotes content
        for marker_re in _EDITORIAL_MARKERS:
            if marker_re.search(headnotes):
                r.headnotes_editorial_contaminated = True
                break

        # Check for lettered margins in headnotes (SCR contamination)
        if lettered_count >= 2 and _LETTERED_MARGIN_RE.search(headnotes):
            r.headnotes_editorial_contaminated = True

    # ── 4. Ratio decidendi quality ──────────────────────────────────
    if not ratio_decidendi or not ratio_decidendi.strip():
        r.ratio_null = True
    else:
        r.ratio_verbose = len(ratio_decidendi) > 2000

    # ── 5. Description quality ──────────────────────────────────────
    if not description or not description.strip():
        r.description_null = True
    else:
        stripped_desc = description.lstrip()
        if stripped_desc:
            r.description_mid_sentence = stripped_desc[0].islower()

    # ── 6. Outcome summary ──────────────────────────────────────────
    if not outcome_summary or not outcome_summary.strip():
        r.outcome_summary_null = True

    # ── 7. Missing critical fields ──────────────────────────────────
    missing = []
    if not title or not title.strip():
        missing.append("title")
    if not court or not court.strip():
        missing.append("court")
    if not year:
        missing.append("year")
    if not judge:
        missing.append("judge")
    if not ratio_decidendi or not ratio_decidendi.strip():
        missing.append("ratio_decidendi")
    r.missing_critical_fields = missing

    # ── 8. Low confidence ───────────────────────────────────────────
    if confidence is not None and confidence < 0.6:
        r.low_confidence = True

    return r


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Audit ingested case metadata quality")
    parser.add_argument("--csv", default="audit_results.csv", help="Output CSV path")
    parser.add_argument("--limit", type=int, default=0, help="Limit cases to audit (0=all)")
    args = parser.parse_args()

    print("=" * 90)
    print("METADATA QUALITY AUDIT — Section Detection & Editorial Contamination")
    print("=" * 90)
    print(f"Run at: {datetime.now().isoformat()}")
    print()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Query all cases with full_text (needed for section detection)
    query = """
    SELECT id, title, year, extraction_confidence,
           full_text, headnotes, ratio_decidendi, description,
           outcome_summary, court, judge
    FROM cases
    ORDER BY year, title
    """
    if args.limit > 0:
        query += f" LIMIT {args.limit}"

    print("Querying database (includes full_text — may take a moment)...")
    cur.execute(query)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print(f"Fetched {len(rows)} cases.")
    print()

    # ── Run audit on each case ──────────────────────────────────────
    results: list[CaseAuditResult] = []
    severity_counts = Counter()
    flag_counts = Counter()

    for i, row in enumerate(rows):
        r = dict(zip(columns, row, strict=False))
        result = audit_case(
            case_id=str(r["id"]),
            title=r["title"],
            year=r["year"],
            confidence=r["extraction_confidence"],
            full_text=r["full_text"],
            headnotes=r["headnotes"],
            ratio_decidendi=r["ratio_decidendi"],
            description=r["description"],
            outcome_summary=r["outcome_summary"],
            court=r["court"],
            judge=r["judge"],
        )
        results.append(result)
        severity_counts[result.severity] += 1

        # Count individual flags
        if result.header_bloated:
            flag_counts["header_bloated (>5K chars)"] += 1
        if result.header_mid_sentence:
            flag_counts["header_mid_sentence"] += 1
        if result.is_scr_format:
            flag_counts["is_scr_format"] += 1
        if result.has_headnote_before_judgment:
            flag_counts["has_headnote_before_judgment"] += 1
        if result.headnotes_editorial_contaminated:
            flag_counts["headnotes_editorial_contaminated"] += 1
        if result.headnotes_verbose:
            flag_counts["headnotes_verbose (>3K chars)"] += 1
        if result.headnotes_null:
            flag_counts["headnotes_null"] += 1
        if result.ratio_verbose:
            flag_counts["ratio_verbose (>2K chars)"] += 1
        if result.ratio_null:
            flag_counts["ratio_null"] += 1
        if result.description_null:
            flag_counts["description_null"] += 1
        if result.description_mid_sentence:
            flag_counts["description_mid_sentence"] += 1
        if result.outcome_summary_null:
            flag_counts["outcome_summary_null"] += 1
        if result.arguments_has_testimony:
            flag_counts["arguments_has_testimony"] += 1
        if result.low_confidence:
            flag_counts["low_confidence (<0.6)"] += 1
        if result.missing_critical_fields:
            flag_counts["missing_critical_fields"] += 1

        # Progress indicator
        if (i + 1) % 200 == 0:
            print(f"  Audited {i + 1}/{len(rows)} cases...")

    print(f"  Audited {len(rows)}/{len(rows)} cases.")
    print()

    total = len(results)

    # ── Summary ─────────────────────────────────────────────────────
    print("=" * 90)
    print("SEVERITY SUMMARY")
    print("=" * 90)
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "CLEAN"]:
        cnt = severity_counts.get(sev, 0)
        pct = cnt * 100 / total if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {sev:<10} {cnt:>6} ({pct:>5.1f}%)  {bar}")
    print()

    # ── Flag breakdown ──────────────────────────────────────────────
    print("=" * 90)
    print("FLAG BREAKDOWN (individual checks)")
    print("=" * 90)
    for flag, cnt in flag_counts.most_common():
        pct = cnt * 100 / total if total else 0
        print(f"  {cnt:>6} ({pct:>5.1f}%)  {flag}")
    print()

    # ── SCR format analysis ─────────────────────────────────────────
    scr_cases = [r for r in results if r.is_scr_format]
    non_scr_cases = [r for r in results if not r.is_scr_format]
    print("=" * 90)
    print("SCR FORMAT ANALYSIS")
    print("=" * 90)
    print(f"  SCR-format cases:     {len(scr_cases)} ({len(scr_cases)*100/total:.1f}%)")
    print(f"  Non-SCR cases:        {len(non_scr_cases)} ({len(non_scr_cases)*100/total:.1f}%)")
    if scr_cases:
        scr_bloated = sum(1 for r in scr_cases if r.header_bloated)
        scr_contaminated = sum(1 for r in scr_cases if r.headnotes_editorial_contaminated)
        print(f"  SCR with bloated HEADER:              {scr_bloated} ({scr_bloated*100/len(scr_cases):.1f}%)")
        print(f"  SCR with editorial in headnotes:      {scr_contaminated} ({scr_contaminated*100/len(scr_cases):.1f}%)")
        avg_header = sum(r.header_section_chars for r in scr_cases) / len(scr_cases)
        print(f"  SCR avg HEADER section size:          {avg_header:,.0f} chars")
    if non_scr_cases:
        non_scr_bloated = sum(1 for r in non_scr_cases if r.header_bloated)
        avg_header_nonscr = sum(r.header_section_chars for r in non_scr_cases) / len(non_scr_cases)
        print(f"  Non-SCR with bloated HEADER:          {non_scr_bloated} ({non_scr_bloated*100/len(non_scr_cases):.1f}%)")
        print(f"  Non-SCR avg HEADER section size:      {avg_header_nonscr:,.0f} chars")
    print()

    # ── HEADER section size distribution ────────────────────────────
    print("=" * 90)
    print("HEADER SECTION SIZE DISTRIBUTION")
    print("=" * 90)
    buckets = {"<1K": 0, "1-3K": 0, "3-5K": 0, "5-10K": 0, "10-20K": 0, ">20K": 0}
    for r in results:
        chars = r.header_section_chars
        if chars < 1000:
            buckets["<1K"] += 1
        elif chars < 3000:
            buckets["1-3K"] += 1
        elif chars < 5000:
            buckets["3-5K"] += 1
        elif chars < 10000:
            buckets["5-10K"] += 1
        elif chars < 20000:
            buckets["10-20K"] += 1
        else:
            buckets[">20K"] += 1
    for bucket, cnt in buckets.items():
        pct = cnt * 100 / total if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {bucket:<8} {cnt:>6} ({pct:>5.1f}%)  {bar}")
    print()

    # ── Top 15 worst cases ──────────────────────────────────────────
    print("=" * 90)
    print("TOP 15 WORST CASES (most issues)")
    print("=" * 90)
    worst = sorted(results, key=lambda r: r.issue_count, reverse=True)[:15]
    for i, r in enumerate(worst, 1):
        flags = []
        if r.header_bloated:
            flags.append(f"HEADER={r.header_section_chars:,}chars")
        if r.header_mid_sentence:
            flags.append("mid-sentence-start")
        if r.headnotes_editorial_contaminated:
            flags.append("editorial-in-headnotes")
        if r.headnotes_verbose:
            flags.append("headnotes-verbose")
        if r.ratio_verbose:
            flags.append("ratio-verbose")
        if r.arguments_has_testimony:
            flags.append("testimony-in-arguments")
        if r.is_scr_format:
            flags.append("SCR-format")
        if r.low_confidence:
            flags.append(f"conf={r.confidence:.2f}")
        if r.missing_critical_fields:
            flags.append(f"missing:[{','.join(r.missing_critical_fields)}]")

        print(f"\n  #{i}  [{r.severity}]  Year={r.year}  Issues={r.issue_count}")
        print(f"       {r.title}")
        print(f"       {', '.join(flags)}")

    # ── Cases with HEADNOTE before JUDGMENT (SCR editorial block) ───
    hn_before_j = [r for r in results if r.has_headnote_before_judgment]
    print()
    print("=" * 90)
    print(f"CASES WITH HEADNOTE BEFORE JUDGMENT MARKER ({len(hn_before_j)} total)")
    print("=" * 90)
    for r in hn_before_j[:20]:
        status = "CONTAMINATED" if r.headnotes_editorial_contaminated else "ok"
        header_note = f"HEADER={r.header_section_chars:,}ch" if r.header_bloated else ""
        print(f"  [{r.year}] headnotes={status:<13} {header_note:<20} {r.title}")
    if len(hn_before_j) > 20:
        print(f"  ... and {len(hn_before_j) - 20} more")
    print()

    # ── CSV export ──────────────────────────────────────────────────
    csv_path = args.csv
    csv_fields = [
        "case_id", "title", "year", "severity", "issue_count", "confidence",
        "header_section_chars", "header_bloated", "header_mid_sentence",
        "is_scr_format", "has_headnote_before_judgment",
        "headnotes_editorial_contaminated", "headnotes_verbose", "headnotes_null",
        "ratio_verbose", "ratio_null",
        "description_null", "description_mid_sentence",
        "outcome_summary_null",
        "arguments_has_testimony", "mismatched_sections",
        "low_confidence", "missing_critical_fields", "num_sections_detected",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            row = {
                "case_id": r.case_id,
                "title": r.title,
                "year": r.year,
                "severity": r.severity,
                "issue_count": r.issue_count,
                "confidence": f"{r.confidence:.3f}" if r.confidence is not None else "",
                "header_section_chars": r.header_section_chars,
                "header_bloated": r.header_bloated,
                "header_mid_sentence": r.header_mid_sentence,
                "is_scr_format": r.is_scr_format,
                "has_headnote_before_judgment": r.has_headnote_before_judgment,
                "headnotes_editorial_contaminated": r.headnotes_editorial_contaminated,
                "headnotes_verbose": r.headnotes_verbose,
                "headnotes_null": r.headnotes_null,
                "ratio_verbose": r.ratio_verbose,
                "ratio_null": r.ratio_null,
                "description_null": r.description_null,
                "description_mid_sentence": r.description_mid_sentence,
                "outcome_summary_null": r.outcome_summary_null,
                "arguments_has_testimony": r.arguments_has_testimony,
                "mismatched_sections": r.mismatched_sections,
                "low_confidence": r.low_confidence,
                "missing_critical_fields": ",".join(r.missing_critical_fields),
                "num_sections_detected": r.num_sections_detected,
            }
            writer.writerow(row)

    print(f"CSV exported to: {csv_path}")
    print()
    print("=" * 90)
    print("AUDIT COMPLETE")
    print("=" * 90)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
