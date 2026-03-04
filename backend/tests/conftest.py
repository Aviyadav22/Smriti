"""Shared test fixtures and configuration."""

import pytest


@pytest.fixture
def sample_judgment_text() -> str:
    """A sample Indian Supreme Court judgment text for testing."""
    return """
IN THE SUPREME COURT OF INDIA
CIVIL APPELLATE JURISDICTION

CIVIL APPEAL NO. 5678 OF 2023

State of Maharashtra                    ... Appellant(s)
                 Versus
Rajesh Kumar & Ors.                     ... Respondent(s)

JUDGMENT

Hon'ble Mr. Justice A.B. Sharma
Hon'ble Mr. Justice C.D. Patel

Date: 15th March 2023

FACTS

The brief facts of the case are that the appellant-State filed a
civil appeal challenging the judgment dated 10.01.2022 of the
High Court of Bombay in Writ Petition No. 3456 of 2021. The
respondent had filed the writ petition challenging the acquisition
of his property under the Right to Fair Compensation and
Transparency in Land Acquisition, Rehabilitation and Resettlement
Act, 2013 (hereinafter referred to as 'the Act of 2013').

The property measuring 2.5 acres was situated in Pune district.
The notification under Section 11 of the Act of 2013 was issued
on 15.06.2020. The respondent claimed that the compensation
offered was inadequate and the procedure under Section 26 was
not followed.

ARGUMENTS

Learned counsel for the appellant submitted that all procedures
under the Act of 2013 were duly followed. Reliance was placed on
(2019) 5 SCC 234 and AIR 2020 SC 1567.

Per contra, learned counsel for the respondent relied upon
2021 INSC 456 and submitted that Section 26 mandates personal
hearing before final determination of compensation.

ANALYSIS AND DISCUSSION

We have carefully considered the submissions made by both sides
and perused the record. The question that falls for our
consideration is whether the procedure under Section 26 of the
Act of 2013 was complied with.

In the landmark judgment reported as (2018) 3 SCC 789, this
Court held that personal hearing is a mandatory requirement
under Section 26. This principle was reiterated in [2020] 4 SCR 123.

We hold that the requirement of personal hearing under Section 26
is mandatory and not directory. The High Court was right in setting
aside the acquisition proceedings.

ORDER

In the result, the appeal is dismissed. The judgment of the High
Court is affirmed. No costs.
"""


@pytest.fixture
def sample_parquet_metadata() -> dict:
    """Sample Parquet metadata as would come from the S3 dataset."""
    return {
        "title": "State of Maharashtra v. Rajesh Kumar",
        "petitioner": "State of Maharashtra",
        "respondent": "Rajesh Kumar & Ors.",
        "description": "Civil appeal regarding land acquisition",
        "judge": "A.B. Sharma, C.D. Patel",
        "author_judge": "A.B. Sharma",
        "citation": "(2023) 7 SCC 456",
        "case_id": "CA-5678-2023",
        "cnr": "SCCA12345678902023",
        "decision_date": "2023-03-15",
        "disposal_nature": "Dismissed",
        "court": "Supreme Court of India",
        "available_languages": "english,hindi",
        "path": "data/tar/year=2023/english/CA-5678-2023.pdf",
        "nc_display": "Civil Appeal",
        "year": 2023,
    }
