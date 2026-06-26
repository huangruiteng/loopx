from __future__ import annotations

import posixpath
import re
import shlex

from .todo_contract import build_todo_id

BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION = (
    "loopx_benchmark_case_active_state_v1"
)
BENCHMARK_CASE_STATE_ROOT = "/app/.codex/goals"
BENCHMARK_CASE_ACTIVE_STATE_BASENAME = "ACTIVE_GOAL_STATE.md"
BENCHMARK_CASE_ACTIVE_STATE_INIT_FLOW = (
    "shared_loopx_benchmark_case_active_state"
)
BENCHMARK_CASE_ACTIVE_STATE_INIT_STAGE = "before_codex_worker_start"
BENCHMARK_CASE_ACTIVE_STATE_STATUS_FIELD = "case_goal_state_init_status"
BENCHMARK_CASE_LIFECYCLE_SCHEMA_VERSION = "loopx_benchmark_case_lifecycle_v0"
BENCHMARK_CASE_LIFECYCLE_SOURCE_OF_TRUTH = "case_active_state_and_rollout_event_log"
BENCHMARK_CASE_LOOPX_INSTALL_FLOW_SCHEMA_VERSION = (
    "loopx_benchmark_case_install_flow_v0"
)
BENCHMARK_CASE_LIFECYCLE_DRIVER_SCHEMA_VERSION = (
    "loopx_benchmark_case_product_lifecycle_driver_v1"
)
BENCHMARK_CASE_LOOPX_PROJECT_ROOT = "/app"
BENCHMARK_CASE_LOOPX_HOME = "/app"
BENCHMARK_CASE_LOOPX_CLI_PATH = "/app/.local/bin/loopx"
BENCHMARK_CASE_LOOPX_REGISTRY_PATH = "/app/.loopx/registry.json"
BENCHMARK_CASE_LOOPX_RUNTIME_ROOT = "/app/.loopx/runtime"
BENCHMARK_CASE_LOOPX_GOAL_DOC_PATH = "/app/.loopx/LOOPX_CASE_GOAL.md"
BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET = "/app/.loopx-source"
BENCHMARK_CASE_LOOPX_EVENT_LOG_BASENAME = "rollout-event-log.jsonl"
BENCHMARK_CASE_LOOPX_AGENT_ID = "codex-benchmark-agent"
BENCHMARK_CASE_LOOPX_TODO_TEXT = (
    "Solve the current benchmark case using the official LoopX product-mode "
    "lifecycle; inspect the task, implement the fix, validate locally, update "
    "this todo, refresh state, and spend quota once after validated work."
)
BENCHMARK_CASE_LOOPX_TODO_ID = build_todo_id(
    role="agent",
    source_section="Agent Todo",
    index=1,
    text=BENCHMARK_CASE_LOOPX_TODO_TEXT,
)
BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS = (
    BENCHMARK_CASE_LOOPX_TODO_TEXT,
    (
        "Validate the benchmark solution locally and keep public-safe LoopX "
        "evidence before final closeout."
    ),
    (
        "Close out the selected solver todo only after validation, then "
        "refresh state and spend quota once."
    ),
)
BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS = tuple(
    build_todo_id(
        role="agent",
        source_section="Agent Todo",
        index=index,
        text=text,
    )
    for index, text in enumerate(
        BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS,
        start=1,
    )
)
BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID = (
    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS[0]
)
BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS = "loopx-product-mode"
BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE = "prompt_driven_loopx_cli"
BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE = (
    "orchestrated_agentloop_loopx_cli"
)
BENCHMARK_CASE_LOOPX_EXECUTION_STYLES = (
    BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE,
    BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE,
)
BENCHMARK_CASE_LOOPX_OFFICIAL_INSTALLER_URL = (
    "https://raw.githubusercontent.com/huangruiteng/loopx/main/"
    "scripts/install-from-github.sh"
)
BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE = (
    "prompt_driven_case_local_loopx_cli"
)
BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE = (
    "cli_scheduler_case_local_loopx_cli"
)
BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS = (
    "case_goal_state_init_required",
    "case_goal_state_initialized_before_agent",
    "case_goal_state_init_status",
    "case_goal_state_schema_version",
    "case_goal_state_path",
)
BENCHMARK_CASE_LIFECYCLE_STEPS = (
    "quota_should_run",
    "todo_claim_or_update",
    "bounded_agent_turn",
    "validation_or_case_result",
    "refresh_state",
    "quota_spend",
)
BENCHMARK_CASE_LIFECYCLE_ROLLOUT_EVENTS = (
    "quota_should_run",
    "todo_claim",
    "todo_update",
    "validation",
    "refresh_state",
    "quota_spend",
    "compact_case_result",
    "failure_attribution",
)


