from __future__ import annotations

from typing import Any

from loopx.control_plane.quota.task_orchestration import (
    apply_task_orchestration_contract,
)


AGENT_ID = "codex-main"


def _todo(
    todo_id: str,
    *,
    task_domain: str = "code",
    action_kind: str = "inspect",
    task_repository: str | None = None,
    required_capabilities: list[str] | None = None,
    required_write_scopes: list[str] | None = None,
    resume_ready: bool | None = None,
    excluded_agents: list[str] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "todo_id": todo_id,
        "status": "open",
        "task_class": "advancement_task",
        "priority": "P0",
        "text": f"Advance {todo_id}",
        "task_domain": task_domain,
        "action_kind": action_kind,
    }
    if required_capabilities:
        item["required_capabilities"] = required_capabilities
    if required_write_scopes:
        item["required_write_scopes"] = required_write_scopes
    if task_repository:
        item["task_repository"] = task_repository
    if resume_ready is not None:
        item["resume_when"] = "todo_done:todo_dependency"
        item["resume_ready"] = resume_ready
    if excluded_agents:
        item["excluded_agents"] = excluded_agents
    return item


def _contract(
    items: list[dict[str, Any]],
    *,
    available_capabilities: list[str],
    allowed_domains: list[str] | None = None,
) -> dict[str, Any] | None:
    summary = {"items": items}
    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "write_scope": ["loopx/**", "tests/**"],
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 2,
                "allowed_domains": allowed_domains or [],
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        raw_user_todo_summary={"items": []},
        available_capabilities=available_capabilities,
    )
    return contract


def test_admission_requires_observed_spawn_capability() -> None:
    contract = _contract(
        [_todo("todo_primary"), _todo("todo_child")],
        available_capabilities=[],
    )

    assert contract is None


def test_admission_emits_complete_child_brief_and_typed_block_reasons() -> None:
    contract = _contract(
        [
            _todo("todo_primary"),
            _todo("todo_child", required_capabilities=["network"]),
            _todo("todo_wrong_domain", task_domain="docs"),
            _todo("todo_waiting", resume_ready=False),
        ],
        available_capabilities=["subagent_spawn", "network"],
        allowed_domains=["code"],
    )

    assert contract is not None
    assert contract["schema_version"] == "task_orchestration_contract_v2"
    assert contract["mode"] == "adaptive"
    assert contract["activation_required"] is False
    assert contract["strategy_owner"] == "task_coordinator"
    assert contract["writeback_owner"] == "task_coordinator"
    assert contract["child_brief_defaults"] == {
        "schema_version": "subagent_control_plane_handoff_v0",
        "parent_goal_id": None,
        "authority_artifact": "quota_should_run.goal_boundary",
        "latest_state_ref": "quota_should_run.action_signature.source_hash",
        "quota_gate_snapshot": "admitted_by_task_orchestration_contract",
        "context_policy": {
            "selection_owner": "task_coordinator",
            "default": "fresh",
            "allowed": ["fresh"],
        },
        "expected_output": "public_safe_evidence",
        "child_decision": "continue",
        "execution_policy": {
            "timeout": "bounded_by_host_turn",
            "cancel": "task_coordinator_or_host_timeout",
        },
        "validation_policy": (
            "run todo-scoped validation when applicable and report commands/results"
        ),
        "acceptance": [
            "report completed scope and evidence",
            "report validation result and residual risk",
            "do not write LoopX state or spend quota",
        ],
        "writeback_spend_contract": (
            "child reports evidence only; task coordinator accepts evidence, "
            "writes state, and spends once"
        ),
    }
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_child"
    ]
    child = contract["eligible_child_lanes"][0]
    assert child["execution_kind"] == "ephemeral_child"
    assert child["child_brief"] == {
        "todo_id": "todo_child",
        "objective": "Advance todo_child",
        "action_kind": "inspect",
        "task_domain": "code",
        "required_capabilities": ["network"],
        "task_repository": None,
        "required_write_scopes": [],
        "workspace_isolation": "not_required",
        "continuation_policy": None,
        "target_key": None,
    }
    blocked = {
        lane["todo_id"]: lane["reason_codes"]
        for lane in contract["blocked_lanes"]
    }
    assert blocked == {
        "todo_wrong_domain": ["task_domain_not_allowed"],
        "todo_waiting": ["dependency_not_ready"],
    }


