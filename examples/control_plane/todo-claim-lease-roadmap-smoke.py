#!/usr/bin/env python3
"""Smoke-test the public todo claim and future per-todo lease contract."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
ROADMAP = REPO_ROOT / "docs" / "frontstage-channel-lease-roadmap.md"
TODO_CONTRACT = REPO_ROOT / "docs" / "project-agent-todo-contract.md"
REGISTRY_EXAMPLE = REPO_ROOT / "examples" / "registry.example.json"
CONTROLLER_SUBAGENTS_EXAMPLE = REPO_ROOT / "examples" / "controller-subagents.registry.example.json"


def require(text: str, snippets: list[str], *, source: Path) -> None:
    compact = " ".join(text.split())
    missing = [
        snippet
        for snippet in snippets
        if snippet not in text and " ".join(snippet.split()) not in compact
    ]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    todo_contract = TODO_CONTRACT.read_text(encoding="utf-8")

    require(
        architecture,
        [
            "a **goal** is the stable `goal_id` boundary",
            "A **todo** is a structured active-state checkbox",
            "There is no separate issue object",
            "`(goal_id, todo_id)` is the contention unit",
            "Different todos under the same goal may proceed in parallel",
            "`coordination.primary_agent`",
            "independent git\nworktrees/branches",
        ],
        source=ARCHITECTURE,
    )
    require(
        roadmap,
        [
            "A **task claim should be a per-todo lease**",
            "pending key is per todo: `(goal_id, todo_id)`",
            "LoopX does not have a separate issue object",
            "one active pending lease per\n  `(goal_id, todo_id)`",
            "not one active lease per goal or project",
            "side agents claim scoped todos and work in separate git worktrees",
            "self-merge small AGENTS-eligible validated changes",
            "primary-agent review todo",
        ],
        source=ROADMAP,
    )
    require(
        todo_contract,
        [
            "a `goal_id` is the LoopX control-plane boundary",
            "A `todo_id` is a structured work item inside that goal",
            "does not\ncurrently model issues as a separate runtime object",
            "one `coordination.primary_agent`",
            "independent git worktree/branch",
            "`--next-claimed-by`",
        ],
        source=TODO_CONTRACT,
    )
    for source in (REGISTRY_EXAMPLE, CONTROLLER_SUBAGENTS_EXAMPLE):
        registry = json.loads(source.read_text(encoding="utf-8"))
        for goal in registry.get("goals") or []:
            coordination = goal.get("coordination") or {}
            if "claim_ttl_minutes" not in coordination:
                continue
            registered_agents = coordination.get("registered_agents")
            assert isinstance(registered_agents, list) and registered_agents, (
                f"{source}: goal {goal.get('id')} has claim_ttl_minutes but no registered_agents"
            )
            primary_agent = coordination.get("primary_agent")
            assert isinstance(primary_agent, str) and primary_agent in registered_agents, (
                f"{source}: goal {goal.get('id')} must declare one registered primary_agent"
            )

    print("todo-claim-lease-roadmap-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
