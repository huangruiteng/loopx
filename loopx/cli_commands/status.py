from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..contract import check_contract, render_contract_markdown
from ..diagnose import collect_diagnosis, render_diagnosis_markdown
from ..handoff_budget import build_handoff_interface_budget
from ..quota import build_quota_should_run
from ..review_packet import build_review_packet, render_review_packet_markdown
from ..status import collect_status, render_status_markdown
from ..control_plane.runtime.status_projection_cache import (
    load_status_projection_cache,
    resolve_status_projection_cache_runtime_root,
    write_status_projection_cache,
)
from ..control_plane.todos.contract import normalize_todo_claimed_by


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _scan_roots(args: argparse.Namespace) -> list[Path]:
    scan_roots = [Path(item).expanduser() for item in args.scan_path]
    return scan_roots or [Path(args.scan_root).expanduser()]


def register_status_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    check_parser = subparsers.add_parser("check", help="Run a read-only contract and public/private boundary check.")
    check_parser.add_argument("--scan-root", default=".", help="Public files to scan for obvious private material.")
    check_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    check_parser.add_argument("--limit", type=int, default=5)

    status_parser = subparsers.add_parser("status", help="Show a first-screen goal status and attention queue.")
    add_subcommand_format(status_parser)
    status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    status_parser.add_argument("--limit", type=int, default=5)
    status_parser.add_argument(
        "--goal-id",
        help=(
            "Optional goal id to focus the status projection. The default remains "
            "the global dashboard/status view."
        ),
    )
    status_parser.add_argument(
        "--agent-id",
        help=(
            "Registered agent id for adding agent-lane next-action projection "
            "to matching status queue items."
        ),
    )
    status_parser.add_argument(
        "--include-task-graph",
        action="store_true",
        help=(
            "Include the optional task_graph_projection_v0 on status items. "
            "Default status output keeps this graph on the cold path to stay "
            "inside the dashboard hot-path budget."
        ),
    )
    status_parser.add_argument(
        "--use-projection-cache",
        action="store_true",
        help=(
            "Read a fresh status_projection_cache_v0 snapshot before running "
            "the full status collector. Misses and expired snapshots fall back "
            "to the full collector."
        ),
    )
    status_parser.add_argument(
        "--write-projection-cache",
        action="store_true",
        help="Write the collected status projection to the cache after a full collection.",
    )
    status_parser.add_argument(
        "--projection-cache-ttl-seconds",
        type=int,
        default=120,
        help="Freshness window for --use-projection-cache. Defaults to 120 seconds.",
    )

    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Build a LoopX diagnostic evidence packet for the user's agent to reason over.",
    )
    add_subcommand_format(diagnose_parser)
    diagnose_parser.add_argument("--goal-id", help="Goal id to diagnose. Defaults to the first attention item.")
    diagnose_parser.add_argument(
        "--agent-id",
        help=(
            "Registered agent id for identity-scoped quota/todo projection. "
            "Use this for multi-agent goals and heartbeat-driven diagnosis."
        ),
    )
    diagnose_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    diagnose_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    diagnose_parser.add_argument("--limit", type=int, default=5)

    review_packet_parser = subparsers.add_parser(
        "review-packet",
        help=(
            "Generate a CLI-visible Review Packet from the current status contract, "
            "including agent-scoped evidence-log read hints when available."
        ),
    )
    review_packet_parser.add_argument("--goal-id", required=True, help="Goal id to package for review or handoff.")
    review_packet_parser.add_argument(
        "--action-kind",
        choices=["reward", "controller", "codex", "evidence", "health"],
        help="Override inferred action kind. Defaults to the goal's current attention item.",
    )
    review_packet_parser.add_argument("--review-url", help="Optional dashboard review URL to include in the packet.")
    review_packet_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    review_packet_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    review_packet_parser.add_argument(
        "--handoff-only",
        action="store_true",
        help="Print only the target project-agent handoff in markdown output; JSON output returns a minimized handoff payload.",
    )
    review_packet_parser.add_argument(
        "--format",
        dest="review_packet_format",
        choices=["markdown", "json"],
        help="Output format for review-packet. This mirrors the global --format flag and may appear after the subcommand.",
    )
    review_packet_parser.add_argument(
        "--agent-id",
        help="Registered agent id for adding read-only agent-member status to the review packet.",
    )
    review_packet_parser.add_argument("--limit", type=int, default=5)


