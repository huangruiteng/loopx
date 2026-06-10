#!/usr/bin/env python3
"""Smoke-test active-user assisted Terminal-Bench treatment preflight."""

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

from goal_harness.status import collect_status  # noqa: E402


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "active-user-assisted-pilot-v0.md"
README = TOPIC_DIR / "README.md"

GOAL_ID = "terminal-bench-active-user-assisted-treatment-preflight-fixture"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_ID = "train-fasttext"
RUN_MODE = "codex_goal_harness_active_user_assisted_treatment_preflight"
WORKER_MODE = "codex_goal_harness_cli"
CLASSIFICATION = "terminal_bench_active_user_assisted_treatment_preflight_v0"
FIRST_BLOCKER = "missing_real_assisted_worker_observation"
LAUNCHER_PLAN_SCHEMA = "terminal_bench_active_user_private_launcher_plan_v0"

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "ARK" + "_BASE_URL=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "fixture-active-user-preflight-value",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]

REQUIRED_DOC_SNIPPETS = [
    "Active User Assisted Pilot V0",
    "active_user_assisted_pilot_v0",
    "active_user_simulator_injection_v0",
    "operator_simulator_run_v0",
    "assisted-collaboration claims",
    "cannot be used as an official Terminal-Bench score",
    "python3 examples/active-user-assisted-pilot-smoke.py",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-10T00:00:00+00:00\n"
        "---\n\n"
        "# Terminal-Bench Active User Assisted Treatment Preflight Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Build the active-user assisted treatment preflight.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-10T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "goal-harness-platform",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "heartbeat": {
                        "enabled": True,
                    },
                }
            ],
        },
    )
    return registry_path, runtime


