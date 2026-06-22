from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BENCHMARK_CASE_ANALYSIS_CANDIDATE_REPORT_SCHEMA_VERSION = (
    "benchmark_case_analysis_candidate_report_v0"
)
BENCHMARK_CASE_ANALYSIS_UPSERT_PROPOSAL_SCHEMA_VERSION = (
    "benchmark_case_analysis_upsert_proposal_v0"
)
BENCHMARK_CASE_ANALYSIS_ACCEPTANCE_POLICY_SCHEMA_VERSION = (
    "benchmark_case_analysis_acceptance_policy_v0"
)

NO_RUN_DECISIONS = {"", "no_runs_recorded"}
CASE_ANALYSIS_ACCEPTANCE_POLICIES = {"proposal-only", "generated-safe"}
GENERATED_SAFE_ACCEPTED_CLASSES = {
    "paired_no_uplift_candidate": "generated_no_uplift_asset",
    "baseline_solved_non_regression_candidate": (
        "generated_baseline_solved_non_regression_asset"
    ),
    "baseline_solved_control_candidate": "generated_baseline_solved_control_asset",
}
CASE_ANALYSIS_DETAIL_START_HEADING = "## Treatment Policy Control Set"
CASE_ANALYSIS_CLASS_LABELS = {
    "baseline_solved_non_regression_asset": (
        "current-protocol baseline-solved / non-regression asset"
    ),
    "generated_baseline_solved_control_asset": (
        "generated baseline-solved control asset"
    ),
    "generated_baseline_solved_non_regression_asset": (
        "generated baseline-solved non-regression asset"
    ),
    "generated_no_uplift_asset": "generated no-uplift asset",
    "no_uplift_asset": "no-uplift asset",
    "positive_uplift_asset": "positive uplift asset",
    "regression_asset": "regression asset",
    "setup_blocker_asset": "setup blocker asset",
}


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
    if isinstance(cases, list):
        for case in cases:
            if not isinstance(case, dict):
                continue
            benchmark_id = _compact_text(case.get("benchmark_id"), limit=160)
            case_id = _compact_text(case.get("case_id"), limit=200)
            if benchmark_id and case_id:
                keys.add((benchmark_id, case_id))
    coverage = analysis.get("terminal_bench_current_protocol_coverage")
    if isinstance(coverage, dict) and isinstance(coverage.get("rows"), list):
        for row in coverage["rows"]:
            if not isinstance(row, dict):
                continue
            case_id = _compact_text(row.get("case_id"), limit=200)
            if case_id:
                keys.add(("terminal-bench@2.0", case_id))
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


def _normalize_acceptance_policy(acceptance_policy: str | None) -> str:
    policy = _compact_text(acceptance_policy or "proposal-only", limit=80)
    if policy not in CASE_ANALYSIS_ACCEPTANCE_POLICIES:
        allowed = ", ".join(sorted(CASE_ANALYSIS_ACCEPTANCE_POLICIES))
        raise ValueError(
            f"unsupported case-analysis acceptance policy {policy!r}; "
            f"expected one of: {allowed}"
        )
    return policy


