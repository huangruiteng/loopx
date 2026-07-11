"""Small helpers for driving the visible Codex CLI ``/goal`` TUI surface."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time


CODEX_CLI_GOAL_COMMAND_PREFIX = "/goal "
CODEX_CLI_GOAL_OBJECTIVE_MAX_CHARS = 4000
CODEX_CLI_GOAL_THREAD_PREWARM_MARKER = "LOOPX_GOAL_THREAD_READY"
CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT = (
    "Start this persisted Codex thread. Reply with exactly the token formed by "
    "joining LOOPX, GOAL, THREAD, and READY with underscores. Do not use tools."
)
CODEX_CLI_GOAL_THREAD_PREWARM_HARD_CAP_MULTIPLIER = 2.0
CODEX_CLI_GOAL_TASK_PROMPT_FILENAME = "skillsbench-task-prompt.md"
CODEX_CLI_GOAL_KICKOFF_PROMPT = (
    "Start working on the active SkillsBench goal now. Read the referenced "
    "task prompt file first, follow it exactly, and perform at least one "
    "task-facing bridge action before reporting status."
)
CODEX_CLI_TUI_READY_STARTUP_GRACE_SEC = 15.0
CODEX_CLI_TUI_READY_STABLE_SEC = 2.0


@dataclass(frozen=True)
class CodexCliGoalLifecycleMarkerCounts:
    active: int = 0
    achieved: int = 0
    failed: int = 0


@dataclass
class CodexCliGoalLifecycleGeneration:
    generation: int = 0
    baseline: CodexCliGoalLifecycleMarkerCounts = (
        CodexCliGoalLifecycleMarkerCounts()
    )
    current: CodexCliGoalLifecycleMarkerCounts = CodexCliGoalLifecycleMarkerCounts()
    turn_active_observed: bool = False

    def begin(self, capture: str) -> None:
        self.generation += 1
        self.baseline = codex_cli_goal_lifecycle_marker_counts(capture)
        self.current = self.baseline
        self.turn_active_observed = False

    def observe(self, capture: str, *, turn_active: bool = False) -> None:
        self.current = codex_cli_goal_lifecycle_marker_counts(capture)
        self.turn_active_observed = self.turn_active_observed or bool(turn_active)

    @property
    def active_advanced(self) -> bool:
        return self.current.active > self.baseline.active

    @property
    def active_observed(self) -> bool:
        return self.active_advanced or self.turn_active_observed

    @property
    def achieved_advanced(self) -> bool:
        return self.current.achieved > self.baseline.achieved

    @property
    def failed_advanced(self) -> bool:
        return self.current.failed > self.baseline.failed

    def trace_fields(self) -> dict[str, int | bool]:
        fields: dict[str, int | bool] = {
            "goal_submission_generation": max(0, self.generation),
            "goal_turn_active_observed": self.turn_active_observed,
        }
        for name in ("active", "achieved", "failed"):
            baseline = getattr(self.baseline, name)
            current = getattr(self.current, name)
            fields[f"goal_{name}_marker_baseline"] = baseline
            fields[f"goal_{name}_marker_current"] = current
            fields[f"goal_{name}_marker_delta"] = max(0, current - baseline)
        return fields


def resolve_codex_cli_binary(codex_bin: str) -> str | None:
    """Resolve an executable Codex CLI without recording its path publicly."""

    candidate = str(codex_bin or "codex").strip() or "codex"
    resolved = shutil.which(candidate) if os.sep not in candidate else candidate
    if not resolved:
        return None
    path = Path(resolved)
    return str(path) if path.is_file() and os.access(path, os.X_OK) else None


def build_codex_cli_goal_tui_input(objective: str) -> str:
    """Return the literal TUI input that sets a Codex CLI goal."""

    return f"{CODEX_CLI_GOAL_COMMAND_PREFIX}{objective}"


def build_codex_cli_goal_file_objective(prompt_filename: str) -> str:
    """Return a short goal objective that points Codex at private task details."""

    prompt_ref = (prompt_filename or CODEX_CLI_GOAL_TASK_PROMPT_FILENAME).strip()
    prompt_ref = prompt_ref.replace("\\", "/").lstrip("/")
    if not prompt_ref or ".." in Path(prompt_ref).parts:
        prompt_ref = CODEX_CLI_GOAL_TASK_PROMPT_FILENAME
    objective = (
        "Complete the SkillsBench task using the private task and bridge "
        f"instructions in ./{prompt_ref}. Read that file first, follow it "
        "exactly, and perform at least one task-facing bridge action before "
        "reporting status."
    )
    if len(objective) > CODEX_CLI_GOAL_OBJECTIVE_MAX_CHARS:
        raise ValueError("codex cli goal file objective exceeds objective cap")
    return objective


def build_codex_cli_tui_command(
    *,
    codex_bin: str,
    sandbox: str,
    approval_policy: str | None,
    cwd: str,
    reasoning_effort: str | None,
    model: object,
) -> list[str]:
    cmd = [
        codex_bin,
        "--no-alt-screen",
        "--disable",
        "apps",
        "-s",
        sandbox,
        "-a",
        approval_policy or "never",
        "-C",
        cwd,
    ]
    if reasoning_effort:
        cmd.extend(
            [
                "-c",
                "model_reasoning_effort=" + json.dumps(str(reasoning_effort)),
            ]
        )
    for trust_path in (cwd, os.path.realpath(cwd)):
        if trust_path:
            cmd.extend(
                [
                    "-c",
                    f"projects.{json.dumps(trust_path)}.trust_level=\"trusted\"",
                ]
            )
    if model:
        cmd.extend(["-m", str(model)])
    return cmd


def codex_cli_tui_environment(codex_api_proxy: str | None) -> dict[str, str]:
    proxy_url = (codex_api_proxy or "").strip()
    if not proxy_url:
        for key in (
            "HTTPS_PROXY",
            "HTTP_PROXY",
            "ALL_PROXY",
            "https_proxy",
            "http_proxy",
            "all_proxy",
        ):
            value = os.environ.get(key)
            if value:
                proxy_url = value.strip()
                break
    if not proxy_url:
        return {}
    env = {
        "HTTPS_PROXY": proxy_url,
        "HTTP_PROXY": proxy_url,
        "ALL_PROXY": proxy_url,
        "https_proxy": proxy_url,
        "http_proxy": proxy_url,
        "all_proxy": proxy_url,
    }
    no_proxy_entries: list[str] = []
    for raw in (os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or "").split(
        ","
    ):
        entry = raw.strip()
        if entry and entry not in no_proxy_entries:
            no_proxy_entries.append(entry)
    for entry in ("localhost", "127.0.0.1", "::1"):
        if entry not in no_proxy_entries:
            no_proxy_entries.append(entry)
    no_proxy = ",".join(no_proxy_entries)
    env["NO_PROXY"] = no_proxy
    env["no_proxy"] = no_proxy
    return env


def codex_cli_tui_shell_command(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
) -> str:
    if not env:
        return " ".join(shlex.quote(part) for part in cmd)
    env_parts = [shlex.quote(f"{key}={value}") for key, value in sorted(env.items())]
    cmd_parts = [shlex.quote(part) for part in cmd]
    return " ".join(["env", *env_parts, *cmd_parts])


def tmux_capture(tmux_name: str) -> str:
    proc = subprocess.run(
        ["tmux", "capture-pane", "-p", "-J", "-S", "-2000", "-t", tmux_name],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return proc.stdout or ""


def tmux_capture_visible(tmux_name: str) -> str:
    proc = subprocess.run(
        ["tmux", "capture-pane", "-p", "-J", "-t", tmux_name],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return proc.stdout or ""


def tmux_kill_session(tmux_name: str) -> None:
    subprocess.run(
        ["tmux", "kill-session", "-t", tmux_name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def tmux_send_literal(tmux_name: str, text: str) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", tmux_name, "-l", text],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def tmux_submit_enter(tmux_name: str) -> None:
    # Codex TUI uses enhanced keyboard handling; the Kitty Enter sequence
    # submits reliably where a plain carriage return may only insert a line.
    try:
        tmux_send_literal(tmux_name, "\x1b[13u")
    except subprocess.SubprocessError:
        subprocess.run(
            ["tmux", "send-keys", "-t", tmux_name, "C-m"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )


def tmux_send_plain_enter(tmux_name: str) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", tmux_name, "C-m"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def codex_cli_tui_active_input_prompt_contains(
    capture: str,
    prompt_text: str,
) -> bool:
    """Return true when the pasted text still appears in the active input row."""

    stripped_prompt = prompt_text.strip()
    if not capture or not stripped_prompt:
        return False
    first_prompt_line = next(
        (line.strip() for line in stripped_prompt.splitlines() if line.strip()),
        "",
    )
    if not first_prompt_line:
        return False
    needle = first_prompt_line[: min(len(first_prompt_line), 48)]
    for raw_line in reversed(capture.splitlines()[-12:]):
        line = raw_line.strip()
        if not line:
            continue
        if not (line.startswith("›") or re.match(r"^[>❯]\s*", line)):
            continue
        if needle and needle in line:
            return True
        return False
    return False


def tmux_paste_file_and_submit(
    *,
    tmux_name: str,
    prompt_path: Path,
    buffer_suffix: str,
) -> None:
    buffer_name = f"{tmux_name}-{buffer_suffix}"
    subprocess.run(
        ["tmux", "load-buffer", "-b", buffer_name, str(prompt_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    subprocess.run(
        ["tmux", "paste-buffer", "-d", "-b", buffer_name, "-t", tmux_name],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    time.sleep(0.8)
    tmux_submit_enter(tmux_name)
    prompt_text = prompt_path.read_text(encoding="utf-8", errors="ignore")
    time.sleep(1.0)
    if codex_cli_tui_active_input_prompt_contains(
        tmux_capture_visible(tmux_name),
        prompt_text,
    ):
        tmux_send_plain_enter(tmux_name)


def tmux_type_text_and_submit(*, tmux_name: str, text: str) -> None:
    """Type a short command into the TUI and submit without bracketed paste."""

    tmux_send_literal(tmux_name, text)
    time.sleep(0.2)
    tmux_submit_enter(tmux_name)
    time.sleep(1.0)
    if codex_cli_tui_active_input_prompt_contains(
        tmux_capture_visible(tmux_name),
        text,
    ):
        tmux_send_plain_enter(tmux_name)


def codex_cli_tui_trust_prompt_visible(capture: str) -> bool:
    lowered = (capture or "").lower()
    return (
        "do you trust the contents of this directory" in lowered
        or ("yes, continue" in lowered and "press enter to continue" in lowered)
    )


def codex_cli_tui_latest_model_line(capture: str) -> str:
    model_lines = [
        line.strip()
        for line in (capture or "").splitlines()
        if "model:" in line.lower()
    ]
    return model_lines[-1] if model_lines else ""


def codex_cli_tui_startup_blocker(capture: str) -> str:
    if not (capture or "").strip():
        return "empty_capture"
    if codex_cli_tui_trust_prompt_visible(capture):
        return "trust_prompt"
    latest_model_line = codex_cli_tui_latest_model_line(capture)
    if "loading" in latest_model_line.lower():
        return "model_loading"
    if "queued follow-up inputs" in capture.lower():
        return "queued_followup"
    return ""


def codex_cli_tui_input_prompt_visible(capture: str) -> bool:
    if not capture:
        return False
    if codex_cli_tui_trust_prompt_visible(capture):
        return False
    for raw_line in reversed(capture.splitlines()[-20:]):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("›"):
            return True
        if re.match(r"^[>❯]\s*(?:$|\S)", line):
            return True
    return False


def codex_cli_tui_turn_active(capture: str) -> bool:
    """Return true while the visible TUI is still running the current turn."""

    recent_lines = (capture or "").splitlines()[-20:]
    for raw_line in recent_lines:
        line = raw_line.lower()
        if "working (" in line and "esc to interrupt" in line:
            return True
        if "pursuing goal (" in line:
            return True
        if "queued follow-up inputs" in line:
            return True
    return False


def codex_cli_goal_watchdog_expired(
    *,
    deadline: float,
    now: float,
    turn_active: bool,
) -> bool:
    """Keep bounded watchdogs from interrupting an active Codex turn."""

    return bool(deadline and now >= deadline and not turn_active)


def codex_cli_goal_lifecycle_marker_counts(
    capture: str,
) -> CodexCliGoalLifecycleMarkerCounts:
    """Count public lifecycle markers in a TUI scrollback capture."""

    text = str(capture or "")
    return CodexCliGoalLifecycleMarkerCounts(
        active=text.count("Goal active") + text.count("Pursuing goal"),
        achieved=text.count("Goal achieved"),
        failed=text.count("Goal failed") + text.count("Goal blocked"),
    )


def codex_cli_tui_retryable_startup_blocker_stage(capture: str) -> str:
    """Classify public-safe Codex CLI TUI startup blockers from screen text."""

    lowered = str(capture or "").lower()
    if any(
        marker in lowered
        for marker in (
            "rate limit",
            "rate_limit",
            "too many requests",
            "status 429",
            "error 429",
        )
    ):
        return "rate_limit_before_goal_active"
    return ""


def codex_cli_goal_should_submit_kickoff(
    *,
    bridge_enabled: bool,
    goal_active_observed: bool,
    kickoff_submitted: bool,
    turn_active: bool,
    first_action_seen: bool,
    capture: str,
) -> bool:
    return (
        bridge_enabled
        and goal_active_observed
        and not kickoff_submitted
        and not turn_active
        and not first_action_seen
        and codex_cli_tui_input_prompt_visible(capture)
    )


def codex_cli_goal_should_ignore_stale_terminal(
    *,
    goal_failed_now: bool,
    kickoff_submitted: bool,
    first_action_seen: bool,
    turn_active: bool,
    first_action_deadline: float,
    now: float,
) -> bool:
    return (
        goal_failed_now
        and kickoff_submitted
        and not first_action_seen
        and (turn_active or (first_action_deadline and now < first_action_deadline))
    )


def codex_cli_goal_reset_pre_bridge_deadlines(
    *,
    now: float,
    first_action_timeout_sec: float,
    goal_active_deadline: float,
    goal_active_timeout_sec: float,
    first_action_deadline: float,
    meaningful_progress_deadline: float,
) -> tuple[float, float, float]:
    timeout = max(1.0, float(first_action_timeout_sec or 0.0))
    return (
        now + max(1.0, float(goal_active_timeout_sec or 0.0))
        if goal_active_deadline
        else goal_active_deadline,
        now + timeout if first_action_deadline else first_action_deadline,
        now + max(1.0, timeout)
        if meaningful_progress_deadline
        else meaningful_progress_deadline,
    )


def wait_for_codex_cli_tui_ready(
    tmux_name: str,
    *,
    timeout_sec: float = 60.0,
    startup_grace_sec: float = CODEX_CLI_TUI_READY_STARTUP_GRACE_SEC,
    stable_sec: float = CODEX_CLI_TUI_READY_STABLE_SEC,
    auto_accept_trust_prompt: bool = False,
) -> bool:
    """Wait until Codex TUI startup noise has settled before pasting input."""

    timeout = max(1.0, float(timeout_sec or 0.0))
    deadline = time.monotonic() + timeout
    grace = max(0.0, min(float(startup_grace_sec or 0.0), max(0.0, timeout - 1.0)))
    if grace:
        time.sleep(grace)
    stable_ready_since = 0.0
    while time.monotonic() < deadline:
        capture = tmux_capture_visible(tmux_name)
        lowered = capture.lower()
        if auto_accept_trust_prompt and codex_cli_tui_trust_prompt_visible(capture):
            tmux_submit_enter(tmux_name)
            stable_ready_since = 0.0
            time.sleep(1.0)
            continue
        if codex_cli_tui_startup_blocker(capture):
            stable_ready_since = 0.0
            time.sleep(0.5)
            continue
        ready = codex_cli_tui_input_prompt_visible(capture) or any(
            marker in lowered
            for marker in (
                "what can i help",
                "ask codex",
                "message codex",
                "send a message",
                "type a message",
            )
        )
        if not ready:
            stable_ready_since = 0.0
            time.sleep(0.5)
            continue
        now = time.monotonic()
        if not stable_ready_since:
            stable_ready_since = now
        if now - stable_ready_since >= max(0.0, float(stable_sec or 0.0)):
            return True
        time.sleep(0.5)
    return False


def start_codex_cli_goal_tui_session(
    *,
    tmux_name: str,
    cwd: str,
    shell_command: str,
    thread_prewarm: bool,
    thread_prewarm_timeout_sec: float,
) -> tuple[str, bool]:
    """Start one fresh Codex TUI session and return its public-safe stage."""

    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            tmux_name,
            "-c",
            cwd,
            shell_command,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not wait_for_codex_cli_tui_ready(
        tmux_name,
        auto_accept_trust_prompt=True,
    ):
        tmux_kill_session(tmux_name)
        return "tui_ready_timeout", False
    if not thread_prewarm:
        return "", False
    thread_prewarm_observed = prewarm_codex_cli_goal_thread(
        tmux_name=tmux_name,
        timeout_sec=thread_prewarm_timeout_sec,
    )
    if not thread_prewarm_observed:
        tmux_kill_session(tmux_name)
        return "thread_prewarm_timeout", False
    return "", True


def prewarm_codex_cli_goal_thread(
    *,
    tmux_name: str,
    timeout_sec: float = 90.0,
) -> bool:
    """Create the persisted TUI thread before submitting ``/goal``."""

    tmux_type_text_and_submit(
        tmux_name=tmux_name,
        text=CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT,
    )
    timeout = max(1.0, float(timeout_sec or 0.0))
    started_at = time.monotonic()
    nominal_deadline = started_at + timeout
    hard_deadline = started_at + (
        timeout * CODEX_CLI_GOAL_THREAD_PREWARM_HARD_CAP_MULTIPLIER
    )
    turn_active_observed = False
    while time.monotonic() < hard_deadline:
        capture = tmux_capture(tmux_name)
        if CODEX_CLI_GOAL_THREAD_PREWARM_MARKER in capture:
            return True
        turn_active = codex_cli_tui_turn_active(capture)
        turn_active_observed = turn_active_observed or turn_active
        if (
            turn_active_observed
            and not turn_active
            and codex_cli_tui_input_prompt_visible(capture)
        ):
            return True
        if time.monotonic() >= nominal_deadline and not turn_active:
            return False
        time.sleep(0.5)
    return False
