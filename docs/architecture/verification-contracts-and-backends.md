# Verification Contracts and Backends

Last reviewed: 2026-07-16

CR-004 introduces the first proof authority in Deductra. A deduction is represented by an immutable `ProofObligation` tied to an exact puzzle revision and source-state hash. Assignment and elimination claims are accepted only when the source constraints plus the logical negation of the claim are unsatisfiable.

## Authority boundary

The verification coordinator is the only component that converts backend certificates into deduction authority. `sat` rejects the proposed deduction, `unknown` or a timeout is inconclusive, and an encoding failure is rejected. A mixture of `sat` and `unsat` from independent backends is quarantined for investigation. None of those outcomes may change canonical state.

An `unsat` result from one configured backend is backend-verified. Matching `unsat` results from more than one independently encoded backend are cross-verified. The verified reducer boundary checks the obligation identity, exact source-state hash, exact event conclusion, and accepted decision before delegating to the pure state reducer.

## Contracts

Verification records contain:

- the complete proof obligation, including assumptions, conclusion, negated claim, and encoding version;
- one integrity-protected certificate per backend, including backend provenance, result, duration, optional unsatisfiable-core references or satisfying model, and a raw-artifact digest;
- the coordinator status and reason.

The canonical serialized form is [Verification Record v1](../../schemas/verification-record-v1.schema.json). Certificate and state digests use the existing canonical JSON and SHA-256 rules.

## Independent encodings

`Z3ProofBackend` creates tracked logical assertions and retains unsatisfiable-core references. `CpSatProofBackend` creates a separate integer finite-domain model and retains a satisfying assignment when one exists. They share validated identifiers and finite-domain mappings, but never share solver expressions or a translated backend model.

CR-004 intentionally supports only assignment and exclusion atoms plus active domain and all-different constraints. Any other atom or constraint fails closed as an invalid encoding. Supporting another constraint kind requires tests proving equivalent semantics in both encoders.

Each invocation has an explicit positive timeout. CP-SAT uses one worker and a fixed random seed for reproducible verification behavior. Native solver compatibility is exercised in the Python 3.13 and 3.14 CI matrix and container build.

## Failure handling

Certificates are evidence, not permission by themselves. Invalid hashes, stale obligations, duplicate backend identities, mismatched obligation identities, unsupported events, inconclusive results, and quarantined disagreements are rejected before reduction. Quarantined evidence must be retained and diagnosed; it must never be resolved by selecting the preferred result.
