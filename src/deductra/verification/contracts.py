"""Backend-neutral proof obligations, certificates, and verification decisions."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, Literal, Protocol, Self, cast, runtime_checkable

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.base import DomainModel, freeze_json, thaw_json
from deductra.domain.ids import (
    CertificateId,
    ObligationId,
    PuzzleRevisionId,
    ValueId,
    VariableId,
)
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_json, canonical_sha256
from deductra.reasoning.events import Sha256Digest
from deductra.reasoning.state import PuzzleState


class VerificationStatus(StrEnum):
    """Authority level assigned to one proof decision."""

    NOT_CHECKED = "not_checked"
    STRUCTURALLY_VALID = "structurally_valid"
    BACKEND_VERIFIED = "backend_verified"
    CROSS_VERIFIED = "cross_verified"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    QUARANTINED = "quarantined"


class AssignmentNegation(DomainModel):
    """Counter-assume that a claimed assignment is false."""

    kind: Literal["assignment_negation"] = "assignment_negation"
    variable_id: VariableId
    value_id: ValueId


class EliminationNegation(DomainModel):
    """Counter-assume that a claimed eliminated value is possible."""

    kind: Literal["elimination_negation"] = "elimination_negation"
    variable_id: VariableId
    value_id: ValueId


type NegatedClaim = Annotated[
    AssignmentNegation | EliminationNegation,
    Field(discriminator="kind"),
]


class ProofObligation(DomainModel):
    """One claim whose negation must be unsatisfiable in the named source state."""

    obligation_id: ObligationId
    puzzle_revision_id: PuzzleRevisionId
    source_state_hash: Sha256Digest
    assumptions: tuple[Atom, ...] = ()
    claimed_conclusions: tuple[Atom, ...]
    negated_claim: NegatedClaim
    expected_result: Literal["unsat"] = "unsat"
    encoding_version: str = "1.0.0"

    @model_validator(mode="after")
    def validate_claim_contract(self) -> ProofObligation:
        if len(self.claimed_conclusions) != 1:
            raise ValueError("CR-004 proof obligations require exactly one conclusion")
        if len({canonical_json(atom) for atom in self.assumptions}) != len(self.assumptions):
            raise ValueError("proof assumptions must be unique")
        conclusion = self.claimed_conclusions[0]
        if isinstance(conclusion, AssignmentAtom):
            expected = AssignmentNegation(
                variable_id=conclusion.variable_id,
                value_id=conclusion.value_id,
            )
        elif isinstance(conclusion, ExclusionAtom):
            expected = EliminationNegation(
                variable_id=conclusion.variable_id,
                value_id=conclusion.value_id,
            )
        else:
            raise ValueError("CR-004 supports assignment and elimination conclusions only")
        if self.negated_claim != expected:
            raise ValueError("negated_claim must be the logical negation of the conclusion")
        return self


type BackendResult = Literal["sat", "unsat", "unknown", "invalid"]


class VerificationCertificate(DomainModel):
    """Immutable result and provenance returned by one verification backend."""

    certificate_id: CertificateId
    backend_id: str
    backend_version: str
    encoding_version: str
    obligation_id: ObligationId
    result: BackendResult
    duration_ms: Annotated[int, Field(ge=0)]
    unsat_core_refs: tuple[str, ...] = ()
    model_snapshot: Mapping[str, JsonValue] | None = None
    raw_artifact_hash: Sha256Digest | None = None
    certificate_hash: Sha256Digest

    @field_validator("model_snapshot", mode="after")
    @classmethod
    def freeze_model_snapshot(
        cls,
        value: Mapping[str, JsonValue] | None,
    ) -> Mapping[str, JsonValue] | None:
        if value is None:
            return None
        return cast(Mapping[str, JsonValue], freeze_json(value))

    @field_serializer("model_snapshot")
    def serialize_model_snapshot(
        self,
        value: Mapping[str, JsonValue] | None,
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return cast(dict[str, Any], thaw_json(value))

    @model_validator(mode="after")
    def validate_evidence_shape(self) -> VerificationCertificate:
        if self.unsat_core_refs and self.result != "unsat":
            raise ValueError("unsat cores are valid only for unsat certificates")
        if self.model_snapshot is not None and self.result != "sat":
            raise ValueError("model snapshots are valid only for sat certificates")
        if self.certificate_hash != compute_certificate_hash(self):
            raise ValueError("certificate_hash does not match canonical certificate contents")
        return self


class VerificationDecision(DomainModel):
    """Coordinator outcome controlling whether a state change may be applied."""

    obligation_id: ObligationId
    status: VerificationStatus
    certificates: tuple[VerificationCertificate, ...] = ()
    reason: str

    @model_validator(mode="after")
    def validate_decision(self) -> VerificationDecision:
        if any(item.obligation_id != self.obligation_id for item in self.certificates):
            raise ValueError("all certificates must reference the decision obligation")
        if len({item.backend_id for item in self.certificates}) != len(self.certificates):
            raise ValueError("a decision cannot contain duplicate backend certificates")
        results = {item.result for item in self.certificates}
        if self.status in {
            VerificationStatus.BACKEND_VERIFIED,
            VerificationStatus.CROSS_VERIFIED,
        } and (not self.certificates or results != {"unsat"}):
            raise ValueError("verified decisions require only unsat certificates")
        if self.status is VerificationStatus.QUARANTINED and not {"sat", "unsat"} <= results:
            raise ValueError("quarantine requires conflicting sat and unsat certificates")
        return self

    @property
    def accepted(self) -> bool:
        """Return whether the decision grants reducer authority."""
        return self.status in {
            VerificationStatus.BACKEND_VERIFIED,
            VerificationStatus.CROSS_VERIFIED,
        }


class VerificationRecord(DomainModel):
    """Public serialized verification contract for one obligation and decision."""

    obligation: ProofObligation
    decision: VerificationDecision

    @model_validator(mode="after")
    def match_identity(self) -> Self:
        if self.obligation.obligation_id != self.decision.obligation_id:
            raise ValueError("verification record identities must match")
        return self


@runtime_checkable
class VerificationBackend(Protocol):
    """Port implemented independently by every proof backend."""

    backend_id: str
    backend_version: str
    encoding_version: str

    def verify(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        obligation: ProofObligation,
        *,
        timeout_ms: int,
    ) -> VerificationCertificate:
        """Check one obligation without mutating puzzle state."""
        ...


def compute_obligation_hash(obligation: ProofObligation) -> str:
    """Return the canonical digest of a complete proof obligation."""
    return canonical_sha256(obligation)


def compute_certificate_hash(certificate: VerificationCertificate) -> str:
    """Hash every certificate field except its self-digest."""
    return canonical_sha256(certificate.model_dump(mode="json", exclude={"certificate_hash"}))


def build_certificate(
    *,
    backend_id: str,
    backend_version: str,
    encoding_version: str,
    obligation_id: ObligationId,
    result: BackendResult,
    duration_ms: int,
    unsat_core_refs: tuple[str, ...] = (),
    model_snapshot: Mapping[str, JsonValue] | None = None,
    raw_artifact_hash: str | None = None,
) -> VerificationCertificate:
    """Seal one backend result into an integrity-protected certificate."""
    identity_digest = canonical_sha256(
        {
            "backend_id": backend_id,
            "encoding_version": encoding_version,
            "obligation_id": obligation_id,
            "raw_artifact_hash": raw_artifact_hash,
            "result": result,
        }
    )
    certificate_id = f"deductra:certificate:{identity_digest}"
    unsigned = VerificationCertificate.model_construct(
        certificate_id=certificate_id,
        backend_id=backend_id,
        backend_version=backend_version,
        encoding_version=encoding_version,
        obligation_id=obligation_id,
        result=result,
        duration_ms=duration_ms,
        unsat_core_refs=unsat_core_refs,
        model_snapshot=model_snapshot,
        raw_artifact_hash=raw_artifact_hash,
        certificate_hash="0" * 64,
    )
    return VerificationCertificate(
        certificate_id=certificate_id,
        backend_id=backend_id,
        backend_version=backend_version,
        encoding_version=encoding_version,
        obligation_id=obligation_id,
        result=result,
        duration_ms=duration_ms,
        unsat_core_refs=unsat_core_refs,
        model_snapshot=model_snapshot,
        raw_artifact_hash=raw_artifact_hash,
        certificate_hash=compute_certificate_hash(unsigned),
    )
