<!-- factory-template: remove this line after replacing every bracketed prompt. -->
# Product Specification

## Product goal

[State the primary actor, problem, and successful outcome in one sentence.]

## Scope

### In scope

- [Coherent MVP behavior]

### Out of scope

- [Explicit non-goal]

## Actors, roles, and permissions

| Role | Goals | Allowed actions | Forbidden actions |
|---|---|---|---|
| [Role] | [Goal] | [Actions] | [Actions] |

## User and operator journeys

### Primary journey

1. [Precondition and action]
2. [Observable result]

### Exceptional and recovery journeys

- [Empty, invalid, denied, unavailable, duplicate, interrupted, or destructive case]

## Functional requirements

| ID | Requirement | Priority | Verification |
|---|---|---|---|
| FR-001 | [Observable behavior] | Must | [Test or procedure] |

## Non-functional requirements

| ID | Requirement/metric | Verification |
|---|---|---|
| NFR-001 | [Measurable quality or operational constraint] | [Test or evidence] |

## Business rules and edge cases

- [Invariant, lifecycle rule, boundary, or concurrency behavior]

## Data, privacy, and retention

| Data class | Source/owner | Sensitivity | Storage/retention | Access/deletion |
|---|---|---|---|---|
| [Data] | [Source] | [Public/internal/confidential/regulated] | [Policy] | [Policy] |

## Assumptions and dependencies

| ID | Assumption/dependency | Impact | Reversal or fallback |
|---|---|---|---|
| ASM-001 | [Low-risk default] | [Impact] | [How to change it] |

## Risks and open decisions

| ID | Risk/decision | Likelihood/impact | Mitigation or blocking question |
|---|---|---|---|
| RISK-001 | [Risk] | [Rating] | [Mitigation] |

## Acceptance criteria

| ID | Requirement | Preconditions | Action | Expected result | Verification |
|---|---|---|---|---|---|
| AC-001 | FR-001 | [State and role] | [Action] | [Observable result] | [Executable test/procedure] |

## Specification gate

- Independent reviewer: [agent/person and date]
- Artifact snapshot: [sha256 of reviewed specification]
- Review batch/reports: [BATCH-### and .factory/reports paths]
- Decision: [pass/fail]
- Evidence: [report path]
- Remaining material ambiguity: [none or blocker]
