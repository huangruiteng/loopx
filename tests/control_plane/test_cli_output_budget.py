from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shlex
from dataclasses import dataclass
from pathlib import Path

from loopx.cli import main as cli_main
from loopx.control_plane.scheduler.execution_context import SchedulerRuntimeProfile
from loopx.control_plane.testing.cli_output_budget import (
    CLI_OUTPUT_BUDGET_BY_ID,
    CLI_OUTPUT_BUDGET_SPECS,
    CLI_OUTPUT_COMMAND_CLASSIFICATION_BY_ID,
    CLI_OUTPUT_COMMAND_CLASSIFICATIONS,
    CLI_OUTPUT_MODE_VARIANT_BY_ID,
    CLI_OUTPUT_MODE_VARIANT_SPECS,
    assert_cli_output_baseline,
    assert_cli_output_mode_variant,
    measure_cli_output,
    public_manifest,
)
from loopx.heartbeat_prompt import build_heartbeat_prompt
from loopx.help_surface import COMMAND_GROUPS
from loopx.rollout_event_log import rollout_event_log_path


GOAL_ID = "cli-output-budget-goal"
AGENT_IDS = ("codex-alpha", "codex-beta", "codex-gamma")
GOAL_TEXT = "Qualify agent-facing CLI output budgets before changing production output."


@dataclass(frozen=True)
class Scenario:
    name: str
    todo_count: int
    agent_count: int
    run_count: int


SCENARIOS = (
    Scenario("small", todo_count=1, agent_count=1, run_count=1),
    Scenario("crowded", todo_count=36, agent_count=1, run_count=12),
    Scenario("multi_agent", todo_count=18, agent_count=3, run_count=12),
)


def _write_fixture(root: Path, scenario: Scenario) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_relative = Path(".codex") / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file = project / state_relative
    state_file.parent.mkdir(parents=True)
    agents = AGENT_IDS[: scenario.agent_count]
    lines = [
        "---",
        "status: active",
        "updated_at: 2026-01-01T00:00:00+00:00",
        "---",
        "",
        "# CLI Output Budget Fixture",
        "",
        "## Agent Todo",
        "",
    ]
    for index in range(scenario.todo_count):
        agent_id = agents[index % len(agents)]
        priority = f"P{index % 3}"
        lines.extend(
            [
                f"- [ ] [{priority}] Validate public fixture lane {index:02d} without reading archival detail.",
                (
                    "  <!-- loopx:todo "
                    f"todo_id=todo_fixture_{index:03d} status=open "
                    "task_class=advancement_task "
                    f"action_kind=fixture_{index % 4} claimed_by={agent_id} "
                    f"priority={priority} -->"
                ),
            ]
        )
    state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "cli-output-budget-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_relative),
                        "adapter": {
                            "kind": "fixture_connected_delivery_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": list(agents),
                            "agent_profiles": {
                                agent_id: {
                                    "schema_version": "agent_profile_v1",
                                    "profile_role": "fixture",
                                    "scope": "public qualification",
                                }
                                for agent_id in agents
                            },
                            "write_scope": ["docs/**"],
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_run_history(runtime, agents=agents, run_count=scenario.run_count)
    _write_rollout_event(runtime, agent_id=agents[0])
    return project, runtime, registry_path, state_file


def _write_run_history(runtime: Path, *, agents: tuple[str, ...], run_count: int) -> None:
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True)
    index_rows = []
    for index in range(run_count):
        json_path = runs_dir / f"fixture-run-{index:02d}.json"
        markdown_path = json_path.with_suffix(".md")
        record = {
            "generated_at": f"2026-01-01T00:{index:02d}:00+00:00",
            "goal_id": GOAL_ID,
            "classification": "fixture_progress",
            "recommended_action": f"Continue fixture step {index}.",
            "health_check": "public fixture healthy",
            "agent_id": agents[index % len(agents)],
            "progress_scope": "agent_lane",
        }
        json_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        markdown_path.write_text("# Public fixture run\n", encoding="utf-8")
        index_rows.append(
            {
                **record,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            }
        )
    (runs_dir / "index.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in index_rows),
        encoding="utf-8",
    )


