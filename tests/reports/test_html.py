from __future__ import annotations

from deductra.reports.html import JinjaHtmlRenderer, validate_semantic_html
from deductra.reports.model import ReportModel


def test_html_is_semantic_local_and_escaped(report_model: ReportModel) -> None:
    rendered = JinjaHtmlRenderer().render(report_model)
    validate_semantic_html(rendered)
    assert "<main>" in rendered
    assert 'lang="en"' in rendered
    assert "The verified solution is A &lt; B." in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered
    assert report_model.claims[0].text not in rendered


def test_html_contains_every_canonical_section(report_model: ReportModel) -> None:
    rendered = JinjaHtmlRenderer().render(report_model)
    for section in report_model.sections:
        assert f'id="{section.section_id}"' in rendered
