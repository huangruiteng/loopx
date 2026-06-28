from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CANARY_PROFILE_SCHEMA_VERSION = "catalog_canary_profile_v0"
CANARY_DOMAIN_PROFILE_SCHEMA_VERSION = "catalog_canary_domain_profile_v0"
CANARY_PROFILES_SCHEMA_VERSION = "catalog_canary_profiles_v0"
CANARY_PLAN_SCHEMA_VERSION = "catalog_canary_plan_v0"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "docs" / "interaction-pattern-catalog.md"


FAMILY_CHECKS: dict[str, list[dict[str, str]]] = {
    "Work Routing": [
        {
            "command": "python3 examples/quota-plan-smoke.py",
            "reason": "exercises quota should-run routing, fallback, and execution obligation projection",
        },
        {
            "command": "python3 examples/quota-work-lane-policy-smoke.py",
            "reason": "checks advancement, monitor, and no-work lane policy selection",
        },
        {
            "command": "python3 examples/monitor-scheduler-contract-smoke.py",
            "reason": "guards due-monitor routing without requiring real external polling",
        },
        {
            "command": "python3 examples/heartbeat-prompt-smoke.py",
            "reason": "checks heartbeat prompt and scheduler guidance for controller loops",
        },
    ],
    "Human Decision": [
        {
            "command": "python3 examples/todo-user-gate-scope-smoke.py",
            "reason": "checks scoped user-gate projection instead of global prose gates",
        },
        {
            "command": "python3 examples/operator-gate-resume-contract-smoke.py",
            "reason": "exercises operator gate preview and resume behavior",
        },
        {
            "command": "python3 examples/reward-gate-direct-write-contract-smoke.py",
            "reason": "guards reward/gate write boundaries before agent continuation",
        },
        {
            "command": "python3 examples/quota-agent-scoped-user-gate-smoke.py",
            "reason": "checks that agent-scoped user gates do not block unrelated lanes",
        },
    ],
    "State And Boundary": [
        {
            "command": "python3 examples/todo-contract-smoke.py",
            "reason": "checks todo metadata shape consumed by status and quota",
        },
        {
            "command": "python3 examples/active-state-structured-projection-smoke.py",
            "reason": "guards active-state structured projection from Markdown drift",
        },
        {
            "command": "python3 examples/task-graph-projection-fixture-smoke.py",
            "reason": "checks task graph projection and lineage without private sources",
        },
        {
            "command": "python3 examples/check-public-boundary-smoke.py",
            "reason": "guards public/private boundary scanning for touched files",
        },
    ],
    "Evidence Lifecycle": [
        {
            "command": "python3 examples/benchmark-run-ledger-smoke.py",
            "reason": "checks compact benchmark/run evidence without raw logs",
        },
        {
            "command": "python3 examples/benchmark-case-analysis-smoke.py",
            "reason": "checks reusable case-analysis projections from compact artifacts",
        },
        {
            "command": "python3 examples/benchmark-artifact-path-filter-smoke.py",
            "reason": "guards raw/private artifact path exclusion",
        },
        {
            "command": "python3 examples/content-ops-public-handle-observation-smoke.py",
            "reason": "checks public-handle evidence observation without private connector reads",
        },
    ],
    "Planning Governance": [
        {
            "command": "python3 examples/autonomous-replan-obligation-smoke.py",
            "reason": "guards stalled-turn autonomous replan obligations",
        },
        {
            "command": "python3 examples/monitor-poll-writeback-smoke.py",
            "reason": "checks monitor poll writeback and no-spend replan triggers",
        },
        {
            "command": "python3 examples/refresh-state-write-correctness-smoke.py",
            "reason": "checks refresh-state writeback correctness and projection updates",
        },
        {
            "command": "python3 examples/dreaming-dry-run-proposal-smoke.py",
            "reason": "checks planning proposal preview remains dry-run and machine-visible",
        },
    ],
}


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
        "loopx/decision_scope.py",
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
        "loopx/todo_contract.py",
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


