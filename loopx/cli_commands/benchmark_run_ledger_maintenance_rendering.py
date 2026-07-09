from __future__ import annotations


def render_benchmark_run_ledger_upsert_markdown(payload: dict[str, object]) -> str:
    ledger = (
        payload.get("benchmark_run_ledger")
        if isinstance(payload.get("benchmark_run_ledger"), dict)
        else {}
    )
    entry = ledger.get("entry") if isinstance(ledger.get("entry"), dict) else {}
    decision = (
        ledger.get("case_decision")
        if isinstance(ledger.get("case_decision"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Upsert",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{ledger.get('updated')}`",
        f"- benchmark: `{entry.get('benchmark_id')}`",
        f"- case: `{entry.get('case_id')}`",
        f"- arm: `{entry.get('arm_id')}`",
        f"- score: `{entry.get('official_score')}`",
        f"- failure: `{entry.get('failure_class')}`",
        f"- decision: `{decision.get('decision')}`",
        f"- ledger: `{ledger.get('ledger_path')}`",
        f"- compact only: `{read_boundary.get('compact_only')}`",
        f"- raw logs read: `{read_boundary.get('raw_logs_read')}`",
        f"- task text read: `{read_boundary.get('task_text_read')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_check_markdown(payload: dict[str, object]) -> str:
    drift = (
        payload.get("benchmark_run_ledger_drift")
        if isinstance(payload.get("benchmark_run_ledger_drift"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Drift Check",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- drift_detected: `{drift.get('drift_detected')}`",
        f"- checked_history_run_count: `{drift.get('checked_history_run_count')}`",
        f"- terminal_history_run_count: `{drift.get('terminal_history_run_count')}`",
        f"- matched_history_run_count: `{drift.get('matched_history_run_count')}`",
        f"- missing_ledger_run_count: `{drift.get('missing_ledger_run_count')}`",
        f"- non_terminal_skipped_count: `{drift.get('non_terminal_skipped_count')}`",
        f"- ledger_run_count: `{drift.get('ledger_run_count')}`",
    ]
    missing_runs = (
        drift.get("missing_runs") if isinstance(drift.get("missing_runs"), list) else []
    )
    if missing_runs:
        lines.extend(
            [
                "",
                "## Missing Compact Runs",
                "",
                "| Benchmark | Case | Arm | Score | Failure | Catch-up |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for run in missing_runs:
            if not isinstance(run, dict):
                continue
            lines.append(
                "| "
                f"`{run.get('benchmark_id')}` | "
                f"`{run.get('case_id')}` | "
                f"`{run.get('arm_id')}` | "
                f"`{run.get('official_score')}` | "
                f"`{run.get('failure_class')}` | "
                f"`{run.get('catch_up_command_template')}` |"
            )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_archive_markdown(payload: dict[str, object]) -> str:
    archive = payload.get("archive") if isinstance(payload.get("archive"), dict) else {}
    samples = (
        archive.get("archived_samples")
        if isinstance(archive.get("archived_samples"), list)
        else []
    )
    lines = [
        "# Benchmark Run Ledger Archive",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{payload.get('updated')}`",
        f"- benchmark: `{archive.get('benchmark_id')}`",
        f"- archive_batch_id: `{archive.get('archive_batch_id')}`",
        f"- matched_run_count: `{archive.get('matched_run_count')}`",
        f"- newly_archived_run_count: `{archive.get('newly_archived_run_count')}`",
        f"- already_archived_run_count: `{archive.get('already_archived_run_count')}`",
        f"- kept_run_count: `{archive.get('kept_run_count')}`",
        f"- ledger: `{payload.get('ledger_path')}`",
    ]
    reason = archive.get("reason")
    if reason:
        lines.append(f"- reason: {reason}")
    if samples:
        lines.extend(
            [
                "",
                "## Archived Samples",
                "",
                "| Case | Arm | Run Group | Score | Failure |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            lines.append(
                "| "
                f"`{sample.get('case_id')}` | "
                f"`{sample.get('arm_id')}` | "
                f"`{sample.get('run_group_id')}` | "
                f"`{sample.get('official_score')}` | "
                f"`{sample.get('failure_class')}` |"
            )
    if archive.get("truncated"):
        lines.append("")
        lines.append("Archived samples are truncated.")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_merge_markdown(payload: dict[str, object]) -> str:
    merge = payload.get("merge") if isinstance(payload.get("merge"), dict) else {}
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Merge",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{payload.get('updated')}`",
        f"- source_ledger_count: `{merge.get('source_ledger_count')}`",
        f"- source_run_count: `{merge.get('source_run_count')}`",
        f"- considered_run_count: `{merge.get('considered_run_count')}`",
        f"- merged_run_count: `{merge.get('merged_run_count')}`",
        f"- new_run_id_count: `{merge.get('new_run_id_count')}`",
        f"- target_run_count: `{merge.get('target_run_count')}`",
        f"- source paths recorded: `{merge.get('source_paths_recorded')}`",
        f"- ledger: `{payload.get('ledger_path')}`",
        f"- compact only: `{read_boundary.get('compact_only')}`",
        f"- raw logs read: `{read_boundary.get('raw_logs_read')}`",
        f"- task text read: `{read_boundary.get('task_text_read')}`",
    ]
    if merge.get("skipped_by_reason"):
        lines.append(f"- skipped_by_reason: `{merge.get('skipped_by_reason')}`")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_aggregate_markdown(payload: dict[str, object]) -> str:
    aggregate = payload.get("aggregate") if isinstance(payload.get("aggregate"), dict) else {}
    distribution = (
        aggregate.get("distribution")
        if isinstance(aggregate.get("distribution"), dict)
        else {}
    )
    score_summary = (
        aggregate.get("countable_score_summary")
        if isinstance(aggregate.get("countable_score_summary"), dict)
        else {}
    )
    standard_case_sets = (
        aggregate.get("standard_case_sets")
        if isinstance(aggregate.get("standard_case_sets"), dict)
        else {}
    )
    selection_policy = (
        aggregate.get("selection_policy")
        if isinstance(aggregate.get("selection_policy"), dict)
        else {}
    )
    target_lane = (
        selection_policy.get("target_lane")
        if isinstance(selection_policy.get("target_lane"), dict)
        else {}
    )

    def _list_count(value: object) -> int:
        return len(value) if isinstance(value, list) else 0

    lines = [
        "# Benchmark Run Ledger Current Aggregate",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{payload.get('updated')}`",
        f"- benchmark: `{aggregate.get('benchmark_id')}`",
        f"- canonical_covered: `{aggregate.get('canonical_covered')}` / `{aggregate.get('canonical_total')}`",
        f"- countable_cases: `{score_summary.get('countable_case_count')}`",
        f"- countable_score_sum: `{score_summary.get('countable_score_sum')}`",
        f"- countable_score_mean: `{score_summary.get('countable_score_mean')}`",
        f"- accepted_case_count: `{_list_count(standard_case_sets.get('accepted_case_ids'))}`",
        f"- missing_case_count: `{_list_count(standard_case_sets.get('missing_case_ids'))}`",
        f"- blocked_uncountable_case_count: `{_list_count(standard_case_sets.get('blocked_uncountable_case_ids'))}`",
        f"- active_case_count: `{_list_count(standard_case_sets.get('active_case_ids'))}`",
        f"- runnable_missing_case_count: `{_list_count(standard_case_sets.get('runnable_missing_case_ids'))}`",
        f"- distribution: `{distribution}`",
        f"- selection_rule: `{selection_policy.get('rule')}`",
        f"- target_lane_enabled: `{target_lane.get('enabled')}`",
        f"- target_lane_id: `{target_lane.get('lane_id')}`",
        f"- deduped_run_count: `{aggregate.get('deduped_run_count')}`",
        f"- source_ledger_files: `{aggregate.get('source_ledger_files')}`",
        f"- output_json: `{payload.get('output_json')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"
