from __future__ import annotations

import hashlib
from typing import Any

import pytest

from deductra.reports.model import (
    REQUIRED_SECTION_ORDER,
    AttachmentSpec,
    ClaimKind,
    EvidenceReference,
    ReportClaim,
    ReportDepth,
    ReportIdentity,
    ReportModel,
    ReportProvenance,
    ReportSection,
    ReportTheme,
    ReportType,
    SectionApplicability,
    SectionKind,
    VisualKind,
    VisualSpec,
    seal_report,
)
from deductra.verification.contracts import VerificationStatus

HASH = "1" * 64
EVENT_ID = "event:accepted:1"
EVIDENCE_ID = "evidence:solution:1"
ATTACHMENT_CONTENT = b'{"solution":"A"}\n'


def make_report(
    *,
    theme_id: str = "theme:default",
    evidence_status: VerificationStatus = VerificationStatus.CROSS_VERIFIED,
    evidence_id: str = EVIDENCE_ID,
    claim_evidence_id: str | None = None,
    include_attachment: bool = True,
) -> ReportModel:
    claim = ReportClaim(
        claim_id="claim:solution:1",
        kind=ClaimKind.FACTUAL,
        text="The verified solution is A < B.",
        evidence_ids=(claim_evidence_id or evidence_id,),
    )
    visual = VisualSpec(
        visual_id="visual:timeline:1",
        kind=VisualKind.TIMELINE,
        title="Verified reasoning timeline",
        data={"steps": ["clue", "deduction", "solution"]},
        source_event_ids=(EVENT_ID,),
        alt_text="Three ordered steps lead from the clue to the verified solution.",
    )
    sections = tuple(
        ReportSection(
            section_id=f"section-{kind.value}",
            kind=kind,
            title=kind.value.replace("_", " ").title(),
            applicability=(
                SectionApplicability.INCLUDED
                if kind in {SectionKind.OVERVIEW, SectionKind.SOLUTION}
                else SectionApplicability.NOT_APPLICABLE
            ),
            claim_ids=(claim.claim_id,) if kind is SectionKind.SOLUTION else (),
            visual_ids=(visual.visual_id,) if kind is SectionKind.OVERVIEW else (),
        )
        for kind in REQUIRED_SECTION_ORDER
    )
    attachments = (
        (
            AttachmentSpec(
                filename="solution-evidence.json",
                media_type="application/json",
                relationship="Data",
                description="Canonical solution evidence.",
                content_hash=hashlib.sha256(ATTACHMENT_CONTENT).hexdigest(),
                schema_version="1.0.0",
                evidence_ids=(EVIDENCE_ID,),
            ),
        )
        if include_attachment
        else ()
    )
    values: dict[str, Any] = {
        "report_id": "report:1",
        "report_type": ReportType.SOLVE,
        "depth": ReportDepth.STANDARD,
        "identity": ReportIdentity(
            title="Verified Deduction Report",
            subject_id="puzzle:1",
            language="en",
            created_at="2026-07-16T00:00:00Z",
        ),
        "sections": sections,
        "claims": (claim,),
        "visuals": (visual,),
        "evidence": (
            EvidenceReference(
                evidence_id=evidence_id,
                evidence_kind="verification_record",
                verification_status=evidence_status,
                content_hash=HASH,
            ),
        ),
        "attachments": attachments,
        "theme": ReportTheme(
            theme_id=theme_id,
            version="1.0.0",
            stylesheet_hash="2" * 64,
        ),
        "provenance": ReportProvenance(
            producer="Deductra",
            producer_version="0.0.0",
            source_event_ids=(EVENT_ID,),
        ),
    }
    return seal_report(**values)


@pytest.fixture
def report_model() -> ReportModel:
    return make_report()
