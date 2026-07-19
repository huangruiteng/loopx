from __future__ import annotations

import contextlib
import io
import json
import shlex
from pathlib import Path
from typing import Any

from loopx.bootstrap_command_pack import (
    GUIDED_COMMAND_PACK_PROJECTION_SCHEMA_VERSION,
    build_start_goal_guided_packet,
)
from loopx.cli import main as cli_main


GOAL_ID = "guided-projection-goal"
AGENT_ID = "codex-guided-projection"
GOAL_TEXT = "Ship a bounded public issue triage workflow."


def _write_connected_project(root: Path) -> Path:
    project = root / "project"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("# Active Goal State\n", encoding="utf-8")
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "goals": [
                    {
                        "id": GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_file.relative_to(project)),
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return project


def _build(project: Path, *, include_detail: bool) -> dict[str, Any]:
    return build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
        include_command_pack_detail=include_detail,
    )


def _host_shadow_document(payload: dict[str, Any]) -> dict[str, Any]:
    command_pack = payload["command_pack"]
    transaction = payload["guided_transaction"]
    return {
        "schema_version": payload["schema_version"],
        "project": payload["project"],
        "goal_id": payload["goal_id"],
        "agent_id": payload["agent_id"],
        "host_surface": payload["host_surface"],
        "goal_text": payload["goal_text"],
        "recommended_next_step": payload["recommended_next_step"],
        "ordered_steps": transaction["ordered_steps"],
        "idempotency_policy": transaction["idempotency_policy"],
        "preserve_todos_policy": transaction["preserve_todos_policy"],
        "goal_start_contract": command_pack["goal_start_contract"],
        "commands": command_pack["commands"],
        "host_loop_activation": command_pack["host_loop_activation"],
        "safety_contract": payload["safety_contract"],
    }


def _resolve_pointer(payload: Any, pointer: str) -> Any:
    assert pointer.startswith("#/")
    current = payload
    for escaped_part in pointer[2:].split("/"):
        part = escaped_part.replace("~1", "/").replace("~0", "~")
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _invoke_detail_command(command: str) -> dict[str, Any]:
    argv = shlex.split(command)
    assert argv[0] == "loopx"
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(argv[1:])
    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert isinstance(payload, dict)
    return payload


