from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text


ISSUE_FIX_OUTCOME_PROJECTION_SCHEMA_VERSION = "issue_fix_outcome_projection_v0"
ISSUE_FIX_OUTCOME_CASE_SCHEMA_VERSION = "issue_fix_outcome_case_v0"
ISSUE_FIX_OUTCOME_COLLECTION_PROJECTION_SCHEMA_VERSION = (
    "issue_fix_outcome_collection_projection_v0"
)
ISSUE_FIX_DELIVERY_EVIDENCE_INPUT_SCHEMA_VERSION = (
    "issue_fix_delivery_evidence_input_v0"
)

DELIVERY_VALIDATION_STATUSES = {"passed", "failed", "partial", "not_run"}
DELIVERY_OUTCOME_STATUSES = {"in_progress", "completed", "blocked"}
BRANCH_REPLAN_MERGE_STATES = {"BEHIND", "DIRTY"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_text(value: Any, *, field: str, limit: int = 260) -> str:
    if value is None:
        return ""
    text = public_safe_compact_text(value, limit=limit)
    if str(value).strip() and not text:
        raise ValueError(f"{field} must be a compact public-safe value")
    return text


def _safe_text_list(
    value: Any,
    *,
    field: str,
    limit: int = 220,
    count_limit: int = 20,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a list")
    return [
        text
        for index, item in enumerate(value)
        if (text := _safe_text(item, field=f"{field}[{index}]", limit=limit))
    ][:count_limit]


def _repo_relative_files(value: Any) -> list[str]:
    files = _safe_text_list(value, field="changed_files", limit=260)
    for path in files:
        pure = PurePosixPath(path)
        if (
            path.startswith(("/", "~"))
            or "\\" in path
            or pure.is_absolute()
            or ".." in pure.parts
        ):
            raise ValueError("changed_files must contain only repo-relative paths")
    return files


def _delivery_evidence(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {
            "provided": False,
            "outcome_status": "in_progress",
            "validation_status": None,
            "changed_files": [],
            "commit_ref": None,
            "outputs": [],
            "risks": [],
        }
    schema_version = str(value.get("schema_version") or "").strip()
    if schema_version != ISSUE_FIX_DELIVERY_EVIDENCE_INPUT_SCHEMA_VERSION:
        raise ValueError(
            "delivery evidence schema_version must be "
            "issue_fix_delivery_evidence_input_v0"
        )
    validation_status = str(value.get("validation_status") or "not_run").strip()
    if validation_status not in DELIVERY_VALIDATION_STATUSES:
        raise ValueError(
            "delivery evidence validation_status must be one of "
            f"{sorted(DELIVERY_VALIDATION_STATUSES)}"
        )
    outcome_status = str(value.get("outcome_status") or "in_progress").strip()
    if outcome_status not in DELIVERY_OUTCOME_STATUSES:
        raise ValueError(
            "delivery evidence outcome_status must be one of "
            f"{sorted(DELIVERY_OUTCOME_STATUSES)}"
        )
    commit_ref = _safe_text(value.get("commit_ref"), field="commit_ref", limit=80)
    if commit_ref and not re.fullmatch(r"[A-Za-z0-9._/-]{4,80}", commit_ref):
        raise ValueError("commit_ref must be a compact public-safe git reference")
    outputs: list[dict[str, str]] = []
    raw_outputs = value.get("outputs") or []
    if not isinstance(raw_outputs, Sequence) or isinstance(raw_outputs, (str, bytes)):
        raise ValueError("delivery evidence outputs must be a list")
    for index, item in enumerate(raw_outputs[:10]):
        if not isinstance(item, Mapping):
            raise ValueError(f"delivery evidence outputs[{index}] must be an object")
        kind = _safe_text(item.get("kind"), field=f"outputs[{index}].kind", limit=60)
        url = _safe_text(item.get("url"), field=f"outputs[{index}].url", limit=320)
        if url and not url.startswith("https://"):
            raise ValueError("delivery evidence output URLs must use https")
        if kind or url:
            outputs.append({"kind": kind or "artifact", "url": url})
    return {
        "provided": True,
        "outcome_status": outcome_status,
        "validation_status": validation_status,
        "validation_label": _safe_text(
            value.get("validation_label"), field="validation_label", limit=260
        ),
        "changed_files": _repo_relative_files(value.get("changed_files") or []),
        "commit_ref": commit_ref or None,
        "outputs": outputs,
        "risks": _safe_text_list(
            value.get("risks") or [], field="risks", limit=260, count_limit=10
        ),
    }


def compact_issue_fix_delivery_evidence(
    value: Mapping[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Validate and compact delivery evidence before domain-state writeback."""

    delivery = _delivery_evidence(value)
    compact: dict[str, Any] = {
        "schema_version": ISSUE_FIX_DELIVERY_EVIDENCE_INPUT_SCHEMA_VERSION,
        "outcome_status": delivery["outcome_status"],
        "validation_status": delivery["validation_status"],
        "validation_label": delivery.get("validation_label") or "",
        "changed_files": list(delivery.get("changed_files") or []),
        "commit_ref": delivery.get("commit_ref"),
        "outputs": list(delivery.get("outputs") or []),
        "risks": list(delivery.get("risks") or []),
    }
    if recorded_at:
        compact["recorded_at"] = _safe_text(
            recorded_at,
            field="delivery evidence recorded_at",
            limit=80,
        )
    return compact


def _stage_and_card_status(
    *,
    route: str,
    reproduction_status: str,
    delivery_outcome_status: str,
    lifecycle_observation: Mapping[str, Any],
) -> tuple[str, str, str]:
    if lifecycle_observation:
        state = str(lifecycle_observation.get("state") or "OPEN").upper()
        checks = _mapping(lifecycle_observation.get("checks"))
        checks_aggregate = str(checks.get("aggregate") or "UNKNOWN").upper()
        review_decision = str(
            lifecycle_observation.get("review_decision") or "UNKNOWN"
        ).upper()
        merge_state = str(
            lifecycle_observation.get("merge_state_status") or "UNKNOWN"
        ).upper()
        if state == "MERGED":
            return "merged", "done", "P1"
        if state == "CLOSED":
            return "closed_without_merge", "done", "P1"
        if delivery_outcome_status == "blocked":
            return "delivery_blocked", "blocked", "P0"
        if checks_aggregate == "FAILING":
            return "ci_failed", "blocked", "P0"
        if review_decision == "CHANGES_REQUESTED":
            return "changes_requested", "blocked", "P0"
        if merge_state in BRANCH_REPLAN_MERGE_STATES:
            return "branch_stale_or_conflicted", "blocked", "P1"
        if lifecycle_observation.get("is_draft") is True:
            return "draft_pr", "open", "P1"
        if checks_aggregate == "PENDING":
            return "ci_pending", "open", "P2"
        if review_decision == "APPROVED" and checks_aggregate == "PASSING":
            return "merge_ready", "open", "P1"
        if review_decision == "REVIEW_REQUIRED":
            return "review_wait", "open", "P2"
        return "pr_open", "open", "P2"
    if route == "triage_only":
        return "triage_complete", "done", "P1"
    if route == "comment_only":
        if delivery_outcome_status == "completed":
            return "comment_published", "done", "P1"
        if delivery_outcome_status == "blocked":
            return "comment_blocked", "blocked", "P1"
        return "comment_packet", "open", "P1"
    if delivery_outcome_status == "blocked":
        return "fix_blocked", "blocked", "P0"
    if delivery_outcome_status == "completed":
        return "fix_review_ready", "open", "P1"
    if reproduction_status == "planned":
        return "reproduction_planned", "open", "P0"
    if reproduction_status in {"missing", "blocked"}:
        return "reproduction_blocked", "blocked", "P0"
    return "fix_in_progress", "open", "P0"


def _result(
    *,
    route: str,
    stage: str,
    issue_url: str,
    pr_url: str,
    delivery: Mapping[str, Any],
) -> dict[str, Any]:
    terminal = stage in {
        "merged",
        "closed_without_merge",
        "triage_complete",
        "comment_published",
    }
    if stage == "merged":
        kind = "fix_pr_merged"
    elif stage == "closed_without_merge":
        kind = "pr_closed_without_merge"
    elif stage == "triage_complete":
        kind = "triage_complete"
    elif stage == "comment_published":
        kind = "useful_comment_published"
    elif route == "comment_only":
        kind = "comment_packet_pending_publication"
    elif pr_url:
        kind = "fix_pr_open"
    else:
        kind = "fix_in_progress"
    outputs = list(delivery.get("outputs") or [])
    known_urls = {
        str(item.get("url") or "") for item in outputs if isinstance(item, Mapping)
    }
    for output_kind, url in (("issue", issue_url), ("pull_request", pr_url)):
        if url and url not in known_urls:
            outputs.append({"kind": output_kind, "url": url})
    return {
        "kind": kind,
        "terminal": terminal,
        "public_outputs": outputs,
    }


def _evidence_summary(case: Mapping[str, Any]) -> str:
    context = _mapping(case.get("repository_context"))
    reproduction = _mapping(case.get("reproduction"))
    validation = _mapping(case.get("validation"))
    pull_request = _mapping(case.get("pull_request"))
    issue = _mapping(case.get("issue"))
    delivery = _mapping(case.get("delivery"))
    result = _mapping(case.get("result"))
    checks = _mapping(pull_request.get("checks"))
    parts = [
        f"stage={case.get('stage')}",
        f"route={case.get('route')}",
        f"revision={context.get('revision') or 'unknown'}",
        f"context={context.get('fingerprint') or 'unknown'}",
        f"reproduction={reproduction.get('status') or 'unknown'}",
        f"validation={validation.get('status') or 'unknown'}",
    ]
    if issue.get("url"):
        parts.append(f"issue={issue.get('url')}")
    if delivery.get("commit_ref"):
        parts.append(f"commit={delivery.get('commit_ref')}")
    changed_files = list(delivery.get("changed_files") or [])
    if changed_files:
        parts.append(f"changed_files={','.join(str(item) for item in changed_files)}")
    if pull_request:
        parts.extend(
            [
                f"pr_state={pull_request.get('state') or 'unknown'}",
                f"checks={checks.get('aggregate') or 'unknown'}",
                f"review={pull_request.get('review_decision') or 'unknown'}",
                f"merge_state={pull_request.get('merge_state_status') or 'unknown'}",
                f"pr={pull_request.get('url') or 'unknown'}",
            ]
        )
    output_urls = [
        str(item.get("url") or "")
        for item in result.get("public_outputs") or []
        if isinstance(item, Mapping) and item.get("url")
    ]
    if output_urls:
        parts.append(f"outputs={','.join(output_urls)}")
    risks = list(case.get("risks") or [])
    if risks:
        parts.append(f"risks={' | '.join(str(item) for item in risks)}")
    return "; ".join(parts)


def build_issue_fix_outcome_projection(
    *,
    goal_id: str,
    feasibility_packet: Mapping[str, Any],
    pr_lifecycle_packet: Mapping[str, Any] | None = None,
    delivery_evidence_input: Mapping[str, Any] | None = None,
    agent_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compose one public-safe issue-fix case view without writing source state."""

    feasibility_observation = _mapping(feasibility_packet.get("observation"))
    feasibility_decision = _mapping(feasibility_packet.get("decision"))
    if feasibility_packet.get("schema_version") != "issue_fix_feasibility_v0":
        raise ValueError("feasibility packet must use issue_fix_feasibility_v0")
    repo = _safe_text(feasibility_observation.get("repo"), field="repo", limit=180)
    issue_ref = _safe_text(
        feasibility_observation.get("issue_ref"), field="issue_ref", limit=180
    )
    if not repo or not issue_ref:
        raise ValueError("feasibility packet must identify repo and issue_ref")
    route = str(feasibility_decision.get("route") or "").strip()
    if route not in {"fix_pr", "comment_only", "triage_only"}:
        raise ValueError("feasibility packet must select a supported route")

    lifecycle_observation: dict[str, Any] = {}
    lifecycle_transition: dict[str, Any] = {}
    if pr_lifecycle_packet is not None:
        if (
            pr_lifecycle_packet.get("schema_version")
            != "issue_fix_pr_lifecycle_monitor_v0"
        ):
            raise ValueError(
                "PR lifecycle packet must use issue_fix_pr_lifecycle_monitor_v0"
            )
        lifecycle_observation = _mapping(pr_lifecycle_packet.get("observation"))
        lifecycle_transition = _mapping(pr_lifecycle_packet.get("transition"))
        lifecycle_repo = str(lifecycle_observation.get("repo") or "").strip()
        if lifecycle_repo != repo:
            raise ValueError(
                "feasibility and PR lifecycle packets must use the same repo"
            )

    repository_context = _mapping(feasibility_observation.get("repository_context"))
    context_effect = _mapping(feasibility_packet.get("repository_context_effect"))
    delivery = _delivery_evidence(delivery_evidence_input)
    reproduction_status = str(
        feasibility_observation.get("reproduction_status") or "missing"
    ).strip()
    stage, card_status, priority = _stage_and_card_status(
        route=route,
        reproduction_status=reproduction_status,
        delivery_outcome_status=str(delivery.get("outcome_status") or "in_progress"),
        lifecycle_observation=lifecycle_observation,
    )
    issue_url = _safe_text(
        feasibility_observation.get("permalink"), field="issue permalink", limit=320
    )
    pr_url = _safe_text(
        lifecycle_observation.get("permalink"), field="PR permalink", limit=320
    )
    issue_number = feasibility_observation.get("number")
    pr_number = lifecycle_observation.get("number")
    title = f"[{route}] {repo} #{issue_number or issue_ref}"
    if pr_number:
        title += f" -> PR #{pr_number}"
    validation_label = delivery.get("validation_label") or _safe_text(
        feasibility_observation.get("validation_label"),
        field="validation label",
        limit=260,
    )
    feasibility_transition = _mapping(feasibility_packet.get("transition"))
    projected_todo = _mapping(feasibility_transition.get("projected_todo"))
    next_action = _safe_text(
        lifecycle_transition.get("reason")
        or projected_todo.get("text")
        or feasibility_transition.get("decision"),
        field="next action",
        limit=320,
    )
    case: dict[str, Any] = {
        "schema_version": ISSUE_FIX_OUTCOME_CASE_SCHEMA_VERSION,
        "outcome_id": f"{repo}:{issue_ref}",
        "title": title,
        "summary": f"{stage}: {next_action}" if next_action else stage,
        "goal_id": goal_id,
        "repo": repo,
        "issue_ref": issue_ref,
        "route": route,
        "stage": stage,
        "status": card_status,
        "priority": priority,
        "task_class": "continuous_monitor"
        if not card_status == "done"
        else "advancement_task",
        "action_kind": "issue_fix_outcome",
        "claimed_by": _safe_text(agent_id, field="agent_id", limit=120) or None,
        "issue": {
            "number": issue_number,
            "url": issue_url,
        },
        "repository_context": {
            "revision": _safe_text(
                repository_context.get("repository_revision"),
                field="repository revision",
                limit=80,
            )
            or None,
            "fingerprint": _safe_text(
                repository_context.get("context_fingerprint")
                or context_effect.get("context_fingerprint"),
                field="context fingerprint",
                limit=80,
            )
            or None,
            "status": _safe_text(
                repository_context.get("context_status")
                or context_effect.get("context_status"),
                field="context status",
                limit=80,
            )
            or "unknown",
        },
        "reproduction": {
            "status": reproduction_status,
            "label": _safe_text(
                feasibility_observation.get("reproduction_label"),
                field="reproduction label",
                limit=260,
            )
            or None,
            "evidence_refs": list(
                context_effect.get("reproduction_evidence_refs") or []
            ),
        },
        "validation": {
            "status": delivery.get("validation_status")
            or ("declared" if validation_label else "unknown"),
            "label": validation_label or None,
            "evidence_refs": list(context_effect.get("validation_evidence_refs") or []),
        },
        "delivery": {
            "evidence_provided": delivery.get("provided") is True,
            "outcome_status": delivery.get("outcome_status"),
            "commit_ref": delivery.get("commit_ref"),
            "changed_files": list(delivery.get("changed_files") or []),
        },
        "pull_request": (
            {
                "number": pr_number,
                "ref": lifecycle_observation.get("pr_ref"),
                "url": pr_url,
                "state": lifecycle_observation.get("state"),
                "is_draft": lifecycle_observation.get("is_draft") is True,
                "checks": _mapping(lifecycle_observation.get("checks")),
                "review_decision": lifecycle_observation.get("review_decision"),
                "merge_state_status": lifecycle_observation.get("merge_state_status"),
                "merged_at": lifecycle_observation.get("merged_at"),
                "closed_at": lifecycle_observation.get("closed_at"),
            }
            if lifecycle_observation
            else None
        ),
        "result": _result(
            route=route,
            stage=stage,
            issue_url=issue_url,
            pr_url=pr_url,
            delivery=delivery,
        ),
        "risks": list(delivery.get("risks") or []),
        "next_action": next_action or None,
        "handoff": next_action or "No further action projected.",
        "scope": "issue_fix_outcome",
        "_include_done_by_default": True,
    }
    case["evidence"] = _evidence_summary(case)
    packet: dict[str, Any] = {
        "ok": True,
        "schema_version": ISSUE_FIX_OUTCOME_PROJECTION_SCHEMA_VERSION,
        "mode": "issue-fix-outcome",
        "source_id": "issue-fix-outcome",
        "goal_id": goal_id,
        "generated_at": generated_at,
        "agent_identity": {"agent_id": agent_id} if agent_id else {},
        "issue_fix_outcomes": [case],
        "source_contract": {
            "feasibility": "issue_fix_feasibility_v0",
            "pr_lifecycle": (
                "issue_fix_pr_lifecycle_monitor_v0"
                if pr_lifecycle_packet is not None
                else None
            ),
            "delivery_evidence": (
                ISSUE_FIX_DELIVERY_EVIDENCE_INPUT_SCHEMA_VERSION
                if delivery_evidence_input is not None
                else None
            ),
            "writes_source_state": False,
            "creates_parallel_state_machine": False,
        },
        "external_reads_performed": False,
        "external_writes_performed": False,
        "raw_logs_captured": False,
        "local_paths_captured": False,
        "credentials_captured": False,
    }
    packet["validation"] = validate_issue_fix_outcome_projection(packet)
    packet["ok"] = packet["validation"]["ok"]
    return packet


def _load_domain_packets(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        return [], []
    packets: list[dict[str, Any]] = []
    warnings: list[str] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            packet = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{path.name}:{line_number} is not valid JSON")
            continue
        if not isinstance(packet, dict):
            warnings.append(f"{path.name}:{line_number} is not an object")
            continue
        packets.append(packet)
    return packets, warnings


def _lifecycle_recency(packet: Mapping[str, Any]) -> tuple[str, str]:
    observation = _mapping(packet.get("observation"))
    return (
        str(
            observation.get("updated_at")
            or observation.get("merged_at")
            or observation.get("closed_at")
            or packet.get("generated_at")
            or ""
        ),
        str(observation.get("pr_ref") or ""),
    )


def build_issue_fix_outcome_collection_from_domain_state(
    *,
    goal_id: str,
    project: str | Path = ".",
    agent_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Derive all goal issue outcomes from existing compact domain state.

    Feasibility rows are the issue inventory. A PR lifecycle row enriches an
    issue only when its observation carries the same explicit ``issue_ref``;
    branch names, titles, and issue numbers are never guessed. No source state
    or parallel outcome ledger is written.
    """

    from ...domain_packs.issue_fix import (
        default_issue_fix_domain_state_ledger_path,
        default_issue_fix_feasibility_ledger_path,
    )

    project_path = Path(project).expanduser()
    feasibility_packets, feasibility_warnings = _load_domain_packets(
        default_issue_fix_feasibility_ledger_path(
            project=project_path,
            goal_id=goal_id,
        )
    )
    lifecycle_packets, lifecycle_warnings = _load_domain_packets(
        default_issue_fix_domain_state_ledger_path(
            project=project_path,
            goal_id=goal_id,
        )
    )
    warnings = [*feasibility_warnings, *lifecycle_warnings]

    lifecycle_by_issue: dict[tuple[str, str], list[dict[str, Any]]] = {}
    linked_lifecycle_ids: set[int] = set()
    for packet in lifecycle_packets:
        observation = _mapping(packet.get("observation"))
        repo = str(observation.get("repo") or "").strip()
        issue_ref = str(observation.get("issue_ref") or "").strip()
        if repo and issue_ref:
            lifecycle_by_issue.setdefault((repo, issue_ref), []).append(packet)

    outcomes: list[dict[str, Any]] = []
    for feasibility_packet in feasibility_packets:
        observation = _mapping(feasibility_packet.get("observation"))
        repo = str(observation.get("repo") or "").strip()
        issue_ref = str(observation.get("issue_ref") or "").strip()
        lifecycle_packet: dict[str, Any] | None = None
        candidates = lifecycle_by_issue.get((repo, issue_ref), [])
        if candidates:
            lifecycle_packet = max(candidates, key=_lifecycle_recency)
            linked_lifecycle_ids.update(id(item) for item in candidates)
        try:
            projection = build_issue_fix_outcome_projection(
                goal_id=goal_id,
                feasibility_packet=feasibility_packet,
                pr_lifecycle_packet=lifecycle_packet,
                delivery_evidence_input=(
                    feasibility_packet.get("delivery_evidence")
                    if isinstance(
                        feasibility_packet.get("delivery_evidence"), Mapping
                    )
                    else None
                ),
                agent_id=agent_id,
                generated_at=generated_at,
            )
        except ValueError as exc:
            safe_identity = public_safe_compact_text(
                f"{repo}:{issue_ref}", limit=220
            ) or "unknown issue"
            safe_error = public_safe_compact_text(exc, limit=260) or "invalid row"
            warnings.append(f"skipped {safe_identity}: {safe_error}")
            continue
        if projection.get("ok") is True:
            outcomes.extend(list(projection.get("issue_fix_outcomes") or []))

    unlinked_lifecycle_count = sum(
        1 for packet in lifecycle_packets if id(packet) not in linked_lifecycle_ids
    )
    collection: dict[str, Any] = {
        "ok": True,
        "schema_version": ISSUE_FIX_OUTCOME_COLLECTION_PROJECTION_SCHEMA_VERSION,
        "mode": "issue-fix-outcome-collection",
        "source_id": "issue-fix-outcome",
        "goal_id": goal_id,
        "generated_at": generated_at,
        "agent_identity": {"agent_id": agent_id} if agent_id else {},
        "issue_fix_outcomes": outcomes,
        "source_contract": {
            "feasibility": "issue_fix_feasibility_v0",
            "pr_lifecycle": "issue_fix_pr_lifecycle_monitor_v0",
            "delivery_evidence": "embedded_in_feasibility_row",
            "association": "explicit_repo_and_issue_ref_only",
            "writes_source_state": False,
            "creates_parallel_state_machine": False,
        },
        "source_counts": {
            "feasibility": len(feasibility_packets),
            "pr_lifecycle": len(lifecycle_packets),
            "outcomes": len(outcomes),
            "unlinked_pr_lifecycle": unlinked_lifecycle_count,
        },
        "warnings": warnings,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "raw_logs_captured": False,
        "local_paths_captured": False,
        "credentials_captured": False,
    }
    collection["validation"] = validate_issue_fix_outcome_collection_projection(
        collection
    )
    collection["ok"] = bool(collection["validation"]["ok"])
    return collection


def validate_issue_fix_outcome_collection_projection(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if (
        packet.get("schema_version")
        != ISSUE_FIX_OUTCOME_COLLECTION_PROJECTION_SCHEMA_VERSION
    ):
        errors.append(
            "schema_version must be issue_fix_outcome_collection_projection_v0"
        )
    outcomes = packet.get("issue_fix_outcomes")
    if not isinstance(outcomes, list):
        errors.append("issue_fix_outcomes must be a list")
        outcomes = []
    outcome_ids = [
        str(item.get("outcome_id") or "")
        for item in outcomes
        if isinstance(item, Mapping)
    ]
    if any(not value for value in outcome_ids):
        errors.append("every issue-fix outcome must have an outcome_id")
    if len(set(outcome_ids)) != len(outcome_ids):
        errors.append("issue-fix outcome ids must be unique")
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "raw_logs_captured",
        "local_paths_captured",
        "credentials_captured",
    ):
        if packet.get(key) is not False:
            errors.append(f"{key} must be false")
    return {
        "schema_version": "issue_fix_outcome_collection_projection_validation_v0",
        "ok": not errors,
        "errors": errors,
    }


def validate_issue_fix_outcome_projection(packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != ISSUE_FIX_OUTCOME_PROJECTION_SCHEMA_VERSION:
        errors.append("schema_version must be issue_fix_outcome_projection_v0")
    outcomes = packet.get("issue_fix_outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != 1:
        errors.append("issue_fix_outcomes must contain exactly one case")
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "raw_logs_captured",
        "local_paths_captured",
        "credentials_captured",
    ):
        if packet.get(key) is not False:
            errors.append(f"{key} must be false")
    return {
        "schema_version": "issue_fix_outcome_projection_validation_v0",
        "ok": not errors,
        "errors": errors,
    }


def render_issue_fix_outcome_projection_markdown(payload: dict[str, Any]) -> str:
    if payload.get("ok") is not True:
        return f"# LoopX issue-fix outcome\n\n- ok: `false`\n- error: `{payload.get('error')}`"
    outcome = _mapping((payload.get("issue_fix_outcomes") or [{}])[0])
    result = _mapping(outcome.get("result"))
    lines = [
        "# LoopX issue-fix outcome",
        "",
        f"- case: `{outcome.get('outcome_id')}`",
        f"- stage: `{outcome.get('stage')}`",
        f"- route: `{outcome.get('route')}`",
        f"- result: `{result.get('kind')}`",
        f"- evidence: {outcome.get('evidence')}",
        f"- next action: {outcome.get('next_action') or 'none'}",
    ]
    return "\n".join(lines)
