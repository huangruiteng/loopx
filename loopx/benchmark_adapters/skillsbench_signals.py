from __future__ import annotations

from typing import Any

from ..control_plane.runtime.benchmark_projection import (
    build_benchmark_solution_quality_signals,
)


def build_skillsbench_solution_quality_signals(
    benchmark_run: dict[str, Any],
) -> dict[str, Any]:
    """Compatibility entry for the original SkillsBench-named projection."""

    return build_benchmark_solution_quality_signals(benchmark_run)
