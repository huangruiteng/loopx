#!/usr/bin/env python3
"""Smoke-test AgentIssue-Bench Codex CLI runner target handoff packet."""

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
DOC = TOPIC_DIR / "agentissue-bench-codex-cli-runner-target-handoff-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "agentissue-runner-target-handoff-fixture"
BENCHMARK_ID = "agentissue-bench"
SELECTED_TAG = "lagent_239"
RUN_MODE = "agentissue_codex_cli_runner_target_handoff_packet"
CLASSIFICATION = "agentissue_bench_codex_cli_runner_target_handoff_v0"

REQUIRED_DOC_SNIPPETS = [
    "AgentIssue-Bench Codex CLI Runner Target Handoff V0",
    "--target-runner-handoff-root",
    "target-runner-handoff.public.json",
    "handoff_target=separate_benchmark_execution_thread",
    "meta_heartbeat_must_not_execute=true",
    "real_run_authorized_by_packet=false",
    "python3 examples/agentissue-bench-codex-cli-runner-target-handoff-smoke.py",
]

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
    "screenshot.png",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    handoff_root = root / "private-target-handoff-root"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-13T00:00:00+00:00\n"
        "---\n\n"
        "# AgentIssue Runner Target Handoff Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Build AgentIssue target-runner handoff packet.\n",
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
    return registry_path, runtime, handoff_root


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


def common_args(registry_path: Path, runtime: Path, handoff_root: Path) -> list[str]:
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
        "--target-runner-handoff-root",
        str(handoff_root),
        "--no-global-sync",
    ]