def _write_rollout_event(runtime: Path, *, agent_id: str) -> None:
    path = rollout_event_log_path(runtime, GOAL_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "loopx_rollout_event_v0",
                "event_id": "fixture-event",
                "event_kind": "todo_updated",
                "recorded_at": "2026-01-01T01:00:00Z",
                "goal_id": GOAL_ID,
                "agent_id": agent_id,
                "todo_id": "todo_fixture_000",
                "status": "appended",
                "summary": "Public fixture evidence.",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_agent_vision(runtime: Path, *, agent_id: str) -> None:
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    index_path = runs_dir / "index.jsonl"
    rows = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    vision = {
        "schema_version": "goal_vision_replan_contract_v0",
        "goal_id": GOAL_ID,
        "agent_id": agent_id,
        "state": "vision_replanned",
        "vision_patch": {
            "vision_summary": "Keep qualifying the CLI output contract.",
            "acceptance_summary": "The active output budget gap is closed.",
            "advancement_policy": "repeat_until_closed",
            "replan_trigger_summary": "The output budget remains above its target.",
        },
        "todo_delta": ["continue_quality_qualification"],
    }
    rows[-1]["agent_vision"] = vision
    run_path = Path(rows[-1]["json_path"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["agent_vision"] = vision
    run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")
    index_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _invoke_cli(args: list[str]) -> tuple[int, str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(args)
    return exit_code, output.getvalue()


@contextlib.contextmanager
def _stable_budget_fixture_root(root: Path):
    """Keep absolute-path fields stable across pytest and xdist temp layouts."""

    root.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    alias = Path("/tmp") / f"loopx-cli-budget-{suffix}"
    if alias.exists() or alias.is_symlink():
        if not alias.is_symlink():
            raise RuntimeError(f"refusing to replace non-symlink fixture root: {alias}")
        alias.unlink()
    alias.symlink_to(root, target_is_directory=True)
    try:
        yield alias
    finally:
        alias.unlink(missing_ok=True)


def _surface_commands(
    *,
    project: Path,
    runtime: Path,
    registry_path: Path,
    state_file: Path,
    output_format: str,
) -> dict[str, list[str]]:
    common = [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        output_format,
    ]
    return {
        "start_goal_guided": [
            "--format",
            output_format,
            "start-goal",
            "--guided",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--host-surface",
            "codex-app",
            "--goal-text",
            GOAL_TEXT,
        ],
        "bootstrap_command_pack": [
            "--format",
            output_format,
            "bootstrap-command-pack",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--host-surface",
            "codex-app",
            "--goal-text",
            GOAL_TEXT,
        ],
        "quota_should_run": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
        ],
        "loopx_turn_plan": common
        + [
            "turn",
            "plan",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
        ],
        "status": common
        + [
            "status",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--limit",
            "5",
        ],
        "diagnose": common
        + [
            "diagnose",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--limit",
            "5",
        ],
        "review_packet_handoff_only": common
        + [
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--handoff-only",
            "--scan-root",
            str(project),
            "--limit",
            "5",
        ],
        "heartbeat_prompt_thin": common
        + [
            "heartbeat-prompt",
            "--thin",
            "--goal-id",
            GOAL_ID,
            "--active-state",
            str(state_file),
            "--agent-id",
            AGENT_IDS[0],
            "--agent-scope",
            "Public CLI output qualification.",
        ],
        "todo_list": common
        + ["todo", "list", "--goal-id", GOAL_ID, "--agent-id", AGENT_IDS[0]],
        "history_limited": common
        + ["history", "--goal-id", GOAL_ID, "--limit", "5"],
        "evidence_log_thin": common
        + [
            "evidence-log",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--limit",
            "5",
            "--history-limit",
            "10",
            "--rollout-limit",
            "20",
            "--thin",
        ],
    }


def _measure_scenario(root: Path, scenario: Scenario) -> dict[str, dict[str, dict]]:
    with _stable_budget_fixture_root(root) as stable_root:
        project, runtime, registry_path, state_file = _write_fixture(
            stable_root,
            scenario,
        )
        results: dict[str, dict[str, dict]] = {}
        for output_format in ("json", "markdown"):
            commands = _surface_commands(
                project=project,
                runtime=runtime,
                registry_path=registry_path,
                state_file=state_file,
                output_format=output_format,
            )
            for surface_id, command in commands.items():
                exit_code, text = _invoke_cli(command)
                assert exit_code == 0, (surface_id, output_format, text)
                measurement = measure_cli_output(  # type: ignore[arg-type]
                    text,
                    output_format=output_format,
                )
                spec = CLI_OUTPUT_BUDGET_BY_ID[surface_id]
                assert_cli_output_baseline(
                    spec,
                    scenario=scenario.name,
                    output_format=output_format,  # type: ignore[arg-type]
                    text=text,
                    measurement=measurement,
                )
                results.setdefault(surface_id, {})[output_format] = measurement
    return results


def _mode_variant_commands(
    *,
    project: Path,
    runtime: Path,
    registry_path: Path,
    state_file: Path,
    output_format: str,
) -> dict[str, list[str]]:
    common = [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        output_format,
    ]
    heartbeat = [
        "--goal-id",
        GOAL_ID,
        "--active-state",
        str(state_file),
        "--agent-id",
        AGENT_IDS[0],
        "--agent-scope",
        "Public CLI output qualification.",
    ]
    return {
        "start_goal_guided_command_pack_detail": [
            "--format",
            output_format,
            "start-goal",
            "--guided",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--host-surface",
            "codex-app",
            "--goal-text",
            GOAL_TEXT,
            "--include-command-pack-detail",
        ],
        "bootstrap_command_pack_message_only": [
            "--format",
            output_format,
            "bootstrap-command-pack",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--goal-text",
            GOAL_TEXT,
            "--message-only",
        ],
        "quota_should_run_scheduler_detail": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--include-scheduler-detail",
        ],
        "quota_should_run_todo_summary_detail": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--include-todo-summary-detail",
        ],
        "quota_should_run_user_todo_summary_detail": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--include-user-todo-summary-detail",
        ],
        "quota_should_run_capability_gate_detail": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--include-capability-gate-detail",
        ],
        "quota_should_run_vision_audit_detail": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--include-vision-audit-detail",
        ],
        "quota_should_run_turn_envelope": common
        + [
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--turn-envelope",
        ],
        "loopx_turn_plan_transaction_detail": common
        + [
            "turn",
            "plan",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--include-transaction-detail",
        ],
        "loopx_turn_run_once_preview": common
        + [
            "turn",
            "run-once",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--project",
            str(project),
            "--host-command-json",
            '["python3","-c","raise SystemExit(9)"]',
            "--scan-root",
            str(project),
            "--no-global-sync",
        ],
        "status_task_graph_detail": common
        + [
            "status",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--limit",
            "5",
            "--include-task-graph",
        ],
        "review_packet_full": common
        + [
            "review-packet",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_IDS[0],
            "--scan-root",
            str(project),
            "--limit",
            "5",
        ],
        "heartbeat_prompt_brief": common + ["heartbeat-prompt", "--brief", *heartbeat],
        "heartbeat_prompt_compact": common + ["heartbeat-prompt", "--compact", *heartbeat],
        "heartbeat_prompt_full": common + ["heartbeat-prompt", "--full", *heartbeat],
    }


