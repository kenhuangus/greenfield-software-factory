# Artifact Contracts

## Contents

1. Run directory
2. Identifier rules
3. State and gate records
4. Product specification
5. Architecture
6. Feature plan
7. Worker packets and results
8. Synchronization barriers
9. Traceability and evidence
10. Handoff

## 1. Run directory

Keep durable coordination data in the target repository:

```text
.factory/
|-- state.json
|-- product-spec.md
|-- architecture.md
|-- feature-plan.json
|-- traceability.md
|-- verification.md
|-- handoff.md
|-- decisions/
|-- evidence/
`-- reports/
    `-- BATCH-###/
```

Use `scripts/factory_state.py init` to create the standard structure from the bundled templates. Preserve existing files. Treat `.factory/state.json` as the authoritative phase and gate record. Treat the other files as reviewable product and verification artifacts.

Store worker results under `.factory/reports/BATCH-###/TASK-###.json`. Store logs, screenshots, traces, scan reports, and benchmark output under `.factory/evidence/` or `.factory/reports/`. Do not store secrets, private production data, or dependency/build caches there. Redact sensitive values before persisting evidence; record that redaction occurred.

## 2. Identifier rules

Use stable, never-recycled IDs:

| Kind | Pattern | Meaning |
|---|---|---|
| Functional requirement | `FR-001` | Observable product behavior |
| Non-functional requirement | `NFR-001` | Quality or operational constraint |
| Acceptance criterion | `AC-001` | Measurable pass/fail behavior |
| Risk | `RISK-001` | Product, delivery, or operational risk |
| Decision | `DEC-001` | Consequential architecture or product choice |
| Vertical slice | `SLICE-001` | Independently verifiable increment |
| Defect | `BUG-001` | Reproducible deviation from expected behavior |
| Worker batch | `BATCH-001` | Set of independent tasks released together |
| Worker task | `TASK-001` | One bounded work or review assignment |
| Review finding | `FIND-001` | One evidence-backed review observation |

Never renumber accepted IDs. Mark withdrawn items as superseded and link the replacement.

## 3. State and gate records

Record:

- schema version, goal, profile, status, and current phase;
- timestamps and append-only transition history;
- artifact paths relative to the project root;
- assumptions and blockers;
- gate status, evidence, and source fingerprint where applicable.

Use phase-gate states `pending`, `passed`, or `failed`. Record an individual conditional check as `not-applicable` only in `.factory/verification.md`, with an explicit rationale. Record a phase as `passed` only after executing its applicable validation. A source fingerprint is mandatory for implementation, validation, and handoff passes.

The orchestrator may mechanically update run state, gate and phase transitions, and slice status only. It must not author or substantively revise product artifacts, feature-plan content or evidence, implementation source, reviews, or tests. Delegate those outputs to their designated artifact-owner or specialist workers and accept them only at a synchronization barrier. Use the helper commands for atomic state writes; do not edit history to conceal a failure.

## 4. Product specification

Keep `.factory/product-spec.md` concise but complete. Include:

- product goal and target outcome;
- in-scope and out-of-scope behavior;
- actors, roles, and permissions;
- primary and exceptional journeys;
- numbered functional and non-functional requirements;
- business rules and edge cases;
- data inventory, classification, retention, and privacy constraints;
- assumptions, dependencies, risks, and open decisions;
- measurable acceptance criteria mapped to requirements.

Write acceptance criteria in observable terms. Avoid adjectives such as "fast", "secure", "intuitive", or "production-ready" without a metric and verification method.

## 5. Architecture

Keep `.factory/architecture.md` decision-oriented. Include:

- context and constraints;
- selected stack with exact versions and verification source;
- system boundaries and a diagram;
- module ownership and dependency direction;
- data model, storage, migrations, and rollback;
- API, event, file, or CLI contracts and error semantics;
- authentication, authorization, trust boundaries, and threat model;
- reliability, observability, performance, privacy, and accessibility design;
- test strategy, delivery partitions, and deployment assumptions;
- rejected alternatives only when they clarify a decision.

Put longer consequential decisions in `.factory/decisions/DEC-###-slug.md` with context, decision, consequences, and supersession links.

## 6. Feature plan

Keep `.factory/feature-plan.json` valid JSON matching `assets/schemas/feature-plan.schema.json`.

Each slice must contain:

- unique `SLICE-###` ID and short title;
- status from the per-slice state model;
- dependency slice IDs;
- mapped requirement and acceptance IDs;
- expected files or modules;
- planned test levels and concrete scenarios;
- risk level and evidence links;
- source fingerprint once accepted.

Use this per-slice state model:

