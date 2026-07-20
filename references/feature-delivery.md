# Feature Delivery

## Contents

1. Planning vertical slices
2. Worker task contracts
3. Wave scheduling and ownership
4. Structured worker reports
5. Synchronization and fingerprint freshness
6. Scaffolding and implementation waves
7. Parallel review and specialist UI testing
8. Acceptance and integration
9. Degraded-capacity and unavailable-worker behavior
10. Documentation discipline

## 1. Planning vertical slices

Make each slice deliver observable behavior across the necessary layers. A good slice is small enough to repair quickly and complete enough to verify independently.

For each `SLICE-###`, record:

- user/operator outcome;
- prerequisite slice IDs;
- mapped `FR-###` and `AC-###` IDs;
- expected modules/files;
- data and contract changes;
- unit, integration, contract, UI, and operational tests as applicable;
- risk level and likely failure modes;
- exit evidence.

Order foundational enablers only when a later vertical slice genuinely depends on them. Avoid architecture-only slices with no executable proof. Include shared contracts and files in the dependency graph so apparently independent slices do not become concurrent writers by accident.

## 2. Worker task contracts

The orchestrator must dispatch every substantive activity as a bounded worker task. It coordinates the work but never performs the task itself. Before dispatch, create an immutable contract containing:

- `batch_id`, `task_id`, lane, worker role, goal, and prerequisite task or slice IDs;
- project root and isolated workspace or worktree path;
- `input_fingerprint` and exact input artifact paths;
- mapped `FR-###`, `AC-###`, `RISK-###`, and `DEC-###` IDs as applicable;
- read scope, a disjoint gate-relevant write allowlist, and a separate evidence-output scope; use an empty gate-relevant write list for reviewers;
- required deliverables, checks, commands, and evidence;
- for every writer, source workspace identity, binding to the input fingerprint, and an immutable output transport: a commit or patch/bundle plus SHA-256 for an isolated writer, or a per-output SHA-256 manifest in the report for a serialized in-place writer;
- authority limits, forbidden side effects, secret/data handling, and stop conditions;
- report path `.factory/reports/BATCH-###/TASK-###.json`, the bundled template and normative schema from section 4;
- a hard worker deadline and a protected finalization reserve of at least 60 seconds. The worker must stop substantive work when the reserve begins, and the scheduler must not declare a timeout before the stated deadline except for cancellation or a safety stop.

Do not change a task contract after dispatch. Cancel and reissue it with a new task ID when the scope, ownership, authority, or input fingerprint changes. Workers must not edit `.factory/state.json`, mark gates, transition phases, broaden their authority, or self-schedule downstream work. They return a report to the orchestrator; the orchestrator decides what to dispatch next.

## 3. Wave scheduling and ownership

Build waves from the phase and slice dependency graph:

1. Compute every task whose prerequisites are accepted and whose required inputs exist.
2. Partition the ready set by write ownership, shared contracts, authority, environment, and available capacity.
3. Assign one common input fingerprint and one `BATCH-###` ID to each independent wave batch.
4. Dispatch the whole batch asynchronously before waiting for any member.
5. Wait for every member to reach a terminal state, then evaluate the synchronization barrier in section 5.

Use the pattern `compute ready set -> dispatch batch -> wait all -> barrier -> integrate -> freeze -> review batch -> barrier`. Do not await one worker serially while other independent tasks are ready, and do not release downstream work early because one task finished first.

Give concurrent writers isolated worktrees, branches, sandboxes, or equivalent copy-on-write workspaces created from the same baseline. Their write allowlists must be disjoint and must account for generated files. Treat package manifests, lockfiles, schemas, migrations, code-generation outputs, shared types, root configuration, and global documentation as single-owner resources within a wave. A dedicated integration worker owns the integration workspace and conflict resolution.

