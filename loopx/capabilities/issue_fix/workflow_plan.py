from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .acceptance_loop import build_issue_fix_caller_repo_branch_packet
from .intake_surface import build_content_ops_issue_fix_metadata_preview_packet


ISSUE_FIX_WORKFLOW_PLAN_PACKET_SCHEMA_VERSION = "issue_fix_workflow_plan_packet_v0"


def _todo_preview(
    *,
    planner_order: int,
    role: str,
    priority: str,
    task_class: str,
    action_kind: str,
    text: str,
    depends_on: Sequence[str],
    blocks: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "loopx_todo_writeback_preview_v0",
        "planner_order": planner_order,
        "command_preview": "loopx todo add",
        "role": role,
        "priority": priority,
        "status": "preview_only",
        "task_class": task_class,
        "action_kind": action_kind,
        "text": text,
        "depends_on": list(depends_on),
        "blocks": list(blocks or []),
        "would_write": False,
        "requires_execute_flag": True,
    }


def _branch_plan_from_dry_run(
    *,
    repo_path: str | None,
    repo: str,
    issue_ref: str,
    url: str | None,
    base_branch: str,
    issue_branch: str | None,
    validation_label: str,
    generated_at: str | None,
) -> dict[str, Any]:
    if not repo_path:
        return {
            "schema_version": "issue_fix_workflow_branch_plan_v0",
            "status": "needs_approved_repo_context",
            "repo_label": repo,
            "base_branch": base_branch,
            "issue_branch": issue_branch,
            "branch_ready": False,
            "repo_path_captured": False,
            "private_repo_state_read": False,
            "execute_required_for_branch_claim": True,
        }

    dry_run = build_issue_fix_caller_repo_branch_packet(
        repo_path=repo_path,
        repo=repo,
        issue_ref=issue_ref,
        url=url,
        base_branch=base_branch,
        issue_branch=issue_branch,
        validation_label=validation_label,
        execute=False,
        generated_at=generated_at,
    )
    branch = dry_run.get("caller_repo_branch")
    if not isinstance(branch, Mapping):
        raise ValueError("caller repo branch dry-run did not return branch metadata")
    return {
        "schema_version": "issue_fix_workflow_branch_plan_v0",
        "status": "approved_repo_dry_run",
        "repo_label": branch.get("repo_label"),
        "base_branch": branch.get("base_branch"),
        "issue_branch": branch.get("issue_branch"),
        "branch_action": branch.get("branch_action"),
        "branch_ready": False,
        "repo_path_captured": False,
        "private_repo_state_read": False,
        "execute_required_for_branch_claim": True,
        "dry_run_schema_version": dry_run.get("schema_version"),
    }


