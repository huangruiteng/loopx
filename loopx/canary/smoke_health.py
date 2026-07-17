from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .planner import (
    REPO_ROOT,
    build_catalog_canary_profiles,
    build_quality_surface_catalog_audit,
)
from .runner import build_canary_smoke_suite_run
from .smoke_profiles import list_smoke_suite_profiles


SMOKE_FLEET_HEALTH_SCHEMA_VERSION = "smoke_fleet_health_v0"
PR_FAST_WORKFLOW = ".github/workflows/python-tests.yml"
PR_FAST_SCRIPTS = (
    "examples/control_plane/cli-output-budget-regression-smoke.py",
)
CADENCE_IDS = (
    "pr_fast",
    "catalog_canary",
    "daily_full_public",
    "release_gate",
)
_PROFILE_REF_RE = re.compile(r"--profile\s+([^\s`]+)")
_SUBPROCESS_CALLS = {"Popen", "check_call", "check_output", "run"}


def _script_from_check(check: dict[str, Any]) -> str:
    normalized = check.get("normalized")
    if isinstance(normalized, dict) and normalized.get("script"):
        return str(normalized["script"]).replace("\\", "/")
    command = str(check.get("command") or "")
    for part in command.split():
        normalized_part = part.strip("'\"").replace("\\", "/")
        if normalized_part.endswith("-smoke.py"):
            return normalized_part
    return ""


def _profile_script_owners() -> tuple[dict[str, set[str]], dict[str, dict[str, Any]]]:
    payload = build_catalog_canary_profiles()
    owners: dict[str, set[str]] = defaultdict(set)
    profile_by_id: dict[str, dict[str, Any]] = {}
    for key in ("profiles", "domain_profiles"):
        for profile in payload.get(key, []):
            if not isinstance(profile, dict):
                continue
            profile_id = str(profile.get("id") or "")
            if not profile_id:
                continue
            profile_by_id[profile_id] = profile
            checks = profile.get("candidate_checks") or profile.get("checks") or []
            for check in checks:
                if not isinstance(check, dict):
                    continue
                script = _script_from_check(check)
                if script:
                    owners[script].add(f"catalog-profile:{profile_id}")
    return owners, profile_by_id


def _smoke_profile_owners() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    for profile in list_smoke_suite_profiles():
        profile_id = str(profile.get("id") or "")
        if not profile_id:
            continue
        preview = build_canary_smoke_suite_run(
            suite=str(profile.get("suite") or "full-public"),
            profiles=[profile_id],
            execute=False,
        )
        for check in preview.get("selected_checks", []):
            if not isinstance(check, dict):
                continue
            script = _script_from_check(check)
            if script:
                owners[script].add(f"smoke-profile:{profile_id}")
    return owners


def _release_profile_ids() -> set[str]:
    profile_ids: set[str] = set()
    audit = build_quality_surface_catalog_audit()
    for surface in audit.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        layers = surface.get("layers")
        release_gate = layers.get("release_gate") if isinstance(layers, dict) else {}
        refs = release_gate.get("refs", []) if isinstance(release_gate, dict) else []
        for ref in refs:
            match = _PROFILE_REF_RE.search(str(ref))
            if match:
                profile_ids.add(match.group(1))
    return profile_ids


def _repo_script_path(script: str) -> Path:
    return REPO_ROOT / script


def _area_for_script(script: str) -> str:
    parts = Path(script).parts
    if len(parts) >= 3 and parts[0] == "examples":
        return parts[1]
    return "examples-root"


def _identical_content_groups(scripts: Iterable[str]) -> list[list[str]]:
    by_digest: dict[str, list[str]] = defaultdict(list)
    for script in scripts:
        path = _repo_script_path(script)
        if path.is_file():
            by_digest[hashlib.sha256(path.read_bytes()).hexdigest()].append(script)
    return sorted(
        (sorted(group) for group in by_digest.values() if len(group) > 1),
        key=lambda group: (-len(group), group),
    )


