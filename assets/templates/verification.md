<!-- factory-template: remove this line after replacing every bracketed prompt. -->
# Verification Report

## Environment

- Source fingerprint: [sha256]
- OS/runtime/tool versions: [versions]
- Clean-install conditions: [conditions]
- External services: [local/stubbed/dedicated test environment]

## Worker batch barriers

| Batch | Purpose | Frozen fingerprint/snapshot | Required tasks | Accepted reports | Barrier disposition |
|---|---|---|---|---|---|
| BATCH-001 | [review/validation purpose] | [sha256] | [TASK IDs] | [.factory/reports/BATCH-001/*.json] | [pass/fail/blocked] |

## Scheduler failures

| Batch/task | Disposition | Timestamp | Attempts | Last fingerprint | Available evidence | Replacement |
|---|---|---|---|---|---|---|
| [BATCH-###/TASK-###] | [timed-out/crashed/cancelled/superseded] | [UTC] | [count] | [sha256] | [paths] | [new BATCH/TASK or blocker] |

## Gate evidence

| Check | Status | Exact command/procedure | Exit/outcome | Evidence | Notes or N/A rationale |
|---|---|---|---|---|---|
| Clean install | [pass/fail/N/A] | [command] | [code] | [.factory/evidence/path] | [notes] |
| Format/lint | [pass/fail/N/A] | [command] | [code] | [path] | [notes] |
| Type/compile/build/package | [pass/fail/N/A] | [command] | [code] | [path] | [notes] |
| Unit/component | [pass/fail/N/A] | [command] | [code] | [path] | [counts/skips] |
| Integration/contract | [pass/fail/N/A] | [command] | [code] | [path] | [coverage] |
| System/E2E | [pass/fail/N/A] | [command] | [code] | [path] | [coverage] |
| UI/accessibility | [pass/fail/N/A] | [delegated ui-testing/$playwright/platform-native procedure] | [outcome] | [worker report and artifacts] | [route/role/action/browser/accessibility coverage or N/A] |
| Security/secrets/dependencies | [pass/fail/N/A] | [commands] | [codes] | [paths] | [findings/waivers] |
| Data migration/rollback/restore | [pass/fail/N/A] | [command/procedure] | [outcome] | [path] | [coverage/N/A] |
| Performance/reliability | [pass/fail/N/A] | [command/procedure] | [outcome] | [path] | [budgets/N/A] |
| Operability/documentation | [pass/fail/N/A] | [procedure] | [outcome] | [path] | [notes] |
| Supply chain/SBOM/license | [pass/fail/N/A] | [commands] | [codes] | [paths] | [policy/N/A] |

## Requirement and slice summary

- Requirements covered: [IDs/count]
- Acceptance criteria passed: [IDs/count]
- Slices accepted: [IDs/count]
- Skipped/quarantined/flaky tests: [none or details]

## Findings and disposition

| ID | Severity | Finding | Disposition | Retest evidence |
|---|---|---|---|---|
| BUG-001 | [severity] | [finding] | [fixed/blocked/explicit residual risk] | [path] |

## Validation gate

- Decision: [pass/fail]
- Timestamp: [UTC]
- Final fingerprint: [sha256]
- Accepted validation batch/reports: [BATCH-### and report paths]
- Residual risks/waivers: [none or explicit list]
