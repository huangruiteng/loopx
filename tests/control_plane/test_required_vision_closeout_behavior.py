from __future__ import annotations

import json
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane.testing.model_tool_behavior import (
    EXEC_COMMAND_TOOL, ScriptedAssistantAction, ScriptedDoubaoExecTransport, ScriptedExecToolAction,
)
from loopx.control_plane.testing.replan_semantic_action_behavior import (
    DoubaoReplanSemanticActionBehaviorActor, _build_fixture,
    _bounded_workspace_read_plan, _execute_workspace_read,
)
from loopx.control_plane.testing.replan_vision_closeout_behavior import _authored_file, _json_heredoc


def _packet(request: Mapping[str, Any]) -> dict[str, Any]:
    for message in request["messages"]:
        if message["role"] == "tool":
            value = json.loads(message["content"])
            if "replan_action_packet" in value:
                return value
    raise AssertionError("quota was not observed")


def vision_patch_action(_: Mapping[str, Any]) -> ScriptedExecToolAction:
    # Authored independently from the implementation under test. The path is
    # still open: evidence confirms reader-by-default, not completion of a Goal.
    decision = {
        "schema_version": "goal_vision_replan_contract_v0",
        "state": "vision_patch_proposed",
        "vision_patch": {
            "vision_summary": "Preserve the explicit write permission boundary.",
            "acceptance_summary": "Reader is default; writing requires an explicit grant.",
            "advancement_policy": "as_needed",
        },
        "path_delta": {
            "schema_version": "goal_path_delta_v0", "outcome": "continue",
            "prior_assumption": "The permission boundary needed inspection.",
            "observed_reality": "The configuration defaults to reader and requires a write grant.",
            "retained": ["Explicit write grant"], "changed": ["Evidence-linked vision baseline"],
            "evidence_refs": ["evidence-permission-config"],
        },
    }
    lines = "\n".join("+" + line for line in json.dumps(decision, indent=2).splitlines())
    return ScriptedExecToolAction(
        "apply_patch <<'PATCH'\n*** Begin Patch\n*** Add File: decision.json\n"
        + lines + "\n*** End Patch\nPATCH"
    )


def projected_refresh(request: Mapping[str, Any]) -> ScriptedExecToolAction:
    actions = _packet(request)["interaction_contract"]["cli_channel"]["next_cli_actions"]
    return ScriptedExecToolAction(actions[0].replace(
        "<path-to-evidence-linked-goal-vision-replan-contract-v0.json>", "decision.json",
    ))


def projected_spend(request: Mapping[str, Any]) -> ScriptedExecToolAction:
    command = _packet(request)["interaction_contract"]["cli_channel"]["next_cli_actions"][1]
    return ScriptedExecToolAction(command)


def heredoc_action(request: Mapping[str, Any]) -> ScriptedExecToolAction:
    patch_lines = vision_patch_action(request).command.splitlines()[3:-2]
    content = "\n".join(line[1:] for line in patch_lines)
    return ScriptedExecToolAction("cat > decision.json <<'JSON'\n" + content + "\nJSON")


