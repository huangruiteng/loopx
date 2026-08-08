from __future__ import annotations

import contextlib
import io
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from loopx.bootstrap_command_pack import (
    GUIDED_COMMAND_PACK_PROJECTION_SCHEMA_VERSION,
    build_loopx_bootstrap_command_pack,
    build_start_goal_guided_packet,
    render_start_goal_guided_markdown,
)
from loopx.capabilities.issue_fix.candidate_preflight import (
    build_issue_fix_candidate_preflight_packet,
    candidate_preflight_input_contract,
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
        "command_cwd_source": transaction["command_cwd_source"],
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
    assert compact["guided_transaction"]["ordered_steps"][-1]["id"] == (
        "scheduler_ack_when_needed"
    )

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


def test_issue_fix_goal_projects_capability_guard_without_todo_fields(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        host_surface="ark-managed-agent",
        goal_text=(
            "Autonomously deliver review-ready fixes for two distinct open "
            "repository issues in one long-running Goal."
        ),
        available_capabilities=["network"],
        capability_route="issue-fix",
    )

    transaction = payload["guided_transaction"]
    assert transaction["command_cwd_source"] == "#/project"
    assert payload["project"] == str(project)
    route = transaction["selected_capability_route"]
    assert route == {
        "schema_version": "loopx_goal_capability_route_v0",
        "capability_id": "issue-fix",
        "selection_source": "explicit_capability_route",
        "selection_reason_code": "capability_route_enabled",
        "entry_command_key": "issue_fix_workflow_plan_template",
        "admission_command_key": "issue_fix_feasibility_template",
        "candidate_authority": "public_open_tracker_issue",
        "authority_refresh_required": "current issue body and latest comments",
        "candidate_preflight": candidate_preflight_input_contract(),
        "implementation_admission": {
            "status": "qualification_required",
            "state_owner": "issue_fix",
            "route_scope": "start_goal_bootstrap_only",
            "candidate_receipt_stream": "candidate-preflight",
            "feasibility_required_for_route": "proceed",
            "durable_execution_binding": {
                "schema_version": "capability_execution_binding_v0",
                "capability_id": "issue-fix",
                "todo_binding_ref_field": "capability_binding_ref",
                "authority_source": "admission_result.capability_execution_binding",
                "authority_stream": "feasibility",
                "authority_packet_schema_version": "issue_fix_feasibility_v0",
                "bound_todo_fields": ["action_kind", "target_key"],
                "legacy_unbound_todo_fallback": {
                    "authority": "current_feasibility_row",
                    "match": "exact_action_kind_and_target_key",
                    "prefix_match_allowed": False,
                },
            },
        },
        "activation_condition": (
            "after selecting a public issue candidate and before substantive "
            "implementation"
        ),
    }
    guard = transaction["ordered_steps"][2]
    assert guard["id"] == "qualify_selected_capability"
    assert guard["candidate_discovery_command_template"].startswith(
        "gh issue list "
    )
    assert guard["command_source"].endswith(
        "/commands/issue_fix_workflow_plan_template"
    )
    assert guard["admission_command_source"].endswith(
        "/commands/issue_fix_feasibility_template"
    )
    assert guard["durable_successor_sources"] == {
        "proceed": "admission_result.transition.projected_todo",
        "non_proceed": "entry_result.ordered_loopx_todo_writeback_preview",
    }
    assert "for non-proceed" in guard["completion_condition"]
    assert "command_template" not in guard
    assert "admission_command_template" not in guard
    commands = payload["command_pack"]["commands"]
    assert commands[route["entry_command_key"]].startswith(
        "loopx issue-fix workflow-plan "
    )
    assert "--fetch-candidate-evidence" in commands[
        route["entry_command_key"]
    ]
    assert f"--goal-id {GOAL_ID}" in commands[route["entry_command_key"]]
    assert "--capability-route issue-fix" in payload["command_pack"][
        "canonical_cli_command"
    ]
    assert guard["candidate_preflight"]["required_before_implementation"] is True
    assert commands[route["admission_command_key"]].startswith(
        "loopx issue-fix feasibility "
    )
    rendered = render_start_goal_guided_markdown(payload)
    assert "authority: open public issue; source clues are evidence only" in rendered
    assert "discover: `gh issue list " in rendered
    assert (
        "numeric_pr_evidence + semantic_pr_evidence + "
        "maintainer_comment_evidence"
    ) in rendered
    assert "only admitted proceed may start a new implementation" in rendered
    assert "loopx issue-fix workflow-plan " in rendered
    assert "loopx issue-fix feasibility " in rendered
    assert "proceed: `loopx issue-fix feasibility " in rendered
    assert len(rendered.replace(str(project), "<project>")) <= 3_600
    todo_command = next(
        step["command_template"]
        for step in transaction["ordered_steps"]
        if step["id"] == "write_ordered_todos"
    )
    assert "--project ." in todo_command
    assert "--action-kind <action_kind>" in todo_command
    assert "[--target-key <target_key>]" in todo_command
    refresh_command = next(
        step["command"]
        for step in transaction["ordered_steps"]
        if step["id"] == "refresh_state"
    )
    assert "--project ." in refresh_command
    assert all(
        field not in todo_command
        for field in ("issue_url", "issue_number", "base_sha", "acceptance")
    )


def test_configured_candidate_preflight_requires_prior_work_evidence() -> None:
    try:
        build_issue_fix_candidate_preflight_packet(
            repo="volcengine/OpenViking",
            issue_ref="#3005",
            input_payload={
                "schema_version": "issue_fix_candidate_preflight_input_v0",
                "semantic_pr_evidence": [],
            },
            generated_at="2026-07-30T00:00:00Z",
        )
    except ValueError as error:
        assert "numeric_pr_evidence" in str(error)
    else:
        raise AssertionError("configured preflight must require prior-work evidence")


def test_candidate_preflight_rejects_unqualified_negative_evidence() -> None:
    def receipt(query_scope: str) -> dict[str, Any]:
        return {
            "repo": "volcengine/OpenViking",
            "issue_ref": "#3005",
            "query_scope": query_scope,
            "complete": True,
            "truncated": False,
            "rows": [],
        }

    complete = {
        "schema_version": "issue_fix_candidate_preflight_input_v0",
        "numeric_pr_evidence": receipt("issue_specific_all_states"),
        "semantic_pr_evidence": receipt("issue_specific_current_revision"),
        "maintainer_comment_evidence": receipt(
            "issue_specific_comment_metadata"
        ),
    }
    packet = build_issue_fix_candidate_preflight_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        input_payload=complete,
        generated_at="2026-07-30T00:00:00Z",
    )
    assert packet["decision"]["route"] == "proceed"
    assert packet["input_contract"] == candidate_preflight_input_contract()

    missing_comment_evidence = dict(complete)
    missing_comment_evidence.pop("maintainer_comment_evidence")
    try:
        build_issue_fix_candidate_preflight_packet(
            repo="volcengine/OpenViking",
            issue_ref="#3005",
            input_payload=missing_comment_evidence,
            generated_at="2026-07-30T00:00:00Z",
        )
    except ValueError as error:
        assert "maintainer_comment_evidence" in str(error)
    else:
        raise AssertionError("missing comment evidence must not admit a candidate")

    invalid_inputs = [
        {
            **complete,
            "numeric_pr_evidence": {
                **complete["numeric_pr_evidence"],
                "truncated": True,
            },
        },
        {
            **complete,
            "semantic_pr_evidence": {
                **complete["semantic_pr_evidence"],
                "query_scope": "aggregate_recent_pull_requests",
            },
        },
    ]
    for payload in invalid_inputs:
        try:
            build_issue_fix_candidate_preflight_packet(
                repo="volcengine/OpenViking",
                issue_ref="#3005",
                input_payload=payload,
                generated_at="2026-07-30T00:00:00Z",
            )
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError("unqualified negative evidence must fail closed")

    try:
        build_issue_fix_candidate_preflight_packet(
            repo="volcengine/OpenViking",
            issue_ref="#3005",
            input_payload={**complete, "numeric_pr_evidence": []},
            generated_at="2026-07-30T00:00:00Z",
        )
    except TypeError as error:
        assert "one evidence receipt object, not a list" in str(error)
        assert "issue_specific_all_states" in str(error)
    else:
        raise AssertionError("receipt lists must fail with an actionable error")


