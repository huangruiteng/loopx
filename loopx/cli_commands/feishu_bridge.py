from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def register_feishu_bridge_commands(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "feishu-bridge",
        help="Run and inspect the Feishu progress bridge service.",
    )
    sub = parser.add_subparsers(dest="feishu_bridge_command", required=True)

    sub.add_parser("run", help="Consume Feishu events and publish LoopX progress updates.")
    sub.add_parser("progress-once", help="Poll tracked todos once and exit.")
    sub.add_parser("migrate-state", help="Rewrite the bridge state file with the current schema.")
    sub.add_parser("print-launch-agent", help="Print a macOS launchd plist for the bridge.")

    doctor = sub.add_parser("doctor", help="Inspect bridge runtime readiness.")
    doctor.add_argument("--format", dest="bridge_format", choices=["markdown", "json"], default="markdown")

    logs = sub.add_parser("logs", help="Print recent bridge log lines.")
    logs.add_argument("--tail", type=int, default=40, help="Number of log lines to print.")


def handle_feishu_bridge_command(args: argparse.Namespace) -> int | None:
    if getattr(args, "command", None) != "feishu-bridge":
        return None
    script = Path(__file__).resolve().parents[2] / "scripts" / "feishu_loopx_progress_bridge.py"
    command = args.feishu_bridge_command
    script_args: list[str] = []
    if command == "doctor":
        script_args = ["--doctor", "--format", args.bridge_format]
    elif command == "run":
        script_args = []
    elif command == "progress-once":
        script_args = ["--progress-once"]
    elif command == "migrate-state":
        script_args = ["--migrate-state"]
    elif command == "print-launch-agent":
        script_args = ["--print-launch-agent"]
    elif command == "logs":
        script_args = ["--log-tail", str(args.tail)]
    else:
        return 2
    result = subprocess.run([sys.executable, str(script), *script_args], text=True)
    return int(result.returncode)