def _agent_facing_help_command_ids() -> set[str]:
    command_ids: set[str] = set()
    for group in COMMAND_GROUPS:
        title = str(group.get("title") or "")
        for row in group.get("commands", []):
            if not isinstance(row, dict):
                continue
            command = str(row.get("command") or "")
            selected = title in {"Start here", "Daily operator commands"}
            selected = selected or command == "loopx heartbeat-prompt"
            if not selected or not command.startswith("loopx "):
                continue
            parts = shlex.split(command)
            assert len(parts) >= 2, command
            command_ids.add(parts[1])
    return command_ids


def test_manifest_covers_the_declared_agent_facing_surface_set() -> None:
    expected = {
        "start_goal_guided",
        "bootstrap_command_pack",
        "quota_should_run",
        "loopx_turn_plan",
        "status",
        "diagnose",
        "review_packet_handoff_only",
        "heartbeat_prompt_thin",
        "todo_list",
        "history_limited",
        "evidence_log_thin",
    }
    manifest = public_manifest()
    assert set(CLI_OUTPUT_BUDGET_BY_ID) == expected
    assert manifest["surface_count"] == len(expected)
    assert {row["surface_id"] for row in manifest["surfaces"]} == expected
    assert all(spec.owner and spec.consumer_action and spec.cold_path for spec in CLI_OUTPUT_BUDGET_SPECS)
    expected_variants = {
        "start_goal_guided_command_pack_detail",
        "bootstrap_command_pack_message_only",
        "quota_should_run_scheduler_detail",
        "quota_should_run_todo_summary_detail",
        "quota_should_run_user_todo_summary_detail",
        "quota_should_run_capability_gate_detail",
        "quota_should_run_vision_audit_detail",
        "quota_should_run_turn_envelope",
        "loopx_turn_plan_transaction_detail",
        "loopx_turn_run_once_preview",
        "status_task_graph_detail",
        "review_packet_full",
        "heartbeat_prompt_brief",
        "heartbeat_prompt_compact",
        "heartbeat_prompt_full",
    }
    assert set(CLI_OUTPUT_MODE_VARIANT_BY_ID) == expected_variants
    assert manifest["mode_variant_count"] == len(expected_variants)
    assert {row["variant_id"] for row in manifest["mode_variants"]} == expected_variants
    assert all(
        spec.parent_surface_id in expected for spec in CLI_OUTPUT_MODE_VARIANT_SPECS
    )
    help_command_ids = _agent_facing_help_command_ids()
    assert set(CLI_OUTPUT_COMMAND_CLASSIFICATION_BY_ID) == help_command_ids
    assert manifest["command_classification_count"] == len(help_command_ids)
    assert {
        row["command_id"] for row in manifest["command_classifications"]
    } == help_command_ids
    for classification in CLI_OUTPUT_COMMAND_CLASSIFICATIONS:
        assert classification.rationale
        if classification.qualification == "qualified_default":
            assert classification.surface_id in expected
        else:
            assert classification.qualification == "explicit_cold_path_exception"
            assert classification.surface_id is None


