#!/usr/bin/env python3
"""Smoke-test AgentIssue-Bench Codex CLI private runner script materialization."""

from __future__ import annotations

import json
import os
import stat
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
DOC = TOPIC_DIR / "agentissue-bench-codex-cli-runner-private-script-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "agentissue-runner-private-script-fixture"
BENCHMARK_ID = "agentissue-bench"
SELECTED_TAG = "lagent_239"
RUN_MODE = "agentissue_codex_cli_runner_private_script"
CLASSIFICATION = "agentissue_bench_codex_cli_runner_private_script_v0"

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
    "AgentIssue-Bench Codex CLI Runner Private Script V0",
    "--private-runner-root",
    "run-lagent239.private.sh",
    "private-runner.public.json",
    "benchmark_run.compact.json",
    "benchmark_result.compact.json",
    "python3 examples/agentissue-bench-codex-cli-runner-private-script-smoke.py",
]

REQUIRED_SCRIPT_SNIPPETS = [
    "set -euo pipefail",
    "extract_buggy_source_from_selected_container",
    "initialize_git_baseline_in_buggy_source",
    "run_host_local_codex_cli_patch_worker",
    "write_attempt_patch_from_buggy_source_git_diff",
    "evaluate_selected_tag_container",
    "write_compact_public_evidence",
    "export TAG IMAGE BUGGY_SOURCE PATCH_PATH MARKER_DIR",
    "reduce_compact_public_evidence",
    "APPEND_HISTORY",
    "ALLOW_DOCKER_PULL",
    "PRECHECK_ONLY",
    "precheck_private_runner_environment",
    "CONTAINER_BUGGY_SOURCE",
    "/app/source_code_buggy",
    "/usr/local/bin/run_test_entrypoint.sh apply_patch /patches/attempt.patch",
    "/usr/local/bin/run_test_entrypoint.sh test_patched",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    runner_root = root / "private-runner-root"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-13T00:00:00+00:00\n"
        "---\n\n"
        "# AgentIssue Runner Private Script Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Materialize a private AgentIssue runner script.\n",
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
    return registry_path, runtime, runner_root


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


def common_args(registry_path: Path, runtime: Path, runner_root: Path) -> list[str]:
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
        "--private-runner-root",
        str(runner_root),
        "--no-global-sync",
    ]


def assert_no_forbidden_text(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 65000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "agentissue-bench-codex-cli-runner-private-script-v0.md" in readme, readme
    assert_no_forbidden_text(text)


def assert_materialized_files(runner_root: Path) -> None:
    script = runner_root / "run-lagent239.private.sh"
    manifest_path = runner_root / "private-runner.public.json"
    compact_run = runner_root / "benchmark_run.compact.json"
    assert script.exists(), script
    assert manifest_path.exists(), manifest_path
    assert compact_run.exists(), compact_run

    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, oct(mode)
    script_text = script.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SCRIPT_SNIPPETS if snippet not in script_text]
    assert not missing, missing
    assert 'find "$BUGGY_SOURCE" -mindepth 1 -maxdepth 1 ! -name .gitkeep' in script_text
    assert 'rm -f "$BUGGY_SOURCE/.gitkeep"' in script_text
    assert 'cp "$TMP_CONTAINER:$CONTAINER_BUGGY_SOURCE/." "$BUGGY_SOURCE"' in script_text
    assert "--entrypoint bash" in script_text
    assert "CODEX" + "_ACCESS_TOKEN" not in script_text
    assert "~/.codex" not in script_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CLASSIFICATION, manifest
    assert manifest["path_recorded"] is False, manifest
    assert manifest["root_path_recorded"] is False, manifest
    assert manifest["private_script_relative_path"] == "run-lagent239.private.sh", manifest
    assert manifest["script_content_public"] is False, manifest
    assert manifest["script_checks"]["precheck_only_mode"] is True, manifest
    assert manifest["script_checks"]["observed_image_source_path_default"] is True, manifest
    assert manifest["script_checks"]["gitkeep_placeholder_safe"] is True, manifest
    assert manifest["script_checks"]["host_codex_phase"] is True, manifest
    assert manifest["script_checks"]["selected_container_eval_phase"] is True, manifest
    assert manifest["script_checks"]["entrypoint_eval_commands"] is True, manifest
    assert manifest["generator_boundary"]["codex_cli_invoked"] is False, manifest
    assert manifest["generator_boundary"]["docker_container_started"] is False, manifest
    assert manifest["later_script_boundary"]["will_invoke_host_codex_cli"] is True, manifest
    assert manifest["later_script_boundary"]["will_start_selected_container"] is True, manifest
    assert manifest["later_script_boundary"]["uses_entrypoint_eval_commands"] is True, manifest
    assert manifest["later_script_boundary"]["upload"] is False, manifest
    assert_no_forbidden_text(manifest)


