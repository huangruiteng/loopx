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
        [sys.executable, "-m", "goal_harness.cli", *args],
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
    from goal_harness.benchmark import build_terminal_bench_goal_harness_access_packet
    from goal_harness.worker_bridge import (
        build_active_user_intervention_channel_contract,
    )

    with tempfile.TemporaryDirectory(prefix="goal-harness-active-user-after-start-") as tmp:
        root = Path(tmp)
        feed = root / "active-user-feed.jsonl"
        observation = root / "active-user-observation.json"

        contract = build_active_user_intervention_channel_contract(
            project_root=str(REPO_ROOT),
            feed_jsonl=str(feed),
            observation_json=str(observation),
        )
        assert contract["worker_start_marker"]["kind"] == "worker_start_seq", contract
        assert contract["claim_boundary"]["worker_pull_required"] is True, contract
        assert contract["claim_boundary"]["direct_codex_chat_injection"] is False, contract

        access_packet = build_terminal_bench_goal_harness_access_packet(
            cli_bridge_available=True,
            command_prefix="goal-harness",
            active_user_intervention_enabled=True,
            active_user_feed_jsonl="/logs/agent/goal-harness-active-user-interventions.jsonl",
            active_user_observation_json="/logs/agent/goal-harness-active-user-observation.json",
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
        assert observation.exists(), observed
        assert_worker_observation(observed)
        assert_worker_observation(json.loads(observation.read_text(encoding="utf-8")))

    print("worker-bridge-active-user-after-start-observation-smoke ok proof=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
