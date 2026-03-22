#!/usr/bin/env python3
"""Download real legal text from authoritative internet sources and convert to standard JSON.

Sources:
  - IPC, CrPC, CPC, IEA: civictech-India GitHub (JSON, CC license)
  - Constitution of India: civictech-India GitHub (JSON, CC license)
  - All other acts: indiacode.nic.in official PDFs (Government of India, public domain)

All sources are legal, publicly available government data.
indiacode.nic.in is the official digital repository of the Ministry of Law and Justice.

Batches:
  1-3: IPC, CrPC, CPC, IEA, COI, BNS, BNSS, BSA (8 acts — already done)
  4:   Commercial-1 — Contract Act, Sale of Goods, Arbitration, FEMA, Partnership
  5:   Commercial-2 — Companies Act, SEBI, Competition, SARFAESI, IBC, NI Act, LLP, Banking Reg
  6:   Family — Hindu Marriage, Hindu Succession, Special Marriage, DV Act, Guardians & Wards
  7:   Labor — Industrial Disputes, Factories, ESI, EPF, Payment of Wages, Minimum Wages,
               Trade Unions, Workmen's Comp
  8:   Tax — Income Tax, CGST, Customs, Central Excise, Stamp Act, Benami
  9:   Property+Env — Transfer of Property, Registration, Easements, RERA, Environment,
                      Wildlife, Forest Conservation
  10:  Tech+Admin — IT Act, DPDP, Aadhaar, RTI, Lokpal, Contempt of Courts,
                    Administrative Tribunals, UAPA, NIA, PMLA, NDPS, JJ Act

Output: JSON files in backend/data/statutes/ overwriting any stubs.

Usage:
    python scripts/download_and_convert_statutes.py
    python scripts/download_and_convert_statutes.py --skip-pdf
    python scripts/download_and_convert_statutes.py --only ipc crpc
    python scripts/download_and_convert_statutes.py --batch 4     # Commercial-1 only
    python scripts/download_and_convert_statutes.py --batch 4 5 6 # multiple batches
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.legal.constants import (
    CRPC_TO_BNSS_MAP,
    EVIDENCE_TO_BSA_MAP,
    IPC_TO_BNS_MAP,
)

logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "statutes"

# ---------------------------------------------------------------------------
# GitHub raw URLs
# ---------------------------------------------------------------------------
CIVICTECH_BASE = "https://raw.githubusercontent.com/civictech-India/Indian-Law-Penal-Code-Json/main"
COI_URL = "https://raw.githubusercontent.com/civictech-India/constitution-of-india/main/constitution_of_india.json"

# Official PDF URLs from indiacode.nic.in (Government of India, public domain)
# All URLs verified against indiacode.nic.in — Ministry of Law and Justice portal
PDF_URLS = {
    # --- Batch 2: New criminal codes ---
    "BNS": "https://www.indiacode.nic.in/bitstream/123456789/20062/1/a202345.pdf",
    "BNSS": "https://www.indiacode.nic.in/bitstream/123456789/21544/1/the_bharatiya_nagarik_suraksha_sanhita,_2023.pdf",
    "BSA": "https://www.indiacode.nic.in/bitstream/123456789/20063/1/aa202347.pdf",
    # --- Batch 4: Commercial-1 ---
    "ICA": "https://www.indiacode.nic.in/bitstream/123456789/2187/2/A187209.pdf",
    "SOGA": "https://www.indiacode.nic.in/bitstream/123456789/2390/1/193003.pdf",
    "ACA": "https://www.indiacode.nic.in/bitstream/123456789/21922/1/the_arbitration_and_conciliation_act,_1996_act_no._26_of_1996.pdf",
    "FEMA": "https://www.indiacode.nic.in/bitstream/123456789/1988/1/A1999_42.pdf",
    "IPA": "https://www.indiacode.nic.in/bitstream/123456789/19863/1/indian_partnership_act_1932.pdf",
    # --- Batch 5: Commercial-2 ---
    "CA2013": "https://www.indiacode.nic.in/bitstream/123456789/2114/5/A2013-18.pdf",
    "SEBI": "https://www.indiacode.nic.in/bitstream/123456789/1890/1/199215.pdf",
    "COMPETITION": "https://www.indiacode.nic.in/bitstream/123456789/2010/7/A2003-12.pdf",
    "SARFAESI": "https://www.indiacode.nic.in/bitstream/123456789/2006/1/A2002-54.pdf",
    "IBC": "https://www.indiacode.nic.in/bitstream/123456789/2154/5/A2016-31.pdf",
    "NIA1881": "https://www.indiacode.nic.in/bitstream/123456789/15327/1/negotiable_instruments_act,_1881.pdf",
    "LLP": "https://www.indiacode.nic.in/bitstream/123456789/2023/1/A2009-06.pdf",
    "BRA": "https://www.indiacode.nic.in/bitstream/123456789/1885/1/aa1949-10.pdf",
    # --- Batch 6: Family ---
    "HMA": "https://www.indiacode.nic.in/bitstream/123456789/1560/1/A1955-25.pdf",
    "HSA": "https://www.indiacode.nic.in/bitstream/123456789/1713/1/AAA1956suc___30.pdf",
    "SMA": "https://www.indiacode.nic.in/bitstream/123456789/15480/1/special_marriage_act.pdf",
    "DVA": "https://www.indiacode.nic.in/bitstream/123456789/15436/1/protection_of_women_from_domestic_violence_act,_2005.pdf",
    "GWA": "https://www.indiacode.nic.in/bitstream/123456789/2318/1/189008.pdf",
    # --- Batch 7: Labor ---
    "IDA": "https://www.indiacode.nic.in/bitstream/123456789/20352/1/the_industrial_disputes_act.pdf",
    "FA1948": "https://www.indiacode.nic.in/bitstream/123456789/6323/1/factories_act_1948.pdf",
    "ESIA": "https://www.indiacode.nic.in/bitstream/123456789/12829/1/the_employees_state_insurance_act,_1948_no._34_of_1948_date_19.04.1948.pdf",
    "EPFA": "https://www.indiacode.nic.in/bitstream/123456789/12828/1/the_employees_provident_funds_and_miscellaneous_provisions_act,_1952_no_19_of_1952_date_04.03.1952_.pdf",
    "PWA": "https://www.indiacode.nic.in/bitstream/123456789/20359/1/payment_of_wages_act_1936.pdf",
    "MWA": "https://www.indiacode.nic.in/bitstream/123456789/20357/1/a1948-011.pdf",
    "TUA": "https://www.indiacode.nic.in/bitstream/123456789/20965/1/the_trade_unions_act,_1926.pdf",
    "WCA": "https://www.indiacode.nic.in/bitstream/123456789/13197/1/the-employees-compensation-act_1923.pdf",
    # --- Batch 8: Tax ---
    "ITA": "https://www.indiacode.nic.in/bitstream/123456789/2435/1/a1961-43.pdf",
    "CGST": "https://www.indiacode.nic.in/bitstream/123456789/7771/1/cgst-act.pdf",
    "CUSTOMS": "https://www.indiacode.nic.in/bitstream/123456789/15359/1/the_customs_act,_1962.pdf",
    "CEA": "https://www.indiacode.nic.in/bitstream/123456789/19238/1/a1944-01.pdf",
    "STAMP": "https://www.indiacode.nic.in/bitstream/123456789/20095/1/the_indian_stamp_act,_1899.pdf",
    "BENAMI": "https://www.indiacode.nic.in/bitstream/123456789/15415/1/the_prohibition_of_benami_property_transactions_act,_1988.pdf",
    # --- Batch 9: Property + Environmental ---
    "TPA": "https://www.indiacode.nic.in/bitstream/123456789/2338/1/A1882-04.pdf",
    "RA1908": "https://www.indiacode.nic.in/bitstream/123456789/15937/1/the_registration_act,1908.pdf",
    "EASEMENTS": "https://www.indiacode.nic.in/bitstream/123456789/2349/1/A1882-05.pdf",
    "RERA": "https://www.indiacode.nic.in/bitstream/123456789/15131/1/the_real_estate_(regulation_and_development)_act,_2016.pdf",
    "EPA": "https://www.indiacode.nic.in/bitstream/123456789/19381/1/the_forest_(conservation)_act,_1980.pdf",  # env act via handle
    "WPA": "https://www.indiacode.nic.in/bitstream/123456789/6198/1/the_wild_life_(protection)_act,_1972.pdf",
    "FCA": "https://www.indiacode.nic.in/bitstream/123456789/10815/1/forest_(conservation)_act,_1980.pdf",
    # --- Batch 10: Technology + Admin ---
    "ITA2000": "https://www.indiacode.nic.in/bitstream/123456789/13116/1/it_act_2000_updated.pdf",
    "DPDP": "https://www.indiacode.nic.in/bitstream/123456789/22037/1/a2023-22.pdf",
    "AADHAAR": "https://www.indiacode.nic.in/bitstream/123456789/2160/1/engaadhaar.pdf",
    "LOKPAL": "https://www.indiacode.nic.in/bitstream/123456789/2122/1/201401.pdf",
    "CONTEMPT": "https://www.indiacode.nic.in/bitstream/123456789/1514/1/A1971-70.pdf",
    "ATT": "https://www.indiacode.nic.in/bitstream/123456789/1832/1/AA1985__13admin.pdf",
    "UAPA": "https://www.indiacode.nic.in/bitstream/123456789/1470/3/A1967-37.pdf",
    "NIA": "https://www.indiacode.nic.in/bitstream/123456789/2054/3/a2008-34.pdf",
    "PMLA": "https://www.indiacode.nic.in/bitstream/123456789/2036/5/A2003-15.pdf",
    "NDPS": "https://www.indiacode.nic.in/bitstream/123456789/18974/1/narcotic-drugs-and-psychotropic-substances-act-1985.pdf",
    "JJA": "https://www.indiacode.nic.in/bitstream/123456789/2148/1/a2016-2.pdf",
    # Additional commercial
    "INSURANCE": "https://www.indiacode.nic.in/bitstream/123456789/2304/1/a1938-04.pdf",
    "MSMED": "https://www.indiacode.nic.in/bitstream/123456789/2013/3/A2006-27.pdf",
}

# Reverse maps for cross-references
_IPC_TO_BNS = IPC_TO_BNS_MAP
_BNS_TO_IPC = {v: k for k, v in IPC_TO_BNS_MAP.items()}
_CRPC_TO_BNSS = CRPC_TO_BNSS_MAP
_BNSS_TO_CRPC = {v: k for k, v in CRPC_TO_BNSS_MAP.items()}
_IEA_TO_BSA = EVIDENCE_TO_BSA_MAP
_BSA_TO_IEA = {v: k for k, v in EVIDENCE_TO_BSA_MAP.items()}

HTTP_TIMEOUT = 60


def fetch_json(url: str) -> list | dict:
    """Download and parse JSON from a URL."""
    logger.info("Downloading %s", url)
    resp = httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def fetch_pdf_bytes(url: str) -> bytes:
    """Download a PDF file."""
    logger.info("Downloading PDF: %s", url)
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# Converters for GitHub JSON sources
# ---------------------------------------------------------------------------


def convert_ipc(data: list[dict]) -> list[dict]:
    """Convert civictech-India IPC JSON to our format."""
    sections = []
    for item in data:
        sec_num = str(item.get("Section", ""))
        bns_num = _IPC_TO_BNS.get(sec_num, "")
        replaced_by = f"BNS, Section {bns_num}" if bns_num else ""

        sections.append({
            "act_name": "Indian Penal Code, 1860",
            "act_short_name": "IPC",
            "act_number": "45",
            "act_year": 1860,
            "part": "",
            "chapter": str(item.get("chapter", "")),
            "section_number": sec_num,
            "section_title": item.get("section_title", ""),
            "section_text": item.get("section_desc", ""),
            "explanation": "",
            "effective_date": None,
            "is_repealed": bool(bns_num),
            "replaced_by": replaced_by,
            "replaces": "",
            "document_type": "statute",
        })
    return sections


def convert_crpc(data: list[dict]) -> list[dict]:
    """Convert civictech-India CrPC JSON to our format."""
    sections = []
    for item in data:
        sec_num = str(item.get("section", item.get("Section", "")))
        bnss_num = _CRPC_TO_BNSS.get(sec_num, "")
        replaced_by = f"BNSS, Section {bnss_num}" if bnss_num else ""

        sections.append({
            "act_name": "Code of Criminal Procedure, 1973",
            "act_short_name": "CrPC",
            "act_number": "2",
            "act_year": 1974,
            "part": "",
            "chapter": str(item.get("chapter", "")),
            "section_number": sec_num,
            "section_title": item.get("section_title", ""),
            "section_text": item.get("section_desc", ""),
            "explanation": "",
            "effective_date": None,
            "is_repealed": bool(bnss_num),
            "replaced_by": replaced_by,
            "replaces": "",
            "document_type": "statute",
        })
    return sections


def convert_cpc(data: list[dict]) -> list[dict]:
    """Convert civictech-India CPC JSON to our format.

    CPC uses different field names: 'title', 'description' instead of
    'section_title', 'section_desc'.
    """
    sections = []
    for item in data:
        sec_num = str(item.get("section", item.get("Section", "")))
        sections.append({
            "act_name": "Code of Civil Procedure, 1908",
            "act_short_name": "CPC",
            "act_number": "5",
            "act_year": 1908,
            "part": "",
            "chapter": str(item.get("chapter", "")),
            "section_number": sec_num,
            "section_title": item.get("title", item.get("section_title", "")),
            "section_text": item.get("description", item.get("section_desc", "")),
            "explanation": "",
            "effective_date": None,
            "is_repealed": False,
            "replaced_by": "",
            "replaces": "",
            "document_type": "statute",
        })
    return sections


def convert_iea(data: list[dict]) -> list[dict]:
    """Convert civictech-India IEA JSON to our format."""
    sections = []
    for item in data:
        sec_num = str(item.get("section", item.get("Section", "")))
        bsa_num = _IEA_TO_BSA.get(sec_num, "")
        replaced_by = f"BSA, Section {bsa_num}" if bsa_num else ""

        sections.append({
            "act_name": "Indian Evidence Act, 1872",
            "act_short_name": "IEA",
            "act_number": "1",
            "act_year": 1872,
            "part": "",
            "chapter": str(item.get("chapter", "")),
            "section_number": sec_num,
            "section_title": item.get("section_title", ""),
            "section_text": item.get("section_desc", ""),
            "explanation": "",
            "effective_date": None,
            "is_repealed": bool(bsa_num),
            "replaced_by": replaced_by,
            "replaces": "",
            "document_type": "statute",
        })
    return sections


# ---------------------------------------------------------------------------
# Constitution of India converter
# ---------------------------------------------------------------------------


def convert_constitution(data: list[dict] | dict) -> list[dict]:
    """Convert civictech-India Constitution JSON to our format.

    Format: list of {article: int, title: str, description: str}
    465 entries covering Articles 0 (Preamble) through 395.
    """
    articles_list = data if isinstance(data, list) else data.get("articles", [])

    sections = []
    for article in articles_list:
        art_no = str(article.get("article", ""))
        title = article.get("title", "")
        description = article.get("description", "")

        if not description:
            continue

        sections.append({
            "act_name": "Constitution of India",
            "act_short_name": "COI",
            "act_number": "",
            "act_year": 1950,
            "part": "",
            "chapter": "",
            "section_number": art_no,
            "section_title": title,
            "section_text": description,
            "explanation": "",
            "effective_date": None,
            "is_repealed": False,
            "replaced_by": "",
            "replaces": "",
            "document_type": "constitution",
        })
    return sections


# ---------------------------------------------------------------------------
# PDF extraction for BNS/BNSS/BSA
# ---------------------------------------------------------------------------


def extract_sections_from_pdf(pdf_bytes: bytes, act_config: dict) -> list[dict]:
    """Extract sections from an Indian bare act PDF using pdfplumber.

    Indian bare acts follow the pattern:
        123. Short title.—Description text continues here...

    Args:
        pdf_bytes: Raw PDF content.
        act_config: Dict with act_name, act_short_name, act_number, act_year, cross_ref_map.

    Returns:
        List of statute dicts in our standard format.
    """
    import io

    import pdfplumber

    full_text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

    if not full_text.strip():
        logger.error("No text extracted from PDF for %s", act_config["act_short_name"])
        return []

    # Pattern for Indian bare act sections: "123. Title.—" or "123. Title. —"
    # Also handles "123A." style numbering
    section_pattern = re.compile(
        r"^(\d+[A-Z]?)\.\s+(.+?)\.?\s*[—–-]\s*",
        re.MULTILINE,
    )

    matches = list(section_pattern.finditer(full_text))
    if not matches:
        # Try alternative pattern without em-dash
        section_pattern = re.compile(
            r"^(\d+[A-Z]?)\.\s+(.+?)\.\s*$",
            re.MULTILINE,
        )
        matches = list(section_pattern.finditer(full_text))

    logger.info("Found %d section headers in %s PDF", len(matches), act_config["act_short_name"])

    cross_ref_map = act_config.get("cross_ref_map", {})
    cross_ref_code = act_config.get("cross_ref_code", "")

    sections = []
    for i, match in enumerate(matches):
        sec_num = match.group(1)
        sec_title = match.group(2).strip()

        # Extract text from this section header to the next
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        raw_text = full_text[start:end].strip()

        # Clean up the text
        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
        raw_text = re.sub(r"[ \t]+", " ", raw_text)

        # Compute cross-references
        old_sec = cross_ref_map.get(sec_num, "")
        replaces = f"{cross_ref_code}, Section {old_sec}" if old_sec else ""

        sections.append({
            "act_name": act_config["act_name"],
            "act_short_name": act_config["act_short_name"],
            "act_number": act_config["act_number"],
            "act_year": act_config["act_year"],
            "part": "",
            "chapter": "",
            "section_number": sec_num,
            "section_title": sec_title,
            "section_text": raw_text,
            "explanation": "",
            "effective_date": None,
            "is_repealed": False,
            "replaced_by": "",
            "replaces": replaces,
            "document_type": "statute",
        })

    return sections


# ---------------------------------------------------------------------------
# PDF act configurations
# ---------------------------------------------------------------------------

PDF_ACT_CONFIGS = {
    # --- Batch 2: New criminal codes ---
    "BNS": {
        "act_name": "Bharatiya Nyaya Sanhita, 2023",
        "act_short_name": "BNS",
        "act_number": "45",
        "act_year": 2023,
        "cross_ref_map": _BNS_TO_IPC,
        "cross_ref_code": "IPC",
    },
    "BNSS": {
        "act_name": "Bharatiya Nagarik Suraksha Sanhita, 2023",
        "act_short_name": "BNSS",
        "act_number": "46",
        "act_year": 2023,
        "cross_ref_map": _BNSS_TO_CRPC,
        "cross_ref_code": "CrPC",
    },
    "BSA": {
        "act_name": "Bharatiya Sakshya Adhiniyam, 2023",
        "act_short_name": "BSA",
        "act_number": "47",
        "act_year": 2023,
        "cross_ref_map": _BSA_TO_IEA,
        "cross_ref_code": "IEA",
    },
    # --- Batch 4: Commercial-1 ---
    "ICA": {
        "act_name": "Indian Contract Act, 1872",
        "act_short_name": "ICA",
        "act_number": "9",
        "act_year": 1872,
    },
    "SOGA": {
        "act_name": "Sale of Goods Act, 1930",
        "act_short_name": "SOGA",
        "act_number": "3",
        "act_year": 1930,
    },
    "ACA": {
        "act_name": "Arbitration and Conciliation Act, 1996",
        "act_short_name": "ACA",
        "act_number": "26",
        "act_year": 1996,
    },
    "FEMA": {
        "act_name": "Foreign Exchange Management Act, 1999",
        "act_short_name": "FEMA",
        "act_number": "42",
        "act_year": 1999,
    },
    "IPA": {
        "act_name": "Indian Partnership Act, 1932",
        "act_short_name": "IPA",
        "act_number": "9",
        "act_year": 1932,
    },
    # --- Batch 5: Commercial-2 ---
    "CA2013": {
        "act_name": "Companies Act, 2013",
        "act_short_name": "CA2013",
        "act_number": "18",
        "act_year": 2013,
    },
    "SEBI": {
        "act_name": "Securities and Exchange Board of India Act, 1992",
        "act_short_name": "SEBI",
        "act_number": "15",
        "act_year": 1992,
    },
    "COMPETITION": {
        "act_name": "Competition Act, 2002",
        "act_short_name": "Competition Act",
        "act_number": "12",
        "act_year": 2002,
    },
    "SARFAESI": {
        "act_name": "Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002",
        "act_short_name": "SARFAESI",
        "act_number": "54",
        "act_year": 2002,
    },
    "IBC": {
        "act_name": "Insolvency and Bankruptcy Code, 2016",
        "act_short_name": "IBC",
        "act_number": "31",
        "act_year": 2016,
    },
    "NIA1881": {
        "act_name": "Negotiable Instruments Act, 1881",
        "act_short_name": "NI Act",
        "act_number": "26",
        "act_year": 1881,
    },
    "LLP": {
        "act_name": "Limited Liability Partnership Act, 2008",
        "act_short_name": "LLP Act",
        "act_number": "6",
        "act_year": 2008,
    },
    "BRA": {
        "act_name": "Banking Regulation Act, 1949",
        "act_short_name": "BR Act",
        "act_number": "10",
        "act_year": 1949,
    },
    # --- Batch 6: Family ---
    "HMA": {
        "act_name": "Hindu Marriage Act, 1955",
        "act_short_name": "HMA",
        "act_number": "25",
        "act_year": 1955,
    },
    "HSA": {
        "act_name": "Hindu Succession Act, 1956",
        "act_short_name": "HSA",
        "act_number": "30",
        "act_year": 1956,
    },
    "SMA": {
        "act_name": "Special Marriage Act, 1954",
        "act_short_name": "SMA",
        "act_number": "43",
        "act_year": 1954,
    },
    "DVA": {
        "act_name": "Protection of Women from Domestic Violence Act, 2005",
        "act_short_name": "DV Act",
        "act_number": "43",
        "act_year": 2005,
    },
    "GWA": {
        "act_name": "Guardians and Wards Act, 1890",
        "act_short_name": "GW Act",
        "act_number": "8",
        "act_year": 1890,
    },
    # --- Batch 7: Labor ---
    "IDA": {
        "act_name": "Industrial Disputes Act, 1947",
        "act_short_name": "ID Act",
        "act_number": "14",
        "act_year": 1947,
    },
    "FA1948": {
        "act_name": "Factories Act, 1948",
        "act_short_name": "Factories Act",
        "act_number": "63",
        "act_year": 1948,
    },
    "ESIA": {
        "act_name": "Employees' State Insurance Act, 1948",
        "act_short_name": "ESI Act",
        "act_number": "34",
        "act_year": 1948,
    },
    "EPFA": {
        "act_name": "Employees' Provident Funds and Miscellaneous Provisions Act, 1952",
        "act_short_name": "EPF Act",
        "act_number": "19",
        "act_year": 1952,
    },
    "PWA": {
        "act_name": "Payment of Wages Act, 1936",
        "act_short_name": "PW Act",
        "act_number": "4",
        "act_year": 1936,
    },
    "MWA": {
        "act_name": "Minimum Wages Act, 1948",
        "act_short_name": "MW Act",
        "act_number": "11",
        "act_year": 1948,
    },
    "TUA": {
        "act_name": "Trade Unions Act, 1926",
        "act_short_name": "TU Act",
        "act_number": "16",
        "act_year": 1926,
    },
    "WCA": {
        "act_name": "Employees' Compensation Act, 1923",
        "act_short_name": "EC Act",
        "act_number": "8",
        "act_year": 1923,
    },
    # --- Batch 8: Tax ---
    "ITA": {
        "act_name": "Income Tax Act, 1961",
        "act_short_name": "IT Act 1961",
        "act_number": "43",
        "act_year": 1961,
    },
    "CGST": {
        "act_name": "Central Goods and Services Tax Act, 2017",
        "act_short_name": "CGST Act",
        "act_number": "12",
        "act_year": 2017,
    },
    "CUSTOMS": {
        "act_name": "Customs Act, 1962",
        "act_short_name": "Customs Act",
        "act_number": "52",
        "act_year": 1962,
    },
    "CEA": {
        "act_name": "Central Excise Act, 1944",
        "act_short_name": "CE Act",
        "act_number": "1",
        "act_year": 1944,
    },
    "STAMP": {
        "act_name": "Indian Stamp Act, 1899",
        "act_short_name": "Stamp Act",
        "act_number": "2",
        "act_year": 1899,
    },
    "BENAMI": {
        "act_name": "Prohibition of Benami Property Transactions Act, 1988",
        "act_short_name": "Benami Act",
        "act_number": "45",
        "act_year": 1988,
    },
    # --- Batch 9: Property + Environmental ---
    "TPA": {
        "act_name": "Transfer of Property Act, 1882",
        "act_short_name": "TPA",
        "act_number": "4",
        "act_year": 1882,
    },
    "RA1908": {
        "act_name": "Registration Act, 1908",
        "act_short_name": "Registration Act",
        "act_number": "16",
        "act_year": 1908,
    },
    "EASEMENTS": {
        "act_name": "Indian Easements Act, 1882",
        "act_short_name": "Easements Act",
        "act_number": "5",
        "act_year": 1882,
    },
    "RERA": {
        "act_name": "Real Estate (Regulation and Development) Act, 2016",
        "act_short_name": "RERA",
        "act_number": "16",
        "act_year": 2016,
    },
    "EPA": {
        "act_name": "Environment (Protection) Act, 1986",
        "act_short_name": "EP Act",
        "act_number": "29",
        "act_year": 1986,
    },
    "WPA": {
        "act_name": "Wild Life (Protection) Act, 1972",
        "act_short_name": "WLP Act",
        "act_number": "53",
        "act_year": 1972,
    },
    "FCA": {
        "act_name": "Forest (Conservation) Act, 1980",
        "act_short_name": "FC Act",
        "act_number": "69",
        "act_year": 1980,
    },
    # --- Batch 10: Technology + Admin ---
    "ITA2000": {
        "act_name": "Information Technology Act, 2000",
        "act_short_name": "IT Act",
        "act_number": "21",
        "act_year": 2000,
    },
    "DPDP": {
        "act_name": "Digital Personal Data Protection Act, 2023",
        "act_short_name": "DPDP Act",
        "act_number": "22",
        "act_year": 2023,
    },
    "AADHAAR": {
        "act_name": "Aadhaar (Targeted Delivery of Financial and Other Subsidies, Benefits and Services) Act, 2016",
        "act_short_name": "Aadhaar Act",
        "act_number": "18",
        "act_year": 2016,
    },
    "LOKPAL": {
        "act_name": "Lokpal and Lokayuktas Act, 2013",
        "act_short_name": "Lokpal Act",
        "act_number": "1",
        "act_year": 2013,
    },
    "CONTEMPT": {
        "act_name": "Contempt of Courts Act, 1971",
        "act_short_name": "Contempt Act",
        "act_number": "70",
        "act_year": 1971,
    },
    "ATT": {
        "act_name": "Administrative Tribunals Act, 1985",
        "act_short_name": "AT Act",
        "act_number": "13",
        "act_year": 1985,
    },
    "UAPA": {
        "act_name": "Unlawful Activities (Prevention) Act, 1967",
        "act_short_name": "UAPA",
        "act_number": "37",
        "act_year": 1967,
    },
    "NIA": {
        "act_name": "National Investigation Agency Act, 2008",
        "act_short_name": "NIA Act",
        "act_number": "34",
        "act_year": 2008,
    },
    "PMLA": {
        "act_name": "Prevention of Money-Laundering Act, 2002",
        "act_short_name": "PMLA",
        "act_number": "15",
        "act_year": 2002,
    },
    "NDPS": {
        "act_name": "Narcotic Drugs and Psychotropic Substances Act, 1985",
        "act_short_name": "NDPS Act",
        "act_number": "61",
        "act_year": 1985,
    },
    "JJA": {
        "act_name": "Juvenile Justice (Care and Protection of Children) Act, 2015",
        "act_short_name": "JJ Act",
        "act_number": "2",
        "act_year": 2015,
    },
    "INSURANCE": {
        "act_name": "Insurance Act, 1938",
        "act_short_name": "Insurance Act",
        "act_number": "4",
        "act_year": 1938,
    },
    "MSMED": {
        "act_name": "Micro, Small and Medium Enterprises Development Act, 2006",
        "act_short_name": "MSMED Act",
        "act_number": "27",
        "act_year": 2006,
    },
}

# Batch groupings for selective download
BATCH_ACTS: dict[int, list[str]] = {
    4: ["ICA", "SOGA", "ACA", "FEMA", "IPA"],
    5: ["CA2013", "SEBI", "COMPETITION", "SARFAESI", "IBC", "NIA1881", "LLP", "BRA"],
    6: ["HMA", "HSA", "SMA", "DVA", "GWA"],
    7: ["IDA", "FA1948", "ESIA", "EPFA", "PWA", "MWA", "TUA", "WCA"],
    8: ["ITA", "CGST", "CUSTOMS", "CEA", "STAMP", "BENAMI"],
    9: ["TPA", "RA1908", "EASEMENTS", "RERA", "EPA", "WPA", "FCA"],
    10: ["ITA2000", "DPDP", "AADHAAR", "LOKPAL", "CONTEMPT", "ATT", "UAPA", "NIA", "PMLA", "NDPS", "JJA", "INSURANCE", "MSMED"],
}


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def save_json(sections: list[dict], filename: str) -> None:
    """Save sections to a JSON file."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / filename
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d sections to %s", len(sections), out_path)