def build_issue_fix_workflow_plan_packet(
    *,
    repo: str = "public_repo_fixture",
    issue_ref: str = "issue_123_public_metadata_fixture",
    url: str | None = None,
    provider_payload: Mapping[str, Any] | None = None,
    fetch_metadata: bool = False,
    fetch_timeout_seconds: int = 10,
    repo_path: str | None = None,
    base_branch: str = "main",
    issue_branch: str | None = None,
    validation_label: str = "caller-declared validation",
    generated_at: str | None = "2026-06-23T00:00:00Z",
) -> dict[str, Any]:
    """Build a public-safe issue-fix workflow plan without writing state."""

    metadata_packet = build_content_ops_issue_fix_metadata_preview_packet(
        repo=repo,
        issue_ref=issue_ref,
        url=url,
        provider_payload=provider_payload,
        fetch_metadata=fetch_metadata,
        fetch_timeout_seconds=fetch_timeout_seconds,
        generated_at=generated_at,
    )
    metadata = metadata_packet["github_metadata_preview"]
    intake = metadata_packet["issue_fix_intake"]
    adapter_preview = metadata_packet["adapter_preview"]
    gated_fields = list(adapter_preview.get("gated_provider_fields_present") or [])
    branch_plan = _branch_plan_from_dry_run(
        repo_path=repo_path,
        repo=str(metadata["repo"]),
        issue_ref=str(metadata["issue_ref"]),
        url=url,
        base_branch=base_branch,
        issue_branch=issue_branch,
        validation_label=validation_label,
        generated_at=generated_at,
    )

    repo_label = str(metadata["repo"])
    issue_label = str(metadata["issue_ref"])
    agent_todos = [
        _todo_preview(
            planner_order=1,
            role="agent",
            priority="P0",
            task_class="advancement_task",
            action_kind="issue_fix_public_metadata_classification",
            text=(
                f"[P0] Classify {repo_label} {issue_label} from body-free public "
                "metadata and pick the first safe repro/code-context route."
            ),
            depends_on=[
                "content_ops_issue_fix_metadata_preview_packet_v0",
                "issue_fix_intake_v0",
            ],
        ),
        _todo_preview(
            planner_order=2,
            role="agent",
            priority="P0",
            task_class="advancement_task",
            action_kind="issue_fix_repro_and_route",
            text=(
                "[P0] Create or identify a focused repro smoke, inspect the "
                "selected repo-relative code route, and stop before private "
                "repro material or external comments."
            ),
            depends_on=["issue_fix_public_metadata_classification"],
        ),
        _todo_preview(
            planner_order=3,
            role="agent",
            priority="P0",
            task_class="advancement_task",
            action_kind="issue_fix_branch_validation",
            text=(
                "[P0] Prepare or claim the approved issue branch and run the "
                "caller-declared validation label before declaring review readiness."
            ),
            depends_on=["issue_fix_repro_and_route"],
            blocks=["pr_review_packet_ready"],
        ),
        _todo_preview(
            planner_order=4,
            role="agent",
            priority="P1",
            task_class="advancement_task",
            action_kind="issue_fix_pr_review_packet",
            text=(
                "[P1] Emit a PR review packet with repo-relative changed files, "
                "validation labels, remaining gates, and no external publication."
            ),
            depends_on=["issue_fix_branch_validation"],
        ),
    ]
    user_gates = [
        _todo_preview(
            planner_order=5,
            role="user",
            priority="P1",
            task_class="user_gate",
            action_kind="approve_external_issue_publish_or_merge",
            text=(
                "[P1] Approve any external issue comment, PR creation, merge, "
                "publish, or repository-policy exception before LoopX performs it."
            ),
            depends_on=["issue_fix_pr_review_packet"],
            blocks=[
                "external_issue_comment",
                "external_pr_creation",
                "merge",
                "publish",
            ],
        )
    ]
    if gated_fields:
        user_gates.insert(
            0,
            _todo_preview(
                planner_order=5,
                role="user",
                priority="P0",
                task_class="user_gate",
                action_kind="approve_github_issue_body_or_comment_read",
                text=(
                    "[P0] Approve a gated read before LoopX uses GitHub issue "
                    "body, comment bodies, timeline events, or raw provider payloads."
                ),
                depends_on=["content_ops_issue_fix_metadata_preview_packet_v0"],
                blocks=["private_repro_material_read", "raw_issue_body_read"],
            )
            | {"gated_fields": gated_fields},
        )
        for offset, gate in enumerate(user_gates, start=5):
            gate["planner_order"] = offset

    validation_plan = [
        {
            "schema_version": "issue_fix_validation_command_v0",
            "command_label": validation_label,
            "command_captured": False,
            "stdout_captured": False,
            "stderr_captured": False,
            "local_path_captured": False,
            "required_for_pr_review": True,
            "executed": False,
            "passed": False,
        }
    ]
    readiness_blockers = [
        "branch_not_executed",
        "validation_not_run",
        "repo_relative_changed_files_missing",
    ]
    if branch_plan["status"] == "needs_approved_repo_context":
        readiness_blockers.insert(0, "approved_repo_context_missing")
    review_packet_preview = {
        "schema_version": "issue_fix_pr_review_packet_v0",
        "ready": False,
        "readiness_blockers": readiness_blockers,
        "files_changed": [],
        "validation_commands": [validation_label],
        "external_issue_comment_performed": False,
        "external_pr_created": False,
        "merge_performed": False,
    }
    first_screen = {
        "waiting_on": "agent",
        "user_action_required": False,
        "agent_can_continue": True,
        "top_agent_todo": agent_todos[0],
        "top_gate": user_gates[0] if gated_fields else None,
        "next_safe_action": (
            "write the ordered LoopX todo plan only after the metadata preview "
            "stays body-free; then run branch/validation work inside the "
            "caller-approved repo context"
        ),
    }
    packet: dict[str, Any] = {
        "ok": True,
        "schema_version": ISSUE_FIX_WORKFLOW_PLAN_PACKET_SCHEMA_VERSION,
        "mode": "issue-fix-workflow-plan",
        "generated_at": generated_at,
        "metadata_preview_schema_version": metadata_packet["schema_version"],
        "issue_fix_intake_schema_version": intake.get("schema_version"),
        "issue_signal": {
            "repo": metadata["repo"],
            "issue_ref": metadata["issue_ref"],
            "kind": metadata["kind"],
            "state": metadata["state"],
            "labels": metadata["labels"],
            "body_captured": False,
            "comment_bodies_captured": False,
        },
        "first_screen": first_screen,
        "branch_plan": branch_plan,
        "ordered_loopx_todo_writeback_preview": agent_todos + user_gates,
        "validation_plan": validation_plan,
        "review_packet_preview": review_packet_preview,
        "external_reads_performed": bool(metadata_packet["external_reads_performed"]),
        "external_writes_performed": False,
        "issue_body_captured": False,
        "comment_bodies_captured": False,
        "response_payloads_captured": False,
        "local_paths_captured": False,
        "private_repo_state_read": False,
        "todo_write_performed": False,
        "destructive_git_used": False,
        "autopublish_allowed": False,
        "automerge_allowed": False,
        "next_safe_action": first_screen["next_safe_action"],
    }
    validation = validate_issue_fix_workflow_plan_packet(packet)
    packet["ok"] = bool(metadata_packet["ok"] and validation["ok"])
    packet["validation"] = validation
    return packet


