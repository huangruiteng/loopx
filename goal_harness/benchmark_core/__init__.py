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

__all__ = [
    "AdapterClassification",
    "BENCHMARK_CANONICAL_LIFECYCLE_SCHEMA_VERSION",
    "BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION",
    "BenchmarkAdapter",
    "BenchmarkLifecyclePhase",
    "BenchmarkRequest",
    "build_benchmark_candidate_source_boundary",
    "build_codex_app_parity_posthoc_check",
    "CANONICAL_LIFECYCLE_PHASES",
    "classify_benchmark_artifact_path",
    "classify_benchmark_candidate_source_path",
    "CODEX_APP_PARITY_REQUIRED_CLI_CALLS",
    "CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION",
    "CODEX_APP_PARITY_TARGET",
    "IngestResult",
    "filter_public_benchmark_artifact_paths",
    "LaunchResult",
    "LedgerUpdate",
    "Observation",
    "PreflightResult",
    "RoundReward",
    "RunHandle",
    "canonical_lifecycle",
    "compact_round_rewards",
    "load_json_object",
    "load_jsonl_objects",
    "optional_float",
    "optional_positive_int",
    "render_codex_app_parity_posthoc_check_markdown",
    "summarize_round_rewards",
]
