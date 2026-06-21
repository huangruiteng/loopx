#!/usr/bin/env python3
"""Smoke-test AgentIssue-Bench Codex CLI runner real-result reducer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import collect_status  # noqa: E402


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "agentissue-bench-codex-cli-runner-real-result-reducer-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "agentissue-runner-real-result-fixture"
BENCHMARK_ID = "agentissue-bench"
SELECTED_TAG = "lagent_239"
RUN_MODE = "agentissue_codex_cli_runner_real_result_reducer"
CLASSIFICATION = "agentissue_bench_codex_cli_runner_real_result_reducer_v0"

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "GOOGLE" + "_API_KEY",
    "CODEX" + "_ACCESS_TOKEN",
    "raw" + "_issue_body:",
    "raw" + "_patch:",
    "raw" + "_log:",
    "trajectory.json",
]

REQUIRED_DOC_SNIPPETS = [
    "AgentIssue-Bench Codex CLI Runner Real-Result Reducer V0",
    "--real-result-root",
    "benchmark_run.compact.json",
    "benchmark_result.compact.json",
    "real-result.public.json",
    "python3 examples/agentissue-bench-codex-cli-runner-real-result-smoke.py",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    real_result_root = root / "private-real-result-root"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-13T00:00:00+00:00\n"
        "---\n\n"
        "# AgentIssue Runner Real-Result Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Reduce AgentIssue compact real-run result.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-13T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "loopx-platform",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "heartbeat": {"enabled": True},
                }
            ],
        },
    )
    write_json(
        real_result_root / "benchmark_run.compact.json",
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "loopx_agentissue_codex_cli_runner",
            "benchmark_id": BENCHMARK_ID,
            "selected_tag": SELECTED_TAG,
            "real_run": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "patch_sha256": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            "patch_bytes": 1054,
            "changed_file_count": 2,
            "hunk_count": 3,
            "patched_exit_code": 0,
            "baseline_exit_code": 124,
            "official_task_score": {
                "kind": "agentissue_bench_single_tag_container_eval",
                "status": "resolved",
                "resolved": True,
                "value": 1,
            },
            "validation": {
                "selected_image_only": True,
                "single_tag_only": True,
                "buggy_source_extracted": True,
                "fixed_source_not_extracted_to_host": True,
                "host_codex_cli_invoked": True,
                "patch_exported_from_buggy_source_git_diff": True,
                "patch_applied_in_container": True,
                "patched_eval_exit_zero": True,
                "patched_eval_success_marker": True,
                "no_upload": True,
                "no_submit": True,
                "no_public_ranking_path": True,
                "raw_logs_public": False,
                "patch_content_public": False,
                "credential_values_recorded": False,
                "codex_auth_synced_to_container_or_remote": False,
            },
        },
    )
    write_json(
        real_result_root / "benchmark_result.compact.json",
        {
            "schema_version": "benchmark_result_v0",
            "benchmark_id": BENCHMARK_ID,
            "selected_tag": SELECTED_TAG,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "patch_sha256": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            "patch_bytes": 1054,
            "changed_file_count": 2,
            "official_task_score": {
                "kind": "agentissue_bench_single_tag_container_eval",
                "status": "resolved",
                "resolved": True,
                "value": 1,
            },
        },
    )
    return registry_path, runtime, real_result_root


def write_patch_apply_failure_fixture(real_result_root: Path) -> None:
    write_json(
        real_result_root / "benchmark_run.compact.json",
        {
            "schema_version": "benchmark_run_v0",
            "source_runner": "loopx_agentissue_codex_cli_runner",
            "benchmark_id": BENCHMARK_ID,
            "selected_tag": SELECTED_TAG,
            "selected_image": "alfin06/agentissue-bench:lagent_239",
            "real_run": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "patch_sha256": "def456abc123def456abc123def456abc123def456abc123def456abc123def4",
            "patch_bytes": 2356,
            "changed_file_count": 1,
            "hunk_count": 4,
            "patched_exit_code": 1,
            "official_task_score": {
                "kind": "agentissue_bench_single_tag_container_eval",
                "resolved": False,
                "value": 0,
            },
            "validation": {
                "selected_image_only": True,
                "single_tag_only": True,
                "buggy_source_extracted": True,
                "fixed_source_not_extracted_to_host": True,
                "host_codex_cli_invoked": True,
                "patch_exported_from_buggy_source_git_diff": True,
                "patch_applied_in_container": False,
                "patched_eval_exit_zero": False,
                "patched_eval_success_marker": False,
                "no_upload": True,
                "no_submit": True,
                "no_public_ranking_path": True,
                "raw_logs_public": False,
                "patch_content_public": False,
                "credential_values_recorded": False,
                "codex_auth_synced_to_container_or_remote": False,
            },
        },
    )
    write_json(
        real_result_root / "benchmark_result.compact.json",
        {
            "schema_version": "benchmark_result_v0",
            "benchmark_id": BENCHMARK_ID,
            "selected_tag": SELECTED_TAG,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "patch_sha256": "def456abc123def456abc123def456abc123def456abc123def456abc123def4",
            "patch_bytes": 2356,
            "changed_file_count": 1,
            "official_task_score": {
                "kind": "agentissue_bench_single_tag_container_eval",
                "resolved": False,
                "value": 0,
            },
        },
    )


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_cli_json(args: list[str]) -> dict[str, Any]:
    result = run_cli(args)
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def common_args(registry_path: Path, runtime: Path, real_result_root: Path) -> list[str]:
    return [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "benchmark",
        "agentissue-codex-runner-flow",
        "--goal-id",
        GOAL_ID,
        "--tag",
        SELECTED_TAG,
        "--real-result-root",
        str(real_result_root),
        "--no-global-sync",
    ]


def assert_no_forbidden_text(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 52000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "agentissue-bench-codex-cli-runner-real-result-reducer-v0.md" in readme, readme
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_real_result_file(
    real_result_root: Path,
    *,
    expected_passed: bool = True,
    patch_applied: bool = True,
) -> None:
    path = real_result_root / "real-result.public.json"
    assert path.exists(), path
    packet = json.loads(path.read_text(encoding="utf-8"))
    assert packet["schema_version"] == CLASSIFICATION, packet
    assert packet["path_recorded"] is False, packet
    assert packet["real_run_done"] is True, packet
    assert packet["real_runner_invoked_by_reducer"] is False, packet
    assert packet["real_codex_invoked_by_reducer"] is False, packet
    assert packet["real_docker_invoked_by_reducer"] is False, packet
    assert packet["result_summary"]["official_task_score"]["passed"] is expected_passed, packet
    assert packet["result_summary"]["official_task_score"]["value"] == (1 if expected_passed else 0), packet
    assert packet["phase_checks"]["buggy_source_extracted"] is True, packet
    assert packet["phase_checks"]["host_codex_cli_invoked"] is True, packet
    assert packet["phase_checks"]["patch_exported_from_buggy_source_git_diff"] is True, packet
    assert packet["phase_checks"]["patch_applied_in_container"] is patch_applied, packet
    assert packet["phase_checks"]["patched_eval_exit_zero"] is expected_passed, packet
    assert packet["boundary"]["no_upload"] is True, packet
    assert packet["boundary"]["no_submit"] is True, packet
    assert packet["boundary"]["no_public_ranking_path"] is True, packet
    assert packet["boundary"]["codex_auth_synced"] is False, packet
    assert packet["boundary"]["raw_logs_public"] is False, packet
    assert packet["boundary"]["patch_content_public"] is False, packet
    assert_no_forbidden_text(packet)


def assert_payload(
    payload: dict[str, Any],
    *,
    appended: bool,
    expected_passed: bool = True,
    patch_applied: bool = True,
) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == CLASSIFICATION, payload

    cli = payload["benchmark_cli"]
    assert cli["benchmark"] == BENCHMARK_ID, cli
    assert cli["command"] == "agentissue-codex-runner-flow", cli
    assert cli["tag"] == SELECTED_TAG, cli
    assert cli["real_result_materialized"] is True, cli
    assert cli["real_result_root_path_recorded"] is False, cli
    assert cli["real_result_read_boundary"] == "compact_only", cli
    assert cli["real_runner_invoked"] is False, cli
    assert cli["real_codex_invoked"] is False, cli
    assert cli["real_docker_invoked"] is False, cli
    assert cli["auth_values_read"] is False, cli

    real_result = payload["agentissue_real_result"]
    assert real_result["schema_version"] == CLASSIFICATION, real_result
    assert real_result["ready"] is True, real_result
    assert real_result["materialized"] is True, real_result
    assert real_result["path_recorded"] is False, real_result
    assert real_result["result_checks"]["resolved"] is expected_passed, real_result
    assert real_result["result_checks"]["buggy_source_extracted"] is True, real_result
    assert real_result["result_checks"]["host_codex_cli_invoked"] is True, real_result
    assert real_result["result_checks"]["patch_exported_from_buggy_source_git_diff"] is True, real_result
    assert real_result["result_checks"]["patch_applied_in_container"] is patch_applied, real_result
    assert real_result["result_checks"]["patched_eval_exit_zero"] is expected_passed, real_result
    assert real_result["result_checks"]["no_upload"] is True, real_result
    assert real_result["result_checks"]["raw_logs_public"] is False, real_result
    assert real_result["execution_boundary"]["codex_cli_invoked_by_reducer"] is False, real_result
    assert real_result["execution_boundary"]["docker_container_started_by_reducer"] is False, real_result

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["benchmark_id"] == BENCHMARK_ID, event
    assert event["mode"] == RUN_MODE, event
    assert event["real_run"] is True, event
    assert event["submit_eligible"] is False, event
    assert event["leaderboard_evidence"] is False, event
    assert event["official_score_claim_allowed"] is False, event
    assert event["official_task_score"]["passed"] is expected_passed, event
    assert event["official_task_score"]["value"] == (1 if expected_passed else 0), event
    assert event["validation"]["all_passed"] is expected_passed, event
    assert event["validation"]["buggy_source_extracted"] is True, event
    assert event["validation"]["host_codex_cli_invoked"] is True, event
    assert event["validation"]["patch_exported_from_buggy_source_git_diff"] is True, event
    assert event["validation"]["patch_applied_in_container"] is patch_applied, event
    assert event["validation"]["patched_eval_exit_zero"] is expected_passed, event
    if not expected_passed:
        assert "unresolved_patch_apply_failed_compact_result" in event[
            "failure_attribution_labels"
        ], event
    assert event["read_boundary"]["compact_only"] is True, event
    assert event["read_boundary"]["raw_artifacts_read"] is False, event

    result = payload["benchmark_result"]
    assert result["schema_version"] == "benchmark_result_v0", result
    assert result["terminal_state"] == ("resolved" if expected_passed else "evaluated_unresolved"), result
    assert result["official_task_score"]["passed"] is expected_passed, result
    assert result["phase_checks"]["buggy_source_extracted"] is True, result
    assert result["phase_checks"]["host_codex_cli_invoked"] is True, result
    assert result["phase_checks"]["patch_applied_in_container"] is patch_applied, result

    assert_no_forbidden_text(cli)
    assert_no_forbidden_text(real_result)
    assert_no_forbidden_text(event)
    assert_no_forbidden_text(result)


def assert_status_projection(
    registry_path: Path,
    runtime: Path,
    *,
    expected_passed: bool = True,
    patch_applied: bool = True,
) -> None:
    status = collect_status(
        registry_path=registry_path,
        runtime_root_override=str(runtime),
        scan_roots=[],
        limit=5,
    )
    assert status["ok"], status
    latest = status["run_history"]["goals"][0]["latest_runs"][0]
    summary = latest["benchmark_run_summary"]
    assert summary["mode"] == RUN_MODE, summary
    assert summary["benchmark_id"] == BENCHMARK_ID, summary
    assert summary["real_run"] is True, summary
    assert summary["official_task_score"]["passed"] is expected_passed, summary
    assert summary["validation"]["all_passed"] is expected_passed, summary
    assert summary["validation"]["buggy_source_extracted"] is True, summary
    assert summary["validation"]["host_codex_cli_invoked"] is True, summary
    assert summary["validation"]["patch_exported_from_buggy_source_git_diff"] is True, summary
    assert summary["validation"]["patch_applied_in_container"] is patch_applied, summary
    assert summary["validation"]["patched_eval_exit_zero"] is expected_passed, summary
    assert summary["read_boundary"]["compact_only"] is True, summary
    assert_no_forbidden_text(summary)


def assert_roots_are_mutually_exclusive(
    registry_path: Path,
    runtime: Path,
    real_result_root: Path,
) -> None:
    args = common_args(registry_path, runtime, real_result_root) + [
        "--first-run-handoff-root",
        str(real_result_root / "other-root"),
    ]
    result = run_cli(args, check=False)
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False, payload
    assert "at most one root option" in payload["error"], payload
    assert "--real-result-root" in payload["error"], payload


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(prefix="agentissue-runner-real-result-resolved-") as tmp:
        registry_path, runtime, real_result_root = write_fixture(Path(tmp))
        dry_payload = run_cli_json(common_args(registry_path, runtime, real_result_root))
        assert_payload(dry_payload, appended=False)
        assert_real_result_file(real_result_root)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime, real_result_root)
            + [
                "--delivery-batch-scale",
                "multi_surface",
                "--delivery-outcome",
                "primary_goal_outcome",
                "--execute",
            ]
        )
        assert_payload(execute_payload, appended=True)
        assert_real_result_file(real_result_root)
        assert_status_projection(registry_path, runtime)
        assert_roots_are_mutually_exclusive(registry_path, runtime, real_result_root)

    with tempfile.TemporaryDirectory(prefix="agentissue-runner-real-result-score0-") as tmp:
        registry_path, runtime, real_result_root = write_fixture(Path(tmp))
        write_patch_apply_failure_fixture(real_result_root)
        dry_payload = run_cli_json(common_args(registry_path, runtime, real_result_root))
        assert_payload(
            dry_payload,
            appended=False,
            expected_passed=False,
            patch_applied=False,
        )
        assert_real_result_file(
            real_result_root,
            expected_passed=False,
            patch_applied=False,
        )

        execute_payload = run_cli_json(
            common_args(registry_path, runtime, real_result_root)
            + [
                "--delivery-batch-scale",
                "multi_surface",
                "--delivery-outcome",
                "primary_goal_outcome",
                "--execute",
            ]
        )
        assert_payload(
            execute_payload,
            appended=True,
            expected_passed=False,
            patch_applied=False,
        )
        assert_real_result_file(
            real_result_root,
            expected_passed=False,
            patch_applied=False,
        )
        assert_status_projection(
            registry_path,
            runtime,
            expected_passed=False,
            patch_applied=False,
        )

    print(
        "agentissue-bench-codex-cli-runner-real-result-smoke ok "
        f"mode={RUN_MODE} appended=True real_run=True score0_patch_apply_failure=True"
    )


if __name__ == "__main__":
    main()
