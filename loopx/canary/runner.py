from __future__ import annotations

import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .planner import REPO_ROOT, build_catalog_canary_plan


CANARY_RUN_SCHEMA_VERSION = "catalog_canary_run_v0"
NO_WRITE_ARGS_BY_SCRIPT = {
    "canary-promotion-readiness-smoke.py": ["--no-write-evidence"],
}
PYTHON_BINARIES = {"python", "python3"}
NODE_BINARIES = {"node"}
SHELL_TOKENS = {"&&", "||", ";", "|", ">", "<", ">>", "2>", "2>>"}


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


def _planned_checks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for profile in plan.get("domain_profiles", []):
        if not isinstance(profile, dict):
            continue
        for check in profile.get("checks", []):
            if not isinstance(check, dict):
                continue
            command = str(check.get("command") or "")
            if not command or command in seen:
                continue
            seen.add(command)
            checks.append(
                {
                    "source": "domain_profile",
                    "profile_id": profile.get("id"),
                    "profile_title": profile.get("title"),
                    "tier": check.get("tier") or "default",
                    **check,
                }
            )
    for profile in plan.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        for check in profile.get("candidate_checks", []):
            if not isinstance(check, dict):
                continue
            command = str(check.get("command") or "")
            if not command or command in seen:
                continue
            seen.add(command)
            checks.append(
                {
                    "source": "catalog_family",
                    "profile_id": profile.get("id"),
                    "profile_title": profile.get("family"),
                    "tier": check.get("tier") or "default",
                    **check,
                }
            )
    return checks


def _run_check(check: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    normalized = normalize_canary_command(str(check.get("command") or ""))
    result = {**check, "normalized": normalized}
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
    planned = _planned_checks(plan)
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
