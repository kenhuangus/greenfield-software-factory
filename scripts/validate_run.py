#!/usr/bin/env python3
"""Validate factory state, artifacts, plan DAG, traceability, and freshness."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from factory_state import (
    FINGERPRINT_RE,
    GATES,
    PHASES,
    PROFILES,
    SOURCE_GATES,
    FactoryStateError,
    compute_fingerprint,
    load_state,
    project_root,
    unresolved_blockers,
)


TEMPLATE_MARKER = "<!-- factory-template:"
REQUIREMENT_RE = re.compile(r"\b(?:FR|NFR)-\d{3,}\b")
ACCEPTANCE_RE = re.compile(r"\bAC-\d{3,}\b")
SLICE_RE = re.compile(r"^SLICE-\d{3,}$")
ALLOWED_SLICE_STATUS = {
    "pending",
    "ready",
    "implementing",
    "verifying",
    "reviewing",
    "repairing",
    "accepted",
    "blocked",
}
REQUIRED_ARTIFACTS = {
    "product_spec": "product-spec.md",
    "architecture": "architecture.md",
    "feature_plan": "feature-plan.json",
    "traceability": "traceability.md",
    "verification": "verification.md",
    "handoff": "handoff.md",
}
PRIMARY_ARTIFACT = {
    "requirements": "product_spec",
    "architecture": "architecture",
    "planning": "feature_plan",
    "implementation": "traceability",
    "validation": "verification",
    "handoff": "handoff",
}
ARTIFACT_PHASE = {artifact: phase for phase, artifact in PRIMARY_ARTIFACT.items()}
REQUIRED_FEATURE_FIELDS = {
    "id",
    "title",
    "status",
    "depends_on",
    "requirements",
    "acceptance_criteria",
    "files",
    "tests",
    "risk",
    "evidence",
    "source_fingerprint",
}


def safe_artifact_path(root: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    relative = Path(raw)
    if relative.is_absolute() or relative.anchor or relative.drive:
        return None
    if ".." in relative.parts:
        return None
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def read_text(path: Path, errors: list[str], label: str) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        errors.append(f"Cannot read {label} at {path}: {exc}")
        return ""


def validate_feature_plan(
    value: Any,
    spec_requirements: set[str],
    spec_acceptance: set[str],
    require_plan_coverage: bool,
    errors: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        errors.append("feature-plan.json root must be an object")
        return []
    if value.get("schema_version") != 1:
        errors.append("feature-plan.json schema_version must equal 1")
    extra_top = set(value) - {"schema_version", "features"}
    if extra_top:
        errors.append(f"feature-plan.json has unsupported keys: {sorted(extra_top)}")
    features = value.get("features")
    if not isinstance(features, list):
        errors.append("feature-plan.json features must be an array")
        return []
    if require_plan_coverage and not features:
        errors.append("feature plan contains no vertical slices")

    by_id: dict[str, dict[str, Any]] = {}
    covered_requirements: set[str] = set()
    covered_acceptance: set[str] = set()

    for index, feature in enumerate(features):
        label = f"feature[{index}]"
        if not isinstance(feature, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = REQUIRED_FEATURE_FIELDS - set(feature)
        extra = set(feature) - REQUIRED_FEATURE_FIELDS
        if missing:
            errors.append(f"{label} is missing fields: {sorted(missing)}")
        if extra:
            errors.append(f"{label} has unsupported fields: {sorted(extra)}")

        feature_id = feature.get("id")
        if not isinstance(feature_id, str) or not SLICE_RE.fullmatch(feature_id):
            errors.append(f"{label}.id must match SLICE-###")
            continue
        if feature_id in by_id:
            errors.append(f"duplicate feature ID: {feature_id}")
        by_id[feature_id] = feature

        if (
            not isinstance(feature.get("title"), str)
            or not feature.get("title", "").strip()
        ):
            errors.append(f"{feature_id}.title must be a non-empty string")
        if feature.get("status") not in ALLOWED_SLICE_STATUS:
            errors.append(f"{feature_id}.status is invalid: {feature.get('status')!r}")
        if feature.get("risk") not in {"low", "medium", "high"}:
            errors.append(f"{feature_id}.risk must be low, medium, or high")

        for field in (
            "depends_on",
            "requirements",
            "acceptance_criteria",
            "files",
            "tests",
            "evidence",
        ):
            if not isinstance(feature.get(field), list):
                errors.append(f"{feature_id}.{field} must be an array")

        dependencies = feature.get("depends_on", [])
        requirements = feature.get("requirements", [])
        acceptance = feature.get("acceptance_criteria", [])
        files = feature.get("files", [])
        tests = feature.get("tests", [])
        evidence = feature.get("evidence", [])
        if isinstance(dependencies, list):
            valid_dependencies: list[str] = []
            for item in dependencies:
                if not isinstance(item, str) or not SLICE_RE.fullmatch(item):
                    errors.append(f"{feature_id} has invalid dependency ID: {item!r}")
                else:
                    valid_dependencies.append(item)
            if len(valid_dependencies) != len(set(valid_dependencies)):
                errors.append(f"{feature_id}.depends_on contains duplicates")
        if isinstance(requirements, list):
            if not requirements:
                errors.append(f"{feature_id}.requirements must not be empty")
            valid_requirements: list[str] = []
            for item in requirements:
                if not isinstance(item, str) or not re.fullmatch(
                    r"(?:FR|NFR)-\d{3,}", item
                ):
                    errors.append(f"{feature_id} has invalid requirement ID: {item!r}")
                else:
                    valid_requirements.append(item)
                    covered_requirements.add(item)
                    if item not in spec_requirements:
                        errors.append(
                            f"{feature_id} references unknown requirement {item}"
                        )
            if len(valid_requirements) != len(set(valid_requirements)):
                errors.append(f"{feature_id}.requirements contains duplicates")
        if isinstance(acceptance, list):
            if not acceptance:
                errors.append(f"{feature_id}.acceptance_criteria must not be empty")
            valid_acceptance: list[str] = []
            for item in acceptance:
                if not isinstance(item, str) or not re.fullmatch(r"AC-\d{3,}", item):
                    errors.append(f"{feature_id} has invalid acceptance ID: {item!r}")
                else:
                    valid_acceptance.append(item)
                    covered_acceptance.add(item)
                    if item not in spec_acceptance:
                        errors.append(
                            f"{feature_id} references unknown acceptance criterion {item}"
                        )
            if len(valid_acceptance) != len(set(valid_acceptance)):
                errors.append(f"{feature_id}.acceptance_criteria contains duplicates")
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"{feature_id}.files must contain only non-empty strings"
                    )
            valid_files = [item for item in files if isinstance(item, str)]
            if len(valid_files) != len(set(valid_files)):
                errors.append(f"{feature_id}.files contains duplicates")
        if isinstance(tests, list):
            if not tests:
                errors.append(f"{feature_id}.tests must not be empty")
            for item in tests:
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"{feature_id}.tests must contain only non-empty strings"
                    )
            valid_tests = [item for item in tests if isinstance(item, str)]
            if len(valid_tests) != len(set(valid_tests)):
                errors.append(f"{feature_id}.tests contains duplicates")
        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, str) or not item.strip():
                    errors.append(
                        f"{feature_id}.evidence must contain only non-empty strings"
                    )

        fingerprint = feature.get("source_fingerprint")
        if fingerprint is not None and (
            not isinstance(fingerprint, str)
            or not FINGERPRINT_RE.fullmatch(fingerprint)
        ):
            errors.append(f"{feature_id}.source_fingerprint is invalid")

        if feature.get("status") == "accepted":
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"accepted {feature_id} requires evidence")
            if not isinstance(fingerprint, str) or not FINGERPRINT_RE.fullmatch(
                fingerprint
            ):
                errors.append(f"accepted {feature_id} requires a source_fingerprint")
    for feature_id, feature in by_id.items():
        dependencies = feature.get("depends_on", [])
        if not isinstance(dependencies, list):
            continue
        for dependency in dependencies:
            if not isinstance(dependency, str) or not SLICE_RE.fullmatch(dependency):
                continue
            if dependency == feature_id:
                errors.append(f"{feature_id} cannot depend on itself")
            elif dependency not in by_id:
                errors.append(f"{feature_id} depends on unknown slice {dependency}")
            elif (
                feature.get("status") not in {"pending", "blocked"}
                and by_id[dependency].get("status") != "accepted"
            ):
                errors.append(
                    f"{feature_id} cannot be {feature.get('status')!r} until "
                    f"dependency {dependency} is accepted"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(feature_id: str, trail: list[str]) -> None:
        if feature_id in visiting:
            cycle_start = trail.index(feature_id) if feature_id in trail else 0
            errors.append(
                f"feature dependency cycle: {' -> '.join(trail[cycle_start:] + [feature_id])}"
            )
            return
        if feature_id in visited:
            return
        visiting.add(feature_id)
        dependencies = by_id[feature_id].get("depends_on", [])
        if isinstance(dependencies, list):
            for dependency in dependencies:
                if (
                    isinstance(dependency, str)
                    and SLICE_RE.fullmatch(dependency)
                    and dependency in by_id
                ):
                    visit(dependency, trail + [feature_id])
        visiting.remove(feature_id)
        visited.add(feature_id)

    for feature_id in sorted(by_id):
        visit(feature_id, [])

    if require_plan_coverage:
        missing_requirements = sorted(spec_requirements - covered_requirements)
        missing_acceptance = sorted(spec_acceptance - covered_acceptance)
        if missing_requirements:
            errors.append(
                f"requirements missing from feature plan: {missing_requirements}"
            )
        if missing_acceptance:
            errors.append(
                f"acceptance criteria missing from feature plan: {missing_acceptance}"
            )
    else:
        missing_requirements = sorted(spec_requirements - covered_requirements)
        missing_acceptance = sorted(spec_acceptance - covered_acceptance)
        if features and missing_requirements:
            warnings.append(
                f"requirements not yet mapped in plan: {missing_requirements}"
            )
        if features and missing_acceptance:
            warnings.append(
                f"acceptance criteria not yet mapped in plan: {missing_acceptance}"
            )

    return [feature for feature in features if isinstance(feature, dict)]


def run_validation(root: Path, gate_mode: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        state = load_state(root)
    except FactoryStateError as exc:
        return [str(exc)], warnings

    current = state["current_phase"]
    current_index = PHASES.index(current)
    if state.get("profile") not in PROFILES:
        errors.append(f"invalid project profile: {state.get('profile')!r}")
    if not isinstance(state.get("goal"), str) or not state.get("goal", "").strip():
        errors.append("state goal must be a non-empty string")
    if (
        not isinstance(state.get("authority_envelope"), str)
        or not state.get("authority_envelope", "").strip()
    ):
        errors.append("state authority_envelope must be a non-empty string")

    gates = state.get("gates", {})
    if not isinstance(gates, dict):
        errors.append("state gates must be an object")
        gates = {}
    for index, name in enumerate(GATES):
        gate = gates.get(name)
        if not isinstance(gate, dict):
            errors.append(f"missing or invalid {name} gate")
            continue
        status = gate.get("status")
        if status not in {"pending", "passed", "failed"}:
            errors.append(f"invalid {name} gate status: {status!r}")
        evidence = gate.get("evidence")
        if status in {"passed", "failed"} and (
            not isinstance(evidence, list)
            or not any(isinstance(item, str) and item.strip() for item in evidence)
        ):
            errors.append(f"{name} gate status {status} requires evidence")
        if index < current_index and status != "passed":
            errors.append(f"prior phase gate {name} is not passed")
        if index > current_index and status != "pending":
            errors.append(f"future phase gate {name} must be pending")

    artifacts = state.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("state artifacts must be an object")
        artifacts = {}
    artifact_text: dict[str, str] = {}
    for name, expected_name in REQUIRED_ARTIFACTS.items():
        raw = artifacts.get(name)
        path = safe_artifact_path(root, raw)
        if path is None:
            errors.append(f"artifact {name} has a missing or unsafe path: {raw!r}")
            continue
        if not path.is_file():
            errors.append(f"artifact {name} does not exist: {path}")
            continue
        if path.name != expected_name:
            warnings.append(f"artifact {name} uses nonstandard filename {path.name!r}")
        if path.suffix.lower() in {".md", ".json"}:
            artifact_text[name] = read_text(path, errors, name)

    for name, text in artifact_text.items():
        if TEMPLATE_MARKER in text:
            phase = ARTIFACT_PHASE.get(name)
            phase_passed = bool(
                phase and gates.get(phase, {}).get("status") == "passed"
            )
            phase_due = bool(
                gate_mode and phase and PHASES.index(phase) <= current_index
            )
            if current == "complete" or phase_passed or phase_due:
                errors.append(
                    f"artifact {name} still contains the factory template marker"
                )
            else:
                warnings.append(f"artifact {name} is still a template")

    spec_text = artifact_text.get("product_spec", "")
    spec_requirements = set(REQUIREMENT_RE.findall(spec_text))
    spec_acceptance = set(ACCEPTANCE_RE.findall(spec_text))
    requirements_due = (
        current == "complete"
        or gates.get("requirements", {}).get("status") == "passed"
        or (gate_mode and current_index >= PHASES.index("requirements"))
    )
    if requirements_due:
        if not spec_requirements:
            errors.append("product specification contains no FR/NFR IDs")
        if not spec_acceptance:
            errors.append("product specification contains no AC IDs")

    plan_value: Any = None
    if "feature_plan" in artifact_text:
        plan_text = artifact_text["feature_plan"]
        if not plan_text.strip():
            errors.append("feature-plan.json is empty")
        else:
            try:
                plan_value = json.loads(plan_text)
            except json.JSONDecodeError as exc:
                errors.append(f"feature-plan.json is invalid JSON: {exc}")
    require_plan_coverage = (
        current == "complete"
        or gates.get("planning", {}).get("status") == "passed"
        or (gate_mode and current_index >= PHASES.index("planning"))
    )
    features: list[dict[str, Any]] = []
    if plan_value is not None:
        features = validate_feature_plan(
            plan_value,
            spec_requirements,
            spec_acceptance,
            require_plan_coverage,
            errors,
            warnings,
        )

    accepted_required = (
        current == "complete"
        or gates.get("implementation", {}).get("status") == "passed"
        or (gate_mode and current_index >= PHASES.index("implementation"))
    )
    if accepted_required:
        not_accepted = [
            feature.get("id", "<unknown>")
            for feature in features
            if feature.get("status") != "accepted"
        ]
        if not_accepted:
            errors.append(f"slices not accepted: {not_accepted}")

    blocked_features = [
        feature.get("id", "<unknown>")
        for feature in features
        if feature.get("status") == "blocked"
    ]
    if blocked_features and (
        state.get("status") != "blocked" or not unresolved_blockers(state)
    ):
        errors.append(
            f"blocked slices require a blocked run and unresolved blocker: {blocked_features}"
        )

    traceability = artifact_text.get("traceability", "")
    traceability_required = (
        current == "complete"
        or gates.get("implementation", {}).get("status") == "passed"
        or (gate_mode and current_index >= PHASES.index("implementation"))
    )
    if traceability_required:
        trace_requirements = set(REQUIREMENT_RE.findall(traceability))
        trace_acceptance = set(ACCEPTANCE_RE.findall(traceability))
        missing_trace = sorted(
            identifier
            for identifier in (spec_requirements | spec_acceptance)
            if identifier not in (trace_requirements | trace_acceptance)
        )
        if missing_trace:
            errors.append(f"IDs missing from traceability.md: {missing_trace}")

    passed_source_gates = [
        name
        for name in GATES
        if name in SOURCE_GATES and gates.get(name, {}).get("status") == "passed"
    ]
    if passed_source_gates:
        try:
            current_fingerprint = compute_fingerprint(root)
        except FactoryStateError as exc:
            errors.append(str(exc))
            current_fingerprint = None
        if current_fingerprint:
            for name in passed_source_gates:
                gate = gates.get(name, {}) if isinstance(gates, dict) else {}
                if gate.get("source_fingerprint") != current_fingerprint:
                    errors.append(
                        f"{name} gate is stale: recorded {gate.get('source_fingerprint')}, "
                        f"current {current_fingerprint}"
                    )

    if gate_mode and current == "handoff":
        validation_gate = gates.get("validation", {})
        if validation_gate.get("status") != "passed":
            errors.append("handoff requires a passed validation gate")

    if current == "complete":
        for name in GATES:
            if gates.get(name, {}).get("status") != "passed":
                errors.append(f"completed run requires passed {name} gate")
        if any(feature.get("status") != "accepted" for feature in features):
            errors.append("completed run contains an unaccepted slice")

    return errors, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a Greenfield Software Factory run."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Require the current phase to be ready for its gate",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable output"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        root = project_root(args.project)
    except FactoryStateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        errors, warnings = run_validation(root, args.gate)
    except (FactoryStateError, OSError) as exc:
        print(f"ERROR: validation could not complete: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {"valid": not errors, "errors": errors, "warnings": warnings}, indent=2
            )
        )
    else:
        for warning in warnings:
            print(f"WARNING: {warning}")
        for error in errors:
            print(f"ERROR: {error}")
        if not errors:
            print(f"Factory run is valid ({len(warnings)} warning(s)).")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
