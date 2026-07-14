#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


from loopx.capabilities.reward_memory import run_reward_memory_evaluation  # noqa: E402
from loopx.capabilities.reward_memory.evaluation_fixtures import (  # noqa: E402
    generic_compact_restart_fixture,
    openviking_pr_3237_regression_fixture,
)


def main() -> None:
    generic_fixture = generic_compact_restart_fixture()
    assert "openviking" not in json.dumps(
        generic_fixture["fixture_identity"], sort_keys=True
    ).lower()
    regression_fixture = openviking_pr_3237_regression_fixture()
    assert regression_fixture["case_ref"].endswith("/OpenViking/pull/3237")

    packet = run_reward_memory_evaluation()
    assert packet["schema_version"] == "reward_memory_evaluation_v0", packet
    assert packet["status"] == "passed", packet
    assert packet["metrics"]["case_count"] == 8, packet
    assert packet["metrics"]["failed_case_count"] == 0, packet
    assert packet["metrics"]["false_application_count"] == 0, packet
    assert packet["metrics"]["storage_write_bytes"] == 0, packet
    assert packet["metrics"]["maintainer_interruption_count"] == 0, packet
    assert packet["release_gate"]["status"] == "ready_for_bounded_dogfood", packet
    assert packet["release_gate"]["semantic_uplift_claim_allowed"] is False, packet
    assert packet["release_gate"]["production_rollout_allowed"] is False, packet
    assert packet["boundaries"]["new_store_provider_or_scheduler_added"] is False
    print("reward-memory-evaluation-smoke: ok")


if __name__ == "__main__":
    main()
