# Specification and Architecture

## Contents

1. Specification method
2. Assumption policy
3. Acceptance design
4. Architecture selection
5. Design completeness
6. Profile-specific decisions
7. Delegated baselining

This reference guides the workers assigned to requirements and architecture. The orchestrator prepares packets, dispatches work, validates result metadata, and records transitions; it does not write the specification or design the system itself.

## 1. Specification method

Translate the brief into testable product behavior before selecting technologies.

1. State the product goal in one sentence.
2. Define the primary actor, problem, and successful outcome.
3. Bound the MVP with explicit in-scope and out-of-scope lists.
4. Enumerate actors and permissions.
5. Describe happy, exceptional, empty, loading, and failure journeys.
6. Create stable functional and non-functional requirement IDs.
7. Identify business rules, lifecycle states, data ownership, and concurrency behavior.
8. Record external dependencies, unknowns, assumptions, and risks.
9. Write measurable acceptance criteria and a verification method for each.
10. Check that requirements do not conflict and that every critical outcome has acceptance coverage.

Prefer one coherent workflow over many shallow features. Do not turn every imagined future capability into current scope.

Return a complete candidate specification artifact and a structured worker result. Do not return only recommendations for another agent to turn into a specification.

## 2. Assumption policy

Make an assumption autonomously only when it is:

- reversible without data loss;
- local to the designated workspace;
- low cost and free of external side effects;
- conventional for the selected profile;
- unlikely to alter security, privacy, legal, or core product behavior.

Record the chosen default, alternatives considered, impact, and reversal path. Ask or block when the missing decision affects identity, authorization, money, regulated/private data, destructive behavior, public exposure, irreversible schema/data changes, or mutually exclusive product goals.

## 3. Acceptance design

Baseline acceptance criteria before implementation. Make each criterion:

- observable by a user, API client, operator, or deterministic test;
- specific about preconditions, action, and expected result;
- explicit about role and data state;
- linked to one or more requirements;
- testable without production systems or real customer data.

For broad behavior, split criteria by equivalence class or risk boundary. Include negative authorization cases, failure recovery, and data integrity where applicable.

Have one or more independent reviewers challenge the frozen acceptance set before product code is written. Give each reviewer the same artifact snapshot hash and raw brief. Reviewers may identify gaps but must not silently expand scope or edit the candidate artifact. Consume all required reports at one synchronization barrier; route material disagreements to a separate adjudication worker.

## 4. Architecture selection

The assigned architecture worker chooses the simplest stack that meets the specification and fits the available environment. Prefer:

- maintained, stable tools with clear official documentation;
- fewer deployable units until scale or isolation requires more;
- standard platform capabilities over custom infrastructure;
- typed contracts and explicit boundary validation;
- deterministic builds and lockfiles;
- local substitutes for external systems during development and tests.

Verify version-sensitive choices using installed metadata, Context Hub, or primary official documentation. Record exact versions and the date/source checked. Do not hardcode stale versions from this skill.

Use a monolith or modular monolith by default for a small greenfield product. Introduce microservices, event buses, distributed caches, or orchestrators only when a documented constraint justifies their operational cost.

## 5. Design completeness

Before passing architecture, define:

- system context, trust boundaries, and external dependencies;
- modules and allowed dependency direction;
- data entities, invariants, indexes, retention, migrations, seed data, and rollback;
- API/event/file contracts, validation, idempotency, pagination, and error semantics;
- authentication, session/token lifecycle, authorization checks, and abuse cases;
- secret/configuration handling and environment separation;
- failure modes, retries, timeouts, concurrency, and consistency expectations;
- logs, metrics, traces, health/readiness checks, and diagnostic behavior;
- performance budgets and capacity assumptions;
- accessibility and internationalization requirements when applicable;
- testing layers, fixtures, test isolation, and clean-install verification;
- parallel-safe delivery partitions, explicit file/module ownership, and integration contracts;
- deployment shape, compatibility, rollback, backup, and restore assumptions.

Use Mermaid or a compact text diagram when it materially clarifies boundaries or data flow.

## 6. Profile-specific decisions

### `web-app`

Define route/role/action inventory, server/client boundary, form and validation ownership, session behavior, browser/viewports, accessibility target, and external-side-effect stubs.

### `api-service`

Define protocol/schema, authentication, authorization, idempotency, pagination, rate limits, compatibility/versioning, error envelope, observability, and contract-test strategy.

### `cli-library`

Define supported runtimes/platforms, command/API stability, exit codes, stdin/stdout/stderr contract, packaging, install/uninstall behavior, backward compatibility, and fixture strategy.

### `mobile-desktop`

Define supported OS/device matrix, permissions, offline and sync behavior, secure local storage, update/distribution assumptions, accessibility, and platform-specific test coverage.

### `data-ml`

Define dataset provenance, schema, leakage controls, split strategy, evaluation metrics/baselines, reproducibility, model/data versioning, privacy, drift, failure behavior, and inference constraints.

### `other`

Derive conditional decisions directly from the requirement risks. Explain why no standard profile fits.

## 7. Delegated baselining

For each phase, keep one worker accountable for the candidate artifact and fan out only independent review questions. Parallelizing multiple authors over the same document creates merge ambiguity and is not a useful batch.

Use this sequence:

1. Dispatch a requirements or architecture author with exclusive ownership of its artifact.
2. Compute a SHA-256 snapshot of the completed candidate artifact. Before product source exists, this artifact hash is the batch fingerprint.
3. Dispatch independent review tasks asynchronously against that exact snapshot. Typical lanes are completeness, feasibility, security/privacy, testability, and profile-specific UX or operations.
4. Require every lane to emit `assets/schemas/worker-result.schema.json` and to report the same input and observed fingerprint.
5. At the barrier, reject stale, malformed, missing, or scope-expanding reports. Dispatch a bounded repair or adjudication worker as needed.
6. Ask the artifact owner to incorporate accepted findings. Because the candidate artifact changed, compute and freeze a fresh snapshot and redispatch every mandatory review lane for that barrier as a new batch, even when a lane appears unaffected. A targeted recheck may run first as a diagnostic, but it cannot satisfy the barrier.
7. Let the orchestrator record the gate only after the final snapshot has all mandatory passing dispositions.

Do not leak one reviewer's intended conclusion into independent peer prompts. Do not let the orchestrator resolve substantive design questions by doing the design work; dispatch a targeted specialist or block on a material user decision.
