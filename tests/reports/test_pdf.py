from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from deductra.reports.html import JinjaHtmlRenderer
from deductra.reports.model import ReportModel
from deductra.reports.pdf import (
    AttachmentPayload,
    ConformanceStatus,
    PdfOutputProfile,
    WeasyPrintPdfRenderer,
)

from .conftest import ATTACHMENT_CONTENT


def _native_renderer_available() -> bool:
    try:
        import_module("weasyprint")
    except OSError:
        return False
    return True


requires_native_renderer = pytest.mark.skipif(
    not _native_renderer_available(),
    reason="WeasyPrint native libraries are not available on this host",
)


def test_attachment_payload_rejects_tampering(report_model: ReportModel) -> None:
    with pytest.raises(ValueError, match="hash mismatch"):
        AttachmentPayload(report_model.attachments[0], b"tampered")


@pytest.mark.parametrize(
    ("profile", "target"),
    [
        (PdfOutputProfile.STANDARD, None),
        (PdfOutputProfile.ACCESSIBLE, "PDF/UA-2"),
    ],
)
@requires_native_renderer
def test_pdf_smoke(
    report_model: ReportModel,
    tmp_path: Path,
    profile: PdfOutputProfile,
    target: str | None,
) -> None:
    destination = tmp_path / f"{profile.value}.pdf"
    result = WeasyPrintPdfRenderer(JinjaHtmlRenderer()).render(
        report_model,
        destination,
        profile=profile,
    )
    assert destination.read_bytes().startswith(b"%PDF")
    assert result.page_count >= 1
    assert result.target_standard == target
    assert result.conformance_status is ConformanceStatus.NOT_CHECKED
    assert result.attachment_filenames == ()


@requires_native_renderer
def test_archive_pdf_embeds_declared_attachment(
    report_model: ReportModel,
    tmp_path: Path,
) -> None:
    payload = AttachmentPayload(report_model.attachments[0], ATTACHMENT_CONTENT)
    result = WeasyPrintPdfRenderer(JinjaHtmlRenderer()).render(
        report_model,
        tmp_path / "archive.pdf",
        profile=PdfOutputProfile.ARCHIVE,
        attachments=(payload,),
    )
    assert result.target_standard == "PDF/A-4f"
    assert result.conformance_status is ConformanceStatus.NOT_CHECKED
    assert result.attachment_filenames == ("solution-evidence.json",)
