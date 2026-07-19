from __future__ import annotations

from ...control_plane.agents.multi_agent.contract import build_three_layer_minimality_contract
from .knn_demo_workspace import (
    KNN_DEMO_CONTRACT_FILE,
    KNN_DEMO_DEV_EVAL_COMMAND,
    KNN_DEMO_EDITABLE_SCOPE,
    KNN_DEMO_HOLDOUT_EVAL_COMMAND,
    KNN_DEMO_PROTECTED_SCOPE,
)


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
    "baseline_source": "generated_knn_benchmark_workspace",
    "question_text_supplies_baseline": False,
    "metric_name": "speedup",
    "baseline_metric": 1.0,
    "workspace_materializer": "built_in_knn_speedup_workspace_v0",
    "benchmark_contract_file": KNN_DEMO_CONTRACT_FILE,
    "editable_scope": list(KNN_DEMO_EDITABLE_SCOPE),
    "protected_scope": list(KNN_DEMO_PROTECTED_SCOPE),
    "dev_eval_command": KNN_DEMO_DEV_EVAL_COMMAND,
    "holdout_eval_command": KNN_DEMO_HOLDOUT_EVAL_COMMAND,
    "holdout_split": "test",
    "claim_boundary": (
        "The KNN baseline is a generated benchmark workspace. Only solution.py is "
        "editable; improvement claims require public-safe dev and held-out command output."
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
            "metric_contract_hints",
            "domain_defaults",
        ],
        preset_forbidden_mechanics=[
            "multi_agent_runner",
            "real_codex_tui_panes",
            "workspace_and_trust_safe_launch",
            "decentralized_a2a_driver",
            "pane_local_a2a_status_check",
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
