from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .bootstrap import default_goal_id


DEFAULT_CODEX_BIN = "codex"
DEFAULT_TIMEOUT_SECONDS = 2.0


HELP_COMMANDS = {
    "root": ("--help",),
    "exec": ("exec", "--help"),
    "resume": ("resume", "--help"),
}


def _normalize(text: str | None) -> str:
    return " ".join((text or "").lower().replace("_", "-").split())


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _visible_session_injection_detected(text: str) -> bool:
    has_session = _has_any(
        text,
        (
            "session",
            "conversation",
            "thread",
            "--session",
            "--conversation",
            "session-id",
            "session id",
        ),
    )
    has_attach = _has_any(
        text,
        (
            "attach to existing tui",
            "attach to active tui",
            "attach to an idle tui",
            "attach to existing session",
            "attach to active session",
            "inject into session",
            "inject into active session",
            "inject prompt into session",
            "send prompt to session",
            "send message to session",
            "send-message",
            "send message",
        ),
    )
    has_visible_turn = _has_any(text, ("prompt", "message", "stdin", "turn", "tui", "visible"))
    return has_session and has_attach and has_visible_turn


def _remote_control_surface_detected(text: str) -> bool:
    return _has_any(text, ("remote-control", "remote control")) and _has_any(
        text,
        ("--remote", "app server", "app-server"),
    )


def _visible_resume_supported(resume_help: str) -> bool:
    return "usage: codex resume" in resume_help and "[prompt]" in resume_help


def classify_codex_cli_session_surface(
    *,
    command_outputs: Mapping[str, str],
    command_errors: Mapping[str, str] | None = None,
    codex_cli_available: bool = True,
) -> dict[str, Any]:
    """Classify public Codex CLI help text without reading local sessions."""

    command_errors = command_errors or {}
    normalized_outputs = {name: _normalize(text) for name, text in command_outputs.items()}
    all_help = " ".join(normalized_outputs.values())
    root_help = normalized_outputs.get("root", "")
    exec_help = normalized_outputs.get("exec", "")
    resume_help = normalized_outputs.get("resume", "")

    exec_supported = " exec" in f" {root_help} " or bool(exec_help.strip())
    resume_supported = " resume" in f" {root_help} " or bool(resume_help.strip())
    session_handle_detected = resume_supported or _has_any(
        all_help,
        (
            "--session",
            "--conversation",
            "session-id",
            "session id",
            "conversation id",
            "resume",
        ),
    )
    same_tui_injection_detected = _visible_session_injection_detected(all_help)
    remote_control_surface_detected = _remote_control_surface_detected(all_help)
    visible_resume_supported = _visible_resume_supported(resume_help)
    safe_injection_supported = same_tui_injection_detected

    if safe_injection_supported:
        recommended_mode = "session_attached_visible_turn"
        automation_action = "try_visible_session_attach_with_idle_guard"
    elif remote_control_surface_detected or visible_resume_supported:
        recommended_mode = "visible_resume_or_remote_control_spike"
        automation_action = "prototype_visible_resume_or_remote_control_with_idle_guard"
    elif exec_supported:
        recommended_mode = "tui_bootstrap_then_explicit_headless_fallback"
        automation_action = "keep_tui_bootstrap_primary_and_require_explicit_fallback"
    else:
        recommended_mode = "tui_bootstrap_only"
        automation_action = "ask_user_to_start_inside_codex_cli_tui"

    warnings: list[str] = []
    if session_handle_detected and not same_tui_injection_detected:
        warnings.append(
            "Resume/session help is not enough to claim same-open-TUI injection; require an explicit visible attach/inject primitive."
        )
    if (remote_control_surface_detected or visible_resume_supported) and not same_tui_injection_detected:
        warnings.append(
            "A visible resume or remote-control surface exists; prototype it behind an idle guard before calling it session-attached automation."
        )
    if not codex_cli_available:
        warnings.append("Codex CLI was not available on PATH; classification used missing-command evidence.")
    if command_errors:
        warnings.append("Some probe commands returned errors; inspect command_errors before enabling automation.")

    return {
        "ok": True,
        "schema_version": "codex_cli_session_probe_v0",
        "codex_cli_available": codex_cli_available,
        "capabilities": {
            "exec_supported": exec_supported,
            "resume_supported": resume_supported,
            "session_handle_detected": session_handle_detected,
            "visible_resume_supported": visible_resume_supported,
            "remote_control_surface_detected": remote_control_surface_detected,
            "same_tui_injection_detected": same_tui_injection_detected,
            "safe_injection_supported": safe_injection_supported,
        },
        "recommended_mode": recommended_mode,
        "automation_action": automation_action,
        "boundary": {
            "help_only_probe": True,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_goal_harness_quota": False,
        },
        "command_errors": dict(command_errors),
        "warnings": warnings,
    }