def benchmark_case_goal_id(benchmark_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", benchmark_id.lower()).strip("-")
    return f"{slug or 'benchmark'}-case"


def benchmark_case_arm_goal_id(
    *,
    benchmark_id: str,
    case_id: str,
    arm_id: str,
) -> str:
    """Return a canonical per-benchmark/case/arm LoopX goal id."""

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        f"{benchmark_id}-{case_id}-{arm_id}".lower(),
    ).strip("-")
    return f"{slug or 'benchmark-case-arm'}-case"


def benchmark_case_active_state_path(
    goal_id: str,
    *,
    root: str = BENCHMARK_CASE_STATE_ROOT,
) -> str:
    return f"{root.rstrip('/')}/{goal_id}/{BENCHMARK_CASE_ACTIVE_STATE_BASENAME}"


def benchmark_case_loopx_case_dir(
    goal_id: str,
    *,
    root: str = BENCHMARK_CASE_STATE_ROOT,
) -> str:
    return f"{root.rstrip('/')}/{goal_id}"


def benchmark_case_loopx_event_log_path(
    goal_id: str,
    *,
    root: str = BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
) -> str:
    return (
        f"{root.rstrip('/')}/goals/{goal_id}/"
        f"{BENCHMARK_CASE_LOOPX_EVENT_LOG_BASENAME}"
    )


def benchmark_case_active_state_init_contract(
    *,
    benchmark_id: str,
    goal_id: str | None = None,
    case_state_path: str | None = None,
    initialized_by_launch_packet: bool = False,
) -> dict[str, object]:
    """Return the public-safe init contract shared by benchmark adapters."""

    resolved_goal_id = goal_id or benchmark_case_goal_id(benchmark_id)
    resolved_path = case_state_path or benchmark_case_active_state_path(
        resolved_goal_id
    )
    return {
        "schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
        "benchmark_case_goal_id": resolved_goal_id,
        "case_state_path": resolved_path,
        "init_required_before_worker": True,
        "initialized_by_launch_packet": initialized_by_launch_packet,
        "init_stage": BENCHMARK_CASE_ACTIVE_STATE_INIT_STAGE,
        "init_flow": BENCHMARK_CASE_ACTIVE_STATE_INIT_FLOW,
        "status_field": BENCHMARK_CASE_ACTIVE_STATE_STATUS_FIELD,
        "proof_fields": list(BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS),
        "surrogate_state_files_allowed": False,
        "raw_task_text_required_for_init": False,
        "local_paths_recorded": False,
    }


def benchmark_case_lifecycle_contract(
    *,
    benchmark_id: str,
    case_id: str,
    arm_id: str,
    goal_id: str | None = None,
    case_state_path: str | None = None,
    max_rounds: int = 5,
) -> dict[str, object]:
    """Return the shared product-path lifecycle contract for a benchmark arm.

    This contract is public-safe and deliberately contains only ids, booleans,
    and lifecycle/event names. It lets benchmark adapters prove that a treatment
    arm uses an isolated LoopX state path and the real quota/todo/
    validation/refresh/spend lifecycle instead of a runner-internal surrogate.
    """

    resolved_goal_id = goal_id or benchmark_case_arm_goal_id(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arm_id=arm_id,
    )
    resolved_path = case_state_path or benchmark_case_active_state_path(
        resolved_goal_id
    )
    rounds = max_rounds if isinstance(max_rounds, int) and max_rounds > 0 else 5
    return {
        "schema_version": BENCHMARK_CASE_LIFECYCLE_SCHEMA_VERSION,
        "lifecycle_driver_schema_version": (
            BENCHMARK_CASE_LIFECYCLE_DRIVER_SCHEMA_VERSION
        ),
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "arm_id": arm_id,
        "case_isolation_scope": "per_benchmark_case_arm",
        "benchmark_case_goal_id": resolved_goal_id,
        "case_state_path": resolved_path,
        "case_registry_path": BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
        "case_runtime_root": BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
        "case_goal_doc_path": BENCHMARK_CASE_LOOPX_GOAL_DOC_PATH,
        "case_cli_path": BENCHMARK_CASE_LOOPX_CLI_PATH,
        "case_agent_id": BENCHMARK_CASE_LOOPX_AGENT_ID,
        "case_todo_id": BENCHMARK_CASE_LOOPX_TODO_ID,
        "case_todo_text_public_safe": BENCHMARK_CASE_LOOPX_TODO_TEXT,
        "case_state_init_required_before_worker": True,
        "formal_treatment_semantics": BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS,
        "canonical_product_mode_lifecycle_driver": True,
        "supported_execution_styles": list(BENCHMARK_CASE_LOOPX_EXECUTION_STYLES),
        "preferred_execution_style": BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE,
        "source_of_truth": BENCHMARK_CASE_LIFECYCLE_SOURCE_OF_TRUTH,
        "required_lifecycle_steps": list(BENCHMARK_CASE_LIFECYCLE_STEPS),
        "required_rollout_event_kinds": list(BENCHMARK_CASE_LIFECYCLE_ROLLOUT_EVENTS),
        "max_rounds_budget": rounds,
        "host_may_install_and_seed_case_state": True,
        "host_may_preflight_quota_before_agent": True,
        "host_claims_case_todo_before_agent": False,
        "agent_must_claim_selected_case_todo": True,
        "runner_internal_prompt_polling_only_allowed": False,
        "surrogate_state_files_allowed": False,
        "official_feedback_forwarded": False,
        "raw_task_text_required_for_lifecycle": False,
        "local_paths_recorded": False,
    }


