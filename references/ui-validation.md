# UI Validation

## Contents

1. Delegation contract
2. Coverage model
3. Test matrix
4. Execution order
5. Safe fixtures and harnesses
6. Visual and accessibility review
7. Structured result and barrier
8. Failure reports

## 1. Delegation contract

The orchestrator must not write UI tests, operate the browser or device, execute UI commands, inspect pages as the tester, or decide missing coverage itself. It coordinates one or more UI-testing workers and consumes their structured results.

Before dispatch:

1. Reach a clean runnable state and freeze the source with `factory_state.py fingerprint`.
2. Create a packet containing `BATCH-###`, `TASK-###`, the frozen fingerprint, product specification, acceptance IDs, route/role/action inventory, setup/start/reset commands, supported browser/device matrix, base-URL or app-identifier allowlist, authority limits, and report path.
3. Give the worker read-only source scope. Permit writes only to its assigned test/evidence locations; adding or changing product tests is a separate implementation task that invalidates the fingerprint.

When a dedicated `ui-testing` skill is available, dispatch a worker that uses it for both impacted-flow and full UI validation. Let that skill govern its detailed method unless it conflicts with the authority envelope or this safety contract. Require a `worker-result` wrapper matching `assets/schemas/worker-result.schema.json`; link any native report, trace, screenshots, video, or generated test artifact from that wrapper.

If the dedicated skill is unavailable, dispatch a UI QA worker with the safe fallback in section 5. Prefer the discoverable `$playwright` skill for web UI automation. The orchestrator still does not run the fallback. If no independent worker or safe harness is available, record a blocker; do not mark the UI gate not applicable and do not substitute code inspection for execution.

## 2. Coverage model

Define "full UI validation" as a current disposition for every item in a measurable route/role/action inventory, not an unbounded Cartesian product. For every reachable route or screen, record:

- allowed roles and denied roles;
- entry points, redirects, deep links, and navigation exits;
- primary, state-changing, and destructive actions;
- forms, controls, menus, dialogs, and keyboard actions;
- loading, empty, success, validation, error, offline, expired-session, and permission states;
- external calls and side effects;
- supported viewport, browser, OS, or device classes.

Map each critical action to acceptance IDs and automated or manual evidence. Exercise every distinct interactive control at least once unless it is unreachable or explicitly excluded with a requirement-backed rationale. Use equivalence classes, boundary analysis, pairwise coverage, and risk prioritization for input combinations.

## 3. Test matrix

Cover, as applicable:

- primary journeys for each role;
- direct route/deep-link access and authorization denial;
- required fields, formats, boundaries, long values, Unicode, and safe special-character input;
- duplicate submission, retry, refresh, back/forward, interrupted network, and idempotency behavior;
- every meaningful enum/dropdown choice and pairwise combinations for independent controls;
- keyboard-only navigation, focus order, visible focus, escape behavior, and focus restoration;
- semantic labels, headings, landmarks, errors, status announcements, and contrast;
- narrow mobile, standard desktop, and requirement-specific viewport/device classes;
- console errors, failed requests, unexpected redirects, and unhandled rejections;
- optimistic updates, stale state, concurrency, offline/sync behavior, and session expiry where applicable.

Do not generate a combinatorial matrix without a requirement or risk reason. Do not call coverage exhaustive when a route, role, critical action, or mandatory state lacks a disposition.

## 4. Execution order

The assigned worker:

1. Recomputes the fingerprint before starting and stops as `stale` on a mismatch.
2. Discovers routes/actions from source and runtime navigation.
3. Compares the discovered inventory with the product specification and reports gaps.
4. Runs a smoke journey on the smallest supported browser/device set.
5. Runs impacted flows for the current slice.
6. Runs negative, boundary, permission, accessibility, recovery, and state-transition scenarios.
7. Runs full cross-feature regression at integration milestones and final validation.
8. Captures traces, screenshots, or video only when useful for diagnosis or acceptance evidence.
9. Recomputes the fingerprint and emits a structured result without repairing source.