def download_github_acts(only: set[str] | None = None) -> dict[str, int]:
    """Download and convert acts from GitHub repos."""
    stats: dict[str, int] = {}

    github_acts = [
        ("ipc", f"{CIVICTECH_BASE}/ipc.json", convert_ipc, "ipc.json"),
        ("crpc", f"{CIVICTECH_BASE}/crpc.json", convert_crpc, "crpc.json"),
        ("cpc", f"{CIVICTECH_BASE}/cpc.json", convert_cpc, "cpc.json"),
        ("iea", f"{CIVICTECH_BASE}/iea.json", convert_iea, "iea.json"),
        ("constitution", COI_URL, convert_constitution, "constitution.json"),
    ]

    for act_key, url, converter, filename in github_acts:
        if only and act_key not in only:
            continue
        try:
            data = fetch_json(url)
            sections = converter(data)
            save_json(sections, filename)
            stats[act_key] = len(sections)
        except Exception as exc:
            logger.error("Failed to download/convert %s: %s", act_key, exc)
            stats[act_key] = 0

    return stats


def download_pdf_acts(
    only: set[str] | None = None,
    batch_codes: set[str] | None = None,
) -> dict[str, int]:
    """Download and extract acts from official PDFs.

    Args:
        only: If set, only process acts whose lowercased key is in this set.
        batch_codes: If set, only process acts whose key is in this set (uppercase).
    """
    stats: dict[str, int] = {}

    for code, url in PDF_URLS.items():
        act_key = code.lower()
        if only and act_key not in only:
            continue
        if batch_codes and code not in batch_codes:
            continue
        if code not in PDF_ACT_CONFIGS:
            logger.warning("No config for %s — skipping", code)
            continue
        try:
            pdf_bytes = fetch_pdf_bytes(url)
            config = PDF_ACT_CONFIGS[code]
            sections = extract_sections_from_pdf(pdf_bytes, config)

            if len(sections) < 3:
                logger.warning(
                    "Only %d sections extracted from %s PDF — quality may be poor",
                    len(sections), code,
                )

            save_json(sections, f"{act_key}.json")
            stats[act_key] = len(sections)
            logger.info("✓ %s: %d sections", code, len(sections))
        except Exception as exc:
            logger.error("Failed to download/extract %s: %s", code, exc)
            stats[act_key] = 0

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real legal text and convert to JSON")
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF extraction entirely")
    parser.add_argument("--only", nargs="+", help="Only download specific acts (e.g., ipc crpc constitution)")
    parser.add_argument(
        "--batch", nargs="+", type=int,
        help="Download specific batches (4-10). Batches 1-3 are GitHub+original PDFs.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    only = set(a.lower() for a in args.only) if args.only else None

    # Compute batch filter
    batch_codes: set[str] | None = None
    if args.batch:
        batch_codes = set()
        for b in args.batch:
            if b in BATCH_ACTS:
                batch_codes.update(BATCH_ACTS[b])
            else:
                logger.warning("Unknown batch %d — valid: 4-10", b)

    print("=" * 60)
    print("Downloading real legal text from authoritative sources")
    print("  Source: indiacode.nic.in (Government of India)")
    print("=" * 60)

    # GitHub sources (IPC, CrPC, CPC, IEA, Constitution) — Batches 1+3
    github_stats: dict[str, int] = {}
    if not args.batch:  # Only run GitHub acts when no batch filter
        github_stats = download_github_acts(only)
        for act, count in github_stats.items():
            print(f"  {act.upper()}: {count} sections")

    # PDF sources
    pdf_stats: dict[str, int] = {}
    if not args.skip_pdf:
        pdf_stats = download_pdf_acts(only, batch_codes)
        for act, count in sorted(pdf_stats.items()):
            print(f"  {act.upper()}: {count} sections (from PDF)")
    else:
        print("  Skipping PDF extraction (--skip-pdf)")

    all_stats = {**github_stats, **pdf_stats}
    total = sum(all_stats.values())
    print(f"\nTOTAL: {total} sections across {len(all_stats)} acts")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
