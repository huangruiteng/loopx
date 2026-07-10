#!/usr/bin/env python3
"""Exercise typed todo continuation policy and legacy compatibility."""

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
    format_todo_metadata_line,
    parse_todo_metadata_line,
    resolve_todo_continuation_policy,
)


GOAL_ID = "todo-continuation-policy-fixture"
PRIMARY_AGENT = "codex-main-control"
SIDE_AGENT = "codex-side-bypass"
SUCCESSOR_ID = "todo_continuation_successor"


def write_registry(root: Path) -> Path:
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "coordination": {
                            "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
                            "primary_agent": PRIMARY_AGENT,
                            "side_agent_handoff_agent": SIDE_AGENT,
                        },
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path


def source_todo(
    *,
    action_kind: str,
    continuation_policy: str | None,
    write_scoped: bool = False,
) -> dict:
    item = {
        "role": "agent",
        "task_class": "advancement_task",
        "action_kind": action_kind,
        "claimed_by": SIDE_AGENT,
        "blocks_agent": PRIMARY_AGENT,
    }
    if continuation_policy:
        item["continuation_policy"] = continuation_policy
    if write_scoped:
        item["required_write_scopes"] = ["loopx/**"]
    return item


def successor(policy: str = "independent_handoff") -> LinkedSuccessor:
    return LinkedSuccessor(
        todo_id=SUCCESSOR_ID,
        role="agent",
        status="open",
        task_class="advancement_task",
        action_kind="continue_lane",
        continuation_policy=policy,
        claimed_by=SIDE_AGENT,
    )


def resolve_existing(
    registry_path: Path,
    *,
    source: dict,
    linked_successor: LinkedSuccessor | None = None,
):
    return resolve_completion_policy(
        registry_path=registry_path,
        goal_id=GOAL_ID,
        claimed_by=SIDE_AGENT,
        evidence="public-safe non-delivery evidence",
        linked_successors=[linked_successor or successor()],
        completion_todo=source,
    )


def expect_rejected(callable_) -> None:
    try:
        callable_()
    except ValueError as exc:
        assert "--side-agent-self-merged" in str(exc), exc
    else:
        raise AssertionError("expected side-agent completion policy rejection")


def assert_action_agnostic_non_delivery_policy(registry_path: Path) -> None:
    for action_kind in (
        "readiness_check",
        "evidence_audit",
        "pilot_readiness_review",
        "artifact_verification",
    ):
        policy = resolve_existing(
            registry_path,
            source=source_todo(
                action_kind=action_kind,
                continuation_policy="same_agent_non_delivery",
            ),
        )
        assert policy.linked_handoff_successor_id == SUCCESSOR_ID, policy
        assert policy.side_agent_self_merged is False, policy


def assert_delivery_and_primary_review_stay_gated(registry_path: Path) -> None:
    expect_rejected(
        lambda: resolve_existing(
            registry_path,
            source=source_todo(
                action_kind="readiness_check",
                continuation_policy="independent_handoff",
            ),
        )
    )
    expect_rejected(
        lambda: resolve_existing(
            registry_path,
            source=source_todo(
                action_kind="readiness_check",
                continuation_policy="same_agent_non_delivery",
                write_scoped=True,
            ),
        )
    )
    expect_rejected(
        lambda: resolve_existing(
            registry_path,
            source=source_todo(
                action_kind="readiness_check",
                continuation_policy="same_agent_non_delivery",
            ),
            linked_successor=successor("primary_review"),
        )
    )


def assert_primary_review_override_is_typed(registry_path: Path) -> None:
    policy = resolve_completion_policy(
        registry_path=registry_path,
        goal_id=GOAL_ID,
        claimed_by=SIDE_AGENT,
        next_claimed_by=PRIMARY_AGENT,
        next_agent_todo="Review the validated delivery.",
        next_action_kind="merge_gate",
        next_continuation_policy="primary_review",
        evidence="validated delivery evidence",
    )
    assert policy.effective_next_claimed_by == PRIMARY_AGENT, policy


def assert_legacy_names_materialize_typed_policy() -> None:
    metadata = format_todo_metadata_line(
        todo_id="todo_legacy_review",
        status="open",
        task_class="advancement_task",
        action_kind="pilot_readiness_review",
    )
    parsed = parse_todo_metadata_line(metadata or "") or {}
    assert parsed["continuation_policy"] == "same_agent_non_delivery", parsed
    assert resolve_todo_continuation_policy(
        None,
        action_kind="primary_review_merge",
    ) == TodoContinuationPolicy.PRIMARY_REVIEW
    assert resolve_todo_continuation_policy(
        None,
        action_kind="implementation_slice",
    ) == TodoContinuationPolicy.INDEPENDENT_HANDOFF


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-continuation-policy-") as tmp:
        registry_path = write_registry(Path(tmp))
        assert_action_agnostic_non_delivery_policy(registry_path)
        assert_delivery_and_primary_review_stay_gated(registry_path)
        assert_primary_review_override_is_typed(registry_path)
    assert_legacy_names_materialize_typed_policy()
    print("todo-continuation-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