def test_candidate_preflight_contract_describes_receipt_shapes() -> None:
    contract = candidate_preflight_input_contract()
    receipts = contract["evidence_receipts"]

    assert {
        field: receipt["query_scope"] for field, receipt in receipts.items()
    } == {
        "numeric_pr_evidence": "issue_specific_all_states",
        "semantic_pr_evidence": "issue_specific_current_revision",
        "maintainer_comment_evidence": "issue_specific_comment_metadata",
    }
    for receipt in receipts.values():
        assert receipt["cardinality"] == "one_receipt_object"
        assert receipt["required_fields"] == [
            "repo",
            "issue_ref",
            "query_scope",
            "complete",
            "truncated",
            "rows",
        ]
        assert (
            receipt["negative_result_rule"]
            == "rows may be empty only when complete=true and truncated=false"
        )


def test_goal_text_never_selects_capability_route_without_switch(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    for goal_text in (
        "Improve the public onboarding documentation.",
        "Fix https://github.com/owner/repo/pull/42.",
        "Fix: https://github.com/owner/repo/issues/42.",
        "Review https://github.com/owner/repo/pull/42.",
        "Merge https://github.com/owner/repo/pull/42 after checks pass.",
        "Monitor https://github.com/owner/repo/pull/42.",
        "Summarize https://github.com/owner/repo/issues/42.",
        (
            "Run one long-lived engineering Goal: keep generic fixes separate "
            "from adapter changes, keep feature MR count small, and verify one "
            "real PR lifecycle transition."
        ),
        "Fix generic tests and follow the PR lifecycle.",
        "Resolve generic test failures\nTrack the PR lifecycle.",
        "Repair the adapter, then verify its pull request lifecycle.",
        "Use issue-fix to resolve the repository issue.",
    ):
        payload = build_start_goal_guided_packet(
            project=project,
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
            cli_bin="loopx",
            host_surface="ark-managed-agent",
            goal_text=goal_text,
            available_capabilities=["network", "issue-fix"],
        )
        transaction = payload["guided_transaction"]
        assert "selected_capability_route" not in transaction
        assert transaction["ordered_steps"][-1]["id"] == "quota_guard"
        assert (
            payload["command_pack"]["goal_start_contract"]
            ["selected_capability_route"]
            is None
        )

    explicit_route = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        host_surface="ark-managed-agent",
        goal_text="Improve the public onboarding documentation.",
        capability_route="issue-fix",
    )
    route = explicit_route["guided_transaction"]["selected_capability_route"]
    assert route["selection_source"] == "explicit_capability_route"
    assert route["selection_reason_code"] == "capability_route_enabled"