def test_admission_serializes_overlapping_write_scopes() -> None:
    contract = _contract(
        [
            _todo(
                "todo_primary",
                action_kind="implement",
                required_write_scopes=["loopx/control_plane/**"],
            ),
            _todo(
                "todo_conflict",
                action_kind="implement",
                required_write_scopes=["loopx/control_plane/quota/**"],
            ),
            _todo(
                "todo_independent",
                action_kind="implement",
                required_write_scopes=["tests/**"],
            ),
        ],
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_independent"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_conflict",
            "task_domain": "code",
            "reason_codes": ["write_scope_conflict"],
            "conflicts_with_todo_id": "todo_primary",
        }
    ]


def test_admission_serializes_implicit_and_explicit_goal_repository_scopes() -> None:
    summary = {
        "items": [
            _todo(
                "todo_primary",
                action_kind="implement",
                required_write_scopes=["loopx/control_plane/**"],
            ),
            _todo(
                "todo_same_repository",
                action_kind="implement",
                task_repository="git:github.com/owner/loopx",
                required_write_scopes=["loopx/control_plane/quota/**"],
            ),
            _todo(
                "todo_independent",
                action_kind="implement",
                task_repository="git:github.com/owner/loopx",
                required_write_scopes=["tests/**"],
            ),
        ]
    }

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "task_repository": "git:github.com/owner/loopx",
            "write_scope": ["loopx/**", "tests/**"],
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 2,
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        raw_user_todo_summary={"items": []},
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_independent"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_same_repository",
            "task_domain": "code",
            "reason_codes": ["write_scope_conflict"],
            "conflicts_with_todo_id": "todo_primary",
        }
    ]


def test_admission_fails_closed_when_configured_domains_are_all_invalid() -> None:
    contract = _contract(
        [_todo("todo_primary"), _todo("todo_child")],
        available_capabilities=["subagent_spawn"],
        allowed_domains=["../private", "CODE/../../private"],
    )

    assert contract is None


def test_admission_fails_closed_when_write_scope_is_not_goal_authorized() -> None:
    summary = {
        "items": [
            _todo("todo_primary"),
            _todo(
                "todo_child",
                action_kind="implement",
                required_write_scopes=["private/**"],
            ),
        ]
    }

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 2,
            }
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is None


def test_admission_blocks_excluded_coordinator_and_open_agent_dependency() -> None:
    items = [
        _todo("todo_primary"),
        _todo("todo_excluded", excluded_agents=[AGENT_ID]),
        _todo("todo_dependency"),
        {
            **_todo("todo_dependent"),
            "resume_when": "todo_done:todo_dependency",
            "resume_ready": False,
        },
    ]

    contract = _contract(
        items,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    blocked = {
        lane["todo_id"]: lane["reason_codes"]
        for lane in contract["blocked_lanes"]
    }
    assert blocked["todo_excluded"] == ["coordinator_excluded"]
    assert blocked["todo_dependent"] == ["dependency_not_ready"]


def test_admission_uses_untruncated_todo_and_user_blocker_authority() -> None:
    primary = _todo("todo_primary")
    blocked_child = _todo("todo_blocked_child")
    independent_child = _todo("todo_independent_child")
    display_summary = {"items": [primary, independent_child]}

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "write_scope": ["loopx/**"],
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 2,
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=display_summary,
        raw_agent_todo_summary=display_summary,
        raw_user_todo_summary={"items": []},
        agent_todo_source_items=[
            primary,
            blocked_child,
            independent_child,
        ],
        user_todo_source_items=[
            {
                "todo_id": "todo_owner_gate",
                "status": "open",
                "task_class": "user_gate",
                "unblocks_todo_id": "todo_blocked_child",
                "text": "Approve the blocked child lane.",
            }
        ],
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_independent_child"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_blocked_child",
            "task_domain": "code",
            "reason_codes": ["dependency_not_ready"],
        }
    ]


def test_admission_reports_ready_lanes_deferred_by_capacity() -> None:
    summary = {
        "items": [
            _todo("todo_primary"),
            _todo("todo_child_one"),
            _todo("todo_child_two"),
        ]
    }

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "write_scope": ["loopx/**"],
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 1,
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_child_one"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_child_two",
            "task_domain": "code",
            "reason_codes": ["capacity_deferred"],
        }
    ]


