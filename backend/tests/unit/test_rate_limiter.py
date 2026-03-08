"""Tests for rate limiter parsing and core logic."""

from __future__ import annotations

import pytest

from app.security.rate_limiter import _parse_rate_limit


class TestParseRateLimit:
    """Tests for the _parse_rate_limit helper function."""

    def test_valid_per_minute(self) -> None:
        count, seconds = _parse_rate_limit("100/minute")
        assert count == 100
        assert seconds == 60

    def test_valid_per_second(self) -> None:
        count, seconds = _parse_rate_limit("5/second")
        assert count == 5
        assert seconds == 1

    def test_valid_per_hour(self) -> None:
        count, seconds = _parse_rate_limit("1000/hour")
        assert count == 1000
        assert seconds == 3600

    def test_valid_per_day(self) -> None:
        count, seconds = _parse_rate_limit("10000/day")
        assert count == 10000
        assert seconds == 86400

    def test_valid_plural_units(self) -> None:
        count, seconds = _parse_rate_limit("50/minutes")
        assert count == 50
        assert seconds == 60

    def test_strips_whitespace(self) -> None:
        count, seconds = _parse_rate_limit("  10 / second ")
        assert count == 10
        assert seconds == 1

    def test_invalid_format_no_slash(self) -> None:
        with pytest.raises(ValueError, match="Invalid rate limit format"):
            _parse_rate_limit("100minute")

    def test_invalid_format_too_many_slashes(self) -> None:
        with pytest.raises(ValueError, match="Invalid rate limit format"):
            _parse_rate_limit("100/min/extra")

    def test_invalid_count_non_numeric(self) -> None:
        with pytest.raises(ValueError, match="Invalid request count"):
            _parse_rate_limit("abc/minute")

    def test_invalid_unit(self) -> None:
        with pytest.raises(ValueError, match="Unknown time unit"):
            _parse_rate_limit("100/fortnight")
