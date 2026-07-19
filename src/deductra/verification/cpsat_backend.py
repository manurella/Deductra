"""Independent OR-Tools CP-SAT encoding for finite-domain verification."""

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false

from __future__ import annotations

import hashlib
from time import perf_counter_ns
from typing import Any

import ortools
from google.protobuf import text_format
from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model

from deductra.domain.atoms import AssignmentAtom, Atom, ExclusionAtom
from deductra.domain.constraints import (
    AllDifferentConstraint,
    ArithmeticConstraint,
    DomainConstraint,
)
from deductra.domain.puzzle import PuzzleSpec
from deductra.domain.serialization import canonical_sha256
from deductra.reasoning.state import PuzzleState
from deductra.verification.contracts import (
    ProofObligation,
    VerificationCertificate,
    build_certificate,
)
from deductra.verification.encoding import EncodingError, FiniteDomainProblem, prepare_problem
from deductra.verification.logic_equations_cpsat import (
    add_cpsat_arithmetic_constraint,
)
from deductra.verification.logic_grid_cpsat import add_logic_grid_cpsat_constraint

LOGIC_GRID_FAMILY_ID = "logic-grid"
LOGIC_GRID_ENCODING_VERSION = "finite-domain-logic-grid-v1"


class CpSatProofBackend:
    """Verify proof obligations and solution feasibility with integer CP-SAT models."""

    backend_id = "cp-sat"
    backend_version = ortools.__version__
    encoding_version = "finite-domain-arithmetic-v1"

    @staticmethod
    def _add_atom(
        model: cp_model.CpModel,
        atom: Atom,
        problem: FiniteDomainProblem,
        variables: dict[str, cp_model.IntVar],
    ) -> None:
        if isinstance(atom, AssignmentAtom):
            variable = problem.variable(atom.variable_id)
            code = variable.code_for(atom.value_id)
            model.add(variables[atom.variable_id] == code)
            return
        if isinstance(atom, ExclusionAtom):
            variable = problem.variable(atom.variable_id)
            code = variable.code_for(atom.value_id)
            model.add(variables[atom.variable_id] != code)
            return
        raise EncodingError(f"unsupported atom kind {atom.kind!r}")

    def verify(
        self,
        puzzle: PuzzleSpec,
        state: PuzzleState,
        obligation: ProofObligation,
        *,
        timeout_ms: int,
    ) -> VerificationCertificate:
        """Encode independently, solve deterministically, and seal the result."""
        started = perf_counter_ns()
        encoding_version = (
            LOGIC_GRID_ENCODING_VERSION
            if puzzle.identity.family_id == LOGIC_GRID_FAMILY_ID
            else self.encoding_version
        )
        if timeout_ms <= 0:
            return self._invalid(
                obligation, started, "timeout_ms must be positive", encoding_version
            )
        try:
            problem = prepare_problem(puzzle, state, obligation)
            model = cp_model.CpModel()
            variables = {
                item.variable_id: model.new_int_var(
                    0,
                    len(item.value_ids) - 1,
                    f"v_{index}",
                )
                for index, item in enumerate(problem.variables)
            }
            for item in problem.variables:
                variable = variables[item.variable_id]
                for value_id in sorted(set(item.value_ids) - set(item.candidate_ids)):
                    model.add(variable != item.code_for(value_id))

            for constraint in problem.constraints:
                if isinstance(constraint, DomainConstraint):
                    item = problem.variable(constraint.variable_id)
                    disallowed = set(item.value_ids) - set(constraint.allowed_value_ids)
                    for value_id in sorted(disallowed):
                        model.add(variables[item.variable_id] != item.code_for(value_id))
                elif isinstance(constraint, AllDifferentConstraint):
                    model.add_all_different(variables[item] for item in constraint.variable_ids)
                elif isinstance(constraint, ArithmeticConstraint):
                    if problem.family_id == LOGIC_GRID_FAMILY_ID:
                        add_logic_grid_cpsat_constraint(
                            model,
                            constraint,
                            problem,
                            variables,
                        )
                    else:
                        add_cpsat_arithmetic_constraint(
                            model,
                            constraint,
                            problem,
                            variables,
                        )
                else:
                    raise EncodingError(f"unsupported active constraint kind: {constraint.kind}")

            for atom in (*problem.asserted_atoms, *problem.assumptions):
                self._add_atom(model, atom, problem, variables)

            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = timeout_ms / 1000
            solver.parameters.num_search_workers = 1
            solver.parameters.random_seed = 0
            base_status = solver.solve(model)
            if base_status == cp_model.INFEASIBLE:
                return self._invalid(
                    obligation,
                    started,
                    "source puzzle and state are already unsatisfiable",
                    encoding_version,
                )
            if base_status == cp_model.UNKNOWN:
                return build_certificate(
                    backend_id=self.backend_id,
                    backend_version=self.backend_version,
                    encoding_version=encoding_version,
                    obligation_id=obligation.obligation_id,
                    result="unknown",
                    duration_ms=(perf_counter_ns() - started) // 1_000_000,
                    raw_artifact_hash=_model_artifact_hash(model),
                )

            self._add_atom(model, problem.counter_assumption, problem, variables)
            raw_artifact_hash = _model_artifact_hash(model)
            status = solver.solve(model)
            duration_ms = (perf_counter_ns() - started) // 1_000_000
            if status == cp_model.INFEASIBLE:
                result = "unsat"
                snapshot = None
            elif status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
                result = "sat"
                snapshot = {
                    item.variable_id: item.value_for(solver.value(variables[item.variable_id]))
                    for item in problem.variables
                }
            elif status == cp_model.UNKNOWN:
                result = "unknown"
                snapshot = None
            else:
                result = "invalid"
                snapshot = None
            return build_certificate(
                backend_id=self.backend_id,
                backend_version=self.backend_version,
                encoding_version=encoding_version,
                obligation_id=obligation.obligation_id,
                result=result,
                duration_ms=duration_ms,
                model_snapshot=cast_model_snapshot(snapshot),
                raw_artifact_hash=raw_artifact_hash,
            )
        except EncodingError as error:
            return self._invalid(obligation, started, str(error), encoding_version)

    def _invalid(
        self,
        obligation: ProofObligation,
        started: int,
        reason: str,
        encoding_version: str,
    ) -> VerificationCertificate:
        return build_certificate(
            backend_id=self.backend_id,
            backend_version=self.backend_version,
            encoding_version=encoding_version,
            obligation_id=obligation.obligation_id,
            result="invalid",
            duration_ms=(perf_counter_ns() - started) // 1_000_000,
            raw_artifact_hash=canonical_sha256({"encoding_error": reason}),
        )


def cast_model_snapshot(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep external solver scalar types outside the certificate boundary."""
    return value


def _model_artifact_hash(model: cp_model.CpModel) -> str:
    """Hash the deterministic protobuf encoding of one native CP-SAT model."""
    normalized = cp_model_pb2.CpModelProto()
    text_format.Parse(str(model.proto), normalized)
    payload = normalized.SerializeToString(deterministic=True)
    return hashlib.sha256(payload).hexdigest()
