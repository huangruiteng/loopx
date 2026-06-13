#!/usr/bin/env python3
"""Smoke-test SWE-Bench Pro public selected-row hash-only compaction."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "swe_bench_pro_selected_row_compaction_v0"
RUN_SCHEMA = "benchmark_run_v0"
BENCHMARK_ID = "swe-bench-pro"
DATASET_ID = "ScaleAI/SWE-bench_Pro"
DATASET_REVISION = "7ab5114912baf22bb098818e604c02fe7ad2c11f"
RUNNER_REPO = "scaleapi/SWE-bench_Pro-os"
RUNNER_COMMIT = "ca10a60a5fcae51e6948ffe1485d4153d421e6c5"
SPLIT = "test"
CONFIG = "default"
OFFSET = 0
ROW_IDX = 0
INSTANCE_ID = "instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan"
REPO = "NodeBB/NodeBB"
BASE_COMMIT = "1e137b07052bc3ea0da44ed201702c94055b8ad2"
DOCKERHUB_TAG = "nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5"
ROW_FIELD_HASHES = {
    "before_repo_set_cmd": {
        "chars": 226,
        "sha256": "7d4300a48ae64e2bd9c4c1fb5641d56385c24ee8308044fdb5ba9bf385a1a8f1",
    },
    "fail_to_pass": {
        "chars": 408,
        "sha256": "f681e11d42023528dca57e74351bb1bd7824d0b41ccd50c5197638a3a6201732",
    },
    "interface": {
        "chars": 971,
        "sha256": "83e94192ed741e8a9d1429f5efa484d60e8579de35e85aadf2376cd7686e77df",
    },
    "issue_categories": {
        "chars": 102,
        "sha256": "24fc694a174aea52f75f6a39fd95eb34cd76f1f2e4cc79227a901ccf8a0e80e6",
    },
    "issue_specificity": {
        "chars": 34,
        "sha256": "0e2b7fa112012020628280b45c410dbb66ed714ed5c285c51980d70bc1250aec",
    },
    "pass_to_pass": {
        "chars": 45764,
        "sha256": "b4b2cc243da9a4b3d853df392a7ae14c083bbb9679540fe13b04a5a5e458bd86",
    },
    "patch": {
        "chars": 12620,
        "sha256": "5604a864308d779c632e64c67c1c9b2eb0562c58bf4aeabc1fabfd43ff7a8f32",
    },
    "problem_statement": {
        "chars": 1330,
        "sha256": "e063181d444133d67464e5bdd49c8effc4f8952af9826cabf04416823c369994",
    },
    "requirements": {
        "chars": 3654,
        "sha256": "0ab84fee799da450cf1692dbb8ec3ea9d7ba93c5c08b676f733b4b222171409a",
    },
    "selected_test_files_to_run": {
        "chars": 68,
        "sha256": "d87bd02ab80f6965d45f6ddc4b21c682345e3f7fdf537759e7c1585d63d480b0",
    },
    "test_patch": {
        "chars": 1436,
        "sha256": "7b598b250cd12c68108906f35916b9a4d2b447f24fa0f46e49e25fa39e69e030",
    },
}
FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "command_argv",
    "credential",
    "docker_output",
    "environment",
    "gold_patch",
    "local_path",
    "password",
    "patch_content",
    "problem_statement_raw",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
    "test_body",
    "test_list_raw",
    "test_patch_raw",
    "trajectory",
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "docker pull",
    "docker run",
)


def key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(key_paths(child, prefix=path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(key_paths(child, prefix=f"{prefix}[{index}]"))
        return paths
    return []


def build_selected_row_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "dataset": {
            "id": DATASET_ID,
            "revision": DATASET_REVISION,
            "config": CONFIG,
            "split": SPLIT,
            "offset": OFFSET,
            "row_idx": ROW_IDX,
            "num_examples": 731,
            "gated": False,
        },
        "runner_source": {
            "repo": RUNNER_REPO,
            "commit": RUNNER_COMMIT,
        },
        "selected_instance": {
            "repo": REPO,
            "instance_id": INSTANCE_ID,
            "base_commit": BASE_COMMIT,
            "dockerhub_tag": DOCKERHUB_TAG,
            "repo_language": "js",
        },
        "row_field_hashes": ROW_FIELD_HASHES,
        "read_boundary": {
            "public_row_accessed": True,
            "raw_problem_statement_recorded": False,
            "raw_patch_recorded": False,
            "raw_test_patch_recorded": False,
            "raw_test_list_recorded": False,
            "raw_requirements_recorded": False,
            "raw_interface_recorded": False,
            "local_paths_recorded": False,
        },
        "execution_boundary": {
            "docker_image_pulled": False,
            "docker_container_started": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "credentials_read": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
        },
        "next_packet": {
            "kind": "swe_bench_pro_one_instance_launch_packet",
            "ready": True,
            "needs_image_size_estimate": True,
            "needs_no_run_local_docker_gate": True,
            "recommended_action": (
                "prepare a no-run one-instance launch packet for the selected "
                "SWE-Bench Pro row, preserving hash-only task material and "
                "stopping before Docker pull/run or Codex/model invocation"
            ),
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "swe-bench-pro",
        "benchmark_id": packet["benchmark_id"],
        "benchmark_revision": packet["dataset"]["revision"],
        "source_commit": packet["runner_source"]["commit"],
        "mode": "public_selected_row_hash_only_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "public_dataset_offset",
        "task_selector_hash": packet["selected_instance"]["instance_id"],
        "selected_instance": {
            "repo": packet["selected_instance"]["repo"],
            "instance_id": packet["selected_instance"]["instance_id"],
            "dockerhub_tag": packet["selected_instance"]["dockerhub_tag"],
            "base_commit": packet["selected_instance"]["base_commit"],
            "repo_language": packet["selected_instance"]["repo_language"],
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
        "validation": {
            "public_row_metadata_available": True,
            "raw_problem_statement_public": False,
            "raw_patch_public": False,
            "raw_test_patch_public": False,
            "raw_test_list_public": False,
            "no_docker_pull": True,
            "no_docker_run": True,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "paths_redacted": True,
        },
        "trials": [
            {
                "task_hash": packet["selected_instance"]["instance_id"],
                "runner_status": "blocked",
                "exception_type": "not_run_selected_row_compaction_only",
                "dockerhub_tag": packet["selected_instance"]["dockerhub_tag"],
            }
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    key_hits = []
    for path in key_paths(payload):
        leaf = path.rsplit(".", 1)[-1].strip("[]").lower()
        if leaf in FORBIDDEN_KEYS:
            key_hits.append(path)
    assert not key_hits, key_hits
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_selected_row_packet()
    run_event = reduce_to_benchmark_run(packet)
    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["dataset"]["split"] == "test", packet
    assert packet["dataset"]["offset"] == 0, packet
    assert packet["selected_instance"]["repo"] == REPO, packet
    assert packet["selected_instance"]["instance_id"] == INSTANCE_ID, packet
    assert packet["selected_instance"]["dockerhub_tag"] == DOCKERHUB_TAG, packet
    assert packet["row_field_hashes"]["problem_statement"]["chars"] == 1330, packet
    assert packet["row_field_hashes"]["patch"]["chars"] == 12620, packet
    assert packet["row_field_hashes"]["test_patch"]["chars"] == 1436, packet
    assert packet["read_boundary"]["public_row_accessed"] is True, packet
    assert packet["read_boundary"]["raw_problem_statement_recorded"] is False, packet
    assert packet["read_boundary"]["raw_patch_recorded"] is False, packet
    assert packet["read_boundary"]["raw_test_patch_recorded"] is False, packet
    assert packet["execution_boundary"]["docker_image_pulled"] is False, packet
    assert packet["execution_boundary"]["codex_cli_invoked"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["public_row_metadata_available"] is True, run_event
    assert run_event["validation"]["raw_problem_statement_public"] is False, run_event
    assert run_event["validation"]["raw_patch_public"] is False, run_event
    assert run_event["validation"]["no_docker_run"] is True, run_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    return {
        "ok": True,
        "classification": "swe_bench_pro_selected_row_compaction_v0",
        "benchmark_id": BENCHMARK_ID,
        "dataset_revision": DATASET_REVISION,
        "selected_repo": REPO,
        "instance_id": INSTANCE_ID,
        "dockerhub_tag": DOCKERHUB_TAG,
        "events": [packet["schema_version"], run_event["schema_version"]],
        "raw_problem_statement_recorded": packet["read_boundary"]["raw_problem_statement_recorded"],
        "raw_patch_recorded": packet["read_boundary"]["raw_patch_recorded"],
        "docker_image_pulled": packet["execution_boundary"]["docker_image_pulled"],
        "codex_cli_invoked": packet["execution_boundary"]["codex_cli_invoked"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
