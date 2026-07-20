#!/usr/bin/env python3
"""Safely manage durable state for Greenfield Software Factory runs."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PHASES = [
    "requirements",
    "architecture",
    "planning",
    "initialization",
    "implementation",
    "validation",
    "handoff",
    "complete",
]
GATES = PHASES[:-1]
PROFILES = [
    "web-app",
    "api-service",
    "cli-library",
    "mobile-desktop",
    "data-ml",
    "other",
]
SOURCE_GATES = {"implementation", "validation", "handoff"}
GATE_STATUSES = {"pending", "passed", "failed"}
RUN_STATUSES = {"active", "blocked", "complete"}
FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ASSUMPTION_ID_RE = re.compile(r"^ASM-[0-9]{3,}$")
BLOCKER_ID_RE = re.compile(r"^BLK-[0-9]{3,}$")
RFC3339_DATETIME_RE = re.compile(
    r"^(\d{4})-(0[1-9]|1[0-2])-(\d{2})[Tt]"
    r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?"
    r"(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)

FACTORY_DIR = ".factory"
STATE_FILE = "state.json"
TEMPLATE_MAP = {
    "product-spec.md": "product_spec",
    "architecture.md": "architecture",
    "feature-plan.json": "feature_plan",
    "traceability.md": "traceability",
    "verification.md": "verification",
    "handoff.md": "handoff",
}

IGNORED_DIRS = {
    ".git",
    FACTORY_DIR,
    ".codex",
    ".cache",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "venv",
}


class FactoryStateError(RuntimeError):
    """Raised for invalid or unsafe state operations."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def nonempty(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise FactoryStateError(f"{label} must be a non-empty string.")
    return normalized


def is_rfc3339_datetime(value: Any) -> bool:
    """Return whether a value matches JSON Schema's RFC 3339 date-time format."""

    if not isinstance(value, str):
        return False
    match = RFC3339_DATETIME_RE.fullmatch(value)
    if match is None:
        return False
    year, month, day = (int(part) for part in match.groups())
    if year == 0:
        return False
    return day <= calendar.monthrange(year, month)[1]


def _require_datetime(value: Any, label: str) -> None:
    if not is_rfc3339_datetime(value):
        raise FactoryStateError(f"{label} must be an RFC 3339 date-time string.")


def is_link_like(path: Path) -> bool:
    """Return whether a path is a symlink or Windows directory junction."""

    try:
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(is_junction and is_junction())
    except OSError as exc:
        raise FactoryStateError(f"Cannot inspect path {path}: {exc}") from exc


def ensure_within_root(root: Path, candidate: Path, label: str) -> Path:
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise FactoryStateError(f"{label} must stay inside the project root.") from exc
    return resolved


def factory_dir(root: Path) -> Path:
    path = root / FACTORY_DIR
    if is_link_like(path):
        raise FactoryStateError(
            f"Factory directory must not be a symlink or junction: {path}"
        )
    ensure_within_root(root, path, "Factory directory")
    if path.exists() and not path.is_dir():
        raise FactoryStateError(f"Factory path is not a directory: {path}")
    return path


def project_root(raw: str) -> Path:
    try:
        root = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise FactoryStateError(
            f"Cannot resolve project directory {raw!r}: {exc}"
        ) from exc
    if not root.is_dir():
        raise FactoryStateError(f"Project directory does not exist: {root}")
    return root


def state_path(root: Path) -> Path:
    path = factory_dir(root) / STATE_FILE
    if is_link_like(path):
        raise FactoryStateError(f"Factory state must not be a symlink: {path}")
    ensure_within_root(root, path, "Factory state")
    return path


def append_history(state: dict[str, Any], event: str, details: str) -> None:
    history = state.get("history")
    if not isinstance(history, list):
        raise FactoryStateError("State field 'history' must be an array.")
    history.append({"at": utc_now(), "event": event, "details": details})


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    descriptor, raw_temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = expected - set(value)
    extra = set(value) - expected
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing {sorted(missing)}")
        if extra:
            parts.append(f"unsupported {sorted(extra)}")
        raise FactoryStateError(f"{label} has invalid fields: {'; '.join(parts)}.")


