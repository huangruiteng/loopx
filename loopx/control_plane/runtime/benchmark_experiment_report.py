from __future__ import annotations

from typing import Any

from .benchmark_attempt_accounting import compact_benchmark_attempt_accounting
from .public_safety import (
    compact_numeric_map,
    public_safe_compact_list,
    public_safe_compact_text,
)

BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION = "benchmark_experiment_report_v0"
BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION = (
    "benchmark_experiment_report_readiness_note_v0"
)
BENCHMARK_EXPERIMENT_REPORT_REPLAY_DECISION_SCHEMA_VERSION = (
    "benchmark_experiment_report_replay_decision_v0"
)
MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS = 5


def _benchmark_experiment_report_source(
    run: dict[str, Any],
) -> dict[str, Any] | None:
    nested = run.get("benchmark_experiment_report")
    if (
        isinstance(nested, dict)
        and nested.get("schema_version") == BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION
    ):
        return nested
    legacy_nested = run.get("benchmark_report")
    if (
        isinstance(legacy_nested, dict)
        and legacy_nested.get("schema_version")
        == BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION
    ):
        return legacy_nested
    if run.get("schema_version") == BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION:
        return run
    return None


def compact_benchmark_experiment_report(
    run: dict[str, Any],
) -> dict[str, Any] | None:
    source = _benchmark_experiment_report_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {
        "schema_version": BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION
    }

    identity = (
        source.get("experiment_identity")
        if isinstance(source.get("experiment_identity"), dict)
        else {}
    )
    compact_identity: dict[str, Any] = {}
    for field in (
        "report_id",
        "benchmark_id",
        "task_slice",
        "worker_surface",
        "harness_identity",
        "harness_policy_version",
        "trace_publicness",
    ):
        value = public_safe_compact_text(identity.get(field), limit=140)
        if value:
            compact_identity[field] = value
    if compact_identity:
        compact["experiment_identity"] = compact_identity

    official = (
        source.get("official_score")
        if isinstance(source.get("official_score"), dict)
        else {}
    )
    compact_official: dict[str, Any] = {}
    for field in ("kind", "task_id_or_split", "runner_source"):
        value = public_safe_compact_text(official.get(field), limit=140)
        if value:
            compact_official[field] = value
    compact_official.update(
        compact_numeric_map(
            official,
            keys=("native_score", "wrapped_score", "delta", "repetitions"),
        )
    )
    for field in ("submit_eligible", "leaderboard_evidence"):
        if isinstance(official.get(field), bool):
            compact_official[field] = official[field]
    if compact_official:
        compact["official_score"] = compact_official

    attempt_accounting = compact_benchmark_attempt_accounting(
        source.get("attempt_accounting")
    )
    if attempt_accounting:
        compact["attempt_accounting"] = attempt_accounting

    passive = (
        source.get("passive_control_plane_score")
        if isinstance(source.get("passive_control_plane_score"), dict)
        else {}
    )
    compact_passive = compact_numeric_map(
        passive,
        keys=(
            "restartability",
            "stale_state_avoidance",
            "evidence_discipline",
            "writeback_quality",
            "failure_attribution",
        ),
    )
    for field in ("overhead_bounded", "regression_avoidance_passed"):
        if isinstance(passive.get(field), bool):
            compact_passive[field] = passive[field]
    passive_events = public_safe_compact_list(
        passive.get("source_events"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )
    if passive_events:
        compact_passive["source_events"] = passive_events
    if compact_passive:
        compact["passive_control_plane_score"] = compact_passive

    simulator = (
        source.get("operator_simulator_ablation")
        if isinstance(source.get("operator_simulator_ablation"), dict)
        else {}
    )
    compact_simulator: dict[str, Any] = {}
    for field in ("enabled", "leaderboard_evidence"):
        if isinstance(simulator.get(field), bool):
            compact_simulator[field] = simulator[field]
    compact_simulator.update(
        compact_numeric_map(simulator, keys=("intervention_count",))
    )
    reason = public_safe_compact_text(simulator.get("reason"), limit=180)
    if reason:
        compact_simulator["reason"] = reason
    if compact_simulator:
        compact["operator_simulator_ablation"] = compact_simulator

    claim_boundary = (
        source.get("claim_boundary")
        if isinstance(source.get("claim_boundary"), dict)
        else {}
    )
    compact_boundary: dict[str, Any] = {}
    for field in ("may_claim", "must_not_claim"):
        values = public_safe_compact_list(
            claim_boundary.get(field),
            limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
        )
        if values:
            compact_boundary[field] = values
    for field in ("source_decision_note_schema", "source_evidence_layer"):
        value = public_safe_compact_text(claim_boundary.get(field), limit=120)
        if value:
            compact_boundary[field] = value
    if compact_boundary:
        compact["claim_boundary"] = compact_boundary

    negative = (
        source.get("negative_results")
        if isinstance(source.get("negative_results"), dict)
        else {}
    )
    compact_negative: dict[str, Any] = {}
    if isinstance(negative.get("null_official_delta"), bool):
        compact_negative["null_official_delta"] = negative["null_official_delta"]
    layers = public_safe_compact_list(
        negative.get("negative_evidence_layers"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )
    failed_hypotheses = (
        negative.get("failed_hypotheses")
        if isinstance(negative.get("failed_hypotheses"), list)
        else []
    )
    for item in failed_hypotheses:
        if not isinstance(item, dict):
            continue
        layer = public_safe_compact_text(item.get("evidence_layer"), limit=120)
        if layer and layer not in layers:
            layers.append(layer)
        if len(layers) >= MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS:
            break
    if failed_hypotheses:
        compact_negative["failed_hypothesis_count"] = len(failed_hypotheses)
    elif isinstance(negative.get("failed_hypothesis_count"), int):
        compact_negative["failed_hypothesis_count"] = negative[
            "failed_hypothesis_count"
        ]
    if layers:
        compact_negative["negative_evidence_layers"] = layers
    overhead_regressions = negative.get("overhead_regressions")
    if isinstance(overhead_regressions, list):
        compact_negative["overhead_regression_count"] = len(overhead_regressions)
    elif isinstance(negative.get("overhead_regression_count"), int):
        compact_negative["overhead_regression_count"] = negative[
            "overhead_regression_count"
        ]
    if compact_negative:
        compact["negative_results"] = compact_negative

    next_decision = (
        source.get("next_decision")
        if isinstance(source.get("next_decision"), dict)
        else {}
    )
    compact_next: dict[str, Any] = {}
    for field in (
        "decision",
        "minimum_next_evidence",
        "stop_condition",
        "source_decision_note_schema",
        "readiness_decision",
        "failure_decision",
    ):
        value = public_safe_compact_text(next_decision.get(field), limit=180)
        if value:
            compact_next[field] = value
    if compact_next:
        compact["next_decision"] = compact_next

    report_sections = (
        "experiment_identity",
        "official_score",
        "passive_control_plane_score",
        "operator_simulator_ablation",
        "cost_latency_overhead",
        "failure_taxonomy",
        "reproducibility_artifacts",
        "claim_boundary",
        "negative_results",
        "next_decision",
    )
    compact["section_count"] = sum(
        1 for section in report_sections if isinstance(source.get(section), dict)
    )

    if set(compact) == {"schema_version", "section_count"}:
        return None
    return compact


def benchmark_experiment_report_readiness_note(
    report: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION
    ):
        return None

    identity = (
        report.get("experiment_identity")
        if isinstance(report.get("experiment_identity"), dict)
        else {}
    )
    official = (
        report.get("official_score")
        if isinstance(report.get("official_score"), dict)
        else {}
    )
    simulator = (
        report.get("operator_simulator_ablation")
        if isinstance(report.get("operator_simulator_ablation"), dict)
        else {}
    )
    boundary = (
        report.get("claim_boundary")
        if isinstance(report.get("claim_boundary"), dict)
        else {}
    )
    negative = (
        report.get("negative_results")
        if isinstance(report.get("negative_results"), dict)
        else {}
    )
    next_decision = (
        report.get("next_decision")
        if isinstance(report.get("next_decision"), dict)
        else {}
    )

    submit_eligible = (
        official.get("submit_eligible")
        if isinstance(official.get("submit_eligible"), bool)
        else None
    )
    leaderboard_evidence = (
        official.get("leaderboard_evidence")
        if isinstance(official.get("leaderboard_evidence"), bool)
        else None
    )
    simulator_enabled = (
        simulator.get("enabled") if isinstance(simulator.get("enabled"), bool) else None
    )
    null_official_delta = (
        negative.get("null_official_delta")
        if isinstance(negative.get("null_official_delta"), bool)
        else None
    )
    negative_layers = public_safe_compact_list(
        negative.get("negative_evidence_layers"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )
    must_not_claim = public_safe_compact_list(
        boundary.get("must_not_claim"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )
    may_claim = public_safe_compact_list(
        boundary.get("may_claim"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )

    readiness = "fixture_ready"
    next_run_authorization = "fixture_only"
    minimum_next_evidence = (
        public_safe_compact_text(next_decision.get("minimum_next_evidence"), limit=180)
        or "compact report summary plus boundary-preserving replay evidence"
    )
    if submit_eligible is True and leaderboard_evidence is True:
        readiness = "review_required"
        next_run_authorization = "requires_operator_approval"
        minimum_next_evidence = (
            "operator review of leaderboard evidence before publication"
        )
    elif submit_eligible is True:
        readiness = "review_required"
        next_run_authorization = "requires_operator_approval"
        minimum_next_evidence = (
            "leaderboard evidence or an explicit downgrade to fixture-only"
        )
    elif simulator_enabled is True:
        readiness = "assisted_mode_separate"
        next_run_authorization = "requires_operator_approval"
        minimum_next_evidence = "operator-simulator ablation evidence kept separate from passive report evidence"
    elif null_official_delta is True or negative_layers:
        readiness = "negative_or_control_plane_only"
        next_run_authorization = "fixture_only"

    stop_condition = public_safe_compact_text(
        next_decision.get("stop_condition"), limit=180
    ) or (
        "stop before real benchmark execution, model-backed simulator work, private traces, "
        "or leaderboard claims without explicit approval"
    )
    report_decision = (
        public_safe_compact_text(next_decision.get("decision"), limit=80) or "continue"
    )

    note: dict[str, Any] = {
        "schema_version": BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION,
        "readiness": readiness,
        "next_run_authorization": next_run_authorization,
        "report_decision": report_decision,
        "minimum_next_evidence": minimum_next_evidence,
        "stop_condition": stop_condition,
        "report_section_hint": [
            "claim_boundary",
            "negative_results",
            "next_decision",
        ],
    }
    for field in ("report_id", "benchmark_id", "task_slice"):
        value = public_safe_compact_text(identity.get(field), limit=140)
        if value:
            note[field] = value
    if may_claim:
        note["may_claim"] = may_claim
    if must_not_claim:
        note["must_not_claim"] = must_not_claim
    if negative_layers:
        note["negative_evidence_layers"] = negative_layers
    for field, value in (
        ("submit_eligible", submit_eligible),
        ("leaderboard_evidence", leaderboard_evidence),
        ("simulator_enabled", simulator_enabled),
        ("null_official_delta", null_official_delta),
    ):
        if isinstance(value, bool):
            note[field] = value
    return note


def benchmark_experiment_report_replay_decision(
    readiness_note: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        not isinstance(readiness_note, dict)
        or readiness_note.get("schema_version")
        != BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION
    ):
        return None

    readiness = (
        public_safe_compact_text(readiness_note.get("readiness"), limit=120)
        or "fixture_ready"
    )
    authorization = (
        public_safe_compact_text(
            readiness_note.get("next_run_authorization"), limit=120
        )
        or "fixture_only"
    )
    report_decision = (
        public_safe_compact_text(readiness_note.get("report_decision"), limit=80)
        or "continue"
    )

    if authorization == "fixture_only":
        replay_decision = (
            "continue_fixture_replay"
            if report_decision in {"continue", "broaden"}
            else "repeat_fixture_replay"
        )
        next_run_mode = "fixture_replay"
    elif authorization == "requires_operator_approval":
        replay_decision = "operator_review_required"
        next_run_mode = "operator_review"
    else:
        replay_decision = "defer_until_authorized"
        next_run_mode = "deferred"

    if readiness == "assisted_mode_separate":
        replay_decision = "separate_assisted_mode_before_replay"
        next_run_mode = "operator_review"

    minimum_next_evidence = (
        public_safe_compact_text(readiness_note.get("minimum_next_evidence"), limit=180)
        or "boundary-preserving replay decision evidence"
    )
    stop_condition = public_safe_compact_text(
        readiness_note.get("stop_condition"), limit=180
    ) or (
        "stop before real benchmark execution, model-backed simulator work, private traces, "
        "or leaderboard claims without explicit approval"
    )
    negative_layers = public_safe_compact_list(
        readiness_note.get("negative_evidence_layers"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )
    must_not_claim = public_safe_compact_list(
        readiness_note.get("must_not_claim"),
        limit=MAX_BENCHMARK_EXPERIMENT_REPORT_LIST_ITEMS,
    )

    decision: dict[str, Any] = {
        "schema_version": BENCHMARK_EXPERIMENT_REPORT_REPLAY_DECISION_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION,
        "readiness": readiness,
        "authorization": authorization,
        "replay_decision": replay_decision,
        "next_run_mode": next_run_mode,
        "minimum_next_evidence": minimum_next_evidence,
        "stop_condition": stop_condition,
        "surface": "status_review_packet_only",
    }
    for field in ("report_id", "benchmark_id", "task_slice"):
        value = public_safe_compact_text(readiness_note.get(field), limit=140)
        if value:
            decision[field] = value
    if negative_layers:
        decision["negative_evidence_layers"] = negative_layers
    if must_not_claim:
        decision["must_not_claim"] = must_not_claim
    return decision
