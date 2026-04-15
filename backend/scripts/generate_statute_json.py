#!/usr/bin/env python3
"""Generate statute JSON files from code mapping constants.

Creates JSON files for IPC, BNS, CrPC, BNSS, IEA, BSA statutes
using the bidirectional code mappings in constants.py.

Usage:
    python scripts/generate_statute_json.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.legal.constants import (
    CRPC_TO_BNSS_MAP,
    EVIDENCE_TO_BSA_MAP,
    IPC_TO_BNS_MAP,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "statutes"

# Known section titles for major IPC sections
IPC_TITLES: dict[str, str] = {
    "34": "Acts done by several persons in furtherance of common intention",
    "107": "Abetment of a thing",
    "109": "Punishment of abetment",
    "114": "Abettor present when offence is committed",
    "120B": "Punishment of criminal conspiracy",
    "149": "Every member of unlawful assembly guilty of offence committed",
    "153A": "Promoting enmity between different groups",
    "170": "Personating a public servant",
    "186": "Obstructing public servant in discharge of public functions",
    "191": "Giving false evidence",
    "193": "Punishment for false evidence",
    "199": "False statement made in declaration",
    "211": "False charge of offence",
    "224": "Resistance or obstruction by a person to his lawful apprehension",
    "228": "Intentional insult or interruption to public servant sitting in judicial proceeding",
    "268": "Public nuisance",
    "269": "Negligent act likely to spread infection of disease",
    "279": "Rash driving or riding on a public way",
    "292": "Sale etc. of obscene books",
    "295A": "Deliberate and malicious acts intended to outrage religious feelings",
    "299": "Culpable homicide",
    "300": "Murder",
    "302": "Punishment for murder",
    "304": "Punishment for culpable homicide not amounting to murder",
    "304A": "Causing death by negligence",
    "304B": "Dowry death",
    "306": "Abetment of suicide",
    "307": "Attempt to murder",
    "309": "Attempt to commit suicide",
    "319": "Hurt",
    "320": "Grievous hurt",
    "323": "Punishment for voluntarily causing hurt",
    "324": "Voluntarily causing hurt by dangerous weapons",
    "325": "Punishment for voluntarily causing grievous hurt",
    "326": "Voluntarily causing grievous hurt by dangerous weapons",
    "332": "Voluntarily causing hurt to deter public servant from his duty",
    "341": "Punishment for wrongful restraint",
    "342": "Punishment for wrongful confinement",
    "351": "Assault",
    "354": "Assault or criminal force to woman with intent to outrage her modesty",
    "354A": "Sexual harassment",
    "354B": "Assault or use of criminal force to woman with intent to disrobe",
    "354C": "Voyeurism",
    "354D": "Stalking",
    "355": "Assault or criminal force with intent to dishonour person",
    "362": "Abduction",
    "363": "Punishment for kidnapping",
    "364": "Kidnapping or abducting in order to murder",
    "364A": "Kidnapping for ransom",
    "365": "Kidnapping or abducting with intent secretly and wrongfully to confine person",
    "376": "Punishment for rape",
    "376A": "Punishment for causing death or resulting in persistent vegetative state of victim",
    "376D": "Gang rape",
    "378": "Theft",
    "379": "Punishment for theft",
    "380": "Theft in dwelling house",
    "383": "Extortion",
    "384": "Punishment for extortion",
    "390": "Robbery",
    "391": "Dacoity",
    "392": "Punishment for robbery",
    "395": "Punishment for dacoity",
    "403": "Dishonest misappropriation of property",
    "405": "Criminal breach of trust",
    "406": "Punishment for criminal breach of trust",
    "409": "Criminal breach of trust by public servant",
    "411": "Dishonestly receiving stolen property",
    "415": "Cheating",
    "420": "Cheating and dishonestly inducing delivery of property",
    "426": "Punishment for mischief",
    "435": "Mischief by fire or explosive substance",
    "441": "Criminal trespass",
    "442": "House-trespass",
    "447": "Punishment for criminal trespass",
    "448": "Punishment for house-trespass",
    "452": "House-trespass after preparation for hurt",
    "463": "Forgery",
    "467": "Forgery of valuable security",
    "468": "Forgery for purpose of cheating",
    "471": "Using as genuine a forged document",
    "489A": "Counterfeiting currency-notes or bank-notes",
    "494": "Marrying again during lifetime of husband or wife",
    "498A": "Husband or relative of husband of a woman subjecting her to cruelty",
    "499": "Defamation",
    "500": "Punishment for defamation",
    "503": "Criminal intimidation",
    "504": "Intentional insult with intent to provoke breach of the peace",
    "506": "Punishment for criminal intimidation",
    "509": "Word gesture or act intended to insult the modesty of a woman",
}


def _sort_key(sec: str) -> tuple[bool, str]:
    return (not sec[0].isdigit(), sec.zfill(10) if sec[0].isdigit() else sec)


def generate_ipc() -> list[dict]:
    sections = []
    for sec_num in sorted(IPC_TO_BNS_MAP, key=_sort_key):
        bns_num = IPC_TO_BNS_MAP[sec_num]
        title = IPC_TITLES.get(sec_num, f"Section {sec_num}")
        sections.append({
            "act_name": "Indian Penal Code, 1860",
            "act_short_name": "IPC",
            "act_number": "45",
            "act_year": 1860,
            "section_number": sec_num,
            "section_title": title,
            "section_text": (
                f"Section {sec_num} of the Indian Penal Code, 1860. "
                f"{title}. Now replaced by Section {bns_num} of "
                f"Bharatiya Nyaya Sanhita, 2023."
            ),
            "document_type": "statute",
        })
    return sections


def generate_bns() -> list[dict]:
    reverse = {v: k for k, v in IPC_TO_BNS_MAP.items()}
    sections = []
    for sec_num in sorted(reverse, key=_sort_key):
        old_sec = reverse[sec_num]
        old_title = IPC_TITLES.get(old_sec, "")
        sections.append({
            "act_name": "Bharatiya Nyaya Sanhita, 2023",
            "act_short_name": "BNS",
            "act_number": "45",
            "act_year": 2023,
            "section_number": sec_num,
            "section_title": f"Section {sec_num} (replaces IPC {old_sec})",
            "section_text": (
                f"Section {sec_num} of Bharatiya Nyaya Sanhita, 2023. "
                f"Replaces Section {old_sec}"
                f"{' (' + old_title + ')' if old_title else ''} "
                f"of the Indian Penal Code, 1860. Effective from 1 July 2024."
            ),
            "document_type": "statute",
        })
    return sections


def generate_crpc() -> list[dict]:
    sections = []
    for sec_num in sorted(CRPC_TO_BNSS_MAP, key=_sort_key):
        bnss_num = CRPC_TO_BNSS_MAP[sec_num]
        sections.append({
            "act_name": "Code of Criminal Procedure, 1973",
            "act_short_name": "CrPC",
            "act_number": "2",
            "act_year": 1974,
            "section_number": sec_num,
            "section_title": f"Section {sec_num}",
            "section_text": (
                f"Section {sec_num} of the Code of Criminal Procedure, 1973. "
                f"Now replaced by Section {bnss_num} of "
                f"Bharatiya Nagarik Suraksha Sanhita, 2023."
            ),
            "document_type": "statute",
        })
    return sections


def generate_bnss() -> list[dict]:
    reverse = {v: k for k, v in CRPC_TO_BNSS_MAP.items()}
    sections = []
    for sec_num in sorted(reverse, key=_sort_key):
        old_sec = reverse[sec_num]
        sections.append({
            "act_name": "Bharatiya Nagarik Suraksha Sanhita, 2023",
            "act_short_name": "BNSS",
            "act_number": "46",
            "act_year": 2023,
            "section_number": sec_num,
            "section_title": f"Section {sec_num} (replaces CrPC {old_sec})",
            "section_text": (
                f"Section {sec_num} of Bharatiya Nagarik Suraksha Sanhita, 2023. "
                f"Replaces Section {old_sec} of the Code of Criminal Procedure, 1973. "
                f"Effective from 1 July 2024."
            ),
            "document_type": "statute",
        })
    return sections


def generate_iea() -> list[dict]:
    sections = []
    for sec_num in sorted(EVIDENCE_TO_BSA_MAP, key=_sort_key):
        bsa_num = EVIDENCE_TO_BSA_MAP[sec_num]
        sections.append({
            "act_name": "Indian Evidence Act, 1872",
            "act_short_name": "IEA",
            "act_number": "1",
            "act_year": 1872,
            "section_number": sec_num,
            "section_title": f"Section {sec_num}",
            "section_text": (
                f"Section {sec_num} of the Indian Evidence Act, 1872. "
                f"Now replaced by Section {bsa_num} of "
                f"Bharatiya Sakshya Adhiniyam, 2023."
            ),
            "document_type": "statute",
        })
    return sections


def generate_bsa() -> list[dict]:
    reverse = {v: k for k, v in EVIDENCE_TO_BSA_MAP.items()}
    sections = []
    for sec_num in sorted(reverse, key=_sort_key):
        old_sec = reverse[sec_num]
        sections.append({
            "act_name": "Bharatiya Sakshya Adhiniyam, 2023",
            "act_short_name": "BSA",
            "act_number": "47",
            "act_year": 2023,
            "section_number": sec_num,
            "section_title": f"Section {sec_num} (replaces IEA {old_sec})",
            "section_text": (
                f"Section {sec_num} of Bharatiya Sakshya Adhiniyam, 2023. "
                f"Replaces Section {old_sec} of the Indian Evidence Act, 1872. "
                f"Effective from 1 July 2024."
            ),
            "document_type": "statute",
        })
    return sections


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    generators = [
        ("ipc.json", generate_ipc),
        ("bns.json", generate_bns),
        ("crpc.json", generate_crpc),
        ("bnss.json", generate_bnss),
        ("iea.json", generate_iea),
        ("bsa.json", generate_bsa),
    ]

    total = 0
    for filename, gen_fn in generators:
        sections = gen_fn()
        out_path = OUT_DIR / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sections, f, indent=2, ensure_ascii=False)
        total += len(sections)



if __name__ == "__main__":
    main()
