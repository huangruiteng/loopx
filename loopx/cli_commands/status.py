from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..contract import check_contract, render_contract_markdown
from ..diagnose import collect_diagnosis, render_diagnosis_markdown
from ..handoff_budget import build_handoff_interface_budget
from ..quota import build_quota_should_run
from ..review_packet import build_review_packet, render_review_packet_markdown
from ..status import collect_status, render_status_markdown


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
        "--agent-id",
        help=(
            "Registered agent id for adding agent-lane next-action projection "
            "to matching status queue items."
        ),
    )

    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Build a LoopX diagnostic evidence packet for the user's agent to reason over.",
    )
    add_subcommand_format(diagnose_parser)
    diagnose_parser.add_argument("--goal-id", help="Goal id to diagnose. Defaults to the first attention item.")
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
        help="Generate a CLI-visible Review Packet from the current status contract.",
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
        payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            limit=max(0, args.limit),
        )
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
        if not isinstance(next_action, dict):
            continue
        item["agent_lane_next_action"] = next_action
        project_asset = item.get("project_asset")
        if isinstance(project_asset, dict):
            project_asset["agent_lane_next_action"] = next_action
        attached += 1
    if attached:
        payload["agent_lane_next_action_projection"] = {
            "schema_version": "agent_lane_next_action_projection_v0",
            "agent_id": safe_agent_id,
            "attached_count": attached,
            "preserves_goal_next_action": True,
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
        )
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