def load_codex_cli_probe_fixture(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text())
    if "command_outputs" in data:
        outputs = data["command_outputs"]
    else:
        outputs = data
    if not isinstance(outputs, dict):
        raise ValueError("Codex CLI probe fixture must be a JSON object")
    return {str(key): str(value) for key, value in outputs.items()}


def run_codex_cli_session_probe(
    *,
    codex_bin: str = DEFAULT_CODEX_BIN,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fixture: Path | None = None,
) -> dict[str, Any]:
    if fixture:
        outputs = load_codex_cli_probe_fixture(fixture)
        payload = classify_codex_cli_session_surface(
            command_outputs=outputs,
            codex_cli_available=True,
        )
        payload["source"] = "fixture"
        return payload

    outputs: dict[str, str] = {}
    errors: dict[str, str] = {}
    available = True
    for name, extra_args in HELP_COMMANDS.items():
        try:
            result = subprocess.run(
                [codex_bin, *extra_args],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError:
            available = False
            errors[name] = "codex_cli_not_found"
            break
        except subprocess.TimeoutExpired:
            errors[name] = "timeout"
            continue
        text = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if result.returncode != 0:
            errors[name] = f"exit_{result.returncode}"
        outputs[name] = text

    payload = classify_codex_cli_session_surface(
        command_outputs=outputs,
        command_errors=errors,
        codex_cli_available=available,
    )
    payload["source"] = "real_help"
    payload["codex_bin"] = codex_bin
    payload["timeout_seconds"] = timeout_seconds
    return payload


def _shell_arg(value: str) -> str:
    return shlex.quote(value)


def build_codex_cli_visible_driver_plan(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a public-safe plan for a visible Codex CLI automation driver.

    The plan is intentionally read-only. It decides whether a future local
    driver should attempt a visible session attachment, run a resume/remote
    control spike, or fall back explicitly to headless `codex exec`.
    """

    resolved_project = str(project.expanduser())
    resolved_goal_id = goal_id or default_goal_id(project)
    capabilities = probe_payload.get("capabilities") if isinstance(probe_payload.get("capabilities"), dict) else {}
    safe_injection_supported = bool(capabilities.get("safe_injection_supported"))
    visible_resume_supported = bool(capabilities.get("visible_resume_supported"))
    remote_control_supported = bool(capabilities.get("remote_control_surface_detected"))
    exec_supported = bool(capabilities.get("exec_supported"))
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    quota_guard_command = (
        f"{_shell_arg(cli_bin)} --format json quota should-run "
        f"--goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
    )
    bootstrap_command = (
        f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
    )
    exec_fallback_command = (
        f"{_shell_arg(cli_bin)} codex-cli-exec-handoff "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg} "
        f"--codex-bin {_shell_arg(codex_bin)}"
    )
    probe_command = f"{_shell_arg(cli_bin)} codex-cli-session-probe --codex-bin {_shell_arg(codex_bin)}"

    if safe_injection_supported:
        driver_mode = "session_attached_visible_turn"
        automation_action = "try_visible_session_attach_with_idle_guard"
        next_step = "wire the detected visible attach primitive behind idle guard and quota guard"
    elif visible_resume_supported or remote_control_supported:
        driver_mode = "visible_resume_or_remote_control_spike"
        automation_action = "prototype_visible_resume_or_remote_control_with_idle_guard"
        next_step = "run an explicit proof that resume or remote-control creates a visible interruptible turn"
    elif exec_supported:
        driver_mode = "explicit_headless_fallback_after_tui_bootstrap"
        automation_action = "keep_tui_bootstrap_primary_and_require_explicit_fallback"
        next_step = "keep one-message TUI bootstrap primary; use codex exec only as explicit fallback"
    else:
        driver_mode = "tui_bootstrap_only"
        automation_action = "ask_user_to_start_inside_codex_cli_tui"
        next_step = "ask the user to start in Codex CLI TUI and paste the bootstrap message"

    driver_steps = [
        "run the session probe and quota guard before any delivery turn",
        "if user_channel.action_required=true, surface only the concrete user gate",
        "if delivery is allowed, verify idle_guard before any visible prompt",
        "prefer a visible same-TUI turn; otherwise use the explicit headless fallback command",
        "write back compact evidence and spend quota only after validation",
    ]
    if driver_mode == "visible_resume_or_remote_control_spike":
        driver_steps.insert(
            3,
            "treat resume [PROMPT] or remote-control as unproven until a visible interruptible turn is observed",
        )
    if driver_mode == "session_attached_visible_turn":
        driver_steps.insert(3, "use only the detected visible attach primitive; do not write hidden session state")

    return {
        "ok": True,
        "schema_version": "codex_cli_visible_driver_plan_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "probe_source": probe_payload.get("source"),
        "probe_recommended_mode": probe_payload.get("recommended_mode"),
        "driver_mode": driver_mode,
        "automation_action": automation_action,
        "next_step": next_step,
        "capabilities": capabilities,
        "commands": {
            "probe": probe_command,
            "quota_guard": quota_guard_command,
            "tui_bootstrap_message": bootstrap_command,
            "explicit_headless_fallback": exec_fallback_command,
        },
        "driver_steps": driver_steps,
        "boundary": {
            "dry_run_plan_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_goal_harness_quota": False,
            "requires_idle_guard_before_visible_prompt": True,
            "requires_user_gate_stop": True,
        },
        "warnings": list(probe_payload.get("warnings") or []),
    }


def render_codex_cli_session_probe_markdown(payload: dict[str, Any]) -> str:
    capabilities = payload.get("capabilities") or {}
    boundary = payload.get("boundary") or {}
    warnings = payload.get("warnings") or []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Session Probe

- source: `{payload.get("source")}`
- recommended_mode: `{payload.get("recommended_mode")}`
- automation_action: `{payload.get("automation_action")}`

## Capabilities

- exec_supported: `{capabilities.get("exec_supported")}`
- resume_supported: `{capabilities.get("resume_supported")}`
- session_handle_detected: `{capabilities.get("session_handle_detected")}`
- visible_resume_supported: `{capabilities.get("visible_resume_supported")}`
- remote_control_surface_detected: `{capabilities.get("remote_control_surface_detected")}`
- same_tui_injection_detected: `{capabilities.get("same_tui_injection_detected")}`
- safe_injection_supported: `{capabilities.get("safe_injection_supported")}`

## Boundary

- help_only_probe: `{boundary.get("help_only_probe")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_credentials: `{boundary.get("reads_credentials")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_goal_harness_quota: `{boundary.get("spends_goal_harness_quota")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_visible_driver_plan_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    steps = payload.get("driver_steps") if isinstance(payload.get("driver_steps"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Visible Driver Plan

- driver_mode: `{payload.get("driver_mode")}`
- automation_action: `{payload.get("automation_action")}`
- probe_recommended_mode: `{payload.get("probe_recommended_mode")}`
- next_step: {payload.get("next_step")}

## Commands

```bash
{commands.get("probe")}
{commands.get("quota_guard")}
{commands.get("tui_bootstrap_message")}
{commands.get("explicit_headless_fallback")}
```

## Driver Steps

{step_lines}

## Boundary

- dry_run_plan_only: `{boundary.get("dry_run_plan_only")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_goal_harness_quota: `{boundary.get("spends_goal_harness_quota")}`
- requires_idle_guard_before_visible_prompt: `{boundary.get("requires_idle_guard_before_visible_prompt")}`
- requires_user_gate_stop: `{boundary.get("requires_user_gate_stop")}`

## Warnings

{warning_lines}
"""
