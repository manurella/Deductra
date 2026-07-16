from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from deductra.reports.model import ReportModel
from deductra.reports.schema import rendered_report_model_json_schema
from deductra.verification.contracts import VerificationStatus

from .conftest import make_report

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_report_round_trips_canonically(report_model: ReportModel) -> None:
    restored = ReportModel.model_validate_json(report_model.model_dump_json())
    assert restored == report_model
    assert restored.facts_hash == report_model.facts_hash


def test_checked_in_schema_matches_report_contract() -> None:
    schema_path = REPOSITORY_ROOT / "schemas" / "report-model-v1.schema.json"
    assert schema_path.read_text(encoding="utf-8") == rendered_report_model_json_schema()


def test_evidence_closure_rejects_unaccepted_evidence() -> None:
    with pytest.raises(ValidationError, match="unaccepted evidence"):
        make_report(evidence_status=VerificationStatus.INCONCLUSIVE)


def test_evidence_closure_rejects_dangling_claim_reference() -> None:
    with pytest.raises(ValidationError, match="missing evidence"):
        make_report(claim_evidence_id="evidence:missing")


def test_theme_isolation_preserves_facts_identity() -> None:
    first = make_report(theme_id="theme:light")
    second = make_report(theme_id="theme:high-contrast")
    assert first.facts_hash == second.facts_hash
    assert first.report_hash != second.report_hash
    assert first.claims == second.claims
    assert first.evidence == second.evidence
