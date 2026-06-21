#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loopx.contract import check_contract


def write_run(run_dir: Path, goal_id: str, *, duplicate_kind: str) -> None:
    run_dir.mkdir(parents=True)
    json_artifact = run_dir / "run.json"
    markdown_artifact = run_dir / "run.md"
    json_artifact.write_text(json.dumps({"ok": True}), encoding="utf-8")
    markdown_artifact.write_text("# Smoke Run\n", encoding="utf-8")
    record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": goal_id,
        "classification": "state_refreshed",
        "recommended_action": "continue from public-safe smoke evidence",
        "json_path": str(json_artifact),
        "markdown_path": str(markdown_artifact),
    }
    lines = [record]
    if duplicate_kind == "reward_overlay":
        lines.append(
            {
                **record,
                "human_reward": {
                    "recorded_at": "2026-01-01T00:00:01+00:00",
                    "decision": "continue",
                    "reward": "positive",
                    "reason_summary": "operator accepted the smoke result",
                    "follow_up": "let the next agent read run history",
                },
            }
        )
    elif duplicate_kind == "plain_duplicate":
        lines.append(dict(record))
    else:
        raise ValueError(f"unknown duplicate_kind: {duplicate_kind}")
    (run_dir / "index.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
        encoding="utf-8",
    )


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    runtime_root = root / "runtime"
    project = root / "project"
    project.mkdir(parents=True)
    reward_state_file = project / ".codex" / "goals" / "reward-overlay-goal" / "ACTIVE_GOAL_STATE.md"
    duplicate_state_file = project / ".codex" / "goals" / "plain-duplicate-goal" / "ACTIVE_GOAL_STATE.md"
    reward_state_file.parent.mkdir(parents=True)
    duplicate_state_file.parent.mkdir(parents=True)
    reward_state_file.write_text("---\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n", encoding="utf-8")
    duplicate_state_file.write_text("---\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n", encoding="utf-8")
    local_private_doc = project / ".local" / "managed_doc" / "PRIVATE_DRAFT.md"
    local_private_doc.parent.mkdir(parents=True)
    private_host = "private-docs.example.invalid"
    local_private_doc.write_text(f"https://{private_host}/docx/private-draft\n", encoding="utf-8")

    write_run(runtime_root / "goals" / "reward-overlay-goal" / "runs", "reward-overlay-goal", duplicate_kind="reward_overlay")
    write_run(runtime_root / "goals" / "plain-duplicate-goal" / "runs", "plain-duplicate-goal", duplicate_kind="plain_duplicate")

    registry = root / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": "reward-overlay-goal",
                        "repo": str(project),
                        "state_file": ".codex/goals/reward-overlay-goal/ACTIVE_GOAL_STATE.md",
                        "domain": "smoke",
                        "status": "connected-read-only",
                        "adapter": {"kind": "smoke", "status": "connected-read-only"},
                    },
                    {
                        "id": "plain-duplicate-goal",
                        "repo": str(project),
                        "state_file": ".codex/goals/plain-duplicate-goal/ACTIVE_GOAL_STATE.md",
                        "domain": "smoke",
                        "status": "connected-read-only",
                        "adapter": {"kind": "smoke", "status": "connected-read-only"},
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry, runtime_root, project


def main() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        registry, runtime_root, project = write_fixture(Path(raw_tmp))
        payload = check_contract(
            registry_path=registry,
            runtime_root_override=str(runtime_root),
            scan_roots=[project],
            limit=20,
        )
        checks = "\n".join(payload["checks"])
        warnings = "\n".join(payload["warnings"])
        assert payload["ok"] is True, payload
        assert "reward-overlay-goal: reward overlay rows raw=2 unique=1 overlays=1" in checks, payload
        assert "reward-overlay-goal: duplicate index rows" not in warnings, payload
        assert "plain-duplicate-goal: duplicate index rows raw=2 unique=1" in warnings, payload
        assert "loopx history inspect-index-duplicates --goal-id plain-duplicate-goal" in warnings, payload
        assert not any(".local/managed_doc" in item for item in payload["errors"]), payload

    print("contract-reward-overlay-smoke ok")


if __name__ == "__main__":
    main()
