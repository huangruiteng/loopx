"""Hermetic file authoring and real-CLI closeout for required-vision qualification.

The executor does not author a decision or repair the actor's command. It only
confines file writes and observes the actual durable result. This is distinct
from the narrower progress-delta actor's acceptance boundary.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .model_tool_behavior import argument_value, loopx_command_tokens
from ..quota.effective_action import EffectiveAction

if TYPE_CHECKING:
    from .replan_semantic_action_behavior import _QualificationState

VISION_HOST_INSTRUCTION = (
    "You are Codex operating a hermetic LoopX project. Follow the heartbeat and "
    "the live control-plane packet, including its semantic writeback and settlement. "
    "The shell cwd is the connected project. Available operations are bounded "
    "workspace reads, LoopX CLI commands, and apply_patch with a single Add File "
    "patch in a quoted heredoc to author a new relative JSON file. No external "
    "network or writes outside the fixture are available. Choose the decision "
    "from the evidence; file creation alone is not delivery."
)


def _authored_file(command: str, project: Path) -> str:
    # Accept data, never execute the model's shell program. JSON quotes and
    # shell metacharacters inside added lines remain literal file content.
    match = re.fullmatch(
        r"apply_patch\s+<<\s*'([A-Za-z_][A-Za-z0-9_]*)'\n"
        r"\*\*\* Begin Patch\n\*\*\* Add File: ([^\n]+)\n"
        r"(.*?)\n\*\*\* End Patch\n\1", command.strip(), re.DOTALL,
    )
    if not match:
        raise ValueError("vision_authoring_requires_single_add_file_patch")
    relative = Path(match[2])
    if relative.is_absolute() or relative.suffix != ".json" or ".." in relative.parts:
        raise ValueError("vision_authoring_path_outside_fixture")
    target = (project / relative).resolve()
    if not target.is_relative_to(project.resolve()) or target.exists():
        raise ValueError("vision_authoring_path_outside_fixture")
    lines = match[3].splitlines()
    if not lines or any(not line.startswith("+") for line in lines):
        raise ValueError("vision_authoring_requires_added_lines")
    content = "\n".join(line[1:] for line in lines) + "\n"
    if not isinstance(json.loads(content), dict):
        raise ValueError("vision_authoring_requires_json_object")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return json.dumps({"ok": True, "path": relative.as_posix()})


def _rows(state: _QualificationState) -> list[dict[str, Any]]:
    goal_id = str((state.quota_packet or {})["goal_id"])
    index = state.fixture.runtime_root / "goals" / goal_id / "runs" / "index.jsonl"
    return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line]


def dispatch_vision_closeout(
    command: str, state: _QualificationState, *, execute: Callable[..., str],
) -> tuple[str, str, bool] | None:
    if command.startswith("apply_patch"):
        if not state.seen_quota:
            raise ValueError("vision_authoring_before_quota")
        return _authored_file(command, state.fixture.project_root), "vision_file_authoring", False
    tokens = loopx_command_tokens(command) or []
    if "refresh-state" not in tokens and "spend-slot" not in tokens:
        return None
    packet = state.quota_packet or {}
    binding = dict(dict(dict(packet.get("interaction_contract") or {}).get("cli_channel") or {}).get("replan_settlement_contract") or {}).get("settlement_binding") or {}
    if not binding or argument_value(tokens, binding["cli_argument"]) != binding["id"]:
        raise ValueError("vision_closeout_binding_mismatch")
    if argument_value(tokens, "--turn-instance-id") != state.turn_instance_id:
        raise ValueError("vision_closeout_turn_mismatch")
    if "refresh-state" in tokens:
        path = argument_value(tokens, "--agent-vision-json")
        if not path or not state.work_source_read:
            raise ValueError("vision_closeout_requires_observed_source_and_authored_decision")
        target = (state.fixture.project_root / path).resolve()
        if not target.is_relative_to(state.fixture.project_root.resolve()):
            raise ValueError("vision_authoring_path_outside_fixture")
        vision = json.loads(target.read_text(encoding="utf-8"))
        source_evidence = json.loads(state.fixture.frontier_target.read_text(encoding="utf-8"))["uncovered"]
        observed_ids = {item["evidence_id"] for item in source_evidence}
        path_delta = vision.get("path_delta")
        refs = path_delta.get("evidence_refs") if isinstance(path_delta, dict) else None
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("vision_closeout_evidence_not_observed")
        refs = set(refs)
        if not refs.intersection(observed_ids):
            raise ValueError("vision_closeout_evidence_not_observed")
        output = execute(command, fixture=state.fixture, turn_instance_id=state.turn_instance_id)
        row = _rows(state)[-1]
        semantic = dict(row.get("autonomous_replan_ack") or {}).get("semantic_delta") or {}
        checkpoint = dict(row.get("vision_checkpoint") or {})
        identity = dict(row.get("settlement_identity") or {})
        expected_identity = dict(packet.get("heartbeat_receipt") or {}).get("settlement_identity")
        if not (semantic.get("accepted") is True and semantic.get("obligation_id") == binding["id"]
                and checkpoint.get("satisfied") is True and identity == expected_identity):
            raise ValueError("vision_closeout_durable_writeback_incomplete")
        state.semantic_delta = semantic
        state.vision_closeout = {"checkpoint_satisfied": True, "bound_writeback": True, "settled": False}
        return output, "semantic_replan_writeback", False
    if state.vision_closeout is None:
        raise ValueError("vision_closeout_spend_before_writeback")
    output = execute(command, fixture=state.fixture, turn_instance_id=state.turn_instance_id)
    replay = json.loads(execute(state.fixture.quota_guard_command, fixture=state.fixture,
                                turn_instance_id=state.turn_instance_id))
    following = json.loads(execute(state.fixture.quota_guard_command, fixture=state.fixture,
                                   turn_instance_id=f"{state.turn_instance_id}-readback"))
    spends = [row for row in _rows(state) if row.get("classification") == "quota_slot_spent"]
    if replay.get("effective_action") != EffectiveAction.HEARTBEAT_SETTLED_SKIP.value or len(spends) != 1:
        raise ValueError("vision_closeout_settlement_readback_failed")
    remaining = dict(following.get("autonomous_replan_obligation") or {})
    remaining_kinds = {item["kind"] for item in remaining.get("triggers", [])}
    if remaining.get("obligation_id") == binding["id"] or remaining_kinds.intersection({"required_agent_vision_missing", "vision_checkpoint_missing"}):
        raise ValueError("vision_closeout_rearmed_after_settlement")
    # A real successor requirement may follow a newly authored continuing
    # vision. Do not force the model to declare as_needed or no_followup just
    # to obtain a quiet next wake.
    state.vision_closeout.update(settled=True, spend_count=1, original_obligation_closed=True)
    state.semantic_reentry_observation = {"effective_action": following.get("effective_action"),
                                          "trigger_kinds": sorted(remaining_kinds)}
    return output, "quota_spend_slot", True
