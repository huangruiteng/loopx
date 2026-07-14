from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text


REWARD_MEMORY_ARCHITECTURE_SCHEMA_VERSION = "reward_memory_architecture_v0"
REWARD_MEMORY_ROUTE_SCHEMA_VERSION = "reward_memory_pilot_meta_route_v0"

MEMORY_CLASS_IDS = (
    "run_bound_reward",
    "hard_policy",
    "soft_preference",
    "procedural_experience",
    "working_context",
)
BEHAVIOR_STATUSES = {"bug_confirmed", "by_design", "uncertain"}
EDGE_CASE_COMPLEXITIES = {"low", "medium", "high"}


def _memory_classes() -> list[dict[str, Any]]:
    return [
        {
            "class_id": "run_bound_reward",
            "purpose": "Judge one exact run or route outcome.",
            "source_kinds": ["explicit_human_reward"],
            "scope_floor": ["goal_id", "run_id"],
            "authority": "outcome_evidence_only",
            "future_influence": "candidate_review_required",
            "durability": "append_only_run_overlay",
            "supersession": "append_correction_without_rewriting_the_judged_run",
            "revocation": "append_revocation_reference",
            "expiry": "none_by_default",
            "privacy": "compact_reason_only_no_raw_chat",
        },
        {
            "class_id": "hard_policy",
            "purpose": "Constrain or veto actions at an explicit boundary.",
            "source_kinds": [
                "explicit_user_boundary",
                "repository_policy",
                "operator_gate",
                "authority_checkpoint",
            ],
            "excluded_sources": [
                "recalled_semantic_memory_without_canonical_policy_binding",
                "provider_soul_or_boundary_text_without_action_authority",
            ],
            "scope_floor": ["project_or_goal", "action_or_surface"],
            "authority": "constraint_or_veto",
            "future_influence": "deterministic_when_active_and_in_scope",
            "durability": "durable_until_superseded_revoked_or_expired",
            "supersession": "explicit_narrower_or_newer_policy_reference",
            "revocation": "explicit_authorized_revocation",
            "expiry": "required_for_temporary_policy",
            "privacy": "private_by_default_unless_rewritten_public_safe",
        },
        {
            "class_id": "soft_preference",
            "purpose": "Rank or shape an output without granting permission.",
            "source_kinds": [
                "explicit_feedback",
                "selected_option",
                "reviewed_preference_candidate",
            ],
            "scope_floor": ["workspace_or_project", "module_surface"],
            "authority": "advisory_ranking_or_rewrite",
            "future_influence": "allowed_only_on_module_owned_surfaces",
            "durability": "durable_after_explicit_review",
            "supersession": "newer_scoped_preference_or_conflict_retirement",
            "revocation": "operator_edit_reject_or_retire",
            "expiry": "recommended_for_unreinforced_or_time_sensitive_items",
            "privacy": "provider_owned_content_compact_receipts_only",
        },
        {
            "class_id": "procedural_experience",
            "experience_subtypes": [
                "trajectory",
                "distilled_experience",
                "architectural_experience",
            ],
            "purpose": (
                "Preserve checkout-verified repair, validation, and architecture "
                "lessons with applicability boundaries."
            ),
            "source_kinds": [
                "revision_stamped_execution_trajectory",
                "validated_outcome",
                "maintainer_correction",
                "accepted_or_rejected_change",
                "reviewed_learning_card",
            ],
            "excluded_sources": [
                "raw_chat_or_tool_transcript",
                "evaluation_case_without_reviewed_distillation",
            ],
            "scope_floor": [
                "repository_or_project",
                "module_or_component",
                "observed_revision",
                "applicability_boundary",
            ],
            "authority": "advisory_until_current_artifact_verification",
            "future_influence": "diagnosis_scope_routing_or_validation_only_after_verification",
            "durability": "revision_stamped_and_supersedable",
            "supersession": "newer_verified_revision_lineage",
            "revocation": "refute_quarantine_or_retire",
            "expiry": "stale_when_revision_or_source_truth_diverges",
            "privacy": "distilled_public_safe_fact_no_raw_evidence",
        },
        {
            "class_id": "working_context",
            "context_subtypes": [
                "fresh_execution_context",
                "session_working_memory",
            ],
            "purpose": (
                "Carry fresh execution state or a revisioned session-continuation "
                "summary without promoting either into reusable policy."
            ),
            "source_kinds": [
                "current_registry_state",
                "active_todo",
                "current_checkout",
                "bounded_tool_observation",
                "versioned_session_archive_overview",
            ],
            "scope_floor": [
                "current_execution_or_session",
                "exact_source_revision_archive_or_timestamp",
            ],
            "authority": "fresh_execution_context_not_long_term_memory",
            "future_influence": (
                "current_execution_or_session_continuation_only_never_action_authority"
            ),
            "durability": (
                "fresh_context_expires_quickly_session_summary_is_archive_revision_bound"
            ),
            "supersession": "next_fresh_read_or_newer_completed_archive",
            "revocation": "source_invalidation",
            "expiry": "required_for_fresh_context_session_summary_stales_on_newer_archive",
            "privacy": "never_promote_raw_chat_logs_credentials_or_local_paths",
        },
    ]


