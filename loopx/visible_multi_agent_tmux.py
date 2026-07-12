from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterable
from hashlib import sha256

from .capabilities.multi_agent.contract import (
    PANE_LOCAL_A2A_WAKEUP_PROMPT,
    build_decentralized_a2a_driver_contract,
)


PANE_A2A_WAKEUP_SCHEMA_VERSION = "multi_agent_pane_a2a_wakeup_v0"
PANE_A2A_WAKEUP_PROMPT = PANE_LOCAL_A2A_WAKEUP_PROMPT
PANE_A2A_INPUT_READY_TIMEOUT_SECONDS = 5.0
TMUX_LANE_ID_OPTION = "@loopx_lane_id"
_CODEX_TUI_USAGE_LIMIT_MARKERS = (
    "you've hit your usage limit",
    "you have hit your usage limit",
    "purchase more credits or try again",
    "rate limit exceeded",
    "429 too many requests",
)
_CODEX_TUI_BACKOFF_REASONS = frozenset({"codex_tui_usage_or_rate_limited"})


def _require_executable(command: str, *, field: str) -> str:
    path = shutil.which(command)
    if not path:
        raise ValueError(f"{field} executable not found on PATH: {command}")
    return path


def build_pane_a2a_wakeup_prompt() -> str:
    """Return the fixed prompt broadcast to live Codex TUI panes."""

    return PANE_A2A_WAKEUP_PROMPT


def _codex_tui_input_ready(capture: str) -> bool:
    if not capture:
        return False
    if _codex_tui_block_reason(capture):
        return False
    prompt_index = max(capture.rfind("\n› "), capture.rfind("\r\n› "))
    if prompt_index < 0:
        return False
    model_lines = [line for line in capture.splitlines() if "model:" in line]
    if model_lines and "loading" in model_lines[-1]:
        return False
    has_codex_surface = "OpenAI Codex" in capture or "gpt-" in capture[prompt_index:]
    if not has_codex_surface:
        return False
    # Codex keeps a queueable input prompt visible while a turn is still running.
    # Busy markers render immediately above that prompt, so checking only the
    # text after the final prompt incorrectly treats an active turn as idle.
    if "Queued follow-up inputs" in capture or "Working (" in capture:
        return False
    current_view = capture[prompt_index:]
    if "Starting MCP servers" in current_view:
        return False
    return True


def _codex_tui_block_reason(capture: str) -> str | None:
    lowered = capture.lower()
    if any(marker in lowered for marker in _CODEX_TUI_USAGE_LIMIT_MARKERS):
        return "codex_tui_usage_or_rate_limited"
    return None


