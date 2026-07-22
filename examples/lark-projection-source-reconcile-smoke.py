#!/usr/bin/env python3
"""Contract smoke for preview-first projection source reconciliation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.extensions.lark.presentation.kanban import (  # noqa: E402
    LarkKanbanConfig,
    lark_kanban_schema_payload,
    read_lark_kanban_local_config,
    sync_loopx_projection_to_lark_kanban,
    write_lark_kanban_local_config,
)


GOAL_ID = "goal-source-reconcile"
SOURCE_ID = "monthly-impact"
DESIRED_ID = f"projection:{SOURCE_ID}:issue_fix_metric:merged-prs"
ORPHAN_ID = f"projection:{SOURCE_ID}:issue_fix_metric:obsolete-metric"
STALE_ID = f"projection:{SOURCE_ID}:issue_fix_metric:missing-remotely"
OTHER_ID = "projection:other-source:issue_fix_metric:keep-me"


def projection_payload(*, extra_row: bool = False) -> dict[str, object]:
    rows: list[dict[str, object]] = [
        {"metric_id": "merged-prs", "metric": "Merged PRs", "current": 3}
    ]
    if extra_row:
        rows.append({"metric_id": "open-prs", "metric": "Open PRs", "current": 7})
    return {
        "schema_version": "issue_fix_metrics_projection_v0",
        "goal_id": GOAL_ID,
        "source_id": SOURCE_ID,
        "impact_rows": rows,
    }


class FixtureRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.remote: list[tuple[str, str]] = [
            (DESIRED_ID, "recDuplicate"),
            (DESIRED_ID, "recDesired"),
            (ORPHAN_ID, "recOrphan"),
            (OTHER_ID, "recOther"),
        ]
        self.has_more = False

    def __call__(
        self, args: list[str], cwd: Path | None, timeout: float | None
    ) -> dict[str, object]:
        self.calls.append(args)
        if "+field-list" in args:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "data": {
                            "fields": lark_kanban_schema_payload()["fields"],
                        },
                    }
                ),
                "stderr": "",
                "timed_out": False,
            }
        if "+record-list" in args:
            rows = [[GOAL_ID, todo_id] for todo_id, _ in self.remote]
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "data": {
                            "fields": ["LoopX Goal ID", "LoopX Todo ID"],
                            "data": rows,
                            "record_id_list": [
                                record_id for _, record_id in self.remote
                            ],
                            "has_more": self.has_more,
                        },
                    }
                ),
                "stderr": "",
                "timed_out": False,
            }
        if "+record-upsert" in args:
            record_id = (
                args[args.index("--record-id") + 1]
                if "--record-id" in args
                else "recCreated"
            )
            return {
                "returncode": 0,
                "stdout": json.dumps({"ok": True, "data": {"record_id": record_id}}),
                "stderr": "",
                "timed_out": False,
            }
        if "+record-delete" in args:
            record_ids = [
                args[index + 1]
                for index, value in enumerate(args)
                if value == "--record-id"
            ]
            self.remote = [
                (todo_id, record_id)
                for todo_id, record_id in self.remote
                if record_id not in record_ids
            ]
            return {
                "returncode": 0,
                "stdout": json.dumps({"ok": True, "data": {"deleted": record_ids}}),
                "stderr": "",
                "timed_out": False,
            }
        raise AssertionError(args)


def expect_value_error(fragment: str, **kwargs: object) -> None:
    try:
        sync_loopx_projection_to_lark_kanban(**kwargs)
    except ValueError as error:
        assert fragment in str(error), error
    else:
        raise AssertionError(f"expected ValueError containing {fragment!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-source-reconcile-") as tmp:
        config_path = Path(tmp) / "lark-kanban.json"
        config = LarkKanbanConfig(
            **{"base_" + "token": "base_public_fixture"},
            table_id="tbl_public_fixture",
        )
        local_map = {
            f"{GOAL_ID}:{DESIRED_ID}": "recDesired",
            f"{GOAL_ID}:{ORPHAN_ID}": "recOrphan",
            f"{GOAL_ID}:{STALE_ID}": "recStaleMissing",
            f"{GOAL_ID}:{OTHER_ID}": "recOther",
        }
        write_lark_kanban_local_config(
            config_path,
            {
                "board": {
                    "base_token": config.base_token,
                    "table_id": config.table_id,
                },
                "todo_records": local_map,
            },
        )
        runner = FixtureRunner()

        normal = sync_loopx_projection_to_lark_kanban(
            config,
            projection=projection_payload(),
            config_path=config_path,
            include_done=True,
            execute=True,
            runner=runner,
        )
        assert normal["ok"] is True, normal
        assert normal["source_reconcile"]["requested"] is False, normal
        assert not any("+record-delete" in call for call in runner.calls), runner.calls
        repaired_local_map = {
            key: record_id
            for key, record_id in local_map.items()
            if key != f"{GOAL_ID}:{STALE_ID}"
        }
        assert read_lark_kanban_local_config(config_path)["todo_records"] == (
            repaired_local_map
        )

        local = read_lark_kanban_local_config(config_path)
        local["todo_records"] = local_map
        write_lark_kanban_local_config(config_path, local)

        base_args = {
            "config": config,
            "projection": projection_payload(),
            "config_path": config_path,
            "include_done": True,
            "reconcile_source": True,
            "source_snapshot_complete": True,
            "runner": runner,
        }
        expect_value_error(
            "agent-filtered",
            **{**base_args, "agent_id": "codex-filtered"},
        )
        expect_value_error(
            "row limit",
            **{
                **base_args,
                "projection": projection_payload(extra_row=True),
                "limit": 1,
            },
        )
        expect_value_error(
            "include_done",
            **{**base_args, "include_done": False},
        )
        expect_value_error(
            "complete source snapshot",
            **{**base_args, "source_snapshot_complete": False},
        )

        runner.has_more = True
        expect_value_error("complete remote record list", **base_args)
        runner.has_more = False

        runner.calls.clear()
        preview = sync_loopx_projection_to_lark_kanban(
            **base_args,
            execute=False,
        )
        receipt = preview["source_reconcile"]
        assert preview["ok"] is True, preview
        assert receipt["mode"] == "preview", receipt
        assert receipt["remote_orphan_record_ids"] == ["recOrphan"], receipt
        assert receipt["remote_duplicate_record_ids"] == ["recDuplicate"], receipt
        assert receipt["remote_delete_record_ids"] == [
            "recDuplicate",
            "recOrphan",
        ], receipt
        assert receipt["remote_duplicate_key_count"] == 1, receipt
        assert receipt["local_mapping_keys_to_remove"] == [
            f"{GOAL_ID}:{ORPHAN_ID}"
        ], receipt
        assert receipt["remote_delete_count"] == 2, receipt
        assert receipt["local_mapping_delete_count"] == 1, receipt
        assert not any("+record-delete" in call for call in runner.calls), runner.calls
        assert read_lark_kanban_local_config(config_path)["todo_records"] == local_map

        runner.calls.clear()
        executed = sync_loopx_projection_to_lark_kanban(
            **base_args,
            execute=True,
        )
        receipt = executed["source_reconcile"]
        assert executed["ok"] is True, executed
        assert receipt["mode"] == "execute", receipt
        assert receipt["executed_remote_delete_count"] == 2, receipt
        delete_calls = [call for call in runner.calls if "+record-delete" in call]
        assert len(delete_calls) == 1, runner.calls
        assert {
            delete_calls[0][index + 1]
            for index, value in enumerate(delete_calls[0])
            if value == "--record-id"
        } == {"recDuplicate", "recOrphan"}
        assert "--yes" in delete_calls[0]
        stored = read_lark_kanban_local_config(config_path)["todo_records"]
        assert f"{GOAL_ID}:{DESIRED_ID}" in stored, stored
        assert f"{GOAL_ID}:{OTHER_ID}" in stored, stored
        assert f"{GOAL_ID}:{ORPHAN_ID}" not in stored, stored
        assert f"{GOAL_ID}:{STALE_ID}" not in stored, stored

        runner.calls.clear()
        retry = sync_loopx_projection_to_lark_kanban(
            **base_args,
            execute=True,
        )
        assert retry["ok"] is True, retry
        assert retry["source_reconcile"]["remote_delete_count"] == 0, retry
        assert retry["source_reconcile"]["local_mapping_delete_count"] == 0, retry
        assert not any("+record-delete" in call for call in runner.calls), runner.calls

    print("lark-projection-source-reconcile-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
