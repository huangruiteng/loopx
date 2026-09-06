from __future__ import annotations

import pytest

from loopx.capabilities.pr_review_queue import (
    build_agent_response_contract,
    build_review_plan,
    build_review_template,
)


def _item(*, areas: dict[str, int]) -> dict[str, object]:
    return {
        "number": 42,
        "base_ref": "main",
        "head_oid": "a" * 40,
        "areas": areas,
        "key_files": [
            {"path": "src/runtime.py", "additions": 20, "deletions": 5},
            {"path": "tests/test_runtime.py", "additions": 30, "deletions": 0},
        ],
    }


def test_execution_contract_owns_deep_review_requirements() -> None:
    response = build_agent_response_contract()

    assert response["required_packet_fields_to_preserve"] == [
        "agent_response_contract",
        "agent_response_contract.review_execution_contract",
        "result_completeness",
        "review_groups",
        "pull_requests[].review_plan",
        "pull_requests[].review_template",
        "pull_requests[].evidence_commands",
    ]
    contract = response["review_execution_contract"]
    assert contract["schema_version"] == "pull_request_review_execution_contract_v2"
    requirements = {
        item["evidence_id"]: item for item in contract["evidence_requirements"]
    }
    assert set(requirements) == {
        "problem_context",
        "architecture_flow",
        "repository_reuse",
        "observable_semantics",
        "changed_line_classification",
        "scope_fit",
        "symbol_map",
        "walkthroughs",
        "validation_matrix",
        "failure_analysis",
        "code_volume",
        "change_proportionality",
        "default_off_isolation",
        "authority_semantics",
        "typed_state_rule",
        "domain_neutrality",
        "behavior_change_disclosure",
        "guidance_vs_obligation",
        "durable_smoke_value",
    }
    assert requirements["symbol_map"]["item_count"] == {
        "minimum": 2,
        "maximum": 5,
    }
    assert "caller_evidence" in requirements["symbol_map"]["item_fields"]
    assert "negative_fields" in requirements["walkthroughs"]
    assert "regression_test" in requirements["failure_analysis"]["fields"]
    assert requirements["scope_fit"]["required_when"] == "behavior_bearing_change"
    assert "instruction_install_or_load_path" in requirements["scope_fit"]["fields"]
    assert "target_audience_and_scope" in requirements["scope_fit"]["fields"]
    assert requirements["typed_state_rule"]["required_when"] == "code_change"
    assert "substring denylists" in requirements["typed_state_rule"]["rule"]
    assert "domain-neutral" in requirements["domain_neutrality"]["rule"]
    assert requirements["behavior_change_disclosure"]["required_when"] == (
        "behavior_bearing_change"
    )
    assert (
        "silent behavior changes" in requirements["behavior_change_disclosure"]["rule"]
    )
    assert "must_attempt_work" in requirements["guidance_vs_obligation"]["rule"]
    proportionality = requirements["change_proportionality"]
    assert proportionality["required_when"] == "code_change"
    assert proportionality["verdict_values"] == [
        "proportionate",
        "disproportionate",
        "not_yet_proven",
    ]
    assert "smallest_viable_fix" in proportionality["fields"]
    assert "maintenance_and_migration_cost" in proportionality["fields"]
    assert "green CI" in proportionality["rule"]
    assert "original problem" in proportionality["rule"]
    isolation = requirements["default_off_isolation"]
    assert isolation["required_when"] == "behavior_bearing_change"
    assert isolation["verdict_values"] == [
        "isolated",
        "not_isolated",
        "not_applicable",
        "not_yet_proven",
    ]
    assert "disabled_prompt_or_guidance" in isolation["fields"]
    assert "declared_activation_scope" in isolation["fields"]
    assert "availability_signals_that_do_not_activate" in isolation["fields"]
    assert "installed_or_auto_loaded_instruction_surfaces" in isolation["fields"]
    assert "disabled_user_experience_parity" in isolation["fields"]
    assert "paired_counterfactual_validation" in isolation["fields"]
    assert "absence of a topology" in isolation["rule"]
    assert "automatically loaded" in isolation["rule"]
    assert "availability from activation" in isolation["rule"]
    assert "runtime default of false" in isolation["rule"]
    authority = requirements["authority_semantics"]
    assert authority["verdict_values"] == [
        "aligned",
        "misleading",
        "not_applicable",
        "not_yet_proven",
    ]
    assert "actual_actor_lifecycle" in authority["fields"]
    assert "ephemeral sub-agent" in authority["rule"]
    assert contract["completion_gate"]["metadata_only_verdict_allowed"] is False
    assert contract["completion_gate"]["stale_head_verdict_allowed"] is False
    assert contract["completion_gate"]["blocking_evidence_verdicts"] == {
        "repository_reuse": ["unjustified_duplication", "not_yet_proven"],
        "observable_semantics": ["unintended_drift", "not_yet_proven"],
        "change_proportionality": ["disproportionate", "not_yet_proven"],
        "default_off_isolation": ["not_isolated", "not_yet_proven"],
        "authority_semantics": ["misleading", "not_yet_proven"],
    }
    assert contract["finding_contract"]["findings_first"] is True
    verdict = contract["verdict_policy"]
    assert verdict["open_pr_blocking_finding"] == "REQUEST_CHANGES"
    assert "REQUEST_CHANGES" in verdict["open_pr_unresolved_proportionality"]
    assert "original problem" in verdict["materially_expanded_rereview"]
    assert verdict["open_pr_non_blocking_finding"] == "APPROVE"
    assert verdict["open_pr_no_finding"] == "APPROVE"
    assert "author-owned PR" in verdict["author_owned_no_blocker_fallback"]


