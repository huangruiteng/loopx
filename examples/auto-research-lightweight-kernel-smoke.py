#!/usr/bin/env python3
"""Smoke-test the lightweight auto-research kernel and one-command CLI path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research import (  # noqa: E402
    LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION,
    run_builtin_lightweight_demo,
)


KERNEL = REPO_ROOT / "loopx/capabilities/auto_research/kernel.py"
CORE = REPO_ROOT / "loopx/capabilities/auto_research/core.py"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "byte" + "dance",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def assert_positive_result(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION, payload
    assert payload["candidate_count"] == 2, payload
    assert payload["dev_round_count"] == 2, payload
    assert payload["evidence_event_count"] == 3, payload
    assert payload["selected_hypothesis_id"] == "hyp_partial_selection", payload
    assert payload["decision"] == "validated_positive", payload
    assert payload["dev_metric"] == 4.0, payload
    assert payload["holdout_metric"] == 4.5, payload
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    assert payload["public_boundary"]["private_artifacts_recorded"] is False, payload
    assert_public_safe(payload)


def main() -> None:
    assert len(KERNEL.read_text(encoding="utf-8").splitlines()) <= 300
    assert len(CORE.read_text(encoding="utf-8").splitlines()) <= 80
    direct = run_builtin_lightweight_demo(goal_id="loopx-auto-research-lite-smoke")
    assert_positive_result(direct)

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "auto-research",
            "lite-e2e",
            "--goal-id",
            "loopx-auto-research-lite-smoke",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert_positive_result(json.loads(cli.stdout))


if __name__ == "__main__":
    main()
