from __future__ import annotations

from ..multi_agent.contract import build_three_layer_minimality_contract


AUTO_RESEARCH_DEFAULT_GOAL_ID = "loopx-auto-research-demo"
AUTO_RESEARCH_DEFAULT_OBJECTIVE = (
    "Improve a bounded research candidate through public-safe multi-agent evidence."
)
AUTO_RESEARCH_PRESET_ID = "auto_research_thin_preset"
AUTO_RESEARCH_KNN_DEMO_PRESET_ID = "knn-demo"
AUTO_RESEARCH_SUPPORTED_PRESET_IDS = (AUTO_RESEARCH_KNN_DEMO_PRESET_ID,)

AUTO_RESEARCH_KNN_DEMO_CONTEXT = {
    "schema_version": "auto_research_preset_context_v0",
    "preset_id": AUTO_RESEARCH_KNN_DEMO_PRESET_ID,
    "source": "built_in_demo_preset",
    "baseline_source": "preset_fixture_not_question_text",
    "question_text_supplies_baseline": False,
    "metric_name": "holdout_metric",
    "baseline_metric": 1.0,
    "protected_scope": ["metric_definition", "baseline_metric", "holdout_split"],
    "claim_boundary": (
        "The KNN baseline and holdout split come from the explicit demo preset; "
        "improvement claims still require public-safe evidence."
    ),
}


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
            "default_loopx_skill_bootstrap",
            "fixed_a2a_wake_prompt",
            "kernel_default_skill_prompting",
        ],
        extension_points=[
            "role_overrides",
            "metric_adapter",
            "evidence_packet_adapter",
            "data_or_eval_entrypoint",
        ],
    )
