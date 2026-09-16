#!/usr/bin/env python3
"""Fail-closed admission check run independently before every LoopX arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from goal30_subset import SUBSET
from hard24_subset import HARD_SUBSET
from remaining4_subset import REMAINING_SUBSET
from workspace_delivery import head_sha, normalize_delivery


TASKS = tuple(dict.fromkeys((*SUBSET, *HARD_SUBSET, *REMAINING_SUBSET)))
EXPECTED_MODEL = "openai/gpt-5.6-sol"
EXPECTED_EFFORT = "xhigh"
EXPECTED_AGENT_TIMEOUT_MULTIPLIER = 3.0
EXPECTED_GOAL_TIMEOUT_SECONDS = 14400.0
EXPECTED_HEARTBEAT_SEGMENT_TIMEOUT_SECONDS = 7200.0
EXPECTED_TURN_IDLE_TIMEOUT_SECONDS = 7200.0
EXPECTED_LOOPX_REVISION = os.environ.get(
    "MR_EXPECTED_LOOPX_REVISION", "2cef51d08b2a0103f4ba026bf47fd70dc8acee30"
)
RUNNERS = {
    "ssh-goal": {
        "file": "loopx_wen_native_runner.py",
        "surface": "native_goal_appserver",
        "required": ('"app-server"', '"turn/interrupt"', '"task_correctness_authority"', '"independent_verifier"'),
        "forbidden": (),
    },
    "codex-cli": {
        "file": "loopx_codex_cli_runner.py",
        "surface": "codex_cli",
        "required": ('"run-once"', '"--host"', '"codex-cli"', '"task_correctness_authority"', '"independent_verifier"'),
        "forbidden": ('"app-server"',),
    },
    "heartbeat": {
        "file": "loopx_heartbeat_supervisor.py",
        "surface": "outer_controller_heartbeat",
        "required": ('"heartbeat-prompt"', '"outer_controller"', '"codex_exec"', '"continuation_owner": "benchmark_supervisor"', '"task_correctness_authority": "independent_verifier"'),
        "forbidden": ('"app-server"',),
    },
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True, check=False
    )


def delivery_self_test() -> tuple[bool, str]:
    """Exercise the exact ignored-control-state failure seen in smoke."""
    with tempfile.TemporaryDirectory(prefix="deepswe-delivery-preflight-") as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        commands = (
            ("init", "-q"),
            ("config", "user.name", "DeepSWE preflight"),
            ("config", "user.email", "preflight@deepswe.invalid"),
        )
        for command in commands:
            result = _git(*command, cwd=project)
            if result.returncode:
                return False, result.stderr[-300:]
        (project / "source.txt").write_text("base\n", encoding="utf-8")
        if _git("add", "source.txt", cwd=project).returncode:
            return False, "could_not_stage_base"
        if _git("commit", "-qm", "base", cwd=project).returncode:
            return False, "could_not_commit_base"
        base = head_sha(project)
        for name in (".loopx", ".codex"):
            (project / name).mkdir()
            (project / name / "state.json").write_text("{}\n", encoding="utf-8")
        (project / "delivered.txt").write_text("ok\n", encoding="utf-8")
        receipt = normalize_delivery(project, base)
        tracked = _git("ls-files", cwd=project).stdout.splitlines()
        valid = (
            receipt.get("treatment_valid") is True
            and receipt.get("patch_applies") is True
            and "delivered.txt" in tracked
            and not any(path.startswith((".loopx/", ".codex/")) for path in tracked)
        )
        return valid, str(receipt.get("reason") or "unknown")


def port_is_free(port: int) -> bool:
    for host in ("127.0.0.1", "127.0.0.1"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.1)
            if probe.connect_ex((host, port)) == 0:
                return False
    return True


def task_manifest(task_root: Path) -> tuple[str, float, list[str]]:
    entries = []
    timeouts = []
    missing = []
    for task in TASKS:
        path = task_root / task / "task.toml"
        if not path.is_file():
            missing.append(task)
            continue
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        base = str(data.get("metadata", {}).get("base_commit_hash") or "")
        timeout = float(data.get("agent", {}).get("timeout_sec") or 0)
        if re.fullmatch(r"[0-9a-fA-F]{7,40}", base) is None or timeout <= 0:
            missing.append(task)
            continue
        timeouts.append(timeout)
        entries.append(f"{task}\t{base}\t{hashlib.sha256(raw).hexdigest()}")
    payload = "\n".join(entries).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), min(timeouts, default=0), missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=tuple(RUNNERS), required=True)
    parser.add_argument("--loopx-root", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--goal-timeout", type=float, required=True)
    parser.add_argument("--heartbeat-segment-timeout", type=float, required=True)
    parser.add_argument("--turn-idle-timeout", type=float, required=True)
    parser.add_argument("--agent-timeout-multiplier", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    errors: list[str] = []
    contract = RUNNERS[args.arm]
    runner_name = str(contract["file"])
    surface = str(contract["surface"])
    runner = root / runner_name
    delivery = root / "workspace_delivery.py"
    adapter = root / "loopx_native_codex.py"
    wrapper = root / "codex_nosandbox_wrapper.py"
    harness = root / "goal_codex.py"
    task_root = root / "upstream" / "tasks"
    manifest_sha256, minimum_agent_timeout, malformed_tasks = task_manifest(task_root)
    if args.port in {4141, 4250}:
        errors.append("prohibited_gateway_port")
    if not port_is_free(args.port):
        errors.append("gateway_port_occupied")
    if args.model != EXPECTED_MODEL:
        errors.append("model_not_fair_control")
    if args.effort != EXPECTED_EFFORT:
        errors.append("effort_not_fair_control")
    if args.agent_timeout_multiplier != EXPECTED_AGENT_TIMEOUT_MULTIPLIER:
        errors.append("agent_timeout_multiplier_not_fair_control")
    if args.goal_timeout != EXPECTED_GOAL_TIMEOUT_SECONDS:
        errors.append("goal_timeout_not_pinned")
    if args.heartbeat_segment_timeout != EXPECTED_HEARTBEAT_SEGMENT_TIMEOUT_SECONDS:
        errors.append("heartbeat_segment_timeout_not_pinned")
    if args.turn_idle_timeout != EXPECTED_TURN_IDLE_TIMEOUT_SECONDS:
        errors.append("turn_idle_timeout_not_pinned")
    if args.heartbeat_segment_timeout >= args.goal_timeout:
        errors.append("heartbeat_segment_not_below_goal_timeout")
    if minimum_agent_timeout <= 0 or args.goal_timeout >= minimum_agent_timeout * args.agent_timeout_multiplier:
        errors.append("inner_timeout_not_below_agent_timeout")
    source = runner.read_text(encoding="utf-8") if runner.is_file() else ""
    if not runner.is_file():
        errors.append("runner_missing")
    if any(marker not in source for marker in contract["required"]):
        errors.append("runner_contract_marker_missing")
    if any(marker in source for marker in contract["forbidden"]):
        errors.append("runner_uses_wrong_surface")
    if not delivery.is_file():
        errors.append("delivery_gate_missing")
    adapter_source = adapter.read_text(encoding="utf-8") if adapter.is_file() else ""
    if not adapter.is_file() or '"--accept-onboarding-agent-todos"' in adapter_source:
        errors.append("benchmark_adapter_allows_onboarding_todos")
    if '"--no-onboarding-scan"' not in adapter_source or '"--text", "[P0] " + task_text' not in adapter_source:
        errors.append("benchmark_task_admission_contract_missing")
    wrapper_source = wrapper.read_text(encoding="utf-8") if wrapper.is_file() else ""
    if args.arm == "codex-cli" and (
        not wrapper.is_file() or "MR_CODEX_REASONING_EFFORT" not in wrapper_source
    ):
        errors.append("codex_cli_effort_injection_missing")
    if args.arm == "heartbeat" and "model_reasoning_effort=" not in source:
        errors.append("heartbeat_effort_injection_missing")
    harness_source = harness.read_text(encoding="utf-8") if harness.is_file() else ""
    if not harness.is_file() or 'args += ["--effort", effort]' not in harness_source:
        errors.append("runner_effort_forwarding_missing")
    if args.arm in {"codex-cli", "heartbeat"} and (
        'runner_env.get("LOOPX_MODE") in {"codex-cli", "heartbeat"}' not in harness_source
        or '"--segment-timeout-seconds"' not in harness_source
        or 'MR_HEARTBEAT_SEGMENT_TIMEOUT_SEC' not in harness_source
    ):
        errors.append("runner_segment_timeout_forwarding_missing")
    if args.arm == "ssh-goal" and (
        'runner_env.get("LOOPX_MODE") == "ssh-goal"' not in harness_source
        or '"--turn-idle-timeout-seconds"' not in harness_source
        or "MR_LOOPX_TURN_IDLE_TIMEOUT_SEC" not in harness_source
    ):
        errors.append("runner_turn_idle_timeout_forwarding_missing")
    compile_check = subprocess.run(
        [sys.executable, "-m", "py_compile", str(runner), str(delivery)],
        capture_output=True,
        text=True,
        check=False,
    )
    if compile_check.returncode:
        errors.append("runner_or_delivery_not_compilable")
    delivery_probe_ok, delivery_probe_detail = delivery_self_test()
    if not delivery_probe_ok:
        errors.append("delivery_self_test_failed")
    if len(TASKS) != 54 or len(set(TASKS)) != 54:
        errors.append("task_set_not_54_unique")
    if malformed_tasks:
        errors.append("missing_or_malformed_task_definitions")
    git = subprocess.run(
        ["git", "-C", str(args.loopx_root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git.returncode or git.stdout.strip():
        errors.append("loopx_source_not_clean")
    revision = subprocess.run(
        ["git", "-C", str(args.loopx_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if len(revision) != 40:
        errors.append("loopx_revision_missing")
    elif revision != EXPECTED_LOOPX_REVISION:
        errors.append("loopx_revision_not_pinned")

    receipt = {
        "schema_version": "deepswe_loopx_arm_admission_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "arm": args.arm,
        "host_surface": surface,
        "runner": runner_name,
        "runner_sha256": digest(runner) if runner.is_file() else None,
        "delivery_gate_sha256": digest(delivery) if delivery.is_file() else None,
        "benchmark_adapter_sha256": digest(adapter) if adapter.is_file() else None,
        "codex_wrapper_sha256": digest(wrapper) if wrapper.is_file() else None,
        "goal_harness_sha256": digest(harness) if harness.is_file() else None,
        "loopx_revision": revision or None,
        "loopx_source_clean": "loopx_source_not_clean" not in errors,
        "model": args.model,
        "effort": args.effort,
        "goal_timeout_seconds": args.goal_timeout,
        "heartbeat_segment_timeout_seconds": args.heartbeat_segment_timeout,
        "turn_idle_timeout_seconds": args.turn_idle_timeout,
        "agent_timeout_multiplier": args.agent_timeout_multiplier,
        "minimum_native_agent_timeout_seconds": minimum_agent_timeout,
        "task_count": len(TASKS),
        "task_manifest_sha256": manifest_sha256,
        "missing_or_malformed_tasks": malformed_tasks,
        "gateway_port": args.port,
        "gateway_port_free": "gateway_port_occupied" not in errors,
        "network_policy": "model_only_dedicated_gateway",
        "sandbox_policy": "danger_full_access_equivalent",
        "web_search": "disabled",
        "delivery_self_test": delivery_probe_ok,
        "delivery_self_test_detail": delivery_probe_detail,
        "lifecycle_authority": "loopx_goal_or_todo",
        "task_correctness_authority": "independent_verifier",
        "admitted": not errors,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["admitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
