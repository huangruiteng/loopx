#!/usr/bin/env python3
"""Smoke-test the explicit KNN demo preset on auto-research start."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTION = "如何提升 KNN holdout metric?"


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "auto-research",
            "start",
            QUESTION,
            "--preset",
            "knn-demo",
            "--language",
            "zh",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    contract = payload["user_contract"]
    preset = contract["preset_context"]
    assert preset["preset_id"] == "knn-demo", preset
    assert preset["baseline_source"] == "preset_fixture_not_question_text", preset
    assert preset["question_text_supplies_baseline"] is False, preset
    assert preset["metric_name"] == "holdout_metric", preset
    assert preset["baseline_metric"] == 1.0, preset
    assert payload["preset_context"] == preset, payload
    assert payload["route_contract"]["preset_id"] == "knn-demo", payload
    assert payload["route_contract"]["preset_baseline_source"] == (
        "preset_fixture_not_question_text"
    ), payload
    assert "--preset knn-demo" in contract["one_click_start"]["command"], contract
    assert "--preset knn-demo" in payload["commands"]["one_question_start"], payload
    assert payload["contract_acceptance"]["accepted"] is True, payload

    markdown_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "auto-research",
            "start",
            QUESTION,
            "--preset",
            "knn-demo",
            "--language",
            "zh",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    markdown = markdown_result.stdout
    assert "## Preset Context" in markdown, markdown
    assert "- preset_id: `knn-demo`" in markdown, markdown
    assert "- baseline_source: `preset_fixture_not_question_text`" in markdown, markdown
    assert "- question_text_supplies_baseline: `False`" in markdown, markdown
    assert "--preset knn-demo" in markdown, markdown

    print("auto-research-knn-preset-start-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
