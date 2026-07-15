#!/usr/bin/env python3
"""Keep quota spend bound to the repository of its accountable delivery."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.quota.slot_accounting import (  # noqa: E402
    build_quota_slot_preview_for_decision,
    build_quota_slot_spend_event,
)
from loopx.state_refresh import refresh_state_run  # noqa: E402


GOAL_ID = "quota-spend-workspace-causality"
AGENT_ID = "codex-peer"
DELIVERY_REPOSITORY = "git:example.invalid/loopx/delivery"


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def create_repository(root: Path, name: str) -> tuple[Path, Path]:
    canonical = root / name
    independent = root / f"{name}-peer"
    canonical.mkdir()
    (canonical / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    run_git(canonical, "init", "--initial-branch", "main")
    run_git(
        canonical,
        "remote",
        "add",
        "origin",
        f"https://example.invalid/loopx/{name}.git",
    )
    run_git(canonical, "add", "README.md")
    run_git(
        canonical,
        "-c",
        "user.name=LoopX Canary",
        "-c",
        "user.email=loopx-canary@example.invalid",
        "commit",
        "-m",
        "initial fixture",
    )
    run_git(canonical, "worktree", "add", "-b", f"{name}-peer", str(independent))
    return canonical, independent


@contextmanager
def working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def write_goal_fixture(project: Path, runtime: Path) -> Path:
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        "---\nstatus: active\nowner_mode: goal\n"
        'objective: "Exercise quota workspace causality."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n---\n\n"
        "# Quota Workspace Causality\n\n## Agent Todo\n\n"
        "- [ ] [P1] Deliver from the delivery repository.\n"
        "  <!-- loopx:todo todo_id=todo_delivery status=open "
        f"task_class=advancement_task action_kind=repair claimed_by={AGENT_ID} "
        f"task_repository={DELIVERY_REPOSITORY} -->\n",
        encoding="utf-8",
    )
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "quota-workspace-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "quota_workspace_fixture_v0",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID, "codex-other"],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path


def quota_decision(*, workspace_repair: bool) -> dict:
    return {
        "ok": True,
        "goal_id": GOAL_ID,
        "should_run": True,
        "state": "eligible",
        "effective_action": (
            "agent_workspace_repair" if workspace_repair else "normal_run"
        ),
        "workspace_repair_allowed": workspace_repair,
        "safe_bypass_allowed": False,
        "recovery_delivery_allowed": False,
        "self_repair_allowed": False,
        "capability_repair_allowed": False,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
        },
    }


def preview(runtime: Path, before: dict) -> dict:
    after = {
        **before,
        "quota": {**before["quota"], "spent_slots": 1},
    }
    return build_quota_slot_preview_for_decision(
        {"runtime_root": str(runtime)},
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _status: after,
        quota_status_builder=lambda goal, **_kwargs: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=AGENT_ID,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-quota-spend-workspace-") as tmp:
        root = Path(tmp)
        delivery, delivery_peer = create_repository(root, "delivery")
        _next, next_peer = create_repository(root, "next")
        runtime = root / "runtime"
        registry_path = write_goal_fixture(delivery, runtime)

        with working_directory(delivery_peer):
            refresh = refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=str(runtime),
                goal_id=GOAL_ID,
                project=None,
                state_file=None,
                classification="validated_delivery_fixture",
                recommended_action="complete the current todo",
                delivery_batch_scale="implementation",
                delivery_outcome="outcome_progress",
                agent_id=AGENT_ID,
                progress_scope="agent_lane",
                dry_run=False,
                sync_global=False,
            )
        workspace = refresh["delivery_workspace"]
        assert workspace == {
            "schema_version": "delivery_workspace_v0",
            "task_repository": DELIVERY_REPOSITORY,
            "repository_source": "current_git_origin",
            "workspace_kind": "independent_git_worktree",
            "peer_independent_worktree_required": True,
        }, workspace

        # Completing the todo may select work in another repository.  Spending
        # from the original delivery worktree remains valid and attributable.
        with working_directory(delivery_peer):
            causal = preview(runtime, quota_decision(workspace_repair=True))
        assert causal["ok"] is True, causal
        assert causal["delivery_completion_spend"] is True, causal
        assert causal["delivery_workspace_validated"] is True, causal
        event = build_quota_slot_spend_event(
            causal,
            self_repair_spend_actions=frozenset(),
            source="heartbeat",
        )
        assert event["quota_event"]["delivery_workspace"] == workspace, event
        assert event["quota_event"]["delivery_workspace_validated"] is True, event

        # A worktree matching the next todo but not the accountable delivery
        # repository must not be allowed to account for that delivery.
        with working_directory(next_peer):
            foreign = preview(runtime, quota_decision(workspace_repair=False))
        assert foreign["ok"] is False, foreign
        guard = foreign["workspace_guard"]
        assert guard["current_workspace"] == "foreign_git_worktree", guard
        assert guard["task_repository"] == DELIVERY_REPOSITORY, guard
        assert guard["repository_source"] == (
            "delivery_run.delivery_workspace.task_repository"
        ), guard

        # The canonical checkout is also not a substitute for the independent
        # worktree that produced the peer delivery.
        with working_directory(delivery):
            canonical = preview(runtime, quota_decision(workspace_repair=True))
        assert canonical["ok"] is False, canonical
        assert canonical["workspace_guard"]["current_workspace"] == (
            "canonical_checkout"
        ), canonical

        # A peer delivery recorded from a canonical checkout is itself unsafe;
        # moving to an independent worktree later must not bless that history.
        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
        recorded_canonical = json.loads(index_path.read_text(encoding="utf-8").strip())
        recorded_canonical["delivery_workspace"] = {
            **workspace,
            "workspace_kind": "canonical_checkout",
        }
        index_path.write_text(
            json.dumps(recorded_canonical) + "\n",
            encoding="utf-8",
        )
        with working_directory(delivery_peer):
            unsafe_history = preview(runtime, quota_decision(workspace_repair=False))
        assert unsafe_history["ok"] is False, unsafe_history
        assert unsafe_history["workspace_guard"]["current_workspace"] == (
            "delivery_not_recorded_from_independent_worktree"
        ), unsafe_history

        # Old accountable runs lack the causal snapshot.  Keep the previous
        # selected-todo workspace repair behavior instead of guessing.
        legacy = json.loads(index_path.read_text(encoding="utf-8").strip())
        legacy.pop("delivery_workspace", None)
        index_path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
        with working_directory(delivery_peer):
            legacy_preview = preview(runtime, quota_decision(workspace_repair=True))
        assert legacy_preview["ok"] is False, legacy_preview
        assert legacy_preview["delivery_workspace_validated"] is False, legacy_preview
        assert "moving to an independent worktree" in legacy_preview["reason"], (
            legacy_preview
        )

    print("quota-spend-workspace-causality-smoke ok")


if __name__ == "__main__":
    main()
