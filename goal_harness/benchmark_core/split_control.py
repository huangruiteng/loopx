from __future__ import annotations

from typing import Any, Mapping, Sequence


BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION = (
    "benchmark_split_control_remote_executor_readiness_v0"
)

DEFAULT_SPLIT_CONTROL_BENCHMARK_IDS = (
    "terminal-bench@2.0",
    "skillsbench@1.1",
    "agents-last-exam@local-docker",
)

REMOTE_EXECUTOR_BASE_REQUIREMENTS = (
    "docker_available",
    "python_available",
    "git_available",
    "rsync_available",
)

REMOTE_AGENT_COMPONENT_FACTS = (
    "codex_available",
    "codex_acp_available",
)


def _truthy(value: Any) -> bool:
    return value is True


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]


def _missing_bool_keys(source: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    return [key for key in keys if not _truthy(source.get(key))]


def _benchmark_status(
    benchmark_id: str,
    *,
    local_agent_ready: bool,
    remote_executor_base_ready: bool,
    remote_executor: Mapping[str, Any],
    adapter: Mapping[str, Any],
) -> dict[str, Any]:
    split_control_adapter_ready = _truthy(adapter.get("split_control_adapter_ready"))
    runner_tooling_ready = _truthy(adapter.get("runner_tooling_ready"))
    task_data_ready = _truthy(adapter.get("task_data_ready"))
    requires_remote_node = _truthy(adapter.get("requires_remote_node"))
    remote_node_ready = _truthy(remote_executor.get("node_available")) and _truthy(
        remote_executor.get("npm_available")
    )

    blockers: list[str] = []
    if not local_agent_ready:
        blockers.append("local_agent_not_ready")
    if not remote_executor_base_ready:
        blockers.append("remote_executor_base_missing")
    if not split_control_adapter_ready:
        blockers.append("split_control_adapter_missing")
    if not runner_tooling_ready:
        blockers.append("remote_runner_tooling_missing")
    if not task_data_ready:
        blockers.append("remote_task_data_or_image_missing")
    if requires_remote_node and not remote_node_ready:
        blockers.append("remote_node_runtime_missing")
    blockers.extend(_string_list(adapter.get("known_blockers")))

    ready = not blockers
    return {
        "benchmark_id": benchmark_id,
        "ready_for_split_control_execution": ready,
        "first_blocker": blockers[0] if blockers else "ready",
        "blockers": blockers,
        "local_agent_ready": local_agent_ready,
        "remote_executor_base_ready": remote_executor_base_ready,
        "split_control_adapter_ready": split_control_adapter_ready,
        "runner_tooling_ready": runner_tooling_ready,
        "task_data_ready": task_data_ready,
        "requires_remote_node": requires_remote_node,
        "remote_node_ready": remote_node_ready,
        "remote_codex_required": False,
        "remote_codex_acp_required": False,
        "remote_codex_missing_is_blocker": False,
    }


def build_split_control_remote_executor_readiness(
    *,
    benchmark_ids: Sequence[str] = DEFAULT_SPLIT_CONTROL_BENCHMARK_IDS,
    local_agent: Mapping[str, Any] | None = None,
    remote_executor: Mapping[str, Any] | None = None,
    adapter_readiness: Mapping[str, Mapping[str, Any]] | None = None,
    max_parallel_cases: int = 4,
) -> dict[str, Any]:
    """Build a public-safe local-agent / remote-executor benchmark gate.

    The contract is intentionally diagnostic. It never asks the remote host to
    own Codex auth, Codex ACP, or model API calls; those remain local agent
    responsibilities. Remote facts only describe runner capacity and data/tool
    readiness.
    """

    local = _as_dict(local_agent)
    remote = _as_dict(remote_executor)
    adapters = dict(adapter_readiness or {})

    local_missing = _missing_bool_keys(
        local,
        (
            "codex_cli_available",
            "goal_harness_available",
            "codex_auth_ready",
            "model_invocation_local",
        ),
    )
    local_agent_ready = not local_missing and _truthy(local.get("codex_auth_local_only"))

    remote_base_missing = _missing_bool_keys(remote, REMOTE_EXECUTOR_BASE_REQUIREMENTS)
    remote_executor_base_ready = not remote_base_missing

    statuses = [
        _benchmark_status(
            benchmark_id,
            local_agent_ready=local_agent_ready,
            remote_executor_base_ready=remote_executor_base_ready,
            remote_executor=remote,
            adapter=_as_dict(adapters.get(benchmark_id)),
        )
        for benchmark_id in benchmark_ids
    ]
    ready_benchmark_ids = [
        item["benchmark_id"]
        for item in statuses
        if item["ready_for_split_control_execution"]
    ]
    blocked_benchmark_ids = [
        item["benchmark_id"]
        for item in statuses
        if not item["ready_for_split_control_execution"]
    ]
    next_repair = next(
        (
            {
                "benchmark_id": item["benchmark_id"],
                "first_blocker": item["first_blocker"],
                "blockers": item["blockers"],
            }
            for item in statuses
            if not item["ready_for_split_control_execution"]
        ),
        None,
    )

    if not local_agent_ready:
        first_blocker = "local_agent_not_ready"
    elif not remote_executor_base_ready:
        first_blocker = "remote_executor_base_missing"
    elif any(not item["split_control_adapter_ready"] for item in statuses):
        first_blocker = "split_control_adapter_missing"
    elif any(not item["runner_tooling_ready"] for item in statuses):
        first_blocker = "remote_runner_tooling_missing"
    elif any(not item["task_data_ready"] for item in statuses):
        first_blocker = "remote_task_data_or_image_missing"
    elif any("remote_node_runtime_missing" in item["blockers"] for item in statuses):
        first_blocker = "remote_node_runtime_missing"
    else:
        first_blocker = "ready_for_parallel_remote_executor_rotation"

    ready_count = len(ready_benchmark_ids)
    max_parallel = max(1, int(max_parallel_cases))
    remote_agent_missing = {
        key: not _truthy(remote.get(key)) for key in REMOTE_AGENT_COMPONENT_FACTS
    }
    return {
        "schema_version": BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION,
        "route": {
            "mode": "local_agent_remote_executor",
            "local_agent_owns": [
                "codex_cli",
                "codex_auth",
                "goal_harness_state",
                "model_invocation",
                "planning_and_patch_generation",
            ],
            "remote_executor_owns": [
                "docker",
                "runner_dependencies",
                "task_data_staging",
                "bounded_command_execution",
                "compact_result_reduction",
            ],
        },
        "ready": ready_count == len(statuses),
        "first_blocker": first_blocker,
        "local_agent": {
            "ready": local_agent_ready,
            "missing": local_missing,
            "codex_auth_local_only": _truthy(local.get("codex_auth_local_only")),
        },
        "remote_executor": {
            "base_ready": remote_executor_base_ready,
            "base_missing": remote_base_missing,
            "codex_available": _truthy(remote.get("codex_available")),
            "codex_acp_available": _truthy(remote.get("codex_acp_available")),
            "node_available": _truthy(remote.get("node_available")),
            "npm_available": _truthy(remote.get("npm_available")),
            "remote_agent_components_missing": remote_agent_missing,
            "remote_agent_components_blocking": False,
        },
        "benchmark_statuses": statuses,
        "readiness_matrix": {
            "ready_benchmark_ids": ready_benchmark_ids,
            "blocked_benchmark_ids": blocked_benchmark_ids,
            "next_ready_batch_benchmark_ids": ready_benchmark_ids[:max_parallel],
            "next_repair_target": next_repair,
            "has_launchable_subset": bool(ready_benchmark_ids),
            "all_requested_benchmarks_ready": ready_count == len(statuses),
        },
        "parallel_policy": {
            "max_parallel_cases": max_parallel,
            "suggested_next_batch_size": min(max_parallel, ready_count),
            "parallelize_only_ready_benchmarks": True,
        },
        "boundary": {
            "codex_auth_sync_allowed": False,
            "credential_sync_allowed": False,
            "remote_codex_invocation_allowed": False,
            "remote_codex_acp_invocation_allowed": False,
            "remote_model_api_invocation_allowed": False,
            "raw_task_material_public": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
        "next_action": (
            "launch bounded parallel remote-executor batch"
            if ready_count
            else "repair split-control adapter, runner tooling, or task-data gates"
        ),
    }