def _subprocess_name(node: ast.expr) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _direct_nested_execution_edges(scripts: Iterable[str]) -> list[dict[str, str]]:
    script_set = set(scripts)
    by_name: dict[str, str] = {}
    duplicate_names: set[str] = set()
    for script in script_set:
        name = Path(script).name
        if name in by_name:
            duplicate_names.add(name)
        else:
            by_name[name] = script
    for name in duplicate_names:
        by_name.pop(name, None)

    edges: set[tuple[str, str]] = set()
    for wrapper in sorted(script_set):
        path = _repo_script_path(wrapper)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _subprocess_name(node.func) not in _SUBPROCESS_CALLS:
                continue
            for child in ast.walk(node):
                if not (
                    isinstance(child, ast.Constant)
                    and isinstance(child.value, str)
                    and child.value.endswith("-smoke.py")
                ):
                    continue
                raw = child.value.replace("\\", "/")
                target = raw if raw in script_set else by_name.get(Path(raw).name, "")
                if target and target != wrapper:
                    edges.add((wrapper, target))
    return [
        {"wrapper": wrapper, "nested_script": nested, "confidence": "direct_static_call"}
        for wrapper, nested in sorted(edges)
    ]


def _expand_receipt_paths(receipt_paths: Iterable[Path]) -> list[Path]:
    expanded: list[Path] = []
    seen: set[Path] = set()
    for raw_path in receipt_paths:
        path = Path(raw_path).expanduser()
        candidates = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            expanded.append(candidate)
    return expanded


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 3)


