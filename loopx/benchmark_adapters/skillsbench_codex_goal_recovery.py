from __future__ import annotations

from loopx.codex_cli_goal_tui import codex_cli_tui_input_prompt_visible


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
POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT = 4


def codex_cli_tui_post_bridge_blocker_stage(
    capture: str,
    *,
    prompt_visible: bool,
) -> str:
    """Classify public-safe Codex CLI TUI blockers after bridge activity."""

    if not prompt_visible:
        return ""
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
        return "post_bridge_tui_rate_limit"
    if any(marker in lowered for marker in ("timed out", "timeout")) and any(
        marker in lowered for marker in ("model", "request", "error", "failed")
    ):
        return "post_bridge_tui_model_timeout"
    if any(marker in lowered for marker in ("press enter", "press return")) and any(
        marker in lowered
        for marker in ("error", "failed", "timed out", "timeout", "model")
    ):
        return "post_bridge_tui_error_prompt"
    return ""


def codex_cli_tui_post_bridge_recovery_action(capture: str, *, stage: str) -> str:
    """Return a bounded public-safe recovery action for post-bridge TUI blockers."""

    if stage not in {
        "post_bridge_tui_model_timeout",
        "post_bridge_tui_error_prompt",
    }:
        return ""
    lowered = str(capture or "").lower()
    if any(marker in lowered for marker in ("press enter", "press return")):
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
    lowered = str(capture or "").lower()
    if not any(marker in lowered for marker in ("press enter", "press return")):
        return "no_retry_affordance"
    return "unsupported_recovery_action"


def codex_cli_tui_post_bridge_closeout_recovery_action(
    *,
    recovery_action: str,
    recovery_attempt_count: int,
    closeout_attempted: bool,
) -> str:
    """Return the final bounded closeout action after continue retries are spent."""

    if closeout_attempted:
        return ""
    if recovery_action not in {"press_enter", "typed_continue"}:
        return ""
    if recovery_attempt_count < POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT:
        return ""
    return "typed_closeout"
