#!/usr/bin/env python3
"""Smoke-test explicit durable Next Action writeback and projection drift."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import loopx.state_refresh as state_refresh
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown
from loopx.status import collect_status, render_status_markdown


GOAL_ID = "next-action-projection-goal"
ACTIVE_NEXT_ACTION = "Keep the durable route on the broad public PoC lane."
RUN_RECOMMENDATION = "Inspect the vliw suite result before changing the durable route."
UPDATED_NEXT_ACTION = "Promote the vliw repair slice as the durable next action."
UPDATED_RUN_RECOMMENDATION = "Validate the vliw repair slice and then write compact evidence."
SIDE_AGENT_ACTION = "Polish the hosted frontstage public case card."


def write_fixture(root: Path, *, include_next_action: bool = True) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True)
    next_action_section = (
        "## Next Action\n\n"
        f"- {ACTIVE_NEXT_ACTION}\n\n"
        if include_next_action
        else ""
    )
    state_path.write_text(
        "---\n"
        "status: active\n"
        "owner_mode: goal\n"
        'objective: "Keep next-action projections explicit."\n'
        "updated_at: 2026-06-22T00:00:00+00:00\n"
        "---\n\n"
        "# Next Action Projection Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] Validate the primary public PoC control-plane lane.\n"
        "  <!-- loopx:todo todo_id=todo_primary status=open "
        "task_class=advancement_task claimed_by=codex-main-control -->\n"
        f"- [ ] [P1] {SIDE_AGENT_ACTION}\n"
        "  <!-- loopx:todo todo_id=todo_side status=open "
        "task_class=advancement_task claimed_by=codex-side-bypass -->\n\n"
        f"{next_action_section}"
        "## Progress Ledger\n\n"
        "- Fixture initialized.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-06-22T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "next-action-projection-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                        "coordination": {
                            "primary_agent": "codex-main-control",
                            "registered_agents": ["codex-main-control", "codex-side-bypass"],
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime, project, state_path


def state_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_state_next_action(path: Path, expected: str) -> None:
    text = state_text(path)
    assert f"- {expected}" in text, text


def collect_projection(registry_path: Path, runtime: Path, project: Path) -> dict[str, object]:
    status = collect_status(
        registry_path=registry_path,
        runtime_root_override=str(runtime),
        scan_roots=[project],
        limit=5,
    )
    items = status["attention_queue"]["items"]
    item = next(item for item in items if item["goal_id"] == GOAL_ID)
    decision = build_quota_should_run(
        status,
        goal_id=GOAL_ID,
        agent_id="codex-side-bypass",
    )
    return {"status": status, "item": item, "decision": decision}


def run_cli_json(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from loopx.cli import main; raise SystemExit(main())",
            *args,
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> None:
    original_now_local = state_refresh.now_local
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-next-action-projection-") as raw_tmp:
            registry_path, runtime, project, state_path = write_fixture(Path(raw_tmp))

            state_refresh.now_local = lambda: "2026-06-22T00:01:00+00:00"
            implicit_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="state_refreshed",
                recommended_action=None,
                agent_id="codex-main-control",
                progress_scope="goal",
                dry_run=True,
                sync_global=False,
            )
            assert implicit_payload["recommended_action"] == ACTIVE_NEXT_ACTION, implicit_payload
            assert (
                implicit_payload["recommended_action_source"] == "active_state_next_action"
            ), implicit_payload
            assert implicit_payload.get("active_state_next_action_update") is None, implicit_payload

            default_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="state_refreshed",
                recommended_action=RUN_RECOMMENDATION,
                agent_id="codex-main-control",
                progress_scope="goal",
                dry_run=False,
                sync_global=False,
            )
            assert default_payload["recommended_action"] == RUN_RECOMMENDATION, default_payload
            assert default_payload["recommended_action_source"] == "explicit_arg", default_payload
            assert default_payload.get("active_state_next_action_update") is None, default_payload
            assert_state_next_action(state_path, ACTIVE_NEXT_ACTION)
            assert RUN_RECOMMENDATION not in state_text(state_path), state_text(state_path)

            first_projection = collect_projection(registry_path, runtime, project)
            first_item = first_projection["item"]
            first_decision = first_projection["decision"]
            assert first_item["active_state_next_action"] == ACTIVE_NEXT_ACTION, first_item
            assert first_item["latest_run_recommended_action"] == RUN_RECOMMENDATION, first_item
            assert first_item["next_action_projection_warning"]["requires_state_writeback"] is True, first_item
            assert first_decision["active_state_next_action"] == ACTIVE_NEXT_ACTION, first_decision
            assert first_decision["latest_run_recommended_action"] == RUN_RECOMMENDATION, first_decision
            first_warning = first_decision["next_action_projection_warning"]
            assert first_warning["severity"] == "info", first_decision
            assert first_warning["requires_state_writeback"] is False, first_decision
            assert first_warning["agent_lane_next_action"] == "[P1] Polish the hosted frontstage public case card.", first_decision

            state_refresh.now_local = lambda: "2026-06-22T00:02:00+00:00"
            explicit_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="state_refreshed",
                recommended_action=UPDATED_RUN_RECOMMENDATION,
                next_action=UPDATED_NEXT_ACTION,
                agent_id="codex-main-control",
                progress_scope="goal",
                dry_run=False,
                sync_global=False,
            )
            update = explicit_payload["active_state_next_action_update"]
            assert explicit_payload["recommended_action_source"] == "explicit_arg", explicit_payload
            assert update["updated"] is True, explicit_payload
            assert update["next_action"] == UPDATED_NEXT_ACTION, explicit_payload
            assert_state_next_action(state_path, UPDATED_NEXT_ACTION)
            assert ACTIVE_NEXT_ACTION not in state_text(state_path), state_text(state_path)

            second_projection = collect_projection(registry_path, runtime, project)
            second_status = second_projection["status"]
            second_item = second_projection["item"]
            second_decision = second_projection["decision"]
            status_markdown = render_status_markdown(second_status)
            quota_markdown = render_quota_should_run_markdown(second_decision)

            assert second_item["active_state_next_action"] == UPDATED_NEXT_ACTION, second_item
            assert second_item["latest_run_recommended_action"] == UPDATED_RUN_RECOMMENDATION, second_item
            assert second_decision["active_state_next_action"] == UPDATED_NEXT_ACTION, second_decision
            assert second_decision["latest_run_recommended_action"] == UPDATED_RUN_RECOMMENDATION, second_decision
            lane = second_decision["agent_lane_next_action"]
            assert lane["todo_id"] == "todo_side", second_decision
            assert lane["title"] == SIDE_AGENT_ACTION, second_decision
            assert SIDE_AGENT_ACTION in lane["text"], second_decision
            warning = second_decision["next_action_projection_warning"]
            assert warning["severity"] == "info", second_decision
            assert warning["requires_state_writeback"] is False, second_decision
            assert (
                warning["reason"]
                == "current agent lane action differs from the durable goal route while explicitly preserving the active-state Next Action"
            ), second_decision
            assert (
                warning["recommended_action"]
                == "run the agent-lane action without mutating active-state Next Action; only the primary/goal route should write a new durable Next Action"
            ), second_decision
            assert (
                warning["agent_lane_next_action"] == lane["text"]
            ), second_decision
            assert "active_state_next_action" in status_markdown, status_markdown
            assert "latest_run_recommended_action" in status_markdown, status_markdown
            assert "active_state_next_action" in quota_markdown, quota_markdown
            assert "latest_run_recommended_action" in quota_markdown, quota_markdown

            cli_ok = run_cli_json(
                [
                    "--format",
                    "json",
                    "--registry",
                    str(registry_path),
                    "--runtime-root",
                    str(runtime),
                    "refresh-state",
                    "--goal-id",
                    GOAL_ID,
                    "--project",
                    str(project),
                    "--classification",
                    "cli_goal_scope_dry_run",
                    "--recommended-action",
                    UPDATED_RUN_RECOMMENDATION,
                    "--agent-id",
                    "codex-main-control",
                    "--progress-scope",
                    "goal",
                    "--dry-run",
                    "--no-global-sync",
                ]
            )
            assert cli_ok.returncode == 0, cli_ok.stderr or cli_ok.stdout
            cli_ok_payload = json.loads(cli_ok.stdout)
            assert cli_ok_payload["ok"] is True, cli_ok_payload
            assert cli_ok_payload["progress_scope"] == "goal", cli_ok_payload
            assert cli_ok_payload["agent_id"] == "codex-main-control", cli_ok_payload

            cli_fail = run_cli_json(
                [
                    "--format",
                    "json",
                    "--registry",
                    str(registry_path),
                    "--runtime-root",
                    str(runtime),
                    "refresh-state",
                    "--goal-id",
                    GOAL_ID,
                    "--project",
                    str(project),
                    "--classification",
                    "cli_unscoped_dry_run",
                    "--recommended-action",
                    SIDE_AGENT_ACTION,
                    "--dry-run",
                    "--no-global-sync",
                ]
            )
            assert cli_fail.returncode == 1, cli_fail.stdout
            cli_fail_payload = json.loads(cli_fail.stdout)
            assert cli_fail_payload["ok"] is False, cli_fail_payload
            assert "requires --agent-id" in cli_fail_payload["error"], cli_fail_payload

        with tempfile.TemporaryDirectory(prefix="loopx-next-action-fallback-") as raw_tmp:
            registry_path, runtime, project, _state_path = write_fixture(
                Path(raw_tmp),
                include_next_action=False,
            )

            fallback_payload = state_refresh.refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=project,
                state_file=None,
                classification="state_refreshed",
                recommended_action=None,
                agent_id="codex-main-control",
                progress_scope="goal",
                dry_run=True,
                sync_global=False,
            )
            assert (
                fallback_payload["recommended_action"]
                == "[P0] Validate the primary public PoC control-plane lane."
            ), fallback_payload
            assert (
                fallback_payload["recommended_action_source"] == "agent_todo_fallback"
            ), fallback_payload
    finally:
        state_refresh.now_local = original_now_local

    print("next-action-projection-contract-smoke ok")


if __name__ == "__main__":
    main()
