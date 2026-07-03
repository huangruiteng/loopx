#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=ROOT,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
    )


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected to find {needle!r} in output:\n{text}")


def payload_from(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"expected JSON stdout, got:\nstdout={result.stdout}\nstderr={result.stderr}"
        ) from exc
    if not isinstance(payload, dict):
        raise AssertionError(payload)
    return payload


def main() -> int:
    help_result = run_cli("benchmark", "run", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--update-run-ledger")
    assert_contains(help_result.stdout, "--skillsbench-route")
    merge_help_result = run_cli("benchmark", "run-ledger-merge", "--help")
    if merge_help_result.returncode != 0:
        raise AssertionError(merge_help_result.stderr or merge_help_result.stdout)
    assert_contains(merge_help_result.stdout, "--source-run-ledger-path")
    assert_contains(merge_help_result.stdout, "--source-run-ledger-glob")

    terminal_result = run_cli(
        "--format",
        "json",
        "benchmark",
        "run",
        "terminal-bench",
        "--goal-id",
        "loopx-meta",
        "--mode",
        "codex-goal-mode",
    )
    if terminal_result.returncode != 0:
        raise AssertionError(terminal_result.stderr or terminal_result.stdout)
    terminal_payload = payload_from(terminal_result)
    if terminal_payload.get("ok") is not True:
        raise AssertionError(terminal_payload)
    if terminal_payload.get("dry_run") is not True:
        raise AssertionError(terminal_payload)
    if terminal_payload["benchmark_cli"].get("real_runner_invoked") is not False:
        raise AssertionError(terminal_payload)
    if terminal_payload["benchmark_cli"].get("submit_eligible") is not False:
        raise AssertionError(terminal_payload)

    skillsbench_result = run_cli(
        "--format",
        "json",
        "benchmark",
        "run",
        "skillsbench",
        "--goal-id",
        "loopx-meta",
    )
    if skillsbench_result.returncode != 0:
        raise AssertionError(skillsbench_result.stderr or skillsbench_result.stdout)
    skillsbench_payload = payload_from(skillsbench_result)
    if skillsbench_payload.get("ok") is not True:
        raise AssertionError(skillsbench_payload)
    if skillsbench_payload["benchmark_cli"].get("benchmark") != "skillsbench":
        raise AssertionError(skillsbench_payload)
    if skillsbench_payload["benchmark_cli"].get("skillsbench_route") != "loopx-blind-loop-treatment":
        raise AssertionError(skillsbench_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        benchmark_run_path = temp_root / "benchmark-run.json"
        benchmark_run_path.write_text(
            json.dumps(terminal_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        parity_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "parity-check",
            "--benchmark-run-json",
            str(benchmark_run_path),
        )
        if parity_result.returncode != 0:
            raise AssertionError(parity_result.stderr or parity_result.stdout)
        parity_payload = payload_from(parity_result)
        if parity_payload.get("ok") is not True:
            raise AssertionError(parity_payload)
        parity_check = parity_payload["codex_app_parity_posthoc_check"]
        if parity_check["read_boundary"].get("raw_task_text_read") is not False:
            raise AssertionError(parity_payload)

        ledger_path = temp_root / "benchmark-run-ledger.json"
        upsert_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-upsert",
            "--benchmark-run-json",
            str(benchmark_run_path),
            "--run-ledger-path",
            str(ledger_path),
        )
        if upsert_result.returncode != 0:
            raise AssertionError(upsert_result.stderr or upsert_result.stdout)
        upsert_payload = payload_from(upsert_result)
        if upsert_payload.get("ok") is not True:
            raise AssertionError(upsert_payload)
        if upsert_payload["read_boundary"].get("raw_logs_read") is not False:
            raise AssertionError(upsert_payload)

        harbor_wrapper_path = temp_root / "harbor-wrapper.json"
        harbor_wrapper_path.write_text(
            json.dumps(
                {
                    "schema_version": "harbor_job_result_reducer_v0",
                    "ok": True,
                    "compact_benchmark_run": terminal_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        harbor_wrapper_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-upsert",
            "--benchmark-run-json",
            str(harbor_wrapper_path),
            "--run-ledger-path",
            str(temp_root / "harbor-wrapper-ledger.json"),
        )
        if harbor_wrapper_result.returncode != 0:
            raise AssertionError(
                harbor_wrapper_result.stderr or harbor_wrapper_result.stdout
            )
        harbor_wrapper_payload = payload_from(harbor_wrapper_result)
        if harbor_wrapper_payload.get("ok") is not True:
            raise AssertionError(harbor_wrapper_payload)
        if harbor_wrapper_payload.get("input_kind") != "harbor_job_result_reducer_v0":
            raise AssertionError(harbor_wrapper_payload)
        if harbor_wrapper_payload["read_boundary"].get("raw_logs_read") is not False:
            raise AssertionError(harbor_wrapper_payload)

        post_launch = {
            "schema_version": "terminal_bench_post_launch_materialization_v0",
            "checked": True,
            "ready_for_launch_state": False,
            "ready_for_compact_result_ingest": False,
            "ready_for_compact_failure_marker": True,
            "first_blocker": "smoke_failure",
            "job_name": "smoke-job",
            "external_handle_terminal": True,
            "trial_result_present_count": 0,
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
        }
        post_launch_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-upsert",
            "--post-launch-json",
            "-",
            "--run-ledger-path",
            str(temp_root / "post-launch-ledger.json"),
            input_text=json.dumps(post_launch),
        )
        if post_launch_result.returncode != 0:
            raise AssertionError(post_launch_result.stderr or post_launch_result.stdout)
        post_launch_payload = payload_from(post_launch_result)
        if post_launch_payload.get("input_kind") != "terminal_bench_post_launch_materialization_v0":
            raise AssertionError(post_launch_payload)
        if post_launch_payload["read_boundary"].get("task_text_read") is not False:
            raise AssertionError(post_launch_payload)

        compact_ledger = {
            "schema_version": "benchmark_run_ledger_v0",
            "benchmarks": {
                "terminal-bench@2.0": {
                    "cases": {
                        "smoke-case": {
                            "latest_decision": {"decision": "single_arm_recorded"},
                            "runs": [{"run_id": "r1"}],
                        }
                    }
                }
            },
        }
        ledger_path.write_text(
            json.dumps(compact_ledger, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        analysis_path = temp_root / "benchmark-case-analysis.json"
        analysis_path.write_text(
            json.dumps(
                {"schema_version": "benchmark_case_analysis_v0", "cases": []},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        candidates_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "case-analysis-candidates",
            "--run-ledger-path",
            str(ledger_path),
            "--case-analysis-path",
            str(analysis_path),
            "--include-proposed-records",
        )
        if candidates_result.returncode != 0:
            raise AssertionError(candidates_result.stderr or candidates_result.stdout)
        candidates_payload = payload_from(candidates_result)
        if candidates_payload.get("ok") is not True:
            raise AssertionError(candidates_payload)
        if candidates_payload["report"].get("candidate_count") != 1:
            raise AssertionError(candidates_payload)
        if candidates_payload["read_boundary"].get("trajectory_read") is not False:
            raise AssertionError(candidates_payload)

        check_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-check",
            "--goal-id",
            "loopx-meta",
            "--history-limit",
            "0",
            "--run-ledger-path",
            str(ledger_path),
        )
        if check_result.returncode != 0:
            raise AssertionError(check_result.stderr or check_result.stdout)
        check_payload = payload_from(check_result)
        if check_payload.get("ok") is not True:
            raise AssertionError(check_payload)
        drift = check_payload["benchmark_run_ledger_drift"]
        if drift.get("drift_detected") is not False:
            raise AssertionError(check_payload)
        if check_payload["read_boundary"].get("upload_invoked") is not False:
            raise AssertionError(check_payload)

        def compact_source_ledger(case_id: str, run_id: str) -> dict[str, object]:
            return {
                "schema_version": "benchmark_run_ledger_v0",
                "benchmarks": {
                    "skillsbench@1.1": {
                        "cases": {
                            case_id: {
                                "case_id": case_id,
                                "runs": [
                                    {
                                        "run_id": run_id,
                                        "benchmark_id": "skillsbench@1.1",
                                        "case_id": case_id,
                                        "arm_id": "codex_app_server_goal_baseline",
                                        "mode": "skillsbench_codex_app_server_goal_baseline",
                                        "run_group_id": (
                                            "skillsbench-revtunnel-appgoal-batch5-smoke"
                                        ),
                                        "official_score": 0.0,
                                        "official_passed": False,
                                        "failure_class": (
                                            "official_verifier_solution_failure"
                                        ),
                                    }
                                ],
                            }
                        }
                    }
                },
            }

        source_a = temp_root / "source-a" / "benchmark-run-ledger.json"
        source_b = temp_root / "source-b" / "benchmark-run-ledger.json"
        source_a.parent.mkdir(parents=True)
        source_b.parent.mkdir(parents=True)
        source_a.write_text(
            json.dumps(compact_source_ledger("merge-alpha", "merge-run-alpha")),
            encoding="utf-8",
        )
        source_b.write_text(
            json.dumps(compact_source_ledger("merge-beta", "merge-run-beta")),
            encoding="utf-8",
        )
        merged_ledger = temp_root / "merged" / "benchmark-run-ledger.json"
        merge_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-merge",
            "--run-ledger-path",
            str(merged_ledger),
            "--source-run-ledger-path",
            str(source_a),
            "--source-run-ledger-path",
            str(source_b),
            "--benchmark-id",
            "skillsbench@1.1",
            "--run-group-contains",
            "batch5",
            "--execute",
        )
        if merge_result.returncode != 0:
            raise AssertionError(merge_result.stderr or merge_result.stdout)
        merge_payload = payload_from(merge_result)
        if merge_payload.get("ok") is not True:
            raise AssertionError(merge_payload)
        merge_summary = merge_payload["merge"]
        if merge_summary.get("source_paths_recorded") is not False:
            raise AssertionError(merge_payload)
        if merge_summary.get("merged_run_count") != 2:
            raise AssertionError(merge_payload)
        if str(source_a) in merge_result.stdout or str(source_b) in merge_result.stdout:
            raise AssertionError(merge_result.stdout)

    print("cli-benchmark-run-ledger-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