If isolated workspaces are unavailable, serialize all writers in dependency order. Read-only analysis and review workers may still run concurrently against a frozen tree. Never rely only on an instruction to avoid conflicts while multiple agents write the same shared directory.

## 4. Structured worker reports

Require every worker to emit JSON that validates against `assets/schemas/worker-result.schema.json`; that schema is normative. Start from `assets/templates/worker-result.json` and do not invent a competing report shape. Use this crash-safe report protocol:

1. As the worker's first write, fill the template's task identity, fingerprints, start time, and report time, keep `status: "error"`, and atomically reserve `.factory/reports/BATCH-###/TASK-###.json`. Its summary must say that it is a crash fallback, not a completed success. The scheduler evaluates it only after the worker runtime becomes terminal.
2. After each durable deliverable or evidence milestone, atomically refresh that fallback with the artifacts and `changed_files` known so far. Write a sibling temporary file, validate it, then replace the report path; never expose truncated JSON.
3. When the protected finalization reserve begins, stop expanding or polishing the deliverable. Record incomplete checks as `not-run`, uncovered IDs in `coverage`, partial artifacts, and the supported non-passing status instead of working until interruption.
4. As soon as all mandatory deliverables and checks exist, atomically replace the fallback with the final `passed`, `failed`, `blocked`, `error`, or `stale` report, validate it, perform no further task writes, and return immediately.

The orchestrator may validate and index that coordination artifact but must not rewrite its technical content. A surviving fallback or checkpoint after a crash or timeout is failure evidence only; it never satisfies a task or gate and does not replace the failed scheduler disposition below.

Every report must include the schema's core identity, status, freshness, timestamps, summary, `artifacts`, and `changed_files`. Include `tool_versions`, `commands`, `coverage`, and `findings` whenever the contract calls for them or they contain evidence; the schema permits omitting an inapplicable empty collection so simple authoring tasks do not spend their reporting reserve manufacturing empty detail. Review and validation tasks must include all four collections, even when empty. Use only schema-defined status values: `passed`, `failed`, `blocked`, `error`, or `stale`. Record failed and not-run commands, partial artifacts, and uncovered acceptance IDs; do not report only successes. Use `FIND-###` for review findings and `BUG-###` only for accepted reproducible defects tracked outside the worker-result finding record.

A writer must identify its source workspace in `summary`, list every gate-relevant source mutation in `changed_files`, and bind its output to the packet input fingerprint. An isolated writer must list the task contract's immutable commit or patch/bundle locator and digest in `artifacts`. For a serialized in-place writer, the report may instead be the immutable transport manifest: list each owned output as `sha256:<64 lowercase hex> <project-relative path>` in `artifacts`. Do not create a duplicate bundle merely to copy an already serialized output. The integration worker or coordinator verifies the declared digest and fingerprint before accepting the output.

A read-only worker must report the frozen fingerprint as both `input_fingerprint` and `observed_fingerprint`, leave `changed_files` empty, and write only within its task-unique `.factory/reports/BATCH-###/` and `.factory/evidence/BATCH-###/TASK-###/` scope. Those evidence sinks are outside the source fingerprint and exempt only from gate-relevant source ownership; list every created report, screenshot, trace, or log in `artifacts`. Treat a missing, schema-invalid, contradictory, stale, or evidence-free report as a failed barrier member. A report is a claim for the barrier to validate, not authority to advance the state machine. The orchestrator checks schema validity, scope, provenance, and freshness; technical correctness remains the responsibility of delegated specialist workers.

If a worker crashes, times out, is cancelled, or disappears before finalizing a valid result, the orchestrator records a durable failed scheduler disposition in `.factory/verification.md` with `batch_id`, `task_id`, disposition (`timed-out`, `crashed`, `cancelled`, or `superseded`), timestamp, attempts, last observed fingerprint, and available evidence, including any crash fallback or checkpoint report. This terminates the scheduler wait and closes that batch as failed; neither the disposition nor a surviving fallback can satisfy a task or gate. Reissue the work with a new task ID in a new batch after recording the failed barrier.