def test_real_cli_output_stays_inside_the_characterized_baseline(
    tmp_path: Path,
) -> None:
    for scenario in SCENARIOS:
        results = _measure_scenario(tmp_path / scenario.name, scenario)
        for formats in results.values():
            assert formats["json"]["json_parseable"] is True
            assert formats["json"]["pretty_print_overhead_chars"] > 0
            assert formats["markdown"]["json_parseable"] is False


def test_quota_cli_keeps_full_agent_todo_diagnostics_on_explicit_cold_path(
    tmp_path: Path,
) -> None:
    with _stable_budget_fixture_root(tmp_path / "quota-todo-detail") as stable_root:
        project, runtime, registry_path, state_file = _write_fixture(
            stable_root,
            SCENARIOS[1],
        )
        default_command = _surface_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run"]
        detail_command = _mode_variant_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run_todo_summary_detail"]

        default_exit_code, default_text = _invoke_cli(default_command)
        detail_exit_code, detail_text = _invoke_cli(detail_command)

    assert default_exit_code == 0, default_text
    assert detail_exit_code == 0, detail_text
    default_payload = json.loads(default_text)
    detail_payload = json.loads(detail_text)
    default_summary = default_payload["agent_todo_summary"]
    detail_summary = detail_payload["agent_todo_summary"]
    assert default_summary["payload_compaction"]["schema_version"] == (
        "quota_cli_todo_summary_compaction_v0"
    )
    assert default_payload["todo_summary_projection"]["detail_ref"] == (
        "quota should-run --include-todo-summary-detail"
    )
    assert "backlog_items" not in default_summary
    assert detail_summary["backlog_items"]
    assert "todo_summary_projection" not in detail_payload
    for key in ("interaction_contract", "scheduler_hint", "selected_todo"):
        assert default_payload[key] == detail_payload[key]


