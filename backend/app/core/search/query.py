"""LLM-based query understanding for legal search queries.

Uses Gemini structured JSON output to parse natural language queries into
structured search components: intent, entities, filters, and an expanded query.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.interfaces import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

QUERY_UNDERSTANDING_SYSTEM = """\
You are a legal search query analyzer for Indian law. Parse the user's search \
query into structured components for a hybrid search system.

RULES:
1. Identify the search intent: "citation_lookup", "topic_search", "case_search", \
"statute_search", "judge_search", "general".
2. Extract any explicit filters mentioned (court, year, case type, judge, act).
3. Generate an expanded query that adds relevant legal synonyms and related terms.
4. Identify key legal concepts and entities.
5. If the query mentions a specific case by name, extract it as a citation_lookup.
6. Handle Indian legal abbreviations: SC = Supreme Court, HC = High Court, \
IPC = Indian Penal Code, CrPC = Code of Criminal Procedure, \
CPC = Code of Civil Procedure, BNS = Bharatiya Nyaya Sanhita, \
BNSS = Bharatiya Nagarik Suraksha Sanhita.
"""

QUERY_UNDERSTANDING_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "citation_lookup",
                "topic_search",
                "case_search",
                "statute_search",
                "judge_search",
                "general",
            ],
        },
        "original_query": {"type": "string"},
        "expanded_query": {"type": "string"},
        "filters": {
            "type": "object",
            "properties": {
                "court": {"type": "string"},
                "year_from": {"type": "integer"},
                "year_to": {"type": "integer"},
                "case_type": {"type": "string"},
                "bench_type": {"type": "string"},
                "judge": {"type": "string"},
                "act": {"type": "string"},
                "section": {"type": "string"},
            },
        },
        "entities": {
            "type": "object",
            "properties": {
                "case_names": {"type": "array", "items": {"type": "string"}},
                "statutes": {"type": "array", "items": {"type": "string"}},
                "legal_concepts": {"type": "array", "items": {"type": "string"}},
                "judges": {"type": "array", "items": {"type": "string"}},
                "courts": {"type": "array", "items": {"type": "string"}},
            },
        },
        "search_strategy": {
            "type": "string",
            "enum": ["vector_heavy", "keyword_heavy", "balanced", "exact_match"],
        },
    },
    "required": [
        "intent",
        "original_query",
        "expanded_query",
        "filters",
        "entities",
        "search_strategy",
    ],
}


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Structured search filters extracted from query or explicit params."""

    court: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    case_type: str | None = None
    bench_type: str | None = None
    judge: str | None = None
    act: str | None = None
    section: str | None = None


@dataclass(frozen=True, slots=True)
class QueryEntities:
    """Named entities extracted from the search query."""

    case_names: list[str] = field(default_factory=list)
    statutes: list[str] = field(default_factory=list)
    legal_concepts: list[str] = field(default_factory=list)
    judges: list[str] = field(default_factory=list)
    courts: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class QueryUnderstanding:
    """Complete parsed representation of a search query."""

    intent: str
    original_query: str
    expanded_query: str
    filters: SearchFilters
    entities: QueryEntities
    search_strategy: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def understand_query(
    raw_query: str,
    llm: LLMProvider,
) -> QueryUnderstanding:
    """Parse a raw search query into structured components via LLM.

    Falls back to a simple passthrough if the LLM call fails so that
    search continues to work (with lower quality) even on LLM errors.
    """
    try:
        result = await llm.generate_structured(
            prompt=f"Parse this legal search query:\n\n{raw_query}",
            system=QUERY_UNDERSTANDING_SYSTEM,
            output_schema=QUERY_UNDERSTANDING_SCHEMA,
        )
        return _parse_llm_result(raw_query, result)
    except (ValueError, KeyError, ConnectionError, TimeoutError, RuntimeError) as exc:
        logger.warning("LLM query understanding failed, using passthrough: %s", exc)
        return _passthrough(raw_query)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_llm_result(raw_query: str, data: dict) -> QueryUnderstanding:
    """Build a ``QueryUnderstanding`` from the LLM structured output."""
    filters_raw = data.get("filters", {})
    entities_raw = data.get("entities", {})

    return QueryUnderstanding(
        intent=data.get("intent", "general"),
        original_query=raw_query,
        expanded_query=data.get("expanded_query", raw_query),
        filters=SearchFilters(
            court=filters_raw.get("court"),
            year_from=filters_raw.get("year_from"),
            year_to=filters_raw.get("year_to"),
            case_type=filters_raw.get("case_type"),
            bench_type=filters_raw.get("bench_type"),
            judge=filters_raw.get("judge"),
            act=filters_raw.get("act"),
            section=filters_raw.get("section"),
        ),
        entities=QueryEntities(
            case_names=entities_raw.get("case_names", []),
            statutes=entities_raw.get("statutes", []),
            legal_concepts=entities_raw.get("legal_concepts", []),
            judges=entities_raw.get("judges", []),
            courts=entities_raw.get("courts", []),
        ),
        search_strategy=data.get("search_strategy", "balanced"),
    )


def _passthrough(raw_query: str) -> QueryUnderstanding:
    """Return a minimal ``QueryUnderstanding`` when LLM is unavailable."""
    return QueryUnderstanding(
        intent="general",
        original_query=raw_query,
        expanded_query=raw_query,
        filters=SearchFilters(),
        entities=QueryEntities(),
        search_strategy="balanced",
    )
