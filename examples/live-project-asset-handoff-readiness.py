#!/usr/bin/env python3
"""Check a live project_asset-backed handoff path without recording private data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATH_PATTERN = re.compile(r"(?<!<)/(?:Users|Volumes|var/folders|tmp|private/tmp)/[^\s`'\"<>]+")
SECRET_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+[a-z0-9._~+/=-]{16,}|(?<![a-z0-9_])(?:ak|sk)[-_=:][a-z0-9_=-]{10,}|\btoken\s*[=:]\s*[^\s`'\"<>]{12,})"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that a real status queue item uses project_asset as the "
            "authority for quota should-run and project-agent handoff-only output."
        )
    )
    parser.add_argument("--goal-id", required=True, help="Live goal id to check.")
    parser.add_argument(
        "--agent-id",
        help=(
            "Registered agent id to use for identity-scoped status, quota, "
            "and handoff packet checks."
        ),
    )
    parser.add_argument(
        "--registry",
        default=str(Path.home() / ".codex" / "loopx" / "registry.global.json"),
        help="LoopX registry path. Defaults to the shared global registry.",
    )
    parser.add_argument("--runtime-root", help="Optional LoopX runtime root.")
    return parser.parse_args()


def agent_id_args(args: argparse.Namespace) -> list[str]:
    return ["--agent-id", args.agent_id] if args.agent_id else []


def run_loopx(args: argparse.Namespace, *command: str) -> dict[str, Any]:
    cli = [sys.executable, "-m", "loopx.cli", "--registry", args.registry]
    if args.runtime_root:
        cli.extend(["--runtime-root", args.runtime_root])
    cli.extend(["--format", "json", *command])
    result = subprocess.run(
        cli,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def attention_item(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any]:
    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in items:
        if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id:
            return item
    raise AssertionError(f"goal {goal_id!r} is not in the live attention queue")


def assert_public_safe_text(text: str, *, label: str) -> None:
    local_paths = LOCAL_PATH_PATTERN.findall(text)
    assert not local_paths, f"{label} leaked local paths: {local_paths[:3]}"
    secret_like = SECRET_PATTERN.findall(text)
    assert not secret_like, f"{label} leaked secret-like material"


def assert_project_asset_handoff(args: argparse.Namespace) -> dict[str, Any]:
    status_payload = run_loopx(
        args,
        "status",
        "--limit",
        "20",
        "--goal-id",
        args.goal_id,
        *agent_id_args(args),
    )
    assert status_payload.get("ok") is True, status_payload
    item = attention_item(status_payload, args.goal_id)
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    assert project_asset, "live attention item is not project_asset-backed"
    readiness = item.get("handoff_readiness") if isinstance(item.get("handoff_readiness"), dict) else {}
    assert readiness.get("ready") is True, readiness
    assert readiness.get("codex_ready") is True, readiness
    assert readiness.get("source") == "project_asset", readiness
    assert readiness.get("quota_state") == "eligible", readiness
    expected_probe = f"loopx review-packet --goal-id {args.goal_id} --handoff-only"
    assert readiness.get("next_probe") == expected_probe, readiness
    checks = readiness.get("checks") if isinstance(readiness.get("checks"), dict) else {}
    for check in (
        "project_asset_backed",
        "same_source_should_run",
        "codex_ready",
        "handoff_has_next_action",
        "handoff_has_stop_condition",
        "handoff_sanitized_surface",
    ):
        assert checks.get(check) is True, readiness

    should_run = run_loopx(
        args,
        "quota",
        "should-run",
        "--goal-id",
        args.goal_id,
        *agent_id_args(args),
    )
    assert should_run.get("ok") is True, should_run
    assert should_run.get("project_asset_source") == "project_asset", should_run
    agent_lane_next_action = (
        item.get("agent_lane_next_action")
        if isinstance(item.get("agent_lane_next_action"), dict)
        else {}
    )
    expected_action = project_asset.get("next_action")
    if args.agent_id and agent_lane_next_action:
        expected_action = agent_lane_next_action.get("text")
        should_run_agent_lane = (
            should_run.get("agent_lane_next_action")
            if isinstance(should_run.get("agent_lane_next_action"), dict)
            else {}
        )
        assert should_run_agent_lane.get("todo_id") == agent_lane_next_action.get("todo_id"), should_run
        assert str(should_run.get("recommended_action") or "").startswith(
            str(expected_action or "")[:200]
        ), should_run
    else:
        assert should_run.get("recommended_action") == expected_action, should_run
    assert should_run.get("state") == project_asset.get("quota", {}).get("state"), should_run
    assert should_run.get("quota", {}).get("compute") == project_asset.get("quota", {}).get("compute"), should_run
    assert should_run.get("goal_boundary", {}).get("stop_condition") == project_asset.get("stop_condition"), should_run
    should_run_readiness = (
        should_run.get("handoff_readiness")
        if isinstance(should_run.get("handoff_readiness"), dict)
        else {}
    )
    assert should_run_readiness.get("handoff_status") == readiness.get("handoff_status"), should_run
    assert should_run_readiness.get("post_handoff_run_seen") == readiness.get("post_handoff_run_seen"), should_run

    for field, summary_key in (("user_todos", "user_todo_summary"), ("agent_todos", "agent_todo_summary")):
        asset_todos = project_asset.get(field) if isinstance(project_asset.get(field), dict) else {}
        if not asset_todos:
            continue
        summary = should_run.get(summary_key) if isinstance(should_run.get(summary_key), dict) else {}
        if args.agent_id and field == "agent_todos":
            assert summary.get("current_agent_claimed_open_count") is not None, should_run
            assert summary.get("claim_scope", {}).get("agent_id") == args.agent_id, should_run
            continue
        assert summary.get("open_count") == asset_todos.get("open"), should_run
        assert summary.get("total_count") == asset_todos.get("total"), should_run

    handoff = run_loopx(
        args,
        "review-packet",
        "--goal-id",
        args.goal_id,
        "--handoff-only",
        "--limit",
        "20",
        *agent_id_args(args),
    )
    assert handoff.get("ok") is True, handoff
    assert handoff.get("handoff_only") is True, handoff
    handoff_text = str(handoff.get("handoff_text") or "")
    assert f"goal_id=`{args.goal_id}`" in handoff_text, handoff_text
    assert "项目资产来源：project_asset" in handoff_text, handoff_text
    assert "不要从旧聊天或旧 packet 拼当前状态" in handoff_text, handoff_text
    assert "停止条件：" in handoff_text, handoff_text
    assert "【LoopX Review Packet】" not in handoff_text, handoff_text
    assert "【人只需判断】" not in handoff_text, handoff_text
    assert "operator_gate_decision_commands" not in json.dumps(handoff, ensure_ascii=False), handoff
    assert_public_safe_text(handoff_text, label="handoff-only markdown")

    return {
        "ok": True,
        "goal_id": args.goal_id,
        "status": item.get("status"),
        "project_asset_source": should_run.get("project_asset_source"),
        "status_readiness": readiness.get("ready"),
        "should_run": should_run.get("should_run"),
        "quota_state": should_run.get("state"),
        "handoff_lines": len(handoff_text.splitlines()),
        "handoff_chars": len(handoff_text),
        "stop_condition": project_asset.get("stop_condition"),
    }


def main() -> int:
    args = parse_args()
    payload = assert_project_asset_handoff(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