def test_runtime_plan_requires_symbol_map_and_negative_walkthrough() -> None:
    plan = build_review_plan(_item(areas={"product_runtime": 1, "test_or_example": 1}))

    assert plan["target"] == {
        "number": 42,
        "base_ref": "main",
        "head_oid": "a" * 40,
        "exact_head_key": f"42@{'a' * 40}",
    }
    assert plan["applicability"]["code_change"] is True
    assert plan["applicability"]["symbol_map_required"] is True
    assert plan["applicability"]["scope_fit_required"] is True
    assert plan["applicability"]["change_proportionality_required"] is True
    assert plan["applicability"]["default_off_isolation_required"] is True
    assert plan["applicability"]["authority_semantics_required"] is True
    assert plan["applicability"]["negative_walkthrough_required"] is True
    assert plan["applicability"]["typed_state_rule_required"] is True
    assert plan["applicability"]["behavior_change_disclosure_required"] is True
    assert plan["applicability"]["domain_neutrality_required"] is True
    assert plan["applicability"]["guidance_vs_obligation_required"] is True
    assert "symbol_map" in plan["required_evidence_ids"]
    assert "scope_fit" in plan["required_evidence_ids"]
    assert "change_proportionality" in plan["required_evidence_ids"]
    assert "default_off_isolation" in plan["required_evidence_ids"]
    assert "authority_semantics" in plan["required_evidence_ids"]
    assert "typed_state_rule" in plan["required_evidence_ids"]
    assert "behavior_change_disclosure" in plan["required_evidence_ids"]
    assert "domain_neutrality" in plan["required_evidence_ids"]
    assert "guidance_vs_obligation" in plan["required_evidence_ids"]
    assert set(plan["result_template"]["evidence"]) == set(
        plan["required_evidence_ids"]
    )
    assert all(
        item["status"] == "unverified"
        for item in plan["result_template"]["evidence"].values()
    )


def test_docs_plan_does_not_invent_code_symbols() -> None:
    item = _item(areas={"public_docs": 2})
    item["key_files"] = [{"path": "docs/design.md", "additions": 15, "deletions": 2}]

    plan = build_review_plan(item)
    template = build_review_template(item)

    assert plan["applicability"]["docs_only"] is True
    assert plan["applicability"]["symbol_map_required"] is False
    assert plan["applicability"]["scope_fit_required"] is False
    assert plan["applicability"]["change_proportionality_required"] is False
    assert plan["applicability"]["default_off_isolation_required"] is False
    assert plan["applicability"]["authority_semantics_required"] is False
    assert plan["applicability"]["typed_state_rule_required"] is False
    assert plan["applicability"]["behavior_change_disclosure_required"] is False
    assert plan["applicability"]["domain_neutrality_required"] is False
    assert plan["applicability"]["guidance_vs_obligation_required"] is False
    assert "symbol_map" not in plan["required_evidence_ids"]
    assert "scope_fit" not in plan["required_evidence_ids"]
    assert "change_proportionality" not in plan["required_evidence_ids"]
    assert "default_off_isolation" not in plan["required_evidence_ids"]
    assert "authority_semantics" not in plan["required_evidence_ids"]
    assert "typed_state_rule" not in plan["required_evidence_ids"]
    assert "domain_neutrality" not in plan["required_evidence_ids"]
    assert "behavior_change_disclosure" not in plan["required_evidence_ids"]
    assert "guidance_vs_obligation" not in plan["required_evidence_ids"]
    concrete = next(
        section for section in template["sections"] if section["label"] == "具体改动"
    )
    assert "### 关键内容讲解" in concrete["agent_instruction"]
    assert template["review_order"] == ["docs/design.md"]


