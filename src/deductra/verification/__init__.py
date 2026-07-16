"""Proof obligations, independent backends, and cross-verification authority."""

from deductra.verification.contracts import (
    AssignmentNegation,
    EliminationNegation,
    ProofObligation,
    VerificationBackend,
    VerificationCertificate,
    VerificationDecision,
    VerificationRecord,
    VerificationStatus,
)
from deductra.verification.coordinator import (
    CrossVerificationCoordinator,
    VerificationRejectedError,
    apply_verified_event,
)
from deductra.verification.cpsat_backend import CpSatProofBackend
from deductra.verification.z3_backend import Z3ProofBackend

__all__ = [
    "AssignmentNegation",
    "CpSatProofBackend",
    "CrossVerificationCoordinator",
    "EliminationNegation",
    "ProofObligation",
    "VerificationBackend",
    "VerificationCertificate",
    "VerificationDecision",
    "VerificationRecord",
    "VerificationRejectedError",
    "VerificationStatus",
    "Z3ProofBackend",
    "apply_verified_event",
]