def _wait_for_tmux_pane_input_ready(
    *,
    tmux_bin: str,
    session: str,
    lane: str,
    target: str | None = None,
    env: dict[str, str],
    timeout_seconds: float = PANE_A2A_INPUT_READY_TIMEOUT_SECONDS,
) -> dict[str, object]:
    deadline = time.monotonic() + max(0.25, timeout_seconds)
    attempts = 0
    tmux_target = target or f"{session}:{lane}"
    while True:
        attempts += 1
        capture = subprocess.run(
            [tmux_bin, "capture-pane", "-pt", tmux_target, "-S", "-80"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        block_reason = _codex_tui_block_reason(capture.stdout)
        if block_reason:
            return {
                "lane": lane,
                "target": tmux_target,
                "ready": False,
                "attempt_count": attempts,
                "capture_ok": capture.returncode == 0,
                "ready_marker": None,
                "not_ready_reason": block_reason,
                "backoff_recommended": True,
            }
        ready = capture.returncode == 0 and _codex_tui_input_ready(capture.stdout)
        if ready:
            return {
                "lane": lane,
                "target": tmux_target,
                "ready": True,
                "attempt_count": attempts,
                "capture_ok": True,
                "ready_marker": "codex_tui_first_turn_ready",
            }
        if time.monotonic() >= deadline:
            return {
                "lane": lane,
                "target": tmux_target,
                "ready": False,
                "attempt_count": attempts,
                "capture_ok": capture.returncode == 0,
                "ready_marker": None,
                "not_ready_reason": "codex_tui_busy_or_not_ready",
                "backoff_recommended": False,
            }
        time.sleep(0.25)


def _list_tmux_lane_targets(
    *,
    tmux_bin: str,
    session: str,
    env: dict[str, str],
) -> list[dict[str, str]]:
    listed = subprocess.run(
        [
            tmux_bin,
            "list-panes",
            "-s",
            "-t",
            session,
            "-F",
            f"#{{pane_id}}\t#{{{TMUX_LANE_ID_OPTION}}}\t#{{pane_title}}\t#{{window_name}}\t#{{pane_index}}",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    panes: list[dict[str, str]] = []
    if listed.returncode == 0:
        for line in listed.stdout.splitlines():
            pane_id, lane_id, pane_title, window_name, pane_index = (
                line.split("\t") + ["", "", "", "", ""]
            )[:5]
            pane_id = pane_id.strip()
            label = lane_id.strip() or pane_id
            if pane_id:
                panes.append(
                    {
                        "lane": label,
                        "target": pane_id,
                        "pane_title": pane_title.strip(),
                        "window_name": window_name.strip(),
                        "pane_index": pane_index.strip(),
                    }
                )
    return panes


def _resolve_tmux_lane_targets(
    *,
    tmux_bin: str,
    session: str,
    lanes: Iterable[str],
    env: dict[str, str],
) -> list[dict[str, str]]:
    target_lanes = [str(lane).strip() for lane in lanes if str(lane).strip()]
    pane_targets = _list_tmux_lane_targets(tmux_bin=tmux_bin, session=session, env=env)
    by_label = {item["lane"]: item["target"] for item in pane_targets}
    by_target = {item["target"]: item["target"] for item in pane_targets}
    if not target_lanes:
        if pane_targets:
            return pane_targets
        listed = subprocess.run(
            [tmux_bin, "list-windows", "-t", session, "-F", "#{window_name}"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        target_lanes = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    resolved: list[dict[str, str]] = []
    for lane in target_lanes:
        target = by_label.get(lane) or by_target.get(lane)
        if not target:
            target = lane if lane.startswith("%") else f"{session}:{lane}"
        resolved.append({"lane": lane, "target": target})
    return resolved


def _prompt_still_waiting_for_submit(capture: str, prompt: str) -> bool:
    if not capture or not prompt:
        return False
    prompt_index = max(capture.rfind("\n› "), capture.rfind("\r\n› "))
    current_view = capture[prompt_index:] if prompt_index >= 0 else capture
    if "Working (" in current_view or "Queued follow-up inputs" in current_view:
        return False
    if "[Pasted Content" in current_view:
        return True
    words = [part for part in prompt.split() if part]
    head = words[:4]
    tail = words[-4:]
    return (bool(head) and all(word in current_view for word in head)) or (
        bool(tail) and all(word in current_view for word in tail)
    )


def _paste_and_submit_tmux_prompt(
    *,
    tmux_bin: str,
    target: str,
    buffer_name: str,
    prompt: str,
    env: dict[str, str],
) -> dict[str, object]:
    subprocess.run(
        [tmux_bin, "paste-buffer", "-b", buffer_name, "-t", target],
        check=True,
        env=env,
    )
    subprocess.run(
        [tmux_bin, "send-keys", "-t", target, "Enter"],
        check=True,
        env=env,
    )
    retry = False
    capture_ok = False
    observation_count = 0
    for _ in range(20):
        time.sleep(0.25)
        observation_count += 1
        capture = subprocess.run(
            [tmux_bin, "capture-pane", "-pt", target, "-S", "-80"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        capture_ok = capture.returncode == 0
        if not capture_ok:
            continue
        if _prompt_still_waiting_for_submit(capture.stdout, prompt):
            retry = True
            break
        if "Working (" in capture.stdout or "Queued follow-up inputs" in capture.stdout:
            break
    if retry:
        subprocess.run(
            [tmux_bin, "send-keys", "-t", target, "Enter"],
            check=True,
            env=env,
        )
    return {
        "target": target,
        "initial_submit_key": "Enter",
        "retry_submit_key": "Enter" if retry else None,
        "retry_count": 1 if retry else 0,
        "capture_ok": capture_ok,
        "observation_count": observation_count,
    }


def wake_visible_multi_agent_panes(
    *,
    session_name: str,
    tmux_bin: str = "tmux",
    lanes: Iterable[str] | None = None,
    execute: bool = False,
    prompt: str | None = None,
    input_ready_timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Broadcast the fixed A2A prompt; each pane still decides via LoopX state."""

    session = str(session_name or "").strip()
    if not session:
        raise ValueError("multi-agent wake requires --session-name")
    prompt_text = str(prompt or build_pane_a2a_wakeup_prompt()).strip()
    if not prompt_text:
        raise ValueError("multi-agent wake prompt must not be empty")
    prompt_hash = sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
    target_lanes = [str(lane).strip() for lane in lanes or [] if str(lane).strip()]
    driver_contract = build_decentralized_a2a_driver_contract()
    input_ready_checks: list[dict[str, object]] = []
    prompt_submit_checks: list[dict[str, object]] = []

    if execute:
        _require_executable(tmux_bin, field="tmux_bin")
        env = os.environ.copy()
        target_specs = _resolve_tmux_lane_targets(
            tmux_bin=tmux_bin,
            session=session,
            lanes=target_lanes,
            env=env,
        )
        if not target_specs:
            raise ValueError("multi-agent wake found no target panes")
        resolved_target_lanes = [str(spec["lane"]) for spec in target_specs]
        input_ready_checks = [
            _wait_for_tmux_pane_input_ready(
                tmux_bin=tmux_bin,
                session=session,
                lane=spec["lane"],
                target=spec["target"],
                env=env,
                timeout_seconds=(
                    PANE_A2A_INPUT_READY_TIMEOUT_SECONDS
                    if input_ready_timeout_seconds is None
                    else input_ready_timeout_seconds
                ),
            )
            for spec in target_specs
        ]
        ready_lanes = [
            str(check.get("lane"))
            for check in input_ready_checks
            if check.get("ready") is True
        ]
        if ready_lanes:
            buffer_name = f"loopx-pane-a2a-wakeup-{prompt_hash}"
            subprocess.run(
                [tmux_bin, "set-buffer", "-b", buffer_name, "--", prompt_text],
                check=True,
                env=env,
            )
            ready_targets = {
                str(spec["lane"]): str(spec["target"])
                for spec in target_specs
                if str(spec["lane"]) in ready_lanes
            }
            for lane in ready_lanes:
                target = ready_targets[lane]
                prompt_submit_checks.append(
                    _paste_and_submit_tmux_prompt(
                        tmux_bin=tmux_bin,
                        target=target,
                        buffer_name=buffer_name,
                        prompt=prompt_text,
                        env=env,
                    )
                )
        not_ready = [
            str(check.get("lane"))
            for check in input_ready_checks
            if check.get("ready") is not True
        ]
    else:
        ready_lanes = []
        not_ready = []
        resolved_target_lanes = target_lanes

    auto_wake_backoff_recommended = (
        execute
        and bool(input_ready_checks)
        and not ready_lanes
        and all(
            str(check.get("not_ready_reason") or "") in _CODEX_TUI_BACKOFF_REASONS
            for check in input_ready_checks
        )
    )
    if not execute:
        prompt_delivery = "dry_run"
    elif auto_wake_backoff_recommended:
        prompt_delivery = "skipped_terminal_pane_backoff"
    elif not prompt_submit_checks:
        prompt_delivery = "skipped_no_input_ready_panes"
    elif not_ready:
        prompt_delivery = "tmux_paste_buffer_after_ready_subset"
    else:
        prompt_delivery = "tmux_paste_buffer_after_codex_tui_first_turn_ready"

    return {
        "ok": True,
        "schema_version": PANE_A2A_WAKEUP_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "session_name": session,
        "target_lanes": resolved_target_lanes if resolved_target_lanes else ["<all-session-panes>"],
        "prompt": prompt_text,
        "prompt_hash": prompt_hash,
        "coordination_model": "decentralized_state_a2a",
        "wakeup_model": "fixed_prompt_broadcast",
        "driver_contract": driver_contract,
        "workflow_driver": False,
        "broadcaster_reads_frontier": driver_contract["broadcaster"]["reads_frontier"],
        "broadcaster_reads_todo_readiness": driver_contract["broadcaster"].get(
            "reads_todo_readiness", False
        ),
        "broadcaster_selects_todo": driver_contract["broadcaster"]["selects_todo"],
        "pane_decision_owner": driver_contract["pane"]["decision_owner"],
        "pane_input_ready_verified": (
            bool(input_ready_checks)
            and all(check.get("ready") is True for check in input_ready_checks)
        )
        if execute
        else False,
        "pane_input_ready_checks": input_ready_checks,
        "pane_input_ready_timeout_seconds": (
            PANE_A2A_INPUT_READY_TIMEOUT_SECONDS
            if input_ready_timeout_seconds is None
            else input_ready_timeout_seconds
        )
        if execute
        else None,
        "ready_lanes": ready_lanes,
        "not_ready_lanes": not_ready,
        "prompt_submit_checks": prompt_submit_checks,
        "prompt_delivery": prompt_delivery,
        "auto_wake_backoff_recommended": auto_wake_backoff_recommended,
        "boundary": {
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "runs_worker_turn_directly": False,
        },
    }