def test_explicit_capability_route_survives_compact_detail_readback(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    compact = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        host_surface="ark-managed-agent",
        goal_text=GOAL_TEXT,
        capability_route="issue-fix",
    )

    detail_command = compact["command_pack"]["detail_command"]
    assert "--capability-route issue-fix" in detail_command
    restored = _invoke_detail_command(detail_command)
    assert (
        restored["guided_transaction"]["selected_capability_route"]
        == compact["guided_transaction"]["selected_capability_route"]
    )


def test_bootstrap_message_does_not_reintroduce_semantic_route_selection(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    common = {
        "project": project,
        "goal_id": GOAL_ID,
        "agent_id": AGENT_ID,
        "cli_bin": "loopx",
        "host_surface": "ark-managed-agent",
        "goal_text": "Fix https://github.com/owner/repo/issues/42.",
    }

    plain = build_loopx_bootstrap_command_pack(**common)
    routed = build_loopx_bootstrap_command_pack(
        **common,
        capability_route="issue-fix",
    )

    marker = "The explicit capability route selects issue-fix."
    assert marker not in plain["message"]
    assert marker in routed["message"]


def test_explicit_cold_path_restores_the_complete_command_pack(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
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
    gate = compact["guided_transaction"]["identity_selection_gate"]
    assert gate["default_action"] == "select_agent_identity"
    assert gate["fresh_agent_registration"] is None
    assert all(
        choice["mode"] == "takeover_existing_agent"
        and choice["requires_explicit_takeover_intent"] is True
        and f"--agent-id {choice['agent_id']}" in choice["rerun_start_goal_command"]
        for choice in gate["choices"]
    )
    assert [
        step["id"] for step in compact["guided_transaction"]["ordered_steps"][:3]
    ] == ["inspect_connection", "connect_if_needed", "select_agent_identity"]
    assert _host_shadow_document(compact) == _host_shadow_document(detailed)


def test_start_goal_reuses_bound_thread_agent_and_scopes_commands(tmp_path: Path) -> None:
    project = _write_connected_project(tmp_path)
    registry_path = project / ".loopx" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["registered_agents"].append("codex-guided-peer")
    registry["goals"][0]["coordination"]["thread_agent_bindings"] = [
        {"thread_id": "thread-a", "host_surface": "codex-app", "agent_id": AGENT_ID}
    ]
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=None,
        thread_id="thread-a",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    assert payload["agent_id"] == AGENT_ID
    assert payload["thread_agent_binding"]["status"] == "bound"
    assert payload["guided_transaction"].get("blocked_by") is None
    commands = payload["command_pack"]["commands"]
    assert f"--agent-id {AGENT_ID}" in commands["goal_start_quota_should_run"]
    assert f"--agent-id {AGENT_ID}" in commands["goal_start_refresh_state"]
    assert commands["goal_start_bind_thread"] is None
    assert "bind_thread_identity" not in {
        step["id"] for step in payload["guided_transaction"]["ordered_steps"]
    }
    assert f"--agent-id {AGENT_ID}" in payload["guided_transaction"]["ordered_steps"][3]["command_template"]

    explicit_override = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id="codex-guided-peer",
        thread_id="thread-a",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )
    assert explicit_override["agent_id"] == "codex-guided-peer"
    assert explicit_override["command_pack"]["commands"]["goal_start_bind_thread"] is None


def test_cli_codex_app_reuses_ambient_thread_binding(
    tmp_path: Path, monkeypatch
) -> None:
    project = _write_connected_project(tmp_path)
    registry_path = project / ".loopx" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["thread_agent_bindings"] = [
        {"thread_id": "thread-ambient", "host_surface": "codex-app", "agent_id": AGENT_ID}
    ]
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-ambient")

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
                "--host-surface",
                "codex-app",
                "--goal-text",
                GOAL_TEXT,
            ]
        )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["thread_id"] == "thread-ambient"
    assert payload["agent_id"] == AGENT_ID
    assert payload["thread_agent_binding"]["status"] == "bound"
    assert payload["guided_transaction"].get("blocked_by") is None


