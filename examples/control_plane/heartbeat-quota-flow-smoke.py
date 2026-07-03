#!/usr/bin/env python3
"""Smoke-test the automatic heartbeat quota lifecycle."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "heartbeat-flow-main-control"
LONG_NEXT_ACTION_TAIL = "without truncating the final private-safe boundary sentence."
EXPECTED_AGENT_TODO_ACTION = "[P1] Run one bounded heartbeat marker and validate the compact result."
EXPECTED_NEXT_ACTION = (
    "Run one bounded heartbeat marker, preserve the wrapped next-action "
    "continuation across more than eight public-safe lines, keep the current "
    "owner gate context intact, keep the validation context intact, keep the "
    "quota accounting context intact, keep the project-agent handoff context "
    "intact, keep the public/private boundary context intact, keep the "
    "status-queue routing context intact, keep the review packet context "
    "intact, and finish without truncating the final private-safe boundary sentence."
)


def run_cli(root: Path, *args: str, registry_path: Path, runtime: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
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


def run_projected_loopx_command(
    root: Path,
    command: str,
    *extra_args: str,
    registry_path: Path,
    runtime: Path,
) -> dict:
    tokens = shlex.split(command)
    assert tokens and tokens[0] == "loopx", command
    return run_cli(
        root,
        *tokens[1:],
        *extra_args,
        registry_path=registry_path,
        runtime=runtime,
    )


def run_cli_result(root: Path, *args: str, registry_path: Path, runtime: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, json.loads(result.stdout)


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active-read-only\n"
        "owner_mode: goal\n"
        'objective: "Exercise heartbeat quota accounting."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Heartbeat Flow Main Control\n\n"
        "## Objective\n\n"
        "Exercise heartbeat quota accounting.\n\n"
        "## Next Action\n\n"
        "- Run one bounded heartbeat marker, preserve the wrapped next-action\n"
        "  continuation across more than eight public-safe lines, keep the current\n"
        "  owner gate context intact, keep the validation context intact, keep the\n"
        "  quota accounting context intact, keep the project-agent handoff context\n"
        "  intact, keep the public/private boundary context intact, keep the\n"
        "  status-queue routing context intact, keep the review packet context\n"
        "  intact, and finish " + LONG_NEXT_ACTION_TAIL + "\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Run one bounded heartbeat marker and validate the compact result.\n"
        "  <!-- loopx:todo todo_id=todo_fixture_heartbeat_marker status=open "
        "task_class=advancement_task action_kind=validate -->\n\n"
        "## Progress Ledger\n\n"
        "- Initialized fixture.\n",
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
                        "domain": "heartbeat-flow-fixture",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "heartbeat_flow_fixture_v0",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 2,
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
    return project, runtime, registry_path


def count_spend_events(runtime: Path) -> int:
    return count_events(runtime, "quota_slot_spent")


def count_events(runtime: Path, classification: str, *, goal_id: str = GOAL_ID) -> int:
    index_path = runtime / "goals" / goal_id / "runs" / "index.jsonl"
    if not index_path.exists():
        return 0
    count = 0
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("classification") == classification:
            count += 1
    return count


def write_monitor_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "monitor-project"
    runtime = root / "monitor-runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: benchmark_execution_route_selection_v0\n"
        "owner_mode: goal\n"
        'objective: "Exercise monitor poll accounting."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Monitor Poll Main Control\n\n"
        "## Next Action\n\n"
        "- Wait for the owner gate before any real benchmark execution.\n\n"
        "## User Todo / Owner Review Reading Queue\n\n"
        "- [x] [P1] Approve the private one-instance execution boundary before any real run.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P2] Meta canary/readiness observation lane: keep status observable and repair only material transitions.\n"
        "  <!-- loopx:todo todo_id=todo_77fad979d712 task_class=continuous_monitor cadence=15m next_due_at=2099-01-01T00:00:00Z -->\n",
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
                        "domain": "heartbeat-flow-fixture",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                        "control_plane": {
                            "self_repair": {
                                "enabled": True,
                                "allow_health_blocker_repair": True,
                                "allow_waiting_projection_repair": True,
                            }
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
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    progress_record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "benchmark_execution_route_selection_v0",
        "recommended_action": "Wait for the owner gate before any real benchmark execution.",
        "health_check": "state_file 1/1; registry_goal 1/1",
        "delivery_batch_scale": "multi_surface",
        "delivery_outcome": "outcome_progress",
        "json_path": str(runs_dir / "2026-01-01T00-00-00+00-00.json"),
        "markdown_path": str(runs_dir / "2026-01-01T00-00-00+00-00.md"),
    }
    Path(progress_record["json_path"]).write_text(json.dumps(progress_record) + "\n", encoding="utf-8")
    Path(progress_record["markdown_path"]).write_text("# Fixture Progress\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(progress_record) + "\n")
    return project, runtime, registry_path


def write_external_evidence_fixture(
    root: Path,
    *,
    latest_classification: str = "waiting_for_external_worker_result_v0",
    registry_waiting_on: bool = True,
) -> tuple[Path, Path, Path]:
    project = root / "external-evidence-project"
    runtime = root / "external-evidence-runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: waiting-for-agentissue-result\n"
        "owner_mode: goal\n"
        'objective: "Exercise external evidence observation contracts."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# External Evidence Observation Fixture\n\n"
        "## Next Action\n\n"
        "- Observe for a compact result from the separate benchmark execution thread.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Target execution-thread result monitor: observe whether the relay packet has produced a compact execution result or blocker from a separate benchmark execution thread. If no new compact result/blocker exists, quiet no-op without quota spend; do not run Docker/Codex/model APIs from the meta heartbeat.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_goal = {
        "id": GOAL_ID,
        "domain": "heartbeat-flow-fixture",
        "status": "waiting-for-agentissue-result",
        "repo": str(project),
        "state_file": state_file,
        "adapter": {
            "kind": "harness_self_improvement",
            "status": "connected-read-only",
        },
        "authority_sources": [],
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "allowed_slots": 5,
        },
    }
    if registry_waiting_on:
        registry_goal["waiting_on"] = "external_evidence"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [registry_goal],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    progress_record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": latest_classification,
        "recommended_action": "Observe for a compact result from the separate benchmark execution thread.",
        "health_check": "state_file 1/1; registry_goal 1/1",
        "delivery_batch_scale": "single_surface",
        "json_path": str(runs_dir / "2026-01-01T00-00-00+00-00.json"),
        "markdown_path": str(runs_dir / "2026-01-01T00-00-00+00-00.md"),
    }
    Path(progress_record["json_path"]).write_text(json.dumps(progress_record) + "\n", encoding="utf-8")
    Path(progress_record["markdown_path"]).write_text("# Fixture External Evidence Wait\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(progress_record) + "\n")
    return project, runtime, registry_path


def write_external_monitor_advancement_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "external-monitor-advancement-project"
    runtime = root / "external-monitor-advancement-runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: terminal_bench_headless_treatment_running_v0\n"
        "owner_mode: goal\n"
        'objective: "Exercise running benchmark observation contracts."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# External Monitor Advancement Fixture\n\n"
        "## Next Action\n\n"
        "- Observe active Terminal-Bench headless-terminal treatment run_group=fixture-headless "
        "via compact process/result markers; ingest compact result and update the ledger when available.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] Observe active Terminal-Bench headless-terminal LoopX treatment "
        "(run_group=fixture-headless; pid=12345): poll process plus compact result markers only, "
        "avoid raw task/log/trajectory reads, then ingest result, update ledger, and compare against baseline "
        "without claiming uplift unless official score improves.\n"
        "  <!-- loopx:todo todo_id=todo_fixture_headless status=open "
        "task_class=advancement_task action_kind=monitor_running_benchmark_case -->\n"
        "- [ ] [P1] Re-rank follow-on benchmark lanes after the active case produces a compact result.\n"
        "  <!-- loopx:todo todo_id=todo_fixture_followup status=open "
        "task_class=advancement_task action_kind=planning_refresh -->\n",
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
                        "domain": "heartbeat-flow-fixture",
                        "status": "terminal_bench_headless_treatment_running_v0",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
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
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    progress_record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "terminal_bench_headless_treatment_running_v0",
        "recommended_action": (
            "Observe active Terminal-Bench headless-terminal treatment via compact process/result markers."
        ),
        "health_check": "state_file 1/1; registry_goal 1/1",
        "delivery_batch_scale": "single_surface",
        "json_path": str(runs_dir / "2026-01-01T00-00-00+00-00.json"),
        "markdown_path": str(runs_dir / "2026-01-01T00-00-00+00-00.md"),
    }
    Path(progress_record["json_path"]).write_text(json.dumps(progress_record) + "\n", encoding="utf-8")
    Path(progress_record["markdown_path"]).write_text("# Fixture Running Benchmark Observation\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(progress_record) + "\n")
    return project, runtime, registry_path


def write_operator_gate_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "operator-gate-project"
    runtime = root / "operator-gate-runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: ready_for_controller_opt_in\n"
        "owner_mode: goal\n"
        'objective: "Exercise operator gate interaction contract."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Operator Gate Fixture\n\n"
        "## Next Action\n\n"
        "- Ask the owner whether this planned adapter may run.\n\n"
        "## User Todo / Owner Review Reading Queue\n\n"
        "- [ ] [P1] Approve or defer the planned adapter opt-in.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P2] If the gate is already surfaced, prepare a read-only checklist that does not execute the gated adapter.\n",
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
                        "domain": "heartbeat-flow-fixture",
                        "status": "ready_for_controller_opt_in",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "planned_adapter_v0",
                            "status": "planned",
                        },
                        "authority_sources": [],
                        "waiting_on": "controller",
                        "operator_gate": "controller_opt_in",
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
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    progress_record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "ready_for_controller_opt_in",
        "recommended_action": "Ask the owner whether this planned adapter may run.",
        "health_check": "state_file 1/1; registry_goal 1/1",
        "json_path": str(runs_dir / "2026-01-01T00-00-00+00-00.json"),
        "markdown_path": str(runs_dir / "2026-01-01T00-00-00+00-00.md"),
    }
    Path(progress_record["json_path"]).write_text(json.dumps(progress_record) + "\n", encoding="utf-8")
    Path(progress_record["markdown_path"]).write_text("# Fixture Operator Gate\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(progress_record) + "\n")
    return project, runtime, registry_path


def fake_codex_executor_decision(guard: dict) -> dict:
    """Model the minimum Codex-side behavior expected from the quota payload."""

    obligation = guard.get("execution_obligation") if isinstance(guard.get("execution_obligation"), dict) else {}
    observation = (
        guard.get("external_evidence_observation")
        if isinstance(guard.get("external_evidence_observation"), dict)
        else {}
    )
    if obligation.get("kind") == "external_evidence_observation_required":
        assert obligation.get("must_attempt_work") is True, guard
        assert observation.get("required") is True, guard
        assert observation.get("requires_observable_handle") is True, guard
        return {
            "quiet_noop_allowed": False,
            "delivery_allowed": False,
            "benchmark_execution_allowed": False,
            "allowed_next_actions": [
                "read_only_observation",
                "compact_blocker_writeback",
            ],
        }
    return {"quiet_noop_allowed": obligation.get("must_attempt_work") is not True}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-heartbeat-quota-flow-") as tmp:
        root = Path(tmp)
        project, runtime, registry_path = write_fixture(root)
        registry_before = registry_path.read_text(encoding="utf-8")

        guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert guard["should_run"] is True, guard
        assert guard["quota"]["spent_slots"] == 0, guard
        assert guard["quota"]["allowed_slots"] == 2, guard
        interaction = guard["interaction_contract"]
        assert interaction["schema_version"] == "loopx_interaction_contract_v0", interaction
        assert interaction["mode"] == "bounded_delivery", interaction
        assert interaction["user_channel"]["action_required"] is False, interaction
        assert interaction["agent_channel"]["must_attempt"] is True, interaction
        assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
        assert interaction["cli_channel"]["spend_allowed_now"] is False, interaction
        assert interaction["cli_channel"]["spend_after_validation"] is True, interaction

        marker = project / "heartbeat-work-marker.txt"
        marker.write_text("bounded heartbeat work completed\n", encoding="utf-8")
        check = run_cli(
            root,
            "check",
            "--scan-path",
            str(marker),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert check["ok"] is True, check

        refresh = run_cli(
            root,
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--no-global-sync",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert refresh["ok"] is True, refresh
        assert refresh["appended"] is True, refresh
        assert refresh["recommended_action"] == EXPECTED_NEXT_ACTION, refresh
        assert refresh["recommended_action_source"] == "active_state_next_action", refresh
        assert LONG_NEXT_ACTION_TAIL in " ".join(refresh["state"]["next_action"]), refresh
        assert count_spend_events(runtime) == 0

        spend = run_cli(
            root,
            "quota",
            "spend-slot",
            "--goal-id",
            GOAL_ID,
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert spend["ok"] is True, spend
        assert spend["appended"] is True, spend
        assert spend["registry_mutated"] is False, spend
        assert spend["quota_event"]["source"] == "heartbeat", spend
        assert spend["quota_event"]["before"]["spent_slots"] == 0, spend
        assert spend["quota_event"]["after"]["spent_slots"] == 1, spend
        assert count_spend_events(runtime) == 1

        follow_up = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert follow_up["should_run"] is True, follow_up
        assert follow_up["state"] == "eligible", follow_up
        assert follow_up["status"] == "state_refreshed", follow_up
        assert follow_up["quota"]["spent_slots"] == 1, follow_up
        assert follow_up["quota"]["allowed_slots"] == 2, follow_up
        assert follow_up["recommended_action"] == EXPECTED_AGENT_TODO_ACTION, follow_up
        assert follow_up["active_state_next_action"].startswith(
            "Run one bounded heartbeat marker, preserve the wrapped next-action"
        ), follow_up
        assert follow_up["latest_run_recommended_action"].startswith(
            "Run one bounded heartbeat marker, preserve the wrapped next-action"
        ), follow_up
        interaction = follow_up["interaction_contract"]
        assert interaction["agent_channel"]["primary_action"] == EXPECTED_AGENT_TODO_ACTION, interaction
        assert "state_action_projection_warning" not in follow_up, follow_up
        assert "agent_action=" + EXPECTED_AGENT_TODO_ACTION in follow_up["protocol_action_packet"]["summary"], follow_up
        assert registry_path.read_text(encoding="utf-8") == registry_before

    with tempfile.TemporaryDirectory(prefix="loopx-heartbeat-operator-gate-") as tmp:
        root = Path(tmp)
        project, runtime, registry_path = write_operator_gate_fixture(root)
        gate_guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert gate_guard["should_run"] is False, gate_guard
        assert gate_guard["state"] == "operator_gate", gate_guard
        assert gate_guard["requires_user_action"] is True, gate_guard
        assert gate_guard["safe_bypass_allowed"] is True, gate_guard
        interaction = gate_guard["interaction_contract"]
        assert interaction["mode"] == "user_gate", interaction
        assert interaction["user_channel"]["action_required"] is True, interaction
        assert interaction["agent_channel"]["must_attempt"] is False, interaction
        assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
        assert interaction["cli_channel"]["spend_after_validation"] is False, interaction
        assert interaction["fallback_policy"]["do_not_cancel_on_block"] is True, interaction

    with tempfile.TemporaryDirectory(prefix="loopx-heartbeat-monitor-poll-") as tmp:
        root = Path(tmp)
        project, runtime, registry_path = write_monitor_fixture(root)
        first_guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert first_guard["effective_action"] == "autonomous_replan_required", first_guard
        assert first_guard["should_run"] is True, first_guard
        assert first_guard["heartbeat_recommendation"]["recommended_mode"] == "autonomous_replan_required", first_guard
        obligation = first_guard["autonomous_replan_obligation"]
        assert obligation["triggers"][0]["kind"] == "frontier_exhausted_monitor_lane", obligation
        assert obligation["stall_threshold"] == 1, obligation
        assert obligation["guidance_actions"] == [
            "create_successor",
            "supersede_monitor",
            "set_watch_expiry",
            "record_no_followup",
        ], obligation
        assert "another monitor-only quiet poll" in obligation["recommended_action"], obligation
        assert first_guard["execution_obligation"]["kind"] == "autonomous_replan_required", first_guard
        assert first_guard["execution_obligation"]["must_attempt_work"] is True, first_guard
        assert first_guard["automation_liveness"]["automation_action"] == "execute_bounded_work", first_guard
        assert first_guard["automation_liveness"]["pause_allowed"] is False, first_guard
        assert first_guard["scheduler_hint"]["action"] == "run_now", first_guard
        assert first_guard["scheduler_hint"]["codex_app"]["recommended_interval_minutes"] == 3, first_guard
        assert first_guard["scheduler_hint"]["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=3", first_guard
        reset = first_guard["scheduler_hint"]["reset_policy"]
        assert reset["codex_app_initial_rrule"] == "FREQ=MINUTELY;INTERVAL=3", reset
        assert "reset_condition_summary" not in reset, reset
        assert "automation=execute_bounded_work" in first_guard["protocol_action_packet"]["summary"], first_guard
        assert count_events(runtime, "quota_monitor_poll") == 0, first_guard
        interaction = first_guard["interaction_contract"]
        assert interaction["mode"] == "autonomous_replan", interaction
        assert interaction["agent_channel"]["must_attempt"] is True, interaction
        assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
        assert interaction["cli_channel"]["spend_after_validation"] is True, interaction

        refresh = run_cli(
            root,
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--classification",
            "monitor_poll_autonomous_replan_recorded_v0",
            "--autonomous-replan-recorded",
            "--repair-delta-kind",
            "watch_lane_continuation",
            "--delivery-batch-scale",
            "single_surface",
            "--delivery-outcome",
            "outcome_progress",
            "--no-global-sync",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert refresh["ok"] is True, refresh
        assert refresh["delivery_outcome"] == "outcome_progress", refresh

        post_refresh_guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert post_refresh_guard.get("autonomous_replan_obligation") is None, post_refresh_guard

        spend = run_cli(
            root,
            "quota",
            "spend-slot",
            "--goal-id",
            GOAL_ID,
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert spend["ok"] is True, spend
        assert spend["delivery_completion_spend"] is True, spend
        assert spend["quota_event"]["delivery_run_classification"] == (
            "monitor_poll_autonomous_replan_recorded_v0"
        ), spend
        assert spend["quota_event"]["delivery_run_generated_at"] == refresh["generated_at"], spend
        assert count_spend_events(runtime) == 1, spend

        duplicate_rc, duplicate = run_cli_result(
            root,
            "quota",
            "spend-slot",
            "--goal-id",
            GOAL_ID,
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert duplicate_rc == 1, duplicate
        assert duplicate["ok"] is False, duplicate
        assert count_spend_events(runtime) == 1, duplicate

        ack = run_cli(
            root,
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--classification",
            "delivery_completion_spend_accounted_v0",
            "--no-global-sync",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert ack["ok"] is True, ack
        assert ack.get("delivery_outcome") is None, ack

        post_ack_guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert post_ack_guard["effective_action"] == "monitor_quiet_skip", post_ack_guard
        assert post_ack_guard["execution_obligation"]["must_attempt_work"] is False, post_ack_guard
        assert post_ack_guard.get("autonomous_replan_obligation") is None, post_ack_guard
        assert (
            post_ack_guard["heartbeat_recommendation"]["recommended_mode"]
            == "monitor_quiet_until_material_transition"
        ), post_ack_guard
        post_ack_interaction = post_ack_guard["interaction_contract"]
        assert post_ack_interaction["mode"] == "monitor_quiet_skip", post_ack_interaction
        post_ack_actions = post_ack_interaction["cli_channel"]["next_cli_actions"]
        post_ack_monitor_poll_action = post_ack_actions[0]
        assert shlex.split(post_ack_monitor_poll_action) == [
            "loopx",
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--execute",
        ], post_ack_interaction

        post_ack_poll_count = count_events(runtime, "quota_monitor_poll")
        for index in range(2):
            if index == 0:
                poll = run_projected_loopx_command(
                    root,
                    post_ack_monitor_poll_action,
                    "--scan-path",
                    str(project),
                    registry_path=registry_path,
                    runtime=runtime,
                )
            else:
                poll = run_cli(
                    root,
                    "quota",
                    "monitor-poll",
                    "--goal-id",
                    GOAL_ID,
                    "--source",
                    "heartbeat",
                    "--execute",
                    "--scan-path",
                    str(project),
                    registry_path=registry_path,
                    runtime=runtime,
                )
            assert poll["ok"] is True, poll
            assert poll["classification"] == "quota_monitor_poll", poll
            assert count_spend_events(runtime) == 1, poll
            assert count_events(runtime, "quota_monitor_poll") == post_ack_poll_count + index + 1, poll

        post_poll_guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert post_poll_guard["effective_action"] == "monitor_quiet_skip", post_poll_guard
        assert post_poll_guard["execution_obligation"]["must_attempt_work"] is False, post_poll_guard
        assert post_poll_guard.get("autonomous_replan_obligation") is None, post_poll_guard
        assert (
            post_poll_guard["heartbeat_recommendation"]["recommended_mode"]
            == "monitor_quiet_until_material_transition"
        ), post_poll_guard

    with tempfile.TemporaryDirectory(prefix="loopx-external-evidence-observation-") as tmp:
        root = Path(tmp)
        project, runtime, registry_path = write_external_evidence_fixture(root)
        guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert guard["decision"] == "observe", guard
        assert guard["should_run"] is True, guard
        assert guard["state"] == "waiting", guard
        assert guard["waiting_on"] == "external_evidence", guard
        assert guard["effective_action"] == "external_evidence_observe", guard
        assert (
            guard["heartbeat_recommendation"]["recommended_mode"]
            == "external_evidence_observe_or_blocker"
        ), guard
        observation = guard["external_evidence_observation"]
        assert observation["schema_version"] == "external_evidence_observation_obligation_v0", observation
        assert observation["required"] is True, observation
        assert observation["scope"] == "read_only_observation", observation
        assert observation["requires_observable_handle"] is True, observation
        assert "thread_id" in observation["observable_handle_examples"], observation
        assert "compact_writeback_path" in observation["observable_handle_examples"], observation
        assert "missing worker/controller handle" in observation["if_handle_missing"], observation
        assert "separate benchmark execution thread" in observation["observation_target"], observation
        assert guard["execution_obligation"]["must_attempt_work"] is True, guard
        assert (
            guard["execution_obligation"]["kind"]
            == "external_evidence_observation_required"
        ), guard
        interaction = guard["interaction_contract"]
        assert interaction["mode"] == "external_evidence_observation", interaction
        assert interaction["user_channel"]["action_required"] is False, interaction
        assert interaction["agent_channel"]["must_attempt"] is True, interaction
        assert interaction["agent_channel"]["delivery_allowed"] is False, interaction
        assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
        assert interaction["cli_channel"]["spend_after_validation"] is True, interaction
        executor = fake_codex_executor_decision(guard)
        assert executor["quiet_noop_allowed"] is False, executor
        assert executor["delivery_allowed"] is False, executor
        assert executor["benchmark_execution_allowed"] is False, executor
        assert executor["allowed_next_actions"] == [
            "read_only_observation",
            "compact_blocker_writeback",
        ], executor
        assert count_spend_events(runtime) == 0, guard
        poll = run_cli(
            root,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert poll["ok"] is True, poll
        assert poll["appended"] is True, poll
        assert poll["classification"] == "quota_monitor_poll", poll
        assert poll["monitor_event"]["monitor_mode"] == (
            "external_monitor_observed_without_material_transition"
        ), poll
        assert poll["monitor_event"]["before"]["effective_action"] == "external_evidence_observe", poll
        assert poll["after"]["effective_action"] == "external_evidence_observe", poll
        assert count_spend_events(runtime) == 0, poll
        assert count_events(runtime, "quota_monitor_poll") == 1, poll

    with tempfile.TemporaryDirectory(prefix="loopx-external-monitor-advancement-") as tmp:
        root = Path(tmp)
        project, runtime, registry_path = write_external_monitor_advancement_fixture(root)
        guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert guard["decision"] == "run", guard
        assert guard["should_run"] is True, guard
        assert guard["effective_action"] == "normal_run", guard
        lane = guard["work_lane_contract"]
        assert lane["lane"] == "advancement_task", lane
        assert lane["monitor_policy"] == "material_transition_only", lane
        assert lane["reason_codes"] == ["open_agent_todo", "external_monitor_context"], lane
        assert guard["execution_obligation"]["must_attempt_work"] is True, guard
        poll = run_cli(
            root,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert poll["ok"] is True, poll
        assert poll["appended"] is True, poll
        assert poll["classification"] == "quota_monitor_poll", poll
        assert poll["monitor_event"]["monitor_mode"] == (
            "external_monitor_observed_without_material_transition"
        ), poll
        assert poll["monitor_event"]["before"]["effective_action"] == "normal_run", poll
        assert poll["before"]["work_lane_contract"]["reason_codes"] == [
            "open_agent_todo",
            "external_monitor_context",
        ], poll
        assert poll["after"]["effective_action"] == "normal_run", poll
        assert count_spend_events(runtime) == 0, poll
        assert count_events(runtime, "quota_monitor_poll") == 1, poll

    with tempfile.TemporaryDirectory(prefix="loopx-external-evidence-projection-") as tmp:
        root = Path(tmp)
        project, runtime, registry_path = write_external_evidence_fixture(
            root,
            latest_classification="external_evidence_observation_contract_validated_v0",
            registry_waiting_on=False,
        )
        guard = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert guard["decision"] == "observe", guard
        assert guard["should_run"] is True, guard
        assert guard["state"] == "waiting", guard
        assert guard["waiting_on"] == "external_evidence", guard
        assert guard["effective_action"] == "external_evidence_observe", guard
        assert (
            guard["execution_obligation"]["kind"]
            == "external_evidence_observation_required"
        ), guard
        assert guard["external_evidence_observation"]["required"] is True, guard
        assert guard["interaction_contract"]["mode"] == "external_evidence_observation", guard

    print("heartbeat-quota-flow-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
