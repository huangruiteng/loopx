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
from .lifecycle import (
    BENCHMARK_CANONICAL_LIFECYCLE_SCHEMA_VERSION,
    BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION,
    CANONICAL_LIFECYCLE_PHASES,
    BenchmarkLifecyclePhase,
    canonical_lifecycle,
)
from .rounds import RoundReward, compact_round_rewards, summarize_round_rewards

__all__ = [
    "AdapterClassification",
    "BENCHMARK_CANONICAL_LIFECYCLE_SCHEMA_VERSION",
    "BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION",
    "BenchmarkAdapter",
    "BenchmarkLifecyclePhase",
    "BenchmarkRequest",
    "CANONICAL_LIFECYCLE_PHASES",
    "IngestResult",
    "LaunchResult",
    "LedgerUpdate",
    "Observation",
    "PreflightResult",
    "RoundReward",
    "RunHandle",
    "canonical_lifecycle",
    "compact_round_rewards",
    "summarize_round_rewards",
]
