from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bootstrap import (
    DEFAULT_DOMAIN,
    DEFAULT_OBJECTIVE,
    bootstrap_project,
    render_bootstrap_markdown,
)
from .contract import check_contract, render_contract_markdown
from .feedback import append_human_reward, compact_reward, render_reward_markdown
from .history import collect_history, load_registry, render_history_markdown
from .paths import default_registry_path, resolve_runtime_root
from .project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    build_new_project_prompt,
    render_new_project_prompt_markdown,
)
from .registry import inspect_registry, render_registry_markdown
from .status import collect_status, render_status_markdown
from .status_server import (
    DEFAULT_STATUS_HOST,
    DEFAULT_STATUS_PATH,
    DEFAULT_STATUS_PORT,
    serve_status,
)


def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Goal Harness control-plane helper.")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = sub.add_parser(
        "bootstrap",
        aliases=["connect"],
        help="Create or connect a project-local registry and active goal state.",
    )
    bootstrap_parser.add_argument("--project", default=".", help="Project directory to connect.")
    bootstrap_parser.add_argument("--goal-id", help="Stable goal id. Defaults to <project-name>-goal.")
    bootstrap_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE, help="Initial goal objective.")
    bootstrap_parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Goal domain label.")
    bootstrap_parser.add_argument("--role", choices=["controller", "subagent"], default="controller")
    bootstrap_parser.add_argument("--parent-goal-id", help="Parent goal id when --role subagent.")
    bootstrap_parser.add_argument("--state-file", help="Active goal state path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--adapter-kind", default="generic_project_goal_v0")
    bootstrap_parser.add_argument("--adapter-status", default="connected")
    bootstrap_parser.add_argument("--next-probe", help="Optional project-specific pre-tick command.")
    bootstrap_parser.add_argument("--spawn-allowed", action="store_true", help="Declare that this controller may spawn child agents.")
    bootstrap_parser.add_argument("--max-children", type=int, default=3)
    bootstrap_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    bootstrap_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")
    bootstrap_parser.add_argument("--claim-ttl-minutes", type=int, default=30)
    bootstrap_parser.add_argument("--force", action="store_true", help="Replace existing goal entry or state file.")
    bootstrap_parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")

    prompt_parser = sub.add_parser(
        "new-project-prompt",
        help="Generate a copy-paste Codex prompt for connecting a project from a goal document.",
    )
    prompt_parser.add_argument("--project", required=True, help="Project directory the target Codex session can access.")
    prompt_parser.add_argument("--goal-doc", required=True, help="Goal document path for the target project.")
    prompt_parser.add_argument("--goal-id", help="Initial stable goal id. Defaults to <project-name>-goal.")
    prompt_parser.add_argument("--objective", help="Initial objective. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--domain", help="Initial domain label. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--adapter-kind", default=DEFAULT_HANDOFF_ADAPTER_KIND)
    prompt_parser.add_argument("--adapter-status", default=DEFAULT_HANDOFF_ADAPTER_STATUS)
    prompt_parser.add_argument("--next-probe", help="Optional read-only pre-tick command for the target project.")
    prompt_parser.add_argument("--spawn-allowed", action="store_true", help="Include controller/sub-agent flags.")
    prompt_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    prompt_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")

    sub.add_parser("registry", help="Inspect registry goals and adapter declarations.")

    history_parser = sub.add_parser("history", help="Read compact run history from the shared runtime root.")
    history_parser.add_argument("--goal-id", help="Only show one goal.")
    history_parser.add_argument("--limit", type=int, default=10)

    reward_parser = sub.add_parser(
        "reward",
        help="Append a compact human reward overlay to a goal run index.",
    )
    reward_parser.add_argument("--goal-id", required=True, help="Goal id whose latest run should receive feedback.")
    reward_parser.add_argument(
        "--run-generated-at",
        help="Exact run generated_at timestamp. Defaults to the latest compact run for the goal.",
    )
    reward_parser.add_argument("--recorded-at", help="Reward timestamp. Defaults to current UTC time.")
    reward_parser.add_argument("--decision", required=True, help="Operator decision label, such as continue_route.")
    reward_parser.add_argument(
        "--reward",
        required=True,
        choices=["positive", "negative", "mixed", "neutral"],
        help="Compact reward polarity.",
    )
    reward_parser.add_argument(
        "--reason-summary",
        required=True,
        help="Short public-safe reason. Do not include raw private evidence.",
    )
    reward_parser.add_argument("--follow-up", help="Optional next handoff or experiment condition.")
    reward_parser.add_argument("--dry-run", action="store_true", help="Print the overlay without appending it.")

    check_parser = sub.add_parser("check", help="Run a read-only contract and public/private boundary check.")
    check_parser.add_argument("--scan-root", default=".", help="Public files to scan for obvious private material.")
    check_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    check_parser.add_argument("--limit", type=int, default=5)

    status_parser = sub.add_parser("status", help="Show a first-screen goal status and attention queue.")
    status_parser.add_argument("--scan-root", default=".", help="Public files to scan for obvious private material.")
    status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    status_parser.add_argument("--limit", type=int, default=5)

    serve_status_parser = sub.add_parser("serve-status", help="Serve live status JSON for the local dashboard.")
    serve_status_parser.add_argument("--host", default=DEFAULT_STATUS_HOST, help="Bind host. Defaults to localhost only.")
    serve_status_parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    serve_status_parser.add_argument("--path", default=DEFAULT_STATUS_PATH, help="Status JSON route.")
    serve_status_parser.add_argument("--scan-root", default=".", help="Public files to scan for obvious private material.")
    serve_status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    serve_status_parser.add_argument("--limit", type=int, default=5)
    serve_status_parser.add_argument("--verbose", action="store_true", help="Print HTTP request logs.")

    args = parser.parse_args(argv)
    registry_path = Path(args.registry).expanduser()

    if args.command in {"bootstrap", "connect"}:
        try:
            runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
            state_file = Path(args.state_file).expanduser() if args.state_file else None
            payload = bootstrap_project(
                project=Path(args.project),
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                objective=args.objective,
                domain=args.domain,
                role=args.role,
                parent_goal_id=args.parent_goal_id,
                state_file=state_file,
                adapter_kind=args.adapter_kind,
                adapter_status=args.adapter_status,
                next_probe=args.next_probe,
                spawn_allowed=args.spawn_allowed,
                max_children=args.max_children,
                allowed_domains=args.allowed_domain,
                write_scope=args.write_scope,
                claim_ttl_minutes=args.claim_ttl_minutes,
                force=args.force,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_bootstrap_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "new-project-prompt":
        payload = build_new_project_prompt(
            project=Path(args.project),
            goal_doc=Path(args.goal_doc),
            goal_id=args.goal_id,
            objective=args.objective,
            domain=args.domain,
            adapter_kind=args.adapter_kind,
            adapter_status=args.adapter_status,
            next_probe=args.next_probe,
            spawn_allowed=bool(args.spawn_allowed),
            allowed_domains=args.allowed_domain,
            write_scope=args.write_scope,
        )
        print_payload(payload, args.format, render_new_project_prompt_markdown)
        return 0

    if args.command == "registry":
        payload = inspect_registry(registry_path)
        print_payload(payload, args.format, render_registry_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "history":
        try:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = collect_history(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_history_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "reward":
        try:
            reward = compact_reward(
                recorded_at=args.recorded_at,
                decision=args.decision,
                reward=args.reward,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
            )
            payload = append_human_reward(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                run_generated_at=args.run_generated_at,
                reward=reward,
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_reward_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "check":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            payload = check_contract(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "scan_roots": args.scan_path or [args.scan_root],
                "summary": {"errors": 1, "warnings": 0, "checks": 0},
                "errors": [str(exc)],
                "warnings": [],
                "checks": [],
            }
        print_payload(payload, args.format, render_contract_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "status":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
                "attention_queue": {
                    "available": False,
                    "item_count": 1,
                    "needs_user_or_controller": 0,
                    "needs_codex": 1,
                    "watching_external_evidence": 0,
                    "items": [
                        {
                            "goal_id": "goal-harness-status",
                            "status": "status_collection_failed",
                            "waiting_on": "codex",
                            "severity": "high",
                            "recommended_action": str(exc),
                            "source": "status",
                        }
                    ],
                },
            }
        print_payload(payload, args.format, render_status_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "serve-status":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            serve_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                host=args.host,
                port=args.port,
                status_path=args.path,
                verbose=bool(args.verbose),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
