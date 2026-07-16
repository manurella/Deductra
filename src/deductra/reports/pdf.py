"""PDF renderer port and WeasyPrint adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from deductra.reports.html import HtmlRenderer
from deductra.reports.model import AttachmentSpec, ReportModel


class PdfOutputProfile(StrEnum):
    STANDARD = "standard"
    ACCESSIBLE = "accessible"
    ARCHIVE = "archive"


class ConformanceStatus(StrEnum):
    NOT_CHECKED = "not_checked"


@dataclass(frozen=True, slots=True)
class AttachmentPayload:
    spec: AttachmentSpec
    content: bytes

    def __post_init__(self) -> None:
        if hashlib.sha256(self.content).hexdigest() != self.spec.content_hash:
            raise ValueError(f"attachment hash mismatch for {self.spec.filename}")


@dataclass(frozen=True, slots=True)
class PdfRenderResult:
    renderer: str
    renderer_version: str
    profile: PdfOutputProfile
    target_standard: str | None
    conformance_status: ConformanceStatus
    output_hash: str
    page_count: int
    attachment_filenames: tuple[str, ...]


@runtime_checkable
class PdfRenderer(Protocol):
    def render(
        self,
        report: ReportModel,
        destination: Path,
        *,
        profile: PdfOutputProfile,
        attachments: tuple[AttachmentPayload, ...] = (),
    ) -> PdfRenderResult:
        """Derive a PDF without granting it unverified conformance status."""
        ...


class WeasyPrintPdfRenderer:
    """Pinned WeasyPrint adapter with local-only resource loading."""

    def __init__(self, html_renderer: HtmlRenderer) -> None:
        self._html_renderer = html_renderer

    def render(
        self,
        report: ReportModel,
        destination: Path,
        *,
        profile: PdfOutputProfile,
        attachments: tuple[AttachmentPayload, ...] = (),
    ) -> PdfRenderResult:
        expected = {item.filename: item for item in report.attachments}
        supplied = {item.spec.filename: item for item in attachments}
        if len(supplied) != len(attachments):
            raise ValueError("attachment payload filenames must be unique")
        if profile is PdfOutputProfile.ARCHIVE:
            if supplied.keys() != expected.keys():
                raise ValueError("archive PDF requires every declared evidence attachment")
        elif attachments:
            raise ValueError("attachments are supported only by the archive profile")
        for filename, payload in supplied.items():
            if payload.spec != expected[filename]:
                raise ValueError(f"attachment metadata mismatch for {filename}")

        weasyprint = import_module("weasyprint")
        html_type = weasyprint.HTML
        attachment_type = weasyprint.Attachment
        html = self._html_renderer.render(report)
        document = html_type(string=html, url_fetcher=_deny_external_fetch).render()
        destination.parent.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {"pdf_tags": True}
        target_standard: str | None = None
        if profile is PdfOutputProfile.ACCESSIBLE:
            target_standard = "PDF/UA-2"
            options["pdf_variant"] = "pdf/ua-2"
        elif profile is PdfOutputProfile.ARCHIVE:
            target_standard = "PDF/A-4f"
            options["pdf_variant"] = "pdf/a-4f"
            options["attachments"] = [
                attachment_type(
                    file_obj=BytesIO(item.content),
                    name=item.spec.filename,
                    description=item.spec.description,
                    relationship=item.spec.relationship,
                )
                for item in attachments
            ]
        document.write_pdf(destination, **options)
        output = destination.read_bytes()
        return PdfRenderResult(
            renderer="WeasyPrint",
            renderer_version=cast(str, weasyprint.__version__),
            profile=profile,
            target_standard=target_standard,
            conformance_status=ConformanceStatus.NOT_CHECKED,
            output_hash=hashlib.sha256(output).hexdigest(),
            page_count=len(document.pages),
            attachment_filenames=tuple(supplied),
        )


def _deny_external_fetch(url: str, *_args: object, **_kwargs: object) -> Any:
    raise ValueError(f"external resource fetch denied: {url}")
