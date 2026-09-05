from __future__ import annotations

import json
from pathlib import Path

from loopx.capabilities.periodic_report.pending_intent import (
    consume_pending_periodic_report_intent,
    pending_periodic_report_intents,
)
from settlement_capability_dispatch_fixture import (
    AGENT_ID,
    COMPLETED_TODO,
    GATED_TODO,
    GOAL_ID,
    PLAIN_TODO,
    complete_todo_via_cli,
)


def _write_unclaimed_frontier_state(project: Path) -> None:
    """State whose progress snapshot has no agent-claimed items yet.

    The unclaimed advancement Todo keeps the successor frontier owned, so the
    dispatch still freezes one stage receipt, while the durable progress
    snapshot stays empty and the pending intent carries capability evidence
    without a frozen project_progress projection.
    """

    project.joinpath("goal.md").write_text(
        f"""# Goal

## User Todo

## Agent Todo

- [ ] Ship the localized weekly report slice.
  <!-- loopx:todo todo_id={COMPLETED_TODO} status=open task_class=advancement_task claimed_by={AGENT_ID} continuation_policy=same_agent_non_delivery -->
- [ ] Advance the next research frontier.
  <!-- loopx:todo todo_id=todo_unclaimed_frontier status=open task_class=advancement_task -->
""",
        encoding="utf-8",
    )


def _claim_gated_successors(project: Path) -> None:
    """Evolve durable state after the dispatch, as the next Turn would."""

    project.joinpath("goal.md").write_text(
        f"""# Goal

## User Todo

## Agent Todo

- [x] Ship the localized weekly report slice.
  <!-- loopx:todo todo_id={COMPLETED_TODO} status=done task_class=advancement_task claimed_by={AGENT_ID} continuation_policy=same_agent_non_delivery updated_at=2026-08-30T10:30:00Z -->
- [ ] Re-run the outbound channel sync after network capacity returns.
  <!-- loopx:todo todo_id={GATED_TODO} status=open task_class=advancement_task claimed_by={AGENT_ID} action_kind=gated_work resume_when=capacity_available:network -->
- [ ] Outline the follow-up frontier analysis.
  <!-- loopx:todo todo_id={PLAIN_TODO} status=open task_class=advancement_task claimed_by={AGENT_ID} -->
""",
        encoding="utf-8",
    )


def _intent_sidecar(runtime: Path) -> dict[str, object]:
    sidecar_dir = runtime / "goals" / GOAL_ID / "post_writeback_hooks"
    sidecars = sorted(sidecar_dir.glob("pwh_*.json"))
    assert len(sidecars) == 1
    return json.loads(sidecars[0].read_text(encoding="utf-8"))


def _editorial_fact_sources(registry: Path, runtime: Path) -> set[str]:
    result = consume_pending_periodic_report_intent(
        registry_path=registry,
        runtime_root=runtime,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        execute=True,
    )
    assert result["status"] == "editorial_required", result
    request = json.loads(Path(result["editorial_request_path"]).read_text("utf-8"))
    return {str(fact.get("source_ref")) for fact in request["facts"]}


def test_pending_intent_fallback_uses_producer_capability_evidence(
    tmp_path: Path,
) -> None:
    captured, registry, runtime = complete_todo_via_cli(
        tmp_path,
        journal_capabilities=["network"],
        write_state=_write_unclaimed_frontier_state,
    )

    assert "available_capabilities" in captured
    intents = pending_periodic_report_intents(
        registry_path=registry,
        runtime_root=runtime,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert len(intents) == 1
    payload = intents[0]["payload"]
    assert "project_progress" not in payload
    assert payload["available_capabilities"] == ["network"]

    _claim_gated_successors(registry.parent)
    assert f"todo:{GATED_TODO}" in _editorial_fact_sources(registry, runtime)


def test_pending_intent_fallback_fails_closed_without_producer_evidence(
    tmp_path: Path,
) -> None:
    _captured, registry, runtime = complete_todo_via_cli(
        tmp_path,
        journal_capabilities=[],
        write_state=_write_unclaimed_frontier_state,
    )

    sidecar = _intent_sidecar(runtime)
    assert "project_progress" not in sidecar["intent"]["payload"]
    assert "available_capabilities" not in sidecar["intent"]["payload"]

    _claim_gated_successors(registry.parent)
    assert f"todo:{GATED_TODO}" not in _editorial_fact_sources(registry, runtime)
    assert f"todo:{PLAIN_TODO}" in _editorial_fact_sources(registry, runtime)
