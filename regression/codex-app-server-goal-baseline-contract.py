#!/usr/bin/env python3
"""Validate the Codex app-server Goal baseline seam contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from goal_harness.codex_goal_baseline import (  # noqa: E402
    build_codex_app_server_goal_baseline_plan,
    build_codex_app_server_goal_baseline_proof,
    build_codex_app_server_goal_worker_plan,
    build_codex_app_server_goal_worker_proof,
    run_isolated_codex_app_server_goal_probe,
)


OBJECTIVE = "Complete the benchmark task and validate the final answer."
TASK_INSTRUCTION = "Solve the benchmark task, write the answer, and run tests."
THREAD_ID = "thread-fixture-123"
TURN_ID = "turn-fixture-456"


def assert_plan_contract() -> None:
    plan = build_codex_app_server_goal_baseline_plan(
        objective=OBJECTIVE,
        cwd="/workspace/benchmark",
        token_budget=200000,
    )
    assert plan["surface"] == "codex_app_server", plan
    assert plan["requires_experimental_api"] is True, plan
    assert "thread/goal/set" in plan["methods"], plan
    assert "thread/goal/get" in plan["methods"], plan
    assert plan["connectivity_smoke"]["codex_exec_is_goal_baseline"] is False, plan
    assert plan["claim_boundary"]["requires_thread_goal_get_evidence"] is True, plan
    assert plan["claim_boundary"]["slash_prefix_prompt_is_unverified"] is True, plan

    initialize = plan["messages"]["initialize"]
    assert initialize["params"]["capabilities"]["experimentalApi"] is True, initialize
    assert plan["messages"]["thread_goal_set"]["params"]["status"] == "active", plan
    assert plan["messages"]["thread_goal_set"]["params"]["objective"] == OBJECTIVE, plan
    assert plan["messages"]["thread_goal_get"]["params"]["threadId"] == "<thread-id>", plan


def assert_proof_contract() -> None:
    set_response = {
        "goal": {
            "threadId": THREAD_ID,
            "objective": OBJECTIVE,
            "status": "active",
            "tokenBudget": 200000,
            "tokensUsed": 0,
            "timeUsedSeconds": 0,
        }
    }
    get_response = {
        "goal": {
            "threadId": THREAD_ID,
            "objective": OBJECTIVE,
            "status": "active",
            "tokenBudget": 200000,
            "tokensUsed": 0,
            "timeUsedSeconds": 0,
        }
    }
    proof = build_codex_app_server_goal_baseline_proof(
        set_response=set_response,
        get_response=get_response,
        expected_objective=OBJECTIVE,
        notifications=["thread/goal/updated"],
    )
    assert proof["persistent_goal_evidence"] is True, proof
    assert proof["baseline_claim_allowed"] is True, proof
    assert proof["matches"] == {"thread": True, "objective": True, "status": True}, proof
    assert proof["set_goal"]["objective_sha256"] == proof["get_goal"]["objective_sha256"], proof
    assert "thread/goal/updated" in proof["notifications"], proof
    assert proof["read_boundary"]["credentials_read_or_recorded"] is False, proof

    codex_exec_only = build_codex_app_server_goal_baseline_proof(
        set_response=set_response,
        get_response=None,
        expected_objective=OBJECTIVE,
        used_codex_exec=True,
    )
    assert codex_exec_only["persistent_goal_evidence"] is False, codex_exec_only
    assert codex_exec_only["baseline_claim_allowed"] is False, codex_exec_only
    assert codex_exec_only["negative_controls"]["codex_exec_only"] is True, codex_exec_only

    slash_prefix_only = build_codex_app_server_goal_baseline_proof(
        set_response=None,
        get_response=None,
        expected_objective="/goal " + OBJECTIVE,
        used_slash_prefix_prompt=True,
    )
    assert slash_prefix_only["persistent_goal_evidence"] is False, slash_prefix_only
    assert slash_prefix_only["baseline_claim_allowed"] is False, slash_prefix_only
    assert slash_prefix_only["negative_controls"]["slash_prefix_prompt_only"] is True, slash_prefix_only

    leaked_state = build_codex_app_server_goal_baseline_proof(
        set_response=set_response,
        get_response=get_response,
        expected_objective=OBJECTIVE,
        included_goal_harness_state=True,
    )
    assert leaked_state["persistent_goal_evidence"] is True, leaked_state
    assert leaked_state["baseline_claim_allowed"] is False, leaked_state


def assert_worker_plan_and_proof_contract() -> None:
    plan = build_codex_app_server_goal_worker_plan(
        objective=OBJECTIVE,
        task_instruction=TASK_INSTRUCTION,
        cwd="/workspace/benchmark",
        model="gpt-5.5",
        token_budget=200000,
    )
    assert plan["schema_version"] == "codex_app_server_goal_worker_v0", plan
    assert "thread/goal/set" in plan["methods"], plan
    assert "thread/goal/get" in plan["methods"], plan
    assert "turn/start" in plan["methods"], plan
    assert plan["claim_boundary"]["requires_turn_start_evidence"] is True, plan
    turn_start = plan["messages"]["turn_start"]
    assert turn_start["method"] == "turn/start", turn_start
    assert turn_start["params"]["threadId"] == "<thread-id>", turn_start
    assert turn_start["params"]["input"] == [
        {"type": "text", "text": TASK_INSTRUCTION}
    ], turn_start
    assert turn_start["params"]["model"] == "gpt-5.5", turn_start

    set_response = {
        "goal": {
            "threadId": THREAD_ID,
            "objective": OBJECTIVE,
            "status": "active",
            "tokenBudget": 200000,
            "tokensUsed": 0,
            "timeUsedSeconds": 0,
        }
    }
    get_response = {
        "goal": {
            "threadId": THREAD_ID,
            "objective": OBJECTIVE,
            "status": "active",
            "tokenBudget": 200000,
            "tokensUsed": 0,
            "timeUsedSeconds": 0,
        }
    }
    turn_start_request = dict(turn_start)
    turn_start_request["params"] = dict(turn_start["params"])
    turn_start_request["params"]["threadId"] = THREAD_ID
    turn_start_response = {
        "turn": {
            "id": TURN_ID,
            "status": "running",
            "items": [],
            "startedAt": 1,
            "completedAt": None,
            "error": None,
        }
    }
    proof = build_codex_app_server_goal_worker_proof(
        set_response=set_response,
        get_response=get_response,
        turn_start_request=turn_start_request,
        turn_start_response=turn_start_response,
        expected_objective=OBJECTIVE,
        expected_task_instruction=TASK_INSTRUCTION,
    )
    assert proof["persistent_goal_evidence"] is True, proof
    assert proof["turn_start_evidence"] is True, proof
    assert proof["baseline_claim_allowed"] is True, proof
    assert proof["matches"]["turn_thread"] is True, proof
    assert proof["matches"]["task_instruction"] is True, proof
    assert proof["task_instruction"]["raw_recorded"] is False, proof
    assert proof["task_instruction"]["chars"] == len(TASK_INSTRUCTION), proof

    missing_turn = build_codex_app_server_goal_worker_proof(
        set_response=set_response,
        get_response=get_response,
        turn_start_request=turn_start_request,
        turn_start_response=None,
        expected_objective=OBJECTIVE,
        expected_task_instruction=TASK_INSTRUCTION,
    )
    assert missing_turn["persistent_goal_evidence"] is True, missing_turn
    assert missing_turn["turn_start_evidence"] is False, missing_turn
    assert missing_turn["baseline_claim_allowed"] is False, missing_turn

    wrong_task = build_codex_app_server_goal_worker_proof(
        set_response=set_response,
        get_response=get_response,
        turn_start_request=turn_start_request,
        turn_start_response=turn_start_response,
        expected_objective=OBJECTIVE,
        expected_task_instruction="Different task",
    )
    assert wrong_task["turn_start_evidence"] is True, wrong_task
    assert wrong_task["baseline_claim_allowed"] is False, wrong_task
    assert wrong_task["matches"]["task_instruction"] is False, wrong_task


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--real-codex",
        action="store_true",
        help="Run an optional isolated local codex app-server paused-goal probe.",
    )
    args = parser.parse_args()

    assert_plan_contract()
    assert_proof_contract()
    assert_worker_plan_and_proof_contract()

    if args.real_codex:
        result = run_isolated_codex_app_server_goal_probe(
            objective=OBJECTIVE,
            status="paused",
        )
        proof = result["proof"]
        assert result["isolated_codex_home"] is True, result
        assert proof["persistent_goal_evidence"] is True, result
        assert proof["baseline_claim_allowed"] is True, result
        print(json.dumps(result, sort_keys=True))

    print("codex-app-server-goal-baseline-contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
