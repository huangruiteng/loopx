from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from ..delivery_outcome import DeliveryOutcome


AGENTISSUE_BENCHMARK_ID = "agentissue-bench"
AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_dry_run_wrapper_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_BENCHMARK_RUN_MODE = (
    "agentissue_codex_cli_runner_dry_run_wrapper"
)
AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_synthetic_staging_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_MODE = (
    "agentissue_codex_cli_runner_synthetic_staging_fixture"
)
AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_execution_gate_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_MODE = (
    "agentissue_codex_cli_runner_execution_gate"
)
AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_first_run_handoff_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_MODE = (
    "agentissue_codex_cli_runner_first_run_handoff_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_workflow_check_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_MODE = (
    "agentissue_codex_cli_runner_workflow_check_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_run_gate_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_MODE = (
    "agentissue_codex_cli_runner_run_gate_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_target_handoff_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_MODE = (
    "agentissue_codex_cli_runner_target_handoff_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_real_result_reducer_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_MODE = (
    "agentissue_codex_cli_runner_real_result_reducer"
)
AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_private_script_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_MODE = (
    "agentissue_codex_cli_runner_private_script"
)
AGENTISSUE_CODEX_CLI_RUNNER_SOURCE_RUNNER = (
    "loopx_agentissue_codex_cli_runner"
)
AGENTISSUE_DEFAULT_TAG = "lagent_239"
AGENTISSUE_DEFAULT_IMAGE = "alfin06/agentissue-bench:lagent_239"
AGENTISSUE_PATCH_RELATIVE_PATH = "Patches/lagent_239/attempt.patch"


def _agentissue_public_label(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("agentissue label is required")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", text):
        raise ValueError("agentissue label must be public-safe")
    return text[:limit]


def build_agentissue_codex_cli_runner_wrapper(
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
    job_root_placeholder: str = "<abs-private-job-root>",
) -> dict[str, Any]:
    """Build a dry-run-default AgentIssue-Bench Codex CLI runner wrapper.

    The wrapper deliberately renders command and staging shapes only. It never
    calls Codex, Docker, model APIs, or benchmark helpers; callers that append
    the embedded benchmark_run_v0 are recording readiness, not a task score.
    """

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner wrapper currently only supports selected tag lagent_239"
        )
    codex = _agentissue_public_label(codex_binary, limit=80)
    docker = _agentissue_public_label(docker_binary, limit=80)
    image = AGENTISSUE_DEFAULT_IMAGE
    buggy_source = f"{job_root_placeholder}/buggy-source"
    context_dir = f"{job_root_placeholder}/context"
    patch_dir = f"{job_root_placeholder}/Patches/lagent_239"
    prompt_path = f"{context_dir}/prompt.md"
    last_message = f"{job_root_placeholder}/codex-last-message.txt"
    compact_run_path = f"{job_root_placeholder}/benchmark_run.compact.json"

    phase_order = [
        "prepare_private_job_root",
        "write_public_issue_context_to_private_context",
        "pull_selected_image_opt_in",
        "extract_buggy_source_from_selected_container_opt_in",
        "initialize_git_baseline_in_buggy_source",
        "run_host_local_codex_cli_patch_worker_opt_in",
        "write_attempt_patch_from_buggy_source_git_diff",
        "evaluate_selected_tag_container_opt_in",
        "reduce_compact_public_evidence",
    ]
    codex_argv = [
        codex,
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--cd",
        buggy_source,
        "--add-dir",
        job_root_placeholder,
        "--output-last-message",
        last_message,
        prompt_path,
    ]
    eval_argv = [
        docker,
        "run",
        "--platform",
        "linux/amd64",
        "--rm",
        "--entrypoint",
        "bash",
        "-v",
        f"{patch_dir}:/patches:ro",
        image,
        "-c",
        "<apply_patch_and_test_patched>",
    ]
    wrapper = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": image,
        "dry_run_default": True,
        "real_execution_done": False,
        "single_tag_only": True,
        "staging_plan": {
            "private_job_root_placeholder": job_root_placeholder,
            "path_recorded": False,
            "buggy_source_placeholder": buggy_source,
            "context_dir_placeholder": context_dir,
            "patch_dir_placeholder": patch_dir,
            "prompt_path_placeholder": prompt_path,
            "last_message_placeholder": last_message,
            "compact_run_placeholder": compact_run_path,
            "phase_order": phase_order,
        },
        "commands": {
            "codex_patch_worker": {
                "argv": codex_argv,
                "runs_on_host": True,
                "runs_after_buggy_source_extraction": True,
                "copy_codex_home": False,
                "auth_material_synced": False,
                "worker_network_allowed": False,
                "worker_docker_allowed": False,
                "reads_fixed_diff_or_oracle": False,
                "execute_by_default": False,
            },
            "patch_export": {
                "input_source": "buggy_source_git_diff",
                "output_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
                "raw_patch_public": False,
                "patch_hash_public": True,
            },
            "single_tag_eval": {
                "argv": eval_argv,
                "official_all_tag_helper_allowed": False,
                "docker_env_credentials": False,
                "upload": False,
                "submit": False,
                "public_ranking_path": False,
                "execute_by_default": False,
            },
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "raw_issue_text_read": False,
            "raw_patch_recorded": False,
            "raw_log_recorded": False,
            "credential_values_recorded": False,
        },
        "reducer_contract": {
            "allowed_public_fields": [
                "tag",
                "image_digest",
                "patch_sha256",
                "patch_bytes",
                "changed_file_count",
                "hunk_count",
                "exit_code",
                "resolved",
                "duration_seconds",
                "log_sha256",
                "no_upload",
                "no_submit",
                "no_public_ranking_path",
            ],
            "raw_issue_text_public": False,
            "raw_patch_public": False,
            "raw_log_public": False,
            "absolute_paths_public": False,
        },
        "stop_rules": {
            "stop_before_codex_auth_sync": True,
            "stop_before_current_head_patch_source": True,
            "stop_before_fixed_diff_or_oracle_read": True,
            "stop_before_all_tag_helpers": True,
            "stop_before_upload_submit_or_public_ranking": True,
            "stop_before_raw_artifact_publication": True,
            "stop_before_destructive_git_or_production": True,
        },
    }
    benchmark_run = {
        "schema_version": "benchmark_run_v0",
        "source_runner": AGENTISSUE_CODEX_CLI_RUNNER_SOURCE_RUNNER,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "job_name": "agentissue_lagent_239_codex_cli_runner_dry_run",
        "mode": AGENTISSUE_CODEX_CLI_RUNNER_BENCHMARK_RUN_MODE,
        "worker_mode": "trusted_host_codex_cli_dry_run_wrapper",
        "trace_publicness": "compact_public_no_issue_text_no_patch_no_logs",
        "first_blocker": "dry_run_wrapper_only_no_real_case",
        "score_failure_attribution": "not_run_wrapper_readiness_only",
        "real_run": False,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_score_comparable_to_native_codex": False,
        "official_score_claim_allowed": False,
        "control_plane_score_applicable": True,
        "official_task_score": {
            "kind": "agentissue_bench_single_tag_container_eval_not_run",
            "status": "not_run",
            "value": None,
            "resolved": None,
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 1,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
        },
        "validation": {
            "runner_wrapper_built": True,
            "dry_run_default": True,
            "single_tag_only": True,
            "absolute_private_job_root_placeholders": True,
            "buggy_source_before_codex_patch": True,
            "patch_from_buggy_source_git_diff": True,
            "selected_tag_eval_only": True,
            "compact_reducer_declared": True,
            "no_codex_cli_invoked": True,
            "no_model_api_invoked": True,
            "no_docker_container_started": True,
            "no_patch_generated": True,
            "no_patch_evaluated": True,
            "no_auth_material_sync": True,
            "no_current_public_head_patch_source": True,
            "no_fixed_diff_or_oracle_read": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
        },
        "trials": [
            {
                "task_id": tag,
                "trial_name": tag,
                "source": "selected_public_tag",
                "exception_type": "dry_run_wrapper_only_no_real_case",
                "trajectory_present": False,
                "artifact_manifest_present": False,
                "trial_result_present": False,
            }
        ],
        "failure_attribution_labels": [
            "no_execution_wrapper_only",
            "ready_for_synthetic_job_root_staging",
        ],
        "evidence_files": [
            "benchmark_run.compact.json",
            "runner-flow-plan.public.json",
        ],
        "stop_conditions": [
            "codex_auth_sync_requested",
            "current_head_patch_source_requested",
            "fixed_diff_or_oracle_requested",
            "all_tag_helper_requested",
            "upload_submit_or_public_ranking_requested",
            "raw_artifact_publication_requested",
        ],
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }
    return {
        **wrapper,
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "run this wrapper against a synthetic private job root, then gate any real "
            "Codex/Docker execution behind explicit opt-in"
        ),
    }


