from __future__ import annotations

from loopx.codex_cli_goal_tui import codex_cli_tui_input_prompt_visible


PRE_BRIDGE_RECOVERY_ATTEMPT_LIMIT = 2
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


def _capture_has_rate_limit(capture: str) -> bool:
    lowered = str(capture or "").lower()
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
    lowered = str(capture or "").lower()
    return any(marker in lowered for marker in ("timed out", "timeout")) and any(
        marker in lowered for marker in ("model", "request", "error", "failed")
    )


def _capture_has_retry_affordance(capture: str) -> bool:
    lowered = str(capture or "").lower()
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
    lowered = str(capture or "").lower()
    if _capture_has_retry_affordance(capture) and any(
        marker in lowered
        for marker in ("error", "failed", "timed out", "timeout", "model")
    ):
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
    if stage == "pre_bridge_tui_model_timeout" and codex_cli_tui_input_prompt_visible(
        capture
    ):
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
    lowered = str(capture or "").lower()
    if _capture_has_retry_affordance(capture) and any(
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