def render_benchmark_case_lifecycle_contract_lines(
    contract: dict[str, object],
) -> list[str]:
    """Render a compact text packet for a case lifecycle contract."""

    fields = (
        "schema_version",
        "benchmark_id",
        "case_id",
        "arm_id",
        "case_isolation_scope",
        "benchmark_case_goal_id",
        "case_state_path",
        "case_registry_path",
        "case_runtime_root",
        "case_goal_doc_path",
        "case_cli_path",
        "case_agent_id",
        "case_todo_id",
        "formal_treatment_semantics",
        "preferred_execution_style",
        "source_of_truth",
        "max_rounds_budget",
        "canonical_product_mode_lifecycle_driver",
        "host_claims_case_todo_before_agent",
        "agent_must_claim_selected_case_todo",
        "runner_internal_prompt_polling_only_allowed",
        "surrogate_state_files_allowed",
        "official_feedback_forwarded",
    )
    lines = ["benchmark_case_lifecycle_contract:"]
    for field in fields:
        value = contract.get(field)
        if value is None or value == "":
            continue
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"  {field}: {rendered}")
    for field in (
        "supported_execution_styles",
        "required_lifecycle_steps",
        "required_rollout_event_kinds",
    ):
        value = contract.get(field)
        if isinstance(value, list) and value:
            lines.append(f"  {field}: {','.join(str(item) for item in value)}")
    return lines


def _packet_line(indent: str, key: str, value: object) -> str:
    rendered = str(value).lower() if isinstance(value, bool) else str(value)
    return f"{indent}{key}: {rendered}"


