#!/usr/bin/env python3
"""Smoke-test the CLI-visible Review Packet formatter."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.review_packet import build_review_packet  # noqa: E402

STATUS_DATA_CONTRACT_PATH = REPO_ROOT / "docs" / "status-data-contract.md"
GOAL_ID = "planned-main-control"
APPROVED_COMMAND = f"goal-harness read-only-map --goal-id {GOAL_ID} --dry-run"
APPROVED_COMMAND_TAIL = f"read-only-map --goal-id {GOAL_ID} --dry-run"
FOCUS_WAIT_GOAL_ID = "focus-wait-owner-blocker"
LOCAL_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(^|[\s`'\"=:(])(?:/[A-Za-z0-9._-]+(?:/[^\s`'\",)]+)+|[A-Za-z]:[\\/][^\s`'\",)]+)"
)
MAX_PROJECT_AGENT_HANDOFF_LINES = 16
MAX_PROJECT_AGENT_HANDOFF_CHARS = 1800
PROJECT_AGENT_HANDOFF_FORBIDDEN_MARKERS = (
    "【Goal Harness Review Packet】",
    "【人只需判断】",
    "【用户本地 Gate 记录草稿】",
    "问题：",
    "建议判断：",
    "回复：",
    "operator_gate_dry_run_command",
    "operator_gate_decision_commands",
    "latest_runs",
    "run_history",
)


def iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def assert_no_local_paths(value: Any, label: str) -> None:
    for text in iter_strings(value):
        match = LOCAL_ABSOLUTE_PATH_PATTERN.search(text)
        assert match is None, f"{label} leaked local path {match.group(0)!r}: {text}"


def assert_project_agent_handoff_compact(text: str, label: str, *, goal_id: str) -> None:
    lines = text.splitlines()
    assert len(lines) <= MAX_PROJECT_AGENT_HANDOFF_LINES, (label, len(lines), text)
    assert len(text) <= MAX_PROJECT_AGENT_HANDOFF_CHARS, (label, len(text), text)
    assert text.startswith(f"目标校验：本段只适用于 goal_id=`{goal_id}`"), (label, text)
    assert "上下文规则：本段只携带最小当前指令" in text, (label, text)
    assert "不要从旧聊天或旧 packet 拼当前状态" in text, (label, text)
    assert "项目资产来源：" in text, (label, text)
    assert "停止条件：" in text, (label, text)
    assert text.count("```bash") <= 1, (label, text)
    assert text.count("```") <= 2, (label, text)
    for marker in PROJECT_AGENT_HANDOFF_FORBIDDEN_MARKERS:
        assert marker not in text, (label, marker, text)


def assert_status_data_contract_documents_handoff_budget() -> None:
    contract = STATUS_DATA_CONTRACT_PATH.read_text(encoding="utf-8")
    compact_contract = " ".join(contract.split())
    assert "within 16 lines and 1800 characters" in compact_contract, contract
    assert "include at most one command block" in compact_contract, contract
    assert "handoff-only output must not carry the full Review Packet" in compact_contract, contract
    assert "raw `run_history`, or `latest_runs` cold-path evidence" in compact_contract, contract


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
                        "authority_registry": {
                            "path": "docs/meta/DOC_REGISTRY.yaml",
                            "read_status": "read",
                            "default_entry_docs": [
                                "README.md",
                                "docs/GOAL.md",
                            ],
                            "topic_authority": {
                                "goal": "docs/GOAL.md",
                                "validation": "docs/VALIDATION.md",
                            },
                            "project_materials": {
                                "migration_design": {
                                    "role": "current_authority",
                                    "source_kind": "external_doc",
                                    "freshness": "owner_review_required",
                                },
                                "source_repo": {
                                    "role": "source_surface",
                                    "source_kind": "repository",
                                    "freshness": "read_only_status_ok",
                                },
                                "target_repo": {
                                    "role": "implementation_surface",
                                    "source_kind": "repository",
                                    "freshness": "read_only_status_ok",
                                },
                                "historical_note": {
                                    "role": "historical_reference",
                                    "source_kind": "external_doc",
                                    "freshness": "stale",
                                },
                            },
                            "deprecated_source_count": 0,
                            "conflict_risk": "low",
                        },
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


def approved_command_with_local_paths(root: Path) -> str:
    return (
        f"goal-harness --registry {root / 'project' / '.goal-harness' / 'registry.json'} "
        f"--runtime-root {root / 'runtime'} read-only-map --goal-id {GOAL_ID} --dry-run"
    )


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
            "agent_command": approved_command_with_local_paths(root),
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
                    "handoff_readiness": {
                        "handoff_status": "post_handoff_run_seen",
                        "post_handoff_run_seen": True,
                        "post_handoff_latest_run": {
                            "generated_at": "2026-01-01T00:02:00+00:00",
                            "classification": "owner_handoff_consumer_test",
                            "delivery_batch_scale": "implementation",
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
    assert (
        payload["handoff_followthrough_summary"]
        == "post_handoff_run=owner_handoff_consumer_test, scale=implementation, at=2026-01-01T00:02:00+00:00"
    ), payload
    assert payload["project_asset_source"] == "project_asset", payload
    assert_project_agent_handoff_compact(
        payload["project_agent_handoff"],
        "approved attention queue project-agent handoff",
        goal_id=GOAL_ID,
    )
    assert "类型：Codex" in packet, packet
    assert "来源：project_asset（owner/gate/next/stop 来自 attention_queue.project_asset）" in packet, packet
    assert "项目资产来源：project_asset（owner/gate/next/stop 来自 attention_queue.project_asset）" in packet, packet
    assert "交付观测：post_handoff_run=owner_handoff_consumer_test, scale=implementation" in packet, packet
    assert "operator gate 已批准" in packet, packet
    assert "【用户本地 Gate 记录草稿】" not in packet, packet
    assert "ask the stale operator gate again" not in packet, packet
    assert "goal-harness stale-command" not in packet, packet
    assert APPROVED_COMMAND in packet, packet


def assert_focus_wait_owner_blocker_packet() -> None:
    blocker_text = "Provide new owner evidence, a clean baseline, or external eval before delivery resumes."
    status_payload = {
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "attention_queue": {
            "items": [
                {
                    "goal_id": FOCUS_WAIT_GOAL_ID,
                    "status": "state_refreshed",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": "Stay quiet until owner evidence changes.",
                    "source": "fixture",
                    "lifecycle_phase": "focus_wait",
                    "lifecycle_flags": ["continuation_boundary"],
                    "project_asset": {
                        "owner": "codex",
                        "gate": "focus_wait",
                        "next_action": "Stay quiet until owner evidence changes.",
                        "stop_condition": "resume only after owner evidence, clean baseline, or external eval changes",
                        "user_todos": {
                            "open": 1,
                            "done": 0,
                            "total": 1,
                            "next": blocker_text,
                        },
                        "quota": {
                            "compute": 1.0,
                            "state": "focus_wait",
                            "spent_slots": 0,
                            "allowed_slots": 1440,
                            "reason": "focus wait: delivery lane has a continuation boundary",
                        },
                    },
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 1440,
                        "spent_slots": 0,
                        "state": "focus_wait",
                        "reason": "focus wait: delivery lane has a continuation boundary",
                    },
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": FOCUS_WAIT_GOAL_ID,
                    "status": "active-read-only",
                    "registry_member": True,
                    "latest_runs": [
                        {
                            "generated_at": "2026-01-01T00:02:00+00:00",
                            "classification": "state_refreshed",
                            "recommended_action": "Stay quiet until owner evidence changes.",
                        }
                    ],
                }
            ]
        },
    }

    payload = build_review_packet(status_payload, goal_id=FOCUS_WAIT_GOAL_ID)
    packet = payload["packet"]

    assert payload["ok"] is True, payload
    assert payload["kind"] == "focus_wait", payload
    assert payload["status"] == "state_refreshed", payload
    assert payload["waiting_on"] == "codex", payload
    assert payload["project_asset_source"] == "project_asset", payload
    assert payload["owner_blocker_text"] == blocker_text, payload
    assert payload["user_todo_text"] == blocker_text, payload
    assert_project_agent_handoff_compact(
        payload["project_agent_handoff"],
        "focus-wait project-agent handoff",
        goal_id=FOCUS_WAIT_GOAL_ID,
    )
    assert payload["operator_gate_dry_run_command"] is None, payload
    assert payload["operator_gate_decision_commands"] == {}, payload
    assert "类型：Focus Wait" in packet, packet
    assert f"解锁条件：{blocker_text}（有新证据或明确暂缓后再调整 focus）" in packet, packet
    assert "问题：是否继续保持 focus wait，直到 owner blocker 有新证据？" in packet, packet
    assert "建议判断：继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。" in packet, packet
    assert "focus wait 不是 delivery 授权" in packet, packet
    assert "【用户本地 Gate 记录草稿】" not in packet, packet
    assert "转发条件：仅当目标项目 Agent 需要当前等待边界时转发；这不是恢复 delivery 的授权。" in packet, packet
    assert "不要继续实现、adapter work、写入或生产动作" in packet, packet
    assert "保持 focus_wait 并用中文回报仍在等待什么" in packet, packet
    assert "history \\" in packet, packet
    assert "read-only-map" not in packet, packet
    assert_order(
        packet,
        ["【人只需判断】", "解锁条件：", "问题：是否继续保持 focus wait", "【给项目 Agent】", "转发条件：仅当目标项目 Agent", "history \\"],
    )


def assert_missing_project_asset_review_packet_fallback() -> None:
    status_payload = {
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "attention_queue": {
            "items": [
                {
                    "goal_id": "legacy-status-only",
                    "status": "state_refreshed",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": "Continue only through raw status fallback.",
                    "agent_command": "goal-harness status --goal-id legacy-status-only",
                    "source": "latest_run",
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": "legacy-status-only",
                    "status": "active-read-only",
                    "registry_member": True,
                    "latest_runs": [],
                }
            ]
        },
    }

    payload = build_review_packet(status_payload, goal_id="legacy-status-only")
    packet = payload["packet"]

    assert payload["ok"] is True, payload
    assert payload["project_asset_source"] == "legacy_raw_fallback", payload
    assert_project_agent_handoff_compact(
        payload["project_agent_handoff"],
        "legacy fallback project-agent handoff",
        goal_id="legacy-status-only",
    )
    assert "来源：legacy/raw fallback" in packet, packet
    assert "不能当 owner/gate/stop authority" in packet, packet
    assert "项目资产来源：legacy/raw fallback" in payload["project_agent_handoff"], payload
    assert "owner/gate/stop authority" in payload["project_agent_handoff"], payload
    assert "项目资产来源：project_asset" not in packet, packet


def main() -> int:
    help_result = subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", "review-packet", "--help"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    compact_help = " ".join(help_result.stdout.split())
    assert "JSON output returns a minimized handoff payload" in compact_help, help_result.stdout
    assert "JSON output keeps the full payload" not in compact_help, help_result.stdout

    assert_status_data_contract_documents_handoff_budget()
    assert_attention_queue_drives_approved_handoff_over_stale_history()
    assert_focus_wait_owner_blocker_packet()
    assert_missing_project_asset_review_packet_fallback()
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
        assert "材料：authority/material: topics=2, materials=4, repositories=2, owner_review_required=1, stale=1, current_authority=1, risk=low（仅脱敏计数；不含内部链接、路径或正文。）" in packet, packet
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
        assert "材料上下文：authority/material: topics=2, materials=4, repositories=2, owner_review_required=1, stale=1, current_authority=1, risk=low" in packet, packet
        assert "不要要求内部链接或原文" in packet, packet
        assert "转发条件：只有用户已经明确同意 read-only/controller dry-run 后，才把本段发给项目 Agent。" in packet, packet
        assert "执行边界：只执行下面只读或 dry-run 项目路径；不要运行用户本地 Gate 记录草稿。" in packet, packet
        assert "停止条件：需要真实 approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。" in packet, packet
        assert "read-only-map" in packet, packet
        assert_order(
            packet,
            ["材料：authority/material", "【人只需判断】", "待办：Read owner review worksheet first.", "【用户本地 Gate 记录草稿】", "operator-gate", "【给项目 Agent】", "目标校验", "Agent 待办", "材料上下文", "read-only-map"],
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
        assert_no_local_paths(
            {
                "project_agent_command": payload["project_agent_command"],
                "project_agent_handoff": payload["project_agent_handoff"],
            },
            "controller project-agent handoff",
        )
        assert_project_agent_handoff_compact(
            payload["project_agent_handoff"],
            "controller project-agent handoff",
            goal_id=GOAL_ID,
        )
        assert payload["user_todo_text"] == "Read owner review worksheet first.", payload
        assert payload["agent_todo_text"] == "Run the read-only map dry-run after owner todo resolution.", payload
        assert payload["authority_summary"] == "authority/material: topics=2, materials=4, repositories=2, owner_review_required=1, stale=1, current_authority=1, risk=low", payload
        assert "转发条件" in payload["packet"], payload
        assert not run_dir.exists(), "json review-packet must not write runtime runs"

        controller_handoff_json_result = run_cli(
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
        controller_handoff_payload = json.loads(controller_handoff_json_result.stdout)
        assert controller_handoff_payload["ok"] is True, controller_handoff_payload
        assert controller_handoff_payload["handoff_only"] is True, controller_handoff_payload
        assert "packet" not in controller_handoff_payload, controller_handoff_payload
        assert "operator_gate_dry_run_command" not in controller_handoff_payload, controller_handoff_payload
        assert "operator_gate_decision_commands" not in controller_handoff_payload, controller_handoff_payload
        assert controller_handoff_payload["handoff_text"] == controller_handoff_payload["project_agent_handoff"], controller_handoff_payload
        assert_no_local_paths(controller_handoff_payload, "controller handoff-only json")
        assert_project_agent_handoff_compact(
            controller_handoff_payload["handoff_text"],
            "controller handoff-only json",
            goal_id=GOAL_ID,
        )

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
        assert "材料上下文：authority/material: topics=2, materials=4, repositories=2, owner_review_required=1, stale=1, current_authority=1, risk=low" in approved_packet, approved_packet
        assert "转发条件：operator gate 已记录为 approve；本段只用于把已批准的 agent_command 交给目标项目 Agent。" in approved_packet, approved_packet
        assert "执行边界：只执行下面命令；这是只读/dry-run 执行，不是写权限、主控接管或生产动作授权。" in approved_packet, approved_packet
        assert "停止条件：命令失败，或需要写入、run history append、生产动作、更高权限时，停下并用中文回报结果。" in approved_packet, approved_packet
        assert APPROVED_COMMAND_TAIL in approved_packet, approved_packet
        assert "<local-path>" in approved_packet, approved_packet
        assert_order(
            approved_packet,
            ["【人只需判断】", "operator gate 已批准", "【给项目 Agent】", "Agent 待办", "operator gate 已记录为 approve", APPROVED_COMMAND_TAIL],
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
        assert APPROVED_COMMAND_TAIL in handoff_only, handoff_only
        assert "<local-path>" in handoff_only, handoff_only
        assert_no_local_paths(handoff_only, "handoff-only markdown")
        assert_project_agent_handoff_compact(
            handoff_only,
            "handoff-only markdown",
            goal_id=GOAL_ID,
        )

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
        assert APPROVED_COMMAND_TAIL in approved_payload["project_agent_command"], approved_payload
        assert "<local-path>" in approved_payload["project_agent_command"], approved_payload
        assert approved_payload["agent_todo_text"] == "Run the read-only map dry-run after owner todo resolution.", approved_payload
        assert approved_payload["authority_summary"] == payload["authority_summary"], approved_payload
        assert approved_payload["project_agent_handoff"], approved_payload
        assert "operator gate 已记录为 approve" in approved_payload["project_agent_handoff"], approved_payload
        assert "不要从旧聊天或旧 packet 拼当前状态" in approved_payload["project_agent_handoff"], approved_payload
        assert_no_local_paths(
            {
                "project_agent_command": approved_payload["project_agent_command"],
                "project_agent_handoff": approved_payload["project_agent_handoff"],
            },
            "approved project-agent handoff",
        )
        assert_project_agent_handoff_compact(
            approved_payload["project_agent_handoff"],
            "approved project-agent handoff",
            goal_id=GOAL_ID,
        )
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
        assert "packet" not in handoff_payload, handoff_payload
        assert "operator_gate_dry_run_command" not in handoff_payload, handoff_payload
        assert "operator_gate_decision_commands" not in handoff_payload, handoff_payload
        assert_no_local_paths(
            {
                "handoff_text": handoff_payload["handoff_text"],
                "project_agent_handoff": handoff_payload["project_agent_handoff"],
                "project_agent_command": handoff_payload["project_agent_command"],
            },
            "handoff-only json",
        )
        assert_project_agent_handoff_compact(
            handoff_payload["handoff_text"],
            "handoff-only json",
            goal_id=GOAL_ID,
        )

        after_files = sorted(path.name for path in run_dir.iterdir())
        assert after_files == before_files, "approved review-packet must not write runtime runs"

    print("review-packet-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
