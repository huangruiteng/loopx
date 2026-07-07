from __future__ import annotations

from pathlib import Path
import uuid

from loopx.codex_cli_goal_tui import codex_cli_tui_input_prompt_visible


PRE_BRIDGE_RECOVERY_ATTEMPT_LIMIT = 2
CODEX_CLI_GOAL_PRIVATE_TUI_TAIL_MAX_LINES = 160
CODEX_CLI_GOAL_PRIVATE_TUI_TAIL_MAX_CHARS = 60000
CODEX_CLI_GOAL_POST_BRIDGE_CONTINUE_PROMPT = (
    "Continue the active SkillsBench goal after the transient model timeout. "
    "If ./skillsbench-task-prompt.md exists, read it before acting. Use the "
    "private bridge command from the task instructions for one task-facing "
    "action, then finish with compact status."
)
CODEX_CLI_GOAL_POST_BRIDGE_CLOSEOUT_PROMPT = (
    "Close out the active SkillsBench goal after repeated post-bridge model "
    "timeouts. Do not start a new investigation. If the task is complete, "
    "finish the active goal now with compact status. If the task is not "
    "complete, report the blocker compactly and end the active goal."
)
POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT = 6
POST_BRIDGE_CLOSEOUT_ATTEMPT_LIMIT = 8
TUI_BLOCKER_RECENT_LINE_WINDOW = 40


def write_private_codex_cli_goal_tui_tail(
    trace_dir_value: object,
    safe_stage: str,
    capture: object,
) -> dict[str, object]:
    """Persist a bounded private TUI tail and return public-safe metadata."""

    metadata: dict[str, object] = {
        "private_tui_tail_recorded": False,
        "private_tui_tail_ref": "",
        "private_tui_tail_line_count": 0,
    }
    if not trace_dir_value or not capture:
        return metadata
    tail_lines = str(capture).splitlines()[-CODEX_CLI_GOAL_PRIVATE_TUI_TAIL_MAX_LINES:]
    tail_text = "\n".join(tail_lines)
    if len(tail_text) > CODEX_CLI_GOAL_PRIVATE_TUI_TAIL_MAX_CHARS:
        tail_text = tail_text[-CODEX_CLI_GOAL_PRIVATE_TUI_TAIL_MAX_CHARS:]
    tail_text = tail_text.rstrip()
    if not tail_text:
        return metadata
    stage = "".join(
        ch if ch.isalnum() or ch == "_" else "_" for ch in str(safe_stage or "")
    ) or "unknown"
    tail_name = f"codex-cli-goal-tui-tail-{stage}-{uuid.uuid4().hex[:12]}.txt"
    try:
        private_dir = Path(str(trace_dir_value)).expanduser() / "private"
        private_dir.mkdir(parents=True, exist_ok=True)
        (private_dir / tail_name).write_text(tail_text + "\n", encoding="utf-8")
    except OSError:
        return metadata
    metadata["private_tui_tail_recorded"] = True
    metadata["private_tui_tail_ref"] = f"private/{tail_name}"
    metadata["private_tui_tail_line_count"] = len(tail_text.splitlines())
    return metadata


def _recent_capture_region(capture: str) -> str:
    lines = str(capture or "").splitlines()
    if len(lines) <= TUI_BLOCKER_RECENT_LINE_WINDOW:
        return "\n".join(lines)
    return "\n".join(lines[-TUI_BLOCKER_RECENT_LINE_WINDOW:])


def _capture_has_rate_limit(capture: str) -> bool:
    lowered = _recent_capture_region(capture).lower()
    return any(
        marker in lowered
        for marker in (
            "rate limit",
            "rate_limit",
            "too many requests",
            "status 429",
            "error 429",
        )
    )


def _capture_has_model_timeout(capture: str) -> bool:
    lowered = _recent_capture_region(capture).lower()
    return any(marker in lowered for marker in ("timed out", "timeout")) and any(
        marker in lowered for marker in ("model", "request", "error", "failed")
    )


def _capture_has_error_marker(capture: str) -> bool:
    lowered = _recent_capture_region(capture).lower()
    return any(
        marker in lowered
        for marker in ("error", "failed", "timed out", "timeout")
    )


def _capture_has_retry_affordance(capture: str) -> bool:
    lowered = _recent_capture_region(capture).lower()
    return any(marker in lowered for marker in ("press enter", "press return"))


def codex_cli_tui_pre_bridge_blocker_stage(
    capture: str,
    *,
    prompt_visible: bool,
) -> str:
    """Classify public-safe Codex CLI TUI blockers before bridge activity."""

    if not prompt_visible:
        return ""
    if _capture_has_rate_limit(capture):
        return "pre_bridge_tui_rate_limit"
    if _capture_has_model_timeout(capture):
        return "pre_bridge_tui_model_timeout"
    if _capture_has_error_marker(capture):
        return "pre_bridge_tui_error_prompt"
    return ""