def build_benchmark_case_lifecycle_packet(
    *,
    packet_header: str | None = None,
    packet_mode: str | None = None,
    benchmark_family: str | None = None,
    benchmark_id: str,
    case_id: str,
    arm_id: str,
    max_rounds: int = 5,
    indent: str = "",
    include_case_paths: bool = False,
    include_case_event_log: bool = False,
    include_cli_commands: bool = True,
    include_completion_hints: bool = False,
) -> tuple[str, dict[str, object]]:
    """Return the shared prompt-facing LoopX case lifecycle packet.

    Benchmark runners differ in the surrounding access packet, but the
    case-local product-mode lifecycle and CLI commands must stay identical.
    Keeping this renderer next to the lifecycle contract prevents future CLI
    parameter drift across SkillsBench, Terminal-Bench, and Harbor workers.
    """

    contract = benchmark_case_lifecycle_contract(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arm_id=arm_id,
        max_rounds=max_rounds,
    )
    case_goal_id = str(contract["benchmark_case_goal_id"])
    case_cli_prefix = benchmark_case_loopx_command_prefix(
        case_cli_path=BENCHMARK_CASE_LOOPX_CLI_PATH,
        case_registry_path=BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
        case_runtime_root=BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
    )

    lines: list[str] = []
    if packet_header:
        lines.append(packet_header)
    if packet_mode is not None:
        lines.append(_packet_line(indent, "packet_mode", packet_mode))
    if benchmark_family is not None:
        lines.append(_packet_line(indent, "benchmark_family", benchmark_family))
    lines.extend(
        [
            _packet_line(
                indent,
                "loopx_formal_treatment_semantics",
                BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS,
            ),
            _packet_line(
                indent,
                "loopx_canonical_product_mode_lifecycle_driver",
                True,
            ),
            _packet_line(
                indent,
                "loopx_product_path_primary_route",
                BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE,
            ),
            _packet_line(
                indent,
                "loopx_prompt_driven_execution_style",
                BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE,
            ),
            _packet_line(
                indent,
                "loopx_workflow_orchestrated_execution_style",
                BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE,
            ),
        ]
    )
    if include_case_paths:
        lines.extend(
            [
                _packet_line(
                    indent,
                    "loopx_case_cli_path",
                    BENCHMARK_CASE_LOOPX_CLI_PATH,
                ),
                _packet_line(
                    indent,
                    "loopx_case_registry_path",
                    BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
                ),
                _packet_line(
                    indent,
                    "loopx_case_runtime_root",
                    BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
                ),
            ]
        )
    if include_case_event_log:
        lines.append(
            _packet_line(
                indent,
                "loopx_case_rollout_event_log_path",
                benchmark_case_loopx_event_log_path(case_goal_id),
            )
        )
    lines.extend(
        [
            _packet_line(
                indent,
                "loopx_case_agent_id",
                BENCHMARK_CASE_LOOPX_AGENT_ID,
            ),
            _packet_line(indent, "loopx_case_todo_id", BENCHMARK_CASE_LOOPX_TODO_ID),
            _packet_line(indent, "loopx_case_todo_seeded_open", True),
            _packet_line(indent, "loopx_case_todo_preclaimed_by_host", False),
            _packet_line(indent, "loopx_agent_must_claim_selected_case_todo", True),
        ]
    )
    lines.extend(render_benchmark_case_lifecycle_contract_lines(contract))
    if include_cli_commands:
        lines.extend(
            [
                _packet_line(
                    indent,
                    "loopx_case_command_quota_should_run",
                    (
                        f"{case_cli_prefix} quota should-run "
                        f"--goal-id {shlex.quote(case_goal_id)} "
                        f"--agent-id {BENCHMARK_CASE_LOOPX_AGENT_ID}"
                    ),
                ),
                _packet_line(
                    indent,
                    "loopx_case_command_claim_todo",
                    (
                        f"{case_cli_prefix} todo claim "
                        f"--goal-id {shlex.quote(case_goal_id)} "
                        f"--todo-id {BENCHMARK_CASE_LOOPX_TODO_ID} "
                        f"--claimed-by {BENCHMARK_CASE_LOOPX_AGENT_ID}"
                    ),
                ),
                _packet_line(
                    indent,
                    "loopx_case_command_status",
                    (
                        f"{case_cli_prefix} status --limit 5 "
                        f"--agent-id {BENCHMARK_CASE_LOOPX_AGENT_ID}"
                    ),
                ),
                _packet_line(
                    indent,
                    "loopx_case_command_mark_todo_done_when_complete",
                    (
                        f"{case_cli_prefix} todo complete "
                        f"--goal-id {shlex.quote(case_goal_id)} "
                        f"--todo-id {BENCHMARK_CASE_LOOPX_TODO_ID} "
                        f"--claimed-by {BENCHMARK_CASE_LOOPX_AGENT_ID} "
                        "--evidence local_validation_done"
                    ),
                ),
                _packet_line(
                    indent,
                    "loopx_case_command_refresh_state",
                    (
                        f"{case_cli_prefix} refresh-state "
                        f"--goal-id {shlex.quote(case_goal_id)} "
                        "--classification benchmark_case_agent_progress "
                        "--delivery-batch-scale implementation "
                        "--delivery-outcome outcome_progress "
                        f"--agent-id {BENCHMARK_CASE_LOOPX_AGENT_ID} "
                        "--agent-lane benchmark_case"
                    ),
                ),
                _packet_line(
                    indent,
                    "loopx_case_command_spend_quota",
                    (
                        f"{case_cli_prefix} quota spend-slot "
                        f"--goal-id {shlex.quote(case_goal_id)} "
                        f"--agent-id {BENCHMARK_CASE_LOOPX_AGENT_ID} "
                        "--source adapter --execute"
                    ),
                ),
            ]
        )
    if include_completion_hints:
        lines.extend(
            [
                _packet_line(
                    indent,
                    "loopx_completion_source_of_truth",
                    "case_local_active_todo",
                ),
                _packet_line(
                    indent,
                    "before_planning_call_loopx_case_quota_should_run_once",
                    True,
                ),
                _packet_line(
                    indent,
                    "before_planning_claim_loopx_case_todo_once",
                    True,
                ),
                _packet_line(indent, "when_task_complete_mark_case_todo_done", True),
                _packet_line(
                    indent,
                    "before_finishing_review_loopx_case_status_or_history_once",
                    True,
                ),
                _packet_line(indent, "separate_completion_file_required", False),
                _packet_line(
                    indent,
                    "host_exit_condition",
                    "confirmed_no_active_loopx_todo",
                ),
                _packet_line(
                    indent,
                    "loopx_case_cli_calls_are_part_of_the_treatment_flow",
                    True,
                ),
            ]
        )
    return "\n".join(lines), contract


def benchmark_case_active_state_seed_text(
    *,
    benchmark_name: str,
    goal_id: str,
    task_id: str,
    route: str,
    max_rounds: int,
    case_state_path: str,
) -> str:
    """Return a public-safe benchmark case active-state skeleton."""

    return (
        "---\n"
        "status: active\n"
        "owner_mode: goal\n"
        f"goal_id: {goal_id}\n"
        f"schema_version: {BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION}\n"
        "---\n\n"
        f"# {benchmark_name} Case Goal\n\n"
        "## Objective\n\n"
        f"Solve the current {benchmark_name} task inside the sandbox using local "
        "evidence and validation only.\n\n"
        "## Boundary\n\n"
        "- No uploads, leaderboard submissions, public claims, credentials, or "
        "private material.\n"
        "- Official reward, pass/fail status, verifier errors, verifier output, "
        "and verifier tails are hidden during the agent loop.\n"
        "- Maintain this active-state file as the case-local LoopX "
        "control surface.\n\n"
        "## Case Metadata\n\n"
        f"- benchmark: `{benchmark_name}`\n"
        f"- task_id: `{task_id}`\n"
        f"- route: `{route}`\n"
        f"- max_rounds: `{max_rounds}`\n"
        f"- case_state_path: `{case_state_path}`\n"
        f"- schema_version: `{BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION}`\n\n"
        "## Agent Todo\n\n"
        "- [ ] Inspect the workspace and task instruction.\n"
        "- [ ] Write a narrow plan before substantive edits.\n"
        "- [ ] Record local evidence and update todos as work progresses.\n"
        "- [ ] Run local validation before declaring done.\n\n"
        "## Done Todo\n\n"
        "- none\n\n"
        "## Local Evidence\n\n"
        "- none yet\n\n"
        "## Replan Log\n\n"
        "- none yet\n\n"
        "## Remaining Goals\n\n"
        "- inspect, implement, validate, and close out only when no open todos remain\n\n"
        "## Next Action\n\n"
        "Read the task instruction and update this active-state file before "
        "substantive edits.\n"
    )


