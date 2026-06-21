#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench LoopX CLI bridge contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_loopx_cli_bridge_contract,
    build_terminal_bench_loopx_interaction_counters,
)


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-loopx-cli-bridge-contract-v0.md"
README = TOPIC_DIR / "README.md"
GOAL_ID = "terminal-bench-loopx-cli-bridge-fixture"

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "ARK" + "_BASE_URL=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench LoopX CLI Bridge Contract V0",
    "terminal_bench_loopx_cli_bridge_contract_v0",
    "host_agent_loopx_cli_bridge_v0",
    "bridge_available=false",
    "loopx_cli_bridge_available",
    "status",
    "quota_should_run",
    "todo_list",
    "history",
    "check",
    "append_benchmark_run",
    "python3 examples/terminal-bench-loopx-cli-bridge-contract-smoke.py",
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    benchmark_run_path = root / "benchmark-run.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-08T00:00:00+00:00\n"
        "---\n\n"
        "# Terminal-Bench LoopX CLI Bridge Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Run the bridge contract fixture.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-08T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "loopx-platform",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "heartbeat": {
                        "enabled": True,
                    },
                }
            ],
        },
    )
    write_json(
        benchmark_run_path,
        build_terminal_bench_benchmark_run(mode="codex-loopx"),
    )
    return registry_path, runtime, benchmark_run_path


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 26000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-loopx-cli-bridge-contract-v0.md" in readme, readme
    assert_public_safe(text)


def assert_public_contract() -> None:
    contract = build_terminal_bench_loopx_cli_bridge_contract()
    assert contract["schema_version"] == TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION, contract
    assert contract["bridge_surface"] == "host_agent_loopx_cli_bridge_v0", contract
    assert contract["bridge_available"] is False, contract
    assert tuple(contract["logical_commands"]) == TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS, contract
    assert set(contract["command_templates"]) == set(TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS), contract
    assert contract["command_templates"]["status"][0] == "loopx", contract
    assert "quota should-run" in " ".join(contract["command_templates"]["todo_list"]), contract
    assert "--dry-run" in contract["command_templates"]["append_benchmark_run"], contract
    assert contract["boundary"]["real_run"] is False, contract
    assert contract["boundary"]["runs_terminal_bench"] is False, contract
    assert_public_safe(contract)


def run_json(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict), payload
    return payload


def assert_executable_bridge_contract(registry_path: Path, runtime: Path, benchmark_run_path: Path) -> None:
    contract = build_terminal_bench_loopx_cli_bridge_contract(
        goal_id=GOAL_ID,
        registry=str(registry_path),
        runtime_root=str(runtime),
        command_prefix=[sys.executable, "-m", "loopx.cli"],
        scan_path=str(REPO_ROOT / "loopx" / "benchmark.py"),
        benchmark_run_json=str(benchmark_run_path),
        classification="terminal_bench_loopx_cli_bridge_contract_fixture_v0",
        bridge_available=True,
    )
    observed_calls: dict[str, int] = {}
    for command in TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS:
        payload = run_json(contract["command_templates"][command])
        assert payload.get("ok") is True, (command, payload)
        if command == "append_benchmark_run":
            assert payload["appended"] is False, payload
            assert payload["dry_run"] is True, payload
        observed_calls[command] = observed_calls.get(command, 0) + 1

    counters = build_terminal_bench_loopx_interaction_counters(
        prompt_policy_injected=True,
        harness_skill_or_packet_injected=True,
        loopx_cli_calls=observed_calls,
        loopx_state_reads=5,
        loopx_state_writes=0,
        case_result_writeback="bridge_append_benchmark_run_dry_run",
        counter_trust_level="bridge_contract_fixture_observed",
    )
    assert counters["loopx_cli_calls"]["total"] == 6, counters
    assert counters["loopx_state_reads"] == 5, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "bridge_append_benchmark_run_dry_run", counters
    assert counters["counter_trust_level"] == "bridge_contract_fixture_observed", counters
    assert_public_safe(counters)


def main() -> None:
    assert_doc_contract()
    assert_public_contract()
    with tempfile.TemporaryDirectory(prefix="terminal-bench-loopx-cli-bridge-") as raw_root:
        registry_path, runtime, benchmark_run_path = write_fixture(Path(raw_root))
        assert_executable_bridge_contract(registry_path, runtime, benchmark_run_path)
    print("terminal-bench-loopx-cli-bridge-contract-smoke ok cli_calls=6")


if __name__ == "__main__":
    main()
