#!/usr/bin/env python3
"""Smoke-test the explicit KNN demo preset on auto-research start."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.knn_demo_workspace import (  # noqa: E402
    materialize_knn_demo_workspace,
)
from loopx.capabilities.auto_research.demo_e2e import (  # noqa: E402
    _seed_visible_demo_control_plane,
)
from loopx.capabilities.auto_research.demo_supervisor import (  # noqa: E402
    build_auto_research_demo_supervisor_plan,
)
from loopx.capabilities.auto_research.user_contract import (  # noqa: E402
    build_auto_research_preset_context,
)

QUESTION = "如何提升 KNN 精确近邻检索速度?"


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
    assert preset["baseline_source"] == "generated_knn_benchmark_workspace", preset
    assert preset["question_text_supplies_baseline"] is False, preset
    assert preset["metric_name"] == "speedup", preset
    assert preset["baseline_metric"] == 1.0, preset
    assert preset["benchmark_contract_file"] == "research_contract.public.json", preset
    assert preset["editable_scope"] == ["solution.py"], preset
    assert preset["protected_scope"] == ["task.py", "eval.py", "eval.sh"], preset
    assert preset["dev_eval_command"] == "bash eval.sh dev", preset
    assert preset["holdout_eval_command"] == "bash eval.sh test", preset
    assert payload["preset_context"] == preset, payload
    assert payload["route_contract"]["preset_id"] == "knn-demo", payload
    assert payload["route_contract"]["preset_baseline_source"] == (
        "generated_knn_benchmark_workspace"
    ), payload
    assert "--preset knn-demo" in contract["one_click_start"]["command"], contract
    assert "--preset knn-demo" in payload["commands"]["one_question_start"], payload
    assert payload["contract_acceptance"]["accepted"] is True, payload

    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id="loopx-auto-research-knn-smoke",
        open_question=QUESTION,
        preset_context=build_auto_research_preset_context("knn-demo"),
        output_language="zh",
    )
    role_steps = {
        role["role_id"]: role["role_profile"]["visible_first_steps"]
        for role in supervisor["lanes"]
    }
    assert "role-specific public-safe artifact" in " ".join(
        role_steps["research_curator"]
    ), role_steps
    assert "two-row hypothesis table" in " ".join(
        role_steps["hypothesis_proposer"]
    ), role_steps
    assert "save the last JSON line as baseline dev evidence" in " ".join(
        role_steps["research_executor"]
    ), role_steps
    assert "feed the real evaluator JSON" in " ".join(
        role_steps["research_executor"]
    ), role_steps
    assert "protected-scope cleanliness" in " ".join(
        role_steps["evaluator_promoter"]
    ), role_steps

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        _visible_control, registry, _runtime_root = _seed_visible_demo_control_plane(
            demo_root=temp,
            goal_id="loopx-auto-research-knn-smoke",
            objective=QUESTION,
            supervisor=supervisor,
            preset_context=preset,
        )
        registry_payload = json.loads(registry.read_text(encoding="utf-8"))
        goal = next(
            item
            for item in registry_payload["goals"]
            if item["id"] == "loopx-auto-research-knn-smoke"
        )
        assert "solution.py" in goal["coordination"]["write_scope"], goal
        assert "benchmark_runner" in goal["coordination"]["available_capabilities"], goal

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
    assert "- baseline_source: `generated_knn_benchmark_workspace`" in markdown, markdown
    assert "- question_text_supplies_baseline: `False`" in markdown, markdown
    assert "- dev_eval_command: `bash eval.sh dev`" in markdown, markdown
    assert "- holdout_eval_command: `bash eval.sh test`" in markdown, markdown
    assert "--preset knn-demo" in markdown, markdown

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "knn-workspace"
        marker = materialize_knn_demo_workspace(
            workspace,
            goal_id="loopx-auto-research-knn-smoke",
        )
        contract_payload = json.loads((workspace / "research_contract.public.json").read_text(encoding="utf-8"))
        assert marker["goal_id"] == "loopx-auto-research-knn-smoke", marker
        assert contract_payload["goal_id"] == "loopx-auto-research-knn-smoke", contract_payload
        assert marker["dev_eval_command"] == "bash eval.sh dev", marker
        assert marker["holdout_eval_command"] == "bash eval.sh test", marker
        assert (workspace / "solution.py").exists(), marker
        assert (workspace / "task.py").exists(), marker
        assert (workspace / "research_contract.public.json").exists(), marker
        dev_result = subprocess.run(
            ["bash", "eval.sh", "dev"],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "score:" in dev_result.stdout, dev_result.stdout
        dev_payload = json.loads(dev_result.stdout.strip().splitlines()[-1])
        assert dev_payload["ok"] is True, dev_payload
        assert dev_payload["metric_name"] == "speedup", dev_payload
        assert dev_payload["score"] > 0.0, dev_payload

    print("auto-research-knn-preset-start-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