def test_default_projection_preserves_host_actions_and_json_anchors(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    compact = _build(project, include_detail=False)
    detailed = _build(project, include_detail=True)

    assert set(compact) == set(detailed)
    assert _host_shadow_document(compact) == _host_shadow_document(detailed)
    assert compact["command_pack_detail_included"] is False
    assert detailed["command_pack_detail_included"] is True

    projection = compact["command_pack"]
    assert projection["schema_version"] == "loopx_bootstrap_command_pack_v0"
    assert (
        projection["projection_schema_version"]
        == GUIDED_COMMAND_PACK_PROJECTION_SCHEMA_VERSION
    )
    assert projection["projection_mode"] == "guided_start_compatibility"
    assert projection["commands"] == detailed["command_pack"]["commands"]
    assert (
        projection["host_loop_activation"]
        == detailed["command_pack"]["host_loop_activation"]
    )
    assert "message" not in projection
    assert "available_slash_commands" not in projection
    assert (
        projection["goal_start_contract"]
        == detailed["command_pack"]["goal_start_contract"]
    )
    assert projection["safety_contract"] == detailed["command_pack"]["safety_contract"]

    compatibility = compact["packet_summary"]["compatibility"]
    assert compatibility == {
        "legacy_fields_retained": False,
        "compact_projection_default": True,
        "removal_gate": "explicit_host_shadow_parity",
    }
    for ref in compact["packet_summary"]["detail_refs"].values():
        _resolve_pointer(compact, ref["json_pointer"])
    for ref in projection["packet_summary"]["detail_refs"].values():
        _resolve_pointer(projection, ref["json_pointer"])


def test_explicit_cold_path_restores_the_complete_command_pack(tmp_path: Path) -> None:
    project = _write_connected_project(tmp_path)
    compact = _build(project, include_detail=False)
    restored = _invoke_detail_command(compact["command_pack"]["detail_command"])

    assert restored["command_pack_detail_included"] is True
    assert "commands" in restored["command_pack"]
    assert "message" in restored["command_pack"]
    assert "host_loop_activation" in restored["command_pack"]
    assert "available_slash_commands" in restored["command_pack"]
    assert _host_shadow_document(restored) == _host_shadow_document(compact)
    assert restored["packet_summary"]["compatibility"] == {
        "legacy_fields_retained": True,
        "compact_projection_default": False,
        "removal_gate": "explicit_host_shadow_parity",
    }


def test_projection_materially_reduces_repetition_without_hiding_measurement(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    compact = _build(project, include_detail=False)
    detailed = _build(project, include_detail=True)
    compact_json = json.dumps(compact, ensure_ascii=False, sort_keys=True)
    detailed_json = json.dumps(detailed, ensure_ascii=False, sort_keys=True)

    assert len(compact_json) <= int(len(detailed_json) * 0.65)
    compact_duplication = compact["packet_summary"]["duplication_measurement"]
    detailed_duplication = detailed["packet_summary"]["duplication_measurement"]
    assert compact_duplication["objective_content"]["duplicate_occurrences"] <= 11
    assert compact_duplication["command_content"]["duplicate_occurrences"] <= 13
    assert (
        compact_duplication["objective_content"]["duplicate_occurrences"]
        < (detailed_duplication["objective_content"]["duplicate_occurrences"])
    )
    assert (
        compact_duplication["command_content"]["duplicate_occurrences"]
        < (detailed_duplication["command_content"]["duplicate_occurrences"])
    )


def test_projection_preserves_agent_identity_gate_actions(tmp_path: Path) -> None:
    project = _write_connected_project(tmp_path)
    registry_path = project / ".loopx" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["registered_agents"].append(
        "codex-guided-reviewer"
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    common = {
        "project": project,
        "goal_id": GOAL_ID,
        "agent_id": None,
        "cli_bin": "loopx",
        "host_surface": "codex-app",
        "goal_text": GOAL_TEXT,
        "available_capabilities": ["network"],
    }
    compact = build_start_goal_guided_packet(
        **common,
        include_command_pack_detail=False,
    )
    detailed = build_start_goal_guided_packet(
        **common,
        include_command_pack_detail=True,
    )

    assert compact["guided_transaction"]["blocked_by"] == "agent_identity_selection"
    assert _host_shadow_document(compact) == _host_shadow_document(detailed)


def test_projection_preserves_multi_goal_selection_actions(tmp_path: Path) -> None:
    project = _write_connected_project(tmp_path)
    registry_path = project / ".loopx" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    second_goal_id = "guided-projection-second-goal"
    second_state = (
        project / ".codex" / "goals" / second_goal_id / "ACTIVE_GOAL_STATE.md"
    )
    second_state.parent.mkdir(parents=True)
    second_state.write_text("# Second Active Goal State\n", encoding="utf-8")
    registry["goals"].append(
        {
            "id": second_goal_id,
            "status": "active",
            "repo": str(project),
            "state_file": str(second_state.relative_to(project)),
            "coordination": {
                "agent_model": "peer_v1",
                "registered_agents": ["codex-guided-second"],
            },
        }
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    common = {
        "project": project,
        "goal_id": None,
        "agent_id": None,
        "cli_bin": "loopx",
        "host_surface": "codex-app",
        "goal_text": GOAL_TEXT,
        "available_capabilities": ["network"],
    }
    compact = build_start_goal_guided_packet(
        **common,
        include_command_pack_detail=False,
    )
    detailed = build_start_goal_guided_packet(
        **common,
        include_command_pack_detail=True,
    )

    assert compact["guided_transaction"]["blocked_by"] == "goal_selection"
    assert [step["id"] for step in compact["guided_transaction"]["ordered_steps"]] == [
        "inspect_connection",
        "select_goal",
    ]
    assert _host_shadow_document(compact) == _host_shadow_document(detailed)


def test_cli_without_host_returns_read_only_host_selection_gate(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--format",
                "json",
                "start-goal",
                "--guided",
                "--project",
                str(project),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--goal-text",
                GOAL_TEXT,
            ]
        )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["guided_transaction"]["blocked_by"] == "host_surface_selection"
    assert payload["safety_contract"]["writes_registry"] is False
    choices = payload["host_surface_selection_gate"]["choices"]
    assert [choice["host_surface"] for choice in choices] == [
        "codex-app",
        "codex-ide-plugin",
        "codex-cli-tui",
        "claude-code",
        "opencode",
        "shell",
    ]
    ide = next(choice for choice in choices if choice["host_surface"] == "codex-ide-plugin")
    assert "--host-surface codex-ide-plugin" in ide["rerun_command"]


def test_codex_ide_plugin_uses_visible_goal_and_preserves_compact_parity(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    common = {
        "project": project,
        "goal_id": GOAL_ID,
        "agent_id": AGENT_ID,
        "cli_bin": "loopx",
        "host_surface": "codex-ide-plugin",
        "goal_text": GOAL_TEXT,
        "available_capabilities": ["network"],
    }
    compact = build_start_goal_guided_packet(
        **common,
        include_command_pack_detail=False,
    )
    detailed = build_start_goal_guided_packet(
        **common,
        include_command_pack_detail=True,
    )

    activation = compact["command_pack"]["host_loop_activation"]
    assert detailed["command_pack"]["agent_type"] == "codex-ide-plugin"
    assert activation["host_surface"] == "codex_ide_visible_goal_mode"
    assert activation["activation_method"] == "set_visible_goal"
    assert activation["host_mutation"]["host_command"] == "/goal <task_body>"
    assert _host_shadow_document(compact) == _host_shadow_document(detailed)

    legacy = build_start_goal_guided_packet(
        **{**common, "host_surface": "codex-ide"},
        include_command_pack_detail=True,
    )
    assert legacy["command_pack"]["agent_type"] == "codex-ide-plugin"
    assert legacy["command_pack"]["host_loop_activation"]["host_surface"] == (
        "codex_ide_visible_goal_mode"
    )
