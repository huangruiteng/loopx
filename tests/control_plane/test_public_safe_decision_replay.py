from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from loopx.control_plane.testing.decision_replay import (
    load_public_safe_decision_replay,
    reduce_public_safe_decision,
    replay_public_safe_decision_case,
    validate_public_safe_decision_case,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run, build_quota_slot_spend_event


AGENT_ID = "replay-agent"
GOAL_ID = "decision-replay-fixture"
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "control_plane"
    / "public_safe_decision_replay_v0.json"
)
PUBLISH_SCOPE = {
    "schema_version": "decision_scope_v0",
    "kind": "direction",
    "granularity": "action",
    "scope_key": "publish_quality_contract",
}


def _decision(*, blocking: bool) -> dict:
    agent_todo = quota_todo_item(
        todo_id="todo_agent_delivery",
        claimed_by=AGENT_ID,
        text="[P1] Publish the quality contract.",
        action_kind="publish_quality_contract",
        required_decision_scopes=[PUBLISH_SCOPE] if blocking else [],
    )
    user_todo = quota_todo_item(
        todo_id="todo_user_gate" if blocking else "todo_user_notice",
        role="user",
        task_class="user_gate" if blocking else "user_action",
        text=(
            "[P2-user] Approve publishing."
            if blocking
            else "[P2-user] Review optional wording."
        ),
        action_kind="publish_quality_contract" if blocking else "review_optional_wording",
        blocks_agent=AGENT_ID if blocking else None,
        decision_scope=(
            PUBLISH_SCOPE
            if blocking
            else {
                "schema_version": "decision_scope_v0",
                "kind": "direction",
                "granularity": "action",
                "scope_key": "review_optional_wording",
            }
        ),
    )
    status = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Publish the quality contract.",
        agent_todos=quota_todo_summary(
            [agent_todo],
            role="agent",
            claim_scope_agent_id=AGENT_ID,
        ),
        user_todos=quota_todo_summary([user_todo], role="user"),
        quota_state="operator_gate" if blocking else "eligible",
        safe_bypass=blocking,
        coordination={"agent_model": "peer_v1", "registered_agents": [AGENT_ID]},
    )
    return build_quota_should_run(status, goal_id=GOAL_ID, agent_id=AGENT_ID)


def _scope_collision_decision() -> dict:
    agent_todo = quota_todo_item(
        todo_id="todo_agent_delivery",
        claimed_by=AGENT_ID,
        text="[P1] Publish the quality contract.",
        action_kind="publish_quality_contract",
        required_decision_scopes=[PUBLISH_SCOPE],
    )
    user_todo = quota_todo_item(
        todo_id="todo_user_notice",
        role="user",
        task_class="user_action",
        text="[P2-user] Review optional wording.",
        action_kind="review_optional_wording",
        decision_scope=PUBLISH_SCOPE,
    )
    status = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Publish the quality contract.",
        agent_todos=quota_todo_summary(
            [agent_todo],
            role="agent",
            claim_scope_agent_id=AGENT_ID,
        ),
        user_todos=quota_todo_summary([user_todo], role="user"),
        quota_state="eligible",
        coordination={"agent_model": "peer_v1", "registered_agents": [AGENT_ID]},
    )
    return build_quota_should_run(status, goal_id=GOAL_ID, agent_id=AGENT_ID)


def test_checked_in_replay_is_an_independent_reviewed_oracle() -> None:
    replay = load_public_safe_decision_replay(FIXTURE)

    for case in replay["cases"]:
        assert case["invariant_id"].startswith("INV-")
        assert len(case["rationale"]) >= 20
        observed = replay_public_safe_decision_case(case)
        assert observed == {
            "decision": case["decision"],
            "selected_todo": case["selected_todo"],
            "interaction_contract": case["interaction_contract"],
            "expected": case["expected"],
        }


def test_reducer_strips_private_and_diagnostic_payloads() -> None:
    decision = _decision(blocking=False)
    decision["raw_logs"] = ["not retained"]
    decision["trajectory"] = {"steps": ["not retained"]}
    decision["private_path"] = "/tmp/not-retained"

    reduced = reduce_public_safe_decision(decision, case_id="redaction-check")
    reduced["invariant_id"] = "INV-REDACTION"
    reduced["rationale"] = (
        "Public replay evidence excludes private diagnostics and local paths."
    )

    assert "raw_logs" not in reduced
    assert "trajectory" not in reduced
    assert "private_path" not in reduced
    validate_public_safe_decision_case(reduced)


