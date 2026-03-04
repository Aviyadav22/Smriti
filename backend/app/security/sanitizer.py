"""Input sanitization and prompt injection detection.

Provides functions to clean user input, strip dangerous content, and detect
potential LLM prompt injection attempts.
"""

import re
from typing import Final

# ---------------------------------------------------------------------------
# HTML tag and dangerous content patterns
# ---------------------------------------------------------------------------

_HTML_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
_NULL_BYTE_PATTERN: re.Pattern[str] = re.compile(r"\x00")
_CONTROL_CHAR_PATTERN: re.Pattern[str] = re.compile(
    r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

# ---------------------------------------------------------------------------
# LLM prompt injection markers
# ---------------------------------------------------------------------------

_INJECTION_MARKERS: Final[list[str]] = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard above",
    "disregard previous",
    "forget your instructions",
    "forget all previous",
    "new instructions:",
    "system prompt:",
    "you are now",
    "pretend you are",
    "act as if",
    "jailbreak",
    "DAN mode",
    "developer mode",
    "ignore safety",
    "bypass restrictions",
    "override system",
    "\\n\\nsystem:",
    "```system",
    "<|im_start|>",
    "<|im_end|>",
    "### instruction",
    "### system",
    "[INST]",
    "[/INST]",
    "<<SYS>>",
    "<</SYS>>",
]

_INJECTION_PATTERN: re.Pattern[str] = re.compile(
    "|".join(re.escape(marker) for marker in _INJECTION_MARKERS),
    re.IGNORECASE,
)

# Patterns that look like role-switching attempts
_ROLE_SWITCH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|\n)\s*(?:system|assistant|user|human|ai)\s*:",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_input(text: str) -> str:
    """Sanitize general user input by removing dangerous content.

    Strips HTML tags, null bytes, and control characters while preserving
    normal whitespace (spaces, tabs, newlines).

    Args:
        text: Raw user input.

    Returns:
        Sanitized text.
    """
    # Strip HTML tags
    cleaned = _HTML_TAG_PATTERN.sub("", text)

    # Remove null bytes
    cleaned = _NULL_BYTE_PATTERN.sub("", cleaned)

    # Remove control characters (preserve \t, \n, \r)
    cleaned = _CONTROL_CHAR_PATTERN.sub("", cleaned)

    # Collapse excessive whitespace (more than 3 consecutive newlines)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)

    return cleaned.strip()


def sanitize_search_query(query: str) -> str:
    """Sanitize a search query with additional LLM injection protection.

    Applies all standard sanitization plus removes known prompt injection
    markers and role-switching patterns.

    Args:
        query: Raw search query from user.

    Returns:
        Sanitized query suitable for LLM and search engine consumption.
    """
    # Apply standard sanitization first
    cleaned = sanitize_input(query)

    # Remove prompt injection markers
    cleaned = _INJECTION_PATTERN.sub("", cleaned)

    # Remove role-switching patterns
    cleaned = _ROLE_SWITCH_PATTERN.sub("", cleaned)

    # Collapse resulting excess whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


def detect_prompt_injection(text: str) -> bool:
    """Detect potential prompt injection attempts in user input.

    Checks for known injection markers, role-switching patterns, and
    suspicious formatting that may indicate an attempt to manipulate
    LLM behavior.

    Args:
        text: User input to analyze.

    Returns:
        True if a prompt injection pattern is detected, False otherwise.
    """
    # Check for known injection markers
    if _INJECTION_PATTERN.search(text):
        return True

    # Check for role-switching patterns
    if _ROLE_SWITCH_PATTERN.search(text):
        return True

    # Check for excessive special characters that may indicate encoding attacks
    # (e.g., many backticks, pipe characters used in chat-ML formatting)
    special_char_count = sum(
        1 for c in text if c in "`|<>{}[]"
    )
    if len(text) > 0 and special_char_count / len(text) > 0.15:
        return True

    return False
