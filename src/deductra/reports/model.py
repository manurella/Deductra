"""Authoritative, renderer-neutral report contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal, Self, cast

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator

from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import (
    EventId,
    EvidenceId,
    ReportClaimId,
    ReportId,
    ReportSectionId,
    ThemeId,
    VisualSpecId,
)
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.events import Sha256Digest
from deductra.verification.contracts import VerificationStatus


class ReportType(StrEnum):
    SOLVE = "solve"
    AUDIT = "audit"
    LEARNING = "learning"


class ReportDepth(StrEnum):
    SUMMARY = "summary"
    STANDARD = "standard"
    DETAILED = "detailed"


class SectionKind(StrEnum):
    COVER = "cover"
    VERIFICATION_SNAPSHOT = "verification_snapshot"
    CONTENTS = "contents"
    OVERVIEW = "overview"
    ORIGINAL_PUZZLE = "original_puzzle"
    FORMAL_MODEL = "formal_model"
    STRATEGY_MAP = "strategy_map"
    REASONING_TRACE = "reasoning_trace"
    CONTRADICTION = "contradiction"
    SOLUTION = "solution"
    ALTERNATIVE_ROUTE = "alternative_route"
    TECHNIQUE = "technique"
    DIFFICULTY = "difficulty"
    PERFORMANCE = "performance"
    LEARNING = "learning"
    HYPERGRAPH = "hypergraph"
    PROVENANCE = "provenance"
    GLOSSARY = "glossary"
    ATTACHMENT_INDEX = "attachment_index"


REQUIRED_SECTION_ORDER = tuple(SectionKind)


class SectionApplicability(StrEnum):
    INCLUDED = "included"
    NOT_APPLICABLE = "not_applicable"


class ClaimKind(StrEnum):
    FACTUAL = "factual"
    NARRATIVE = "narrative"


class VisualKind(StrEnum):
    GRID = "grid"
    CANDIDATE_MATRIX = "candidate_matrix"
    ASSOCIATION_GRID = "association_grid"
    ORDERED_STRIP = "ordered_strip"
    DEPENDENCY_GRAPH = "dependency_graph"
    HYPERGRAPH = "hypergraph"
    TIMELINE = "timeline"
    METRIC_CARD = "metric_card"


class EvidenceReference(DomainModel):
    evidence_id: EvidenceId
    evidence_kind: str
    verification_status: VerificationStatus
    content_hash: Sha256Digest


class ReportClaim(DomainModel):
    claim_id: ReportClaimId
    kind: ClaimKind
    text: str = Field(min_length=1)
    evidence_ids: tuple[EvidenceId, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_policy(self) -> Self:
        if self.kind is ClaimKind.FACTUAL and not self.evidence_ids:
            raise ValueError("factual report claims require evidence")
        if self.kind is ClaimKind.NARRATIVE and self.evidence_ids:
            raise ValueError("narrative report claims cannot carry factual evidence")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("claim evidence identifiers must be unique")
        return self


class VisualSpec(DomainModel):
    visual_id: VisualSpecId
    kind: VisualKind
    title: str = Field(min_length=1)
    data: Mapping[str, JsonValue]
    source_event_ids: tuple[EventId, ...] = ()
    alt_text: str | None = None
    long_description: str | None = None
    decorative: bool = False

    @field_validator("data", mode="after")
    @classmethod
    def freeze_data(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return cast(Mapping[str, JsonValue], freeze_json(value))

    @field_serializer("data")
    def serialize_data(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        return cast(dict[str, Any], thaw_json(value))

    @model_validator(mode="after")
    def validate_accessibility(self) -> Self:
        if self.decorative:
            if self.alt_text or self.long_description:
                raise ValueError("decorative visuals must not expose alternative text")
            return self
        if not self.alt_text:
            raise ValueError("informative visuals require alternative text")
        if not self.source_event_ids:
            raise ValueError("informative visuals require source events")
        if self.kind in {VisualKind.DEPENDENCY_GRAPH, VisualKind.HYPERGRAPH} and not (
            self.long_description
        ):
            raise ValueError("complex graph visuals require a long description")
        return self


class ReportSection(DomainModel):
    section_id: ReportSectionId
    kind: SectionKind
    title: str = Field(min_length=1)
    applicability: SectionApplicability
    claim_ids: tuple[ReportClaimId, ...] = ()
    visual_ids: tuple[VisualSpecId, ...] = ()

    @model_validator(mode="after")
    def validate_applicability(self) -> Self:
        if self.applicability is SectionApplicability.NOT_APPLICABLE and (
            self.claim_ids or self.visual_ids
        ):
            raise ValueError("not-applicable sections cannot contain claims or visuals")
        return self


class ReportTheme(DomainModel):
    theme_id: ThemeId
    version: str = Field(min_length=1)
    stylesheet_hash: Sha256Digest
    asset_hashes: tuple[Sha256Digest, ...] = ()


class AttachmentSpec(DomainModel):
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1)
    relationship: Literal["Source", "Data", "Supplement", "Alternative"]
    description: str = Field(min_length=1)
    content_hash: Sha256Digest
    schema_version: str = Field(min_length=1)
    evidence_ids: tuple[EvidenceId, ...]

    @model_validator(mode="after")
    def validate_attachment(self) -> Self:
        if "/" in self.filename or "\\" in self.filename or self.filename in {".", ".."}:
            raise ValueError("attachment filename must be a safe basename")
        if not self.evidence_ids:
            raise ValueError("evidence attachments must reference evidence")
        return self


class ReportIdentity(DomainModel):
    title: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
    created_at: str = Field(min_length=1)


class ReportProvenance(DomainModel):
    producer: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)
    source_event_ids: tuple[EventId, ...]


class ReportModel(DomainModel):
    """Single authoritative report representation; outputs are derived artifacts."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    report_id: ReportId
    report_type: ReportType
    depth: ReportDepth
    identity: ReportIdentity
    sections: tuple[ReportSection, ...]
    claims: tuple[ReportClaim, ...]
    visuals: tuple[VisualSpec, ...]
    evidence: tuple[EvidenceReference, ...]
    attachments: tuple[AttachmentSpec, ...] = ()
    theme: ReportTheme
    provenance: ReportProvenance
    facts_hash: Sha256Digest
    report_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(section.kind for section in self.sections) != REQUIRED_SECTION_ORDER:
            raise ValueError("report sections must contain the complete canonical catalog in order")
        _require_unique(self.sections, "section_id")
        _require_unique(self.claims, "claim_id")
        _require_unique(self.visuals, "visual_id")
        _require_unique(self.evidence, "evidence_id")
        claim_ids = {item.claim_id for item in self.claims}
        visual_ids = {item.visual_id for item in self.visuals}
        referenced_claims = tuple(item for section in self.sections for item in section.claim_ids)
        referenced_visuals = tuple(item for section in self.sections for item in section.visual_ids)
        if set(referenced_claims) != claim_ids or len(referenced_claims) != len(claim_ids):
            raise ValueError("every report claim must be referenced exactly by the section catalog")
        if set(referenced_visuals) != visual_ids or len(referenced_visuals) != len(visual_ids):
            raise ValueError("every visual must be referenced exactly by the section catalog")
        validate_evidence_closure(self)
        if self.facts_hash != compute_facts_hash(self):
            raise ValueError("facts_hash does not match renderer-neutral report facts")
        if self.report_hash != compute_report_hash(self):
            raise ValueError("report_hash does not match the complete report model")
        return self