def assert_no_forbidden_text(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 110000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "agentissue-bench-codex-cli-runner-target-handoff-v0.md" in readme, readme
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_handoff_files(handoff_root: Path) -> None:
    expected_paths = [
        "context/prompt.md",
        "buggy-source/.gitkeep",
        "Patches/lagent_239/.gitkeep",
        "runner-flow-plan.public.json",
        "execution-gate.public.json",
        "first-run-handoff.public.json",
        "first-run-handoff.md",
        "workflow-check.public.json",
        "run-specific-gate.public.json",
        "run-specific-gate.md",
        "target-runner-handoff.public.json",
        "target-runner-handoff.md",
        "benchmark_run.compact.json",
    ]
    missing = [rel for rel in expected_paths if not (handoff_root / rel).exists()]
    assert not missing, missing

    handoff = json.loads(
        (handoff_root / "target-runner-handoff.public.json").read_text(encoding="utf-8")
    )
    assert handoff["schema_version"] == CLASSIFICATION, handoff
    assert handoff["path_recorded"] is False, handoff
    assert handoff["handoff_target"] == "separate_benchmark_execution_thread", handoff
    assert handoff["meta_heartbeat_must_not_execute"] is True, handoff
    assert handoff["real_run_authorized_by_packet"] is False, handoff
    assert handoff["ready_for_real_run"] is False, handoff
    assert handoff["credential_boundary"]["host_codex_auth_local_only"] is True, handoff
    assert handoff["credential_boundary"]["shared_remote_host_receives_codex_auth"] is False, handoff
    assert handoff["public_output_contract"]["raw_logs_public"] is False, handoff
    assert handoff["execution_boundary"]["codex_cli_invoked"] is False, handoff
    assert handoff["execution_boundary"]["docker_container_started"] is False, handoff
    assert handoff["execution_boundary"]["target_runner_executed"] is False, handoff
    assert "do_not_execute_in_meta_heartbeat_thread" in handoff["stop_conditions"], handoff
    for required in [
        "private_job_root_selected",
        "operator_explicit_real_run_trigger",
        "selected_container_source_extracted",
        "private_git_baseline_created_before_codex",
        "host_codex_exec_ephemeral_from_buggy_source",
        "attempt_patch_reducer_configured",
        "selected_tag_eval_no_upload_submit_ranking",
        "compact_public_reducer_enabled",
        "host_codex_auth_local_only",
    ]:
        assert required in handoff["target_runner_prerequisites"], (required, handoff)

    local_run = json.loads((handoff_root / "benchmark_run.compact.json").read_text(encoding="utf-8"))
    assert local_run["schema_version"] == "benchmark_run_v0", local_run
    assert local_run["mode"] == RUN_MODE, local_run
    assert local_run["validation"]["target_runner_handoff_materialized"] is True, local_run
    assert local_run["validation"]["meta_heartbeat_must_not_execute"] is True, local_run
    assert local_run["validation"]["target_runner_executed"] is False, local_run
    assert local_run["first_blocker"] == "target_handoff_packet_only_no_meta_execution", local_run


def assert_payload(payload: dict[str, Any], *, appended: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == CLASSIFICATION, payload

    cli = payload["benchmark_cli"]
    assert cli["benchmark"] == BENCHMARK_ID, cli
    assert cli["command"] == "agentissue-codex-runner-flow", cli
    assert cli["tag"] == SELECTED_TAG, cli
    assert cli["target_handoff_materialized"] is True, cli
    assert cli["target_handoff_root_path_recorded"] is False, cli
    assert cli["real_runner_invoked"] is False, cli
    assert cli["real_codex_invoked"] is False, cli
    assert cli["real_docker_invoked"] is False, cli
    assert cli["auth_values_read"] is False, cli
    assert cli["submit_eligible"] is False, cli
    assert cli["leaderboard_evidence"] is False, cli

    handoff = payload["agentissue_target_handoff"]
    assert handoff["schema_version"] == CLASSIFICATION, handoff
    assert handoff["handoff_target"] == "separate_benchmark_execution_thread", handoff
    assert handoff["ready_for_real_run"] is False, handoff
    assert handoff["real_run_authorized_by_packet"] is False, handoff
    assert "target-runner-handoff.public.json" in handoff["created_relative_paths"], handoff
    assert handoff["execution_boundary"]["codex_cli_invoked"] is False, handoff

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["benchmark_id"] == BENCHMARK_ID, event
    assert event["mode"] == RUN_MODE, event
    assert event["first_blocker"] == "target_handoff_packet_only_no_meta_execution", event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["leaderboard_evidence"] is False, event
    assert "target-runner-handoff.public.json" in event["evidence_files"], event
    assert_no_forbidden_text(handoff)
    assert_no_forbidden_text(event)
    assert_no_forbidden_text(cli)


def assert_status_projection(registry_path: Path, runtime: Path) -> None:
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
    assert summary["first_blocker"] == "target_handoff_packet_only_no_meta_execution", summary
    assert_no_forbidden_text(summary)


def assert_roots_are_mutually_exclusive(
    registry_path: Path, runtime: Path, handoff_root: Path
) -> None:
    args = common_args(registry_path, runtime, handoff_root) + [
        "--run-gate-root",
        str(handoff_root / "other-root"),
    ]
    result = run_cli(args, check=False)
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False, payload
    assert "at most one" in payload["error"], payload


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(prefix="agentissue-runner-target-handoff-") as tmp:
        registry_path, runtime, handoff_root = write_fixture(Path(tmp))
        dry_payload = run_cli_json(common_args(registry_path, runtime, handoff_root))
        assert_payload(dry_payload, appended=False)
        assert_handoff_files(handoff_root)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime, handoff_root)
            + [
                "--delivery-batch-scale",
                "multi_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ]
        )
        assert_payload(execute_payload, appended=True)
        assert_handoff_files(handoff_root)
        assert_status_projection(registry_path, runtime)
        assert_roots_are_mutually_exclusive(registry_path, runtime, handoff_root / "mutual")

    print(
        "agentissue-bench-codex-cli-runner-target-handoff-smoke ok "
        f"mode={RUN_MODE} appended=True real_run=False"
    )


if __name__ == "__main__":
    main()
