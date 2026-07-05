"""Shared constants for the SkillsBench automation runner."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from loopx.benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_path,
)
from loopx.benchmark_core.loop_protocol import (
    CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
    CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    CODEX_CLI_GOAL_BASELINE_ROUTE,
    LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
    LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
    LOOPX_PRODUCT_MODE_ROUTE,
    LOOPX_PROMPT_POLLING_TEST_ROUTE,
    RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLSBENCH_ROOT = REPO_ROOT / ".local/benchmark/externals/skillsbench"
PUBLIC_BENCHMARK_RUN_LEDGER = (
    REPO_ROOT
    / "docs/research/long-horizon-agent-benchmarks/benchmark-run-ledger.json"
)
DEFAULT_PRIVATE_LEDGER = (
    REPO_ROOT
    / ".local/private-benchmark-jobs"
    / "skillsbench-current-global-ledger/benchmark-run-ledger.json"
)
DEFAULT_LEDGER = DEFAULT_PRIVATE_LEDGER
DEFAULT_CURRENT_AGGREGATE_FILENAME = "current-aggregate-status.v3.json"
TERMINAL_OFFICIAL_NONPASSING_ATTRIBUTIONS = {
    "official_score_zero_case_failure",
    "official_verifier_solution_failure",
}
DEFAULT_GOAL_ID = "loopx-meta"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_TIMEOUT_SEC = 7200
DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC = 3600
DEFAULT_HOST_LOCAL_CODEX_TASK_OUTPUT_QUIET_TIMEOUT_SEC = 600
DEFAULT_APP_SERVER_GOAL_FIRST_ACTION_TIMEOUT_SEC = 3600
DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC = 900
DEFAULT_BUILD_STALL_TIMEOUT_SEC = 900
MAX_BUILD_STALL_TIMEOUT_SEC = 900
DEFAULT_VERIFIER_PREP_TIMEOUT_SEC = 120
DEFAULT_SOFT_VERIFIER_TIMEOUT_SEC = 600
DEFAULT_PRODUCT_MODE_SOFT_VERIFY_POLICY = "every-round"
DEFAULT_MAX_ROUNDS = 16
PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS = 10
RUNNER_PREREQUISITES_PUBLIC_FILENAME = "runner_prerequisites.public.json"
RUNNER_CONFIG_PUBLIC_FILENAME = "runner_config.public.json"
HOST_LOCAL_ACP_TARGET_ENV_KEYS = (
    "AI_ADDR",
    "AI_PORT",
    "GOAL_HARNESS_REMOTE_BENCH_ROOT",
    "LOOPX_SKILLSBENCH_EGRESS_PROXY",
    "LOOPX_BENCHMARK_EGRESS_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
    "LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY",
)


def _expanded_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser()


def _same_ledger_path(left: Path, right: Path) -> bool:
    return left.resolve(strict=False) == right.resolve(strict=False)


def _ledger_scope_label(primary_path: Path, global_path: Path) -> str:
    if _same_ledger_path(primary_path, global_path):
        return "global"
    return "run_group_with_global_sync"


def _inherit_global_ledger_snapshot(
    *,
    primary_path: Path,
    global_path: Path,
    dry_run: bool,
    enabled: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "skillsbench_global_ledger_inheritance_v0",
        "enabled": enabled,
        "dry_run": dry_run,
        "inherited": False,
        "markdown_inherited": False,
        "primary_ledger_path": str(primary_path),
        "global_ledger_path": str(global_path),
    }
    if not enabled:
        result["status"] = "disabled"
        return result
    if _same_ledger_path(primary_path, global_path):
        result["status"] = "same_as_global"
        return result
    if primary_path.exists():
        result["status"] = "primary_ledger_already_exists"
        return result
    if not global_path.exists():
        result["status"] = "global_ledger_missing"
        return result
    if dry_run:
        result["status"] = "would_inherit"
        result["inherited"] = True
        result["markdown_inherited"] = global_path.with_suffix(".md").exists()
        return result

    primary_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(global_path, primary_path)
    result["inherited"] = True
    global_markdown = global_path.with_suffix(".md")
    primary_markdown = primary_path.with_suffix(".md")
    if global_markdown.exists():
        shutil.copy2(global_markdown, primary_markdown)
        result["markdown_inherited"] = True
    result["status"] = "inherited"
    return result
CODEX_API_REVERSE_TUNNEL_PROXY_ENV_KEYS = (
    "LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY",
    "CODEX_API_REVERSE_TUNNEL_PROXY",
)
CODEX_API_PROXY_FORWARD_ENV_KEYS = (
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "https_proxy",
    "http_proxy",
    "all_proxy",
    "LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY",
)
CODEX_API_EGRESS_TEST_HOST = "chatgpt.com"
CODEX_API_EGRESS_TEST_PORT = 443
CODEX_API_EGRESS_MODE_CHOICES = ("auto", "reverse-tunnel", "direct")
DEFAULT_CODEX_API_EGRESS_PREFLIGHT_TIMEOUT_SEC = 8.0
BENCHMARK_EGRESS_PROXY_ENV_KEYS = (
    "LOOPX_SKILLSBENCH_EGRESS_PROXY",
    "LOOPX_BENCHMARK_EGRESS_PROXY",
)
BENCHMARK_EGRESS_PROXY_FORWARD_ENV_KEYS = (
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "https_proxy",
    "http_proxy",
    "all_proxy",
)
BENCHMARK_EGRESS_NO_PROXY_ENV_KEYS = (
    "LOOPX_SKILLSBENCH_EGRESS_NO_PROXY",
    "LOOPX_BENCHMARK_EGRESS_NO_PROXY",
)
DEFAULT_BENCHMARK_EGRESS_NO_PROXY = (
    "localhost,127.0.0.1,::1,hifis-storage.desy.de"
)
BENCHMARK_EGRESS_PROXY_MODE_CHOICES = ("auto", "off", "require")
BENCHMARK_EGRESS_TEST_HOST = "pypi.org"
BENCHMARK_EGRESS_TEST_PORT = 443
DEFAULT_BENCHMARK_EGRESS_PROXY_PREFLIGHT_TIMEOUT_SEC = 8.0
_MISSING = object()
SUPPORTED_ROUTES = (
    CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
    CODEX_CLI_GOAL_BASELINE_ROUTE,
    LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
    LOOPX_PROMPT_POLLING_TEST_ROUTE,
    RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
    LOOPX_PRODUCT_MODE_ROUTE,
    LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
    CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
)
DEFAULT_ROUTE = LOOPX_BLIND_LOOP_TREATMENT_ROUTE
CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL = "codex_acp_set_model_unsupported"
ACP_TRAJECTORY_SUMMARY_SCHEMA_VERSION = "skillsbench_acp_trajectory_summary_v0"
LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION = (
    "skillsbench_local_codex_participant_materialization_v0"
)
LOCAL_CODEX_PARTICIPANT_READY_MARKER = (
    "LOOPX_LOCAL_CODEX_PARTICIPANT_READY"
)
PRODUCT_MODE_CASE_GOAL_ID = "skillsbench-case"
PRODUCT_MODE_CASE_STATE_PATH = benchmark_case_active_state_path(
    PRODUCT_MODE_CASE_GOAL_ID
)
PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION = BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
LOOPX_PRODUCT_MODE_FAMILY_ROUTES = frozenset(
    {
        LOOPX_PRODUCT_MODE_ROUTE,
        LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
    }
)
PRODUCT_MODE_CONTROLLER_ROUTES = frozenset(
    {
        RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        *LOOPX_PRODUCT_MODE_FAMILY_ROUTES,
    }
)
