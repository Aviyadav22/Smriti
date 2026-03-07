"""Tests for document analysis Celery task."""

from unittest.mock import MagicMock

from app.tasks.document_tasks import _format_issues_with_precedents


class TestFormatIssuesWithPrecedents:
    def test_formats_single_issue(self) -> None:
        issues = [MagicMock(title="Privacy", description="Article 21 violation")]
        precedents = [
            MagicMock(
                supporting=[
                    MagicMock(title="KS Puttaswamy v. UOI", citation="(2017) 10 SCC 1", score=0.95),
                ],
                statutes=["IT Act, 2000"],
            )
        ]
        result = _format_issues_with_precedents(issues, precedents)
        assert "Privacy" in result
        assert "KS Puttaswamy" in result
        assert "IT Act, 2000" in result

    def test_formats_multiple_issues(self) -> None:
        issues = [
            MagicMock(title="Issue 1", description="Desc 1"),
            MagicMock(title="Issue 2", description="Desc 2"),
        ]
        precedents = [
            MagicMock(supporting=[], statutes=[]),
            MagicMock(supporting=[], statutes=[]),
        ]
        result = _format_issues_with_precedents(issues, precedents)
        assert "Issue 1" in result
        assert "Issue 2" in result

    def test_handles_no_precedents(self) -> None:
        issues = [MagicMock(title="Orphan Issue", description="No cases found")]
        precedents = [MagicMock(supporting=[], statutes=[])]
        result = _format_issues_with_precedents(issues, precedents)
        assert "Orphan Issue" in result
        assert "Supporting" not in result
