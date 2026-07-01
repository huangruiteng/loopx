from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from . import (
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
    AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    AUTO_RESEARCH_QUICKSTART_TEMPLATE,
    AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
    build_auto_research_board_projection,
    build_auto_research_demo_acceptance_packet,
    build_auto_research_demo_supervisor_plan,
    build_auto_research_quickstart,
    build_auto_research_rollout_events,
    build_live_auto_research_projection,
    build_auto_research_projection,
    load_auto_research_evidence_packet,
    load_auto_research_evidence_packet_inputs,
    load_auto_research_fixture,
    render_auto_research_markdown,
    run_builtin_lightweight_demo,
    run_auto_research_worker_turn,
)
from .demo_e2e import run_auto_research_demo_e2e
from .live_evidence import (
    LIVE_CODEX_E2E_DEFAULT_OUTPUT,
    capture_live_codex_e2e_evidence,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import (
    append_rollout_event,
    load_rollout_events,
    rollout_event_log_path,
)
from ...status import collect_status
from ...visible_multi_agent_launcher import execute_visible_multi_agent_launcher


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_auto_research_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    auto_research_parser = subparsers.add_parser(
        "auto-research",
        help="Project public-safe decentralized auto-research frontiers.",
    )
    auto_research_sub = auto_research_parser.add_subparsers(
        dest="auto_research_command",
        required=True,
    )
    quickstart_parser = auto_research_sub.add_parser(
        "quickstart",
        help="Preview or create a protected starter pack for decentralized auto-research.",
    )
    add_subcommand_format(quickstart_parser)
    quickstart_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id that should receive the first runnable hypothesis.",
    )
    quickstart_parser.add_argument(
        "--goal-id",
        default=AUTO_RESEARCH_DEFAULT_GOAL_ID,
        help="Research goal id for the generated contract.",
    )
    quickstart_parser.add_argument(
        "--objective",
        default=AUTO_RESEARCH_DEFAULT_OBJECTIVE,
        help="Compact public-safe research objective for the generated contract.",
    )
    quickstart_parser.add_argument(
        "--output-dir",
        default="auto_research_knn_pack",
        help="Relative output directory for --execute. Refuses to overwrite an existing pack.",
    )
    quickstart_parser.add_argument(
        "--template",
        choices=[AUTO_RESEARCH_QUICKSTART_TEMPLATE],
        default=AUTO_RESEARCH_QUICKSTART_TEMPLATE,
        help="Starter pack template.",
    )
    quickstart_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the starter pack. Omit for a read-only preview.",
    )

    frontier_parser = auto_research_sub.add_parser(
        "frontier",
        help="Render a per-agent decentralized research frontier from a public fixture or live LoopX state.",
    )
    add_subcommand_format(frontier_parser)
    frontier_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    frontier_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    frontier_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose runnable frontier should be projected.",
    )

    board_parser = auto_research_sub.add_parser(
        "board",
        help="Render a read-only Frontstage board packet from a fixture or live LoopX rollout projection.",
    )
    add_subcommand_format(board_parser)
    board_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    board_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    board_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose board/frontier should be projected.",
    )

    acceptance_parser = auto_research_sub.add_parser(
        "acceptance",
        help="Render an operator acceptance packet that links board output, dry-run supervisor, and takeover checks.",
    )
    add_subcommand_format(acceptance_parser)
    acceptance_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    acceptance_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    acceptance_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose board/frontier should be projected.",
    )
    acceptance_parser.add_argument(
        "--agent",
        action="append",
        default=[],
        help=(
            "Supervisor agent/lane pair as agent_id:lane_id. Repeat for each visible lane. "
            "Omit to use the default LoopX auto-research demo lane set."
        ),
    )
    acceptance_parser.add_argument(
        "--session-name",
        default="loopx-auto-research",
        help="Public-safe tmux session name for the dry-run supervisor packet.",
    )
    acceptance_parser.add_argument("--cli-bin", default="loopx", help="LoopX CLI executable name.")
    acceptance_parser.add_argument("--codex-bin", default="codex", help="Codex CLI executable name.")
    acceptance_parser.add_argument("--tmux-bin", default="tmux", help="tmux executable name.")
    acceptance_parser.add_argument(
        "--reasoning-effort",
        default="high",
        help="Reasoning effort passed to visible Codex lanes in the demo supervisor packet.",
    )

    evidence_parser = auto_research_sub.add_parser(
        "evidence",
        help="Build public-safe research hypothesis/evidence records from protected eval outputs.",
    )
    add_subcommand_format(evidence_parser)
    evidence_parser.add_argument("--contract", required=True, help="Path to research_contract_v0 JSON.")
    evidence_parser.add_argument(
        "--eval-result",
        action="append",
        required=True,
        help="Path to a protected evaluator JSON result. Repeat for dev/holdout or retry evidence.",
    )
    evidence_parser.add_argument("--hypothesis-id", required=True)
    evidence_parser.add_argument("--todo-id", required=True)
    evidence_parser.add_argument("--agent-id", required=True)
    evidence_parser.add_argument("--claimed-by", required=True)
    evidence_parser.add_argument("--mechanism-family", required=True)
    evidence_parser.add_argument("--hypothesis", required=True)
    evidence_parser.add_argument("--parent-hypothesis-id")
    evidence_parser.add_argument("--grounding-ref", action="append", default=[])
    evidence_parser.add_argument("--novelty-audit-ref")
    evidence_parser.add_argument("--branch-ref")
    evidence_parser.add_argument("--attempt-start", type=int, default=1)

    append_parser = auto_research_sub.add_parser(
        "append-evidence",
        help="Append an auto_research_evidence_packet_v0 into the LoopX rollout event log.",
    )
    add_subcommand_format(append_parser)
    append_parser.add_argument("--packet", required=True, help="Path to auto_research_evidence_packet_v0 JSON.")
    append_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rollout events without appending them.",
    )
    append_parser.add_argument(
        "--output",
        help="Write the append result JSON to this path without recording the path in LoopX state.",
    )

    live_evidence_parser = auto_research_sub.add_parser(
        "capture-live-evidence",
        help="Build compact public-safe live Codex E2E evidence after lane-authored evidence is appended.",
    )
    add_subcommand_format(live_evidence_parser)
    live_evidence_parser.add_argument(
        "--packet",
        required=True,
        help="Path to the public auto_research_evidence_packet_v0 JSON produced by a visible lane.",
    )
    live_evidence_parser.add_argument(
        "--append-result",
        required=True,
        help="Path to the JSON output from a real auto-research append-evidence run.",
    )
    live_evidence_parser.add_argument("--agent-id", required=True)
    live_evidence_parser.add_argument(
        "--lane-count",
        type=int,
        default=3,
        help="Accepted visible lane count to record in the compact live evidence.",
    )
    live_evidence_parser.add_argument(
        "--visible-lanes-accepted",
        action="store_true",
        help="Required acknowledgement that the visible lanes were launched and accepted.",
    )
    live_evidence_parser.add_argument(
        "--output",
        default=LIVE_CODEX_E2E_DEFAULT_OUTPUT,
        help="Output path for --execute. The path is not recorded in the evidence payload.",
    )
    live_evidence_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the compact evidence JSON to --output. Omit to preview the payload.",
    )

    worker_turn_parser = auto_research_sub.add_parser(
        "worker-turn",
        help="Run one LoopX-selected auto-research worker turn from quota/frontier.",
    )
    add_subcommand_format(worker_turn_parser)
    worker_turn_parser.add_argument("--agent-id", required=True)
    worker_turn_parser.add_argument(
        "--goal-id",
        default=AUTO_RESEARCH_DEFAULT_GOAL_ID,
        help="Research goal id whose quota/frontier this worker should obey.",
    )
    worker_turn_parser.add_argument(
        "--objective",
        default=AUTO_RESEARCH_DEFAULT_OBJECTIVE,
        help="Public-safe objective used only when the quickstart pack must be created.",
    )
    worker_turn_parser.add_argument(
        "--output-dir",
        default="auto_research_knn_pack",
        help="Quickstart pack directory inside the worker workspace.",
    )
    worker_turn_parser.add_argument(
        "--evidence-dir",
        default=".local/auto-research-worker",
        help="Local-only evidence output directory inside the worker workspace.",
    )
    worker_turn_parser.add_argument(
        "--lane-count",
        type=int,
        default=1,
        help="Visible lane count recorded when live evidence is captured.",
    )
    worker_turn_parser.add_argument(
        "--visible-lanes-accepted",
        action="store_true",
        help="Acknowledge that the visible lanes were launched and accepted.",
    )
    worker_turn_parser.add_argument(
        "--live-evidence-output",
        default=LIVE_CODEX_E2E_DEFAULT_OUTPUT,
        help="Local filename for compact public-safe live evidence.",
    )
    worker_turn_parser.add_argument(
        "--complete-selected-todo",
        action="store_true",
        help="After a successful --execute turn, mark the selected LoopX todo done.",
    )
    worker_turn_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the selected worker action. Omit to show the plan from quota/frontier.",
    )

    demo_supervisor_parser = auto_research_sub.add_parser(
        "demo-supervisor",
        help="Plan a dry-run tmux/Codex-CLI supervisor for decentralized auto-research lanes.",
    )
    add_subcommand_format(demo_supervisor_parser)
    demo_supervisor_parser.add_argument(
        "--goal-id",
        default=AUTO_RESEARCH_DEFAULT_GOAL_ID,
        help="Research goal id whose frontier each lane should inspect.",
    )
    demo_supervisor_parser.add_argument(
        "--agent",
        action="append",
        default=[],
        help=(
            "Agent/lane pair as agent_id:lane_id. Repeat for each visible lane. "
            "Omit to use the default LoopX auto-research demo lane set."
        ),
    )
    demo_supervisor_parser.add_argument(
        "--session-name",
        default="loopx-auto-research",
        help="Public-safe tmux session name for the generated dry-run script.",
    )
    demo_supervisor_parser.add_argument("--cli-bin", default="loopx", help="LoopX CLI executable name.")
    demo_supervisor_parser.add_argument("--codex-bin", default="codex", help="Codex CLI executable name.")
    demo_supervisor_parser.add_argument("--tmux-bin", default="tmux", help="tmux executable name.")
    demo_supervisor_parser.add_argument(
        "--reasoning-effort",
        default="high",
        help="Reasoning effort passed to visible Codex lanes through model_reasoning_effort.",
    )
    demo_supervisor_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually launch visible Codex CLI lanes. Omit for the default dry-run packet. "
            "This only starts local visible terminals; LoopX writeback still happens through normal lane commands."
        ),
    )
    demo_supervisor_parser.add_argument(
        "--launcher",
        choices=["auto", "tmux", "terminal"],
        default="auto",
        help="Visible process launcher for --execute. auto prefers tmux, then macOS Terminal.",
    )
    demo_supervisor_parser.add_argument(
        "--attach",
        action="store_true",
        help="After --execute with tmux, attach to the session. Terminal launcher opens visible windows directly.",
    )
    demo_supervisor_parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="With tmux launcher, kill an existing session with the same name before launching.",
    )
    demo_supervisor_parser.add_argument(
        "--workspace",
        help=(
            "Directory where visible Codex lanes should start. Defaults to the current directory. "
            "For demos, prefer an empty user-owned research workspace that shares LoopX state through "
            "--registry/--runtime-root."
        ),
    )
    demo_supervisor_parser.add_argument(
        "--create-workspace",
        action="store_true",
        help="Create --workspace when it does not already exist.",
    )

    demo_e2e_parser = auto_research_sub.add_parser(
        "demo-e2e",
        help=(
            "Run or preview the one-command multi-round k-NN research path and "
            "report board/acceptance truth boundaries."
        ),
    )
    add_subcommand_format(demo_e2e_parser)
    demo_e2e_parser.add_argument("--agent-id", required=True)
    demo_e2e_parser.add_argument(
        "--goal-id",
        default=AUTO_RESEARCH_DEFAULT_GOAL_ID,
        help="Research goal id for the positive demo evidence.",
    )
    demo_e2e_parser.add_argument(
        "--tracking-goal-id",
        help=(
            "Optional parent/productization goal id for status writeback context. "
            "Visible lanes still inspect --goal-id as the research frontier."
        ),
    )
    demo_e2e_parser.add_argument(
        "--objective",
        default=AUTO_RESEARCH_DEFAULT_OBJECTIVE,
        help="Compact public-safe research objective for the generated contract.",
    )
    demo_e2e_parser.add_argument(
        "--output-dir",
        default="auto_research_knn_pack",
        help="Relative output directory inside the temporary demo workspace.",
    )
    demo_e2e_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Run the lightweight multi-round protected-eval kernel, append public rollout evidence, "
            "and report measured dev/holdout gains. This still requires live evidence before "
            "claiming that visible Codex panes authored the result."
        ),
    )
    demo_e2e_parser.add_argument(
        "--launch-visible",
        action="store_true",
        help=(
            "With --execute, also launch the visible multi-lane supervisor. "
            "Visible panes alone do not make the multi-round kernel a live Codex E2E result."
        ),
    )
    demo_e2e_parser.add_argument(
        "--live-evidence",
        help=(
            "Path to compact public-safe live Codex lane evidence. "
            "Only this can flip live_codex_e2e.claim_allowed; raw transcripts are not read."
        ),
    )
    demo_e2e_parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep the temporary demo workspace after execution. The output payload still redacts its absolute path.",
    )
    demo_e2e_parser.add_argument(
        "--session-name",
        default="loopx-auto-research",
        help="Public-safe tmux session name when --launch-visible is set.",
    )
    demo_e2e_parser.add_argument("--cli-bin", default="loopx", help="LoopX CLI executable name.")
    demo_e2e_parser.add_argument("--codex-bin", default="codex", help="Codex CLI executable name.")
    demo_e2e_parser.add_argument("--tmux-bin", default="tmux", help="tmux executable name.")
    demo_e2e_parser.add_argument(
        "--reasoning-effort",
        default="high",
        help="Reasoning effort passed to visible Codex lanes through model_reasoning_effort.",
    )
    demo_e2e_parser.add_argument(
        "--launcher",
        choices=["auto", "tmux", "terminal"],
        default="auto",
        help="Visible process launcher for --launch-visible.",
    )
    demo_e2e_parser.add_argument(
        "--attach",
        action="store_true",
        help="After --launch-visible with tmux, attach to the session.",
    )
    demo_e2e_parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="With tmux launcher, kill an existing session with the same name before launching.",
    )
    demo_e2e_parser.add_argument(
        "--workspace",
        help="Directory where visible Codex lanes should start when --launch-visible is set.",
    )
    demo_e2e_parser.add_argument(
        "--create-workspace",
        action="store_true",
        help="Create --workspace when it does not already exist.",
    )

    lite_e2e_parser = auto_research_sub.add_parser(
        "lite-e2e",
        help="Run the lightweight two-round auto-research kernel demo.",
    )
    add_subcommand_format(lite_e2e_parser)
    lite_e2e_parser.add_argument(
        "--goal-id",
        default="loopx-auto-research-lite",
        help="Public-safe goal id for the lightweight demo result.",
    )


