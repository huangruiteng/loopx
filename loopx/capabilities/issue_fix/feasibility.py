from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .metadata_preview import normalise_github_issue_reference
from .repository_context import build_issue_fix_repository_context_packet


ISSUE_FIX_FEASIBILITY_PACKET_SCHEMA_VERSION = "issue_fix_feasibility_v0"
ISSUE_FIX_FEASIBILITY_OBSERVATION_SCHEMA_VERSION = (
    "issue_fix_feasibility_observation_v0"
)
ISSUE_FIX_FEASIBILITY_DECISION_SCHEMA_VERSION = "issue_fix_feasibility_decision_v0"

REPRODUCTION_STATES = {"confirmed", "planned", "missing", "blocked"}
SCOPE_CLASSES = {"bounded", "uncertain", "oversized"}
COMMENT_VALUES = {"none", "clarification", "diagnosis"}
RESOLUTION_ROUTES = {"fix_pr", "comment_only", "triage_only"}
EXTERNAL_ACTION_AUTHORITY_SCOPE_ALIASES = {
    "external_pr_creation": {"external_pr_creation", "publish"},
    "external_issue_comment": {"external_issue_comment", "publish"},
    "merge": {"merge"},
    "publish": {"publish"},
}


def _safe_label(value: str | None, *, field: str, required: bool = False) -> str | None:
    label = public_safe_compact_text(value, limit=220)
    if required and not label:
        raise ValueError(f"{field} must be a compact public-safe label")
    if value and not label:
        raise ValueError(f"{field} must not contain a local path or secret-like value")
    return label


def _route_decision(
    *,
    reproduction_status: str,
    scope_class: str,
    reproduction_label: str | None,
    validation_label: str | None,
    comment_value: str,
) -> tuple[str, list[str]]:
    fix_ready = bool(
        reproduction_status in {"confirmed", "planned"}
        and scope_class == "bounded"
        and reproduction_label
        and validation_label
    )
    if fix_ready:
        return "fix_pr", [
            f"reproduction_{reproduction_status}",
            "bounded_scope",
            "validation_surface_named",
        ]
    if comment_value != "none":
        return "comment_only", [
            f"comment_value_{comment_value}",
            f"reproduction_{reproduction_status}",
            f"scope_{scope_class}",
        ]
    return "triage_only", [
        f"reproduction_{reproduction_status}",
        f"scope_{scope_class}",
        "no_public_comment_value",
    ]


def _project_transition(
    *,
    route: str,
    repo: str,
    issue_ref: str,
    reproduction_status: str,
    boundary_authority_scopes: Sequence[str],
    boundary_authority_resolved: bool,
) -> dict[str, Any]:
    base = {
        "schema_version": "issue_fix_feasibility_transition_v0",
        "route": route,
        "would_write_todo": False,
        "external_write_performed": False,
    }
    if route == "fix_pr":
        action_kind = (
            "issue_fix_confirm_reproduction"
            if reproduction_status == "planned"
            else "issue_fix_branch_validation"
        )
        return base | {
            "decision": "runnable_successor",
            "projected_todo": {
                "schema_version": "loopx_todo_writeback_preview_v0",
                "role": "agent",
                "priority": "P0",
                "task_class": "advancement_task",
                "action_kind": action_kind,
                "text": (
                    f"[P0] Advance the selected fix_pr route for {repo} {issue_ref}; "
                    "confirm the named repro before patching, then run the named "
                    "validation surface."
                ),
                "would_write": False,
                "requires_execute_flag": True,
            },
            "external_write_gate": _project_external_write_gate(
                required_before=["external_pr_creation", "merge", "publish"],
                boundary_authority_scopes=boundary_authority_scopes,
                boundary_authority_resolved=boundary_authority_resolved,
            ),
            "no_followup": False,
        }
    if route == "comment_only":
        return base | {
            "decision": "runnable_successor",
            "projected_todo": {
                "schema_version": "loopx_todo_writeback_preview_v0",
                "role": "agent",
                "priority": "P1",
                "task_class": "advancement_task",
                "action_kind": "issue_fix_external_comment_packet",
                "text": (
                    f"[P1] Draft a compact public-safe maintainer comment for "
                    f"{repo} {issue_ref}; do not post it without an external-write gate."
                ),
                "would_write": False,
                "requires_execute_flag": True,
            },
            "external_write_gate": _project_external_write_gate(
                required_before=["external_issue_comment"],
                boundary_authority_scopes=boundary_authority_scopes,
                boundary_authority_resolved=boundary_authority_resolved,
            ),
            "no_followup": False,
        }
    return base | {
        "decision": "no_followup",
        "projected_todo": None,
        "external_write_gate": None,
        "no_followup": True,
    }


