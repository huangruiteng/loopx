from __future__ import annotations

import re
from typing import Any

from .delivery_outcome import DeliveryOutcome


DEFAULT_EXECUTION_PROFILE: dict[str, Any] = {
    "cadence": "bounded_progress_segment",
    "minimum_scale": "multi_surface_or_implementation",
    "must_include": [
        "coherent_artifact",
        "targeted_validation",
        "state_writeback",
    ],
    "spend_rule": "spend_only_after_artifact_validation_writeback",
    "outcome_floor": {
        "required_when": "after_surface_progress_streak",
        "surface_streak_threshold": 3,
        "outcome_markers": [],
        "surface_only_hints": [],
        "must_advance": [
            DeliveryOutcome.PRIMARY_GOAL_OUTCOME.value,
        ],
        "avoid": [
            "surface_only_progress_loop",
        ],
        "if_unavailable": "report_blocker_without_spend",
    },
    "degradation_policy": {
        "small_scale_streak_threshold": 2,
        "on_degradation": "require_blocker_or_expand_next_batch",
    },
}

_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,79}$")


def _label(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if _LABEL_PATTERN.match(text):
        return text
    return fallback


def _label_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    labels = []
    for item in value:
        label = _label(item, "")
        if label:
            labels.append(label)
    return labels or list(fallback)


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def build_execution_profile(
    *,
    minimum_scale: str | None = None,
    must_include: list[str] | None = None,
    small_scale_streak_threshold: int | None = None,
    outcome_markers: list[str] | None = None,
    surface_only_hints: list[str] | None = None,
    surface_streak_threshold: int | None = None,
    outcome_must_advance: list[str] | None = None,
) -> dict[str, Any]:
    profile = compact_execution_profile(None)
    if minimum_scale:
        profile["minimum_scale"] = _label(minimum_scale, str(profile["minimum_scale"]))
    if must_include:
        profile["must_include"] = _label_list(must_include, list(profile["must_include"]))
    if small_scale_streak_threshold is not None:
        policy = dict(profile["degradation_policy"])
        policy["small_scale_streak_threshold"] = _positive_int(
            small_scale_streak_threshold,
            int(policy["small_scale_streak_threshold"]),
        )
        profile["degradation_policy"] = policy
    floor = dict(profile["outcome_floor"])
    if outcome_markers:
        floor["outcome_markers"] = _label_list(outcome_markers, list(floor["outcome_markers"]))
    if surface_only_hints:
        floor["surface_only_hints"] = _label_list(surface_only_hints, list(floor["surface_only_hints"]))
    if surface_streak_threshold is not None:
        floor["surface_streak_threshold"] = _positive_int(
            surface_streak_threshold,
            int(floor["surface_streak_threshold"]),
        )
    if outcome_must_advance:
        floor["must_advance"] = _label_list(outcome_must_advance, list(floor["must_advance"]))
    profile["outcome_floor"] = floor
    return profile


def compact_execution_profile(value: Any) -> dict[str, Any]:
    defaults = DEFAULT_EXECUTION_PROFILE
    profile = {
        "cadence": defaults["cadence"],
        "minimum_scale": defaults["minimum_scale"],
        "must_include": list(defaults["must_include"]),
        "spend_rule": defaults["spend_rule"],
        "outcome_floor": {
            "required_when": defaults["outcome_floor"]["required_when"],
            "surface_streak_threshold": defaults["outcome_floor"]["surface_streak_threshold"],
            "outcome_markers": list(defaults["outcome_floor"]["outcome_markers"]),
            "surface_only_hints": list(defaults["outcome_floor"]["surface_only_hints"]),
            "must_advance": list(defaults["outcome_floor"]["must_advance"]),
            "avoid": list(defaults["outcome_floor"]["avoid"]),
            "if_unavailable": defaults["outcome_floor"]["if_unavailable"],
        },
        "degradation_policy": dict(defaults["degradation_policy"]),
    }
    if not isinstance(value, dict):
        return profile

    profile["cadence"] = _label(value.get("cadence"), str(profile["cadence"]))
    profile["minimum_scale"] = _label(value.get("minimum_scale"), str(profile["minimum_scale"]))
    profile["must_include"] = _label_list(value.get("must_include"), list(profile["must_include"]))
    profile["spend_rule"] = _label(value.get("spend_rule"), str(profile["spend_rule"]))

    raw_policy = value.get("degradation_policy") if isinstance(value.get("degradation_policy"), dict) else {}
    policy = dict(profile["degradation_policy"])
    policy["small_scale_streak_threshold"] = _positive_int(
        raw_policy.get("small_scale_streak_threshold"),
        int(policy["small_scale_streak_threshold"]),
    )
    policy["on_degradation"] = _label(raw_policy.get("on_degradation"), str(policy["on_degradation"]))
    profile["degradation_policy"] = policy

    raw_floor = value.get("outcome_floor") if isinstance(value.get("outcome_floor"), dict) else {}
    floor = dict(profile["outcome_floor"])
    floor["required_when"] = _label(raw_floor.get("required_when"), str(floor["required_when"]))
    floor["surface_streak_threshold"] = _positive_int(
        raw_floor.get("surface_streak_threshold"),
        int(floor["surface_streak_threshold"]),
    )
    floor["outcome_markers"] = _label_list(raw_floor.get("outcome_markers"), list(floor["outcome_markers"]))
    floor["surface_only_hints"] = _label_list(
        raw_floor.get("surface_only_hints"),
        list(floor["surface_only_hints"]),
    )
    floor["must_advance"] = _label_list(raw_floor.get("must_advance"), list(floor["must_advance"]))
    floor["avoid"] = _label_list(raw_floor.get("avoid"), list(floor["avoid"]))
    floor["if_unavailable"] = _label(raw_floor.get("if_unavailable"), str(floor["if_unavailable"]))
    profile["outcome_floor"] = floor
    return profile


def execution_profile_threshold(profile: dict[str, Any] | None) -> int:
    normalized = compact_execution_profile(profile)
    policy = normalized.get("degradation_policy") if isinstance(normalized.get("degradation_policy"), dict) else {}
    return _positive_int(
        policy.get("small_scale_streak_threshold"),
        int(DEFAULT_EXECUTION_PROFILE["degradation_policy"]["small_scale_streak_threshold"]),
    )


def execution_profile_outcome_floor(profile: dict[str, Any] | None) -> dict[str, Any]:
    normalized = compact_execution_profile(profile)
    floor = normalized.get("outcome_floor") if isinstance(normalized.get("outcome_floor"), dict) else {}
    return dict(floor)


def outcome_floor_threshold(profile: dict[str, Any] | None) -> int:
    floor = execution_profile_outcome_floor(profile)
    return _positive_int(
        floor.get("surface_streak_threshold"),
        int(DEFAULT_EXECUTION_PROFILE["outcome_floor"]["surface_streak_threshold"]),
    )


def execution_profile_summary(profile: dict[str, Any] | None) -> str:
    normalized = compact_execution_profile(profile)
    policy = normalized.get("degradation_policy") if isinstance(normalized.get("degradation_policy"), dict) else {}
    floor = normalized.get("outcome_floor") if isinstance(normalized.get("outcome_floor"), dict) else {}
    floor_suffix = ""
    outcome_markers = floor.get("outcome_markers") if isinstance(floor.get("outcome_markers"), list) else []
    surface_hints = floor.get("surface_only_hints") if isinstance(floor.get("surface_only_hints"), list) else []
    if outcome_markers or surface_hints:
        floor_suffix = (
            " "
            f"outcome_floor=threshold:{floor.get('surface_streak_threshold')},"
            f"markers:{','.join(outcome_markers)},"
            f"surface:{','.join(surface_hints)}"
        )
    return (
        f"cadence={normalized.get('cadence')} "
        f"minimum={normalized.get('minimum_scale')} "
        f"include={','.join(normalized.get('must_include') or [])} "
        f"spend_rule={normalized.get('spend_rule')} "
        f"small_streak_threshold={policy.get('small_scale_streak_threshold')}"
        f"{floor_suffix}"
    )
