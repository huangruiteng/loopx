from __future__ import annotations

import json
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane.testing.model_tool_behavior import (
    ScriptedAssistantAction, ScriptedDoubaoExecTransport, ScriptedExecToolAction,
)
from loopx.control_plane.testing.replan_semantic_action_behavior import (
    DoubaoReplanSemanticActionBehaviorActor, _build_fixture,
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