def _openviking_alignment() -> dict[str, Any]:
    return {
        "provider_role": "context_database_not_action_authority",
        "content_source_of_truth": "agfs_content",
        "index_role": "retrieval_reference_not_content_source_of_truth",
        "class_mapping": {
            "run_bound_reward": (
                "loopx_overlay_no_direct_openviking_memory_equivalent"
            ),
            "hard_policy": (
                "loopx_repository_operator_or_user_authority_only_provider_soul_is_advisory"
            ),
            "soft_preference": "reviewed_openviking_preference_candidate",
            "procedural_experience": {
                "trajectory": "openviking_trajectories_add_only_operation_contract",
                "distilled_experience": (
                    "openviking_experiences_upsert_and_supersedes"
                ),
                "architectural_experience": (
                    "reviewed_revision_stamped_loopx_distillation"
                ),
            },
            "working_context": {
                "fresh_execution_context": (
                    "loopx_registry_todo_checkout_and_tool_observation"
                ),
                "session_working_memory": (
                    "openviking_archive_overview_bound_to_session_and_archive_revision"
                ),
            },
        },
        "non_instruction_artifacts": {
            "openviking_cases": "training_and_evaluation_fixture_not_executable_memory",
        },
        "scope_boundaries": [
            "account",
            "user",
            "peer",
            "session",
            "repository_revision",
        ],
        "health_states_must_remain_distinct": [
            "corpus_present",
            "index_present",
            "retrieval_query_succeeded",
            "result_readback_verified",
            "memory_applied_with_receipt",
        ],
        "known_stage_1_check": (
            "codex_auto_recall_may_exclude_experiences_even_when_the_corpus_exists"
        ),
    }


