from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .planner import REPO_ROOT
from .runner import build_canary_smoke_suite_run


PREMERGE_GATE_SCHEMA_VERSION = "loopx_premerge_validation_gate_v0"
PREMERGE_VALIDATION_SUMMARY_SCHEMA_VERSION = "premerge_validation_summary_v0"
ProgressCallback = Callable[[dict[str, Any]], None]

PREMERGE_TIERS = {"quick", "standard", "deep"}

CONTROL_PLANE_TOKENS = (
    "loopx/control_plane/",
    "loopx/quota.py",
    "loopx/status.py",
    "loopx/todos.py",
    "loopx/state_refresh.py",
    "loopx/review_packet.py",
    "loopx/heartbeat_prompt.py",
    "loopx/cli_commands/quota",
    "loopx/cli_commands/status",
    "loopx/cli_commands/todo",
    "loopx/cli_commands/refresh",
)
CANARY_TOKENS = (
    "loopx/canary/",
    "loopx/cli_commands/canary.py",
    "examples/canary/",
    "tests/test_smoke_suite.py",
)
INSTALL_RELEASE_TOKENS = (
    "scripts/install",
    "scripts/loopx",
    "loopx/promotion_gate.py",
    "examples/release/",
    "examples/public_entry/",
)
DOC_CONTENT_TOKENS = (
    "docs/",
    "README",
    "AGENTS.md",
    "CONTRIBUTOR_TASKS.md",
    "examples/project/",
    "loopx/capabilities/content_ops/",
)
PUBLIC_BOUNDARY_TOKENS = (
    "docs/",
    "examples/",
    "README",
    "AGENTS.md",
    ".github/",
)
BENCHMARK_SENSITIVE_TOKENS = (
    "loopx/benchmark",
    "loopx/worker_bridge.py",
    "scripts/skillsbench",
    "scripts/terminal_bench",
    "examples/skillsbench",
    "examples/terminal-bench",
    "examples/benchmark",
)
LARK_KANBAN_TOKENS = (
    "loopx/lark_kanban.py",
    "loopx/cli_commands/lark_kanban.py",
    "examples/lark-kanban",
)
INHERITED_BASELINE_COMMANDS = (
    "repo-python-line-budget-smoke.py",
)


