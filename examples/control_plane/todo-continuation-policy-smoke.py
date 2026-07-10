#!/usr/bin/env python3
"""Exercise typed continuation policy for equal peers."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.completion_policy import (  # noqa: E402
    LinkedSuccessor,
    resolve_completion_policy,
)
from loopx.control_plane.todos.contract import (  # noqa: E402
    TodoContinuationPolicy,
    normalize_todo_continuation_policy,
    resolve_todo_continuation_policy,
)


GOAL_ID = "continuation-policy-fixture"
PEER_ALPHA = "codex-alpha"
PEER_BETA = "codex-beta"


def write_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [PEER_ALPHA, PEER_BETA],
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-continuation-policy-") as tmp:
        registry_path = Path(tmp) / "registry.json"
        write_registry(registry_path)

        same_peer = resolve_completion_policy(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            claimed_by=PEER_ALPHA,
            next_agent_todo="Continue a read-only validation lane.",
            next_continuation_policy="same_agent_non_delivery",
        )
        assert same_peer.agent_model == "peer_v1", same_peer
        assert same_peer.effective_next_claimed_by == PEER_ALPHA, same_peer

        review = resolve_completion_policy(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            claimed_by=PEER_ALPHA,
            next_claimed_by=PEER_BETA,
            next_agent_todo="Independently review the delivery.",
            next_continuation_policy="review_handoff",
        )
        assert review.effective_next_claimed_by == PEER_BETA, review
        assert not hasattr(review, "primary_agent"), review

        try:
            resolve_completion_policy(
                registry_path=registry_path,
                goal_id=GOAL_ID,
                claimed_by=PEER_ALPHA,
                next_claimed_by=PEER_ALPHA,
                next_agent_todo="Review your own delivery.",
                next_continuation_policy="review_handoff",
            )
        except ValueError as exc:
            assert "different registered peer" in str(exc), exc
        else:
            raise AssertionError("review handoff must not self-claim")

        try:
            resolve_completion_policy(
                registry_path=registry_path,
                goal_id=GOAL_ID,
                claimed_by=PEER_ALPHA,
                self_merged=True,
            )
        except ValueError as exc:
            assert "--self-merged requires --evidence" in str(exc), exc
        else:
            raise AssertionError("self-merged completion requires evidence")

        merged = resolve_completion_policy(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            claimed_by=PEER_ALPHA,
            self_merged=True,
            evidence="commit and focused validation passed",
            linked_successors=[
                LinkedSuccessor(
                    todo_id="todo_peer_successor",
                    role="agent",
                    status="open",
                    claimed_by=PEER_BETA,
                )
            ],
        )
        assert merged.self_merged is True, merged
        assert merged.linked_successor_id == "todo_peer_successor", merged

        assert normalize_todo_continuation_policy("primary_review") == (
            TodoContinuationPolicy.REVIEW_HANDOFF.value
        )
        assert resolve_todo_continuation_policy(
            None,
            action_kind="primary_review_merge",
        ) == TodoContinuationPolicy.REVIEW_HANDOFF

    print("todo-continuation-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
