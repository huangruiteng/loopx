from __future__ import annotations

from ..multi_agent.contract import build_three_layer_minimality_contract


AUTO_RESEARCH_DEFAULT_GOAL_ID = "loopx-auto-research-demo"
AUTO_RESEARCH_DEFAULT_OBJECTIVE = (
    "Improve a bounded research candidate through public-safe multi-agent evidence."
)
AUTO_RESEARCH_PRESET_ID = "auto_research_thin_preset"


def build_auto_research_layer_contract() -> dict[str, object]:
    """Return the reusable layer split for auto-research as a thin preset."""

    return build_three_layer_minimality_contract(
        product_id="auto-research",
        preset_id=AUTO_RESEARCH_PRESET_ID,
        user_intent_fields=[
            "topic_or_objective",
            "rounds",
            "role_overrides",
            "data_or_eval_entrypoint",
        ],
        preset_responsibilities=[
            "research_roles",
            "handoff_hints",
            "metric_evidence_loop",
            "domain_defaults",
        ],
        preset_forbidden_mechanics=[
            "multi_agent_runner",
            "real_codex_tui_panes",
            "workspace_and_trust_safe_launch",
            "decentralized_a2a_driver",
            "pane_local_a2a_tick",
            "todo_evidence_status_protocol",
            "compact_human_status",
        ],
        extension_points=[
            "role_overrides",
            "metric_adapter",
            "evidence_packet_adapter",
            "data_or_eval_entrypoint",
        ],
    )
