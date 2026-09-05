from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, NamedTuple


FAMILY_SELECTOR_HINTS: dict[str, tuple[str, ...]] = {
    "Work Routing": (
        "quota",
        "should-run",
        "status",
        "review-packet",
        "heartbeat",
        "scheduler",
        "work-lane",
        "monitor",
        "handoff",
        "loopx/quota.py",
        "loopx/status.py",
        "loopx/review_packet.py",
        "loopx/heartbeat_prompt.py",
    ),
    "Human Decision": (
        "user todo",
        "operator-gate",
        "reward",
        "decision-scope",
        "deferred",
        "gate",
        "loopx/operator_gate.py",
        "loopx/control_plane/todos/decision_scope.py",
        "loopx/feedback.py",
    ),
    "State And Boundary": (
        "active state",
        "todo",
        "task graph",
        "authority",
        "boundary",
        "connector",
        "public/private",
        "loopx/todos.py",
        "loopx/control_plane/todos/contract.py",
        "loopx/status.py",
        "loopx/state_projection.py",
        "loopx/boundary_authority.py",
        "loopx/authority.py",
    ),
    "Evidence Lifecycle": (
        "benchmark",
        "evidence",
        "ledger",
        "artifact",
        "public handle",
        "ci",
        "content-ops",
        "worker_bridge",
        "loopx/benchmark",
        "loopx/worker_bridge.py",
        "loopx/capabilities/content_ops",
    ),
    "Planning Governance": (
        "replan",
        "repair",
        "cadence",
        "dreaming",
        "plan-to-todo",
        "refresh-state",
        "monitor-poll",
        "loopx/dreaming.py",
        "loopx/state_refresh.py",
        "loopx/long_task_cadence.py",
    ),
}


class SelectorResolution(NamedTuple):
    requested_families: frozenset[str]
    requested_catalog_profiles: frozenset[str]
    requested_domain_profiles: frozenset[str]
    errors: tuple[dict[str, str], ...]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def catalog_profile_id(profile: dict[str, Any]) -> str:
    return slug(str(profile.get("id") or profile.get("family") or ""))


def selector_blob(changed_files: Sequence[str], surfaces: Sequence[str]) -> str:
    return "\n".join([*changed_files, *surfaces]).lower()


def catalog_selection_reasons(profile: dict[str, Any], selector_text: str) -> list[str]:
    family = str(profile.get("family") or "")
    family_lc = family.lower()
    reasons: list[str] = []
    if family_lc and family_lc in selector_text:
        reasons.append(f"selector names catalog family `{family}`")
    for hint in FAMILY_SELECTOR_HINTS.get(family, ()):
        if hint.lower() in selector_text:
            reasons.append(f"selector matches `{hint}`")
    trigger_surfaces = str(profile.get("trigger_surfaces") or "").lower()
    for token in re.findall(r"[a-z][a-z0-9_-]{2,}", selector_text):
        reason = f"trigger surface mentions `{token}`"
        if token in trigger_surfaces and reason not in reasons:
            reasons.append(reason)
    return reasons


def domain_selection_reasons(profile: dict[str, Any], selector_text: str) -> list[str]:
    reasons: list[str] = []
    profile_id = str(profile.get("id") or "")
    title = str(profile.get("title") or "")
    if profile_id and profile_id in selector_text:
        reasons.append(f"selector names profile `{profile_id}`")
    if title and title.lower() in selector_text:
        reasons.append(f"selector names profile `{title}`")
    for hint in profile.get("trigger_hints", []):
        hint_text = str(hint or "").lower()
        if hint_text and hint_text in selector_text:
            reasons.append(f"selector matches `{hint}`")
    for family in profile.get("catalog_families", []):
        family_text = str(family or "").lower()
        if family_text and family_text in selector_text:
            reasons.append(f"selector matches family `{family}`")
    return reasons


def select_domain_profile_checks(
    profile: dict[str, Any],
    *,
    include_deep_checks: bool,
    max_checks: int,
) -> dict[str, Any]:
    checks = [
        dict(check)
        for check in profile.get("checks", [])
        if include_deep_checks or check.get("tier") != "deep"
    ]
    soft_target = max(1, max_checks)
    mandatory_checks = [check for check in checks if check.get("mandatory") is True]
    optional_checks = [check for check in checks if check.get("mandatory") is not True]
    selected_commands = {str(check.get("command") or "") for check in mandatory_checks}
    selected_checks = list(mandatory_checks)
    for check in optional_checks:
        if len(selected_checks) >= soft_target:
            break
        command = str(check.get("command") or "")
        if command and command not in selected_commands:
            selected_checks.append(check)
            selected_commands.add(command)
    selected_checks.sort(key=checks.index)

    copied = dict(profile)
    copied["checks"] = selected_checks
    copied["check_soft_target"] = soft_target
    copied["mandatory_check_count"] = len(mandatory_checks)
    copied["check_soft_target_expanded_for_mandatory"] = (
        len(selected_checks) > soft_target
    )
    copied["deep_checks_available"] = any(
        isinstance(check, dict) and check.get("tier") == "deep"
        for check in profile.get("checks", [])
    )
    copied["deep_checks_included"] = bool(include_deep_checks)
    return copied


def resolve_explicit_selectors(
    *,
    catalog_profiles: Sequence[dict[str, Any]],
    domain_profiles: Sequence[dict[str, Any]],
    families: Sequence[str],
    profiles: Sequence[str],
    surfaces: Sequence[str],
) -> SelectorResolution:
    requested_families = frozenset(slug(value) for value in families if value.strip())
    requested_profiles = frozenset(slug(value) for value in profiles if value.strip())
    catalog_profile_ids = frozenset(
        catalog_profile_id(item) for item in catalog_profiles
    )
    domain_profile_ids = frozenset(
        slug(str(item.get("id") or "")) for item in domain_profiles
    )
    requested_catalog_profiles = requested_profiles & catalog_profile_ids
    requested_domain_profiles = requested_profiles & domain_profile_ids
    known_family_ids = {
        slug(str(item.get("family") or "")) for item in catalog_profiles
    }
    unknown_surfaces = sorted(
        surface
        for surface in surfaces
        if not any(
            catalog_selection_reasons(item, surface.lower())
            for item in catalog_profiles
        )
        and not any(
            domain_selection_reasons(item, surface.lower()) for item in domain_profiles
        )
    )
    errors = (
        *(
            {"kind": "unknown_profile", "selector": value}
            for value in sorted(
                requested_profiles - catalog_profile_ids - domain_profile_ids
            )
        ),
        *(
            {"kind": "unknown_family", "selector": value}
            for value in sorted(requested_families - known_family_ids)
        ),
        *({"kind": "unknown_surface", "selector": value} for value in unknown_surfaces),
    )
    return SelectorResolution(
        requested_families=requested_families,
        requested_catalog_profiles=requested_catalog_profiles,
        requested_domain_profiles=requested_domain_profiles,
        errors=errors,
    )
