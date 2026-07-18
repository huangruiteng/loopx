from __future__ import annotations

from typing import Any


NON_BENCHMARK_SMOKE_EXCLUDE_MODULES = [
    "agentissue-bench",
    "agents-last-exam",
    "benchmark",
    "skillsbench",
    "swe-marathon",
    "terminal-bench",
]
SMOKE_SUITE_PROFILE_MANIFEST: dict[str, dict[str, Any]] = {
    "core-control-plane": {
        "suite": "full-public",
        "modules": [
            "control-plane",
            "control_plane",
            "project",
            "protocol",
            "quota",
            "review-packet",
            "review_packet",
            "scheduler",
            "session-runtime",
            "session_runtime",
            "state",
            "status",
            "todo",
        ],
        "exclude_modules": NON_BENCHMARK_SMOKE_EXCLUDE_MODULES,
        "description": "LoopX runtime/control-plane contracts without benchmark adapters.",
    },
    "canary-runner": {
        "suite": "full-public",
        "modules": [
            "catalog",
            "premerge",
            "pytest-smoke-suite",
            "pytest_smoke_suite",
            "smoke-suite",
            "smoke_suite",
        ],
        "exclude_modules": NON_BENCHMARK_SMOKE_EXCLUDE_MODULES,
        "description": "Canary planner, runner, smoke-suite, and pytest facade contracts.",
    },
    "public-entry-install-release": {
        "suite": "full-public",
        "modules": [
            "codex-cli-packaged-install",
            "install",
            "public-entry",
            "public_entry",
            "readme",
            "release",
        ],
        "exclude_modules": NON_BENCHMARK_SMOKE_EXCLUDE_MODULES,
        "description": "Public entry, packaged install, README, and release-readiness checks.",
    },
    "docs-project-content-ops": {
        "suite": "full-public",
        "modules": [
            "content",
            "content-ops",
            "content_ops",
            "docs",
            "project",
            "update-note",
            "update_notes",
        ],
        "exclude_modules": NON_BENCHMARK_SMOKE_EXCLUDE_MODULES,
        "description": "Docs, project lifecycle, and content/update-note operations checks.",
    },
    "extension-runtime": {
        "suite": "full-public",
        "modules": [
            "capability-extension",
            "extension",
            "lark-event",
            "lark-inbox",
            "openviking-extension",
        ],
        "exclude_modules": NON_BENCHMARK_SMOKE_EXCLUDE_MODULES,
        "description": (
            "Extension placement, lifecycle, provider activation, and Lark "
            "inbox compatibility checks."
        ),
    },
    "public-smoke-watch": {
        "suite": "full-public",
        "modules": [
            "canary",
            "control-plane",
            "control_plane",
            "full-public-smokes",
            "install",
            "issue-fix",
            "line-budget",
            "monitor",
            "public-entry",
            "public_entry",
            "quota",
            "readme",
            "scheduler",
            "smoke-suite",
            "smoke_suite",
            "status",
            "todo",
        ],
        "exclude_modules": NON_BENCHMARK_SMOKE_EXCLUDE_MODULES,
        "description": (
            "Recurring public health watch profile for canary runner, public "
            "entry/install, control-plane monitor, and repository budget checks."
        ),
    },
}


def list_smoke_suite_profiles() -> list[dict[str, Any]]:
    """Return stable, machine-readable smoke-suite profile metadata."""

    profiles: list[dict[str, Any]] = []
    for profile_id, profile_spec in sorted(SMOKE_SUITE_PROFILE_MANIFEST.items()):
        profiles.append(
            {
                "id": profile_id,
                "suite": str(profile_spec.get("suite") or "default-public"),
                "modules": [
                    str(item)
                    for item in profile_spec.get("modules", [])
                    if str(item).strip()
                ],
                "exclude_modules": [
                    str(item)
                    for item in profile_spec.get("exclude_modules", [])
                    if str(item).strip()
                ],
                "description": str(profile_spec.get("description") or ""),
            }
        )
    return profiles


def _append_unique(values: list[str], additions: list[str]) -> list[str]:
    seen = {value for value in values if value}
    expanded = list(values)
    for value in additions:
        if not value or value in seen:
            continue
        seen.add(value)
        expanded.append(value)
    return expanded


def resolve_smoke_suite_profiles(
    *,
    suite: str,
    suite_choices: set[str],
    modules: list[str],
    exclude_modules: list[str],
    profiles: list[str],
) -> dict[str, Any]:
    normalized_suite = suite if suite in suite_choices else "default-public"
    expanded_modules = list(modules)
    expanded_exclude_modules = list(exclude_modules)
    smoke_profiles: list[str] = []
    catalog_profiles: list[str] = []
    profile_expansions: list[dict[str, Any]] = []
    for profile in profiles:
        profile_id = profile.strip()
        if not profile_id:
            continue
        profile_spec = SMOKE_SUITE_PROFILE_MANIFEST.get(profile_id)
        if profile_spec is None:
            catalog_profiles.append(profile_id)
            continue
        smoke_profiles.append(profile_id)
        normalized_suite = str(profile_spec.get("suite") or normalized_suite)
        profile_modules = [
            str(item)
            for item in profile_spec.get("modules", [])
            if str(item).strip()
        ]
        profile_excludes = [
            str(item)
            for item in profile_spec.get("exclude_modules", [])
            if str(item).strip()
        ]
        expanded_modules = _append_unique(expanded_modules, profile_modules)
        expanded_exclude_modules = _append_unique(
            expanded_exclude_modules,
            profile_excludes,
        )
        profile_expansions.append(
            {
                "profile": profile_id,
                "suite": normalized_suite,
                "modules": profile_modules,
                "exclude_modules": profile_excludes,
                "description": profile_spec.get("description"),
            }
        )
    return {
        "suite": normalized_suite,
        "modules": expanded_modules,
        "exclude_modules": expanded_exclude_modules,
        "smoke_profiles": smoke_profiles,
        "catalog_profiles": catalog_profiles,
        "profile_expansions": profile_expansions,
    }