def _norm_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _path_matches(path: str, tokens: tuple[str, ...]) -> bool:
    normalized = _norm_path(path)
    lowered = normalized.lower()
    for token in tokens:
        token_lower = token.lower()
        if lowered == token_lower or lowered.startswith(token_lower):
            return True
        if token_lower in lowered:
            return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = _norm_path(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def classify_premerge_surfaces(changed_files: list[str]) -> dict[str, Any]:
    files = _dedupe(changed_files)
    python_files = [
        path for path in files
        if path.endswith(".py") and (REPO_ROOT / path).exists()
    ]
    surfaces: list[str] = []
    risk_profiles: list[str] = []
    manual_holds: list[dict[str, str]] = []

    def mark(surface: str, profile: str | None = None) -> None:
        if surface not in surfaces:
            surfaces.append(surface)
        if profile and profile not in risk_profiles:
            risk_profiles.append(profile)

    if any(_path_matches(path, CONTROL_PLANE_TOKENS) for path in files):
        mark("control_plane", "core-control-plane")
    if any(_path_matches(path, CANARY_TOKENS) for path in files):
        mark("canary_runner", "canary-runner")
    if any(_path_matches(path, INSTALL_RELEASE_TOKENS) for path in files):
        mark("install_release", "public-entry-install-release")
    if any(_path_matches(path, DOC_CONTENT_TOKENS) for path in files):
        mark("docs_project_content", "docs-project-content-ops")
    if any(_path_matches(path, PUBLIC_BOUNDARY_TOKENS) for path in files):
        mark("public_boundary")
    if any(_path_matches(path, BENCHMARK_SENSITIVE_TOKENS) for path in files):
        mark("benchmark_sensitive")
        manual_holds.append(
            {
                "kind": "benchmark_sensitive",
                "reason": (
                    "benchmark adapter, scoring, runner, or evidence paths require "
                    "explicit maintainer review before self-merge"
                ),
            }
        )
    if any(_path_matches(path, LARK_KANBAN_TOKENS) for path in files):
        mark("lark_kanban")
        manual_holds.append(
            {
                "kind": "lark_kanban_reviewer",
                "reason": "Lark Kanban paths require ZaynJarvis review or explicit owner bypass",
            }
        )
    if python_files:
        mark("python")
    if not surfaces and files:
        mark("general")

    if "control_plane" in surfaces and "canary-runner" not in risk_profiles:
        # Control-plane refactors often depend on planner selection staying honest.
        risk_profiles.append("canary-runner")

    return {
        "changed_files": files,
        "changed_file_count": len(files),
        "python_files": python_files,
        "surfaces": surfaces,
        "risk_profiles": risk_profiles,
        "manual_holds": manual_holds,
        "public_boundary_scan_recommended": "public_boundary" in surfaces,
    }


def _display_argv(argv: list[str]) -> list[str]:
    displayed = list(argv)
    if displayed and Path(displayed[0]).resolve() == Path(sys.executable).resolve():
        displayed[0] = "python3"
    for index, value in enumerate(displayed[1:], start=1):
        path = Path(value)
        try:
            displayed[index] = str(path.resolve().relative_to(REPO_ROOT.resolve()))
        except (OSError, ValueError):
            displayed[index] = value
    return displayed


def _run_gate_check(
    *,
    check_id: str,
    argv: list[str],
    reason: str,
    execute: bool,
    timeout_seconds: float,
    progress_callback: ProgressCallback | None = None,
    section: str = "direct_checks",
    check_index: int | None = None,
    check_count: int | None = None,
) -> dict[str, Any]:
    check = {
        "id": check_id,
        "kind": "direct_command",
        "argv": argv,
        "display_argv": _display_argv(argv),
        "command": " ".join(_display_argv(argv)),
        "reason": reason,
        "status": "ready",
        "ok": True,
    }
    if check_index is not None and check_count is not None:
        check.update({"check_index": check_index, "check_count": check_count})
    if not execute:
        return check

    started = time.monotonic()
    if progress_callback:
        progress_callback(
            {
                "schema_version": "canary_premerge_progress_v0",
                "event": "check_started",
                "section": section,
                "check_id": check_id,
                "check_index": check_index,
                "check_count": check_count,
                "command": check["command"],
            }
        )
    try:
        completed = subprocess.run(
            argv,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(1.0, timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        check.update(
            {
                "ok": False,
                "status": "timed_out",
                "returncode": None,
                "duration_seconds": round(time.monotonic() - started, 3),
                "stdout_tail": (exc.stdout or "")[-800:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-800:] if isinstance(exc.stderr, str) else "",
            }
        )
        if progress_callback:
            progress_callback(
                {
                    "schema_version": "canary_premerge_progress_v0",
                    "event": "check_finished",
                    "section": section,
                    "check_id": check_id,
                    "check_index": check_index,
                    "check_count": check_count,
                    "status": check.get("status"),
                    "ok": False,
                    "duration_seconds": check.get("duration_seconds"),
                }
            )
        return check

    check.update(
        {
            "ok": completed.returncode == 0,
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": completed.stdout[-800:],
            "stderr_tail": completed.stderr[-800:],
        }
    )
    if progress_callback:
        progress_callback(
            {
                "schema_version": "canary_premerge_progress_v0",
                "event": "check_finished",
                "section": section,
                "check_id": check_id,
                "check_index": check_index,
                "check_count": check_count,
                "status": check.get("status"),
                "ok": bool(check.get("ok")),
                "duration_seconds": check.get("duration_seconds"),
            }
        )
    return check


def _diff_hygiene_checks(
    *,
    base_ref: str,
    execute: bool,
    timeout_seconds: float,
    progress_callback: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    base = (base_ref or "origin/main").strip() or "origin/main"
    specs = [
        (
            "diff_check_committed",
            ["git", "diff", "--check", f"{base}...HEAD"],
            "checks committed PR diff whitespace/conflict-marker hygiene",
        ),
        (
            "diff_check_staged",
            ["git", "diff", "--cached", "--check"],
            "checks staged changes not yet committed",
        ),
        (
            "diff_check_unstaged",
            ["git", "diff", "--check"],
            "checks unstaged changes not yet committed",
        ),
    ]
    checks: list[dict[str, Any]] = []
    for index, (check_id, argv, reason) in enumerate(specs, start=1):
        checks.append(
            _run_gate_check(
                check_id=check_id,
                argv=argv,
                reason=reason,
                execute=execute,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                section="direct_checks",
                check_index=index,
                check_count=len(specs),
            )
        )
    return checks


def _py_compile_check(
    *,
    python_files: list[str],
    execute: bool,
    timeout_seconds: float,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any] | None:
    if not python_files:
        return None
    return _run_gate_check(
        check_id="changed_python_py_compile",
        argv=[sys.executable, "-m", "py_compile", *python_files],
        reason="compiles changed Python files that still exist in the worktree",
        execute=execute,
        timeout_seconds=timeout_seconds,
        progress_callback=progress_callback,
        section="python_compile",
        check_index=1,
        check_count=1,
    )


def _gate_status(
    *,
    execute: bool,
    changed_files: list[str],
    direct_checks: list[dict[str, Any]],
    catalog_run: dict[str, Any],
    risk_profile_run: dict[str, Any] | None,
    boundary_run: dict[str, Any] | None,
    manual_holds: list[dict[str, str]],
) -> dict[str, Any]:
    direct_failures = [check for check in direct_checks if not check.get("ok")]
    run_failures = []
    for run in [catalog_run, risk_profile_run, boundary_run]:
        if isinstance(run, dict) and not run.get("ok"):
            run_failures.append(run)
    if direct_failures or run_failures:
        status = "failed"
    elif not changed_files:
        status = "no_changes"
    elif manual_holds:
        status = "manual_review_required"
    elif not execute:
        status = "preview_only"
    else:
        status = "passed"
    return {
        "status": status,
        "merge_gate_passed": status == "passed",
        "self_merge_allowed": status == "passed" and not manual_holds,
        "direct_failure_count": len(direct_failures),
        "run_failure_count": len(run_failures),
        "manual_hold_count": len(manual_holds),
    }


def _check_command(check: dict[str, Any]) -> str:
    normalized = (
        check.get("normalized")
        if isinstance(check.get("normalized"), dict)
        else {}
    )
    display_argv = normalized.get("display_argv")
    if isinstance(display_argv, list) and display_argv:
        return " ".join(str(part) for part in display_argv)
    return str(check.get("command") or "")


def _run_summary(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    selected_checks = [
        check for check in run.get("selected_checks", [])
        if isinstance(check, dict)
    ]
    executed_checks = [
        check for check in selected_checks
        if str(check.get("status") or "") not in {"", "ready", "skipped"}
    ]
    failures = [check for check in selected_checks if check.get("ok") is False]
    return {
        "ok": bool(run.get("ok")),
        "selected_check_count": int(run.get("selected_check_count") or len(selected_checks)),
        "executed_check_count": int(run.get("executed_check_count") or len(executed_checks)),
        "failure_count": int(run.get("failure_count") or len(failures)),
        "warning_count": int(run.get("warning_count") or 0),
        "advisory_failure_count": int(run.get("advisory_failure_count") or 0),
        "selected_commands": [_check_command(check) for check in selected_checks],
        "failed_commands": [_check_command(check) for check in failures],
    }


def build_validation_summary(
    *,
    direct_checks: list[dict[str, Any]],
    catalog_run: dict[str, Any],
    risk_profile_run: dict[str, Any] | None,
    boundary_run: dict[str, Any] | None,
) -> dict[str, Any]:
    direct_failures = [check for check in direct_checks if check.get("ok") is False]
    direct_commands = [str(check.get("command") or "") for check in direct_checks]
    run_summaries = {
        "catalog_run": _run_summary(catalog_run),
        "risk_profile_run": _run_summary(risk_profile_run),
        "boundary_run": _run_summary(boundary_run),
    }
    active_run_summaries = [
        summary for summary in run_summaries.values()
        if isinstance(summary, dict)
    ]
    selected_commands: list[str] = []
    failed_commands: list[str] = []
    for summary in active_run_summaries:
        selected_commands.extend(summary["selected_commands"])
        failed_commands.extend(summary["failed_commands"])
    failed_commands.extend(str(check.get("command") or "") for check in direct_failures)
    return {
        "schema_version": PREMERGE_VALIDATION_SUMMARY_SCHEMA_VERSION,
        "direct_check_count": len(direct_checks),
        "direct_failure_count": len(direct_failures),
        "selected_check_count": sum(
            int(summary["selected_check_count"]) for summary in active_run_summaries
        ),
        "executed_check_count": sum(
            int(summary["executed_check_count"]) for summary in active_run_summaries
        ),
        "failure_count": len(direct_failures)
        + sum(int(summary["failure_count"]) for summary in active_run_summaries),
        "warning_count": sum(int(summary["warning_count"]) for summary in active_run_summaries),
        "advisory_failure_count": sum(
            int(summary["advisory_failure_count"]) for summary in active_run_summaries
        ),
        "direct_commands": [command for command in direct_commands if command],
        "selected_commands": selected_commands,
        "all_commands": [command for command in [*direct_commands, *selected_commands] if command],
        "failed_commands": [command for command in failed_commands if command],
        "runs": run_summaries,
    }


def _recompute_smoke_run_status(run: dict[str, Any]) -> None:
    results = [
        item for item in run.get("selected_checks", [])
        if isinstance(item, dict) and item.get("status")
    ]
    failures = [item for item in results if not item.get("ok")]
    run["failures"] = failures
    run["failure_count"] = len(failures)
    run["advisory_failure_count"] = len(
        [
            item for item in results
            if item.get("status") == "advisory_inherited_failure"
        ]
    )
    run["ok"] = not failures and not run.get("warning_count")


def downgrade_inherited_baseline_failures(
    run: dict[str, Any] | None,
    *,
    changed_files: list[str],
) -> dict[str, Any] | None:
    """Downgrade known repo-baseline failures when they do not mention changed files."""

    if not isinstance(run, dict):
        return run
    changed = {_norm_path(path) for path in changed_files if _norm_path(path)}
    changed_mentions = {path for path in changed}
    for path in list(changed):
        basename = Path(path).name
        if Path(path).suffix:
            changed_mentions.add(basename)

    changed_any = False
    for check in run.get("selected_checks", []):
        if not isinstance(check, dict) or check.get("ok"):
            continue
        command = str(check.get("command") or "")
        if not any(token in command for token in INHERITED_BASELINE_COMMANDS):
            continue
        evidence = "\n".join(
            str(check.get(key) or "")
            for key in ("stdout_tail", "stderr_tail")
        )
        if any(needle and needle in evidence for needle in changed_mentions):
            continue
        check.update(
            {
                "ok": True,
                "status": "advisory_inherited_failure",
                "inherited_baseline_failure": True,
                "advisory_reason": (
                    "known baseline smoke failure did not mention changed files; "
                    "record it in the PR comment but do not block this diff"
                ),
            }
        )
        changed_any = True
    if changed_any:
        _recompute_smoke_run_status(run)
    return run


def _tier_limits(tier: str) -> dict[str, int | bool]:
    normalized = tier if tier in PREMERGE_TIERS else "standard"
    if normalized == "quick":
        return {"catalog_limit": 3, "profile_limit": 0, "deep": False}
    if normalized == "deep":
        return {"catalog_limit": 0, "profile_limit": 0, "deep": True}
    return {"catalog_limit": 8, "profile_limit": 8, "deep": False}


def build_premerge_validation_gate(
    *,
    changed_files: list[str] | None = None,
    base_ref: str = "origin/main",
    tier: str = "standard",
    execute: bool = True,
    timeout_seconds: float = 120.0,
    fail_fast: bool = False,
    include_deep_checks: bool | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    files = _dedupe(list(changed_files or []))
    classification = classify_premerge_surfaces(files)
    limits = _tier_limits(tier)
    include_deep = bool(limits["deep"] if include_deep_checks is None else include_deep_checks)
    if progress_callback and execute:
        progress_callback(
            {
                "schema_version": "canary_premerge_progress_v0",
                "event": "premerge_started",
                "tier": tier if tier in PREMERGE_TIERS else "standard",
                "changed_file_count": len(files),
                "surfaces": list(classification["surfaces"]),
                "risk_profiles": list(classification["risk_profiles"]),
            }
        )

    direct_checks = _diff_hygiene_checks(
        base_ref=base_ref,
        execute=execute,
        timeout_seconds=timeout_seconds,
        progress_callback=progress_callback,
    )
    py_compile = _py_compile_check(
        python_files=list(classification["python_files"]),
        execute=execute,
        timeout_seconds=timeout_seconds,
        progress_callback=progress_callback,
    )
    if py_compile is not None:
        direct_checks.append(py_compile)

    catalog_progress = _section_progress_callback(
        progress_callback,
        section="catalog_canaries",
    )
    _emit_section_progress(
        catalog_progress,
        event="section_started",
        selected_hint=int(limits["catalog_limit"]),
    )
    catalog_run = build_canary_smoke_suite_run(
        suite="catalog-plan",
        changed_files=files,
        include_deep_checks=include_deep,
        max_checks_per_family=3,
        max_checks_per_profile=4,
        limit=int(limits["catalog_limit"]),
        execute=execute,
        timeout_seconds=timeout_seconds,
        fail_fast=fail_fast,
        progress_callback=catalog_progress if execute else None,
    )
    _emit_section_progress(
        catalog_progress,
        event="section_finished",
        status="passed" if catalog_run.get("ok") else "failed",
        ok=bool(catalog_run.get("ok")),
        selected_check_count=catalog_run.get("selected_check_count"),
        executed_check_count=catalog_run.get("executed_check_count"),
        failure_count=catalog_run.get("failure_count"),
    )
    catalog_run = downgrade_inherited_baseline_failures(
        catalog_run,
        changed_files=files,
    )

    risk_profiles = list(classification["risk_profiles"])
    risk_profile_run: dict[str, Any] | None = None
    if risk_profiles:
        risk_progress = _section_progress_callback(
            progress_callback,
            section="risk_profile_smokes",
        )
        _emit_section_progress(
            risk_progress,
            event="section_started",
            profiles=risk_profiles,
            selected_hint=int(limits["profile_limit"]),
        )
        risk_profile_run = build_canary_smoke_suite_run(
            suite="default-public",
            profiles=risk_profiles,
            include_deep_checks=include_deep,
            limit=int(limits["profile_limit"]),
            execute=execute,
            timeout_seconds=timeout_seconds,
            fail_fast=fail_fast,
            progress_callback=risk_progress if execute else None,
        )
        _emit_section_progress(
            risk_progress,
            event="section_finished",
            status="passed" if risk_profile_run.get("ok") else "failed",
            ok=bool(risk_profile_run.get("ok")),
            selected_check_count=risk_profile_run.get("selected_check_count"),
            executed_check_count=risk_profile_run.get("executed_check_count"),
            failure_count=risk_profile_run.get("failure_count"),
        )
        risk_profile_run = downgrade_inherited_baseline_failures(
            risk_profile_run,
            changed_files=files,
        )

    boundary_run: dict[str, Any] | None = None
    if classification["public_boundary_scan_recommended"]:
        boundary_progress = _section_progress_callback(
            progress_callback,
            section="public_boundary",
        )
        _emit_section_progress(boundary_progress, event="section_started", selected_hint=1)
        boundary_run = build_canary_smoke_suite_run(
            suite="default-public",
            scripts=["examples/control_plane/check-public-boundary-smoke.py"],
            execute=execute,
            timeout_seconds=timeout_seconds,
            fail_fast=fail_fast,
            progress_callback=boundary_progress if execute else None,
        )
        _emit_section_progress(
            boundary_progress,
            event="section_finished",
            status="passed" if boundary_run.get("ok") else "failed",
            ok=bool(boundary_run.get("ok")),
            selected_check_count=boundary_run.get("selected_check_count"),
            executed_check_count=boundary_run.get("executed_check_count"),
            failure_count=boundary_run.get("failure_count"),
        )
        boundary_run = downgrade_inherited_baseline_failures(
            boundary_run,
            changed_files=files,
        )

    gate = _gate_status(
        execute=execute,
        changed_files=files,
        direct_checks=direct_checks,
        catalog_run=catalog_run,
        risk_profile_run=risk_profile_run,
        boundary_run=boundary_run,
        manual_holds=list(classification["manual_holds"]),
    )
    validation_summary = build_validation_summary(
        direct_checks=direct_checks,
        catalog_run=catalog_run,
        risk_profile_run=risk_profile_run,
        boundary_run=boundary_run,
    )
    ok = gate["status"] in {"passed", "no_changes"} or (
        not execute and gate["status"] in {"preview_only", "manual_review_required", "no_changes"}
    )
    payload = {
        "ok": ok,
        "schema_version": PREMERGE_GATE_SCHEMA_VERSION,
        "repo_root": str(REPO_ROOT),
        "base_ref": (base_ref or "origin/main").strip() or "origin/main",
        "tier": tier if tier in PREMERGE_TIERS else "standard",
        "dry_run": not execute,
        "executes_checks": execute,
        "writes_evidence": False,
        "creates_runtime_contract": False,
        "changed_files": files,
        "classification": classification,
        "direct_checks": direct_checks,
        "catalog_run": catalog_run,
        "risk_profile_run": risk_profile_run,
        "boundary_run": boundary_run,
        "validation_summary": validation_summary,
        "gate": gate,
        "recommended_pr_comment_fields": [
            "changed_surfaces",
            "direct_checks",
            "catalog_canaries",
            "risk_profile_smokes",
            "public_private_boundary",
            "failures_or_skips",
            "manual_holds",
            "merge_decision",
        ],
        "note": (
            "Pre-merge validation is a risk-based gate: it runs diff hygiene, "
            "changed Python compile checks, catalog-selected canaries, risk-profile "
            "smokes, and public/private boundary checks. It reports manual holds for "
            "benchmark-sensitive or reviewer-gated surfaces instead of treating local "
            "smoke success as self-merge permission."
        ),
    }
    if progress_callback and execute:
        progress_callback(
            {
                "schema_version": "canary_premerge_progress_v0",
                "event": "premerge_finished",
                "status": gate["status"],
                "ok": ok,
                "selected_check_count": validation_summary["selected_check_count"],
                "failure_count": validation_summary["failure_count"],
                "manual_hold_count": gate["manual_hold_count"],
            }
        )
    return payload


def _section_progress_callback(
    progress_callback: ProgressCallback | None,
    *,
    section: str,
) -> ProgressCallback | None:
    if progress_callback is None:
        return None

    def callback(event: dict[str, Any]) -> None:
        updated = dict(event)
        updated.setdefault("schema_version", "canary_premerge_progress_v0")
        updated["section"] = section
        progress_callback(updated)

    return callback


def _emit_section_progress(
    progress_callback: ProgressCallback | None,
    *,
    event: str,
    **fields: Any,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "schema_version": "canary_premerge_progress_v0",
            "event": event,
            **fields,
        }
    )


def render_premerge_validation_gate_markdown(payload: dict[str, Any]) -> str:
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    classification = (
        payload.get("classification")
        if isinstance(payload.get("classification"), dict)
        else {}
    )
    lines = [
        "# Pre-Merge Validation Gate",
        "",
        f"- status: `{gate.get('status')}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- merge_gate_passed: `{str(gate.get('merge_gate_passed')).lower()}`",
        f"- self_merge_allowed: `{str(gate.get('self_merge_allowed')).lower()}`",
        f"- tier: `{payload.get('tier')}`",
        f"- dry_run: `{str(payload.get('dry_run')).lower()}`",
        f"- changed_files: `{classification.get('changed_file_count')}`",
        f"- surfaces: `{', '.join(classification.get('surfaces') or [])}`",
        f"- risk_profiles: `{', '.join(classification.get('risk_profiles') or [])}`",
        f"- manual_holds: `{gate.get('manual_hold_count')}`",
        "",
        str(payload.get("note") or ""),
        "",
        "## Direct Checks",
    ]
    for check in payload.get("direct_checks", []):
        if not isinstance(check, dict):
            continue
        lines.extend(
            [
                f"- `{check.get('id')}`: `{check.get('status')}` "
                f"`{check.get('command')}`",
            ]
        )
        if check.get("stderr_tail"):
            lines.append(f"  stderr_tail: `{str(check.get('stderr_tail')).strip()[-240:]}`")

    def append_run(title: str, run: Any) -> None:
        if not isinstance(run, dict):
            return
        lines.extend(
            [
                "",
                f"## {title}",
                f"- ok: `{str(run.get('ok')).lower()}`",
                f"- selected_checks: `{run.get('selected_check_count')}`",
                f"- executed_checks: `{run.get('executed_check_count')}`",
                f"- failures: `{run.get('failure_count')}`",
                f"- advisory_failures: `{run.get('advisory_failure_count') or 0}`",
                f"- warnings: `{run.get('warning_count')}`",
            ]
        )
        for check in run.get("selected_checks", [])[:12]:
            if not isinstance(check, dict):
                continue
            normalized = (
                check.get("normalized")
                if isinstance(check.get("normalized"), dict)
                else {}
            )
            command = " ".join(str(part) for part in normalized.get("display_argv") or [])
            lines.append(f"- `{check.get('status') or 'ready'}` {command or check.get('command')}")
            if check.get("advisory_reason"):
                lines.append(f"  advisory_reason: {check.get('advisory_reason')}")

    append_run("Catalog Canaries", payload.get("catalog_run"))
    append_run("Risk Profile Smokes", payload.get("risk_profile_run"))
    append_run("Public Boundary", payload.get("boundary_run"))

    manual_holds = classification.get("manual_holds") or []
    if manual_holds:
        lines.extend(["", "## Manual Holds"])
        for hold in manual_holds:
            if isinstance(hold, dict):
                lines.append(f"- `{hold.get('kind')}`: {hold.get('reason')}")
    return "\n".join(lines).rstrip() + "\n"
