from __future__ import annotations

import re

from ..benchmark_case_state import benchmark_case_active_state_path, benchmark_case_goal_id

AGENTS_LAST_EXAM_BENCHMARK_ID = "agents-last-exam"
AGENTS_LAST_EXAM_RESULT_INGEST_POLICY_VERSION = "ale-result-ingest-contract-v0"
AGENTS_LAST_EXAM_LOCAL_PREFLIGHT_SCHEMA_VERSION = (
    "agents_last_exam_local_preflight_v0"
)
AGENTS_LAST_EXAM_LOCAL_DRY_RUN_PLAN_SCHEMA_VERSION = (
    "agents_last_exam_local_dry_run_plan_v0"
)
AGENTS_LAST_EXAM_LOCAL_RUNNER_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_local_runner_readiness_v0"
)
AGENTS_LAST_EXAM_LOCAL_SOURCE_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_local_source_readiness_v0"
)
AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_task_material_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_scan_v0"
)
AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_candidate_task_data_scan_v0"
)
AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION = (
    "agents_last_exam_local_launch_packet_v0"
)
AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION = (
    "agents_last_exam_local_exact_dry_run_result_v0"
)
AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION = (
    "agents_last_exam_host_codex_cli_route_v0"
)
AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION = (
    "agents_last_exam_host_codex_cua_no_task_smoke_v0"
)
AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION = (
    "agents_last_exam_validation_run_gate_v0"
)
AGENTS_LAST_EXAM_TRACE_PUBLICNESS = (
    "compact_public_safe_no_task_body_no_trajectory_no_output"
)
AGENTS_LAST_EXAM_CASE_GOAL_ID = benchmark_case_goal_id(AGENTS_LAST_EXAM_BENCHMARK_ID)
AGENTS_LAST_EXAM_CASE_STATE_PATH = benchmark_case_active_state_path(
    AGENTS_LAST_EXAM_CASE_GOAL_ID
)
AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE = "agentslastexam/ale-kasm:latest"
AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE = "ale-ubuntu22-docker:latest"
AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT = "cpu-free-ubuntu"
AGENTS_LAST_EXAM_DEFAULT_REPO_URL = (
    "https://github.com/rdi-berkeley/agents-last-exam.git"
)
AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED = (
    "trajectory.json",
    "origin_log",
    "output",
)

_AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE = re.compile(
    r"^\s*(?:self\.)?REQUIRES_TASK_DATA\s*(?::[^=]+)?=\s*(True|False)\b"
)