## 5. Synchronization and fingerprint freshness

Use `factory_state.py fingerprint --project <workspace>` as the canonical fingerprint algorithm. It covers gate-relevant source while excluding factory reports and volatile build output so recording evidence does not change the reviewed fingerprint. Use the same algorithm for packet input, worker observation, integration, review, and validation; do not compare fingerprints produced by different algorithms.

At an implementation barrier:

1. Require a schema-valid terminal report from every dispatched task in the batch. If a task instead has the failed scheduler disposition defined in section 4, close the batch as failed and do not integrate it.
2. Verify batch and task IDs, lane, expected input and observed fingerprints, authority compliance, disjoint ownership, `changed_files`, artifacts, command outcomes, coverage, findings, and evidence paths.
3. Reject and reissue work whose baseline changed, whose writes escaped its allowlist, or whose output cannot be reproduced from the declared input.
4. Dispatch an integration worker to apply eligible outputs in deterministic dependency order and resolve conflicts without weakening requirements or tests.
5. Validate the integrator's structured report and compute the integrated fingerprint.
6. Freeze that fingerprint before dispatching any review or validation batch.

At a review or validation barrier:

1. Require every lane to verify the fingerprint immediately before and after its read-only work.
2. Accept reports only when all mandatory statuses are `passed`, all `input_fingerprint` and `observed_fingerprint` values equal the exact same frozen fingerprint, and every read-only lane has an empty `changed_files` array.
3. Treat any relevant mutation, even a repair requested by one lane, as invalidating every approval on the old fingerprint.
4. Dispatch repairs as a new writer wave, integrate them, compute a new fingerprint, and rerun every mandatory lane for that gate against it.
5. Advance the gate only when every mandatory lane has a current passing report and no blocking finding or unresolved ownership violation remains.

Keep stale reports as history, never as current gate evidence. Do not carry a pass forward merely because a worker believes its reviewed area was unchanged; the new barrier must establish freshness on the new fingerprint.

## 6. Scaffolding and implementation waves

Assign one scaffold worker ownership of shared root files and ask it to create only the skeleton needed to prove:

- runtime and package metadata;
- exact dependency lockfile;
- source/test directory conventions;
- environment example with fake placeholders only;
- format, lint, type-check, build, test, and start commands;
- deterministic local fixtures;
- CI-equivalent local workflow;
- one smoke path proving install, startup, and shutdown.

Independent dependency, security, or documentation research may run as read-only tasks in the same phase. Inspect an existing non-empty directory before scaffolding. Do not clobber user files or reinitialize version control unexpectedly.

For each implementation wave:

1. Select ready slices and allocate non-overlapping write scopes.
2. Dispatch implementers in isolated workspaces from the common fingerprint.
3. Require each implementer to deliver the smallest complete vertical behavior, its tests, updated contracts/fixtures/docs, and targeted check evidence. Do not accept TODOs in required behavior.
4. Stop at the implementation barrier, then use an integration worker.
5. Freeze the integrated tree and dispatch the review batch.
6. Route failed findings to bounded repair tasks with an explicit root-cause hypothesis. Re-enter the writer and review barriers after each material change.
7. Accept slices and release dependent work only after current evidence covers every mapped acceptance ID.

Do not rerun the complete end-to-end suite after every trivial edit. Have workers run targeted checks per slice and full regression at integration milestones and final validation.

## 7. Parallel review and specialist UI testing

After freezing a fingerprint, dispatch applicable read-only lanes together:

- **Code review:** correctness, maintainability, architecture conformance, error handling, concurrency, resource cleanup, and regression risk.
- **Security review:** threat model deltas, trust boundaries, input validation, authn/authz, secrets, privacy, dependency/supply-chain risk, and abuse cases.
- **Test review:** acceptance traceability, assertions, negative/boundary cases, fixture isolation, skipped tests, and false-positive risk.
- **UI/UX review:** for changed UI slices, route/action coverage, states, accessibility, keyboard behavior, layout, console/network failures, and destructive-action isolation.