def test_quota_cli_keeps_full_user_todo_diagnostics_on_explicit_cold_path(
    tmp_path: Path,
) -> None:
    with _stable_budget_fixture_root(tmp_path / "quota-user-todo-detail") as stable_root:
        project, runtime, registry_path, state_file = _write_fixture(
            stable_root,
            SCENARIOS[2],
        )
        state_text = state_file.read_text(encoding="utf-8")
        user_section = "\n".join(
            [
                "## User Todo",
                "",
                "- [ ] [P0-user] Approve the scoped output release.",
                (
                    "  <!-- loopx:todo todo_id=todo_user_gate_001 status=open "
                    "task_class=user_gate action_kind=approve_output_release "
                    "blocks_agent=codex-alpha "
                    "decision_scope=release:action:quota-output priority=P0-USER -->"
                ),
                "- [ ] [P1] Review the other agent output notes.",
                (
                    "  <!-- loopx:todo todo_id=todo_user_action_001 status=open "
                    "task_class=user_action action_kind=review_output_notes "
                    "bound_agent=codex-beta priority=P1 -->"
                ),
                "",
            ]
        )
        state_file.write_text(
            state_text.replace("## Agent Todo", f"{user_section}\n## Agent Todo"),
            encoding="utf-8",
        )
        default_command = _surface_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run"]
        detail_command = _mode_variant_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run_user_todo_summary_detail"]

        default_exit_code, default_text = _invoke_cli(default_command)
        detail_exit_code, detail_text = _invoke_cli(detail_command)

    assert default_exit_code == 0, default_text
    assert detail_exit_code == 0, detail_text
    default_payload = json.loads(default_text)
    detail_payload = json.loads(detail_text)
    default_summary = default_payload["user_todo_summary"]
    detail_summary = detail_payload["user_todo_summary"]
    assert default_summary["payload_compaction"]["schema_version"] == (
        "quota_cli_user_todo_summary_compaction_v0"
    )
    assert default_payload["todo_summary_projection"]["role_detail_refs"]["user"] == (
        "quota should-run --include-user-todo-summary-detail"
    )
    assert default_summary["gate_open_items"][0]["todo_id"] == "todo_user_gate_001"
    assert default_summary["gate_open_items"][0]["blocks_agent"] == "codex-alpha"
    assert "other_agent_bound_user_action_items" not in default_summary
    assert detail_summary["other_agent_bound_user_action_items"][0]["todo_id"] == (
        "todo_user_action_001"
    )
    for key in ("interaction_contract", "scheduler_hint", "selected_todo"):
        assert default_payload[key] == detail_payload[key]


def test_quota_cli_keeps_full_capability_gate_on_explicit_cold_path(
    tmp_path: Path,
) -> None:
    with _stable_budget_fixture_root(
        tmp_path / "quota-capability-gate-detail"
    ) as stable_root:
        project, runtime, registry_path, state_file = _write_fixture(
            stable_root,
            SCENARIOS[1],
        )
        state_text = state_file.read_text(encoding="utf-8")
        state_file.write_text(
            state_text.replace(
                "todo_id=todo_fixture_000 status=open ",
                (
                    "todo_id=todo_fixture_000 status=open "
                    "required_capabilities=shell,filesystem_write "
                ),
                1,
            ),
            encoding="utf-8",
        )
        default_command = _surface_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run"]
        detail_command = _mode_variant_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run_capability_gate_detail"]

        default_exit_code, default_text = _invoke_cli(default_command)
        detail_exit_code, detail_text = _invoke_cli(detail_command)

    assert default_exit_code == 0, default_text
    assert detail_exit_code == 0, detail_text
    default_payload = json.loads(default_text)
    detail_payload = json.loads(detail_text)
    default_gate = default_payload["capability_gate"]
    detail_gate = detail_payload["capability_gate"]
    assert default_gate["payload_compaction"]["schema_version"] == (
        "quota_cli_capability_gate_compaction_v0"
    )
    assert default_payload["capability_gate_projection"]["detail_ref"] == (
        "quota should-run --include-capability-gate-detail"
    )
    assert "text" not in default_gate["runnable_candidates"][0]
    assert "handoff_note" not in default_gate["runnable_candidates"][0]
    assert detail_gate["runnable_candidates"][0]["text"]
    assert "capability_gate_projection" not in detail_payload
    for key in (
        "action",
        "decision_owner",
        "required",
        "available",
        "missing",
        "owner_action",
    ):
        assert default_gate[key] == detail_gate[key]
    for key in ("interaction_contract", "scheduler_hint", "selected_todo"):
        assert default_payload[key] == detail_payload[key]


