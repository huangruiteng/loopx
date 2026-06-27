from __future__ import annotations

from typing import Any


def markdown_scalar(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def append_human_reward_markdown(lines: list[str], goal_id: Any, reward: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("recorded_at", "decision", "reward"):
        value = reward.get(field)
        if value:
            headline_parts.append(f"{field}={markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - human_reward: {' '.join(headline_parts)}")
    reason = reward.get("reason_summary")
    if reason:
        lines.append(f"      - reason_summary: {markdown_scalar(reason)}")
    follow_up = reward.get("follow_up")
    if follow_up:
        lines.append(f"      - follow_up: {markdown_scalar(follow_up)}")
    lesson = reward.get("lesson") if isinstance(reward.get("lesson"), dict) else {}
    if lesson:
        lines.append(
            "      - lesson: "
            f"kind={markdown_scalar(lesson.get('kind') or '')} "
            f"summary={markdown_scalar(lesson.get('summary') or '')}"
        )
        for field in ("avoid", "prefer"):
            values = lesson.get(field) if isinstance(lesson.get(field), list) else []
            if values:
                lines.append(
                    f"        - lesson_{field}: "
                    + ", ".join(markdown_scalar(value) for value in values[:5])
                )
    if goal_id:
        lines.append(
            "      - project_agent_visibility: "
            f"`loopx history --goal-id {markdown_scalar(goal_id)} --limit 3`"
        )


def append_operator_gate_resume_contract_markdown(lines: list[str], contract: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("version", "gate_id", "operator_decision"):
        value = contract.get(field)
        if value:
            headline_parts.append(f"{field}={markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - operator_gate_resume_contract: {' '.join(headline_parts)}")
    for field in (
        "latest_state_ref",
        "freshness_check",
        "precondition_check",
        "migration_or_rebase_result",
        "validation_after_resume",
    ):
        value = contract.get(field)
        if value:
            lines.append(f"      - {field}: {markdown_scalar(value)}")

