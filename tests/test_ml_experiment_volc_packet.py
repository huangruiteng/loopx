from __future__ import annotations

from loopx.ml_experiment import (
    VOLC_MLP_RESULT_LEDGER_SCHEMA_VERSION,
    VOLC_MLP_TASK_PACKET_SCHEMA_VERSION,
    build_volc_mlp_result_ledger,
    build_volc_mlp_task_packet,
    render_volc_mlp_result_ledger_markdown,
    render_volc_mlp_task_packet_markdown,
)


def test_volc_mlp_task_packet_redacts_private_refs() -> None:
    payload = build_volc_mlp_task_packet(
        task_id="task-candidate-0",
        task_name="external_slice_cross_screen",
        state="Running",
        priority=4,
        retried_times=0,
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        mechanism_family="explicit_context_item_crosses",
        source_task_id="task-baseline-0",
        workspace_ref="/private/raw/workspace",
        metric_refs=["metrics/eval-summary.json", "https://private.example/raw-log"],
        primary_metric="target_slice_auc",
        guardrail_metrics=["overall_auc", "ctr_auc"],
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == VOLC_MLP_TASK_PACKET_SCHEMA_VERSION
    assert payload["observable_handle"]["state"] == "Running"
    assert payload["lineage"]["workspace_ref"]["kind"] == "redacted_ref"
    assert payload["lineage"]["workspace_ref"]["value"].startswith("redacted:")
    assert payload["metric_artifacts"][0]["kind"] == "alias"
    assert payload["metric_artifacts"][1]["kind"] == "redacted_ref"
    assert payload["poll_contract"]["raw_logs_recorded"] is False
    assert payload["poll_contract"]["raw_command_recorded"] is False
    assert payload["poll_contract"]["raw_env_recorded"] is False
    assert payload["production_actions_enabled"] is False


def test_volc_mlp_task_packet_markdown_is_public_safe() -> None:
    payload = build_volc_mlp_task_packet(
        task_id="task-candidate-0",
        task_name="external_slice_cross_screen",
        state="Queueing",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        workspace_ref="/private/raw/workspace",
        metric_refs=["/private/raw/metrics"],
    )

    rendered = render_volc_mlp_task_packet_markdown(payload)

    assert "Volc MLP Task Packet" in rendered
    assert "task-candidate-0" in rendered
    assert "/private/raw" not in rendered
    assert "redacted:" in rendered


def test_volc_mlp_result_ledger_classifies_public_safe_failure() -> None:
    payload = build_volc_mlp_result_ledger(
        experiment_id="external_slice_screen",
        task_id="task-candidate-0",
        task_name="external_slice_cross_screen",
        state="Failed",
        priority=4,
        retried_times=0,
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        mechanism_family="explicit_context_item_crosses",
        primary_metric="target_slice_auc",
        guardrail_status="unknown",
        baseline_task_id="task-baseline-0",
        workspace_ref="/private/raw/workspace",
        metric_refs=["/private/raw/metrics"],
        failure_labels=["stale_model_py_root", "missing_restore_checkpoint"],
        negative_evidence=["failed_before_eval_metrics"],
    )
    rendered = render_volc_mlp_result_ledger_markdown(payload)

    assert payload["ok"] is True
    assert payload["schema_version"] == VOLC_MLP_RESULT_LEDGER_SCHEMA_VERSION
    assert payload["comparison"]["primary_metric_delta"]["primary_metric_status"] == "pending"
    assert payload["decision"]["outcome"] == "needs_repair_before_conclusion"
    assert payload["decision"]["promotion_eligible"] is False
    assert payload["failure_attribution"]["raw_logs_recorded"] is False
    assert "/private/raw" not in rendered
    assert "stale_model_py_root" in rendered


def test_volc_mlp_result_ledger_marks_clean_improvement_as_promotion_candidate() -> None:
    payload = build_volc_mlp_result_ledger(
        experiment_id="external_slice_screen",
        task_id="task-candidate-1",
        task_name="external_slice_cross_screen",
        state="Completed",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        mechanism_family="explicit_context_item_crosses",
        primary_metric="target_slice_auc",
        baseline_value=0.731,
        candidate_value=0.742,
        guardrail_status="clean",
        guardrail_metrics=["guardrail_slice_a_auc", "guardrail_slice_b_auc"],
        positive_evidence=["same_window_target_slice_auc_up"],
    )

    assert payload["comparison"]["primary_metric_delta"]["primary_metric_status"] == "improved"
    assert payload["decision"]["outcome"] == "promote_to_larger_window_or_handoff"
    assert payload["decision"]["promotion_eligible"] is True
    assert payload["comparison"]["same_window_required"] is True
    assert payload["comparison"]["train_metrics_are_guardrails_only"] is True
