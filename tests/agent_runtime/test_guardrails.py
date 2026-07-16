from __future__ import annotations

from deductra.agents.contracts import (
    AgentClaim,
    AgentClaimKind,
    AgentClaimMethod,
    AgentCommandKind,
    AgentCommandProposal,
    AgentOutput,
    GuardrailCode,
    GuardrailOutcome,
)
from deductra.agents.guardrails import validate_agent_output, validate_agent_request
from deductra.verification.contracts import VerificationStatus

from .conftest import EVIDENCE_ID, make_context, make_policy, make_request


def _codes(output: AgentOutput) -> set[GuardrailCode]:
    report = validate_agent_output(
        output,
        make_request(),
        make_context(),
        make_policy(),
    )
    return {item.code for item in report.findings}


def test_unknown_evidence_is_rejected() -> None:
    output = AgentOutput(
        claims=(
            AgentClaim(
                claim_id="claim:1",
                kind=AgentClaimKind.FACTUAL,
                method=AgentClaimMethod.DETERMINISTIC_EVIDENCE,
                text="A factual claim.",
                evidence_ids=("evidence:missing",),
            ),
        ),
    )
    assert GuardrailCode.UNKNOWN_EVIDENCE in _codes(output)


def test_uncited_report_fact_is_rejected() -> None:
    output = AgentOutput(
        claims=(
            AgentClaim(
                claim_id="claim:report:1",
                kind=AgentClaimKind.REPORT_FACT,
                method=AgentClaimMethod.DETERMINISTIC_EVIDENCE,
                text="An unsupported report statement.",
            ),
        ),
    )
    assert GuardrailCode.UNCITED_FACT in _codes(output)


def test_agent_cannot_request_canonical_state_mutation() -> None:
    output = AgentOutput(
        commands=(
            AgentCommandProposal(
                kind=AgentCommandKind.COMMIT_SOLUTION,
                rationale="Bypass deterministic verification.",
                evidence_ids=(EVIDENCE_ID,),
            ),
        ),
    )
    assert GuardrailCode.ATTEMPTED_STATE_MUTATION in _codes(output)


def test_verified_solution_can_only_be_presented_with_deterministic_evidence() -> None:
    output = AgentOutput(
        claims=(
            AgentClaim(
                claim_id="claim:solution:1",
                kind=AgentClaimKind.SOLUTION,
                method=AgentClaimMethod.DETERMINISTIC_EVIDENCE,
                text="The verified solution.",
                evidence_ids=(EVIDENCE_ID,),
            ),
        ),
    )
    report = validate_agent_output(
        output,
        make_request(),
        make_context(),
        make_policy(),
    )
    assert report.outcome is GuardrailOutcome.PASSED


def test_quarantined_backend_result_blocks_solution_claim() -> None:
    output = AgentOutput(
        claims=(
            AgentClaim(
                claim_id="claim:solution:1",
                kind=AgentClaimKind.SOLUTION,
                method=AgentClaimMethod.DETERMINISTIC_EVIDENCE,
                text="A disputed solution.",
                evidence_ids=(EVIDENCE_ID,),
            ),
        ),
    )
    report = validate_agent_output(
        output,
        make_request(),
        make_context(status=VerificationStatus.QUARANTINED),
        make_policy(),
    )
    codes = {item.code for item in report.findings}
    assert GuardrailCode.UNACCEPTED_EVIDENCE in codes
    assert GuardrailCode.DETERMINISTIC_CONFLICT in codes


def test_request_tool_must_be_in_both_policy_and_context_allowlists() -> None:
    report = validate_agent_request(
        make_request(tools=("unrestricted_storage",)),
        make_context(),
        make_policy(),
    )
    assert report.outcome is GuardrailOutcome.REJECTED
    assert {item.code for item in report.findings} == {GuardrailCode.TOOL_NOT_ALLOWED}


def test_runtime_cannot_use_allowlisted_tool_that_request_did_not_declare() -> None:
    report = validate_agent_output(
        AgentOutput(refusal_reason="No tool was requested."),
        make_request(),
        make_context(),
        make_policy(),
        used_tools=("verify_deduction",),
    )
    assert {item.code for item in report.findings} == {GuardrailCode.TOOL_USE_NOT_DECLARED}


def test_hidden_search_is_rejected() -> None:
    output = AgentOutput(
        claims=(
            AgentClaim(
                claim_id="claim:hidden-search",
                kind=AgentClaimKind.FACTUAL,
                method=AgentClaimMethod.HIDDEN_SEARCH,
                text="A result obtained by undisclosed search.",
                evidence_ids=(EVIDENCE_ID,),
            ),
        ),
    )
    assert GuardrailCode.HIDDEN_SEARCH in _codes(output)