def _receipt_health(
    *,
    inventory_scripts: set[str],
    receipt_paths: Iterable[Path],
    slow_threshold_seconds: float,
    review_limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    paths = _expand_receipt_paths(receipt_paths)
    warnings: list[dict[str, Any]] = []
    observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sources: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    durations: list[float] = []

    for path in paths:
        source = path.name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            warnings.append(
                {"kind": "invalid_receipt", "source": source, "message": str(exc)}
            )
            continue
        if not isinstance(payload, dict) or payload.get("schema_version") != "canary_smoke_suite_run_v0":
            warnings.append(
                {
                    "kind": "unsupported_receipt",
                    "source": source,
                    "message": "expected canary_smoke_suite_run_v0",
                }
            )
            continue
        if payload.get("suite") != "full-public":
            warnings.append(
                {
                    "kind": "wrong_suite",
                    "source": source,
                    "message": "smoke health accepts full-public receipts only",
                }
            )
            continue
        selected_checks = payload.get("selected_checks")
        if not isinstance(selected_checks, list):
            warnings.append(
                {
                    "kind": "invalid_receipt",
                    "source": source,
                    "message": "selected_checks must be a list",
                }
            )
            continue
        sources.append(
            {
                "source": source,
                "selected_check_count": len(selected_checks),
                "failure_count": int(payload.get("failure_count") or 0),
                "timeout_count": int(payload.get("timeout_count") or 0),
            }
        )
        seen_in_receipt: set[str] = set()
        timeout_seconds = float(payload.get("timeout_seconds") or 0.0)
        for check in selected_checks:
            if not isinstance(check, dict):
                continue
            script = _script_from_check(check)
            if not script:
                warnings.append(
                    {"kind": "missing_script", "source": source, "message": "check has no smoke script"}
                )
                continue
            if script in seen_in_receipt:
                warnings.append(
                    {
                        "kind": "duplicate_receipt_check",
                        "source": source,
                        "script": script,
                        "message": "script appears more than once in one receipt",
                    }
                )
            seen_in_receipt.add(script)
            if script not in inventory_scripts:
                warnings.append(
                    {
                        "kind": "unknown_script",
                        "source": source,
                        "script": script,
                        "message": "receipt script is not in the current full-public inventory",
                    }
                )
                continue
            status = str(check.get("status") or "unknown")
            duration_raw = check.get("duration_seconds")
            duration = (
                float(duration_raw)
                if isinstance(duration_raw, (int, float)) and not isinstance(duration_raw, bool)
                else None
            )
            observation = {
                "source": source,
                "status": status,
                "ok": bool(check.get("ok")),
                "duration_seconds": duration,
                "timeout_seconds": timeout_seconds,
            }
            observations[script].append(observation)
            status_counts[status] += 1
            if duration is not None:
                durations.append(duration)

    failure_examples: list[dict[str, Any]] = []
    slow_checks: list[dict[str, Any]] = []
    near_timeout_checks: list[dict[str, Any]] = []
    for script, script_observations in observations.items():
        for observation in script_observations:
            if not observation["ok"]:
                failure_examples.append({"script": script, **observation})
        measured = [
            item for item in script_observations if item["duration_seconds"] is not None
        ]
        if not measured:
            continue
        slowest = max(measured, key=lambda item: float(item["duration_seconds"]))
        summary = {
            "script": script,
            "max_duration_seconds": round(float(slowest["duration_seconds"]), 3),
            "observation_count": len(script_observations),
        }
        if float(slowest["duration_seconds"]) >= slow_threshold_seconds:
            slow_checks.append(summary)
        timeout_seconds = float(slowest["timeout_seconds"] or 0.0)
        if timeout_seconds and float(slowest["duration_seconds"]) >= timeout_seconds * 0.8:
            near_timeout_checks.append(
                {**summary, "timeout_seconds": timeout_seconds, "timeout_ratio": round(float(slowest["duration_seconds"]) / timeout_seconds, 3)}
            )

    failure_examples.sort(key=lambda item: (item["script"], item["source"]))
    slow_checks.sort(key=lambda item: (-float(item["max_duration_seconds"]), item["script"]))
    near_timeout_checks.sort(
        key=lambda item: (-float(item["timeout_ratio"]), item["script"])
    )
    observed_scripts = set(observations)
    missing_scripts = sorted(inventory_scripts - observed_scripts)
    invalid_receipt_count = sum(
        warning["kind"] in {"invalid_receipt", "unsupported_receipt", "wrong_suite"}
        for warning in warnings
    )
    failed_count = sum(count for status, count in status_counts.items() if status not in {"passed", "skipped_git_required"})
    timeout_count = status_counts.get("timed_out", 0)
    ready = bool(paths) and not invalid_receipt_count and not missing_scripts and not failed_count
    return (
        {
            "ready": ready,
            "receipt_path_count": len(paths),
            "accepted_receipt_count": len(sources),
            "sources": sources[:review_limit],
            "observed_script_count": len(observed_scripts),
            "missing_script_count": len(missing_scripts),
            "missing_script_examples": missing_scripts[:review_limit],
            "observation_count": sum(status_counts.values()),
            "status_counts": dict(sorted(status_counts.items())),
            "failure_count": failed_count,
            "timeout_count": timeout_count,
            "failure_examples": failure_examples[:review_limit],
            "duration_seconds": {
                "sample_count": len(durations),
                "sum": round(sum(durations), 3),
                "p50": _percentile(durations, 0.50),
                "p95": _percentile(durations, 0.95),
                "p99": _percentile(durations, 0.99),
                "max": round(max(durations), 3) if durations else None,
            },
            "slow_threshold_seconds": slow_threshold_seconds,
            "slow_check_count": len(slow_checks),
            "slow_check_examples": slow_checks[:review_limit],
            "near_timeout_check_count": len(near_timeout_checks),
            "near_timeout_check_examples": near_timeout_checks[:review_limit],
            "note": (
                "Readiness requires at least one accepted full-public receipt, complete "
                "current-inventory coverage, and no failed or timed-out observations. "
                "stdout/stderr tails and repository-local paths are intentionally omitted."
            ),
        },
        warnings,
    )


def build_smoke_fleet_health(
    *,
    receipt_paths: Iterable[Path] = (),
    include_inventory: bool = False,
    slow_threshold_seconds: float = 30.0,
    review_limit: int = 20,
) -> dict[str, Any]:
    """Build a compact, read-only health baseline for public smoke coverage."""

    review_limit = max(1, int(review_limit))
    slow_threshold_seconds = max(0.0, float(slow_threshold_seconds))
    full_preview = build_canary_smoke_suite_run(suite="full-public", execute=False)
    inventory_scripts = sorted(
        {
            _script_from_check(check)
            for check in full_preview.get("selected_checks", [])
            if isinstance(check, dict) and _script_from_check(check)
        }
    )
    inventory_set = set(inventory_scripts)
    catalog_owners, catalog_profiles = _profile_script_owners()
    smoke_owners = _smoke_profile_owners()
    release_profile_ids = _release_profile_ids()
    release_scripts: set[str] = set()
    for profile_id in release_profile_ids:
        profile = catalog_profiles.get(profile_id, {})
        checks = profile.get("candidate_checks") or profile.get("checks") or []
        for check in checks:
            if isinstance(check, dict):
                script = _script_from_check(check)
                if script:
                    release_scripts.add(script)

    pr_fast_scripts = set(PR_FAST_SCRIPTS)
    workflow_path = REPO_ROOT / PR_FAST_WORKFLOW
    workflow_text = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    workflow_missing_scripts = sorted(
        script for script in pr_fast_scripts if script not in workflow_text
    )

    inventory: list[dict[str, Any]] = []
    cadence_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    area_counts: Counter[str] = Counter()
    owner_gap_examples: list[str] = []
    for script in inventory_scripts:
        cadences = ["daily_full_public"]
        owners = set(catalog_owners.get(script, set())) | set(smoke_owners.get(script, set()))
        if script in pr_fast_scripts:
            cadences.append("pr_fast")
            owners.add("pr-fast:python-tests")
        if script in catalog_owners:
            cadences.append("catalog_canary")
        if script in release_scripts:
            cadences.append("release_gate")
        ordered_cadences = [cadence for cadence in CADENCE_IDS if cadence in cadences]
        ordered_owners = sorted(owners)
        area = _area_for_script(script)
        for cadence in ordered_cadences:
            cadence_counts[cadence] += 1
        for owner in ordered_owners:
            owner_counts[owner] += 1
        area_counts[area] += 1
        if not ordered_owners:
            owner_gap_examples.append(script)
        inventory.append(
            {
                "script": script,
                "area": area,
                "cadences": ordered_cadences,
                "targeted_owners": ordered_owners,
                "owner_status": "targeted" if ordered_owners else "daily_only",
            }
        )

    identical_groups = _identical_content_groups(inventory_scripts)
    nested_edges = _direct_nested_execution_edges(inventory_scripts)
    receipt_health, receipt_warnings = _receipt_health(
        inventory_scripts=inventory_set,
        receipt_paths=receipt_paths,
        slow_threshold_seconds=slow_threshold_seconds,
        review_limit=review_limit,
    )
    warnings = list(receipt_warnings)
    if workflow_missing_scripts:
        warnings.append(
            {
                "kind": "pr_fast_workflow_drift",
                "source": PR_FAST_WORKFLOW,
                "scripts": workflow_missing_scripts,
                "message": "declared PR-fast smoke is missing from the workflow",
            }
        )
    ok = bool(inventory_scripts) and not workflow_missing_scripts and not any(
        warning.get("kind") in {"invalid_receipt", "unsupported_receipt", "wrong_suite"}
        for warning in warnings
    )
    payload: dict[str, Any] = {
        "ok": ok,
        "ready": bool(ok and receipt_health["ready"]),
        "schema_version": SMOKE_FLEET_HEALTH_SCHEMA_VERSION,
        "dry_run": True,
        "executes_checks": False,
        "writes_evidence": False,
        "creates_runtime_contract": False,
        "inventory_count": len(inventory_scripts),
        "cadence_counts": {
            cadence: cadence_counts.get(cadence, 0) for cadence in CADENCE_IDS
        },
        "area_counts": dict(sorted(area_counts.items())),
        "targeted_owner_count": sum(
            1 for entry in inventory if entry["owner_status"] == "targeted"
        ),
        "owner_gap_count": len(owner_gap_examples),
        "owner_gap_examples": owner_gap_examples[:review_limit],
        "targeted_owner_counts": dict(sorted(owner_counts.items())),
        "workflow_contract": {
            "pr_fast_workflow": PR_FAST_WORKFLOW,
            "declared_scripts": sorted(pr_fast_scripts),
            "missing_scripts": workflow_missing_scripts,
        },
        "contract_reuse": {
            "identical_content_group_count": len(identical_groups),
            "identical_content_groups": identical_groups[:review_limit],
            "direct_nested_execution_count": len(nested_edges),
            "direct_nested_execution_candidates": nested_edges[:review_limit],
            "semantic_duplicate_inference": "manual_review_required",
            "note": (
                "Exact file identity and direct static subprocess nesting are high-confidence "
                "review candidates. Shared profile membership or similar names are not treated "
                "as semantic duplicates and never trigger automatic deletion."
            ),
        },
        "receipt_health": receipt_health,
        "warning_count": len(warnings),
        "warnings": warnings[:review_limit],
        "note": (
            "This report separates the fast PR gate, catalog canaries, daily full-public "
            "coverage, and release profiles. It reports retirement candidates but does not "
            "delete, migrate, or weaken any smoke contract. Use --include-inventory only for "
            "the explicit diagnostic cold path."
        ),
    }
    if include_inventory:
        payload["inventory"] = inventory
    return payload


def render_smoke_fleet_health_markdown(payload: dict[str, Any]) -> str:
    cadence_counts = payload.get("cadence_counts")
    cadence_counts = cadence_counts if isinstance(cadence_counts, dict) else {}
    receipt = payload.get("receipt_health")
    receipt = receipt if isinstance(receipt, dict) else {}
    contract_reuse = payload.get("contract_reuse")
    contract_reuse = contract_reuse if isinstance(contract_reuse, dict) else {}
    durations = receipt.get("duration_seconds")
    durations = durations if isinstance(durations, dict) else {}
    lines = [
        "# Smoke Fleet Health",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- ready: `{str(payload.get('ready')).lower()}`",
        f"- inventory: `{payload.get('inventory_count')}`",
        f"- pr_fast: `{cadence_counts.get('pr_fast') or 0}`",
        f"- catalog_canary: `{cadence_counts.get('catalog_canary') or 0}`",
        f"- daily_full_public: `{cadence_counts.get('daily_full_public') or 0}`",
        f"- release_gate: `{cadence_counts.get('release_gate') or 0}`",
        f"- targeted_owners: `{payload.get('targeted_owner_count')}`",
        f"- owner_gaps: `{payload.get('owner_gap_count')}`",
        f"- receipt_observations: `{receipt.get('observation_count') or 0}`",
        f"- receipt_failures: `{receipt.get('failure_count') or 0}`",
        f"- receipt_timeouts: `{receipt.get('timeout_count') or 0}`",
        f"- duration_p95_seconds: `{durations.get('p95')}`",
        f"- duration_max_seconds: `{durations.get('max')}`",
        f"- identical_content_groups: `{contract_reuse.get('identical_content_group_count') or 0}`",
        f"- direct_nested_execution_candidates: `{contract_reuse.get('direct_nested_execution_count') or 0}`",
        "",
        str(payload.get("note") or ""),
    ]
    for title, key in (
        ("Slow Checks", "slow_check_examples"),
        ("Failures", "failure_examples"),
        ("Owner Gaps", "owner_gap_examples"),
    ):
        values = receipt.get(key) if key != "owner_gap_examples" else payload.get(key)
        if not isinstance(values, list) or not values:
            continue
        lines.extend(["", f"## {title}"])
        for value in values:
            if isinstance(value, dict):
                script = value.get("script")
                detail = value.get("max_duration_seconds") or value.get("status") or "review"
                lines.append(f"- `{script}`: `{detail}`")
            else:
                lines.append(f"- `{value}`")
    return "\n".join(lines).rstrip() + "\n"
