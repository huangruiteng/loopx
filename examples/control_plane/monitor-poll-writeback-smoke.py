#!/usr/bin/env python3
"""Smoke-test monitor-poll todo metadata writeback."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import loopx.cli_commands.quota as quota_command  # noqa: E402
from loopx.control_plane.quota.monitor_poll import (  # noqa: E402
    build_quota_monitor_poll_event,
)
from loopx.control_plane.scheduler.monitor_poll_writeback import (  # noqa: E402
    resolve_monitor_todo_item,
    write_monitor_poll_todo_state,
)
from loopx.control_plane.testing.canary_harness import (  # noqa: E402
    read_run_index,
    run_json_cli,
    run_json_cli_result,
    runtime_root_from_registry,
    write_fixture_registry,
)
from loopx.status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, parse_active_state_todos  # noqa: E402


GOAL_ID = "monitor-poll-writeback-fixture"
AGENT_ID = "codex-product-capability"
TODO_ID = "todo_monitorpoll000"
TARGET_KEY = "update-note-draft-pr"
OTHER_TARGET_KEY = "other-monitor-target"


def write_promotion_readiness(runtime: Path) -> None:
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    json_path = runs_dir / "readiness.json"
    markdown_path = runs_dir / "readiness.md"
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "canary_promotion_readiness_smoke_group",
        "delivery_batch_scale": "multi_surface",
        "delivery_outcome": "primary_goal_outcome",
        "recommended_action": "fixture promotion readiness is fresh",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    json_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text("# Canary promotion readiness\n", encoding="utf-8")
    (runs_dir / "index.jsonl").write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(
    root: Path,
    *,
    selected_target_key: str | None = TARGET_KEY,
    include_other_monitor: bool = False,
    include_user_gate: bool = False,
    include_advancement: bool = False,
    primary_monitor_priority: str = "P0",
    monitor_required_capabilities: tuple[str, ...] = (),
) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    write_promotion_readiness(runtime)
    monitor_metadata = (
        f"target_key={selected_target_key} "
        if selected_target_key
        else ""
    )
    monitor_capability_metadata = (
        f"required_capabilities={','.join(monitor_required_capabilities)} "
        if monitor_required_capabilities
        else ""
    )
    other_monitor = (
        "- [ ] [P1] Poll another monitor target.\n"
        "  <!-- loopx:todo "
        "todo_id=todo_monitorpoll111 "
        "status=open "
        "task_class=continuous_monitor "
        "action_kind=poll "
        f"claimed_by={AGENT_ID} "
        f"target_key={OTHER_TARGET_KEY} "
        "cadence=15m "
        "next_due_at=2026-01-01T00:00:00+00:00 "
        "result_hash=old "
        "consecutive_no_change=1 "
        "material_change=false "
        "-->\n"
        if include_other_monitor
        else ""
    )
    gated_advancement = (
        "- [ ] [P1] Prepare the gated publication packet.\n"
        "  <!-- loopx:todo "
        "todo_id=todo_monitorpollblocked "
        "status=open "
        "task_class=advancement_task "
        f"claimed_by={AGENT_ID} "
        "-->\n"
        if include_user_gate
        else ""
    )
    advancement = (
        "- [ ] [P0] Advance the independent delivery task.\n"
        "  <!-- loopx:todo "
        "todo_id=todo_monitorpolladvance "
        "status=open "
        "task_class=advancement_task "
        "required_capabilities=network "
        f"claimed_by={AGENT_ID} "
        "-->\n"
        if include_advancement
        else ""
    )
    user_gate = (
        "\n## User Todo\n\n"
        "- [ ] [P0-user] Review the unrelated publication gate.\n"
        "  <!-- loopx:todo "
        "todo_id=todo_monitorpollgate "
        "status=open "
        "task_class=user_gate "
        "action_kind=review_publication_gate "
        f"blocks_agent={AGENT_ID} "
        "unblocks_todo_id=todo_monitorpollblocked "
        "-->\n"
        if include_user_gate
        else ""
    )
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Exercise due monitor poll writeback.\n\n"
        "## Agent Todo\n\n"
        f"- [ ] [{primary_monitor_priority}] Poll the update-note draft PR for material changes.\n"
        "  <!-- loopx:todo "
        f"todo_id={TODO_ID} "
        "status=open "
        "task_class=continuous_monitor "
        "action_kind=poll "
        f"{monitor_capability_metadata}"
        f"claimed_by={AGENT_ID} "
        f"{monitor_metadata}"
        "cadence=15m "
        "next_due_at=2026-01-01T00:00:00+00:00 "
        "result_hash=old "
        "consecutive_no_change=1 "
        "material_change=false "
        "-->\n"
        f"{other_monitor}"
        f"{gated_advancement}"
        f"{advancement}"
        f"{user_gate}",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="monitor-poll-writeback",
        adapter_kind="generic_project_goal_v0",
        registered_agents=[AGENT_ID],
        quota_allowed_slots=None,
    )
    return registry_path, state_file


def run_cli(registry_path: Path, *args: str) -> dict:
    scan_args = ["--scan-path", str(Path(__file__).resolve())] if args[:1] == ("quota",) else []
    return run_json_cli(
        *args,
        *scan_args,
        registry_path=registry_path,
        runtime_root=runtime_root_from_registry(registry_path),
        cwd=REPO_ROOT,
        include_returncode=False,
    )


def run_cli_expect_error(registry_path: Path, *args: str) -> dict:
    scan_args = ["--scan-path", str(Path(__file__).resolve())] if args[:1] == ("quota",) else []
    returncode, payload = run_json_cli_result(
        *args,
        *scan_args,
        registry_path=registry_path,
        runtime_root=runtime_root_from_registry(registry_path),
        cwd=REPO_ROOT,
    )
    assert returncode != 0, payload
    return payload


def run_cli_markdown_expect_error(registry_path: Path, *args: str) -> str:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime_root_from_registry(registry_path)),
        *args,
        "--scan-path",
        str(Path(__file__).resolve()),
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0, result.stdout
    assert result.stdout.strip(), result.stderr
    return result.stdout


def agent_todos(state_file: Path) -> list[dict]:
    fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
    return fields["agent_todos"]["items"]


def find_todo(state_file: Path, todo_id: str) -> dict:
    for item in agent_todos(state_file):
        if item.get("todo_id") == todo_id:
            return item
    raise AssertionError(f"missing todo {todo_id}")


def run_index_records(registry_path: Path) -> list[dict]:
    runtime = runtime_root_from_registry(registry_path)
    assert runtime is not None, registry_path
    return read_run_index(runtime, GOAL_ID)


def monitor_poll_records(registry_path: Path) -> list[dict]:
    return [
        record
        for record in run_index_records(registry_path)
        if record.get("classification") == "quota_monitor_poll"
    ]


def assert_due_monitor_selected(registry_path: Path, *, due_count: int = 1) -> None:
    quota = run_cli(
        registry_path,
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert quota["should_run"] is True, quota
    contract = quota.get("work_lane_contract")
    assert isinstance(contract, dict), quota
    assert contract.get("obligation") == "attempt_due_monitor", quota
    assert contract.get("selected_todo_id") == TODO_ID, quota
    assert contract.get("monitor_due_count") == due_count, quota


def assert_unchanged_writeback() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-unchanged-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))
        assert_due_monitor_selected(registry_path)

        payload = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--todo-id",
            TODO_ID,
            "--result-hash",
            "old",
            "--execute",
        )
        assert payload["ok"] is True, payload
        assert payload["appended"] is True, payload
        writeback = payload["todo_writeback"]
        assert writeback["todo_id"] == TODO_ID, payload
        assert writeback["consecutive_no_change"] == 2, payload
        item = find_todo(state_file, TODO_ID)
        assert item["result_hash"] == "old", item
        assert item["consecutive_no_change"] == "2", item
        assert item["last_checked_at"], item
        assert item["next_due_at"] != "2026-01-01T00:00:00+00:00", item
        assert item["material_change"] == "false", item
        assert payload["classification"] == "quota_monitor_poll", payload
        assert payload["delivery_outcome"] == "surface_only", payload
        assert "no quota spend" in payload["health_check"], payload
        summary = payload["decision_summary"]
        assert summary["before"] == payload["monitor_event"]["before"], payload
        assert summary["before"]["effective_action"] == payload["before"]["effective_action"], payload
        assert "work_lane_contract" not in summary["before"], payload
        assert payload["before"]["work_lane_contract"]["obligation"] == "attempt_due_monitor", payload
        assert summary["after"]["effective_action"] == payload["after"]["effective_action"], payload
        assert "interaction_contract" not in summary["after"], payload
        assert payload["after"]["interaction_contract"]["mode"] == "autonomous_replan", payload
        records = monitor_poll_records(registry_path)
        assert [record["classification"] for record in records] == ["quota_monitor_poll"], records

        followup = run_cli(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
        )
        assert followup["decision"] == "autonomous_replan_required", followup
        assert followup["effective_action"] == "autonomous_replan_required", followup
        assert followup["should_run"] is True, followup
        assert followup["heartbeat_recommendation"]["recommended_mode"] == (
            "autonomous_replan_required"
        ), followup
        assert followup["scheduler_hint"]["cadence_class"] == "active_work", followup
        lane = followup["work_lane_contract"]
        assert lane["lane"] == "continuous_monitor", lane
        assert lane["obligation"] == "quiet_until_material_monitor_transition", lane
        frontier = followup["goal_frontier_projection"]
        assert frontier["monitor_only_lanes"]["present"] is True, frontier
        assert frontier["monitor_only_lanes"]["quiet_until_material_transition"] is True, frontier
        assert frontier["replan_required"] is True, frontier
        assert followup["autonomous_replan_obligation"]["required"] is True, followup
        assert followup["interaction_contract"]["mode"] == "autonomous_replan", followup
        assert followup["interaction_contract"]["agent_channel"]["must_attempt"] is True, followup
        assert followup["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is False, followup
        assert followup["execution_obligation"]["kind"] == "autonomous_replan_required", followup
        assert followup["execution_obligation"]["must_attempt_work"] is True, followup


def assert_material_transition_followup() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-material-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))
        assert_due_monitor_selected(registry_path)

        payload = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--target-key",
            TARGET_KEY,
            "--result-hash",
            "new",
            "--material-change",
            "--next-agent-todo",
            "Review the material monitor transition and prepare a public-safe packet.",
            "--execute",
        )
        assert payload["ok"] is True, payload
        assert payload["material_change"] is True, payload
        writeback = payload["todo_writeback"]
        assert writeback["consecutive_no_change"] == 0, payload
        assert writeback["next_todos"], payload
        monitor = find_todo(state_file, TODO_ID)
        assert monitor["result_hash"] == "new", monitor
        assert monitor["consecutive_no_change"] == "0", monitor
        assert monitor["material_change"] == "true", monitor
        successors = [
            item
            for item in agent_todos(state_file)
            if item.get("unblocks_todo_id") == TODO_ID
        ]
        assert successors, agent_todos(state_file)
        assert successors[0]["task_class"] == "advancement_task", successors[0]
        successor_id = successors[0]["todo_id"]
        records = monitor_poll_records(registry_path)
        assert [record["classification"] for record in records] == ["quota_monitor_poll"], records
        assert records[0]["delivery_outcome"] == "outcome_progress", records[0]
        event = payload["monitor_event"]
        assert event["monitor_mode"] == "due_monitor_material_transition", event
        assert event["reason_summary"] == "due monitor observation produced a material transition", event
        assert "due monitor material transition observed" in payload["health_check"], payload
        assert "unchanged" not in payload["health_check"], payload

        handoff = run_cli(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
        )
        assert handoff["ok"] is True, handoff
        assert handoff["decision"] == "run", handoff
        assert handoff["effective_action"] == "normal_run", handoff
        assert handoff["agent_lane_next_action"]["todo_id"] == successor_id, handoff
        lane = handoff["work_lane_contract"]
        assert lane["lane"] == "advancement_task", lane
        assert lane["obligation"] == "advance_one_bounded_segment", lane
        assert "due_monitor_context" not in lane.get("reason_codes", []), lane
        monitor_after = find_todo(state_file, TODO_ID)
        assert monitor_after["next_due_at"] != "2026-01-01T00:00:00+00:00", monitor_after
        scheduler = handoff["scheduler_hint"]
        assert scheduler["action"] == "run_now", scheduler
        assert scheduler["cadence_class"] == "active_work", scheduler
        assert scheduler["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=3", scheduler
        contract = handoff["interaction_contract"]
        assert contract["agent_channel"]["must_attempt"] is True, contract
        assert contract["cli_channel"]["spend_after_validation"] is True, contract


def assert_external_material_transition_receipt_correlation() -> None:
    before = {
        "goal_id": GOAL_ID,
        "should_run": True,
        "requires_user_action": False,
        "effective_action": "external_evidence_observe",
        "recommended_action": "Observe the external result handle.",
        "external_evidence_observation": {
            "required": True,
            "must_attempt_observation": True,
            "delivery_allowed": False,
            "if_handle_live_and_unchanged": "quiet_noop_no_spend",
        },
        "work_lane_contract": {
            "lane": "continuous_monitor",
            "must_attempt_work": True,
            "monitor_policy": "read_only_observation_then_no_spend_if_unchanged",
            "reason_codes": ["external_monitor_context"],
        },
        "heartbeat_recommendation": {
            "recommended_mode": "external_evidence_observe_or_blocker",
            "reason": "Observe the external result handle before deciding whether to continue.",
        },
        "agent_identity": {"agent_id": AGENT_ID},
    }

    record = build_quota_monitor_poll_event(
        before,
        todo_id=TODO_ID,
        target_key=TARGET_KEY,
        result_hash="external-result-ready",
        material_change=True,
    )

    event = record["monitor_event"]
    assert event["material_change"] is True, record
    assert event["monitor_mode"] == "external_monitor_material_transition", record
    assert event["reason_summary"] == (
        "external monitor observation produced a material transition"
    ), record
    assert "external monitor material transition observed" in record["health_check"], record
    assert "unchanged" not in record["health_check"], record
    assert "no material transition" not in record["health_check"], record
    assert record["delivery_outcome"] == "outcome_progress", record


def assert_due_monitor_poll_allowed_with_open_user_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-user-gate-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp), include_user_gate=True)
        quota = run_cli(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
        )
        assert quota["requires_user_action"] is True, quota
        contract = quota.get("work_lane_contract")
        assert isinstance(contract, dict), quota
        assert contract.get("obligation") == "attempt_due_monitor", quota

        payload = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--todo-id",
            TODO_ID,
            "--target-key",
            TARGET_KEY,
            "--result-hash",
            "old",
            "--execute",
        )
        assert payload["ok"] is True, payload
        assert payload["agent_id"] == AGENT_ID, payload
        assert payload["todo_id"] == TODO_ID, payload
        assert payload["target_key"] == TARGET_KEY, payload
        item = find_todo(state_file, TODO_ID)
        assert item["consecutive_no_change"] == "2", item
        assert item["next_due_at"] != "2026-01-01T00:00:00+00:00", item


def assert_target_key_cannot_hijack_selected_due_monitor() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-target-key-") as tmp:
        registry_path, state_file = write_fixture(
            Path(tmp),
            selected_target_key=None,
            include_other_monitor=True,
        )
        assert_due_monitor_selected(registry_path, due_count=2)

        payload = run_cli_expect_error(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--target-key",
            OTHER_TARGET_KEY,
            "--result-hash",
            "new",
            "--execute",
        )
        assert payload["ok"] is False, payload
        assert "monitor-poll requires" in payload["reason"], payload
        markdown = run_cli_markdown_expect_error(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--target-key",
            OTHER_TARGET_KEY,
            "--result-hash",
            "new",
            "--material-change",
            "--execute",
        )
        assert "- ok: `False`" in markdown, markdown
        assert "- mode: `monitor-poll`" in markdown, markdown
        assert "- todo_id: ``" in markdown, markdown
        assert f"- target_key: `{OTHER_TARGET_KEY}`" in markdown, markdown
        assert "- material_change: `True`" in markdown, markdown
        assert "- appended: `False`" in markdown, markdown
        assert "- registry_mutated: `False`" in markdown, markdown
        assert "- reason: monitor-poll requires" in markdown, markdown
        assert "`None`" not in markdown, markdown
        selected = find_todo(state_file, TODO_ID)
        other = find_todo(state_file, "todo_monitorpoll111")
        assert selected["result_hash"] == "old", selected
        assert other["result_hash"] == "old", other
        assert monitor_poll_records(registry_path) == [], run_index_records(registry_path)


def assert_compacted_auxiliary_due_monitor_can_write_back() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-compacted-due-") as tmp:
        registry_path, state_file = write_fixture(
            Path(tmp),
            include_other_monitor=True,
            include_advancement=True,
            primary_monitor_priority="P1",
        )
        quota = run_cli(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--available-capability",
            "network",
        )
        assert quota["work_lane_contract"]["obligation"] == "advance_one_bounded_segment", quota
        assert quota["agent_todo_summary"]["monitor_due_count"] == 2, quota
        assert len(quota["agent_todo_summary"]["monitor_due_items"]) == 1, quota
        projected_due_id = quota["agent_todo_summary"]["monitor_due_items"][0]["todo_id"]
        assert projected_due_id != "todo_monitorpoll111", quota

        payload = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--available-capability",
            "network",
            "--todo-id",
            "todo_monitorpoll111",
            "--target-key",
            OTHER_TARGET_KEY,
            "--result-hash",
            "old",
            "--execute",
        )
        assert payload["ok"] is True, payload
        assert payload["todo_writeback"]["todo_id"] == "todo_monitorpoll111", payload
        assert "network" in payload["before"]["capability_gate"]["available"], payload
        assert "network" in payload["after"]["capability_gate"]["available"], payload
        other = find_todo(state_file, "todo_monitorpoll111")
        assert other["consecutive_no_change"] == "2", other
        assert other["next_due_at"] != "2026-01-01T00:00:00+00:00", other


def assert_capability_gated_monitor_poll_requires_declaration_parity() -> None:
    capabilities = ("network", "external_evidence_poll")
    capability_args = tuple(
        arg
        for capability in capabilities
        for arg in ("--available-capability", capability)
    )
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-capability-parity-") as tmp:
        registry_path, state_file = write_fixture(
            Path(tmp),
            monitor_required_capabilities=capabilities,
        )

        should_run = run_cli(
            registry_path,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            *capability_args,
        )
        assert should_run["work_lane_contract"]["obligation"] == "attempt_due_monitor", should_run

        failure = run_cli_expect_error(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--todo-id",
            TODO_ID,
            "--target-key",
            TARGET_KEY,
            "--result-hash",
            "old",
        )
        assert "monitor-poll recomputes should-run" in failure["reason"], failure
        retry = failure["capability_retry"]
        assert retry["missing"] == list(capabilities), retry
        assert retry["cli_args"] == list(capability_args), retry

        option_failure = run_cli_expect_error(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--material-change",
        )
        assert "capability_retry" not in option_failure, option_failure

        success = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            *capability_args,
            "--todo-id",
            TODO_ID,
            "--target-key",
            TARGET_KEY,
            "--result-hash",
            "old",
        )
        assert success["ok"] is True, success
        assert success["before"]["work_lane_contract"]["obligation"] == "attempt_due_monitor", success
        assert success["todo_writeback"]["todo_id"] == TODO_ID, success
        assert find_todo(state_file, TODO_ID)["consecutive_no_change"] == "1"


def assert_cli_help_names_capability_sensitive_commands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "quota", "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    option_help = result.stdout[result.stdout.index("--available-capability") :]
    for command in (
        "quota should-run",
        "quota monitor-poll",
        "quota scheduler-ack",
        "quota scheduler-ack-current",
        "quota spend-slot",
    ):
        assert command in option_help, (command, option_help)


def assert_writeback_helper_preview_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-helper-parity-") as tmp:
        registry_path, _state_file = write_fixture(Path(tmp))
        resolved = resolve_monitor_todo_item(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            todo_id=TODO_ID,
        )
        assert resolved["todo_id"] == TODO_ID, resolved
        assert resolved["target_key"] == TARGET_KEY, resolved
        generated_at = "2026-01-01T00:05:00+00:00"
        preview = write_monitor_poll_todo_state(
            registry_path=registry_path,
            goal_id=GOAL_ID,
            generated_at=generated_at,
            execute=False,
            todo_id=TODO_ID,
            result_hash="old",
        )
        assert preview["schema_version"] == "monitor_poll_todo_writeback_v0", preview
        assert preview["dry_run"] is True, preview
        assert preview["goal_id"] == GOAL_ID, preview
        assert preview["todo_id"] == TODO_ID, preview
        assert preview["target_key"] == TARGET_KEY, preview
        assert preview["result_hash"] == "old", preview
        assert preview["material_change"] is False, preview
        assert preview["consecutive_no_change"] == 2, preview
        assert preview["last_checked_at"] == generated_at, preview
        assert preview["next_due_at"] != "2026-01-01T00:00:00+00:00", preview
        assert preview["cadence"] == "15m", preview


def assert_cli_monitor_poll_uses_should_run_lookback() -> None:
    seen: dict[str, object] = {}

    def fake_collect_status(**kwargs: object) -> dict:
        seen["limit"] = kwargs.get("limit")
        return {"ok": True, "summary": {}}

    def fake_record_quota_monitor_poll(status_payload: dict, **kwargs: object) -> dict:
        seen["status_payload"] = status_payload
        seen["record_kwargs"] = kwargs
        return {"ok": True, "mode": "monitor-poll", "dry_run": True, "appended": False}

    def fake_print_payload(payload: dict, _fmt: str, _renderer: object) -> None:
        seen["payload"] = payload

    args = argparse.Namespace(
        quota_command="monitor-poll",
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        available_capabilities=["network"],
        include_scheduler_detail=False,
        slots=1,
        source="heartbeat",
        void_generated_at=None,
        reason_summary=None,
        todo_id=TODO_ID,
        target_key=None,
        result_hash="old",
        material_change=False,
        cadence=None,
        next_due_at=None,
        next_agent_todo=None,
        next_user_todo=None,
        next_claimed_by=None,
        surface="codex_app",
        state_key="scheduler_hint.codex_app.stateful_backoff",
        applied_rrule=None,
        reset_token=None,
        identity_signature=None,
        dry_run=True,
        execute=False,
        scan_root=str(REPO_ROOT),
        scan_path=[],
        limit=5,
        format="json",
    )
    original_collect_status = quota_command.collect_status
    original_record_monitor_poll = quota_command.record_quota_monitor_poll
    try:
        quota_command.collect_status = fake_collect_status
        quota_command.record_quota_monitor_poll = fake_record_quota_monitor_poll
        rc = quota_command.handle_quota_command(
            args,
            registry_path=REPO_ROOT / ".loopx" / "registry.json",
            runtime_root_arg=None,
            print_payload=fake_print_payload,
            append_cli_rollout_event=lambda **_: {},
        )
    finally:
        quota_command.collect_status = original_collect_status
        quota_command.record_quota_monitor_poll = original_record_monitor_poll

    assert rc == 0, rc
    assert seen["limit"] == AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, seen
    assert seen["record_kwargs"]["available_capabilities"] == ["network"], seen
    assert seen["payload"] == {"ok": True, "mode": "monitor-poll", "dry_run": True, "appended": False}, seen


def main() -> int:
    assert_cli_help_names_capability_sensitive_commands()
    assert_cli_monitor_poll_uses_should_run_lookback()
    assert_writeback_helper_preview_contract()
    assert_unchanged_writeback()
    assert_material_transition_followup()
    assert_external_material_transition_receipt_correlation()
    assert_due_monitor_poll_allowed_with_open_user_gate()
    assert_target_key_cannot_hijack_selected_due_monitor()
    assert_compacted_auxiliary_due_monitor_can_write_back()
    assert_capability_gated_monitor_poll_requires_declaration_parity()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
