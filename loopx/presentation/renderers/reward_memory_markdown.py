"""Reward Memory fragments for the status renderer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..markdown import markdown_scalar


def append_agent_reward_memory_markdown(
    lines: list[str],
    item: dict[str, Any],
    project_asset: dict[str, Any],
) -> None:
    agent_reward_memory = (
        project_asset.get("agent_reward_memory")
        if isinstance(project_asset.get("agent_reward_memory"), dict)
        else item.get("agent_reward_memory")
        if isinstance(item.get("agent_reward_memory"), dict)
        else {}
    )
    if not agent_reward_memory:
        return
    config_runtime_route_value = agent_reward_memory.get("config_runtime_route")
    config_runtime_route: Mapping[str, Any] = (
        config_runtime_route_value
        if isinstance(config_runtime_route_value, Mapping)
        else {}
    )
    lines.append(
        "    - agent_reward_memory: "
        f"agent={markdown_scalar(agent_reward_memory.get('agent_id') or '')} "
        f"status={markdown_scalar(agent_reward_memory.get('experiment_status') or '')} "
        f"automatic_ingest={agent_reward_memory.get('automatic_ingest')} "
        f"automatic_recall={agent_reward_memory.get('automatic_recall')} "
        f"isolation={markdown_scalar(agent_reward_memory.get('isolation_mode') or '')} "
        f"enablement={markdown_scalar(agent_reward_memory.get('enablement_receipt_status') or '')} "
        f"writability={agent_reward_memory.get('writability_verified')} "
        f"runtime_scope={markdown_scalar(config_runtime_route.get('runtime_scope') or '')} "
        f"exact_readback={config_runtime_route.get('exact_readback_verified')}"
    )
    host_coverage = agent_reward_memory.get("host_coverage")
    if not isinstance(host_coverage, list):
        return
    coverage_parts = [
        (
            f"{coverage.get('host_id')}:"
            f"recall={coverage.get('automatic_recall')},"
            f"ingest={coverage.get('automatic_ingest')}"
        )
        for coverage in host_coverage
        if isinstance(coverage, dict) and coverage.get("host_id")
    ]
    if coverage_parts:
        lines.append("    - reward_memory_host_coverage: " + "; ".join(coverage_parts))
