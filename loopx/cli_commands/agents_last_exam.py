from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    build_agents_last_exam_host_codex_cli_route,
    build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment,
    build_agents_last_exam_local_exact_dry_run_result,
    build_agents_last_exam_local_launch_packet,
    build_agents_last_exam_validation_run_gate,
)
from .agents_last_exam_baked_input import (
    AGENTS_LAST_EXAM_BAKED_INPUT_COMMANDS,
    handle_agents_last_exam_baked_input_command,
    register_agents_last_exam_baked_input_commands,
)
from .agents_last_exam_local_plan import (
    AGENTS_LAST_EXAM_LOCAL_PLAN_COMMANDS,
    handle_agents_last_exam_local_plan_command,
    register_agents_last_exam_local_plan_commands,
)
from .agents_last_exam_runner_source import (
    AGENTS_LAST_EXAM_RUNNER_SOURCE_COMMANDS,
    handle_agents_last_exam_runner_source_command,
    register_agents_last_exam_runner_source_commands,
)
from .agents_last_exam_task_material import (
    AGENTS_LAST_EXAM_TASK_MATERIAL_COMMANDS,
    handle_agents_last_exam_task_material_command,
    register_agents_last_exam_task_material_commands,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_COMMANDS = {
    "ale-local-launch-packet",
    "ale-local-exact-dry-run-result",
    "ale-host-codex-cli-route",
    "ale-host-codex-cua-no-task-e2e",
    "ale-validation-run-gate",
} | (
    AGENTS_LAST_EXAM_LOCAL_PLAN_COMMANDS
    | AGENTS_LAST_EXAM_RUNNER_SOURCE_COMMANDS
    | AGENTS_LAST_EXAM_TASK_MATERIAL_COMMANDS
    | AGENTS_LAST_EXAM_BAKED_INPUT_COMMANDS
)


def render_agents_last_exam_local_launch_packet_markdown(
    payload: dict[str, object],
) -> str:
    source_lock = (
        payload.get("source_lock")
        if isinstance(payload.get("source_lock"), dict)
        else {}
    )
    runner = payload.get("runner") if isinstance(payload.get("runner"), dict) else {}
    experiment_spec = (
        payload.get("experiment_spec")
        if isinstance(payload.get("experiment_spec"), dict)
        else {}
    )
    launch_packet = (
        payload.get("launch_packet")
        if isinstance(payload.get("launch_packet"), dict)
        else {}
    )
    case_state = (
        payload.get("case_state_init_contract")
        if isinstance(payload.get("case_state_init_contract"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Launch Packet",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Source head: `{source_lock.get('head')}`",
        f"- Upstream current: `{source_lock.get('head_matches_upstream')}`",
        f"- Fetch origin attempted/ok: `{source_lock.get('fetch_origin_attempted')}`/`{source_lock.get('fetch_origin_ok')}`",
        f"- Source root path recorded: `{source_lock.get('source_root_path_recorded')}`",
        f"- Runner command label: `{runner.get('command_label')}`",
        f"- Runner module available: `{runner.get('python_module_available')}`",
        f"- Experiment spec: `{experiment_spec.get('relative_path')}`",
        f"- Experiment spec exists/content read: `{experiment_spec.get('exists')}`/`{experiment_spec.get('content_read')}`",
        f"- Mode: `{launch_packet.get('mode')}`",
        f"- Will execute/start container: `{launch_packet.get('will_execute')}`/`{launch_packet.get('will_start_container')}`",
        f"- Will upload/submit: `{launch_packet.get('will_upload')}`/`{launch_packet.get('will_submit')}`",
        f"- Case state init required/path: `{case_state.get('init_required_before_worker')}`/`{case_state.get('case_state_path')}`",
        f"- Case state schema: `{case_state.get('schema_version')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_exact_dry_run_result_markdown(
    payload: dict[str, object],
) -> str:
    environment = (
        payload.get("environment")
        if isinstance(payload.get("environment"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Exact Dry-Run Result",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Exit code: `{payload.get('exit_code')}`",
        f"- Experiment: `{payload.get('experiment')}`",
        f"- Environment: `{environment.get('kind')}` / `{environment.get('route')}`",
        f"- Concurrency: `{payload.get('concurrency')}`",
        f"- Unit count declared/parsed: `{payload.get('unit_count_declared')}`/`{payload.get('unit_count_parsed')}`",
        f"- Raw stdout recorded: `{boundary.get('raw_stdout_recorded')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_host_codex_cli_route_markdown(
    payload: dict[str, object],
) -> str:
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    codex_cli = (
        payload.get("host_codex_cli")
        if isinstance(payload.get("host_codex_cli"), dict)
        else {}
    )
    host_auth = (
        payload.get("host_auth") if isinstance(payload.get("host_auth"), dict) else {}
    )
    cua_assets = (
        payload.get("cua_mcp_assets")
        if isinstance(payload.get("cua_mcp_assets"), dict)
        else {}
    )
    ale_sandbox = (
        payload.get("ale_sandbox")
        if isinstance(payload.get("ale_sandbox"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Host Codex CLI Route",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Route mode: `{route.get('mode')}`",
        f"- Host Codex binary/version: `{codex_cli.get('binary')}` / `{codex_cli.get('version')}`",
        f"- Host Codex available: `{codex_cli.get('binary_available')}`",
        f"- Host auth/config present: `{host_auth.get('auth_cache_present')}`/`{host_auth.get('config_present')}`",
        f"- Credential values recorded: `{host_auth.get('credential_values_recorded')}`",
        f"- Auth copied to sandbox: `{host_auth.get('auth_material_copied_to_sandbox')}`",
        f"- CUA MCP assets ready: `{cua_assets.get('available')}`",
        f"- ALE CUA smoke ready: `{ale_sandbox.get('cua_smoke_ready')}`",
        f"- Runs Codex in sandbox: `{route.get('runs_codex_inside_ale_sandbox')}`",
        f"- Container started/task read: `{boundary.get('container_started')}`/`{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_host_codex_cua_no_task_smoke_markdown(
    payload: dict[str, object],
) -> str:
    codex_exec = (
        payload.get("codex_exec_surface")
        if isinstance(payload.get("codex_exec_surface"), dict)
        else {}
    )
    mcp_config = (
        payload.get("codex_mcp_config")
        if isinstance(payload.get("codex_mcp_config"), dict)
        else {}
    )
    cua_bridge = (
        payload.get("cua_mcp_bridge")
        if isinstance(payload.get("cua_mcp_bridge"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Host Codex CUA No-Task E2E",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Route gate ready: `{payload.get('route_gate_ready')}`",
        f"- Codex exec surface ready: `{codex_exec.get('available')}`",
        f"- Codex MCP config ready: `{mcp_config.get('available')}`",
        f"- CUA MCP bridge ready: `{cua_bridge.get('available')}`",
        f"- Codex prompt sent: `{boundary.get('codex_prompt_sent')}`",
        f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
        f"- Raw output recorded: `{boundary.get('raw_output_recorded')}`",
        f"- Container started/task read: `{boundary.get('container_started')}`/`{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_validation_run_gate_markdown(
    payload: dict[str, object],
) -> str:
    selected_task = (
        payload.get("selected_task")
        if isinstance(payload.get("selected_task"), dict)
        else {}
    )
    readiness = (
        payload.get("readiness_inputs")
        if isinstance(payload.get("readiness_inputs"), dict)
        else {}
    )
    model_policy = (
        payload.get("model_policy")
        if isinstance(payload.get("model_policy"), dict)
        else {}
    )
    run_boundary = (
        payload.get("run_boundary")
        if isinstance(payload.get("run_boundary"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Validation Run Gate",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected task: `{selected_task.get('task_id')}`",
        f"- Task material ready: `{readiness.get('task_material_ready')}`",
        f"- Host Codex no-task E2E ready: `{readiness.get('host_codex_no_task_e2e_ready')}`",
        f"- Exact dry-run ready: `{readiness.get('exact_dry_run_ready')}`",
        f"- Launch packet ready: `{readiness.get('launch_packet_ready')}`",
        f"- Fresh source required/ready: `{readiness.get('fresh_source_required')}`/`{readiness.get('fresh_source_ready')}`",
        f"- Compact reducer ready: `{readiness.get('compact_result_reducer_ready')}`",
        f"- Connectivity model: `{model_policy.get('connectivity_e2e_model')}`",
        f"- Formal score agent/candidate: `{model_policy.get('formal_score_agent')}`/`{model_policy.get('formal_score_candidate')}`",
        f"- Task run started by gate: `{run_boundary.get('task_run_started_by_this_gate')}`",
        f"- Upload/submit eligible: `{run_boundary.get('no_upload')}`/`{run_boundary.get('submit_eligible')}`",
        f"- Raw trajectory/task body read: `{run_boundary.get('raw_trajectory_read')}`/`{run_boundary.get('task_body_read_by_loopx')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"



def register_agents_last_exam_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    register_agents_last_exam_local_plan_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_runner_source_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_baked_input_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_task_material_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )

    ale_local_launch_packet_parser = benchmark_subparsers.add_parser(
        "ale-local-launch-packet",
        help=(
            "Build a no-execution Agents' Last Exam local dry-run launch packet. "
            "This combines source, runner, Docker preflight, and experiment-spec "
            "existence gates without starting containers, reading task bodies, "
            "invoking model APIs, uploading, or submitting."
        ),
    )
    add_subcommand_format(ale_local_launch_packet_parser)
    ale_local_launch_packet_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--experiment-spec",
        required=True,
        help=(
            "Public relative path to the ALE experiment spec under source root "
            "or --experiment-spec-root."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--experiment-spec-root",
        help=(
            "Optional external spec root for LoopX wrapper specs. The "
            "path is probed for existence only and never recorded."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--expected-repo-url",
        default="https://github.com/rdi-berkeley/agents-last-exam.git",
        help="Expected public ALE repository URL.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-binary",
        default="python3",
        help="PATH-visible runner binary name to probe.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-python-module",
        default="ale_run",
        help="Python module expected to provide the ALE runner CLI.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-command-label",
        default="python-m-ale-run",
        help="Public-safe label for the configured runner command.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--operator-authorized",
        action="store_true",
        help="Mark that the operator authorized local container start for dry-run.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--allow-public-task-material",
        action="store_true",
        help="Mark that public ALE task material may be touched by a later dry-run.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--fetch-origin",
        action="store_true",
        help=(
            "Run git fetch --prune origin before launch-packet source freshness "
            "checks. No raw git output, command argv, or local paths are recorded."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--require-upstream-current",
        action="store_true",
        help="Require the ALE checkout HEAD to match upstream before the launch packet is ready.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the launch packet is ready.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help="Do not call Docker; emit a fixture-like blocked launch packet.",
    )

    ale_local_exact_dry_run_result_parser = benchmark_subparsers.add_parser(
        "ale-local-exact-dry-run-result",
        help=(
            "Reduce ALE `run --dry-run` stdout into a compact public-safe result. "
            "This reads only the provided dry-run stdout file and records labels "
            "and counts, never raw stdout, task text, paths, trajectories, "
            "screenshots, credentials, uploads, or command argv."
        ),
    )
    add_subcommand_format(ale_local_exact_dry_run_result_parser)
    ale_local_exact_dry_run_result_parser.add_argument(
        "--stdout-file",
        required=True,
        help=(
            "File containing ALE dry-run stdout to reduce. The path and raw text "
            "are not recorded."
        ),
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--exit-code",
        required=True,
        help="Exit code from the ALE dry-run command.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--expected-task-id",
        help="Optional public task id expected in the dry-run matrix.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--expected-agent-id",
        help="Optional public agent id expected in the dry-run matrix.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the compact dry-run result is ready.",
    )

    ale_host_codex_cli_route_parser = benchmark_subparsers.add_parser(
        "ale-host-codex-cli-route",
        help=(
            "Check the host Codex CLI auth route for a future Agents' Last Exam "
            "run. This verifies only compact host-side readiness signals and "
            "does not read credential values, copy auth into the sandbox, start "
            "containers, read task bodies, upload, or submit."
        ),
    )
    add_subcommand_format(ale_host_codex_cli_route_parser)
    ale_host_codex_cli_route_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="PATH-visible host Codex CLI binary name to probe. Paths are not recorded.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--assume-codex-binary-available",
        action="store_true",
        help="Fixture flag for dependency-free smokes; records no binary path.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--codex-version-text",
        help=(
            "Optional pre-probed Codex version text. If omitted, the command "
            "runs `<codex-binary> --version` without recording argv or paths."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--host-auth-cache-present",
        action="store_true",
        help=(
            "Mark that host Codex auth cache existence was verified. The value "
            "is not read or recorded."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--host-config-present",
        action="store_true",
        help=(
            "Mark that host Codex config existence was verified. The content is "
            "not read or recorded."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--require-host-config",
        action="store_true",
        help="Require host config existence in addition to host auth cache.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--cua-mcp-assets-root",
        help="Local CUA MCP server asset root to probe. The path is never recorded.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--ale-sandbox-cua-smoke-ready",
        action="store_true",
        help="Mark that the ALE DockerProvider CUA smoke is already ready.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--operator-authorized-host-codex-auth",
        action="store_true",
        help="Mark that the owner authorized using host Codex auth for this route.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the host Codex CLI route gate is ready.",
    )

    ale_host_codex_cua_no_task_e2e_parser = benchmark_subparsers.add_parser(
        "ale-host-codex-cua-no-task-e2e",
        help=(
            "Build compact no-task evidence that host Codex CLI help, Codex MCP "
            "config loading, and the CUA MCP bridge are ready. This does not "
            "send a Codex prompt, invoke a model API, read task bodies, record "
            "raw output, upload, or submit."
        ),
    )
    add_subcommand_format(ale_host_codex_cua_no_task_e2e_parser)
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="PATH-visible host Codex CLI binary name to probe. Paths are not recorded.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--assume-codex-binary-available",
        action="store_true",
        help="Fixture flag for dependency-free route-gate smokes; records no binary path.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--codex-version-text",
        help=(
            "Optional pre-probed Codex version text for the route gate. If "
            "omitted, the command runs `<codex-binary> --version` without "
            "recording argv or paths."
        ),
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--host-auth-cache-present",
        action="store_true",
        help="Mark that host Codex auth cache existence was verified without reading it.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--host-config-present",
        action="store_true",
        help="Mark that host Codex config existence was verified without reading it.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--require-host-config",
        action="store_true",
        help="Require host config existence in addition to host auth cache.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--cua-mcp-assets-root",
        required=True,
        help="Local CUA MCP server asset root to probe. The path is never recorded.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--cua-server-url",
        default="http://127.0.0.1:8000",
        help="Local CUA server URL used only inside a temporary Codex MCP config.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--install-node-deps",
        action="store_true",
        help="Allow npm install in a temporary copy of the CUA MCP assets if node_modules is absent.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--ale-sandbox-cua-smoke-ready",
        action="store_true",
        help="Mark that the ALE DockerProvider CUA smoke/e2e prerequisite is already ready.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--operator-authorized-host-codex-auth",
        action="store_true",
        help="Mark that the owner authorized using host Codex auth for this route.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the no-task host Codex CUA E2E gate is ready.",
    )

    ale_validation_run_gate_parser = benchmark_subparsers.add_parser(
        "ale-validation-run-gate",
        help=(
            "Combine compact ALE readiness artifacts into a pre-run decision "
            "for one local/no-upload validation run. This reads only compact "
            "JSON gates and does not start containers, send Codex prompts, "
            "read raw trajectories, upload, submit, or record local paths."
        ),
    )
    add_subcommand_format(ale_validation_run_gate_parser)
    ale_validation_run_gate_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--validation-hypothesis",
        required=True,
        help="Public-safe hypothesis for why this run can improve LoopX validation.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--task-material-readiness-json",
        required=True,
        help="Compact ale-task-material-readiness JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--host-codex-no-task-e2e-json",
        required=True,
        help="Compact ale-host-codex-cua-no-task-e2e JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--exact-dry-run-json",
        required=True,
        help="Compact ale-local-exact-dry-run-result JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--launch-packet-json",
        help="Optional compact ale-local-launch-packet JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--result-reducer-ready",
        action="store_true",
        help="Mark that the compact ALE result reducer is ready for post-run ingest.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--formal-score-candidate",
        action="store_true",
        help="Mark that the next run is intended as a formal score candidate.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--require-fresh-source",
        action="store_true",
        help=(
            "Require the launch packet to prove fetch-origin and upstream-current "
            "source freshness. Formal score candidates imply this requirement."
        ),
    )
    ale_validation_run_gate_parser.add_argument(
        "--expected-formal-agent",
        default="host_codex_gpt55_xhigh",
        help="Public-safe expected formal scoring agent id.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving the gate blocks submit-enabled runs.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--leaderboard-enabled",
        action="store_true",
        help="Fixture flag proving the gate blocks leaderboard-enabled runs.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the validation-run gate is ready.",
    )



def handle_agents_last_exam_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_COMMANDS:
        return None

    local_plan_result = handle_agents_last_exam_local_plan_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if local_plan_result is not None:
        return local_plan_result

    runner_source_result = handle_agents_last_exam_runner_source_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if runner_source_result is not None:
        return runner_source_result

    baked_input_result = handle_agents_last_exam_baked_input_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if baked_input_result is not None:
        return baked_input_result

    task_material_result = handle_agents_last_exam_task_material_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if task_material_result is not None:
        return task_material_result

    if args.benchmark_command == "ale-local-launch-packet":
        try:
            image_metadata = None
            alternate_image_metadata = None
            if args.no_docker_probe:
                image_metadata = {
                    "image_ref": args.image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_probe_disabled",
                }
                alternate_image_metadata = {
                    "image_ref": args.alternate_image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_probe_disabled",
                }
            payload = build_agents_last_exam_local_launch_packet(
                source_root=args.source_root,
                experiment_spec_relative_path=args.experiment_spec,
                experiment_spec_root=args.experiment_spec_root,
                selected_task_id=args.selected_task_id,
                expected_repo_url=args.expected_repo_url,
                snapshot=args.snapshot,
                image_ref=args.image,
                alternate_image_ref=args.alternate_image,
                runner_binary=args.runner_binary,
                runner_python_module=args.runner_python_module,
                runner_command_label=args.runner_command_label,
                operator_authorized=bool(args.operator_authorized),
                allow_public_task_material=bool(args.allow_public_task_material),
                fetch_origin=bool(args.fetch_origin),
                require_upstream_current=bool(args.require_upstream_current),
                image_metadata=image_metadata,
                alternate_image_metadata=alternate_image_metadata,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_launch_packet_v0",
                "error": "ale_local_launch_packet_failed",
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
                    "experiment_spec_content_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_local_launch_packet_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_launch_packet_markdown,
        )
        return 0 if payload.get("ok") else 1
    if args.benchmark_command == "ale-local-exact-dry-run-result":
        try:
            stdout_text = Path(args.stdout_file).expanduser().read_text(
                encoding="utf-8"
            )
            payload = build_agents_last_exam_local_exact_dry_run_result(
                stdout_text=stdout_text,
                exit_code=args.exit_code,
                expected_task_id=args.expected_task_id,
                expected_agent_id=args.expected_agent_id,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_exact_dry_run_result_v0",
                "error": "ale_local_exact_dry_run_result_failed",
                "error_type": type(exc).__name__,
                "read_boundary": {
                    "compact_only": True,
                    "raw_stdout_recorded": False,
                    "task_text_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_local_exact_dry_run_result_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_exact_dry_run_result_markdown,
        )
        return 0 if payload.get("ok") else 1
    if args.benchmark_command == "ale-host-codex-cli-route":
        try:
            payload = build_agents_last_exam_host_codex_cli_route(
                codex_binary=args.codex_binary,
                codex_binary_available=True
                if args.assume_codex_binary_available
                else None,
                codex_version_text=args.codex_version_text,
                host_auth_cache_present=True
                if args.host_auth_cache_present
                else None,
                host_config_present=True if args.host_config_present else None,
                require_host_config=bool(args.require_host_config),
                cua_mcp_assets_root=args.cua_mcp_assets_root,
                ale_sandbox_cua_smoke_ready=bool(
                    args.ale_sandbox_cua_smoke_ready
                ),
                operator_authorized_host_codex_auth=bool(
                    args.operator_authorized_host_codex_auth
                ),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_host_codex_cli_route_v0",
                "error": "ale_host_codex_cli_route_failed",
                "read_boundary": {
                    "compact_only": True,
                    "auth_values_read": False,
                    "config_content_read": False,
                    "task_text_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_host_codex_cli_route_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_host_codex_cli_route_markdown,
        )
        return 0 if payload.get("ok") else 1
    if args.benchmark_command == "ale-host-codex-cua-no-task-e2e":
        try:
            payload = build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
                codex_binary=args.codex_binary,
                codex_binary_available=True
                if args.assume_codex_binary_available
                else None,
                codex_version_text=args.codex_version_text,
                host_auth_cache_present=True
                if args.host_auth_cache_present
                else None,
                host_config_present=True if args.host_config_present else None,
                require_host_config=bool(args.require_host_config),
                cua_mcp_assets_root=args.cua_mcp_assets_root,
                cua_server_url=args.cua_server_url,
                install_node_deps=bool(args.install_node_deps),
                ale_sandbox_cua_smoke_ready=bool(
                    args.ale_sandbox_cua_smoke_ready
                ),
                operator_authorized_host_codex_auth=bool(
                    args.operator_authorized_host_codex_auth
                ),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_host_codex_cua_no_task_smoke_v0",
                "error": "ale_host_codex_cua_no_task_e2e_failed",
                "read_boundary": {
                    "compact_only": True,
                    "auth_values_read": False,
                    "config_content_read": False,
                    "task_text_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_host_codex_cua_no_task_e2e_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_host_codex_cua_no_task_smoke_markdown,
        )
        return 0 if payload.get("ok") else 1
    if args.benchmark_command == "ale-validation-run-gate":
        try:
            task_material_readiness = json.loads(
                Path(args.task_material_readiness_json)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            host_codex_no_task_e2e = json.loads(
                Path(args.host_codex_no_task_e2e_json)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            exact_dry_run_result = json.loads(
                Path(args.exact_dry_run_json)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            launch_packet = None
            if args.launch_packet_json:
                launch_packet = json.loads(
                    Path(args.launch_packet_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
                )
            payload = build_agents_last_exam_validation_run_gate(
                selected_task_id=args.selected_task_id,
                validation_hypothesis=args.validation_hypothesis,
                task_material_readiness=task_material_readiness,
                host_codex_no_task_e2e=host_codex_no_task_e2e,
                exact_dry_run_result=exact_dry_run_result,
                launch_packet=launch_packet,
                result_reducer_ready=bool(args.result_reducer_ready),
                submit_enabled=bool(args.submit_enabled),
                leaderboard_enabled=bool(args.leaderboard_enabled),
                formal_score_candidate=bool(args.formal_score_candidate),
                require_fresh_source=bool(args.require_fresh_source),
                expected_formal_agent=args.expected_formal_agent,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_validation_run_gate_v0",
                "error": "ale_validation_run_gate_failed",
                "error_type": type(exc).__name__,
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
                    "task_card_content_read": False,
                    "script_content_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                    "model_api_invoked": False,
                    "codex_prompt_sent": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_validation_run_gate_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_validation_run_gate_markdown,
        )
        return 0 if payload.get("ok") else 1
