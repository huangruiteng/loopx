from __future__ import annotations

from typing import Any


def new_codex_cli_goal_recovery_summary() -> dict[str, Any]:
    return {
        "pre_bridge_attempt_count": 0,
        "pre_bridge_actions": [],
        "pre_bridge_skip_reasons": [],
        "post_bridge_attempt_count": 0,
        "post_bridge_actions": [],
        "post_bridge_skip_reasons": [],
    }


def _append_unique(values: list[str], value: object, *, limit: int) -> None:
    if not isinstance(value, str) or not value:
        return
    safe_value = value[:limit]
    if safe_value not in values:
        values.append(safe_value)


def merge_codex_cli_goal_recovery_trace(
    summary: dict[str, Any],
    goal_trace: dict[str, Any],
) -> None:
    """Accumulate public-safe pre/post bridge TUI recovery counters.

    Older traces wrote pre-bridge retry facts into the post-bridge fields. The
    stage is the durable discriminator, so preserve compatibility by projecting
    those legacy fields into the pre-bridge summary when stage starts with
    ``pre_bridge_``.
    """

    stage = goal_trace.get("stage")
    stage_is_pre_bridge = isinstance(stage, str) and stage.startswith("pre_bridge_")
    phase = "pre_bridge" if stage_is_pre_bridge else "post_bridge"
    attempts = goal_trace.get(f"{phase}_recovery_attempt_count")
    if attempts is None and stage_is_pre_bridge:
        attempts = goal_trace.get("post_bridge_recovery_attempt_count")
    if isinstance(attempts, int) and not isinstance(attempts, bool):
        summary[f"{phase}_attempt_count"] += max(0, attempts)

    action = goal_trace.get(f"{phase}_recovery_action")
    if not action and stage_is_pre_bridge:
        action = goal_trace.get("post_bridge_recovery_action")
    _append_unique(summary[f"{phase}_actions"], action, limit=40)

    skip_reason = goal_trace.get(f"{phase}_recovery_skip_reason")
    if not skip_reason and stage_is_pre_bridge:
        skip_reason = goal_trace.get("post_bridge_recovery_skip_reason")
    _append_unique(summary[f"{phase}_skip_reasons"], skip_reason, limit=80)


def codex_cli_goal_recovery_public_fields(
    summary: dict[str, Any],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for phase in ("pre_bridge", "post_bridge"):
        prefix = f"codex_cli_goal_tui_{phase}_recovery"
        actions = [
            item[:40]
            for item in summary.get(f"{phase}_actions", [])
            if isinstance(item, str) and item
        ][:8]
        skip_reasons = [
            item[:80]
            for item in summary.get(f"{phase}_skip_reasons", [])
            if isinstance(item, str) and item
        ][:8]
        fields[f"{prefix}_attempt_count"] = max(
            0,
            int(summary.get(f"{phase}_attempt_count") or 0),
        )
        fields[f"{prefix}_actions"] = actions
        fields[f"{prefix}_action"] = actions[0] if actions else ""
        fields[f"{prefix}_skip_reasons"] = skip_reasons
        fields[f"{prefix}_skip_reason"] = skip_reasons[0] if skip_reasons else ""
    return fields
