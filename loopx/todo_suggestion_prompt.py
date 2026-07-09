from __future__ import annotations

from pathlib import Path
from typing import Any


TODO_SUGGESTION_PROMPT_SCHEMA_VERSION = "todo_suggestion_prompt_v0"
SUGGESTED_TODO_CANDIDATE_SCHEMA_VERSION = "suggested_todo_candidate_v0"
DEFAULT_SUGGESTION_LIMIT = 3
MAX_SUGGESTION_LIMIT = 5
ALLOWED_TODO_SUGGESTION_SOURCES = (
    "recent-repo",
    "issues-prs",
    "failing-checks",
    "todo-markers",
    "complexity-hotspots",
    "loopx-deferred",
    "docs-smokes",
)
DEFAULT_TODO_SUGGESTION_SOURCES = (
    "recent-repo",
    "issues-prs",
    "failing-checks",
    "todo-markers",
    "loopx-deferred",
    "docs-smokes",
)
ALLOWED_TODO_SUGGESTION_TRIGGERS = (
    "user-requested",
    "post-connect",
    "no-runnable-todo",
    "repo-changed",
    "quality-watch",
)


def normalize_suggestion_sources(sources: list[str] | None) -> list[str]:
    raw_sources = sources or list(DEFAULT_TODO_SUGGESTION_SOURCES)
    normalized: list[str] = []
    for source in raw_sources:
        compact = str(source or "").strip()
        if compact not in ALLOWED_TODO_SUGGESTION_SOURCES:
            raise ValueError(f"unsupported todo suggestion source: {compact}")
        if compact not in normalized:
            normalized.append(compact)
    return normalized


def effective_suggestion_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_SUGGESTION_LIMIT
    if limit < 1:
        raise ValueError("todo suggestion --limit must be at least 1")
    return min(limit, MAX_SUGGESTION_LIMIT)


def _project_hint(project: Path | None) -> str:
    if project is None:
        return "current project root"
    return str(project)


def build_todo_suggestion_prompt_packet(
    *,
    goal_id: str,
    project: Path | None = None,
    agent_id: str | None = None,
    sources: list[str] | None = None,
    limit: int | None = None,
    trigger: str | None = None,
) -> dict[str, Any]:
    """Build an agent-facing prompt for candidate todo discovery.

    LoopX intentionally does not inspect the repository here. The packet tells
    the user's current project agent how to perform a bounded read-only analysis
    and how to return a decision queue without writing formal LoopX todos.
    """

    if not goal_id.strip():
        raise ValueError("goal_id is required")
    selected_sources = normalize_suggestion_sources(sources)
    selected_trigger = trigger or "user-requested"
    if selected_trigger not in ALLOWED_TODO_SUGGESTION_TRIGGERS:
        raise ValueError(f"unsupported todo suggestion trigger: {selected_trigger}")
    selected_limit = effective_suggestion_limit(limit)
    requested_limit = limit if limit is not None else DEFAULT_SUGGESTION_LIMIT
    project_hint = _project_hint(project)
    agent_label = agent_id or "current project agent"
    source_text = ", ".join(selected_sources)
    quality_watch_note = (
        "\n\nBecause this is a `quality-watch` turn, compare fresh signals against the "
        "last known state first. Return candidates only for new or still-uncovered "
        "evidence; otherwise return an empty list with a short rationale."
        if selected_trigger == "quality-watch"
        else ""
    )

    task_body = f"""Generate a bounded candidate todo decision queue for LoopX goal `{goal_id}`.

You are `{agent_label}` operating in the current project. LoopX is only giving
you the analysis contract; LoopX is not analyzing the repository itself.

Read the current repo and recent project signals in read-only mode. Use these
source lanes when available: {source_text}. Prefer public-safe evidence such as
repo-relative paths, commit or PR identifiers, failing check names, TODO/FIXME
locations, LoopX deferred todo ids, and docs/smoke gaps. Do not include raw logs,
credentials, private material, local absolute paths, issue bodies, or chat
transcripts.

Return at most {selected_limit} items in a `suggested_todos` list. These are
decision candidates, not formal LoopX todos. Do not call `loopx todo add`,
`loopx todo update`, `loopx todo complete`, or edit LoopX state in this turn.
If the evidence is weak or already covered by existing runnable todos, return an
empty list with a short rationale.
{quality_watch_note}

Each candidate must use schema `{SUGGESTED_TODO_CANDIDATE_SCHEMA_VERSION}` and
include: `candidate_id`, `title`, `why_now`, `evidence`, `first_safe_action`,
`requires_user_decision`, `risk`, `value`, `confidence`, `suggested_owner_agent`,
and `promotion_preview`. `promotion_preview` should be a public-safe
`loopx todo add ...` command draft, but it must not be executed unless the user
or primary controller explicitly promotes the candidate.

Keep user gates separate: a candidate is not a user todo. Only set
`requires_user_decision=true` when the first safe action genuinely needs owner
choice, protected access, external action, or private material approval."""

    return {
        "ok": True,
        "schema_version": TODO_SUGGESTION_PROMPT_SCHEMA_VERSION,
        "goal_id": goal_id,
        "mode": "agent_guided_candidate_todo_queue",
        "analysis_owner": "user_project_agent",
        "loopx_role": "prompt_contract_only",
        "agent_id": agent_id,
        "project": project_hint,
        "trigger": selected_trigger,
        "sources": selected_sources,
        "requested_limit": requested_limit,
        "effective_limit": selected_limit,
        "max_limit": MAX_SUGGESTION_LIMIT,
        "state_write_performed": False,
        "formal_todos_written": False,
        "candidate_queue_field": "suggested_todos",
        "candidate_schema_version": SUGGESTED_TODO_CANDIDATE_SCHEMA_VERSION,
        "task_body": task_body,
        "expected_candidate_fields": [
            "candidate_id",
            "title",
            "why_now",
            "evidence",
            "first_safe_action",
            "requires_user_decision",
            "risk",
            "value",
            "confidence",
            "suggested_owner_agent",
            "promotion_preview",
        ],
        "promotion_policy": {
            "default_state": "candidate_only",
            "who_may_promote": ["user", "primary_controller"],
            "promotion_command": "loopx todo add --goal-id <goal-id> --role agent --text <approved candidate>",
            "do_not_execute_in_suggestion_turn": True,
        },
        "frequency_policy": {
            "default_limit": DEFAULT_SUGGESTION_LIMIT,
            "hard_limit": MAX_SUGGESTION_LIMIT,
            "recommended_triggers": list(ALLOWED_TODO_SUGGESTION_TRIGGERS),
            "avoid_every_heartbeat": True,
        },
    }


def render_todo_suggestion_prompt_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Todo Suggestion Prompt",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- analysis_owner: `{payload.get('analysis_owner')}`",
        f"- loopx_role: `{payload.get('loopx_role')}`",
        f"- state_write_performed: `{payload.get('state_write_performed')}`",
        f"- formal_todos_written: `{payload.get('formal_todos_written')}`",
        f"- effective_limit: `{payload.get('effective_limit')}`",
        f"- sources: `{', '.join(payload.get('sources') or [])}`",
        "",
        "## Agent Task Body",
        "",
        "```text",
        str(payload.get("task_body") or "").rstrip(),
        "```",
        "",
        "## Promotion Policy",
        "",
        "- Suggested items are decision candidates, not formal LoopX todos.",
        "- Only the user or primary controller should promote a candidate.",
        "- Promotion uses `loopx todo add` after explicit approval.",
    ]
    if payload.get("error"):
        lines.extend(["", "## Error", "", str(payload.get("error"))])
    return "\n".join(lines) + "\n"