def _append_auto_research_rollout_events(
    *,
    packet_path: str,
    registry_path: Path,
    runtime_root_arg: str | None,
    dry_run: bool,
) -> dict[str, object]:
    packet = load_auto_research_evidence_packet(packet_path)
    goal_id = packet["research_contract"]["goal_id"]
    events = build_auto_research_rollout_events(packet)
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    log_path = rollout_event_log_path(runtime_root, goal_id)
    existing_ids = {
        str(event.get("event_id"))
        for event in load_rollout_events(log_path)
        if event.get("event_id")
    }
    appended_ids: list[str] = []
    skipped_ids: list[str] = []
    for event in events:
        event_id = str(event["event_id"])
        if event_id in existing_ids:
            skipped_ids.append(event_id)
            continue
        if not dry_run:
            append_rollout_event(log_path, event)
            existing_ids.add(event_id)
        appended_ids.append(event_id)
    counts_by_kind = Counter(str(event.get("event_kind") or "") for event in events)
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
        "goal_id": goal_id,
        "dry_run": dry_run,
        "event_count": len(events),
        "appended_count": 0 if dry_run else len(appended_ids),
        "would_append_count": len(appended_ids),
        "skipped_existing_count": len(skipped_ids),
        "event_ids": [str(event["event_id"]) for event in events],
        "appended_event_ids": [] if dry_run else appended_ids,
        "skipped_existing_event_ids": skipped_ids,
        "counts_by_kind": dict(sorted(counts_by_kind.items())),
        "packet_summary": packet["summary"],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "source": "loopx_rollout_event_log",
        },
    }


