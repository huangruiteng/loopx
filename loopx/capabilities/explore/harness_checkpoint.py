from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .router_state import is_router_state


HARNESS_CHECKPOINT_SCHEMA_VERSION = "loopx_explore_harness_checkpoint_v0"


def write_arm_checkpoint(path: Path, payload: Mapping[str, Any]) -> None:
    """Replace a restart contract only after the complete JSON is durable."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_arm_checkpoint(
    path: Path,
    *,
    expected_signature: Mapping[str, Any],
) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"resume checkpoint does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"resume checkpoint is unreadable or invalid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError("resume checkpoint must be a JSON object")
    if payload.get("schema_version") != HARNESS_CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(
            "resume checkpoint schema is incompatible: expected "
            f"{HARNESS_CHECKPOINT_SCHEMA_VERSION!r}, got {payload.get('schema_version')!r}"
        )
    expected_arm = str(expected_signature.get("arm_key") or "")
    if str(payload.get("arm_key") or "") != expected_arm:
        raise ValueError(
            "resume checkpoint arm_key is incompatible: "
            f"expected {expected_arm!r}, got {payload.get('arm_key')!r}"
        )
    signature = payload.get("runtime_signature")
    if not isinstance(signature, dict):
        raise ValueError("resume checkpoint is missing runtime_signature")
    mismatches = [
        key
        for key, expected in expected_signature.items()
        if signature.get(key) != expected
    ]
    if mismatches:
        details = ", ".join(
            f"{key}={signature.get(key)!r} (expected {expected_signature.get(key)!r})"
            for key in mismatches
        )
        raise ValueError(f"resume checkpoint runtime is incompatible: {details}")
    state = payload.get("state")
    if not isinstance(state, dict):
        raise ValueError("resume checkpoint is missing state")
    for field in ("epochs", "checkpoints", "novelty_seen", "catalog_consumed"):
        if not isinstance(state.get(field), list):
            raise ValueError(f"resume checkpoint state.{field} must be a list")
    if any(not isinstance(epoch, dict) for epoch in state["epochs"]):
        raise ValueError("resume checkpoint state.epochs must contain objects")
    if any(not isinstance(checkpoint, dict) for checkpoint in state["checkpoints"]):
        raise ValueError("resume checkpoint state.checkpoints must contain objects")
    if any(not isinstance(key, str) for key in state["novelty_seen"]):
        raise ValueError("resume checkpoint state.novelty_seen must contain strings")
    if any(not isinstance(spec_id, str) for spec_id in state["catalog_consumed"]):
        raise ValueError("resume checkpoint state.catalog_consumed must contain strings")
    if not isinstance(state.get("coverage_first_seen"), dict):
        raise ValueError("resume checkpoint state.coverage_first_seen must be an object")
    try:
        for minutes in state["coverage_first_seen"].values():
            float(minutes)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "resume checkpoint state.coverage_first_seen values must be numeric"
        ) from error
    if state.get("load_profile") is not None and not isinstance(state.get("load_profile"), dict):
        raise ValueError("resume checkpoint state.load_profile must be an object or null")

    try:
        completed_epochs = int(payload.get("completed_epochs") or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("resume checkpoint completed_epochs must be an integer") from error
    if completed_epochs != len(state["epochs"]):
        raise ValueError("resume checkpoint completed_epochs does not match epoch history")
    if len(state["checkpoints"]) != completed_epochs:
        raise ValueError("resume checkpoint anytime history does not match completed_epochs")
    expected_epochs = list(range(1, completed_epochs + 1))
    try:
        epoch_numbers = [int(epoch.get("epoch") or 0) for epoch in state["epochs"]]
        checkpoint_epochs = [
            int(checkpoint.get("epoch") or 0) for checkpoint in state["checkpoints"]
        ]
    except (TypeError, ValueError) as error:
        raise ValueError("resume checkpoint epoch history must use integer epoch ids") from error
    if epoch_numbers != expected_epochs or checkpoint_epochs != expected_epochs:
        raise ValueError("resume checkpoint epoch history is not contiguous from epoch 1")
    try:
        next_epoch = int(state.get("next_epoch") or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("resume checkpoint state.next_epoch must be an integer") from error
    expected_next_epoch = completed_epochs + 1
    if next_epoch != expected_next_epoch:
        raise ValueError(
            "resume checkpoint next_epoch is inconsistent: "
            f"expected {expected_next_epoch}, got {next_epoch}"
        )
    if expected_signature.get("use_router") and not is_router_state(state.get("router_state")):
        raise ValueError("resume checkpoint has an invalid router_state for a router arm")
    for field in (
        "elapsed_minutes",
        "raw_value_total",
        "novel_value_total",
        "variant_records_total",
    ):
        try:
            float(state.get(field) or 0.0)
        except (TypeError, ValueError) as error:
            raise ValueError(f"resume checkpoint state.{field} must be numeric") from error
    return state


def build_arm_checkpoint(
    *,
    arm_key: str,
    runtime_signature: Mapping[str, Any],
    next_epoch: int,
    elapsed_minutes: float,
    epochs: Sequence[Mapping[str, Any]],
    checkpoints: Sequence[Mapping[str, Any]],
    novelty_seen: Sequence[str],
    router_state: Mapping[str, Any] | None,
    load_profile: Mapping[str, Any] | None,
    catalog_consumed: Sequence[str],
    coverage_first_seen: Mapping[str, float],
    raw_value_total: float,
    novel_value_total: float,
    variant_records_total: int,
) -> dict[str, Any]:
    return {
        "schema_version": HARNESS_CHECKPOINT_SCHEMA_VERSION,
        "arm_key": arm_key,
        "completed_epochs": len(epochs),
        "runtime_signature": dict(runtime_signature),
        "state": {
            "next_epoch": int(next_epoch),
            "elapsed_minutes": round(float(elapsed_minutes), 6),
            "epochs": [dict(epoch) for epoch in epochs],
            "checkpoints": [dict(checkpoint) for checkpoint in checkpoints],
            "novelty_seen": sorted(novelty_seen),
            "router_state": dict(router_state) if isinstance(router_state, Mapping) else None,
            "load_profile": dict(load_profile) if isinstance(load_profile, Mapping) else None,
            "catalog_consumed": sorted(catalog_consumed),
            "coverage_first_seen": dict(coverage_first_seen),
            "raw_value_total": round(float(raw_value_total), 6),
            "novel_value_total": round(float(novel_value_total), 6),
            "variant_records_total": int(variant_records_total),
        },
    }
