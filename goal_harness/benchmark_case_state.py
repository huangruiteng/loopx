from __future__ import annotations

import posixpath
import re
import shlex

BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION = (
    "goal_harness_benchmark_case_active_state_v1"
)
BENCHMARK_CASE_STATE_ROOT = "/app/.codex/goals"
BENCHMARK_CASE_ACTIVE_STATE_BASENAME = "ACTIVE_GOAL_STATE.md"
BENCHMARK_CASE_ACTIVE_STATE_INIT_FLOW = (
    "shared_goal_harness_benchmark_case_active_state"
)
BENCHMARK_CASE_ACTIVE_STATE_INIT_STAGE = "before_codex_worker_start"
BENCHMARK_CASE_ACTIVE_STATE_STATUS_FIELD = "case_goal_state_init_status"
BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS = (
    "case_goal_state_init_required",
    "case_goal_state_initialized_before_agent",
    "case_goal_state_init_status",
    "case_goal_state_schema_version",
    "case_goal_state_path",
)


def benchmark_case_goal_id(benchmark_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", benchmark_id.lower()).strip("-")
    return f"{slug or 'benchmark'}-case"


def benchmark_case_active_state_path(
    goal_id: str,
    *,
    root: str = BENCHMARK_CASE_STATE_ROOT,
) -> str:
    return f"{root.rstrip('/')}/{goal_id}/{BENCHMARK_CASE_ACTIVE_STATE_BASENAME}"


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
        "- Maintain this active-state file as the case-local Goal Harness "
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

    delimiter = "__GOAL_HARNESS_BENCHMARK_CASE_ACTIVE_STATE_EOF__"
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
