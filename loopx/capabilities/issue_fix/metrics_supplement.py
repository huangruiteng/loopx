from __future__ import annotations

from datetime import datetime
from typing import Any


SUPPLEMENT_SCHEMA_VERSION = "issue_fix_metrics_supplement_v0"
EVENT_BATCH_SCHEMA_VERSION = "issue_fix_metrics_event_batch_v0"
PROJECTION_SCHEMA_VERSION = "issue_fix_metrics_supplement_projection_v0"

_EVENT_TYPES = {
    "capability_gap",
    "duplicate_external_write",
    "first_push_ci",
    "human_intervention",
    "useful_public_comment",
}
_SUPPLEMENT_FIELDS = (
    "human_interventions",
    "automatic_terminal_closeouts",
    "duplicate_external_writes",
    "loopx_capability_gaps_found",
    "loopx_capability_gaps_fixed",
    "loopx_capability_gaps_real_callsite_verified",
    "memory_retrievals",
    "memory_verified_decision_influence",
    "memory_verified_patch_influence",
    "memory_stale_results",
    "useful_public_comments",
    "triage_outcomes",
    "issues_screened",
    "first_push_ci_passed",
    "first_push_ci_total",
)


def _timestamp(value: Any, *, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _latest_rows(
    rows: list[dict[str, Any]], *, repo: str, ref_field: str
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        observation = row.get("observation") if isinstance(row, dict) else None
        if not isinstance(observation, dict) or observation.get("repo") != repo:
            continue
        reference = str(observation.get(ref_field) or "").strip()
        if reference:
            latest[reference] = row
    return [latest[key] for key in sorted(latest)]


def _events_in_period(
    event_batch: dict[str, Any] | None,
    *,
    period_start: datetime,
    period_end: datetime,
) -> list[dict[str, Any]]:
    if event_batch is None:
        return []
    if event_batch.get("schema_version") != EVENT_BATCH_SCHEMA_VERSION:
        raise ValueError(f"event batch must use {EVENT_BATCH_SCHEMA_VERSION}")
    raw_events = event_batch.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("event batch events must be a list")
    events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_events):
        if not isinstance(item, dict):
            raise ValueError(f"events[{index}] must be an object")
        event_id = str(item.get("event_id") or "").strip()
        event_type = str(item.get("event_type") or "").strip()
        if not event_id or event_type not in _EVENT_TYPES:
            raise ValueError(
                f"events[{index}] requires event_id and a known event_type"
            )
        if event_id in seen_ids:
            raise ValueError(f"duplicate event_id: {event_id}")
        seen_ids.add(event_id)
        occurred_at = _timestamp(
            item.get("occurred_at"), field=f"events[{index}].occurred_at"
        )
        if period_start <= occurred_at <= period_end:
            events.append(dict(item))
    return events


def _lifecycle_first_push_ci(
    lifecycles: list[dict[str, Any]],
    *,
    period_start: datetime,
    period_end: datetime,
) -> tuple[set[str], dict[str, str]]:
    eligible_refs: set[str] = set()
    observed: dict[str, str] = {}
    for index, row in enumerate(lifecycles):
        observation = row.get("observation") or {}
        pr_ref = str(observation.get("pr_ref") or "").strip()
        if not pr_ref:
            continue
        eligible_refs.add(pr_ref)
        evidence = row.get("first_push_ci")
        if not isinstance(evidence, dict):
            continue
        if evidence.get("schema_version") != "issue_fix_first_push_ci_evidence_v0":
            raise ValueError(
                f"pr_lifecycle_rows[{index}].first_push_ci uses an unsupported schema"
            )
        observed_at = _timestamp(
            evidence.get("observed_at"),
            field=f"pr_lifecycle_rows[{index}].first_push_ci.observed_at",
        )
        if not period_start <= observed_at <= period_end:
            continue
        status = str(evidence.get("status") or "").upper()
        if status not in {"PASSING", "FAILING"}:
            raise ValueError(
                f"pr_lifecycle_rows[{index}].first_push_ci.status must be PASSING or FAILING"
            )
        evidence_ref = str(evidence.get("pr_ref") or "").strip()
        if evidence_ref and evidence_ref != pr_ref:
            raise ValueError(
                f"pr_lifecycle_rows[{index}].first_push_ci.pr_ref must match observation"
            )
        observed[pr_ref] = status
    return eligible_refs, observed


def _memory_counts(
    memory_results: list[dict[str, Any]], feasibility: list[dict[str, Any]]
) -> dict[str, int] | None:
    results: list[dict[str, Any]] = []
    for index, payload in enumerate(memory_results):
        if (
            payload.get("schema_version")
            != "issue_fix_repository_memory_read_result_v0"
        ):
            raise ValueError(
                f"repository memory input {index} must use issue_fix_repository_memory_read_result_v0"
            )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise ValueError(f"repository memory input {index} results must be a list")
        results.extend(item for item in raw_results if isinstance(item, dict))
    if results:
        return {
            "memory_retrievals": len(results),
            "memory_verified_decision_influence": sum(
                str(item.get("verification_status") or "").lower() == "confirmed"
                and bool(item.get("decision_influence"))
                for item in results
            ),
            "memory_verified_patch_influence": sum(
                str(item.get("verification_status") or "").lower() == "confirmed"
                and item.get("patch_influence_allowed") is True
                for item in results
            ),
            "memory_stale_results": sum(
                str(item.get("verification_status") or "").lower() == "stale"
                for item in results
            ),
        }

    hooks = []
    for row in feasibility:
        observation = row.get("observation") or {}
        repository_context = observation.get("repository_context") or {}
        memory = repository_context.get("memory_projection") or {}
        hook = memory.get("retrieval_hook")
        if isinstance(hook, dict) and hook.get("read_performed") is True:
            hooks.append(hook)
    if not hooks:
        return None
    return {
        "memory_retrievals": sum(int(item.get("result_count") or 0) for item in hooks),
        "memory_verified_decision_influence": sum(
            int(item.get("verified_decision_influence_count") or 0)
            for item in hooks
        ),
        "memory_verified_patch_influence": sum(
            int(item.get("patch_influence_allowed_count") or 0) for item in hooks
        ),
        "memory_stale_results": sum(
            int(item.get("stale_count") or 0) for item in hooks
        ),
    }


def _history_human_interventions(
    history_rows: list[dict[str, Any]],
    *,
    period_start: datetime,
    period_end: datetime,
) -> list[str]:
    """Return stable ids for explicit route-changing human decisions.

    The compact run index is already LoopX's audit source for operator gates and
    run-bound rewards. Ordinary chat, passive acknowledgements, and rewards
    without an explicit correction lesson are intentionally out of scope.
    """

    event_ids: set[str] = set()
    for row in history_rows:
        if not isinstance(row, dict):
            continue
        generated_at = str(row.get("generated_at") or "").strip()
        classification = str(row.get("classification") or "").strip()
        operator_gate = row.get("operator_gate")
        if classification in {
            "operator_gate_approved",
            "operator_gate_rejected",
            "operator_gate_deferred",
        } and isinstance(operator_gate, dict):
            occurred_at = _timestamp(
                operator_gate.get("recorded_at") or generated_at,
                field="run_history.operator_gate.recorded_at",
            )
            if period_start <= occurred_at <= period_end:
                gate = str(operator_gate.get("gate") or "unknown").strip()
                decision = str(operator_gate.get("decision") or "unknown").strip()
                event_ids.add(f"operator_gate:{generated_at}:{gate}:{decision}")

        human_reward = row.get("human_reward")
        lesson = (
            human_reward.get("lesson")
            if isinstance(human_reward, dict)
            else None
        )
        if not (
            isinstance(lesson, dict)
            and lesson.get("schema_version") == "human_reward_lesson_v0"
        ):
            continue
        occurred_at = _timestamp(
            human_reward.get("recorded_at"),
            field="run_history.human_reward.recorded_at",
        )
        if period_start <= occurred_at <= period_end:
            decision = str(human_reward.get("decision") or "unknown").strip()
            event_ids.add(f"human_correction:{generated_at}:{decision}")
    return sorted(event_ids)


def _rollout_capability_gap_states(
    rollout_event_rows: list[dict[str, Any]],
    *,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, set[str]]:
    states: dict[str, set[str]] = {}
    for index, event in enumerate(rollout_event_rows):
        if not isinstance(event, dict) or event.get("event_kind") != "capability_gap":
            continue
        occurred_at = _timestamp(
            event.get("recorded_at"),
            field=f"rollout_event_rows[{index}].recorded_at",
        )
        if not period_start <= occurred_at <= period_end:
            continue
        gap_id = str(event.get("todo_id") or "").strip()
        status = str(event.get("status") or "").strip().lower()
        details = event.get("details")
        target_capabilities = (
            details.get("target_capabilities")
            if isinstance(details, dict)
            else None
        )
        if (
            not gap_id
            or status not in {"found", "fixed", "real_callsite_verified"}
            or not str(target_capabilities or "").strip()
        ):
            raise ValueError(
                "capability_gap rollout events require todo_id, a known status, "
                "and non-empty details.target_capabilities"
            )
        states.setdefault(gap_id, set()).add(status)
    return states


def _capability_gap_counts(gap_states: dict[str, set[str]]) -> dict[str, int]:
    return {
        "loopx_capability_gaps_found": len(gap_states),
        "loopx_capability_gaps_fixed": sum(
            bool(states & {"fixed", "real_callsite_verified"})
            for states in gap_states.values()
        ),
        "loopx_capability_gaps_real_callsite_verified": sum(
            "real_callsite_verified" in states for states in gap_states.values()
        ),
    }


def build_issue_fix_metrics_supplement(
    *,
    repo: str,
    period_start: str,
    period_end: str,
    feasibility_rows: list[dict[str, Any]],
    pr_lifecycle_rows: list[dict[str, Any]],
    event_batch: dict[str, Any] | None,
    run_history_rows: list[dict[str, Any]],
    human_intervention_coverage_start: str | None,
    rollout_event_rows: list[dict[str, Any]],
    capability_gap_coverage_start: str | None,
    repository_memory_results: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    repo = str(repo or "").strip()
    if not repo:
        raise ValueError("repo is required")
    start = _timestamp(period_start, field="period_start")
    end = _timestamp(period_end, field="period_end")
    _timestamp(generated_at, field="generated_at")
    if end < start:
        raise ValueError("period_end must not predate period_start")

    feasibility = _latest_rows(feasibility_rows, repo=repo, ref_field="issue_ref")
    lifecycles = _latest_rows(pr_lifecycle_rows, repo=repo, ref_field="pr_ref")
    events = _events_in_period(event_batch, period_start=start, period_end=end)
    history_intervention_ids = _history_human_interventions(
        run_history_rows,
        period_start=start,
        period_end=end,
    )
    rollout_gap_states = (
        _rollout_capability_gap_states(
            rollout_event_rows,
            period_start=start,
            period_end=end,
        )
        if event_batch is None
        else {}
    )
    first_push_eligible, first_push_statuses = _lifecycle_first_push_ci(
        lifecycles,
        period_start=start,
        period_end=end,
    )
    counts: dict[str, int] = {
        "issues_screened": len(feasibility),
        "triage_outcomes": sum(
            str((row.get("decision") or {}).get("route") or "") == "triage_only"
            for row in feasibility
        ),
        "automatic_terminal_closeouts": sum(
            str((row.get("transition") or {}).get("decision") or "") == "no_followup"
            and str((row.get("observation") or {}).get("state") or "").upper()
            in {"MERGED", "CLOSED"}
            for row in lifecycles
        ),
    }

    human_intervention_coverage: dict[str, Any]
    if event_batch is not None:
        counts["human_interventions"] = sum(
            item.get("event_type") == "human_intervention" for item in events
        )
        human_intervention_coverage = {
            "source": EVENT_BATCH_SCHEMA_VERSION,
            "observed_events": counts["human_interventions"],
            "complete": True,
        }
        counts["duplicate_external_writes"] = sum(
            item.get("event_type") == "duplicate_external_write" for item in events
        )
        counts["useful_public_comments"] = sum(
            item.get("event_type") == "useful_public_comment" for item in events
        )
        first_push = [
            item for item in events if item.get("event_type") == "first_push_ci"
        ]
        pr_refs = [str(item.get("pr_ref") or "").strip() for item in first_push]
        if any(not value for value in pr_refs) or len(set(pr_refs)) != len(pr_refs):
            raise ValueError("first_push_ci events require unique pr_ref values")
        statuses = [str(item.get("status") or "").upper() for item in first_push]
        if any(status not in {"PASSING", "FAILING"} for status in statuses):
            raise ValueError("first_push_ci status must be PASSING or FAILING")
        for pr_ref, status in zip(pr_refs, statuses):
            existing = first_push_statuses.get(pr_ref)
            if existing is not None and existing != status:
                raise ValueError(
                    f"first_push_ci event for {pr_ref} conflicts with lifecycle evidence"
                )
            first_push_eligible.add(pr_ref)
            first_push_statuses[pr_ref] = status

        gaps = [item for item in events if item.get("event_type") == "capability_gap"]
        gap_states: dict[str, set[str]] = {}
        for item in gaps:
            gap_id = str(item.get("gap_id") or "").strip()
            status = str(item.get("status") or "").strip().lower()
            if not gap_id or status not in {"found", "fixed", "real_callsite_verified"}:
                raise ValueError(
                    "capability_gap events require gap_id and a known status"
                )
            gap_states.setdefault(gap_id, set()).add(status)
        counts.update(_capability_gap_counts(gap_states))
        capability_gap_coverage: dict[str, Any] = {
            "source": EVENT_BATCH_SCHEMA_VERSION,
            "observed_gaps": len(gap_states),
            "complete": True,
        }
    else:
        capture_start = (
            _timestamp(
                human_intervention_coverage_start,
                field="human_intervention_coverage_start",
            )
            if human_intervention_coverage_start
            else None
        )
        complete = capture_start is not None and capture_start <= start
        human_intervention_coverage = {
            "source": "loopx_compact_run_index",
            "observed_events": len(history_intervention_ids),
            "complete": complete,
        }
        if capture_start is not None:
            human_intervention_coverage["complete_from"] = (
                human_intervention_coverage_start
            )
        if complete:
            counts["human_interventions"] = len(history_intervention_ids)
        gap_capture_start = (
            _timestamp(
                capability_gap_coverage_start,
                field="capability_gap_coverage_start",
            )
            if capability_gap_coverage_start
            else None
        )
        gap_complete = gap_capture_start is not None and gap_capture_start <= start
        capability_gap_coverage = {
            "source": "loopx_rollout_event_log",
            "observed_gaps": len(rollout_gap_states),
            "complete": gap_complete,
        }
        if gap_capture_start is not None:
            capability_gap_coverage["complete_from"] = (
                capability_gap_coverage_start
            )
        if gap_complete:
            counts.update(_capability_gap_counts(rollout_gap_states))

    first_push_complete = bool(first_push_eligible) and len(first_push_statuses) == len(
        first_push_eligible
    )
    if first_push_complete:
        counts["first_push_ci_total"] = len(first_push_statuses)
        counts["first_push_ci_passed"] = sum(
            status == "PASSING" for status in first_push_statuses.values()
        )

    memory = _memory_counts(repository_memory_results, feasibility)
    if memory is not None:
        counts.update(memory)

    missing_fields = [field for field in _SUPPLEMENT_FIELDS if field not in counts]
    supplement = {
        "schema_version": SUPPLEMENT_SCHEMA_VERSION,
        "counts": counts,
        "coverage": {
            "human_intervention": human_intervention_coverage,
            "capability_gap": capability_gap_coverage,
            "first_push_ci": {
                "eligible_prs": len(first_push_eligible),
                "observed_prs": len(first_push_statuses),
                "complete": first_push_complete,
            }
        },
    }
    return {
        "ok": True,
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "mode": "issue-fix-metrics-supplement",
        "repo": repo,
        "period": {"start": period_start, "end": period_end},
        "supplement": supplement,
        "missing_fields": missing_fields,
        "source_summary": {
            "feasibility_rows": len(feasibility),
            "pr_lifecycle_rows": len(lifecycles),
            "event_rows": len(events),
            "run_history_rows": len(run_history_rows),
            "rollout_event_rows": len(rollout_event_rows),
            "repository_memory_inputs": len(repository_memory_results),
        },
        "generated_at": generated_at,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "raw_event_payload_captured": False,
        "raw_memory_captured": False,
        "credentials_captured": False,
        "local_paths_captured": False,
    }


def render_issue_fix_metrics_supplement_markdown(payload: dict[str, Any]) -> str:
    if payload.get("ok") is not True:
        return f"# Issue-fix metrics supplement\n\n- Error: {payload.get('error') or 'invalid input'}"
    counts = (payload.get("supplement") or {}).get("counts") or {}
    return "\n".join(
        [
            "# Issue-fix metrics supplement",
            "",
            f"- repository: `{payload.get('repo')}`",
            f"- issues screened: `{counts.get('issues_screened')}`",
            f"- automatic terminal closeouts: `{counts.get('automatic_terminal_closeouts')}`",
            f"- memory retrievals: `{counts.get('memory_retrievals', 'not available')}`",
            f"- missing fields: `{len(payload.get('missing_fields') or [])}`",
        ]
    )