def test_agent_instruction_plan_requires_default_off_user_experience_evidence() -> None:
    item = _item(areas={"agent_instruction_surface": 1})
    item["key_files"] = [
        {"path": "skills/project/SKILL.md", "additions": 20, "deletions": 2}
    ]

    plan = build_review_plan(item)

    assert plan["applicability"]["code_change"] is False
    assert plan["applicability"]["behavioral_policy_change"] is True
    assert plan["applicability"]["behavior_bearing_change"] is True
    assert plan["applicability"]["smoke_or_example_only"] is False
    assert plan["applicability"]["durable_smoke_value_required"] is False
    assert plan["applicability"]["scope_fit_required"] is True
    assert plan["applicability"]["default_off_isolation_required"] is True
    assert plan["applicability"]["negative_walkthrough_required"] is True
    assert plan["applicability"]["behavior_change_disclosure_required"] is True
    assert plan["applicability"]["guidance_vs_obligation_required"] is True
    assert "scope_fit" in plan["required_evidence_ids"]
    assert "default_off_isolation" in plan["required_evidence_ids"]
    assert "behavior_change_disclosure" in plan["required_evidence_ids"]
    assert "guidance_vs_obligation" in plan["required_evidence_ids"]
    assert "symbol_map" not in plan["required_evidence_ids"]


def test_smoke_only_plan_requires_durable_value_evidence() -> None:
    item = _item(areas={"test_or_example": 1})
    item["key_files"] = [
        {"path": "examples/walkthrough-smoke.py", "additions": 500, "deletions": 0}
    ]

    plan = build_review_plan(item)

    assert plan["applicability"]["code_change"] is False
    assert plan["applicability"]["docs_only"] is False
    assert plan["applicability"]["smoke_or_example_only"] is True
    assert plan["applicability"]["durable_smoke_value_required"] is True
    assert plan["applicability"]["duplication_scan_required"] is True
    assert plan["applicability"]["batch_pattern_scan_required"] is True
    assert "durable_smoke_value" in plan["required_evidence_ids"]
    assert set(plan["result_template"]["evidence"]) == set(
        plan["required_evidence_ids"]
    )


def test_runtime_plan_does_not_require_smoke_durability_gate() -> None:
    plan = build_review_plan(_item(areas={"product_runtime": 1}))

    assert plan["applicability"]["smoke_or_example_only"] is False
    assert plan["applicability"]["durable_smoke_value_required"] is False
    assert "durable_smoke_value" not in plan["required_evidence_ids"]


def test_test_only_plan_skips_runtime_lenses() -> None:
    plan = build_review_plan(_item(areas={"test_or_example": 2}))

    assert plan["applicability"]["code_change"] is False
    assert plan["applicability"]["typed_state_rule_required"] is False
    assert plan["applicability"]["behavior_change_disclosure_required"] is False
    assert plan["applicability"]["domain_neutrality_required"] is False
    assert plan["applicability"]["guidance_vs_obligation_required"] is False
    assert "typed_state_rule" not in plan["required_evidence_ids"]
    assert "domain_neutrality" not in plan["required_evidence_ids"]


@pytest.mark.parametrize(
    "area",
    [
        "product_runtime",
        "app_or_ui_surface",
        "ci_or_release",
        "build_or_config",
        "agent_instruction_surface",
        "public_entry_or_policy",
    ],
)
def test_behavior_review_requires_repository_reuse_even_with_green_checks(
    area: str,
) -> None:
    item = _item(areas={area: 1, "test_or_example": 1})
    # A narrow changed-file list and passing CI cannot establish that an
    # unchanged sibling already implements the same caller outcome.
    item["key_files"] = [{"path": "src/history_list.py", "additions": 80}]
    item["checks"] = {"counts": {"success": 4, "failure": 0}}
    plan = build_review_plan(item)
    assert plan["applicability"]["repository_reuse_required"] is True
    assert "repository_reuse" in plan["required_evidence_ids"]
    assert plan["result_template"]["evidence"]["repository_reuse"] == {
        "status": "unverified"
    }


@pytest.mark.parametrize("area", ["public_docs", "test_or_example"])
def test_non_behavior_review_keeps_existing_coverage_policy(area: str) -> None:
    plan = build_review_plan(_item(areas={area: 1}))
    assert plan["applicability"]["repository_reuse_required"] is False
    assert "repository_reuse" not in plan["required_evidence_ids"]


