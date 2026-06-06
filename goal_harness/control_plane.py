from __future__ import annotations

from typing import Any


SELF_REPAIR_MODES = {
    "health_blocker_repair": "allow_health_blocker_repair",
    "waiting_projection_repair": "allow_waiting_projection_repair",
}


def _flag(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def compact_control_plane_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    self_repair = value.get("self_repair") if isinstance(value.get("self_repair"), dict) else {}
    if self_repair:
        enabled = _flag(self_repair.get("enabled"), default=False)
        compact["self_repair"] = {
            "enabled": enabled,
            "allow_health_blocker_repair": _flag(
                self_repair.get("allow_health_blocker_repair"),
                default=enabled,
            ),
            "allow_waiting_projection_repair": _flag(
                self_repair.get("allow_waiting_projection_repair"),
                default=enabled,
            ),
        }
    return compact


def control_plane_self_repair_allows(policy: Any, mode: str) -> bool:
    compact = compact_control_plane_policy(policy)
    self_repair = compact.get("self_repair") if isinstance(compact.get("self_repair"), dict) else {}
    if self_repair.get("enabled") is not True:
        return False
    flag_name = SELF_REPAIR_MODES.get(mode)
    if not flag_name:
        return False
    return self_repair.get(flag_name) is True


def control_plane_policy_summary(policy: Any) -> str:
    compact = compact_control_plane_policy(policy)
    self_repair = compact.get("self_repair") if isinstance(compact.get("self_repair"), dict) else {}
    if not self_repair:
        return "self_repair=default_off"
    enabled = "on" if self_repair.get("enabled") else "off"
    health = "health" if self_repair.get("allow_health_blocker_repair") else "no-health"
    waiting = "waiting" if self_repair.get("allow_waiting_projection_repair") else "no-waiting"
    return f"self_repair={enabled}:{health},{waiting}"
