#!/usr/bin/env python3
"""Serve the LoopX SkillsBench local ACP relay over stdio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
)
from loopx.benchmark_case_state import BENCHMARK_CASE_LOOPX_TODO_ID  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Local Codex CLI binary used outside dry-run mode.",
    )
    parser.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
        help="Sandbox mode passed to local codex exec outside dry-run mode.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model passed to local codex exec.",
    )
    parser.add_argument(
        "--route",
        default="unknown",
        help="Public route label used in compact relay trace files.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=7200,
        help="Per-prompt local codex exec timeout outside dry-run mode.",
    )
    parser.add_argument(
        "--dry-run-response",
        default=None,
        help=(
            "Return this fixed response for session/prompt instead of invoking "
            "Codex. Intended for handshake/preflight smokes."
        ),
    )
    parser.add_argument(
        "--app-server-goal-worker",
        action="store_true",
        help=(
            "Delegate each ACP prompt to scripts/skillsbench_host_codex_goal_worker.py "
            "instead of codex exec. Deprecated for SkillsBench scored runs; "
            "prefer --codex-cli-goal-worker."
        ),
    )
    parser.add_argument(
        "--codex-cli-goal-worker",
        action="store_true",
        help=(
            "Delegate each ACP prompt to a host Codex CLI TUI and submit it "
            "with a real /goal slash command. This is the canonical Codex "
            "Goal baseline path."
        ),
    )
    parser.add_argument("--dataset", default="skillsbench-v1.1")
    parser.add_argument("--task-id", default="llm-prefix-cache-replay")
    parser.add_argument("--run-group-id", default="")
    parser.add_argument("--job-name", default="")
    parser.add_argument("--rollout-name", default="")
    parser.add_argument("--approval-policy", default="never")
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        help=(
            "Reasoning effort passed to Codex. For codex exec and "
            "--codex-cli-goal-worker this maps to -c "
            "model_reasoning_effort=...; for --app-server-goal-worker this "
            "maps to the deprecated app-server turn/start effort."
        ),
    )
    parser.add_argument(
        "--codex-api-proxy",
        default=None,
        help=(
            "Private HTTP proxy URL injected into the Codex CLI /goal process "
            "environment. The raw URL must not be written to public compact "
            "artifacts."
        ),
    )
    parser.add_argument(
        "--response-timeout-sec",
        type=float,
        default=30.0,
        help="Timeout for the worker to observe initial app-server response events.",
    )
    parser.add_argument(
        "--stream-heartbeat-interval-sec",
        type=float,
        default=120.0,
        help=(
            "Interval for public-safe ACP thought keepalives while the host "
            "app-server Goal worker is still executing."
        ),
    )
    parser.add_argument(
        "--first-action-timeout-sec",
        type=float,
        default=0.0,
        help=(
            "Optional timeout for observing the first sandbox bridge operation "
            "from a Codex turn. 0 disables the watchdog."
        ),
    )
    parser.add_argument(
        "--goal-active-timeout-sec",
        type=float,
        default=CodexExecConfig.goal_active_timeout_sec,
        help=(
            "Optional timeout for observing Codex CLI /goal active state before "
            "the first sandbox bridge operation. 0 disables the startup watchdog."
        ),
    )
    parser.add_argument(
        "--app-server-goal-followup-max",
        type=int,
        default=0,
        help=(
            "Experimental same-thread continuation budget for ordinary "
            "completed app-server Goal worker turns. No verifier/reward "
            "feedback is forwarded. 0 preserves the single-turn baseline."
        ),
    )
    parser.add_argument(
        "--app-server-goal-prompt-style",
        choices=("bridge-only", "native-goal", "cli-exec-like"),
        default="bridge-only",
        help=(
            "Prompt framing for --app-server-goal-worker. bridge-only keeps "
            "the bare app-server baseline to task prompt plus sandbox bridge; "
            "native-goal adds app closeout framing; cli-exec-like keeps the "
            "worker prompt closer to the Codex exec bridge prompt for "
            "diagnostic compatibility."
        ),
    )
    parser.add_argument(
        "--bridge-idle-timeout-sec",
        type=float,
        default=0.0,
        help=(
            "Optional timeout after the most recent sandbox bridge operation "
            "from a Codex turn. 0 disables the watchdog."
        ),
    )
    parser.add_argument(
        "--task-output-quiet-timeout-sec",
        type=float,
        default=0.0,
        help=(
            "Optional timeout after a successful task-facing file write and no "
            "inflight sandbox bridge operation. 0 disables the watchdog."
        ),
    )
    parser.add_argument(
        "--worker-script",
        default=None,
        help="Optional path to skillsbench_host_codex_goal_worker.py.",
    )
    parser.add_argument(
        "--worker-public-trace-dir",
        default=None,
        help=(
            "Optional directory for public-safe relay or host app-server Goal "
            "worker compact traces. Response text, bridge commands, raw "
            "stdout/stderr, and raw app-server streams are not written there."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-command",
        default=None,
        help=(
            "Private command used by the relay/driver to reach the scored "
            "SkillsBench sandbox through a bounded command/file bridge."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-agent-command",
        default=None,
        help=(
            "Optional bridge command injected into the private local Codex "
            "prompt. Use this when the relay runs remotely but Codex exec runs "
            "on the controller host through a reverse channel."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-timeout-sec",
        type=float,
        default=10.0,
        help="Timeout for the per-prompt remote command/file bridge readiness probe.",
    )
    parser.add_argument(
        "--loopx-workflow-lifecycle-checkpoint",
        action="store_true",
        help=(
            "For loopx-product-mode host-local ACP runs, execute a public-safe "
            "workflow-style case-local LoopX quota/todo/refresh checkpoint "
            "through the remote bridge before each Codex prompt."
        ),
    )
    parser.add_argument("--loopx-case-goal-id", default="skillsbench-case")
    parser.add_argument("--loopx-case-agent-id", default="codex-benchmark-agent")
    parser.add_argument("--loopx-case-todo-id", default=BENCHMARK_CASE_LOOPX_TODO_ID)
    parser.add_argument("--loopx-case-cli-path", default="/app/.local/bin/loopx")
    parser.add_argument("--loopx-case-registry-path", default="/app/.loopx/registry.json")
    parser.add_argument("--loopx-case-runtime-root", default="/app/.loopx/runtime")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(
            codex_bin=args.codex_bin,
            sandbox=args.sandbox,
            model=args.model,
            route=args.route,
            timeout_sec=args.timeout_sec,
            dry_run_response=args.dry_run_response,
            app_server_goal_worker=args.app_server_goal_worker,
            codex_cli_goal_worker=args.codex_cli_goal_worker,
            dataset=args.dataset,
            task_id=args.task_id,
            run_group_id=args.run_group_id,
            job_name=args.job_name,
            rollout_name=args.rollout_name,
            approval_policy=args.approval_policy,
            reasoning_effort=args.reasoning_effort,
            codex_api_proxy=args.codex_api_proxy,
            response_timeout_sec=args.response_timeout_sec,
            worker_script=args.worker_script,
            stream_heartbeat_interval_sec=args.stream_heartbeat_interval_sec,
            first_action_timeout_sec=args.first_action_timeout_sec,
            goal_active_timeout_sec=args.goal_active_timeout_sec,
            app_server_goal_followup_max=args.app_server_goal_followup_max,
            app_server_goal_prompt_style=args.app_server_goal_prompt_style,
            bridge_idle_timeout_sec=args.bridge_idle_timeout_sec,
            task_output_quiet_timeout_sec=args.task_output_quiet_timeout_sec,
            worker_public_trace_dir=args.worker_public_trace_dir,
            remote_command_file_bridge_command=(
                args.remote_command_file_bridge_command
            ),
            remote_command_file_bridge_agent_command=(
                args.remote_command_file_bridge_agent_command
            ),
            remote_command_file_bridge_timeout_sec=(
                args.remote_command_file_bridge_timeout_sec
            ),
            loopx_workflow_lifecycle_checkpoint=(
                args.loopx_workflow_lifecycle_checkpoint
            ),
            loopx_case_goal_id=args.loopx_case_goal_id,
            loopx_case_agent_id=args.loopx_case_agent_id,
            loopx_case_todo_id=args.loopx_case_todo_id,
            loopx_case_cli_path=args.loopx_case_cli_path,
            loopx_case_registry_path=args.loopx_case_registry_path,
            loopx_case_runtime_root=args.loopx_case_runtime_root,
        )
    )
    return relay.serve()


if __name__ == "__main__":
    raise SystemExit(main())