def assert_payload(payload: dict[str, Any], *, appended: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == CLASSIFICATION, payload

    cli = payload["benchmark_cli"]
    assert cli["benchmark"] == BENCHMARK_ID, cli
    assert cli["command"] == "agentissue-codex-runner-flow", cli
    assert cli["tag"] == SELECTED_TAG, cli
    assert cli["private_runner_script_materialized"] is True, cli
    assert cli["private_runner_root_path_recorded"] is False, cli
    assert cli["private_runner_script_content_public"] is False, cli
    assert cli["real_runner_invoked"] is False, cli
    assert cli["real_codex_invoked"] is False, cli
    assert cli["real_docker_invoked"] is False, cli
    assert cli["auth_values_read"] is False, cli

    runner = payload["agentissue_private_runner_script"]
    assert runner["schema_version"] == CLASSIFICATION, runner
    assert runner["ready"] is True, runner
    assert runner["materialized"] is True, runner
    assert runner["path_recorded"] is False, runner
    assert runner["script_root_path_recorded"] is False, runner
    assert runner["script_relative_path"] == "run-lagent239.private.sh", runner
    assert runner["script_checks"]["precheck_only_mode"] is True, runner
    assert runner["script_checks"]["observed_image_source_path_default"] is True, runner
    assert runner["script_checks"]["gitkeep_placeholder_safe"] is True, runner
    assert runner["script_checks"]["host_codex_phase"] is True, runner
    assert runner["script_checks"]["entrypoint_eval_commands"] is True, runner
    assert runner["script_checks"]["compact_reducer_phase"] is True, runner
    assert runner["execution_boundary"]["codex_cli_invoked"] is False, runner
    assert runner["execution_boundary"]["docker_container_started"] is False, runner
    assert runner["later_script_boundary"]["will_invoke_host_codex_cli"] is True, runner
    assert runner["later_script_boundary"]["will_start_selected_container"] is True, runner

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["benchmark_id"] == BENCHMARK_ID, event
    assert event["mode"] == RUN_MODE, event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["leaderboard_evidence"] is False, event
    assert event["official_score_claim_allowed"] is False, event
    assert event["validation"]["all_passed"] is True, event
    assert event["validation"]["private_runner_script_materialized"] is True, event
    assert event["validation"]["script_renders_host_codex"] is True, event
    assert event["validation"]["script_renders_observed_image_source_path"] is True, event
    assert event["validation"]["script_renders_precheck_only"] is True, event
    assert event["validation"]["script_handles_gitkeep_placeholder"] is True, event
    assert event["validation"]["script_renders_selected_tag_eval"] is True, event
    assert event["validation"]["script_renders_entrypoint_eval_commands"] is True, event
    assert event["validation"]["script_renders_real_result_reducer"] is True, event
    assert event["validation"]["no_generator_codex_execution"] is True, event
    assert event["validation"]["no_generator_docker_execution"] is True, event

    assert_no_forbidden_text(cli)
    assert_no_forbidden_text(runner)
    assert_no_forbidden_text(event)


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
    assert summary["real_run"] is False, summary
    assert summary["validation"]["all_passed"] is True, summary
    assert summary["validation"]["private_runner_script_materialized"] is True, summary
    assert summary["validation"]["script_renders_host_codex"] is True, summary
    assert summary["validation"]["script_renders_observed_image_source_path"] is True, summary
    assert summary["validation"]["script_renders_precheck_only"] is True, summary
    assert summary["validation"]["script_handles_gitkeep_placeholder"] is True, summary
    assert summary["validation"]["script_renders_selected_tag_eval"] is True, summary
    assert summary["validation"]["script_renders_entrypoint_eval_commands"] is True, summary
    assert summary["validation"]["script_renders_real_result_reducer"] is True, summary
    assert_no_forbidden_text(summary)


def assert_roots_are_mutually_exclusive(
    registry_path: Path,
    runtime: Path,
    runner_root: Path,
) -> None:
    args = common_args(registry_path, runtime, runner_root) + [
        "--real-result-root",
        str(runner_root / "other-root"),
    ]
    result = run_cli(args, check=False)
    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is False, payload
    assert "at most one root option" in payload["error"], payload
    assert "--private-runner-root" in payload["error"], payload


def main() -> None:
    assert_doc_contract()
    with tempfile.TemporaryDirectory(prefix="agentissue-runner-private-script-") as tmp:
        registry_path, runtime, runner_root = write_fixture(Path(tmp))
        dry_payload = run_cli_json(common_args(registry_path, runtime, runner_root))
        assert_payload(dry_payload, appended=False)
        assert_materialized_files(runner_root)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime, runner_root)
            + [
                "--delivery-batch-scale",
                "multi_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ]
        )
        assert_payload(execute_payload, appended=True)
        assert_materialized_files(runner_root)
        assert_status_projection(registry_path, runtime)
        assert_roots_are_mutually_exclusive(registry_path, runtime, runner_root)

    print(
        "agentissue-bench-codex-cli-runner-private-script-smoke ok "
        f"mode={RUN_MODE} appended=True generator_no_execute=True"
    )


if __name__ == "__main__":
    main()