def build_reward_memory_architecture_packet() -> dict[str, Any]:
    """Return the Stage-0 classification and precedence compatibility contract."""

    return {
        "ok": True,
        "schema_version": REWARD_MEMORY_ARCHITECTURE_SCHEMA_VERSION,
        "status": "design_contract",
        "memory_classes": _memory_classes(),
        "required_record_fields": [
            "class_id",
            "source",
            "scope",
            "authority",
            "confidence",
            "lifecycle_state",
            "supersession",
            "revocation",
            "expiry",
            "privacy",
        ],
        "field_contracts": {
            "source": ["source_kind", "source_ref", "actor_ref", "observed_at"],
            "scope": [
                "workspace_or_user",
                "project_or_repository",
                "module_or_surface",
                "revision_or_time_boundary",
            ],
            "authority": ["evidence", "advisory", "constraint", "veto"],
            "confidence": {
                "levels": ["low", "medium", "high"],
                "basis_required": True,
                "may_increase_authority": False,
            },
            "lifecycle": [
                "state",
                "supersedes_refs",
                "revoked_by_ref",
                "expires_at",
                "retired_reason",
            ],
            "privacy": [
                "visibility",
                "retention_class",
                "raw_content_captured",
            ],
        },
        "lifecycle_states": [
            "observed",
            "candidate",
            "active",
            "superseded",
            "revoked",
            "expired",
            "retired",
        ],
        "precedence": [
            "explicit_action_authority_and_privacy_boundary",
            "active_in_scope_hard_policy",
            "fresh_working_context_and_current_source_of_truth",
            "current_artifact_verified_procedural_experience",
            "active_in_scope_soft_preference",
            "run_bound_reward_as_evidence_only",
        ],
        "conflict_resolution": [
            "reject_out_of_scope_revoked_expired_or_unverified_items",
            "prefer_explicit_over_inferred_sources",
            "prefer_narrower_scope_then_newer_source_truth",
            "do_not_apply_when_same_authority_conflict_remains_unresolved",
        ],
        "safety_invariants": [
            "confidence_never_increases_authority",
            "reward_or_preference_never_grants_permission",
            "memory_never_overrides_a_gate_policy_or_current_source_of_truth",
            "raw_chat_tool_logs_credentials_and_local_paths_are_not_memory_records",
            "retrieval_without_current_artifact_verification_has_zero_patch_authority",
            "promotion_from_reward_requires_explicit_candidate_review",
            "provider_soul_boundary_or_experience_text_never_grants_action_authority",
            "evaluation_cases_are_not_executable_instructions",
            "corpus_or_index_presence_is_not_retrieval_or_application_health",
        ],
        "provider_alignment": {"openviking": _openviking_alignment()},
        "pilot_meta_delegation": {
            "schema_version": "reward_memory_pilot_meta_delegation_v0",
            "pilot_requires": [
                "confirmed_bug_semantics",
                "single_bounded_surface",
                "no_semantic_contract_change",
                "no_generic_boundary_for_specific_policy",
                "named_reproduction",
                "named_validation",
                "low_or_medium_edge_case_complexity",
                "all_relevance_gated_evidence_present",
            ],
            "meta_triggers": [
                "by_design_or_uncertain_semantics",
                "semantic_contract_change",
                "cross_surface_change",
                "generic_boundary_for_specific_policy",
                "high_edge_case_complexity",
            ],
            "relevance_gated_evidence": {
                "effect": "always",
                "ux": "when_user_visible_behavior_changes",
                "benchmark": "when_retrieval_or_memory_quality_is_claimed",
                "performance_cost": "when_hot_path_or_storage_behavior_changes",
            },
            "decisions": ["pilot_fix", "meta_design_gate", "hold_for_evidence"],
            "no_cross_agent_authority": True,
        },
        "stage_boundaries": {
            "stage_0": "classification_precedence_and_delegation_only",
            "stage_1": "corpus_registry_ownership_and_retrieval_health",
            "stage_2": "candidate_distillation_and_human_review",
            "stage_3": "cross_module_recall_and_application",
            "stage_4": "evaluation_harness_and_release_gate",
            "stage_5": "bounded_dogfood_and_operator_controls",
        },
        "external_writes_performed": False,
        "raw_memory_captured": False,
    }


def pr_3237_regression_observation() -> dict[str, Any]:
    """Public regression fixture derived from the terminal PR review outcome."""

    return {
        "case_ref": "https://github.com/volcengine/OpenViking/pull/3237",
        "behavior_status": "by_design",
        "surface_count": 2,
        "semantic_contract_change": True,
        "generic_boundary_for_specific_policy": True,
        "user_visible_behavior_change": True,
        "hot_path_or_storage_change": True,
        "retrieval_or_memory_quality_claim": False,
        "edge_case_complexity": "high",
        "named_reproduction": True,
        "named_validation": True,
        "effect_evidence": False,
        "ux_evidence": False,
        "benchmark_evidence": False,
        "performance_evidence": False,
    }


