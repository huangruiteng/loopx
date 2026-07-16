#!/usr/bin/env python3
"""Smoke-test public-safe interaction-to-scheduler decision replays."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.decision_replay import (  # noqa: E402
    load_public_safe_decision_replay,
    replay_public_safe_decision_case,
)


FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "control_plane"
    / "public_safe_decision_replay_v0.json"
)


def main() -> int:
    replay = load_public_safe_decision_replay(FIXTURE)
    assert len(replay["cases"]) >= 3, replay
    for case in replay["cases"]:
        observed = replay_public_safe_decision_case(case)
        assert observed == {
            "decision": case["decision"],
            "selected_todo": case["selected_todo"],
            "interaction_contract": case["interaction_contract"],
            "expected": case["expected"],
        }, case
    print("interaction scheduler authority smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
