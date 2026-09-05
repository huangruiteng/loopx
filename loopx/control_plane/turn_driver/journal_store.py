"""Filesystem boundary for canonical LoopX Turn journals."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...file_lock import exclusive_file_lock
from .turn_journal_runtime import write_turn_journal


LOOPX_TURN_JOURNAL_SCHEMA_VERSION = "loopx_turn_journal_v0"
TURN_KEY_RE = re.compile(r"^sha256:(?P<digest>[0-9a-f]{64})$")


def turn_journal_path(runtime_root: Path, *, goal_id: str, turn_key: str) -> Path:
    match = TURN_KEY_RE.fullmatch(turn_key)
    if not match:
        raise ValueError("turn_key must be a sha256 digest")
    return runtime_root / "goals" / goal_id / "turns" / f"{match.group('digest')}.json"


def load_turn_journal(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != LOOPX_TURN_JOURNAL_SCHEMA_VERSION
    ):
        raise ValueError("LoopX Turn journal has an unsupported schema")
    return value


def journal_committed_effect_id(journal: Mapping[str, Any]) -> str | None:
    """Return the typed settlement identity when this is not a legacy journal."""

    stored_plan = journal.get("plan")
    if not isinstance(stored_plan, Mapping):
        return None
    transaction = stored_plan.get("transaction")
    if not isinstance(transaction, Mapping):
        return None
    settlement_plan = transaction.get("settlement_plan")
    if not isinstance(settlement_plan, Mapping):
        return None
    identity = settlement_plan.get("identity")
    if not isinstance(identity, Mapping):
        return None
    effect_id = str(identity.get("effect_id") or "").strip()
    return effect_id or None


def write_turn_journal_checkpoint(path: Path, journal: Mapping[str, Any]) -> None:
    write_turn_journal(
        str(path),
        journal,
        expected_effect_id=journal_committed_effect_id(journal),
    )


def load_loopx_turn_plan_from_journal(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any]:
    path = turn_journal_path(runtime_root, goal_id=goal_id, turn_key=turn_key)
    with exclusive_file_lock(path):
        journal = load_turn_journal(path)
    if journal is None:
        raise ValueError("LoopX Turn resume journal does not exist")
    plan = journal.get("plan")
    if not isinstance(plan, dict):
        raise TypeError("LoopX Turn resume journal does not contain a plan")
    transaction = (
        plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    )
    if transaction.get("turn_key") != turn_key or journal.get("turn_key") != turn_key:
        raise ValueError("LoopX Turn resume journal has mismatched turn lineage")
    envelope = (
        plan.get("turn_envelope") if isinstance(plan.get("turn_envelope"), dict) else {}
    )
    if envelope.get("goal_id") != goal_id or journal.get("goal_id") != goal_id:
        raise ValueError("LoopX Turn resume journal belongs to another goal")
    return dict(plan)


def _journal_plan_turn_instance_id(plan: Mapping[str, Any]) -> str | None:
    transaction = plan.get("transaction")
    if isinstance(transaction, Mapping):
        direct = str(transaction.get("turn_instance_id") or "").strip()
        if direct:
            return direct
    settlement = (
        transaction.get("settlement_plan")
        if isinstance(transaction, Mapping)
        else None
    )
    identity = (
        settlement.get("identity") if isinstance(settlement, Mapping) else None
    )
    if isinstance(identity, Mapping):
        nested = str(identity.get("turn_instance_id") or "").strip()
        if nested:
            return nested
    return None


def _envelope_observed_capabilities(envelope: Mapping[str, Any]) -> list[str]:
    """Read the capability set this Turn's scheduler decision already froze.

    Two durable sub-sources compose the validated set, mirroring what the
    scheduler consumed: the journaled boundary declares goal/coordination
    capabilities, and a journaled capability gate whose required capabilities
    were not missing proves the scheduler observed them for this Turn.
    Anything else stays absent so downstream gates fail closed.
    """

    observed: list[str] = []

    def append(values: Any) -> None:
        if not isinstance(values, list):
            return
        for capability in values:
            rendered = str(capability or "").strip()
            if rendered and rendered not in observed:
                observed.append(rendered)

    boundary = (
        envelope.get("boundary")
        if isinstance(envelope.get("boundary"), Mapping)
        else {}
    )
    append(boundary.get("available_capabilities"))
    gate = (
        envelope.get("capability_gate")
        if isinstance(envelope.get("capability_gate"), Mapping)
        else {}
    )
    required = gate.get("required_capabilities")
    missing = gate.get("missing_capabilities")
    if isinstance(required, list) and required and missing in (None, []):
        append(required)
    return observed


def turn_journal_observed_capabilities(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_instance_id: str,
) -> list[str] | None:
    """Return capabilities the settled Turn durably observed, if any.

    The Turn journal is the settlement-grade record: its envelope froze the
    scheduler decision that already judged capability gates for this exact
    turn_instance_id. Unreadable, missing, or unmatched journals return None
    so callers fail closed instead of guessing from the current environment.
    """

    normalized_turn_instance_id = str(turn_instance_id or "").strip()
    if not normalized_turn_instance_id:
        return None
    turns_dir = runtime_root / "goals" / goal_id / "turns"
    if not turns_dir.is_dir():
        return None
    for path in sorted(turns_dir.glob("*.json")):
        try:
            journal = load_turn_journal(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if journal is None:
            continue
        if journal.get("goal_id") != goal_id:
            continue
        plan = journal.get("plan")
        if not isinstance(plan, Mapping):
            continue
        if (
            _journal_plan_turn_instance_id(plan)
            != normalized_turn_instance_id
        ):
            continue
        envelope = (
            plan.get("turn_envelope")
            if isinstance(plan.get("turn_envelope"), Mapping)
            else {}
        )
        return _envelope_observed_capabilities(envelope)
    return None
