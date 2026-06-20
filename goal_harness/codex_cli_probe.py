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


def load_codex_cli_visible_session_proof_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Codex CLI visible session proof fixture must be a JSON object")
    return data


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


def _nested_bool(payload: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return False
        current = current.get(key)
    return current is True


def _nested_false(payload: Mapping[str, Any], path: tuple[str, ...]) -> bool:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return False
        current = current.get(key)
    return current is False


VISIBLE_SESSION_PROOF_REQUIRED_TRUE_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("user_opt_in", ("user_opt_in",), "user explicitly opted into this proof"),
    ("quota_guard_passed", ("quota_guard", "passed"), "quota should-run allowed this proof path"),
    ("idle_no_human_typing", ("idle_guard", "no_active_human_typing"), "idle guard saw no active human typing"),
    ("idle_no_running_turn", ("idle_guard", "no_running_turn"), "idle guard saw no running Codex turn"),
    ("idle_checked_before_prompt", ("idle_guard", "checked_before_prompt"), "idle guard ran before the visible prompt"),
    ("visible_to_user", ("turn_visibility", "visible_to_user"), "the steering turn was visible to the user"),
    ("visible_prompt_public_safe", ("turn_visibility", "prompt_public_safe"), "the visible prompt was public-safe"),
    ("user_can_interrupt", ("interruptibility", "user_can_interrupt"), "the user can interrupt the turn"),
    ("manual_takeover_available", ("interruptibility", "manual_takeover_available"), "manual takeover remains available"),
    ("compact_writeback_planned", ("writeback", "compact_evidence_planned"), "compact evidence writeback is planned before quota spend"),
)


VISIBLE_SESSION_PROOF_REQUIRED_FALSE_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("no_raw_transcript_read", ("boundary", "reads_raw_transcripts"), "raw transcripts were not read"),
    ("no_session_files_read", ("boundary", "reads_session_files"), "session files were not read"),
    ("no_credentials_read", ("boundary", "reads_credentials"), "credentials were not read"),
    ("no_hidden_session_mutation", ("boundary", "mutates_hidden_session_state"), "hidden session state was not mutated"),
    ("no_quota_spend_before_writeback", ("boundary", "spends_quota_before_writeback"), "quota was not spent before writeback"),
)