def test_quota_cli_keeps_full_vision_audit_on_explicit_cold_path(
    tmp_path: Path,
) -> None:
    with _stable_budget_fixture_root(tmp_path / "quota-vision-detail") as stable_root:
        project, runtime, registry_path, state_file = _write_fixture(
            stable_root,
            SCENARIOS[1],
        )
        _write_agent_vision(runtime, agent_id=AGENT_IDS[0])
        default_command = _surface_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run"]
        detail_command = _mode_variant_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )["quota_should_run_vision_audit_detail"]

        default_exit_code, default_text = _invoke_cli(default_command)
        detail_exit_code, detail_text = _invoke_cli(detail_command)

    assert default_exit_code == 0, default_text
    assert detail_exit_code == 0, detail_text
    default_payload = json.loads(default_text)
    detail_payload = json.loads(detail_text)
    default_audit = default_payload["vision_continuation_audit"]
    detail_audit = detail_payload["vision_continuation_audit"]
    assert default_audit["schema_version"] == (
        "quota_cli_vision_audit_compaction_v0"
    )
    assert default_payload["vision_audit_projection"]["detail_ref"] == (
        "quota should-run --include-vision-audit-detail"
    )
    assert "acceptance_gaps" not in default_audit
    assert detail_audit["acceptance_gaps"]
    assert "vision_audit_projection" not in detail_payload
    for key in ("required", "decision", "recommended_action"):
        assert default_audit[key] == detail_audit[key]
    for key in ("scheduler_hint", "selected_todo"):
        assert default_payload[key] == detail_payload[key]


def test_status_and_quota_json_ignore_compatibility_reexport_bindings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _stable_budget_fixture_root(tmp_path / "compat") as stable_root:
        project, runtime, registry_path, state_file = _write_fixture(
            stable_root,
            SCENARIOS[0],
        )
        commands = _surface_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format="json",
        )

        def semantic_receipts() -> dict[str, dict[str, object]]:
            receipts: dict[str, dict[str, object]] = {}
            for surface_id in ("status", "quota_should_run"):
                exit_code, text = _invoke_cli(commands[surface_id])
                assert exit_code == 0, (surface_id, text)
                measurement = measure_cli_output(text, output_format="json")
                payload = measurement["payload"]
                assert isinstance(payload, dict)
                receipts[surface_id] = {
                    "top_level_keys": sorted(payload),
                    "json_shape_paths": measurement["json_shape_paths"],
                    "action_signature_sha256": measurement[
                        "action_signature_sha256"
                    ],
                }
            return receipts

        baseline = semantic_receipts()

        import loopx.quota as quota_facade
        import loopx.status as status_facade

        for facade in (status_facade, quota_facade):
            for export_name in facade._PUBLIC_COMPAT_REEXPORTS:
                monkeypatch.setattr(facade, export_name, object())

        assert semantic_receipts() == baseline


def test_collection_growth_and_bootstrap_duplication_are_explicit(tmp_path: Path) -> None:
    small = _measure_scenario(tmp_path / "small", SCENARIOS[0])
    crowded = _measure_scenario(tmp_path / "crowded", SCENARIOS[1])
    added_todos = SCENARIOS[1].todo_count - SCENARIOS[0].todo_count
    added_runs = SCENARIOS[1].run_count - SCENARIOS[0].run_count
    for spec in CLI_OUTPUT_BUDGET_SPECS:
        if spec.max_json_growth_chars_per_unit is None:
            continue
        units = (
            added_runs
            if spec.scale_axis in {"returned_run_count", "returned_evidence_count"}
            else added_todos
        )
        growth = (
            crowded[spec.surface_id]["json"]["chars"]
            - small[spec.surface_id]["json"]["chars"]
        )
        assert growth <= spec.max_json_growth_chars_per_unit * units, (
            spec.surface_id,
            growth,
            units,
        )

    start_payload = small["start_goal_guided"]["json"]["payload"]
    bootstrap_payload = small["bootstrap_command_pack"]["json"]["payload"]
    start_duplication = start_payload["packet_summary"]["duplication_measurement"]
    bootstrap_duplication = bootstrap_payload["packet_summary"]["duplication_measurement"]
    assert start_duplication["objective_content"]["duplicate_occurrences"] <= 11
    assert start_duplication["command_content"]["duplicate_occurrences"] <= 13
    assert bootstrap_duplication["objective_content"]["duplicate_occurrences"] <= 8
    assert bootstrap_duplication["command_content"]["duplicate_occurrences"] <= 9
    assert start_duplication["objective_content"]["duplicate_occurrences"] > 0
    assert bootstrap_duplication["objective_content"]["duplicate_occurrences"] > 0


