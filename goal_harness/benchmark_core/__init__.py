"""Shared benchmark harness contracts.

This package is intentionally small: benchmark-specific launchers should live
in adapters, while the control plane consumes these common shapes.
"""

from .adapter import (
    AdapterClassification,
    BenchmarkAdapter,
    BenchmarkRequest,
    IngestResult,
    LaunchResult,
    LedgerUpdate,
    Observation,
    PreflightResult,
    RunHandle,
)
from .attempts import (
    BENCHMARK_ATTEMPT_ACCOUNTING_SCHEMA_VERSION,
    BenchmarkAttemptPhase,
    BenchmarkFailureClass,
    build_benchmark_attempt_accounting,
    classify_benchmark_failure,
)
from .artifacts import (
    build_benchmark_candidate_source_boundary,
    classify_benchmark_artifact_path,
    classify_benchmark_candidate_source_path,
    filter_public_benchmark_artifact_paths,
)
from .lifecycle import (
    BENCHMARK_CANONICAL_LIFECYCLE_SCHEMA_VERSION,
    BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION,
    CANONICAL_LIFECYCLE_PHASES,
    BenchmarkLifecyclePhase,
    canonical_lifecycle,
)
from .io import (
    load_json_object,
    load_jsonl_objects,
    optional_float,
    optional_positive_int,
)
from .parity import (
    CODEX_APP_PARITY_REQUIRED_CLI_CALLS,
    CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION,
    CODEX_APP_PARITY_TARGET,
    build_codex_app_parity_posthoc_check,
    render_codex_app_parity_posthoc_check_markdown,
)
from .rounds import RoundReward, compact_round_rewards, summarize_round_rewards
from .run_permissions import (
    DEFAULT_RUN_PERMISSION_ALLOWED_ACTIONS,
    DEFAULT_RUN_PERMISSION_FORBIDDEN_ACTIONS,
    RUN_PERMISSION_POLICY_SCHEMA_VERSION,
    RUN_PERMISSION_QUOTA_PROJECTION_SCHEMA_VERSION,
    RunPermissionAction,
    build_run_permission_policy,
    compact_run_permission_policy_for_quota,
    validate_run_permission_policy,
)
from .split_control import (
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_EXECUTION_SEAM_SCHEMA_VERSION,
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_LAUNCH_PLAN_SCHEMA_VERSION,
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_RUNNER_BATCH_SCHEMA_VERSION,
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION,
    DEFAULT_SPLIT_CONTROL_BENCHMARK_IDS,
    build_split_control_remote_executor_execution_seam,
    build_split_control_remote_executor_launch_plan,
    build_split_control_remote_executor_readiness,
    build_split_control_remote_executor_runner_batch,
)

__all__ = [
    "AdapterClassification",
    "BENCHMARK_ATTEMPT_ACCOUNTING_SCHEMA_VERSION",
    "BENCHMARK_CANONICAL_LIFECYCLE_SCHEMA_VERSION",
    "BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION",
    "BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_EXECUTION_SEAM_SCHEMA_VERSION",
    "BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_LAUNCH_PLAN_SCHEMA_VERSION",
    "BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_RUNNER_BATCH_SCHEMA_VERSION",
    "BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION",
    "BenchmarkAdapter",
    "BenchmarkAttemptPhase",
    "BenchmarkFailureClass",
    "BenchmarkLifecyclePhase",
    "BenchmarkRequest",
    "build_benchmark_attempt_accounting",
    "build_run_permission_policy",
    "build_benchmark_candidate_source_boundary",
    "build_codex_app_parity_posthoc_check",
    "build_split_control_remote_executor_execution_seam",
    "build_split_control_remote_executor_launch_plan",
    "build_split_control_remote_executor_readiness",
    "build_split_control_remote_executor_runner_batch",
    "CANONICAL_LIFECYCLE_PHASES",
    "classify_benchmark_artifact_path",
    "classify_benchmark_candidate_source_path",
    "classify_benchmark_failure",
    "CODEX_APP_PARITY_REQUIRED_CLI_CALLS",
    "CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION",
    "CODEX_APP_PARITY_TARGET",
    "DEFAULT_RUN_PERMISSION_ALLOWED_ACTIONS",
    "DEFAULT_RUN_PERMISSION_FORBIDDEN_ACTIONS",
    "DEFAULT_SPLIT_CONTROL_BENCHMARK_IDS",
    "IngestResult",
    "filter_public_benchmark_artifact_paths",
    "LaunchResult",
    "LedgerUpdate",
    "Observation",
    "PreflightResult",
    "RoundReward",
    "RunHandle",
    "RUN_PERMISSION_POLICY_SCHEMA_VERSION",
    "RUN_PERMISSION_QUOTA_PROJECTION_SCHEMA_VERSION",
    "RunPermissionAction",
    "canonical_lifecycle",
    "compact_run_permission_policy_for_quota",
    "compact_round_rewards",
    "load_json_object",
    "load_jsonl_objects",
    "optional_float",
    "optional_positive_int",
    "render_codex_app_parity_posthoc_check_markdown",
    "summarize_round_rewards",
    "validate_run_permission_policy",
]
