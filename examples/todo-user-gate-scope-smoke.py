#!/usr/bin/env python3
"""Smoke-test multi-agent user gate scope enforcement."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.contract import check_contract  # noqa: E402
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
                            "primary_agent": PRIMARY_AGENT,
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-user-gate-scope-") as tmp:
        root = Path(tmp)
        repo, state, registry = write_fixture(root)

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