@pytest.mark.parametrize("advancement_policy", ["as_needed", "repeat_until_closed"])
@pytest.mark.parametrize("authoring", ["apply_patch", "heredoc_with_closeout"])
def test_required_vision_uses_real_bound_refresh_spend_and_readback(tmp_path: Path, advancement_policy: str, authoring: str) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def authored_decision(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        command = (vision_patch_action if authoring == "apply_patch" else heredoc_action)(request).command
        command = command.replace('"as_needed"', json.dumps(advancement_policy))
        if authoring == "heredoc_with_closeout":
            command += "\n" + projected_refresh(request).command + " && " + projected_spend(request).command
        return ScriptedExecToolAction(command)
    actions = [
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json"),
        ScriptedExecToolAction("cat fixture/permission-config.json"),
        authored_decision,
    ]
    if authoring == "apply_patch":
        actions.extend([projected_refresh, projected_spend])
    transport = ScriptedDoubaoExecTransport(actions)
    receipt = DoubaoReplanSemanticActionBehaviorActor(
        api_key="test-only-placeholder", transport=transport,
    ).qualify(qualification_id="required-vision", fixture_root=tmp_path / "actor", required_vision=True)
    assert receipt["qualification_passed"] is True, receipt
    assert receipt["trigger_kinds"] == ["required_agent_vision_missing"]
    assert receipt["selected_semantic_outcomes"] == ["fresh_vision_path_outcome"]
    assert receipt["vision_closeout"] == {
        "checkpoint_satisfied": True, "bound_writeback": True, "settled": True,
        "spend_count": 1, "original_obligation_closed": True,
    }
    if advancement_policy == "as_needed":
        assert receipt["semantic_reentry"]["effective_action"] == "monitor_quiet_skip"
    assert "required_agent_vision_missing" not in receipt["semantic_reentry"]["trigger_kinds"]


def test_successful_refresh_without_settlement_is_not_qualified(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json"),
        ScriptedExecToolAction("cat fixture/permission-config.json"),
        vision_patch_action, projected_refresh, ScriptedAssistantAction("Done"),
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(
        api_key="test-only-placeholder", transport=transport,
    ).qualify(qualification_id="required-vision-incomplete", fixture_root=tmp_path / "actor", required_vision=True)
    assert receipt["qualification_passed"] is False
    assert receipt["vision_closeout"]["checkpoint_satisfied"] is True
    assert receipt["vision_closeout"]["settled"] is False


def test_wrong_turn_is_rejected_not_repaired_by_fixture_adapter(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def wrong_turn(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        tokens = shlex.split(projected_refresh(request).command)
        tokens[tokens.index("--turn-instance-id") + 1] = "another-turn"
        return ScriptedExecToolAction(shlex.join(tokens))
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json"),
        ScriptedExecToolAction("cat fixture/permission-config.json"),
        vision_patch_action, wrong_turn,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(
        api_key="test-only-placeholder", transport=transport,
    ).qualify(qualification_id="wrong-turn", fixture_root=tmp_path / "actor", required_vision=True)
    assert receipt["qualification_passed"] is False
    assert receipt["failure_code"] == "vision_closeout_turn_mismatch"
    assert "vision_closeout" not in receipt


def test_authoring_cannot_escape_or_overwrite_fixture(tmp_path: Path) -> None:
    command = vision_patch_action({}).command
    for path in ("../outside.json", "/outside.json"):
        with pytest.raises(ValueError, match="path_outside_fixture"):
            _authored_file(command.replace("decision.json", path), tmp_path)
    _authored_file(command, tmp_path)
    original = (tmp_path / "decision.json").read_bytes()
    with pytest.raises(ValueError, match="path_outside_fixture"):
        _authored_file(command, tmp_path)
    assert (tmp_path / "decision.json").read_bytes() == original


def test_heredoc_is_inert_json_and_never_an_arbitrary_shell_program() -> None:
    command = heredoc_action({}).command
    name, content, suffix = _json_heredoc(command.replace("Explicit write grant", "$(touch outside); `echo untrusted`"))
    assert name == "decision.json" and suffix == []
    assert "$(touch outside)" in json.loads(content)["path_delta"]["retained"][0]
    for tail in ("\ntouch outside", "\nloopx quota spend-slot; touch outside", "\nloopx quota spend-slot | echo outside"):
        with pytest.raises(ValueError, match="suffix_requires_loopx"):
            _json_heredoc(command + tail)
    assert _json_heredoc(command.replace("<<'JSON'", "<<JSON")) is None


def test_host_composes_bounded_reads_and_real_cli_help(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path, required_vision=True)
    command = f'ls {shlex.quote(str(fixture.runtime_root))} 2>/dev/null && echo "---" && loopx --help 2>&1 | head -60'
    plan = _bounded_workspace_read_plan(command, fixture=fixture)
    assert plan is not None
    assert plan[-1].kind == "loopx_help"
    output, frontier_read, source_read, exit_code = _execute_workspace_read(command, fixture=fixture)
    assert "usage:" in output.lower() and "loopx" in output
    assert exit_code == 0 and not frontier_read and not source_read
    # Adding an unadmitted effect rejects the entire plan before execution.
    assert _bounded_workspace_read_plan(command + " && touch injected", fixture=fixture) is None
    with pytest.raises(ValueError, match="outside the hermetic fixture"):
        _execute_workspace_read(command + " && touch injected", fixture=fixture)
    assert not (fixture.project_root / "injected").exists()


@pytest.mark.parametrize("command", ["loopx --help", "cat replan-frontier.json && loopx refresh-state --help"])
def test_read_and_help_extension_preserves_quota_first(command: str, tmp_path: Path) -> None:
    transport = ScriptedDoubaoExecTransport([ScriptedExecToolAction(command)])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="read-before-quota", fixture_root=tmp_path, required_vision=True,
    )
    assert receipt["qualification_passed"] is False
    assert receipt["failure_code"] == "workspace_read_before_quota"
    assert receipt["semantic_action_accepted"] is False


def test_read_error_reaches_model_and_recovery_still_requires_full_closeout(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def recover(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        error = json.loads(request["messages"][-1]["content"])
        assert error["exit_code"] != 0
        assert error["error_code"] == "workspace_read_nonzero"
        assert "missing.json" in error["output"]
        return ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json")
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat missing.json"), recover,
        vision_patch_action, projected_refresh, projected_spend,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="read-error-recovery", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is True
    assert receipt["vision_closeout"]["spend_count"] == 1
    assert receipt["tool_call_count"] == 6
    assert receipt["tool_call_receipts"][1]["error_code"] == "workspace_read_nonzero"
    assert "bounded" in transport.requests[0]["tools"][0]["function"]["description"]


def test_read_failures_consume_the_full_closeout_call_budget(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        *[ScriptedExecToolAction("cat missing.json") for _ in range(15)],
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="read-errors-exhaust-budget", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is False
    assert receipt["failure_code"] == "tool_call_budget_exhausted"
    assert receipt["tool_call_count"] == receipt["tool_call_limit"] == 16
    assert receipt["semantic_action_accepted"] is False


@pytest.mark.parametrize("command", [
    "ls -la .codex/ && find .codex -maxdepth 5 -type f | head -50",
    "touch injected",
])
def test_unadmitted_commands_return_feedback_without_execution_or_extra_budget(command: str, tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def recover(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        error = json.loads(request["messages"][-1]["content"])
        assert error["error_code"] == "unsupported_host_command"
        assert error["exit_code"] != 0
        assert "not executed" in error["output"]
        return vision_patch_action(request)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json"),
        ScriptedExecToolAction(command), recover, projected_refresh, projected_spend,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="unadmitted-command-recovery", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is True
    assert receipt["vision_closeout"]["spend_count"] == 1
    assert receipt["tool_call_count"] == 6
    assert receipt["tool_call_receipts"][2]["error_code"] == "unsupported_host_command"
    assert not list(tmp_path.rglob("injected"))


def test_unadmitted_commands_never_supply_evidence_or_success(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        *[ScriptedExecToolAction("find . -maxdepth 5 -type f") for _ in range(15)],
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="unadmitted-command-budget", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is False
    assert receipt["failure_code"] == "tool_call_budget_exhausted"
    assert receipt["semantic_action_accepted"] is False
    assert receipt["tool_call_count"] == receipt["tool_call_limit"] == 16


@pytest.mark.parametrize("extra_reads,passed", [(11, True), (12, False)])
def test_full_closeout_budget_boundary_never_waives_settlement(extra_reads: int, passed: bool, tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json"),
        *[ScriptedExecToolAction("pwd") for _ in range(extra_reads)],
        vision_patch_action, projected_refresh, projected_spend,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="closeout-budget-boundary", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is passed
    assert receipt["tool_call_count"] == receipt["tool_call_limit"] == 16
    assert receipt["semantic_action_accepted"] is True
    assert receipt["vision_closeout"]["settled"] is passed
    if passed:
        assert receipt["vision_closeout"]["spend_count"] == 1
    else:
        assert receipt["failure_code"] == "tool_call_budget_exhausted"


def test_narrow_semantic_action_keeps_seven_call_budget(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle")
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        *[ScriptedExecToolAction("pwd") for _ in range(7)],
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="narrow-budget-unchanged", fixture_root=tmp_path / "actor",
    )
    assert receipt["qualification_passed"] is False
    assert receipt["failure_code"] == "tool_call_budget_exhausted"
    assert receipt["tool_call_count"] == receipt["tool_call_limit"] == 7


@pytest.mark.parametrize("rejection", ["suffix", "outside", "invalid_json", "overwrite"])
def test_authoring_rejection_is_recoverable_but_has_no_file_or_suffix_effect(rejection: str, tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    root = tmp_path / "actor" / "project"
    def rejected_authoring(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        command = heredoc_action(request).command
        if rejection == "suffix":
            command += "\ntouch injected"
        elif rejection == "outside":
            command = command.replace("decision.json", "../outside.json")
        elif rejection == "invalid_json":
            command = "cat > decision.json <<'JSON'\n{broken\nJSON"
        else:
            command = command.replace("decision.json", "fixture/permission-config.json")
        return ScriptedExecToolAction(command)
    def recover(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        error = json.loads(request["messages"][-1]["content"])
        assert error["exit_code"] != 0 and "not executed" in error["output"]
        if rejection == "suffix":
            assert "touch" in error["output"] and "heredoc alone" in error["output"]
        assert not (root / "decision.json").exists()
        assert not list(tmp_path.rglob("injected"))
        assert not list(tmp_path.rglob("outside.json"))
        assert (root / "fixture/permission-config.json").read_bytes() == fixture.work_source_target.read_bytes()
        return heredoc_action(request)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json"),
        rejected_authoring, recover, projected_refresh, projected_spend,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="authoring-error-recovery", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is True
    assert receipt["vision_closeout"]["spend_count"] == 1
    assert receipt["tool_call_count"] == 6


@pytest.mark.parametrize("evidence_ref,passed", [
    ("evidence-permission-config", True), ("fixture/permission-config.json", True),
    ("fixture/unread.json", False), ("replan-frontier.json", False),
])
def test_closeout_matches_observed_evidence_not_one_identifier_spelling(evidence_ref: str, passed: bool, tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def author(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        return ScriptedExecToolAction(heredoc_action(request).command.replace("evidence-permission-config", evidence_ref))
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json"),
        author, projected_refresh,
        projected_spend if passed else ScriptedAssistantAction("No observed source reference supplied."),
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="observed-evidence-reference", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is passed
    if passed:
        assert receipt["vision_closeout"]["spend_count"] == 1
    else:
        assert receipt["tool_call_receipts"][-1]["error_code"] == "vision_closeout_evidence_not_observed"
        assert receipt["semantic_action_accepted"] is False


@pytest.mark.parametrize("shell_shape", ["assignment_prefix", "newline_sequence"])
def test_shell_shape_is_not_silently_discarded_before_binding_check(shell_shape: str, tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def prefixed(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        command = projected_refresh(request).command
        command = ("TURN=unexpanded\n" + command if shell_shape == "assignment_prefix"
                   else command + "\n" + projected_spend(request).command)
        return ScriptedExecToolAction(command)
    def recover(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        error = json.loads(request["messages"][-1]["content"])
        assert error["error_code"] == "vision_command_requires_literal_loopx_argv"
        assert "not executed" in error["output"]
        return projected_refresh(request)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json"),
        vision_patch_action, prefixed, recover, projected_spend,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="literal-cli-admission", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is True
    assert receipt["vision_closeout"]["spend_count"] == 1
    assert receipt["tool_call_count"] == 6


@pytest.mark.parametrize("rejection", ["unobserved_evidence", "oversized_vision"])
def test_actor_can_correct_its_own_draft_after_rejection(rejection: str, tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    def ungrounded(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        command = heredoc_action(request).command
        command = (command.replace("evidence-permission-config", "unobserved-evidence")
                   if rejection == "unobserved_evidence" else command.replace(
                       "Reader is default; writing requires an explicit grant.", "x" * 700))
        return ScriptedExecToolAction(command)
    def corrected(request: Mapping[str, Any]) -> ScriptedExecToolAction:
        error = json.loads(request["messages"][-1]["content"])
        if rejection == "unobserved_evidence":
            assert error["error_code"] == "vision_closeout_evidence_not_observed"
            assert "fixture/permission-config.json" in error["output"]
        else:
            assert error["error_code"] == "loopx_cli_nonzero"
            assert error["exit_code"] != 0
        return heredoc_action(request)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json && cat fixture/permission-config.json"),
        ungrounded, projected_refresh, corrected, projected_refresh, projected_spend,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="correct-owned-draft", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is True
    assert receipt["vision_closeout"]["spend_count"] == 1
    assert receipt["tool_call_count"] == 7


def test_help_host_extension_does_not_change_narrow_actor_contract(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path)
    assert _bounded_workspace_read_plan("loopx --help", fixture=fixture) is None
    with pytest.raises(RuntimeError, match="workspace read failed"):
        _execute_workspace_read("cat missing.json", fixture=fixture)


def test_failed_read_does_not_supply_source_evidence(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path / "oracle", required_vision=True)
    transport = ScriptedDoubaoExecTransport([
        ScriptedExecToolAction(fixture.quota_guard_command),
        ScriptedExecToolAction("cat replan-frontier.json"),
        ScriptedExecToolAction("cat missing.json"), vision_patch_action, projected_refresh,
    ])
    receipt = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport).qualify(
        qualification_id="failed-read-is-not-evidence", fixture_root=tmp_path / "actor", required_vision=True,
    )
    assert receipt["qualification_passed"] is False
    assert receipt["failure_code"] == "vision_closeout_requires_observed_source_and_authored_decision"
    assert receipt["semantic_action_accepted"] is False


def test_read_short_circuit_and_stderr_suppression_are_preserved(tmp_path: Path) -> None:
    fixture = _build_fixture(tmp_path, required_vision=True)
    output, _, _, code = _execute_workspace_read("cat missing.json 2>/dev/null && loopx --help", fixture=fixture)
    assert code != 0 and output == ""
    output, _, _, code = _execute_workspace_read("cat missing.json 2>/dev/null || loopx --help", fixture=fixture)
    assert code == 0 and "usage:" in output.lower()


def test_tool_description_override_is_request_local() -> None:
    transport = ScriptedDoubaoExecTransport([ScriptedAssistantAction("done"), ScriptedAssistantAction("done")])
    client = DoubaoReplanSemanticActionBehaviorActor(api_key="test-only-placeholder", transport=transport)._client
    client.next_step([], tool_description="A bounded test host")
    client.next_step([])
    custom = transport.requests[0]["tools"][0]
    assert custom["function"]["description"] == "A bounded test host"
    assert custom["function"]["parameters"] == EXEC_COMMAND_TOOL["function"]["parameters"]
    assert transport.requests[1]["tools"] == [EXEC_COMMAND_TOOL]
