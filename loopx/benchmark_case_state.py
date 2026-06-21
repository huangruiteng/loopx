from __future__ import annotations

import posixpath
import re
import shlex

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
BENCHMARK_CASE_LOOPX_CLI_PATH = "/app/.local/bin/loopx"
BENCHMARK_CASE_LOOPX_EVENT_LOG_BASENAME = "rollout-event-log.jsonl"
BENCHMARK_CASE_LOOPX_AGENT_ID = "codex-benchmark-agent"
BENCHMARK_CASE_LOOPX_TODO_ID = "todo_benchmark_case_main"
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
    root: str = BENCHMARK_CASE_STATE_ROOT,
) -> str:
    return (
        f"{benchmark_case_loopx_case_dir(goal_id, root=root).rstrip('/')}/"
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
        "benchmark_id": benchmark_id,
        "case_id": case_id,
        "arm_id": arm_id,
        "case_isolation_scope": "per_benchmark_case_arm",
        "benchmark_case_goal_id": resolved_goal_id,
        "case_state_path": resolved_path,
        "case_state_init_required_before_worker": True,
        "source_of_truth": BENCHMARK_CASE_LIFECYCLE_SOURCE_OF_TRUTH,
        "required_lifecycle_steps": list(BENCHMARK_CASE_LIFECYCLE_STEPS),
        "required_rollout_event_kinds": list(BENCHMARK_CASE_LIFECYCLE_ROLLOUT_EVENTS),
        "max_rounds_budget": rounds,
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
        "source_of_truth",
        "max_rounds_budget",
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
    for field in ("required_lifecycle_steps", "required_rollout_event_kinds"):
        value = contract.get(field)
        if isinstance(value, list) and value:
            lines.append(f"  {field}: {','.join(str(item) for item in value)}")
    return lines


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


def benchmark_case_loopx_install_command(
    *,
    goal_id: str,
    case_state_path: str,
    content: str,
    case_cli_path: str = BENCHMARK_CASE_LOOPX_CLI_PATH,
    case_rollout_event_log_path: str | None = None,
    case_agent_id: str = BENCHMARK_CASE_LOOPX_AGENT_ID,
    case_todo_id: str = BENCHMARK_CASE_LOOPX_TODO_ID,
) -> str:
    """Return a shell command that installs the per-case GH CLI surface.

    The installed CLI is intentionally tiny and public-safe: it models the
    quota/todo/status/refresh/spend lifecycle inside the benchmark sandbox, logs
    only event kinds and ids, and never records raw task text, verifier output,
    trajectories, credentials, or host-local paths.
    """

    event_log_path = case_rollout_event_log_path or (
        benchmark_case_loopx_event_log_path(goal_id)
    )
    cli_parent = shlex.quote(posixpath.dirname(case_cli_path.rstrip("/")) or "/")
    cli_target = shlex.quote(case_cli_path)
    event_log_target = shlex.quote(event_log_path)
    case_dir = shlex.quote(posixpath.dirname(case_state_path.rstrip("/")) or "/")
    state_write = benchmark_case_active_state_write_command(
        case_state_path=case_state_path,
        content=content,
    )
    script = f"""#!/usr/bin/env sh
set -eu
GOAL_ID={shlex.quote(goal_id)}
STATE_FILE={shlex.quote(case_state_path)}
EVENT_LOG={shlex.quote(event_log_path)}
AGENT_ID={shlex.quote(case_agent_id)}
TODO_ID={shlex.quote(case_todo_id)}

record_event() {{
  kind="$1"
  mkdir -p "$(dirname "$EVENT_LOG")"
  printf '{{"schema_version":"benchmark_case_loopx_cli_event_v0","event_kind":"%s","goal_id":"%s","todo_id":"%s","agent_id":"%s","raw_logs_recorded":false,"raw_task_text_recorded":false,"raw_verifier_output_recorded":false,"raw_agent_trajectory_recorded":false,"local_paths_recorded":false}}\\n' "$kind" "$GOAL_ID" "$TODO_ID" "$AGENT_ID" >> "$EVENT_LOG"
}}

if [ "${{1:-}}" = "--format" ]; then
  shift
  [ "${{1:-}}" = "json" ] && shift || true
fi

cmd="${{1:-}}"
[ "$#" -gt 0 ] && shift || true

case "$cmd" in
  check)
    record_event check
    cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","scan_path_public":true,"raw_logs_recorded":false}}
JSON
    ;;
  status)
    record_event status
    cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","status":"active","active_state_path":"$STATE_FILE","agent_todo_summary":{{"open_count":1,"items":[{{"todo_id":"$TODO_ID","priority":"P0","status":"open","task_class":"advancement_task","claimed_by":"$AGENT_ID"}}]}},"raw_logs_recorded":false,"local_paths_recorded":false}}
JSON
    ;;
  history)
    record_event history
    cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","events_public_counts_only":true,"raw_logs_recorded":false,"raw_task_text_recorded":false}}
JSON
    ;;
  refresh-state)
    record_event refresh_state
    cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","refreshed":true,"raw_logs_recorded":false}}
JSON
    ;;
  quota)
    sub="${{1:-}}"
    [ "$#" -gt 0 ] && shift || true
    case "$sub" in
      should-run)
        record_event quota_should_run
        cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","agent_id":"$AGENT_ID","should_run":true,"decision":"run","interaction_contract":{{"user_channel":{{"action_required":false,"open_count":0}}}},"agent_lane_next_action":{{"todo_id":"$TODO_ID","priority":"P0","status":"open","task_class":"advancement_task","claimed_by":"$AGENT_ID"}},"raw_logs_recorded":false}}
JSON
        ;;
      spend-slot|spend)
        record_event quota_spend
        cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","spent":true,"raw_logs_recorded":false}}
JSON
        ;;
      *)
        echo "unsupported quota subcommand: $sub" >&2
        exit 2
        ;;
    esac
    ;;
  todo)
    sub="${{1:-}}"
    [ "$#" -gt 0 ] && shift || true
    case "$sub" in
      claim)
        record_event todo_claim
        cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","todo_id":"$TODO_ID","claimed_by":"$AGENT_ID","status":"claimed","raw_logs_recorded":false}}
JSON
        ;;
      update)
        record_event todo_update
        cat <<JSON
{{"ok":true,"goal_id":"$GOAL_ID","todo_id":"$TODO_ID","status":"updated","raw_logs_recorded":false}}
JSON
        ;;
      *)
        echo "unsupported todo subcommand: $sub" >&2
        exit 2
        ;;
    esac
    ;;
  *)
    echo "unsupported loopx case CLI command: $cmd" >&2
    exit 2
    ;;
esac
"""
    delimiter = "__LOOPX_BENCHMARK_CASE_CLI_EOF__"
    while delimiter in script:
        delimiter += "_"
    install_event = (
        '{"schema_version":"benchmark_case_loopx_cli_event_v0",'
        '"event_kind":"install","raw_logs_recorded":false,'
        '"raw_task_text_recorded":false,"raw_verifier_output_recorded":false,'
        '"raw_agent_trajectory_recorded":false,"local_paths_recorded":false}'
    )
    return (
        f"{state_write} && "
        f"mkdir -p {cli_parent} {case_dir} && "
        f"cat > {cli_target} <<'{delimiter}'\n"
        f"{script}"
        f"{delimiter}\n"
        f"chmod +x {cli_target} && "
        f": > {event_log_target} && "
        f"printf '%s\\n' {shlex.quote(install_event)} >> {event_log_target} && "
        f"test -x {cli_target} && "
        f"test -s {shlex.quote(case_state_path)}"
    )


def benchmark_case_loopx_install_payload(
    *,
    benchmark_id: str,
    case_id: str,
    arm_id: str,
    route: str,
    max_rounds: int,
    case_cli_path: str = BENCHMARK_CASE_LOOPX_CLI_PATH,
    case_agent_id: str = BENCHMARK_CASE_LOOPX_AGENT_ID,
    case_todo_id: str = BENCHMARK_CASE_LOOPX_TODO_ID,
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
    return {
        "schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
        "install_flow_schema_version": (
            BENCHMARK_CASE_LOOPX_INSTALL_FLOW_SCHEMA_VERSION
        ),
        "benchmark_case_goal_id": goal_id,
        "case_state_path": case_state_path,
        "case_cli_path": case_cli_path,
        "case_rollout_event_log_path": case_rollout_event_log_path,
        "case_agent_id": case_agent_id,
        "case_todo_id": case_todo_id,
        "case_todo_seeded": True,
        "install_flow_required": True,
        "prompt_driven_route_required": True,
        "product_path_primary_route": (
            BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE
        ),
        "scheduler_route_supported": True,
        "scheduler_route": BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE,
        "command": benchmark_case_loopx_install_command(
            goal_id=goal_id,
            case_state_path=case_state_path,
            content=seed,
            case_cli_path=case_cli_path,
            case_rollout_event_log_path=case_rollout_event_log_path,
            case_agent_id=case_agent_id,
            case_todo_id=case_todo_id,
        ),
        "raw_task_text_required_for_init": False,
        "raw_logs_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
        "local_paths_recorded": False,
    }
