"""Issue-fix fields and views for the generic Lark Kanban sink."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any


DEFAULT_ISSUE_FIX_GRID_VIEW = "Issue Fix Outcomes"
DEFAULT_ISSUE_FIX_KANBAN_VIEW = "Issue Fix Kanban"

ISSUE_FIX_CARD_FIELDS = [
    "Task",
    "Repository",
    "Issue",
    "Pull Request",
    "Route",
    "Stage",
    "Validation",
    "Outcome",
    "Status",
]

ISSUE_FIX_STAGE_OPTIONS = [
    "reproduction_planned",
    "fix_in_progress",
    "fix_review_ready",
    "ci_pending",
    "ci_failed",
    "review_wait",
    "changes_requested",
    "merge_ready",
    "reproduction_blocked",
    "fix_blocked",
    "delivery_blocked",
    "draft_pr",
    "branch_stale_or_conflicted",
    "pr_open",
    "merged",
    "closed_without_merge",
    "comment_packet",
    "comment_blocked",
    "comment_published",
    "triage_complete",
]


def issue_fix_field_definitions(
    select_options: Callable[[list[str]], list[dict[str, str]]],
) -> list[dict[str, Any]]:
    return [
        {
            "name": "Work Item Type",
            "type": "select",
            "multiple": False,
            "options": select_options(["Todo", "Issue Fix"]),
        },
        {"name": "Repository", "type": "text", "style": {"type": "plain"}},
        {"name": "Issue", "type": "text", "style": {"type": "url"}},
        {"name": "Pull Request", "type": "text", "style": {"type": "url"}},
        {
            "name": "Route",
            "type": "select",
            "multiple": False,
            "options": select_options(["fix_pr", "comment_only", "triage_only"]),
        },
        {
            "name": "Stage",
            "type": "select",
            "multiple": False,
            "options": select_options(ISSUE_FIX_STAGE_OPTIONS),
        },
        {"name": "Validation", "type": "text", "style": {"type": "plain"}},
        {"name": "Outcome", "type": "text", "style": {"type": "plain"}},
    ]


def issue_fix_views() -> list[dict[str, str]]:
    return [
        {"name": DEFAULT_ISSUE_FIX_GRID_VIEW, "type": "grid"},
        {"name": DEFAULT_ISSUE_FIX_KANBAN_VIEW, "type": "kanban"},
    ]


def issue_fix_record_values(
    block: Mapping[str, Any],
    *,
    compact_text: Callable[..., str],
) -> dict[str, Any]:
    if str(block.get("action_kind") or "") != "issue_fix_outcome":
        return {}
    issue = block.get("issue") if isinstance(block.get("issue"), Mapping) else {}
    pull_request = (
        block.get("pull_request")
        if isinstance(block.get("pull_request"), Mapping)
        else {}
    )
    validation = (
        block.get("validation") if isinstance(block.get("validation"), Mapping) else {}
    )
    result = block.get("result") if isinstance(block.get("result"), Mapping) else {}
    issue_number = issue.get("number")
    pr_number = pull_request.get("number")
    issue_url = compact_text(issue.get("url"), limit=320)
    pr_url = compact_text(pull_request.get("url"), limit=320)
    validation_status = compact_text(validation.get("status"), limit=80)
    validation_label = compact_text(validation.get("label"), limit=220)
    return {
        "Work Item Type": "Issue Fix",
        "Repository": compact_text(block.get("repo"), limit=160),
        "Issue": issue_url
        or (
            f"#{issue_number}"
            if issue_number is not None
            else compact_text(block.get("issue_ref"), limit=80)
        ),
        "Pull Request": pr_url
        or (
            f"#{pr_number}"
            if pr_number is not None
            else compact_text(pull_request.get("ref"), limit=80)
        ),
        "Route": compact_text(block.get("route"), limit=80),
        "Stage": compact_text(block.get("stage"), limit=80),
        "Validation": compact_text(
            ": ".join(part for part in (validation_status, validation_label) if part),
            limit=300,
        ),
        "Outcome": compact_text(result.get("kind"), limit=120),
    }


def todo_record_values() -> dict[str, str]:
    return {
        "Work Item Type": "Todo",
        "Repository": "",
        "Issue": "",
        "Pull Request": "",
        "Route": "",
        "Stage": "",
        "Validation": "",
        "Outcome": "",
    }


def extract_field_names(parsed: Any) -> set[str]:
    if isinstance(parsed, dict):
        fields = parsed.get("fields")
        if isinstance(fields, list):
            return {
                str(item.get("name") or "").strip()
                for item in fields
                if isinstance(item, Mapping) and str(item.get("name") or "").strip()
            }
        for value in parsed.values():
            names = extract_field_names(value)
            if names:
                return names
    if isinstance(parsed, list):
        for value in parsed:
            names = extract_field_names(value)
            if names:
                return names
    return set()


def missing_field_definitions(
    parsed: Any, definitions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing = extract_field_names(parsed)
    return [item for item in definitions if str(item.get("name") or "").strip() not in existing]


def issue_fix_view_configuration_commands(
    *,
    cli_bin: str,
    identity: str,
    base_token: str,
    table_id: str,
    view_ids: dict[str, str],
) -> list[list[str]]:
    issue_grid_view = (
        view_ids.get(DEFAULT_ISSUE_FIX_GRID_VIEW) or DEFAULT_ISSUE_FIX_GRID_VIEW
    )
    issue_kanban_view = (
        view_ids.get(DEFAULT_ISSUE_FIX_KANBAN_VIEW) or DEFAULT_ISSUE_FIX_KANBAN_VIEW
    )
    common = [
        cli_bin,
        "base",
        "--as",
        identity,
        "--base-token",
        base_token,
        "--table-id",
        table_id,
    ]
    commands = [
        [
            *common[:2],
            "+field-update",
            *common[2:],
            "--field-id",
            definition["name"],
            "--json",
            json.dumps(definition, ensure_ascii=False),
            "--yes",
        ]
        for definition in issue_fix_field_definitions(
            lambda options: [
                {"name": option, "hue": "Blue", "lightness": "Light"}
                for option in options
            ]
        )
        if definition["name"] in {"Issue", "Pull Request", "Stage"}
    ]
    commands.extend(
        [
            *common[:2],
            "+view-set-filter",
            *common[2:],
            "--view-id",
            view_id,
            "--json",
            json.dumps(
                {
                    "logic": "and",
                    "conditions": [["Work Item Type", "intersects", ["Issue Fix"]]],
                },
                ensure_ascii=False,
            ),
        ]
        for view_id in (issue_grid_view, issue_kanban_view)
    )
    commands.append(
        [
            *common[:2],
            "+view-set-group",
            *common[2:],
            "--view-id",
            issue_kanban_view,
            "--json",
            json.dumps(
                {"group_config": [{"field": "Stage", "desc": False}]},
                ensure_ascii=False,
            ),
        ]
    )
    commands.extend(
        [
            *common[:2],
            "+view-set-visible-fields",
            *common[2:],
            "--view-id",
            view_id,
            "--json",
            json.dumps({"visible_fields": ISSUE_FIX_CARD_FIELDS}, ensure_ascii=False),
        ]
        for view_id in (issue_grid_view, issue_kanban_view)
    )
    return commands


def view_configuration_commands(
    *,
    cli_bin: str,
    identity: str,
    base_token: str,
    table_id: str,
    view_ids: dict[str, str],
    worker_view_name: str,
    todo_statuses: list[str],
    user_gate_status: str,
    operator_card_fields: list[str],
) -> list[list[str]]:
    worker_view = view_ids.get(worker_view_name) or worker_view_name
    user_gate_view = view_ids.get("User Gates") or "User Gates"
    kanban_view = view_ids.get("Kanban") or "Kanban"
    common = [
        "--as",
        identity,
        "--base-token",
        base_token,
        "--table-id",
        table_id,
    ]
    commands = [
        [
            cli_bin,
            "base",
            "+view-set-filter",
            *common,
            "--view-id",
            worker_view,
            "--json",
            json.dumps(
                {
                    "logic": "and",
                    "conditions": [["Status", "intersects", todo_statuses]],
                },
                ensure_ascii=False,
            ),
        ],
        [
            cli_bin,
            "base",
            "+view-set-filter",
            *common,
            "--view-id",
            user_gate_view,
            "--json",
            json.dumps(
                {
                    "logic": "and",
                    "conditions": [["Status", "intersects", [user_gate_status]]],
                },
                ensure_ascii=False,
            ),
        ],
        [
            cli_bin,
            "base",
            "+view-set-group",
            *common,
            "--view-id",
            kanban_view,
            "--json",
            json.dumps(
                {"group_config": [{"field": "Status", "desc": False}]},
                ensure_ascii=False,
            ),
        ],
        [
            cli_bin,
            "base",
            "+view-set-visible-fields",
            *common,
            "--view-id",
            kanban_view,
            "--json",
            json.dumps({"visible_fields": operator_card_fields}, ensure_ascii=False),
        ],
    ]
    commands.extend(
        issue_fix_view_configuration_commands(
            cli_bin=cli_bin,
            identity=identity,
            base_token=base_token,
            table_id=table_id,
            view_ids=view_ids,
        )
    )
    return commands
