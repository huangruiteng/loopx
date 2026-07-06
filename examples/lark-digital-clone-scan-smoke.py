#!/usr/bin/env python3
"""Smoke-test the Lark digital clone scan CLI with public synthetic input."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def synthetic_messages() -> dict[str, object]:
    return {
        "messages": [
            {
                "message_id": "om_public_fixture_001",
                "chat_id": "oc_public_fixture",
                "chat_name": "Product Sync",
                "sender": "Ada",
                "create_time": "2026-07-04T09:00:00+08:00",
                "text": "@me please review the launch note before 5pm.",
            },
            {
                "message_id": "om_public_fixture_002",
                "chat_id": "oc_public_fixture",
                "chat_name": "Product Sync",
                "sender": "Ben",
                "create_time": "2026-07-04T10:00:00+08:00",
                "text": "@me can you confirm the weekly metrics summary?",
            },
            {
                "message_id": "om_public_fixture_003",
                "chat_id": "oc_public_fixture_2",
                "chat_name": "Research Desk",
                "sender": "Chen",
                "create_time": "2026-07-04T11:00:00+08:00",
                "text": "@me FYI, this customer signal may be useful for the weekly report.",
            },
        ]
    }


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        fixture_path = root / "messages.json"
        out_dir = root / "artifacts"
        fixture_path.write_text(json.dumps(synthetic_messages(), ensure_ascii=False), encoding="utf-8")

        result = run_cli(
            [
                "--format",
                "json",
                "lark-digital-clone",
                "scan",
                "--at-me",
                "--since",
                "24h",
                "--fixture-json",
                str(fixture_path),
                "--out-dir",
                str(out_dir),
                "--skip-auth-check",
            ]
        )
        payload = json.loads(result.stdout)

        assert payload["ok"] is True, payload
        assert payload["schema_version"] == "loopx_lark_digital_clone_scan_v0", payload
        assert payload["mode"] == "fixture", payload
        assert payload["read_boundary"]["external_reads_performed"] is False, payload
        assert payload["write_boundary"]["external_writes_performed"] is False, payload
        assert payload["write_boundary"]["send_requires_user_approval"] is True, payload
        assert payload["summary"]["message_count"] == 3, payload
        assert payload["summary"]["actionable_count"] == 3, payload
        assert payload["summary"]["weekly_material_count"] == 3, payload

        expected_files = {
            "summary_json": "summary.json",
            "today_todo": "today_todo.md",
            "reply_drafts": "reply_drafts.md",
            "weekly_material": "weekly_material.md",
            "send_review": "send_review.md",
            "review_queue": "review_queue.json",
            "loopx_todo_packet": "loopx_todo_packet.json",
        }
        artifacts = payload["artifacts"]
        for key, filename in expected_files.items():
            path = Path(artifacts[key])
            assert path.name == filename, artifacts
            assert path.exists(), path

        review_queue = json.loads(Path(artifacts["review_queue"]).read_text(encoding="utf-8"))
        assert len(review_queue["items"]) == 3, review_queue
        assert all(item["status"] == "needs_user_approval" for item in review_queue["items"]), review_queue
        assert all("--dry-run" in item["dry_run_command"] for item in review_queue["items"]), review_queue

        todo_packet = json.loads(Path(artifacts["loopx_todo_packet"]).read_text(encoding="utf-8"))
        assert todo_packet["schema_version"] == "loopx_lark_digital_clone_todo_packet_v0", todo_packet
        assert todo_packet["write_boundary"] == "candidate_packet_only", todo_packet
        assert len(todo_packet["user_todos"]) == 3, todo_packet
        assert len(todo_packet["agent_todos"]) == 1, todo_packet

        assert "lark-cli" in Path(artifacts["send_review"]).read_text(encoding="utf-8")
        assert "--dry-run" in Path(artifacts["send_review"]).read_text(encoding="utf-8")

    print("lark-digital-clone-scan-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
