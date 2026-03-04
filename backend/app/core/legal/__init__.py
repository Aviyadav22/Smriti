"""Indian legal domain utilities."""

from app.core.legal.constants import (
    BENCH_TYPES,
    CASE_TYPES,
    DISPOSAL_NATURES,
    JURISDICTIONS,
    SECTION_TYPES,
)
from app.core.legal.courts import (
    AIR_COURT_CODES,
    COURT_NAME_MAP,
    get_court_level,
    normalize_court_name,
)
from app.core.legal.extractor import (
    ActReference,
    Citation,
    extract_acts_cited,
    extract_citations,
)

__all__ = [
    "AIR_COURT_CODES",
    "BENCH_TYPES",
    "CASE_TYPES",
    "COURT_NAME_MAP",
    "DISPOSAL_NATURES",
    "JURISDICTIONS",
    "SECTION_TYPES",
    "ActReference",
    "Citation",
    "extract_acts_cited",
    "extract_citations",
    "get_court_level",
    "normalize_court_name",
]
