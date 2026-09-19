"""Hermetic file authoring and real-CLI closeout for required-vision qualification.

The executor does not author a decision or repair the actor's command. It only
confines file writes and observes the actual durable result. This is distinct
from the narrower progress-delta actor's acceptance boundary.
"""
from __future__ import annotations

import json
import re
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .model_tool_behavior import argument_value, loopx_command_tokens
from .model_behavior_qualification import model_behavior_semantic_contract_from_packet
from ..quota.effective_action import EffectiveAction

if TYPE_CHECKING:
    from .replan_semantic_action_behavior import _QualificationState

# Full closeout includes evidence discovery, authoring, refresh and settlement;
# its resource bound is independent of the narrower single-action qualifier.
REQUIRED_VISION_CLOSEOUT_MAX_CALLS = 16

VISION_HOST_INSTRUCTION = (
    "You are Codex operating a hermetic LoopX project. Follow the heartbeat and "
    "the live control-plane packet, including its semantic writeback and settlement. "
    "The shell cwd is the connected project. Available operations are bounded "
    "workspace reads, LoopX CLI commands, and new relative JSON file authoring "
    "via apply_patch Add File or cat with a quoted heredoc. A cat write may be "
    "followed by bound LoopX commands separated by newlines or &&. No external "
    "network or writes outside the fixture are available. Choose the decision "
    "from the evidence; file creation alone is not delivery."
)

VISION_EXEC_TOOL_DESCRIPTION = (
    "Execute bounded fixture commands, not an unrestricted shell. Workspace reads "
    "support pwd, ls (-a/-l), find (maxdepth at most 4), rg --files, cat, head and "
    "sed -n, optionally joined with &&, || or ; (at most 8 statements). Root "
    "loopx --help and loopx refresh-state --help are read-only queries and may "
    "be combined with reads or piped to head (at most 200 lines). Author a new "
    "relative JSON file via apply_patch Add File or cat with a quoted heredoc; "
    "a heredoc may be followed by up to two bound LoopX closeout commands using "
    "newlines or &&. Other LoopX commands must be separate single invocations. "
    "Returns stdout on success; nonzero workspace reads and unsupported command "
    "shapes return exit_code and output for correction within the same call "
    "budget. Unsupported programs or syntax are never executed. Semantic, "
    "identity and write-boundary errors fail qualification. No external network "
    "or outside-fixture writes."
)