def build_codex_cli_visible_session_proof(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    proof_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate a public-safe proof packet for visible Codex CLI steering.

    This command intentionally does not run Codex or inspect local session
    state. It validates whether a separately captured public-safe observation
    is strong enough to treat resume/remote-control as a candidate for future
    same-session automation.
    """

    resolved_project = str(project.expanduser())
    resolved_goal_id = goal_id or default_goal_id(project)
    if proof_payload is None:
        return {
            "ok": False,
            "schema_version": "codex_cli_visible_session_proof_v0",
            "project": resolved_project,
            "goal_id": resolved_goal_id,
            "agent_id": agent_id,
            "decision": "proof_fixture_required",
            "approved_for_same_session_automation": False,
            "recommended_action": "capture a public-safe proof fixture; do not run same-session automation yet",
            "required_fixture_shape": {
                "user_opt_in": True,
                "quota_guard": {"passed": True},
                "idle_guard": {
                    "no_active_human_typing": True,
                    "no_running_turn": True,
                    "checked_before_prompt": True,
                },
                "turn_visibility": {
                    "visible_to_user": True,
                    "prompt_public_safe": True,
                },
                "interruptibility": {
                    "user_can_interrupt": True,
                    "manual_takeover_available": True,
                },
                "boundary": {
                    "reads_raw_transcripts": False,
                    "reads_session_files": False,
                    "reads_credentials": False,
                    "mutates_hidden_session_state": False,
                    "spends_quota_before_writeback": False,
                },
                "writeback": {"compact_evidence_planned": True},
            },
            "boundary": {
                "fixture_only": True,
                "runs_codex": False,
                "reads_raw_transcripts": False,
                "reads_credentials": False,
                "reads_session_files": False,
                "mutates_codex_session": False,
                "spends_goal_harness_quota": False,
            },
            "checks": [],
            "failures": ["missing_proof_fixture"],
        }

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    for key, path, description in VISIBLE_SESSION_PROOF_REQUIRED_TRUE_CHECKS:
        passed = _nested_bool(proof_payload, path)
        checks.append({"key": key, "required": True, "passed": passed, "description": description})
        if not passed:
            failures.append(key)
    for key, path, description in VISIBLE_SESSION_PROOF_REQUIRED_FALSE_CHECKS:
        passed = _nested_false(proof_payload, path)
        checks.append({"key": key, "required": False, "passed": passed, "description": description})
        if not passed:
            failures.append(key)

    observed_surface = str(proof_payload.get("observed_surface") or "unknown")
    supported_surface = observed_surface in {
        "visible_resume_prompt",
        "remote_control_visible_prompt",
        "same_tui_visible_attach",
    }
    if not supported_surface:
        failures.append("unsupported_observed_surface")
    checks.append(
        {
            "key": "supported_observed_surface",
            "required": sorted(
                [
                    "remote_control_visible_prompt",
                    "same_tui_visible_attach",
                    "visible_resume_prompt",
                ]
            ),
            "actual": observed_surface,
            "passed": supported_surface,
            "description": "observed surface is a visible Codex CLI steering path",
        }
    )

    approved = not failures
    if approved:
        decision = "visible_session_proof_passed"
        recommended_action = (
            "allow a future opt-in driver spike to use this visible surface behind quota and idle guards"
        )
    else:
        decision = "visible_session_proof_incomplete"
        recommended_action = (
            "keep TUI bootstrap primary and headless exec explicit; do not treat this as same-session automation"
        )

    return {
        "ok": True,
        "schema_version": "codex_cli_visible_session_proof_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "source": "proof_fixture",
        "observed_surface": observed_surface,
        "decision": decision,
        "approved_for_same_session_automation": approved,
        "recommended_action": recommended_action,
        "checks": checks,
        "failures": failures,
        "boundary": {
            "fixture_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_goal_harness_quota": False,
        },
    }


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


def build_codex_cli_local_driver_plan(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a dry-run-first local driver plan for Codex CLI.

    This does not launch Codex or mutate any session. It composes the existing
    one-message TUI bootstrap, visible-driver plan, quota guard, and explicit
    headless fallback into one operator-facing decision packet.
    """

    visible_plan = build_codex_cli_visible_driver_plan(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
    )
    resolved_project = visible_plan["project"]
    resolved_goal_id = visible_plan["goal_id"]
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    visible_driver_plan_command = (
        f"{_shell_arg(cli_bin)} codex-cli-visible-driver-plan "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg} "
        f"--codex-bin {_shell_arg(codex_bin)}"
    )
    quota_guard_command = (
        f"{_shell_arg(cli_bin)} --format json "
        "--registry \"$HOME/.codex/goal-harness/registry.global.json\" "
        f"quota should-run --goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
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
    driver_mode = str(visible_plan.get("driver_mode") or "tui_bootstrap_only")

    if driver_mode == "session_attached_visible_turn":
        decision = "attempt_visible_session_attach_after_idle_guard"
        operator_instruction = (
            "Run quota guard, verify idle guard, then attempt only the detected visible attach primitive."
        )
    elif driver_mode == "visible_resume_or_remote_control_spike":
        decision = "run_visible_resume_or_remote_control_proof"
        operator_instruction = (
            "Treat resume or remote-control as a proof target, not production session attachment, until the turn is visible and interruptible."
        )
    elif driver_mode == "explicit_headless_fallback_after_tui_bootstrap":
        decision = "keep_tui_primary_offer_explicit_exec_fallback"
        operator_instruction = (
            "Keep one-message Codex CLI TUI bootstrap as the default; use codex exec only after explicit opt-in."
        )
    else:
        decision = "ask_user_to_start_from_tui"
        operator_instruction = "Ask the user to start inside Codex CLI TUI and paste the bootstrap message."

    return {
        "ok": True,
        "schema_version": "codex_cli_local_driver_plan_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "driver_phase": "dry_run_plan",
        "driver_mode": driver_mode,
        "decision": decision,
        "operator_instruction": operator_instruction,
        "visible_driver_plan": {
            "schema_version": visible_plan.get("schema_version"),
            "driver_mode": visible_plan.get("driver_mode"),
            "automation_action": visible_plan.get("automation_action"),
            "next_step": visible_plan.get("next_step"),
        },
        "commands": {
            "quota_guard": quota_guard_command,
            "local_driver_plan": (
                f"{_shell_arg(cli_bin)} codex-cli-local-driver-plan "
                f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg} "
                f"--codex-bin {_shell_arg(codex_bin)}"
            ),
            "visible_driver_plan": visible_driver_plan_command,
            "tui_bootstrap_message": bootstrap_command,
            "explicit_headless_fallback": exec_fallback_command,
        },
        "driver_steps": [
            "run quota_guard and stop when user_channel.action_required=true",
            "run visible_driver_plan to classify TUI, resume, remote-control, or exec fallback mode",
            "verify idle_guard before any visible resume or remote-control prompt",
            "prefer one-message TUI bootstrap until visible attach is proven",
            "offer explicit_headless_fallback only after opt-in and goal_boundary approval",
            "write back compact evidence or a precise blocker before quota spend",
        ],
        "idle_guard": {
            "required": True,
            "implemented": False,
            "placeholder": "future driver must prove no active human typing and no running turn before visible resume or remote-control prompt",
        },
        "execution_policy": {
            "tui_bootstrap_primary": True,
            "headless_fallback_requires_user_opt_in": True,
            "same_session_attachment_requires_visible_proof": True,
            "quota_guard_required": True,
            "spend_after_validated_writeback_only": True,
        },
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
        "warnings": list(visible_plan.get("warnings") or []),
    }


