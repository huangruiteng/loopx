from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable

from .codex_cli_probe import (
    DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
    _shell_arg,
    build_codex_cli_runtime_idle_detector,
    build_codex_cli_visible_driver_run_packet,
)


def _scheduler_label(goal_id: str, agent_id: str | None) -> str:
    raw = f"{goal_id}-{agent_id or 'agent'}"
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    safe = "-".join(part for part in safe.split("-") if part)
    return f"com.loopx.codex-cli.{safe}"


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def build_codex_cli_local_scheduler_tick(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    quota_payload: dict[str, Any] | None = None,
    proof_payload: dict[str, Any] | None = None,
    idle_payload: dict[str, Any] | None = None,
    allow_headless_fallback: bool = False,
) -> dict[str, Any]:
    """Build a local scheduler tick packet without executing Codex.

    This is the first executor-facing spike: a local scheduler can run it as a
    one-shot tick and either receive a candidate external command or a precise
    blocker writeback command. The tick itself does not read Codex session
    files, inspect transcripts, mutate sessions, launch Codex, or spend quota.
    """

    run_packet = build_codex_cli_visible_driver_run_packet(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        allow_headless_fallback=allow_headless_fallback,
    )
    idle_detector = build_codex_cli_runtime_idle_detector(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        idle_payload=idle_payload,
    )
    idle_approved = bool(idle_detector.get("approved_for_visible_later_turn") is True)
    resolved_project = str(run_packet["project"])
    resolved_goal_id = str(run_packet["goal_id"])
    decision = str(run_packet.get("decision") or "tui_bootstrap_only")
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    common_args = (
        f"--project {_shell_arg(resolved_project)} "
        f"--goal-id {_shell_arg(resolved_goal_id)}{agent_arg} "
        f"--codex-bin {_shell_arg(codex_bin)}"
    )
    visible_driver_run_command = (
        f"{_shell_arg(cli_bin)} codex-cli-visible-driver-run {common_args}"
    )
    runtime_idle_detector_command = (
        f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{agent_arg} --observe-local-runtime --observed-surface visible_resume_prompt "
        "--turn-state idle --probe-human-input-idle --checked-before-prompt "
        "--visible-to-user --user-can-interrupt --manual-takeover-available"
    )
    runtime_idle_fixture_command = (
        f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{agent_arg} --idle-fixture <public-runtime-idle.json>"
    )
    scheduler_tick_command = (
        f"{_shell_arg(cli_bin)} codex-cli-local-scheduler-tick {common_args} "
        "--observe-local-runtime --observed-surface visible_resume_prompt "
        "--turn-state idle --probe-human-input-idle --checked-before-prompt "
        "--visible-to-user --user-can-interrupt --manual-takeover-available"
    )
    scheduler_hint = (
        quota_payload.get("scheduler_hint")
        if isinstance(quota_payload, dict)
        and isinstance(quota_payload.get("scheduler_hint"), dict)
        else {}
    )
    local_scheduler_hint = (
        scheduler_hint.get("local_scheduler")
        if isinstance(scheduler_hint.get("local_scheduler"), dict)
        else {}
    )
    codex_app_hint = (
        scheduler_hint.get("codex_app")
        if isinstance(scheduler_hint.get("codex_app"), dict)
        else {}
    )
    reset_policy = (
        scheduler_hint.get("reset_policy")
        if isinstance(scheduler_hint.get("reset_policy"), dict)
        else {}
    )
    recommended_interval_minutes = _positive_int(
        local_scheduler_hint.get("recommended_interval_minutes")
        or codex_app_hint.get("recommended_interval_minutes"),
        10,
    )
    reset_interval_minutes = _positive_int(
        reset_policy.get("local_scheduler_initial_interval_minutes"),
        recommended_interval_minutes,
    )

    candidate_command = None
    precise_blocker: dict[str, str] | None = None
    if decision == "visible_session_turn_candidate":
        if idle_approved:
            scheduler_action = "external_visible_command_candidate"
            candidate_command = run_packet.get("recommended_command")
            next_safe_step = (
                "external scheduler may run the visible command only after a fresh quota guard, "
                "runtime idle observation, guard_checked, and an allowed command prefix"
            )
        else:
            scheduler_action = "write_precise_blocker"
            reason = (
                "runtime_idle_evidence_missing"
                if idle_payload is None
                else "runtime_idle_detector_incomplete"
            )
            failures = idle_detector.get("failures") if isinstance(idle_detector.get("failures"), list) else []
            precise_blocker = {
                "reason": reason,
                "message": (
                    "Codex CLI visible automation is blocked until a public-safe runtime idle "
                    "observation proves no active human typing, no running visible turn, user "
                    f"visibility, and interruptibility. failures={failures}"
                ),
            }
            next_safe_step = (
                "capture a public-safe runtime idle observation, keep the one-message TUI path visible, "
                "and do not run Codex from the scheduler"
            )
    elif decision == "visible_session_proof_required":
        scheduler_action = "write_precise_blocker"
        precise_blocker = {
            "reason": "visible_session_proof_missing",
            "message": (
                "Codex CLI automation is blocked until a public-safe visible-session proof "
                "shows user opt-in, quota guard, idle guard, visibility, interruptibility, "
                "boundary safety, and compact writeback planning."
            ),
        }
        next_safe_step = "write the blocker, keep TUI bootstrap primary, and do not run Codex from the scheduler"
    elif decision.startswith("headless_"):
        scheduler_action = "write_precise_blocker"
        precise_blocker = {
            "reason": "headless_fallback_disabled",
            "message": (
                "Codex CLI headless fallback is disabled for the default LoopX "
                "/goal bootstrap path; keep the visible TUI bootstrap primary."
            ),
        }
        next_safe_step = "write the blocker and keep the one-message TUI bootstrap as the user-facing path"
    else:
        scheduler_action = "surface_tui_bootstrap"
        next_safe_step = "surface the TUI bootstrap command; do not run Codex from the scheduler"

    if precise_blocker:
        recommended_action = f"{precise_blocker['reason']}: {precise_blocker['message']}"
        blocker_writeback_command = (
            f"{_shell_arg(cli_bin)} refresh-state --goal-id {_shell_arg(resolved_goal_id)} "
            "--classification codex_cli_local_scheduler_blocked "
            "--delivery-batch-scale single_surface --delivery-outcome outcome_gap"
            f"{agent_arg} --agent-lane productization_codex_cli "
            f"--recommended-action {_shell_arg(recommended_action)}"
        )
    else:
        blocker_writeback_command = None

    return {
        "ok": True,
        "schema_version": "codex_cli_local_scheduler_tick_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "scheduler_phase": "tick_packet_no_execution",
        "scheduler_action": scheduler_action,
        "decision": decision,
        "next_safe_step": next_safe_step,
        "candidate_command": candidate_command,
        "precise_blocker": precise_blocker,
        "blocker_writeback_command": blocker_writeback_command,
        "scheduler_hint": scheduler_hint or None,
        "launchd": {
            "label": _scheduler_label(resolved_goal_id, agent_id),
            "one_shot_command": scheduler_tick_command,
            "keep_alive": False,
            "recommended_interval_seconds": recommended_interval_minutes * 60,
            "reset_token": reset_policy.get("reset_token"),
            "reset_interval_seconds": reset_interval_minutes * 60,
            "reset_policy": reset_policy or None,
            "notes": [
                "Run this tick as a one-shot or low-frequency launchd job.",
                "If quota scheduler_hint is present, apply its cadence/backoff and unchanged-poll stop policy.",
                "If scheduler_hint.reset_policy.reset_token changes, reset the local interval to reset_interval_seconds and clear unchanged-poll state without spending quota.",
                "The tick prints a candidate command or blocker command; it does not execute Codex.",
                "Use external logging that excludes raw transcripts, session files, credentials, and private paths.",
            ],
        },
        "commands": {
            "visible_driver_run": visible_driver_run_command,
            "runtime_idle_detector": runtime_idle_detector_command,
            "runtime_idle_detector_fixture": runtime_idle_fixture_command,
            "scheduler_tick": scheduler_tick_command,
            "candidate_codex_command": candidate_command,
            "blocker_writeback": blocker_writeback_command,
        },
        "visible_driver_run_packet": {
            "schema_version": run_packet.get("schema_version"),
            "driver_mode": run_packet.get("driver_mode"),
            "decision": run_packet.get("decision"),
            "next_driver_action": run_packet.get("next_driver_action"),
            "allow_headless_fallback": run_packet.get("allow_headless_fallback"),
            "visible_session_proof": run_packet.get("visible_session_proof"),
        },
        "runtime_idle_detector": {
            "supplied": idle_payload is not None,
            "approved": idle_approved,
            "decision": idle_detector.get("decision"),
            "failures": idle_detector.get("failures") or [],
            "source": idle_detector.get("source"),
        },
        "boundary": {
            "tick_packet_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_loopx_quota": False,
            "writes_loopx_state": False,
            "blocker_writeback_requires_external_execution": True,
            "visible_candidate_requires_runtime_idle_detector": True,
            "headless_execution_disabled": True,
        },
        "warnings": list(run_packet.get("warnings") or []),
    }