def _boolean(observation: Mapping[str, Any], key: str) -> bool:
    value = observation.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def build_reward_memory_route_packet(
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Route a bounded issue-fix observation to pilot, meta, or evidence hold."""

    behavior_status = str(observation.get("behavior_status") or "").strip()
    if behavior_status not in BEHAVIOR_STATUSES:
        raise ValueError(
            f"behavior_status must be one of {sorted(BEHAVIOR_STATUSES)}"
        )
    complexity = str(observation.get("edge_case_complexity") or "").strip()
    if complexity not in EDGE_CASE_COMPLEXITIES:
        raise ValueError(
            "edge_case_complexity must be one of "
            f"{sorted(EDGE_CASE_COMPLEXITIES)}"
        )
    surface_count = observation.get("surface_count")
    if isinstance(surface_count, bool) or not isinstance(surface_count, int):
        raise ValueError("surface_count must be an integer")
    if surface_count < 1 or surface_count > 20:
        raise ValueError("surface_count must be between 1 and 20")

    boolean_keys = (
        "semantic_contract_change",
        "generic_boundary_for_specific_policy",
        "user_visible_behavior_change",
        "hot_path_or_storage_change",
        "retrieval_or_memory_quality_claim",
        "named_reproduction",
        "named_validation",
        "effect_evidence",
        "ux_evidence",
        "benchmark_evidence",
        "performance_evidence",
    )
    values = {key: _boolean(observation, key) for key in boolean_keys}
    meta_reasons: list[str] = []
    if behavior_status != "bug_confirmed":
        meta_reasons.append(f"semantics_{behavior_status}")
    if values["semantic_contract_change"]:
        meta_reasons.append("semantic_contract_change")
    if surface_count > 1:
        meta_reasons.append("cross_surface_change")
    if values["generic_boundary_for_specific_policy"]:
        meta_reasons.append("generic_boundary_for_specific_policy")
    if complexity == "high":
        meta_reasons.append("high_edge_case_complexity")
    required_evidence = {
        "effect_evidence": True,
        "ux_evidence": values["user_visible_behavior_change"],
        "benchmark_evidence": values["retrieval_or_memory_quality_claim"],
        "performance_evidence": values["hot_path_or_storage_change"],
    }
    missing_required_evidence = [
        evidence
        for evidence, required in required_evidence.items()
        if required and not values[evidence]
    ]

    missing_pilot_evidence: list[str] = list(missing_required_evidence)
    if not values["named_reproduction"]:
        missing_pilot_evidence.append("named_reproduction")
    if not values["named_validation"]:
        missing_pilot_evidence.append("named_validation")

    if meta_reasons:
        decision = "meta_design_gate"
        reasons = meta_reasons + [
            f"missing_{item}" for item in missing_required_evidence
        ]
    elif missing_pilot_evidence:
        decision = "hold_for_evidence"
        reasons = [f"missing_{item}" for item in missing_pilot_evidence]
    else:
        decision = "pilot_fix"
        reasons = [
            "confirmed_bug_semantics",
            "single_bounded_surface",
            "no_semantic_contract_change",
            "no_generic_boundary_for_specific_policy",
            f"edge_case_complexity_{complexity}",
            "reproduction_validation_and_relevant_evidence_present",
        ]

    raw_case_ref = str(observation.get("case_ref") or "manual_observation")
    if raw_case_ref.startswith(("/", "~")):
        raise ValueError("case_ref must be compact and public-safe")
    case_ref = public_safe_compact_text(raw_case_ref, limit=240)
    if not case_ref:
        raise ValueError("case_ref must be compact and public-safe")

    return {
        "ok": True,
        "schema_version": REWARD_MEMORY_ROUTE_SCHEMA_VERSION,
        "case_ref": case_ref,
        "decision": decision,
        "reason_codes": reasons,
        "required_evidence": [
            key.removesuffix("_evidence")
            for key, required in required_evidence.items()
            if required
        ],
        "missing_required_evidence": [
            key.removesuffix("_evidence") for key in missing_required_evidence
        ],
        "pilot_authorized": decision == "pilot_fix",
        "meta_review_required": decision == "meta_design_gate",
        "memory_patch_authority": False,
        "external_write_authorized": False,
        "raw_issue_or_memory_captured": False,
    }
