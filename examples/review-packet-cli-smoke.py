#!/usr/bin/env python3
"""Smoke-test the CLI-visible Review Packet formatter."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.review_packet import build_review_packet  # noqa: E402

GOAL_ID = "planned-main-control"
APPROVED_COMMAND = f"goal-harness read-only-map --goal-id {GOAL_ID} --dry-run"


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
        "# Planned Main Control\n\n"
        "## User Todo\n\n"
        "- [ ] Read owner review worksheet first.\n\n"
        "## Agent Todo\n\n"
        "- [ ] Run the read-only map dry-run after owner todo resolution.\n",
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


def append_operator_gate_approval_fixture(root: Path) -> None:
    run_dir = root / "runtime" / "goals" / GOAL_ID / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    generated_at = "2026-01-01T00:01:00+00:00"
    compact_time = generated_at.replace("-", "").replace(":", "")
    json_path = run_dir / f"{compact_time}-operator-gate.json"
    markdown_path = run_dir / f"{compact_time}-operator-gate.md"
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "operator_gate_approved",
        "recommended_action": "把已批准的 agent_command 发给目标项目 agent；这不是写权限授权",
        "health_check": "fixture operator_gate decision=approve; agent_command 1/1",
        "operator_gate": {
            "recorded_at": generated_at,
            "gate": "read_only_map_opt_in",
            "decision": "approve",
            "operator_question": f"是否同意 `{GOAL_ID}` 先执行 read-only map opt-in？",
            "reason_summary": f"同意 {GOAL_ID} 先做 read-only map dry-run，不授权写入或生产动作",
            "agent_command": APPROVED_COMMAND,
        },
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture operator gate approval\n", encoding="utf-8")
    with (run_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    **record,
                    "json_path": str(json_path),
                    "markdown_path": str(markdown_path),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


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


def assert_attention_queue_drives_approved_handoff_over_stale_history() -> None:
    status_payload = {
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "operator_gate_approved",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": "run the approved handoff now",
                    "agent_command": APPROVED_COMMAND,
                    "project_asset": {
                        "owner": "codex",
                        "gate": "none",
                        "next_action": "run the approved handoff now",
                        "stop_condition": "stop if the command needs write control",
                        "agent_todos": {
                            "next": "Run the approved queue-authority dry-run.",
                        },
                    },
                    "source": "latest_run",
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "status": "operator_gate_deferred",
                    "registry_member": True,
                    "latest_runs": [
                        {
                            "generated_at": "2026-01-01T00:00:00+00:00",
                            "classification": "operator_gate_deferred",
                            "recommended_action": "ask the stale operator gate again",
                            "operator_gate": {
                                "decision": "defer",
                                "agent_command": "goal-harness stale-command --dry-run",
                            },
                        }
                    ],
                }
            ]
        },
    }

    payload = build_review_packet(status_payload, goal_id=GOAL_ID)
    packet = payload["packet"]

    assert payload["ok"] is True, payload
    assert payload["kind"] == "codex", payload
    assert payload["status"] == "operator_gate_approved", payload
    assert payload["waiting_on"] == "codex", payload
    assert payload["operator_gate_approved_handoff"] is True, payload
    assert payload["project_agent_command"] == APPROVED_COMMAND, payload
    assert payload["operator_gate_dry_run_command"] is None, payload
    assert payload["operator_gate_decision_commands"] == {}, payload
    assert payload["agent_todo_text"] == "Run the approved queue-authority dry-run.", payload
    assert "类型：Codex" in packet, packet
    assert "operator gate 已批准" in packet, packet
    assert "【用户本地 Gate 记录草稿】" not in packet, packet
    assert "ask the stale operator gate again" not in packet, packet
    assert "goal-harness stale-command" not in packet, packet
    assert APPROVED_COMMAND in packet, packet


def main() -> int:
    assert_attention_queue_drives_approved_handoff_over_stale_history()
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
        assert "待办：Read owner review worksheet first.（先处理/暂缓再判 gate）" in packet, packet
        assert f"建议判断：先确认待办；完成后：同意 {GOAL_ID} 先做 read-only map dry-run；不授权写入或生产动作。" in packet, packet
        assert f"回复：同意 {GOAL_ID} 先做 read-only map dry-run / 暂不同意 + 一句话原因。" in packet, packet
        assert f"--reason-summary '同意 {GOAL_ID} 先做 read-only map dry-run，不授权写入或生产动作'" in packet, packet
        assert "【用户本地 Gate 记录草稿】" in packet, packet
        assert "记录规则：保留 --dry-run 只预览；确认写入 durable operator gate 时再删除 --dry-run。" in packet, packet
        assert "reject / defer 与一句 public-safe 原因" in packet, packet
        assert "operator-gate" in packet, packet
        assert "【给项目 Agent】" in packet, packet
        assert f"目标校验：本段只适用于 goal_id=`{GOAL_ID}`；如果与你当前 active goal 或 registry entry 不一致，停止并回报目标不匹配。" in packet, packet
        assert "上下文规则：本段只携带最小当前指令" in packet, packet
        assert "不要从旧聊天或旧 packet 拼当前状态" in packet, packet
        assert "Agent 待办：Run the read-only map dry-run after owner todo resolution." in packet, packet
        assert "转发条件：只有用户已经明确同意 read-only/controller dry-run 后，才把本段发给项目 Agent。" in packet, packet
        assert "执行边界：只执行下面只读或 dry-run 项目路径；不要运行用户本地 Gate 记录草稿。" in packet, packet
        assert "停止条件：需要真实 approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。" in packet, packet
        assert "read-only-map" in packet, packet
        assert_order(
            packet,
            ["【人只需判断】", "待办：Read owner review worksheet first.", "【用户本地 Gate 记录草稿】", "operator-gate", "【给项目 Agent】", "目标校验", "Agent 待办", "read-only-map"],
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
        assert payload["operator_gate_decision_commands"]["approve"] == payload["operator_gate_dry_run_command"], payload
        assert "--decision reject" in payload["operator_gate_decision_commands"]["reject"], payload
        assert "<public-safe-reason>" in payload["operator_gate_decision_commands"]["reject"], payload
        assert "--decision defer" in payload["operator_gate_decision_commands"]["defer"], payload
        assert "<public-safe-condition>" in payload["operator_gate_decision_commands"]["defer"], payload
        assert payload["project_agent_command"], payload
        assert payload["user_todo_text"] == "Read owner review worksheet first.", payload
        assert payload["agent_todo_text"] == "Run the read-only map dry-run after owner todo resolution.", payload
        assert "转发条件" in payload["packet"], payload
        assert not run_dir.exists(), "json review-packet must not write runtime runs"

        append_operator_gate_approval_fixture(root)
        before_files = sorted(path.name for path in run_dir.iterdir())
        approved_markdown_result = run_cli(
            root,
            registry_path,
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--scan-root",
            str(root / "project"),
        )
        approved_packet = approved_markdown_result.stdout
        assert "类型：Codex" in approved_packet, approved_packet
        assert "问题：operator gate 已批准；是否把短交接发给目标项目 Agent？" in approved_packet, approved_packet
        assert "建议判断：直接转发给项目 Agent；不追加写权限、主控接管或生产动作授权。" in approved_packet, approved_packet
        assert "回复：转发下方【给项目 Agent】即可。" in approved_packet, approved_packet
        assert "这只是执行已批准的只读/dry-run agent_command" in approved_packet, approved_packet
        assert "【用户本地 Gate 记录草稿】" not in approved_packet, approved_packet
        assert "上下文规则：本段只携带最小当前指令" in approved_packet, approved_packet
        assert "不要从旧聊天或旧 packet 拼当前状态" in approved_packet, approved_packet
        assert "Agent 待办：Run the read-only map dry-run after owner todo resolution." in approved_packet, approved_packet
        assert "转发条件：operator gate 已记录为 approve；本段只用于把已批准的 agent_command 交给目标项目 Agent。" in approved_packet, approved_packet
        assert "执行边界：只执行下面命令；这是只读/dry-run 执行，不是写权限、主控接管或生产动作授权。" in approved_packet, approved_packet
        assert "停止条件：命令失败，或需要写入、run history append、生产动作、更高权限时，停下并用中文回报结果。" in approved_packet, approved_packet
        assert APPROVED_COMMAND in approved_packet, approved_packet
        assert_order(
            approved_packet,
            ["【人只需判断】", "operator gate 已批准", "【给项目 Agent】", "Agent 待办", "operator gate 已记录为 approve", APPROVED_COMMAND],
        )

        handoff_only_result = run_cli(
            root,
            registry_path,
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--scan-root",
            str(root / "project"),
            "--handoff-only",
        )
        handoff_only = handoff_only_result.stdout
        assert handoff_only.startswith(f"目标校验：本段只适用于 goal_id=`{GOAL_ID}`"), handoff_only
        assert "【Goal Harness Review Packet】" not in handoff_only, handoff_only
        assert "【人只需判断】" not in handoff_only, handoff_only
        assert "【用户本地 Gate 记录草稿】" not in handoff_only, handoff_only
        assert "operator gate 已记录为 approve" in handoff_only, handoff_only
        assert "不要从旧聊天或旧 packet 拼当前状态" in handoff_only, handoff_only
        assert APPROVED_COMMAND in handoff_only, handoff_only

        approved_json_result = run_cli(
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
        approved_payload = json.loads(approved_json_result.stdout)
        assert approved_payload["ok"] is True, approved_payload
        assert approved_payload["kind"] == "codex", approved_payload
        assert approved_payload["operator_gate_approved_handoff"] is True, approved_payload
        assert approved_payload["project_agent_command"] == APPROVED_COMMAND, approved_payload
        assert approved_payload["agent_todo_text"] == "Run the read-only map dry-run after owner todo resolution.", approved_payload
        assert approved_payload["project_agent_handoff"], approved_payload
        assert "operator gate 已记录为 approve" in approved_payload["project_agent_handoff"], approved_payload
        assert "不要从旧聊天或旧 packet 拼当前状态" in approved_payload["project_agent_handoff"], approved_payload
        assert approved_payload["operator_gate_dry_run_command"] is None, approved_payload
        assert approved_payload["operator_gate_decision_commands"] == {}, approved_payload

        handoff_json_result = run_cli(
            root,
            registry_path,
            "--format",
            "json",
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--scan-root",
            str(root / "project"),
            "--handoff-only",
        )
        handoff_payload = json.loads(handoff_json_result.stdout)
        assert handoff_payload["ok"] is True, handoff_payload
        assert handoff_payload["handoff_only"] is True, handoff_payload
        assert handoff_payload["handoff_text"] == handoff_payload["project_agent_handoff"], handoff_payload
        assert handoff_payload["operator_gate_approved_handoff"] is True, handoff_payload

        after_files = sorted(path.name for path in run_dir.iterdir())
        assert after_files == before_files, "approved review-packet must not write runtime runs"

    print("review-packet-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
