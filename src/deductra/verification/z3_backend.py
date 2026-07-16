"""Independent Z3 encoding for finite-domain proof obligations."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportArgumentType=false, reportReturnType=false, reportAttributeAccessIssue=false

from __future__ import annotations

from time import perf_counter_ns
from typing import Any

import z3

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.constraints import AllDifferentConstraint, DomainConstraint
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.state import PuzzleState
from deductra.verification.contracts import (
    ProofObligation,
    VerificationCertificate,
    build_certificate,
)
from deductra.verification.encoding import EncodingError, FiniteDomainProblem, prepare_problem


class Z3ProofBackend:
    """Verify that a state plus the negated claim is unsatisfiable in Z3."""

    backend_id = "z3"
    backend_version = z3.get_version_string()
    encoding_version = "finite-domain-v1"

    @staticmethod
    def _atom_formula(
        atom: Atom,
        problem: FiniteDomainProblem,
        variables: dict[str, z3.ArithRef],
    ) -> z3.BoolRef:
        if isinstance(atom, AssignmentAtom):
            variable = problem.variable(atom.variable_id)
            code = variable.code_for(atom.value_id)
            return variables[atom.variable_id] == code
        if isinstance(atom, ExclusionAtom):
            variable = problem.variable(atom.variable_id)
            code = variable.code_for(atom.value_id)
            return variables[atom.variable_id] != code
        raise EncodingError(f"unsupported atom kind {atom.kind!r}")

    def verify(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        obligation: ProofObligation,
        *,
        timeout_ms: int,
    ) -> VerificationCertificate:
        """Encode independently, check satisfiability, and seal the result."""
        started = perf_counter_ns()
        if timeout_ms <= 0:
            return self._invalid(obligation, started, "timeout_ms must be positive")
        try:
            problem = prepare_problem(puzzle, state, obligation)
            solver = z3.Solver()
            solver.set(timeout=timeout_ms, unsat_core=True)
            variables = {
                item.variable_id: z3.Int(f"v_{index}")
                for index, item in enumerate(problem.variables)
            }

            def track(formula: z3.BoolRef, reference: str) -> None:
                solver.assert_and_track(formula, z3.Bool(reference))

            for item in problem.variables:
                variable = variables[item.variable_id]
                track(
                    z3.Or(
                        *(variable == item.code_for(value_id) for value_id in item.candidate_ids)
                    ),
                    f"state:candidates:{item.variable_id}",
                )

            for constraint in problem.constraints:
                if isinstance(constraint, DomainConstraint):
                    item = problem.variable(constraint.variable_id)
                    allowed = tuple(
                        item.code_for(value_id) for value_id in constraint.allowed_value_ids
                    )
                    track(
                        z3.Or(*(variables[item.variable_id] == code for code in allowed)),
                        f"constraint:{constraint.constraint_id}",
                    )
                elif isinstance(constraint, AllDifferentConstraint):
                    track(
                        z3.Distinct(*(variables[item] for item in constraint.variable_ids)),
                        f"constraint:{constraint.constraint_id}",
                    )

            for index, atom in enumerate(problem.asserted_atoms):
                track(self._atom_formula(atom, problem, variables), f"state:atom:{index}")
            for index, atom in enumerate(problem.assumptions):
                track(self._atom_formula(atom, problem, variables), f"assumption:{index}")
            track(
                self._atom_formula(problem.counter_assumption, problem, variables),
                "negated_claim",
            )

            raw_artifact_hash = canonical_sha256({"smt2": solver.sexpr()})
            status = solver.check()
            duration_ms = (perf_counter_ns() - started) // 1_000_000
            if status == z3.unsat:
                return build_certificate(
                    backend_id=self.backend_id,
                    backend_version=self.backend_version,
                    encoding_version=self.encoding_version,
                    obligation_id=obligation.obligation_id,
                    result="unsat",
                    duration_ms=duration_ms,
                    unsat_core_refs=tuple(sorted(str(item) for item in solver.unsat_core())),
                    raw_artifact_hash=raw_artifact_hash,
                )
            if status == z3.sat:
                model = solver.model()
                snapshot: dict[str, Any] = {}
                for item in problem.variables:
                    value = model.eval(variables[item.variable_id], model_completion=True).as_long()
                    snapshot[item.variable_id] = item.value_for(value)
                return build_certificate(
                    backend_id=self.backend_id,
                    backend_version=self.backend_version,
                    encoding_version=self.encoding_version,
                    obligation_id=obligation.obligation_id,
                    result="sat",
                    duration_ms=duration_ms,
                    model_snapshot=snapshot,
                    raw_artifact_hash=raw_artifact_hash,
                )
            return build_certificate(
                backend_id=self.backend_id,
                backend_version=self.backend_version,
                encoding_version=self.encoding_version,
                obligation_id=obligation.obligation_id,
                result="unknown",
                duration_ms=duration_ms,
                raw_artifact_hash=raw_artifact_hash,
            )
        except EncodingError as error:
            return self._invalid(obligation, started, str(error))

    def _invalid(
        self,
        obligation: ProofObligation,
        started: int,
        reason: str,
    ) -> VerificationCertificate:
        return build_certificate(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            encoding_version=self.encoding_version,
            obligation_id=obligation.obligation_id,
            result="invalid",
            duration_ms=(perf_counter_ns() - started) // 1_000_000,
            raw_artifact_hash=canonical_sha256({"encoding_error": reason}),
        )