def _execute_auto_research_demo_supervisor(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    launcher: str,
    tmux_bin: str,
    cli_bin: str,
    codex_bin: str,
    attach: bool,
    replace_existing: bool,
    workspace: str | None,
    create_workspace: bool,
) -> dict[str, object]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    result, chosen, workspace_mode = execute_visible_multi_agent_launcher(
        payload=payload,
        registry=registry_path,
        runtime_root=runtime_root,
        requested_launcher=launcher,
        tmux_bin=tmux_bin,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
        attach=attach,
        replace_existing=replace_existing,
        workspace=workspace,
        create_workspace=create_workspace,
        cwd=Path.cwd(),
        launch_result_schema="auto_research_demo_launch_result_v0",
        acceptance_schema="auto_research_visible_launch_acceptance_v0",
        lane_default="research-lane",
        terminal_lane_label_template="[LoopX auto-research lane: {lane_id}]",
        frontier_or_blocker_markers=(
            "[LoopX auto-research frontier]",
            "[LoopX blocked reason]",
        ),
        frontier_or_blocker_status_markers=("frontier_or_blocked_reason=printed",),
    )
    payload["mode"] = "executed_visible_launch"
    payload["launch_result"] = result
    boundary = payload.get("boundary")
    if isinstance(boundary, dict):
        boundary.update(
            {
                "dry_run_plan_only": False,
                "starts_tmux": chosen == "tmux",
                "opens_terminal": chosen == "terminal",
                "runs_codex": True,
                "writes_loopx_state": False,
                "spends_loopx_quota": False,
                "external_service_call": False,
                "workspace_mode": workspace_mode,
                "workspace_write_scope": "user_selected_workspace_only",
                "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
                "shared_goal_surface": True,
                "all_lane_workspace_isolation": False,
                "mutation_isolation_policy": (
                    "only mutating evidence-runner attempts require a claimed git worktree "
                    "or equivalent execution boundary"
                ),
            }
        )
    return payload