def _command_matches_allowed_prefix(command: str | None, prefixes: list[str]) -> bool:
    if not command or not prefixes:
        return False
    try:
        command_parts = shlex.split(command)
    except ValueError:
        command_parts = []
    for raw_prefix in prefixes:
        prefix = (raw_prefix or "").strip()
        if not prefix:
            continue
        try:
            prefix_parts = shlex.split(prefix)
        except ValueError:
            prefix_parts = []
        if prefix_parts and command_parts[: len(prefix_parts)] == prefix_parts:
            return True
        if command.strip() == prefix or command.strip().startswith(f"{prefix} "):
            return True
    return False


def _run_scheduler_executor_shell_command(
    command: str,
    *,
    timeout_seconds: float,
    capture_output: bool = False,
) -> dict[str, Any]:
    stdout = subprocess.PIPE if capture_output else subprocess.DEVNULL
    stderr = subprocess.PIPE if capture_output else subprocess.DEVNULL
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return {
            "attempted": False,
            "returncode": None,
            "timed_out": False,
            "output_captured": capture_output,
            "error": f"invalid_command: {exc}",
        }
    if not argv:
        return {
            "attempted": False,
            "returncode": None,
            "timed_out": False,
            "output_captured": capture_output,
            "error": "empty_command",
        }
    try:
        completed = subprocess.run(
            argv,
            check=False,
            text=True,
            timeout=timeout_seconds,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        return {
            "attempted": True,
            "returncode": None,
            "timed_out": True,
            "output_captured": capture_output,
        }
    return {
        "attempted": True,
        "returncode": completed.returncode,
        "timed_out": False,
        "output_captured": capture_output,
    }


SchedulerCommandRunner = Callable[..., dict[str, Any]]


def execute_codex_cli_local_scheduler_tick_result(
    tick_payload: dict[str, Any],
    *,
    execute_candidate: bool = False,
    execute_blocker_writeback: bool = False,
    guard_checked: bool = False,
    candidate_command_prefixes: list[str] | None = None,
    executor_timeout_seconds: float = DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
    runner: SchedulerCommandRunner | None = None,
) -> dict[str, Any]:
    """Optionally execute one scheduler tick result behind explicit opt-in gates."""

    candidate_command_prefixes = list(candidate_command_prefixes or [])
    runner = runner or _run_scheduler_executor_shell_command
    scheduler_action = str(tick_payload.get("scheduler_action") or "")
    candidate_command = tick_payload.get("candidate_command")
    blocker_writeback_command = tick_payload.get("blocker_writeback_command")
    candidate_command = candidate_command if isinstance(candidate_command, str) else None
    blocker_writeback_command = (
        blocker_writeback_command if isinstance(blocker_writeback_command, str) else None
    )
    commands = tick_payload.get("commands") if isinstance(tick_payload.get("commands"), dict) else {}
    runtime_idle = (
        tick_payload.get("runtime_idle_detector")
        if isinstance(tick_payload.get("runtime_idle_detector"), dict)
        else {}
    )
    runtime_idle_approved = bool(runtime_idle.get("approved") is True)

    execution: dict[str, Any] = {
        "attempted": False,
        "executed": False,
        "kind": None,
        "reason": "no_execute_flag",
        "returncode": None,
        "timed_out": False,
        "output_captured": False,
        "candidate_prefix_matched": None,
    }

    if execute_candidate and execute_blocker_writeback:
        execution["reason"] = "choose_one_execute_mode"
    elif (execute_candidate or execute_blocker_writeback) and not guard_checked:
        execution["reason"] = "fresh_quota_guard_confirmation_required"
    elif execute_candidate:
        if scheduler_action != "external_visible_command_candidate":
            execution["reason"] = "scheduler_action_not_candidate"
        elif scheduler_action == "external_visible_command_candidate" and not runtime_idle_approved:
            execution["reason"] = "runtime_idle_detector_required"
        elif not candidate_command:
            execution["reason"] = "candidate_command_missing"
        elif not candidate_command_prefixes:
            execution["reason"] = "candidate_command_prefix_required"
        elif not _command_matches_allowed_prefix(candidate_command, candidate_command_prefixes):
            execution["reason"] = "candidate_command_prefix_mismatch"
            execution["candidate_prefix_matched"] = False
        else:
            execution["candidate_prefix_matched"] = True
            result = runner(
                candidate_command,
                timeout_seconds=executor_timeout_seconds,
                capture_output=False,
            )
            execution.update(result)
            execution["executed"] = True
            execution["kind"] = "candidate_command"
            execution["reason"] = "candidate_command_executed"
    elif execute_blocker_writeback:
        if scheduler_action != "write_precise_blocker":
            execution["reason"] = "scheduler_action_not_blocker_writeback"
        elif not blocker_writeback_command:
            execution["reason"] = "blocker_writeback_command_missing"
        else:
            result = runner(
                blocker_writeback_command,
                timeout_seconds=executor_timeout_seconds,
                capture_output=False,
            )
            execution.update(result)
            execution["executed"] = True
            execution["kind"] = "blocker_writeback"
            execution["reason"] = "blocker_writeback_executed"

    executed = bool(execution.get("executed"))
    command_failed = executed and (
        bool(execution.get("timed_out")) or execution.get("returncode") not in {0, None}
    )
    return {
        "ok": not command_failed,
        "schema_version": "codex_cli_local_scheduler_executor_v0",
        "project": tick_payload.get("project"),
        "goal_id": tick_payload.get("goal_id"),
        "agent_id": tick_payload.get("agent_id"),
        "cli_bin": tick_payload.get("cli_bin"),
        "codex_bin": tick_payload.get("codex_bin"),
        "executor_phase": "explicit_opt_in_executor",
        "scheduler_action": scheduler_action,
        "decision": tick_payload.get("decision"),
        "next_safe_step": tick_payload.get("next_safe_step"),
        "execution_request": {
            "execute_candidate": execute_candidate,
            "execute_blocker_writeback": execute_blocker_writeback,
            "guard_checked": guard_checked,
            "candidate_command_prefixes": candidate_command_prefixes,
            "executor_timeout_seconds": executor_timeout_seconds,
            "runtime_idle_detector_required_for_visible_candidate": True,
        },
        "execution": execution,
        "commands": {
            "scheduler_tick": commands.get("scheduler_tick"),
            "candidate_command": candidate_command,
            "blocker_writeback": blocker_writeback_command,
        },
        "scheduler_tick": {
            "schema_version": tick_payload.get("schema_version"),
            "scheduler_phase": tick_payload.get("scheduler_phase"),
            "scheduler_action": scheduler_action,
            "decision": tick_payload.get("decision"),
            "precise_blocker": tick_payload.get("precise_blocker"),
            "visible_session_proof": (
                (tick_payload.get("visible_driver_run_packet") or {}).get("visible_session_proof")
                if isinstance(tick_payload.get("visible_driver_run_packet"), dict)
                else None
            ),
            "runtime_idle_detector": runtime_idle,
        },
        "boundary": {
            "executor_wrapper": True,
            "requires_explicit_execute_flag": True,
            "requires_fresh_quota_guard_confirmation": True,
            "candidate_prefix_required": True,
            "runtime_idle_detector_required_for_visible_candidate": True,
            "runs_external_candidate": executed and execution.get("kind") == "candidate_command",
            "runs_codex_candidate_possible": executed and execution.get("kind") == "candidate_command",
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "candidate_output_captured": False,
            "blocker_output_captured": False,
            "spends_loopx_quota": False,
            "writes_loopx_state": executed and execution.get("kind") == "blocker_writeback",
        },
        "warnings": list(tick_payload.get("warnings") or []),
    }


def build_codex_cli_local_scheduler_executor(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    quota_payload: dict[str, Any] | None = None,
    proof_payload: dict[str, Any] | None = None,
    idle_payload: dict[str, Any] | None = None,
    allow_headless_fallback: bool = False,
    execute_candidate: bool = False,
    execute_blocker_writeback: bool = False,
    guard_checked: bool = False,
    candidate_command_prefixes: list[str] | None = None,
    executor_timeout_seconds: float = DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
    runner: SchedulerCommandRunner | None = None,
) -> dict[str, Any]:
    tick_payload = build_codex_cli_local_scheduler_tick(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
        quota_payload=quota_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=allow_headless_fallback,
    )
    return execute_codex_cli_local_scheduler_tick_result(
        tick_payload,
        execute_candidate=execute_candidate,
        execute_blocker_writeback=execute_blocker_writeback,
        guard_checked=guard_checked,
        candidate_command_prefixes=candidate_command_prefixes,
        executor_timeout_seconds=executor_timeout_seconds,
        runner=runner,
    )
