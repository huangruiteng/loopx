from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .content_ops_surface import (
    EXPLORATION_PLAN_SCHEMA_VERSION,
    _as_mappings,
    _normalise_exploration_label,
    build_content_ops_exploration_plan_packet,
)


CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION = (
    "content_ops_issue_fix_intake_packet_v0"
)
CONTENT_OPS_ISSUE_FIX_METADATA_PREVIEW_PACKET_SCHEMA_VERSION = (
    "content_ops_issue_fix_metadata_preview_packet_v0"
)
ISSUE_FIX_INTAKE_SCHEMA_VERSION = "issue_fix_intake_v0"
GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION = "github_issue_metadata_preview_v0"

ALLOWED_ISSUE_FIX_INTAKE_STATES = {"open", "closed", "unknown"}
ALLOWED_ISSUE_FIX_ROUTE_STATUSES = {"candidate", "blocked_until_gate", "selected"}
GITHUB_BODY_OR_COMMENT_KEYS = {
    "body",
    "body_text",
    "comments",
    "comment_bodies",
    "timeline",
    "events",
    "raw",
    "response_payload",
}


def _normalise_github_issue_reference(
    *,
    repo: str | None = None,
    issue_ref: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    if url:
        parsed = urlsplit(str(url).strip())
        if parsed.scheme != "https":
            raise ValueError("GitHub issue URL must use https")
        if parsed.username or parsed.password:
            raise ValueError("GitHub issue URL must not include credentials")
        host = (parsed.hostname or "").lower().rstrip(".")
        if host != "github.com":
            raise ValueError("GitHub issue URL must use github.com")
        if parsed.query or parsed.fragment:
            raise ValueError("GitHub issue URL must not include query or fragment data")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 4 or parts[2] not in {"issues", "pull"}:
            raise ValueError("GitHub issue URL must look like /owner/repo/issues/123")
        if not parts[3].isdigit():
            raise ValueError("GitHub issue or PR number must be numeric")
        repo_label = _normalise_exploration_label(f"{parts[0]}/{parts[1]}", "repo")
        issue_label = f"{parts[2]}_{parts[3]}"
        permalink = urlunsplit(("https", "github.com", "/" + "/".join(parts), "", ""))
        return {
            "repo": repo_label,
            "issue_ref": issue_label,
            "kind": "pull_request" if parts[2] == "pull" else "issue",
            "number": int(parts[3]),
            "permalink": permalink,
        }

    repo_label = _normalise_exploration_label(repo, "repo")
    issue_label = _normalise_exploration_label(issue_ref, "issue_ref")
    number = None
    digits = "".join(ch for ch in issue_label if ch.isdigit())
    if digits:
        number = int(digits)
    return {
        "repo": repo_label,
        "issue_ref": issue_label,
        "kind": "issue",
        "number": number,
        "permalink": None,
    }


def _provider_payload_labels(payload: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    raw_labels = payload.get("labels")
    if not isinstance(raw_labels, Sequence) or isinstance(raw_labels, (str, bytes)):
        return labels
    for item in raw_labels:
        if isinstance(item, Mapping):
            label = _normalise_exploration_label(item.get("name"), "label")
        else:
            label = _normalise_exploration_label(item, "label")
        if label and label not in labels:
            labels.append(label)
    return labels[:12]


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _github_metadata_from_provider_payload(
    *,
    reference: Mapping[str, Any],
    provider_payload: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    payload = provider_payload or {}
    gated_keys = sorted(
        str(key) for key in payload if str(key).lower() in GITHUB_BODY_OR_COMMENT_KEYS
    )
    labels = _provider_payload_labels(payload) or ["needs-triage"]
    state = str(payload.get("state") or "unknown").strip().lower()
    if state not in ALLOWED_ISSUE_FIX_INTAKE_STATES:
        state = "unknown"
    number = _safe_int(payload.get("number"))
    if number is None:
        number = reference.get("number") if isinstance(reference.get("number"), int) else None
    comments_count = _safe_int(payload.get("comments_count"))
    if comments_count is None:
        comments_count = _safe_int(payload.get("comments"))
    metadata = {
        "schema_version": GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION,
        "provider": "github",
        "provider_mode": "mocked_metadata" if provider_payload else "reference_only",
        "repo": reference["repo"],
        "issue_ref": reference["issue_ref"],
        "kind": payload.get("kind") or reference["kind"],
        "number": number,
        "state": state,
        "title_summary": (
            _normalise_exploration_label(payload.get("title"), "title")
            if payload.get("title")
            else "public GitHub issue metadata preview"
        ),
        "labels": labels,
        "updated_at": _normalise_exploration_label(payload.get("updated_at"), "updated_at")
        if payload.get("updated_at")
        else None,
        "author_association": _normalise_exploration_label(
            payload.get("author_association"),
            "author_association",
        )
        if payload.get("author_association")
        else "unknown",
        "comments_count": comments_count,
        "permalink": reference.get("permalink"),
        "body_captured": False,
        "comment_bodies_captured": False,
        "response_payload_captured": False,
        "local_path_captured": False,
        "private_repo_state_read": False,
        "gated_provider_fields_present": gated_keys,
    }
    return metadata, gated_keys


def build_content_ops_issue_fix_intake_packet(
    *,
    repo: str = "public_repo_fixture",
    issue_ref: str = "issue_123_public_metadata_fixture",
    issue_state: str = "open",
    generated_at: str | None = "2026-06-23T00:00:00Z",
) -> dict[str, Any]:
    """Build a fixture-only issue-fix intake packet from public metadata."""

    repo_label = _normalise_exploration_label(repo, "repo")
    issue_label = _normalise_exploration_label(issue_ref, "issue_ref")
    if issue_state not in ALLOWED_ISSUE_FIX_INTAKE_STATES:
        allowed = sorted(ALLOWED_ISSUE_FIX_INTAKE_STATES)
        raise ValueError(f"issue_state must be one of {allowed}")

    exploration_packet = build_content_ops_exploration_plan_packet(
        scenario="repo_issue_fix_intake",
        generated_at=generated_at,
    )
    exploration_plan = exploration_packet["exploration_plan"]
    selected_lane = next(
        lane
        for lane in exploration_plan["selected_source_lanes"]
        if lane.get("lane_id") == "repo_issue_public_metadata"
    )
    issue_metadata = {
        "schema_version": "public_issue_metadata_fixture_v0",
        "repo": repo_label,
        "issue_ref": issue_label,
        "source_kind": "github_issue_or_pr",
        "source_status": "public",
        "state": issue_state,
        "metadata_fields_present": [
            "repository",
            "number_or_ref",
            "title_summary",
            "labels",
            "state",
            "updated_at",
        ],
        "title_summary": (
            "public metadata fixture for a reproducible repo issue needing "
            "code-context routing"
        ),
        "labels": ["bug", "needs-repro", "loopx-scenario"],
        "body_captured": False,
        "comment_bodies_captured": False,
        "response_payload_captured": False,
        "local_path_captured": False,
        "private_repo_state_read": False,
    }
    code_context_routes = [
        {
            "schema_version": "code_context_route_v0",
            "route_id": "route_reproduction_surface",
            "status": "selected",
            "source": "public issue labels and title metadata",
            "candidate_path_globs": ["examples/**", "tests/**", "loopx/**"],
            "suggested_commands": [
                "rg -n '<public error symbol>' examples tests loopx",
                "python3 <focused smoke path>",
            ],
            "requires_private_repo_state": False,
            "reads_private_material": False,
            "confidence": "medium",
        },
        {
            "schema_version": "code_context_route_v0",
            "route_id": "route_owner_or_component_inference",
            "status": "candidate",
            "source": "public labels and changed-file metadata when available",
            "candidate_path_globs": ["docs/**", "loopx/**", "scripts/**"],
            "suggested_commands": [
                "rg -n '<public component label>' docs loopx scripts",
                "git log --oneline -- <candidate path glob>",
            ],
            "requires_private_repo_state": False,
            "reads_private_material": False,
            "confidence": "low",
        },
    ]
    agent_todo_candidates = [
        {
            "schema_version": "agent_todo_candidate_v0",
            "role": "agent",
            "priority": "P1",
            "action_kind": "issue_fix_repro_smoke",
            "title": "Create or identify a focused failing smoke from public issue metadata.",
            "depends_on": ["repo_issue_public_metadata"],
            "validation_surface": "failing smoke, no-repro note, or fixture blocker",
            "stop_condition": "stop before external issue comments or private source reads",
        },
        {
            "schema_version": "agent_todo_candidate_v0",
            "role": "agent",
            "priority": "P1",
            "action_kind": "issue_fix_code_context_route",
            "title": "Inspect candidate code paths and propose the smallest safe fix route.",
            "depends_on": ["route_reproduction_surface"],
            "validation_surface": "code route and test command recorded",
            "stop_condition": "stop before destructive git or production actions",
        },
        {
            "schema_version": "agent_todo_candidate_v0",
            "role": "agent",
            "priority": "P2",
            "action_kind": "issue_fix_pr_ready_patch",
            "title": "Patch behind a focused smoke and prepare reviewable PR evidence.",
            "depends_on": ["issue_fix_repro_smoke", "issue_fix_code_context_route"],
            "validation_surface": "focused smoke passes and public/private scan is clean",
            "stop_condition": "stop before merge if repository policy requires review",
        },
    ]
    gate_projections = [
        {
            "schema_version": "issue_fix_gate_projection_v0",
            "gate_id": "owner_triage_gate",
            "role": "owner",
            "status": "not_required_for_metadata_intake",
            "action_required": False,
            "question": (
                "Assign or confirm an owner only if public metadata cannot infer "
                "a safe component route."
            ),
            "safe_without_gate": [
                "public metadata fixture intake",
                "local public-code search",
                "focused smoke drafting",
            ],
            "blocks": ["external issue comment", "owner assignment", "merge promotion"],
        },
        {
            "schema_version": "issue_fix_gate_projection_v0",
            "gate_id": "private_repro_material_gate",
            "role": "user",
            "status": "conditional",
            "action_required": False,
            "question": (
                "If the issue requires private logs or repro material, provide "
                "a compact public-safe repro label or approve a gated private read."
            ),
            "safe_without_gate": [
                "metadata-only triage",
                "public fixture smoke",
                "code-context route proposal",
            ],
            "blocks": [
                "private log read",
                "private repo state read",
                "raw repro material quote",
            ],
        },
    ]
    first_screen = {
        "waiting_on": "agent",
        "user_action_required": False,
        "agent_can_continue": True,
        "top_agent_todo": agent_todo_candidates[0],
        "top_gate": None,
        "next_safe_action": (
            "turn the public issue metadata fixture into a focused repro smoke "
            "and code-context route; do not comment externally or read private "
            "repro material"
        ),
    }
    intake = {
        "schema_version": ISSUE_FIX_INTAKE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "issue_metadata": issue_metadata,
        "selected_exploration_lane": selected_lane,
        "code_context_routes": code_context_routes,
        "agent_todo_candidates": agent_todo_candidates,
        "gate_projections": gate_projections,
        "first_screen": first_screen,
        "boundary": {
            "external_reads_performed": False,
            "external_writes_performed": False,
            "issue_body_captured": False,
            "comment_bodies_captured": False,
            "response_payloads_captured": False,
            "local_paths_captured": False,
            "private_repo_state_read": False,
            "automerge_allowed": False,
        },
        "truth_contract": {
            "metadata_fixture_is_source_of_truth": True,
            "issue_body_is_not_source_of_truth": True,
            "candidate_todos_require_loopx_todo_writeback": True,
            "external_issue_actions_require_owner_gate": True,
            "private_repro_material_requires_user_gate": True,
        },
    }
    packet: dict[str, Any] = {
        "ok": True,
        "schema_version": CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION,
        "mode": "content-ops-issue-fix-intake",
        "exploration_plan_schema_version": EXPLORATION_PLAN_SCHEMA_VERSION,
        "issue_fix_intake": intake,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "private_source_bodies_read": False,
        "private_source_content_read": False,
        "local_paths_captured": False,
        "autopublish_allowed": False,
        "automerge_allowed": False,
        "next_safe_action": first_screen["next_safe_action"],
    }
    validation = validate_content_ops_issue_fix_intake_packet(packet)
    packet["ok"] = bool(validation["ok"])
    packet["validation"] = validation
    return packet


def build_content_ops_issue_fix_metadata_preview_packet(
    *,
    repo: str | None = "public_repo_fixture",
    issue_ref: str | None = "issue_123_public_metadata_fixture",
    url: str | None = None,
    provider_payload: Mapping[str, Any] | None = None,
    generated_at: str | None = "2026-06-23T00:00:00Z",
) -> dict[str, Any]:
    """Build a mocked GitHub metadata adapter preview for issue-fix intake."""

    reference = _normalise_github_issue_reference(
        repo=repo,
        issue_ref=issue_ref,
        url=url,
    )
    metadata, gated_keys = _github_metadata_from_provider_payload(
        reference=reference,
        provider_payload=provider_payload,
    )
    intake_packet = build_content_ops_issue_fix_intake_packet(
        repo=metadata["repo"],
        issue_ref=metadata["issue_ref"],
        issue_state=str(metadata["state"]),
        generated_at=generated_at,
    )
    intake = dict(intake_packet["issue_fix_intake"])
    intake["issue_metadata"] = metadata

    candidate_todo_writeback_preview = [
        {
            "schema_version": "loopx_todo_writeback_preview_v0",
            "command_preview": "loopx todo add",
            "role": "agent",
            "status": "preview_only",
            "task_class": "advancement_task",
            "action_kind": "issue_fix_public_metadata_triage",
            "claimed_by": "codex-product-capability",
            "text": (
                "[P2] Triage public GitHub metadata for "
                f"{metadata['repo']} {metadata['issue_ref']}: create or identify "
                "a focused repro smoke, then inspect the code-context route."
            ),
            "would_write": False,
            "requires_execute_flag": True,
        }
    ]
    gated_field_todos = []
    if gated_keys:
        gated_field_todos.append(
            {
                "schema_version": "loopx_todo_writeback_preview_v0",
                "command_preview": "loopx todo add",
                "role": "user",
                "status": "preview_only",
                "task_class": "user_gate",
                "action_kind": "approve_github_issue_body_or_comment_read",
                "text": (
                    "Approve a gated read before LoopX uses GitHub issue body, "
                    "comment bodies, timeline events, or raw provider payloads."
                ),
                "gated_fields": gated_keys,
                "would_write": False,
                "requires_execute_flag": True,
            }
        )

    adapter_preview = {
        "schema_version": "github_issue_metadata_adapter_preview_v0",
        "adapter": "github_issue_metadata",
        "provider": "mock",
        "input_mode": "mocked_provider_payload" if provider_payload else "reference_only",
        "live_read_performed": False,
        "live_read_allowed_by_default": False,
        "default_allowed_fields": [
            "repo",
            "issue_ref",
            "kind",
            "number",
            "state",
            "title_summary",
            "labels",
            "updated_at",
            "author_association",
            "comments_count",
            "permalink",
        ],
        "gated_provider_fields_present": gated_keys,
        "candidate_loopx_todo_writeback_preview": (
            candidate_todo_writeback_preview + gated_field_todos
        ),
    }
    intake["adapter_preview"] = adapter_preview
    intake["first_screen"] = {
        "waiting_on": "agent",
        "user_action_required": False,
        "agent_can_continue": True,
        "top_agent_todo": candidate_todo_writeback_preview[0],
        "top_gate": gated_field_todos[0] if gated_field_todos else None,
        "next_safe_action": (
            "review the mocked public GitHub metadata preview, then write the "
            "candidate LoopX agent todo only after metadata fields stay body-free"
        ),
    }
    intake["boundary"] = {
        "external_reads_performed": False,
        "external_writes_performed": False,
        "issue_body_captured": False,
        "comment_bodies_captured": False,
        "response_payloads_captured": False,
        "local_paths_captured": False,
        "private_repo_state_read": False,
        "todo_write_performed": False,
        "automerge_allowed": False,
    }
    packet: dict[str, Any] = {
        "ok": True,
        "schema_version": CONTENT_OPS_ISSUE_FIX_METADATA_PREVIEW_PACKET_SCHEMA_VERSION,
        "mode": "content-ops-issue-fix-metadata-preview",
        "exploration_plan_schema_version": EXPLORATION_PLAN_SCHEMA_VERSION,
        "issue_fix_intake_schema_version": ISSUE_FIX_INTAKE_SCHEMA_VERSION,
        "issue_fix_intake": intake,
        "github_metadata_preview": metadata,
        "adapter_preview": adapter_preview,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "private_source_bodies_read": False,
        "private_source_content_read": False,
        "local_paths_captured": False,
        "todo_write_performed": False,
        "autopublish_allowed": False,
        "automerge_allowed": False,
        "next_safe_action": intake["first_screen"]["next_safe_action"],
    }
    validation = validate_content_ops_issue_fix_metadata_preview_packet(packet)
    packet["ok"] = bool(validation["ok"])
    packet["validation"] = validation
    return packet


def validate_content_ops_issue_fix_intake_packet(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION:
        errors.append("packet schema_version must be content_ops_issue_fix_intake_packet_v0")
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "private_source_bodies_read",
        "private_source_content_read",
        "local_paths_captured",
        "autopublish_allowed",
        "automerge_allowed",
    ):
        if packet.get(key) is not False:
            errors.append(f"packet {key} must be false")

    intake = packet.get("issue_fix_intake")
    if not isinstance(intake, Mapping):
        errors.append("issue_fix_intake is required")
        intake = {}
    if intake.get("schema_version") != ISSUE_FIX_INTAKE_SCHEMA_VERSION:
        errors.append("issue_fix_intake schema_version must be issue_fix_intake_v0")

    issue_metadata = (
        intake.get("issue_metadata")
        if isinstance(intake.get("issue_metadata"), Mapping)
        else {}
    )
    if issue_metadata.get("source_status") != "public":
        errors.append("issue metadata source_status must be public")
    if issue_metadata.get("source_kind") != "github_issue_or_pr":
        errors.append("issue metadata source_kind must be github_issue_or_pr")
    if issue_metadata.get("state") not in ALLOWED_ISSUE_FIX_INTAKE_STATES:
        errors.append("issue metadata state is invalid")
    for key in (
        "body_captured",
        "comment_bodies_captured",
        "response_payload_captured",
        "local_path_captured",
        "private_repo_state_read",
    ):
        if issue_metadata.get(key) is not False:
            errors.append(f"issue metadata {key} must be false")

    selected_lane = (
        intake.get("selected_exploration_lane")
        if isinstance(intake.get("selected_exploration_lane"), Mapping)
        else {}
    )
    if selected_lane.get("lane_id") != "repo_issue_public_metadata":
        errors.append("selected exploration lane must be repo_issue_public_metadata")
    if selected_lane.get("requires_user_gate") is not False:
        errors.append("public issue metadata lane must not require a user gate")

    routes = _as_mappings(intake.get("code_context_routes"))  # type: ignore[arg-type]
    todos = _as_mappings(intake.get("agent_todo_candidates"))  # type: ignore[arg-type]
    gates = _as_mappings(intake.get("gate_projections"))  # type: ignore[arg-type]
    if not routes:
        errors.append("at least one code_context_route_v0 is required")
    if not todos:
        errors.append("at least one agent_todo_candidate_v0 is required")
    if not gates:
        errors.append("at least one gate projection is required")

    for route in routes:
        route_id = str(route.get("route_id") or "").strip()
        if route.get("schema_version") != "code_context_route_v0":
            errors.append(f"route {route_id or '?'} has wrong schema")
        if route.get("status") not in ALLOWED_ISSUE_FIX_ROUTE_STATUSES:
            errors.append(f"route {route_id or '?'} has invalid status")
        if route.get("requires_private_repo_state") is not False:
            errors.append(f"route {route_id or '?'} must not require private repo state")
        if route.get("reads_private_material") is not False:
            errors.append(f"route {route_id or '?'} must not read private material")
        for glob in route.get("candidate_path_globs") or []:
            text = str(glob)
            if text.startswith("/") or "\\Users\\" in text or "/Users/" in text:
                errors.append(f"route {route_id or '?'} must use repo-relative globs")

    for todo in todos:
        if todo.get("schema_version") != "agent_todo_candidate_v0":
            errors.append(f"todo {todo.get('action_kind')} has wrong schema")
        if todo.get("role") != "agent":
            errors.append(f"todo {todo.get('action_kind')} must be role=agent")
        if not str(todo.get("action_kind") or "").strip():
            errors.append("todo action_kind is required")
        if not str(todo.get("validation_surface") or "").strip():
            errors.append(f"todo {todo.get('action_kind')} needs validation_surface")

    for gate in gates:
        if gate.get("schema_version") != "issue_fix_gate_projection_v0":
            errors.append(f"gate {gate.get('gate_id')} has wrong schema")
        if gate.get("action_required") is not False:
            errors.append(f"gate {gate.get('gate_id')} should be conditional/nonblocking")
        if not isinstance(gate.get("safe_without_gate"), Sequence) or isinstance(
            gate.get("safe_without_gate"), (str, bytes)
        ):
            errors.append(f"gate {gate.get('gate_id')} needs safe_without_gate list")

    first_screen = (
        intake.get("first_screen")
        if isinstance(intake.get("first_screen"), Mapping)
        else {}
    )
    if first_screen.get("waiting_on") != "agent":
        errors.append("first_screen.waiting_on must be agent")
    if first_screen.get("user_action_required") is not False:
        errors.append("first_screen.user_action_required must be false")
    if first_screen.get("agent_can_continue") is not True:
        errors.append("first_screen.agent_can_continue must be true")

    boundary = (
        intake.get("boundary") if isinstance(intake.get("boundary"), Mapping) else {}
    )
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "issue_body_captured",
        "comment_bodies_captured",
        "response_payloads_captured",
        "local_paths_captured",
        "private_repo_state_read",
        "automerge_allowed",
    ):
        if boundary.get(key) is not False:
            errors.append(f"boundary.{key} must be false")

    return {
        "schema_version": "content_ops_issue_fix_intake_validation_v0",
        "ok": not errors,
        "errors": errors,
        "route_count": len(routes),
        "agent_todo_candidate_count": len(todos),
        "gate_projection_count": len(gates),
    }


def validate_content_ops_issue_fix_metadata_preview_packet(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if (
        packet.get("schema_version")
        != CONTENT_OPS_ISSUE_FIX_METADATA_PREVIEW_PACKET_SCHEMA_VERSION
    ):
        errors.append(
            "packet schema_version must be "
            "content_ops_issue_fix_metadata_preview_packet_v0"
        )
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "private_source_bodies_read",
        "private_source_content_read",
        "local_paths_captured",
        "todo_write_performed",
        "autopublish_allowed",
        "automerge_allowed",
    ):
        if packet.get(key) is not False:
            errors.append(f"packet {key} must be false")

    metadata = (
        packet.get("github_metadata_preview")
        if isinstance(packet.get("github_metadata_preview"), Mapping)
        else {}
    )
    if metadata.get("schema_version") != GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION:
        errors.append(
            "github_metadata_preview schema_version must be "
            "github_issue_metadata_preview_v0"
        )
    for key in GITHUB_BODY_OR_COMMENT_KEYS:
        if key in metadata:
            errors.append(f"github metadata must not include raw field {key}")
    for key in (
        "body_captured",
        "comment_bodies_captured",
        "response_payload_captured",
        "local_path_captured",
        "private_repo_state_read",
    ):
        if metadata.get(key) is not False:
            errors.append(f"github metadata {key} must be false")

    adapter_preview = (
        packet.get("adapter_preview")
        if isinstance(packet.get("adapter_preview"), Mapping)
        else {}
    )
    if adapter_preview.get("provider") != "mock":
        errors.append("adapter preview provider must be mock")
    if adapter_preview.get("live_read_performed") is not False:
        errors.append("adapter preview live_read_performed must be false")
    if adapter_preview.get("live_read_allowed_by_default") is not False:
        errors.append("adapter preview live_read_allowed_by_default must be false")

    todo_previews = _as_mappings(
        adapter_preview.get("candidate_loopx_todo_writeback_preview")  # type: ignore[arg-type]
    )
    if not todo_previews:
        errors.append("at least one todo writeback preview is required")
    for todo in todo_previews:
        if todo.get("schema_version") != "loopx_todo_writeback_preview_v0":
            errors.append(f"todo preview {todo.get('action_kind')} has wrong schema")
        if todo.get("would_write") is not False:
            errors.append(f"todo preview {todo.get('action_kind')} must not write")
        if todo.get("requires_execute_flag") is not True:
            errors.append(
                f"todo preview {todo.get('action_kind')} must require execute flag"
            )

    intake = (
        packet.get("issue_fix_intake")
        if isinstance(packet.get("issue_fix_intake"), Mapping)
        else {}
    )
    boundary = (
        intake.get("boundary") if isinstance(intake.get("boundary"), Mapping) else {}
    )
    for key in (
        "external_reads_performed",
        "external_writes_performed",
        "issue_body_captured",
        "comment_bodies_captured",
        "response_payloads_captured",
        "local_paths_captured",
        "private_repo_state_read",
        "todo_write_performed",
        "automerge_allowed",
    ):
        if boundary.get(key) is not False:
            errors.append(f"boundary.{key} must be false")
    first_screen = (
        intake.get("first_screen")
        if isinstance(intake.get("first_screen"), Mapping)
        else {}
    )
    if first_screen.get("waiting_on") != "agent":
        errors.append("first_screen.waiting_on must be agent")
    if first_screen.get("user_action_required") is not False:
        errors.append("first_screen.user_action_required must be false")
    if first_screen.get("agent_can_continue") is not True:
        errors.append("first_screen.agent_can_continue must be true")

    return {
        "schema_version": "content_ops_issue_fix_metadata_preview_validation_v0",
        "ok": not errors,
        "errors": errors,
        "metadata_field_count": len(metadata),
        "gated_provider_field_count": len(
            metadata.get("gated_provider_fields_present") or []
        ),
        "todo_writeback_preview_count": len(todo_previews),
    }


def render_content_ops_issue_fix_metadata_preview_markdown(
    payload: dict[str, Any],
) -> str:
    lines = [
        "# LoopX Repo Issue Fix Metadata Preview",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- todo_write_performed: `{payload.get('todo_write_performed')}`",
        f"- private_source_bodies_read: `{payload.get('private_source_bodies_read')}`",
        f"- local_paths_captured: `{payload.get('local_paths_captured')}`",
        f"- automerge_allowed: `{payload.get('automerge_allowed')}`",
    ]
    metadata = payload.get("github_metadata_preview")
    if isinstance(metadata, Mapping):
        lines.extend(
            [
                "",
                "## GitHub Metadata Preview",
                "",
                f"- repo: `{metadata.get('repo')}`",
                f"- issue_ref: `{metadata.get('issue_ref')}`",
                f"- kind: `{metadata.get('kind')}`",
                f"- state: `{metadata.get('state')}`",
                f"- labels: `{metadata.get('labels')}`",
                f"- gated_provider_fields_present: "
                f"`{metadata.get('gated_provider_fields_present')}`",
                f"- body_captured: `{metadata.get('body_captured')}`",
                f"- comment_bodies_captured: "
                f"`{metadata.get('comment_bodies_captured')}`",
            ]
        )
    adapter = payload.get("adapter_preview")
    if isinstance(adapter, Mapping):
        todos = adapter.get("candidate_loopx_todo_writeback_preview")
        lines.extend(
            [
                "",
                "## Adapter Preview",
                "",
                f"- provider: `{adapter.get('provider')}`",
                f"- input_mode: `{adapter.get('input_mode')}`",
                f"- live_read_performed: `{adapter.get('live_read_performed')}`",
                f"- live_read_allowed_by_default: "
                f"`{adapter.get('live_read_allowed_by_default')}`",
            ]
        )
        if isinstance(todos, Sequence) and not isinstance(todos, (str, bytes)):
            lines.extend(["", "## Todo Writeback Preview", ""])
            for todo in todos:
                if isinstance(todo, Mapping):
                    lines.append(
                        f"- `{todo.get('role')}` `{todo.get('action_kind')}`: "
                        f"would_write=`{todo.get('would_write')}`"
                    )
    validation = payload.get("validation")
    if isinstance(validation, Mapping):
        errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
        lines.extend(
            [
                "",
                "## Validation",
                "",
                f"- validation_ok: `{validation.get('ok')}`",
                f"- gated_provider_field_count: "
                f"`{validation.get('gated_provider_field_count')}`",
                f"- todo_writeback_preview_count: "
                f"`{validation.get('todo_writeback_preview_count')}`",
                f"- error_count: `{len(errors)}`",
            ]
        )
    if payload.get("error"):
        lines.extend(["", "## Error", "", str(payload.get("error"))])
    return "\n".join(lines) + "\n"


def render_content_ops_issue_fix_intake_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Repo Issue Fix Intake",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- private_source_bodies_read: `{payload.get('private_source_bodies_read')}`",
        f"- local_paths_captured: `{payload.get('local_paths_captured')}`",
        f"- automerge_allowed: `{payload.get('automerge_allowed')}`",
    ]
    intake = payload.get("issue_fix_intake")
    if isinstance(intake, Mapping):
        first_screen = intake.get("first_screen")
        if isinstance(first_screen, Mapping):
            lines.extend(
                [
                    "",
                    "## First Screen",
                    "",
                    f"- waiting_on: `{first_screen.get('waiting_on')}`",
                    f"- user_action_required: `{first_screen.get('user_action_required')}`",
                    f"- agent_can_continue: `{first_screen.get('agent_can_continue')}`",
                    f"- next_safe_action: {first_screen.get('next_safe_action')}",
                ]
            )
        issue_metadata = intake.get("issue_metadata")
        if isinstance(issue_metadata, Mapping):
            lines.extend(
                [
                    "",
                    "## Issue Metadata",
                    "",
                    f"- repo: `{issue_metadata.get('repo')}`",
                    f"- issue_ref: `{issue_metadata.get('issue_ref')}`",
                    f"- state: `{issue_metadata.get('state')}`",
                    f"- labels: `{issue_metadata.get('labels')}`",
                    f"- body_captured: `{issue_metadata.get('body_captured')}`",
                ]
            )
        routes = intake.get("code_context_routes")
        if isinstance(routes, Sequence) and not isinstance(routes, (str, bytes)):
            lines.extend(["", "## Code Context Routes", ""])
            for route in routes:
                if isinstance(route, Mapping):
                    lines.append(
                        f"- `{route.get('route_id')}`: status=`{route.get('status')}`, "
                        f"confidence=`{route.get('confidence')}`"
                    )
        todos = intake.get("agent_todo_candidates")
        if isinstance(todos, Sequence) and not isinstance(todos, (str, bytes)):
            lines.extend(["", "## Agent Todo Candidates", ""])
            for todo in todos:
                if isinstance(todo, Mapping):
                    lines.append(
                        f"- `{todo.get('priority')}` `{todo.get('action_kind')}`: "
                        f"{todo.get('title')}"
                    )
        gates = intake.get("gate_projections")
        if isinstance(gates, Sequence) and not isinstance(gates, (str, bytes)):
            lines.extend(["", "## Gate Projections", ""])
            for gate in gates:
                if isinstance(gate, Mapping):
                    lines.append(
                        f"- `{gate.get('gate_id')}`: role=`{gate.get('role')}`, "
                        f"action_required=`{gate.get('action_required')}`"
                    )
    validation = payload.get("validation")
    if isinstance(validation, Mapping):
        errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
        lines.extend(
            [
                "",
                "## Validation",
                "",
                f"- validation_ok: `{validation.get('ok')}`",
                f"- route_count: `{validation.get('route_count')}`",
                f"- agent_todo_candidate_count: `{validation.get('agent_todo_candidate_count')}`",
                f"- gate_projection_count: `{validation.get('gate_projection_count')}`",
                f"- error_count: `{len(errors)}`",
            ]
        )
    if payload.get("error"):
        lines.extend(["", "## Error", "", str(payload.get("error"))])
    return "\n".join(lines) + "\n"
