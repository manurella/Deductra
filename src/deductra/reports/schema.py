"""Canonical JSON Schema export for the report contract."""

from __future__ import annotations

import json
from typing import Any

from deductra.reports.model import ReportModel


def report_model_json_schema() -> dict[str, Any]:
    return ReportModel.model_json_schema()


def rendered_report_model_json_schema() -> str:
    return json.dumps(report_model_json_schema(), indent=2, sort_keys=True) + "\n"
