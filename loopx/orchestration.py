from __future__ import annotations

from typing import Any


DEFAULT_ORCHESTRATION_MODE = "default"
MULTI_SUBAGENT_ORCHESTRATION_MODE = "multi_subagent"
VALID_ORCHESTRATION_MODES = {
    DEFAULT_ORCHESTRATION_MODE,
    MULTI_SUBAGENT_ORCHESTRATION_MODE,
}
EXPLORE_HARNESS_PROFILES = (
    "generic",
    "adaptive-resilient",
    "moe-router",
)


def _int_number(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def orchestration_mode_from_spawn_policy(spawn_policy: Any) -> str:
    if not isinstance(spawn_policy, dict):
        return DEFAULT_ORCHESTRATION_MODE
    explicit_mode = str(
        spawn_policy.get("mode") or spawn_policy.get("orchestration_mode") or ""
    ).strip()
    if explicit_mode in VALID_ORCHESTRATION_MODES:
        return explicit_mode
    spawn_allowed = bool(spawn_policy.get("allowed") or spawn_policy.get("spawn_allowed"))
    if spawn_allowed and _int_number(spawn_policy.get("max_children")) > 0:
        return MULTI_SUBAGENT_ORCHESTRATION_MODE
    return DEFAULT_ORCHESTRATION_MODE


def compact_explore_harness_policy(policy: Any) -> dict[str, Any]:
    """Normalize the per-goal explore-harness opt-in gate.

    Absence of the section means the gate is closed. The opt-in bit is a
    deny-by-default switch, so it fails closed: only a real boolean ``true``
    opens it -- truthy strings like ``"false"`` or ``"true"`` stay closed
    instead of silently inverting a hand-edited deny. ``profile`` is carried
    only when the goal explicitly pins one, so planners can tell a pinned
    profile apart from their own default.
    """

    harness = policy if isinstance(policy, dict) else {}
    compact: dict[str, Any] = {"enabled": harness.get("enabled") is True}
    profile = str(harness.get("profile") or "").strip()
    if profile:
        compact["profile"] = profile
    return compact


def compact_orchestration_policy(spawn_policy: Any) -> dict[str, Any]:
    policy = spawn_policy if isinstance(spawn_policy, dict) else {}
    max_children = max(0, _int_number(policy.get("max_children")))
    allowed_domains = policy.get("allowed_domains")
    if not isinstance(allowed_domains, list):
        allowed_domains = []
    compact: dict[str, Any] = {
        "mode": orchestration_mode_from_spawn_policy(policy),
        "spawn_allowed": bool(policy.get("allowed") or policy.get("spawn_allowed")),
        "max_children": max_children,
    }
    compact_domains = [str(value) for value in allowed_domains if str(value).strip()]
    if compact_domains:
        compact["allowed_domains"] = compact_domains
    if isinstance(policy.get("explore_harness"), dict):
        compact["explore_harness"] = compact_explore_harness_policy(policy.get("explore_harness"))
    return compact


def orchestration_policy_summary(policy: dict[str, Any] | None) -> str:
    compact = compact_orchestration_policy(policy)
    summary = (
        f"mode={compact.get('mode')} "
        f"spawn_allowed={compact.get('spawn_allowed')} "
        f"max_children={compact.get('max_children')}"
    )
    harness = compact.get("explore_harness")
    if isinstance(harness, dict):
        state = "on" if harness.get("enabled") else "off"
        profile = str(harness.get("profile") or "")
        if harness.get("enabled") and profile:
            state = f"on({profile})"
        summary += f" explore_harness={state}"
    return summary
