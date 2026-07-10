#!/usr/bin/env python3
"""Smoke-test multi-agent user gate scope enforcement."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.contract import check_contract  # noqa: E402
from loopx.control_plane.todos.todo_summary import active_state_todo_attention_item  # noqa: E402
from loopx.quota import build_quota_should_run  # noqa: E402
from loopx.status import collect_status  # noqa: E402
from loopx.todos import add_goal_todo, complete_goal_todo, update_goal_todo  # noqa: E402


GOAL_ID = "user-gate-scope-smoke"
PRIMARY_AGENT = "codex-main-control"
SIDE_AGENT = "codex-product-capability"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    repo = root / "repo"
    repo.mkdir()
    state = repo / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "\n".join(
            [
                "---",
                f"goal_id: {GOAL_ID}",
                "updated_at: 2026-06-26T00:00:00+00:00",
                "---",
                "",
                "## Agent Todo",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    registry = root / "registry.global.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "harness_self_improvement",
                        "status": "active",
                        "repo": str(repo),
                        "state_file": "ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "harness_self_improvement"},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return repo, state, registry


def assert_raises_message(action: Callable[[], object], expected: str) -> None:
    try:
        action()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
        return
    raise AssertionError(f"expected ValueError containing {expected!r}")


def insert_before_agent_section(state: Path, block: str) -> None:
    text = state.read_text(encoding="utf-8")
    marker = "\n## Agent Todo\n"
    assert marker in text, text
    state.write_text(text.replace(marker, f"\n{block.rstrip()}\n{marker}", 1), encoding="utf-8")


def assert_user_action_does_not_drive_active_state_attention() -> None:
    item = active_state_todo_attention_item(
        {"id": GOAL_ID},
        {
            "user_todos": {
                "open_count": 1,
                "first_open_items": [
                    {
                        "text": "Track a non-blocking owner note.",
                        "task_class": "user_action",
                    }
                ],
            },
            "agent_todos": {
                "open_count": 1,
                "first_open_items": [
                    {
                        "text": "Deliver a product-capability slice.",
                        "task_class": "advancement_task",
                    }
                ],
            },
        },
        None,
        public_safe_compact_text=lambda value, limit=320: str(value or "").strip()[:limit] or None,
        first_open_todo_text=lambda summary: (
            str((summary.get("first_open_items") or [{}])[0].get("text") or "")
            if isinstance(summary, dict) and summary.get("first_open_items")
            else None
        ),
        todo_summary_open_count=lambda summary: int(summary.get("open_count") or 0) if isinstance(summary, dict) else 0,
        goal_lifecycle_fields=lambda _goal, _run: {},
        attention_item=lambda **kwargs: kwargs,
    )
    assert item is not None, item
    assert item["status"] == "active_state_agent_todo", item
    assert item["waiting_on"] == "codex", item

    gate_item = active_state_todo_attention_item(
        {"id": GOAL_ID},
        {
            "user_todos": {
                "open_count": 1,
                "first_open_items": [
                    {
                        "text": "Approve the side-agent delivery.",
                        "task_class": "user_gate",
                        "blocks_agent": SIDE_AGENT,
                    }
                ],
            },
            "agent_todos": {
                "open_count": 1,
                "first_open_items": [
                    {
                        "text": "Deliver a product-capability slice.",
                        "task_class": "advancement_task",
                    }
                ],
            },
        },
        None,
        public_safe_compact_text=lambda value, limit=320: str(value or "").strip()[:limit] or None,
        first_open_todo_text=lambda summary: (
            str((summary.get("first_open_items") or [{}])[0].get("text") or "")
            if isinstance(summary, dict) and summary.get("first_open_items")
            else None
        ),
        todo_summary_open_count=lambda summary: int(summary.get("open_count") or 0) if isinstance(summary, dict) else 0,
        goal_lifecycle_fields=lambda _goal, _run: {},
        attention_item=lambda **kwargs: kwargs,
    )
    assert gate_item is not None, gate_item
    assert gate_item["status"] == "active_state_user_gate", gate_item
    assert gate_item["waiting_on"] == "controller", gate_item


def main() -> int:
    assert_user_action_does_not_drive_active_state_attention()

    with tempfile.TemporaryDirectory(prefix="loopx-user-gate-scope-") as tmp:
        root = Path(tmp)
        repo, state, registry = write_fixture(root)

        assert_raises_message(
            lambda: add_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                role="user",
                text="Track a non-blocking owner note.",
                dry_run=True,
            ),
            "user todo requires explicit --task-class",
        )

        user_action = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="user",
            text="Track a non-blocking owner note.",
            task_class="user_action",
        )
        assert user_action["task_class"] == "user_action", user_action

        assert_raises_message(
            lambda: add_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                role="user",
                text="Try to make a non-blocking action scoped.",
                task_class="user_action",
                blocks_agent=SIDE_AGENT,
                dry_run=True,
            ),
            "user_action is non-blocking",
        )

        side_agent_todo = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text="Deliver a product-capability slice.",
            task_class="advancement_task",
            claimed_by=SIDE_AGENT,
        )
        assert side_agent_todo["claimed_by"] == SIDE_AGENT, side_agent_todo
        status_payload = collect_status(
            registry_path=registry,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[repo],
            limit=1,
            goal_id=GOAL_ID,
        )
        quota_payload = build_quota_should_run(
            status_payload,
            goal_id=GOAL_ID,
            agent_id=SIDE_AGENT,
        )
        user_summary = quota_payload.get("user_todo_summary")
        assert isinstance(user_summary, dict), quota_payload
        assert user_summary["user_action_open_count"] == 1, user_summary
        assert user_summary["gate_open_items"] == [], user_summary

        assert_raises_message(
            lambda: add_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                role="user",
                text="Approve the product-capability PR merge.",
                task_class="user_gate",
                dry_run=True,
            ),
            "multi-agent user_gate requires an explicit scope",
        )

        scoped = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="user",
            text="Approve the product-capability PR merge.",
            task_class="user_gate",
            agent_id=SIDE_AGENT,
        )
        assert scoped["blocks_agent"] == SIDE_AGENT, scoped
        assert f"blocks_agent={SIDE_AGENT}" in state.read_text(encoding="utf-8")

        global_gate = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="user",
            text="Approve pausing every registered agent.",
            task_class="user_gate",
            global_gate=True,
        )
        assert global_gate["global_gate"] is True, global_gate
        assert "global_gate=true" in state.read_text(encoding="utf-8")

        agent_todo = add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text="Prepare release notes for review.",
            task_class="advancement_task",
            claimed_by=PRIMARY_AGENT,
        )
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=str(agent_todo["todo_id"]),
            role="agent",
            claimed_by=PRIMARY_AGENT,
            evidence="fixture validation",
            next_user_todo="Approve publishing the release notes.",
        )
        state_text = state.read_text(encoding="utf-8")
        assert "Approve publishing the release notes." in state_text, state_text
        assert f"blocks_agent={PRIMARY_AGENT}" in state_text, state_text

        assert_raises_message(
            lambda: update_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                todo_id=str(agent_todo["todo_id"]),
                role="agent",
                global_gate=True,
                dry_run=True,
            ),
            "global_gate is only valid for user_gate todos",
        )

        clean_check = check_contract(
            registry_path=registry,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[repo],
            limit=1,
        )
        assert clean_check["ok"] is True, clean_check

        insert_before_agent_section(
            state,
            "- [ ] Approve an intentionally unscoped gate.\n"
            "  <!-- loopx:todo todo_id=todo_unscoped_gate status=open task_class=user_gate -->",
        )
        bad_check = check_contract(
            registry_path=registry,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[repo],
            limit=1,
        )
        assert bad_check["ok"] is False, bad_check
        assert any("todo_unscoped_gate" in item for item in bad_check["errors"]), bad_check

        closed = update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id="todo_unscoped_gate",
            role="user",
            status="done",
        )
        assert closed["changed"] is True, closed
        repaired_check = check_contract(
            registry_path=registry,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[repo],
            limit=1,
        )
        assert repaired_check["ok"] is True, repaired_check

        insert_before_agent_section(
            state,
            "- [ ] Track an intentionally untyped user todo.\n"
            "  <!-- loopx:todo todo_id=todo_untyped_user status=open -->",
        )
        untyped_check = check_contract(
            registry_path=registry,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[repo],
            limit=1,
        )
        assert untyped_check["ok"] is False, untyped_check
        assert any("todo_untyped_user" in item and "requires task_class" in item for item in untyped_check["errors"]), untyped_check

        closed_untyped = update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id="todo_untyped_user",
            role="user",
            status="done",
        )
        assert closed_untyped["changed"] is True, closed_untyped

        insert_before_agent_section(
            state,
            "- [ ] Approve a gate with an unregistered blocked agent.\n"
            "  <!-- loopx:todo todo_id=todo_bad_agent status=open task_class=user_gate blocks_agent=codex-unknown -->\n"
            "- [ ] Approve a gate with conflicting scope.\n"
            f"  <!-- loopx:todo todo_id=todo_both_scopes status=open task_class=user_gate blocks_agent={SIDE_AGENT} global_gate=true -->",
        )
        invalid_scope_check = check_contract(
            registry_path=registry,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[repo],
            limit=1,
        )
        assert invalid_scope_check["ok"] is False, invalid_scope_check
        assert any("todo_bad_agent" in item and "not registered" in item for item in invalid_scope_check["errors"]), invalid_scope_check
        assert any("todo_both_scopes" in item and "cannot set both" in item for item in invalid_scope_check["errors"]), invalid_scope_check

    print("todo-user-gate-scope-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