def review_packet_handoff_only_payload(payload: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "ok": bool(payload.get("ok")),
        "goal_id": payload.get("goal_id"),
        "handoff_only": True,
    }
    if not payload.get("ok"):
        result["error"] = payload.get("error")
        return result
    handoff_text = str(payload.get("project_agent_handoff") or "")
    raw_contract = payload.get("handoff_delivery_contract")
    agent_contract = raw_contract
    if isinstance(raw_contract, dict):
        agent_contract = {
            "mode": raw_contract.get("mode"),
            "instruction": raw_contract.get("instruction"),
            "minimum_scale": raw_contract.get("minimum_scale"),
            "must_include": raw_contract.get("must_include"),
            "if_blocked": raw_contract.get("if_blocked"),
        }
    handoff_budget = payload.get("handoff_interface_budget")
    if not isinstance(handoff_budget, dict):
        handoff_budget = build_handoff_interface_budget(handoff_text)
    result.update(
        {
            "kind": payload.get("kind"),
            "status": payload.get("status"),
            "waiting_on": payload.get("waiting_on"),
            "project_agent_command": payload.get("project_agent_command"),
            "project_agent_handoff": handoff_text,
            "handoff_text": handoff_text,
            "benchmark_report_chain_handoff": payload.get("benchmark_report_chain_handoff"),
            "project_agent_required_reads": payload.get("project_agent_required_reads") or [],
            "operator_gate_approved_handoff": payload.get("operator_gate_approved_handoff"),
            "connected_delivery_handoff": payload.get("connected_delivery_handoff"),
            "handoff_delivery_contract": agent_contract,
            "handoff_interface_budget": handoff_budget,
            "line_count": handoff_budget.get("line_count"),
            "char_count": handoff_budget.get("char_count"),
            "within_budget": handoff_budget.get("within_budget"),
        }
    )
    return result


def handle_check_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    allow_missing_registry: bool,
    print_payload: PrintPayload,
) -> int:
    try:
        payload = check_contract(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            limit=max(0, args.limit),
            allow_missing_registry=allow_missing_registry,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "registry": str(registry_path),
            "runtime_root": runtime_root_arg,
            "scan_roots": args.scan_path or [args.scan_root],
            "summary": {"errors": 1, "warnings": 0, "checks": 0},
            "errors": [str(exc)],
            "warnings": [],
            "checks": [],
        }
    print_payload(payload, args.format, render_contract_markdown)
    return 0 if payload.get("ok") else 1


def handle_status_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        scan_roots = _scan_roots(args)
        limit = max(0, args.limit)
        runtime_root = resolve_status_projection_cache_runtime_root(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
        )
        payload = None
        cache_metadata = None
        if args.use_projection_cache:
            payload, cache_metadata = load_status_projection_cache(
                registry_path=registry_path,
                runtime_root=runtime_root,
                scan_roots=scan_roots,
                limit=limit,
                include_task_graph=args.include_task_graph,
                goal_id=args.goal_id,
                max_age_seconds=args.projection_cache_ttl_seconds,
            )
        if payload is None:
            payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=runtime_root_arg,
                scan_roots=scan_roots,
                limit=limit,
                include_task_graph=args.include_task_graph,
                goal_id=args.goal_id,
            )
            if args.write_projection_cache:
                cache_metadata = write_status_projection_cache(
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    scan_roots=scan_roots,
                    limit=limit,
                    include_task_graph=args.include_task_graph,
                    goal_id=args.goal_id,
                    payload=payload,
                    max_age_seconds=args.projection_cache_ttl_seconds,
                )
                payload["projection_cache"] = cache_metadata
            elif cache_metadata:
                payload["projection_cache"] = cache_metadata
        if args.agent_id:
            attach_agent_lane_next_actions(payload, agent_id=args.agent_id)
    except Exception as exc:
        payload = {
            "ok": False,
            "registry": str(registry_path),
            "runtime_root": runtime_root_arg,
            "error": str(exc),
            "attention_queue": {
                "available": False,
                "item_count": 1,
                "needs_user_or_controller": 0,
                "needs_codex": 1,
                "watching_external_evidence": 0,
                "items": [
                    {
                        "goal_id": "loopx-status",
                        "status": "status_collection_failed",
                        "waiting_on": "codex",
                        "severity": "high",
                        "recommended_action": str(exc),
                        "source": "status",
                    }
                ],
            },
        }
    print_payload(payload, output_format(args), render_status_markdown)
    return 0 if payload.get("ok") else 1


