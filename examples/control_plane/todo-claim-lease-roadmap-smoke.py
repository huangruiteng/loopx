#!/usr/bin/env python3
"""Smoke-test the public soft-claim and optional hard-lease contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
ROADMAP = REPO_ROOT / "docs" / "frontstage-channel-lease-roadmap.md"
TODO_CONTRACT = REPO_ROOT / "docs" / "project-agent-todo-contract.md"
REGISTRY_EXAMPLE = REPO_ROOT / "examples" / "registry.example.json"
PEER_AGENTS_EXAMPLE = (
    REPO_ROOT / "examples" / "peer-agent-task-orchestration.registry.example.json"
)


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
            "Registered identities are peers",
            "workspace-isolation rule",
        ],
        source=ARCHITECTURE,
    )
    require(
        roadmap,
        [
            "A **task claim is a soft per-todo route by default**",
            "an optional hard lease adds TTL",
            "pending key is per todo: `(goal_id, todo_id)`",
            "LoopX does not have a separate issue object",
            "Do not serialize an entire\ngoal",
            "does not replace\nthe default soft `claimed_by` route or participate in quota decisions",
            "registered-owner validation",
            "repository-writing peers use isolated worktrees",
            "self-merge with\nevidence",
            "review action over an independent handoff",
        ],
        source=ROADMAP,
    )
    require(
        todo_contract,
        [
            "a `goal_id` is the LoopX control-plane boundary",
            "A `todo_id` is a structured work item inside that goal",
            "does not\ncurrently model issues as a separate runtime object",
            "`coordination.agent_model=peer_v1`",
            "Create or switch to a separate worktree",
            "`--next-claimed-by`",
        ],
        source=TODO_CONTRACT,
    )
    for source in (REGISTRY_EXAMPLE, PEER_AGENTS_EXAMPLE):
        registry = json.loads(source.read_text(encoding="utf-8"))
        for goal in registry.get("goals") or []:
            coordination = goal.get("coordination") or {}
            assert "claim_ttl_minutes" not in coordination, (
                f"{source}: soft claims must not advertise an inert TTL"
            )

    help_result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "bootstrap", "--help"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "--claim-ttl-minutes" not in help_result.stdout, help_result.stdout

    with tempfile.TemporaryDirectory(prefix="loopx-soft-claim-ttl-smoke-") as tmp:
        root = Path(tmp)
        registry_path = root / "registry.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--format",
                "json",
                "bootstrap",
                "--project",
                str(root / "project"),
                "--goal-id",
                "soft-claim-ttl-smoke",
                "--objective",
                "verify soft claim TTL compatibility",
                "--claim-ttl-minutes",
                "5",
                "--no-onboarding-scan",
                "--no-global-sync",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout or result.stderr
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        coordination = registry["goals"][0]["coordination"]
        assert "claim_ttl_minutes" not in coordination, coordination

    print("todo-claim-lease-roadmap-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