def test_explicit_registered_peer_bundle_precedes_ephemeral_host_capacity() -> None:
    peers = [AGENT_ID, "codex-peer-one", "codex-peer-two"]
    items = [
        {
            **_todo(f"todo_peer_{index}"),
            "claimed_by": peer,
        }
        for index, peer in enumerate(peers, start=1)
    ]
    summary = {"items": items}
    contracts = []
    for agent_id in peers:
        contract, _work_lane = apply_task_orchestration_contract(
            fallback_work_lane_contract={"lane": "advancement_task"},
            goal_boundary={
                "write_scope": ["loopx/**"],
                "orchestration": {
                    "mode": "multi_subagent",
                    "spawn_allowed": True,
                    "max_children": 2,
                },
            },
            agent_identity={
                "agent_id": agent_id,
                "registered_agents": peers,
            },
            agent_todo_summary=summary,
            raw_agent_todo_summary=summary,
            available_capabilities=[],
        )
        if contract:
            contracts.append(contract)

    assert len(contracts) == 1
    assert contracts[0]["schema_version"] == "task_orchestration_contract_v1"
    assert contracts[0]["mode"] == "task_scoped_peer"


def test_claimed_primary_agent_coordinates_unclaimed_child_work() -> None:
    peers = [AGENT_ID, "codex-peer-1", "codex-peer-2"]
    summary = {
        "items": [
            {
                **_todo(
                    "todo_primary",
                    required_write_scopes=["loopx/**"],
                ),
                "claimed_by": AGENT_ID,
            },
            _todo("todo_child"),
        ]
    }
    contracts = []
    for agent_id in peers:
        contract, _work_lane = apply_task_orchestration_contract(
            fallback_work_lane_contract={"lane": "advancement_task"},
            goal_boundary={
                "write_scope": ["loopx/**"],
                "orchestration": {
                    "mode": "multi_subagent",
                    "spawn_allowed": True,
                    "max_children": 1,
                },
            },
            agent_identity={
                "agent_id": agent_id,
                "registered_agents": peers,
            },
            agent_todo_summary=summary,
            raw_agent_todo_summary=summary,
            available_capabilities=["subagent_spawn"],
        )
        if contract:
            contracts.append(contract)

    assert len(contracts) == 1
    assert contracts[0]["coordinator_agent_id"] == AGENT_ID
    assert contracts[0]["primary_todo_id"] == "todo_primary"
    assert contracts[0]["primary_todo"] == {
        "todo_id": "todo_primary",
        "required_write_scopes": ["loopx/**"],
    }
    assert contracts[0]["eligible_child_lanes"][0]["todo_id"] == "todo_child"


def test_admission_rejects_explicit_repository_without_goal_authority() -> None:
    summary = {
        "items": [
            _todo("todo_primary"),
            {
                **_todo("todo_child"),
                "task_repository": "git:github.com/owner/other-repo",
            },
        ]
    }

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 1,
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is None


def test_admission_accepts_only_goal_repository_identity() -> None:
    summary = {
        "items": [
            _todo("todo_primary"),
            {
                **_todo("todo_same_repo"),
                "task_repository": "git:github.com/owner/loopx",
            },
            {
                **_todo("todo_other_repo"),
                "task_repository": "git:github.com/owner/other-repo",
            },
        ]
    }

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "task_repository": "git:github.com/owner/loopx",
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 2,
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_same_repo"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_other_repo",
            "task_domain": "code",
            "reason_codes": ["task_repository_not_allowed"],
        }
    ]


def test_admission_requires_scope_for_mutating_child_work() -> None:
    summary = {
        "items": [
            _todo("todo_primary"),
            _todo("todo_mutating", action_kind="implement"),
            _todo("todo_read_only", action_kind="inspect"),
        ]
    }

    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary={
            "write_scope": ["loopx/**"],
            "orchestration": {
                "mode": "multi_subagent",
                "spawn_allowed": True,
                "max_children": 2,
            },
        },
        agent_identity={
            "agent_id": AGENT_ID,
            "registered_agents": [AGENT_ID],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_read_only"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_mutating",
            "task_domain": "code",
            "reason_codes": ["write_scope_missing"],
        }
    ]


def test_admission_requires_scope_for_unknown_child_action() -> None:
    summary = {
        "items": [
            _todo("todo_primary"),
            _todo("todo_unknown", action_kind="custom_action"),
            _todo("todo_review", action_kind="review_pr"),
        ]
    }

    contract = _contract(
        summary["items"],
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_review"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_unknown",
            "task_domain": "code",
            "reason_codes": ["write_scope_missing"],
        }
    ]
