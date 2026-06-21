#!/usr/bin/env python3
"""Smoke-test public-safe ALE candidate task-data scanning."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    build_agents_last_exam_candidate_task_data_scan,
)


def write_task(source: Path, task_id: str, main_py: str) -> None:
    category, name = task_id.split("/", 1)
    task = source / "tasks" / category / name
    task.mkdir(parents=True)
    (task / "main.py").write_text(main_py, encoding="utf-8")


def make_source(root: Path, selected_tasks: list[str]) -> Path:
    source = root / "agents-last-exam"
    selected = source / "selected_tasks" / "unlicensed"
    selected.mkdir(parents=True)
    (source / "selected_tasks" / "linux_only.txt").write_text(
        "\n".join(selected_tasks) + "\n",
        encoding="utf-8",
    )
    (selected / "near-term.txt").write_text("", encoding="utf-8")
    write_task(
        source,
        "computing_math/no_data_task",
        '"""SECRET_PROMPT_SHOULD_NOT_LEAK"""\n\n'
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class TaskConfig:\n"
        "    REQUIRES_TASK_DATA: bool = False\n",
    )
    write_task(
        source,
        "computing_math/default_data_task",
        '"""SECRET_DEFAULT_PROMPT_SHOULD_NOT_LEAK"""\n\n'
        "class TaskConfig:\n"
        "    DOMAIN_NAME = 'computing_math'\n",
    )
    write_task(
        source,
        "computing_math/true_data_task",
        "class TaskConfig:\n"
        "    def __post_init__(self):\n"
        "        self.REQUIRES_TASK_DATA = True\n",
    )
    write_task(
        source,
        "demo/tool_smoke",
        "class TaskConfig:\n"
        "    REQUIRES_TASK_DATA: bool = False\n",
    )
    return source


def assert_public_safe(payload: dict[str, object], temp_root: Path) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        str(temp_root),
        "SECRET_PROMPT_SHOULD_NOT_LEAK",
        "SECRET_DEFAULT_PROMPT_SHOULD_NOT_LEAK",
        "task_card.json",
        "task_instructions.md",
        "trajectory.json",
        "screenshot.png",
        "OPENAI_API_KEY",
        "CODEX_ACCESS_TOKEN",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["task_config_line_scan"] is True
    assert boundary["task_config_source_content_recorded"] is False
    assert boundary["task_card_content_read"] is False
    assert boundary["script_content_read"] is False
    assert boundary["task_instruction_file_read"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["local_paths_recorded"] is False


def run_function_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-candidate-task-data-") as tmp:
        temp_root = Path(tmp)
        source = make_source(
            temp_root,
            [
                "computing_math/no_data_task",
                "computing_math/default_data_task",
                "computing_math/true_data_task",
                "demo/tool_smoke",
            ],
        )
        payload = build_agents_last_exam_candidate_task_data_scan(
            source_root=str(source),
        )
        assert payload["schema_version"] == "agents_last_exam_candidate_task_data_scan_v0", payload
        assert payload["ready"] is True, payload
        summary = payload["scan_summary"]
        assert isinstance(summary, dict)
        assert summary["selected_task_count"] == 4, payload
        assert summary["formal_no_task_data_candidate_count"] == 1, payload
        assert summary["demo_no_task_data_candidate_count"] == 1, payload
        candidates = payload["candidate_tasks"]
        assert isinstance(candidates, dict)
        assert candidates["eligible_no_task_data_candidates"] == [
            "computing_math__no_data_task"
        ], payload
        assert_public_safe(payload, temp_root)

        demo_only_source = make_source(temp_root / "demo-only", ["demo/tool_smoke"])
        demo_blocked = build_agents_last_exam_candidate_task_data_scan(
            source_root=str(demo_only_source),
        )
        assert demo_blocked["ready"] is False, demo_blocked
        assert demo_blocked["first_blocker"] == "no_formal_no_task_data_candidate_found", demo_blocked
        assert_public_safe(demo_blocked, temp_root)

        demo_allowed = build_agents_last_exam_candidate_task_data_scan(
            source_root=str(demo_only_source),
            allow_demo_candidate=True,
        )
        assert demo_allowed["ready"] is True, demo_allowed
        assert demo_allowed["candidate_tasks"]["eligible_no_task_data_candidates"] == [
            "demo__tool_smoke"
        ], demo_allowed
        assert_public_safe(demo_allowed, temp_root)


def run_cli_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-candidate-task-data-cli-") as tmp:
        temp_root = Path(tmp)
        source = make_source(temp_root, ["computing_math/no_data_task"])
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-candidate-task-data-scan",
                "--source-root",
                str(source),
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["ready"] is True, payload
        assert_public_safe(payload, temp_root)


if __name__ == "__main__":
    run_function_smoke()
    run_cli_smoke()
    print("agents-last-exam-candidate-task-data-scan-smoke ok")