def _compact_member_text(value: Any, *, limit: int = 180) -> str | None:
    if isinstance(value, list):
        compact = "; ".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, str):
        compact = value
    else:
        return None
    compact = " ".join(compact.split())
    if not compact or any(char in compact for char in "<>"):
        return None
    if len(compact) > limit:
        compact = compact[: limit - 1].rstrip() + "…"
    return compact


def _agent_profile_for(coordination: dict[str, Any], agent_id: str) -> dict[str, Any]:
    profiles = coordination.get("agent_profiles")
    if not isinstance(profiles, dict):
        return {}
    profile = profiles.get(agent_id)
    return profile if isinstance(profile, dict) else {}


def _profile_scope_summary(profile: dict[str, Any]) -> str | None:
    for key in (
        "scope_summary",
        "default_scope",
        "scope",
        "scope_summaries",
        "default_scopes",
        "scopes",
    ):
        summary = _compact_member_text(profile.get(key))
        if summary:
            return summary
    return None


def _profile_worktree_policy(profile: dict[str, Any]) -> tuple[str | None, bool | None]:
    policy = profile.get("worktree_policy")
    if isinstance(policy, dict):
        mode = _compact_member_text(policy.get("mode"), limit=80)
        requires = policy.get("requires_independent_worktree")
        return mode, requires if isinstance(requires, bool) else None
    return _compact_member_text(policy, limit=80), None


def _review_handoff_agent(
    *,
    coordination: dict[str, Any],
    profile: dict[str, Any],
    identity: dict[str, Any],
    role: str | None,
) -> str | None:
    review_policy = profile.get("review_policy")
    if isinstance(review_policy, dict):
        handoff_agent = normalize_todo_claimed_by(review_policy.get("handoff_agent"))
        if handoff_agent:
            return handoff_agent
    handoff_agent = normalize_todo_claimed_by(identity.get("handoff_agent"))
    if handoff_agent:
        return handoff_agent
    if role == "side-agent":
        return normalize_todo_claimed_by(coordination.get("side_agent_handoff_agent"))
    return None


def _current_claims_for_agent(item: dict[str, Any], *, agent_id: str) -> list[str]:
    claims: list[str] = []
    todo_sources: list[Any] = [item.get("agent_todos")]
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        todo_sources.append(project_asset.get("agent_todos"))
    for todos in todo_sources:
        if not isinstance(todos, dict):
            continue
        raw_items = todos.get("items") if isinstance(todos.get("items"), list) else []
        if not raw_items and isinstance(todos.get("first_open_items"), list):
            raw_items = todos.get("first_open_items") or []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict) or raw_item.get("done"):
                continue
            if normalize_todo_claimed_by(raw_item.get("claimed_by")) != agent_id:
                continue
            todo_id = str(raw_item.get("todo_id") or "").strip()
            if todo_id and todo_id not in claims:
                claims.append(todo_id)
    return claims


def _selected_claim_for_agent(guard: dict[str, Any], *, agent_id: str) -> str | None:
    next_action = guard.get("agent_lane_next_action")
    if not isinstance(next_action, dict):
        return None
    todo_id = str(next_action.get("todo_id") or "").strip()
    if not todo_id:
        return None
    lane_agent = normalize_todo_claimed_by(next_action.get("agent_id"))
    if lane_agent and lane_agent != agent_id:
        return None
    if next_action.get("claim_required_before_work") is True:
        return None
    claimed_by = normalize_todo_claimed_by(next_action.get("claimed_by"))
    selected_by = str(next_action.get("selected_by") or "").strip()
    if claimed_by == agent_id or selected_by == "current_agent_claimed_todo":
        return todo_id
    return None


def _current_claims_with_selected_lane(
    item: dict[str, Any],
    *,
    guard: dict[str, Any],
    agent_id: str,
) -> list[str]:
    claims = _current_claims_for_agent(item, agent_id=agent_id)
    selected_claim = _selected_claim_for_agent(guard, agent_id=agent_id)
    if not selected_claim:
        return claims
    claims = [claim for claim in claims if claim != selected_claim]
    return [selected_claim, *claims]


