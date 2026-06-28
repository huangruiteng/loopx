#!/usr/bin/env python3
"""Smoke-test public-safe benchmark debug bundle import."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-debug-bundle-import-") as tmp:
        root = Path(tmp)
        source = root / "source"
        output = root / "index.public.json"

        write_json(
            source / "run-a" / "benchmark_run.compact.json",
            {
                "compact_benchmark_run": {
                    "schema_version": "benchmark_run_v0",
                    "benchmark_id": "skillsbench@fixture",
                    "case_id": "citation-check-fixture",
                    "mode": "loopx_goal_start_product_mode",
                    "official_score_status": "observed",
                    "official_score": 0.0,
                    "score_failure_attribution": "solver_layer_failure",
                    "runner_return_status": "completed",
                    "interaction_counters": {
                        "schema_version": "skillsbench_interaction_counters_v0",
                        "goal_harness_state_reads": 2,
                        "goal_harness_case_state_writes": 3,
                    },
                }
            },
        )
        write_json(
            source / "run-a" / "loopx_controller_trace.public.json",
            {
                "schema_version": "loopx_controller_trace_v0",
                "max_round_observed": 10,
                "followup_prompt_count": 9,
                "last_decision": {"stop": False, "reason": "score_below_target"},
                "event_kind_counts": {
                    "quota_should_run": 10,
                    "todo_claim": 1,
                    "todo_update": 3,
                    "refresh_state": 2,
                    "quota_spend": 2,
                    "validation": 1,
                    "case_result": 1,
                },
                "loopx_case_todo_id": "todo_case_fixture",
                "final_todo_status": "open",
                "open_todo_count": 1,
                "todo_text": "Do not leak this fixture task text.",
            },
        )
        write_json(
            source / "run-b" / "case_goal_state_init.compact.json",
            {
                "schema_version": "case_goal_state_init_v0",
                "loopx_case_todo_id": "todo_case_init",
                "loopx_case_agent_id": "codex-case-agent",
                "case_goal_state_init_status": "initialized",
            },
        )
        write_json(
            source / "raw-named-run" / "benchmark_run.compact.json",
            {"schema_version": "benchmark_run_v0", "case_id": "raw-named-warning"},
        )
        (source / "run-c").mkdir(parents=True)
        (source / "run-c" / "bad.public.json").write_text("{not-json", encoding="utf-8")

        # These files must never be indexed, even though they are nearby evidence.
        (source / "run-a" / "trajectory.json").write_text("{}", encoding="utf-8")
        (source / "run-a" / "raw.log").write_text("raw content", encoding="utf-8")
        (source / "run-a" / "verifier_output_tail.txt").write_text("tail", encoding="utf-8")
        (source / "run-a" / "private.local.json").write_text("{}", encoding="utf-8")

        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "benchmark_debug_bundle_import.py"),
                "--source-dir",
                str(source),
                "--output",
                str(output),
                "--fail-on-empty",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "loopx_benchmark_debug_bundle_import_v0", payload
        assert payload["artifact_count"] == 5, payload
        assert payload["readable_count"] == 4, payload
        assert payload["malformed_count"] == 1, payload
        assert payload["filename_marker_warning_count"] == 1, payload
        boundary = payload["source_boundary"]
        assert boundary["raw_task_text_read"] is False, boundary
        assert boundary["raw_trajectory_read"] is False, boundary
        assert boundary["raw_logs_read"] is False, boundary
        assert boundary["verifier_output_tail_read"] is False, boundary
        assert boundary["absolute_paths_recorded"] is False, boundary

        rendered = json.dumps(payload, sort_keys=True)
        assert str(source) not in rendered, rendered
        assert "trajectory.json" not in rendered, rendered
        assert "raw.log" not in rendered, rendered
        assert "verifier_output_tail.txt" not in rendered, rendered
        assert "private.local.json" not in rendered, rendered
        assert "Do not leak this fixture task text" not in rendered, rendered

        run_item = next(item for item in payload["items"] if item["path"] == "run-a/benchmark_run.compact.json")
        assert run_item["summary"]["case_id"] == "citation-check-fixture", run_item
        assert run_item["summary"]["official_score"] == 0.0, run_item
        assert run_item["counters"]["phase_counters"]["status"] == 2, run_item
        assert run_item["counters"]["phase_counters"]["todo_update"] == 3, run_item

        controller = next(item for item in payload["items"] if item["path"] == "run-a/loopx_controller_trace.public.json")
        assert controller["todo_flow"]["loopx_case_todo_id"] == "todo_case_fixture", controller
        assert controller["todo_flow"]["final_todo_status"] == "open", controller
        assert controller["counters"]["phase_counters"]["quota_should_run"] == 10, controller
        assert controller["counters"]["phase_counters"]["case_result"] == 1, controller

        malformed = next(item for item in payload["items"] if item["path"] == "run-c/bad.public.json")
        assert malformed["readable"] is False, malformed
        assert malformed["error_type"] == "JSONDecodeError", malformed
    print("benchmark-debug-bundle-import-smoke ok")


if __name__ == "__main__":
    main()