def build_codex_cli_visible_driver_run_packet(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    proof_payload: dict[str, Any] | None = None,
    allow_headless_fallback: bool = False,
) -> dict[str, Any]:
    """Build the v0 runner packet for one visible Codex CLI driver turn.

    The packet is deliberately not an executor. It converts the dry-run local
    driver plan, optional visible-session proof, and explicit headless opt-in
    into the next safe command boundary for a local scheduler or human operator.
    """

    local_plan = build_codex_cli_local_driver_plan(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
    )
    resolved_project = str(local_plan["project"])
    resolved_goal_id = str(local_plan["goal_id"])
    driver_mode = str(local_plan.get("driver_mode") or "tui_bootstrap_only")
    commands = local_plan.get("commands") if isinstance(local_plan.get("commands"), dict) else {}
    proof = build_codex_cli_visible_session_proof(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        proof_payload=proof_payload,
    ) if proof_payload is not None else None
    proof_approved = bool(proof and proof.get("approved_for_same_session_automation") is True)
    proof_command = (
        f"{_shell_arg(cli_bin)} codex-cli-visible-session-proof "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{' --agent-id ' + _shell_arg(agent_id) if agent_id else ''} "
        "--proof-fixture <public-visible-proof.json>"
    )

    if proof_approved:
        decision = "visible_session_turn_candidate"
        next_driver_action = "run_visible_session_turn_after_quota_and_idle_guard"
        recommended_command = proof_payload.get("recommended_command") if isinstance(proof_payload, dict) else None
        if not recommended_command:
            recommended_command = "use the proven visible Codex CLI surface; do not read transcripts or hidden session files"
    elif driver_mode in {"session_attached_visible_turn", "visible_resume_or_remote_control_spike"}:
        decision = "visible_session_proof_required"
        next_driver_action = "capture_public_safe_visible_session_proof"
        recommended_command = proof_command
    elif driver_mode == "explicit_headless_fallback_after_tui_bootstrap" and allow_headless_fallback:
        decision = "headless_fallback_command_ready"
        next_driver_action = "run_explicit_headless_fallback_after_quota_guard"
        recommended_command = commands.get("explicit_headless_fallback")
    elif driver_mode == "explicit_headless_fallback_after_tui_bootstrap":
        decision = "headless_fallback_requires_explicit_opt_in"
        next_driver_action = "ask_user_before_headless_codex_exec"
        recommended_command = commands.get("tui_bootstrap_message")
    else:
        decision = "tui_bootstrap_only"
        next_driver_action = "ask_user_to_start_inside_codex_cli_tui"
        recommended_command = commands.get("tui_bootstrap_message")

    driver_steps = [
        "run quota_guard and stop if user_channel.action_required=true",
        "stop or relocate if workspace_guard blocks the current checkout",
        "use a visible session only when proof_approved=true and an idle guard passes",
        "use headless codex exec only when allow_headless_fallback=true and the goal boundary permits it",
        "after the Codex turn, validate evidence or blocker before refresh-state",
        "spend quota exactly once after validated writeback, never for this packet alone",
    ]

    return {
        "ok": True,
        "schema_version": "codex_cli_visible_driver_run_packet_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "driver_phase": "run_packet_no_execution",
        "driver_mode": driver_mode,
        "decision": decision,
        "next_driver_action": next_driver_action,
        "recommended_command": recommended_command,
        "allow_headless_fallback": allow_headless_fallback,
        "visible_session_proof": {
            "supplied": proof is not None,
            "approved": proof_approved,
            "decision": proof.get("decision") if proof else None,
            "failures": proof.get("failures") if proof else [],
        },
        "local_driver_plan": {
            "schema_version": local_plan.get("schema_version"),
            "driver_mode": local_plan.get("driver_mode"),
            "decision": local_plan.get("decision"),
            "operator_instruction": local_plan.get("operator_instruction"),
        },
        "commands": {
            "quota_guard": commands.get("quota_guard"),
            "tui_bootstrap_message": commands.get("tui_bootstrap_message"),
            "visible_session_proof": proof_command,
            "explicit_headless_fallback": commands.get("explicit_headless_fallback"),
        },
        "driver_steps": driver_steps,
        "execution_policy": {
            "tui_bootstrap_primary": True,
            "same_session_attachment_requires_visible_proof": True,
            "headless_fallback_requires_explicit_opt_in": True,
            "quota_guard_required": True,
            "idle_guard_required_before_visible_prompt": True,
            "spend_after_validated_writeback_only": True,
        },
        "boundary": {
            "run_packet_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_goal_harness_quota": False,
            "requires_user_gate_stop": True,
            "requires_goal_boundary_before_headless": True,
        },
        "warnings": list(local_plan.get("warnings") or []),
    }