def evaluate_case_analysis_acceptance(
    candidate: dict[str, Any],
    *,
    acceptance_policy: str = "proposal-only",
) -> dict[str, Any]:
    policy = _normalize_acceptance_policy(acceptance_policy)
    candidate_class = _compact_text(candidate.get("candidate_class"), limit=160)
    latest_decision = _compact_text(candidate.get("latest_decision"), limit=160)
    run_count = int(candidate.get("run_count") or 0)
    accepted_classification = GENERATED_SAFE_ACCEPTED_CLASSES.get(candidate_class)
    reason_codes: list[str] = []
    if policy == "proposal-only":
        return {
            "schema_version": BENCHMARK_CASE_ANALYSIS_ACCEPTANCE_POLICY_SCHEMA_VERSION,
            "policy": policy,
            "accepted": False,
            "status": "proposal_only_not_applied",
            "accepted_classification": None,
            "requires_manual_review": True,
            "reason_codes": ["proposal_only_policy"],
        }
    if not accepted_classification:
        reason_codes.append("candidate_class_requires_manual_review")
    if candidate_class == "paired_no_uplift_candidate":
        if latest_decision != "paired_no_score_uplift":
            reason_codes.append("decision_not_paired_no_score_uplift")
        if run_count < 2:
            reason_codes.append("paired_candidate_needs_two_runs")
    elif candidate_class == "baseline_solved_non_regression_candidate":
        if latest_decision != "paired_baseline_solved_treatment_preserved":
            reason_codes.append("decision_not_baseline_solved_treatment_preserved")
        if run_count < 2:
            reason_codes.append("paired_candidate_needs_two_runs")
    elif candidate_class == "baseline_solved_control_candidate":
        if latest_decision != "baseline_passed_not_current_treatment_priority":
            reason_codes.append("decision_not_baseline_passed_control")
        if run_count < 1:
            reason_codes.append("control_candidate_needs_one_run")
    accepted = bool(accepted_classification) and not reason_codes
    return {
        "schema_version": BENCHMARK_CASE_ANALYSIS_ACCEPTANCE_POLICY_SCHEMA_VERSION,
        "policy": policy,
        "accepted": accepted,
        "status": (
            "accepted_generated_not_applied"
            if accepted
            else "proposal_only_not_applied"
        ),
        "accepted_classification": accepted_classification if accepted else None,
        "requires_manual_review": not accepted,
        "reason_codes": reason_codes or ["generated_safe_policy_matched"],
    }


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
    *,
    acceptance_policy: str = "proposal-only",
) -> dict[str, Any]:
    benchmark_id = _compact_text(candidate.get("benchmark_id"), limit=160)
    case_id = _compact_text(candidate.get("case_id"), limit=200)
    candidate_class = _compact_text(candidate.get("candidate_class"), limit=160)
    recent_run_ids = [
        _compact_text(run_id, limit=120)
        for run_id in candidate.get("recent_run_ids", [])
        if run_id
    ]
    acceptance = evaluate_case_analysis_acceptance(
        candidate,
        acceptance_policy=acceptance_policy,
    )
    accepted = bool(acceptance.get("accepted"))
    record = {
        "schema_version": BENCHMARK_CASE_ANALYSIS_UPSERT_PROPOSAL_SCHEMA_VERSION,
        "proposal_status": _compact_text(acceptance.get("status"), limit=80),
        "analysis_id": _case_analysis_id(benchmark_id, case_id, candidate_class),
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "classification": (
            _compact_text(acceptance.get("accepted_classification"), limit=160)
            if accepted
            else _proposal_classification(candidate_class)
        ),
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
        "acceptance_policy": acceptance,
        "source_boundary": {
            "inputs": [
                "compact benchmark-run-ledger candidate",
                "benchmark-case-analysis existing keys",
            ],
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "trajectory_recorded": False,
            "absolute_paths_recorded": False,
            "proposal_only": not accepted,
            "accepted_generated_case_analysis": accepted,
        },
    }
    return record


def build_case_analysis_upsert_proposals(
    *,
    ledger: dict[str, Any],
    analysis: dict[str, Any],
    limit: int | None = None,
    acceptance_policy: str = "proposal-only",
) -> list[dict[str, Any]]:
    policy = _normalize_acceptance_policy(acceptance_policy)
    candidates = find_case_analysis_candidates(ledger=ledger, analysis=analysis)
    proposals = [
        proposed_case_analysis_record_from_candidate(
            candidate,
            acceptance_policy=policy,
        )
        for candidate in candidates
    ]
    if limit is not None:
        return proposals[: max(0, limit)]
    return proposals