CURRENT_REPO_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "pr-review-and-merge",
        "title": "PR review and merge workflow",
        "purpose": "Check public PR review packets, public-handle evidence, and merge-gate boundaries without approving or merging anything.",
        "catalog_families": ["Human Decision", "Evidence Lifecycle", "State And Boundary"],
        "trigger_hints": ("pr-review", "pull request", "github pr", "self-merge", "merge policy", "public pr metadata"),
        "checks": [
            {
                "command": "python3 examples/pr-review-command-smoke.py",
                "tier": "default",
                "reason": "checks the public-safe /loopx-pr-review packet and review-card contract",
            },
            {
                "command": "python3 examples/value-connectors-github-public-probe-smoke.py",
                "tier": "default",
                "reason": "guards public GitHub issue/PR metadata probes without raw body capture",
            },
            {
                "command": "python3 examples/check-public-boundary-smoke.py",
                "tier": "deep",
                "reason": "runs broader public/private boundary checks when review artifacts are promoted",
            },
        ],
    },
    {
        "id": "release-promotion",
        "title": "Release promotion readiness",
        "purpose": "Check whether the release/canary promotion path is ready without mutating the install.",
        "catalog_families": ["Work Routing", "Planning Governance", "State And Boundary"],
        "trigger_hints": ("release", "promotion", "canary-promotion", "install", "upgrade"),
        "checks": [
            {
                "command": "python3 examples/canary-promotion-readiness-smoke.py",
                "tier": "default",
                "reason": "checks promotion readiness from compact run history",
            },
            {
                "command": "python3 examples/canary-promotion-no-write-contract-smoke.py",
                "tier": "default",
                "reason": "guards no-write promotion readiness behavior",
            },
            {
                "command": "python3 examples/canary-promotion-readiness-writeback-smoke.py",
                "tier": "deep",
                "reason": "exercises promotion readiness writeback after explicit opt-in",
            },
        ],
    },
    {
        "id": "control-plane-refactor",
        "title": "Control-plane refactor safety",
        "purpose": "Sample hot-path route, policy seam, and interface budget checks for quota/status refactors.",
        "catalog_families": ["Work Routing", "State And Boundary", "Planning Governance"],
        "trigger_hints": ("refactor", "quota.py", "status.py", "control-plane", "policy seam"),
        "checks": [
            {
                "command": "python3 examples/control-plane-risk-characterization-smoke.py",
                "tier": "default",
                "reason": "characterizes shared control-plane routing risks",
            },
            {
                "command": "python3 examples/hot-path-interface-budget-smoke.py",
                "tier": "default",
                "reason": "keeps hot-path payload and module growth bounded",
            },
            {
                "command": "python3 examples/work-lane-contract-smoke.py",
                "tier": "deep",
                "reason": "covers broad work-lane policy interactions after larger refactors",
            },
        ],
    },
    {
        "id": "monitor-scheduler",
        "title": "Monitor scheduler routing",
        "purpose": "Check monitor due/quiet/replan behavior without polling external targets by default.",
        "catalog_families": ["Work Routing", "Planning Governance"],
        "trigger_hints": ("monitor", "scheduler", "next_due_at", "monitor-poll", "continuous_monitor"),
        "checks": [
            {
                "command": "python3 examples/monitor-scheduler-contract-smoke.py",
                "tier": "default",
                "reason": "checks due monitor selection, expiry, and priority behavior",
            },
            {
                "command": "python3 examples/monitor-poll-writeback-smoke.py",
                "tier": "default",
                "reason": "guards no-spend monitor poll writeback and replan triggers",
            },
            {
                "command": "python3 examples/heartbeat-quota-flow-smoke.py",
                "tier": "deep",
                "reason": "runs a broader heartbeat/quota control-flow sample",
            },
        ],
    },
    {
        "id": "state-write-correctness",
        "title": "State write correctness",
        "purpose": "Check local state writes, refresh-state, and todo write paths before touching writer internals.",
        "catalog_families": ["State And Boundary", "Planning Governance", "Human Decision"],
        "trigger_hints": ("state write", "refresh-state", "todo write", "idempotency", "revision", "lease"),
        "checks": [
            {
                "command": "python3 examples/local-state-write-correctness-contract-smoke.py",
                "tier": "default",
                "reason": "checks local state write correctness contract fixtures",
            },
            {
                "command": "python3 examples/refresh-state-write-correctness-smoke.py",
                "tier": "default",
                "reason": "guards refresh-state update behavior and projection writes",
            },
            {
                "command": "python3 examples/todo-concurrent-write-lock-smoke.py",
                "tier": "deep",
                "reason": "samples lock behavior for concurrent todo writes",
            },
        ],
    },
    {
        "id": "frontstage-rollout",
        "title": "Frontstage rollout projection",
        "purpose": "Check public frontstage/showcase projection data before visual browser smokes.",
        "catalog_families": ["State And Boundary", "Evidence Lifecycle", "Human Decision"],
        "trigger_hints": ("frontstage", "showcase", "rollout", "dashboard", "visual"),
        "checks": [
            {
                "command": "python3 examples/frontstage-rollout-projections-fixture-smoke.py",
                "tier": "default",
                "reason": "checks reusable frontstage rollout projection fixtures",
            },
            {
                "command": "python3 examples/showcase-animation-prototype-smoke.py",
                "tier": "default",
                "reason": "guards showcase animation projection data without a browser",
            },
            {
                "command": "node examples/dashboard-frontstage-browser-smoke.mjs",
                "tier": "deep",
                "reason": "runs browser-level visual route validation when UI is promoted",
            },
        ],
    },
    {
        "id": "benchmark-adapter-readiness",
        "title": "Benchmark adapter readiness",
        "purpose": "Check public adapter contracts and evidence boundaries without launching benchmark jobs by default.",
        "catalog_families": ["Evidence Lifecycle", "State And Boundary", "Work Routing"],
        "trigger_hints": ("benchmark", "adapter", "runner", "ledger", "skillsbench", "terminal-bench"),
        "checks": [
            {
                "command": "python3 examples/benchmark-core-adapter-contract-smoke.py",
                "tier": "default",
                "reason": "checks shared benchmark adapter contract behavior",
            },
            {
                "command": "python3 examples/benchmark-artifact-path-filter-smoke.py",
                "tier": "default",
                "reason": "guards raw/private benchmark artifact path exclusion",
            },
            {
                "command": "python3 examples/skillsbench-benchmark-run-smoke.py",
                "tier": "deep",
                "reason": "runs the heavier SkillsBench integration smoke only when explicitly requested",
            },
        ],
    },
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _parse_markdown_table(lines: list[str]) -> list[dict[str, str]]:
    rows = [_split_table_row(line) for line in lines if line.strip().startswith("|")]
    if len(rows) < 3:
        return []
    headers = rows[0]
    parsed: list[dict[str, str]] = []
    for row in rows[2:]:
        if len(row) != len(headers):
            continue
        parsed.append({headers[index]: value for index, value in enumerate(row)})
    return parsed


