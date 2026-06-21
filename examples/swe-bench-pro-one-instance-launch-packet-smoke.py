#!/usr/bin/env python3
"""Smoke-test a no-run SWE-Bench Pro one-instance launch packet."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "swe_bench_pro_one_instance_launch_packet_v0"
RUN_SCHEMA = "benchmark_run_v0"
BENCHMARK_ID = "swe-bench-pro"
DATASET_ID = "ScaleAI/SWE-bench_Pro"
DATASET_REVISION = "7ab5114912baf22bb098818e604c02fe7ad2c11f"
RUNNER_REPO = "scaleapi/SWE-bench_Pro-os"
RUNNER_COMMIT = "ca10a60a5fcae51e6948ffe1485d4153d421e6c5"
INSTANCE_ID = "instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan"
REPO = "NodeBB/NodeBB"
BASE_COMMIT = "1e137b07052bc3ea0da44ed201702c94055b8ad2"
IMAGE_REPOSITORY = "jefzda/sweap-images"
IMAGE_TAG = "nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5"
IMAGE_DIGEST = "sha256:e49637ebe82a479ca43b4663525955bc9cdd58c457140ee31c20958d621d3cf7"
IMAGE_SIZE_BYTES = 845_713_884
IMAGE_LAST_UPDATED = "2025-08-29T20:27:42.72333Z"
IMAGE_LAST_PUSHED = "2025-08-29T20:27:42.72333Z"
LOCAL_DOCKER_CONTEXT = "colima-loopx-bench"
LOCAL_DOCKER_SERVER_VERSION = "28.4.0"
LOCAL_DOCKER_CLIENT_VERSION = "29.2.0"
LOCAL_DOCKER_SERVER_ARCH = "arm64/aarch64"
LOCAL_DOCKER_NCPU = 4
LOCAL_DOCKER_MEMORY_BYTES = 8_308_088_832
LOCAL_WORKSPACE_FREE_BYTES = 17_140_224_000
ROW_HASHES_REF = {
    "problem_statement_sha256": "e063181d444133d67464e5bdd49c8effc4f8952af9826cabf04416823c369994",
    "patch_sha256": "5604a864308d779c632e64c67c1c9b2eb0562c58bf4aeabc1fabfd43ff7a8f32",
    "test_patch_sha256": "7b598b250cd12c68108906f35916b9a4d2b447f24fa0f46e49e25fa39e69e030",
    "fail_to_pass_sha256": "f681e11d42023528dca57e74351bb1bd7824d0b41ccd50c5197638a3a6201732",
    "pass_to_pass_sha256": "b4b2cc243da9a4b3d853df392a7ae14c083bbb9679540fe13b04a5a5e458bd86",
}

FORBIDDEN_KEYS = {
    "api_key",
    "auth",
    "authorization",
    "command_argv",
    "credential",
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
    "HF_TOKEN",
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


def build_launch_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "runner_repo": RUNNER_REPO,
            "runner_commit": RUNNER_COMMIT,
            "selected_row_packet": "swe_bench_pro_selected_row_compaction_v0",
        },
        "selected_instance": {
            "repo": REPO,
            "instance_id": INSTANCE_ID,
            "base_commit": BASE_COMMIT,
            "repo_language": "js",
            "task_material_mode": "hash_only",
            "row_hashes_ref": ROW_HASHES_REF,
        },
        "public_image_metadata": {
            "repository": IMAGE_REPOSITORY,
            "tag": IMAGE_TAG,
            "digest": IMAGE_DIGEST,
            "os": "linux",
            "architecture": "amd64",
            "status": "active",
            "size_bytes": IMAGE_SIZE_BYTES,
            "last_updated": IMAGE_LAST_UPDATED,
            "last_pushed": IMAGE_LAST_PUSHED,
            "metadata_source": "docker_hub_tag_api",
            "metadata_only": True,
        },
        "local_provider_metadata": {
            "docker_context": LOCAL_DOCKER_CONTEXT,
            "docker_context_reachable": True,
            "client_version": LOCAL_DOCKER_CLIENT_VERSION,
            "server_version": LOCAL_DOCKER_SERVER_VERSION,
            "server_os": "linux",
            "server_architecture": LOCAL_DOCKER_SERVER_ARCH,
            "server_cpus": LOCAL_DOCKER_NCPU,
            "server_memory_bytes": LOCAL_DOCKER_MEMORY_BYTES,
            "workspace_free_bytes": LOCAL_WORKSPACE_FREE_BYTES,
            "containers_running_observed": 0,
            "metadata_only": True,
        },
        "launch_readiness": {
            "no_run_packet_ready": True,
            "execution_ready": False,
            "image_platform": "linux/amd64",
            "local_server_platform": "linux/arm64",
            "platform_mismatch_requires_explicit_platform": True,
            "planned_docker_platform": "linux/amd64",
            "image_size_bytes": IMAGE_SIZE_BYTES,
            "workspace_free_bytes": LOCAL_WORKSPACE_FREE_BYTES,
            "storage_margin_known": True,
            "memory_margin_known": True,
            "runtime_emulation_not_verified": True,
        },
        "runner_input_boundary": {
            "required_by_official_evaluator": [
                "raw_sample_path",
                "patch_path",
                "output_dir",
                "dockerhub_username",
                "scripts_dir",
            ],
            "raw_sample_path_ready": False,
            "patch_path_ready": False,
            "scripts_dir_ready": False,
            "dockerhub_username_ready": True,
            "candidate_inputs_recorded_as_values": False,
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
            "raw_row_material_recorded": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
        },
        "next_gate": {
            "kind": "swe_bench_pro_one_instance_execution_gate",
            "ready": False,
            "needs_explicit_execution_scope": True,
            "needs_raw_sample_private_reducer": True,
            "needs_patch_producer_decision": True,
            "needs_docker_pull_run_decision": True,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "swe-bench-pro",
        "benchmark_id": packet["benchmark_id"],
        "benchmark_revision": packet["source"]["dataset_revision"],
        "source_commit": packet["source"]["runner_commit"],
        "mode": "one_instance_launch_packet_no_run",
        "real_run": False,
        "dry_run": True,
        "selected_instance": {
            "repo": packet["selected_instance"]["repo"],
            "instance_id": packet["selected_instance"]["instance_id"],
            "image_tag": packet["public_image_metadata"]["tag"],
            "image_digest": packet["public_image_metadata"]["digest"],
        },
        "provider": {
            "kind": "local_docker_metadata_only",
            "context": packet["local_provider_metadata"]["docker_context"],
            "server_architecture": packet["local_provider_metadata"]["server_architecture"],
            "planned_platform": packet["launch_readiness"]["planned_docker_platform"],
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
            "public_image_metadata_available": True,
            "hash_only_task_material": True,
            "no_docker_pull": True,
            "no_docker_run": True,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_patch_generation": True,
            "no_patch_evaluation": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "execution_gate_required": True,
        },
        "trials": [
            {
                "task_hash": packet["selected_instance"]["instance_id"],
                "runner_status": "blocked",
                "exception_type": "not_run_launch_packet_only",
                "image_digest": packet["public_image_metadata"]["digest"],
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
    packet = build_launch_packet()
    run_event = reduce_to_benchmark_run(packet)
    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["public_image_metadata"]["size_bytes"] == IMAGE_SIZE_BYTES, packet
    assert packet["public_image_metadata"]["architecture"] == "amd64", packet
    assert packet["local_provider_metadata"]["server_architecture"] == LOCAL_DOCKER_SERVER_ARCH, packet
    assert packet["launch_readiness"]["no_run_packet_ready"] is True, packet
    assert packet["launch_readiness"]["execution_ready"] is False, packet
    assert packet["launch_readiness"]["platform_mismatch_requires_explicit_platform"] is True, packet
    assert packet["runner_input_boundary"]["raw_sample_path_ready"] is False, packet
    assert packet["runner_input_boundary"]["patch_path_ready"] is False, packet
    assert packet["execution_boundary"]["docker_image_pulled"] is False, packet
    assert packet["execution_boundary"]["docker_container_started"] is False, packet
    assert packet["execution_boundary"]["codex_cli_invoked"] is False, packet
    assert run_event["validation"]["hash_only_task_material"] is True, run_event
    assert run_event["validation"]["no_docker_pull"] is True, run_event
    assert run_event["validation"]["execution_gate_required"] is True, run_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "instance_id": INSTANCE_ID,
        "image_repository": IMAGE_REPOSITORY,
        "image_tag": IMAGE_TAG,
        "image_digest": IMAGE_DIGEST,
        "image_size_bytes": IMAGE_SIZE_BYTES,
        "local_docker_context": LOCAL_DOCKER_CONTEXT,
        "planned_docker_platform": "linux/amd64",
        "execution_ready": packet["launch_readiness"]["execution_ready"],
        "events": [packet["schema_version"], run_event["schema_version"]],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
