#!/usr/bin/env python3
"""Smoke-test the active-user worker-bridge external update feed."""

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
    assert len(text) < 18000, len(text)


def run_cli_json(args: list[str], *, check: bool = True) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def assert_contract(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert (
        payload["schema_version"]
        == "goal_harness_active_user_intervention_channel_contract_v0"
    ), payload
    assert payload["channel_surface"] == "goal_harness_active_user_external_update_loop_v0", payload
    assert payload["mode"] == "audited_external_update_loop", payload
    assert payload["worker_start_marker"]["kind"] == "worker_start_seq", payload
    assert "active-user-observe" in payload["worker_observe_command"], payload
    assert "active-user-intervention" in payload["simulator_append_command"], payload
    assert payload["frequency_budget"]["max_interventions_per_task"] == 3, payload
    assert payload["frequency_budget"]["artificial_mildness_required"] is False, payload
    boundary = payload["claim_boundary"]
    assert boundary["assisted_collaboration_claim_allowed"] is True, payload
    assert boundary["official_score_claim_allowed"] is False, payload
    assert boundary["leaderboard_claim_allowed"] is False, payload
    assert boundary["direct_codex_chat_injection"] is False, payload
    assert boundary["worker_pull_required"] is True, payload
    assert_public_safe(payload)


def assert_intervention(payload: dict[str, Any], *, seq: int, after_start: bool) -> None:
    assert payload["schema_version"] == "goal_harness_active_user_intervention_v0", payload
    assert payload["channel_surface"] == "goal_harness_active_user_external_update_loop_v0", payload
    assert payload["seq"] == seq, payload
    assert payload["channel"] == "simulator_proactive_user_message", payload
    assert payload["type"] == "active_user_instruction", payload
    assert payload["created_after_worker_start"] is after_start, payload
    assert payload["oracle_free"] is True, payload
    assert payload["hidden_tests_visible"] is False, payload
    assert payload["expected_solution_visible"] is False, payload
    assert payload["official_score_claim_allowed"] is False, payload
    assert payload["leaderboard_claim_allowed"] is False, payload
    assert_public_safe(payload)


def assert_observation(payload: dict[str, Any], *, observed: bool) -> None:
    assert payload["ok"] is True, payload
    assert (
        payload["schema_version"]
        == "goal_harness_active_user_intervention_observation_v0"
    ), payload
    assert payload["channel_surface"] == "goal_harness_active_user_external_update_loop_v0", payload
    assert payload["feed_present"] is True, payload
    assert payload["feed_path_recorded"] is False, payload
    assert payload["observed_after_worker_start"] is observed, payload
    assert payload["worker_observation_proof"] is observed, payload
    boundary = payload["claim_boundary"]
    assert boundary["official_score_claim_allowed"] is False, payload
    assert boundary["leaderboard_claim_allowed"] is False, payload
    assert boundary["direct_codex_chat_injection"] is False, payload
    if observed:
        assert payload["observed_intervention_count"] == 1, payload
        latest = payload["latest_intervention"]
        assert latest["seq"] == 2, payload
        assert latest["message"] == "Pause and run the focused public smoke before editing further.", payload
        assert latest["hidden_tests_visible"] is False, payload
    else:
        assert payload["observed_intervention_count"] == 0, payload
        assert payload["latest_intervention"] == {}, payload
    assert_public_safe(payload)


def main() -> int:
    from goal_harness.worker_bridge import (
        build_active_user_intervention,
        build_active_user_intervention_channel_contract,
        observe_active_user_intervention_feed,
    )

    assert_contract(build_active_user_intervention_channel_contract())
    assert_contract(
        run_cli_json(
            [
                "worker-bridge",
                "active-user-contract",
                "--format",
                "json",
            ]
        )
    )

    before_start = build_active_user_intervention(
        seq=0,
        message="Record worker start and wait for public progress evidence.",
        created_after_worker_start=False,
    )
    assert_intervention(before_start, seq=0, after_start=False)
    after_start = run_cli_json(
        [
            "worker-bridge",
            "active-user-intervention",
            "--seq",
            "2",
            "--message",
            "Pause and run the focused public smoke before editing further.",
            "--format",
            "json",
        ]
    )
    assert_intervention(after_start, seq=2, after_start=True)

    with tempfile.TemporaryDirectory(prefix="goal-harness-active-user-feed-") as tmp:
        root = Path(tmp)
        feed = root / "feed.jsonl"
        observation_path = root / "observation.json"
        feed.write_text(
            json.dumps(before_start, sort_keys=True) + "\n"
            + json.dumps(after_start, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        module_observation = observe_active_user_intervention_feed(
            feed,
            worker_start_seq=1,
        )
        assert_observation(module_observation, observed=True)

        cli_observation = run_cli_json(
            [
                "worker-bridge",
                "active-user-observe",
                "--feed-jsonl",
                str(feed),
                "--worker-start-seq",
                "1",
                "--observation-json",
                str(observation_path),
                "--format",
                "json",
            ]
        )
        assert cli_observation["observation_written"] is True, cli_observation
        assert observation_path.exists(), cli_observation
        assert_observation(cli_observation, observed=True)
        assert_public_safe(json.loads(observation_path.read_text(encoding="utf-8")))

        no_new_observation = run_cli_json(
            [
                "worker-bridge",
                "active-user-observe",
                "--feed-jsonl",
                str(feed),
                "--worker-start-seq",
                "2",
                "--format",
                "json",
            ]
        )
        assert_observation(no_new_observation, observed=False)

    rejected = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "worker-bridge",
            "active-user-intervention",
            "--seq",
            "3",
            "--message",
            "/" + "Users/private/path should be rejected",
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert rejected.returncode == 1, rejected.stdout
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "a non-public marker" in rejected_payload["error"], rejected_payload
    assert_public_safe(rejected_payload)

    print("worker-bridge-active-user-feed-smoke ok observed_after_worker_start=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
