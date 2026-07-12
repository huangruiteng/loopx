from __future__ import annotations

from typing import Any

from .public_safety import public_safe_compact_list, public_safe_compact_text

BENCHMARK_COMPARISON_SCHEMA_VERSION = "benchmark_comparison_v0"
BENCHMARK_COMPARISON_DECISION_SCHEMA_VERSION = "benchmark_comparison_decision_note_v0"
BENCHMARK_BASELINE_FAILURE_GATE_SCHEMA_VERSION = "benchmark_baseline_failure_gate_v0"
MAX_BENCHMARK_COMPARISON_LIST_ITEMS = 5


def _benchmark_comparison_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_comparison")
    if (
        isinstance(nested, dict)
        and nested.get("schema_version") == BENCHMARK_COMPARISON_SCHEMA_VERSION
    ):
        return nested
    if run.get("schema_version") == BENCHMARK_COMPARISON_SCHEMA_VERSION:
        return run
    return None


def compact_comparison_delta(value: Any) -> int | float | str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return public_safe_compact_text(value, limit=120)


def _compact_benchmark_baseline_failure_gate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {
        "schema_version": BENCHMARK_BASELINE_FAILURE_GATE_SCHEMA_VERSION,
    }
    for field in (
        "baseline_mode",
        "baseline_scenario_id",
        "baseline_terminal_state",
        "failure_phase",
        "failure_class",
        "negative_selection_reason",
        "minimum_next_evidence",
        "next_action",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "baseline_failed",
        "control_plane_addressable",
        "treatment_eligible",
        "same_task_semantics",
        "same_runner_protocol",
        "trace_publicness_verified",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in ("baseline_attempt_count",):
        count = value.get(field)
        if isinstance(count, int) and not isinstance(count, bool):
            compact[field] = count
    for field in ("failure_attribution_labels", "evidence_refs"):
        values = public_safe_compact_list(
            value.get(field), limit=MAX_BENCHMARK_COMPARISON_LIST_ITEMS
        )
        if values:
            compact[field] = values
    if set(compact.keys()) == {"schema_version"}:
        return {}
    return compact


def compact_benchmark_comparison(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_comparison_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_COMPARISON_SCHEMA_VERSION}
    for field in (
        "task_id",
        "comparison_id",
        "decision_id",
        "benchmark_id",
        "baseline_scenario_id",
        "treatment_scenario_id",
        "next_action",
    ):
        value = public_safe_compact_text(source.get(field), limit=180)
        if value:
            compact[field] = value

    mode_pair = public_safe_compact_list(
        source.get("mode_pair"), limit=MAX_BENCHMARK_COMPARISON_LIST_ITEMS
    )
    if mode_pair:
        compact["mode_pair"] = mode_pair

    for field in (
        "scenario_count",
        "official_task_score_delta",
        "control_plane_score_delta",
        "cost_delta_usd",
        "with_loopx_overhead_ms",
        "with_loopx_extra_writebacks",
        "with_loopx_extra_spends",
        "checklist_pass_count",
    ):
        delta = compact_comparison_delta(source.get(field))
        if delta is not None:
            compact[field] = delta

    for field in (
        "both_success",
        "ready_to_attempt_no_submit_setup_probe",
        "ready_to_run_real_benchmark",
        "ready_to_submit_leaderboard",
        "requires_explicit_authorization_for_real_execution",
    ):
        if isinstance(source.get(field), bool):
            compact[field] = source.get(field)

    for field in (
        "metrics_compared",
        "interrupt_fixture_markers",
        "stop_conditions",
        "failure_attribution_labels",
    ):
        values = public_safe_compact_list(
            source.get(field), limit=MAX_BENCHMARK_COMPARISON_LIST_ITEMS
        )
        if values:
            compact[field] = values

    claim_boundary = source.get("claim_boundary")
    if isinstance(claim_boundary, dict):
        compact_claim_boundary: dict[str, bool] = {}
        for field in (
            "leaderboard_claim_allowed",
            "official_score_uplift_claim_allowed",
            "assisted_collaboration_claim_allowed",
            "raw_trace_excluded",
            "credential_values_recorded",
        ):
            if isinstance(claim_boundary.get(field), bool):
                compact_claim_boundary[field] = claim_boundary[field]
        if compact_claim_boundary:
            compact["claim_boundary"] = compact_claim_boundary

    baseline_gate = _compact_benchmark_baseline_failure_gate(
        source.get("baseline_failure_gate")
    )
    if baseline_gate:
        compact["baseline_failure_gate"] = baseline_gate

    decision = source.get("decision")
    if isinstance(decision, dict):
        compact_decision: dict[str, Any] = {}
        for field in ("score_uplift", "validation_enhancement_point"):
            if isinstance(decision.get(field), bool):
                compact_decision[field] = decision[field]
        why = public_safe_compact_text(decision.get("why"), limit=240)
        if why:
            compact_decision["why"] = why
        if compact_decision:
            compact["decision"] = compact_decision

    result_refs: list[dict[str, Any]] = []
    for item in source.get("result_refs") or []:
        if not isinstance(item, dict):
            continue
        compact_ref: dict[str, Any] = {}
        for field in ("scenario_id", "task_id", "result_id"):
            value = public_safe_compact_text(item.get(field), limit=140)
            if value:
                compact_ref[field] = value
        if compact_ref:
            result_refs.append(compact_ref)
            if len(result_refs) >= MAX_BENCHMARK_COMPARISON_LIST_ITEMS:
                break
    if result_refs:
        compact["result_refs"] = result_refs

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


def _comparison_delta_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if isinstance(value, str) and value.strip():
            return float(value)
    except ValueError:
        return None
    return None


def benchmark_comparison_decision_note(
    comparison: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        not isinstance(comparison, dict)
        or comparison.get("schema_version") != BENCHMARK_COMPARISON_SCHEMA_VERSION
    ):
        return None

    official_delta = _comparison_delta_number(
        comparison.get("official_task_score_delta")
    )
    control_delta = _comparison_delta_number(
        comparison.get("control_plane_score_delta")
    )
    symbolic_official = (
        comparison.get("official_task_score_delta")
        if isinstance(comparison.get("official_task_score_delta"), str)
        else None
    )
    both_success = (
        comparison.get("both_success")
        if isinstance(comparison.get("both_success"), bool)
        else None
    )
    submit_ready = comparison.get("ready_to_submit_leaderboard")
    real_ready = comparison.get("ready_to_run_real_benchmark")
    decision_summary = (
        comparison.get("decision")
        if isinstance(comparison.get("decision"), dict)
        else {}
    )
    validation_enhancement = (
        decision_summary.get("validation_enhancement_point")
        if isinstance(decision_summary.get("validation_enhancement_point"), bool)
        else None
    )
    score_uplift = (
        decision_summary.get("score_uplift")
        if isinstance(decision_summary.get("score_uplift"), bool)
        else None
    )
    failure_labels = public_safe_compact_list(
        comparison.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_COMPARISON_LIST_ITEMS,
    )
    baseline_gate = (
        comparison.get("baseline_failure_gate")
        if isinstance(comparison.get("baseline_failure_gate"), dict)
        else {}
    )
    baseline_failed = (
        baseline_gate.get("baseline_failed")
        if isinstance(baseline_gate.get("baseline_failed"), bool)
        else None
    )
    control_plane_addressable = (
        baseline_gate.get("control_plane_addressable")
        if isinstance(baseline_gate.get("control_plane_addressable"), bool)
        else None
    )
    treatment_eligible = (
        baseline_gate.get("treatment_eligible")
        if isinstance(baseline_gate.get("treatment_eligible"), bool)
        else None
    )

    evidence_layer = "comparison_summary"
    decision = "repeat"
    minimum_next_evidence = "repeat the paired comparison or record a blocker"
    may_claim = ["compact paired comparison is available"]
    must_not_claim = ["official leaderboard uplift"]

    if symbolic_official == "not_applicable_readiness_only":
        evidence_layer = "readiness_only"
        decision = "continue"
        minimum_next_evidence = (
            "record no-submit setup evidence before any real benchmark run"
        )
        may_claim.append("readiness boundary is documented")
        must_not_claim.append("benchmark pass/fail or score uplift")
    elif official_delta is None and control_delta is None and baseline_gate:
        if (
            baseline_failed is True
            and control_plane_addressable is True
            and treatment_eligible is True
        ):
            evidence_layer = "baseline_failure_gate"
            decision = "continue"
            minimum_next_evidence = (
                public_safe_compact_text(
                    baseline_gate.get("minimum_next_evidence"), limit=180
                )
                or "run the treatment arm only for this control-plane-addressable baseline failure"
            )
            may_claim.append(
                "baseline failure is control-plane-addressable and treatment-eligible"
            )
            must_not_claim.append(
                "treatment uplift before paired treatment evidence exists"
            )
        else:
            evidence_layer = "baseline_failure_gate_negative_selection"
            decision = "defer"
            minimum_next_evidence = (
                public_safe_compact_text(
                    baseline_gate.get("negative_selection_reason"), limit=180
                )
                or "select a baseline failure with public-safe control-plane-addressable attribution"
            )
            may_claim.append("candidate was screened by baseline-failure gate")
            must_not_claim.append(
                "treatment execution on non-addressable or unverified baseline failures"
            )
    elif official_delta == 0 and control_delta is not None and control_delta > 0:
        evidence_layer = "control_plane_only"
        decision = "continue"
        minimum_next_evidence = "convert the control-plane delta into a report note or repeat on an official-runner-compatible output"
        may_claim.append(
            "control-plane delta improved while official score delta stayed zero"
        )
        must_not_claim.append(
            "benchmark pass/fail improvement from control-plane-only evidence"
        )
    elif official_delta is not None and official_delta > 0:
        evidence_layer = "official_score_candidate"
        decision = "defer" if submit_ready is not True else "broaden"
        minimum_next_evidence = "verify benchmark protocol, submit eligibility, and side-effect audit before claiming official uplift"
        may_claim.append("official score candidate exists")
        must_not_claim.append(
            "official uplift before protocol and submit-eligibility verification"
        )
    elif (
        official_delta == 0 and validation_enhancement is True and score_uplift is False
    ):
        evidence_layer = "validation_enhancement_no_score_uplift"
        decision = "continue"
        minimum_next_evidence = "repeat on a stronger target or harden the recorded failure-attribution/writeback path"
        may_claim.append(
            "validation or failure-attribution evidence improved while official score delta stayed zero"
        )
        must_not_claim.append("official score uplift")
    elif both_success is False:
        evidence_layer = "failure_analysis"
        decision = "repeat"
        minimum_next_evidence = "attribute the failed scenario before broadening"
        may_claim.append("paired comparison found a failure needing attribution")
    elif real_ready is False:
        evidence_layer = "boundary_guarded"
        decision = "defer"
        minimum_next_evidence = "resolve real-run readiness blockers before execution"
        may_claim.append("real benchmark execution remains gated")

    note: dict[str, Any] = {
        "schema_version": BENCHMARK_COMPARISON_DECISION_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_COMPARISON_SCHEMA_VERSION,
        "decision": decision,
        "evidence_layer": evidence_layer,
        "minimum_next_evidence": minimum_next_evidence,
        "stop_condition": "stop before real benchmark execution, model-backed simulator work, private traces, or leaderboard claims without explicit approval",
        "may_claim": may_claim[:MAX_BENCHMARK_COMPARISON_LIST_ITEMS],
        "must_not_claim": must_not_claim[:MAX_BENCHMARK_COMPARISON_LIST_ITEMS],
        "report_section_hint": ["claim_boundary", "next_decision"],
    }
    for field in ("task_id", "comparison_id"):
        value = public_safe_compact_text(comparison.get(field), limit=140)
        if value:
            note[field] = value
    if official_delta is not None:
        note["official_task_score_delta"] = official_delta
    elif symbolic_official:
        note["official_task_score_delta"] = symbolic_official
    if control_delta is not None:
        note["control_plane_score_delta"] = control_delta
    elif isinstance(comparison.get("control_plane_score_delta"), str):
        note["control_plane_score_delta"] = public_safe_compact_text(
            comparison.get("control_plane_score_delta"), limit=120
        )
    if failure_labels:
        note["failure_attribution_labels"] = failure_labels
    if baseline_gate:
        compact_note_gate: dict[str, Any] = {
            "schema_version": BENCHMARK_BASELINE_FAILURE_GATE_SCHEMA_VERSION,
        }
        for field in (
            "baseline_mode",
            "failure_phase",
            "failure_class",
            "negative_selection_reason",
        ):
            value = public_safe_compact_text(baseline_gate.get(field), limit=140)
            if value:
                compact_note_gate[field] = value
        for field, value in (
            ("baseline_failed", baseline_failed),
            ("control_plane_addressable", control_plane_addressable),
            ("treatment_eligible", treatment_eligible),
        ):
            if isinstance(value, bool):
                compact_note_gate[field] = value
        note["baseline_failure_gate"] = compact_note_gate
    if validation_enhancement is not None:
        note["validation_enhancement_point"] = validation_enhancement
    if score_uplift is not None:
        note["score_uplift"] = score_uplift
    return note