def case_analysis_record_from_accepted_upsert(
    record: dict[str, Any],
) -> dict[str, Any]:
    if record.get("proposal_status") != "accepted_generated_not_applied":
        raise ValueError("only accepted_generated_not_applied records can be applied")
    boundary = (
        record.get("source_boundary")
        if isinstance(record.get("source_boundary"), dict)
        else {}
    )
    return {
        "analysis_id": _compact_text(record.get("analysis_id"), limit=260),
        "benchmark_id": _compact_text(record.get("benchmark_id"), limit=160),
        "case_id": _compact_text(record.get("case_id"), limit=200),
        "classification": _compact_text(record.get("classification"), limit=160),
        "decision": _compact_text(record.get("latest_ledger_decision"), limit=160),
        "evidence_status": "generated_from_compact_benchmark_run_ledger",
        "source_run_ids": [
            _compact_text(run_id, limit=120)
            for run_id in record.get("source_run_ids", [])
            if run_id
        ],
        "source_run_count": int(record.get("source_run_count") or 0),
        "capability_signal": _compact_text(
            record.get("capability_signal"),
            limit=320,
        ),
        "control_plane_signal": _compact_text(
            record.get("control_plane_signal"),
            limit=320,
        ),
        "routing_guidance": {
            "repeat_policy": _compact_text(
                record.get("recommended_next_action"),
                limit=260,
            )
        },
        "acceptance_policy": record.get("acceptance_policy"),
        "source_boundary": {
            "inputs": [
                "compact benchmark-run-ledger candidate",
                "benchmark-case-analysis existing keys",
            ],
            "raw_logs_recorded": bool(boundary.get("raw_logs_recorded", False)),
            "raw_task_text_recorded": bool(
                boundary.get("raw_task_text_recorded", False)
            ),
            "trajectory_recorded": bool(boundary.get("trajectory_recorded", False)),
            "absolute_paths_recorded": bool(
                boundary.get("absolute_paths_recorded", False)
            ),
            "generated_case_analysis": True,
        },
    }