def test_start_goal_binds_selected_lane_before_todo_writeback(
    tmp_path: Path, monkeypatch
) -> None:
    project = _write_connected_project(tmp_path)
    source_registry = project / ".loopx" / "registry.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    source_payload = json.loads(source_registry.read_text(encoding="utf-8"))
    global_payload = {
        **source_payload,
        "registry_role": "global-local",
    }
    global_payload["goals"][0]["source_registry"] = str(source_registry)
    (runtime / "registry.global.json").write_text(
        json.dumps(global_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOOPX_RUNTIME_ROOT", str(runtime))

    first = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        thread_id="thread-first-selection",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    ordered_steps = first["guided_transaction"]["ordered_steps"]
    assert [step["id"] for step in ordered_steps[:4]] == [
        "inspect_connection",
        "connect_if_needed",
        "bind_thread_identity",
        "plan_ranked_todos",
    ]
    bind_step = ordered_steps[2]
    assert bind_step["must_stop_on_failure"] is True
    assert bind_step["result_contract"]["required_result"] == {
        "ok": True,
        "global_sync": {"ok": True},
        "registration_readback": {"verified": True},
    }

    output = io.StringIO()
    bind_argv = shlex.split(bind_step["command"])
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(["--runtime-root", str(runtime), *bind_argv[1:]])
    assert exit_code == 0, output.getvalue()

    second = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=None,
        thread_id="thread-first-selection",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text="continue the same task",
        available_capabilities=["network"],
    )
    assert second["agent_id"] == AGENT_ID
    assert second["thread_agent_binding"]["status"] == "bound"
    assert second["command_pack"]["commands"]["goal_start_bind_thread"] is None
    assert "bind_thread_identity" not in {
        step["id"] for step in second["guided_transaction"]["ordered_steps"]
    }


def test_start_goal_with_unbound_thread_defaults_to_fresh_registration(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    registry_path = project / ".loopx" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["registered_agents"].append("codex-guided-peer")
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=None,
        thread_id="thread-new",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    gate = payload["guided_transaction"]["identity_selection_gate"]
    assert payload["guided_transaction"]["blocked_by"] == "agent_identity_selection"
    assert gate["state"] == "fresh_agent_registration_required"
    assert gate["default_action"] == "register_fresh_agent"
    assert gate["fresh_agent_registration"]["recommended"] is True
    assert all(
        choice["requires_explicit_takeover_intent"] is True
        for choice in gate["choices"]
    )


def test_start_goal_unbound_thread_does_not_reuse_the_only_registered_agent(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)

    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=None,
        thread_id="thread-unbound",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    assert payload["agent_id"] is None
    assert payload["guided_transaction"]["blocked_by"] == "agent_identity_selection"
    gate = payload["guided_transaction"]["identity_selection_gate"]
    assert gate["state"] == "fresh_agent_registration_required"
    assert gate["default_action"] == "register_fresh_agent"
    assert gate["fresh_agent_registration"]["recommended"] is True


def test_start_goal_without_thread_id_requires_explicit_lane_selection(tmp_path: Path) -> None:
    project = _write_connected_project(tmp_path)

    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=None,
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    assert payload["agent_id"] is None
    assert payload["guided_transaction"]["blocked_by"] == "agent_identity_selection"
    gate = payload["guided_transaction"]["identity_selection_gate"]
    assert gate["default_action"] == "select_agent_identity"
    assert gate["fresh_agent_registration"] is None
    assert gate["choices"][0]["agent_id"] == AGENT_ID
    assert gate["choices"][0]["requires_explicit_takeover_intent"] is True


def test_cli_codex_app_unbound_ambient_thread_defaults_to_fresh_registration(
    tmp_path: Path, monkeypatch
) -> None:
    project = _write_connected_project(tmp_path)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-new-session")

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
                "--host-surface",
                "codex-app",
                "--goal-text",
                GOAL_TEXT,
            ]
        )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["thread_id"] == "thread-new-session"
    assert payload["agent_id"] is None
    gate = payload["guided_transaction"]["identity_selection_gate"]
    assert gate["state"] == "fresh_agent_registration_required"
    assert gate["default_action"] == "register_fresh_agent"
    assert gate["fresh_agent_registration"]["recommended"] is True