def benchmark_case_active_state_write_command(
    *,
    case_state_path: str,
    content: str,
) -> str:
    """Return a shell command that atomically seeds the case active-state file."""

    delimiter = "__LOOPX_BENCHMARK_CASE_ACTIVE_STATE_EOF__"
    while delimiter in content:
        delimiter += "_"
    target = shlex.quote(case_state_path)
    tmp_template = shlex.quote(f"{case_state_path}.tmp.XXXXXX")
    parent = shlex.quote(posixpath.dirname(case_state_path.rstrip("/")) or "/")
    return (
        f"mkdir -p {parent} && "
        f"tmp=$(mktemp {tmp_template}) && "
        f"cat > \"$tmp\" <<'{delimiter}'\n"
        f"{content}"
        f"{delimiter}\n"
        f"mv \"$tmp\" {target} && "
        f"test -s {target}"
    )


def benchmark_case_goal_doc_text(
    *,
    benchmark_name: str,
    goal_id: str,
    task_id: str,
    route: str,
    max_rounds: int,
) -> str:
    """Return the public-safe goal doc used by official case-local LoopX."""

    return (
        f"# {benchmark_name} Case Goal\n\n"
        "Solve the current benchmark task inside the sandbox using official "
        "LoopX product-mode lifecycle evidence.\n\n"
        "## Boundary\n\n"
        "- Do not upload, submit to leaderboards, expose credentials, or record "
        "raw task text, verifier output, raw logs, screenshots, or agent "
        "trajectories in LoopX state.\n"
        "- The benchmark runner/scorer remains authoritative for official "
        "reward and pass/fail results.\n"
        "- Case-local LoopX state is only for planning, todo ownership, local "
        "evidence, validation, refresh, and quota accounting.\n\n"
        "## Case Metadata\n\n"
        f"- benchmark: `{benchmark_name}`\n"
        f"- task_id: `{task_id}`\n"
        f"- route: `{route}`\n"
        f"- goal_id: `{goal_id}`\n"
        f"- max_rounds: `{max_rounds}`\n"
    )


def _benchmark_case_write_text_command(path: str, content: str) -> str:
    delimiter = "__LOOPX_BENCHMARK_CASE_TEXT_EOF__"
    while delimiter in content:
        delimiter += "_"
    target = shlex.quote(path)
    tmp_template = shlex.quote(f"{path}.tmp.XXXXXX")
    parent = shlex.quote(posixpath.dirname(path.rstrip("/")) or "/")
    return (
        f"mkdir -p {parent} && "
        f"tmp=$(mktemp {tmp_template}) && "
        f"cat > \"$tmp\" <<'{delimiter}'\n"
        f"{content}"
        f"{delimiter}\n"
        f"mv \"$tmp\" {target} && "
        f"test -s {target}"
    )


def benchmark_case_loopx_command_prefix(
    *,
    case_cli_path: str = BENCHMARK_CASE_LOOPX_CLI_PATH,
    case_registry_path: str = BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
    case_runtime_root: str = BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
    json_output: bool = True,
) -> str:
    """Return the canonical case-local LoopX CLI prefix."""

    parts = [
        shlex.quote(case_cli_path),
        "--registry",
        shlex.quote(case_registry_path),
        "--runtime-root",
        shlex.quote(case_runtime_root),
    ]
    if json_output:
        parts.extend(["--format", "json"])
    return " ".join(parts)


