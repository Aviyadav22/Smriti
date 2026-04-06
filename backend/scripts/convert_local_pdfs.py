#!/usr/bin/env python3
"""Convert locally-downloaded statute PDFs to JSON for ingestion.

Place PDFs in backend/data/statute_pdfs/ with the filenames shown by --list.
The script extracts sections from each PDF and saves as JSON in data/statutes/.

Usage:
    python scripts/convert_local_pdfs.py --list          # show all expected PDFs
    python scripts/convert_local_pdfs.py                  # convert all found PDFs
    python scripts/convert_local_pdfs.py --only la pca    # convert specific acts
    python scripts/convert_local_pdfs.py --tier 1         # convert only tier 1 (missing)
    python scripts/convert_local_pdfs.py --tier 0         # convert only tier 0 (re-extract)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.download_and_convert_statutes import (
    PDF_ACT_CONFIGS,
    extract_sections_from_pdf,
    save_json,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PDF_DIR = Path(__file__).resolve().parent.parent / "data" / "statute_pdfs"

# ── Complete mapping: PDF filename stem → config key, organized by tier ──

# TIER 0: Re-extract (have data but sections missing due to extraction bugs)
TIER_0_REEXTRACT = {
    "bns": "BNS",           # 51/358 sections missing (14%)
    "bnss": "BNSS",         # 18/531 sections missing (3%)
    "bsa": "BSA",           # 18/170 sections missing (11%)
}

# TIER 1: Completely missing from DB — high citation count
TIER_1_MISSING = {
    "la": "LA",             # Limitation Act, 1963 — 976 citations
    "laa": "LAA",           # Land Acquisition Act, 1894 — 295 citations
    "larr": "LARR",         # Right to Fair Compensation Act, 2013 — 184 citations
    "pca": "PCA",           # Prevention of Corruption Act, 1988 — 184 citations
    "cpa2019": "CPA2019",   # Consumer Protection Act, 2019 — 142 citations
    "mva": "MVA",           # Motor Vehicles Act, 1988 — 141 citations
    "electricity": "ELECTRICITY",  # Electricity Act, 2003 — 101 citations
    "sra": "SRA",           # Specific Relief Act, 1963 — 85 citations
    "cpa1986": "CPA1986",   # Consumer Protection Act, 1986 — 79 citations
    "gca": "GCA",           # General Clauses Act, 1897 — 72 citations
    "arms": "ARMS",         # Arms Act, 1959 — 69 citations
    "pocso": "POCSO",       # POCSO Act, 2012 — 54 citations
    "dpa": "DPA",           # Dowry Prohibition Act, 1961 — 42 citations
    "rpa": "RPA",           # Representation of People Act, 1951 — 30 citations
    "scst": "SCST",         # SC/ST Atrocities Act, 1989 — 28 citations
    "rti": "RTI",           # Right to Information Act, 2005 — 24 citations
    "ngt": "NGT",           # National Green Tribunal Act, 2010 — 24 citations
    "societies": "SOCIETIES",     # Societies Registration Act, 1860 — 22 citations
    "succession": "SUCCESSION",   # Indian Succession Act, 1925 — 21 citations
    "commercial_courts": "COMMERCIAL_COURTS",  # Commercial Courts Act, 2015 — 19 citations
    "drugs": "DRUGS",       # Drugs and Cosmetics Act, 1940 — 19 citations
    "water": "WATER",       # Water (Prevention) Act, 1974 — 19 citations
    "cst": "CST",           # Central Sales Tax Act, 1956 — 18 citations
    "disability": "DISABILITY",   # Rights of Persons with Disabilities Act, 2016 — 17 citations
    "forest": "FOREST",     # Indian Forest Act, 1927 — 16 citations
    "advocates": "ADVOCATES",     # Advocates Act, 1961 — 16 citations
    "air": "AIR",           # Air (Prevention) Act, 1981 — 14 citations
    "army": "ARMY",         # Army Act, 1950 — 15 citations
}

# TIER 2: In DB but severely incomplete (PDF extraction missed most sections)
TIER_2_INCOMPLETE = {
    "hsa": "HSA",           # Hindu Succession Act — 4/30 sections (87% missing)
    "epa": "EPA",           # Environment Protection Act — 5/26 sections (81% missing)
    "factories": "FA1948",  # Factories Act — 22/120 sections (82% missing)
    "cgst": "CGST",         # CGST Act — 20/164 sections (88% missing)
    "sma": "SMA",           # Special Marriage Act — 12/50 sections (76% missing)
    "fca": "FCA",           # Forest Conservation Act — 1/5 sections (80% missing)
}

# Combined mapping
ALL_ACTS = {**TIER_0_REEXTRACT, **TIER_1_MISSING, **TIER_2_INCOMPLETE}

TIER_MAP = {
    0: TIER_0_REEXTRACT,
    1: TIER_1_MISSING,
    2: TIER_2_INCOMPLETE,
}


def main():
    parser = argparse.ArgumentParser(description="Convert local statute PDFs to JSON")
    parser.add_argument("--only", nargs="+", help="Only convert these acts (by filename stem)")
    parser.add_argument("--tier", type=int, choices=[0, 1, 2], help="Only convert a specific tier")
    parser.add_argument("--list", action="store_true", help="List all expected PDF files")
    args = parser.parse_args()

    if args.list:
        for tier_num, tier_name, tier_acts in [
            (0, "RE-EXTRACT (have data but missing sections)", TIER_0_REEXTRACT),
            (1, "MISSING (not in DB at all)", TIER_1_MISSING),
            (2, "INCOMPLETE (in DB but most sections missing)", TIER_2_INCOMPLETE),
        ]:
            print(f"\n{'='*80}")
            print(f"TIER {tier_num}: {tier_name}")
            print(f"{'='*80}")
            for stem, config_key in tier_acts.items():
                config = PDF_ACT_CONFIGS.get(config_key, {})
                act_name = config.get("act_name", "?")
                act_year = config.get("act_year", "?")
                print(f"  {stem}.pdf{' '*(25-len(stem))} {act_name}, {act_year}")
        print(f"\nTotal: {len(ALL_ACTS)} PDFs expected in backend/data/statute_pdfs/")
        return

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Select targets
    if args.only:
        targets = {k: v for k, v in ALL_ACTS.items() if k in args.only}
    elif args.tier is not None:
        targets = TIER_MAP[args.tier]
    else:
        targets = ALL_ACTS

    total_sections = 0
    converted = 0
    skipped = 0
    failed = 0

    for stem, config_key in targets.items():
        pdf_path = PDF_DIR / f"{stem}.pdf"
        if not pdf_path.exists():
            skipped += 1
            continue

        config = PDF_ACT_CONFIGS.get(config_key)
        if not config:
            logger.error("No config for %s (key=%s)", stem, config_key)
            failed += 1
            continue

        logger.info("Converting %s -> %s", pdf_path.name, config["act_name"])
        pdf_bytes = pdf_path.read_bytes()
        sections = extract_sections_from_pdf(pdf_bytes, config)

        if not sections:
            logger.error("No sections extracted from %s!", pdf_path.name)
            failed += 1
            continue

        out_filename = f"{stem}.json"
        save_json(sections, out_filename)
        total_sections += len(sections)
        converted += 1
        logger.info("  -> %d sections saved to %s", len(sections), out_filename)

    print()
    print(f"Results: {converted} converted, {skipped} skipped (PDF not found), {failed} failed")
    print(f"Total: {total_sections} sections extracted")
    if skipped > 0:
        missing = [s for s in targets if not (PDF_DIR / f"{s}.pdf").exists()]
        print(f"\nMissing PDFs ({skipped}):")
        for stem in missing:
            config = PDF_ACT_CONFIGS.get(targets[stem], {})
            print(f"  {stem}.pdf  ->  {config.get('act_name', '?')}")
    if converted > 0:
        print(f"\nNext step:")
        print(f"  cd backend && python scripts/ingest_statutes.py --source data/statutes/ --all")


if __name__ == "__main__":
    main()