def test_start_goal_new_peer_explicitly_allows_fresh_registration(tmp_path: Path) -> None:
    project = _write_connected_project(tmp_path)

    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=None,
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text=GOAL_TEXT,
        new_peer=True,
        available_capabilities=["network"],
    )

    gate = payload["guided_transaction"]["identity_selection_gate"]
    assert gate["default_action"] == "register_fresh_agent"
    assert gate["fresh_agent_registration"]["recommended"] is True


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
        "capability_route": "issue-fix",
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
    for choice in compact["goal_selection_gate"]["choices"]:
        assert "--capability-route issue-fix" in choice["rerun_command"]
    assert "--capability-route issue-fix" in compact["command_pack"][
        "detail_command"
    ]


def test_start_goal_keeps_the_requested_linked_worktree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    subprocess.run(["git", "init"], cwd=primary, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "loopx@example.invalid"],
        cwd=primary,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "LoopX Test"],
        cwd=primary,
        check=True,
        capture_output=True,
    )
    (primary / "README.md").write_text("# primary\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=primary, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=primary,
        check=True,
        capture_output=True,
    )

    worktree = tmp_path / "fresh-worktree"
    subprocess.run(
        ["git", "worktree", "add", "-b", "fresh-worktree", str(worktree)],
        cwd=primary,
        check=True,
        capture_output=True,
    )

    old_goal_id = "old-primary-goal"
    primary_registry = primary / ".loopx" / "registry.json"
    primary_registry.parent.mkdir(parents=True)
    old_goal = {
        "id": old_goal_id,
        "status": "active",
        "repo": str(primary),
        "state_file": f".codex/goals/{old_goal_id}/ACTIVE_GOAL_STATE.md",
    }
    primary_registry.write_text(
        json.dumps({"schema_version": "0.1", "goals": [old_goal]}, indent=2) + "\n",
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "registry.global.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "goals": [
                    {
                        **old_goal,
                        "source_registry": str(primary_registry),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOOPX_RUNTIME_ROOT", str(runtime))

    payload = build_start_goal_guided_packet(
        project=worktree,
        goal_id=None,
        agent_id=None,
        cli_bin="loopx",
        host_surface="ark-managed-agent",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    assert Path(payload["project"]).resolve() == worktree.resolve()
    assert payload["goal_id"] == "fresh-worktree-goal"
    alias = payload["project_connection"]["canonical_project_alias"]
    assert alias["applied"] is False
    assert alias["kind"] == "exact_project_route"
    connect_command = payload["command_pack"]["commands"][
        "goal_start_connect_if_needed"
    ]
    assert str(worktree.resolve()) in connect_command
    assert old_goal_id not in json.dumps(payload)


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
                "--capability-route",
                "issue-fix",
            ]
        )

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload["guided_transaction"]["blocked_by"] == "host_surface_selection"
    assert payload["safety_contract"]["writes_registry"] is False
    choices = payload["host_surface_selection_gate"]["choices"]
    assert [choice["host_surface"] for choice in choices] == [
        "codex-app",
        "codex-app-ssh",
        "codex-ide-plugin",
        "codex-cli-tui",
        "claude-code",
        "opencode",
        "traex-cli",
        "pi",
        "gemini-cli",
        "cursor-agent",
        "ark-managed-agent",
        "shell",
        "other-agent",
    ]
    ide = next(choice for choice in choices if choice["host_surface"] == "codex-ide-plugin")
    assert "--host-surface codex-ide-plugin" in ide["rerun_command"]
    assert "--capability-route issue-fix" in ide["rerun_command"]


def test_ark_managed_agent_plans_todos_before_one_shot_goal_activation(
    tmp_path: Path,
) -> None:
    project = _write_connected_project(tmp_path)
    payload = build_start_goal_guided_packet(
        project=project,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        host_surface="ark-managed-agent",
        goal_text=GOAL_TEXT,
        available_capabilities=["network"],
    )

    ordered_step_ids = [
        step["id"] for step in payload["guided_transaction"]["ordered_steps"]
    ]
    activation = payload["command_pack"]["host_loop_activation"]
    inspect_step = payload["guided_transaction"]["ordered_steps"][0]
    connect_step = payload["guided_transaction"]["ordered_steps"][1]

    assert ordered_step_ids.index("write_ordered_todos") < ordered_step_ids.index(
        "activate_host_loop"
    )
    assert inspect_step["command_source"] == "#/command_pack/canonical_cli_command"
    inspect_command = payload["command_pack"]["canonical_cli_command"]
    assert "--host-surface ark-managed-agent" in inspect_command
    assert "--available-capability network" in inspect_command
    assert f"--goal-text '{GOAL_TEXT}'" in inspect_command
    connect_command = connect_step["command"]
    assert "\n" in connect_command
    assert f"--objective {shlex.quote(GOAL_TEXT)}" in connect_command
    actionable_connect_command = (
        f"cd {shlex.quote(str(project))} && loopx bootstrap"
        " --project ."
        f" --goal-id {GOAL_ID}"
        f" --objective {shlex.quote(GOAL_TEXT)}"
        " --adapter-kind read_only_project_map_v0"
        " --adapter-status connected-read-only"
        " --no-onboarding-scan"
        " --codex-app-heartbeat ask"
    )
    assert actionable_connect_command in payload["message"]
    assert "preview the issue-fix route before todo writeback" not in payload["message"]
    assert activation["agent_type"] == "ark-managed-agent"
    assert activation["host_surface"] == "ark_managed_agent_goal_mode"
    assert activation["activation_method"] == "submit_goal_once"
    assert activation["host_mutation"]["transport_contract"] == "goal_prompt_v0"
    assert activation["host_mutation"]["prompt_field"] == "task_body"
    assert "--runtime-profile ark_managed_agent_goal" in (
        activation["commands"]["heartbeat_prompt"]
    )


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
