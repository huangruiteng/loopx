from __future__ import annotations

import json
import platform
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from .bootstrap import default_goal_id
from .project_prompt import build_codex_cli_bootstrap_message


DEFAULT_CODEX_BIN = "codex"
DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_EXECUTOR_TIMEOUT_SECONDS = 30.0
DEFAULT_MIN_HUMAN_INPUT_IDLE_SECONDS = 5.0


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
        recommended_mode = "tui_bootstrap_only"
        automation_action = "ask_user_to_start_inside_codex_cli_tui"
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
    if exec_supported and not (safe_injection_supported or remote_control_surface_detected or visible_resume_supported):
        warnings.append(
            "Codex exec is available, but headless fallback is disabled for the default LoopX setup-then-goal bootstrap path."
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
            "spends_loopx_quota": False,
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


def load_codex_cli_runtime_idle_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Codex CLI runtime idle fixture must be a JSON object")
    return data


def load_codex_cli_first_response_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Codex CLI first-response fixture must be a JSON object")
    return data


def probe_human_input_idle_seconds(*, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Read a coarse local human-input idle metric without touching Codex state.

    On macOS this reads IOHIDSystem's HIDIdleTime counter. The value says only
    how long the machine has been idle since the last keyboard/mouse event; it
    does not read typed text, terminal buffers, Codex transcripts, session
    files, stdout/stderr, or credentials.
    """

    system = platform.system().lower()
    if system != "darwin":
        return {
            "ok": False,
            "source": "unsupported_platform",
            "platform": system or "unknown",
            "error": "human_input_idle_probe_only_implemented_for_macos",
        }
    try:
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return {"ok": False, "source": "macos_hid_idle_time", "error": "ioreg_not_found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "source": "macos_hid_idle_time", "error": "timeout"}
    if result.returncode != 0:
        return {"ok": False, "source": "macos_hid_idle_time", "error": f"exit_{result.returncode}"}
    for line in result.stdout.splitlines():
        if "HIDIdleTime" not in line:
            continue
        raw_value = line.split("=", 1)[-1].strip()
        try:
            return {
                "ok": True,
                "source": "macos_hid_idle_time",
                "platform": "darwin",
                "human_input_idle_seconds": int(raw_value) / 1_000_000_000,
            }
        except ValueError:
            return {
                "ok": False,
                "source": "macos_hid_idle_time",
                "error": "unparseable_hid_idle_time",
            }
    return {"ok": False, "source": "macos_hid_idle_time", "error": "hid_idle_time_not_found"}


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


RUNTIME_IDLE_REQUIRED_TRUE_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("idle_no_human_typing", ("idle_guard", "no_active_human_typing"), "no active human typing was observed"),
    ("idle_no_running_turn", ("idle_guard", "no_running_turn"), "no running Codex turn was observed"),
    ("idle_checked_before_prompt", ("idle_guard", "checked_before_prompt"), "idle check ran before any visible prompt"),
    ("visible_to_user", ("turn_visibility", "visible_to_user"), "the target turn remains visible to the user"),
    ("user_can_interrupt", ("interruptibility", "user_can_interrupt"), "the user can interrupt the turn"),
    ("manual_takeover_available", ("interruptibility", "manual_takeover_available"), "manual takeover remains available"),
)


RUNTIME_IDLE_REQUIRED_FALSE_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("no_raw_transcript_read", ("boundary", "reads_raw_transcripts"), "raw transcripts were not read"),
    ("no_session_files_read", ("boundary", "reads_session_files"), "session files were not read"),
    ("no_stdout_stderr_read", ("boundary", "reads_stdout_stderr"), "stdout/stderr streams were not read"),
    ("no_credentials_read", ("boundary", "reads_credentials"), "credentials were not read"),
    ("no_hidden_session_mutation", ("boundary", "mutates_hidden_session_state"), "hidden session state was not mutated"),
)


FIRST_RESPONSE_REQUIRED_TRUE_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("manual_or_visible_delivery", ("prompt_delivery", "manual_or_visible_delivery"), "the start message was delivered through a visible TUI path"),
    ("prompt_public_safe", ("prompt_delivery", "prompt_public_safe"), "the delivered prompt was public-safe"),
    ("goal_id_visible", ("first_response", "goal_id_visible"), "the first response showed the current goal id"),
    ("user_gate_or_none_visible", ("first_response", "user_gate_or_none_visible"), "the first response showed the concrete user gate or that none blocks the path"),
    ("top_user_todo_or_none_visible", ("first_response", "top_user_todo_or_none_visible"), "the first response showed the top user todo or that none exists"),
    ("top_agent_todo_visible", ("first_response", "top_agent_todo_visible"), "the first response showed the selected agent todo"),
    ("next_safe_action_visible", ("first_response", "next_safe_action_visible"), "the first response showed the next safe action"),
    ("bounded_segment_started_or_blocker_written", ("first_response", "bounded_segment_started_or_blocker_written"), "the first response either started one bounded segment or wrote a precise blocker"),
    ("user_can_interrupt", ("interruptibility", "user_can_interrupt"), "the user can interrupt the visible TUI path"),
    ("manual_takeover_available", ("interruptibility", "manual_takeover_available"), "manual takeover remains available"),
    ("compact_evidence_planned", ("writeback", "compact_evidence_planned"), "compact evidence writeback is planned before quota spend"),
    ("quota_spend_after_writeback_only", ("writeback", "quota_spend_after_writeback_only"), "quota spend happens only after validated writeback"),
)


FIRST_RESPONSE_REQUIRED_FALSE_CHECKS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("no_argv_prompt", ("prompt_delivery", "argv_prompt_used"), "the start prompt was not passed as a process argv prompt"),
    ("no_raw_transcript_read", ("boundary", "reads_raw_transcripts"), "raw transcripts were not read"),
    ("no_session_files_read", ("boundary", "reads_session_files"), "session files were not read"),
    ("no_stdout_stderr_read", ("boundary", "reads_stdout_stderr"), "stdout/stderr streams were not read"),
    ("no_credentials_read", ("boundary", "reads_credentials"), "credentials were not read"),
    ("no_hidden_session_mutation", ("boundary", "mutates_hidden_session_state"), "hidden session state was not mutated"),
    ("no_quota_spend_before_writeback", ("boundary", "spends_quota_before_writeback"), "quota was not spent before writeback"),
)


def build_codex_cli_runtime_idle_observation_payload(
    *,
    observed_surface: str,
    turn_state: str,
    human_input_idle_seconds: float | None,
    min_human_input_idle_seconds: float,
    checked_before_prompt: bool,
    visible_to_user: bool,
    user_can_interrupt: bool,
    manual_takeover_available: bool,
    probe_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert public-safe local idle observations into detector input."""

    idle_seconds_known = human_input_idle_seconds is not None
    no_active_human_typing = bool(
        idle_seconds_known and human_input_idle_seconds >= min_human_input_idle_seconds
    )
    no_running_turn = turn_state == "idle"
    return {
        "observed_surface": observed_surface,
        "source": "local_runtime_observation",
        "runtime_observation": {
            "schema_version": "codex_cli_runtime_idle_observation_v0",
            "human_input_idle_seconds": human_input_idle_seconds,
            "min_human_input_idle_seconds": min_human_input_idle_seconds,
            "human_input_idle_source": (probe_result or {}).get("source") or "provided",
            "human_input_idle_probe_ok": (probe_result or {}).get("ok"),
            "turn_state": turn_state,
            "turn_state_source": "public_safe_local_observation",
            "cannot_prove_unknown_turn_state": turn_state == "unknown",
        },
        "idle_guard": {
            "no_active_human_typing": no_active_human_typing,
            "no_running_turn": no_running_turn,
            "checked_before_prompt": checked_before_prompt,
        },
        "turn_visibility": {"visible_to_user": visible_to_user},
        "interruptibility": {
            "user_can_interrupt": user_can_interrupt,
            "manual_takeover_available": manual_takeover_available,
        },
        "boundary": {
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_hidden_session_state": False,
        },
    }


def build_codex_cli_runtime_idle_detector(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    idle_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate public-safe runtime idle evidence before a visible later turn.

    This is not a Codex session inspector. It accepts either a reproducible
    public-safe fixture or a narrow local observation payload. Both paths prove
    the two product-critical facts for later visible turns: the user is not
    typing, and Codex is not already running a turn. The detector intentionally
    does not read transcripts, session files, stdout/stderr, credentials, or
    hidden runtime state.
    """

    resolved_project = str(project.expanduser())
    resolved_goal_id = goal_id or default_goal_id(project)
    required_fixture_shape = {
        "observed_surface": "visible_resume_prompt | remote_control_visible_prompt | same_tui_visible_attach | codex_cli_tui_visible_window",
        "idle_guard": {
            "no_active_human_typing": True,
            "no_running_turn": True,
            "checked_before_prompt": True,
        },
        "turn_visibility": {"visible_to_user": True},
        "interruptibility": {
            "user_can_interrupt": True,
            "manual_takeover_available": True,
        },
        "boundary": {
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_hidden_session_state": False,
        },
    }
    if idle_payload is None:
        return {
            "ok": False,
            "schema_version": "codex_cli_runtime_idle_detector_v0",
            "project": resolved_project,
            "goal_id": resolved_goal_id,
            "agent_id": agent_id,
            "cli_bin": cli_bin,
            "source": "idle_evidence_required",
            "decision": "runtime_idle_evidence_required",
            "approved_for_visible_later_turn": False,
            "recommended_action": "capture public-safe runtime idle evidence before steering a later visible Codex CLI turn",
            "required_fixture_shape": required_fixture_shape,
            "checks": [],
            "failures": ["missing_runtime_idle_evidence"],
            "boundary": {
                "fixture_only": False,
                "public_safe_fixture_supported": True,
                "local_observation_adapter_supported": True,
                "runs_codex": False,
                "reads_raw_transcripts": False,
                "reads_session_files": False,
                "reads_stdout_stderr": False,
                "reads_credentials": False,
                "mutates_codex_session": False,
                "spends_loopx_quota": False,
            },
        }

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    for key, path, description in RUNTIME_IDLE_REQUIRED_TRUE_CHECKS:
        passed = _nested_bool(idle_payload, path)
        checks.append({"key": key, "required": True, "passed": passed, "description": description})
        if not passed:
            failures.append(key)
    for key, path, description in RUNTIME_IDLE_REQUIRED_FALSE_CHECKS:
        passed = _nested_false(idle_payload, path)
        checks.append({"key": key, "required": False, "passed": passed, "description": description})
        if not passed:
            failures.append(key)

    observed_surface = str(idle_payload.get("observed_surface") or "unknown")
    supported_surface = observed_surface in {
        "visible_resume_prompt",
        "remote_control_visible_prompt",
        "same_tui_visible_attach",
        "codex_cli_tui_visible_window",
    }
    checks.append(
        {
            "key": "supported_observed_surface",
            "required": sorted(
                [
                    "codex_cli_tui_visible_window",
                    "remote_control_visible_prompt",
                    "same_tui_visible_attach",
                    "visible_resume_prompt",
                ]
            ),
            "actual": observed_surface,
            "passed": supported_surface,
            "description": "idle evidence was captured from a visible Codex CLI surface",
        }
    )
    if not supported_surface:
        failures.append("unsupported_observed_surface")

    approved = not failures
    if approved:
        decision = "runtime_idle_detector_passed"
        recommended_action = "allow a later visible Codex CLI turn only after a fresh quota guard"
    else:
        decision = "runtime_idle_detector_incomplete"
        recommended_action = "keep the TUI bootstrap path visible and do not steer a later turn yet"

    source = str(idle_payload.get("source") or "idle_fixture")
    local_observation = source == "local_runtime_observation"
    return {
        "ok": True,
        "schema_version": "codex_cli_runtime_idle_detector_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "source": source,
        "observed_surface": observed_surface,
        "runtime_observation": idle_payload.get("runtime_observation"),
        "decision": decision,
        "approved_for_visible_later_turn": approved,
        "recommended_action": recommended_action,
        "checks": checks,
        "failures": failures,
        "boundary": {
            "fixture_only": not local_observation,
            "public_safe_fixture_supported": True,
            "local_observation_adapter_supported": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_codex_session": False,
            "spends_loopx_quota": False,
        },
    }


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
                "spends_loopx_quota": False,
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
            "keep TUI bootstrap primary; do not treat this as same-session automation"
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
            "spends_loopx_quota": False,
        },
    }


def build_codex_cli_visible_attach_acceptance(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    proof_payload: dict[str, Any] | None = None,
    idle_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide whether evidence is strong enough for same-TUI visible attach.

    This packet is an acceptance gate, not an executor. It deliberately keeps
    Codex CLI `resume` / `remote-control` surfaces in a spike lane unless a
    public-safe proof shows a visible same-TUI attach and a fresh idle detector
    proves the later turn is not racing the user or an existing turn.
    """

    local_plan = build_codex_cli_local_driver_plan(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
    )
    visible_plan = (
        local_plan.get("visible_driver_plan")
        if isinstance(local_plan.get("visible_driver_plan"), dict)
        else {}
    )
    proof = build_codex_cli_visible_session_proof(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        proof_payload=proof_payload,
    )
    idle_detector = build_codex_cli_runtime_idle_detector(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        idle_payload=idle_payload,
    )
    resolved_project = str(local_plan["project"])
    resolved_goal_id = str(local_plan["goal_id"])
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    common_args = (
        f"--project {_shell_arg(resolved_project)} "
        f"--goal-id {_shell_arg(resolved_goal_id)}{agent_arg} "
        f"--codex-bin {_shell_arg(codex_bin)}"
    )
    proof_approved = proof.get("approved_for_same_session_automation") is True
    idle_approved = idle_detector.get("approved_for_visible_later_turn") is True
    observed_surface = str(proof.get("observed_surface") or "unknown")
    driver_mode = str(local_plan.get("driver_mode") or "tui_bootstrap_only")
    same_tui_proof = proof_approved and observed_surface == "same_tui_visible_attach"
    accepted_same_tui = same_tui_proof and idle_approved
    visible_later_turn_candidate = proof_approved and idle_approved

    blockers: list[str] = []
    if accepted_same_tui:
        decision = "same_tui_visible_attach_accepted"
        acceptance_action = "allow_opt_in_same_tui_visible_turn_after_fresh_quota_guard"
        next_safe_step = (
            "wire the proven same-TUI visible attach primitive behind a fresh "
            "quota guard, runtime idle detector, and explicit command boundary"
        )
    elif proof_approved and idle_approved:
        decision = "visible_surface_spike_passed_not_same_tui"
        acceptance_action = "keep_visible_surface_as_spike_candidate_not_same_tui_attach"
        blockers.append("same_tui_visible_attach_not_proven")
        next_safe_step = (
            "keep one-message TUI bootstrap primary; treat the proven visible "
            "resume/remote-control surface as an opt-in spike until same-TUI "
            "attachment is demonstrated"
        )
    elif proof_approved:
        decision = "runtime_idle_evidence_required"
        acceptance_action = "capture_runtime_idle_evidence_before_later_visible_turn"
        blockers.extend(idle_detector.get("failures") or ["runtime_idle_evidence_missing"])
        next_safe_step = (
            "capture a public-safe runtime idle fixture or local observation "
            "before any later visible Codex CLI prompt"
        )
    elif driver_mode in {"session_attached_visible_turn", "visible_resume_or_remote_control_spike"}:
        decision = "visible_session_proof_required"
        acceptance_action = "capture_public_safe_visible_session_proof"
        if proof_payload is None:
            blockers.append("visible_session_proof_missing")
        else:
            blockers.extend(proof.get("failures") or ["visible_session_proof_incomplete"])
        next_safe_step = (
            "do not call this accepted automation yet; first prove visibility, "
            "interruptibility, boundaries, and compact writeback planning"
        )
    else:
        decision = "tui_bootstrap_only"
        acceptance_action = "ask_user_to_start_inside_codex_cli_tui"
        blockers.append("codex_cli_attach_surface_not_exposed_by_probe")
        next_safe_step = (
            "ask the user to start in Codex CLI TUI and paste the bootstrap message; "
            "headless codex exec is disabled for this product path"
        )

    commands = (
        local_plan.get("commands")
        if isinstance(local_plan.get("commands"), dict)
        else {}
    )
    return {
        "ok": True,
        "schema_version": "codex_cli_visible_attach_acceptance_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "decision": decision,
        "acceptance_action": acceptance_action,
        "accepted_for_same_tui_automation": accepted_same_tui,
        "accepted_for_visible_later_turn": visible_later_turn_candidate,
        "observed_surface": observed_surface,
        "driver_mode": driver_mode,
        "next_safe_step": next_safe_step,
        "blockers": blockers,
        "requirements": {
            "help_probe_required": True,
            "public_safe_visible_session_proof_required": True,
            "runtime_idle_detector_required": True,
            "same_tui_surface_required_for_same_tui_acceptance": True,
            "fresh_quota_guard_required_before_execution": True,
            "headless_execution_disabled": True,
        },
        "probe": {
            "schema_version": probe_payload.get("schema_version"),
            "source": probe_payload.get("source"),
            "recommended_mode": probe_payload.get("recommended_mode"),
            "capabilities": probe_payload.get("capabilities"),
            "warnings": probe_payload.get("warnings") or [],
        },
        "visible_driver_plan": {
            "schema_version": visible_plan.get("schema_version"),
            "driver_mode": visible_plan.get("driver_mode"),
            "automation_action": visible_plan.get("automation_action"),
            "next_step": visible_plan.get("next_step"),
        },
        "visible_session_proof": {
            "supplied": proof_payload is not None,
            "approved": proof_approved,
            "decision": proof.get("decision"),
            "observed_surface": proof.get("observed_surface"),
            "failures": proof.get("failures") or [],
        },
        "runtime_idle_detector": {
            "supplied": idle_payload is not None,
            "approved": idle_approved,
            "decision": idle_detector.get("decision"),
            "failures": idle_detector.get("failures") or [],
            "source": idle_detector.get("source"),
        },
        "commands": {
            "session_probe": f"{_shell_arg(cli_bin)} codex-cli-session-probe --codex-bin {_shell_arg(codex_bin)}",
            "local_driver_plan": commands.get("local_driver_plan"),
            "visible_driver_plan": commands.get("visible_driver_plan"),
            "visible_attach_acceptance": (
                f"{_shell_arg(cli_bin)} codex-cli-visible-attach-acceptance {common_args} "
                "--proof-fixture <public-visible-proof.json> --idle-fixture <public-runtime-idle.json>"
            ),
            "visible_session_proof": (
                f"{_shell_arg(cli_bin)} codex-cli-visible-session-proof "
                f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
                f"{agent_arg} --proof-fixture <public-visible-proof.json>"
            ),
            "runtime_idle_detector_fixture": (
                f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
                f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
                f"{agent_arg} --idle-fixture <public-runtime-idle.json>"
            ),
            "tui_bootstrap_message": commands.get("tui_bootstrap_message"),
            "explicit_headless_fallback": None,
            "headless_fallback_disabled": commands.get("headless_fallback_disabled"),
        },
        "boundary": {
            "acceptance_packet_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "mutates_codex_session": False,
            "spends_loopx_quota": False,
            "writes_loopx_state": False,
            "requires_fresh_quota_guard_before_execution": True,
            "headless_execution_disabled": True,
        },
        "warnings": list(probe_payload.get("warnings") or []),
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
    control spike, or keep the one-message TUI bootstrap as the product path.
    """

    resolved_project = str(project.expanduser())
    resolved_goal_id = goal_id or default_goal_id(project)
    capabilities = probe_payload.get("capabilities") if isinstance(probe_payload.get("capabilities"), dict) else {}
    safe_injection_supported = bool(capabilities.get("safe_injection_supported"))
    visible_resume_supported = bool(capabilities.get("visible_resume_supported"))
    remote_control_supported = bool(capabilities.get("remote_control_surface_detected"))
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    quota_guard_command = (
        f"{_shell_arg(cli_bin)} --format json quota should-run "
        f"--goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
    )
    bootstrap_command = (
        f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
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
    else:
        driver_mode = "tui_bootstrap_only"
        automation_action = "ask_user_to_start_inside_codex_cli_tui"
        next_step = "ask the user to start in Codex CLI TUI and paste the bootstrap message; headless fallback is disabled"

    driver_steps = [
        "run the session probe and quota guard before any delivery turn",
        "if user_channel.action_required=true, surface only the concrete user gate",
        "if delivery is allowed, verify idle_guard before any visible prompt",
        "prefer a visible same-TUI turn; otherwise keep the one-message TUI bootstrap as the product path",
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
            "explicit_headless_fallback": None,
            "headless_fallback_disabled": "headless codex exec is disabled for the default LoopX setup-then-goal bootstrap path",
        },
        "driver_steps": driver_steps,
        "boundary": {
            "dry_run_plan_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_loopx_quota": False,
            "requires_idle_guard_before_visible_prompt": True,
            "requires_user_gate_stop": True,
            "headless_execution_disabled": True,
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
    one-message TUI bootstrap, visible-driver plan, quota guard, and the
    headless-disabled boundary into one operator-facing decision packet.
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
        "--registry \"$HOME/.codex/loopx/registry.global.json\" "
        f"quota should-run --goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
    )
    bootstrap_command = (
        f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
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
    else:
        decision = "ask_user_to_start_from_tui"
        operator_instruction = (
            "Ask the user to start inside Codex CLI TUI and paste the bootstrap message; "
            "headless codex exec is disabled for this product path."
        )

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
            "explicit_headless_fallback": None,
            "headless_fallback_disabled": "headless codex exec is disabled for the default LoopX setup-then-goal bootstrap path",
        },
        "driver_steps": [
            "run quota_guard and stop when user_channel.action_required=true",
            "run visible_driver_plan to classify TUI, resume, or remote-control mode",
            "verify idle_guard before any visible resume or remote-control prompt",
            "prefer one-message TUI bootstrap until visible attach is proven",
            "do not offer headless codex exec from the default LoopX setup-then-goal bootstrap path",
            "write back compact evidence or a precise blocker before quota spend",
        ],
        "idle_guard": {
            "required": True,
            "implemented": False,
            "placeholder": "future driver must prove no active human typing and no running turn before visible resume or remote-control prompt",
        },
        "execution_policy": {
            "tui_bootstrap_primary": True,
            "headless_execution_disabled": True,
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
            "spends_loopx_quota": False,
            "requires_idle_guard_before_visible_prompt": True,
            "requires_user_gate_stop": True,
            "headless_execution_disabled": True,
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
    driver plan and optional visible-session proof into the next safe command
    boundary for a local scheduler or human operator. Headless fallback remains
    disabled for this default LoopX setup-then-goal bootstrap path.
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
    else:
        decision = "tui_bootstrap_only"
        next_driver_action = "ask_user_to_start_inside_codex_cli_tui"
        recommended_command = commands.get("tui_bootstrap_message")

    driver_steps = [
        "run quota_guard and stop if user_channel.action_required=true",
        "stop or relocate if workspace_guard blocks the current checkout",
        "use a visible session only when proof_approved=true and an idle guard passes",
        "do not use headless codex exec from the default LoopX setup-then-goal bootstrap path",
        "after the Codex turn, validate evidence or blocker before refresh-state",
        "spend quota exactly once after validated writeback, never for this packet alone",
    ]
    warnings = list(local_plan.get("warnings") or [])
    if allow_headless_fallback:
        warnings.append(
            "allow_headless_fallback was ignored because headless fallback is disabled for the default LoopX setup-then-goal bootstrap path."
        )

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
            "explicit_headless_fallback": None,
            "headless_fallback_disabled": commands.get("headless_fallback_disabled"),
        },
        "driver_steps": driver_steps,
        "execution_policy": {
            "tui_bootstrap_primary": True,
            "same_session_attachment_requires_visible_proof": True,
            "headless_execution_disabled": True,
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
            "spends_loopx_quota": False,
            "requires_user_gate_stop": True,
            "headless_execution_disabled": True,
        },
        "warnings": warnings,
    }


def _scheduler_label(goal_id: str, agent_id: str | None) -> str:
    raw = f"{goal_id}-{agent_id or 'agent'}"
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    safe = "-".join(part for part in safe.split("-") if part)
    return f"com.loopx.codex-cli.{safe}"


def build_codex_cli_local_scheduler_tick(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
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


def build_codex_cli_one_message_loop_pilot(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    proof_payload: dict[str, Any] | None = None,
    idle_payload: dict[str, Any] | None = None,
    allow_headless_fallback: bool = False,
) -> dict[str, Any]:
    """Compose the first-message TUI path with the safe scheduler bridge."""

    bootstrap = build_codex_cli_bootstrap_message(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
    )
    resolved_project = str(bootstrap["project"])
    resolved_goal_id = str(bootstrap["goal_id"])
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    common_args = (
        f"--project {_shell_arg(resolved_project)} "
        f"--goal-id {_shell_arg(resolved_goal_id)}{agent_arg} "
        f"--codex-bin {_shell_arg(codex_bin)}"
    )
    scheduler_executor = build_codex_cli_local_scheduler_executor(
        project=project,
        goal_id=resolved_goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=allow_headless_fallback,
        execute_candidate=False,
        execute_blocker_writeback=False,
    )
    scheduler_action = str(scheduler_executor.get("scheduler_action") or "")
    scheduler_tick = (
        scheduler_executor.get("scheduler_tick")
        if isinstance(scheduler_executor.get("scheduler_tick"), dict)
        else {}
    )
    scheduler_blocker = (
        scheduler_tick.get("precise_blocker")
        if isinstance(scheduler_tick.get("precise_blocker"), dict)
        else {}
    )
    scheduler_blocker_reason = str(scheduler_blocker.get("reason") or "")
    if scheduler_action == "external_visible_command_candidate":
        pilot_decision = "first_message_then_candidate_available"
        followup_mode = "local scheduler can show the candidate, but execution still requires guard and prefix opt-in"
    elif scheduler_action == "write_precise_blocker" and scheduler_blocker_reason.startswith("runtime_idle_"):
        pilot_decision = "first_message_then_runtime_idle_required"
        followup_mode = (
            "local scheduler must capture public-safe runtime idle observation before later visible automation"
        )
    elif scheduler_action == "write_precise_blocker":
        pilot_decision = "first_message_then_visible_blocker_writeback"
        followup_mode = "local scheduler can write the precise blocker after explicit guard-checked opt-in"
    else:
        pilot_decision = "first_message_tui_bootstrap_only"
        followup_mode = "keep the TUI bootstrap as the product path until a visible proof exists"

    bootstrap_command = (
        f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
    )
    scheduler_exec_dry_run_command = (
        f"{_shell_arg(cli_bin)} codex-cli-local-scheduler-exec {common_args}"
        " --observe-local-runtime --observed-surface visible_resume_prompt "
        "--turn-state idle --probe-human-input-idle --checked-before-prompt "
        "--visible-to-user --user-can-interrupt --manual-takeover-available"
    )
    candidate_execute_template = (
        f"{scheduler_exec_dry_run_command} --guard-checked --execute-candidate "
        "--candidate-command-prefix <allowed-prefix>"
    )
    blocker_execute_template = (
        f"{scheduler_exec_dry_run_command} --guard-checked --execute-blocker-writeback"
    )
    return {
        "ok": True,
        "schema_version": "codex_cli_one_message_loop_pilot_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "pilot_decision": pilot_decision,
        "followup_mode": followup_mode,
        "start_surface": "codex_cli_tui_one_message",
        "first_turn": {
            "user_action": "paste_bootstrap_message_into_codex_cli_tui",
            "autostarts_loopx_loop": True,
            "setup_then_loop_activation": True,
            "preserve_tui": True,
            "loop_activation": {
                "source_command": bootstrap.get("heartbeat_prompt_json_command"),
                "codex_cli": "/goal <thin task_body>",
                "codex_app": "<thin task_body> heartbeat automation",
            },
            "stop_only_for": [
                "concrete_user_gate",
                "workspace_guard",
                "missing_capability",
                "missing_installation_primitive",
                "unsafe_boundary",
            ],
            "message": bootstrap.get("message"),
            "snapshot_required": [
                "current goal id",
                "concrete user gate or none",
                "top user todo or none",
                "top agent todo",
                "next safe action",
            ],
        },
        "later_turn_contract": {
            "preserve_visible_tui": True,
            "visible_steering_requires": [
                "public_safe_visible_session_proof",
                "runtime_idle_evidence",
                "fresh_quota_guard",
                "guard_checked",
                "explicit_execution_bounds",
            ],
            "default_without_proof": "write_blocker_or_keep_tui_bootstrap_primary",
        },
        "automation_bridge": {
            "command": "codex-cli-local-scheduler-exec",
            "default_executes": False,
            "scheduler_action": scheduler_action,
            "executor_reason": (scheduler_executor.get("execution") or {}).get("reason")
            if isinstance(scheduler_executor.get("execution"), dict)
            else None,
            "followup_mode": followup_mode,
        },
        "commands": {
            "bootstrap_message": bootstrap_command,
            "scheduler_exec_dry_run": scheduler_exec_dry_run_command,
            "scheduler_exec_candidate_template": candidate_execute_template,
            "scheduler_exec_blocker_template": blocker_execute_template,
        },
        "bootstrap_message": {
            "schema_version": bootstrap.get("schema_version"),
            "invocation_mode": bootstrap.get("invocation_mode"),
            "heartbeat_prompt_json_command": bootstrap.get("heartbeat_prompt_json_command"),
            "quota_guard_command": bootstrap.get("quota_guard_command"),
            "refresh_command": bootstrap.get("refresh_command"),
            "quota_spend_command": bootstrap.get("quota_spend_command"),
        },
        "scheduler_executor": scheduler_executor,
        "boundary": {
            "pilot_packet_only": True,
            "runs_codex": False,
            "runs_scheduler_result": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_loopx_quota": False,
            "requires_user_visible_start": True,
            "headless_execution_disabled": True,
            "candidate_execution_requires_guard_and_prefix": True,
        },
        "warnings": list(scheduler_executor.get("warnings") or []),
    }


def build_codex_cli_visible_local_driver_pilot(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
    probe_payload: dict[str, Any],
    proof_payload: dict[str, Any] | None = None,
    idle_payload: dict[str, Any] | None = None,
    allow_headless_fallback: bool = False,
) -> dict[str, Any]:
    """Prototype the visible local driver loop without executing Codex.

    This composes the first visible TUI bootstrap, a no-execution scheduler
    wrapper, and the public-safe proof boundary a returning user would need
    before LoopX can steer later visible turns.
    """

    one_message = build_codex_cli_one_message_loop_pilot(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=allow_headless_fallback,
    )
    scheduler_executor = (
        one_message.get("scheduler_executor")
        if isinstance(one_message.get("scheduler_executor"), dict)
        else {}
    )
    scheduler_tick = (
        scheduler_executor.get("scheduler_tick")
        if isinstance(scheduler_executor.get("scheduler_tick"), dict)
        else {}
    )
    execution = (
        scheduler_executor.get("execution")
        if isinstance(scheduler_executor.get("execution"), dict)
        else {}
    )
    resolved_project = str(one_message["project"])
    resolved_goal_id = str(one_message["goal_id"])
    scheduler_action = str(scheduler_executor.get("scheduler_action") or "")
    scheduler_blocker = (
        scheduler_tick.get("precise_blocker")
        if isinstance(scheduler_tick.get("precise_blocker"), dict)
        else {}
    )
    scheduler_blocker_reason = str(scheduler_blocker.get("reason") or "")
    proof = (
        scheduler_tick.get("visible_session_proof")
        if isinstance(scheduler_tick.get("visible_session_proof"), dict)
        else {}
    )
    proof_approved = bool(proof.get("approved") is True)
    idle_detector = build_codex_cli_runtime_idle_detector(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        idle_payload=idle_payload,
    )
    idle_approved = bool(idle_detector.get("approved_for_visible_later_turn") is True)
    idle_detector_command = (
        f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{' --agent-id ' + _shell_arg(agent_id) if agent_id else ''} "
        "--observe-local-runtime --observed-surface visible_resume_prompt "
        "--turn-state idle --probe-human-input-idle --checked-before-prompt "
        "--visible-to-user --user-can-interrupt --manual-takeover-available"
    )
    idle_fixture_detector_command = (
        f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{' --agent-id ' + _shell_arg(agent_id) if agent_id else ''} "
        "--idle-fixture <public-runtime-idle.json>"
    )

    if proof_approved and scheduler_action == "external_visible_command_candidate" and idle_approved:
        loop_decision = "visible_candidate_ready_for_guarded_execution"
        next_driver_action = "run_scheduler_exec_candidate_after_fresh_guard_and_prefix"
    elif proof_approved and (
        scheduler_action == "external_visible_command_candidate"
        or scheduler_blocker_reason.startswith("runtime_idle_")
    ):
        loop_decision = "runtime_idle_detector_required"
        next_driver_action = "capture_public_safe_runtime_idle_observation"
    elif scheduler_action == "write_precise_blocker":
        loop_decision = "visible_loop_blocker_writeback_ready"
        next_driver_action = "write_precise_blocker_after_fresh_guard"
    elif scheduler_action == "surface_tui_bootstrap":
        loop_decision = "surface_tui_bootstrap_only"
        next_driver_action = "keep_first_message_tui_path_visible"
    else:
        loop_decision = "review_scheduler_packet_before_execution"
        next_driver_action = "inspect_scheduler_executor_packet"

    commands = one_message.get("commands") if isinstance(one_message.get("commands"), dict) else {}
    scheduler_commands = (
        scheduler_executor.get("commands")
        if isinstance(scheduler_executor.get("commands"), dict)
        else {}
    )
    visible_loop_steps = [
        "start from the visible Codex CLI TUI with the one-message bootstrap",
        "run quota should-run with the registered agent id before each scheduler tick",
        "stop on interaction_contract.user_channel.action_required=true and show the concrete user todo",
        "require public-safe local idle observation or a fixture before any visible resume, remote-control, or same-TUI prompt",
        "run codex-cli-local-scheduler-exec as dry-run unless guard and explicit execution flags are present",
        "for a visible candidate, require guard_checked plus an allowed candidate command prefix",
        "for a blocker, write compact LoopX state only after guard_checked",
        "never read raw transcripts, session files, credentials, stdout, or stderr for this pilot",
    ]

    return {
        "ok": True,
        "schema_version": "codex_cli_visible_local_driver_pilot_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "pilot_phase": "visible_local_driver_loop_no_execution",
        "start_surface": "codex_cli_tui_one_message",
        "loop_decision": loop_decision,
        "next_driver_action": next_driver_action,
        "one_message_pilot": {
            "schema_version": one_message.get("schema_version"),
            "pilot_decision": one_message.get("pilot_decision"),
            "start_surface": one_message.get("start_surface"),
            "followup_mode": one_message.get("followup_mode"),
        },
        "scheduler_executor": {
            "schema_version": scheduler_executor.get("schema_version"),
            "scheduler_action": scheduler_action,
            "decision": scheduler_executor.get("decision"),
            "executor_reason": execution.get("reason"),
            "executed": execution.get("executed"),
        },
        "visible_session_proof": {
            "supplied": bool(proof.get("supplied")),
            "approved": proof_approved,
            "decision": proof.get("decision"),
            "failures": proof.get("failures") or [],
        },
        "runtime_idle_detector": {
            "supplied": idle_payload is not None,
            "approved": idle_approved,
            "decision": idle_detector.get("decision"),
            "failures": idle_detector.get("failures") or [],
            "command": idle_detector_command,
        },
        "idle_guard_contract": {
            "required_before_visible_prompt": True,
            "fixture_keys": [
                "idle_guard.no_active_human_typing",
                "idle_guard.no_running_turn",
                "idle_guard.checked_before_prompt",
                "turn_visibility.visible_to_user",
                "interruptibility.user_can_interrupt",
                "interruptibility.manual_takeover_available",
            ],
            "current_pilot_implements_runtime_idle_detection": True,
            "fixture_backed_runtime_idle_detector": True,
            "runtime_sensor_implemented": True,
            "public_safe_fixture_supported": True,
            "local_observation_adapter_supported": True,
            "no_private_state_observation": True,
        },
        "visible_loop_steps": visible_loop_steps,
        "commands": {
            "bootstrap_message": commands.get("bootstrap_message"),
            "scheduler_exec_dry_run": commands.get("scheduler_exec_dry_run"),
            "scheduler_exec_candidate_template": commands.get("scheduler_exec_candidate_template"),
            "scheduler_exec_blocker_template": commands.get("scheduler_exec_blocker_template"),
            "scheduler_tick": scheduler_commands.get("scheduler_tick"),
            "candidate_command": scheduler_commands.get("candidate_command"),
            "blocker_writeback": scheduler_commands.get("blocker_writeback"),
            "runtime_idle_detector": idle_detector_command,
            "runtime_idle_detector_fixture": idle_fixture_detector_command,
        },
        "execution_policy": {
            "tui_bootstrap_primary": True,
            "later_turns_visible_to_user": True,
            "user_can_interrupt_or_take_over": True,
            "same_session_attachment_requires_visible_proof": True,
            "headless_execution_disabled": True,
            "quota_guard_required_each_tick": True,
            "spend_after_validated_writeback_only": True,
        },
        "boundary": {
            "pilot_packet_only": True,
            "runs_codex": False,
            "runs_scheduler_result": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "mutates_codex_session": False,
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "requires_fresh_guard_before_execution": True,
            "candidate_execution_requires_guard_and_prefix": True,
            "blocker_writeback_requires_guard_checked": True,
            "headless_execution_disabled": True,
        },
        "warnings": [
            *list(one_message.get("warnings") or []),
            *(
                ["Runtime idle detector must pass before a later visible Codex CLI turn can run."]
                if proof_approved and not idle_approved
                else []
            ),
        ],
    }


def build_codex_cli_visible_first_response_capture_plan(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    first_response_path: str = "public-first-response.json",
    idle_path: str = "public-runtime-idle.json",
) -> dict[str, Any]:
    """Describe the safest public fixture capture path for visible TUI bootstrap.

    This is deliberately a plan packet. It does not start Codex, read terminal
    buffers, inspect session files, or write fixtures. A human-visible TUI run
    supplies the observations, and the bounded visible adapter validates the
    resulting public-safe JSON before any success claim or quota spend.
    """

    adapter = build_codex_cli_bounded_visible_pilot_adapter(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
    )
    resolved_project = str(adapter["project"])
    resolved_goal_id = str(adapter["goal_id"])
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    first_response_fixture = {
        "observed_surface": "codex_cli_tui_visible_window",
        "prompt_delivery": {
            "manual_or_visible_delivery": True,
            "prompt_public_safe": True,
            "argv_prompt_used": False,
        },
        "first_response": {
            "goal_id_visible": True,
            "user_gate_or_none_visible": True,
            "top_user_todo_or_none_visible": True,
            "top_agent_todo_visible": True,
            "next_safe_action_visible": True,
            "bounded_segment_started_or_blocker_written": True,
        },
        "interruptibility": {
            "user_can_interrupt": True,
            "manual_takeover_available": True,
        },
        "writeback": {
            "compact_evidence_planned": True,
            "quota_spend_after_writeback_only": True,
        },
        "boundary": {
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_hidden_session_state": False,
            "spends_quota_before_writeback": False,
        },
    }
    runtime_idle_fixture = {
        "observed_surface": "codex_cli_tui_visible_window",
        "idle_guard": {
            "no_active_human_typing": True,
            "no_running_turn": True,
            "checked_before_prompt": True,
        },
        "turn_visibility": {"visible_to_user": True},
        "interruptibility": {
            "user_can_interrupt": True,
            "manual_takeover_available": True,
        },
        "boundary": {
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_hidden_session_state": False,
        },
    }
    first_response_checklist = [
        {
            "key": key,
            "required": True,
            "description": description,
            "path": ".".join(path),
        }
        for key, path, description in FIRST_RESPONSE_REQUIRED_TRUE_CHECKS
    ] + [
        {
            "key": key,
            "required": False,
            "description": description,
            "path": ".".join(path),
        }
        for key, path, description in FIRST_RESPONSE_REQUIRED_FALSE_CHECKS
    ]
    runtime_idle_checklist = [
        {
            "key": key,
            "required": True,
            "description": description,
            "path": ".".join(path),
        }
        for key, path, description in RUNTIME_IDLE_REQUIRED_TRUE_CHECKS
    ] + [
        {
            "key": key,
            "required": False,
            "description": description,
            "path": ".".join(path),
        }
        for key, path, description in RUNTIME_IDLE_REQUIRED_FALSE_CHECKS
    ]
    capture_steps = [
        "Run quota should-run for the goal and stop if a concrete user gate blocks this path.",
        "Open Codex CLI TUI yourself in the project repo; do not pass the bootstrap message as argv.",
        "Paste the generated LoopX bootstrap message into the visible TUI.",
        "Observe only whether the first response exposes the required public-safe fields; do not copy raw text.",
        f"Write those booleans to {first_response_path}.",
        "After the first response or blocker is visible, confirm the TUI is idle and the user is not typing.",
        f"Write those idle booleans to {idle_path}.",
        "Run the bounded visible pilot adapter with both fixtures before claiming success or spending quota.",
    ]
    stop_conditions = [
        "the first response contains private paths, internal project names, credentials, or raw logs",
        "the bootstrap message would have to be passed as argv",
        "the user is typing or Codex is already running a visible turn",
        "the response does not show goal/todo/gate/next-action status clearly enough to fill the fixture",
        "any required boundary boolean would be false",
    ]
    commands = {
        "quota_guard": (
            f"{_shell_arg(cli_bin)} --format json quota should-run "
            f"--goal-id {_shell_arg(resolved_goal_id)}{agent_arg}"
        ),
        "bootstrap_message": (
            f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
            f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
            f"{agent_arg} --message-only"
        ),
        "runtime_idle_detector": (
            f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
            f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
            f"{agent_arg} --idle-fixture {_shell_arg(idle_path)}"
        ),
        "bounded_visible_pilot_adapter": (
            f"{_shell_arg(cli_bin)} codex-cli-bounded-visible-pilot-adapter "
            f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
            f"{agent_arg} --first-response-fixture {_shell_arg(first_response_path)} "
            f"--idle-fixture {_shell_arg(idle_path)}"
        ),
        "capture_plan": (
            f"{_shell_arg(cli_bin)} codex-cli-visible-first-response-capture-plan "
            f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
            f"{agent_arg} --first-response-path {_shell_arg(first_response_path)} "
            f"--idle-path {_shell_arg(idle_path)}"
        ),
    }
    return {
        "ok": True,
        "schema_version": "codex_cli_visible_first_response_capture_plan_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "decision": "manual_visible_capture_plan_ready",
        "start_surface": "codex_cli_tui_manual_paste",
        "next_safe_step": "paste the bootstrap message into a visible Codex CLI TUI and record only public-safe fixture booleans",
        "output_artifacts": {
            "first_response_fixture": first_response_path,
            "runtime_idle_fixture": idle_path,
        },
        "capture_steps": capture_steps,
        "stop_conditions": stop_conditions,
        "first_response_checklist": first_response_checklist,
        "runtime_idle_checklist": runtime_idle_checklist,
        "sample_first_response_fixture": first_response_fixture,
        "sample_runtime_idle_fixture": runtime_idle_fixture,
        "commands": commands,
        "adapter_decision_without_fixtures": adapter.get("decision"),
        "boundary": {
            "capture_plan_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_codex_session": False,
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "requires_visible_delivery": True,
            "manual_paste_primary": True,
            "argv_prompt_rejected": True,
            "success_claim_requires_bounded_adapter": True,
        },
    }


def build_codex_cli_bounded_visible_pilot_adapter(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    first_response_payload: dict[str, Any] | None = None,
    idle_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the bounded evidence needed before claiming live TUI success.

    The adapter is intentionally a packet builder and fixture validator. It
    does not start Codex, inspect transcripts, read session files, or capture
    stdout/stderr. A separate visible/manual run must supply a public-safe
    first-response fixture and a runtime-idle fixture before this packet can
    approve a live-TUI first-message success claim.
    """

    bootstrap = build_codex_cli_bootstrap_message(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
    )
    resolved_project = str(bootstrap["project"])
    resolved_goal_id = str(bootstrap["goal_id"])
    agent_arg = f" --agent-id {_shell_arg(agent_id)}" if agent_id else ""
    required_first_response_shape = {
        "observed_surface": "codex_cli_tui_visible_window | visible_paste_adapter",
        "prompt_delivery": {
            "manual_or_visible_delivery": True,
            "prompt_public_safe": True,
            "argv_prompt_used": False,
        },
        "first_response": {
            "goal_id_visible": True,
            "user_gate_or_none_visible": True,
            "top_user_todo_or_none_visible": True,
            "top_agent_todo_visible": True,
            "next_safe_action_visible": True,
            "bounded_segment_started_or_blocker_written": True,
        },
        "interruptibility": {
            "user_can_interrupt": True,
            "manual_takeover_available": True,
        },
        "writeback": {
            "compact_evidence_planned": True,
            "quota_spend_after_writeback_only": True,
        },
        "boundary": {
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "reads_credentials": False,
            "mutates_hidden_session_state": False,
            "spends_quota_before_writeback": False,
        },
    }

    first_response_checks: list[dict[str, Any]] = []
    first_response_failures: list[str] = []
    observed_surface = "missing"
    if first_response_payload is None:
        first_response_failures.append("missing_first_response_evidence")
    else:
        observed_surface = str(first_response_payload.get("observed_surface") or "unknown")
        for key, path, description in FIRST_RESPONSE_REQUIRED_TRUE_CHECKS:
            passed = _nested_bool(first_response_payload, path)
            first_response_checks.append(
                {"key": key, "required": True, "passed": passed, "description": description}
            )
            if not passed:
                first_response_failures.append(key)
        for key, path, description in FIRST_RESPONSE_REQUIRED_FALSE_CHECKS:
            passed = _nested_false(first_response_payload, path)
            first_response_checks.append(
                {"key": key, "required": False, "passed": passed, "description": description}
            )
            if not passed:
                first_response_failures.append(key)
        supported_surface = observed_surface in {
            "codex_cli_tui_visible_window",
            "visible_paste_adapter",
        }
        first_response_checks.append(
            {
                "key": "supported_observed_surface",
                "required": sorted(["codex_cli_tui_visible_window", "visible_paste_adapter"]),
                "actual": observed_surface,
                "passed": supported_surface,
                "description": "first response was observed on a visible Codex CLI surface",
            }
        )
        if not supported_surface:
            first_response_failures.append("unsupported_observed_surface")
        if _nested_bool(first_response_payload, ("prompt_delivery", "argv_prompt_used")):
            first_response_failures.append("argv_prompt_leakage_risk")

    idle_detector = build_codex_cli_runtime_idle_detector(
        project=project,
        goal_id=resolved_goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
        idle_payload=idle_payload,
    )
    idle_approved = idle_detector.get("approved_for_visible_later_turn") is True
    first_response_approved = bool(first_response_payload is not None and not first_response_failures)
    blockers: list[str] = []
    blockers.extend(first_response_failures)
    if not idle_approved:
        blockers.extend(idle_detector.get("failures") or ["runtime_idle_evidence_required"])

    if first_response_approved and idle_approved:
        decision = "bounded_visible_pilot_ready_for_success_claim"
        approved = True
        next_safe_step = (
            "write compact success evidence, refresh state with outcome_progress, "
            "then spend exactly one quota slot"
        )
    elif first_response_payload is None:
        decision = "bounded_visible_completion_evidence_required"
        approved = False
        next_safe_step = (
            "capture the first visible TUI response as the public-safe fixture shape "
            "below, then rerun this adapter before spending quota"
        )
    elif not first_response_approved:
        decision = "bounded_visible_first_response_incomplete"
        approved = False
        next_safe_step = (
            "treat the live TUI pilot as blocked and write the precise blocker; "
            "do not claim first-message success"
        )
    else:
        decision = "bounded_visible_runtime_idle_required"
        approved = False
        next_safe_step = (
            "capture runtime idle evidence proving no active typing or running turn "
            "before marking the visible pilot complete"
        )

    bounded_adapter_command = (
        f"{_shell_arg(cli_bin)} codex-cli-bounded-visible-pilot-adapter "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{agent_arg} --first-response-fixture <public-first-response.json> "
        "--idle-fixture <public-runtime-idle.json>"
    )
    runtime_idle_command = (
        f"{_shell_arg(cli_bin)} codex-cli-runtime-idle-detector "
        f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
        f"{agent_arg} --idle-fixture <public-runtime-idle.json>"
    )
    blocker_summary = blockers[0] if blockers else "none"
    blocker_writeback = (
        f"{_shell_arg(cli_bin)} refresh-state --goal-id {_shell_arg(resolved_goal_id)} "
        "--classification codex_cli_bounded_visible_pilot_blocker "
        "--delivery-batch-scale implementation --delivery-outcome outcome_gap "
        f"--recommended-action {_shell_arg('Codex CLI bounded visible pilot blocked: ' + blocker_summary)}"
    )
    success_writeback = (
        f"{_shell_arg(cli_bin)} refresh-state --goal-id {_shell_arg(resolved_goal_id)} "
        "--classification codex_cli_bounded_visible_pilot_success "
        "--delivery-batch-scale implementation --delivery-outcome outcome_progress "
        "--recommended-action "
        f"{_shell_arg('Promote Codex CLI one-message TUI bootstrap only after documented release-path validation.')}"
    )

    return {
        "ok": True,
        "schema_version": "codex_cli_bounded_visible_pilot_adapter_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "decision": decision,
        "approved_for_live_tui_success_claim": approved,
        "observed_surface": observed_surface,
        "next_safe_step": next_safe_step,
        "blockers": blockers,
        "first_response": {
            "supplied": first_response_payload is not None,
            "approved": first_response_approved,
            "checks": first_response_checks,
            "failures": first_response_failures,
        },
        "runtime_idle_detector": {
            "supplied": idle_payload is not None,
            "approved": idle_approved,
            "decision": idle_detector.get("decision"),
            "failures": idle_detector.get("failures") or [],
            "source": idle_detector.get("source"),
        },
        "commands": {
            "bootstrap_message": (
                f"{_shell_arg(cli_bin)} codex-cli-bootstrap-message "
                f"--project {_shell_arg(resolved_project)} --goal-id {_shell_arg(resolved_goal_id)}"
                f"{agent_arg} --message-only"
            ),
            "bounded_visible_pilot_adapter": bounded_adapter_command,
            "runtime_idle_detector": runtime_idle_command,
            "blocker_writeback": blocker_writeback,
            "success_writeback": success_writeback,
        },
        "required_first_response_shape": required_first_response_shape,
        "required_runtime_idle_shape": idle_detector.get("required_fixture_shape"),
        "boundary": {
            "adapter_packet_only": True,
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "reads_stdout_stderr": False,
            "mutates_codex_session": False,
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "requires_visible_delivery": True,
            "argv_prompt_rejected": True,
            "success_claim_requires_first_response_and_idle": True,
        },
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
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`

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
    headless_line = commands.get("explicit_headless_fallback") or (
        f"# {commands.get('headless_fallback_disabled') or 'headless fallback disabled'}"
    )
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
{headless_line}
```

## Driver Steps

{step_lines}

## Boundary

- dry_run_plan_only: `{boundary.get("dry_run_plan_only")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
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
    headless_line = commands.get("explicit_headless_fallback") or (
        f"# {commands.get('headless_fallback_disabled') or 'headless fallback disabled'}"
    )
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
{headless_line}
```

## Driver Steps

{step_lines}

## Idle Guard

- required: `{idle_guard.get("required")}`
- implemented: `{idle_guard.get("implemented")}`
- placeholder: {idle_guard.get("placeholder")}

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- headless_execution_disabled: `{policy.get("headless_execution_disabled")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- quota_guard_required: `{policy.get("quota_guard_required")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- dry_run_plan_only: `{boundary.get("dry_run_plan_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`

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
    headless_line = commands.get("explicit_headless_fallback") or (
        f"# {commands.get('headless_fallback_disabled') or 'headless fallback disabled'}"
    )
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
{headless_line}
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
- headless_execution_disabled: `{policy.get("headless_execution_disabled")}`
- quota_guard_required: `{policy.get("quota_guard_required")}`
- idle_guard_required_before_visible_prompt: `{policy.get("idle_guard_required_before_visible_prompt")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- run_packet_only: `{boundary.get("run_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_local_scheduler_tick_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    launchd = payload.get("launchd") if isinstance(payload.get("launchd"), dict) else {}
    blocker = payload.get("precise_blocker") if isinstance(payload.get("precise_blocker"), dict) else None
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
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
{commands.get("runtime_idle_detector")}
{commands.get("runtime_idle_detector_fixture")}
{commands.get("scheduler_tick")}
{commands.get("candidate_codex_command") or "# no Codex command candidate"}
{commands.get("blocker_writeback") or "# no blocker writeback command"}
```

## Precise Blocker

{blocker_lines}

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

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
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- visible_candidate_requires_runtime_idle_detector: `{boundary.get("visible_candidate_requires_runtime_idle_detector")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_local_scheduler_executor_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    request = payload.get("execution_request") if isinstance(payload.get("execution_request"), dict) else {}
    scheduler_tick = payload.get("scheduler_tick") if isinstance(payload.get("scheduler_tick"), dict) else {}
    runtime_idle = (
        scheduler_tick.get("runtime_idle_detector")
        if isinstance(scheduler_tick.get("runtime_idle_detector"), dict)
        else {}
    )
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Local Scheduler Executor

- executor_phase: `{payload.get("executor_phase")}`
- scheduler_action: `{payload.get("scheduler_action")}`
- decision: `{payload.get("decision")}`
- next_safe_step: {payload.get("next_safe_step")}

## Execution Request

- execute_candidate: `{request.get("execute_candidate")}`
- execute_blocker_writeback: `{request.get("execute_blocker_writeback")}`
- guard_checked: `{request.get("guard_checked")}`
- candidate_command_prefixes: `{request.get("candidate_command_prefixes")}`
- executor_timeout_seconds: `{request.get("executor_timeout_seconds")}`
- runtime_idle_detector_required_for_visible_candidate: `{request.get("runtime_idle_detector_required_for_visible_candidate")}`

## Execution Result

- attempted: `{execution.get("attempted")}`
- executed: `{execution.get("executed")}`
- kind: `{execution.get("kind")}`
- reason: `{execution.get("reason")}`
- returncode: `{execution.get("returncode")}`
- timed_out: `{execution.get("timed_out")}`
- output_captured: `{execution.get("output_captured")}`
- candidate_prefix_matched: `{execution.get("candidate_prefix_matched")}`

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Commands

```bash
{commands.get("scheduler_tick")}
{commands.get("candidate_command") or "# no candidate command"}
{commands.get("blocker_writeback") or "# no blocker writeback command"}
```

## Boundary

- executor_wrapper: `{boundary.get("executor_wrapper")}`
- requires_explicit_execute_flag: `{boundary.get("requires_explicit_execute_flag")}`
- requires_fresh_quota_guard_confirmation: `{boundary.get("requires_fresh_quota_guard_confirmation")}`
- candidate_prefix_required: `{boundary.get("candidate_prefix_required")}`
- runtime_idle_detector_required_for_visible_candidate: `{boundary.get("runtime_idle_detector_required_for_visible_candidate")}`
- runs_external_candidate: `{boundary.get("runs_external_candidate")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- candidate_output_captured: `{boundary.get("candidate_output_captured")}`
- blocker_output_captured: `{boundary.get("blocker_output_captured")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_one_message_loop_pilot_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    first_turn = payload.get("first_turn") if isinstance(payload.get("first_turn"), dict) else {}
    bridge = payload.get("automation_bridge") if isinstance(payload.get("automation_bridge"), dict) else {}
    snapshot_required = first_turn.get("snapshot_required") if isinstance(first_turn.get("snapshot_required"), list) else []
    snapshot_lines = "\n".join(f"- {item}" for item in snapshot_required)
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI One-Message Loop Pilot

- start_surface: `{payload.get("start_surface")}`
- pilot_decision: `{payload.get("pilot_decision")}`
- followup_mode: {payload.get("followup_mode")}

## First TUI Turn

- user_action: `{first_turn.get("user_action")}`
- preserve_tui: `{first_turn.get("preserve_tui")}`

The first response should show:

{snapshot_lines}

````text
{first_turn.get("message") or ""}
````

## Automation Bridge

- command: `{bridge.get("command")}`
- default_executes: `{bridge.get("default_executes")}`
- scheduler_action: `{bridge.get("scheduler_action")}`
- executor_reason: `{bridge.get("executor_reason")}`
- followup_mode: {bridge.get("followup_mode")}

## Commands

```bash
{commands.get("bootstrap_message")}
{commands.get("scheduler_exec_dry_run")}
{commands.get("scheduler_exec_candidate_template")}
{commands.get("scheduler_exec_blocker_template")}
```

## Boundary

- pilot_packet_only: `{boundary.get("pilot_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- runs_scheduler_result: `{boundary.get("runs_scheduler_result")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- requires_user_visible_start: `{boundary.get("requires_user_visible_start")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`
- candidate_execution_requires_guard_and_prefix: `{boundary.get("candidate_execution_requires_guard_and_prefix")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_visible_local_driver_pilot_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    proof = payload.get("visible_session_proof") if isinstance(payload.get("visible_session_proof"), dict) else {}
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    idle_guard = payload.get("idle_guard_contract") if isinstance(payload.get("idle_guard_contract"), dict) else {}
    scheduler = payload.get("scheduler_executor") if isinstance(payload.get("scheduler_executor"), dict) else {}
    policy = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    steps = payload.get("visible_loop_steps") if isinstance(payload.get("visible_loop_steps"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    fixture_keys = idle_guard.get("fixture_keys") if isinstance(idle_guard.get("fixture_keys"), list) else []
    fixture_key_lines = "\n".join(f"- {key}" for key in fixture_keys)
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Visible Local Driver Pilot

- pilot_phase: `{payload.get("pilot_phase")}`
- start_surface: `{payload.get("start_surface")}`
- loop_decision: `{payload.get("loop_decision")}`
- next_driver_action: `{payload.get("next_driver_action")}`

## Scheduler Executor

- scheduler_action: `{scheduler.get("scheduler_action")}`
- decision: `{scheduler.get("decision")}`
- executor_reason: `{scheduler.get("executor_reason")}`
- executed: `{scheduler.get("executed")}`

## Visible Session Proof

- supplied: `{proof.get("supplied")}`
- approved: `{proof.get("approved")}`
- decision: `{proof.get("decision")}`
- failures: `{proof.get("failures")}`

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Idle Guard Contract

- required_before_visible_prompt: `{idle_guard.get("required_before_visible_prompt")}`
- current_pilot_implements_runtime_idle_detection: `{idle_guard.get("current_pilot_implements_runtime_idle_detection")}`
- fixture_backed_runtime_idle_detector: `{idle_guard.get("fixture_backed_runtime_idle_detector")}`
- runtime_sensor_implemented: `{idle_guard.get("runtime_sensor_implemented")}`
- public_safe_fixture_supported: `{idle_guard.get("public_safe_fixture_supported")}`
- local_observation_adapter_supported: `{idle_guard.get("local_observation_adapter_supported")}`
- no_private_state_observation: `{idle_guard.get("no_private_state_observation")}`

{fixture_key_lines}

## Visible Loop Steps

{step_lines}

## Commands

```bash
{commands.get("bootstrap_message")}
{commands.get("scheduler_exec_dry_run")}
{commands.get("scheduler_exec_candidate_template")}
{commands.get("scheduler_exec_blocker_template")}
{commands.get("runtime_idle_detector")}
{commands.get("runtime_idle_detector_fixture")}
```

## Execution Policy

- tui_bootstrap_primary: `{policy.get("tui_bootstrap_primary")}`
- later_turns_visible_to_user: `{policy.get("later_turns_visible_to_user")}`
- user_can_interrupt_or_take_over: `{policy.get("user_can_interrupt_or_take_over")}`
- same_session_attachment_requires_visible_proof: `{policy.get("same_session_attachment_requires_visible_proof")}`
- headless_execution_disabled: `{policy.get("headless_execution_disabled")}`
- quota_guard_required_each_tick: `{policy.get("quota_guard_required_each_tick")}`
- spend_after_validated_writeback_only: `{policy.get("spend_after_validated_writeback_only")}`

## Boundary

- pilot_packet_only: `{boundary.get("pilot_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- runs_scheduler_result: `{boundary.get("runs_scheduler_result")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- candidate_execution_requires_guard_and_prefix: `{boundary.get("candidate_execution_requires_guard_and_prefix")}`
- blocker_writeback_requires_guard_checked: `{boundary.get("blocker_writeback_requires_guard_checked")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`

## Warnings

{warning_lines}
"""


def render_codex_cli_bounded_visible_pilot_adapter_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    first_response = (
        payload.get("first_response")
        if isinstance(payload.get("first_response"), dict)
        else {}
    )
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers) if blockers else "- none"
    checks = first_response.get("checks") if isinstance(first_response.get("checks"), list) else []
    check_lines = "\n".join(
        f"- [{'x' if check.get('passed') else ' '}] {check.get('key')}: {check.get('description')}"
        for check in checks
        if isinstance(check, dict)
    )
    if not check_lines:
        check_lines = "- no first-response fixture supplied"
    required_first_response_shape = payload.get("required_first_response_shape")
    required_runtime_idle_shape = payload.get("required_runtime_idle_shape")
    required_shapes = ""
    if isinstance(required_first_response_shape, dict):
        required_shapes += f"""
## Required First-Response Fixture

```json
{json.dumps(required_first_response_shape, indent=2, ensure_ascii=False)}
```
"""
    if isinstance(required_runtime_idle_shape, dict):
        required_shapes += f"""
## Required Runtime Idle Fixture

```json
{json.dumps(required_runtime_idle_shape, indent=2, ensure_ascii=False)}
```
"""
    return f"""# Codex CLI Bounded Visible Pilot Adapter

- decision: `{payload.get("decision")}`
- approved_for_live_tui_success_claim: `{payload.get("approved_for_live_tui_success_claim")}`
- observed_surface: `{payload.get("observed_surface")}`
- next_safe_step: {payload.get("next_safe_step")}

## First Response

- supplied: `{first_response.get("supplied")}`
- approved: `{first_response.get("approved")}`

{check_lines}

## Runtime Idle Detector

- supplied: `{runtime_idle.get("supplied")}`
- approved: `{runtime_idle.get("approved")}`
- decision: `{runtime_idle.get("decision")}`
- failures: `{runtime_idle.get("failures")}`

## Blockers

{blocker_lines}

## Commands

```bash
{commands.get("bootstrap_message")}
{commands.get("bounded_visible_pilot_adapter")}
{commands.get("runtime_idle_detector")}
{commands.get("blocker_writeback")}
{commands.get("success_writeback")}
```

## Boundary

- adapter_packet_only: `{boundary.get("adapter_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- requires_visible_delivery: `{boundary.get("requires_visible_delivery")}`
- argv_prompt_rejected: `{boundary.get("argv_prompt_rejected")}`
- success_claim_requires_first_response_and_idle: `{boundary.get("success_claim_requires_first_response_and_idle")}`
{required_shapes}
"""


def render_codex_cli_visible_first_response_capture_plan_markdown(
    payload: dict[str, Any],
) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    artifacts = (
        payload.get("output_artifacts")
        if isinstance(payload.get("output_artifacts"), dict)
        else {}
    )
    steps = payload.get("capture_steps") if isinstance(payload.get("capture_steps"), list) else []
    stops = payload.get("stop_conditions") if isinstance(payload.get("stop_conditions"), list) else []
    first_response_fixture = payload.get("sample_first_response_fixture")
    runtime_idle_fixture = payload.get("sample_runtime_idle_fixture")
    step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    stop_lines = "\n".join(f"- {stop}" for stop in stops) if stops else "- none"
    return f"""# Codex CLI Visible First-Response Capture Plan

- decision: `{payload.get("decision")}`
- start_surface: `{payload.get("start_surface")}`
- first_response_fixture: `{artifacts.get("first_response_fixture")}`
- runtime_idle_fixture: `{artifacts.get("runtime_idle_fixture")}`
- next_safe_step: {payload.get("next_safe_step")}

## Commands

```bash
{commands.get("quota_guard")}
{commands.get("bootstrap_message")}
{commands.get("bounded_visible_pilot_adapter")}
{commands.get("runtime_idle_detector")}
```

## Capture Steps

{step_lines}

## Stop Conditions

{stop_lines}

## Sample First-Response Fixture

```json
{json.dumps(first_response_fixture, indent=2, ensure_ascii=False)}
```

## Sample Runtime Idle Fixture

```json
{json.dumps(runtime_idle_fixture, indent=2, ensure_ascii=False)}
```

## Boundary

- capture_plan_only: `{boundary.get("capture_plan_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- manual_paste_primary: `{boundary.get("manual_paste_primary")}`
- argv_prompt_rejected: `{boundary.get("argv_prompt_rejected")}`
- success_claim_requires_bounded_adapter: `{boundary.get("success_claim_requires_bounded_adapter")}`
"""


def render_codex_cli_runtime_idle_detector_markdown(payload: dict[str, Any]) -> str:
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
        check_lines = "- no runtime idle evidence supplied"
    failure_lines = "\n".join(f"- {failure}" for failure in failures) if failures else "- none"
    required_shape_block = ""
    if isinstance(required_shape, dict):
        required_shape_block = f"""
## Required Evidence Shape

```json
{json.dumps(required_shape, indent=2, ensure_ascii=False)}
```
"""
    return f"""# Codex CLI Runtime Idle Detector

- decision: `{payload.get("decision")}`
- approved_for_visible_later_turn: `{payload.get("approved_for_visible_later_turn")}`
- source: `{payload.get("source")}`
- observed_surface: `{payload.get("observed_surface")}`
- recommended_action: {payload.get("recommended_action")}

## Checks

{check_lines}

## Failures

{failure_lines}

## Boundary

- fixture_only: `{boundary.get("fixture_only")}`
- public_safe_fixture_supported: `{boundary.get("public_safe_fixture_supported")}`
- local_observation_adapter_supported: `{boundary.get("local_observation_adapter_supported")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
{required_shape_block}
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
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
{required_shape_block}
"""


def render_codex_cli_visible_attach_acceptance_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    proof = (
        payload.get("visible_session_proof")
        if isinstance(payload.get("visible_session_proof"), dict)
        else {}
    )
    runtime_idle = (
        payload.get("runtime_idle_detector")
        if isinstance(payload.get("runtime_idle_detector"), dict)
        else {}
    )
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers) if blockers else "- none"
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    warning_lines = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    return f"""# Codex CLI Visible Attach Acceptance

- decision: `{payload.get("decision")}`
- accepted_for_same_tui_automation: `{payload.get("accepted_for_same_tui_automation")}`
- accepted_for_visible_later_turn: `{payload.get("accepted_for_visible_later_turn")}`
- observed_surface: `{payload.get("observed_surface")}`
- driver_mode: `{payload.get("driver_mode")}`
- next_safe_step: {payload.get("next_safe_step")}

## Proof And Idle

- proof_supplied: `{proof.get("supplied")}`
- proof_approved: `{proof.get("approved")}`
- proof_decision: `{proof.get("decision")}`
- idle_supplied: `{runtime_idle.get("supplied")}`
- idle_approved: `{runtime_idle.get("approved")}`
- idle_decision: `{runtime_idle.get("decision")}`

## Blockers

{blocker_lines}

## Commands

```bash
{commands.get("session_probe")}
{commands.get("visible_attach_acceptance")}
{commands.get("visible_session_proof")}
{commands.get("runtime_idle_detector_fixture")}
{commands.get("tui_bootstrap_message")}
```

## Boundary

- acceptance_packet_only: `{boundary.get("acceptance_packet_only")}`
- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_stdout_stderr: `{boundary.get("reads_stdout_stderr")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- writes_loopx_state: `{boundary.get("writes_loopx_state")}`

## Warnings

{warning_lines}
"""