def test_explicit_compact_and_detail_modes_are_characterized(tmp_path: Path) -> None:
    project, runtime, registry_path, state_file = _write_fixture(tmp_path, SCENARIOS[0])
    for output_format in ("json", "markdown"):
        commands = _mode_variant_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format=output_format,
        )
        for variant_id, command in commands.items():
            spec = CLI_OUTPUT_MODE_VARIANT_BY_ID[variant_id]
            if output_format not in spec.output_formats:
                continue
            exit_code, text = _invoke_cli(command)
            assert exit_code == 0, (variant_id, output_format, text)
            measurement = measure_cli_output(text, output_format=output_format)  # type: ignore[arg-type]
            assert_cli_output_mode_variant(
                spec,
                output_format=output_format,  # type: ignore[arg-type]
                text=text,
                measurement=measurement,
            )


def test_turn_envelope_cli_preserves_codex_app_scheduler_binding(
    tmp_path: Path,
) -> None:
    project, runtime, registry_path, state_file = _write_fixture(
        tmp_path,
        SCENARIOS[0],
    )
    command = _mode_variant_commands(
        project=project,
        runtime=runtime,
        registry_path=registry_path,
        state_file=state_file,
        output_format="json",
    )["quota_should_run_turn_envelope"]

    exit_code, text = _invoke_cli([*command, "--codex-app"])

    assert exit_code == 0, text
    payload = json.loads(text)
    assert payload["detail_ref"]["full_decision"] == (
        "loopx --format json quota should-run "
        f"--goal-id {GOAL_ID} --agent-id {AGENT_IDS[0]} --codex-app"
    )


def test_first_class_runtime_profiles_fit_thin_prompt_budget_and_cli_round_trip(
    tmp_path: Path,
) -> None:
    cases = (
        (SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT, "--codex-app"),
        (SchedulerRuntimeProfile.CODEX_CLI_VISIBLE, "--runtime-profile codex_cli"),
        (SchedulerRuntimeProfile.CLAUDE_CODE_VISIBLE, "--runtime-profile claude_code"),
        (SchedulerRuntimeProfile.GENERIC_CLI_AGENT_LOOP, "--runtime-profile generic_cli"),
        (
            SchedulerRuntimeProfile.GENERIC_CLI_OUTER_CONTROLLER,
            "--runtime-profile outer_controller",
        ),
    )
    for index, (profile, expected_binding) in enumerate(cases):
        with _stable_budget_fixture_root(tmp_path / f"profile-{index}") as root:
            project, runtime, registry_path, state_file = _write_fixture(
                root,
                SCENARIOS[0],
            )
            prompt = build_heartbeat_prompt(
                goal_id=GOAL_ID,
                active_state=state_file,
                agent_id=AGENT_IDS[0],
                thin=True,
                runtime_profile=profile.value,
            )

            assert prompt["interface_budget"]["within_budget"] is True
            assert expected_binding in prompt["quota_guard_command"]
            assert expected_binding in prompt["task_body"]
            assert " -H " not in prompt["quota_guard_command"]
            assert " -O " not in prompt["quota_guard_command"]
            assert " -M " not in prompt["quota_guard_command"]

            exit_code, text = _invoke_cli(
                [
                    "--registry",
                    str(registry_path),
                    "--runtime-root",
                    str(runtime),
                    "--format",
                    "json",
                    "quota",
                    "should-run",
                    "--goal-id",
                    GOAL_ID,
                    "--agent-id",
                    AGENT_IDS[0],
                    "--scan-root",
                    str(project),
                    "--runtime-profile",
                    profile.value,
                ]
            )

            assert exit_code == 0, text
            payload = json.loads(text)
            assert payload["scheduler_hint"].get("action") != (
                "repair_scheduler_execution_context"
            )