def _scheduler_label(goal_id: str, agent_id: str | None) -> str:
    raw = f"{goal_id}-{agent_id or 'agent'}"
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    safe = "-".join(part for part in safe.split("-") if part)
    return f"com.goal-harness.codex-cli.{safe}"


def build_codex_cli_local_scheduler_tick(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    proof_payload: dict[str, Any] | None = None,
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
    scheduler_tick_command = (
        f"{_shell_arg(cli_bin)} codex-cli-local-scheduler-tick {common_args}"
    )

    candidate_command = None
    precise_blocker: dict[str, str] | None = None
    if decision == "visible_session_turn_candidate":
        scheduler_action = "external_visible_command_candidate"
        candidate_command = run_packet.get("recommended_command")
        next_safe_step = "external scheduler may run the visible command only after a fresh quota guard and idle guard"
    elif decision == "headless_fallback_command_ready":
        scheduler_action = "external_headless_fallback_candidate"
        candidate_command = run_packet.get("recommended_command")
        next_safe_step = "external scheduler may run the headless fallback only after explicit opt-in and a fresh quota guard"
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
    elif decision == "headless_fallback_requires_explicit_opt_in":
        scheduler_action = "write_precise_blocker"
        precise_blocker = {
            "reason": "headless_fallback_opt_in_missing",
            "message": (
                "Codex CLI automation is blocked from using headless codex exec until the user "
                "or operator explicitly opts into the fallback for this goal."
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
        "launchd": {
            "label": _scheduler_label(resolved_goal_id, agent_id),
            "one_shot_command": scheduler_tick_command,
            "keep_alive": False,
            "recommended_interval_seconds": 600,
            "notes": [
                "Run this tick as a one-shot or low-frequency launchd job.",
                "The tick prints a candidate command or blocker command; it does not execute Codex.",
                "Use external logging that excludes raw transcripts, session files, credentials, and private paths.",
            ],
        },
        "commands": {
            "visible_driver_run": visible_driver_run_command,
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
        "boundary": {
            "tick_packet_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_goal_harness_quota": False,
            "writes_goal_harness_state": False,
            "blocker_writeback_requires_external_execution": True,
        },
        "warnings": list(run_packet.get("warnings") or []),
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


def render_codex_cli_local_driver_plan_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    steps = payload.get("driver_steps") if isinstance(payload.get("driver_steps"), list) else []
    idle_guard = payload.get("idle_guard") if isinstance(payload.get("idle_guard"), dict) else {}
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Local Driver Plan

- driver_phase: `{payload.get("driver_phase")}`
- driver_mode: `{payload.get("driver_mode")}`
- decision: `{payload.get("decision")}`
- operator_instruction: {payload.get("operator_instruction")}

## Commands

```bash
{commands.get("quota_guard")}
{commands.get("visible_driver_plan")}
{commands.get("tui_bootstrap_message")}
{commands.get("explicit_headless_fallback")}
```

## Driver Steps

{step_lines}

## Idle Guard

- required: `{idle_guard.get("required")}`
- implemented: `{idle_guard.get("implemented")}`
- placeholder: {idle_guard.get("placeholder")}

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- headless_fallback_requires_user_opt_in: `{policy.get("headless_fallback_requires_user_opt_in")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- quota_guard_required: `{policy.get("quota_guard_required")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- dry_run_plan_only: `{boundary.get("dry_run_plan_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_goal_harness_quota: `{boundary.get("spends_goal_harness_quota")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_visible_driver_run_packet_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    steps = payload.get("driver_steps") if isinstance(payload.get("driver_steps"), list) else []
    proof = payload.get("visible_session_proof") if isinstance(payload.get("visible_session_proof"), dict) else {}
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Visible Driver Run Packet

- driver_phase: `{payload.get("driver_phase")}`
- driver_mode: `{payload.get("driver_mode")}`
- decision: `{payload.get("decision")}`
- next_driver_action: `{payload.get("next_driver_action")}`
- allow_headless_fallback: `{payload.get("allow_headless_fallback")}`

## Recommended Command

```bash
{payload.get("recommended_command")}
```

## Commands

```bash
{commands.get("quota_guard")}
{commands.get("tui_bootstrap_message")}
{commands.get("visible_session_proof")}
{commands.get("explicit_headless_fallback")}
```

## Visible Session Proof

- supplied: `{proof.get("supplied")}`
- approved: `{proof.get("approved")}`
- decision: `{proof.get("decision")}`
- failures: `{proof.get("failures")}`

## Driver Steps

{step_lines}

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- headless_fallback_requires_explicit_opt_in: `{policy.get("headless_fallback_requires_explicit_opt_in")}`
- quota_guard_required: `{policy.get("quota_guard_required")}`
- idle_guard_required_before_visible_prompt: `{policy.get("idle_guard_required_before_visible_prompt")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- run_packet_only: `{boundary.get("run_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_goal_harness_quota: `{boundary.get("spends_goal_harness_quota")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_local_scheduler_tick_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    launchd = payload.get("launchd") if isinstance(payload.get("launchd"), dict) else {}
    blocker = payload.get("precise_blocker") if isinstance(payload.get("precise_blocker"), dict) else None
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    blocker_lines = "- none"
    if blocker:
        blocker_lines = f"- reason: `{blocker.get('reason')}`\n- message: {blocker.get('message')}"
    return f"""# Codex CLI Local Scheduler Tick

- scheduler_phase: `{payload.get("scheduler_phase")}`
- scheduler_action: `{payload.get("scheduler_action")}`
- decision: `{payload.get("decision")}`
- next_safe_step: {payload.get("next_safe_step")}

## Commands

```bash
{commands.get("visible_driver_run")}
{commands.get("scheduler_tick")}
{commands.get("candidate_codex_command") or "# no Codex command candidate"}
{commands.get("blocker_writeback") or "# no blocker writeback command"}
```

## Precise Blocker

{blocker_lines}

## Launchd Shape

- label: `{launchd.get("label")}`
- keep_alive: `{launchd.get("keep_alive")}`
- recommended_interval_seconds: `{launchd.get("recommended_interval_seconds")}`
- one_shot_command: `{launchd.get("one_shot_command")}`

## Boundary

- tick_packet_only: `{boundary.get("tick_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_goal_harness_quota: `{boundary.get("spends_goal_harness_quota")}`
- writes_goal_harness_state: `{boundary.get("writes_goal_harness_state")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_visible_session_proof_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    required_shape = payload.get("required_fixture_shape")
    check_lines = "\n".join(
        f"- [{'x' if check.get('passed') else ' '}] {check.get('key')}: {check.get('description')}"
        for check in checks
        if isinstance(check, dict)
    )
    if not check_lines:
        check_lines = "- no proof fixture supplied"
    failure_lines = "\n".join(f"- {failure}" for failure in failures) if failures else "- none"
    required_shape_block = ""
    if isinstance(required_shape, dict):
        required_shape_block = f"""
## Required Fixture Shape

```json
{json.dumps(required_shape, indent=2, ensure_ascii=False)}
```
"""
    return f"""# Codex CLI Visible Session Proof

- decision: `{payload.get("decision")}`
- approved_for_same_session_automation: `{payload.get("approved_for_same_session_automation")}`
- observed_surface: `{payload.get("observed_surface")}`
- recommended_action: {payload.get("recommended_action")}

## Checks

{check_lines}

## Failures

{failure_lines}

## Boundary

- fixture_only: `{boundary.get("fixture_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_goal_harness_quota: `{boundary.get("spends_goal_harness_quota")}`
{required_shape_block}
"""
