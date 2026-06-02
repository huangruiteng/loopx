#!/usr/bin/env python3
"""Smoke-test the CLI-visible Review Packet formatter."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "planned-main-control"


def write_planned_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: planned-high-complexity\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Planned Main Control\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "complex-project",
                        "status": "planned-high-complexity",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "complex_project_read_only_map_v0",
                            "status": "planned",
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry_path


def run_cli(root: Path, registry_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(root / "runtime"),
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def assert_order(text: str, labels: list[str]) -> None:
    positions = [text.index(label) for label in labels]
    assert positions == sorted(positions), (labels, positions, text)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-review-packet-") as tmp:
        root = Path(tmp)
        registry_path = write_planned_registry(root)
        run_dir = root / "runtime" / "goals" / GOAL_ID / "runs"
        markdown_result = run_cli(
            root,
            registry_path,
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--review-url",
            "https://example.invalid/review",
            "--scan-root",
            str(root / "project"),
        )
        packet = markdown_result.stdout
        assert "【Goal Harness Review Packet】" in packet, packet
        assert "类型：Controller" in packet, packet
        assert f"建议判断：同意 {GOAL_ID} 先做 read-only map dry-run；不授权写入或生产动作。" in packet, packet
        assert f"回复：同意 {GOAL_ID} 先做 read-only map dry-run / 暂不同意 + 一句话原因。" in packet, packet
        assert f"--reason-summary '同意 {GOAL_ID} 先做 read-only map dry-run，不授权写入或生产动作'" in packet, packet
        assert "【用户本地 Gate 记录草稿】" in packet, packet
        assert "operator-gate" in packet, packet
        assert "【给项目 Agent】" in packet, packet
        assert f"目标校验：本段只适用于 goal_id=`{GOAL_ID}`；如果与你当前 active goal 或 registry entry 不一致，停止并回报目标不匹配。" in packet, packet
        assert "转发条件：只有用户已经明确同意 read-only/controller dry-run 后，才把本段发给项目 Agent。" in packet, packet
        assert "执行边界：只执行下面只读或 dry-run 项目路径；不要运行用户本地 Gate 记录草稿。" in packet, packet
        assert "停止条件：需要真实 approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。" in packet, packet
        assert "read-only-map" in packet, packet
        assert_order(
            packet,
            ["【人只需判断】", "【用户本地 Gate 记录草稿】", "operator-gate", "【给项目 Agent】", "目标校验", "read-only-map"],
        )
        assert not run_dir.exists(), "review-packet must not write runtime runs"

        json_result = run_cli(
            root,
            registry_path,
            "--format",
            "json",
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--scan-root",
            str(root / "project"),
        )
        payload = json.loads(json_result.stdout)
        assert payload["ok"] is True, payload
        assert payload["kind"] == "controller", payload
        assert payload["operator_gate_dry_run_command"], payload
        assert payload["project_agent_command"], payload
        assert "转发条件" in payload["packet"], payload
        assert not run_dir.exists(), "json review-packet must not write runtime runs"

    print("review-packet-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