def _build_agent_member_projection(
    item: dict[str, Any],
    *,
    guard: dict[str, Any],
    agent_id: str,
) -> dict[str, Any] | None:
    identity = guard.get("agent_identity")
    if not isinstance(identity, dict):
        return None
    coordination = item.get("coordination") if isinstance(item.get("coordination"), dict) else {}
    profile = _agent_profile_for(coordination, agent_id)
    role = _compact_member_text(profile.get("role"), limit=80) or _compact_member_text(
        identity.get("role"),
        limit=80,
    )
    worktree_policy, requires_independent_worktree = _profile_worktree_policy(profile)
    claims = _current_claims_with_selected_lane(item, guard=guard, agent_id=agent_id)
    member: dict[str, Any] = {
        "schema_version": "agent_member_v0",
        "agent_id": agent_id,
        "role": role,
        "primary_agent": normalize_todo_claimed_by(identity.get("primary_agent")),
        "profile_source": "registry.coordination.agent_profiles" if profile else "quota.agent_identity",
        "authority_source": "registry+quota_should_run+todo_projection",
        "role_is_advisory": True,
        "current_claims": claims[:10],
        "current_claim_count": len(claims),
        "lease_projection": {
            "source": "todo.claimed_by",
            "hard_lease_available": False,
        },
    }
    scope_summary = _profile_scope_summary(profile)
    if scope_summary:
        member["scope_summary"] = scope_summary
    if worktree_policy:
        member["worktree_policy"] = worktree_policy
    if requires_independent_worktree is not None:
        member["requires_independent_worktree"] = requires_independent_worktree
    handoff_agent = _review_handoff_agent(
        coordination=coordination,
        profile=profile,
        identity=identity,
        role=role,
    )
    if handoff_agent:
        member["handoff_agent"] = handoff_agent
        member["review_handoff_status"] = "handoff_agent_configured"
    else:
        member["review_handoff_status"] = "no_agent_specific_handoff"
    review_policy = profile.get("review_policy")
    if isinstance(review_policy, dict):
        can_self_merge = review_policy.get("can_self_merge")
        if isinstance(can_self_merge, (bool, str)):
            member["can_self_merge"] = can_self_merge
    return member


def _agent_lane_text(next_action: dict[str, Any]) -> str | None:
    text = str(next_action.get("text") or next_action.get("title") or "").strip()
    return text or None


def _guard_allows_agent_lane_next_action(guard: dict[str, object]) -> bool:
    interaction = guard.get("interaction_contract")
    if not isinstance(interaction, dict):
        return False
    user_channel = interaction.get("user_channel")
    agent_channel = interaction.get("agent_channel")
    user_action_required = (
        bool(user_channel.get("action_required"))
        if isinstance(user_channel, dict)
        else False
    )
    agent_must_attempt = (
        bool(agent_channel.get("must_attempt"))
        if isinstance(agent_channel, dict)
        else False
    )
    return agent_must_attempt and not user_action_required


def _sync_status_item_next_action_from_agent_lane(
    item: dict[str, object],
    *,
    next_action: dict[str, Any],
    guard: dict[str, object],
) -> None:
    if item.get("status") not in {"connected_without_run", "active_state_agent_todo"}:
        return
    if not _guard_allows_agent_lane_next_action(guard):
        return
    text = _agent_lane_text(next_action)
    if not text:
        return
    item["recommended_action"] = text
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        project_asset["next_action"] = text
    goal_channel = item.get("goal_channel_projection")
    if isinstance(goal_channel, dict):
        goal_channel["next_action"] = text