def materialize_agentissue_codex_cli_runner_synthetic_staging(
    staging_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a synthetic AgentIssue runner job root without real task material."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner synthetic staging currently only supports selected tag lagent_239"
        )
    root = Path(staging_root).expanduser()
    if not str(root):
        raise ValueError("synthetic staging root is required")

    wrapper = build_agentissue_codex_cli_runner_wrapper(
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    context_dir = root / "context"
    buggy_source_dir = root / "buggy-source"
    patch_dir = root / "Patches" / tag
    prompt_path = context_dir / "prompt.md"
    runner_plan_path = root / "runner-flow-plan.public.json"
    compact_run_path = root / "benchmark_run.compact.json"

    prompt_text = (
        "# Synthetic AgentIssue-Bench lagent_239 Prompt Placeholder\n\n"
        "This fixture contains no real issue statement, source diff, test patch, "
        "expected patch, auth value, trajectory, screenshot, or raw log.\n\n"
        f"Expected patch output path: {AGENTISSUE_PATCH_RELATIVE_PATH}\n\n"
        "Run boundary: do not invoke Codex, Docker, model APIs, upload, submit, "
        "or public ranking paths from this fixture.\n"
    )
    benchmark_run = json.loads(json.dumps(wrapper["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_synthetic_staging",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_MODE,
            "worker_mode": "trusted_host_codex_cli_synthetic_staging_fixture",
            "first_blocker": "synthetic_staging_only_no_real_case",
            "score_failure_attribution": "not_run_synthetic_staging_only",
            "failure_attribution_labels": [
                "synthetic_staging_fixture_only",
                "ready_for_guarded_private_source_extraction_gate",
            ],
            "evidence_files": [
                "benchmark_run.compact.json",
                "runner-flow-plan.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "synthetic_private_job_root_materialized": True,
            "context_dir_created": True,
            "buggy_source_dir_created": True,
            "patch_dir_created": True,
            "prompt_placeholder_written": True,
            "prompt_path_rendered": True,
            "patch_output_parent_reserved": True,
            "compact_run_filename_reserved": True,
            "runner_flow_plan_public_json_written": True,
            "no_absolute_paths_public": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "synthetic_staging_only_no_real_case"

    runner_plan = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "path_recorded": False,
        "relative_paths": {
            "context_dir": "context",
            "buggy_source_dir": "buggy-source",
            "patch_dir": "Patches/lagent_239",
            "prompt": "context/prompt.md",
            "expected_patch": AGENTISSUE_PATCH_RELATIVE_PATH,
            "compact_run": "benchmark_run.compact.json",
            "runner_plan": "runner-flow-plan.public.json",
        },
        "command_placeholders": wrapper["commands"],
        "execution_boundary": wrapper["execution_boundary"],
        "stop_rules": wrapper["stop_rules"],
    }

    context_dir.mkdir(parents=True, exist_ok=True)
    buggy_source_dir.mkdir(parents=True, exist_ok=True)
    patch_dir.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    (buggy_source_dir / ".gitkeep").write_text("", encoding="utf-8")
    (patch_dir / ".gitkeep").write_text("", encoding="utf-8")
    runner_plan_path.write_text(
        json.dumps(runner_plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    created_relative_paths = [
        "context/",
        "context/prompt.md",
        "buggy-source/",
        "buggy-source/.gitkeep",
        "Patches/lagent_239/",
        "Patches/lagent_239/.gitkeep",
        "runner-flow-plan.public.json",
        "benchmark_run.compact.json",
    ]
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "staging_root_path_recorded": False,
        "created_relative_paths": created_relative_paths,
        "prompt_relative_path": "context/prompt.md",
        "expected_patch_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
        "compact_run_relative_path": "benchmark_run.compact.json",
        "runner_plan_relative_path": "runner-flow-plan.public.json",
        "command_rendering_checks": {
            "codex_argv_uses_prompt_placeholder": True,
            "codex_argv_uses_buggy_source_placeholder": True,
            "eval_argv_uses_selected_image": True,
            "patch_output_parent_reserved": True,
            "compact_reducer_filename_reserved": True,
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "raw_issue_text_read": False,
            "raw_patch_recorded": False,
            "raw_log_recorded": False,
            "credential_values_recorded": False,
        },
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "add a guarded opt-in real-source extraction and host-Codex execution "
            "gate for lagent_239, still defaulting to no-execute"
        ),
    }


def materialize_agentissue_codex_cli_runner_execution_gate(
    gate_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute gate packet for the first real AgentIssue runner step."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner execution gate currently only supports selected tag lagent_239"
        )
    root = Path(gate_root).expanduser()
    staging = materialize_agentissue_codex_cli_runner_synthetic_staging(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    wrapper = build_agentissue_codex_cli_runner_wrapper(
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    docker = _agentissue_public_label(docker_binary, limit=80)
    image = AGENTISSUE_DEFAULT_IMAGE
    container_label = "<tmp-agentissue-lagent-239-container>"
    job_root = "<abs-private-job-root>"
    buggy_source = f"{job_root}/buggy-source"
    patch_path = f"{job_root}/{AGENTISSUE_PATCH_RELATIVE_PATH}"
    gate_path = root / "execution-gate.public.json"
    compact_run_path = root / "benchmark_run.compact.json"

    extraction_commands = {
        "inspect_selected_image": [docker, "image", "inspect", image],
        "create_selected_container": [
            docker,
            "create",
            "--name",
            container_label,
            image,
        ],
        "copy_buggy_source": [
            docker,
            "cp",
            f"{container_label}:/workspace/.",
            buggy_source,
        ],
        "remove_selected_container": [docker, "rm", container_label],
    }
    git_baseline_commands = {
        "init": ["git", "-C", buggy_source, "init"],
        "add": ["git", "-C", buggy_source, "add", "."],
        "commit": [
            "git",
            "-C",
            buggy_source,
            "commit",
            "-m",
            "agentissue-bench-buggy-source-baseline",
        ],
    }
    patch_export = {
        "input_source": "buggy_source_git_diff",
        "command_shape": f"git -C {buggy_source} diff --binary > {patch_path}",
        "output_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
    }
    gate = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": image,
        "path_recorded": False,
        "default_mode": "no_execute",
        "future_opt_in_required": True,
        "single_tag_only": True,
        "relative_paths": {
            "context_prompt": "context/prompt.md",
            "buggy_source_dir": "buggy-source",
            "attempt_patch": AGENTISSUE_PATCH_RELATIVE_PATH,
            "execution_gate": "execution-gate.public.json",
            "compact_run": "benchmark_run.compact.json",
        },
        "source_extraction_gate": {
            "commands": extraction_commands,
            "selected_container_only": True,
            "execute_by_default": False,
            "docker_invoked": False,
            "docker_pull_or_start_allowed": False,
        },
        "private_git_baseline_gate": {
            "commands": git_baseline_commands,
            "execute_by_default": False,
            "destructive_git": False,
        },
        "host_codex_gate": {
            "command": wrapper["commands"]["codex_patch_worker"],
            "execute_by_default": False,
            "codex_cli_invoked": False,
            "auth_material_synced": False,
        },
        "patch_output_gate": patch_export,
        "eval_gate": wrapper["commands"]["single_tag_eval"],
        "stop_rules": {
            **wrapper["stop_rules"],
            "stop_before_real_source_extraction_without_future_gate": True,
            "stop_before_host_codex_execution_without_future_gate": True,
        },
    }

    benchmark_run = json.loads(json.dumps(staging["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_execution_gate",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_gate",
            "first_blocker": "execution_gate_only_no_real_case",
            "score_failure_attribution": "not_run_execution_gate_only",
            "failure_attribution_labels": [
                "execution_gate_fixture_only",
                "ready_for_future_run_specific_opt_in",
            ],
            "evidence_files": [
                "execution-gate.public.json",
                "benchmark_run.compact.json",
                "runner-flow-plan.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "execution_gate_materialized": True,
            "synthetic_staging_reused": True,
            "selected_container_source_extraction_commands_rendered": True,
            "private_git_baseline_commands_rendered": True,
            "host_codex_command_readiness_rendered": True,
            "attempt_patch_output_placement_checked": True,
            "compact_run_filename_checked": True,
            "future_execution_opt_in_required": True,
            "no_real_source_extraction": True,
            "no_real_codex_execution": True,
            "no_docker_pull_or_start": True,
            "no_auth_sync_to_shared_host": True,
            "no_fixed_diff_or_oracle_read": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "execution_gate_only_no_real_case"

    gate_path.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": image,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "gate_root_path_recorded": False,
        "synthetic_staging": {
            "schema_version": staging["schema_version"],
            "ready": staging["ready"],
            "created_relative_paths": staging["created_relative_paths"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *staging["created_relative_paths"],
            "execution-gate.public.json",
        ],
        "gate_relative_path": "execution-gate.public.json",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "attempt_patch_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
        "gate_checks": {
            "selected_container_source_extraction_commands_rendered": True,
            "private_git_baseline_commands_rendered": True,
            "host_codex_command_readiness_rendered": True,
            "attempt_patch_output_placement_checked": True,
            "future_execution_opt_in_required": True,
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "source_extracted": False,
            "git_baseline_created": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "credential_values_recorded": False,
            "auth_material_synced": False,
        },
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "build a no-execute first-run handoff packet for lagent_239"
        ),
    }


def materialize_agentissue_codex_cli_runner_first_run_handoff(
    handoff_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute first-run handoff packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner first-run handoff currently only supports selected tag lagent_239"
        )
    root = Path(handoff_root).expanduser()
    gate = materialize_agentissue_codex_cli_runner_execution_gate(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    handoff_path = root / "first-run-handoff.public.json"
    handoff_markdown_path = root / "first-run-handoff.md"
    compact_run_path = root / "benchmark_run.compact.json"

    no_execute_cli_argv = [
        "loopx",
        "benchmark",
        "agentissue-codex-runner-flow",
        "--goal-id",
        "<goal-id>",
        "--tag",
        tag,
        "--execution-gate-root",
        "<private-gate-root>",
        "--delivery-batch-scale",
        "multi_surface",
        "--delivery-outcome",
        DeliveryOutcome.OUTCOME_PROGRESS.value,
        "--execute",
    ]
    safety_checklist = [
        {
            "item": "private_job_root_selected",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": False,
        },
        {
            "item": "codex_auth_stays_on_host",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
        {
            "item": "no_codex_home_sync_to_shared_host",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
        {
            "item": "selected_container_source_extraction_planned",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": False,
        },
        {
            "item": "attempt_patch_compact_reducer_planned",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
        {
            "item": "upload_submit_public_ranking_disabled",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
    ]
    handoff = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "path_recorded": False,
        "default_mode": "no_execute",
        "later_operator_triggered_e2e": True,
        "real_run_done": False,
        "exact_command_shape": {
            "argv": no_execute_cli_argv,
            "runs_real_benchmark": False,
            "appends_compact_no_run_event": True,
        },
        "private_artifact_boundary": {
            "root_placeholder": "<private-gate-root>",
            "root_path_recorded": False,
            "public_relative_files": [
                "runner-flow-plan.public.json",
                "execution-gate.public.json",
                "first-run-handoff.public.json",
                "first-run-handoff.md",
                "benchmark_run.compact.json",
            ],
            "private_relative_dirs": [
                "context/",
                "buggy-source/",
                "Patches/lagent_239/",
            ],
            "raw_artifacts_public": False,
            "absolute_paths_public": False,
        },
        "expected_compact_outputs": {
            "benchmark_run_mode": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_MODE,
            "compact_run": "benchmark_run.compact.json",
            "history_event": "benchmark_run_v0",
            "official_score_claim_allowed": False,
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
        "budget_auth_boundary": {
            "codex_auth_values_read": False,
            "codex_home_synced": False,
            "model_api_invoked": False,
            "model_budget_spent_by_packet": False,
            "docker_invoked_by_packet": False,
            "shared_remote_host_receives_codex_auth": False,
        },
        "safety_checklist": safety_checklist,
        "no_execute_assertions": {
            "source_extracted": False,
            "codex_cli_invoked": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "destructive_git": False,
            "production_action": False,
        },
    }
    handoff_markdown = (
        "# AgentIssue-Bench lagent_239 First-Run Handoff\n\n"
        "This packet is no-execute. It names the command shape, private artifact "
        "boundary, compact outputs, budget/auth boundary, and safety checklist "
        "for a later operator-triggered e2e run.\n\n"
        "## Command Shape\n\n"
        "```text\n"
        + " ".join(no_execute_cli_argv)
        + "\n```\n\n"
        "## Boundary\n\n"
        "- Codex auth stays on the host and is not copied to a shared machine.\n"
        "- Public files are limited to `*.public.json`, `*.compact.json`, and this packet.\n"
        "- No source extraction, Docker start, Codex invocation, patch generation, "
        "evaluation, upload, submit, public ranking, destructive git, or production "
        "action is performed by this packet.\n"
    )

    benchmark_run = json.loads(json.dumps(gate["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_first_run_handoff",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_first_run_handoff",
            "first_blocker": "first_run_handoff_only_no_real_case",
            "score_failure_attribution": "not_run_first_run_handoff_only",
            "failure_attribution_labels": [
                "first_run_handoff_packet_only",
                "ready_for_later_operator_triggered_e2e_run",
            ],
            "evidence_files": [
                "first-run-handoff.public.json",
                "first-run-handoff.md",
                "execution-gate.public.json",
                "benchmark_run.compact.json",
                "runner-flow-plan.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "first_run_handoff_materialized": True,
            "exact_command_shape_rendered": True,
            "private_artifact_boundary_declared": True,
            "expected_compact_outputs_declared": True,
            "budget_auth_boundary_declared": True,
            "safety_checklist_declared": True,
            "no_execute_packet": True,
            "no_codex_auth_value_read": True,
            "no_codex_home_sync": True,
            "no_model_budget_spent_by_packet": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "first_run_handoff_only_no_real_case"

    handoff_path.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    handoff_markdown_path.write_text(handoff_markdown, encoding="utf-8")
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "handoff_root_path_recorded": False,
        "execution_gate": {
            "schema_version": gate["schema_version"],
            "ready": gate["ready"],
            "gate_relative_path": gate["gate_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *gate["created_relative_paths"],
            "first-run-handoff.public.json",
            "first-run-handoff.md",
        ],
        "handoff_relative_path": "first-run-handoff.public.json",
        "handoff_markdown_relative_path": "first-run-handoff.md",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "handoff_checks": {
            "exact_command_shape_rendered": True,
            "private_artifact_boundary_declared": True,
            "expected_compact_outputs_declared": True,
            "budget_auth_boundary_declared": True,
            "safety_checklist_declared": True,
            "later_operator_triggered_e2e": True,
        },
        "execution_boundary": handoff["no_execute_assertions"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "use the no-execute first-run handoff packet as the checklist for a "
            "later operator-triggered AgentIssue-Bench lagent_239 e2e run"
        ),
    }


def materialize_agentissue_codex_cli_runner_workflow_check(
    workflow_check_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute workflow check packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner workflow check currently only supports selected tag lagent_239"
        )
    root = Path(workflow_check_root).expanduser()
    handoff = materialize_agentissue_codex_cli_runner_first_run_handoff(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    runner_plan_path = root / "runner-flow-plan.public.json"
    gate_path = root / "execution-gate.public.json"
    handoff_path = root / "first-run-handoff.public.json"
    workflow_path = root / "workflow-check.public.json"
    compact_run_path = root / "benchmark_run.compact.json"

    runner_plan = json.loads(runner_plan_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    handoff_public = json.loads(handoff_path.read_text(encoding="utf-8"))

    codex_command = runner_plan["command_placeholders"]["codex_patch_worker"]
    eval_command = runner_plan["command_placeholders"]["single_tag_eval"]
    patch_export = runner_plan["command_placeholders"]["patch_export"]
    budget_auth = handoff_public["budget_auth_boundary"]
    no_execute = handoff_public["no_execute_assertions"]
    required_public_files = [
        "runner-flow-plan.public.json",
        "execution-gate.public.json",
        "first-run-handoff.public.json",
        "first-run-handoff.md",
        "workflow-check.public.json",
        "benchmark_run.compact.json",
    ]
    required_private_dirs = [
        "context/",
        "buggy-source/",
        "Patches/lagent_239/",
    ]
    checks = {
        "single_selected_tag": runner_plan["selected_tag"] == gate["selected_tag"] == handoff_public["selected_tag"] == tag,
        "selected_image_consistent": runner_plan["selected_image"] == gate["selected_image"] == handoff_public["selected_image"],
        "source_extracted_before_codex": bool(codex_command.get("runs_after_buggy_source_extraction")),
        "host_codex_uses_ephemeral": "--ephemeral" in codex_command.get("argv", []),
        "host_codex_auth_not_synced": codex_command.get("auth_material_synced") is False and budget_auth["codex_home_synced"] is False,
        "worker_no_network_or_docker": codex_command.get("worker_network_allowed") is False and codex_command.get("worker_docker_allowed") is False,
        "patch_from_buggy_source_git_diff": patch_export["input_source"] == "buggy_source_git_diff",
        "attempt_patch_relative_path": patch_export["output_relative_path"] == AGENTISSUE_PATCH_RELATIVE_PATH,
        "single_tag_eval_no_upload_submit": eval_command["upload"] is False and eval_command["submit"] is False,
        "single_tag_eval_no_public_ranking": eval_command["public_ranking_path"] is False,
        "no_execute_packet": all(value is False for value in no_execute.values()),
        "public_files_compact_or_public": all(
            path.endswith((".public.json", ".compact.json", ".md"))
            for path in required_public_files
        ),
        "private_dirs_not_public_artifacts": all(path.endswith("/") for path in required_private_dirs),
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    workflow_check = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": not failed_checks,
        "materialized": True,
        "path_recorded": False,
        "default_mode": "no_execute",
        "input_packets": {
            "runner_plan": "runner-flow-plan.public.json",
            "execution_gate": "execution-gate.public.json",
            "first_run_handoff": "first-run-handoff.public.json",
        },
        "required_public_files": required_public_files,
        "required_private_dirs": required_private_dirs,
        "workflow_checks": checks,
        "failed_checks": failed_checks,
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "source_extracted": False,
            "git_baseline_created": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "credential_values_recorded": False,
            "auth_material_synced": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
        },
        "stop_before_later_e2e_unless": [
            "private_job_root_selected",
            "operator_explicitly_triggers_real_run",
            "runner_artifact_reducer_writes_compact_public_result",
        ],
    }

    benchmark_run = json.loads(json.dumps(handoff["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_workflow_check",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_workflow_check",
            "first_blocker": "workflow_check_only_no_real_case",
            "score_failure_attribution": "not_run_workflow_check_only",
            "failure_attribution_labels": [
                "workflow_check_packet_only",
                "ready_for_later_operator_triggered_e2e_run"
                if not failed_checks
                else "workflow_check_failed_before_real_run",
            ],
            "evidence_files": required_public_files,
        }
    )
    benchmark_run["validation"].update(
        {
            "workflow_check_materialized": True,
            "workflow_check_all_passed": not failed_checks,
            "workflow_check_failed_checks": failed_checks,
            "single_selected_tag": checks["single_selected_tag"],
            "selected_image_consistent": checks["selected_image_consistent"],
            "source_extracted_before_codex": checks["source_extracted_before_codex"],
            "host_codex_uses_ephemeral": checks["host_codex_uses_ephemeral"],
            "host_codex_auth_not_synced": checks["host_codex_auth_not_synced"],
            "worker_no_network_or_docker": checks["worker_no_network_or_docker"],
            "patch_from_buggy_source_git_diff": checks["patch_from_buggy_source_git_diff"],
            "single_tag_eval_no_upload_submit": checks["single_tag_eval_no_upload_submit"],
            "single_tag_eval_no_public_ranking": checks["single_tag_eval_no_public_ranking"],
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "workflow_check_only_no_real_case"

    workflow_path.write_text(
        json.dumps(workflow_check, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": not failed_checks,
        "materialized": True,
        "path_recorded": False,
        "workflow_check_root_path_recorded": False,
        "first_run_handoff": {
            "schema_version": handoff["schema_version"],
            "ready": handoff["ready"],
            "handoff_relative_path": handoff["handoff_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *handoff["created_relative_paths"],
            "workflow-check.public.json",
        ],
        "workflow_check_relative_path": "workflow-check.public.json",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "workflow_checks": checks,
        "failed_checks": failed_checks,
        "execution_boundary": workflow_check["execution_boundary"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "use workflow-check.public.json as the pre-run invariant packet before "
            "any later operator-triggered AgentIssue-Bench lagent_239 e2e run"
        ),
    }

def materialize_agentissue_codex_cli_runner_run_gate(
    run_gate_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute run-specific gate packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner run-specific gate currently only supports selected tag lagent_239"
        )
    root = Path(run_gate_root).expanduser()
    workflow = materialize_agentissue_codex_cli_runner_workflow_check(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    workflow_path = root / "workflow-check.public.json"
    gate_path = root / "execution-gate.public.json"
    handoff_path = root / "first-run-handoff.public.json"
    run_gate_path = root / "run-specific-gate.public.json"
    run_gate_markdown_path = root / "run-specific-gate.md"
    compact_run_path = root / "benchmark_run.compact.json"

    workflow_check = json.loads(workflow_path.read_text(encoding="utf-8"))
    execution_gate = json.loads(gate_path.read_text(encoding="utf-8"))
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

    gate_items = [
        {
            "id": "selected_tag_and_image_locked",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["single_selected_tag"]
            and workflow_check["workflow_checks"]["selected_image_consistent"],
            "public_evidence": "workflow-check.public.json",
        },
        {
            "id": "host_codex_auth_local_only",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["host_codex_auth_not_synced"],
            "public_evidence": "workflow-check.public.json",
        },
        {
            "id": "private_job_root_selected",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "stop_if_missing": True,
        },
        {
            "id": "operator_explicit_real_run_trigger",
            "owner": "owner",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "stop_if_missing": True,
        },
        {
            "id": "selected_container_source_extracted",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "public_command_shape": "execution-gate.public.json",
            "stop_if_missing": True,
        },
        {
            "id": "private_git_baseline_created_before_codex",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "public_command_shape": "execution-gate.public.json",
            "stop_if_missing": True,
        },
        {
            "id": "host_codex_exec_ephemeral_from_buggy_source",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "public_command_shape": "execution-gate.public.json",
            "stop_if_missing": True,
        },
        {
            "id": "attempt_patch_reducer_configured",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["patch_from_buggy_source_git_diff"]
            and workflow_check["workflow_checks"]["attempt_patch_relative_path"],
            "public_evidence": AGENTISSUE_PATCH_RELATIVE_PATH,
        },
        {
            "id": "selected_tag_eval_no_upload_submit_ranking",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["single_tag_eval_no_upload_submit"]
            and workflow_check["workflow_checks"]["single_tag_eval_no_public_ranking"],
            "public_evidence": "workflow-check.public.json",
        },
        {
            "id": "compact_public_reducer_enabled",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["public_files_compact_or_public"],
            "public_evidence": "benchmark_run.compact.json",
        },
        {
            "id": "raw_artifact_and_auth_leak_stop_rules_enabled",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": True,
            "stop_if_raw_task_patch_log_trajectory_screenshot_or_auth_material_public": True,
        },
    ]
    blocking_gate_ids = [
        item["id"]
        for item in gate_items
        if item["required_before_real_run"] and not item["satisfied_by_packet"]
    ]
    run_gate = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "default_mode": "no_execute",
        "materialized": True,
        "path_recorded": False,
        "real_run_authorized": False,
        "ready_for_real_run": False,
        "ready_for_operator_review": True,
        "blocking_gate_ids": blocking_gate_ids,
        "input_packets": {
            "workflow_check": "workflow-check.public.json",
            "first_run_handoff": "first-run-handoff.public.json",
            "execution_gate": "execution-gate.public.json",
        },
        "owner_agent_gate_items": gate_items,
        "phase_order": [
            "select_private_job_root",
            "extract_selected_container_buggy_source",
            "create_private_git_baseline",
            "run_host_codex_exec_ephemeral_from_buggy_source",
            "export_attempt_patch_from_buggy_source_git_diff",
            "run_selected_tag_eval_no_upload_submit_ranking",
            "reduce_to_compact_public_result",
        ],
        "public_artifact_policy": {
            "allowed_public_relative_files": [
                "runner-flow-plan.public.json",
                "execution-gate.public.json",
                "first-run-handoff.public.json",
                "workflow-check.public.json",
                "run-specific-gate.public.json",
                "run-specific-gate.md",
                "benchmark_run.compact.json",
            ],
            "raw_task_material_public": False,
            "patch_content_public": False,
            "raw_logs_public": False,
            "trajectories_public": False,
            "screenshots_public": False,
            "absolute_paths_public": False,
            "credential_values_public": False,
        },
        "credential_boundary": {
            "codex_auth_values_read_by_packet": False,
            "codex_home_synced": False,
            "shared_remote_host_receives_codex_auth": False,
            "host_codex_auth_local_only": True,
        },
        "stop_conditions": [
            "private_job_root_missing",
            "operator_real_run_trigger_missing",
            "selected_container_source_not_extracted",
            "private_git_baseline_missing_before_codex",
            "host_codex_not_ephemeral_or_not_from_buggy_source",
            "attempt_patch_missing_or_not_from_buggy_source_git_diff",
            "eval_attempts_upload_submit_or_public_ranking",
            "public_artifact_contains_raw_task_patch_log_trajectory_screenshot_auth_or_absolute_path",
        ],
        "execution_boundary": {
            **workflow_check["execution_boundary"],
            "real_run_authorized": False,
            "operator_trigger_recorded": False,
        },
        "rendered_command_sources": {
            "source_extraction_gate": execution_gate["source_extraction_gate"]["commands"],
            "private_git_baseline_gate": execution_gate["private_git_baseline_gate"]["commands"],
            "host_codex_gate": execution_gate["host_codex_gate"]["command"],
            "patch_output_gate": execution_gate["patch_output_gate"],
            "eval_gate": execution_gate["eval_gate"],
        },
    }
    markdown = (
        "# AgentIssue-Bench lagent_239 Run-Specific Gate\n\n"
        "This packet is no-execute. It separates the gates that are already "
        "covered by public/compact no-run packets from the gates that still "
        "block a real no-upload run.\n\n"
        "## Blocking Gates\n\n"
        + "\n".join(f"- {gate_id}" for gate_id in blocking_gate_ids)
        + "\n\n## Public Boundary\n\n"
        "- Codex auth stays on the host; no Codex home or auth material is synced.\n"
        "- Public artifacts stay compact/public and relative-path only.\n"
        "- Raw task material, patch content, raw logs, trajectories, screenshots, "
        "credentials, and absolute private paths remain private.\n"
    )

    benchmark_run = json.loads(json.dumps(workflow["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_run_gate",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_run_gate",
            "first_blocker": "run_gate_packet_only_real_run_not_authorized",
            "score_failure_attribution": "not_run_run_gate_only",
            "failure_attribution_labels": [
                "run_specific_gate_packet_only",
                "real_run_blocked_until_gate_items_satisfied",
            ],
            "evidence_files": run_gate["public_artifact_policy"][
                "allowed_public_relative_files"
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "run_specific_gate_materialized": True,
            "owner_agent_gate_items_declared": True,
            "blocking_gate_ids_declared": True,
            "ready_for_operator_review": True,
            "real_run_authorized": False,
            "private_job_root_required": True,
            "operator_trigger_required": True,
            "phase_order_declared": True,
            "credential_boundary_declared": True,
            "public_artifact_policy_declared": True,
            "stop_conditions_declared": True,
            "no_execute_packet": True,
            "no_real_source_extraction": True,
            "no_real_codex_execution": True,
            "no_docker_pull_or_start": True,
            "no_auth_sync_to_shared_host": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "run_gate_packet_only_no_real_case"

    run_gate_path.write_text(
        json.dumps(run_gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run_gate_markdown_path.write_text(markdown, encoding="utf-8")
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready_for_operator_review": True,
        "ready_for_real_run": False,
        "materialized": True,
        "path_recorded": False,
        "run_gate_root_path_recorded": False,
        "blocking_gate_ids": blocking_gate_ids,
        "workflow_check": {
            "schema_version": workflow["schema_version"],
            "ready": workflow["ready"],
            "workflow_check_relative_path": workflow["workflow_check_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *workflow["created_relative_paths"],
            "run-specific-gate.public.json",
            "run-specific-gate.md",
        ],
        "run_gate_relative_path": "run-specific-gate.public.json",
        "run_gate_markdown_relative_path": "run-specific-gate.md",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "gate_checks": {
            "owner_agent_gate_items_declared": True,
            "blocking_gate_ids_declared": True,
            "credential_boundary_declared": True,
            "public_artifact_policy_declared": True,
            "stop_conditions_declared": True,
            "real_run_authorized": False,
        },
        "execution_boundary": run_gate["execution_boundary"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "review run-specific gate packet before any later real no-upload "
            "AgentIssue-Bench lagent_239 Docker/Codex execution"
        ),
    }

def materialize_agentissue_codex_cli_runner_target_handoff(
    target_handoff_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute target-runner handoff packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner target handoff currently only supports selected tag lagent_239"
        )
    root = Path(target_handoff_root).expanduser()
    run_gate = materialize_agentissue_codex_cli_runner_run_gate(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    run_gate_path = root / "run-specific-gate.public.json"
    target_handoff_path = root / "target-runner-handoff.public.json"
    target_handoff_markdown_path = root / "target-runner-handoff.md"
    compact_run_path = root / "benchmark_run.compact.json"

    run_gate_public = json.loads(run_gate_path.read_text(encoding="utf-8"))
    command_sources = run_gate_public["rendered_command_sources"]
    gate_item_ids = [
        item["id"] for item in run_gate_public["owner_agent_gate_items"]
    ]
    required_before_execution = [
        "private_job_root_selected",
        "operator_explicit_real_run_trigger",
        "selected_container_source_extracted",
        "private_git_baseline_created_before_codex",
        "host_codex_exec_ephemeral_from_buggy_source",
        "attempt_patch_reducer_configured",
        "selected_tag_eval_no_upload_submit_ranking",
        "compact_public_reducer_enabled",
        "host_codex_auth_local_only",
    ]
    missing_from_gate = [
        gate_id for gate_id in required_before_execution if gate_id not in gate_item_ids
    ]
    no_execute_boundary = {
        **run_gate_public["execution_boundary"],
        "target_thread_started": False,
        "target_runner_executed": False,
        "benchmark_execution_authorized_by_packet": False,
    }
    target_handoff = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "default_mode": "no_execute",
        "materialized": True,
        "path_recorded": False,
        "target_handoff_root_path_recorded": False,
        "handoff_target": "separate_benchmark_execution_thread",
        "meta_heartbeat_must_not_execute": True,
        "real_run_authorized_by_packet": False,
        "ready_for_real_run": False,
        "ready_for_separate_execution_thread_after_gate_satisfied": (
            not missing_from_gate
        ),
        "source_packets": {
            "runner_plan": "runner-flow-plan.public.json",
            "execution_gate": "execution-gate.public.json",
            "first_run_handoff": "first-run-handoff.public.json",
            "workflow_check": "workflow-check.public.json",
            "run_gate": "run-specific-gate.public.json",
        },
        "target_runner_prerequisites": required_before_execution,
        "missing_from_run_gate": missing_from_gate,
        "execution_thread_checklist": [
            {
                "phase": "select_private_job_root",
                "required": True,
                "public_packet_only": False,
                "private_state_allowed_in_execution_thread": True,
                "meta_thread_must_not_run": True,
            },
            {
                "phase": "extract_selected_container_buggy_source",
                "required": True,
                "command_shape_source": "run-specific-gate.public.json:rendered_command_sources.source_extraction_gate",
                "commands": command_sources["source_extraction_gate"],
            },
            {
                "phase": "create_private_git_baseline",
                "required": True,
                "command_shape_source": "run-specific-gate.public.json:rendered_command_sources.private_git_baseline_gate",
                "commands": command_sources["private_git_baseline_gate"],
            },
            {
                "phase": "run_host_codex_exec_ephemeral_from_buggy_source",
                "required": True,
                "command_shape_source": "run-specific-gate.public.json:rendered_command_sources.host_codex_gate",
                "command": command_sources["host_codex_gate"],
                "auth_boundary": "host_local_only_no_auth_sync",
            },
            {
                "phase": "export_attempt_patch_from_buggy_source_git_diff",
                "required": True,
                "command_shape_source": "run-specific-gate.public.json:rendered_command_sources.patch_output_gate",
                "output_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
                "patch_content_public": False,
            },
            {
                "phase": "run_selected_tag_eval_no_upload_submit_ranking",
                "required": True,
                "command_shape_source": "run-specific-gate.public.json:rendered_command_sources.eval_gate",
                "upload": False,
                "submit": False,
                "public_ranking_path": False,
            },
            {
                "phase": "reduce_to_compact_public_result",
                "required": True,
                "public_outputs": [
                    "benchmark_run.compact.json",
                    "target-runner-handoff.public.json",
                ],
                "private_outputs_not_public": [
                    AGENTISSUE_PATCH_RELATIVE_PATH,
                    "raw logs",
                    "task material",
                    "model transcript",
                    "screenshots",
                    "credentials",
                ],
            },
        ],
        "public_output_contract": {
            "allowed_public_relative_files": [
                "target-runner-handoff.public.json",
                "target-runner-handoff.md",
                *run_gate_public["public_artifact_policy"][
                    "allowed_public_relative_files"
                ],
            ],
            "raw_task_material_public": False,
            "patch_content_public": False,
            "raw_logs_public": False,
            "trajectories_public": False,
            "screenshots_public": False,
            "absolute_paths_public": False,
            "credential_values_public": False,
        },
        "credential_boundary": {
            "codex_auth_values_read_by_packet": False,
            "codex_home_synced": False,
            "shared_remote_host_receives_codex_auth": False,
            "host_codex_auth_local_only": True,
        },
        "execution_boundary": no_execute_boundary,
        "stop_conditions": [
            "do_not_execute_in_meta_heartbeat_thread",
            *run_gate_public["stop_conditions"],
            "public_handoff_contains_raw_task_patch_log_transcript_screenshot_auth_or_absolute_path",
        ],
    }
    markdown = (
        "# AgentIssue-Bench lagent_239 Target-Runner Handoff\n\n"
        "This packet is no-execute. It is a compact public handoff for a "
        "separate benchmark execution thread, not permission for the meta "
        "heartbeat thread to run the benchmark.\n\n"
        "## Target\n\n"
        "- handoff target: separate benchmark execution thread\n"
        "- meta heartbeat must not execute Codex, Docker, model APIs, source "
        "extraction, patch generation, eval, upload, submit, or ranking paths\n"
        "- real_run_authorized_by_packet=false\n\n"
        "## Required Gates\n\n"
        + "\n".join(f"- {gate_id}" for gate_id in required_before_execution)
        + "\n\n## Public Outputs\n\n"
        "- benchmark_run.compact.json\n"
        "- run-specific-gate.public.json\n"
        "- target-runner-handoff.public.json\n"
        "- target-runner-handoff.md\n\n"
        "Private execution artifacts stay private and must be reduced before "
        "any public writeback.\n"
    )

    benchmark_run = json.loads(json.dumps(run_gate["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_target_handoff",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_target_handoff",
            "first_blocker": "target_handoff_packet_only_no_meta_execution",
            "score_failure_attribution": "not_run_target_handoff_only",
            "failure_attribution_labels": [
                "target_runner_handoff_packet_only",
                "ready_for_separate_execution_thread_after_gate_satisfied",
            ],
            "evidence_files": target_handoff["public_output_contract"][
                "allowed_public_relative_files"
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "target_runner_handoff_materialized": True,
            "handoff_target_declared": True,
            "meta_heartbeat_must_not_execute": True,
            "target_runner_prerequisites_declared": True,
            "real_run_authorized_by_packet": False,
            "target_thread_started": False,
            "target_runner_executed": False,
            "no_upload_submit_or_public_ranking": True,
            "no_auth_sync_to_shared_host": True,
            "public_output_contract_declared": True,
            "ready_for_separate_execution_thread_after_gate_satisfied": (
                not missing_from_gate
            ),
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "target_handoff_packet_only_no_real_case"

    target_handoff_path.write_text(
        json.dumps(target_handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    target_handoff_markdown_path.write_text(markdown, encoding="utf-8")
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "handoff_target": "separate_benchmark_execution_thread",
        "ready_for_real_run": False,
        "ready_for_separate_execution_thread_after_gate_satisfied": (
            not missing_from_gate
        ),
        "materialized": True,
        "path_recorded": False,
        "target_handoff_root_path_recorded": False,
        "real_run_authorized_by_packet": False,
        "run_gate": {
            "schema_version": run_gate["schema_version"],
            "ready_for_operator_review": run_gate["ready_for_operator_review"],
            "ready_for_real_run": run_gate["ready_for_real_run"],
            "run_gate_relative_path": run_gate["run_gate_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *run_gate["created_relative_paths"],
            "target-runner-handoff.public.json",
            "target-runner-handoff.md",
        ],
        "target_handoff_relative_path": "target-runner-handoff.public.json",
        "target_handoff_markdown_relative_path": "target-runner-handoff.md",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "execution_boundary": target_handoff["execution_boundary"],
        "target_runner_prerequisites": required_before_execution,
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "hand off target-runner packet to a separate benchmark execution "
            "thread; keep meta heartbeat no-execute/no-upload"
        ),
    }

def _agentissue_private_runner_script_text(
    *,
    tag: str,
    image: str,
    codex_binary: str,
    docker_binary: str,
) -> str:
    codex = shlex.quote(_agentissue_public_label(codex_binary, limit=80))
    docker = shlex.quote(_agentissue_public_label(docker_binary, limit=80))
    quoted_tag = shlex.quote(tag)
    quoted_image = shlex.quote(image)
    container_buggy_source = "/app/source_code_buggy"
    eval_apply = "/usr/local/bin/run_test_entrypoint.sh apply_patch /patches/attempt.patch"
    eval_test = "/usr/local/bin/run_test_entrypoint.sh test_patched"
    return f"""#!/usr/bin/env bash
set -euo pipefail

TAG="${{TAG:-{quoted_tag}}}"
IMAGE="${{IMAGE:-{quoted_image}}}"
CODEX_BIN="${{CODEX_BIN:-{codex}}}"
DOCKER_BIN="${{DOCKER_BIN:-{docker}}}"
LOOPX_BIN="${{LOOPX_BIN:-loopx}}"
GOAL_ID="${{GOAL_ID:-loopx-meta}}"
ALLOW_DOCKER_PULL="${{ALLOW_DOCKER_PULL:-0}}"
APPEND_HISTORY="${{APPEND_HISTORY:-0}}"
PRECHECK_ONLY="${{PRECHECK_ONLY:-0}}"
PATCH_APPLY_SH="${{PATCH_APPLY_SH:-{eval_apply}}}"
PATCH_TEST_SH="${{PATCH_TEST_SH:-{eval_test}}}"
CONTAINER_BUGGY_SOURCE="${{CONTAINER_BUGGY_SOURCE:-{container_buggy_source}}}"
JOB_ROOT="${{JOB_ROOT:-$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)}}"
CONTEXT_DIR="$JOB_ROOT/context"
PROMPT_PATH="${{PROMPT_PATH:-$CONTEXT_DIR/prompt.md}}"
BUGGY_SOURCE="$JOB_ROOT/buggy-source"
PATCH_DIR="$JOB_ROOT/Patches/lagent_239"
PATCH_PATH="$PATCH_DIR/attempt.patch"
LAST_MESSAGE="$JOB_ROOT/codex-last-message.txt"
MARKER_DIR="$JOB_ROOT/result-markers"
BENCHMARK_RUN_JSON="$JOB_ROOT/benchmark_run.compact.json"
BENCHMARK_RESULT_JSON="$JOB_ROOT/benchmark_result.compact.json"
TMP_CONTAINER=""

fail() {{
  printf 'agentissue-runner: %s\\n' "$*" >&2
  exit 1
}}

cleanup() {{
  if [ -n "$TMP_CONTAINER" ]; then
    "$DOCKER_BIN" rm -f "$TMP_CONTAINER" >/dev/null 2>&1 || true
  fi
}}
trap cleanup EXIT

require_selected_lagent239() {{
  [ "$TAG" = "lagent_239" ] || fail "only lagent_239 is supported"
  [ "$IMAGE" = "{image}" ] || fail "only the selected lagent_239 image is supported"
}}

prepare_private_job_root() {{
  require_selected_lagent239
  mkdir -p "$CONTEXT_DIR" "$PATCH_DIR" "$MARKER_DIR"
  [ -s "$PROMPT_PATH" ] || fail "missing private context/prompt.md"
  if grep -q "Synthetic AgentIssue-Bench lagent_239 Prompt Placeholder" "$PROMPT_PATH"; then
    fail "replace the synthetic prompt placeholder before running Codex"
  fi
}}

precheck_private_runner_environment() {{
  require_selected_lagent239
  command -v "$CODEX_BIN" >/dev/null 2>&1 || fail "Codex binary is not on PATH"
  command -v "$DOCKER_BIN" >/dev/null 2>&1 || fail "Docker binary is not on PATH"
  if ! "$DOCKER_BIN" image inspect "$IMAGE" >/dev/null 2>&1; then
    [ "$ALLOW_DOCKER_PULL" = "1" ] || fail "selected image is missing; set ALLOW_DOCKER_PULL=1 to pull it"
    "$DOCKER_BIN" pull "$IMAGE"
  fi
  "$DOCKER_BIN" run --platform linux/amd64 --rm --entrypoint bash \\
    -e CONTAINER_BUGGY_SOURCE="$CONTAINER_BUGGY_SOURCE" \\
    "$IMAGE" -lc \\
    '[ -d "$CONTAINER_BUGGY_SOURCE" ] && grep -q "apply_patch)" /usr/local/bin/run_test_entrypoint.sh && grep -q "test_patched)" /usr/local/bin/run_test_entrypoint.sh'
}}

extract_buggy_source_from_selected_container() {{
  if [ -d "$BUGGY_SOURCE/.git" ]; then
    return 0
  fi
  if [ -e "$BUGGY_SOURCE" ] && [ "$(find "$BUGGY_SOURCE" -mindepth 1 -maxdepth 1 ! -name .gitkeep | wc -l | tr -d ' ')" != "0" ]; then
    fail "buggy-source is non-empty but has no git baseline; move it aside or set up baseline first"
  fi
  mkdir -p "$BUGGY_SOURCE"
  rm -f "$BUGGY_SOURCE/.gitkeep"
  if ! "$DOCKER_BIN" image inspect "$IMAGE" >/dev/null 2>&1; then
    [ "$ALLOW_DOCKER_PULL" = "1" ] || fail "selected image is missing; set ALLOW_DOCKER_PULL=1 to pull it"
    "$DOCKER_BIN" pull "$IMAGE"
  fi
  TMP_CONTAINER="agentissue-lagent-239-extract-$$"
  "$DOCKER_BIN" create --name "$TMP_CONTAINER" "$IMAGE" >/dev/null
  "$DOCKER_BIN" cp "$TMP_CONTAINER:$CONTAINER_BUGGY_SOURCE/." "$BUGGY_SOURCE"
  "$DOCKER_BIN" rm "$TMP_CONTAINER" >/dev/null
  TMP_CONTAINER=""
  [ "$(find "$BUGGY_SOURCE" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')" != "0" ] || fail "buggy source extraction produced no files"
}}

initialize_git_baseline_in_buggy_source() {{
  git -C "$BUGGY_SOURCE" rev-parse --is-inside-work-tree >/dev/null 2>&1 && return 0
  git -C "$BUGGY_SOURCE" init
  git -C "$BUGGY_SOURCE" config user.email "loopx@example.invalid"
  git -C "$BUGGY_SOURCE" config user.name "LoopX"
  git -C "$BUGGY_SOURCE" add .
  git -C "$BUGGY_SOURCE" commit -m "agentissue-bench-buggy-source-baseline"
}}

run_host_local_codex_cli_patch_worker() {{
  "$CODEX_BIN" exec \\
    --ephemeral \\
    --ignore-rules \\
    --sandbox workspace-write \\
    --cd "$BUGGY_SOURCE" \\
    --add-dir "$JOB_ROOT" \\
    --output-last-message "$LAST_MESSAGE" \\
    "$PROMPT_PATH"
  touch "$MARKER_DIR/host_codex_cli_invoked"
}}

write_attempt_patch_from_buggy_source_git_diff() {{
  git -C "$BUGGY_SOURCE" diff --binary > "$PATCH_PATH"
  [ -s "$PATCH_PATH" ] || fail "Codex run produced an empty git diff"
}}

evaluate_selected_tag_container() {{
  rm -f "$MARKER_DIR/patch_applied" "$MARKER_DIR/test_success"
  set +e
  "$DOCKER_BIN" run \\
    --platform linux/amd64 \\
    --rm \\
    --entrypoint bash \\
    -v "$PATCH_DIR:/patches:ro" \\
    -v "$MARKER_DIR:/markers" \\
    -e PATCH_APPLY_SH="$PATCH_APPLY_SH" \\
    -e PATCH_TEST_SH="$PATCH_TEST_SH" \\
    "$IMAGE" \\
    -lc 'set -euo pipefail; eval "$PATCH_APPLY_SH"; touch /markers/patch_applied; eval "$PATCH_TEST_SH"; touch /markers/test_success'
  local exit_code=$?
  set -e
  printf '%s\\n' "$exit_code" > "$MARKER_DIR/patched_exit_code"
}}

write_compact_public_evidence() {{
  export TAG IMAGE BUGGY_SOURCE PATCH_PATH MARKER_DIR
  python3 - "$BENCHMARK_RUN_JSON" "$BENCHMARK_RESULT_JSON" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

run_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
tag = os.environ["TAG"]
image = os.environ["IMAGE"]
source = Path(os.environ["BUGGY_SOURCE"])
patch = Path(os.environ["PATCH_PATH"])
markers = Path(os.environ["MARKER_DIR"])
patched_exit = int((markers / "patched_exit_code").read_text().strip())
patch_bytes = patch.stat().st_size if patch.exists() else 0
patch_sha = hashlib.sha256(patch.read_bytes()).hexdigest() if patch.exists() else "missing"
name_result = subprocess.run(
    ["git", "-C", str(source), "diff", "--name-only"],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
)
changed_files = [line for line in name_result.stdout.splitlines() if line.strip()]
hunk_count = 0
if patch.exists():
    hunk_count = sum(1 for line in patch.read_text(errors="ignore").splitlines() if line.startswith("@@ "))
patch_applied = (markers / "patch_applied").exists()
test_success = (markers / "test_success").exists()
resolved = patched_exit == 0 and test_success
score = {{
    "kind": "agentissue_bench_single_tag_container_eval",
    "resolved": resolved,
    "value": 1 if resolved else 0,
}}
validation = {{
    "selected_image_only": image == "alfin06/agentissue-bench:lagent_239",
    "single_tag_only": tag == "lagent_239",
    "buggy_source_extracted": source.exists(),
    "fixed_source_not_extracted_to_host": True,
    "host_codex_cli_invoked": (markers / "host_codex_cli_invoked").exists(),
    "patch_exported_from_buggy_source_git_diff": patch.exists() and patch_bytes > 0,
    "patch_applied_in_container": patch_applied,
    "patched_eval_exit_zero": patched_exit == 0,
    "patched_eval_success_marker": test_success,
    "no_upload": True,
    "no_submit": True,
    "no_public_ranking_path": True,
    "raw_logs_public": False,
    "patch_content_public": False,
    "credential_values_recorded": False,
    "codex_auth_synced_to_container_or_remote": False,
}}
benchmark_run = {{
    "schema_version": "benchmark_run_v0",
    "source_runner": "loopx_agentissue_codex_cli_runner",
    "benchmark_id": "agentissue-bench",
    "selected_tag": tag,
    "selected_image": image,
    "real_run": True,
    "no_upload": True,
    "no_submit": True,
    "no_public_ranking_path": True,
    "patch_sha256": patch_sha,
    "patch_bytes": patch_bytes,
    "changed_file_count": len(changed_files),
    "hunk_count": hunk_count,
    "patched_exit_code": patched_exit,
    "official_task_score": score,
    "validation": validation,
}}
benchmark_result = {{
    "schema_version": "benchmark_result_v0",
    "benchmark_id": "agentissue-bench",
    "selected_tag": tag,
    "official_task_score": score,
    "no_upload": True,
    "no_submit": True,
    "no_public_ranking_path": True,
    "patch_sha256": patch_sha,
    "patch_bytes": patch_bytes,
    "changed_file_count": len(changed_files),
}}
run_path.write_text(json.dumps(benchmark_run, indent=2, sort_keys=True) + "\\n")
result_path.write_text(json.dumps(benchmark_result, indent=2, sort_keys=True) + "\\n")
PY
}}

reduce_compact_public_evidence() {{
  local args=("$LOOPX_BIN" "benchmark" "agentissue-codex-runner-flow" "--goal-id" "$GOAL_ID" "--tag" "$TAG" "--real-result-root" "$JOB_ROOT")
  if [ "$APPEND_HISTORY" = "1" ]; then
    args+=("--delivery-batch-scale" "multi_surface" "--delivery-outcome" "{DeliveryOutcome.PRIMARY_GOAL_OUTCOME.value}" "--execute")
  fi
  "${{args[@]}}"
}}

main() {{
  if [ "$PRECHECK_ONLY" = "1" ]; then
    precheck_private_runner_environment
    return 0
  fi
  prepare_private_job_root
  extract_buggy_source_from_selected_container
  initialize_git_baseline_in_buggy_source
  run_host_local_codex_cli_patch_worker
  write_attempt_patch_from_buggy_source_git_diff
  evaluate_selected_tag_container
  write_compact_public_evidence
  reduce_compact_public_evidence
}}

main "$@"
"""


def materialize_agentissue_codex_cli_runner_private_script(
    script_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a private runner script plus public manifest without executing it."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner private script currently only supports selected tag lagent_239"
        )
    root = Path(script_root).expanduser()
    handoff = materialize_agentissue_codex_cli_runner_first_run_handoff(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    script_path = root / "run-lagent239.private.sh"
    manifest_path = root / "private-runner.public.json"
    compact_run_path = root / "benchmark_run.compact.json"
    phase_order = [
        "prepare_private_job_root",
        "extract_buggy_source_from_selected_container",
        "initialize_git_baseline_in_buggy_source",
        "run_host_local_codex_cli_patch_worker",
        "write_attempt_patch_from_buggy_source_git_diff",
        "evaluate_selected_tag_container",
        "write_compact_public_evidence",
        "reduce_compact_public_evidence",
    ]
    script_text = _agentissue_private_runner_script_text(
        tag=tag,
        image=AGENTISSUE_DEFAULT_IMAGE,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    script_path.write_text(script_text, encoding="utf-8")
    script_path.chmod(0o700)

    manifest = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "path_recorded": False,
        "root_path_recorded": False,
        "private_script_relative_path": "run-lagent239.private.sh",
        "script_content_public": False,
        "default_generator_mode": "no_execute",
        "phase_order": phase_order,
        "relative_outputs": {
            "attempt_patch": AGENTISSUE_PATCH_RELATIVE_PATH,
            "benchmark_run": "benchmark_run.compact.json",
            "benchmark_result": "benchmark_result.compact.json",
            "real_result": "real-result.public.json",
            "private_runner_manifest": "private-runner.public.json",
        },
        "operator_inputs_required": [
            "private context/prompt.md with public issue/task context",
            "host-local Codex CLI auth already present on the trusted host",
            "selected lagent_239 image present or ALLOW_DOCKER_PULL=1",
        ],
        "script_checks": {
            "strict_mode": True,
            "precheck_only_mode": True,
            "selected_tag_guard": True,
            "selected_image_guard": True,
            "observed_image_source_path_default": True,
            "gitkeep_placeholder_safe": True,
            "buggy_source_extraction_phase": True,
            "git_baseline_phase": True,
            "host_codex_phase": True,
            "patch_export_phase": True,
            "selected_container_eval_phase": True,
            "entrypoint_eval_commands": True,
            "compact_reducer_phase": True,
            "appends_history_only_when_append_history_is_one": True,
        },
        "generator_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "source_extracted": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "auth_material_synced": False,
            "credential_values_recorded": False,
            "raw_logs_public": False,
            "patch_content_public": False,
            "absolute_paths_public": False,
        },
        "later_script_boundary": {
            "will_invoke_host_codex_cli": True,
            "will_start_selected_container": True,
            "will_write_compact_files": True,
            "uses_entrypoint_eval_commands": True,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "auth_material_sync": False,
            "raw_logs_public": False,
            "patch_content_public": False,
        },
    }
    _agentissue_assert_compact_public_safe(manifest, label="private-runner.public.json")

    benchmark_run = json.loads(json.dumps(handoff["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_private_script",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_MODE,
            "worker_mode": "trusted_host_codex_cli_private_script_generator",
            "first_blocker": "private_runner_script_generated_not_executed",
            "score_failure_attribution": "not_run_private_runner_script_generator_only",
            "failure_attribution_labels": [
                "private_runner_script_generator_only",
                "ready_for_controlled_script_execution_or_real_codex_regression",
            ],
            "evidence_files": [
                "private-runner.public.json",
                "benchmark_run.compact.json",
                "first-run-handoff.public.json",
                "execution-gate.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "private_runner_script_materialized": True,
            "private_runner_manifest_materialized": True,
            "script_executable_bit_set": True,
            "script_content_not_public": True,
            "script_path_relative_only": True,
            "phase_order_rendered": True,
            "script_renders_source_extraction": True,
            "script_renders_observed_image_source_path": True,
            "script_renders_precheck_only": True,
            "script_handles_gitkeep_placeholder": True,
            "script_renders_git_baseline": True,
            "script_renders_host_codex": True,
            "script_renders_patch_export": True,
            "script_renders_selected_tag_eval": True,
            "script_renders_entrypoint_eval_commands": True,
            "script_renders_compact_evidence": True,
            "script_renders_real_result_reducer": True,
            "no_generator_codex_execution": True,
            "no_generator_docker_execution": True,
            "no_generator_model_api_invoked": True,
            "no_generator_upload": True,
            "no_generator_submit": True,
            "no_generator_public_ranking_path": True,
            "no_auth_material_sync": True,
            "no_raw_logs_public": True,
            "no_patch_content_public": True,
            "no_absolute_paths_public": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "private_runner_script_generated_not_executed"

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "script_root_path_recorded": False,
        "script_relative_path": "run-lagent239.private.sh",
        "manifest_relative_path": "private-runner.public.json",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "benchmark_result_relative_path": "benchmark_result.compact.json",
        "real_result_relative_path": "real-result.public.json",
        "created_relative_paths": [
            *handoff["created_relative_paths"],
            "run-lagent239.private.sh",
            "private-runner.public.json",
        ],
        "phase_order": phase_order,
        "script_checks": manifest["script_checks"],
        "execution_boundary": manifest["generator_boundary"],
        "later_script_boundary": manifest["later_script_boundary"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "run the private script only from a trusted local operator context, "
            "or add a low-frequency real Codex CLI regression that executes it "
            "without syncing auth material, uploading, submitting, or claiming a public ranking"
        ),
    }


AGENTISSUE_REAL_RESULT_FORBIDDEN_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "codex_auth",
    "credential",
    "environment",
    "file_content",
    "fixed_diff",
    "gold_material",
    "local_path",
    "password",
    "patch_content",
    "problem_statement",
    "raw_artifact",
    "raw_comment",
    "raw_diff",
    "raw_issue_body",
    "raw_issue_title",
    "raw_log",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
    "source_diff",
    "test_body",
    "test_patch",
    "trajectory",
}
AGENTISSUE_REAL_RESULT_FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "CODEX" + "_ACCESS_TOKEN",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "GOOGLE" + "_API_KEY",
    "raw_issue_body",
    "raw_patch",
    "trajectory.json",
)

AGENTISSUE_REAL_RESULT_REQUIRED_PHASE_CHECKS = (
    "selected_image_only",
    "single_tag_only",
    "buggy_source_extracted",
    "fixed_source_not_extracted_to_host",
    "host_codex_cli_invoked",
    "patch_exported_from_buggy_source_git_diff",
)
AGENTISSUE_REAL_RESULT_RESULT_PHASE_CHECKS = (
    "patch_applied_in_container",
)


def _agentissue_key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(_agentissue_key_paths(child, prefix=path))
        return paths
    if isinstance(value, list):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_agentissue_key_paths(child, prefix=f"{prefix}[{index}]"))
        return paths
    return []


def _agentissue_leaf(path: str) -> str:
    segment = path.rsplit(".", 1)[-1]
    if "[" in segment:
        segment = segment.split("[", 1)[0]
    return segment.lower()


def _agentissue_public_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else False


def _agentissue_public_number(value: Any, *, default: int | float = 0) -> int | float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return value
    return default


def _agentissue_assert_compact_public_safe(payload: dict[str, Any], *, label: str) -> None:
    key_hits = [
        path
        for path in _agentissue_key_paths(payload)
        if _agentissue_leaf(path) in AGENTISSUE_REAL_RESULT_FORBIDDEN_KEYS
    ]
    if key_hits:
        raise ValueError(f"{label} contains forbidden compact key(s): {', '.join(key_hits[:4])}")
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaked = [marker for marker in AGENTISSUE_REAL_RESULT_FORBIDDEN_TEXT if marker in rendered]
    if leaked:
        raise ValueError(f"{label} contains forbidden private marker(s): {', '.join(leaked[:4])}")


def _agentissue_compact_official_score(
    run: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    run_score = run.get("official_task_score") if isinstance(run.get("official_task_score"), dict) else {}
    result_score = (
        result.get("official_task_score")
        if isinstance(result.get("official_task_score"), dict)
        else {}
    )
    source = result_score or run_score
    kind = _agentissue_public_label(
        source.get("kind") or "agentissue_bench_single_tag_container_eval",
        limit=80,
    )
    value = _agentissue_public_number(source.get("value"), default=0)
    resolved = source.get("resolved")
    if not isinstance(resolved, bool):
        resolved = value == 1
    return {
        "kind": kind,
        "value": value,
        "passed": bool(resolved),
    }


def _agentissue_required_phase_checks(validation: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    missing: list[str] = []
    for key in AGENTISSUE_REAL_RESULT_REQUIRED_PHASE_CHECKS:
        checks[key] = validation.get(key) is True
        if not checks[key]:
            missing.append(key)
    for key in AGENTISSUE_REAL_RESULT_RESULT_PHASE_CHECKS:
        if not isinstance(validation.get(key), bool):
            missing.append(key)
        checks[key] = validation.get(key) is True
    if missing:
        raise ValueError(
            "real-result compact inputs are missing required runner phase proof(s): "
            + ", ".join(missing)
        )
    return checks


def materialize_agentissue_codex_cli_runner_real_result(
    real_result_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
) -> dict[str, Any]:
    """Reduce an already-completed private AgentIssue run from compact files only."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner real-result reducer currently only supports selected tag lagent_239"
        )
    root = Path(real_result_root).expanduser()
    run_path = root / "benchmark_run.compact.json"
    result_path = root / "benchmark_result.compact.json"
    public_packet_path = root / "real-result.public.json"
    if not run_path.exists():
        raise ValueError("real-result root is missing benchmark_run.compact.json")
    if not result_path.exists():
        raise ValueError("real-result root is missing benchmark_result.compact.json")
    run_input = json.loads(run_path.read_text(encoding="utf-8"))
    result_input = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(run_input, dict) or run_input.get("schema_version") != "benchmark_run_v0":
        raise ValueError("benchmark_run.compact.json must contain benchmark_run_v0")
    if not isinstance(result_input, dict) or result_input.get("schema_version") != "benchmark_result_v0":
        raise ValueError("benchmark_result.compact.json must contain benchmark_result_v0")
    _agentissue_assert_compact_public_safe(run_input, label="benchmark_run.compact.json")
    _agentissue_assert_compact_public_safe(result_input, label="benchmark_result.compact.json")

    selected = _agentissue_public_label(
        run_input.get("selected_tag")
        or run_input.get("task_selector_hash")
        or result_input.get("selected_tag")
        or tag
    )
    if selected != tag:
        raise ValueError(f"real-result selected tag mismatch: expected {tag}, got {selected}")

    official_score = _agentissue_compact_official_score(run_input, result_input)
    resolved = bool(official_score.get("passed"))
    patch_sha = _agentissue_public_label(
        run_input.get("patch_sha256") or result_input.get("patch_sha256") or "missing",
        limit=120,
    )
    patch_bytes = int(_agentissue_public_number(run_input.get("patch_bytes"), default=0))
    changed_files = int(
        _agentissue_public_number(
            run_input.get("changed_file_count") or result_input.get("changed_file_count"),
            default=0,
        )
    )
    hunk_count = int(_agentissue_public_number(run_input.get("hunk_count"), default=0))
    patched_exit = int(_agentissue_public_number(run_input.get("patched_exit_code"), default=0))
    baseline_exit = int(_agentissue_public_number(run_input.get("baseline_exit_code"), default=0))

    validation = run_input.get("validation") if isinstance(run_input.get("validation"), dict) else {}
    phase_checks = _agentissue_required_phase_checks(validation)
    patched_eval_exit_zero = (
        validation.get("patched_eval_exit_zero")
        if isinstance(validation.get("patched_eval_exit_zero"), bool)
        else patched_exit == 0
    )
    patched_eval_success_marker = (
        validation.get("patched_eval_success_marker")
        if isinstance(validation.get("patched_eval_success_marker"), bool)
        else resolved
    )
    patch_applied = phase_checks.get("patch_applied_in_container") is True
    failure_label = (
        "resolved_single_tag_eval"
        if resolved
        else (
            "unresolved_patch_apply_failed_compact_result"
            if not patch_applied
            else "unresolved_single_tag_eval_compact_result"
        )
    )
    no_upload = _agentissue_public_bool(run_input.get("no_upload")) or _agentissue_public_bool(
        validation.get("no_upload")
    )
    no_submit = _agentissue_public_bool(run_input.get("no_submit")) or _agentissue_public_bool(
        validation.get("no_submit")
    )
    no_public_ranking = _agentissue_public_bool(
        run_input.get("no_public_ranking_path")
    ) or _agentissue_public_bool(validation.get("no_public_ranking_path"))
    if not (no_upload and no_submit and no_public_ranking):
        raise ValueError(
            "real-result compact inputs must prove no_upload, no_submit, and no_public_ranking_path"
        )
    if validation.get("codex_auth_synced_to_container_or_remote") is True:
        raise ValueError("real-result compact inputs report Codex auth sync")
    if validation.get("credential_values_recorded") is True:
        raise ValueError("real-result compact inputs report credential value recording")
    if validation.get("raw_logs_public") is True or validation.get("patch_content_public") is True:
        raise ValueError("real-result compact inputs report raw logs or patch content public")

    result_packet = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "path_recorded": False,
        "real_run_done": True,
        "real_runner_invoked_by_reducer": False,
        "real_codex_invoked_by_reducer": False,
        "real_docker_invoked_by_reducer": False,
        "input_files": {
            "benchmark_run": {
                "relative_path": "benchmark_run.compact.json",
                "schema_version": run_input.get("schema_version"),
                "read": True,
            },
            "benchmark_result": {
                "relative_path": "benchmark_result.compact.json",
                "schema_version": result_input.get("schema_version"),
                "read": True,
            },
        },
        "result_summary": {
            "official_task_score": official_score,
            "resolved": resolved,
            "patch_sha256": patch_sha,
            "patch_bytes": patch_bytes,
            "changed_file_count": changed_files,
            "hunk_count": hunk_count,
            "patched_exit_code": patched_exit,
            "baseline_exit_code": baseline_exit,
        },
        "phase_checks": {
            **phase_checks,
            "patched_eval_exit_zero": patched_eval_exit_zero,
            "patched_eval_success_marker": patched_eval_success_marker,
        },
        "boundary": {
            "no_upload": no_upload,
            "no_submit": no_submit,
            "no_public_ranking_path": no_public_ranking,
            "codex_auth_synced": False,
            "credential_values_recorded": False,
            "raw_logs_public": False,
            "patch_content_public": False,
            "absolute_paths_public": False,
        },
        "public_outputs": [
            "real-result.public.json",
            "benchmark_run.compact.json",
            "benchmark_result.compact.json",
        ],
    }
    _agentissue_assert_compact_public_safe(result_packet, label="real-result.public.json")

    benchmark_run = {
        "schema_version": "benchmark_run_v0",
        "source_runner": AGENTISSUE_CODEX_CLI_RUNNER_SOURCE_RUNNER,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "job_name": "agentissue_lagent_239_codex_cli_runner_real_result_reducer",
        "mode": AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_MODE,
        "worker_mode": "trusted_host_codex_cli_real_result_reducer",
        "trace_publicness": "compact_public_no_issue_text_no_patch_no_logs",
        "score_failure_attribution": failure_label,
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_score_comparable_to_native_codex": False,
        "official_score_claim_allowed": False,
        "control_plane_score_applicable": True,
        "official_task_score": official_score,
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 1,
            "n_errored_trials": 0 if resolved else 1,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
        },
        "validation": {
            "real_result_reducer_materialized": True,
            "compact_run_read": True,
            "compact_result_read": True,
            "selected_tag_checked": True,
            **phase_checks,
            "patch_hash_recorded": bool(patch_sha and patch_sha != "missing"),
            "patched_eval_exit_zero": patched_eval_exit_zero,
            "patched_eval_success_marker": patched_eval_success_marker,
            "no_upload": no_upload,
            "no_submit": no_submit,
            "no_public_ranking_path": no_public_ranking,
            "no_raw_logs_public": True,
            "no_patch_content_public": True,
            "no_absolute_paths_public": True,
            "no_codex_auth_sync": True,
            "no_credential_values_recorded": True,
            "no_reducer_codex_execution": True,
            "no_reducer_docker_execution": True,
        },
        "trials": [
            {
                "task_id": tag,
                "trial_name": tag,
                "source": "selected_public_tag",
                "exception_type": "" if resolved else failure_label,
                "trajectory_present": False,
                "artifact_manifest_present": False,
                "trial_result_present": True,
            }
        ],
        "failure_attribution_labels": [failure_label],
        "evidence_files": [
            "real-result.public.json",
            "benchmark_run.compact.json",
            "benchmark_result.compact.json",
        ],
        "stop_conditions": [
            "raw_log_requested",
            "patch_content_requested",
            "absolute_private_path_publication_requested",
            "upload_submit_or_public_ranking_requested",
            "codex_auth_sync_requested",
        ],
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }
    benchmark_result = {
        "schema_version": "benchmark_result_v0",
        "task_id": "agentissue_bench_lagent_239",
        "scenario_id": AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_MODE,
        "worker_mode": "trusted_host_codex_cli_real_result_reducer",
        "harness_identity": "loopx",
        "terminal_state": "resolved" if resolved else "evaluated_unresolved",
        "trace_publicness": "compact_public_no_issue_text_no_patch_no_logs",
        "official_task_score": official_score,
        "validation_pass_count": 14,
        "validation_fail_count": 0 if resolved else 1,
        "changed_file_count": changed_files,
        "forbidden_access_count": 0,
        "phase_checks": {
            **phase_checks,
            "patched_eval_exit_zero": patched_eval_exit_zero,
            "patched_eval_success_marker": patched_eval_success_marker,
        },
        "failure_attribution_labels": benchmark_run["failure_attribution_labels"],
    }
    public_packet_path.write_text(
        json.dumps(result_packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "result_root_path_recorded": False,
        "real_run_done": True,
        "result_relative_path": "real-result.public.json",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "compact_result_relative_path": "benchmark_result.compact.json",
        "result_checks": {
            "compact_run_read": True,
            "compact_result_read": True,
            "selected_tag_checked": True,
            **phase_checks,
            "patched_eval_exit_zero": patched_eval_exit_zero,
            "patched_eval_success_marker": patched_eval_success_marker,
            "resolved": resolved,
            "no_upload": no_upload,
            "no_submit": no_submit,
            "no_public_ranking_path": no_public_ranking,
            "raw_logs_public": False,
            "patch_content_public": False,
            "absolute_paths_public": False,
        },
        "execution_boundary": {
            "codex_cli_invoked_by_reducer": False,
            "model_api_invoked_by_reducer": False,
            "docker_container_started_by_reducer": False,
            "source_extracted_by_reducer": False,
            "patch_generated_by_reducer": False,
            "patch_evaluated_by_reducer": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
        },
        "benchmark_run": benchmark_run,
        "benchmark_result": benchmark_result,
        "public_packet": result_packet,
        "recommended_next_action": (
            "use --real-result-root for future AgentIssue-Bench lagent_239 compact "
            "result reductions, then compare repeat runs or extend to the next selected tag"
        ),
    }
