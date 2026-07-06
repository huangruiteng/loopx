#!/usr/bin/env python3
"""Smoke-test the live status agent management projection."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.agents.management_projection import (  # noqa: E402
    AGENT_MANAGEMENT_PROJECTION_SCHEMA_VERSION,
    AGENT_MANAGEMENT_MODE,
    TODO_ROW_SCHEMA_VERSION,
    build_agent_management_projection,
)


FORBIDDEN_ACTION_KEYS = {
    "task_id",
    "action_url",
    "claim_url",
    "dispatch_url",
    "reclaim_url",
    "cancel_url",
    "unblock_url",
    "write_command",
    "delete_command",
    "archive_command",
    "merge_command",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that agent_management_projection_v0 is available from "
            "status as a read-only view over existing todos/evidence/handoffs."
        )
    )
    parser.add_argument(
        "--goal-id",
        help="Optional live goal id. When omitted, the bundled public example and synthetic fixture are checked.",
    )
    parser.add_argument("--agent-id", help="Expected agent row in the live status projection.")
    parser.add_argument(
        "--registry",
        default=str(Path.home() / ".codex" / "loopx" / "registry.global.json"),
        help="LoopX registry path. Defaults to the shared global registry.",
    )
    parser.add_argument("--runtime-root", help="Optional LoopX runtime root.")
    return parser.parse_args()


def assert_no_write_action_keys(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_ACTION_KEYS:
                raise AssertionError(f"projection exposed writable action key {child_path}")
            if key == "write_api" and child is not False:
                raise AssertionError(f"projection write_api must be false at {child_path}")
            assert_no_write_action_keys(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_write_action_keys(child, path=f"{path}[{index}]")


def assert_projection_shape(
    projection: dict[str, Any],
    *,
    expected_agent_id: str | None = None,
    require_handoff: bool = False,
) -> None:
    assert projection.get("schema_version") == AGENT_MANAGEMENT_PROJECTION_SCHEMA_VERSION, projection
    assert projection.get("mode") == AGENT_MANAGEMENT_MODE, projection
    truth = projection.get("truth_contract") if isinstance(projection.get("truth_contract"), dict) else {}
    assert truth.get("todo_is_runtime_work_item") is True, truth
    assert truth.get("projection_is_writable") is False, truth
    assert truth.get("introduces_task_runtime") is False, truth
    assert truth.get("write_api") is False, truth
    assert_no_write_action_keys(projection)

    agents = projection.get("agents") if isinstance(projection.get("agents"), list) else []
    assert agents, "projection should include at least one agent row"
    if expected_agent_id:
        assert any(row.get("agent_id") == expected_agent_id for row in agents if isinstance(row, dict)), agents

    current_rows = [
        row
        for row in agents
        if isinstance(row, dict)
        and isinstance(row.get("current_todo"), dict)
        and row["current_todo"].get("todo_id")
    ]
    assert current_rows, "projection should include a current_todo with the source todo_id"
    for row in current_rows:
        assert row["current_todo"].get("schema_version") == TODO_ROW_SCHEMA_VERSION, row

    if require_handoff:
        assert any(
            isinstance(row, dict) and row.get("handoff_refs")
            for row in agents
        ), "live projection should carry at least one handoff ref from existing todo/evidence state"


def fixture_status_payload() -> dict[str, Any]:
    return {
        "goal_filter": "fixture-goal",
        "run_history": {
            "goals": [
                {
                    "id": "fixture-goal",
                    "coordination": {
                        "primary_agent": "agent-main",
                        "registered_agents": ["agent-main", "agent-reviewer"],
                    },
                }
            ]
        },
        "attention_queue": {
            "items": [
                {
                    "goal_id": "fixture-goal",
                    "agent_todos": {
                        "items": [
                            {
                                "index": 1,
                                "done": False,
                                "text": "Review the read-only projection.",
                                "todo_id": "todo_live_handoff",
                                "role": "agent",
                                "status": "open",
                                "priority": "P1",
                                "title": "Review the read-only projection.",
                                "task_class": "advancement_task",
                                "action_kind": "review_projection",
                                "claimed_by": "agent-reviewer",
                                "required_write_scopes": ["apps/dashboard/**"],
                                "workspace_ref": {
                                    "kind": "worktree",
                                    "label": "agent-reviewer-worktree",
                                    "path_safe": False,
                                    "branch": "codex/agent-reviewer",
                                },
                                "updated_at": "2026-01-01T00:00:00Z",
                                "handoff_note": {
                                    "schema_version": "handoff_note_v0",
                                    "handoff_id": "handoff_live_handoff",
                                    "todo_id": "todo_live_handoff",
                                    "from_agent": "agent-main",
                                    "to_agent": "agent-reviewer",
                                    "intent": "review_projection",
                                    "summary": "Display-only review.",
                                    "evidence_refs": ["run:fixture-refresh"],
                                    "suggested_next_action": "Read the display-only row.",
                                },
                            }
                        ]
                    },
                }
            ]
        },
        "todo_index": {
            "items": [
                {
                    "goal_id": "fixture-goal",
                    "index": 2,
                    "done": False,
                    "text": "Agent-id fallback row.",
                    "todo_id": "todo_agent_id_fallback",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                    "title": "Agent-id fallback row.",
                    "task_class": "advancement_task",
                    "action_kind": "agent_id_fallback",
                    "agent_id": "agent-main",
                    "latest_event_kind": "todo_update",
                    "latest_event_at": "2026-07-05T00:01:00Z",
                }
            ]
        },
    }


def assert_synthetic_projection() -> None:
    projection = build_agent_management_projection(fixture_status_payload())
    assert_projection_shape(projection, expected_agent_id="agent-reviewer", require_handoff=True)
    by_agent = {
        row.get("agent_id"): row
        for row in projection.get("agents", [])
        if isinstance(row, dict)
    }
    assert by_agent["agent-main"]["role"] == "primary", by_agent
    assert by_agent["agent-main"]["current_todo"]["todo_id"] == "todo_agent_id_fallback", by_agent
    assert by_agent["agent-reviewer"]["current_todo"]["todo_id"] == "todo_live_handoff", by_agent
    assert by_agent["agent-reviewer"]["handoff_refs"] == ["handoff_live_handoff"], by_agent
    assert "run:fixture-refresh" in by_agent["agent-reviewer"]["evidence_refs"], by_agent
    workspace_ref = by_agent["agent-reviewer"].get("workspace_ref")
    assert workspace_ref.get("kind") == "worktree", by_agent
    assert workspace_ref.get("path_safe") is False, by_agent
    assert "apps/dashboard/**" in workspace_ref.get("write_scope", []), by_agent
    stale_hint = by_agent["agent-reviewer"].get("stale_claim_hint")
    assert stale_hint.get("state") == "suspected_stale", by_agent
    assert stale_hint.get("claimed_by") == "agent-reviewer", by_agent
    assert "reclaim_url" not in json.dumps(stale_hint, sort_keys=True), stale_hint


def assert_bundled_public_example() -> dict[str, Any]:
    payload = json.loads((REPO_ROOT / "examples" / "status.example.json").read_text(encoding="utf-8"))
    projection = payload.get("agent_management_projection")
    assert isinstance(projection, dict), "bundled example should expose agent_management_projection"
    assert_projection_shape(projection, expected_agent_id="codex-value-explorer", require_handoff=False)
    source_summary = projection.get("source_summary") if isinstance(projection.get("source_summary"), dict) else {}
    assert source_summary.get("todo_source") == "live_loopx_status_public_slice", source_summary
    assert source_summary.get("public_safe_export") is True, source_summary
    agent_ids = {
        row.get("agent_id")
        for row in projection.get("agents", [])
        if isinstance(row, dict)
    }
    expected_agents = {
        "codex-main-control",
        "codex-product-capability",
        "codex-side-bypass",
        "codex-value-explorer",
    }
    assert expected_agents.issubset(agent_ids), agent_ids
    todo_ids = {
        row.get("current_todo", {}).get("todo_id")
        for row in projection.get("agents", [])
        if isinstance(row, dict) and isinstance(row.get("current_todo"), dict)
    }
    assert "todo_2bf560b48a0c" in todo_ids, todo_ids
    assert "todo_584f55f8f3b4" in todo_ids, todo_ids
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden_snippets = (
        "todo_example_",
        "experiment-controller-goal",
        "department-",
        "department_",
        ".local",
        "/Users/",
        "/private/",
        "/tmp/",
        "AK=",
        "SK=",
    )
    for snippet in forbidden_snippets:
        assert snippet not in rendered, f"bundled example leaked {snippet}"
    return {
        "agent_rows": len(projection.get("agents") or []),
        "todo_source": source_summary.get("todo_source"),
    }


def run_loopx_status(args: argparse.Namespace) -> dict[str, Any]:
    cli = [sys.executable, "-m", "loopx.cli", "--registry", args.registry]
    if args.runtime_root:
        cli.extend(["--runtime-root", args.runtime_root])
    cli.extend(["--format", "json", "status", "--limit", "20"])
    if args.goal_id:
        cli.extend(["--goal-id", args.goal_id])
    if args.agent_id:
        cli.extend(["--agent-id", args.agent_id])
    result = subprocess.run(
        cli,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def assert_live_projection(args: argparse.Namespace) -> dict[str, Any]:
    payload = run_loopx_status(args)
    assert payload.get("ok") is True, payload
    projection = payload.get("agent_management_projection")
    assert isinstance(projection, dict), "status should expose agent_management_projection"
    assert_projection_shape(
        projection,
        expected_agent_id=args.agent_id,
        require_handoff=False,
    )
    if args.agent_id:
        expected = next(
            (
                row
                for row in projection.get("agents", [])
                if isinstance(row, dict) and row.get("agent_id") == args.agent_id
            ),
            {},
        )
        assert isinstance(expected.get("current_todo"), dict), expected
        assert expected["current_todo"].get("todo_id"), expected
    return {
        "goal_id": args.goal_id,
        "agent_id": args.agent_id,
        "agent_rows": len(projection.get("agents") or []),
        "current_todo_rows": sum(
            1
            for row in projection.get("agents", [])
            if isinstance(row, dict) and isinstance(row.get("current_todo"), dict)
        ),
        "handoff_rows": sum(
            1
            for row in projection.get("agents", [])
            if isinstance(row, dict) and row.get("handoff_refs")
        ),
    }


def main() -> int:
    args = parse_args()
    assert_synthetic_projection()
    result: dict[str, Any] = {
        "synthetic": "ok",
        "bundled_example": assert_bundled_public_example(),
    }
    if args.goal_id:
        result["live"] = assert_live_projection(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
