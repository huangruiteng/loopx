from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

from loopx.domain_state import default_domain_state_file_path, upsert_domain_state_jsonl
from loopx.domain_packs.ml_experiment import (
    VOLC_MLP_RESULT_LEDGER_SCHEMA_VERSION,
    VOLC_MLP_TASK_PACKET_SCHEMA_VERSION,
    build_volc_mlp_result_ledger,
    build_volc_mlp_task_packet,
    default_ml_experiment_domain_state_ledger_path,
    render_volc_mlp_result_ledger_markdown,
    render_volc_mlp_task_packet_markdown,
    upsert_ml_experiment_ledger_jsonl,
)
from loopx.ml_experiment import build_volc_mlp_task_packet as compat_build_volc_mlp_task_packet


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


def test_ml_experiment_compat_module_reexports_domain_pack() -> None:
    payload = compat_build_volc_mlp_task_packet(
        task_id="task-candidate-compat",
        task_name="external_slice_cross_screen",
        state="Running",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
    )

    assert payload["schema_version"] == VOLC_MLP_TASK_PACKET_SCHEMA_VERSION


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


def test_volc_mlp_result_ledger_jsonl_upserts_public_safe_rows(tmp_path) -> None:
    ledger_path = tmp_path / "ml-experiment-ledger.jsonl"
    running_payload = build_volc_mlp_result_ledger(
        experiment_id="external_slice_screen",
        task_id="task-candidate-1",
        task_name="external_slice_cross_screen",
        state="Running",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        workspace_ref="/private/raw/workspace",
        metric_refs=["/private/raw/metrics"],
        next_action="monitor_until_eval",
    )
    first_write = upsert_ml_experiment_ledger_jsonl(ledger_path, running_payload)

    completed_payload = build_volc_mlp_result_ledger(
        experiment_id="external_slice_screen",
        task_id="task-candidate-1",
        task_name="external_slice_cross_screen",
        state="Completed",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        primary_metric="target_slice_auc",
        baseline_value=0.731,
        candidate_value=0.742,
        guardrail_status="clean",
    )
    second_write = upsert_ml_experiment_ledger_jsonl(ledger_path, completed_payload)

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert first_write["status"] == "inserted"
    assert second_write["status"] == "updated"
    assert second_write["path_recorded"] is False
    assert len(rows) == 1
    assert rows[0]["task_packet"]["observable_handle"]["state"] == "Completed"
    assert rows[0]["decision"]["outcome"] == "promote_to_larger_window_or_handoff"
    assert "/private/raw" not in ledger_path.read_text(encoding="utf-8")


def test_volc_mlp_result_ledger_upsert_dedupes_legacy_rows_without_domain_key(tmp_path) -> None:
    ledger_path = tmp_path / "ml-experiment-ledger.jsonl"
    legacy_payload = build_volc_mlp_result_ledger(
        experiment_id="external_slice_screen",
        task_id="task-candidate-1",
        task_name="external_slice_cross_screen",
        state="Running",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
    )
    ledger_path.write_text(json.dumps(legacy_payload, sort_keys=True) + "\n", encoding="utf-8")

    completed_payload = build_volc_mlp_result_ledger(
        experiment_id="external_slice_screen",
        task_id="task-candidate-1",
        task_name="external_slice_cross_screen",
        state="Completed",
        train_window="20251002-20260501",
        eval_window="20260501-20260508",
        code_ref="codex/example-feature-cross@abc1234",
        model_name="candidate_model_abc1234",
        primary_metric="target_slice_auc",
        baseline_value=0.731,
        candidate_value=0.742,
        guardrail_status="clean",
    )
    write_result = upsert_ml_experiment_ledger_jsonl(ledger_path, completed_payload)

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert write_result["status"] == "updated"
    assert len(rows) == 1
    assert rows[0]["domain_state_key"]["task_id"] == "task-candidate-1"
    assert rows[0]["task_packet"]["observable_handle"]["state"] == "Completed"


def test_ml_experiment_default_domain_state_path_is_project_local(tmp_path) -> None:
    path = default_ml_experiment_domain_state_ledger_path(
        project=tmp_path,
        goal_id="example-goal",
    )

    assert path == tmp_path / ".loopx" / "domain-state" / "example-goal" / "ml_experiment" / "ledger.jsonl"


def test_generic_domain_state_path_groups_packs_by_goal(tmp_path) -> None:
    ml_path = default_domain_state_file_path(
        project=tmp_path,
        goal_id="example-goal",
        domain_pack="ml_experiment",
        filename="ledger.jsonl",
    )
    content_path = default_domain_state_file_path(
        project=tmp_path,
        goal_id="example-goal",
        domain_pack="content_ops",
        filename="ledger.jsonl",
    )

    assert ml_path.parent.parent == content_path.parent.parent
    result = upsert_domain_state_jsonl(
        ml_path,
        {"schema_version": "example_domain_row_v0", "ok": True},
        key={"schema_version": "example_domain_row_v0", "row_id": "row-1"},
    )
    rows = [json.loads(line) for line in ml_path.read_text(encoding="utf-8").splitlines()]
    assert result["status"] == "inserted"
    assert rows[0]["domain_state_key"]["row_id"] == "row-1"


def test_volc_mlp_ledger_jsonl_allows_concurrent_task_writes(tmp_path) -> None:
    ledger_path = tmp_path / "ml-experiment-ledger.jsonl"
    payloads = [
        build_volc_mlp_result_ledger(
            experiment_id="external_slice_screen",
            task_id=f"task-candidate-{index}",
            task_name=f"external_slice_cross_screen_{index}",
            state="Running",
            train_window="20251002-20260501",
            eval_window="20260501-20260508",
            code_ref="codex/example-feature-cross@abc1234",
            model_name=f"candidate_model_{index}",
        )
        for index in range(2)
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda payload: upsert_ml_experiment_ledger_jsonl(ledger_path, payload), payloads))

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {
        row["task_packet"]["observable_handle"]["task_id"]
        for row in rows
    } == {"task-candidate-0", "task-candidate-1"}
