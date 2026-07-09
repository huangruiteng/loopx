"""Runtime proxy evidence helpers for SkillsBench launches."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


def apply_proxy_runtime_env(
    environ: MutableMapping[str, str],
    proxy_env: Mapping[str, str],
    docker_config_env: Mapping[str, str],
    *,
    plan: dict[str, Any] | None,
) -> None:
    environ.update(proxy_env)
    environ.update(docker_config_env)
    if not isinstance(plan, dict):
        return
    prerequisites = plan.setdefault("runner_prerequisites", {})
    if not isinstance(prerequisites, dict):
        return
    prerequisites["benchmark_egress_proxy_agent_env_injected"] = bool(proxy_env)
    if docker_config_env.get("DOCKER_CONFIG"):
        prerequisites["benchmark_egress_proxy_docker_config_injected"] = True
        prerequisites["benchmark_egress_proxy_docker_config_path_recorded"] = False
        prerequisites["benchmark_egress_proxy_docker_config_raw_proxy_recorded"] = False
