"""Legal domain constants for the Indian legal system.

Defines enumerations, mappings, and reference data used across the platform
for case classification, statutory cross-referencing, and judgment structure.
"""

from typing import Final

# ---------------------------------------------------------------------------
# Case types — classification of filings before Indian courts
# ---------------------------------------------------------------------------

CASE_TYPES: Final[list[str]] = [
    "Civil Appeal",
    "Criminal Appeal",
    "Special Leave Petition",
    "Writ Petition",
    "Transfer Petition",
    "Review Petition",
    "Contempt Petition",
    "Original Suit",
    "Reference",
    "Other",
]

# ---------------------------------------------------------------------------
# Bench types — ordered by ascending precedent weight
# ---------------------------------------------------------------------------

BENCH_TYPES: Final[list[str]] = [
    "single",
    "division",
    "full",
    "constitutional",
]

# ---------------------------------------------------------------------------
# Disposal natures — how a case was finally resolved
# ---------------------------------------------------------------------------

DISPOSAL_NATURES: Final[list[str]] = [
    "Allowed",
    "Dismissed",
    "Partly Allowed",
    "Withdrawn",
    "Remanded",
    "Other",
]

# ---------------------------------------------------------------------------
# Jurisdictions
# ---------------------------------------------------------------------------

JURISDICTIONS: Final[list[str]] = [
    "civil",
    "criminal",
    "constitutional",
    "tax",
    "labor",
    "company",
    "other",
]

# ---------------------------------------------------------------------------
# Judgment section types — canonical labels for structural segments
# ---------------------------------------------------------------------------

SECTION_TYPES: Final[list[str]] = [
    "HEADER",
    "FACTS",
    "ARGUMENTS",
    "ISSUES",
    "ANALYSIS",
    "RATIO",
    "ORDER",
]

# ---------------------------------------------------------------------------
# IPC → BNS section mapping  (Indian Penal Code, 1860 → Bharatiya Nyaya
# Sanhita, 2023 — effective 1 July 2024)
# ---------------------------------------------------------------------------

IPC_TO_BNS_MAP: Final[dict[str, str]] = {
    # Offences against the human body
    "302": "103",   # Murder
    "304": "105",   # Culpable homicide not amounting to murder
    "304A": "106",  # Death by negligence
    "304B": "80",   # Dowry death
    "306": "108",   # Abetment of suicide
    "307": "109",   # Attempt to murder
    "323": "115",   # Voluntarily causing hurt
    "324": "118",   # Voluntarily causing hurt by dangerous weapon
    "326": "119",   # Voluntarily causing grievous hurt by dangerous weapon
    "354": "74",    # Assault on woman with intent to outrage modesty
    "376": "63",    # Rape
    "377": "377",   # Unnatural offences (repealed / read down — S.377 retained in BNS debates for bestiality)
    "384": "308",   # Extortion
    "390": "309",   # Robbery
    "392": "309",   # Punishment for robbery
    "395": "310",   # Dacoity
    "397": "310",   # Robbery or dacoity with attempt to cause death or grievous hurt
    "406": "316",   # Criminal breach of trust
    "420": "318",   # Cheating and dishonestly inducing delivery of property
    "498A": "85",   # Cruelty by husband or relatives
    "499": "356",   # Defamation
    "500": "356",   # Punishment for defamation
    "506": "351",   # Criminal intimidation
    "509": "79",    # Word, gesture or act intended to insult modesty of a woman
    "34": "3(5)",   # Acts done by several persons in furtherance of common intention
    "120B": "61",   # Criminal conspiracy
    "149": "190",   # Every member of unlawful assembly guilty of offence committed
    "153A": "196",  # Promoting enmity between groups
    "295A": "299",  # Deliberate acts to outrage religious feelings
    "379": "303",   # Theft
    "411": "317",   # Dishonestly receiving stolen property
    "467": "336",   # Forgery of valuable security
    "468": "337",   # Forgery for purpose of cheating
    "471": "340",   # Using as genuine a forged document
}

# ---------------------------------------------------------------------------
# CrPC → BNSS section mapping  (Code of Criminal Procedure, 1973 →
# Bharatiya Nagarik Suraksha Sanhita, 2023)
# ---------------------------------------------------------------------------

CRPC_TO_BNSS_MAP: Final[dict[str, str]] = {
    "41": "35",     # When police may arrest without warrant
    "125": "144",   # Order for maintenance of wives, children and parents
    "144": "163",   # Power to issue order in urgent cases of nuisance or apprehended danger
    "154": "173",   # Information in cognizable cases (FIR)
    "161": "180",   # Examination of witnesses by police
    "164": "183",   # Recording of confessions and statements
    "167": "187",   # Procedure when investigation cannot be completed in 24 hours
    "197": "218",   # Prosecution of judges and public servants
    "313": "351",   # Power to examine the accused
    "354": "392",   # Language of judgments
    "374": "411",   # Appeals from convictions
    "378": "419",   # Appeal in case of acquittal
    "438": "482",   # Direction for grant of bail to person apprehending arrest (anticipatory bail)
    "439": "483",   # Special powers of High Court or Court of Session regarding bail
    "482": "528",   # Saving of inherent powers of High Court
}

# ---------------------------------------------------------------------------
# Indian Evidence Act, 1872 → BSA mapping  (Bharatiya Sakshya Adhiniyam, 2023)
# ---------------------------------------------------------------------------

EVIDENCE_TO_BSA_MAP: Final[dict[str, str]] = {
    "3": "2",       # Interpretation clause / definitions
    "17": "15",     # Admission defined
    "24": "22",     # Confession caused by inducement, threat or promise
    "25": "23",     # Confession to police officer not to be proved
    "27": "25",     # How much information received from accused may be proved
    "32": "26",     # Cases in which statement of relevant fact by person who is dead
    "45": "39",     # Opinion of experts
    "65B": "63",    # Admissibility of electronic records
    "101": "104",   # Burden of proof
    "113A": "118",  # Presumption as to abetment of suicide by married woman
    "113B": "119",  # Presumption as to dowry death
    "114": "120",   # Court may presume existence of certain facts
}