## 5. Safe fixtures and harnesses

Use seeded ephemeral accounts and data. Stub email, payments, analytics, messaging, object storage, and third-party APIs unless the user explicitly authorized a dedicated test environment. Make destructive actions operate only on disposable records. Reset state deterministically between tests.

Never embed real credentials or customer data in tests, screenshots, traces, or reports. Verify that test mode cannot target production endpoints. Allow only the packet's local or dedicated-test origins; fail closed on unexpected navigation or network destinations. Do not use the user's logged-in browser profile.

Fallback selection when the dedicated skill is unavailable:

- **Web UI:** Dispatch a worker using the `$playwright` skill when it is available, and reuse the project's existing Playwright suite when present. Otherwise use an equivalent Playwright runner in an isolated browser context against an allowlisted local or explicitly authorized dedicated test URL. Do not add a dependency or modify a lockfile from the read-only test lane; dispatch a separate setup worker, then refreeze, if harness installation is authorized and necessary.
- **Mobile/desktop UI:** Prefer the project's platform-native test runner with an isolated emulator, simulator, disposable profile, or sandbox. Disable real notifications, purchases, contacts, file deletion outside fixtures, and external integrations.
- **Existing alternative harness:** Use it only when it can produce equivalent route/action, failure, and artifact evidence under the same isolation contract. Record why it is equivalent.

If the required browser/device/runtime cannot be provisioned safely, return `blocked` with the smallest needed action. Never fall back to a production endpoint, a personal session, or uncontrolled manual clicking.

## 6. Visual and accessibility review

Combine automation with worker-performed visual inspection. Check:

- clipping, overlap, overflow, wrapping, and responsive reflow;
- loading skeletons, empty states, errors, disabled states, and dialogs;
- hierarchy, spacing, typography, and action prominence;
- zoom, text resizing, reduced motion, and platform settings when required;
- color independence and contrast;
- screen-reader semantics and announced validation/status changes.

Automated accessibility scanners are a floor, not a complete accessibility assessment. Include keyboard and semantic review for critical journeys. Use synthetic content in captured artifacts and redact unexpected sensitive values before storage.

## 7. Structured result and barrier

Write the result to `.factory/reports/BATCH-###/TASK-###.json` using the bundled worker-result schema. Include:

- `lane: "ui-testing"`, terminal status, assigned and observed fingerprints, timestamps, and tool versions;
- exact setup, start, seed/reset, and test commands with outcomes;
- coverage entries for every route, role, critical action, acceptance criterion, supported browser/device class, viewport, state, and accessibility obligation;
- artifact paths for reports, traces, screenshots, videos, console/network logs, and raw runner output;
- `FIND-###` entries linked to acceptance IDs and reproducible evidence;
- an empty `changed_files` list because the UI-testing lane is source-read-only.

At the synchronization barrier, the orchestrator validates report shape and identity, confirms that all required UI tasks finished on the frozen fingerprint, and combines the result with peer code, security, and test reports. It must reject stale or incomplete coverage and route repairs to workers. After any relevant source, test, dependency or lockfile, schema or migration, or configuration mutation, the UI report and every peer mandatory lane report for that barrier are stale regardless of perceived impact. Compute and freeze a fresh fingerprint, then redispatch the complete mandatory review and validation batch, including every required UI task. An impacted-flow UI retest may run first only as a fast repair diagnostic; it is not barrier evidence.

## 8. Failure reports

Assign `BUG-###` in the defect record and `FIND-###` in the worker report. Record:

- acceptance, route, role, and action IDs;
- fixture, viewport/device, browser/runtime, and fingerprint;
- exact reproduction steps;
- expected and actual result;
- severity, user impact, and frequency;
- console/network evidence and artifact paths;
- suspected layer without presenting speculation as fact;
- retest evidence after a repair.

The UI-testing worker never repairs product source. The orchestrator routes the report to an implementation worker and schedules retesting against the next frozen fingerprint.