def _require_unique(items: tuple[DomainModel, ...], attribute: str) -> None:
    values = tuple(getattr(item, attribute) for item in items)
    if len(values) != len(set(values)):
        raise ValueError(f"{attribute} values must be unique")


def validate_evidence_closure(report: ReportModel) -> None:
    """Reject dangling, unverified, or incomplete evidence relationships."""
    evidence = {item.evidence_id: item for item in report.evidence}
    accepted = {
        VerificationStatus.STRUCTURALLY_VALID,
        VerificationStatus.BACKEND_VERIFIED,
        VerificationStatus.CROSS_VERIFIED,
    }
    for claim in report.claims:
        for evidence_id in claim.evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                raise ValueError(f"claim {claim.claim_id} references missing evidence")
            if item.verification_status not in accepted:
                raise ValueError(f"claim {claim.claim_id} references unaccepted evidence")
    provenance_events = set(report.provenance.source_event_ids)
    for visual in report.visuals:
        if not set(visual.source_event_ids) <= provenance_events:
            raise ValueError(f"visual {visual.visual_id} references unknown source events")
    for attachment in report.attachments:
        if not set(attachment.evidence_ids) <= evidence.keys():
            raise ValueError(f"attachment {attachment.filename} references missing evidence")
        if any(
            evidence[item].verification_status not in accepted for item in attachment.evidence_ids
        ):
            raise ValueError(f"attachment {attachment.filename} references unaccepted evidence")


def compute_facts_hash(report: ReportModel) -> str:
    """Hash report facts while excluding presentation theme and self-digests."""
    return canonical_sha256(
        report.model_dump(
            mode="json",
            exclude={"theme", "facts_hash", "report_hash"},
        )
    )


def compute_report_hash(report: ReportModel) -> str:
    return canonical_sha256(report.model_dump(mode="json", exclude={"report_hash"}))


def seal_report(**values: Any) -> ReportModel:
    """Build a report and calculate its facts and complete-model hashes."""
    unsigned = ReportModel.model_construct(**values, facts_hash="0" * 64, report_hash="0" * 64)
    facts_hash = compute_facts_hash(unsigned)
    with_facts = ReportModel.model_construct(**values, facts_hash=facts_hash, report_hash="0" * 64)
    return ReportModel(**values, facts_hash=facts_hash, report_hash=compute_report_hash(with_facts))
