from __future__ import annotations

import shlex
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .planner import REPO_ROOT, build_catalog_canary_plan, flatten_catalog_canary_checks


CANARY_RUN_SCHEMA_VERSION = "catalog_canary_run_v0"
CANARY_SMOKE_SUITE_RUN_SCHEMA_VERSION = "canary_smoke_suite_run_v0"
NO_WRITE_ARGS_BY_SCRIPT = {
    "canary-promotion-readiness-smoke.py": ["--no-write-evidence"],
    "dashboard-demo-readiness-smoke.py": ["--skip-browser"],
}
EXPLICIT_GROUPED_SMOKES = {
    "canary-promotion-readiness-smoke.py",
    "dashboard-demo-readiness-smoke.py",
}
PYTHON_BINARIES = {"python", "python3"}
NODE_BINARIES = {"node"}
SHELL_TOKENS = {"&&", "||", ";", "|", ">", "<", ">>", "2>", "2>>"}
SMOKE_SUITE_CHOICES = {"default-public", "full-public", "catalog-plan"}
ProgressCallback = Callable[[dict[str, Any]], None]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def normalize_canary_command(command: str) -> dict[str, Any]:
    """Parse a planner command into a shell-free, repository-local argv."""

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return {
            "ok": False,
            "command": command,
            "reason": f"could not parse command: {exc}",
            "argv": [],
        }
    if len(parts) < 2:
        return {
            "ok": False,
            "command": command,
            "reason": "command must include an interpreter and examples script",
            "argv": [],
        }
    if any("\n" in part or part in SHELL_TOKENS for part in parts):
        return {
            "ok": False,
            "command": command,
            "reason": "shell control tokens are not allowed in canary commands",
            "argv": [],
        }

    interpreter = parts[0]
    script = (REPO_ROOT / parts[1]).resolve()
    examples_root = (REPO_ROOT / "examples").resolve()
    if not _is_relative_to(script, examples_root):
        return {
            "ok": False,
            "command": command,
            "reason": "canary runner only executes repository-local examples",
            "argv": [],
        }
    if interpreter in PYTHON_BINARIES and script.suffix == ".py":
        argv = [sys.executable, str(script), *parts[2:]]
    elif interpreter in NODE_BINARIES and script.suffix == ".mjs":
        argv = [interpreter, str(script), *parts[2:]]
    else:
        return {
            "ok": False,
            "command": command,
            "reason": "only python examples/*.py and node examples/*.mjs commands are allowed",
            "argv": [],
        }

    injected_args = [
        arg
        for arg in NO_WRITE_ARGS_BY_SCRIPT.get(script.name, [])
        if arg not in argv
    ]
    if injected_args:
        argv.extend(injected_args)
    return {
        "ok": True,
        "command": command,
        "argv": argv,
        "display_argv": _display_argv(argv),
        "injected_args": injected_args,
        "script": str(script.relative_to(REPO_ROOT)),
    }


def _display_argv(argv: list[str]) -> list[str]:
    displayed = list(argv)
    if displayed and Path(displayed[0]).resolve() == Path(sys.executable).resolve():
        displayed[0] = "python3"
    for index, value in enumerate(displayed[1:], start=1):
        path = Path(value)
        if path.is_absolute() and _is_relative_to(path.resolve(), REPO_ROOT.resolve()):
            displayed[index] = str(path.resolve().relative_to(REPO_ROOT.resolve()))
    return displayed


def _tracked_change_paths() -> tuple[bool, list[str], str]:
    worktree_probe = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--is-inside-work-tree"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if worktree_probe.returncode != 0 or worktree_probe.stdout.strip() != "true":
        detail = (
            worktree_probe.stderr
            or worktree_probe.stdout
            or "repository root is not a git worktree"
        ).strip()
        return False, [], f"not_a_git_worktree: {detail[-400:]}"

    paths: set[str] = set()
    stderr_parts: list[str] = []
    ok = True
    for args in (["diff", "--name-only"], ["diff", "--name-only", "--cached"]):
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            ok = False
            stderr_parts.append(f"git_diff_failed: {completed.stderr[-400:]}")
            continue
        paths.update(line.strip() for line in completed.stdout.splitlines() if line.strip())
    return ok, sorted(paths), "\n".join(part for part in stderr_parts if part)