def _project_external_write_gate(
    *,
    required_before: Sequence[str],
    boundary_authority_scopes: Sequence[str],
    boundary_authority_resolved: bool,
) -> dict[str, Any]:
    active_scopes = {
        str(scope).strip()
        for scope in boundary_authority_scopes
        if str(scope).strip()
    }
    required = [str(action) for action in required_before]
    authorized = [
        action
        for action in required
        if EXTERNAL_ACTION_AUTHORITY_SCOPE_ALIASES.get(action, {action})
        & active_scopes
    ]
    blocked = [action for action in required if action not in authorized]
    return {
        "schema_version": "issue_fix_external_write_gate_v0",
        "required_before": required,
        "authorized_before": authorized,
        "blocked_before": blocked,
        "satisfied": not blocked,
        "authority_projection_resolved": boundary_authority_resolved,
        "authority_source": (
            "goal_checkpointed_boundary_authority"
            if boundary_authority_resolved
            else "not_available"
        ),
    }


def _repository_context_effect(context: Mapping[str, Any]) -> dict[str, Any]:
    coverage = context.get("coverage") if isinstance(context.get("coverage"), Mapping) else {}

    def refs_for(aspect: str) -> list[str]:
        row = coverage.get(aspect)
        return list(row.get("source_refs") or []) if isinstance(row, Mapping) else []

    return {
        "schema_version": "issue_fix_repository_context_effect_v0",
        "context_status": context.get("context_status"),
        "context_fingerprint": context.get("context_fingerprint"),
        "route_confidence": context.get("context_status"),
        "change_scope_evidence_refs": refs_for("change_scope"),
        "reproduction_evidence_refs": refs_for("reproduction"),
        "validation_evidence_refs": refs_for("validation"),
        "unresolved_required_aspects": list(
            context.get("unresolved_required_aspects") or []
        ),
        "expert_next_action": (
            context.get("expert_consultation") or {}
        ).get("next_action"),
        "route_overridden": False,
        "external_write_authorized": False,
    }