def validate_issue_fix_workflow_plan_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if packet.get("schema_version") != ISSUE_FIX_WORKFLOW_PLAN_PACKET_SCHEMA_VERSION:
        errors.append("packet schema_version must be issue_fix_workflow_plan_packet_v0")
    for key in (
        "external_writes_performed",
        "issue_body_captured",
        "comment_bodies_captured",
        "response_payloads_captured",
        "local_paths_captured",
        "private_repo_state_read",
        "todo_write_performed",
        "destructive_git_used",
        "autopublish_allowed",
        "automerge_allowed",
    ):
        if packet.get(key) is not False:
            errors.append(f"packet {key} must be false")

    issue_signal = packet.get("issue_signal")
    if not isinstance(issue_signal, Mapping):
        errors.append("issue_signal is required")
        issue_signal = {}
    for key in ("repo", "issue_ref", "kind", "state"):
        if not issue_signal.get(key):
            errors.append(f"issue_signal {key} is required")
    if issue_signal.get("body_captured") is not False:
        errors.append("issue_signal body_captured must be false")
    if issue_signal.get("comment_bodies_captured") is not False:
        errors.append("issue_signal comment_bodies_captured must be false")

    branch_plan = packet.get("branch_plan")
    if not isinstance(branch_plan, Mapping):
        errors.append("branch_plan is required")
        branch_plan = {}
    if branch_plan.get("repo_path_captured") is not False:
        errors.append("branch_plan repo_path_captured must be false")
    if branch_plan.get("private_repo_state_read") is not False:
        errors.append("branch_plan private_repo_state_read must be false")

    previews = packet.get("ordered_loopx_todo_writeback_preview")
    if not isinstance(previews, Sequence) or isinstance(previews, (str, bytes)):
        errors.append("ordered_loopx_todo_writeback_preview must be a list")
        previews = []
    orders: list[int] = []
    roles = set()
    priorities = set()
    for preview in previews:
        if not isinstance(preview, Mapping):
            errors.append("todo preview entries must be objects")
            continue
        if preview.get("schema_version") != "loopx_todo_writeback_preview_v0":
            errors.append("todo preview has wrong schema")
        if preview.get("would_write") is not False:
            errors.append("todo preview would_write must be false")
        if preview.get("requires_execute_flag") is not True:
            errors.append("todo preview must require execute flag")
        order = preview.get("planner_order")
        if isinstance(order, int):
            orders.append(order)
        else:
            errors.append("todo preview planner_order must be an integer")
        roles.add(preview.get("role"))
        priorities.add(preview.get("priority"))
    if orders != sorted(orders):
        errors.append("todo previews must be ordered by planner_order")
    if "agent" not in roles:
        errors.append("at least one agent todo preview is required")
    if "P0" not in priorities:
        errors.append("at least one P0 todo preview is required")

    review = packet.get("review_packet_preview")
    if not isinstance(review, Mapping):
        errors.append("review_packet_preview is required")
        review = {}
    if review.get("schema_version") != "issue_fix_pr_review_packet_v0":
        errors.append("review packet preview has wrong schema")
    if review.get("ready") is not False:
        errors.append("workflow plan preview must not mark PR review ready")
    if review.get("external_issue_comment_performed") is not False:
        errors.append("review preview must not perform external issue comments")
    if review.get("external_pr_created") is not False:
        errors.append("review preview must not create PRs")
    if review.get("merge_performed") is not False:
        errors.append("review preview must not merge")

    return {
        "ok": not errors,
        "schema_version": "issue_fix_workflow_plan_validation_v0",
        "errors": errors,
        "todo_preview_count": len(previews),
        "user_gate_preview_count": sum(
            1
            for preview in previews
            if isinstance(preview, Mapping) and preview.get("role") == "user"
        ),
        "readiness_blocker_count": len(review.get("readiness_blockers") or []),
    }


