from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence
from typing import Any


def _configure_command(
    goal_id: str,
    *arguments: str,
    execute: bool = False,
) -> str:
    parts = ["loopx", "configure-goal", "--goal-id", goal_id, *arguments]
    if execute:
        parts.append("--execute")
    return shlex.join(parts)


def build_goal_configuration_catalog(
    *,
    goal_id: str,
    settings: Mapping[str, Any],
    feature_summary: Mapping[str, Any],
    default_multi_subagent_max_children: int,
    explore_harness_profiles: Sequence[str],
) -> dict[str, Any]:
    """Build the on-demand configuration read model for optional features."""

    orchestration = (
        settings.get("orchestration")
        if isinstance(settings.get("orchestration"), Mapping)
        else {}
    )
    graph = (
        feature_summary.get("explore_graph")
        if isinstance(feature_summary.get("explore_graph"), Mapping)
        else {}
    )
    harness = (
        feature_summary.get("explore_harness")
        if isinstance(feature_summary.get("explore_harness"), Mapping)
        else {}
    )
    lark_event_inbox = (
        feature_summary.get("lark_event_inbox")
        if isinstance(feature_summary.get("lark_event_inbox"), Mapping)
        else {}
    )
    reward_memory = (
        feature_summary.get("reward_memory")
        if isinstance(feature_summary.get("reward_memory"), Mapping)
        else {}
    )
    inspect_command = _configure_command(goal_id)
    multi_enable_args = (
        "--multi-subagent-feature",
        "enabled",
        "--max-children",
        str(default_multi_subagent_max_children),
        "--allowed-domain",
        "<bounded-domain>",
    )
    graph_enable_args = ("--explore-graph-enabled",)
    harness_enable_args = (
        "--explore-harness-enabled",
        "--explore-harness-profile",
        "generic",
    )

    return {
        "schema_version": "loopx_goal_configuration_catalog_v0",
        "scope": "default_off_optional_capabilities",
        "all_settings_help_command": "loopx configure-goal --help",
        "disclosure_policy": {
            "mode": "on_demand",
            "first_run_configuration_required": False,
            "inspect_command": inspect_command,
            "mutation_policy": "preview_without_execute_then_apply_explicitly",
            "agent_rule": (
                "Do not enable optional features during onboarding or merely because they "
                "exist. Inspect this catalog only when the task needs the capability, then "
                "preview and explain the boundary change before apply."
            ),
        },
        "features": [
            {
                "feature_id": "multi_subagent",
                "display_name": "Bounded child agents",
                "availability": "supported_opt_in",
                "default": {"enabled": False},
                "current": {
                    "enabled": feature_summary.get("multi_subagent") == "enabled",
                    "max_children": orchestration.get("max_children"),
                    "allowed_domains": list(orchestration.get("allowed_domains") or []),
                },
                "required_inputs": {
                    "bounded-domain": (
                        "Replace the placeholder with one public-safe child-agent "
                        "responsibility domain. Repeat --allowed-domain when needed."
                    )
                },
                "consider_when": (
                    "The goal has at least two independent, non-overlapping work items and "
                    "the host can run child agents."
                ),
                "effect": "Allows bounded host child-agent orchestration for this goal.",
                "does_not": [
                    "create an agent hierarchy or durable authority",
                    "bypass todo claims, quota, gates, capabilities, or write scope",
                ],
                "commands": {
                    "preview_enable": _configure_command(goal_id, *multi_enable_args),
                    "apply_enable": _configure_command(
                        goal_id, *multi_enable_args, execute=True
                    ),
                    "preview_disable": _configure_command(
                        goal_id, "--multi-subagent-feature", "off"
                    ),
                    "apply_disable": _configure_command(
                        goal_id, "--multi-subagent-feature", "off", execute=True
                    ),
                    "verify": [
                        inspect_command,
                        shlex.join(
                            ["loopx", "quota", "should-run", "--goal-id", goal_id]
                        ),
                    ],
                },
                "documentation": {
                    "path": "docs/codex-subagent-orchestration.md",
                    "url": (
                        "https://github.com/huangruiteng/loopx/blob/main/"
                        "docs/codex-subagent-orchestration.md"
                    ),
                },
            },
            {
                "feature_id": "explore_graph",
                "display_name": "Explore Graph",
                "availability": "supported_opt_in",
                "default": {"enabled": False},
                "current": {"enabled": graph.get("enabled") is True},
                "consider_when": (
                    "The goal needs a durable topology of hypotheses, evidence, decisions, "
                    "or an already configured operator-facing graph sink."
                ),
                "effect": "Projects durable Explore evidence after material refreshes.",
                "does_not": [
                    "enable Explore Harness",
                    "spawn workers, claim todos, or spend quota by itself",
                ],
                "commands": {
                    "preview_enable": _configure_command(goal_id, *graph_enable_args),
                    "apply_enable": _configure_command(
                        goal_id, *graph_enable_args, execute=True
                    ),
                    "preview_disable": _configure_command(
                        goal_id, "--no-explore-graph-enabled"
                    ),
                    "apply_disable": _configure_command(
                        goal_id, "--no-explore-graph-enabled", execute=True
                    ),
                    "verify": [
                        inspect_command,
                        shlex.join(
                            [
                                "loopx",
                                "explore",
                                "graph",
                                "--goal-id",
                                goal_id,
                                "--graph-format",
                                "mermaid",
                            ]
                        ),
                    ],
                },
                "documentation": {
                    "path": "docs/capabilities/explore/README.md",
                    "url": (
                        "https://github.com/huangruiteng/loopx/blob/main/"
                        "docs/capabilities/explore/README.md"
                    ),
                },
            },
            {
                "feature_id": "explore_harness",
                "display_name": "Explore Harness",
                "availability": "supported_opt_in",
                "default": {"enabled": False, "profile": "generic"},
                "current": {
                    "enabled": harness.get("enabled") is True,
                    "profile": harness.get("profile"),
                },
                "profiles": list(explore_harness_profiles),
                "consider_when": (
                    "The goal benefits from comparing alternative branches with explicit "
                    "evaluation criteria and guardrails."
                ),
                "effect": "Enables read-only Explore branch and worker-lane planning.",
                "does_not": [
                    "enable Explore Graph",
                    "launch workers, claim todos, acquire leases, mutate state, or spend quota",
                ],
                "commands": {
                    "preview_enable": _configure_command(goal_id, *harness_enable_args),
                    "apply_enable": _configure_command(
                        goal_id, *harness_enable_args, execute=True
                    ),
                    "preview_disable": _configure_command(
                        goal_id, "--no-explore-harness-enabled"
                    ),
                    "apply_disable": _configure_command(
                        goal_id, "--no-explore-harness-enabled", execute=True
                    ),
                    "verify": [
                        inspect_command,
                        shlex.join(
                            [
                                "loopx",
                                "explore",
                                "worker-branch-plan",
                                "--goal-id",
                                goal_id,
                                "--harness-profile",
                                str(harness.get("profile") or "generic"),
                            ]
                        ),
                    ],
                },
                "documentation": {
                    "path": "docs/capabilities/explore/README.md",
                    "url": (
                        "https://github.com/huangruiteng/loopx/blob/main/"
                        "docs/capabilities/explore/README.md"
                    ),
                },
            },
            {
                "feature_id": "reward_memory",
                "display_name": "Reward Memory experiment",
                "availability": "experimental_opt_in",
                "default": {"enabled": False},
                "current": {
                    "enabled": reward_memory.get("enabled") is True,
                    "experimental": reward_memory.get("experimental") is True,
                    "config_pointer_registered": reward_memory.get(
                        "config_pointer_registered"
                    )
                    is True,
                    "enabled_agents": list(reward_memory.get("enabled_agents") or []),
                },
                "required_inputs": {
                    "ignored-reward-memory-config": (
                        "Replace the placeholder with a repo-relative ignored JSON "
                        "config under .loopx/config/."
                    ),
                    "agent-id": (
                        "Replace the placeholder with one registered agent lane. "
                        "Repeat --reward-memory-agent for another explicit lane."
                    ),
                },
                "consider_when": (
                    "A named agent lane should trial reviewed, scoped operating "
                    "lessons through a configured context provider."
                ),
                "effect": (
                    "Allows only the named agent lanes to resolve the ignored "
                    "provider binding for explicit Reward Memory ingest and recall."
                ),
                "does_not": [
                    "make any provider a global LoopX feature or dependency",
                    "install, authenticate, or configure the selected provider",
                    "enable every agent, automatically ingest feedback, or automatically recall",
                    "bypass scope, authority, freshness, conflict, or exact-readback guards",
                ],
                "commands": {
                    "preview_enable": _configure_command(
                        goal_id,
                        "--reward-memory-config",
                        "<ignored-reward-memory-config>",
                        "--reward-memory-agent",
                        "<agent-id>",
                    ),
                    "apply_enable": _configure_command(
                        goal_id,
                        "--reward-memory-config",
                        "<ignored-reward-memory-config>",
                        "--reward-memory-agent",
                        "<agent-id>",
                        execute=True,
                    ),
                    "preview_disable": _configure_command(
                        goal_id, "--clear-reward-memory-config"
                    ),
                    "apply_disable": _configure_command(
                        goal_id, "--clear-reward-memory-config", execute=True
                    ),
                    "verify": [
                        inspect_command,
                        shlex.join(
                            [
                                "loopx",
                                "reward-memory",
                                "experiment-status",
                                "--goal-id",
                                goal_id,
                                "--agent-id",
                                "<agent-id>",
                            ]
                        ),
                    ],
                },
                "documentation": {
                    "path": "docs/reference/protocols/reward-memory-architecture-v0.md",
                    "url": (
                        "https://github.com/huangruiteng/loopx/blob/main/"
                        "docs/reference/protocols/reward-memory-architecture-v0.md"
                    ),
                },
            },
            {
                "feature_id": "lark_event_inbox",
                "display_name": "Lark event inbox",
                "availability": "supported_opt_in",
                "default": {"enabled": False},
                "current": {
                    "enabled": lark_event_inbox.get("enabled") is True,
                    "config_pointer_registered": lark_event_inbox.get(
                        "config_pointer_registered"
                    )
                    is True,
                },
                "required_inputs": {
                    "ignored-inbox-config": (
                        "Replace the placeholder with a repo-relative ignored JSON "
                        "config under .loopx/config/."
                    )
                },
                "consider_when": (
                    "A goal should consume durable Lark feedback without keeping an "
                    "agent process or hand-editing its heartbeat prompt."
                ),
                "effect": (
                    "Projects a goal-configured generic inbox into quota and generated "
                    "heartbeat drain behavior."
                ),
                "does_not": [
                    "install lark-cli, authenticate a user, or configure bot credentials",
                    "send Lark messages or turn inbound feedback into an automatic write",
                ],
                "commands": {
                    "preview_enable": _configure_command(
                        goal_id,
                        "--lark-event-inbox-config",
                        "<ignored-inbox-config>",
                    ),
                    "apply_enable": _configure_command(
                        goal_id,
                        "--lark-event-inbox-config",
                        "<ignored-inbox-config>",
                        execute=True,
                    ),
                    "preview_disable": _configure_command(
                        goal_id, "--clear-lark-event-inbox-config"
                    ),
                    "apply_disable": _configure_command(
                        goal_id, "--clear-lark-event-inbox-config", execute=True
                    ),
                    "verify": [
                        inspect_command,
                        shlex.join(
                            [
                                "loopx",
                                "lark-inbox",
                                "drain",
                                "--goal-id",
                                goal_id,
                                "--project",
                                ".",
                            ]
                        ),
                    ],
                },
                "documentation": {
                    "path": "docs/capabilities/lark-event-inbox.md",
                    "url": (
                        "https://github.com/huangruiteng/loopx/blob/main/"
                        "docs/capabilities/lark-event-inbox.md"
                    ),
                },
            },
        ],
    }