def write_fake_command(bin_dir: Path, name: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_fake_surface_commands(root: Path) -> Path:
    bin_dir = root / "fake-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in ("uvx", "docker", "colima", "codex"):
        write_fake_command(bin_dir, name)
    return bin_dir


def run_cli(args: list[str], *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def run_cli_json(args: list[str], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_cli(args, env=env)
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def common_args(registry_path: Path, runtime: Path) -> list[str]:
    return [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "benchmark",
        "run",
        "terminal-bench",
        "--goal-id",
        GOAL_ID,
        "--mode",
        "codex-goal-harness",
        "--dataset",
        BENCHMARK_ID,
        "--include-task-name",
        TASK_ID,
        "--preflight-guard",
        "--active-cli-bridge",
        "--active-user-assisted-treatment",
        "--no-global-sync",
    ]


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 26000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    compact_text = " ".join(text.split())
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in compact_text]
    assert not missing, missing
    assert "active-user-assisted-pilot-v0.md" in readme, readme
    assert_public_safe(text)


def assert_preflight_guard(guard: dict[str, Any]) -> None:
    assert guard["schema_version"] == CLASSIFICATION, guard
    assert guard["first_blocker"] == FIRST_BLOCKER, guard
    assert guard["active_cli_bridge_enabled"] is True, guard
    assert guard["active_user_assisted_treatment"] is True, guard
    assert guard["simulator_setting"] == "deterministic_scripted_user", guard
    assert guard["simulator_to_worker_injection_channel_available"] is True, guard
    assert guard["interactive_user_message_injection_checked"] is True, guard
    assert guard["initial_prompt_only_is_not_active_intervention"] is True, guard
    assert guard["no_oracle_audit_required"] is True, guard
    assert guard["assisted_score_kept_separate_from_official"] is True, guard
    assert guard["claim_requires_worker_cli_calls"] is True, guard
    assert guard["required_worker_goal_harness_cli_call_total_min"] == 1, guard


def assert_channel_probe(channel: dict[str, Any]) -> None:
    assert channel["schema_version"] == "terminal_bench_active_user_simulator_injection_channel_v0", channel
    assert channel["channel_available"] is True, channel
    assert channel["first_blocker"] == FIRST_BLOCKER, channel
    assert channel["required_capability"] == "worker_observes_simulator_message_after_start", channel
    assert channel["current_agent_surface"] == "goal_harness_active_user_external_update_loop_v0", channel
    assert channel["direct_codex_chat_injection_available"] is False, channel
    assert channel["audited_external_update_loop_available"] is True, channel
    assert channel["initial_prompt_only_is_not_active_intervention"] is True, channel
    assert channel["no_user_message_injected"] is True, channel
    assert channel["model_api_invoked"] is False, channel
    assert channel["raw_transcript_recorded"] is False, channel
    assert channel["checked_channel_count"] == 4, channel
    checked = channel["checked_channels"]
    assert [item["channel"] for item in checked] == [
        "initial_prompt_instruction_append",
        "worker_goal_harness_cli_pull",
        "audited_external_update_loop",
        "interactive_worker_session_bridge",
    ], channel
    verdicts = {item["channel"]: item["verdict"] for item in checked}
    assert verdicts["initial_prompt_instruction_append"] == "rejected_for_active_intervention", channel
    assert verdicts["worker_goal_harness_cli_pull"] == "partial_worker_pull_not_user_push", channel
    assert verdicts["audited_external_update_loop"] == "available_worker_pull_channel", channel
    assert verdicts["interactive_worker_session_bridge"] == "optional_direct_chat_missing", channel
    assert channel["next_channel_requirement"] == (
        "wire_worker_prompt_to_poll_active_user_observe_during_assisted_treatment"
    ), channel
    assert channel["minimum_next_implementation"] == (
        "run a worker sample that observes a post-start active-user intervention"
    ), channel


def assert_compact_channel_probe(channel: dict[str, Any]) -> None:
    assert channel["schema_version"] == "terminal_bench_active_user_simulator_injection_channel_v0", channel
    assert channel["channel_available"] is True, channel
    assert channel["first_blocker"] == FIRST_BLOCKER, channel
    assert channel["checked_channel_count"] == 4, channel
    assert channel["checked_channel_names"] == [
        "initial_prompt_instruction_append",
        "worker_goal_harness_cli_pull",
        "audited_external_update_loop",
        "interactive_worker_session_bridge",
    ], channel
    assert channel["next_channel_requirement"] == (
        "wire_worker_prompt_to_poll_active_user_observe_during_assisted_treatment"
    ), channel


def assert_active_user_preflight(preflight: dict[str, Any], *, compact: bool = False) -> None:
    assert preflight["schema_version"] == CLASSIFICATION, preflight
    assert preflight["pilot_schema_version"] == "active_user_assisted_pilot_v0", preflight
    assert preflight["active_injection_schema_version"] == "active_user_simulator_injection_v0", preflight
    assert preflight["operator_simulator_run_schema_version"] == "operator_simulator_run_v0", preflight
    assert preflight["simulator_setting"] == "deterministic_scripted_user", preflight
    assert preflight["proactive_intervention_allowed"] is True, preflight
    assert preflight["directive_feedback_allowed"] is True, preflight
    assert preflight["artificial_mildness_required"] is False, preflight
    assert preflight["frequency_budget_required"] is True, preflight
    assert preflight["visibility_policy_required"] is True, preflight
    assert preflight["no_oracle_audit_required"] is True, preflight
    assert preflight["assisted_collaboration_claim_allowed"] is True, preflight
    assert preflight["official_score_claim_allowed"] is False, preflight
    assert preflight["leaderboard_claim_allowed"] is False, preflight
    assert (
        preflight["next_step"]
        == "wire_worker_prompt_to_poll_active_user_observe_during_assisted_treatment"
    ), preflight
    channel = preflight["simulator_to_worker_injection_channel"]
    if compact:
        assert_compact_channel_probe(channel)
    else:
        assert_channel_probe(channel)
    assert_private_launcher_plan(preflight["private_launcher_plan"])


def assert_private_launcher_plan(plan: dict[str, Any]) -> None:
    assert plan["schema_version"] == LAUNCHER_PLAN_SCHEMA, plan
    assert plan["launch_surface"] == "private_no_upload_terminal_bench_single_worker", plan
    assert plan["ready"] is True, plan
    assert plan["first_blocker"] == "ready_for_private_no_upload_assisted_worker_sample", plan
    assert plan["required_capability"] == "worker_observes_simulator_message_after_start", plan
    assert plan["worker_start_marker"] == "worker_start_seq", plan
    assert "goal-harness-active-user-interventions.jsonl" in plan["active_user_feed_jsonl"], plan
    assert "goal-harness-active-user-observation.json" in plan["active_user_observation_json"], plan
    assert plan["sequence_steps"] == [
        "launch_single_codex_goal_harness_worker_with_no_upload",
        "record_worker_start_seq_before_first_poll",
        "append_public_safe_simulator_intervention_with_seq_gt_worker_start_seq",
        "worker_polls_active_user_observe_after_start",
        "ingest_worker_observation_as_non_official_collaboration_evidence",
    ], plan
    assert "worker_observation_proof_true" in plan["required_evidence"], plan
    assert "leaderboard_or_upload_requested" in plan["stop_conditions"], plan
    assert plan["claim_boundary"]["assisted_collaboration_claim_allowed"] is True, plan
    assert plan["claim_boundary"]["official_score_claim_allowed"] is False, plan
    assert plan["claim_boundary"]["leaderboard_claim_allowed"] is False, plan
    assert plan["claim_boundary"]["official_score_must_remain_separate"] is True, plan
    assert plan["public_boundary"]["no_upload"] is True, plan
    assert plan["public_boundary"]["raw_paths_recorded"] is False, plan
    assert plan["public_boundary"]["raw_transcript_recorded"] is False, plan
    assert plan["public_boundary"]["credential_values_recorded"] is False, plan


def assert_payload(payload: dict[str, Any], *, appended: bool) -> None:
    assert payload["ok"] is True, payload
    assert payload["appended"] is appended, payload
    assert payload["dry_run"] is (not appended), payload
    assert payload["classification"] == CLASSIFICATION, payload
    assert "active-user-observe" in payload["recommended_action"], payload

    cli = payload["benchmark_cli"]
    assert cli["benchmark"] == "terminal-bench", cli
    assert cli["mode"] == "codex-goal-harness", cli
    assert cli["preflight_guard"] is True, cli
    assert cli["active_cli_bridge"] is True, cli
    assert cli["active_user_assisted_treatment"] is True, cli
    assert cli["real_runner_invoked"] is False, cli
    assert cli["real_codex_invoked"] is False, cli
    assert cli["auth_values_read"] is False, cli

    event = payload["benchmark_run"]
    assert event["schema_version"] == "benchmark_run_v0", event
    assert event["source_runner"] == "goal_harness_terminal_bench_active_user_assisted_treatment_preflight", event
    assert event["benchmark_id"] == BENCHMARK_ID, event
    assert event["mode"] == RUN_MODE, event
    assert event["worker_mode"] == WORKER_MODE, event
    assert event["first_blocker"] == FIRST_BLOCKER, event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["official_task_score"]["kind"] == "not_run", event
    assert event["goal_harness_worker_cli_bridge_available"] is True, event
    assert event["goal_harness_worker_cli_bridge_trace_observed"] is False, event
    assert event["planned_worker_goal_harness_cli_call_total"] == 2, event
    assert event["worker_goal_harness_cli_call_total"] == 0, event
    assert event["assisted_collaboration_claim_allowed"] is True, event
    assert event["official_score_claim_allowed"] is False, event
    assert event["active_user_simulator_injection_channel_available"] is True, event
    assert_private_launcher_plan(event["active_user_private_launcher_plan"])
    launch_summary = event["private_runner_launch_summary"]
    assert launch_summary["active_user_writable_mount_requested"] is True, launch_summary
    assert launch_summary["active_user_writable_mount_count"] == 1, launch_summary
    assert launch_summary["raw_paths_recorded"] is False, launch_summary
    assert event["validation"]["all_passed"] is True, event
    assert event["validation"]["failed_checks"] == [], event
    assert event["validation"]["active_user_assisted_treatment_preflight"] is True, event
    assert event["validation"]["active_user_simulator_contract_checked"] is True, event
    assert event["validation"]["simulator_to_worker_injection_channel_checked"] is True, event
    assert event["validation"]["simulator_to_worker_injection_channel_probe_checked"] is True, event
    assert event["validation"]["simulator_to_worker_external_update_loop_available"] is True, event
    assert event["validation"]["real_assisted_worker_observation_missing"] is True, event
    assert event["validation"]["no_real_user_message_injected"] is True, event
    assert event["validation"]["no_model_backed_simulator_invoked"] is True, event
    assert event["validation"]["no_oracle_audit_required"] is True, event
    assert event["validation"]["assisted_score_kept_separate_from_official"] is True, event

    counters = event["interaction_counters"]
    assert counters["goal_harness_cli_calls"]["total"] == 0, counters
    assert counters["case_result_writeback"] == "not_observed_active_user_assisted_treatment_preflight", counters
    assert (
        counters["counter_trust_level"]
        == "active_user_assisted_treatment_preflight_external_update_loop_no_worker_observation"
    ), counters
    assert_preflight_guard(event["preflight_guard"])
    assert_active_user_preflight(event["active_user_assisted_treatment_preflight"], compact=True)
    assert_public_safe(payload)


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
    assert summary["worker_mode"] == WORKER_MODE, summary
    assert summary["benchmark_id"] == BENCHMARK_ID, summary
    assert summary["first_blocker"] == FIRST_BLOCKER, summary
    assert summary["assisted_collaboration_claim_allowed"] is True, summary
    assert summary["official_score_claim_allowed"] is False, summary
    assert summary["active_user_simulator_injection_channel_available"] is True, summary
    assert_private_launcher_plan(summary["active_user_private_launcher_plan"])
    assert_preflight_guard(summary["preflight_guard"])
    assert_active_user_preflight(summary["active_user_assisted_treatment_preflight"], compact=True)
    assert_public_safe(summary)


def assert_help_exposes_active_user_flag() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "benchmark",
            "run",
            "terminal-bench",
            "--help",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert "--active-user-assisted-treatment" in result.stdout, result.stdout


def main() -> None:
    assert_doc_contract()
    assert_help_exposes_active_user_flag()
    with tempfile.TemporaryDirectory(
        prefix="terminal-bench-active-user-treatment-preflight-"
    ) as tmp:
        root = Path(tmp)
        registry_path, runtime = write_fixture(root)
        fake_bin = write_fake_surface_commands(root)
        env = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "CODEX_FORCE_AUTH_JSON": "fixture-active-user-preflight-value",
        }
        dry_payload = run_cli_json(common_args(registry_path, runtime), env=env)
        assert_payload(dry_payload, appended=False)

        execute_payload = run_cli_json(
            common_args(registry_path, runtime)
            + [
                "--delivery-batch-scale",
                "single_surface",
                "--delivery-outcome",
                "outcome_progress",
                "--execute",
            ],
            env=env,
        )
        assert_payload(execute_payload, appended=True)
        assert_status_projection(registry_path, runtime)

    print(
        "terminal-bench-active-user-assisted-treatment-preflight-smoke ok "
        f"mode={RUN_MODE} first_blocker={FIRST_BLOCKER}"
    )


if __name__ == "__main__":
    main()