def benchmark_case_loopx_install_command(
    *,
    goal_id: str,
    case_state_path: str,
    content: str,
    benchmark_id: str = "benchmark",
    case_id: str = "current-case",
    route: str = BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS,
    max_rounds: int = 0,
    case_cli_path: str = BENCHMARK_CASE_LOOPX_CLI_PATH,
    case_registry_path: str = BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
    case_runtime_root: str = BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
    case_goal_doc_path: str = BENCHMARK_CASE_LOOPX_GOAL_DOC_PATH,
    case_project_root: str = BENCHMARK_CASE_LOOPX_PROJECT_ROOT,
    case_home: str = BENCHMARK_CASE_LOOPX_HOME,
    case_loopx_source_path: str | None = None,
    case_agent_id: str = BENCHMARK_CASE_LOOPX_AGENT_ID,
    case_todo_text: str = BENCHMARK_CASE_LOOPX_TODO_TEXT,
    case_todo_id: str = BENCHMARK_CASE_LOOPX_TODO_ID,
    goal_start_product_mode: bool = False,
) -> str:
    """Return the official case-local LoopX product-mode install command.

    The command mirrors the README path: install or reuse the real ``loopx``
    CLI, bootstrap/connect a project-local registry and active state, register
    the benchmark agent, seed one open agent todo through ``loopx todo add``,
    and run a quota guard. The host may run this before the agent starts, but
    it must not claim or complete the case todo on the agent's behalf.
    """

    del content  # Official bootstrap owns the initial state body.
    cli_prefix = benchmark_case_loopx_command_prefix(
        case_cli_path=case_cli_path,
        case_registry_path=case_registry_path,
        case_runtime_root=case_runtime_root,
    )
    goal_doc = benchmark_case_goal_doc_text(
        benchmark_name=benchmark_id,
        goal_id=goal_id,
        task_id=case_id,
        route=route,
        max_rounds=max_rounds,
    )
    goal_doc_write = _benchmark_case_write_text_command(
        case_goal_doc_path,
        goal_doc,
    )
    cli_parent = shlex.quote(posixpath.dirname(case_cli_path.rstrip("/")) or "/")
    project_root = shlex.quote(case_project_root)
    home = shlex.quote(case_home)
    cli_target = shlex.quote(case_cli_path)
    source_path_value = case_loopx_source_path.rstrip("/") if case_loopx_source_path else ""
    source_path = shlex.quote(source_path_value) if source_path_value else ""
    registry_parent = shlex.quote(
        posixpath.dirname(case_registry_path.rstrip("/")) or "/"
    )
    runtime_root = shlex.quote(case_runtime_root)
    installer_url = shlex.quote(BENCHMARK_CASE_LOOPX_OFFICIAL_INSTALLER_URL)
    bootstrap_cmd = (
        f"{cli_prefix} bootstrap "
        f"--project {project_root} "
        f"--goal-id {shlex.quote(goal_id)} "
        f"--objective {shlex.quote('Solve the current benchmark case using LoopX product-mode lifecycle.')} "
        "--domain benchmark "
        f"--state-file {shlex.quote(case_state_path)} "
        f"--goal-doc {shlex.quote(case_goal_doc_path)} "
        "--adapter-kind benchmark_case_loopx_product_mode_v0 "
        "--adapter-status connected "
        "--no-onboarding-scan "
        "--force "
        "--no-global-sync"
    )
    configure_cmd = (
        f"{cli_prefix} configure-goal "
        f"--goal-id {shlex.quote(goal_id)} "
        f"--registered-agent {shlex.quote(case_agent_id)} "
        f"--primary-agent {shlex.quote(case_agent_id)} "
        "--execute"
    )
    goal_start_pack_cmd = (
        f"{cli_prefix} bootstrap-command-pack "
        f"--project {project_root} "
        f"--goal-id {shlex.quote(goal_id)} "
        f"--agent-id {shlex.quote(case_agent_id)} "
        "--host-surface shell "
        "--message-only "
        "--goal-text "
        f"{shlex.quote('Solve the current benchmark task with a compact LoopX ranked todo plan.')}"
    )
    if goal_start_product_mode:
        if len(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS) != len(
            BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS
        ):
            raise ValueError("goal-start todo text/id contract length mismatch")
        todo_specs = [
            (
                text,
                todo_id,
                "solve_benchmark_case"
                if index == 0
                else "validate_benchmark_case"
                if index == 1
                else "closeout_benchmark_case",
            )
            for index, (text, todo_id) in enumerate(
                zip(
                    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS,
                    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS,
                )
            )
        ]
    else:
        todo_specs = [(case_todo_text, case_todo_id, "solve_benchmark_case")]
    todo_add_cmds = []
    for planned_todo_text, planned_todo_id, action_kind in todo_specs:
        todo_add_cmds.append(
            f"{cli_prefix} todo add "
            f"--goal-id {shlex.quote(goal_id)} "
            "--role agent "
            f"--todo-id {shlex.quote(planned_todo_id)} "
            f"--text {shlex.quote(planned_todo_text)} "
            "--task-class advancement_task "
            f"--action-kind {shlex.quote(action_kind)}"
        )
    todo_add_cmd = "\n".join(todo_add_cmds)
    goal_start_plan_cmd = (
        "echo 'loopx_case_init_phase:goal_start_plan' >&2\n"
        f"{goal_start_pack_cmd} >/tmp/loopx_goal_start_command_pack.txt\n"
        "test -s /tmp/loopx_goal_start_command_pack.txt\n"
        if goal_start_product_mode
        else ""
    )
    quota_cmd = (
        f"{cli_prefix} quota should-run "
        f"--goal-id {shlex.quote(goal_id)} "
        f"--agent-id {shlex.quote(case_agent_id)}"
    )
    refresh_cmd = (
        f"{cli_prefix} refresh-state "
        f"--goal-id {shlex.quote(goal_id)} "
        "--classification benchmark_case_lifecycle_initialized "
        "--delivery-batch-scale single_surface "
        "--delivery-outcome surface_only "
        "--no-global-sync"
    )
    expected_todo_comment = (
        f"# expected stable case todo id: {shlex.quote(case_todo_id)}"
    )
    return (
        "set -eu\n"
        "echo 'loopx_case_init_phase:prepare_paths' >&2\n"
        f"export HOME={home}\n"
        f"export PATH={shlex.quote(posixpath.dirname(case_cli_path.rstrip('/')))}:$PATH\n"
        f"mkdir -p {cli_parent} {registry_parent} {runtime_root} {project_root}\n"
        "echo 'loopx_case_init_phase:ensure_cli' >&2\n"
        f"if [ ! -x {cli_target} ]; then\n"
        f"  if [ -n {shlex.quote(source_path_value)} ]; then\n"
        f"    if [ ! -f {source_path}/loopx/cli.py ]; then\n"
        "      echo 'LoopX local source install requested but loopx/cli.py is missing' >&2\n"
        "      exit 127\n"
        "    fi\n"
        "    if command -v python3 >/dev/null 2>&1; then\n"
        "      loopx_python=\"$(command -v python3)\"\n"
        "    elif command -v python >/dev/null 2>&1; then\n"
        "      loopx_python=\"$(command -v python)\"\n"
        "    else\n"
        "      echo 'LoopX local source install requested but python is missing' >&2\n"
        "      exit 127\n"
        "    fi\n"
        f"    cat > {cli_target} <<'LOOPX_CASE_LOOPX_SH'\n"
        "#!/bin/sh\n"
        "set -eu\n"
        f"LOOPX_RELEASE_ROOT=${{LOOPX_RELEASE_ROOT:-{source_path}}}\n"
        "LOOPX_PYTHON_BIN=${LOOPX_PYTHON:-}\n"
        "if [ -z \"$LOOPX_PYTHON_BIN\" ]; then\n"
        "  if command -v python3 >/dev/null 2>&1; then\n"
        "    LOOPX_PYTHON_BIN=\"$(command -v python3)\"\n"
        "  elif command -v python >/dev/null 2>&1; then\n"
        "    LOOPX_PYTHON_BIN=\"$(command -v python)\"\n"
        "  else\n"
        "    echo 'LoopX CLI requires python inside the benchmark sandbox' >&2\n"
        "    exit 127\n"
        "  fi\n"
        "fi\n"
        "export LOOPX_RELEASE_ROOT\n"
        "export PYTHONPATH=\"$LOOPX_RELEASE_ROOT${PYTHONPATH:+:$PYTHONPATH}\"\n"
        "exec \"$LOOPX_PYTHON_BIN\" -m loopx.cli \"$@\"\n"
        "LOOPX_CASE_LOOPX_SH\n"
        f"    chmod +x {cli_target}\n"
        "  elif command -v loopx >/dev/null 2>&1; then\n"
        f"    ln -sf \"$(command -v loopx)\" {cli_target}\n"
        "  elif command -v curl >/dev/null 2>&1; then\n"
        f"    curl -fsSL {installer_url} | HOME={home} bash\n"
        "  else\n"
        "    echo 'LoopX CLI unavailable and curl is missing for official install' >&2\n"
        "    exit 127\n"
        "  fi\n"
        "fi\n"
        f"test -x {cli_target}\n"
        "echo 'loopx_case_init_phase:write_goal_doc' >&2\n"
        f"{goal_doc_write}\n"
        f"{expected_todo_comment}\n"
        "echo 'loopx_case_init_phase:bootstrap' >&2\n"
        f"{bootstrap_cmd}\n"
        "echo 'loopx_case_init_phase:configure_goal' >&2\n"
        f"{configure_cmd}\n"
        f"{goal_start_plan_cmd}"
        "echo 'loopx_case_init_phase:todo_add' >&2\n"
        f"{todo_add_cmd}\n"
        "echo 'loopx_case_init_phase:quota_should_run' >&2\n"
        f"{quota_cmd}\n"
        "echo 'loopx_case_init_phase:refresh_state' >&2\n"
        f"{refresh_cmd}\n"
        "echo 'loopx_case_init_phase:verify_state' >&2\n"
        f"test -s {shlex.quote(case_state_path)}\n"
        "echo 'loopx_case_init_phase:grant_agent_access' >&2\n"
        "chmod -R a+rwX /app/.codex /app/.loopx /app/.local 2>/dev/null || true\n"
        "echo 'loopx_case_init_phase:complete' >&2\n"
    )