def build_issue_fix_feasibility_packet(
    *,
    repo: str = "public_repo_fixture",
    issue_ref: str = "issue_123_public_metadata_fixture",
    url: str | None = None,
    reproduction_status: str,
    scope_class: str,
    reproduction_label: str | None = None,
    validation_label: str | None = None,
    comment_value: str = "none",
    repository_context_input: Mapping[str, Any] | None = None,
    boundary_authority_scopes: Sequence[str] = (),
    boundary_authority_resolved: bool = False,
    generated_at: str | None = "2026-06-23T00:00:00Z",
) -> dict[str, Any]:
    """Select one issue-fix route from compact, public-safe agent observations."""

    if reproduction_status not in REPRODUCTION_STATES:
        raise ValueError(f"reproduction_status must be one of {sorted(REPRODUCTION_STATES)}")
    if scope_class not in SCOPE_CLASSES:
        raise ValueError(f"scope_class must be one of {sorted(SCOPE_CLASSES)}")
    if comment_value not in COMMENT_VALUES:
        raise ValueError(f"comment_value must be one of {sorted(COMMENT_VALUES)}")

    reference = normalise_github_issue_reference(
        repo=repo,
        issue_ref=issue_ref,
        url=url,
    )
    repository_context = build_issue_fix_repository_context_packet(
        repo=str(reference["repo"]),
        issue_ref=str(reference["issue_ref"]),
        context_input=repository_context_input,
        generated_at=generated_at,
    )
    safe_reproduction_label = _safe_label(
        reproduction_label,
        field="reproduction_label",
        required=reproduction_status in {"confirmed", "planned"},
    )
    safe_validation_label = _safe_label(
        validation_label,
        field="validation_label",
        required=False,
    )
    route, reason_codes = _route_decision(
        reproduction_status=reproduction_status,
        scope_class=scope_class,
        reproduction_label=safe_reproduction_label,
        validation_label=safe_validation_label,
        comment_value=comment_value,
    )
    reason_codes.append(
        f"repository_context_{repository_context['context_status']}"
    )
    observation = {
        "schema_version": ISSUE_FIX_FEASIBILITY_OBSERVATION_SCHEMA_VERSION,
        "repo": reference["repo"],
        "issue_ref": reference["issue_ref"],
        "kind": reference["kind"],
        "number": reference["number"],
        "permalink": reference["permalink"],
        "reproduction_status": reproduction_status,
        "reproduction_label": safe_reproduction_label,
        "scope_class": scope_class,
        "validation_label": safe_validation_label,
        "comment_value": comment_value,
        "repository_context": repository_context,
        "issue_body_captured": False,
        "comment_bodies_captured": False,
        "raw_logs_captured": False,
        "local_paths_captured": False,
    }
    transition = _project_transition(
        route=route,
        repo=str(reference["repo"]),
        issue_ref=str(reference["issue_ref"]),
        reproduction_status=reproduction_status,
        boundary_authority_scopes=boundary_authority_scopes,
        boundary_authority_resolved=boundary_authority_resolved,
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            {"observation": observation, "route": route},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    packet: dict[str, Any] = {
        "ok": True,
        "schema_version": ISSUE_FIX_FEASIBILITY_PACKET_SCHEMA_VERSION,
        "mode": "issue-fix-feasibility",
        "generated_at": generated_at,
        "observation": observation,
        "decision": {
            "schema_version": ISSUE_FIX_FEASIBILITY_DECISION_SCHEMA_VERSION,
            "route": route,
            "reason_codes": reason_codes,
            "observation_fingerprint": fingerprint,
        },
        "repository_context_effect": _repository_context_effect(repository_context),
        "transition": transition,
        "domain_state_projection": {
            "schema_version": "issue_fix_feasibility_domain_state_projection_v0",
            "domain_pack": "issue_fix",
            "stream": "feasibility",
            "key": {
                "repo": reference["repo"],
                "issue_ref": reference["issue_ref"],
            },
            "write_performed": False,
        },
        "external_reads_performed": False,
        "external_writes_performed": False,
        "todo_write_performed": False,
        "issue_body_captured": False,
        "comment_bodies_captured": False,
        "response_payloads_captured": False,
        "raw_logs_captured": False,
        "local_paths_captured": False,
        "destructive_git_used": False,
    }
    validation = validate_issue_fix_feasibility_packet(packet)
    packet["ok"] = validation["ok"]
    packet["validation"] = validation
    return packet


def validate_issue_fix_feasibility_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != ISSUE_FIX_FEASIBILITY_PACKET_SCHEMA_VERSION:
        errors.append("packet schema_version must be issue_fix_feasibility_v0")
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "todo_write_performed",
        "issue_body_captured",
        "comment_bodies_captured",
        "response_payloads_captured",
        "raw_logs_captured",
        "local_paths_captured",
        "destructive_git_used",
    ):
        if packet.get(key) is not False:
            errors.append(f"packet {key} must be false")

    observation = packet.get("observation")
    if not isinstance(observation, Mapping):
        errors.append("observation is required")
        observation = {}
    decision = packet.get("decision")
    if not isinstance(decision, Mapping):
        errors.append("decision is required")
        decision = {}
    route = decision.get("route")
    if route not in RESOLUTION_ROUTES:
        errors.append("decision route must select exactly one supported route")
    transition = packet.get("transition")
    if not isinstance(transition, Mapping):
        errors.append("transition is required")
        transition = {}
    if transition.get("route") != route:
        errors.append("transition route must match the selected route")
    repository_context = observation.get("repository_context")
    context_effect = packet.get("repository_context_effect")
    if repository_context is not None or context_effect is not None:
        if not isinstance(repository_context, Mapping):
            errors.append("observation repository_context must be an object when present")
            repository_context = {}
        if repository_context.get("ok") is not True:
            errors.append("observation repository_context must be valid")
        if not isinstance(context_effect, Mapping):
            errors.append("repository_context_effect must be an object when present")
            context_effect = {}
        if context_effect.get("context_fingerprint") != repository_context.get(
            "context_fingerprint"
        ):
            errors.append("repository context effect fingerprint must match observation")
        if context_effect.get("route_overridden") is not False:
            errors.append("repository context must not silently override feasibility route")
        if context_effect.get("external_write_authorized") is not False:
            errors.append("repository context must not authorize external writes")
    if route == "fix_pr":
        if observation.get("scope_class") != "bounded":
            errors.append("fix_pr requires bounded scope")
        if observation.get("reproduction_status") not in {"confirmed", "planned"}:
            errors.append("fix_pr requires confirmed or planned reproduction")
        if not observation.get("reproduction_label"):
            errors.append("fix_pr requires a named reproduction label")
        if not observation.get("validation_label"):
            errors.append("fix_pr requires a named validation label")
    if route == "comment_only" and observation.get("comment_value") == "none":
        errors.append("comment_only requires a useful comment value")
    if route == "triage_only" and transition.get("no_followup") is not True:
        errors.append("triage_only must project no_followup")
    gate = transition.get("external_write_gate")
    if route in {"fix_pr", "comment_only"}:
        if not isinstance(gate, Mapping):
            errors.append("runnable external-write route requires a gate projection")
        else:
            required = list(gate.get("required_before") or [])
            authorized = list(gate.get("authorized_before") or [])
            blocked = list(gate.get("blocked_before") or [])
            if (
                any(
                    (action in authorized) == (action in blocked)
                    for action in required
                )
                or any(action not in required for action in authorized + blocked)
            ):
                errors.append("external-write gate must partition required actions")
            if gate.get("satisfied") is not (not blocked):
                errors.append("external-write gate satisfied must match blocked actions")

    return {
        "ok": not errors,
        "schema_version": "issue_fix_feasibility_validation_v0",
        "errors": errors,
    }


def render_issue_fix_feasibility_markdown(payload: dict[str, Any]) -> str:
    observation = payload.get("observation") or {}
    decision = payload.get("decision") or {}
    transition = payload.get("transition") or {}
    return "\n".join(
        [
            "# LoopX Issue Fix Feasibility",
            "",
            f"- ok: `{payload.get('ok')}`",
            f"- repo: `{observation.get('repo')}`",
            f"- issue_ref: `{observation.get('issue_ref')}`",
            f"- reproduction_status: `{observation.get('reproduction_status')}`",
            f"- scope_class: `{observation.get('scope_class')}`",
            f"- route: `{decision.get('route')}`",
            f"- repository_context_status: "
            f"`{(payload.get('repository_context_effect') or {}).get('context_status')}`",
            f"- transition: `{transition.get('decision')}`",
            f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
            f"- domain_state_write_performed: "
            f"`{(payload.get('domain_state_projection') or {}).get('write_performed')}`",
        ]
    )
