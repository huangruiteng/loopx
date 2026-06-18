#!/usr/bin/env python3
"""Smoke-test local-only dreaming proposal generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "dreaming-dry-run-fixture"


def run_cli(*args: str, registry_path: Path, runtime: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def append_run(runs_dir: Path, *, generated_at: str, classification: str, action: str) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    json_path = runs_dir / f"{generated_at.replace(':', '-')}.json"
    markdown_path = runs_dir / f"{generated_at.replace(':', '-')}.md"
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": classification,
        "recommended_action": action,
        "delivery_outcome": "outcome_progress",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    json_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture Run\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".goal-harness" / "registry.json"
    runs_dir = runtime / "goals" / GOAL_ID / "runs"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Dreaming Dry-Run Fixture\n\n"
        "## Next Action\n\n"
        "- Continue the selected delivery lane after operator review.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Keep the dry-run proposal advisory until approved.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "dreaming-dry-run-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    append_run(
        runs_dir,
        generated_at="2026-01-01T00:03:00+00:00",
        classification="docs_governance_refactor_warning_merged",
        action="A repeated docs governance refactor warning was validated.",
    )
    append_run(
        runs_dir,
        generated_at="2026-01-01T00:02:00+00:00",
        classification="quota_slot_spent",
        action="Spend accounting should not be evidence for dreaming proposals.",
    )
    append_run(
        runs_dir,
        generated_at="2026-01-01T00:01:00+00:00",
        classification="docs_governance_refactor_warning_merged",
        action="Another refactor warning points at duplicated state handling.",
    )
    append_run(
        runs_dir,
        generated_at="2026-01-01T00:00:00+00:00",
        classification="state_contract_doc_update",
        action="Documented state interaction model changes.",
    )
    return registry_path, runtime, state_path, runs_dir / "index.jsonl"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-dreaming-dry-run-") as tmp:
        registry_path, runtime, state_path, index_path = write_fixture(Path(tmp))
        before_state = state_path.read_text(encoding="utf-8")
        before_index = index_path.read_text(encoding="utf-8")

        payload = run_cli(
            "dreaming",
            "dry-run",
            "--goal-id",
            GOAL_ID,
            "--limit",
            "10",
            registry_path=registry_path,
            runtime=runtime,
        )

        assert payload["ok"] is True, payload
        assert payload["dry_run"] is True, payload
        assert payload["classification"] == "dreaming_refactor_warning", payload
        assert payload["proposal_type"] == "refactor_warning", payload
        assert len(payload["recent_evidence"]) == 3, payload
        preview = payload["run_record_preview"]
        assert preview["agent_command"] is None, preview
        assert preview["dreaming"]["advisory"] is True, preview
        assert preview["dreaming"]["execution_allowed"] is False, preview
        assert preview["dreaming"]["delivery_spend_allowed"] is False, preview
        side_effects = payload["side_effects"]
        assert side_effects["runtime_history_appended"] is False, side_effects
        assert side_effects["active_state_mutated"] is False, side_effects
        assert side_effects["quota_spent"] is False, side_effects
        assert state_path.read_text(encoding="utf-8") == before_state
        assert index_path.read_text(encoding="utf-8") == before_index

    print("dreaming-dry-run-proposal-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