def benchmark_case_loopx_install_payload(
    *,
    benchmark_id: str,
    case_id: str,
    arm_id: str,
    route: str,
    max_rounds: int,
    case_cli_path: str = BENCHMARK_CASE_LOOPX_CLI_PATH,
    case_loopx_source_path: str | None = None,
    case_agent_id: str = BENCHMARK_CASE_LOOPX_AGENT_ID,
    case_todo_id: str = BENCHMARK_CASE_LOOPX_TODO_ID,
    goal_start_product_mode: bool = False,
) -> dict[str, object]:
    """Return the case-local GH install/state/todo launch payload."""

    contract = benchmark_case_lifecycle_contract(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arm_id=arm_id,
        max_rounds=max_rounds,
    )
    goal_id = str(contract["benchmark_case_goal_id"])
    case_state_path = str(contract["case_state_path"])
    seed = benchmark_case_active_state_seed_text(
        benchmark_name=benchmark_id,
        goal_id=goal_id,
        task_id=case_id,
        route=route,
        max_rounds=max_rounds,
        case_state_path=case_state_path,
    )
    case_rollout_event_log_path = benchmark_case_loopx_event_log_path(goal_id)
    planned_todo_texts = (
        BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS
        if goal_start_product_mode
        else (BENCHMARK_CASE_LOOPX_TODO_TEXT,)
    )
    planned_todo_ids = (
        BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS
        if goal_start_product_mode
        else (case_todo_id,)
    )
    selected_todo_id = (
        BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID
        if goal_start_product_mode
        else case_todo_id
    )
    return {
        "schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
        "install_flow_schema_version": (
            BENCHMARK_CASE_LOOPX_INSTALL_FLOW_SCHEMA_VERSION
        ),
        "lifecycle_driver_schema_version": (
            BENCHMARK_CASE_LIFECYCLE_DRIVER_SCHEMA_VERSION
        ),
        "formal_treatment_semantics": BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS,
        "canonical_product_mode_lifecycle_driver": True,
        "execution_style": BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE,
        "supported_execution_styles": list(BENCHMARK_CASE_LOOPX_EXECUTION_STYLES),
        "benchmark_case_goal_id": goal_id,
        "case_state_path": case_state_path,
        "case_registry_path": BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
        "case_runtime_root": BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
        "case_goal_doc_path": BENCHMARK_CASE_LOOPX_GOAL_DOC_PATH,
        "case_cli_path": case_cli_path,
        "case_loopx_source_path": case_loopx_source_path or "",
        "case_loopx_source_path_recorded": False,
        "case_loopx_source_install_requested": bool(case_loopx_source_path),
        "case_rollout_event_log_path": case_rollout_event_log_path,
        "case_agent_id": case_agent_id,
        "case_todo_id": selected_todo_id,
        "case_todo_text_public_safe": BENCHMARK_CASE_LOOPX_TODO_TEXT,
        "case_todo_seeded": True,
        "case_todo_preclaimed": False,
        "case_todo_seeded_by": "loopx todo add",
        "goal_start_product_mode": goal_start_product_mode,
        "goal_start_plan_observed": goal_start_product_mode,
        "planner_before_todo_write": goal_start_product_mode,
        "planned_todo_count": len(planned_todo_ids),
        "planned_todo_ids": list(planned_todo_ids),
        "planned_todo_texts_public_safe": list(planned_todo_texts),
        "planned_p0_count": 1 if goal_start_product_mode else 0,
        "same_priority_order_preserved": goal_start_product_mode,
        "selected_p0_todo_id": selected_todo_id,
        "selected_todo_claimed": False,
        "selected_todo_updated_before_solver": False,
        "selected_todo_completed_before_spend": False,
        "non_selected_todos_preserved_open_or_deferred": (
            goal_start_product_mode
        ),
        "install_flow_required": True,
        "prompt_driven_route_required": True,
        "product_path_primary_route": (
            BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE
        ),
        "host_claims_case_todo_before_agent": False,
        "agent_must_claim_selected_case_todo": True,
        "scheduler_route_supported": True,
        "scheduler_route": BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE,
        "workflow_orchestrated_route_supported": True,
        "workflow_orchestrated_route": (
            BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE
        ),
        "command": benchmark_case_loopx_install_command(
            benchmark_id=benchmark_id,
            case_id=case_id,
            route=route,
            max_rounds=max_rounds,
            goal_id=goal_id,
            case_state_path=case_state_path,
            content=seed,
            case_cli_path=case_cli_path,
            case_loopx_source_path=case_loopx_source_path,
            case_registry_path=BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
            case_runtime_root=BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
            case_goal_doc_path=BENCHMARK_CASE_LOOPX_GOAL_DOC_PATH,
            case_agent_id=case_agent_id,
            case_todo_text=BENCHMARK_CASE_LOOPX_TODO_TEXT,
            case_todo_id=selected_todo_id,
            goal_start_product_mode=goal_start_product_mode,
        ),
        "raw_task_text_required_for_init": False,
        "raw_logs_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
        "local_paths_recorded": False,
    }
