#!/usr/bin/env python3
"""Smoke-test durable interaction-pattern documentation coverage."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "docs" / "interaction-pattern-catalog.md"
STATE_MODEL = REPO_ROOT / "docs" / "state-interaction-model.md"
SELF_REPAIR_PATTERNS = (
    REPO_ROOT
    / "skills"
    / "goal-harness-self-repair"
    / "references"
    / "repair-patterns.md"
)


def require(text: str, snippets: list[str], *, source: Path) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    catalog = CATALOG.read_text(encoding="utf-8")
    state_model = STATE_MODEL.read_text(encoding="utf-8")
    repair_patterns = SELF_REPAIR_PATTERNS.read_text(encoding="utf-8")

    require(
        catalog,
        [
            "## Pattern Families",
            "| Work Routing |",
            "| Human Decision |",
            "| State And Boundary |",
            "| Evidence Lifecycle |",
            "| Planning Governance |",
            "IP-017 | User Reward Lesson Promotion",
            "IP-018 | Plan To Todo Writeback",
            "promote correction into durable lesson",
            "User-facing plans are not durable control-plane state by themselves",
            "writeback target",
            "IP-022 | Claimed Todo Visibility Lanes",
            "Todo projection has two jobs that should not collapse into one list",
            "`current_agent_claimed_advancement_items`",
            "The default agent-facing lane cap should remain modest",
            "remote development\nmachine, but Codex stays local",
            "future `user_reward_lesson_projection_gap`",
        ],
        source=CATALOG,
    )
    require(
        state_model,
        [
            "candidate operating lesson",
            "Codex stays local; the remote host is\nonly the execution substrate",
            "Chat memory alone is not a replayable\n  control-plane signal.",
        ],
        source=STATE_MODEL,
    )
    require(
        repair_patterns,
        [
            "user_reward_lesson_projection_gap",
            "plan_todo_writeback_gap",
            "The correction stayed in chat/model belief",
            "Agent used chat as memory after understanding the plan",
            "refresh state so `quota should-run` selects the corrected rule",
        ],
        source=SELF_REPAIR_PATTERNS,
    )

    print("interaction-pattern-catalog-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
