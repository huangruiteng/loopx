from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any


LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION = "auto_research_lightweight_result_v0"
LIGHTWEIGHT_AUTO_RESEARCH_HYPOTHESIS_SCHEMA_VERSION = "auto_research_lightweight_hypothesis_v0"
LIGHTWEIGHT_AUTO_RESEARCH_EVIDENCE_SCHEMA_VERSION = "auto_research_lightweight_evidence_v0"

MetricEvaluator = Callable[[dict[str, Any], str], Mapping[str, Any]]


def _token(value: object, *, default: str = "unknown") -> str:
    text = str(value or "").strip()
    return text or default


def _number(value: object, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"metric value is not numeric: {value!r}") from exc
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"metric value is not finite: {value!r}")
    return number


def _improved(value: float | None, baseline: float, *, direction: str) -> bool:
    if value is None:
        return False
    if direction == "minimize":
        return value < baseline
    if direction != "maximize":
        raise ValueError("direction must be maximize or minimize")
    return value > baseline


def lightweight_hypothesis(
    *,
    hypothesis_id: str,
    todo_id: str,
    claimed_by: str,
    text: str,
    candidate_key: str,
) -> dict[str, Any]:
    return {
        "schema_version": LIGHTWEIGHT_AUTO_RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
        "hypothesis_id": _token(hypothesis_id, default="hypothesis"),
        "todo_id": _token(todo_id, default="todo"),
        "claimed_by": _token(claimed_by, default="agent"),
        "hypothesis": _token(text, default="untitled hypothesis"),
        "candidate_key": _token(candidate_key, default="candidate"),
    }


def _evidence_event(
    *,
    hypothesis: dict[str, Any],
    split: str,
    result: Mapping[str, Any],
    baseline: float,
    direction: str,
) -> dict[str, Any]:
    metric = _number(result.get("metric"))
    exact = bool(result.get("exact", True))
    clean = bool(result.get("protected_scope_clean", True))
    status = "improved" if exact and clean and _improved(metric, baseline, direction=direction) else "not_improved"
    return {
        "schema_version": LIGHTWEIGHT_AUTO_RESEARCH_EVIDENCE_SCHEMA_VERSION,
        "hypothesis_id": hypothesis["hypothesis_id"],
        "todo_id": hypothesis["todo_id"],
        "claimed_by": hypothesis["claimed_by"],
        "candidate_key": hypothesis["candidate_key"],
        "split": _token(split, default="dev"),
        "metric": metric,
        "baseline": baseline,
        "direction": direction,
        "exact": exact,
        "protected_scope_clean": clean,
        "status": status,
        "result_source": _token(result.get("result_source"), default="metric_evaluator"),
        "strategy": _token(result.get("strategy"), default=hypothesis["candidate_key"]),
        "artifact_refs": [
            _token(item, default="artifact")
            for item in result.get("artifact_refs", [])
            if str(item).strip()
        ][:8],
    }


def _rank_key(event: dict[str, Any]) -> float:
    value = event["metric"]
    return float("-inf") if value is None else float(value)


def _best_positive(
    evidence: list[dict[str, Any]],
    *,
    direction: str,
) -> dict[str, Any] | None:
    positives = [event for event in evidence if event["status"] == "improved"]
    if not positives:
        return None
    if direction == "minimize":
        return min(positives, key=_rank_key)
    return max(positives, key=_rank_key)


def run_lightweight_auto_research(
    *,
    goal_id: str,
    hypotheses: Iterable[dict[str, Any]],
    evaluate: MetricEvaluator,
    baseline: float = 1.0,
    direction: str = "maximize",
    dev_split: str = "dev",
    holdout_split: str = "holdout",
    max_dev_rounds: int | None = None,
) -> dict[str, Any]:
    """Run a small auto-research loop: dev attempts, best candidate, holdout.

    This kernel deliberately avoids board, frontier, launcher, and artifact
    projection concerns. Those layers can wrap the result without growing the
    research decision core.
    """

    base = _number(baseline)
    if base is None:
        raise ValueError("baseline is required")
    if direction not in {"maximize", "minimize"}:
        raise ValueError("direction must be maximize or minimize")
    items = list(hypotheses)
    if not items:
        raise ValueError("at least one hypothesis is required")
    limit = len(items) if max_dev_rounds is None else max(0, min(max_dev_rounds, len(items)))

    evidence: list[dict[str, Any]] = []
    by_id = {item["hypothesis_id"]: item for item in items}
    for hypothesis in items[:limit]:
        event = _evidence_event(
            hypothesis=hypothesis,
            split=dev_split,
            result=evaluate(hypothesis, dev_split),
            baseline=base,
            direction=direction,
        )
        evidence.append(event)

    best_dev = _best_positive(evidence, direction=direction)
    selected = by_id.get(best_dev["hypothesis_id"]) if best_dev else None
    holdout_event = None
    if selected is not None:
        holdout_event = _evidence_event(
            hypothesis=selected,
            split=holdout_split,
            result=evaluate(selected, holdout_split),
            baseline=base,
            direction=direction,
        )
        evidence.append(holdout_event)

    holdout_positive = bool(holdout_event and holdout_event["status"] == "improved")
    dev_positive = best_dev is not None
    decision = (
        "validated_positive"
        if holdout_positive
        else "dev_supported"
        if dev_positive
        else "continue_research"
    )
    return {
        "ok": True,
        "schema_version": LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION,
        "goal_id": _token(goal_id, default="auto-research"),
        "candidate_count": len(items),
        "dev_round_count": limit,
        "evidence_event_count": len(evidence),
        "selected_hypothesis_id": selected["hypothesis_id"] if selected else None,
        "decision": decision,
        "dev_metric": best_dev["metric"] if best_dev else None,
        "holdout_metric": holdout_event["metric"] if holdout_event else None,
        "evidence": evidence,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "raw_source_bodies_recorded": False,
        },
    }
