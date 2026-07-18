from __future__ import annotations

from typing import Any

from .contract import TODO_STATUS_OPEN, todo_marker_for_status


def render_todo_markdown(payload: dict[str, Any]) -> str:
    if payload.get("command") == "list":
        lines = [
            "# LoopX Todo List",
            "",
            f"- ok: `{payload.get('ok')}`",
            f"- read_only: `{payload.get('read_only')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- role: `{payload.get('role')}`",
            f"- status_filter: `{payload.get('status_filter')}`",
            f"- source: `{payload.get('source')}`",
            f"- todo_count: `{payload.get('todo_count')}`",
            f"- state_file: `{payload.get('state_file')}`",
        ]
        if payload.get("agent_id_filter"):
            lines.extend(
                [
                    f"- agent_id_filter: `{payload.get('agent_id_filter')}`",
                    f"- unfiltered_todo_count: `{payload.get('unfiltered_todo_count')}`",
                    f"- filter_semantics: `{payload.get('filter_semantics')}`",
                ]
            )
        projection = payload.get("state_event_projection")
        if isinstance(projection, dict):
            lines.extend(
                [
                    f"- event_log: `{projection.get('event_log')}`",
                    f"- source_event_count: `{projection.get('source_event_count')}`",
                    f"- last_event_id: `{projection.get('last_event_id')}`",
                ]
            )
        for key, heading in (
            ("user_todos", "User Todo"),
            ("agent_todos", "Agent Todo"),
        ):
            summary = payload.get(key)
            if not isinstance(summary, dict):
                continue
            lines.extend(["", f"## {heading}", ""])
            items = summary.get("items") or []
            if not items:
                lines.append("- none")
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                marker = todo_marker_for_status(item.get("status") or TODO_STATUS_OPEN)
                text = item.get("text") or item.get("title") or ""
                metadata = []
                for metadata_key in (
                    "todo_id",
                    "status",
                    "task_class",
                    "action_kind",
                    "task_repository",
                    "continuation_policy",
                    "claimed_by",
                    "bound_agent",
                    "goal_bound",
                    "blocks_agent",
                    "global_gate",
                    "excluded_agents",
                    "target_key",
                    "cadence",
                    "next_due_at",
                    "expires_at",
                ):
                    if item.get(metadata_key):
                        metadata.append(f"{metadata_key}={item.get(metadata_key)}")
                suffix = f" <!-- {' '.join(metadata)} -->" if metadata else ""
                lines.append(f"- [{marker}] {text}{suffix}")
        if payload.get("error"):
            lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)

    lines = [
        "# LoopX Todo",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- role: `{payload.get('role')}`",
        f"- section: `{payload.get('section')}`",
        f"- state_file: `{payload.get('state_file')}`",
    ]
    if "moved_count" in payload:
        lines.extend(
            [
                f"- changed: `{payload.get('changed')}`",
                f"- archive_section: `{payload.get('archive_section')}`",
                f"- active_done_before: `{payload.get('active_done_before')}`",
                f"- active_done_after: `{payload.get('active_done_after')}`",
                f"- max_active_done: `{payload.get('max_active_done')}`",
                f"- moved_count: `{payload.get('moved_count')}`",
            ]
        )
    else:
        lines.extend(
            [
                f"- changed: `{payload.get('changed')}`",
                f"- added: `{payload.get('added')}`",
                f"- already_exists: `{payload.get('already_exists')}`",
                f"- todo_id: `{payload.get('todo_id')}`",
                f"- status: `{payload.get('status')}`",
                f"- required_capabilities: `{payload.get('required_capabilities')}`",
                f"- target_capabilities: `{payload.get('target_capabilities')}`",
                f"- claimed_by: `{payload.get('claimed_by')}`",
                f"- bound_agent: `{payload.get('bound_agent')}`",
                f"- goal_bound: `{payload.get('goal_bound')}`",
                f"- blocks_agent: `{payload.get('blocks_agent')}`",
                f"- excluded_agents: `{payload.get('excluded_agents')}`",
                f"- global_gate: `{payload.get('global_gate')}`",
                f"- resume_when: `{payload.get('resume_when')}`",
                f"- target_key: `{payload.get('target_key')}`",
                f"- cadence: `{payload.get('cadence')}`",
                f"- next_due_at: `{payload.get('next_due_at')}`",
                f"- expires_at: `{payload.get('expires_at')}`",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    elif "todo" in payload:
        marker = todo_marker_for_status(payload.get("status") or TODO_STATUS_OPEN)
        lines.extend(["", "## Todo", "", f"- [{marker}] {payload.get('todo')}"])
    correctness = payload.get("local_state_write_correctness")
    if isinstance(correctness, dict):
        intent = correctness.get("write_intent") if isinstance(correctness.get("write_intent"), dict) else {}
        apply_result = (
            correctness.get("apply_result")
            if isinstance(correctness.get("apply_result"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Local State Write Correctness",
                "",
                f"- schema_version: `{correctness.get('schema_version')}`",
                f"- write_id: `{intent.get('write_id')}`",
                f"- write_class: `{intent.get('write_class')}`",
                f"- idempotency_key: `{intent.get('idempotency_key')}`",
                f"- status: `{apply_result.get('status')}`",
            ]
        )
    return "\n".join(lines)