Give each lane the raw specification, plan entry, frozen fingerprint, diff, and test output. Do not leak an intended verdict. Require file/line references, a reproducible scenario, or an evidence artifact for every actionable finding.

For every UI product, add a mandatory **full UI testing** specialist to the final validation batch. If an exact `$ui-testing` skill is installed at run time, invoke it in that worker. Otherwise, for web/Electron runtime browser automation and acceptance evidence, invoke the installed `$playwright` skill at `C:\Users\kenhu\.codex\skills\playwright\SKILL.md`; use the project's own test runner for authored regression specs. For mobile/desktop, use platform-native automation. This fallback changes the tool, not the worker boundary.

The UI specialist must test the frozen release-candidate fingerprint from the route/role/action inventory, use seeded ephemeral data, isolate destructive and external side effects, and return a schema-valid `ui-testing` lane report whose `artifacts` and `coverage` reference screenshots, traces, console/network evidence, accessibility results, and failed scenarios as applicable. Its report participates in the same validation barrier as every other specialist. The orchestrator must never operate the UI, perform visual inspection, declare UI coverage from another lane, or bypass a missing UI report. If neither an exact preferred skill nor a viable fallback can run in a worker, the validation gate is blocked.

## 8. Acceptance and integration

Before accepting a slice, require current worker evidence that:

- every mapped acceptance scenario ran;
- changed contracts and migrations were proved;
- critical/high findings and all correctness defects were closed;
- lower-severity residual risk was recorded or fixed;
- traceability and plan evidence were updated;
- the reviewed fingerprint still equals the integrated fingerprint;
- impacted regression tests passed.

At integration milestones, dispatch workers to run cross-slice flows and the full suite appropriate to project size. A slice pass does not guarantee system compatibility. The orchestrator records the decision only after the integration and review barriers pass; it does not merge, repair, or retest the product itself.

## 9. Degraded-capacity and unavailable-worker behavior

Preserve role separation when capacity or tooling degrades:

- With fewer workers than ready tasks, dispatch the largest safe batch, complete its barrier, then dispatch the next batch. A one-worker batch is valid; coordinator execution is not.
- Without isolated workspaces, serialize writers while parallelizing only read-only tasks.
- When a specialist skill is missing, dispatch a worker with an authorized equivalent tool and record the substitution. Do not silently omit a mandatory lane.
- When a worker times out, crashes, or returns no valid report, record the failed scheduler disposition from section 4, close the old batch as failed, then retry or reassign under a new task and batch ID within the recovery limits. Do not finish its work in the orchestrator.
- When no subagent or equivalent worker runtime is available, persist `worker-runtime-unavailable`, enter `blocked`, and report the smallest action that would restore delegation. Do not fabricate worker reports or collapse the orchestrator into an implementer.
- On resume, compare the current fingerprint with every pending task's input fingerprint. Reuse only current terminal reports and reissue stale or indeterminate tasks.

A failed or blocked mandatory worker closes its batch with a failed disposition and prevents the phase gate from passing; only a later replacement batch can supply a passing result. Reduced parallelism may slow a run; it never weakens the authority envelope, state machine, evidence standard, or quality gate.

## 10. Documentation discipline

Assign documentation writes to the slice owner or a dedicated documenter with explicit file ownership. Update documentation in the same slice when behavior, setup, API contracts, configuration, or operations change. Keep:

- public API and CLI behavior synchronized with implementation;
- environment examples free of secrets;
- migration and rollback instructions next to schema changes;
- architecture decisions aligned with actual code;
- exact commands verified from a clean environment.

Do not generate large generic documentation that says less than the source. Optimize for a new developer or operator successfully running and verifying the product.
