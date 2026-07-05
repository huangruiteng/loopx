"""Small helpers for driving the visible Codex CLI ``/goal`` TUI surface."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time


CODEX_CLI_GOAL_COMMAND_PREFIX = "/goal "
CODEX_CLI_GOAL_OBJECTIVE_MAX_CHARS = 4000
CODEX_CLI_GOAL_THREAD_PREWARM_MARKER = "LOOPX_GOAL_THREAD_READY"
CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT = (
    "Start this persisted Codex thread. Reply with exactly the token formed by "
    "joining LOOPX, GOAL, THREAD, and READY with underscores. Do not use tools."
)
CODEX_CLI_GOAL_TASK_PROMPT_FILENAME = "skillsbench-task-prompt.md"


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
    if codex_cli_tui_active_input_prompt_contains(tmux_capture(tmux_name), prompt_text):
        tmux_send_plain_enter(tmux_name)


def tmux_type_text_and_submit(*, tmux_name: str, text: str) -> None:
    """Type a short command into the TUI and submit without bracketed paste."""

    tmux_send_literal(tmux_name, text)
    time.sleep(0.2)
    tmux_submit_enter(tmux_name)
    time.sleep(1.0)
    if codex_cli_tui_active_input_prompt_contains(tmux_capture(tmux_name), text):
        tmux_send_plain_enter(tmux_name)


def codex_cli_tui_input_prompt_visible(capture: str) -> bool:
    if not capture:
        return False
    if "›" in capture:
        return True
    return bool(re.search(r"(?m)^\\s*[>❯]\\s*(?:$|\\[)", capture))


def wait_for_codex_cli_tui_ready(
    tmux_name: str,
    *,
    timeout_sec: float = 30.0,
) -> bool:
    """Wait until Codex TUI startup noise has settled before pasting input."""

    deadline = time.monotonic() + max(1.0, float(timeout_sec or 0.0))
    while time.monotonic() < deadline:
        capture = tmux_capture(tmux_name)
        lowered = capture.lower()
        if not capture.strip():
            time.sleep(0.5)
            continue
        if codex_cli_tui_input_prompt_visible(capture):
            return True
        if any(
            marker in lowered
            for marker in (
                "what can i help",
                "ask codex",
                "message codex",
                "send a message",
                "type a message",
            )
        ):
            return True
        time.sleep(0.5)
    return False


def prewarm_codex_cli_goal_thread(
    *,
    tmux_name: str,
    tmp_path: Path,
    timeout_sec: float = 90.0,
) -> bool:
    """Create the persisted TUI thread before submitting ``/goal``."""

    prompt_path = tmp_path / "goal-thread-prewarm.txt"
    prompt_path.write_text(CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT, encoding="utf-8")
    tmux_paste_file_and_submit(
        tmux_name=tmux_name,
        prompt_path=prompt_path,
        buffer_suffix="prewarm",
    )
    deadline = time.monotonic() + max(1.0, float(timeout_sec or 0.0))
    while time.monotonic() < deadline:
        capture = tmux_capture(tmux_name)
        if CODEX_CLI_GOAL_THREAD_PREWARM_MARKER in capture:
            return True
        time.sleep(0.5)
    return False