def codex_cli_tui_pre_bridge_recovery_action(capture: str, *, stage: str) -> str:
    """Return a bounded recovery action before the first bridge request."""

    if stage not in {
        "pre_bridge_tui_model_timeout",
        "pre_bridge_tui_error_prompt",
    }:
        return ""
    if _capture_has_retry_affordance(capture):
        return "press_enter"
    if codex_cli_tui_input_prompt_visible(capture):
        return "typed_goal_resubmit"
    return ""


def codex_cli_tui_pre_bridge_recovery_skip_reason(
    capture: str,
    *,
    stage: str,
    recovery_action: str,
) -> str:
    """Return why no pre-bridge recovery action was taken."""

    if recovery_action:
        return ""
    if stage == "pre_bridge_tui_rate_limit":
        return "rate_limit_no_retry"
    if stage not in {
        "pre_bridge_tui_model_timeout",
        "pre_bridge_tui_error_prompt",
    }:
        return ""
    if not _capture_has_retry_affordance(capture) and not codex_cli_tui_input_prompt_visible(
        capture
    ):
        return "no_retry_affordance"
    return "unsupported_recovery_action"


def codex_cli_tui_pre_bridge_terminal_stage(
    capture: str,
    *,
    prompt_visible: bool,
) -> str:
    """Classify a terminal goal that ended before any bridge activity."""

    if not prompt_visible:
        return ""
    if _capture_has_rate_limit(capture):
        return "pre_bridge_tui_rate_limit"
    if _capture_has_model_timeout(capture):
        return "pre_bridge_tui_model_timeout"
    if _capture_has_error_marker(capture):
        return "pre_bridge_tui_error_prompt"
    return ""


def codex_cli_tui_pre_bridge_terminal_skip_reason(
    capture: str,
    *,
    prompt_visible: bool,
) -> str:
    """Return public-safe flags for a terminal goal before bridge activity."""

    has_error_marker = _capture_has_error_marker(capture)
    return (
        f"pre_bridge_terminal:p={int(bool(prompt_visible))},"
        f"timeout={int(_capture_has_model_timeout(capture))},"
        f"rate={int(_capture_has_rate_limit(capture))},"
        f"retry={int(_capture_has_retry_affordance(capture))},"
        f"error={int(has_error_marker)}"
    )


def codex_cli_tui_post_bridge_blocker_stage(
    capture: str,
    *,
    prompt_visible: bool,
) -> str:
    """Classify public-safe Codex CLI TUI blockers after bridge activity."""

    if not prompt_visible:
        return ""
    if _capture_has_rate_limit(capture):
        return "post_bridge_tui_rate_limit"
    if _capture_has_model_timeout(capture):
        return "post_bridge_tui_model_timeout"
    if _capture_has_retry_affordance(capture) and _capture_has_error_marker(capture):
        return "post_bridge_tui_error_prompt"
    return ""


def codex_cli_tui_post_bridge_recovery_action(capture: str, *, stage: str) -> str:
    """Return a bounded public-safe recovery action for post-bridge TUI blockers."""

    if stage not in {
        "post_bridge_tui_model_timeout",
        "post_bridge_tui_error_prompt",
    }:
        return ""
    if _capture_has_retry_affordance(capture):
        return "press_enter"
    if (
        stage == "post_bridge_tui_model_timeout"
        and codex_cli_tui_input_prompt_visible(capture)
    ):
        return "typed_continue"
    return ""


def codex_cli_tui_post_bridge_recovery_skip_reason(
    capture: str,
    *,
    stage: str,
    recovery_action: str,
) -> str:
    """Return why no post-bridge recovery action was taken."""

    if recovery_action:
        return ""
    if stage == "post_bridge_tui_rate_limit":
        return "rate_limit_no_retry"
    if stage not in {
        "post_bridge_tui_model_timeout",
        "post_bridge_tui_error_prompt",
    }:
        return ""
    if not _capture_has_retry_affordance(capture):
        return "no_retry_affordance"
    return "unsupported_recovery_action"


def codex_cli_tui_post_bridge_closeout_recovery_action(
    *,
    recovery_action: str,
    recovery_attempt_count: int,
    closeout_attempted: bool,
    closeout_attempt_count: int = 0,
) -> str:
    """Return the final bounded closeout action after continue retries are spent."""

    if recovery_action not in {"press_enter", "typed_continue"}:
        return ""
    if recovery_attempt_count < POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT:
        return ""
    effective_closeout_count = max(
        int(closeout_attempted),
        max(0, int(closeout_attempt_count or 0)),
    )
    if effective_closeout_count >= POST_BRIDGE_CLOSEOUT_ATTEMPT_LIMIT:
        return ""
    return "typed_closeout"