def attach_agent_lane_next_actions(payload: dict[str, object], *, agent_id: str) -> dict[str, object]:
    safe_agent_id = str(agent_id or "").strip()
    if not safe_agent_id:
        return payload
    queue = payload.get("attention_queue")
    if not isinstance(queue, dict):
        return payload
    items = queue.get("items")
    if not isinstance(items, list):
        return payload
    attached = 0
    frontier_attached = 0
    hint_attached = 0
    goal_frontier_attached = 0
    member_attached = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "").strip()
        if not goal_id:
            continue
        try:
            guard = build_quota_should_run(payload, goal_id=goal_id, agent_id=safe_agent_id)
        except Exception:
            continue
        next_action = guard.get("agent_lane_next_action")
        project_asset = item.get("project_asset")
        changed = False
        if isinstance(next_action, dict):
            item["agent_lane_next_action"] = next_action
            if isinstance(project_asset, dict):
                project_asset["agent_lane_next_action"] = next_action
            _sync_status_item_next_action_from_agent_lane(
                item,
                next_action=next_action,
                guard=guard,
            )
            attached += 1
            changed = True
        frontier = guard.get("agent_scope_frontier")
        if isinstance(frontier, dict):
            item["agent_scope_frontier"] = frontier
            if isinstance(project_asset, dict):
                project_asset["agent_scope_frontier"] = frontier
            frontier_attached += 1
            changed = True
        frontier_hint = guard.get("agent_lane_frontier_hint")
        if isinstance(frontier_hint, dict):
            item["agent_lane_frontier_hint"] = frontier_hint
            if isinstance(project_asset, dict):
                project_asset["agent_lane_frontier_hint"] = frontier_hint
            hint_attached += 1
            changed = True
        goal_frontier = guard.get("goal_frontier_projection")
        if isinstance(goal_frontier, dict):
            item["goal_frontier_projection"] = goal_frontier
            if isinstance(project_asset, dict):
                project_asset["goal_frontier_projection"] = goal_frontier
            goal_frontier_attached += 1
            changed = True
        agent_member = _build_agent_member_projection(
            item,
            guard=guard,
            agent_id=safe_agent_id,
        )
        if isinstance(agent_member, dict):
            item["agent_member"] = agent_member
            if isinstance(project_asset, dict):
                project_asset["agent_member"] = agent_member
            member_attached += 1
            changed = True
        if not changed:
            continue
    if attached or frontier_attached or hint_attached or goal_frontier_attached or member_attached:
        payload["agent_lane_next_action_projection"] = {
            "schema_version": "agent_lane_next_action_projection_v0",
            "agent_id": safe_agent_id,
            "attached_count": attached,
            "frontier_attached_count": frontier_attached,
            "frontier_hint_attached_count": hint_attached,
            "goal_frontier_attached_count": goal_frontier_attached,
            "agent_member_attached_count": member_attached,
            "preserves_goal_next_action": True,
        }
    if member_attached:
        payload["agent_member_projection"] = {
            "schema_version": "agent_member_projection_v0",
            "agent_id": safe_agent_id,
            "attached_count": member_attached,
            "source": "registry+quota_should_run+todo_projection",
            "projection_is_authoritative": False,
        }
    return payload


def handle_diagnose_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        payload = collect_diagnosis(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            limit=max(1, args.limit),
            goal_id=args.goal_id,
            agent_id=args.agent_id,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "loopx_agent_diagnosis_packet_v0",
            "packet_kind": "agent_reasoning_evidence_packet",
            "agent_must_reason": True,
            "registry": str(registry_path),
            "runtime_root": runtime_root_arg,
            "error": str(exc),
            "selected": {
                "machine_signal": "diagnosis_collection_failed",
                "machine_signals_are_not_final_verdict": True,
                "recommended_action": (
                    "The agent should repair LoopX installation, registry path, or status collection "
                    "before making a delivery decision."
                ),
                "agent_reasoning_checklist": [
                    "Run or repair `loopx doctor`.",
                    "Verify the project registry path or connect the project.",
                    "Do not claim autonomous readiness until status and quota can be read.",
                ],
            },
        }
    print_payload(payload, output_format(args), render_diagnosis_markdown)
    return 0 if payload.get("ok") else 1


def handle_review_packet_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    selected_format = output_format(args, "review_packet_format")
    try:
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            limit=max(0, args.limit),
            include_task_graph=not args.handoff_only,
        )
        if args.agent_id:
            attach_agent_lane_next_actions(status_payload, agent_id=args.agent_id)
        payload = build_review_packet(
            status_payload,
            goal_id=args.goal_id,
            action_kind=args.action_kind,
            review_url=args.review_url,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "goal_id": args.goal_id,
            "error": str(exc),
        }
    if args.handoff_only:
        payload = review_packet_handoff_only_payload(payload)
    if args.handoff_only and selected_format != "json" and payload.get("ok"):
        print(str(payload.get("handoff_text") or ""))
    else:
        print_payload(payload, selected_format, render_review_packet_markdown)
    return 0 if payload.get("ok") else 1