def handle_auto_research_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.auto_research_command == "quickstart":
            payload = build_auto_research_quickstart(
                agent_id=args.agent_id,
                goal_id=args.goal_id,
                objective=args.objective,
                output_dir=args.output_dir,
                template=args.template,
                execute=args.execute,
                cwd=Path.cwd(),
            )
        elif args.auto_research_command in {"frontier", "board", "acceptance"}:
            if bool(args.fixture) == bool(args.goal_id):
                raise ValueError(f"auto-research {args.auto_research_command} requires exactly one of --fixture or --goal-id")
            if args.fixture:
                fixture = load_auto_research_fixture(args.fixture)
                payload = build_auto_research_projection(
                    fixture,
                    agent_id=args.agent_id,
                )
            else:
                status_payload = collect_status(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    scan_roots=[Path.cwd()],
                    limit=5,
                )
                quota_payload = build_quota_should_run(
                    status_payload,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                )
                registry = load_registry(registry_path)
                runtime_root = resolve_runtime_root(registry, runtime_root_arg)
                rollout_events = load_rollout_events(
                    rollout_event_log_path(runtime_root, args.goal_id)
                )
                payload = build_live_auto_research_projection(
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    quota_payload=quota_payload,
                    rollout_events=rollout_events,
                )
            if args.auto_research_command in {"board", "acceptance"}:
                payload = build_auto_research_board_projection(payload)
            if args.auto_research_command == "acceptance":
                supervisor = build_auto_research_demo_supervisor_plan(
                    goal_id=args.goal_id or payload["research_contract"]["goal_id"],
                    agent_specs=args.agent,
                    session_name=args.session_name,
                    cli_bin=args.cli_bin,
                    codex_bin=args.codex_bin,
                    tmux_bin=args.tmux_bin,
                    reasoning_effort=args.reasoning_effort,
                )
                payload = build_auto_research_demo_acceptance_packet(payload, supervisor)
        elif args.auto_research_command == "evidence":
            payload = load_auto_research_evidence_packet_inputs(
                contract_path=args.contract,
                eval_result_paths=args.eval_result,
                hypothesis_id=args.hypothesis_id,
                todo_id=args.todo_id,
                agent_id=args.agent_id,
                claimed_by=args.claimed_by,
                mechanism_family=args.mechanism_family,
                hypothesis=args.hypothesis,
                parent_hypothesis_id=args.parent_hypothesis_id,
                grounding_refs=args.grounding_ref,
                novelty_audit_ref=args.novelty_audit_ref,
                branch_ref=args.branch_ref,
                attempt_start=args.attempt_start,
            )
        elif args.auto_research_command == "append-evidence":
            payload = _append_auto_research_rollout_events(
                packet_path=args.packet,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                dry_run=args.dry_run,
            )
            if args.output:
                output_path = Path(args.output).expanduser()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        elif args.auto_research_command == "capture-live-evidence":
            payload = capture_live_codex_e2e_evidence(
                packet_path=args.packet,
                append_result_path=args.append_result,
                agent_id=args.agent_id,
                lane_count=args.lane_count,
                visible_lanes_accepted=args.visible_lanes_accepted,
            )
            if args.execute:
                output_path = Path(args.output).expanduser()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        elif args.auto_research_command == "worker-turn":
            def append_worker_evidence(packet_path: str) -> dict[str, object]:
                return _append_auto_research_rollout_events(
                    packet_path=packet_path,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    dry_run=False,
                )

            payload = run_auto_research_worker_turn(
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                objective=args.objective,
                workspace=Path.cwd(),
                output_dir=args.output_dir,
                evidence_dir=args.evidence_dir,
                execute=args.execute,
                append_evidence=append_worker_evidence if args.execute else None,
                lane_count=args.lane_count,
                visible_lanes_accepted=args.visible_lanes_accepted,
                live_evidence_output=args.live_evidence_output,
                complete_selected_todo=args.complete_selected_todo,
            )
        elif args.auto_research_command == "demo-supervisor":
            payload = build_auto_research_demo_supervisor_plan(
                goal_id=args.goal_id,
                agent_specs=args.agent,
                session_name=args.session_name,
                cli_bin=args.cli_bin,
                codex_bin=args.codex_bin,
                tmux_bin=args.tmux_bin,
                reasoning_effort=args.reasoning_effort,
            )
            if args.execute:
                payload = _execute_auto_research_demo_supervisor(
                    payload,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    launcher=args.launcher,
                    tmux_bin=args.tmux_bin,
                    cli_bin=args.cli_bin,
                    codex_bin=args.codex_bin,
                    attach=args.attach,
                    replace_existing=args.replace_existing,
                    workspace=args.workspace,
                    create_workspace=args.create_workspace,
                )
        elif args.auto_research_command == "demo-e2e":
            def append_demo_e2e_evidence(packet_path: str) -> dict[str, object]:
                return _append_auto_research_rollout_events(
                    packet_path=packet_path,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    dry_run=False,
                )

            visible_launcher: Callable[[dict[str, object], Path, str | None], dict[str, object]] | None = None
            if args.launch_visible:
                def visible_launcher(
                    supervisor: dict[str, object],
                    visible_registry_path: Path,
                    visible_runtime_root_arg: str | None,
                    default_workspace: Path,
                ) -> dict[str, object]:
                    workspace = args.workspace or str(default_workspace)
                    return _execute_auto_research_demo_supervisor(
                        supervisor,
                        registry_path=visible_registry_path,
                        runtime_root_arg=visible_runtime_root_arg,
                        launcher=args.launcher,
                        tmux_bin=args.tmux_bin,
                        cli_bin=args.cli_bin,
                        codex_bin=args.codex_bin,
                        attach=args.attach,
                        replace_existing=args.replace_existing,
                        workspace=workspace,
                        create_workspace=args.create_workspace,
                    )

            payload = run_auto_research_demo_e2e(
                agent_id=args.agent_id,
                goal_id=args.goal_id,
                tracking_goal_id=args.tracking_goal_id,
                objective=args.objective,
                output_dir=args.output_dir,
                execute=args.execute,
                launch_visible=args.launch_visible,
                keep_workspace=args.keep_workspace,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                session_name=args.session_name,
                cli_bin=args.cli_bin,
                codex_bin=args.codex_bin,
                tmux_bin=args.tmux_bin,
                reasoning_effort=args.reasoning_effort,
                live_evidence_path=args.live_evidence,
                append_evidence=append_demo_e2e_evidence,
                visible_launcher=visible_launcher,
            )
        elif args.auto_research_command == "lite-e2e":
            payload = run_builtin_lightweight_demo(goal_id=args.goal_id)
        else:
            raise ValueError(
                "auto-research requires the `quickstart`, `frontier`, `evidence`, "
                "`board`, `acceptance`, `append-evidence`, `capture-live-evidence`, "
                "`worker-turn`, `demo-supervisor`, `demo-e2e`, or `lite-e2e` subcommand"
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "auto-research",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_auto_research_markdown)
    return 0 if payload.get("ok") else 1