def _first_table_after(text: str, marker: str) -> list[dict[str, str]]:
    index = text.find(marker)
    if index < 0:
        return []
    table_lines: list[str] = []
    in_table = False
    for line in text[index:].splitlines():
        if line.strip().startswith("|"):
            table_lines.append(line)
            in_table = True
        elif in_table:
            break
    return _parse_markdown_table(table_lines)


def _pattern_ids(value: str) -> list[str]:
    return sorted(set(re.findall(r"\bIP-\d{3}\b", value)))


def _split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def _read_catalog(catalog_path: Path | None = None) -> tuple[Path, str]:
    path = (catalog_path or DEFAULT_CATALOG_PATH).expanduser()
    return path, path.read_text(encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_catalog_canary_profiles(catalog_path: Path | None = None) -> dict[str, Any]:
    path, text = _read_catalog(catalog_path)
    archetype_rows = _first_table_after(text, "| Canary Archetype |")
    family_rows = _first_table_after(text, "| Family |")

    archetypes = []
    for row in archetype_rows:
        name = row.get("Canary Archetype", "")
        archetypes.append(
            {
                "id": _slug(name),
                "name": name,
                "primary_question": row.get("Primary Question", ""),
                "trigger_surface": row.get("Typical Trigger Surface", ""),
                "fixture_depth": row.get("Fixture Depth", ""),
                "cost_tier": row.get("Cost Tier", ""),
                "failure_meaning": row.get("Failure Usually Means", ""),
            }
        )

    profiles = []
    for row in family_rows:
        family = row.get("Family", "")
        archetype_names = _split_semicolon(row.get("Default Canary Archetypes", ""))
        profiles.append(
            {
                "schema_version": CANARY_PROFILE_SCHEMA_VERSION,
                "id": _slug(family),
                "family": family,
                "pattern_ids": _pattern_ids(row.get("P0/P1 Pattern Coverage", "")),
                "default_archetypes": [
                    {
                        "id": _slug(name),
                        "name": name,
                    }
                    for name in archetype_names
                ],
                "trigger_surfaces": row.get("Trigger Surfaces", ""),
                "minimum_useful_fixture": row.get("Minimum Useful Fixture", ""),
                "failure_meaning": row.get("Failure Meaning", ""),
                "candidate_checks": FAMILY_CHECKS.get(family, []),
            }
        )

    domain_profiles = []
    for profile in CURRENT_REPO_PROFILES:
        domain_profiles.append(
            {
                "schema_version": CANARY_DOMAIN_PROFILE_SCHEMA_VERSION,
                **profile,
                "checks": list(profile.get("checks", [])),
            }
        )

    return {
        "ok": bool(archetypes and profiles),
        "schema_version": CANARY_PROFILES_SCHEMA_VERSION,
        "source": _display_path(path),
        "dry_run": True,
        "executes_checks": False,
        "archetype_count": len(archetypes),
        "profile_count": len(profiles),
        "domain_profile_count": len(domain_profiles),
        "archetypes": archetypes,
        "profiles": profiles,
        "domain_profiles": domain_profiles,
    }


def _selector_blob(changed_files: list[str], surfaces: list[str]) -> str:
    return "\n".join([*changed_files, *surfaces]).lower()


def _selection_reasons(profile: dict[str, Any], selector_blob: str) -> list[str]:
    family = str(profile.get("family") or "")
    family_lc = family.lower()
    reasons: list[str] = []
    if family_lc and family_lc in selector_blob:
        reasons.append(f"selector names catalog family `{family}`")
    for hint in FAMILY_SELECTOR_HINTS.get(family, ()):
        if hint.lower() in selector_blob:
            reasons.append(f"selector matches `{hint}`")
    trigger_surfaces = str(profile.get("trigger_surfaces") or "").lower()
    for token in re.findall(r"[a-z][a-z0-9_-]{2,}", selector_blob):
        if token in trigger_surfaces and f"trigger surface mentions `{token}`" not in reasons:
            reasons.append(f"trigger surface mentions `{token}`")
    return reasons


def _domain_selection_reasons(profile: dict[str, Any], selector_blob: str) -> list[str]:
    reasons: list[str] = []
    profile_id = str(profile.get("id") or "")
    title = str(profile.get("title") or "")
    if profile_id and profile_id in selector_blob:
        reasons.append(f"selector names profile `{profile_id}`")
    if title and title.lower() in selector_blob:
        reasons.append(f"selector names profile `{title}`")
    for hint in profile.get("trigger_hints", []):
        hint_text = str(hint or "").lower()
        if hint_text and hint_text in selector_blob:
            reasons.append(f"selector matches `{hint}`")
    for family in profile.get("catalog_families", []):
        family_text = str(family or "").lower()
        if family_text and family_text in selector_blob:
            reasons.append(f"selector matches family `{family}`")
    return reasons


def _domain_profile_with_checks(
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
    copied = dict(profile)
    copied["checks"] = checks[: max(1, max_checks)]
    copied["deep_checks_available"] = any(
        isinstance(check, dict) and check.get("tier") == "deep"
        for check in profile.get("checks", [])
    )
    copied["deep_checks_included"] = bool(include_deep_checks)
    return copied


def build_catalog_canary_plan(
    *,
    catalog_path: Path | None = None,
    changed_files: list[str] | None = None,
    surfaces: list[str] | None = None,
    families: list[str] | None = None,
    profiles: list[str] | None = None,
    include_deep_checks: bool = False,
    max_checks_per_family: int = 3,
    max_checks_per_profile: int = 3,
) -> dict[str, Any]:
    packet = build_catalog_canary_profiles(catalog_path)
    changed_files = changed_files or []
    surfaces = surfaces or []
    requested_families = {_slug(family) for family in (families or []) if family.strip()}
    requested_profiles = {_slug(profile) for profile in (profiles or []) if profile.strip()}
    selector_blob = _selector_blob(changed_files, surfaces)
    max_checks = max(1, max_checks_per_family)
    max_profile_checks = max(1, max_checks_per_profile)

    selected_profiles: list[dict[str, Any]] = []
    for profile in packet["profiles"]:
        if requested_profiles and not requested_families and not selector_blob:
            continue
        reasons = _selection_reasons(profile, selector_blob)
        if requested_families and _slug(str(profile.get("family") or "")) not in requested_families:
            continue
        if not requested_families and selector_blob and not reasons:
            continue
        profile_copy = dict(profile)
        profile_copy["candidate_checks"] = list(profile_copy.get("candidate_checks", []))[:max_checks]
        profile_copy["selection_reasons"] = reasons or [
            "selected because no narrower selector was provided",
        ]
        selected_profiles.append(profile_copy)

    selected_domain_profiles: list[dict[str, Any]] = []
    for profile in packet["domain_profiles"]:
        reasons = _domain_selection_reasons(profile, selector_blob)
        if requested_profiles and _slug(str(profile.get("id") or "")) not in requested_profiles:
            continue
        if not requested_profiles and selector_blob and not reasons:
            continue
        if not requested_profiles and not selector_blob:
            continue
        profile_copy = _domain_profile_with_checks(
            profile,
            include_deep_checks=include_deep_checks,
            max_checks=max_profile_checks,
        )
        profile_copy["selection_reasons"] = reasons or [
            "selected because this profile was explicitly requested",
        ]
        selected_domain_profiles.append(profile_copy)

    return {
        "ok": True,
        "schema_version": CANARY_PLAN_SCHEMA_VERSION,
        "source": packet["source"],
        "dry_run": True,
        "executes_checks": False,
        "selection_inputs": {
            "changed_files": changed_files,
            "surfaces": surfaces,
            "families": families or [],
            "profiles": profiles or [],
            "include_deep_checks": include_deep_checks,
            "max_checks_per_family": max_checks,
            "max_checks_per_profile": max_profile_checks,
        },
        "profile_count": len(selected_profiles),
        "domain_profile_count": len(selected_domain_profiles),
        "profiles": selected_profiles,
        "domain_profiles": selected_domain_profiles,
        "note": (
            "This planner only selects and explains candidate canary checks. "
            "It does not execute smoke tests or create new runtime contracts."
        ),
    }


def render_catalog_canary_profiles_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Catalog Canary Profiles",
        "",
        f"- source: `{payload.get('source')}`",
        f"- archetypes: `{payload.get('archetype_count')}`",
        f"- profiles: `{payload.get('profile_count')}`",
        "- dry_run: `true`",
        "- executes_checks: `false`",
        "",
    ]
    for profile in payload.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        lines.extend(
            [
                f"## {profile.get('family')}",
                f"- patterns: `{', '.join(profile.get('pattern_ids') or [])}`",
                "- archetypes: "
                + ", ".join(
                    f"`{item.get('name')}`"
                    for item in profile.get("default_archetypes", [])
                    if isinstance(item, dict)
                ),
                f"- trigger surfaces: {profile.get('trigger_surfaces')}",
                f"- minimum fixture: {profile.get('minimum_useful_fixture')}",
                f"- failure meaning: {profile.get('failure_meaning')}",
                "",
            ]
        )
    if payload.get("domain_profiles"):
        lines.extend(["## Current Repo Profiles", ""])
        for profile in payload.get("domain_profiles", []):
            if not isinstance(profile, dict):
                continue
            default_count = sum(
                1 for check in profile.get("checks", []) if isinstance(check, dict) and check.get("tier") != "deep"
            )
            deep_count = sum(
                1 for check in profile.get("checks", []) if isinstance(check, dict) and check.get("tier") == "deep"
            )
            lines.extend(
                [
                    f"### {profile.get('title')}",
                    f"- id: `{profile.get('id')}`",
                    f"- catalog families: `{', '.join(profile.get('catalog_families') or [])}`",
                    f"- purpose: {profile.get('purpose')}",
                    f"- default checks: `{default_count}`",
                    f"- deep checks: `{deep_count}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_catalog_canary_plan_markdown(payload: dict[str, Any]) -> str:
    inputs = payload.get("selection_inputs") if isinstance(payload.get("selection_inputs"), dict) else {}
    lines = [
        "# Catalog Canary Plan",
        "",
        f"- source: `{payload.get('source')}`",
        "- dry_run: `true`",
        "- executes_checks: `false`",
        f"- selected_profiles: `{payload.get('profile_count')}`",
        f"- selected_domain_profiles: `{payload.get('domain_profile_count')}`",
        f"- changed_files: `{', '.join(inputs.get('changed_files') or [])}`",
        f"- surfaces: `{', '.join(inputs.get('surfaces') or [])}`",
        f"- families: `{', '.join(inputs.get('families') or [])}`",
        f"- profiles: `{', '.join(inputs.get('profiles') or [])}`",
        f"- include_deep_checks: `{str(inputs.get('include_deep_checks')).lower()}`",
        "",
        str(payload.get("note") or ""),
        "",
    ]
    for profile in payload.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        lines.extend(
            [
                f"## {profile.get('family')}",
                f"- patterns: `{', '.join(profile.get('pattern_ids') or [])}`",
                "- selected because: "
                + "; ".join(str(reason) for reason in profile.get("selection_reasons", [])),
                "- archetypes: "
                + ", ".join(
                    f"`{item.get('name')}`"
                    for item in profile.get("default_archetypes", [])
                    if isinstance(item, dict)
                ),
                f"- minimum fixture: {profile.get('minimum_useful_fixture')}",
                f"- failure meaning: {profile.get('failure_meaning')}",
                "- suggested checks:",
            ]
        )
        for check in profile.get("candidate_checks", []):
            if isinstance(check, dict):
                lines.append(f"  - `{check.get('command')}` - {check.get('reason')}")
        lines.append("")
    for profile in payload.get("domain_profiles", []):
        if not isinstance(profile, dict):
            continue
        lines.extend(
            [
                f"## {profile.get('title')}",
                f"- id: `{profile.get('id')}`",
                f"- catalog families: `{', '.join(profile.get('catalog_families') or [])}`",
                "- selected because: "
                + "; ".join(str(reason) for reason in profile.get("selection_reasons", [])),
                f"- purpose: {profile.get('purpose')}",
                f"- deep checks available: `{str(profile.get('deep_checks_available')).lower()}`",
                f"- deep checks included: `{str(profile.get('deep_checks_included')).lower()}`",
                "- suggested checks:",
            ]
        )
        for check in profile.get("checks", []):
            if isinstance(check, dict):
                lines.append(
                    f"  - `{check.get('command')}` [{check.get('tier')}] - {check.get('reason')}"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
