# Quality Gates

## Contents

1. Evidence standard
2. Worker batch barrier
3. Requirements gate
4. Architecture gate
5. Initialization gate
6. Slice gate
7. System validation gate
8. Handoff gate
9. Waivers and non-applicable checks

## 1. Evidence standard

Record for every executable gate:

- exact command and working directory;
- exit code;
- tool/runtime versions;
- timestamp;
- source fingerprint;
- log/report path;
- worker batch, task, and result-report path;
- concise interpretation.

Use the current source fingerprint for implementation, validation, and handoff evidence. Any relevant source, test, dependency or lockfile, schema or migration, or configuration mutation makes every approval at the applicable downstream barrier stale.

Never claim a check ran from code inspection alone. Never infer that an unreported test suite passed.

The orchestrator coordinates gates but does not execute tests, scans, reviews, or product commands. Dispatch each applicable check to a worker with the required authority and tools. A gate decision is a coordination action derived from accepted worker evidence, not a substitute for that evidence.

## 2. Worker batch barrier

Freeze one input fingerprint before releasing a review or validation batch. For pre-source phases, use a SHA-256 hash of the candidate artifact; for source-related gates, use `factory_state.py fingerprint`.

Pass the synchronization barrier only when:

- every mandatory `TASK-###` has one schema-valid `worker-result` report;
- every report identifies the assigned batch, task, lane, and frozen fingerprint;
- the observed fingerprint still equals the input and current fingerprint;
- review/test lanes changed no source, and implementation lanes stayed within assigned ownership;
- commands, versions, outcomes, coverage dispositions, findings, and evidence paths are present when applicable;
- no report is failed, blocked, errored, stale, or missing;
- no critical/high correctness or security finding remains open;
- any materially conflicting conclusions have a completed independent adjudication report.

Do not partially pass a barrier. After any relevant source, test, dependency or lockfile, schema or migration, or configuration mutation, invalidate the whole prior batch and disregard its late reports. Compute and freeze a fresh fingerprint, then redispatch every mandatory review and validation lane for that barrier as one new batch, even when a lane appears unaffected. Targeted or impacted checks may run before refreezing as fast repair diagnostics, but they do not satisfy the barrier and no prior passing disposition carries forward.

## 3. Requirements gate

Pass only when:

- goal, scope, non-goals, actors, and permissions are explicit;
- all functional and non-functional requirements have stable IDs;
- acceptance criteria are measurable and map to requirements;
- exceptional paths, data classification, privacy, and destructive behavior are covered;
- assumptions and risks are visible;
- material contradictions or authority questions are resolved or blocked;
- the frozen candidate has passed the required independent review batch without silently changing scope.

## 4. Architecture gate

Pass only when:

- the architecture satisfies all baselined requirements with minimal complexity;
- exact dependency/runtime versions are verified and recorded;
- component, data, API, and trust boundaries are explicit;
- authentication, authorization, validation, secret handling, and abuse cases are designed;
- migration, rollback, backup/restore, and compatibility are addressed when relevant;
- observability, failure behavior, performance, accessibility, and test strategy are defined;
- major decisions and rejected high-impact alternatives are recorded;
- the design is feasible in the available workspace and authority envelope.

The architecture author and architecture reviewers must be separate tasks. Reviewers operate on the same artifact snapshot and emit structured reports at the barrier.

## 5. Initialization gate

Pass only after recording evidence for the applicable commands:

- clean dependency install from lockfile;
- formatter/linter configuration;
- type or compile check;
- production build/package step;
- test discovery and one smoke test;
- start, health/readiness, and graceful shutdown where applicable;
- `.env.example` or equivalent with no real secrets;
- CI-equivalent commands runnable locally.

Inspect package lifecycle scripts and registry/provenance when dependencies are unfamiliar or high risk.

## 6. Slice gate

Require:

- mapped acceptance scenarios pass;
- formatting, lint, type/compile, and build checks pass for impacted code;
- unit/component tests cover logic and error paths;
- integration/contract tests cover changed boundaries;
- migrations/fixtures are deterministic and reversible where relevant;
- independent code, security, and test-review reports reference the same frozen fingerprint and arrive in one batch;
- UI checks cover impacted routes/actions when applicable;
- no unresolved critical/high security or correctness finding;
- traceability and documentation are current.

Run broader regression when the slice changes shared infrastructure, authentication, global state, schema, build configuration, or public contracts.

After a repair mutation, use narrow and impacted checks only to diagnose the repair quickly. Before passing the slice gate, freeze the new fingerprint and rerun the complete mandatory review batch for the gate, including code, security, test-review, and applicable UI lanes.

## 7. System validation gate

Apply only relevant checks, but explain every omission:

| Area | Minimum evidence |
|---|---|
| Reproducibility | Clean install/build/start from documented commands |
| Static | Format check, lint, type/compile, build/package |
| Unit/component | Full discovered suite, no hidden skips |
| Integration/contract | Real boundaries or faithful local substitutes |
| System/E2E | Critical cross-feature journeys and failures |
| Security | Threat-model review, secret scan, dependency audit, authz abuse tests, relevant SAST/DAST/IaC/container checks |
| Data | Migrations, seed behavior, integrity, rollback/restore where relevant |
| UI/accessibility | Dedicated `ui-testing` skill report when available, otherwise a delegated safe fallback; route/action matrix, keyboard, automated accessibility plus manual semantic checks, supported viewports |
| Performance | Requirement-linked budgets with stable test conditions |
| Reliability | Timeouts, retries, graceful degradation, health checks, shutdown, recovery |
| Operability | Config, logs, metrics/traces as required, runbook and diagnostics |
| Documentation | Fresh operator can install, run, test, and understand limitations |
| Supply chain | Lockfile, provenance review, vulnerability/license policy, SBOM where appropriate |

Treat flaky, skipped, quarantined, or environment-dependent mandatory tests as unresolved failures unless explicitly waived with risk and rationale.

For UI products, follow `ui-validation.md`. The UI-testing worker, never the orchestrator, must execute the UI suite against the frozen source fingerprint and return structured coverage and evidence for the barrier.

## 8. Handoff gate

Pass only when:

- every in-scope requirement and acceptance criterion has a current disposition;
- every planned slice is accepted or explicitly removed from scope with a recorded decision;
- full validation evidence matches the final fingerprint;
- setup/run/test commands were verified;
- known limitations, residual risks, and waivers are visible;
- configuration needs contain no secret values;
- deployment/migration/rollback notes match the product;
- the handoff clearly distinguishes review-ready, staged, deployed, and released states;
- `validate_run.py` reports no errors.

## 9. Waivers and non-applicable checks

Use `not-applicable` only when the product profile makes a gate irrelevant, not when a tool is inconvenient or a check fails. Record:

- gate/check name;
- reason it does not apply;
- supporting architecture/profile fact;
- residual risk;
- reviewer or authority if one is required.

Never waive a failed safety, authorization, or acceptance requirement merely to complete the run.
