"""Tests for Drafting Agent V2 features."""
from __future__ import annotations

import pytest

from app.core.drafting.court_profiles import COURT_PROFILES
from app.core.drafting.export import export_to_docx, export_to_pdf
from app.core.drafting.templates import get_template


class TestExportWithCourtProfile:
    @pytest.mark.asyncio
    async def test_docx_export_with_sc_profile(self) -> None:
        template = get_template("bail_application")
        profile = COURT_PROFILES["supreme_court"]
        content = "## FACTS\n\nThe accused was arrested on 01.01.2024."
        result = await export_to_docx(content, template, court_profile=profile)
        assert isinstance(result, bytes)
        assert len(result) > 100  # Not empty

    @pytest.mark.asyncio
    async def test_docx_export_with_affidavit(self) -> None:
        template = get_template("bail_application")
        content = "## FACTS\n\nThe accused was arrested."
        affidavit = "## AFFIDAVIT\n\nI solemnly affirm and state on oath..."
        result = await export_to_docx(content, template, affidavit=affidavit)
        assert isinstance(result, bytes)
        assert len(result) > 100

    @pytest.mark.asyncio
    async def test_docx_export_with_profile_and_affidavit(self) -> None:
        template = get_template("bail_application")
        profile = COURT_PROFILES["supreme_court"]
        content = "## FACTS\n\nTest content."
        affidavit = "## AFFIDAVIT\n\nI solemnly affirm..."
        result = await export_to_docx(
            content, template, court_profile=profile, affidavit=affidavit
        )
        assert isinstance(result, bytes)
        assert len(result) > 100

    @pytest.mark.asyncio
    async def test_pdf_export_with_sc_profile(self) -> None:
        template = get_template("bail_application")
        profile = COURT_PROFILES["supreme_court"]
        content = "## FACTS\n\nThe accused was arrested."
        result = await export_to_pdf(content, template, court_profile=profile)
        assert isinstance(result, bytes)
        assert len(result) > 100

    @pytest.mark.asyncio
    async def test_pdf_export_with_affidavit(self) -> None:
        template = get_template("bail_application")
        content = "## FACTS\n\nTest."
        affidavit = "## AFFIDAVIT\n\nI affirm..."
        result = await export_to_pdf(content, template, affidavit=affidavit)
        assert isinstance(result, bytes)
        assert len(result) > 100

    @pytest.mark.asyncio
    async def test_export_backwards_compatible_without_profile(self) -> None:
        """Existing callers without court_profile should still work."""
        template = get_template("bail_application")
        content = "## FACTS\n\nTest content."
        result_docx = await export_to_docx(content, template)
        result_pdf = await export_to_pdf(content, template)
        assert isinstance(result_docx, bytes)
        assert isinstance(result_pdf, bytes)

    @pytest.mark.asyncio
    async def test_bombay_hc_uses_legal_paper_size(self) -> None:
        template = get_template("bail_application")
        profile = COURT_PROFILES["bombay_hc"]
        content = "## FACTS\n\nTest."
        # Just verify it doesn't crash with legal paper size
        result = await export_to_pdf(content, template, court_profile=profile)
        assert isinstance(result, bytes)
        assert len(result) > 100
