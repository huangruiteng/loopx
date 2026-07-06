#!/usr/bin/env python3
"""Smoke-test the Lark Kanban control-plane adapter."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.sinks.lark.kanban import (  # noqa: E402
    CLAIM_UNCLAIMED,
    STATUS_CLAIMED,
    STATUS_DONE,
    STATUS_USER_GATE,
    STATUS_REVIEW,
    STATUS_TODO,
    LarkKanbanConfig,
    _lark_record_from_todo_block,
    build_create_board_plan,
    default_lark_kanban_config_path,
    lark_kanban_feasibility_cases,
    lark_kanban_heartbeat,
    lark_kanban_operator_card_fields,
    lark_kanban_schema_payload,
    lark_kanban_ux_task,
    read_lark_kanban_local_config,
    seed_lark_kanban_records,
    setup_lark_kanban_board,
    sync_loopx_projection_to_lark_kanban,
    sync_loopx_todos_to_lark_kanban,
    use_lark_kanban_board,
)


def fixture_payload() -> dict[str, object]:
    fields = [
        "Task",
        "Status",
        "Claim",
        "Claimed By",
        "Priority",
        "Task Class",
        "Action Kind",
        "LoopX Goal ID",
        "LoopX Todo ID",
        "Scope",
        "User Gate",
        "Handoff",
        "Evidence",
        "Run History",
        "Worker Command",
        "Workdir",
        "Last Error",
        "Last Result Code",
        "Last Heartbeat",
    ]
    row = [
        "POC: produce compact public evidence",
        [STATUS_TODO],
        [CLAIM_UNCLAIMED],
        None,
        ["P1"],
        ["advancement_task"],
        "analyze",
        "loopx-lark-kanban-poc",
        "todo_public_poc",
        "public fixture only",
        None,
        "Worker should produce compact evidence and handoff.",
        None,
        "",
        "python3 -c 'print(\"evidence: public fixture worker completed\")'",
        str(REPO_ROOT),
        None,
        None,
        None,
    ]
    return {
        "ok": True,
        "data": {
            "fields": fields,
            "data": [row],
            "record_id_list": ["recFixture001"],
            "has_more": False,
        },
    }


def fake_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
    assert args[0] == "python3", args
    assert cwd == REPO_ROOT, cwd
    assert timeout == 600.0, timeout
    return {
        "returncode": 0,
        "stdout": "evidence: public fixture worker completed\n",
        "stderr": "",
        "timed_out": False,
    }


def partial_setup_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
    if args == ["lark-cli", "--version"]:
        return {"returncode": 0, "stdout": "lark-cli 1.0.56\n", "stderr": "", "timed_out": False}
    if args == ["lark-cli", "auth", "status"]:
        return {
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "identities": {"user": {"available": True}}}),
            "stderr": "",
            "timed_out": False,
        }
    if args[-1:] == ["--help"]:
        return {"returncode": 0, "stdout": "help\n", "stderr": "", "timed_out": False}
    if "+base-create" in args:
        return {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "ok": True,
                    "data": {
                        "base_token": "base_live_fixture",
                        "table_id": "tbl_live_fixture",
                    },
                }
            ),
            "stderr": "",
            "timed_out": False,
        }
    if "+view-list" in args:
        return {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "ok": True,
                    "data": [
                        {"name": "Worker Queue", "view_id": "vew_worker_fixture"},
                        {"name": "User Gates", "view_id": "vew_user_fixture"},
                        {"name": "Kanban", "view_id": "vew_kanban_fixture"},
                    ],
                }
            ),
            "stderr": "",
            "timed_out": False,
        }
    if "+view-set-visible-fields" in args:
        return {
            "returncode": 1,
            "stdout": json.dumps({"ok": False, "error": {"message": "visible fields denied"}}),
            "stderr": "",
            "timed_out": False,
        }
    return {"returncode": 0, "stdout": json.dumps({"ok": True}), "stderr": "", "timed_out": False}


def run_cli(*extra_args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    schema = lark_kanban_schema_payload()
    assert schema["ok"] is True, schema
    assert schema["schema_version"] == "loopx_lark_kanban_control_plane_v0", schema
    assert schema["source_of_truth"] == "loopx_todos_projected_to_lark_base", schema
    assert schema["adapter_role"] == "status_tracker_claim_surface", schema
    assert schema["task_spawning_model"]["board_creates_tasks"] is False, schema
    assert "LoopX todo lifecycle" in schema["task_spawning_model"]["rule"], schema
    field_names = [field["name"] for field in schema["fields"]]
    for expected in ["Task", "Status", "Claim", "Handoff", "Evidence", "Run History", "Worker Command"]:
        assert expected in field_names, field_names
    assert schema["heartbeat_model"]["fallback"].startswith("agent heartbeat"), schema
    assert schema["operator_view"]["kanban_card_fields"] == lark_kanban_operator_card_fields(), schema
    assert lark_kanban_operator_card_fields() == [
        "Task",
        "Claim",
        "Priority",
        "User Gate",
        "Evidence",
        "Status",
    ]

    plan = build_create_board_plan(
        base_name="LoopX Lark Kanban Control Plane POC",
        table_name="LoopX Control Plane",
        **{"base_" + "token": "base_public_fixture"},
        user_open_id="ou_public_fixture",
    )
    joined = [" ".join(command) for command in plan]
    assert any("+table-create" in command for command in joined), joined
    assert any("permission.members" in command for command in joined), joined
    assert any("+view-set-group" in command and "Kanban" in command for command in joined), joined
    assert any("group_config" in command for command in joined), joined
    assert any("+view-set-visible-fields" in command for command in joined), joined

    heartbeat = lark_kanban_heartbeat(
        LarkKanbanConfig(
            **{"base_" + "token": "base_public_fixture"},
            table_id="tbl_public_fixture",
            view_id="Worker Queue",
        ),
        fixture=fixture_payload(),
        agent_id="codex-kanban-worker",
        execute_lark=False,
        execute_worker=True,
        allowed_command_prefixes=["python3"],
        runner=fake_runner,
    )
    assert heartbeat["ok"] is True, heartbeat
    assert heartbeat["decision"] == "task_processed", heartbeat
    assert heartbeat["selected_record_id"] == "recFixture001", heartbeat
    assert heartbeat["worker"]["executed"] is True, heartbeat
    assert heartbeat["final_status"] == STATUS_REVIEW, heartbeat
    assert "evidence: public fixture worker completed" in heartbeat["writeback"]["Evidence"], heartbeat
    assert heartbeat["writeback"]["Claimed By"] == "codex-kanban-worker", heartbeat
    assert len(heartbeat["commands"]) == 2, heartbeat
    assert all(command["executed"] is False for command in heartbeat["commands"]), heartbeat

    records = [lark_kanban_ux_task()] + lark_kanban_feasibility_cases()
    assert len(records) == 5, records
    assert records[0]["Status"] == "User Gate", records[0]
    assert any("notes.zaynjarvis.com" in item["Task"] for item in records), records
    seeded = seed_lark_kanban_records(
        LarkKanbanConfig(
            **{"base_" + "token": "base_public_fixture"},
            table_id="tbl_public_fixture",
        ),
        records=records,
        execute=False,
    )
    assert seeded["ok"] is True, seeded
    assert seeded["record_count"] == 5, seeded
    assert all(item["command"]["executed"] is False for item in seeded["records"]), seeded

    with tempfile.TemporaryDirectory(prefix="loopx-lark-kanban-smoke-") as tmp:
        fixture = Path(tmp) / "record-list.json"
        fixture.write_text(json.dumps(fixture_payload()), encoding="utf-8")
        config_path = Path(tmp) / ".loopx" / "lark-kanban.json"
        use_payload = use_lark_kanban_board(
            config_path=config_path,
            base_url="https://example.invalid/base/base_public_fixture?table=tbl_public_fixture&view=vew_public_fixture",
            cli_bin="lark-cli",
            identity="user",
        )
        assert use_payload["ok"] is True, use_payload
        stored = read_lark_kanban_local_config(config_path)
        assert stored["board"]["base_token"] == "base_public_fixture", stored
        assert stored["board"]["table_id"] == "tbl_public_fixture", stored
        cli = run_cli(
            "lark-kanban",
            "heartbeat",
            "--config-path",
            str(config_path),
            "--fixture",
            str(fixture),
            "--agent-id",
            "codex-kanban-worker",
        )
    assert cli["ok"] is True, cli
    assert cli["decision"] == "task_processed", cli
    assert cli["worker"]["executed"] is False, cli
    assert cli["final_status"] == "Claimed", cli

    case_cli = run_cli(
        "lark-kanban",
        "seed-cases",
        "--base-token",
        "base_public_fixture",
        "--table-id",
        "tbl_public_fixture",
    )
    assert case_cli["ok"] is True, case_cli
    assert case_cli["execute"] is False, case_cli
    assert case_cli["record_count"] == 5, case_cli
    assert case_cli["operator_card_fields"] == lark_kanban_operator_card_fields(), case_cli

    with tempfile.TemporaryDirectory(prefix="loopx-lark-kanban-partial-") as tmp:
        config_path = Path(tmp) / ".loopx" / "lark-kanban.json"
        setup_payload = setup_lark_kanban_board(
            config_path=config_path,
            base_name="LoopX Partial Setup Fixture",
            cli_bin="lark-cli",
            identity="user",
            execute=True,
            runner=partial_setup_runner,
        )
        assert setup_payload["ok"] is True, setup_payload
        assert setup_payload["partial"] is True, setup_payload
        assert setup_payload["enrichment_ok"] is False, setup_payload
        assert setup_payload["enrichment_error"] == "visible fields denied", setup_payload
        stored = read_lark_kanban_local_config(config_path)
        assert stored["exists"] is True, stored
        assert stored["board"]["base_token"] == "base_live_fixture", stored
        assert stored["board"]["table_id"] == "tbl_live_fixture", stored
        assert stored["board"]["view_ids"]["Kanban"] == "vew_kanban_fixture", stored
        assert setup_payload["config"]["board"]["table_id"] == "tbl_live_fixture", setup_payload

    with tempfile.TemporaryDirectory(prefix="loopx-lark-kanban-sync-") as tmp:
        root = Path(tmp)
        registry = root / ".loopx" / "registry.json"
        registry.parent.mkdir(parents=True)
        state = root / "active-state.md"
        state.write_text(
            "\n".join(
                [
                    "---",
                    "updated_at: 2026-06-23T00:00:00+00:00",
                    "---",
                    "",
                    "## User Todo / Owner Review Reading Queue",
                    "",
                    "- [ ] [P1] Approve LoopX board sharing",
                    "  <!-- loopx: todo_id=todo_user_share status=open task_class=user_gate action_kind=decide blocks_agent=codex-main-control -->",
                    "",
                    "## Agent Todo",
                    "",
                    "- [ ] [P2] Wire conservative board sync",
                    "  <!-- loopx: todo_id=todo_agent_sync status=open task_class=advancement_task action_kind=sync_board required_write_scopes=loopx claimed_by=codex-main-control -->",
                    "- [ ] [P1] Product capability scoped board sync",
                    "  <!-- loopx: todo_id=todo_product_scope status=open task_class=advancement_task action_kind=sync_board claimed_by=codex-product-capability -->",
                    "",
                    "- [ ] [P1] Keep malformed metadata executable",
                    "  <!-- loopx: todo_id=todo_agent_malformed status=blocked_typo task_class=user_gate_typo action_kind=sync_board claimed_by=codex-main-control -->",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        registry.write_text(
            json.dumps(
                {
                    "goals": [
                        {
                            "id": "goal_lark_sync_fixture",
                            "repo": str(root),
                            "state_file": "active-state.md",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        sync_payload = sync_loopx_todos_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            registry_path=registry,
            goal_id="goal_lark_sync_fixture",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        assert sync_payload["ok"] is True, sync_payload
        assert sync_payload["todo_count"] == 4, sync_payload
        assert any(item["values"]["Status"] == "User Gate" for item in sync_payload["records"]), sync_payload
        malformed = next(
            item for item in sync_payload["records"] if item["todo_id"] == "todo_agent_malformed"
        )
        assert malformed["values"]["Status"] == STATUS_CLAIMED, malformed
        assert malformed["values"]["Task Class"] == "advancement_task", malformed
        assert malformed["values"]["Run History"].endswith("status=open"), malformed
        assert all(item["values"]["Workdir"] == "" for item in sync_payload["records"]), sync_payload
        assert str(root) not in json.dumps(sync_payload["records"], ensure_ascii=False), sync_payload
        assert all(item["command"]["executed"] is False for item in sync_payload["records"]), sync_payload
        scoped_payload = sync_loopx_todos_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            registry_path=registry,
            goal_id="goal_lark_sync_fixture",
            agent_id="codex-main-control",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        scoped_todo_ids = {item["todo_id"] for item in scoped_payload["records"]}
        assert scoped_payload["todo_count"] == 3, scoped_payload
        assert scoped_todo_ids == {
            "todo_user_share",
            "todo_agent_sync",
            "todo_agent_malformed",
        }, scoped_payload

        projection_payload = {
            "schema_version": "goal_channel_projection_v0",
            "goal_id": "goal_lark_sync_fixture",
            "source_id": "frontstage-smoke",
            "agent_identity": {"agent_id": "codex-main-control"},
            "user_todos": [
                {
                    "todo_id": "todo_projection_gate",
                    "title": "[P1] Approve projection sink",
                    "status": "open",
                    "task_class": "user_gate",
                    "action_kind": "decide",
                    "blocks_agent": "codex-main-control",
                }
            ],
            "agent_todos": [
                {
                    "todo_id": "todo_projection_sync",
                    "title": "[P0] Sync projection rows",
                    "status": "open",
                    "task_class": "advancement_task",
                    "action_kind": "sync_projection",
                    "claimed_by": "codex-main-control",
                },
                {
                    "todo_id": "todo_projection_other",
                    "title": "[P2] Other lane item",
                    "status": "open",
                    "task_class": "advancement_task",
                    "action_kind": "sync_projection",
                    "claimed_by": "codex-product-capability",
                },
                {
                    "todo_id": "todo_projection_done",
                    "title": "[P2] Completed projection item",
                    "status": "done",
                    "task_class": "advancement_task",
                    "action_kind": "sync_projection",
                    "claimed_by": "codex-main-control",
                },
            ],
            "agent_lane_next_action": {
                "todo_id": "todo_projection_next",
                "text": "[P0] Run the projected next action",
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "next_action",
            },
        }
        projection_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=projection_payload,
            agent_id="codex-main-control",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        projection_todo_ids = {item["todo_id"] for item in projection_sync["records"]}
        assert projection_sync["ok"] is True, projection_sync
        assert projection_sync["schema_version"] == "loopx_lark_kanban_sync_projection_v0", projection_sync
        assert projection_sync["row_count"] == 3, projection_sync
        assert "projection:frontstage-smoke:user_todo:todo_projection_gate" in projection_todo_ids, projection_sync
        assert "projection:frontstage-smoke:agent_todo:todo_projection_sync" in projection_todo_ids, projection_sync
        assert "projection:frontstage-smoke:agent_todo:todo_projection_done" not in projection_todo_ids
        assert all(item["command"]["executed"] is False for item in projection_sync["records"]), projection_sync
        next_action_record = next(
            item["values"]
            for item in projection_sync["records"]
            if item["todo_id"] == "projection:frontstage-smoke:next_action:todo_projection_next"
        )
        assert next_action_record["Priority"] == "P0", next_action_record
        assert next_action_record["Scope"] == "projection_source=frontstage-smoke", next_action_record

        quota_projection = {
            "goal_id": "goal_lark_sync_fixture",
            "agent_identity": {"agent_id": "codex-product-capability"},
            "agent_lane_next_action": {
                "todo_id": "todo_quota_next",
                "text": "[P0] Execute quota next action",
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "quota_next_action",
            },
            "capability_gate": {
                "runnable_candidates": [
                    {
                        "todo_id": "todo_quota_run",
                        "text": "[P1] Runnable product candidate",
                        "status": "open",
                        "task_class": "advancement_task",
                        "action_kind": "run_candidate",
                        "claimed_by": "codex-product-capability",
                    },
                    {
                        "todo_id": "todo_quota_other",
                        "text": "[P1] Other agent candidate",
                        "status": "open",
                        "task_class": "advancement_task",
                        "action_kind": "run_candidate",
                        "claimed_by": "codex-main-control",
                    },
                ]
            },
        }
        quota_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=quota_projection,
            agent_id="codex-product-capability",
            source_id="quota-smoke",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        assert quota_sync["row_count"] == 2, quota_sync
        assert {item["todo_id"] for item in quota_sync["records"]} == {
            "projection:quota-smoke:next_action:todo_quota_next",
            "projection:quota-smoke:runnable_candidate:todo_quota_run",
        }, quota_sync

        lifecycle_projection = {
            "schema_version": "goal_channel_projection_v0",
            "goal_id": "goal_lark_sync_fixture",
            "source_id": "row-lifecycle-smoke",
            "agent_identity": {"agent_id": "codex-product-capability"},
            "row_lifecycle_events": [
                {
                    "row_id": "legacy-local-seed-1",
                    "row_lifecycle": {
                        "state": "superseded",
                        "source_row_id": "legacy-local-seed-1",
                        "supersedes": ["legacy-local-seed-1"],
                        "superseded_by": "projection:row-lifecycle-smoke:agent_todo:todo_projection_current",
                        "migration_audit_id": "audit_public_fixture_001",
                    },
                    "text": "[P2] Mark legacy local seed row superseded",
                    "claimed_by": "codex-product-capability",
                }
            ],
        }
        lifecycle_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=lifecycle_projection,
            agent_id="codex-product-capability",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        assert lifecycle_sync["row_count"] == 1, lifecycle_sync
        lifecycle_record = lifecycle_sync["records"][0]["values"]
        assert lifecycle_sync["records"][0]["todo_id"] == (
            "projection:row-lifecycle-smoke:row_lifecycle:legacy-local-seed-1"
        ), lifecycle_sync
        assert lifecycle_record["Status"] == STATUS_DONE, lifecycle_record
        assert lifecycle_record["Action Kind"] == "projection_row_lifecycle", lifecycle_record
        assert "row_lifecycle=superseded" in lifecycle_record["Evidence"], lifecycle_record
        assert "supersedes=legacy-local-seed-1" in lifecycle_record["Evidence"], lifecycle_record
        assert "superseded_by=projection:row-lifecycle-smoke:agent_todo:todo_projection_current" in lifecycle_record["Evidence"], lifecycle_record
        assert "migration_audit_id=audit_public_fixture_001" in lifecycle_record["Evidence"], lifecycle_record

        private_projection = {
            "schema_version": "goal_channel_projection_v0",
            "goal_id": "goal_lark_sync_fixture",
            "source_id": "PRIVATE_MATERIAL_projection",
            "agent_identity": {"agent_id": "codex-product-capability"},
            "agent_lane_next_action": {
                "todo_id": "todo_shared_private",
                "text": "[P0] Inspect /Users/example/loopx/.local/private-plan.md",
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "projection_sink_safety",
                "claimed_by": "codex-product-capability",
                "scope": "/private/tmp/loopx-private/**",
                "handoff": "Open file:///Users/example/secret.md and https://internal.example.invalid/doc/private",
                "evidence": "PRIVATE_MATERIAL_ref from base_privatefixture and recPrivateFixture001",
            },
        }
        owner_only_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=private_projection,
            agent_id="codex-product-capability",
            sink_visibility="owner-only",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        owner_only_blob = json.dumps(owner_only_sync["records"], ensure_ascii=False)
        assert "/Users/example/loopx/.local/private-plan.md" in owner_only_blob, owner_only_sync
        assert "PRIVATE_MATERIAL_ref" in owner_only_blob, owner_only_sync

        shared_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=private_projection,
            agent_id="codex-product-capability",
            sink_visibility="shared",
            config_path=default_lark_kanban_config_path(registry),
            execute=False,
        )
        shared_blob = json.dumps(shared_sync["records"], ensure_ascii=False)
        assert shared_sync["public_safe_redaction"] is True, shared_sync
        assert "[local-path-redacted]" in shared_blob, shared_sync
        assert "[private-link-redacted]" in shared_blob, shared_sync
        assert "[private-ref-redacted]" in shared_blob, shared_sync
        for private_fragment in (
            "/Users/example",
            "/private/tmp",
            "file:///Users",
            "internal.example.invalid",
            "PRIVATE_MATERIAL_ref",
            "base_privatefixture",
            "recPrivateFixture001",
        ):
            assert private_fragment not in shared_blob, (private_fragment, shared_sync)

        projection_calls: list[list[str]] = []

        def projection_upsert_runner(args: list[str], cwd: Path | None, timeout: float | None) -> dict[str, object]:
            projection_calls.append(args)
            if "+record-list" in args:
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "ok": True,
                            "data": {
                                "fields": ["LoopX Goal ID", "LoopX Todo ID"],
                                "data": [],
                                "record_id_list": [],
                            },
                        }
                    ),
                    "stderr": "",
                    "timed_out": False,
                }
            if "+record-upsert" in args:
                return {
                    "returncode": 0,
                    "stdout": json.dumps({"ok": True, "data": {"record_id": "recProjection0001"}}),
                    "stderr": "",
                    "timed_out": False,
                }
            raise AssertionError(args)

        idempotent_config_path = Path(tmp) / ".loopx" / "projection-idempotent.json"
        first_execute_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=private_projection,
            agent_id="codex-product-capability",
            sink_visibility="shared",
            config_path=idempotent_config_path,
            execute=True,
            runner=projection_upsert_runner,
        )
        assert first_execute_sync["ok"] is True, first_execute_sync
        assert first_execute_sync["row_count"] == 1, first_execute_sync
        stored_projection_config = read_lark_kanban_local_config(idempotent_config_path)
        assert "recProjection0001" in set(stored_projection_config["todo_records"].values()), stored_projection_config

        projection_calls.clear()
        second_execute_sync = sync_loopx_projection_to_lark_kanban(
            LarkKanbanConfig(
                **{"base_" + "token": "base_public_fixture"},
                table_id="tbl_public_fixture",
            ),
            projection=private_projection,
            agent_id="codex-product-capability",
            sink_visibility="shared",
            config_path=idempotent_config_path,
            execute=True,
            runner=projection_upsert_runner,
        )
        assert second_execute_sync["ok"] is True, second_execute_sync
        upsert_commands = [args for args in projection_calls if "+record-upsert" in args]
        assert len(upsert_commands) == 1, projection_calls
        assert "--record-id" in upsert_commands[0], upsert_commands
        assert "recProjection0001" in upsert_commands[0], upsert_commands

    sink_record = _lark_record_from_todo_block(
        {
            "role": "agent",
            "status": "blocked_typo",
            "task_class": "user_gate_typo",
            "claimed_by": "codex-main-control",
            "text": "[P1] Keep malformed sink input executable",
            "todo_id": "todo_sink_malformed",
        },
        goal_id="goal_lark_sync_fixture",
        state_file=Path("active-state.md"),
        priority="P1",
    )
    assert sink_record["Status"] == STATUS_CLAIMED, sink_record
    assert sink_record["Task Class"] == "advancement_task", sink_record
    assert sink_record["User Gate"] == "", sink_record
    assert sink_record["Run History"].endswith("status=open"), sink_record

    user_sink_record = _lark_record_from_todo_block(
        {
            "role": "user",
            "status": "open",
            "task_class": "advancement_task_typo",
            "text": "[P1] Choose board target",
            "todo_id": "todo_user_target",
        },
        goal_id="goal_lark_sync_fixture",
        state_file=Path("active-state.md"),
        priority="P1",
    )
    assert user_sink_record["Status"] == STATUS_USER_GATE, user_sink_record
    assert user_sink_record["Task Class"] == "user_gate", user_sink_record

    print("lark-kanban-control-plane-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