def test_reuse_evidence_compares_semantics_beyond_the_diff() -> None:
    contract = build_agent_response_contract()["review_execution_contract"]
    reuse = next(
        row
        for row in contract["evidence_requirements"]
        if row["evidence_id"] == "repository_reuse"
    )
    assert reuse["required_when"] == "behavior_bearing_change"
    assert reuse["verdict_values"] == [
        "reused",
        "separation_justified",
        "no_existing_candidate",
        "unjustified_duplication",
        "not_yet_proven",
    ]
    assert {
        "searched_revisions",
        "queries_and_paths",
        "existing_candidates",
        "semantic_comparison",
        "reuse_or_separation_reason",
        "validation_evidence",
        "verdict",
    } <= set(reuse["fields"])
    assert {
        "resource_and_caller",
        "data_scope_and_filters",
        "ordering_and_pagination",
        "authority_and_sanitization",
        "state_retry_and_failure_owner",
    } <= set(reuse["comparison_dimensions"])
    assert "unchanged" in reuse["rule"]
    assert "negative search" in reuse["rule"]
    assert "coexistence" in reuse["rule"]
    assert "not an automatic similarity detector" in reuse["rule"]
    assert "repository_reuse" in contract["verdict_policy"]["open_pr_unresolved_reuse"]


@pytest.mark.parametrize(
    "area",
    [
        "product_runtime",
        "app_or_ui_surface",
        "ci_or_release",
        "build_or_config",
        "agent_instruction_surface",
        "public_entry_or_policy",
    ],
)
def test_observable_parity_is_required_without_refactor_title_detection(
    area: str,
) -> None:
    item = _item(areas={area: 1})
    item["title"] = "Extract shared decision helper"
    item["checks"] = {"counts": {"success": 51, "failure": 0}}
    plan = build_review_plan(item)
    assert plan["applicability"]["observable_semantics_required"] is True
    assert plan["result_template"]["evidence"]["observable_semantics"] == {
        "status": "unverified"
    }


@pytest.mark.parametrize("area", ["public_docs", "test_or_example"])
def test_non_behavior_changes_do_not_invent_parity_execution(area: str) -> None:
    plan = build_review_plan(_item(areas={area: 1}))
    assert plan["applicability"]["observable_semantics_required"] is False
    assert "observable_semantics" not in plan["required_evidence_ids"]


def test_observable_semantics_covers_diagnostics_and_claim_neutral_note_paths() -> None:
    contract = build_agent_response_contract()["review_execution_contract"]
    parity = next(
        row
        for row in contract["evidence_requirements"]
        if row["evidence_id"] == "observable_semantics"
    )
    assert parity["required_when"] == "behavior_bearing_change"
    assert {
        "baseline_revision",
        "reviewed_head",
        "caller_branch_inventory",
        "comparison_rows",
        "execution_receipts",
        "normalization_rules",
        "intentional_deltas",
        "regression_sensitivity",
        "unverified_dimensions",
        "verdict",
    } <= set(parity["fields"])
    assert {
        "accepted_inputs_and_defaults",
        "eligibility_and_rejection_precedence",
        "full_diagnostics_and_remediation",
        "argument_to_persistence_readback",
        "state_receipts_and_no_effects",
        "replay_and_concurrent_updates",
    } <= set(parity["comparison_dimensions"])
    assert {
        "input_and_pre_state",
        "entrypoint_and_backend",
        "baseline_observation",
        "head_observation",
        "expected_invariant_source",
        "validation_evidence",
    } <= set(parity["row_fields"])
    assert {
        "revision",
        "command",
        "public_entrypoint",
        "backend",
        "fixture_fingerprint",
        "exit_status",
        "observation_fingerprint",
        "public_safe_artifact_reference_or_inline_observation",
    } <= set(parity["execution_receipt_fields"])
    assert {
        "invariant",
        "historical_defect_or_deliberate_mutation",
        "command",
        "expected_failure",
        "observed_failure",
        "passing_head_receipt",
    } <= set(parity["regression_sensitivity_fields"])
    assert parity["verdict_values"] == [
        "equivalent",
        "intentional_change_validated",
        "unintended_drift",
        "not_yet_proven",
    ]
    assert "reviewer-executed" in parity["rule"]
    assert "replayable command" in parity["rule"]
    assert "real affected backend" in parity["rule"]
    assert "independent oracle fail" in parity["rule"]
    assert (
        "observable_semantics"
        in contract["verdict_policy"]["open_pr_unresolved_semantics"]
    )
