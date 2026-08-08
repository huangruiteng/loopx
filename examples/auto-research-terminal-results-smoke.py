#!/usr/bin/env python3
"""Exercise evidence-bound Auto Research terminal results and reviews."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.evidence_packet import (  # noqa: E402
    RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
    RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
)
from loopx.capabilities.auto_research.research_state import (  # noqa: E402
    build_research_evidence_graph_from_records,
)
from loopx.capabilities.auto_research.terminal_results import (  # noqa: E402
    build_peer_review_event,
    build_terminal_decision_event,
    build_terminal_result_explore_events,
    build_terminal_result_query,
)
from loopx.capabilities.explore.result_log import (  # noqa: E402
    build_explore_result_projection,
)
GOAL_ID = "terminal-result-fixture"
BASELINE = 0.0
PRODUCER = "research-executor"
PROMOTER = "evaluator-promoter"
REVIEWER = "independent-reviewer"
REGISTERED_AGENTS = [
    PRODUCER,
    PROMOTER,
    REVIEWER,
    "second-independent-reviewer",
]


def hypothesis(
    hypothesis_id: str,
    *,
    text: str,
    status: str,
    parent: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
        "hypothesis_id": hypothesis_id,
        "parent_hypothesis_id": parent,
        "todo_id": f"todo_{hypothesis_id}",
        "claimed_by": PRODUCER,
        "mechanism_family": "finance_style_claim",
        "hypothesis": text,
        "status": status,
        "grounding_refs": [],
        "novelty_audit_ref": None,
        "blocked_by": (
            ["evidence_or_boundary_guardrail_failed"]
            if status == "contradicted"
            else []
        ),
    }


def evidence(
    hypothesis_id: str,
    *,
    split: str,
    value: float,
    metric_status: str,
    attempt: int = 1,
) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_EVIDENCE_EVENT_SCHEMA_VERSION,
        "hypothesis_id": hypothesis_id,
        "todo_id": f"todo_{hypothesis_id}",
        "agent_id": PRODUCER,
        "attempt": attempt,
        "split": split,
        "metric": {
            "name": "research_quality",
            "value": value,
            "direction": "maximize",
        },
        "baseline_metric": BASELINE,
        "eval_status": "scored",
        "primary_metric_status": metric_status,
        "artifact_refs": [f"evidence:{hypothesis_id}:{split}:{attempt}"],
        "protected_scope_clean": True,
        "raw_logs_recorded": False,
        "private_artifacts_recorded": False,
    }


def fixture_graph() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    hypotheses = [
        hypothesis(
            "value_case",
            text="The candidate satisfies the preregistered company-value gate.",
            status="supported",
        ),
        hypothesis(
            "persistent_alpha",
            text="The candidate has persistent benchmark-adjusted alpha.",
            status="contradicted",
        ),
        hypothesis(
            "single_window_alpha",
            text="One frozen window contains positive benchmark-adjusted alpha.",
            status="supported",
        ),
        hypothesis(
            "walk_forward_alpha",
            text="The single-window alpha persists across rolling held-out windows.",
            status="contradicted",
            parent="single_window_alpha",
        ),
        hypothesis(
            "duplicate_route",
            text="A duplicate route should retire without becoming a refuted finding.",
            status="active",
        ),
    ]
    evidence_events = [
        evidence("value_case", split="dev", value=0.6, metric_status="improved"),
        evidence(
            "value_case",
            split="holdout",
            value=0.4,
            metric_status="improved",
        ),
        evidence(
            "persistent_alpha",
            split="holdout",
            value=-0.5,
            metric_status="regressed",
        ),
        evidence(
            "single_window_alpha",
            split="dev",
            value=0.7,
            metric_status="improved",
        ),
        evidence(
            "walk_forward_alpha",
            split="holdout",
            value=-0.2,
            metric_status="regressed",
        ),
    ]
    graph = build_research_evidence_graph_from_records(
        goal_id=GOAL_ID,
        hypotheses=hypotheses,
        evidence_events=evidence_events,
        metric_name="research_quality",
        metric_direction="maximize",
        baseline_metric=BASELINE,
    )
    return graph, hypotheses, evidence_events


def terminal_events(graph: dict[str, Any]) -> list[dict[str, Any]]:
    value = build_terminal_decision_event(
        evidence_graph=graph,
        hypothesis_id="value_case",
        outcome="promoted",
        reason="holdout_validated",
        decided_by=PROMOTER,
        evidence_refs=["decision:value_case"],
        recorded_at="2026-08-08T00:00:00Z",
    )
    persistent = build_terminal_decision_event(
        evidence_graph=graph,
        hypothesis_id="persistent_alpha",
        outcome="retired",
        reason="contradicted",
        decided_by=PROMOTER,
        evidence_refs=["decision:persistent_alpha"],
        recorded_at="2026-08-08T00:00:01Z",
    )
    rolling = build_terminal_decision_event(
        evidence_graph=graph,
        hypothesis_id="walk_forward_alpha",
        outcome="retired",
        reason="contradicted",
        decided_by=PROMOTER,
        evidence_refs=["decision:walk_forward_alpha"],
        recorded_at="2026-08-08T00:00:02Z",
    )
    duplicate = build_terminal_decision_event(
        evidence_graph=graph,
        hypothesis_id="duplicate_route",
        outcome="retired",
        reason="duplicate",
        decided_by=PROMOTER,
        evidence_refs=["decision:duplicate_route"],
        recorded_at="2026-08-08T00:00:03Z",
    )
    return [value, persistent, rolling, duplicate]


def reviews(
    graph: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    self_review = build_peer_review_event(
        evidence_graph=graph,
        rollout_events=decisions,
        hypothesis_id="value_case",
        reviewer_agent_id=PROMOTER,
        verdict="approve",
        evidence_refs=["review:self"],
        registered_agent_ids=REGISTERED_AGENTS,
        recorded_at="2026-08-08T00:01:00Z",
    )
    independent = [
        build_peer_review_event(
            evidence_graph=graph,
            rollout_events=decisions,
            hypothesis_id=hypothesis_id,
            reviewer_agent_id=REVIEWER,
            verdict="approve",
            evidence_refs=[f"review:{hypothesis_id}"],
            require_independent=True,
            registered_agent_ids=REGISTERED_AGENTS,
            recorded_at=f"2026-08-08T00:01:0{index}Z",
        )
        for index, hypothesis_id in enumerate(
            ["value_case", "persistent_alpha", "walk_forward_alpha"],
            start=1,
        )
    ]
    try:
        build_peer_review_event(
            evidence_graph=graph,
            rollout_events=decisions,
            hypothesis_id="value_case",
            reviewer_agent_id=PROMOTER,
            verdict="approve",
            require_independent=True,
            registered_agent_ids=REGISTERED_AGENTS,
        )
    except ValueError as exc:
        assert "distinct" in str(exc), exc
    else:
        raise AssertionError("same-agent independent review must fail")
    try:
        build_peer_review_event(
            evidence_graph=graph,
            rollout_events=decisions,
            hypothesis_id="value_case",
            reviewer_agent_id="unregistered-reviewer",
            verdict="approve",
            registered_agent_ids=REGISTERED_AGENTS,
        )
    except ValueError as exc:
        assert "not registered" in str(exc), exc
    else:
        raise AssertionError("unregistered peer review must fail")
    return [self_review, *independent]


def assert_query_semantics(
    graph: dict[str, Any],
    decisions: list[dict[str, Any]],
    review_events: list[dict[str, Any]],
) -> dict[str, Any]:
    query = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, *review_events],
        registered_agent_ids=REGISTERED_AGENTS,
        include_history=True,
    )
    by_id = {item["hypothesis_id"]: item for item in query["results"]}
    assert by_id["value_case"]["finding_status"] == "confirmed", by_id
    assert by_id["persistent_alpha"]["finding_status"] == "refuted", by_id
    assert by_id["single_window_alpha"]["finding_status"] == "tentative", by_id
    assert by_id["walk_forward_alpha"]["finding_status"] == "refuted", by_id
    assert by_id["duplicate_route"]["finding_status"] is None, by_id
    assert by_id["value_case"]["peer_review"]["independent"] is True, by_id
    assert by_id["value_case"]["terminal_decision"]["outcome"] == "promoted", by_id

    self_review_only = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, review_events[0]],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert self_review_only["finding_status"] == "tentative", self_review_only
    assert self_review_only["peer_review"]["state"] == "self_review_only", self_review_only
    forged_self_review = {
        **review_events[0],
        "details": {
            **review_events[0]["details"],
            "independent": True,
        },
    }
    forged = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, forged_self_review],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert forged["peer_review"]["state"] == "self_review_only", forged
    assert forged["finding_status"] == "tentative", forged

    downgraded_independence_claim = {
        **review_events[1],
        "details": {
            **review_events[1]["details"],
            "independent": False,
        },
    }
    downgraded = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, downgraded_independence_claim],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert downgraded["peer_review"]["state"] == "self_review_only", downgraded
    assert downgraded["finding_status"] == "tentative", downgraded

    removed_reviewer = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, *review_events],
        registered_agent_ids=[PRODUCER, PROMOTER],
        hypothesis_id="value_case",
    )["results"][0]
    assert removed_reviewer["peer_review"]["state"] == "self_review_only", removed_reviewer
    assert removed_reviewer["finding_status"] == "tentative", removed_reviewer

    conflict = build_terminal_decision_event(
        evidence_graph=graph,
        hypothesis_id="value_case",
        outcome="retired",
        reason="duplicate",
        decided_by="alternate-promoter",
        recorded_at="2026-08-08T00:02:00Z",
    )
    conflicted = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, conflict, *review_events],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert conflicted["decision_state"] == "conflict", conflicted
    assert conflicted["finding_status"] == "tentative", conflicted

    review_reject = build_peer_review_event(
        evidence_graph=graph,
        rollout_events=decisions,
        hypothesis_id="value_case",
        reviewer_agent_id="second-independent-reviewer",
        verdict="reject",
        require_independent=True,
        registered_agent_ids=REGISTERED_AGENTS,
        recorded_at="2026-08-08T00:03:00Z",
    )
    review_conflict = build_terminal_result_query(
        evidence_graph=graph,
        rollout_events=[*decisions, *review_events, review_reject],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert review_conflict["peer_review"]["state"] == "conflict", review_conflict
    assert review_conflict["finding_status"] == "tentative", review_conflict

    stale_graph = build_research_evidence_graph_from_records(
        goal_id=GOAL_ID,
        hypotheses=[
            hypothesis(
                "value_case",
                text="The candidate satisfies the preregistered company-value gate.",
                status="supported",
            )
        ],
        evidence_events=[
            evidence("value_case", split="dev", value=0.6, metric_status="improved"),
            evidence(
                "value_case",
                split="holdout",
                value=0.4,
                metric_status="improved",
            ),
            evidence(
                "value_case",
                split="holdout",
                value=0.45,
                metric_status="improved",
                attempt=2,
            ),
        ],
        metric_name="research_quality",
        metric_direction="maximize",
        baseline_metric=BASELINE,
    )
    stale = build_terminal_result_query(
        evidence_graph=stale_graph,
        rollout_events=[*decisions, *review_events],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert stale["decision_state"] == "stale", stale
    assert stale["finding_status"] == "tentative", stale

    revised_decision = build_terminal_decision_event(
        evidence_graph=stale_graph,
        hypothesis_id="value_case",
        outcome="retired",
        reason="duplicate",
        decided_by=PROMOTER,
        recorded_at="2026-08-08T00:04:00Z",
    )
    assert (
        revised_decision["causality"]["decision_id"]
        != decisions[0]["causality"]["decision_id"]
    )
    assert (
        revised_decision["details"]["hypothesis_evidence_revision"]
        != decisions[0]["details"]["hypothesis_evidence_revision"]
    )
    revised = build_terminal_result_query(
        evidence_graph=stale_graph,
        rollout_events=[*decisions, revised_decision, *review_events],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
        include_history=True,
    )["results"][0]
    assert revised["decision_state"] == "current", revised
    assert revised["terminal_decision"]["outcome"] == "retired", revised
    assert len(revised["decision_history"]) == 2, revised
    assert revised["finding_status"] == "tentative", revised

    unrelated_hypothesis = hypothesis(
        "unrelated_route",
        text="An unrelated hypothesis should not stale another terminal decision.",
        status="active",
    )
    unrelated_graph = build_research_evidence_graph_from_records(
        goal_id=GOAL_ID,
        hypotheses=[
            *fixture_graph()[1],
            unrelated_hypothesis,
        ],
        evidence_events=fixture_graph()[2],
        metric_name="research_quality",
        metric_direction="maximize",
        baseline_metric=BASELINE,
    )
    still_current = build_terminal_result_query(
        evidence_graph=unrelated_graph,
        rollout_events=[*decisions, *review_events],
        registered_agent_ids=REGISTERED_AGENTS,
        hypothesis_id="value_case",
    )["results"][0]
    assert still_current["decision_state"] == "current", still_current
    assert still_current["finding_status"] == "confirmed", still_current
    return query


def assert_projection(query: dict[str, Any]) -> None:
    events = build_terminal_result_explore_events(query=query)
    repeated = build_terminal_result_explore_events(query=query)
    assert events == repeated
    assert [event["event_id"] for event in events] == [
        event["event_id"] for event in repeated
    ]
    projection = build_explore_result_projection(events, goal_id=GOAL_ID)
    findings = {
        item["finding"]: item["status"] for item in projection["findings"]
    }
    assert findings == {
        "The candidate satisfies the preregistered company-value gate.": "confirmed",
        "The candidate has persistent benchmark-adjusted alpha.": "refuted",
        "One frozen window contains positive benchmark-adjusted alpha.": "tentative",
        "The single-window alpha persists across rolling held-out windows.": "refuted",
    }, findings
    edges = [edge for edge in projection["edges"] if edge["edge_type"] == "leads_to"]
    assert len(edges) == 1, edges
    assert projection["counts"]["finding_count"] == 4, projection


def main() -> int:
    graph, _, _ = fixture_graph()
    decisions = terminal_events(graph)
    review_events = reviews(graph, decisions)
    query = assert_query_semantics(graph, decisions, review_events)
    assert_projection(query)
    print("auto-research-terminal-results-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
