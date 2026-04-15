"""Shared test fixtures and configuration."""

# IMPORTANT: set default env vars BEFORE any `app.*` import. Pydantic Settings
# reads the environment at module-import time, so we need these in place
# before `app.core.config` is pulled in by anything else in this file.
# These are test-only fake values — real production secrets come from
# Secret Manager, not from this conftest.
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-" + "x" * 40)
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-jwt-refresh-" + "x" * 40)
# 64-char hex = 32 bytes, matches app.security.encryption's validation.
os.environ.setdefault("ENCRYPTION_KEY", "a" * 64)
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("PINECONE_HOST", "https://test.pinecone.io")
os.environ.setdefault("COHERE_API_KEY", "test-cohere-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.security import rate_limiter as _rl_module  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_rate_limiter():
    """Reset and mock the rate-limiter singleton for every test.

    Without this, the module-level singleton connects to real Redis
    (via settings.redis_url) and shares state across tests — causing
    flaky failures when the sliding window accumulates entries.

    This fixture:
    1. Resets the singleton so no stale connection persists.
    2. Patches _get_rate_limiter to return a mock that always allows.
    3. Clears in-memory buckets so tests start fresh.
    """
    _rl_module._rate_limiter = None
    _rl_module._redis_client = None
    _rl_module._mem_buckets.clear()

    mock_limiter = AsyncMock()
    mock_limiter.check_rate_limit.return_value = True

    with patch.object(_rl_module, "_get_rate_limiter", return_value=mock_limiter):
        yield

    # Cleanup: reset again after test
    _rl_module._rate_limiter = None
    _rl_module._redis_client = None
    _rl_module._mem_buckets.clear()


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