def _restore_tracked_paths(paths: list[str]) -> dict[str, Any]:
    if not paths:
        return {"ok": True, "restored_paths": []}
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "restore", "--staged", "--worktree", "--", *paths],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "restored_paths": paths if completed.returncode == 0 else [],
        "stderr_tail": completed.stderr[-800:],
    }


def _run_check(
    check: dict[str, Any],
    *,
    timeout_seconds: float,
    check_index: int | None = None,
    check_count: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_canary_command(str(check.get("command") or ""))
    result = {**check, "normalized": normalized}
    if check_index is not None and check_count is not None:
        result.update({"check_index": check_index, "check_count": check_count})
    if not normalized.get("ok"):
        result.update({"status": "skipped", "ok": False, "reason": normalized.get("reason")})
        return result

    started = time.monotonic()
    try:
        completed = subprocess.run(
            normalized["argv"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result.update(
            {
                "status": "timed_out",
                "ok": False,
                "returncode": None,
                "duration_seconds": round(time.monotonic() - started, 3),
                "stdout_tail": (exc.stdout or "")[-800:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-800:] if isinstance(exc.stderr, str) else "",
            }
        )
        return result

    result.update(
        {
            "status": "passed" if completed.returncode == 0 else "failed",
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_tail": completed.stdout[-800:],
            "stderr_tail": completed.stderr[-800:],
        }
    )
    return result


def run_canary_smoke_check(
    check: dict[str, Any],
    *,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    """Execute one normalized canary smoke-suite check through the runner contract."""

    return _run_check(check, timeout_seconds=max(1.0, timeout_seconds))


def _smoke_script_relative(script: Path) -> str:
    return script.relative_to(REPO_ROOT).as_posix()


def _smoke_script_filter_keys(script: Path) -> set[str]:
    examples_root = REPO_ROOT / "examples"
    return {
        script.name,
        _smoke_script_relative(script),
        script.relative_to(examples_root).as_posix(),
    }


def _smoke_script_check(script: Path, *, source: str = "suite") -> dict[str, Any]:
    return {
        "source": source,
        "profile_id": "smoke-suite",
        "profile_title": "Smoke suite",
        "tier": "default",
        "command": f"python3 {_smoke_script_relative(script)}",
        "reason": "tracked public smoke script",
    }


def _normalize_script_filter(script: str) -> str:
    value = script.strip().replace("\\", "/")
    if not value:
        return ""
    path = Path(value)
    if path.parts and path.parts[0] == "examples":
        if path.suffix and len(path.parts) == 2:
            return path.name
        return path.as_posix()
    if path.suffix and len(path.parts) > 1:
        return path.as_posix()
    return path.name if path.suffix else value


def _matches_modules(script: Path, modules: list[str]) -> bool:
    if not modules:
        return True
    examples_relative = script.relative_to(REPO_ROOT / "examples").as_posix().lower()
    haystack = f"{script.name.lower()} {examples_relative}"
    stem_tokens = {
        token for token in re.split(r"[-_./]+", examples_relative.removesuffix(script.suffix)) if token
    }
    for module in modules:
        needle = module.strip().lower()
        if not needle:
            continue
        needle_variants = {
            needle,
            needle.replace("-", "_"),
            needle.replace("_", "-"),
        }
        needle_tokens = {
            token for token in re.split(r"[-_./]+", needle) if token
        }
        if (
            any(variant in haystack or variant in stem_tokens for variant in needle_variants)
            or (needle_tokens and needle_tokens.issubset(stem_tokens))
        ):
            return True
    return False


def _discover_smoke_suite_checks(
    *,
    suite: str,
    modules: list[str] | None = None,
    scripts: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_suite = suite if suite in SMOKE_SUITE_CHOICES else "default-public"
    modules = list(modules or [])
    requested_scripts = {
        script for script in (_normalize_script_filter(item) for item in (scripts or [])) if script
    }
    all_scripts = sorted(path for path in (REPO_ROOT / "examples").rglob("*-smoke.py") if path.is_file())
    if normalized_suite == "default-public":
        all_scripts = [
            script for script in all_scripts
            if script.name not in EXPLICIT_GROUPED_SMOKES
        ]
    selected: list[Path] = []
    missing_scripts = set(requested_scripts)
    for script in all_scripts:
        script_filter_keys = _smoke_script_filter_keys(script)
        if requested_scripts and requested_scripts.isdisjoint(script_filter_keys):
            continue
        if not _matches_modules(script, modules):
            continue
        selected.append(script)
        missing_scripts.difference_update(script_filter_keys)
    warnings = [
        {
            "kind": "unknown_script",
            "script": script,
            "message": "requested script was not found in selected smoke suite",
        }
        for script in sorted(missing_scripts)
    ]
    return [_smoke_script_check(script) for script in selected], warnings


def _dedupe_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for check in checks:
        command = str(check.get("command") or "")
        if not command or command in seen:
            continue
        seen.add(command)
        deduped.append(check)
    return deduped


def build_canary_smoke_suite_run(
    *,
    suite: str = "default-public",
    modules: list[str] | None = None,
    scripts: list[str] | None = None,
    catalog_path: Path | None = None,
    changed_files: list[str] | None = None,
    surfaces: list[str] | None = None,
    families: list[str] | None = None,
    profiles: list[str] | None = None,
    include_deep_checks: bool = False,
    max_checks_per_family: int = 3,
    max_checks_per_profile: int = 3,
    limit: int = 0,
    execute: bool = True,
    timeout_seconds: float = 120.0,
    fail_fast: bool = False,
    allow_tracked_side_effects: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Build and optionally execute a continue-on-failure smoke suite.

    This runner is intentionally bounded to repository-local `examples/**/*-smoke.py`
    commands plus catalog-plan checks. It gives maintainers a full regression
    sweep without hiding the smaller profile/module loops used while developing.
    """

    normalized_suite = suite if suite in SMOKE_SUITE_CHOICES else "default-public"
    modules = list(modules or [])
    scripts = list(scripts or [])
    families = list(families or [])
    profiles = list(profiles or [])
    changed_files = list(changed_files or [])
    surfaces = list(surfaces or [])
    catalog_selector_requested = bool(families or profiles or changed_files or surfaces)
    suite_requested = normalized_suite != "catalog-plan"
    if catalog_selector_requested and not modules and not scripts and normalized_suite == "default-public":
        suite_requested = False

    selected: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    plan: dict[str, Any] | None = None
    if suite_requested:
        suite_checks, suite_warnings = _discover_smoke_suite_checks(
            suite=normalized_suite,
            modules=modules,
            scripts=scripts,
        )
        selected.extend(suite_checks)
        warnings.extend(suite_warnings)
    if catalog_selector_requested or normalized_suite == "catalog-plan":
        plan = build_catalog_canary_plan(
            catalog_path=catalog_path,
            changed_files=changed_files,
            surfaces=surfaces,
            families=families,
            profiles=profiles,
            include_deep_checks=include_deep_checks,
            max_checks_per_family=max_checks_per_family,
            max_checks_per_profile=max_checks_per_profile,
        )
        selected.extend(flatten_catalog_canary_checks(plan))

    selected = _dedupe_checks(selected)
    if limit and limit > 0:
        selected = selected[:limit]
    normalized = [
        {**check, "normalized": normalize_canary_command(str(check.get("command") or ""))}
        for check in selected
    ]

    results: list[dict[str, Any]] = []
    side_effect_guard: dict[str, Any] = {
        "schema_version": "canary_smoke_suite_side_effect_guard_v0",
        "tracked_side_effects_allowed": allow_tracked_side_effects,
        "enforced": False,
        "enforcement_reason": "not_executed",
        "clean_start": None,
        "tracked_before": [],
        "tracked_side_effects": [],
        "auto_restored": False,
    }
    if execute:
        git_ok, tracked_before, git_stderr = _tracked_change_paths()
        clean_start = git_ok and not tracked_before
        if allow_tracked_side_effects:
            enforcement_reason = "tracked_side_effects_explicitly_allowed"
        elif not git_ok:
            enforcement_reason = "git_worktree_unavailable"
        else:
            enforcement_reason = "tracked_side_effect_guard_active"
        side_effect_guard.update(
            {
                "git_status_ok": git_ok,
                "clean_start": clean_start,
                "tracked_before": tracked_before,
                "enforced": bool(git_ok and not allow_tracked_side_effects),
                "enforcement_reason": enforcement_reason,
            }
        )
        if git_stderr:
            side_effect_guard["git_status_unavailable_reason"] = git_stderr[-800:]
        for index, check in enumerate(selected, start=1):
            normalized_check = normalize_canary_command(str(check.get("command") or ""))
            if progress_callback:
                progress_callback(
                    {
                        "schema_version": "canary_smoke_suite_progress_v0",
                        "event": "check_started",
                        "check_index": index,
                        "check_count": len(selected),
                        "command": " ".join(
                            str(part) for part in normalized_check.get("display_argv") or []
                        )
                        or str(check.get("command") or ""),
                    }
                )
            result = _run_check(
                check,
                timeout_seconds=max(1.0, timeout_seconds),
                check_index=index,
                check_count=len(selected),
            )
            if side_effect_guard["enforced"]:
                after_ok, tracked_after, after_stderr = _tracked_change_paths()
                side_effects = sorted(set(tracked_after) - set(tracked_before))
                if side_effects:
                    result.update(
                        {
                            "ok": False,
                            "status": "failed_tracked_side_effect",
                            "tracked_side_effects": side_effects,
                        }
                    )
                    if clean_start:
                        restore = _restore_tracked_paths(side_effects)
                        result["tracked_side_effect_restore"] = restore
                        side_effect_guard["auto_restored"] = (
                            bool(side_effect_guard.get("auto_restored")) or bool(restore.get("ok"))
                        )
                if not after_ok and after_stderr:
                    result["tracked_side_effect_stderr_tail"] = after_stderr[-800:]
            if progress_callback:
                progress_callback(
                    {
                        "schema_version": "canary_smoke_suite_progress_v0",
                        "event": "check_finished",
                        "check_index": index,
                        "check_count": len(selected),
                        "status": result.get("status"),
                        "ok": bool(result.get("ok")),
                        "duration_seconds": result.get("duration_seconds"),
                    }
                )
            results.append(result)
            if fail_fast and not result.get("ok"):
                break
        if side_effect_guard["enforced"]:
            final_ok, tracked_after, final_stderr = _tracked_change_paths()
            side_effects = sorted(set(tracked_after) - set(tracked_before))
            side_effect_guard.update(
                {
                    "git_status_final_ok": final_ok,
                    "tracked_after": tracked_after,
                    "tracked_side_effects": side_effects,
                }
            )
            if final_stderr:
                side_effect_guard["git_status_final_stderr_tail"] = final_stderr[-800:]

    display_items = results if execute else normalized
    failures = [item for item in results if not item.get("ok")]
    timed_out = [item for item in results if item.get("status") == "timed_out"]
    side_effect_failures = [
        item for item in results if item.get("status") == "failed_tracked_side_effect"
    ]
    unsafe = [
        item
        for item in normalized
        if not isinstance(item.get("normalized"), dict) or not item["normalized"].get("ok")
    ]
    ok = not failures and (execute or not unsafe) and not warnings
    return {
        "ok": ok,
        "schema_version": CANARY_SMOKE_SUITE_RUN_SCHEMA_VERSION,
        "suite": normalized_suite,
        "repo_root": str(REPO_ROOT),
        "dry_run": not execute,
        "executes_checks": execute,
        "writes_evidence": bool(allow_tracked_side_effects),
        "creates_runtime_contract": False,
        "timeout_seconds": max(1.0, timeout_seconds),
        "fail_fast": fail_fast,
        "side_effect_guard": side_effect_guard,
        "limit": max(0, limit),
        "selected_check_count": len(selected),
        "executed_check_count": len(results),
        "failure_count": len(failures),
        "timeout_count": len(timed_out),
        "tracked_side_effect_failure_count": len(side_effect_failures),
        "unsafe_command_count": len(unsafe),
        "warning_count": len(warnings),
        "warnings": warnings,
        "selection_inputs": {
            "suite": normalized_suite,
            "modules": modules,
            "scripts": scripts,
            "changed_files": changed_files,
            "surfaces": surfaces,
            "families": families,
            "profiles": profiles,
            "include_deep_checks": include_deep_checks,
            "max_checks_per_family": max_checks_per_family,
            "max_checks_per_profile": max_checks_per_profile,
        },
        "catalog_plan": {
            "schema_version": plan.get("schema_version"),
            "planned_check_count": len(flatten_catalog_canary_checks(plan)),
            "profiles": plan.get("profiles", []),
            "domain_profiles": plan.get("domain_profiles", []),
        } if isinstance(plan, dict) else None,
        "selected_checks": display_items,
        "failures": failures,
        "note": (
            "Smoke-suite run executes repository-local public smoke scripts with "
            "shell-free argv, per-check timeouts, and continue-on-failure reporting. "
            "Use --suite full-public for a full sweep, --module/--script for local "
            "development, or catalog selectors such as --profile for canary-plan modules."
        ),
    }


def build_catalog_canary_run(
    *,
    catalog_path: Path | None = None,
    changed_files: list[str] | None = None,
    surfaces: list[str] | None = None,
    families: list[str] | None = None,
    profiles: list[str] | None = None,
    include_deep_checks: bool = False,
    max_checks_per_family: int = 3,
    max_checks_per_profile: int = 3,
    check_limit: int = 3,
    execute: bool = True,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    plan = build_catalog_canary_plan(
        catalog_path=catalog_path,
        changed_files=changed_files,
        surfaces=surfaces,
        families=families,
        profiles=profiles,
        include_deep_checks=include_deep_checks,
        max_checks_per_family=max_checks_per_family,
        max_checks_per_profile=max_checks_per_profile,
    )
    planned = flatten_catalog_canary_checks(plan)
    selected = planned[: max(0, check_limit)]
    normalized = [
        {**check, "normalized": normalize_canary_command(str(check.get("command") or ""))}
        for check in selected
    ]
    results = []
    if execute:
        results = [
            _run_check(check, timeout_seconds=max(1.0, timeout_seconds))
            for check in selected
        ]

    failures = [item for item in results if not item.get("ok")]
    unsafe = [
        item
        for item in normalized
        if not isinstance(item.get("normalized"), dict) or not item["normalized"].get("ok")
    ]
    ok = not failures and (execute or not unsafe)
    return {
        "ok": ok,
        "schema_version": CANARY_RUN_SCHEMA_VERSION,
        "plan_schema_version": plan.get("schema_version"),
        "source": plan.get("source"),
        "dry_run": not execute,
        "executes_checks": execute,
        "writes_evidence": False,
        "creates_runtime_contract": False,
        "check_limit": max(0, check_limit),
        "timeout_seconds": max(1.0, timeout_seconds),
        "planned_check_count": len(planned),
        "selected_check_count": len(selected),
        "executed_check_count": len(results),
        "failure_count": len(failures),
        "unsafe_command_count": len(unsafe),
        "selection_inputs": plan.get("selection_inputs"),
        "profiles": plan.get("profiles", []),
        "domain_profiles": plan.get("domain_profiles", []),
        "selected_checks": normalized if not execute else results,
        "note": (
            "Canary run consumes the catalog plan and executes only selected "
            "repository-local examples with shell-free argv. It never writes "
            "promotion evidence or creates runtime contracts."
        ),
    }


def render_catalog_canary_run_markdown(payload: dict[str, Any]) -> str:
    mode = "execute" if payload.get("executes_checks") else "preview"
    lines = [
        "# Catalog Canary Run",
        "",
        f"- mode: `{mode}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- source: `{payload.get('source')}`",
        f"- planned_checks: `{payload.get('planned_check_count')}`",
        f"- selected_checks: `{payload.get('selected_check_count')}`",
        f"- executed_checks: `{payload.get('executed_check_count')}`",
        "- writes_evidence: `false`",
        "- creates_runtime_contract: `false`",
        "",
        str(payload.get("note") or ""),
        "",
    ]
    for check in payload.get("selected_checks", []):
        if not isinstance(check, dict):
            continue
        normalized = check.get("normalized") if isinstance(check.get("normalized"), dict) else {}
        command = " ".join(str(part) for part in normalized.get("display_argv") or [])
        status = check.get("status") or ("ready" if normalized.get("ok") else "skipped")
        lines.extend(
            [
                f"## {check.get('profile_title') or check.get('profile_id')}",
                f"- status: `{status}`",
                f"- tier: `{check.get('tier')}`",
                f"- command: `{command or check.get('command')}`",
                f"- reason: {check.get('reason')}",
            ]
        )
        if check.get("injected_args") or normalized.get("injected_args"):
            lines.append(
                "- injected_args: `"
                + ", ".join(str(arg) for arg in normalized.get("injected_args") or check.get("injected_args") or [])
                + "`"
            )
        if check.get("returncode") is not None:
            lines.append(f"- returncode: `{check.get('returncode')}`")
        if check.get("stderr_tail"):
            lines.append(f"- stderr_tail: `{str(check.get('stderr_tail')).strip()[-300:]}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_canary_smoke_suite_run_markdown(payload: dict[str, Any]) -> str:
    mode = "execute" if payload.get("executes_checks") else "preview"
    guard = payload.get("side_effect_guard")
    guard = guard if isinstance(guard, dict) else {}
    lines = [
        "# Canary Smoke Suite",
        "",
        f"- mode: `{mode}`",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- suite: `{payload.get('suite')}`",
        f"- selected_checks: `{payload.get('selected_check_count')}`",
        f"- executed_checks: `{payload.get('executed_check_count')}`",
        f"- failures: `{payload.get('failure_count')}`",
        f"- timeouts: `{payload.get('timeout_count')}`",
        f"- tracked_side_effect_failures: `{payload.get('tracked_side_effect_failure_count')}`",
        f"- warnings: `{payload.get('warning_count')}`",
        f"- writes_evidence: `{str(payload.get('writes_evidence')).lower()}`",
        "- creates_runtime_contract: `false`",
        f"- read_only_guard_enforced: `{str(guard.get('enforced')).lower()}`",
        f"- read_only_guard_reason: `{guard.get('enforcement_reason')}`",
        f"- read_only_guard_clean_start: `{str(guard.get('clean_start')).lower()}`",
        "",
        str(payload.get("note") or ""),
        "",
    ]
    for warning in payload.get("warnings", []):
        if isinstance(warning, dict):
            lines.append(f"- warning: `{warning.get('kind')}` {warning.get('script')}: {warning.get('message')}")
    if payload.get("warnings"):
        lines.append("")
    for check in payload.get("selected_checks", []):
        if not isinstance(check, dict):
            continue
        normalized = check.get("normalized") if isinstance(check.get("normalized"), dict) else {}
        command = " ".join(str(part) for part in normalized.get("display_argv") or [])
        status = check.get("status") or ("ready" if normalized.get("ok") else "skipped")
        title = check.get("profile_title") or check.get("profile_id") or "smoke"
        lines.extend(
            [
                f"## {title}",
                f"- status: `{status}`",
                f"- source: `{check.get('source')}`",
                f"- command: `{command or check.get('command')}`",
            ]
        )
        if normalized.get("injected_args"):
            lines.append(
                "- injected_args: `"
                + ", ".join(str(arg) for arg in normalized.get("injected_args") or [])
                + "`"
            )
        if check.get("returncode") is not None:
            lines.append(f"- returncode: `{check.get('returncode')}`")
        if check.get("duration_seconds") is not None:
            lines.append(f"- duration_seconds: `{check.get('duration_seconds')}`")
        if check.get("tracked_side_effects"):
            lines.append(
                "- tracked_side_effects: `"
                + ", ".join(str(path) for path in check.get("tracked_side_effects") or [])
                + "`"
            )
        restore = check.get("tracked_side_effect_restore")
        if isinstance(restore, dict):
            lines.append(f"- tracked_side_effect_restore_ok: `{str(restore.get('ok')).lower()}`")
        if check.get("stderr_tail"):
            lines.append(f"- stderr_tail: `{str(check.get('stderr_tail')).strip()[-300:]}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
