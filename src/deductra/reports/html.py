"""Semantic HTML derivation and structural accessibility checks."""

from __future__ import annotations

from html.parser import HTMLParser
from importlib.resources import files
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from deductra.domain.serialization import canonical_json
from deductra.reports.model import ReportModel


@runtime_checkable
class HtmlRenderer(Protocol):
    def render(self, report: ReportModel) -> str:
        """Derive semantic HTML without changing or inventing report claims."""
        ...


class JinjaHtmlRenderer:
    """Strict, autoescaped renderer over packaged local templates."""

    def __init__(self) -> None:
        self._environment = Environment(
            loader=PackageLoader("deductra.reports"),
            autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=True),
            undefined=StrictUndefined,
            enable_async=False,
        )
        self._environment.filters["canonical_json"] = canonical_json

    def render(self, report: ReportModel) -> str:
        stylesheet = (
            files("deductra.reports").joinpath("styles/report.css").read_text(encoding="utf-8")
        )
        template = self._environment.get_template("report.html")
        rendered = template.render(report=report, stylesheet=stylesheet)
        validate_semantic_html(rendered)
        return rendered


class _SemanticAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.language: str | None = None
        self.main_count = 0
        self.h1_count = 0
        self.heading_levels: list[int] = []
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.links: list[str] = []
        self.remote_urls: list[str] = []
        self.figures = 0
        self.figcaptions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.language = values.get("lang")
        elif tag == "main":
            self.main_count += 1
        elif tag == "h1":
            self.h1_count += 1
            self.heading_levels.append(1)
        elif tag in {"h2", "h3", "h4", "h5", "h6"}:
            self.heading_levels.append(int(tag[1]))
        elif tag == "figure":
            self.figures += 1
        elif tag == "figcaption":
            self.figcaptions += 1
        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        for attribute in ("href", "src"):
            url = values.get(attribute)
            if not url:
                continue
            if url.startswith("#"):
                self.links.append(url[1:])
            elif urlparse(url).scheme or url.startswith("//"):
                self.remote_urls.append(url)


def validate_semantic_html(document: str) -> None:
    """Fail closed on the accessibility structure guaranteed before PDF conversion."""
    audit = _SemanticAudit()
    audit.feed(document)
    if not audit.language:
        raise ValueError("report HTML must declare a document language")
    if audit.main_count != 1 or audit.h1_count != 1:
        raise ValueError("report HTML must contain exactly one main landmark and one h1")
    if audit.duplicate_ids:
        raise ValueError("report HTML contains duplicate element identifiers")
    if set(audit.links) - audit.ids:
        raise ValueError("report HTML contains dangling internal links")
    if audit.remote_urls:
        raise ValueError("report HTML cannot reference remote resources")
    if audit.figures != audit.figcaptions:
        raise ValueError("every report figure must have a caption")
    for previous, current in zip(audit.heading_levels, audit.heading_levels[1:], strict=False):
        if current > previous + 1:
            raise ValueError("report HTML cannot skip heading levels")