def apply_accepted_case_analysis_records(
    *,
    analysis: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = deepcopy(analysis)
    cases = updated.setdefault("cases", [])
    if not isinstance(cases, list):
        raise ValueError("case-analysis payload must contain a cases list")
    existing = case_analysis_keys(updated)
    added_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        key = (
            _compact_text(record.get("benchmark_id"), limit=160),
            _compact_text(record.get("case_id"), limit=200),
        )
        if record.get("proposal_status") != "accepted_generated_not_applied":
            skipped_records.append(
                {
                    "benchmark_id": key[0],
                    "case_id": key[1],
                    "reason": "not_accepted_by_policy",
                }
            )
            continue
        if not key[0] or not key[1] or key in existing:
            skipped_records.append(
                {
                    "benchmark_id": key[0],
                    "case_id": key[1],
                    "reason": "already_present_or_invalid_key",
                }
            )
            continue
        case_record = case_analysis_record_from_accepted_upsert(record)
        cases.append(case_record)
        existing.add(key)
        added_records.append(case_record)
    return {
        "analysis": updated,
        "added_count": len(added_records),
        "skipped_count": len(skipped_records),
        "added_records": added_records,
        "skipped_records": skipped_records,
    }


def _case_analysis_class_label(case: dict[str, Any]) -> str:
    classification = _compact_text(case.get("classification"), limit=180)
    if not classification:
        return "case-analysis asset"
    if classification in CASE_ANALYSIS_CLASS_LABELS:
        return CASE_ANALYSIS_CLASS_LABELS[classification]
    return classification.replace("_", " ")


def _case_analysis_score_triplet(case: dict[str, Any]) -> tuple[object, object, object]:
    scores = case.get("scores") if isinstance(case.get("scores"), dict) else {}
    baseline = scores.get("baseline_official_score")
    treatment = scores.get("treatment_official_score")
    delta = scores.get("official_score_delta")
    decision = _compact_text(case.get("decision"), limit=180)
    classification = _compact_text(case.get("classification"), limit=180)
    if baseline is None and treatment is None and delta is None:
        if decision == "paired_no_score_uplift":
            return 0.0, 0.0, 0.0
        if decision == "baseline_passed_not_current_treatment_priority":
            return 1.0, None, None
        if "setup" in classification or "runner" in decision:
            return "missing", None, None
    return baseline, treatment, delta


def _markdown_table_value(value: object) -> str:
    if value is None or value == "":
        return "n/a"
    text = _compact_text(value, limit=120)
    return f"`{text}`"


def _markdown_escape_cell(value: object) -> str:
    return _compact_text(value, limit=240).replace("|", "\\|")


def _render_case_analysis_summary_table(analysis: dict[str, Any]) -> list[str]:
    lines = [
        "| Benchmark | Case | Class | Baseline | Treatment | Delta | Decision |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    cases = analysis.get("cases")
    if not isinstance(cases, list):
        return lines
    for case in cases:
        if not isinstance(case, dict):
            continue
        baseline, treatment, delta = _case_analysis_score_triplet(case)
        lines.append(
            "| "
            f"`{_markdown_escape_cell(case.get('benchmark_id'))}` | "
            f"`{_markdown_escape_cell(case.get('case_id'))}` | "
            f"{_markdown_escape_cell(_case_analysis_class_label(case))} | "
            f"{_markdown_table_value(baseline)} | "
            f"{_markdown_table_value(treatment)} | "
            f"{_markdown_table_value(delta)} | "
            f"`{_markdown_escape_cell(case.get('decision'))}` |"
        )
    return lines


def _render_terminal_bench_current_protocol_coverage(
    analysis: dict[str, Any],
) -> list[str]:
    coverage = analysis.get("terminal_bench_current_protocol_coverage")
    if not isinstance(coverage, dict):
        return []
    rows = coverage.get("rows")
    if not isinstance(rows, list):
        return []
    lines = [
        "## Terminal-Bench Current-Protocol Coverage",
        "",
        "These rows are generated from the latest compact ledger decisions. They are",
        "current-protocol success-preservation guards: both baseline and treatment",
        "score `1.0`, so none of them should be counted as current uplift.",
        "",
        "| Case | Baseline | Treatment | Delta | Role | Case Analysis Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        baseline = row.get("baseline_official_score")
        treatment = row.get("treatment_official_score")
        delta = row.get("official_score_delta")
        baseline_run = _compact_text(row.get("baseline_run_id"), limit=40)
        treatment_run = _compact_text(row.get("treatment_run_id"), limit=40)
        lines.append(
            "| "
            f"`{_markdown_escape_cell(row.get('case_id'))}` | "
            f"`{baseline}` (`{baseline_run}`) | "
            f"`{treatment}` (`{treatment_run}`) | "
            f"`{delta}` | "
            f"`{_markdown_escape_cell(row.get('main_table_role'))}` | "
            f"`{_markdown_escape_cell(row.get('case_analysis_status'))}` |"
        )
    return lines


def _preserved_case_analysis_detail(existing_markdown: str | None) -> str:
    if not existing_markdown:
        return (
            "## Boundary\n\n"
            "This file records only compact public-safe evidence. It does not copy "
            "raw logs, task prompts, trajectories, credentials, hidden tests, "
            "uploads, or absolute local paths.\n"
        )
    marker = f"\n{CASE_ANALYSIS_DETAIL_START_HEADING}"
    start = existing_markdown.find(marker)
    if start >= 0:
        return existing_markdown[start + 1 :].strip() + "\n"
    if existing_markdown.startswith(CASE_ANALYSIS_DETAIL_START_HEADING):
        return existing_markdown.strip() + "\n"
    return (
        "## Boundary\n\n"
        "This file records only compact public-safe evidence. It does not copy "
        "raw logs, task prompts, trajectories, credentials, hidden tests, "
        "uploads, or absolute local paths.\n"
    )


def render_case_analysis_markdown(
    analysis: dict[str, Any],
    *,
    existing_markdown: str | None = None,
) -> str:
    """Render the generated case-analysis summary while preserving deep notes."""
    cases = analysis.get("cases")
    case_count = len(cases) if isinstance(cases, list) else 0
    generated_count = (
        sum(
            1
            for case in cases
            if isinstance(case, dict)
            and _compact_text(case.get("classification"), limit=180).startswith(
                "generated_"
            )
        )
        if isinstance(cases, list)
        else 0
    )
    lines = [
        "# Benchmark Case Analysis",
        "",
        "This file is the human view of `benchmark_case_analysis_v0`. It records durable",
        "case lessons that should guide benchmark routing, treatment design, and claims.",
        "",
        "It is intentionally separate from `benchmark-run-ledger.md`. The run ledger",
        "records compact attempts and scores; this file records why a result matters.",
        "",
        f"- schema_version: `{analysis.get('schema_version')}`",
        f"- updated_at: `{analysis.get('updated_at')}`",
        "- machine_source: `benchmark-case-analysis.json`",
        "- ledger-only migration audit:",
        "  `benchmark-case-analysis-ledger-only-migration-audit-20260618.md`",
        "",
        "## Summary",
        "",
        "The table below is generated from compact public case-analysis JSON. It uses",
        "`n/a` when the compact record does not establish a comparable paired arm,",
        "and it preserves detailed hand-authored case notes below the generated",
        "summary sections.",
        "",
        f"- case_count: `{case_count}`",
        f"- generated_compact_record_count: `{generated_count}`",
        "",
    ]
    lines.extend(_render_case_analysis_summary_table(analysis))
    coverage_lines = _render_terminal_bench_current_protocol_coverage(analysis)
    if coverage_lines:
        lines.extend(["", *coverage_lines])
    detail = _preserved_case_analysis_detail(existing_markdown)
    lines.extend(["", detail.strip()])
    return "\n".join(lines).rstrip() + "\n"


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
    acceptance_policy: str = "proposal-only",
) -> dict[str, Any]:
    policy = _normalize_acceptance_policy(acceptance_policy)
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
            proposed_case_analysis_record_from_candidate(
                candidate,
                acceptance_policy=policy,
            )
            for candidate in candidates
        ]
        if proposal_limit is not None:
            proposed_records = proposed_records[: max(0, proposal_limit)]
        accepted_count = sum(
            1
            for record in proposed_records
            if isinstance(record, dict)
            and record.get("proposal_status") == "accepted_generated_not_applied"
        )
        report["acceptance_policy"] = {
            "schema_version": BENCHMARK_CASE_ANALYSIS_ACCEPTANCE_POLICY_SCHEMA_VERSION,
            "policy": policy,
            "accepted_record_count": accepted_count,
            "manual_review_record_count": len(proposed_records) - accepted_count,
        }
        report["proposed_record_count"] = len(proposed_records)
        report["accepted_record_count"] = accepted_count
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
        acceptance_policy = report.get("acceptance_policy")
        lines.extend(
            [
                "",
                "## Proposed Case-Analysis Records",
                "",
                "These records are proposal-only. They are safe to review, but the",
                "case-analysis file should not be edited until the proposed",
                "classification and handling are accepted.",
                "",
                "| Priority | Benchmark | Case | Classification | Status | Source Runs |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        if isinstance(acceptance_policy, dict):
            lines.extend(
                [
                    "",
                    "- acceptance_policy: "
                    f"`{acceptance_policy.get('policy')}`",
                    "- accepted_record_count: "
                    f"`{acceptance_policy.get('accepted_record_count', 0)}`",
                    "",
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
                f"`{record.get('proposal_status', '')}` | "
                f"`{record.get('source_run_count', 0)}` |"
            )
    return "\n".join(lines) + "\n"