def test_other_agent_gate_is_semantically_inert_for_current_agent() -> None:
    replay = load_public_safe_decision_replay(FIXTURE)
    base = next(
        case
        for case in replay["cases"]
        if case["case_id"] == "nonblocking-action-with-runnable-work"
    )
    mutated = {
        **base,
        "case_id": "nonblocking-action-with-unrelated-other-agent-gate",
        "user_todos": [
            *base["user_todos"],
            {
                "todo_id": "todo_other_agent_gate",
                "status": "open",
                "task_class": "user_gate",
                "blocks_agent": "codex-other-agent",
                "action_kind": "approve_other_agent_release",
                "decision_scope": {
                    "schema_version": "decision_scope_v0",
                    "kind": "direction",
                    "granularity": "action",
                    "scope_key": "approve_other_agent_release",
                },
            },
        ],
    }

    observed = replay_public_safe_decision_case(mutated)

    assert observed == {
        "decision": base["decision"],
        "selected_todo": base["selected_todo"],
        "interaction_contract": base["interaction_contract"],
        "expected": base["expected"],
    }


def test_global_gate_has_authority_for_matching_required_scope() -> None:
    replay = load_public_safe_decision_replay(FIXTURE)
    blocking = next(
        case for case in replay["cases"] if case["case_id"] == "blocking-gate"
    )
    global_gate = deepcopy(blocking)
    global_gate["case_id"] = "matching-global-gate"
    global_gate["invariant_id"] = "INV-MATCHED-GLOBAL-GATE"
    global_gate["rationale"] = (
        "An explicitly global gate with the matching scope blocks every agent lane."
    )
    global_gate["user_todos"][0].pop("blocks_agent")
    global_gate["user_todos"][0]["global_gate"] = True

    observed = replay_public_safe_decision_case(global_gate)

    assert observed == {
        "decision": blocking["decision"],
        "selected_todo": blocking["selected_todo"],
        "interaction_contract": blocking["interaction_contract"],
        "expected": blocking["expected"],
    }


def test_other_agent_gate_cannot_inherit_global_operator_gate_authority() -> None:
    replay = load_public_safe_decision_replay(FIXTURE)
    runnable = next(
        case
        for case in replay["cases"]
        if case["case_id"] == "nonblocking-action-with-runnable-work"
    )
    other_agent = deepcopy(runnable)
    other_agent["case_id"] = "other-agent-gate-with-global-operator-state"
    other_agent["invariant_id"] = "INV-OTHER-AGENT-GATE-ISOLATION"
    other_agent["rationale"] = (
        "A global operator_gate status caused by another agent cannot block or notify "
        "the current agent when its independent todo remains runnable."
    )
    other_agent["scenario"] = {"quota_state": "operator_gate", "safe_bypass": True}
    other_agent["user_todos"] = [
        {
            "todo_id": "todo_other_agent_gate",
            "status": "open",
            "task_class": "user_gate",
            "blocks_agent": "codex-other-agent",
            "action_kind": "approve_other_agent_release",
            "decision_scope": {
                "schema_version": "decision_scope_v0",
                "kind": "direction",
                "granularity": "action",
                "scope_key": "approve_other_agent_release",
            },
        }
    ]
    expected_interaction = deepcopy(runnable["interaction_contract"])
    expected_interaction["user_channel"] = {
        "action_required": False,
        "notify": "DONT_NOTIFY",
    }

    observed = replay_public_safe_decision_case(other_agent)

    assert observed == {
        "decision": runnable["decision"],
        "selected_todo": runnable["selected_todo"],
        "interaction_contract": expected_interaction,
        "expected": runnable["expected"],
    }


def test_real_quota_repairs_nonblocking_action_scope_collision() -> None:
    decision = _scope_collision_decision()

    assert decision["decision"] == "self_repair"
    assert decision["should_run"] is True
    assert decision["normal_delivery_allowed"] is False
    assert decision["self_repair_allowed"] is True
    assert decision["effective_action"] == "todo_decision_scope_projection_repair"
    assert decision["interaction_contract"]["mode"] == "control_plane_self_repair"
    assert decision["scheduler_hint"]["cadence_class"] == "active_work"
    consistency = decision["todo_decision_scope_consistency"]
    assert consistency["ok"] is False
    assert (
        consistency["errors"][0]["reason_code"]
        == "non_blocking_user_action_scope_collision"
    )


def test_scope_repair_action_can_be_accounted_after_validated_writeback() -> None:
    before = _scope_collision_decision()
    before["quota"] = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "spent_slots": 0,
        "allowed_slots": 1440,
    }
    after = {
        **before,
        "quota": {**before["quota"], "spent_slots": 1},
    }

    event = build_quota_slot_spend_event(
        {
            "ok": True,
            "goal_id": GOAL_ID,
            "slots": 1,
            "before": before,
            "after": after,
        }
    )

    assert event["classification"] == "quota_slot_spent"
    assert "control-plane self-repair" in event["health_check"]
