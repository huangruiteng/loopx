from __future__ import annotations

import json
from pathlib import Path

from loopx.extensions.lark.presentation.kanban import (
    LarkKanbanConfig,
    lark_kanban_doctor,
    lark_kanban_schema_payload,
    read_lark_kanban_local_config,
    save_lark_kanban_board_config,
    sync_loopx_projection_to_lark_kanban,
    write_lark_kanban_local_config,
)


def _result(payload: object) -> dict[str, object]:
    return {
        "returncode": 0,
        "stdout": json.dumps(payload),
        "stderr": "",
        "timed_out": False,
    }


def _stale_schema_runner(
    calls: list[list[str]],
):
    def run(
        args: list[str], cwd: Path | None, timeout: float | None
    ) -> dict[str, object]:
        calls.append(args)
        if args == ["lark-cli", "--version"]:
            return _result({"version": "1.0.56"})
        if args == ["lark-cli", "auth", "status"]:
            return _result(
                {"ok": True, "identities": {"user": {"available": True}}}
            )
        if args[-1:] == ["--help"]:
            return _result({"ok": True})
        if "+field-list" in args:
            return _result(
                {
                    "ok": True,
                    "data": {
                        "fields": [
                            {"id": "fld_task", "name": "Task", "type": "text"},
                            {
                                "id": "fld_status",
                                "name": "Status",
                                "type": "select",
                            },
                        ]
                    },
                }
            )
        return _result({"ok": True})

    return run


def test_doctor_reports_stale_schema_with_migration_command(tmp_path: Path) -> None:
    config_path = tmp_path / "lark-kanban.json"
    save_lark_kanban_board_config(
        config_path,
        base_token="base_public_fixture",
        table_id="tbl_public_fixture",
        cli_bin="lark-cli",
        identity="user",
    )
    calls: list[list[str]] = []

    payload = lark_kanban_doctor(
        config_path=config_path,
        runner=_stale_schema_runner(calls),
    )

    assert payload["ok"] is False
    assert payload["schema_check"]["status"] == "stale"
    assert "Work Item Type" in payload["schema_check"]["missing_fields"]
    assert payload["schema_check"]["remediation_command"] == (
        "loopx lark-kanban setup --execute"
    )
    assert any("setup --execute" in issue["message"] for issue in payload["issues"])
    assert sum("+field-list" in args for args in calls) == 1


def test_execute_sync_stops_before_writes_when_schema_is_stale() -> None:
    calls: list[list[str]] = []
    config = LarkKanbanConfig(
        base_token="base_public_fixture",
        table_id="tbl_public_fixture",
        cli_bin="lark-cli",
        identity="user",
    )

    payload = sync_loopx_projection_to_lark_kanban(
        config,
        projection={
            "schema_version": "goal_channel_projection_v0",
            "goal_id": "goal_public_fixture",
            "source_id": "source-public-fixture",
            "agent_todos": [
                {
                    "todo_id": "todo_public_fixture",
                    "title": "Repair the public fixture",
                    "status": "open",
                    "task_class": "advancement_task",
                }
            ],
        },
        execute=True,
        runner=_stale_schema_runner(calls),
    )

    assert payload["ok"] is False
    assert payload["schema_check"]["status"] == "stale"
    assert "setup --execute" in payload["error"]
    assert payload["records"] == []
    assert len(calls) == 1
    assert "+field-list" in calls[0]
    assert not any("+record-upsert" in args for args in calls)


def test_complete_remote_list_replaces_stale_local_record_id(tmp_path: Path) -> None:
    config_path = tmp_path / "lark-kanban.json"
    config = LarkKanbanConfig(
        base_token="base_public_fixture",
        table_id="tbl_public_fixture",
        cli_bin="lark-cli",
        identity="user",
    )
    save_lark_kanban_board_config(
        config_path,
        base_token=config.base_token,
        table_id=config.table_id,
        cli_bin=config.cli_bin,
        identity=config.identity,
    )
    local = read_lark_kanban_local_config(config_path)
    record_key = (
        "goal_public_fixture:"
        "projection:source-public-fixture:agent_todo:todo_public_fixture"
    )
    local["todo_records"] = {record_key: "rec_stale_fixture"}
    write_lark_kanban_local_config(config_path, local)
    calls: list[list[str]] = []

    def runner(
        args: list[str], cwd: Path | None, timeout: float | None
    ) -> dict[str, object]:
        calls.append(args)
        if "+field-list" in args:
            return _result(
                {
                    "ok": True,
                    "data": {"fields": lark_kanban_schema_payload()["fields"]},
                }
            )
        if "+record-list" in args:
            return _result(
                {
                    "ok": True,
                    "data": {
                        "fields": ["LoopX Goal ID", "LoopX Todo ID"],
                        "data": [["goal_public_fixture", "todo_different_fixture"]],
                        "record_id_list": ["rec_stale_fixture"],
                        "has_more": False,
                    },
                }
            )
        if "+record-upsert" in args:
            assert "--record-id" not in args
            return _result({"ok": True, "data": {"record_id": "rec_fresh_fixture"}})
        raise AssertionError(args)

    payload = sync_loopx_projection_to_lark_kanban(
        config,
        projection={
            "schema_version": "goal_channel_projection_v0",
            "goal_id": "goal_public_fixture",
            "source_id": "source-public-fixture",
            "agent_todos": [
                {
                    "todo_id": "todo_public_fixture",
                    "title": "Repair the public fixture",
                    "status": "open",
                    "task_class": "advancement_task",
                }
            ],
        },
        config_path=config_path,
        execute=True,
        runner=runner,
    )

    assert payload["ok"] is True
    assert payload["records"][0]["record_id"] == "rec_fresh_fixture"
    persisted = read_lark_kanban_local_config(config_path)["todo_records"]
    assert persisted[record_key] == "rec_fresh_fixture"
    assert persisted["goal_public_fixture:todo_different_fixture"] == (
        "rec_stale_fixture"
    )
    assert sum("+record-upsert" in args for args in calls) == 1
