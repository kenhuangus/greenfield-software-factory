<!-- factory-template: remove this line after replacing every bracketed prompt. -->
# Review-Ready Handoff

## Outcome

[State what is working and explicitly distinguish review-ready, staged, deployed, and released.]

## Project location and contents

- Project root: [path]
- Main components: [components]
- Final source fingerprint: [sha256]

## Install, configure, run, build, and test

```text
[Exact verified commands in execution order]
```

- Required configuration: [variable names and sources; never values]
- Local substitutes/fixtures: [services and seed/reset commands]

## Architecture and behavior

- Architecture summary: [summary]
- Primary user/operator journeys: [journeys]
- Data and external dependencies: [summary]

## Scope and coverage

- Requirements delivered: [FR/NFR IDs]
- Acceptance criteria passed: [AC IDs]
- Explicit non-outcomes/deferred scope: [items]
- Evidence index: [.factory/verification.md and related paths]
- Accepted worker batches: [BATCH-### IDs and report directories]

## Assumptions, limitations, and residual risk

| Kind/ID | Description | Impact | Recommended follow-up |
|---|---|---|---|
| [ASM/RISK/BUG/waiver] | [Description] | [Impact] | [Action] |

## Deployment, migration, operations, and rollback

- Deployment status and required authorization: [status]
- Migration/compatibility notes: [notes]
- Rollback/restore notes: [notes]
- Health, logs, diagnostics, and runbook: [paths/commands]

## Final human review

- [ ] Confirm the product behavior and explicit non-goals.
- [ ] Review assumptions, residual risks, and waivers.
- [ ] Re-run or inspect the linked evidence on the final fingerprint.
- [ ] Supply any required credentials/configuration through the approved channel.
- [ ] Separately authorize deployment, publishing, or release if desired.
