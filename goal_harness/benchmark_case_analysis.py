from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BENCHMARK_CASE_ANALYSIS_CANDIDATE_REPORT_SCHEMA_VERSION = (
    "benchmark_case_analysis_candidate_report_v0"
)
BENCHMARK_CASE_ANALYSIS_UPSERT_PROPOSAL_SCHEMA_VERSION = (
    "benchmark_case_analysis_upsert_proposal_v0"
)

NO_RUN_DECISIONS = {"", "no_runs_recorded"}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _compact_text(value: object, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def case_analysis_keys(analysis: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    cases = analysis.get("cases")
    if not isinstance(cases, list):
        return keys
    for case in cases:
        if not isinstance(case, dict):
            continue
        benchmark_id = _compact_text(case.get("benchmark_id"), limit=160)
        case_id = _compact_text(case.get("case_id"), limit=200)
        if benchmark_id and case_id:
            keys.add((benchmark_id, case_id))
    return keys


def classify_case_analysis_candidate(
    *,
    latest_decision: str,
    run_count: int,
) -> dict[str, str]:
    if latest_decision == "paired_no_score_uplift":
        return {
            "candidate_class": "paired_no_uplift_candidate",
            "promotion_priority": "P1",
            "recommended_handling": (
                "promote when the no-uplift result changes routing, prompt, or "
                "treatment policy"
            ),
        }
    if latest_decision == "paired_baseline_solved_treatment_preserved":
        return {
            "candidate_class": "baseline_solved_non_regression_candidate",
            "promotion_priority": "P2",
            "recommended_handling": (
                "promote selectively as a non-regression guard or keep in "
                "generated coverage"
            ),
        }
    if latest_decision.startswith("paired_treatment_") and (
        "alignment_required" in latest_decision
        or "preflight_required" in latest_decision
    ):
        return {
            "candidate_class": "infrastructure_alignment_candidate",
            "promotion_priority": "P1",
            "recommended_handling": (
                "promote only when the alignment or preflight lesson is reusable "
                "across future runs"
            ),
        }
    if latest_decision == "baseline_failed_treatment_candidate":
        return {
            "candidate_class": "baseline_failure_treatment_candidate",
            "promotion_priority": "P1",
            "recommended_handling": (
                "add failure attribution or a matched treatment before making a "
                "strong case-analysis claim"
            ),
        }
    if "runner_or_setup" in latest_decision or "setup" in latest_decision:
        return {
            "candidate_class": "setup_or_runner_gap_defer",
            "promotion_priority": "P2",
            "recommended_handling": (
                "defer until the compact run reaches scoring or the setup blocker "
                "itself becomes a reusable infrastructure lesson"
            ),
        }
    if latest_decision == "baseline_passed_not_current_treatment_priority":
        return {
            "candidate_class": "baseline_solved_control_candidate",
            "promotion_priority": "P2",
            "recommended_handling": (
                "promote selectively as a baseline-solved control when the case "
                "is needed for routing or coverage"
            ),
        }
    if latest_decision == "single_arm_recorded":
        priority = "P1" if run_count > 1 else "P2"
        return {
            "candidate_class": "single_arm_coverage_or_baseline_candidate",
            "promotion_priority": priority,
            "recommended_handling": (
                "keep as coverage unless the single-arm result teaches a durable "
                "routing or infrastructure lesson"
            ),
        }
    return {
        "candidate_class": "needs_manual_classification",
        "promotion_priority": "P1",
        "recommended_handling": (
            "inspect compact ledger fields only and classify before editing "
            "case-analysis"
        ),
    }


def _case_analysis_id(benchmark_id: str, case_id: str, candidate_class: str) -> str:
    def slug(value: str) -> str:
        text = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
        text = "-".join(part for part in text.split("-") if part)
        return text or "unknown"

    return f"{slug(benchmark_id)}__{slug(case_id)}__{slug(candidate_class)}"


def _proposal_classification(candidate_class: str) -> str:
    mapping = {
        "paired_no_uplift_candidate": "no_uplift_candidate_proposal",
        "baseline_solved_non_regression_candidate": (
            "baseline_solved_non_regression_candidate_proposal"
        ),
        "infrastructure_alignment_candidate": (
            "infrastructure_alignment_candidate_proposal"
        ),
        "baseline_failure_treatment_candidate": (
            "baseline_failure_treatment_candidate_proposal"
        ),
        "setup_or_runner_gap_defer": "setup_or_runner_gap_defer_proposal",
        "baseline_solved_control_candidate": (
            "baseline_solved_control_candidate_proposal"
        ),
        "single_arm_coverage_or_baseline_candidate": (
            "single_arm_coverage_or_baseline_candidate_proposal"
        ),
    }
    return mapping.get(candidate_class, "manual_classification_required_proposal")


def _proposal_capability_signal(candidate: dict[str, Any]) -> str:
    candidate_class = _compact_text(candidate.get("candidate_class"), limit=120)
    decision = _compact_text(candidate.get("latest_decision"), limit=120)
    benchmark_id = _compact_text(candidate.get("benchmark_id"), limit=120)
    case_id = _compact_text(candidate.get("case_id"), limit=160)
    run_count = candidate.get("run_count", 0)
    if candidate_class == "baseline_failure_treatment_candidate":
        return (
            f"{benchmark_id}/{case_id} has a compact baseline failure candidate "
            f"({decision}) across {run_count} recorded run(s); promote only after "
            "matched treatment or stronger compact attribution."
        )
    if candidate_class == "infrastructure_alignment_candidate":
        return (
            f"{benchmark_id}/{case_id} carries a compact infrastructure/alignment "
            f"lesson ({decision}); promote if the setup or verifier-alignment "
            "lesson applies beyond this single run."
        )
    if candidate_class == "paired_no_uplift_candidate":
        return (
            f"{benchmark_id}/{case_id} has compact paired no-uplift evidence "
            f"({decision}); use it to adjust routing or treatment policy, not as "
            "a positive uplift claim."
        )
    if candidate_class == "baseline_solved_control_candidate":
        return (
            f"{benchmark_id}/{case_id} is a compact baseline-solved control "
            f"({decision}); promote selectively for coverage or routing balance."
        )
    return (
        f"{benchmark_id}/{case_id} is a compact ledger-only candidate "
        f"({decision}); review proposed classification before editing the case "
        "analysis table."
    )


def _proposal_control_plane_signal(candidate: dict[str, Any]) -> str:
    handling = _compact_text(candidate.get("recommended_handling"), limit=220)
    priority = _compact_text(candidate.get("promotion_priority"), limit=20)
    return (
        f"Generated as a {priority} proposal from compact ledger metadata only. "
        f"Recommended handling: {handling}."
    )


def proposed_case_analysis_record_from_candidate(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    benchmark_id = _compact_text(candidate.get("benchmark_id"), limit=160)
    case_id = _compact_text(candidate.get("case_id"), limit=200)
    candidate_class = _compact_text(candidate.get("candidate_class"), limit=160)
    recent_run_ids = [
        _compact_text(run_id, limit=120)
        for run_id in candidate.get("recent_run_ids", [])
        if run_id
    ]
    return {
        "schema_version": BENCHMARK_CASE_ANALYSIS_UPSERT_PROPOSAL_SCHEMA_VERSION,
        "proposal_status": "proposal_only_not_applied",
        "analysis_id": _case_analysis_id(benchmark_id, case_id, candidate_class),
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "classification": _proposal_classification(candidate_class),
        "latest_ledger_decision": _compact_text(
            candidate.get("latest_decision"), limit=160
        ),
        "candidate_class": candidate_class,
        "promotion_priority": _compact_text(
            candidate.get("promotion_priority"), limit=20
        ),
        "source_run_ids": recent_run_ids,
        "source_run_count": int(candidate.get("run_count") or 0),
        "capability_signal": _proposal_capability_signal(candidate),
        "control_plane_signal": _proposal_control_plane_signal(candidate),
        "recommended_next_action": _compact_text(
            candidate.get("recommended_handling"), limit=260
        ),
        "source_boundary": {
            "inputs": [
                "compact benchmark-run-ledger candidate",
                "benchmark-case-analysis existing keys",
            ],
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "trajectory_recorded": False,
            "absolute_paths_recorded": False,
            "proposal_only": True,
        },
    }


def build_case_analysis_upsert_proposals(
    *,
    ledger: dict[str, Any],
    analysis: dict[str, Any],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    candidates = find_case_analysis_candidates(ledger=ledger, analysis=analysis)
    proposals = [
        proposed_case_analysis_record_from_candidate(candidate)
        for candidate in candidates
    ]
    if limit is not None:
        return proposals[: max(0, limit)]
    return proposals


def find_case_analysis_candidates(
    *,
    ledger: dict[str, Any],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    existing = case_analysis_keys(analysis)
    candidates: list[dict[str, Any]] = []
    benchmarks = ledger.get("benchmarks")
    if not isinstance(benchmarks, dict):
        return candidates
    for benchmark_id in sorted(benchmarks):
        benchmark = benchmarks[benchmark_id]
        if not isinstance(benchmark, dict):
            continue
        cases = benchmark.get("cases")
        if not isinstance(cases, dict):
            continue
        for case_id in sorted(cases):
            if (benchmark_id, case_id) in existing:
                continue
            case = cases[case_id]
            if not isinstance(case, dict):
                continue
            latest = case.get("latest_decision")
            if not isinstance(latest, dict):
                continue
            decision = _compact_text(latest.get("decision"), limit=160)
            if decision in NO_RUN_DECISIONS:
                continue
            runs = [run for run in case.get("runs", []) if isinstance(run, dict)]
            classified = classify_case_analysis_candidate(
                latest_decision=decision,
                run_count=len(runs),
            )
            run_ids = [
                _compact_text(run.get("run_id"), limit=120)
                for run in runs[-3:]
                if run.get("run_id")
            ]
            candidates.append(
                {
                    "benchmark_id": benchmark_id,
                    "case_id": case_id,
                    "latest_decision": decision,
                    "run_count": len(runs),
                    "recent_run_ids": run_ids,
                    **classified,
                    "raw_logs_recorded": False,
                    "raw_task_text_recorded": False,
                    "trajectory_recorded": False,
                }
            )
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    candidates.sort(
        key=lambda item: (
            priority_order.get(str(item.get("promotion_priority")), 99),
            str(item.get("candidate_class")),
            str(item.get("benchmark_id")),
            str(item.get("case_id")),
        )
    )
    return candidates


def build_case_analysis_candidate_report(
    *,
    ledger: dict[str, Any],
    analysis: dict[str, Any],
    include_proposed_records: bool = False,
    proposal_limit: int | None = None,
) -> dict[str, Any]:
    candidates = find_case_analysis_candidates(ledger=ledger, analysis=analysis)
    report: dict[str, Any] = {
        "schema_version": BENCHMARK_CASE_ANALYSIS_CANDIDATE_REPORT_SCHEMA_VERSION,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "source_boundary": {
            "inputs": [
                "compact benchmark-run-ledger",
                "benchmark-case-analysis case keys",
            ],
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "trajectory_recorded": False,
            "absolute_paths_recorded": False,
        },
    }
    if include_proposed_records:
        proposed_records = [
            proposed_case_analysis_record_from_candidate(candidate)
            for candidate in candidates
        ]
        if proposal_limit is not None:
            proposed_records = proposed_records[: max(0, proposal_limit)]
        report["proposed_record_count"] = len(proposed_records)
        report["proposed_records"] = proposed_records
    return report


def render_case_analysis_candidate_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Benchmark Case-Analysis Candidates",
        "",
        "This report is derived only from compact benchmark-run ledger rows and",
        "existing case-analysis keys. It must not include raw task text, logs,",
        "trajectories, credentials, uploads, verifier tails, or local paths.",
        "",
        f"- schema_version: `{report.get('schema_version')}`",
        f"- candidate_count: `{report.get('candidate_count', 0)}`",
        "",
        "| Priority | Class | Benchmark | Case | Decision | Runs | Recommended Handling |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in report.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        lines.append(
            "| "
            f"`{candidate.get('promotion_priority', '')}` | "
            f"`{candidate.get('candidate_class', '')}` | "
            f"`{candidate.get('benchmark_id', '')}` | "
            f"`{candidate.get('case_id', '')}` | "
            f"`{candidate.get('latest_decision', '')}` | "
            f"`{candidate.get('run_count', 0)}` | "
            f"{candidate.get('recommended_handling', '')} |"
        )
    proposed_records = report.get("proposed_records")
    if isinstance(proposed_records, list):
        lines.extend(
            [
                "",
                "## Proposed Case-Analysis Records",
                "",
                "These records are proposal-only. They are safe to review, but the",
                "case-analysis file should not be edited until the proposed",
                "classification and handling are accepted.",
                "",
                "| Priority | Benchmark | Case | Classification | Source Runs |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for record in proposed_records:
            if not isinstance(record, dict):
                continue
            lines.append(
                "| "
                f"`{record.get('promotion_priority', '')}` | "
                f"`{record.get('benchmark_id', '')}` | "
                f"`{record.get('case_id', '')}` | "
                f"`{record.get('classification', '')}` | "
                f"`{record.get('source_run_count', 0)}` |"
            )
    return "\n".join(lines) + "\n"
