"""Validated identifier aliases used by the common domain boundary."""

from typing import Annotated

from pydantic import StringConstraints

type Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

type PuzzleId = Identifier
type PuzzleRevisionId = Identifier
type VariableId = Identifier
type ValueId = Identifier
type DomainId = Identifier
type ConstraintId = Identifier
type ClueId = Identifier
type GenerationId = Identifier
type ProvenanceId = Identifier
type EventId = Identifier
type TraceId = Identifier
type AttemptId = Identifier
type BranchId = Identifier
type ProducerId = Identifier
type CorrelationId = Identifier
type CausationId = Identifier
type StateId = Identifier
type SnapshotId = Identifier
type ContradictionId = Identifier
type ObligationId = Identifier
type CertificateId = Identifier
type RuleId = Identifier
type RuleCandidateId = Identifier
type GraphVertexId = Identifier
type HyperedgeId = Identifier
