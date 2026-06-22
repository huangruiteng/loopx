#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "loopx" / "cli.py"
MODULE = ROOT / "loopx" / "cli_commands" / "worker_bridge.py"
INIT = ROOT / "loopx" / "cli_commands" / "__init__.py"


def run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        input=stdin,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        raise AssertionError(
            f"expected success, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result.stdout


def main() -> None:
    cli_source = CLI.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_cli_markers = [
        "worker_bridge_parser = sub.add_parser",
        "worker_bridge_sub = worker_bridge_parser.add_subparsers",
        "build_worker_bridge_install_contract(",
        "observe_active_user_intervention_feed(",
        'if args.command == "worker-bridge":',
    ]
    for marker in forbidden_cli_markers:
        require(marker not in cli_source, f"worker-bridge marker leaked into cli.py: {marker}")

    for marker in (
        "register_worker_bridge_commands",
        "handle_worker_bridge_command",
        "WORKER_BRIDGE_COMMANDS",
        "build_worker_bridge_benchmark_run_from_counters(",
        "append_worker_bridge_counter_trace_row(",
    ):
        require(marker in module_source, f"worker-bridge command module missing {marker}")
    require("register_worker_bridge_commands" in init_source, "__init__ did not export worker bridge registration")
    require("handle_worker_bridge_command" in init_source, "__init__ did not export worker bridge handler")

    help_text = require_success(run_cli("worker-bridge", "active-user-observe", "--help"))
    for option in ("--feed-jsonl", "--observation-json", "--counter-trace-json", "--benchmark-run-json"):
        require(option in help_text, f"active-user-observe help omitted {option}")

    contract_payload = json.loads(
        require_success(run_cli("worker-bridge", "contract", "--format", "json"))
    )
    require(contract_payload.get("ok") is True, "worker bridge contract should be ok")
    require(
        contract_payload.get("schema_version")
        == "loopx_worker_bridge_install_contract_v0",
        "contract schema changed",
    )

    outcome_payload = json.loads(
        require_success(
            run_cli(
                "worker-bridge",
                "outcome",
                "--format",
                "json",
                "--worker-cli-call-total",
                "4",
                "--counter-trace-present",
                "--interrupted",
                "--interrupt-reason",
                "controller_interrupt_after_wall_time_limit",
                "--wall-time-seconds",
                "720",
                "--wall-time-limit-seconds",
                "900",
            )
        )
    )
    require(outcome_payload.get("worker_bridge_verified") is True, "outcome should verify worker bridge")
    require(
        outcome_payload.get("runner_return_status")
        == "interrupted_after_worker_bridge_success",
        "outcome runner-return status changed",
    )

    benchmark_run_payload = json.loads(
        require_success(
            run_cli(
                "worker-bridge",
                "benchmark-run",
                "--format",
                "json",
                "--worker-cli-call-total",
                "4",
                "--counter-trace-present",
                "--interrupted",
                "--interrupt-reason",
                "controller_interrupt_after_wall_time_limit",
                "--wall-time-seconds",
                "720",
                "--wall-time-limit-seconds",
                "900",
            )
        )
    )
    require(benchmark_run_payload.get("schema_version") == "benchmark_run_v0", "benchmark-run schema changed")
    require(benchmark_run_payload.get("submit_eligible") is False, "worker bridge smoke must stay no-submit")
    require(
        (benchmark_run_payload.get("worker_bridge_outcome") or {}).get("worker_bridge_verified")
        is True,
        "benchmark-run should embed verified worker bridge outcome",
    )

    with tempfile.TemporaryDirectory(prefix="loopx-worker-bridge-cli-") as tmp:
        root = Path(tmp)
        before = require_success(
            run_cli(
                "worker-bridge",
                "active-user-intervention",
                "--seq",
                "0",
                "--message",
                "before worker start",
                "--before-worker-start",
                "--jsonl",
            )
        ).strip()
        after = require_success(
            run_cli(
                "worker-bridge",
                "active-user-intervention",
                "--seq",
                "2",
                "--message",
                "after worker start",
                "--jsonl",
            )
        ).strip()
        feed_path = root / "feed.jsonl"
        observation_path = root / "observation.json"
        counter_trace_path = root / "counter-trace.jsonl"
        benchmark_run_path = root / "benchmark-run.json"
        feed_path.write_text(before + "\n" + after + "\n", encoding="utf-8")

        observe_payload = json.loads(
            require_success(
                run_cli(
                    "worker-bridge",
                    "active-user-observe",
                    "--feed-jsonl",
                    str(feed_path),
                    "--worker-start-seq",
                    "1",
                    "--observation-json",
                    str(observation_path),
                    "--counter-trace-json",
                    str(counter_trace_path),
                    "--benchmark-run-json",
                    str(benchmark_run_path),
                    "--format",
                    "json",
                )
            )
        )
        require(observe_payload.get("ok") is True, "active-user-observe should succeed")
        require(observe_payload.get("observation_written") is True, "observation writeback missing")
        require(observe_payload.get("counter_trace_written") is True, "counter trace writeback missing")
        require(
            observe_payload.get("benchmark_run_checkpoint_written") is True,
            "benchmark_run checkpoint writeback missing",
        )
        require(
            observe_payload.get("benchmark_run_checkpoint_schema_version")
            == "benchmark_run_v0",
            "checkpoint schema changed",
        )
        checkpoint = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
        require(
            checkpoint.get("source_runner") == "worker_bridge_active_user_observe",
            "checkpoint source runner changed",
        )
        require(
            (checkpoint.get("worker_bridge_checkpoint") or {}).get("raw_paths_recorded")
            is False,
            "checkpoint must not record raw paths",
        )

    print("cli-worker-bridge-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
