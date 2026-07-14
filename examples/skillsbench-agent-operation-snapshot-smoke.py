#!/usr/bin/env python3
"""Prove cumulative relay snapshots do not inflate SkillsBench counters."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
)
from scripts.skillsbench_automation_loop import (  # noqa: E402
    _merge_host_local_acp_relay_trace_summary,
)


def append_operation(records: list[dict[str, object]]) -> None:
    records.extend(
        (
            {
                "operation": "exec",
                "record_phase": "start",
                "operation_observed": True,
                "task_facing_operation": True,
            },
            {
                "operation": "exec",
                "record_phase": "complete",
                "returncode": 0,
                "task_facing_operation": True,
            },
        )
    )


def write_summary(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def merge_trace(trace_dir: Path) -> dict[str, object]:
    plan = {
        "host_local_acp_relay_trace_dir": str(trace_dir),
        "runner_prerequisites": {
            "remote_command_file_bridge_agent_operation_trace_required": True,
        },
    }
    trace: dict[str, object] = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-goal-start-product-mode",
        "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
    }
    _merge_host_local_acp_relay_trace_summary(plan, trace)
    return trace


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-agent-snapshots-") as tmp:
        root = Path(tmp)
        trace_dir = root / "traces"
        summary_path = root / "bridge-summary.jsonl"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                route="loopx-goal-start-product-mode",
                worker_public_trace_dir=str(trace_dir),
            )
        )

        records: list[dict[str, object]] = []
        for _ in range(2):
            append_operation(records)
            write_summary(summary_path, records)
            relay._publish_remote_bridge_agent_operations_trace(
                bridge_summary_path=summary_path,
            )

        payloads = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(trace_dir.glob("*.compact.json"))
        ]
        snapshots = [
            payload["remote_command_file_bridge_agent_operations"]
            for payload in payloads
        ]
        assert len(snapshots) == 2, snapshots
        assert len({snapshot["snapshot_id"] for snapshot in snapshots}) == 1
        assert sorted(snapshot["snapshot_index"] for snapshot in snapshots) == [1, 2]

        trace = merge_trace(trace_dir)
        assert trace["remote_command_file_bridge_agent_operation_trace_count"] == 2
        assert trace["remote_command_file_bridge_agent_superseded_snapshot_count"] == 1
        assert trace["remote_command_file_bridge_agent_request_count"] == 2, trace
        assert trace["remote_command_file_bridge_agent_success_count"] == 2, trace
        assert trace["remote_command_file_bridge_agent_operation_counts"] == {
            "exec": 2,
        }, trace

        independent_summary_path = root / "independent-summary.jsonl"
        write_summary(independent_summary_path, records[:2])
        relay._publish_remote_bridge_agent_operations_trace(
            bridge_summary_path=independent_summary_path,
        )
        trace = merge_trace(trace_dir)
        assert trace["remote_command_file_bridge_agent_operation_trace_count"] == 3
        assert trace["remote_command_file_bridge_agent_superseded_snapshot_count"] == 1
        assert trace["remote_command_file_bridge_agent_request_count"] == 3, trace
        assert trace["remote_command_file_bridge_agent_success_count"] == 3, trace
        assert trace["remote_command_file_bridge_agent_operation_counts"] == {
            "exec": 3,
        }, trace

    print("skillsbench-agent-operation-snapshot-smoke: ok")


if __name__ == "__main__":
    main()