```text
pending -> ready -> implementing -> verifying -> reviewing -> accepted
                                      \-> repairing -> verifying
```

Use `blocked` only with a recorded blocker. The orchestrator is the only writer of the mechanical per-slice `status` field; it may not change substantive feature-plan content or evidence. Assign one feature-plan artifact-owner worker to update slice definitions, dependencies, requirement and acceptance mappings, expected files/modules, planned tests, risks, fingerprints, and evidence links. Accept that worker's schema-valid update at a synchronization barrier before treating it as authoritative. The implementation worker owns the actual slice source output. Serialize artifact-owner and status writes when they touch the same plan file. Derive an asynchronous implementation batch from ready DAG nodes only when their file ownership and contracts do not overlap. Do not add ad hoc batch fields to `feature-plan.json`; persist batch/task results under `.factory/reports/` so the plan remains compatible with the bundled validator.

## 7. Worker packets and results

The orchestrator creates a bounded packet for every task. A packet must state:

- `BATCH-###`, `TASK-###`, lane, purpose, and expected disposition;
- immutable input fingerprint (`sha256:<64 lowercase hex>`), or an artifact snapshot hash before product source exists;
- raw inputs and paths, without an intended conclusion or hidden diagnosis;
- owned files or read-only scope, plus explicit exclusions;
- requirement, acceptance, risk, and slice IDs in scope;
- dependencies and required peer tasks at the barrier;
- permitted tools and authority limits;
- required output path and the bundled result schema;
- bounded retry, time, and resource expectations.

Give implementation workers disjoint source ownership. Give review and test workers read-only source scope; they may write only their assigned `.factory/reports/` and `.factory/evidence/` outputs. Never give a worker broader authority than the run envelope.

Require every worker to emit JSON matching `assets/schemas/worker-result.schema.json`. Start from `assets/templates/worker-result.json` when useful. A result records the task identity, worker role, status, input and observed fingerprints, timestamps, tool versions, commands, coverage, evidence artifacts, findings, and changed source files.

Do not accept prose-only "pass" messages as gate evidence. Do not accept a report whose task ID, lane, scope, or fingerprint differs from its packet.

## 8. Synchronization barriers

Release independent tasks as one asynchronous batch, then wait at a named barrier. The orchestrator performs coordination only:

1. Verify every required task reached a terminal status and produced a schema-valid report.
2. Reject a report as stale if its observed fingerprint differs from the packet fingerprint or the current frozen fingerprint.
3. Confirm read-only lanes report no source changes and implementation lanes changed only owned files.
4. Route failed, blocked, malformed, contradictory, or missing results to the recovery policy; do not fill in missing work itself.
5. Dispatch a narrow adjudication task when reports conflict materially.
6. Advance the slice or phase only when all mandatory tasks pass and no blocking finding remains.
7. Record the accepted report paths and barrier disposition in `.factory/verification.md` and the relevant gate evidence.

Do not pollute a new worker prompt with prior reviewers' conclusions unless the task is an explicit repair or adjudication. Cancel or disregard outstanding work as soon as the frozen fingerprint changes.

After any relevant source, test, dependency or lockfile, schema or migration, or configuration mutation, invalidate every approval tied to the prior fingerprint. Compute and freeze a fresh fingerprint, then redispatch every mandatory review and validation lane for that barrier as a new batch, even when a lane appears unaffected. Targeted or impacted checks may run before that batch as fast repair diagnostics, but they are not barrier evidence and cannot be carried forward as a passing disposition.

## 9. Traceability and evidence

Maintain `.factory/traceability.md` as a reviewable matrix:

```text
requirement -> acceptance criterion -> decision -> slice -> files -> tests -> worker report -> evidence -> status
```

For each executable gate, record:

- exact command or manual procedure;
- exit code or explicit outcome;
- relevant tool/runtime versions;
- timestamp;
- source or artifact fingerprint;
- worker report and evidence paths;
- skipped items with rationale.

Store raw output when it materially supports the claim. Summaries may link to raw evidence; they must not replace it. Evidence is current only for the fingerprint on which it was produced.

## 10. Handoff

Keep `.factory/handoff.md` human-readable. Include:

- delivered outcome and explicit non-outcomes;
- exact install, configure, run, build, and test commands;
- key architecture and data-flow summary;
- requirement and acceptance coverage summary;
- verification evidence, accepted worker reports, and current fingerprint;
- assumptions, known limitations, unresolved risks, and waivers;
- configuration or secrets still required, without secret values;
- deployment, migration, rollback, and operational notes;
- the smallest final-review checklist.

State "review-ready release candidate" unless a separately authorized release or deployment actually occurred.
