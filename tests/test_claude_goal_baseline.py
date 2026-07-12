from __future__ import annotations

import pytest

from loopx.claude_goal_baseline import (
    CLAUDE_CODE_GOAL_SEAMS,
    build_claude_code_goal_baseline_plan,
    build_claude_code_goal_baseline_proof,
    stable_text_digest,
)


def test_claude_goal_baseline_plan_describes_supported_control_plane() -> None:
    write_scope = ["src/**", "tests/**"]

    plan = build_claude_code_goal_baseline_plan(
        objective="Fix the failing parser contract",
        write_scope=write_scope,
        token_budget=4_000,
    )
    write_scope.append("docs/**")

    assert plan["schema_version"] == "claude_code_goal_baseline_v0"
    assert plan["native_goal_api_present"] is False
    assert plan["seams"] == list(CLAUDE_CODE_GOAL_SEAMS)
    assert plan["objective_sha256"] == stable_text_digest(
        "Fix the failing parser contract"
    )
    assert plan["objective_chars"] == 31
    assert plan["status"] == "active"
    assert plan["write_scope"] == ["src/**", "tests/**"]
    assert plan["token_budget_present"] is True
    assert plan["claim_boundary"]["permission_decision_is_deterministic"] is True


@pytest.mark.parametrize(
    ("objective", "status", "message"),
    [
        ("  ", "active", "objective must be non-empty"),
        ("Fix parser", "running", "unsupported goal status: running"),
    ],
)
def test_claude_goal_baseline_plan_rejects_invalid_inputs(
    objective: str,
    status: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_claude_code_goal_baseline_plan(objective=objective, status=status)


def test_claude_goal_baseline_proof_allows_complete_deterministic_evidence() -> None:
    proof = build_claude_code_goal_baseline_proof(
        expected_objective="Fix parser",
        hook_installed=True,
        hook_denied_out_of_scope=True,
        hook_allowed_in_scope=True,
        should_run_consulted=True,
        todo_completed_via_cli_or_mcp=True,
    )

    assert proof["schema_version"] == "claude_code_goal_baseline_proof_v0"
    assert proof["deterministic_gate_evidence"] is True
    assert proof["loop_evidence"] is True
    assert proof["baseline_claim_allowed"] is True
    assert proof["expected_objective_sha256"] == stable_text_digest("Fix parser")
    assert proof["negative_controls"] == {
        "prompt_only_loop": False,
        "included_loopx_state_in_prompt": False,
    }


@pytest.mark.parametrize(
    "override",
    [
        {"hook_denied_out_of_scope": False},
        {"should_run_consulted": False},
        {"used_unverified_prompt_only_loop": True},
        {"included_loopx_state_in_prompt": True},
    ],
)
def test_claude_goal_baseline_proof_fails_closed(
    override: dict[str, bool],
) -> None:
    kwargs = {
        "expected_objective": "Fix parser",
        "hook_installed": True,
        "hook_denied_out_of_scope": True,
        "hook_allowed_in_scope": True,
        "should_run_consulted": True,
        "todo_completed_via_cli_or_mcp": True,
        **override,
    }

    proof = build_claude_code_goal_baseline_proof(**kwargs)

    assert proof["baseline_claim_allowed"] is False
