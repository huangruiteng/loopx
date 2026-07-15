from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal


CLI_OUTPUT_BUDGET_SCHEMA_VERSION = "loopx_cli_output_budget_v0"
CLI_OUTPUT_MEASUREMENT_SCHEMA_VERSION = "loopx_cli_output_measurement_v0"

OutputFormat = Literal["json", "markdown"]
QualificationPolicy = Literal[
    "absolute_hot_path",
    "baseline_and_growth",
    "explicit_limit_cold_path",
]


@dataclass(frozen=True)
class CliOutputBudgetSpec:
    surface_id: str
    command: str
    owner: str
    consumer_action: str
    qualification_policy: QualificationPolicy
    cold_path: str
    semantic_json_keys: tuple[str, ...]
    markdown_anchor: str
    max_chars: dict[str, dict[OutputFormat, int]]
    max_lines: dict[str, dict[OutputFormat, int]]
    scale_axis: str | None = None
    max_json_growth_chars_per_unit: int | None = None


# These ceilings characterize the emitted CLI text on public fixtures. They are
# deliberately separate from compact in-memory payload budgets. Baseline-only
# ceilings freeze current debt so later optimization can lower them safely.
CLI_OUTPUT_BUDGET_SPECS: tuple[CliOutputBudgetSpec, ...] = (
    CliOutputBudgetSpec(
        surface_id="start_goal_guided",
        command="start-goal --guided",
        owner="goal bootstrap",
        consumer_action="plan a goal start before any mutation",
        qualification_policy="baseline_and_growth",
        cold_path="packet_summary detail_refs and bootstrap-command-pack",
        semantic_json_keys=("guided_transaction", "command_pack", "safety_contract", "packet_summary"),
        markdown_anchor="# Guided Start Goal",
        max_chars={
            "small": {"json": 64_000, "markdown": 3_200},
            "crowded": {"json": 64_000, "markdown": 3_200},
            "multi_agent": {"json": 64_000, "markdown": 3_200},
        },
        max_lines={
            "small": {"json": 650, "markdown": 55},
            "crowded": {"json": 650, "markdown": 55},
            "multi_agent": {"json": 650, "markdown": 55},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=8,
    ),
    CliOutputBudgetSpec(
        surface_id="bootstrap_command_pack",
        command="bootstrap-command-pack",
        owner="slash-command bootstrap",
        consumer_action="connect and activate one host loop",
        qualification_policy="baseline_and_growth",
        cold_path="message-only projection and packet_summary detail_refs",
        semantic_json_keys=("commands", "goal_start_contract", "host_loop_activation", "packet_summary"),
        markdown_anchor="# /loopx Bootstrap Command Pack",
        max_chars={
            "small": {"json": 45_000, "markdown": 14_500},
            "crowded": {"json": 45_000, "markdown": 14_500},
            "multi_agent": {"json": 45_000, "markdown": 14_500},
        },
        max_lines={
            "small": {"json": 470, "markdown": 240},
            "crowded": {"json": 470, "markdown": 240},
            "multi_agent": {"json": 470, "markdown": 240},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=8,
    ),
    CliOutputBudgetSpec(
        surface_id="quota_should_run",
        command="quota should-run",
        owner="quota guard",
        consumer_action="decide whether one agent may run",
        qualification_policy="absolute_hot_path",
        cold_path="status, history, active state, and --include-scheduler-detail",
        semantic_json_keys=("interaction_contract", "scheduler_hint", "selected_todo"),
        markdown_anchor="# LoopX Quota Should Run",
        max_chars={
            "small": {"json": 26_000, "markdown": 6_700},
            "crowded": {"json": 40_000, "markdown": 7_800},
            "multi_agent": {"json": 36_000, "markdown": 7_000},
        },
        max_lines={
            "small": {"json": 720, "markdown": 72},
            "crowded": {"json": 1_050, "markdown": 78},
            "multi_agent": {"json": 1_000, "markdown": 75},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=400,
    ),
    CliOutputBudgetSpec(
        surface_id="status",
        command="status --goal-id",
        owner="operator and agent status",
        consumer_action="locate the current goal and attention state",
        qualification_policy="absolute_hot_path",
        cold_path="--include-task-graph, history, and run artifacts",
        semantic_json_keys=("status_contract", "attention_queue", "todo_index"),
        markdown_anchor="# LoopX Status",
        max_chars={
            "small": {"json": 42_000, "markdown": 7_000},
            "crowded": {"json": 70_000, "markdown": 7_800},
            "multi_agent": {"json": 70_000, "markdown": 7_800},
        },
        max_lines={
            "small": {"json": 1_120, "markdown": 85},
            "crowded": {"json": 1_850, "markdown": 90},
            "multi_agent": {"json": 1_850, "markdown": 90},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=750,
    ),
    CliOutputBudgetSpec(
        surface_id="diagnose",
        command="diagnose --goal-id",
        owner="agent self-repair",
        consumer_action="explain whether and why one goal can advance",
        qualification_policy="explicit_limit_cold_path",
        cold_path="status plus goal-specific quota and todo reads",
        semantic_json_keys=("agent_must_reason", "selected", "goals", "status_summary"),
        markdown_anchor="# LoopX Diagnosis Packet",
        max_chars={
            "small": {"json": 21_000, "markdown": 4_300},
            "crowded": {"json": 34_000, "markdown": 4_500},
            "multi_agent": {"json": 21_000, "markdown": 4_300},
        },
        max_lines={
            "small": {"json": 470, "markdown": 72},
            "crowded": {"json": 720, "markdown": 72},
            "multi_agent": {"json": 480, "markdown": 72},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=360,
    ),
    CliOutputBudgetSpec(
        surface_id="review_packet_handoff_only",
        command="review-packet --handoff-only",
        owner="project-agent handoff",
        consumer_action="forward the smallest sufficient work packet",
        qualification_policy="absolute_hot_path",
        cold_path="full review-packet and run-history artifacts",
        semantic_json_keys=("project_agent_handoff", "handoff_interface_budget", "within_budget"),
        markdown_anchor="quota should-run",
        max_chars={
            "small": {"json": 4_500, "markdown": 1_400},
            "crowded": {"json": 5_100, "markdown": 1_700},
            "multi_agent": {"json": 5_100, "markdown": 1_700},
        },
        max_lines={
            "small": {"json": 48, "markdown": 18},
            "crowded": {"json": 48, "markdown": 20},
            "multi_agent": {"json": 48, "markdown": 20},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=20,
    ),
    CliOutputBudgetSpec(
        surface_id="heartbeat_prompt_thin",
        command="heartbeat-prompt --thin",
        owner="heartbeat automation",
        consumer_action="wake and route one bounded turn",
        qualification_policy="absolute_hot_path",
        cold_path="heartbeat-prompt --compact or --full",
        semantic_json_keys=("task_body", "quota_guard_command", "interface_budget"),
        markdown_anchor="# Heartbeat Automation Prompt",
        max_chars={
            "small": {"json": 6_000, "markdown": 5_100},
            "crowded": {"json": 6_000, "markdown": 5_100},
            "multi_agent": {"json": 6_000, "markdown": 5_100},
        },
        max_lines={
            "small": {"json": 58, "markdown": 72},
            "crowded": {"json": 58, "markdown": 72},
            "multi_agent": {"json": 58, "markdown": 72},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=4,
    ),
    CliOutputBudgetSpec(
        surface_id="todo_list",
        command="todo list",
        owner="todo control plane",
        consumer_action="select and inspect current work items",
        qualification_policy="baseline_and_growth",
        cold_path="role/status filters and direct todo-id lifecycle commands",
        semantic_json_keys=("todos", "agent_todos", "filter_semantics"),
        markdown_anchor="# LoopX Todo List",
        max_chars={
            "small": {"json": 7_500, "markdown": 1_000},
            "crowded": {"json": 82_000, "markdown": 8_500},
            "multi_agent": {"json": 30_000, "markdown": 2_200},
        },
        max_lines={
            "small": {"json": 220, "markdown": 28},
            "crowded": {"json": 2_300, "markdown": 70},
            "multi_agent": {"json": 850, "markdown": 38},
        },
        scale_axis="todo_count",
        max_json_growth_chars_per_unit=2_050,
    ),
    CliOutputBudgetSpec(
        surface_id="history_limited",
        command="history --limit 5",
        owner="run-history read model",
        consumer_action="inspect bounded recent progress",
        qualification_policy="explicit_limit_cold_path",
        cold_path="individual run JSON/Markdown artifacts",
        semantic_json_keys=("goals", "runs", "run_count"),
        markdown_anchor="# LoopX Run History",
        max_chars={
            "small": {"json": 5_800, "markdown": 900},
            "crowded": {"json": 12_500, "markdown": 1_500},
            "multi_agent": {"json": 12_500, "markdown": 1_500},
        },
        max_lines={
            "small": {"json": 160, "markdown": 22},
            "crowded": {"json": 280, "markdown": 28},
            "multi_agent": {"json": 290, "markdown": 28},
        },
        scale_axis="returned_run_count",
        max_json_growth_chars_per_unit=1_600,
    ),
    CliOutputBudgetSpec(
        surface_id="evidence_log_thin",
        command="evidence-log --thin --limit 5",
        owner="agent-scoped evidence ledger",
        consumer_action="read bounded public-safe evidence for replan",
        qualification_policy="explicit_limit_cold_path",
        cold_path="referenced run-history and rollout-event artifacts",
        semantic_json_keys=("ledger", "truncated", "other_agent_frontier"),
        markdown_anchor="# LoopX Evidence Log",
        max_chars={
            "small": {"json": 2_900, "markdown": 800},
            "crowded": {"json": 3_500, "markdown": 1_100},
            "multi_agent": {"json": 4_300, "markdown": 1_200},
        },
        max_lines={
            "small": {"json": 100, "markdown": 26},
            "crowded": {"json": 120, "markdown": 30},
            "multi_agent": {"json": 140, "markdown": 34},
        },
        scale_axis="returned_evidence_count",
        max_json_growth_chars_per_unit=800,
    ),
)


CLI_OUTPUT_BUDGET_BY_ID = {spec.surface_id: spec for spec in CLI_OUTPUT_BUDGET_SPECS}


def measure_cli_output(
    text: str,
    *,
    output_format: OutputFormat,
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    compact_payload_chars: int | None = None
    if output_format == "json":
        decoded = json.loads(text)
        if not isinstance(decoded, dict):
            raise ValueError("agent-facing CLI JSON output must be an object")
        payload = decoded
        compact_payload_chars = len(
            json.dumps(
                decoded,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return {
        "schema_version": CLI_OUTPUT_MEASUREMENT_SCHEMA_VERSION,
        "format": output_format,
        "chars": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "lines": len(text.splitlines()),
        "json_parseable": payload is not None,
        "top_level_keys": len(payload or {}),
        "compact_payload_chars": compact_payload_chars,
        "pretty_print_overhead_chars": (
            len(text) - compact_payload_chars
            if compact_payload_chars is not None
            else None
        ),
        "payload": payload,
    }


def assert_cli_output_baseline(
    spec: CliOutputBudgetSpec,
    *,
    scenario: str,
    output_format: OutputFormat,
    text: str,
    measurement: dict[str, Any],
) -> None:
    max_chars = spec.max_chars[scenario][output_format]
    max_lines = spec.max_lines[scenario][output_format]
    if int(measurement["chars"]) > max_chars:
        raise AssertionError(
            f"{spec.surface_id}/{scenario}/{output_format} emitted "
            f"{measurement['chars']} chars; baseline ceiling is {max_chars}"
        )
    if int(measurement["lines"]) > max_lines:
        raise AssertionError(
            f"{spec.surface_id}/{scenario}/{output_format} emitted "
            f"{measurement['lines']} lines; baseline ceiling is {max_lines}"
        )
    if output_format == "markdown" and spec.markdown_anchor not in text:
        raise AssertionError(
            f"{spec.surface_id} markdown lost semantic anchor {spec.markdown_anchor!r}"
        )
    if output_format == "json":
        payload = measurement.get("payload")
        if not isinstance(payload, dict):
            raise AssertionError(f"{spec.surface_id} did not emit a JSON object")
        missing = [key for key in spec.semantic_json_keys if key not in payload]
        if missing:
            raise AssertionError(
                f"{spec.surface_id} JSON lost semantic key(s): {', '.join(missing)}"
            )


def public_manifest() -> dict[str, Any]:
    return {
        "schema_version": CLI_OUTPUT_BUDGET_SCHEMA_VERSION,
        "surface_count": len(CLI_OUTPUT_BUDGET_SPECS),
        "surfaces": [
            {
                "surface_id": spec.surface_id,
                "command": spec.command,
                "owner": spec.owner,
                "consumer_action": spec.consumer_action,
                "qualification_policy": spec.qualification_policy,
                "cold_path": spec.cold_path,
                "formats": ["json", "markdown"],
                "scenarios": sorted(spec.max_chars),
                "scale_axis": spec.scale_axis,
            }
            for spec in CLI_OUTPUT_BUDGET_SPECS
        ],
    }