def _validate_record_list(
    value: Any,
    *,
    label: str,
    fields: set[str],
    id_field: str | None = None,
    id_pattern: re.Pattern[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise FactoryStateError(f"State field {label!r} must be an array.")
    result: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(item, dict):
            raise FactoryStateError(f"{item_label} must be an object.")
        _require_exact_keys(item, fields, item_label)
        if id_field is not None and id_pattern is not None:
            identifier = item.get(id_field)
            if not isinstance(identifier, str) or not id_pattern.fullmatch(identifier):
                raise FactoryStateError(f"{item_label}.{id_field} has an invalid ID.")
            if identifier in identifiers:
                raise FactoryStateError(f"Duplicate {label} ID: {identifier}.")
            identifiers.add(identifier)
        result.append(item)
    return result


def validate_state_shape(value: Any) -> dict[str, Any]:
    """Validate the durable state shape before any command relies on it."""

    if not isinstance(value, dict):
        raise FactoryStateError("Factory state root must be a JSON object.")
    required = {
        "schema_version",
        "goal",
        "profile",
        "authority_envelope",
        "status",
        "current_phase",
        "created_at",
        "updated_at",
        "artifacts",
        "gates",
        "assumptions",
        "blockers",
        "history",
    }
    _require_exact_keys(value, required, "Factory state")

    if value.get("schema_version") != 1:
        raise FactoryStateError(
            f"Unsupported state schema_version: {value.get('schema_version')!r}"
        )
    for field in ("goal", "authority_envelope"):
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            raise FactoryStateError(
                f"State field {field!r} must be a non-empty string."
            )
    for field in ("created_at", "updated_at"):
        _require_datetime(value.get(field), f"State field {field!r}")
    if value.get("profile") not in PROFILES:
        raise FactoryStateError(f"Unknown project profile: {value.get('profile')!r}")
    if value.get("current_phase") not in PHASES:
        raise FactoryStateError(
            f"Unknown current phase: {value.get('current_phase')!r}"
        )
    if value.get("status") not in RUN_STATUSES:
        raise FactoryStateError(f"Unknown run status: {value.get('status')!r}")

    artifacts = value.get("artifacts")
    if not isinstance(artifacts, dict):
        raise FactoryStateError("State field 'artifacts' must be an object.")
    for name, raw_path in artifacts.items():
        if not isinstance(name, str) or not name.strip():
            raise FactoryStateError("Artifact names must be non-empty strings.")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise FactoryStateError(f"Artifact {name!r} must have a non-empty path.")

    gates = value.get("gates")
    if not isinstance(gates, dict):
        raise FactoryStateError("State field 'gates' must be an object.")
    _require_exact_keys(gates, set(GATES), "State gates")
    gate_fields = {"status", "evidence", "source_fingerprint", "updated_at"}
    for name in GATES:
        gate = gates[name]
        if not isinstance(gate, dict):
            raise FactoryStateError(f"Gate {name!r} must be an object.")
        _require_exact_keys(gate, gate_fields, f"Gate {name!r}")
        status = gate.get("status")
        if status not in GATE_STATUSES:
            raise FactoryStateError(f"Gate {name!r} has invalid status {status!r}.")
        evidence = gate.get("evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(item, str) or not item.strip() for item in evidence
        ):
            raise FactoryStateError(
                f"Gate {name!r} evidence must contain only non-empty strings."
            )
        if status in {"passed", "failed"} and not evidence:
            raise FactoryStateError(f"Gate {name!r} status {status} requires evidence.")
        if status == "pending" and evidence:
            raise FactoryStateError(f"Pending gate {name!r} cannot contain evidence.")
        fingerprint = gate.get("source_fingerprint")
        if fingerprint is not None and (
            not isinstance(fingerprint, str)
            or not FINGERPRINT_RE.fullmatch(fingerprint)
        ):
            raise FactoryStateError(f"Gate {name!r} has an invalid source fingerprint.")
        if name in SOURCE_GATES and status in {"passed", "failed"}:
            if fingerprint is None:
                raise FactoryStateError(
                    f"Gate {name!r} status {status} requires a source fingerprint."
                )
        elif name not in SOURCE_GATES and fingerprint is not None:
            raise FactoryStateError(
                f"Gate {name!r} must not contain a source fingerprint."
            )
        elif status == "pending" and fingerprint is not None:
            raise FactoryStateError(
                f"Pending gate {name!r} must not contain a source fingerprint."
            )
        updated_at = gate.get("updated_at")
        if status == "pending" and updated_at is not None:
            raise FactoryStateError(f"Pending gate {name!r} must not have updated_at.")
        if updated_at is not None:
            _require_datetime(updated_at, f"Gate {name!r} updated_at")

    assumptions = _validate_record_list(
        value.get("assumptions"),
        label="assumptions",
        fields={"id", "text", "at"},
        id_field="id",
        id_pattern=ASSUMPTION_ID_RE,
    )
    for index, item in enumerate(assumptions):
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise FactoryStateError(
                f"assumptions[{index}].text must be a non-empty string."
            )
        _require_datetime(item.get("at"), f"assumptions[{index}].at")

    blockers = _validate_record_list(
        value.get("blockers"),
        label="blockers",
        fields={
            "id",
            "reason",
            "phase",
            "at",
            "resolved",
            "resolved_at",
            "resolution",
        },
        id_field="id",
        id_pattern=BLOCKER_ID_RE,
    )
    for index, item in enumerate(blockers):
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise FactoryStateError(
                f"blockers[{index}].reason must be a non-empty string."
            )
        _require_datetime(item.get("at"), f"blockers[{index}].at")
        if item.get("phase") not in PHASES[:-1]:
            raise FactoryStateError(f"blockers[{index}].phase is invalid.")
        if not isinstance(item.get("resolved"), bool):
            raise FactoryStateError(f"blockers[{index}].resolved must be boolean.")
        resolved_at = item.get("resolved_at")
        resolution = item.get("resolution")
        if item["resolved"]:
            _require_datetime(resolved_at, f"Resolved blocker {item['id']} resolved_at")
            if not isinstance(resolution, str) or not resolution.strip():
                raise FactoryStateError(
                    f"Resolved blocker {item['id']} requires a resolution."
                )
        elif resolved_at is not None or resolution is not None:
            raise FactoryStateError(
                f"Unresolved blocker {item['id']} cannot have resolution fields."
            )

    status = value["status"]
    current_phase = value["current_phase"]
    unresolved = [item for item in blockers if not item["resolved"]]
    if (status == "complete") != (current_phase == "complete"):
        raise FactoryStateError(
            "Run status and current phase must both be 'complete' or both be incomplete."
        )
    if status == "blocked" and not unresolved:
        raise FactoryStateError("Blocked run requires an unresolved blocker.")
    if status != "blocked" and unresolved:
        raise FactoryStateError("An unresolved blocker requires blocked run status.")

    history = _validate_record_list(
        value.get("history"),
        label="history",
        fields={"at", "event", "details"},
    )
    for index, item in enumerate(history):
        _require_datetime(item.get("at"), f"history[{index}].at")
        if not isinstance(item.get("event"), str) or not item["event"].strip():
            raise FactoryStateError(
                f"history[{index}].event must be a non-empty string."
            )
        if not isinstance(item.get("details"), str) or not item["details"].strip():
            raise FactoryStateError(
                f"history[{index}].details must be a non-empty string."
            )
    return value


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.is_file():
        raise FactoryStateError(
            f"Factory state is missing: {path}. Run the init command first."
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FactoryStateError(f"Cannot read valid factory state: {exc}") from exc
    return validate_state_shape(value)


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(state_path(root), state)


def compute_fingerprint(root: Path) -> str:
    """Hash relevant project files while excluding run evidence and build caches."""

    digest = hashlib.sha256()
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        traversable: list[str] = []
        for name in sorted(directories):
            if name in IGNORED_DIRS:
                continue
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if is_link_like(path):
                digest.update(relative.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0directory-link\0")
                try:
                    target = os.readlink(path)
                except OSError as exc:
                    raise FactoryStateError(
                        f"Cannot fingerprint {relative}: {exc}"
                    ) from exc
                digest.update(target.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0")
            else:
                traversable.append(name)
        directories[:] = traversable
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
            try:
                if path.is_symlink():
                    digest.update(b"symlink\0")
                    digest.update(
                        os.readlink(path).encode("utf-8", errors="surrogateescape")
                    )
                else:
                    digest.update(b"file\0")
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
            except OSError as exc:
                raise FactoryStateError(
                    f"Cannot fingerprint {relative}: {exc}"
                ) from exc
            digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def unresolved_blockers(state: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = state.get("blockers", [])
    if not isinstance(blockers, list):
        raise FactoryStateError("State field 'blockers' must be an array.")
    return [
        item for item in blockers if isinstance(item, dict) and not item.get("resolved")
    ]


def next_identifier(items: list[dict[str, Any]], prefix: str) -> str:
    highest = 0
    for item in items:
        raw = str(item.get("id", ""))
        if raw.startswith(f"{prefix}-"):
            try:
                highest = max(highest, int(raw.split("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}-{highest + 1:03d}"


def require_active(state: dict[str, Any]) -> None:
    if state.get("status") != "active":
        raise FactoryStateError(
            f"Run status is {state.get('status')!r}; resume it before this operation."
        )


def require_passed_gates_fresh(
    root: Path, state: dict[str, Any], names: list[str]
) -> None:
    current_fingerprint: str | None = None
    for name in names:
        gate = state["gates"][name]
        if gate.get("status") != "passed":
            raise FactoryStateError(
                f"Prior phase gate {name!r} is {gate.get('status')!r}, not 'passed'."
            )
        if name in SOURCE_GATES:
            if current_fingerprint is None:
                current_fingerprint = compute_fingerprint(root)
            if gate.get("source_fingerprint") != current_fingerprint:
                raise FactoryStateError(
                    f"Prior phase gate {name!r} is stale. Recorded "
                    f"{gate.get('source_fingerprint')}, current {current_fingerprint}."
                )


def command_init(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    goal = nonempty(args.goal, "Goal")
    authority = nonempty(args.authority, "Authority envelope")
    path = state_path(root)
    if path.exists():
        raise FactoryStateError(
            f"Factory state already exists at {path}; resume it instead of replacing it."
        )

    factory = factory_dir(root)
    skill_root = Path(__file__).resolve().parent.parent
    template_root = skill_root / "assets" / "templates"
    for template_name in TEMPLATE_MAP:
        source = template_root / template_name
        if not source.is_file():
            raise FactoryStateError(f"Bundled template is missing: {source}")

    directories = (
        factory,
        factory / "decisions",
        factory / "evidence",
        factory / "reports",
    )
    for directory in directories:
        ensure_within_root(root, directory, "Factory directory")
        if is_link_like(directory):
            raise FactoryStateError(
                f"Factory directory must not be a symlink or junction: {directory}"
            )
        if directory.exists() and not directory.is_dir():
            raise FactoryStateError(f"Factory path is not a directory: {directory}")
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}
    created: list[str] = []
    preserved: list[str] = []

    for template_name, artifact_name in TEMPLATE_MAP.items():
        source = template_root / template_name
        destination = factory / template_name
        if is_link_like(destination):
            raise FactoryStateError(
                f"Factory artifact must not be a symlink: {destination}"
            )
        if destination.exists():
            if not destination.is_file():
                raise FactoryStateError(
                    f"Factory artifact path is not a file: {destination}"
                )
            preserved.append(destination.relative_to(root).as_posix())
        else:
            shutil.copyfile(source, destination)
            created.append(destination.relative_to(root).as_posix())
        artifacts[artifact_name] = destination.relative_to(root).as_posix()

    timestamp = utc_now()
    state: dict[str, Any] = {
        "schema_version": 1,
        "goal": goal,
        "profile": args.profile,
        "authority_envelope": authority,
        "status": "active",
        "current_phase": "requirements",
        "created_at": timestamp,
        "updated_at": timestamp,
        "artifacts": artifacts,
        "gates": {
            name: {
                "status": "pending",
                "evidence": [],
                "source_fingerprint": None,
                "updated_at": None,
            }
            for name in GATES
        },
        "assumptions": [],
        "blockers": [],
        "history": [
            {
                "at": timestamp,
                "event": "initialized",
                "details": f"profile={args.profile}; authority={authority}",
            }
        ],
    }
    atomic_write_json(path, state)

    print(f"Initialized factory run at {factory}")
    print(f"Created templates: {len(created)}")
    if preserved:
        print("Preserved existing artifacts:")
        for item in preserved:
            print(f"  - {item}")


def command_show(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    if args.json:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return

    print(f"Goal: {state.get('goal')}")
    print(f"Profile: {state.get('profile')}")
    print(f"Status: {state.get('status')}")
    print(f"Current phase: {state.get('current_phase')}")
    print("Gates:")
    for name in GATES:
        gate = state["gates"].get(name, {})
        suffix = (
            f" ({gate.get('source_fingerprint')})"
            if gate.get("source_fingerprint")
            else ""
        )
        print(f"  - {name}: {gate.get('status')}{suffix}")
    pending = unresolved_blockers(state)
    print(f"Unresolved blockers: {len(pending)}")
    for item in pending:
        print(f"  - {item.get('id')}: {item.get('reason')}")


def command_assume(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    require_active(state)
    text = nonempty(args.text, "Assumption")
    assumptions = state["assumptions"]
    item = {
        "id": next_identifier(assumptions, "ASM"),
        "text": text,
        "at": utc_now(),
    }
    assumptions.append(item)
    append_history(state, "assumption-recorded", f"{item['id']}: {item['text']}")
    save_state(root, state)
    print(f"Recorded {item['id']}")


def command_artifact(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    require_active(state)
    name = nonempty(args.name, "Artifact name")
    raw_value = nonempty(args.path, "Artifact path")
    raw_path = Path(raw_value).expanduser()
    unresolved = raw_path if raw_path.is_absolute() else root / raw_path
    candidate = ensure_within_root(root, unresolved, "Artifact path")
    relative = candidate.relative_to(root)
    if not candidate.exists():
        raise FactoryStateError(f"Artifact does not exist: {candidate}")
    state["artifacts"][name] = relative.as_posix()
    append_history(state, "artifact-recorded", f"{name}={relative.as_posix()}")
    save_state(root, state)
    print(f"Recorded artifact {name}: {relative.as_posix()}")


def command_gate(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    require_active(state)
    current = state["current_phase"]
    if args.name != current:
        raise FactoryStateError(
            f"Only the current phase gate may be changed (current: {current})."
        )
    evidence = [item.strip() for item in args.evidence if item.strip()]
    if args.status in {"passed", "failed"} and not evidence:
        raise FactoryStateError(
            "Passed or failed gates require at least one evidence item."
        )
    if args.status == "pending" and evidence:
        raise FactoryStateError("A pending gate cannot contain evidence.")
    if args.status == "passed":
        current_index = PHASES.index(current)
        require_passed_gates_fresh(root, state, GATES[:current_index])
    fingerprint = (
        compute_fingerprint(root)
        if args.name in SOURCE_GATES and args.status in {"passed", "failed"}
        else None
    )
    gate = {
        "status": args.status,
        "evidence": evidence,
        "source_fingerprint": fingerprint,
        "updated_at": None if args.status == "pending" else utc_now(),
    }
    previous = state["gates"].get(args.name)
    state["gates"][args.name] = gate
    append_history(
        state,
        "gate-recorded",
        json.dumps(
            {"name": args.name, "previous": previous, "current": gate},
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    save_state(root, state)
    print(f"Recorded {args.name} gate: {args.status}")
    if fingerprint:
        print(f"Source fingerprint: {fingerprint}")


def command_transition(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    require_active(state)
    current = state["current_phase"]
    target = args.to
    if current == "complete":
        raise FactoryStateError("A completed run cannot transition.")
    if target == current:
        raise FactoryStateError(f"Run is already in phase {current}.")

    current_index = PHASES.index(current)
    target_index = PHASES.index(target)
    if target_index == current_index + 1:
        require_passed_gates_fresh(root, state, GATES[: current_index + 1])
        if target == "complete" and unresolved_blockers(state):
            raise FactoryStateError("Cannot complete with unresolved blockers.")
    elif target_index < current_index:
        if not args.note.strip():
            raise FactoryStateError("Backward rework transitions require --note.")
        invalidated = {
            name: state["gates"][name]
            for name in GATES[target_index:]
            if state["gates"][name].get("status") != "pending"
        }
        if invalidated:
            append_history(
                state,
                "gates-invalidated",
                json.dumps(invalidated, ensure_ascii=False, sort_keys=True),
            )
        for name in GATES[target_index:]:
            state["gates"][name] = {
                "status": "pending",
                "evidence": [],
                "source_fingerprint": None,
                "updated_at": None,
            }
    else:
        raise FactoryStateError(
            f"Cannot skip phases from {current} to {target}; advance one phase at a time."
        )

    state["current_phase"] = target
    if target == "complete":
        state["status"] = "complete"
    append_history(
        state,
        "phase-transition",
        f"{current}->{target}; note={args.note.strip() or 'gate passed'}",
    )
    save_state(root, state)
    print(f"Transitioned {current} -> {target}")


def command_block(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    reason = nonempty(args.reason, "Blocker reason")
    if state.get("status") == "complete":
        raise FactoryStateError("A completed run cannot be blocked.")
    if state.get("status") == "blocked":
        raise FactoryStateError(
            "Run is already blocked; update the existing blocker externally."
        )
    blockers = state["blockers"]
    item = {
        "id": next_identifier(blockers, "BLK"),
        "reason": reason,
        "phase": state["current_phase"],
        "at": utc_now(),
        "resolved": False,
        "resolved_at": None,
        "resolution": None,
    }
    blockers.append(item)
    state["status"] = "blocked"
    append_history(state, "blocked", f"{item['id']}: {item['reason']}")
    save_state(root, state)
    print(f"Run blocked as {item['id']}")


def command_resume(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    state = load_state(root)
    note = nonempty(args.note, "Resolution note")
    if state.get("status") != "blocked":
        raise FactoryStateError("Only a blocked run can be resumed.")
    pending = unresolved_blockers(state)
    if not pending:
        raise FactoryStateError("Blocked status has no unresolved blocker to resolve.")
    timestamp = utc_now()
    for item in pending:
        item["resolved"] = True
        item["resolved_at"] = timestamp
        item["resolution"] = note
    state["status"] = "active"
    append_history(
        state,
        "resumed",
        f"resolved={','.join(item['id'] for item in pending)}; note={note}",
    )
    save_state(root, state)
    print(f"Resumed run; resolved {len(pending)} blocker(s)")


def command_fingerprint(args: argparse.Namespace) -> None:
    root = project_root(args.project)
    print(compute_fingerprint(root))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage a Greenfield Software Factory run safely."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Initialize .factory artifacts and state")
    init.add_argument("--project", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--profile", required=True, choices=PROFILES)
    init.add_argument(
        "--authority",
        default="local workspace; reversible operations; synthetic data; no deployment or external side effects",
    )
    init.set_defaults(handler=command_init)

    show = commands.add_parser("show", help="Show current state")
    show.add_argument("--project", required=True)
    show.add_argument("--json", action="store_true")
    show.set_defaults(handler=command_show)

    assume = commands.add_parser("assume", help="Append a low-risk assumption")
    assume.add_argument("--project", required=True)
    assume.add_argument("--text", required=True)
    assume.set_defaults(handler=command_assume)

    artifact = commands.add_parser("artifact", help="Record a project-local artifact")
    artifact.add_argument("--project", required=True)
    artifact.add_argument("--name", required=True)
    artifact.add_argument("--path", required=True)
    artifact.set_defaults(handler=command_artifact)

    gate = commands.add_parser("gate", help="Record the current phase gate")
    gate.add_argument("--project", required=True)
    gate.add_argument("--name", required=True, choices=GATES)
    gate.add_argument("--status", required=True, choices=sorted(GATE_STATUSES))
    gate.add_argument("--evidence", action="append", default=[])
    gate.set_defaults(handler=command_gate)

    transition = commands.add_parser(
        "transition", help="Move to the next phase or regress for rework"
    )
    transition.add_argument("--project", required=True)
    transition.add_argument("--to", required=True, choices=PHASES)
    transition.add_argument("--note", default="")
    transition.set_defaults(handler=command_transition)

    block = commands.add_parser("block", help="Stop safely on a genuine blocker")
    block.add_argument("--project", required=True)
    block.add_argument("--reason", required=True)
    block.set_defaults(handler=command_block)

    resume = commands.add_parser(
        "resume", help="Resolve blockers and resume the saved phase"
    )
    resume.add_argument("--project", required=True)
    resume.add_argument("--note", required=True)
    resume.set_defaults(handler=command_resume)

    fingerprint = commands.add_parser(
        "fingerprint", help="Hash relevant project source"
    )
    fingerprint.add_argument("--project", required=True)
    fingerprint.set_defaults(handler=command_fingerprint)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except FactoryStateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: filesystem operation failed: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: interrupted; existing state was preserved", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
