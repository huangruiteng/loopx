#!/usr/bin/env python3
"""Smoke-test a worker after-start active-user observation round trip."""

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

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/" + "benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth" + ".json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 20000, len(text)


def run_json(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def run_shell_json(command: str) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def assert_worker_observation(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["feed_present"] is True, payload
    assert payload["feed_path_recorded"] is False, payload
    assert payload["worker_start_seq"] == 1, payload
    assert payload["valid_intervention_count"] == 2, payload
    assert payload["observed_after_worker_start"] is True, payload
    assert payload["observed_intervention_count"] == 1, payload
    assert payload["worker_observation_proof"] is True, payload
    latest = payload["latest_intervention"]
    assert latest["seq"] == 2, payload
    assert latest["message"] == "Run the public bridge smoke before broader edits.", payload
    assert latest["oracle_free"] is True, payload
    assert latest["hidden_tests_visible"] is False, payload
    assert latest["expected_solution_visible"] is False, payload
    boundary = payload["claim_boundary"]
    assert boundary["assisted_collaboration_claim_allowed"] is True, payload
    assert boundary["official_score_claim_allowed"] is False, payload
    assert boundary["leaderboard_claim_allowed"] is False, payload
    assert boundary["direct_codex_chat_injection"] is False, payload
    assert_public_safe(payload)


def main() -> int:
    from loopx.benchmark import build_terminal_bench_loopx_access_packet
    from loopx.worker_bridge import (
        build_active_user_intervention_channel_contract,
    )

    with tempfile.TemporaryDirectory(prefix="loopx-active-user-after-start-") as tmp:
        root = Path(tmp)
        feed = root / "active-user-feed.jsonl"
        observation = root / "active-user-observation.json"
        counter_trace = root / "counter-trace.jsonl"
        benchmark_run = root / "worker-benchmark-run.json"

        contract = build_active_user_intervention_channel_contract(
            project_root=str(REPO_ROOT),
            feed_jsonl=str(feed),
            observation_json=str(observation),
            counter_trace_json=str(counter_trace),
            benchmark_run_json=str(benchmark_run),
        )
        assert contract["worker_start_marker"]["kind"] == "worker_start_seq", contract
        assert contract["claim_boundary"]["worker_pull_required"] is True, contract
        assert contract["claim_boundary"]["direct_codex_chat_injection"] is False, contract
        assert "--counter-trace-json" in contract["worker_observe_command"], contract
        assert "--benchmark-run-json" in contract["worker_observe_command"], contract

        access_packet = build_terminal_bench_loopx_access_packet(
            cli_bridge_available=True,
            command_prefix="loopx",
            active_user_intervention_enabled=True,
            active_user_feed_jsonl="/logs/agent/loopx-active-user-interventions.jsonl",
            active_user_observation_json="/logs/agent/loopx-active-user-observation.json",
            active_user_observe_command=contract["worker_observe_command"],
        )
        assert "active_user_worker_must_poll_after_start: true" in access_packet
        assert "active_user_intervention_observe_command:" in access_packet
        assert "<active-user-observe-command-redacted>" in access_packet
        assert "active-user-observe" in access_packet

        before_start = run_json(
            [
                "worker-bridge",
                "active-user-intervention",
                "--seq",
                "1",
                "--message",
                "Record worker start before observing simulator updates.",
                "--before-worker-start",
                "--format",
                "json",
            ]
        )
        assert before_start["created_after_worker_start"] is False, before_start
        append_jsonl(feed, before_start)

        no_update = run_shell_json(
            contract["worker_observe_command"].replace("<worker-start-seq>", "1")
        )
        assert no_update["observed_after_worker_start"] is False, no_update
        assert no_update["worker_observation_proof"] is False, no_update
        assert no_update["counter_trace_written"] is True, no_update
        assert no_update["benchmark_run_checkpoint_written"] is True, no_update

        append_command = (
            contract["simulator_append_command"]
            .replace("<next-seq>", "2")
            .replace(
                "<public-safe-user-message>",
                "Run the public bridge smoke before broader edits.",
            )
        )
        subprocess.run(
            append_command,
            cwd=REPO_ROOT,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        observed = run_shell_json(
            contract["worker_observe_command"].replace("<worker-start-seq>", "1")
        )
        assert observed["observation_written"] is True, observed
        assert observed["counter_trace_written"] is True, observed
        assert observed["benchmark_run_checkpoint_written"] is True, observed
        assert observation.exists(), observed
        assert counter_trace.exists(), observed
        assert benchmark_run.exists(), observed
        assert_worker_observation(observed)
        assert_worker_observation(json.loads(observation.read_text(encoding="utf-8")))
        trace_rows = [
            json.loads(line)
            for line in counter_trace.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(trace_rows) == 2, trace_rows
        assert trace_rows[-1]["command"] == "active_user_observe", trace_rows
        checkpoint = json.loads(benchmark_run.read_text(encoding="utf-8"))
        assert checkpoint["schema_version"] == "benchmark_run_v0", checkpoint
        assert checkpoint["worker_loopx_cli_call_total"] == 2, checkpoint
        assert checkpoint["worker_bridge_outcome"]["worker_bridge_verified"] is True, checkpoint
        assert (
            checkpoint["worker_bridge_checkpoint"]["checkpoint_kind"]
            == "active_user_observe"
        ), checkpoint
        assert_public_safe(checkpoint)

    print("worker-bridge-active-user-after-start-observation-smoke ok proof=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