def required_vision_scenario_contract(
    source_packet: Mapping[str, Any], contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the source scenario and bind its full closeout acceptance."""
    semantics = model_behavior_semantic_contract_from_packet(source_packet, arm="full_packet")
    vision = semantics["vision_continuation"]
    trigger_kinds = set(vision.get("trigger_kinds", []))
    required = {
        "selected_todo_id": None,
        "user_action_required": False,
        "must_attempt_work": True,
        "quiet_noop_allowed": False,
    }
    if any(contract.get(field) != value for field, value in required.items()):
        raise ValueError("required-vision scenario must execute before quiet wait")
    if vision.get("required") is not True or "required_agent_vision_missing" not in trigger_kinds:
        raise ValueError("required-vision scenario must preserve the profile gap")
    if semantics["required_reads"]:
        raise ValueError("required-vision replan must not require a model read ritual")
    action_packet = source_packet.get("replan_action_packet")
    obligation = source_packet.get("autonomous_replan_obligation")
    if not (
        isinstance(action_packet, Mapping)
        and isinstance(obligation, Mapping)
        and action_packet.get("decision") == "replan_required"
        and action_packet.get("obligation_id") == obligation.get("obligation_id")
        and dict(obligation.get("replan_context") or {}).get("delivery") == "host_projected"
    ):
        raise ValueError("required-vision scenario must preserve host-delivered replan context")
    if semantics["scheduler_action"].get("action") != "run_now":
        raise ValueError("required-vision scenario must remain immediately runnable")
    return {
        "qualification_scope": "required_vision_closeout",
        "trigger_kinds": sorted({item["kind"] for item in obligation["triggers"]}),
        "required_semantic_outcomes": list(action_packet["uncovered_frontier"]["required_any_of"]),
        "vision_closeout": {
            "checkpoint_satisfied": True, "bound_writeback": True,
            "settled": True, "spend_count": 1, "original_obligation_closed": True,
        },
    }


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
    lines = match[3].splitlines()
    if not lines or any(not line.startswith("+") for line in lines):
        raise ValueError("vision_authoring_requires_added_lines")
    return _write_json_file(project, match[2], "\n".join(line[1:] for line in lines) + "\n")


def _write_json_file(project: Path, name: str, content: str) -> str:
    relative = Path(name)
    if relative.is_absolute() or relative.suffix != ".json" or ".." in relative.parts:
        raise ValueError("vision_authoring_path_outside_fixture")
    target = (project / relative).resolve()
    if not target.is_relative_to(project.resolve()) or target.exists():
        raise ValueError("vision_authoring_path_outside_fixture")
    if not isinstance(json.loads(content), dict):
        raise ValueError("vision_authoring_requires_json_object")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return json.dumps({"ok": True, "path": relative.as_posix()})


def _json_heredoc(command: str) -> tuple[str, str, list[str]] | None:
    """Decode inert JSON plus a bounded CLI suffix, never a shell program."""
    header, newline, rest = command.partition("\n")
    if not newline or not header.lstrip().startswith("cat "):
        return None
    quoted = re.search(r"<<\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1", header)
    if quoted is None:
        return None
    lexer = shlex.shlex(header, posix=True, punctuation_chars="<>&;|")
    lexer.whitespace_split = True
    tokens = list(lexer)
    if len(tokens) != 5 or tokens[0] != "cat" or set(tokens[1::2]) != {">", "<<"}:
        raise ValueError("vision_authoring_requires_literal_json_heredoc")
    name = tokens[tokens.index(">") + 1]
    delimiter = tokens[tokens.index("<<") + 1]
    if delimiter != quoted[2]:
        raise ValueError("vision_authoring_requires_literal_json_heredoc")
    lines = rest.splitlines(keepends=True)
    end = next((index for index, line in enumerate(lines) if line.rstrip("\r\n") == delimiter), None)
    if end is None:
        raise ValueError("vision_authoring_requires_literal_json_heredoc")
    suffix = "".join(lines[end + 1:]).strip()
    lexer = shlex.shlex(suffix, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands: list[str] = []
    argv: list[str] = []
    for token in [*lexer, "\n"]:
        if token == "&&" or token.strip("\n") == "":
            if argv:
                if Path(argv[0]).name != "loopx":
                    raise ValueError("vision_authoring_suffix_requires_loopx")
                commands.append(shlex.join(argv))
                argv = []
        elif token in {";", "|", "||", "&"}:
            raise ValueError("vision_authoring_suffix_requires_loopx")
        else:
            argv.append(token)
    if len(commands) > 2:
        raise ValueError("vision_authoring_suffix_requires_loopx")
    return name, "".join(lines[:end]), commands


def _rows(state: _QualificationState) -> list[dict[str, Any]]:
    goal_id = str((state.quota_packet or {})["goal_id"])
    index = state.fixture.runtime_root / "goals" / goal_id / "runs" / "index.jsonl"
    return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line]


def dispatch_vision_closeout(
    command: str, state: _QualificationState, *, execute: Callable[..., str],
) -> tuple[str, str, bool] | None:
    heredoc = _json_heredoc(command)
    if heredoc is not None:
        if not state.seen_quota:
            raise ValueError("vision_authoring_before_quota")
        name, content, suffix = heredoc
        result: tuple[str, str, bool] = (_write_json_file(state.fixture.project_root, name, content), "vision_file_authoring", False)
        for following in suffix:
            if result[2]:
                raise ValueError("vision_authoring_suffix_requires_loopx")
            next_result = dispatch_vision_closeout(following, state, execute=execute)
            if next_result is None:
                raise ValueError("vision_authoring_suffix_requires_loopx")
            result = next_result
        return result
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