def render_issue_fix_workflow_plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Issue Fix Workflow Plan",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- todo_write_performed: `{payload.get('todo_write_performed')}`",
        f"- local_paths_captured: `{payload.get('local_paths_captured')}`",
        f"- private_repo_state_read: `{payload.get('private_repo_state_read')}`",
    ]
    first_screen = payload.get("first_screen")
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
    issue_signal = payload.get("issue_signal")
    if isinstance(issue_signal, Mapping):
        lines.extend(
            [
                "",
                "## Issue Signal",
                "",
                f"- repo: `{issue_signal.get('repo')}`",
                f"- issue_ref: `{issue_signal.get('issue_ref')}`",
                f"- kind: `{issue_signal.get('kind')}`",
                f"- state: `{issue_signal.get('state')}`",
                f"- labels: `{issue_signal.get('labels')}`",
            ]
        )
    branch = payload.get("branch_plan")
    if isinstance(branch, Mapping):
        lines.extend(
            [
                "",
                "## Branch Plan",
                "",
                f"- status: `{branch.get('status')}`",
                f"- base_branch: `{branch.get('base_branch')}`",
                f"- issue_branch: `{branch.get('issue_branch')}`",
                f"- repo_path_captured: `{branch.get('repo_path_captured')}`",
                f"- execute_required_for_branch_claim: "
                f"`{branch.get('execute_required_for_branch_claim')}`",
            ]
        )
    todos = payload.get("ordered_loopx_todo_writeback_preview")
    if isinstance(todos, Sequence) and not isinstance(todos, (str, bytes)):
        lines.extend(["", "## Ordered Todo Writeback Preview", ""])
        for todo in todos:
            if isinstance(todo, Mapping):
                lines.append(
                    f"- `{todo.get('planner_order')}` `{todo.get('role')}` "
                    f"`{todo.get('priority')}` `{todo.get('action_kind')}`: "
                    f"would_write=`{todo.get('would_write')}`"
                )
    review = payload.get("review_packet_preview")
    if isinstance(review, Mapping):
        lines.extend(
            [
                "",
                "## PR Review Packet Preview",
                "",
                f"- ready: `{review.get('ready')}`",
                f"- readiness_blockers: `{review.get('readiness_blockers')}`",
                f"- external_pr_created: `{review.get('external_pr_created')}`",
                f"- merge_performed: `{review.get('merge_performed')}`",
            ]
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
                f"- todo_preview_count: `{validation.get('todo_preview_count')}`",
                f"- user_gate_preview_count: `{validation.get('user_gate_preview_count')}`",
                f"- readiness_blocker_count: `{validation.get('readiness_blocker_count')}`",
                f"- error_count: `{len(errors)}`",
            ]
        )
    if payload.get("error"):
        lines.extend(["", "## Error", "", str(payload.get("error"))])
    return "\n".join(lines) + "\n"
