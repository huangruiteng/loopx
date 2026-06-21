from __future__ import annotations

from typing import Any, Mapping, Sequence


BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION = (
    "benchmark_split_control_remote_executor_readiness_v0"
)
BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_LAUNCH_PLAN_SCHEMA_VERSION = (
    "benchmark_split_control_remote_executor_launch_plan_v0"
)
BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_RUNNER_BATCH_SCHEMA_VERSION = (
    "benchmark_split_control_remote_executor_runner_batch_v0"
)
BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_EXECUTION_SEAM_SCHEMA_VERSION = (
    "benchmark_split_control_remote_executor_execution_seam_v1"
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

DEFAULT_SPLIT_CONTROL_LAUNCH_COMMAND_LABELS = {
    "terminal-bench@2.0": "terminal-bench compact no-upload remote-executor dry-run or mini-pair",
    "skillsbench@1.1": "skillsbench compact no-upload remote-executor dry-run or mini-pair",
    "agents-last-exam@local-docker": "agents-last-exam provider/task-data validation gate",
}

PUBLIC_RUNNER_RESULT_FIELDS = (
    "status",
    "score",
    "best_score",
    "final_score",
    "first_success_round",
    "duration_s",
    "blocker",
    "compact_result_or_blocker",
    "summary",
)

RAW_RUNNER_RESULT_KEYS = (
    "raw_task_text",
    "raw_logs",
    "raw_trajectory",
    "verifier_output_body",
    "credentials",
    "local_absolute_paths",
    "remote_absolute_paths",
    "remote_command",
    "shell_command",
    "stdout",
    "stderr",
    "trace",
    "transcript",
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
            "loopx_available",
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
                "loopx_state",
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


def build_split_control_remote_executor_launch_plan(
    readiness: Mapping[str, Any],
    *,
    command_labels: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Project a readiness payload into a non-executing launch plan.

    The launch plan is deliberately a control-plane artifact. It may name a
    compact command label for the local controller to run later, but it does
    not include raw task text, credentials, local paths, remote shell snippets,
    or executable command bodies. The caller still owns the actual benchmark
    launcher and must re-check current readiness before execution.
    """

    matrix = _as_dict(readiness.get("readiness_matrix"))
    boundary = _as_dict(readiness.get("boundary"))
    route = _as_dict(readiness.get("route"))
    labels = {
        **DEFAULT_SPLIT_CONTROL_LAUNCH_COMMAND_LABELS,
        **dict(command_labels or {}),
    }
    ready_ids = _string_list(matrix.get("next_ready_batch_benchmark_ids"))
    blocked_ids = _string_list(matrix.get("blocked_benchmark_ids"))
    statuses = {
        str(item.get("benchmark_id")): _as_dict(item)
        for item in _as_sequence_of_mappings(readiness.get("benchmark_statuses"))
        if item.get("benchmark_id")
    }
    launch_cases = [
        {
            "benchmark_id": benchmark_id,
            "execution_mode": "local_agent_remote_executor",
            "local_agent_owns": _string_list(route.get("local_agent_owns")),
            "remote_executor_owns": _string_list(route.get("remote_executor_owns")),
            "command_label": _compact_label(labels.get(benchmark_id, "compact no-upload remote-executor launch")),
            "requires_fresh_readiness_recheck": True,
            "compact_evidence_required": True,
            "raw_material_allowed": False,
            "upload_allowed": False,
            "submit_allowed": False,
        }
        for benchmark_id in ready_ids
    ]
    third_gate = _third_gate_from_blocked_statuses(blocked_ids, statuses)
    return {
        "schema_version": BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_LAUNCH_PLAN_SCHEMA_VERSION,
        "source_schema_version": readiness.get("schema_version"),
        "ready_to_launch": bool(launch_cases),
        "launch_cases": launch_cases,
        "blocked_benchmark_ids": blocked_ids,
        "third_gate": third_gate,
        "parallel_policy": {
            **_as_dict(readiness.get("parallel_policy")),
            "launch_only_ready_cases": True,
            "recheck_before_each_case": True,
        },
        "boundary": {
            "codex_auth_stays_local": not _truthy(boundary.get("codex_auth_sync_allowed")),
            "credential_sync_allowed": _truthy(boundary.get("credential_sync_allowed")),
            "remote_codex_invocation_allowed": _truthy(boundary.get("remote_codex_invocation_allowed")),
            "remote_model_api_invocation_allowed": _truthy(boundary.get("remote_model_api_invocation_allowed")),
            "raw_task_material_public": _truthy(boundary.get("raw_task_material_public")),
            "upload_allowed": _truthy(boundary.get("upload_allowed")),
            "submit_allowed": _truthy(boundary.get("submit_allowed")),
        },
        "post_launch_evidence_contract": {
            "required_fields": [
                "benchmark_id",
                "route",
                "readiness_rechecked",
                "compact_result_or_blocker",
                "raw_material_read",
                "upload_attempted",
                "submit_attempted",
            ],
            "must_keep_private": [
                "raw_task_text",
                "raw_logs",
                "raw_trajectory",
                "verifier_output_body",
                "credentials",
                "local_absolute_paths",
            ],
        },
        "next_action": (
            "run launch_cases after fresh readiness recheck"
            if launch_cases
            else "repair third_gate before launch"
        ),
    }


def build_split_control_remote_executor_runner_batch(
    launch_plan: Mapping[str, Any],
    *,
    fresh_readiness: Mapping[str, Any] | None = None,
    case_results: Mapping[str, Mapping[str, Any]] | None = None,
    execution_mode: str = "compact_no_upload_dry_run",
) -> dict[str, Any]:
    """Build the executable public-safe runner batch from a launch plan.

    This is still a control-plane contract, not a shell launcher. It refuses to
    produce runner cases unless the caller supplies a fresh readiness payload
    whose next ready batch still covers every launch case. Compact post-launch
    results are optional and are sanitized to public evidence fields.
    """

    launch_cases = _as_sequence_of_mappings(launch_plan.get("launch_cases"))
    planned_ids = [
        str(case.get("benchmark_id"))
        for case in launch_cases
        if case.get("benchmark_id")
    ]
    fresh = _as_dict(fresh_readiness)
    fresh_matrix = _as_dict(fresh.get("readiness_matrix"))
    fresh_ready_ids = _string_list(fresh_matrix.get("next_ready_batch_benchmark_ids"))
    fresh_ready_set = set(fresh_ready_ids)
    missing_from_fresh = [
        benchmark_id for benchmark_id in planned_ids if benchmark_id not in fresh_ready_set
    ]

    blockers: list[str] = []
    if not planned_ids:
        blockers.append("launch_plan_has_no_cases")
    if not fresh:
        blockers.append("fresh_readiness_recheck_missing")
    elif missing_from_fresh:
        blockers.append("fresh_readiness_recheck_changed")

    ready_to_execute = not blockers
    runner_cases = [
        _runner_case_from_launch_case(case, execution_mode=execution_mode)
        for case in launch_cases
        if ready_to_execute
    ]

    compact_results, result_boundary = _compact_runner_results(
        case_results or {},
        allowed_benchmark_ids=planned_ids,
    )
    result_boundary_violations = result_boundary["violations"]

    if blockers:
        next_action = "refresh readiness before runner launch"
    elif not compact_results:
        next_action = "execute runner_cases and record compact evidence"
    elif result_boundary_violations:
        next_action = "repair compact evidence boundary before writeback"
    else:
        next_action = "write compact evidence and score summary"

    return {
        "schema_version": BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_RUNNER_BATCH_SCHEMA_VERSION,
        "source_schema_version": launch_plan.get("schema_version"),
        "fresh_readiness_schema_version": fresh.get("schema_version"),
        "ready_to_execute": ready_to_execute,
        "blockers": blockers,
        "planned_benchmark_ids": planned_ids,
        "fresh_ready_benchmark_ids": fresh_ready_ids,
        "stale_launch_case_ids": missing_from_fresh,
        "runner_cases": runner_cases,
        "post_launch_evidence": compact_results,
        "post_launch_evidence_boundary": result_boundary,
        "ready_to_spend": ready_to_execute
        and bool(compact_results)
        and not result_boundary_violations,
        "boundary": {
            **_as_dict(launch_plan.get("boundary")),
            "fresh_readiness_recheck_required": True,
            "raw_task_text_public": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
        "next_action": next_action,
    }


def build_split_control_remote_executor_execution_seam(
    runner_batch: Mapping[str, Any],
    *,
    command_adapters: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the machine-checkable execution seam for remote runner adapters.

    The runner batch says which benchmark families are eligible to run after a
    fresh readiness re-check. The execution seam adds the next missing layer:
    whether each family has a real command adapter and compact result reducer.
    It deliberately records labels and handle contracts only, never shell
    argv, host paths, raw logs, task text, trajectories, uploads, or submit
    paths.
    """

    batch = _as_dict(runner_batch)
    adapters = dict(command_adapters or {})
    runner_cases = _as_sequence_of_mappings(batch.get("runner_cases"))
    batch_blockers = _string_list(batch.get("blockers"))
    seam_cases = [
        _execution_seam_case_from_runner_case(
            case,
            adapter=_as_dict(adapters.get(str(case.get("benchmark_id")))),
        )
        for case in runner_cases
    ]
    missing_adapter_ids = [
        case["benchmark_id"]
        for case in seam_cases
        if not case["command_materialization"]["adapter_facts_ready"]
    ]
    missing_materializer_ids = [
        case["benchmark_id"]
        for case in seam_cases
        if case["command_materialization"]["adapter_facts_ready"]
        and not case["command_materialization"]["ready"]
    ]
    missing_reducer_ids = [
        case["benchmark_id"]
        for case in seam_cases
        if not case["result_reducer"]["ready"]
    ]
    case_blockers = [
        blocker
        for case in seam_cases
        for blocker in _string_list(case.get("blockers"))
    ]
    seam_blockers: list[str] = list(batch_blockers)
    if not runner_cases and not batch_blockers:
        seam_blockers.append("runner_batch_has_no_cases")
    if missing_adapter_ids:
        seam_blockers.append("command_adapter_missing")
    if missing_materializer_ids:
        seam_blockers.append("remote_executor_materializer_missing")
    if missing_reducer_ids:
        seam_blockers.append("compact_result_reducer_missing")
    seam_blockers.extend(
        blocker for blocker in case_blockers if blocker not in seam_blockers
    )

    ready_to_execute = (
        _truthy(batch.get("ready_to_execute"))
        and bool(seam_cases)
        and not seam_blockers
    )
    if batch_blockers or not _truthy(batch.get("ready_to_execute")):
        next_action = "repair runner_batch readiness before command materialization"
    elif missing_adapter_ids:
        next_action = "implement missing remote-executor command adapter(s)"
    elif missing_reducer_ids:
        next_action = "implement missing compact result reducer(s)"
    elif seam_blockers:
        next_action = "repair execution seam blockers before launch"
    else:
        next_action = "launch execution seam cases and ingest compact evidence"

    return {
        "schema_version": BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_EXECUTION_SEAM_SCHEMA_VERSION,
        "source_schema_version": batch.get("schema_version"),
        "ready_to_execute": ready_to_execute,
        "ready_to_spend": ready_to_execute and _truthy(batch.get("ready_to_spend")),
        "blockers": seam_blockers,
        "missing_command_adapter_ids": missing_adapter_ids,
        "missing_remote_materializer_ids": missing_materializer_ids,
        "missing_result_reducer_ids": missing_reducer_ids,
        "planned_benchmark_ids": _string_list(batch.get("planned_benchmark_ids")),
        "execution_cases": seam_cases,
        "post_launch_evidence": batch.get("post_launch_evidence") or [],
        "post_launch_evidence_boundary": _as_dict(
            batch.get("post_launch_evidence_boundary")
        ),
        "boundary": {
            **_as_dict(batch.get("boundary")),
            "shell_commands_embedded": False,
            "argv_embedded": False,
            "local_paths_embedded": False,
            "remote_paths_embedded": False,
            "raw_task_text_public": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
        "next_action": next_action,
    }


def _runner_case_from_launch_case(
    launch_case: Mapping[str, Any],
    *,
    execution_mode: str,
) -> dict[str, Any]:
    return {
        "benchmark_id": str(launch_case.get("benchmark_id")),
        "route": "local_agent_remote_executor",
        "execution_mode": _compact_label(execution_mode),
        "command_label": _compact_label(
            str(launch_case.get("command_label") or "compact no-upload runner case")
        ),
        "local_agent_owns": _string_list(launch_case.get("local_agent_owns")),
        "remote_executor_owns": _string_list(launch_case.get("remote_executor_owns")),
        "remote_executor_allowed_actions": [
            "runner_dependency_check",
            "bounded_command_execution",
            "compact_result_reduction",
        ],
        "remote_executor_disallowed_actions": [
            "codex_auth_sync",
            "credential_sync",
            "remote_model_api_invocation",
            "raw_task_text_publication",
            "raw_log_publication",
            "upload",
            "submit",
        ],
        "required_evidence_fields": [
            "benchmark_id",
            "route",
            "readiness_rechecked",
            "compact_result_or_blocker",
            "raw_material_read",
            "upload_attempted",
            "submit_attempted",
        ],
        "raw_material_allowed": False,
        "upload_allowed": False,
        "submit_allowed": False,
    }


def _execution_seam_case_from_runner_case(
    runner_case: Mapping[str, Any],
    *,
    adapter: Mapping[str, Any],
) -> dict[str, Any]:
    benchmark_id = str(runner_case.get("benchmark_id"))
    adapter_ready = _truthy(adapter.get("command_adapter_ready"))
    reducer_ready = _truthy(adapter.get("result_reducer_ready"))
    surface_contract = _as_dict(adapter.get("surface_contract"))
    if "remote_materializer_ready" in surface_contract:
        remote_materializer_ready = _truthy(
            surface_contract.get("remote_materializer_ready")
        )
    elif "remote_materializer_ready" in adapter:
        remote_materializer_ready = _truthy(adapter.get("remote_materializer_ready"))
    else:
        remote_materializer_ready = True
    local_driver = _as_dict(adapter.get("local_driver_contract"))
    remote_sandbox = _as_dict(adapter.get("remote_sandbox_contract"))
    adapter_blockers = _string_list(adapter.get("known_blockers"))
    blockers: list[str] = []
    if not adapter_ready:
        blockers.append("command_adapter_missing")
    if adapter_ready and not remote_materializer_ready:
        blockers.append("remote_executor_materializer_missing")
    if adapter_ready and remote_materializer_ready and not _truthy(
        local_driver.get("ready")
    ):
        blockers.append("local_driver_contract_missing")
    if adapter_ready and remote_materializer_ready and not _truthy(
        remote_sandbox.get("ready")
    ):
        blockers.append("remote_sandbox_contract_missing")
    if not reducer_ready:
        blockers.append("compact_result_reducer_missing")
    blockers.extend(adapter_blockers)
    materialization_ready = adapter_ready and remote_materializer_ready
    local_agent_owns = _string_list(runner_case.get("local_agent_owns")) or [
        "codex_cli",
        "codex_auth",
        "loopx_state",
        "model_invocation",
        "planning_and_patch_generation",
    ]
    remote_executor_owns = _string_list(runner_case.get("remote_executor_owns")) or [
        "docker",
        "runner_dependencies",
        "task_data_staging",
        "bounded_command_execution",
        "compact_result_reduction",
    ]
    return {
        "benchmark_id": benchmark_id,
        "route": "local_agent_remote_executor",
        "execution_mode": _compact_label(str(runner_case.get("execution_mode") or "")),
        "command_label": _compact_label(str(runner_case.get("command_label") or "")),
        "ready_to_execute_remote_command": not blockers,
        "blockers": blockers,
        "command_materialization": {
            "ready": materialization_ready,
            "adapter_facts_ready": adapter_ready,
            "status": _compact_label(
                str(
                    adapter.get("command_adapter_status")
                    or ("ready" if materialization_ready else "missing")
                )
            ),
            "entrypoint_label": _compact_label(
                str(adapter.get("entrypoint_label") or "not_materialized")
            ),
            "remote_materializer_ready": remote_materializer_ready,
            "shell_command_embedded": False,
            "argv_embedded": False,
            "host_path_embedded": False,
        },
        "local_driver_contract": {
            "ready": _truthy(local_driver.get("ready")),
            "driver_label": _compact_label(
                str(local_driver.get("driver_label") or "local_codex_driver")
            ),
            "owns": _string_list(local_driver.get("owns")) or local_agent_owns,
            "remote_request_fields": _string_list(
                local_driver.get("remote_request_fields")
            )
            or [
                "benchmark_id",
                "case_handle",
                "execution_mode",
                "no_upload",
                "compact_artifact_ref",
            ],
            "keeps_local": _string_list(local_driver.get("keeps_local"))
            or [
                "codex_auth",
                "model_invocation",
                "loopx_state",
                "raw_reasoning_trace",
            ],
            "credential_sync_allowed": False,
            "remote_model_invocation_allowed": False,
            "raw_task_text_sent_to_remote": False,
            "shell_command_embedded": False,
            "argv_embedded": False,
        },
        "remote_sandbox_contract": {
            "ready": _truthy(remote_sandbox.get("ready")),
            "sandbox_label": _compact_label(
                str(remote_sandbox.get("sandbox_label") or "remote_executor_sandbox")
            ),
            "owns": _string_list(remote_sandbox.get("owns")) or remote_executor_owns,
            "allowed_actions": _string_list(remote_sandbox.get("allowed_actions"))
            or _string_list(runner_case.get("remote_executor_allowed_actions")),
            "disallowed_actions": _string_list(
                remote_sandbox.get("disallowed_actions")
            )
            or _string_list(runner_case.get("remote_executor_disallowed_actions")),
            "returns": _string_list(remote_sandbox.get("returns"))
            or [
                "readiness_state",
                "job_handle",
                "compact_result_or_blocker",
                "cleanup_state",
            ],
            "remote_agent_runtime_allowed": False,
            "remote_codex_runtime_allowed": False,
            "remote_model_api_invocation_allowed": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
        },
        "execution_handle_contract": {
            "required_fields": _string_list(adapter.get("handle_fields"))
            or [
                "benchmark_id",
                "runner_handle",
                "readiness_rechecked",
                "poll_label",
                "cleanup_label",
                "compact_artifact_ref",
            ],
            "handle_values_may_be_private": True,
            "public_handle_shape_only": True,
        },
        "result_reducer": {
            "ready": reducer_ready,
            "label": _compact_label(
                str(adapter.get("result_reducer_label") or "not_materialized")
            ),
            "accepted_public_fields": list(PUBLIC_RUNNER_RESULT_FIELDS),
            "raw_values_copied": False,
        },
        "remote_executor_allowed_actions": _string_list(
            runner_case.get("remote_executor_allowed_actions")
        ),
        "remote_executor_disallowed_actions": _string_list(
            runner_case.get("remote_executor_disallowed_actions")
        ),
        "raw_material_allowed": False,
        "upload_allowed": False,
        "submit_allowed": False,
    }


def _compact_runner_results(
    case_results: Mapping[str, Mapping[str, Any]],
    *,
    allowed_benchmark_ids: Sequence[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = set(allowed_benchmark_ids)
    compact_results: list[dict[str, Any]] = []
    raw_key_hits: dict[str, list[str]] = {}
    unexpected_case_ids: list[str] = []
    unsafe_flags: dict[str, list[str]] = {}

    for benchmark_id, result in case_results.items():
        benchmark_key = str(benchmark_id)
        if benchmark_key not in allowed:
            unexpected_case_ids.append(benchmark_key)
            continue
        result_dict = _as_dict(result)
        raw_keys = sorted(
            key for key in result_dict if str(key).lower() in RAW_RUNNER_RESULT_KEYS
        )
        if raw_keys:
            raw_key_hits[benchmark_key] = raw_keys
        unsafe = [
            key
            for key in ("raw_material_read", "upload_attempted", "submit_attempted")
            if _truthy(result_dict.get(key))
        ]
        if unsafe:
            unsafe_flags[benchmark_key] = unsafe
        compact_results.append(
            {
                "benchmark_id": benchmark_key,
                "route": _compact_label(
                    str(result_dict.get("route") or "local_agent_remote_executor")
                ),
                "readiness_rechecked": _truthy(result_dict.get("readiness_rechecked")),
                "compact_result_or_blocker": _compact_label(
                    str(
                        result_dict.get("compact_result_or_blocker")
                        or result_dict.get("blocker")
                        or result_dict.get("summary")
                        or result_dict.get("status")
                        or "pending_compact_result"
                    )
                ),
                "status": _compact_label(str(result_dict.get("status") or "unknown")),
                "score": result_dict.get("score"),
                "best_score": result_dict.get("best_score"),
                "final_score": result_dict.get("final_score"),
                "first_success_round": result_dict.get("first_success_round"),
                "duration_s": result_dict.get("duration_s"),
                "raw_material_read": _truthy(result_dict.get("raw_material_read")),
                "upload_attempted": _truthy(result_dict.get("upload_attempted")),
                "submit_attempted": _truthy(result_dict.get("submit_attempted")),
            }
        )

    violations: list[str] = []
    if raw_key_hits:
        violations.append("raw_result_keys_present")
    if unexpected_case_ids:
        violations.append("unexpected_case_result")
    if unsafe_flags:
        violations.append("unsafe_result_flag_true")
    return compact_results, {
        "public_result_fields": list(PUBLIC_RUNNER_RESULT_FIELDS),
        "raw_result_key_hits": raw_key_hits,
        "unexpected_case_ids": unexpected_case_ids,
        "unsafe_flags": unsafe_flags,
        "violations": violations,
        "raw_result_values_copied": False,
    }


def _as_sequence_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _compact_label(value: str, max_length: int = 120) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 1]}…"


def _third_gate_from_blocked_statuses(
    blocked_ids: Sequence[str],
    statuses: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if "agents-last-exam@local-docker" not in blocked_ids:
        return {
            "benchmark_id": "agents-last-exam@local-docker",
            "required": False,
            "status": "not_blocking_current_launch_subset",
            "first_blocker": "none",
            "blockers": [],
        }
    status = _as_dict(statuses.get("agents-last-exam@local-docker"))
    return {
        "benchmark_id": "agents-last-exam@local-docker",
        "required": True,
        "status": "provider_or_task_data_gate",
        "first_blocker": status.get("first_blocker") or "remote_task_data_or_image_missing",
        "blockers": _string_list(status.get("blockers")),
        "repair_action": "validate ALE provider/task-data substrate before formal launch",
    }
