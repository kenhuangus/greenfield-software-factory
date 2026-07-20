# Recovery and Failure Routing

## Classify before repairing

| Failure class | Route | Retry policy |
|---|---|---|
| Transient network/tool startup | Same phase | Retry unchanged operation at most twice with bounded backoff |
| Suspected flaky test | Test review | Rerun unchanged fingerprint twice; inconsistency remains a failure |
| Implementation defect | Implementer | Up to three diagnosed, materially different repairs per signature |
| Test/fixture defect | Test owner | Repair without weakening the acceptance behavior |
| Environment/scaffold defect | Initialization | Fix reproducibility, then invalidate downstream gates |
| Architecture defect | Architecture | Revise decision and replan affected slices |
| Specification contradiction | Requirements | Do not guess; block if the core outcome changes |
| Malformed factory artifact | Artifact owner | Dispatch one controlled reconstruction from preserved evidence, then block |
| Malformed/missing worker result | Batch barrier | Close the batch as failed; dispatch one replacement with new batch/task IDs or block |
| Worker crash or bounded timeout | Batch barrier | Record the scheduler failure; dispatch one replacement with new batch/task IDs or block |
| Stale fingerprint result | Batch barrier | Discard it; replace only the stale task if the frozen input is unchanged, but after a relevant mutation refreeze and redispatch every mandatory lane |
| Materially conflicting reviews | Adjudication | Dispatch one narrow independent adjudicator; block if still unresolved |
| Missing equivalent tool | Current phase | Try one safe equivalent, then block |
| Credential/authority/destructive/policy issue | Blocked | Do not retry |

## Repair protocol

1. Preserve the exact command, output, source fingerprint, environment, and failure signature.
2. Distinguish product, test, environment, specification, architecture, and external failures.
3. State one falsifiable root-cause hypothesis.
4. Choose the smallest repair that tests the hypothesis.
5. Dispatch the repair to a worker with explicit file ownership; the orchestrator does not implement it.
6. Rerun the narrow failed check as a fast pre-barrier diagnostic only.
7. If the repair mutated source, tests, dependencies or lockfiles, schemas or migrations, or relevant configuration, compute and freeze a fresh fingerprint. Re-enter each invalidated barrier and redispatch every mandatory review and validation lane for that barrier; do not carry forward a prior pass because it appears unaffected.
8. Record the result and whether the signature changed.

Do not edit code before classifying a suspected flake. A rerun that passes once does not erase inconsistent behavior.

## Stop conditions

Stop early and enter `blocked` when:

- the same signature remains after three total materially different implementation repairs, or earlier when further repair has no falsifiable hypothesis;
- diffs make no progress or oscillate between failures;
- a repair would weaken a requirement, test, scan, or safety control;
- the required credential, service, data, authority, or rollback is unavailable;
- resource/time/process limits prevent reliable validation;
- state or evidence cannot be trusted after one controlled reconstruction attempt.

Record the smallest concrete recovery action. Never advance through a failed mandatory gate.

## Batch recovery

At a synchronization barrier:

1. Validate each report against `assets/schemas/worker-result.schema.json` before interpreting its status and findings.
2. Compare batch ID, task ID, lane, input fingerprint, observed fingerprint, and current frozen fingerprint.
3. Mark mismatches `stale`; never merge their findings into a pass decision.
4. Preserve valid peer reports and artifacts as historical evidence, but do not relabel the failed batch as passed. When the frozen fingerprint is unchanged, redispatch missing, malformed, crashed, or timed-out work under new batch/task IDs.
5. Cancel or disregard outstanding tasks when source ownership is violated or the fingerprint changes.
6. Route substantive report conflicts to an adjudication worker using the raw artifacts and reports. The orchestrator does not decide the technical issue itself.
7. Record the final barrier disposition and every accepted report path in `.factory/verification.md`.

A replacement may reuse the same immutable inputs only when the fingerprint is unchanged, but it always receives new batch/task IDs after the prior barrier closes. After any relevant source, test, dependency or lockfile, schema or migration, or configuration mutation, close or supersede the whole prior batch, compute and freeze a new fingerprint, and redispatch every mandatory review and validation lane for the barrier under new IDs. Prior passing peer reports remain historical evidence only. Targeted failed or impacted checks may run first as diagnostics, but cannot satisfy the barrier. Record `timed-out`, `crashed`, `cancelled`, or `superseded` scheduler dispositions in `.factory/verification.md`; they never substitute for a worker result. Do not leak an intended conclusion into a replacement worker prompt.

## Resume protocol

1. Read `.factory/state.json`, history, unresolved blockers, git/worktree status, and latest evidence.
2. Validate artifacts before changing source.
3. Confirm whether the authority envelope or external condition changed.
4. Resolve the blocker in state with a note; do not delete it.
5. Recompute the source fingerprint. If a relevant source, test, dependency or lockfile, schema or migration, or configuration mutation occurred, invalidate all reports at each applicable barrier and redispatch every mandatory lane against the freshly frozen fingerprint.
6. Only when the frozen fingerprint is unchanged, reconstruct an incomplete batch from its saved packets and accepted reports; do not assume an in-flight worker completed.
7. Resume from the earliest affected phase, not from the last optimistic claim.
8. Re-run the phase gate before advancing.

Use idempotent commands where possible. Before repeating an action, verify whether its intended effect already occurred; this is mandatory for migrations, releases, external calls, and generated artifacts.
