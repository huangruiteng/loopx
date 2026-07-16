#!/usr/bin/env python3
"""Run one SkillsBench task through the compact SkillsBench runner bridge.

This is a thin launcher around the official SkillsBench/BenchFlow runner.  It
keeps task execution and verification inside BenchFlow, then reduces only the
official result/timing files into ``benchmark_run_v0``.

The ``codex-cli-goal-baseline`` route is the canonical Codex Goal baseline:
it drives the Codex CLI TUI slash-command surface with a real ``/goal`` command.
The comparable LoopX route is ``loopx-goal-start-product-mode``. It runs the
actual guided ``/loopx <task objective>`` contract, requires the agent-authored
plan and selected-P0 lifecycle, and records a compact control score. Historical
prompt-polling routes are intentionally not launchable because they measured an
outer prompt/controller treatment rather than the LoopX product lifecycle.

Routes that forward official verifier reward, pass/fail status, verifier
errors, or verifier output back to the agent are intentionally unsupported for
SkillsBench product-mode research. Official verifier artifacts may be reduced
into private metrics and public-safe compact counters only after the agent turn;
they must not become continuation prompts or case-local LoopX todos.

The historical ``codex-app-server-goal-baseline`` route remains in the codebase
for compatibility and reducer forensics, but it is deprecated for SkillsBench
treatment/baseline collection. Normal executions fail closed unless an explicit
legacy override flag is passed; prefer ``codex-cli-goal-baseline``.

Run from the SkillsBench checkout so BenchFlow's dependency environment is
available, for example:

    cd .local/benchmark/externals/skillsbench
    uv run python /path/to/loopx/scripts/skillsbench_automation_loop.py \
      --task-id react-performance-debugging

When invoked from the LoopX repository with a Python that cannot import
``benchflow``, the launcher re-execs itself with the SkillsBench checkout's
``.venv/bin/python`` if that environment is present.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import contextlib
import difflib
import importlib
import inspect
import json
import logging
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, get_args, get_origin
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from loopx.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LOOPX_AGENT_ID,
    BENCHMARK_CASE_LOOPX_CLI_PATH,
    BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
    BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
    BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET,
    BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE,
    BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE,
    BENCHMARK_CASE_LOOPX_TODO_ID,
    benchmark_case_loopx_command_prefix,
    benchmark_case_loopx_install_payload,
    benchmark_case_active_state_path,
    benchmark_case_active_state_seed_text,
    benchmark_case_active_state_write_command,
)
from loopx.benchmark_adapters.skillsbench import (  # noqa: E402
    apply_skillsbench_pre_agent_setup_diagnostic_attribution,
    build_skillsbench_app_server_goal_worker_contract,
    build_skillsbench_run_permission_policy,
    build_skillsbench_worker_handshake_preflight,
)
from loopx.benchmark_adapters.skillsbench_batch import (  # noqa: E402
    BatchCaseStartPacer,
    batch_case_args_to_cli as _batch_case_args_to_cli,
    batch_task_ids as _batch_task_ids,
    clone_args_for_batch_case as _clone_args_for_batch_case,
    parallel_batch_requires_subprocess_isolation as _parallel_isolation_required,
    split_task_ids_arg as _split_task_ids_arg,
)
from loopx.benchmark_adapters.skillsbench_task_source import (  # noqa: E402
    classify_missing_task_source,
)
from loopx.benchmark_adapters import (  # noqa: E402
    skillsbench_codex_runtime as codex_runtime,
    skillsbench_dockerfile_runtime as dockerfile_runtime,
    skillsbench_proxy_runtime as proxy_runtime,
    skillsbench_runner_source as runner_source,
    skillsbench_uv_cache as uv_cache,
    skillsbench_verifier_bootstrap as verifier_bootstrap,
    skillsbench_verifier_cache as verifier_cache,
)
from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER,
    SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_PROMPT,
    SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER,
    default_skillsbench_local_acp_relay_command,
    run_skillsbench_host_local_acp_transport_probe,
    run_skillsbench_local_acp_relay_probe,
)
from loopx.benchmark_adapters.skillsbench_acp_failure_policy import (  # noqa: E402
    RECOVERABLE_CODEX_TURN_FAILURE_CATEGORIES,
)
from loopx.benchmark_adapters.skillsbench_codex_goal_trace import (  # noqa: E402
    codex_cli_goal_recovery_public_fields,
    merge_codex_cli_goal_recovery_trace,
    new_codex_cli_goal_recovery_summary,
)
from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    run_skillsbench_remote_command_file_bridge_probe,
    skillsbench_remote_command_file_bridge_command_is_fixture_probe,
)
from loopx.benchmark_adapters.skillsbench_setup_preflight import (  # noqa: E402
    run_setup_only_public_preflight,
)
from loopx.benchmark_adapters.skillsbench_typed_repair import (  # noqa: E402
    advance_skillsbench_typed_repair_controller,
    begin_skillsbench_typed_repair,
    build_skillsbench_typed_repair_prompt,
    record_skillsbench_typed_repair_terminal,
    skillsbench_projected_open_todo_count,
)
from loopx.benchmark_adapters.skillsbench_turn_route import (  # noqa: E402
    SkillsBenchTurnTraceSummary,
    add_skillsbench_loopx_turn_arguments,
    skillsbench_loopx_turn_launch_error,
    skillsbench_loopx_turn_runner_prerequisites,
    sync_skillsbench_loopx_turn_trace_into_compact,
)
from loopx.benchmark_core import (  # noqa: E402
    build_benchmark_launch_observable_handle,
    canonical_lifecycle,
    compact_benchmark_canonical_lifecycle,
    read_container_file_via_compose_copy,
    run_container_command_with_exit_status,
    write_benchmark_run_observable_status,
)
from loopx.benchmark_core.loop_protocol import (  # noqa: E402
    BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
    CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    CODEX_CLI_GOAL_BASELINE_ROUTE,
    LOOPX_GOAL_START_PRODUCT_MODE_ROUTE,
    LOOPX_PRODUCT_MODE_ROUTE,
    LOOPX_TURN_AGENT_CLI_ROUTE,
    RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
    build_benchmark_loop_controller_trace,
    build_blind_loop_continuation_prompt,
    build_blind_loop_initial_prompt,
)
from loopx.benchmark_trajectory import (
    loopx_cli_state_usage,
    normalized_loopx_cli_call,
    summarize_public_acp_trajectory,
)
from loopx.control_plane.runtime.goal_start_control_score import (
    build_goal_start_product_mode_control_score,
    goal_start_public_command_records as _goal_start_public_command_records,
    goal_start_public_text_list as _goal_start_public_text_list,
    goal_start_public_todo_id_list as _goal_start_public_todo_id_list,
)


class SkillsBenchRunnerInterrupted(RuntimeError):
    """Public-safe interruption used to force compact runner closeout."""


class SkillsBenchProductModeNoLifecycleRequests(RuntimeError):
    """Product-mode agent made no required case-local LoopX lifecycle request."""


from scripts import skillsbench_runner_constants as _runner_constants

globals().update(
    {
        name: getattr(_runner_constants, name)
        for name in dir(_runner_constants)
        if not name.startswith("__")
    }
)

INDEPENDENT_GOAL_RETRY_ROUTES = {
    CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    CODEX_CLI_GOAL_BASELINE_ROUTE,
}


def _is_loopx_product_mode_route(route: str) -> bool:
    return route in LOOPX_PRODUCT_MODE_FAMILY_ROUTES


def _is_goal_start_product_mode_route(route: str) -> bool:
    return route == LOOPX_GOAL_START_PRODUCT_MODE_ROUTE


def _is_loopx_turn_agent_cli_route(route: str) -> bool:
    return route == LOOPX_TURN_AGENT_CLI_ROUTE


def _is_case_loopx_route(route: str) -> bool:
    return route in LOOPX_CASE_RUNTIME_ROUTES


def _product_mode_arm_id_for_route(route: str) -> str:
    if _is_goal_start_product_mode_route(route):
        return "loopx_goal_start_product_mode"
    return "loopx_product_mode"


def _loopx_case_arm_id_for_route(route: str) -> str:
    if _is_loopx_turn_agent_cli_route(route):
        return "loopx_turn_agent_cli"
    return _product_mode_arm_id_for_route(route)


def product_mode_soft_verify_policy_for_route(
    route: str,
    requested_policy: str,
) -> str:
    if route == LOOPX_TURN_AGENT_CLI_ROUTE:
        # Turn owns a separate public workspace validator and recovery receipt.
        # Re-running the private official verifier every round duplicates that
        # control signal and can exhaust the agent timeout before final scoring.
        return "final-only"
    if route in PRODUCT_MODE_CONTROLLER_ROUTES:
        return requested_policy
    return "every-round"


def _filter_kwargs_for_signature(
    target: Any,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Drop optional kwargs that an installed upstream callable cannot accept."""

    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return dict(kwargs)
    if any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return dict(kwargs)
    return {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }


def _tuple_annotation_arity(annotation: Any) -> int | None:
    args = get_args(annotation)
    if args and args[-1] is not Ellipsis:
        origin = get_origin(annotation)
        if origin is tuple or str(origin) in {"tuple", "<class 'tuple'>"}:
            return len(args)
    text = str(annotation)
    if "tuple[" not in text and "Tuple[" not in text:
        return None
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return None
    depth = 0
    parts: list[str] = []
    current: list[str] = []
    for char in text[start + 1 : end]:
        if char == "[":
            depth += 1
        elif char == "]" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    if parts and parts[-1] == "...":
        return None
    return len(parts)


def _benchflow_connect_acp_return_arity(target: Any) -> int:
    try:
        annotation = inspect.signature(target).return_annotation
    except (TypeError, ValueError):
        return 3
    if annotation is inspect.Signature.empty:
        return 3
    return _tuple_annotation_arity(annotation) or 3


def _benchflow_connect_as_unpack_arity(target: Any) -> int | None:
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        return None
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value.value if isinstance(node.value, ast.Await) else node.value
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        if not (isinstance(func, ast.Attribute) and func.attr == "connect_acp"):
            continue
        if not node.targets:
            continue
        target_node = node.targets[0]
        if isinstance(target_node, ast.Tuple):
            return len(target_node.elts)
    return None


def _benchflow_rollout_planes_class(module: Any) -> type[Any] | None:
    if module is None:
        return None
    direct = getattr(module, "DefaultRolloutPlanes", None)
    if isinstance(direct, type):
        return direct
    factory = getattr(module, "default_rollout_planes", None)
    if not callable(factory):
        return None
    try:
        instance = factory()
    except Exception:
        return None
    klass = instance.__class__
    return klass if isinstance(klass, type) else None


DOCKER_APP_SKILLS_MOUNT_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_APP_SKILLS_MOUNT"
DOCKER_APP_SKILLS_MOUNT_END = "# END LOOPX_SKILLSBENCH_APP_SKILLS_MOUNT"
DOCKER_APP_SKILLS_MOUNT_KEEP_FILE = "loopx_app_skills_keep"
DOCKER_APP_SKILLS_DOCKERIGNORE_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_APP_SKILLS_CONTEXT"
DOCKER_APP_SKILLS_DOCKERIGNORE_END = "# END LOOPX_SKILLSBENCH_APP_SKILLS_CONTEXT"
DOCKER_APT_RETRY_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_APT_RETRY"
DOCKER_APT_RETRY_END = "# END LOOPX_SKILLSBENCH_APT_RETRY"
DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_CODEX_ACP_RUNTIME_TOOLS"
)
DOCKER_CODEX_ACP_RUNTIME_TOOLS_END = (
    "# END LOOPX_SKILLSBENCH_CODEX_ACP_RUNTIME_TOOLS"
)
DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_LOOPX_CASE_PYTHON_RUNTIME"
)
DOCKER_LOOPX_CASE_PYTHON_RUNTIME_END = (
    "# END LOOPX_SKILLSBENCH_LOOPX_CASE_PYTHON_RUNTIME"
)
DOCKER_PIP_BOOTSTRAP_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_PIP_BOOTSTRAP"
DOCKER_PIP_BOOTSTRAP_END = "# END LOOPX_SKILLSBENCH_PIP_BOOTSTRAP"
DOCKER_GCR_MIRROR_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_GCR_MIRROR"
DOCKER_GCR_MIRROR_END = "# END LOOPX_SKILLSBENCH_GCR_MIRROR"
DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_DOCKER_BENCHMARK_EGRESS_PROXY"
)
DOCKER_BENCHMARK_EGRESS_PROXY_END = (
    "# END LOOPX_SKILLSBENCH_DOCKER_BENCHMARK_EGRESS_PROXY"
)
DOCKER_ELAN_TOOLCHAIN_RETRY_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_ELAN_TOOLCHAIN_RETRY"
)
DOCKER_ELAN_TOOLCHAIN_RETRY_END = (
    "# END LOOPX_SKILLSBENCH_ELAN_TOOLCHAIN_RETRY"
)
DOCKER_NETWORK_DOWNLOAD_RETRY_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_NETWORK_DOWNLOAD_RETRY"
)
DOCKER_NETWORK_DOWNLOAD_RETRY_END = (
    "# END LOOPX_SKILLSBENCH_NETWORK_DOWNLOAD_RETRY"
)
DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_DOCKER_UV_BOOTSTRAP_MIRROR"
)
DOCKER_UV_BOOTSTRAP_MIRROR_END = (
    "# END LOOPX_SKILLSBENCH_DOCKER_UV_BOOTSTRAP_MIRROR"
)
DOCKER_MAVEN_MIRROR_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_MAVEN_MIRROR"
DOCKER_MAVEN_MIRROR_END = "# END LOOPX_SKILLSBENCH_MAVEN_MIRROR"
DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_BASE = "https://mirrors.huaweicloud.com/apache"
DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST = "mirrors.huaweicloud.com"
DEFAULT_DOCKER_MAVEN_MIRROR_URL = "https://repo.huaweicloud.com/repository/maven"
DEFAULT_DOCKER_MAVEN_MIRROR_HOST = "repo.huaweicloud.com"
DEFAULT_DOCKER_MAVEN_SETTINGS_PATH = "/opt/loopx-maven/settings.xml"
VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_VERIFIER_BENCHMARK_EGRESS_PROXY"
)
VERIFIER_BENCHMARK_EGRESS_PROXY_END = (
    "# END LOOPX_SKILLSBENCH_VERIFIER_BENCHMARK_EGRESS_PROXY"
)
DEFAULT_VERIFIER_UV_RELEASE_MIRROR_BASE = (
    verifier_bootstrap.DEFAULT_VERIFIER_UV_RELEASE_MIRROR_BASE
)
DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST = (
    verifier_bootstrap.DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
)
VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN = (
    verifier_bootstrap.VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN
)
VERIFIER_UV_BOOTSTRAP_MIRROR_END = verifier_bootstrap.VERIFIER_UV_BOOTSTRAP_MIRROR_END
DEFAULT_DOCKER_PIP_INDEX_URL = verifier_bootstrap.DEFAULT_DOCKER_PIP_INDEX_URL
DEFAULT_DOCKER_PIP_EXTRA_INDEX_URL = (
    verifier_bootstrap.DEFAULT_DOCKER_PIP_EXTRA_INDEX_URL
)
DEFAULT_DOCKER_PIP_INDEX_HOST = "pypi.tuna.tsinghua.edu.cn"
DOCKER_HOST_CPU_ENV = "LOOPX_SKILLSBENCH_DOCKER_CPUS"
SANDBOX_PATH_RE = re.compile(r"/(?:app|root|workspace|tmp)/[A-Za-z0-9_./-]+")
LOOPX_CLI_RE = re.compile(r"(?:^|\s|/)loopx(?:\s|$)")
LOOPX_FLAG_VALUE_OPTIONS = {
    "--format",
    "--registry",
    "--runtime-root",
}
SHELL_EDIT_RE = re.compile(
    r"(?i)(?:apply_patch|perl\b.*\s-[0-9a-z]*p|sed\b.*\s-i|"
    r"python\b.*(?:write_text|open\(.+['\"]w|Path\(.+\)\.write)|"
    r"(?:^|\s)(?:tee|cat)\s*>|(?:^|\s)(?:mv|cp)\s+)"
)
PROTECTED_DIRECTIVE_RE = re.compile(
    r"(?i)(?:do\s+not|don't|must\s+not|never|禁止|不要|不得|别).{0,120}"
    r"(?:modify|edit|change|write|touch|修改|编辑|改动|写)"
)
DECLARED_DONE_MARKER = "AGENT_DECLARED_DONE_NO_REMAINING_GOALS"
PRODUCT_MODE_FINAL_CLOSEOUT_MAX_CHECKPOINTS = 3
PRODUCT_MODE_NO_OPEN_TODO_STOP_STREAK_THRESHOLD = 2
PRODUCT_MODE_HOST_LOCAL_IDLE_NO_PROGRESS_STREAK_THRESHOLD = 2
CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD = (
    "set -e; "
    "export DEBIAN_FRONTEND=noninteractive; "
    "if command -v curl >/dev/null 2>&1 && "
    "command -v tar >/dev/null 2>&1 && "
    "command -v xz >/dev/null 2>&1; then "
    "  exit 0; "
    "fi; "
    "if command -v apt-get >/dev/null 2>&1; then "
    "  apt_cache=/var/cache/apt/archives; "
    "  rm -f \"$apt_cache\"/*.deb; "
    "  mkdir -p \"$apt_cache/partial\"; "
    "  apt-get clean >/dev/null 2>&1 || true; "
    "  rm -rf /var/cache/apt/archives/*.deb /var/lib/apt/lists/*; "
    "  apt-get update -qq && "
    "  apt-get -o Dir::Cache::archives=\"$apt_cache\" "
    "install -y -qq --no-install-recommends "
    "ca-certificates curl tar xz-utils; "
    "  rm -f \"$apt_cache\"/*.deb; "
    "  rm -rf \"$apt_cache/partial\"/*; "
    "  apt-get clean >/dev/null 2>&1 || true; "
    "  rm -rf /var/cache/apt/archives/*.deb /var/lib/apt/lists/*; "
    "elif command -v apk >/dev/null 2>&1; then "
    "  apk add --no-cache ca-certificates curl tar xz; "
    "elif command -v microdnf >/dev/null 2>&1; then "
    "  (microdnf install -y ca-certificates tar xz || "
    "microdnf install -y ca-certificates tar xz-utils); "
    "  if ! command -v curl >/dev/null 2>&1; then "
    "    microdnf install -y curl-minimal || microdnf install -y curl; "
    "  fi; "
    "elif command -v dnf >/dev/null 2>&1; then "
    "  (dnf -y install ca-certificates tar xz || "
    "dnf -y install ca-certificates tar xz-utils); "
    "  if ! command -v curl >/dev/null 2>&1; then "
    "    dnf -y install curl-minimal || dnf -y install curl; "
    "  fi; "
    "elif command -v yum >/dev/null 2>&1; then "
    "  (yum install -y ca-certificates tar xz || "
    "yum install -y ca-certificates tar xz-utils); "
    "  if ! command -v curl >/dev/null 2>&1; then "
    "    yum install -y curl-minimal || yum install -y curl; "
    "  fi; "
    "else "
    "  command -v curl >/dev/null 2>&1 && "
    "  command -v tar >/dev/null 2>&1 && "
    "  command -v xz >/dev/null 2>&1; "
    "fi; "
    "command -v curl >/dev/null 2>&1 && "
    "command -v tar >/dev/null 2>&1 && "
    "command -v xz >/dev/null 2>&1"
)
CODEX_ACP_RUNTIME_DEPS_SETUP_CMD = (
    "glibc_version=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}'); "
    "if [ -n \"$glibc_version\" ] && "
    "[ \"$(printf '%s\\n' 2.34 \"$glibc_version\" | sort -V | head -n1)\" "
    "!= \"2.34\" ]; then "
    "  echo \"codex-acp runtime unsupported: glibc >=2.34 required by "
    "@zed-industries/codex-acp-linux-x64; found glibc ${glibc_version}\" >&2; "
    "  exit 127; "
    "fi; "
    "if (ldconfig -p 2>/dev/null | grep -q 'libssl.so.3') || "
    "find /lib /usr/lib /usr/local/lib -name libssl.so.3 -print -quit "
    "2>/dev/null | grep -q .; then exit 0; fi; "
    "export DEBIAN_FRONTEND=noninteractive; "
    "if command -v apt-get >/dev/null 2>&1; then "
    "  apt_cache=/var/cache/apt/archives; "
    "  rm -f \"$apt_cache\"/*.deb; "
    "  mkdir -p \"$apt_cache/partial\"; "
    "  apt-get update -qq && "
    "  (apt-get -o Dir::Cache::archives=\"$apt_cache\" "
    "install -y -qq --no-install-recommends libssl3 || "
    "apt-get -o Dir::Cache::archives=\"$apt_cache\" "
    "install -y -qq --no-install-recommends openssl); "
    "  rm -f \"$apt_cache\"/*.deb; "
    "  rm -rf \"$apt_cache/partial\"/*; "
    "  apt-get clean >/dev/null 2>&1 || true; "
    "  rm -rf /var/cache/apt/archives/*.deb /var/lib/apt/lists/*; "
    "elif command -v apk >/dev/null 2>&1; then "
    "  apk add --no-cache libssl3 || apk add --no-cache openssl; "
    "elif command -v microdnf >/dev/null 2>&1; then "
    "  microdnf install -y openssl-libs || microdnf install -y openssl; "
    "elif command -v dnf >/dev/null 2>&1; then "
    "  dnf install -y openssl-libs || dnf install -y openssl; "
    "elif command -v yum >/dev/null 2>&1; then "
    "  yum install -y openssl-libs || yum install -y openssl; "
    "else "
    "  echo 'codex-acp runtime dependency setup needs libssl.so.3 but no supported package manager was found' >&2; "
    "  exit 127; "
    "fi; "
    "(ldconfig -p 2>/dev/null | grep -q 'libssl.so.3') || "
    "find /lib /usr/lib /usr/local/lib -name libssl.so.3 -print -quit "
    "2>/dev/null | grep -q ."
)
CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_TIMEOUT_SEC = 60
BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET = "/opt/benchflow"
BENCHFLOW_AGENT_RUNTIME_CONTAINER_PATH = (
    "/opt/benchflow/bin:"
    "/opt/benchflow/js-agents/bin:"
    "/opt/benchflow/node/bin:"
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)


class SkillsBenchSetupPreflightBlocked(RuntimeError):
    """Raised when a public-safe setup preflight blocks a full case run."""


def _same_executable(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return str(left) == str(right)


def ensure_benchflow_runtime(args: argparse.Namespace) -> None:
    """Run real BenchFlow cases with the SkillsBench dependency environment."""

    if args.plan_only or args.reduce_only:
        return
    try:
        __import__("benchflow")
        return
    except ModuleNotFoundError as exc:
        if exc.name != "benchflow":
            raise

    venv_python = Path(args.skillsbench_root).expanduser() / ".venv/bin/python"
    current_python = Path(sys.executable)
    if not venv_python.exists():
        raise RuntimeError(
            "SkillsBench benchflow runtime unavailable: benchflow import failed "
            "and skillsbench-root .venv/bin/python is missing; pass "
            "--skillsbench-root pointing at a prepared SkillsBench checkout"
        ) from None
    if _same_executable(venv_python, current_python):
        raise RuntimeError(
            "SkillsBench benchflow runtime unavailable: benchflow import failed "
            "and skillsbench-root .venv/bin/python resolves to the current "
            "Python executable"
        ) from None
    os.execv(
        str(venv_python),
        [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
    )


def ensure_skillsbench_dependency_python(args: argparse.Namespace) -> None:
    """Re-exec diagnostics with the SkillsBench venv Python when available."""

    venv_python = Path(args.skillsbench_root).expanduser() / ".venv/bin/python"
    current_python = Path(sys.executable)
    if venv_python.exists() and not _same_executable(venv_python, current_python):
        os.execv(
            str(venv_python),
            [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        )
CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD = (
    f"if [ -d {shlex.quote(BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET)} ]; then "
    f"  export PATH={shlex.quote(BENCHFLOW_AGENT_RUNTIME_CONTAINER_PATH)}; "
    f"  export CODEX_ACP_RUNTIME_HOME={shlex.quote(BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET)}; "
    "fi; "
    "agent_bin=/opt/benchflow/bin/codex-acp; "
    "if [ ! -x \"$agent_bin\" ]; then "
    "  if command -v codex-acp >/dev/null 2>&1; then "
    "    agent_bin=$(command -v codex-acp); "
    "  else "
    "    echo 'codex-acp runtime launch preflight failed: "
    "benchflow wrapper missing and binary not on PATH' >&2; "
    "    exit 127; "
    "  fi; "
    "fi; "
    "if command -v timeout >/dev/null 2>&1; then "
    "  timeout 20 \"$agent_bin\" --version >/dev/null 2>&1 || "
    "  timeout 20 \"$agent_bin\" --help >/dev/null 2>&1; "
    "else "
    "  \"$agent_bin\" --version >/dev/null 2>&1 || "
    "  \"$agent_bin\" --help >/dev/null 2>&1; "
    "fi; "
    "rc=$?; "
    "if [ \"$rc\" -ne 0 ]; then "
    "  echo \"codex-acp runtime launch preflight failed: "
    "codex-acp did not start or expose --version/--help rc=${rc}\" >&2; "
    "  exit \"$rc\"; "
    "fi"
)


def _now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%Z")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _compact_size_bucket(size: int) -> str:
    if size <= 0:
        return "empty"
    if size < 200:
        return "1_199"
    if size < 1000:
        return "200_999"
    if size < 5000:
        return "1000_4999"
    return "5000_plus"


LOCAL_PROXY_ENV_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
)
LOOPBACK_PROXY_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _host_local_proxy_endpoint_probe(
    *,
    env: dict[str, str] | None = None,
    timeout_sec: float = 1.0,
) -> dict[str, Any]:
    """Probe a configured loopback proxy without recording the raw proxy URL."""

    source_env = env if env is not None else os.environ
    for key in LOCAL_PROXY_ENV_KEYS:
        raw_value = str(source_env.get(key) or "").strip()
        if not raw_value:
            continue
        parsed = urlsplit(raw_value if "://" in raw_value else f"http://{raw_value}")
        host = parsed.hostname or ""
        if host not in LOOPBACK_PROXY_HOSTS:
            return {
                "configured": True,
                "checked": False,
                "status": "non_loopback_proxy",
                "env_key": key,
                "proxy_scheme": parsed.scheme[:20],
                "raw_proxy_url_recorded": False,
            }
        if parsed.scheme in {"http", "https", "ws", "wss"}:
            default_port = 443 if parsed.scheme in {"https", "wss"} else 80
        else:
            default_port = 1080
        try:
            port = parsed.port or default_port
        except ValueError as exc:
            return {
                "configured": True,
                "checked": False,
                "status": "invalid_loopback_proxy_port",
                "env_key": key,
                "proxy_scheme": parsed.scheme[:20],
                "raw_proxy_url_recorded": False,
                "error_class": exc.__class__.__name__[:80],
            }
        result: dict[str, Any] = {
            "configured": True,
            "checked": True,
            "status": "checking",
            "env_key": key,
            "proxy_scheme": parsed.scheme[:20],
            "loopback_proxy_port": port,
            "raw_proxy_url_recorded": False,
        }
        try:
            with socket.create_connection((host, port), timeout=timeout_sec):
                result["status"] = "reachable"
                return result
        except OSError as exc:
            result["status"] = "unreachable"
            result["error_class"] = exc.__class__.__name__[:80]
            return result
    return {
        "configured": False,
        "checked": False,
        "status": "not_configured",
        "raw_proxy_url_recorded": False,
    }


def _prepend_skillsbench_site_packages(skillsbench_root: Path) -> None:
    venv = skillsbench_root.expanduser() / ".venv"
    if not venv.exists():
        return
    for candidate in sorted((venv / "lib").glob("python*/site-packages")):
        candidate_text = str(candidate)
        if candidate.exists() and candidate_text not in sys.path:
            sys.path.insert(0, candidate_text)
            return


def inspect_skillsbench_worker_handshake(
    *,
    skillsbench_root: str | Path,
    dataset: str,
    task_id: str,
    local_codex_cli_participant_ready: bool = False,
    local_acp_relay_command: str | None = None,
    probe_local_acp_relay: bool = False,
    local_acp_relay_probe_timeout_sec: float = 10.0,
    probe_host_local_acp_transport: bool = False,
    host_local_acp_transport_probe_timeout_sec: float = 10.0,
    probe_remote_command_file_bridge: bool = False,
    remote_command_file_bridge_probe_command: str | None = None,
    remote_command_file_bridge_probe_timeout_sec: float = 10.0,
    remote_executor_ready: bool = True,
    remote_task_data_ready: bool = True,
    remote_command_file_bridge_ready: bool = False,
) -> dict[str, Any]:
    """Inspect BenchFlow's worker protocol requirements without launching a task."""

    root = Path(skillsbench_root).expanduser()
    _prepend_skillsbench_site_packages(root)

    benchflow_available = False
    registry_available = False
    acp_runtime_available = False
    default_codex_agent = "codex-acp"
    codex_agent_protocol = None
    codex_agent_launch_registered = False
    local_acp_relay_probe = None
    local_acp_relay_ready = False
    host_local_acp_transport_probe = None
    host_local_acp_transport_ready = False
    remote_command_file_bridge_probe = None
    if probe_local_acp_relay:
        local_acp_relay_probe = run_skillsbench_local_acp_relay_probe(
            local_acp_relay_command,
            timeout_sec=local_acp_relay_probe_timeout_sec,
        )
        local_acp_relay_ready = local_acp_relay_probe.get("ready") is True
    if probe_host_local_acp_transport:
        host_local_acp_transport_probe = run_skillsbench_host_local_acp_transport_probe(
            local_acp_relay_command,
            skillsbench_root=root,
            timeout_sec=host_local_acp_transport_probe_timeout_sec,
        )
        host_local_acp_transport_ready = (
            host_local_acp_transport_probe.get("ready") is True
        )
    if probe_remote_command_file_bridge:
        remote_command_file_bridge_probe = (
            run_skillsbench_remote_command_file_bridge_probe(
                remote_command_file_bridge_probe_command,
                timeout_sec=remote_command_file_bridge_probe_timeout_sec,
            )
        )
        remote_command_file_bridge_ready = (
            remote_command_file_bridge_probe.get("ready") is True
        )
    try:
        __import__("benchflow")
        benchflow_available = True
    except ModuleNotFoundError:
        pass

    if benchflow_available:
        try:
            from benchflow.agents.registry import AGENTS, AGENT_ALIASES, AGENT_LAUNCH

            registry_available = True
            default_codex_agent = str(AGENT_ALIASES.get("codex", "codex-acp"))
            agent_config = AGENTS.get(default_codex_agent)
            if agent_config is not None:
                codex_agent_protocol = str(getattr(agent_config, "protocol", "") or "")
            codex_agent_launch_registered = bool(AGENT_LAUNCH.get(default_codex_agent))
        except Exception:
            pass

        try:
            from benchflow.acp.runtime import connect_acp, execute_prompts  # noqa: F401

            acp_runtime_available = True
        except Exception:
            pass

    return build_skillsbench_worker_handshake_preflight(
        dataset=dataset,
        task_id=task_id,
        benchflow_available=benchflow_available,
        benchflow_agent_registry_available=registry_available,
        benchflow_acp_runtime_available=acp_runtime_available,
        default_codex_agent=default_codex_agent,
        codex_agent_protocol=codex_agent_protocol,
        codex_agent_launch_registered=codex_agent_launch_registered,
        local_codex_cli_participant_ready=local_codex_cli_participant_ready,
        local_acp_relay_ready=local_acp_relay_ready,
        local_acp_relay_probe=local_acp_relay_probe,
        host_local_acp_transport_ready=host_local_acp_transport_ready,
        host_local_acp_transport_probe=host_local_acp_transport_probe,
        remote_command_file_bridge_ready=remote_command_file_bridge_ready,
        remote_command_file_bridge_probe=remote_command_file_bridge_probe,
        remote_executor_ready=remote_executor_ready,
        remote_task_data_ready=remote_task_data_ready,
    )


def _host_local_acp_launch_command(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> list[str]:
    if args.local_acp_relay_command:
        return shlex.split(args.local_acp_relay_command)
    command = list(default_skillsbench_local_acp_relay_command())
    if "--dry-run-response" in command:
        index = command.index("--dry-run-response")
        del command[index : index + 2]
    relay_trace_dir = str(plan.get("host_local_acp_relay_trace_dir") or "")
    if args.route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE:
        worker_trace_dir = str(plan.get("app_server_goal_worker_trace_dir") or "")
        command.extend(
            [
                "--app-server-goal-worker",
                "--approval-policy",
                "never",
                "--reasoning-effort",
                _effective_app_server_reasoning_effort(args),
                "--response-timeout-sec",
                "30",
                "--stream-heartbeat-interval-sec",
                str(args.app_server_acp_heartbeat_interval_sec),
                "--app-server-goal-followup-max",
                str(
                    max(
                        0,
                        int(getattr(args, "app_server_goal_followup_max", 0) or 0),
                    )
                ),
                "--app-server-goal-prompt-style",
                str(getattr(args, "app_server_goal_prompt_style", "bridge-only")),
            ]
        )
        if worker_trace_dir:
            command.extend(["--worker-public-trace-dir", worker_trace_dir])
    elif args.route == CODEX_CLI_GOAL_BASELINE_ROUTE:
        command.extend(["--codex-cli-goal-worker"])
        if getattr(args, "codex_cli_goal_thread_prewarm", False): command.extend(["--codex-cli-goal-thread-prewarm"])
        proxy_url, _proxy_source = _codex_api_reverse_tunnel_proxy(args)
        if (
            proxy_url
            and args.host_local_acp_launch
            and _codex_api_egress_resolved_mode(args) == "reverse-tunnel"
        ):
            command.extend(["--codex-api-proxy", proxy_url])
        if relay_trace_dir:
            command.extend(["--worker-public-trace-dir", relay_trace_dir])
    elif relay_trace_dir:
        command.extend(["--worker-public-trace-dir", relay_trace_dir])
    command.extend(
        [
            "--route",
            args.route,
            "--dataset",
            args.dataset,
            "--task-id",
            args.task_id,
            "--run-group-id",
            str(plan.get("run_group_id") or ""),
            "--job-name",
            str(plan.get("job_name") or ""),
            "--rollout-name",
            str(plan.get("rollout_name") or ""),
            "--codex-bin",
            args.local_codex_bin,
            "--sandbox",
            args.local_codex_sandbox,
            "--timeout-sec",
            str(_effective_local_codex_exec_timeout_sec(args)),
            "--first-action-timeout-sec",
            str(_effective_local_codex_first_action_timeout_sec(args)),
            "--goal-active-timeout-sec",
            str(_effective_local_codex_goal_active_timeout_sec(args)),
            "--bridge-idle-timeout-sec",
            str(_effective_local_codex_bridge_idle_timeout_sec(args)),
            "--task-output-quiet-timeout-sec",
            str(_effective_local_codex_task_output_quiet_timeout_sec(args)),
        ]
    )
    cli_reasoning_effort = _effective_codex_cli_reasoning_effort(args)
    if cli_reasoning_effort and args.route != CODEX_APP_SERVER_GOAL_BASELINE_ROUTE:
        command.extend(["--reasoning-effort", cli_reasoning_effort])
    if args.host_local_acp_launch and args.route != CODEX_APP_SERVER_GOAL_BASELINE_ROUTE:
        heartbeat_interval = min(
            max(1.0, float(args.app_server_acp_heartbeat_interval_sec)),
            15.0,
        )
        command.extend(["--stream-heartbeat-interval-sec", str(heartbeat_interval)])
    if args.model:
        command.extend(["--model", args.model])
    bridge_enabled_route = args.route in HOST_LOCAL_BRIDGE_ROUTES or (
        args.route
        in {CODEX_APP_SERVER_GOAL_BASELINE_ROUTE, CODEX_CLI_GOAL_BASELINE_ROUTE}
    )
    if (
        bridge_enabled_route
        and args.host_local_acp_launch
        and args.remote_command_file_bridge_solver_command
        and (
            args.remote_command_file_bridge_ready
            or args.remote_command_file_bridge_probe
        )
    ):
        command.extend(
            [
                "--remote-command-file-bridge-command",
                args.remote_command_file_bridge_solver_command,
                "--remote-command-file-bridge-timeout-sec",
                str(args.remote_command_file_bridge_probe_timeout_sec),
            ]
        )
        if args.remote_command_file_bridge_agent_command:
            command.extend(
                [
                    "--remote-command-file-bridge-agent-command",
                    args.remote_command_file_bridge_agent_command,
                ]
        )
        if (
            _is_loopx_product_mode_route(args.route)
            and not _is_goal_start_product_mode_route(args.route)
        ):
            payload = benchmark_case_loopx_install_payload(
                benchmark_id="skillsbench",
                case_id=args.task_id,
                arm_id=_product_mode_arm_id_for_route(args.route),
                route=args.route,
                max_rounds=args.max_rounds,
                case_loopx_source_path=_loopx_case_source_path_for_container(args),
                goal_start_product_mode=_is_goal_start_product_mode_route(args.route),
            )
            command.extend(
                [
                    "--loopx-workflow-lifecycle-checkpoint",
                    "--loopx-case-goal-id",
                    str(payload.get("benchmark_case_goal_id") or ""),
                    "--loopx-case-agent-id",
                    str(payload.get("case_agent_id") or BENCHMARK_CASE_LOOPX_AGENT_ID),
                    "--loopx-case-todo-id",
                    str(payload.get("case_todo_id") or BENCHMARK_CASE_LOOPX_TODO_ID),
                    "--loopx-case-cli-path",
                    str(payload.get("case_cli_path") or BENCHMARK_CASE_LOOPX_CLI_PATH),
                    "--loopx-case-registry-path",
                    str(
                        payload.get("case_registry_path")
                        or BENCHMARK_CASE_LOOPX_REGISTRY_PATH
                    ),
                    "--loopx-case-runtime-root",
                    str(
                        payload.get("case_runtime_root")
                        or BENCHMARK_CASE_LOOPX_RUNTIME_ROOT
                    ),
                ]
            )
    if _is_loopx_turn_agent_cli_route(args.route):
        payload = benchmark_case_loopx_install_payload(
            benchmark_id="skillsbench",
            case_id=args.task_id,
            arm_id=_loopx_case_arm_id_for_route(args.route),
            route=args.route,
            max_rounds=args.max_rounds,
            case_loopx_source_path=_loopx_case_source_path_for_container(args),
            goal_start_product_mode=False,
        )
        command.extend(
            [
                "--loopx-turn-agent-cli",
                "--loopx-case-goal-id",
                str(payload.get("benchmark_case_goal_id") or ""),
                "--loopx-case-agent-id",
                str(payload.get("case_agent_id") or BENCHMARK_CASE_LOOPX_AGENT_ID),
                "--loopx-case-todo-id",
                str(payload.get("case_todo_id") or BENCHMARK_CASE_LOOPX_TODO_ID),
                "--loopx-case-cli-path",
                str(payload.get("case_cli_path") or BENCHMARK_CASE_LOOPX_CLI_PATH),
                "--loopx-case-registry-path",
                str(
                    payload.get("case_registry_path")
                    or BENCHMARK_CASE_LOOPX_REGISTRY_PATH
                ),
                "--loopx-case-runtime-root",
                str(
                    payload.get("case_runtime_root")
                    or BENCHMARK_CASE_LOOPX_RUNTIME_ROOT
                ),
            ]
        )
        validation_command = str(
            getattr(args, "loopx_turn_validation_command", "") or ""
        ).strip()
        if validation_command:
            command.extend(
                ["--loopx-turn-validation-command", validation_command]
            )
    if (
        _is_loopx_product_mode_route(args.route)
        and not _is_goal_start_product_mode_route(args.route)
        and args.host_local_acp_launch
        and "--loopx-workflow-lifecycle-checkpoint" not in command
    ):
        payload = benchmark_case_loopx_install_payload(
            benchmark_id="skillsbench",
            case_id=args.task_id,
            arm_id=_product_mode_arm_id_for_route(args.route),
            route=args.route,
            max_rounds=args.max_rounds,
            case_loopx_source_path=_loopx_case_source_path_for_container(args),
            goal_start_product_mode=_is_goal_start_product_mode_route(args.route),
        )
        command.extend(
            [
                "--loopx-workflow-lifecycle-checkpoint",
                "--loopx-case-goal-id",
                str(payload.get("benchmark_case_goal_id") or ""),
                "--loopx-case-agent-id",
                str(payload.get("case_agent_id") or BENCHMARK_CASE_LOOPX_AGENT_ID),
                "--loopx-case-todo-id",
                str(payload.get("case_todo_id") or BENCHMARK_CASE_LOOPX_TODO_ID),
                "--loopx-case-cli-path",
                str(payload.get("case_cli_path") or BENCHMARK_CASE_LOOPX_CLI_PATH),
                "--loopx-case-registry-path",
                str(
                    payload.get("case_registry_path")
                    or BENCHMARK_CASE_LOOPX_REGISTRY_PATH
                ),
                "--loopx-case-runtime-root",
                str(
                    payload.get("case_runtime_root")
                    or BENCHMARK_CASE_LOOPX_RUNTIME_ROOT
                ),
            ]
        )
    return command


def _effective_reasoning_effort(args: argparse.Namespace) -> str:
    return str(getattr(args, "reasoning_effort", None) or "").strip()


def _effective_app_server_reasoning_effort(args: argparse.Namespace) -> str:
    return str(
        getattr(args, "reasoning_effort", None)
        or getattr(args, "app_server_reasoning_effort", None)
        or "high"
    ).strip()


def _effective_codex_cli_reasoning_effort(args: argparse.Namespace) -> str:
    return _effective_reasoning_effort(args)


def _effective_local_codex_exec_timeout_sec(args: argparse.Namespace) -> int:
    configured_raw = getattr(args, "local_codex_exec_timeout_sec", None)
    configured = max(1, int(configured_raw or DEFAULT_TIMEOUT_SEC))
    idle_timeout = max(0, int(getattr(args, "agent_idle_timeout", 0) or 0))
    if (
        configured_raw is None
        and bool(getattr(args, "host_local_acp_launch", False))
    ):
        if getattr(args, "route", "") == "codex-app-server-goal-baseline":
            outer_timeout = max(0, int(getattr(args, "outer_timeout_sec", 0) or 0))
            return max(configured, outer_timeout)
        bridge_idle_timeout = _effective_local_codex_bridge_idle_timeout_sec(args)
        if bridge_idle_timeout > 0:
            return max(
                1,
                bridge_idle_timeout + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC,
            )
    if configured_raw is None and idle_timeout > 0:
        return min(configured, idle_timeout)
    return configured


HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC = 60


def _effective_benchflow_agent_timeout_sec(args: argparse.Namespace) -> int:
    requested = max(0, int(getattr(args, "agent_idle_timeout", 0) or 0))
    if bool(getattr(args, "host_local_acp_launch", False)):
        local_exec_timeout = _effective_local_codex_exec_timeout_sec(args)
        if local_exec_timeout > 0:
            requested = max(
                requested,
                local_exec_timeout + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC,
            )
    return requested


def _effective_local_codex_bridge_idle_timeout_sec(args: argparse.Namespace) -> int:
    configured = getattr(args, "local_codex_bridge_idle_timeout_sec", None)
    if configured is not None:
        return max(0, int(configured or 0))
    if bool(getattr(args, "host_local_acp_launch", False)):
        return DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
    requested = max(0, int(getattr(args, "agent_idle_timeout", 0) or 0))
    if requested <= 0:
        return DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
    return min(requested, DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC)


def _effective_local_codex_first_action_timeout_sec(args: argparse.Namespace) -> int:
    configured = getattr(args, "local_codex_first_action_timeout_sec", None)
    if configured is not None:
        return max(0, int(configured or 0))
    if (
        bool(getattr(args, "host_local_acp_launch", False))
        and getattr(args, "route", "") == CODEX_CLI_GOAL_BASELINE_ROUTE
    ):
        idle_timeout = max(0, int(getattr(args, "agent_idle_timeout", 0) or 0))
        if idle_timeout > 0:
            return min(idle_timeout, DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC)
        return DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC
    if (
        bool(getattr(args, "host_local_acp_launch", False))
        and getattr(args, "route", "") == "codex-app-server-goal-baseline"
    ):
        idle_timeout = max(0, int(getattr(args, "agent_idle_timeout", 0) or 0))
        if idle_timeout > 0:
            return min(idle_timeout, DEFAULT_APP_SERVER_GOAL_FIRST_ACTION_TIMEOUT_SEC)
        return DEFAULT_APP_SERVER_GOAL_FIRST_ACTION_TIMEOUT_SEC
    return 0


def _effective_local_codex_goal_active_timeout_sec(args: argparse.Namespace) -> int:
    configured = getattr(args, "local_codex_goal_active_timeout_sec", None)
    if configured is not None:
        return max(0, int(configured or 0))
    if (
        bool(getattr(args, "host_local_acp_launch", False))
        and getattr(args, "route", "") == CODEX_CLI_GOAL_BASELINE_ROUTE
    ):
        return 0 if _effective_local_codex_first_action_timeout_sec(args) <= 0 else min(max(0, int(getattr(args, "agent_idle_timeout", 0) or 0)) or DEFAULT_CODEX_CLI_GOAL_ACTIVE_TIMEOUT_SEC, DEFAULT_CODEX_CLI_GOAL_ACTIVE_TIMEOUT_SEC)
    return 0


def _effective_local_codex_task_output_quiet_timeout_sec(
    args: argparse.Namespace,
) -> int:
    configured = getattr(args, "local_codex_task_output_quiet_timeout_sec", None)
    if configured is not None:
        requested = max(0, int(configured or 0))
        if requested <= 0:
            return 0
        bridge_idle_timeout = _effective_local_codex_bridge_idle_timeout_sec(args)
        if bridge_idle_timeout <= 0:
            return requested
        return min(requested, bridge_idle_timeout)
    bridge_idle_timeout = _effective_local_codex_bridge_idle_timeout_sec(args)
    if bridge_idle_timeout <= 0:
        return 0
    return min(
        DEFAULT_HOST_LOCAL_CODEX_TASK_OUTPUT_QUIET_TIMEOUT_SEC,
        bridge_idle_timeout,
    )


def _codex_api_egress_preflight_required(args: argparse.Namespace) -> bool:
    if bool(getattr(args, "setup_only_public_preflight", False)):
        return False
    if not bool(getattr(args, "host_local_acp_launch", False)):
        return False
    requested = _codex_api_egress_requested_mode(args)
    if requested in {"reverse-tunnel", "direct"}:
        return True
    return getattr(args, "route", "") in {
        "codex-app-server-goal-baseline",
        CODEX_CLI_GOAL_BASELINE_ROUTE,
    }


def _codex_api_egress_requested_mode(args: argparse.Namespace | None) -> str:
    requested = ""
    if args is not None:
        requested = str(getattr(args, "codex_api_egress_mode", "") or "")
    if requested in CODEX_API_EGRESS_MODE_CHOICES:
        return requested
    return "auto"


def _codex_api_egress_resolved_mode(args: argparse.Namespace | None) -> str:
    if args is None or not bool(getattr(args, "host_local_acp_launch", False)):
        return "not_required"
    requested = _codex_api_egress_requested_mode(args)
    if requested == "auto":
        # Formal remote Goal benchmark runs must use the reverse tunnel path by
        # default; direct egress is only for explicit local debugging.
        if getattr(args, "route", "") in {
            "codex-app-server-goal-baseline",
            CODEX_CLI_GOAL_BASELINE_ROUTE,
        }:
            return "reverse-tunnel"
        return "not_required"
    return requested


def _formal_app_server_goal_bootstrap_light_guard_required(
    args: argparse.Namespace | None,
) -> bool:
    return bool(
        args is not None
        and getattr(args, "route", "") == "codex-app-server-goal-baseline"
        and getattr(args, "host_local_acp_launch", False)
        and not getattr(args, "reduce_only", False)
        and _codex_api_egress_resolved_mode(args) == "reverse-tunnel"
    )


def _formal_app_server_goal_bootstrap_light_fail_fast_required(
    args: argparse.Namespace | None,
) -> bool:
    return bool(
        _formal_app_server_goal_bootstrap_light_guard_required(args)
        and not getattr(args, "allow_staged_bootstrap_repair_run", False)
    )


def _codex_api_reverse_tunnel_proxy(args: argparse.Namespace | None) -> tuple[str, str]:
    explicit = ""
    if args is not None:
        explicit = str(getattr(args, "codex_api_reverse_tunnel_proxy", "") or "")
    if explicit:
        return explicit, "cli"
    for key in CODEX_API_REVERSE_TUNNEL_PROXY_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value, f"env:{key}"
    return "", ""


def _benchmark_egress_proxy(args: argparse.Namespace | None) -> tuple[str, str]:
    explicit = ""
    if args is not None:
        explicit = str(getattr(args, "benchmark_egress_proxy", "") or "")
    if explicit:
        return _normalized_proxy_url(explicit), "cli"
    for key in BENCHMARK_EGRESS_PROXY_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return _normalized_proxy_url(value), f"env:{key}"
    return "", ""


def _normalized_proxy_url(proxy_url: str) -> str:
    raw = str(proxy_url or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        return raw
    return f"http://{raw}"


def _proxy_url_validation_error(proxy_url: str) -> str:
    raw = str(proxy_url or "").strip()
    if not raw:
        return ""
    if re.search(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*", raw):
        return "unexpanded_placeholder"
    if "<" in raw or ">" in raw:
        return "placeholder_marker"
    try:
        scheme, host, port = _parse_proxy_endpoint(raw)
    except Exception as exc:
        return type(exc).__name__
    if not scheme or not host or not port:
        return "missing_endpoint"
    return ""


def _merged_no_proxy(*values: str) -> str:
    entries: list[str] = []
    seen: set[str] = set()
    for value in values:
        for raw_entry in str(value or "").split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            key = entry.lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    return ",".join(entries)


def _benchmark_egress_no_proxy(args: argparse.Namespace | None) -> str:
    configured = ""
    if args is not None:
        configured = str(getattr(args, "benchmark_egress_no_proxy", "") or "")
    if not configured:
        for key in BENCHMARK_EGRESS_NO_PROXY_ENV_KEYS:
            value = os.environ.get(key)
            if value:
                configured = value
                break
    return _merged_no_proxy(DEFAULT_BENCHMARK_EGRESS_NO_PROXY, configured)


def _benchmark_egress_proxy_requested_mode(
    args: argparse.Namespace | None,
) -> str:
    requested = ""
    if args is not None:
        requested = str(getattr(args, "benchmark_egress_proxy_mode", "") or "")
    if requested in BENCHMARK_EGRESS_PROXY_MODE_CHOICES:
        if requested == "auto" and _formal_goal_benchmark_egress_proxy_required(args):
            return "require"
        return requested
    return "auto"


def _formal_goal_benchmark_egress_proxy_required(
    args: argparse.Namespace | None,
) -> bool:
    if args is None:
        return False
    if bool(getattr(args, "reduce_only", False)):
        return False
    if not bool(getattr(args, "host_local_acp_launch", False)):
        return False
    if getattr(args, "route", "") not in {
        "codex-app-server-goal-baseline",
        CODEX_CLI_GOAL_BASELINE_ROUTE,
    }:
        return False
    return _codex_api_egress_resolved_mode(args) == "reverse-tunnel"


def _proxy_host_kind(host: str) -> str:
    normalized = host.strip("[]").lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return "loopback"
    if normalized.startswith("10.") or normalized.startswith("192.168."):
        return "private"
    if normalized.startswith("172."):
        try:
            second_octet = int(normalized.split(".", 2)[1])
        except (IndexError, ValueError):
            second_octet = -1
        if 16 <= second_octet <= 31:
            return "private"
    if normalized.startswith("100."):
        try:
            second_octet = int(normalized.split(".", 2)[1])
        except (IndexError, ValueError):
            second_octet = -1
        if 64 <= second_octet <= 127:
            return "private"
    return "public_or_unknown"


def _parse_proxy_endpoint(proxy_url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlparse(proxy_url)
    scheme = (parsed.scheme or "").lower()
    host = parsed.hostname or ""
    port = int(parsed.port or (443 if scheme == "https" else 80))
    return scheme, host, port


def _public_codex_api_egress_contract(
    args: argparse.Namespace,
    *,
    status: str = "pending",
    ready: bool = False,
    error_kind: str = "",
) -> dict[str, Any]:
    proxy_url, proxy_source = _codex_api_reverse_tunnel_proxy(args)
    requested_mode = _codex_api_egress_requested_mode(args)
    resolved_mode = _codex_api_egress_resolved_mode(args)
    scheme = ""
    host = ""
    port = 0
    parse_error = ""
    if proxy_url:
        try:
            scheme, host, port = _parse_proxy_endpoint(proxy_url)
        except Exception as exc:
            parse_error = type(exc).__name__
    proxy_endpoint_kind = _proxy_host_kind(host) if host else ""
    return {
        "schema_version": "skillsbench_codex_api_egress_preflight_v0",
        "required": _codex_api_egress_preflight_required(args),
        "ready": bool(ready),
        "status": status,
        "error_kind": error_kind or parse_error,
        "requested_mode": requested_mode,
        "resolved_mode": resolved_mode,
        "reverse_tunnel_required": resolved_mode == "reverse-tunnel",
        "proxy_configured": bool(proxy_url),
        "proxy_source": proxy_source.split(":", 1)[0] if proxy_source else "",
        "proxy_env_key": proxy_source.split(":", 1)[1] if proxy_source.startswith("env:") else "",
        "proxy_scheme": scheme[:20],
        "proxy_endpoint_kind": proxy_endpoint_kind,
        "proxy_endpoint_port": port,
        "proxy_url_recorded": False,
        "raw_probe_output_recorded": False,
        "test_host": CODEX_API_EGRESS_TEST_HOST,
        "test_host_public_only": True,
    }


def _probe_http_connect_proxy(
    *,
    host: str,
    port: int,
    timeout_sec: float,
    target_host: str = CODEX_API_EGRESS_TEST_HOST,
    target_port: int = CODEX_API_EGRESS_TEST_PORT,
) -> str:
    with socket.create_connection((host, port), timeout=timeout_sec) as sock:
        sock.settimeout(timeout_sec)
        request = (
            f"CONNECT {target_host}:{target_port} "
            "HTTP/1.1\r\n"
            f"Host: {target_host}:{target_port}\r\n"
            "Proxy-Connection: close\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = sock.recv(256).decode("iso-8859-1", errors="replace")
    first_line = response.splitlines()[0] if response.splitlines() else ""
    if " 200 " in f" {first_line} ":
        return "http_connect_ready"
    if " 407 " in f" {first_line} ":
        return "proxy_auth_required"
    return "proxy_connect_rejected"


def _probe_direct_tcp_egress(
    *,
    host: str,
    port: int,
    timeout_sec: float,
) -> str:
    with socket.create_connection((host, port), timeout=timeout_sec):
        pass
    return "direct_tcp_ready"


def _run_codex_api_egress_preflight(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> dict[str, Any]:
    if not _codex_api_egress_preflight_required(args):
        contract = _public_codex_api_egress_contract(
            args,
            status="not_required",
            ready=True,
        )
        plan["codex_api_egress_preflight"] = contract
        return contract
    proxy_url, _source = _codex_api_reverse_tunnel_proxy(args)
    timeout_sec = max(
        1.0,
        float(
            getattr(
                args,
                "codex_api_egress_preflight_timeout_sec",
                DEFAULT_CODEX_API_EGRESS_PREFLIGHT_TIMEOUT_SEC,
            )
            or DEFAULT_CODEX_API_EGRESS_PREFLIGHT_TIMEOUT_SEC
        ),
    )
    status = "pending"
    error_kind = ""
    ready = False
    mode = _codex_api_egress_resolved_mode(args)
    try:
        if mode == "reverse-tunnel":
            if not proxy_url:
                status = "missing_reverse_tunnel_proxy"
                ready = False
            else:
                scheme, host, port = _parse_proxy_endpoint(proxy_url)
                if not host or not port:
                    raise ValueError("proxy endpoint missing host or port")
                if scheme == "http":
                    status = _probe_http_connect_proxy(
                        host=host,
                        port=port,
                        timeout_sec=timeout_sec,
                    )
                    ready = status == "http_connect_ready"
                else:
                    status = "unsupported_proxy_scheme"
                    ready = False
        elif mode == "direct":
            status = _probe_direct_tcp_egress(
                host=CODEX_API_EGRESS_TEST_HOST,
                port=CODEX_API_EGRESS_TEST_PORT,
                timeout_sec=timeout_sec,
            )
            ready = True
        else:
            status = "unsupported_egress_mode"
            ready = False
    except Exception as exc:
        error_kind = type(exc).__name__
        status = "failed"
        ready = False
    contract = _public_codex_api_egress_contract(
        args,
        status=status,
        ready=ready,
        error_kind=error_kind,
    )
    plan["codex_api_egress_preflight"] = contract
    prerequisites = plan.setdefault("runner_prerequisites", {})
    if isinstance(prerequisites, dict):
        _sync_codex_api_egress_contract(prerequisites, contract)
    if not ready:
        raise SkillsBenchSetupPreflightBlocked(
            "codex API egress preflight blocked: run the native app-server "
            "goal baseline with --codex-api-egress-mode reverse-tunnel and "
            "configure --codex-api-reverse-tunnel-proxy or "
            "LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY"
        )
    return contract


def _sync_codex_api_egress_contract(
    target: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    target["codex_api_egress_preflight_required"] = bool(contract.get("required"))
    target["codex_api_egress_preflight_ready"] = bool(contract.get("ready"))
    target["codex_api_egress_preflight_status"] = str(contract.get("status") or "")
    target["codex_api_egress_preflight_error_kind"] = str(
        contract.get("error_kind") or ""
    )
    target["codex_api_egress_mode_requested"] = str(
        contract.get("requested_mode") or ""
    )
    target["codex_api_egress_mode_resolved"] = str(
        contract.get("resolved_mode") or ""
    )
    target["codex_api_reverse_tunnel_required"] = bool(
        contract.get("reverse_tunnel_required")
    )
    target["codex_api_reverse_tunnel_proxy_configured"] = bool(
        contract.get("proxy_configured")
    )
    target["codex_api_reverse_tunnel_proxy_source"] = str(
        contract.get("proxy_source") or ""
    )
    target["codex_api_reverse_tunnel_proxy_scheme"] = str(
        contract.get("proxy_scheme") or ""
    )
    target["codex_api_reverse_tunnel_proxy_endpoint_kind"] = str(
        contract.get("proxy_endpoint_kind") or ""
    )
    port = contract.get("proxy_endpoint_port")
    target["codex_api_reverse_tunnel_proxy_endpoint_port"] = (
        int(port) if isinstance(port, int) and not isinstance(port, bool) else 0
    )
    target["codex_api_reverse_tunnel_proxy_url_recorded"] = False


def _public_benchmark_egress_proxy_contract(
    args: argparse.Namespace,
    *,
    status: str = "pending",
    ready: bool = False,
    error_kind: str = "",
) -> dict[str, Any]:
    proxy_mode = _benchmark_egress_proxy_requested_mode(args)
    proxy_url = ""
    proxy_source = ""
    if proxy_mode != "off":
        proxy_url, proxy_source = _benchmark_egress_proxy(args)
    validation_error = _proxy_url_validation_error(proxy_url)
    scheme = ""
    host = ""
    port = 0
    parse_error = ""
    if proxy_url and not validation_error:
        try:
            scheme, host, port = _parse_proxy_endpoint(proxy_url)
        except Exception as exc:
            parse_error = type(exc).__name__
    no_proxy = _benchmark_egress_no_proxy(args) if proxy_mode != "off" else ""
    no_proxy_entry_count = (
        len([entry for entry in no_proxy.split(",") if entry.strip()])
        if no_proxy
        else 0
    )
    configured = bool(proxy_url and not validation_error)
    if status == "pending":
        if proxy_mode == "off":
            status = "disabled"
            ready = True
        elif validation_error:
            status = "invalid_proxy_value"
            ready = proxy_mode == "auto"
        elif not configured and proxy_mode == "auto":
            status = "not_configured"
            ready = True
        elif not configured:
            status = "missing_required_proxy"
            ready = False
    return {
        "schema_version": "skillsbench_benchmark_egress_proxy_v0",
        "requested_mode": proxy_mode,
        "effective_mode": (
            "direct"
            if status
            in {
                "direct_tcp_ready_after_proxy_failure",
                "direct_tcp_ready_after_invalid_proxy",
            }
            or (status == "invalid_proxy_value" and proxy_mode == "auto")
            else ("proxy" if ready and configured and proxy_mode != "off" else proxy_mode)
        ),
        "ready": bool(ready),
        "status": status,
        "error_kind": error_kind or validation_error or parse_error,
        "proxy_configured": configured,
        "proxy_value_valid": not bool(validation_error),
        "proxy_invalid_reason": validation_error[:80],
        "proxy_required": proxy_mode == "require",
        "proxy_source": (
            proxy_source.split(":", 1)[0] if proxy_source else ""
        ),
        "proxy_env_key": (
            proxy_source.split(":", 1)[1]
            if proxy_source.startswith("env:")
            else ""
        ),
        "proxy_scheme": scheme[:20],
        "proxy_endpoint_kind": _proxy_host_kind(host) if host else "",
        "proxy_endpoint_port": port,
        "no_proxy_configured": bool(no_proxy),
        "no_proxy_entry_count": no_proxy_entry_count,
        "no_proxy_raw_value_recorded": False,
        "proxy_url_recorded": False,
        "raw_proxy_url_recorded": False,
        "raw_probe_output_recorded": False,
        "direct_fallback_allowed": proxy_mode == "auto",
        "direct_fallback_active": status
        in {
            "direct_tcp_ready_after_proxy_failure",
            "direct_tcp_ready_after_invalid_proxy",
        },
        "test_host": BENCHMARK_EGRESS_TEST_HOST,
        "test_host_public_only": True,
    }


def _run_benchmark_egress_proxy_preflight(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> dict[str, Any]:
    proxy_mode = _benchmark_egress_proxy_requested_mode(args)
    proxy_url, _source = _benchmark_egress_proxy(args)
    timeout_sec = max(
        1.0,
        float(
            getattr(
                args,
                "benchmark_egress_proxy_preflight_timeout_sec",
                DEFAULT_BENCHMARK_EGRESS_PROXY_PREFLIGHT_TIMEOUT_SEC,
            )
            or DEFAULT_BENCHMARK_EGRESS_PROXY_PREFLIGHT_TIMEOUT_SEC
        ),
    )
    status = "pending"
    ready = False
    error_kind = ""
    direct_fallback_active = False
    try:
        if proxy_mode == "off":
            status = "disabled"
            ready = True
        elif not proxy_url:
            status = (
                "not_configured"
                if proxy_mode == "auto"
                else "missing_required_proxy"
            )
            ready = proxy_mode == "auto"
        else:
            validation_error = _proxy_url_validation_error(proxy_url)
            if validation_error:
                error_kind = validation_error
                if proxy_mode == "auto":
                    fallback_status = _probe_direct_tcp_egress(
                        host=BENCHMARK_EGRESS_TEST_HOST,
                        port=BENCHMARK_EGRESS_TEST_PORT,
                        timeout_sec=timeout_sec,
                    )
                    if fallback_status == "direct_tcp_ready":
                        status = "direct_tcp_ready_after_invalid_proxy"
                        ready = True
                        direct_fallback_active = True
                    else:
                        status = "invalid_proxy_value"
                        ready = False
                else:
                    status = "invalid_proxy_value"
                    ready = False
            else:
                scheme, host, port = _parse_proxy_endpoint(proxy_url)
                if not host or not port:
                    raise ValueError("proxy endpoint missing host or port")
                if scheme != "http":
                    status = "unsupported_proxy_scheme"
                    ready = False
                else:
                    status = _probe_http_connect_proxy(
                        host=host,
                        port=port,
                        timeout_sec=timeout_sec,
                        target_host=BENCHMARK_EGRESS_TEST_HOST,
                        target_port=BENCHMARK_EGRESS_TEST_PORT,
                    )
                    ready = status == "http_connect_ready"
                    if not ready and proxy_mode == "auto":
                        fallback_status = _probe_direct_tcp_egress(
                            host=BENCHMARK_EGRESS_TEST_HOST,
                            port=BENCHMARK_EGRESS_TEST_PORT,
                            timeout_sec=timeout_sec,
                        )
                        if fallback_status == "direct_tcp_ready":
                            status = "direct_tcp_ready_after_proxy_failure"
                            ready = True
                            direct_fallback_active = True
    except Exception as exc:
        status = "failed"
        ready = False
        error_kind = type(exc).__name__
        if proxy_mode == "auto":
            try:
                fallback_status = _probe_direct_tcp_egress(
                    host=BENCHMARK_EGRESS_TEST_HOST,
                    port=BENCHMARK_EGRESS_TEST_PORT,
                    timeout_sec=timeout_sec,
                )
                if fallback_status == "direct_tcp_ready":
                    status = "direct_tcp_ready_after_proxy_failure"
                    ready = True
                    direct_fallback_active = True
            except Exception:
                pass
    setattr(
        args,
        "_benchmark_egress_proxy_direct_fallback_active",
        direct_fallback_active,
    )
    contract = _public_benchmark_egress_proxy_contract(
        args,
        status=status,
        ready=ready,
        error_kind=error_kind,
    )
    plan["benchmark_egress_proxy"] = contract
    prerequisites = plan.setdefault("runner_prerequisites", {})
    if isinstance(prerequisites, dict):
        _sync_benchmark_egress_proxy_contract(prerequisites, contract)
    if not ready:
        raise SkillsBenchSetupPreflightBlocked(
            "benchmark egress proxy preflight blocked: configure a valid "
            "private proxy in LOOPX_SKILLSBENCH_EGRESS_PROXY or run with "
            "--benchmark-egress-proxy-mode off for explicit no-proxy runs"
        )
    return contract


def _sync_benchmark_egress_proxy_contract(
    target: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    target["benchmark_egress_proxy_ready"] = bool(contract.get("ready"))
    target["benchmark_egress_proxy_configured"] = bool(
        contract.get("proxy_configured")
    )
    target["benchmark_egress_proxy_value_valid"] = bool(
        contract.get("proxy_value_valid")
    )
    target["benchmark_egress_proxy_invalid_reason"] = str(
        contract.get("proxy_invalid_reason") or ""
    )
    target["benchmark_egress_proxy_required"] = bool(contract.get("proxy_required"))
    target["benchmark_egress_proxy_url_recorded"] = False
    target["benchmark_egress_proxy_status"] = str(contract.get("status") or "")
    target["benchmark_egress_proxy_error_kind"] = str(
        contract.get("error_kind") or ""
    )
    target["benchmark_egress_proxy_mode_requested"] = str(
        contract.get("requested_mode") or ""
    )
    target["benchmark_egress_proxy_mode_effective"] = str(
        contract.get("effective_mode") or ""
    )
    target["benchmark_egress_direct_fallback_allowed"] = bool(
        contract.get("direct_fallback_allowed")
    )
    target["benchmark_egress_direct_fallback_active"] = bool(
        contract.get("direct_fallback_active")
    )
    target["benchmark_egress_proxy_source"] = str(
        contract.get("proxy_source") or ""
    )
    target["benchmark_egress_proxy_env_key"] = str(
        contract.get("proxy_env_key") or ""
    )
    target["benchmark_egress_proxy_scheme"] = str(
        contract.get("proxy_scheme") or ""
    )
    target["benchmark_egress_proxy_endpoint_kind"] = str(
        contract.get("proxy_endpoint_kind") or ""
    )
    port = contract.get("proxy_endpoint_port")
    target["benchmark_egress_proxy_endpoint_port"] = (
        int(port) if isinstance(port, int) and not isinstance(port, bool) else 0
    )
    target["benchmark_egress_no_proxy_configured"] = bool(
        contract.get("no_proxy_configured")
    )
    entry_count = contract.get("no_proxy_entry_count")
    target["benchmark_egress_no_proxy_entry_count"] = (
        int(entry_count)
        if isinstance(entry_count, int) and not isinstance(entry_count, bool)
        else 0
    )
    target["benchmark_egress_no_proxy_raw_value_recorded"] = False
    target.setdefault("benchmark_egress_proxy_docker_config_injected", False)
    target.setdefault("benchmark_egress_proxy_docker_config_path_recorded", False)
    target.setdefault("benchmark_egress_proxy_docker_config_raw_proxy_recorded", False)


def _benchmark_egress_proxy_env(args: argparse.Namespace | None) -> dict[str, str]:
    if args is None or _benchmark_egress_proxy_requested_mode(args) == "off":
        return {}
    if getattr(args, "_benchmark_egress_proxy_direct_fallback_active", False):
        return {}
    proxy_url, _source = _benchmark_egress_proxy(args)
    if not proxy_url:
        return {}
    if _proxy_url_validation_error(proxy_url):
        return {}
    env = {key: proxy_url for key in BENCHMARK_EGRESS_PROXY_FORWARD_ENV_KEYS}
    env["LOOPX_SKILLSBENCH_EGRESS_PROXY"] = proxy_url
    no_proxy = _benchmark_egress_no_proxy(args)
    env["NO_PROXY"] = no_proxy
    env["no_proxy"] = no_proxy
    return env


@contextlib.contextmanager
def _benchmark_egress_proxy_env_applied(
    args: argparse.Namespace, *, plan: dict[str, Any] | None = None,
) -> Any:
    with proxy_runtime.proxy_runtime_env_applied(
        _benchmark_egress_proxy_env(args), plan=plan
    ):
        yield


def _host_local_acp_target_env(
    agent_env: object,
    *,
    args: argparse.Namespace | None = None,
) -> dict[str, str]:
    if not isinstance(agent_env, dict):
        agent_env = {}
    target_env: dict[str, str] = {}
    for key in HOST_LOCAL_ACP_TARGET_ENV_KEYS:
        value = agent_env.get(key)
        if value is None:
            continue
        target_env[key] = str(value)
    proxy_url, _proxy_source = _codex_api_reverse_tunnel_proxy(args)
    if (
        proxy_url
        and args is not None
        and _codex_api_egress_resolved_mode(args) == "reverse-tunnel"
    ):
        for key in CODEX_API_PROXY_FORWARD_ENV_KEYS:
            target_env[key] = proxy_url
        target_env.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
        target_env.setdefault("no_proxy", "localhost,127.0.0.1,::1")
    for key, value in _benchmark_egress_proxy_env(args).items():
        target_env.setdefault(key, value)
    return target_env


def _replace_option_value(command: list[str], option: str, value: str) -> list[str]:
    updated = list(command)
    for index, item in enumerate(updated[:-1]):
        if item == option:
            updated[index + 1] = value
    return updated


def _set_option_value(command: list[str], option: str, value: str) -> list[str]:
    updated = _replace_option_value(command, option, value)
    if option in updated:
        return updated
    return [*updated, option, value]


def _host_local_acp_docker_bridge_command(
    env: Any,
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> str | None:
    compose_paths = getattr(env, "_docker_compose_paths", None)
    environment_dir = getattr(env, "environment_dir", None)
    session_id = getattr(env, "session_id", None)
    if not compose_paths or environment_dir is None or not isinstance(session_id, str):
        return None

    try:
        project_dir = str(Path(environment_dir).resolve().absolute())
        compose_files = [str(Path(path).resolve().absolute()) for path in compose_paths]
    except (TypeError, OSError):
        return None
    if not compose_files:
        return None

    project_name = session_id.lower().replace(".", "-")
    prerequisites = plan.setdefault("runner_prerequisites", {})
    prerequisites["host_local_acp_sandbox_bridge_configured"] = True
    prerequisites["host_local_acp_sandbox_bridge_mode"] = "docker_compose"
    prerequisites["host_local_acp_sandbox_bridge_compose_file_count"] = len(
        compose_files
    )
    prerequisites["host_local_acp_sandbox_bridge_path_recorded"] = False
    bridge_script = Path(args.loopx_source_dir or REPO_ROOT) / "scripts" / (
        "skillsbench_docker_command_file_bridge.py"
    )
    command = [sys.executable, str(bridge_script)]
    command.extend(["--project-name", project_name])
    command.extend(["--project-dir", project_dir])
    for compose_file in compose_files:
        command.extend(["--compose-file", compose_file])
    command.extend(["--service", "main"])
    return shlex.join(command)


def _host_local_acp_codex_exec_preflight_command(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> list[str]:
    local_acp_relay_command = getattr(args, "local_acp_relay_command", None)
    if local_acp_relay_command:
        command = shlex.split(str(local_acp_relay_command))
    else:
        command = list(default_skillsbench_local_acp_relay_command())
    if "--dry-run-response" in command:
        index = command.index("--dry-run-response")
        del command[index : index + 2]
    command.extend(
        [
            "--route",
            args.route,
            "--dataset",
            args.dataset,
            "--task-id",
            args.task_id,
            "--codex-bin",
            args.local_codex_bin,
            "--sandbox",
            args.local_codex_sandbox,
            "--timeout-sec",
            str(max(1, int(args.host_local_acp_codex_exec_preflight_timeout_sec))),
        ]
    )
    if args.model:
        command.extend(["--model", args.model])
    cli_reasoning_effort = _effective_codex_cli_reasoning_effort(args)
    if cli_reasoning_effort and args.route != "codex-app-server-goal-baseline":
        command.extend(["--reasoning-effort", cli_reasoning_effort])
    relay_trace_dir = str(plan.get("host_local_acp_relay_trace_dir") or "")
    if relay_trace_dir:
        command.extend(
            [
                "--worker-public-trace-dir",
                str(Path(relay_trace_dir) / "codex-exec-preflight"),
            ]
        )
    if _host_local_acp_codex_exec_preflight_requires_bridge_action(args):
        command.extend(
            [
                "--remote-command-file-bridge-command",
                str(getattr(args, "remote_command_file_bridge_solver_command") or ""),
                "--remote-command-file-bridge-timeout-sec",
                str(
                    max(
                        1.0,
                        float(
                            getattr(
                                args,
                                "remote_command_file_bridge_probe_timeout_sec",
                                10.0,
                            )
                            or 10.0
                        ),
                    )
                ),
                "--first-action-timeout-sec",
                str(_host_local_acp_codex_exec_preflight_first_action_timeout(args)),
            ]
        )
        agent_command = str(
            getattr(args, "remote_command_file_bridge_agent_command", None) or ""
        )
        if agent_command:
            command.extend(["--remote-command-file-bridge-agent-command", agent_command])
    return command


def _host_local_acp_codex_exec_preflight_should_run(
    args: argparse.Namespace,
) -> bool:
    """Return whether the host-local Codex exec path must be probed first."""

    if bool(getattr(args, "setup_only_public_preflight", False)):
        return False
    route = str(getattr(args, "route", "") or "")
    if bool(getattr(args, "host_local_acp_launch", False)) and route in {
        CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
        CODEX_CLI_GOAL_BASELINE_ROUTE,
    }:
        return False
    if bool(getattr(args, "host_local_acp_codex_exec_preflight", False)):
        return True
    return bool(
        getattr(args, "host_local_acp_launch", False)
        and _is_goal_start_product_mode_route(str(getattr(args, "route", "") or ""))
        and str(getattr(args, "remote_command_file_bridge_solver_command", "") or "")
    )


def _host_local_acp_codex_exec_preflight_requires_bridge_action(
    args: argparse.Namespace,
) -> bool:
    return bool(
        getattr(args, "host_local_acp_launch", False)
        and str(getattr(args, "route", "") or "")
        in HOST_LOCAL_BRIDGE_ROUTES
        and str(getattr(args, "remote_command_file_bridge_solver_command", "") or "")
        and (
            bool(getattr(args, "remote_command_file_bridge_ready", False))
            or bool(getattr(args, "remote_command_file_bridge_probe", False))
        )
    )


def _host_local_acp_codex_exec_preflight_first_action_timeout(
    args: argparse.Namespace,
) -> int:
    preflight_timeout = max(
        1,
        int(float(getattr(args, "host_local_acp_codex_exec_preflight_timeout_sec", 30))),
    )
    configured = max(
        0,
        int(float(getattr(args, "local_codex_first_action_timeout_sec", 0) or 0)),
    )
    if configured and configured < 30:
        return max(1, min(preflight_timeout, configured))
    return max(1, min(preflight_timeout, 90))


def _summarize_host_local_acp_preflight_bridge_trace(
    trace_dir: Path | None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "trace_present": False,
        "trace_count": 0,
        "request_count": 0,
        "preflight_operation_count": 0,
        "task_facing_operation_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "preflight_success_count": 0,
        "preflight_failure_count": 0,
        "task_facing_success_count": 0,
        "task_facing_failure_count": 0,
        "operation_counts": {},
        "returncode_counts": {},
        "failure_category_counts": {},
        "raw_material_recorded": False,
    }
    if trace_dir is None or not trace_dir.exists():
        return summary
    for trace_file in sorted(trace_dir.glob("*.compact.json")):
        try:
            trace = json.loads(trace_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(trace, dict):
            continue
        boundary = trace.get("boundary") if isinstance(trace.get("boundary"), dict) else {}
        summary["raw_material_recorded"] = bool(
            summary["raw_material_recorded"]
            or any(
                boundary.get(field) is True
                for field in (
                    "raw_command_recorded",
                    "raw_stdout_recorded",
                    "raw_stderr_recorded",
                    "raw_task_text_recorded",
                    "raw_logs_recorded",
                    "raw_trajectory_recorded",
                    "credential_values_recorded",
                    "host_paths_recorded",
                    "remote_paths_recorded",
                )
            )
        )
        if trace.get("trace_kind") != "remote_command_file_bridge_agent_operations":
            continue
        operations = trace.get("remote_command_file_bridge_agent_operations")
        if not isinstance(operations, dict):
            continue
        summary["trace_present"] = True
        summary["trace_count"] = int(summary["trace_count"]) + 1
        for source_key, target_key in (
            ("request_count", "request_count"),
            ("task_facing_operation_count", "task_facing_operation_count"),
            ("success_count", "success_count"),
            ("failure_count", "failure_count"),
            ("preflight_success_count", "preflight_success_count"),
            ("preflight_failure_count", "preflight_failure_count"),
            ("task_facing_success_count", "task_facing_success_count"),
            ("task_facing_failure_count", "task_facing_failure_count"),
        ):
            value = operations.get(source_key)
            if isinstance(value, int) and not isinstance(value, bool):
                summary[target_key] = int(summary[target_key]) + max(0, value)
        for source_key, target_key in (
            ("operation_counts", "operation_counts"),
            ("returncode_counts", "returncode_counts"),
            ("failure_category_counts", "failure_category_counts"),
        ):
            source_counts = operations.get(source_key)
            target_counts = summary.get(target_key)
            if not isinstance(source_counts, dict) or not isinstance(
                target_counts, dict
            ):
                continue
            for key, value in source_counts.items():
                if not isinstance(key, str) or not key:
                    continue
                if not isinstance(value, int) or isinstance(value, bool):
                    continue
                safe_key = key[:80]
                target_counts[safe_key] = int(target_counts.get(safe_key, 0)) + max(
                    0, value
                )
        operation_counts = summary.get("operation_counts")
        if isinstance(operation_counts, dict):
            value = operation_counts.get("preflight")
            if isinstance(value, int) and not isinstance(value, bool):
                summary["preflight_operation_count"] = max(0, value)
    return summary


def _host_local_acp_codex_exec_preflight_bridge_success_observed(
    bridge_summary: dict[str, Any],
) -> bool:
    action_count = int(bridge_summary.get("preflight_operation_count") or 0) + int(
        bridge_summary.get("task_facing_operation_count") or 0
    )
    successful_action_count = int(
        bridge_summary.get("preflight_success_count") or 0
    ) + int(bridge_summary.get("task_facing_success_count") or 0)
    return action_count > 0 and successful_action_count > 0


def _first_bridge_failure_category(bridge_summary: dict[str, Any]) -> str:
    counts = bridge_summary.get("failure_category_counts")
    if isinstance(counts, dict):
        for key, value in sorted(counts.items()):
            if isinstance(key, str) and key and isinstance(value, int) and value > 0:
                return key[:120]
    return "codex_remote_bridge_operation_failed"


def _run_host_local_acp_codex_exec_preflight(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> None:
    prerequisites = plan.setdefault("runner_prerequisites", {})
    prerequisites["host_local_acp_codex_exec_preflight_requested"] = True
    prerequisites["host_local_acp_codex_exec_preflight_status"] = "running"
    bridge_action_required = _host_local_acp_codex_exec_preflight_requires_bridge_action(
        args
    )
    prerequisites["host_local_acp_codex_exec_preflight_bridge_action_required"] = (
        bridge_action_required
    )
    attempts = max(
        1,
        int(getattr(args, "host_local_acp_codex_exec_preflight_attempts", 1) or 1),
    )
    command = _host_local_acp_codex_exec_preflight_command(args, plan)
    target_env = _host_local_acp_target_env({}, args=args)
    prerequisites["host_local_acp_target_env_forwarded"] = bool(target_env)
    prerequisites["host_local_acp_target_env_key_count"] = len(target_env)
    prerequisites["host_local_acp_target_env_keys"] = sorted(target_env)
    if target_env:
        prerequisites["benchmark_egress_proxy_agent_env_injected"] = bool(
            any(key.startswith("LOOPX_SKILLSBENCH") for key in target_env)
        )
    proxy_probe = _host_local_proxy_endpoint_probe(env=target_env or None)
    prerequisites["host_local_acp_proxy_endpoint_status"] = proxy_probe["status"]
    prerequisites["host_local_acp_proxy_endpoint_checked"] = (
        proxy_probe.get("checked") is True
    )
    prerequisites["host_local_acp_proxy_endpoint_raw_url_recorded"] = False
    if proxy_probe.get("configured") is True:
        prerequisites["host_local_acp_proxy_endpoint_env_key"] = str(
            proxy_probe.get("env_key") or ""
        )[:80]
        prerequisites["host_local_acp_proxy_endpoint_scheme"] = str(
            proxy_probe.get("proxy_scheme") or ""
        )[:20]
    if isinstance(proxy_probe.get("loopback_proxy_port"), int):
        prerequisites["host_local_acp_proxy_endpoint_loopback_port"] = proxy_probe[
            "loopback_proxy_port"
        ]
    if proxy_probe.get("error_class"):
        prerequisites["host_local_acp_proxy_endpoint_error_class"] = str(
            proxy_probe.get("error_class") or ""
        )[:80]
    if proxy_probe["status"] in {"unreachable", "invalid_loopback_proxy_port"}:
        proxy_blocker = "skillsbench_host_local_acp_proxy_endpoint_unreachable"
        proxy_failure_category = "codex_proxy_endpoint_unreachable"
        proxy_error = "host-local ACP proxy endpoint unreachable"
        if proxy_probe["status"] == "invalid_loopback_proxy_port":
            proxy_blocker = "skillsbench_host_local_acp_proxy_endpoint_invalid"
            proxy_failure_category = "codex_proxy_endpoint_invalid"
            proxy_error = "host-local ACP proxy endpoint invalid"
        prerequisites["host_local_acp_codex_exec_preflight_status"] = "failed"
        prerequisites["host_local_acp_codex_exec_preflight_first_blocker"] = (
            proxy_blocker
        )
        prerequisites["host_local_acp_codex_exec_failure_category"] = (
            proxy_failure_category
        )
        prerequisites["host_local_acp_codex_exec_preflight_ready"] = False
        raise RuntimeError(proxy_error)
    relay_trace_dir = str(plan.get("host_local_acp_relay_trace_dir") or "")
    preflight_trace_dir = (
        Path(relay_trace_dir) / "codex-exec-preflight" if relay_trace_dir else None
    )
    for attempt in range(1, attempts + 1):
        prerequisites["host_local_acp_codex_exec_preflight_attempt_count"] = attempt
        if preflight_trace_dir:
            preflight_trace_dir.mkdir(parents=True, exist_ok=True)
            for trace_file in preflight_trace_dir.glob("*.compact.json"):
                trace_file.unlink(missing_ok=True)
        probe = run_skillsbench_local_acp_relay_probe(
            command,
            timeout_sec=float(args.host_local_acp_codex_exec_preflight_timeout_sec),
            prompt_text=(
                SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_PROMPT
                if bridge_action_required
                else None
            ),
            required_response_marker=(
                SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER
                if bridge_action_required
                else SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER
            ),
            model_id=str(getattr(args, "model", "") or "") or None,
            env=target_env or None,
        )
        ready = probe.get("ready") is True
        prerequisites["host_local_acp_codex_exec_preflight_ready"] = ready
        prerequisites["host_local_acp_codex_exec_preflight_stage"] = str(
            probe.get("stage") or ""
        )[:180]
        prerequisites["host_local_acp_codex_exec_preflight_first_blocker"] = str(
            probe.get("first_blocker") or ""
        )[:180]
        prerequisites[
            "host_local_acp_codex_exec_preflight_response_marker_observed"
        ] = probe.get("response_marker_observed") is True
        bridge_summary = _summarize_host_local_acp_preflight_bridge_trace(
            preflight_trace_dir
        )
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_trace_present"
        ] = bridge_summary["trace_present"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_trace_count"
        ] = bridge_summary["trace_count"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_request_count"
        ] = bridge_summary["request_count"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_task_facing_operation_count"
        ] = bridge_summary["task_facing_operation_count"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_preflight_operation_count"
        ] = bridge_summary["preflight_operation_count"]
        prerequisites["host_local_acp_codex_exec_preflight_bridge_success_count"] = (
            bridge_summary["success_count"]
        )
        prerequisites["host_local_acp_codex_exec_preflight_bridge_failure_count"] = (
            bridge_summary["failure_count"]
        )
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_preflight_success_count"
        ] = bridge_summary["preflight_success_count"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_preflight_failure_count"
        ] = bridge_summary["preflight_failure_count"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_task_facing_success_count"
        ] = bridge_summary["task_facing_success_count"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_task_facing_failure_count"
        ] = bridge_summary["task_facing_failure_count"]
        prerequisites["host_local_acp_codex_exec_preflight_bridge_returncode_counts"] = (
            bridge_summary["returncode_counts"]
        )
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_failure_category_counts"
        ] = bridge_summary["failure_category_counts"]
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_raw_material_recorded"
        ] = bridge_summary["raw_material_recorded"]
        bridge_action_observed = bool(
            bridge_summary["preflight_operation_count"] > 0
            or bridge_summary["task_facing_operation_count"] > 0
        )
        prerequisites["host_local_acp_codex_exec_preflight_bridge_action_observed"] = (
            bridge_action_observed
        )
        bridge_action_success_observed = (
            _host_local_acp_codex_exec_preflight_bridge_success_observed(
                bridge_summary
            )
        )
        prerequisites[
            "host_local_acp_codex_exec_preflight_bridge_action_success_observed"
        ] = bridge_action_success_observed
        if ready and (not bridge_action_required or bridge_action_success_observed):
            prerequisites["host_local_acp_codex_exec_preflight_status"] = "passed"
            for key in (
                "host_local_acp_codex_exec_failure_category",
                "host_local_acp_codex_exec_failure_categories",
                "host_local_acp_codex_exec_failure_trace_count",
                "host_local_acp_codex_exec_failure_trace_present",
            ):
                prerequisites.pop(key, None)
            return
        prerequisites["host_local_acp_codex_exec_preflight_status"] = "failed"
        if ready and bridge_action_required and not bridge_action_observed:
            prerequisites["host_local_acp_codex_exec_preflight_first_blocker"] = (
                "skillsbench_host_local_acp_codex_exec_preflight_bridge_action_missing"
            )
            prerequisites["host_local_acp_codex_exec_failure_category"] = (
                "codex_exec_no_bridge_action"
            )
        elif ready and bridge_action_required and not bridge_action_success_observed:
            prerequisites["host_local_acp_codex_exec_preflight_first_blocker"] = (
                "skillsbench_host_local_acp_codex_exec_preflight_bridge_action_failed"
            )
            prerequisites["host_local_acp_codex_exec_failure_category"] = (
                _first_bridge_failure_category(bridge_summary)
            )
        if preflight_trace_dir:
            trace: dict[str, Any] = {
                "schema_version": "skillsbench_loopx_controller_trace_v0"
            }
            preflight_plan = {
                "host_local_acp_relay_trace_dir": str(preflight_trace_dir),
                "runner_prerequisites": prerequisites,
            }
            _merge_host_local_acp_relay_trace_summary(preflight_plan, trace)
        category = str(
            prerequisites.get("host_local_acp_codex_exec_failure_category") or ""
        )
        if (
            category == "codex_reverse_channel_unavailable"
            and attempt < attempts
        ):
            time.sleep(2.0)
            continue
        raise RuntimeError("host-local ACP codex exec preflight failed")


def _benchflow_agent_runtime_layer_contract(args: argparse.Namespace) -> dict[str, Any]:
    runtime_dir_arg = getattr(args, "benchflow_agent_runtime_dir", None)
    runtime_dir = Path(runtime_dir_arg).expanduser() if runtime_dir_arg else None
    required = bool(getattr(args, "require_preinstalled_benchflow_agent_runtime", False))
    required_relatives = (
        "bin/node",
        "bin/npm",
        "bin/codex-acp",
    )
    missing: list[str] = []
    if runtime_dir is None:
        missing = list(required_relatives)
    elif not runtime_dir.exists():
        missing = list(required_relatives)
    else:
        for relative in required_relatives:
            if not (runtime_dir / relative).exists():
                missing.append(relative)
    ready = not missing
    status = "ready" if ready else "missing_runtime_files"
    if not required and runtime_dir is None:
        status = "not_requested"
    return {
        "schema_version": "skillsbench_benchflow_agent_runtime_layer_contract_v0",
        "required": required,
        "ready": ready if required or runtime_dir is not None else False,
        "status": status,
        "first_blocker": "" if ready else "missing_preinstalled_benchflow_agent_runtime",
        "source_basename": runtime_dir.name if runtime_dir else "",
        "source_path_recorded": False,
        "mount_target": BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET,
        "required_files": list(required_relatives),
        "missing_files": missing,
        "case_container_rule": "agent_runtime_preinstalled_before_case_start",
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "credential_values_recorded": False,
    }


def _benchflow_agent_runtime_mounts(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    runtime_dir_arg = getattr(args, "benchflow_agent_runtime_dir", None)
    if not runtime_dir_arg:
        return []
    runtime_dir = Path(str(runtime_dir_arg)).expanduser()
    return [
        {
            "type": "bind",
            "source": str(runtime_dir),
            "target": BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET,
            "read_only": True,
        }
    ]


def _loopx_source_mount_contract(args: argparse.Namespace) -> dict[str, Any]:
    source_arg = getattr(args, "loopx_source_dir", None)
    source_dir = Path(str(source_arg)).expanduser() if source_arg else None
    disabled = bool(getattr(args, "no_loopx_source_mount", False))
    requested = (
        _is_loopx_product_mode_route(args.route)
        and args.sandbox == "docker"
        and not disabled
        and source_dir is not None
    )
    ready = bool(
        requested
        and source_dir is not None
        and (source_dir / "loopx" / "cli.py").exists()
    )
    status = "not_requested"
    if requested:
        status = "ready" if ready else "missing_local_source_files"
    return {
        "schema_version": "skillsbench_loopx_source_mount_contract_v0",
        "requested": requested,
        "ready": ready,
        "status": status,
        "source_path_recorded": False,
        "mount_target": BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET,
        "read_only": True,
        "first_blocker": "" if ready or not requested else "missing_loopx_source_mount",
    }


def _loopx_source_mounts(args: argparse.Namespace) -> list[dict[str, Any]]:
    contract = _loopx_source_mount_contract(args)
    if not contract.get("requested"):
        return []
    if getattr(args, "host_local_acp_launch", False):
        return []
    source_dir = Path(str(args.loopx_source_dir)).expanduser()
    return [
        {
            "type": "bind",
            "source": str(source_dir),
            "target": BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET,
            "read_only": True,
        }
    ]


def _loopx_case_source_path_for_container(args: argparse.Namespace) -> str | None:
    contract = _loopx_source_mount_contract(args)
    if contract.get("ready"):
        return BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET
    return None


def _loopx_source_upload_paths(source_dir: Path) -> list[Path]:
    """Return the minimal real LoopX source subset needed by ``python -m loopx.cli``."""

    candidates = [
        source_dir / "loopx",
        source_dir / "pyproject.toml",
        source_dir / "README.md",
    ]
    return [path for path in candidates if path.exists()]


def _copy_loopx_source_subset(source_dir: Path, target_dir: Path) -> int:
    file_count = 0
    for source_path in _loopx_source_upload_paths(source_dir):
        destination = target_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(
                source_path,
                destination,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".mypy_cache",
                    ".pytest_cache",
                    ".ruff_cache",
                ),
            )
            file_count += sum(1 for path in destination.rglob("*") if path.is_file())
        else:
            shutil.copy2(source_path, destination)
            file_count += 1
    return file_count


def _public_runner_prerequisites(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "agent_execution_mode",
        "benchflow_run_stage",
        "host_local_acp_launch_status",
        "host_local_acp_install_stage",
        "host_local_acp_install_failed_stage",
        "codex_acp_runtime_launch_preflight_stage",
        "codex_acp_runtime_launch_preflight_status",
        "benchflow_agent_runtime_layer_status",
        "benchflow_agent_runtime_layer_mount_target",
        "loopx_source_mount_status",
        "loopx_source_mount_target",
        "loopx_source_upload_fallback_status",
        "loopx_source_upload_fallback_exception_type",
        "loopx_source_upload_target",
        "codex_app_server_goal_worker_plan_schema",
        "benchflow_user_loop_recovery_exception_type",
        "benchflow_user_loop_recovery_stage",
        "benchflow_user_loop_soft_verify_exception_type",
        "benchflow_user_loop_soft_verify_exception_stage",
        "benchflow_user_loop_no_tool_exception_type",
        "benchflow_user_loop_no_tool_exception_stage",
        "benchflow_intermediate_soft_verify_policy",
        "benchflow_intermediate_soft_verify_timeout_stage",
        "benchflow_intermediate_soft_verify_timeout_cleanup_status",
        "benchflow_intermediate_soft_verify_orphan_cleanup_status",
        "host_local_acp_attempt_cleanup_status",
        "benchflow_setup_stall_cleanup_status",
        "remote_command_file_bridge_consumption_status",
        "remote_command_file_bridge_agent_operation_trace_status",
        "remote_command_file_bridge_agent_transport_mode",
        "host_local_acp_sandbox_bridge_mode",
        "host_local_acp_session_adapter_status",
        "host_local_acp_pwd_probe_status",
        "host_local_acp_pwd_probe_exception_type",
        "host_local_acp_pwd_probe_stdout_type",
        "host_local_acp_codex_exec_preflight_status",
        "host_local_acp_codex_exec_preflight_stage",
        "host_local_acp_codex_exec_preflight_first_blocker",
        "host_local_acp_codex_exec_failure_category",
        "codex_cli_goal_tui_stage",
        "codex_cli_goal_tui_post_bridge_recovery_action",
        "codex_cli_goal_tui_post_bridge_recovery_skip_reason",
        "codex_cli_goal_tui_reasoning_effort",
        "codex_api_egress_preflight_status",
        "codex_api_egress_preflight_error_kind",
        "codex_api_egress_mode_requested",
        "codex_api_egress_mode_resolved",
        "codex_api_reverse_tunnel_proxy_source",
        "codex_api_reverse_tunnel_proxy_scheme",
        "codex_api_reverse_tunnel_proxy_endpoint_kind",
        "benchmark_egress_proxy_status",
        "benchmark_egress_proxy_error_kind",
        "benchmark_egress_proxy_mode_requested",
        "benchmark_egress_proxy_mode_effective",
        "benchmark_egress_proxy_source",
        "benchmark_egress_proxy_env_key",
        "benchmark_egress_proxy_scheme",
        "benchmark_egress_proxy_endpoint_kind",
        "verifier_dependency_cache_mode",
        "host_local_acp_proxy_endpoint_status",
        "host_local_acp_proxy_endpoint_env_key",
        "host_local_acp_proxy_endpoint_scheme",
        "host_local_acp_proxy_endpoint_error_class",
        "host_local_acp_bridge_progress_status",
        "host_local_acp_bridge_progress_signal_source",
        "runner_interruption_kind",
        "runner_interruption_status",
        "reduce_only_prerequisites_source",
    ):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            compact[field] = raw[:180]
    for field in (
        "codex_acp_runtime_container_bootstrap",
        "codex_acp_runtime_dependency_preflight",
        "codex_acp_runtime_launch_preflight",
        "codex_acp_runtime_launch_preflight_raw_logs_read",
        "host_local_acp_launch",
        "host_local_acp_sandbox_bridge_configured",
        "host_local_acp_sandbox_bridge_path_recorded",
        "host_local_acp_target_env_forwarded",
        "host_local_acp_pwd_probe_cwd_present",
        "host_local_acp_rollout_planes_available",
        "host_local_acp_codex_exec_preflight_requested",
        "host_local_acp_codex_exec_preflight_ready",
        "codex_api_egress_preflight_required",
        "codex_api_egress_preflight_ready",
        "codex_api_reverse_tunnel_required",
        "codex_api_reverse_tunnel_proxy_configured",
        "codex_api_reverse_tunnel_proxy_url_recorded",
        "benchmark_egress_proxy_ready",
        "benchmark_egress_proxy_configured",
        "benchmark_egress_proxy_required",
        "benchmark_egress_proxy_url_recorded",
        "benchmark_egress_direct_fallback_allowed",
        "benchmark_egress_direct_fallback_active",
        "benchmark_egress_no_proxy_configured",
        "benchmark_egress_no_proxy_raw_value_recorded",
        "benchmark_egress_proxy_agent_env_injected",
        "benchmark_egress_proxy_docker_config_injected",
        "benchmark_egress_proxy_docker_config_path_recorded",
        "benchmark_egress_proxy_docker_config_raw_proxy_recorded",
        "benchmark_egress_proxy_docker_cli_plugins_preserved",
        "benchmark_egress_proxy_docker_cli_plugin_paths_recorded",
        "host_local_acp_codex_exec_preflight_response_marker_observed",
        "host_local_acp_codex_exec_preflight_bridge_action_required",
        "host_local_acp_codex_exec_preflight_bridge_action_observed",
        "host_local_acp_codex_exec_preflight_bridge_action_success_observed",
        "host_local_acp_codex_exec_preflight_bridge_trace_present",
        "host_local_acp_codex_exec_preflight_bridge_raw_material_recorded",
        "host_local_acp_proxy_endpoint_checked",
        "host_local_acp_proxy_endpoint_raw_url_recorded",
        "container_codex_acp_install_skipped",
        "benchflow_agent_install_skipped_by_runtime_layer",
        "benchflow_rollout_planes_module_available",
        "remote_command_file_bridge_materialized",
        "remote_command_file_bridge_command_configured",
        "remote_command_file_bridge_agent_command_configured",
        "remote_command_file_bridge_agent_command_instrumented",
        "remote_command_file_bridge_agent_queue_configured",
        "remote_command_file_bridge_agent_queue_path_recorded",
        "remote_command_file_bridge_probe_command_configured",
        "remote_command_file_bridge_solver_wiring_configured",
        "remote_command_file_bridge_consumed_by_solver",
        "remote_command_file_bridge_solver_trace_dir_present",
        "remote_command_file_bridge_solver_public_trace_read",
        "remote_command_file_bridge_solver_raw_material_recorded",
        "remote_command_file_bridge_agent_operation_trace_required",
        "remote_command_file_bridge_agent_operation_trace_satisfied",
        "remote_command_file_bridge_agent_operation_trace_present",
        "remote_command_file_bridge_driver_lifecycle_trace_present",
        "host_local_acp_codex_exec_failure_trace_present",
        "host_local_acp_codex_exec_failure_raw_material_recorded",
        "remote_command_file_bridge_driver_lifecycle_raw_material_recorded",
        "codex_cli_goal_tui_trace_present",
        "codex_cli_goal_tui_raw_material_recorded",
        "preinstalled_benchflow_agent_runtime_required",
        "benchflow_agent_runtime_layer_ready",
        "codex_acp_runtime_dependency_setup_skipped",
        "benchflow_agent_runtime_mount_injected",
        "benchflow_agent_runtime_mount_read_only",
        "benchflow_agent_runtime_mount_source_recorded",
        "loopx_source_mount_requested",
        "loopx_source_mount_ready",
        "loopx_source_mount_injected",
        "loopx_source_mount_read_only",
        "loopx_source_mount_source_recorded",
        "loopx_source_visible_before_upload",
        "loopx_source_visible_after_upload",
        "loopx_source_upload_fallback_supported",
        "loopx_source_upload_fallback_attempted",
        "loopx_source_upload_raw_material_recorded",
        "verifier_dependency_cache_requested",
        "verifier_dependency_cache_ready",
        "verifier_dependency_cache_mount_injected",
        "verifier_dependency_cache_raw_path_recorded",
        "verifier_dependency_cache_solver_write_access",
        "verifier_dependency_cache_scoring_material_cached",
        "benchflow_agent_timeout_overridden",
        "codex_app_server_goal_worker_adapter_present",
        "codex_app_server_goal_worker_turn_start_required",
        "codex_app_server_goal_worker_goal_get_required",
        "codex_app_server_goal_worker_runner_integration_ready",
        "benchflow_user_loop_final_verify_recovery_enabled",
        "benchflow_user_loop_final_verify_recovery_triggered",
        "benchflow_user_loop_recovery_after_agent_activity",
        "benchflow_user_loop_recovery_raw_error_recorded",
        "benchflow_user_loop_recovery_preserved_final_verify",
        "benchflow_user_loop_soft_verify_exception_continued",
        "benchflow_user_loop_soft_verify_exception_raw_error_recorded",
        "benchflow_user_loop_no_tool_exception_continued",
        "benchflow_user_loop_no_tool_exception_raw_error_recorded",
        "benchflow_intermediate_soft_verify_final_only",
        "benchflow_intermediate_soft_verify_raw_output_recorded",
        "benchflow_intermediate_soft_verify_timeout_enabled",
        "benchflow_intermediate_soft_verify_timeout_triggered",
        "benchflow_intermediate_soft_verify_timeout_raw_output_recorded",
        "benchflow_intermediate_soft_verify_timeout_cleanup_requested",
        "benchflow_intermediate_soft_verify_timeout_cleanup_raw_logs_read",
        "benchflow_intermediate_soft_verify_orphan_cleanup_requested",
        "benchflow_intermediate_soft_verify_orphan_cleanup_raw_logs_read",
        "host_local_acp_attempt_cleanup_requested",
        "host_local_acp_attempt_cleanup_raw_logs_read",
        "host_local_acp_attempt_cleanup_raw_command_recorded",
        "goal_start_product_mode",
        "goal_start_plan_required",
        "goal_start_guided_command_required",
        "goal_start_agent_authored_plan_required",
        "goal_start_host_preseed_forbidden",
        "goal_start_selected_p0_lifecycle_required",
        "benchflow_verifier_prep_timeout_override_enabled",
        "benchflow_verifier_prep_timeout_raw_command_recorded",
        "benchflow_final_verifier_timeout_enabled",
        "benchflow_final_verifier_timeout_triggered",
        "benchflow_final_verifier_timeout_raw_command_recorded",
        "benchflow_final_verifier_timeout_raw_output_recorded",
        "benchflow_verifier_completion_poll_enabled",
        "benchflow_verifier_completion_poll_timeout_triggered",
        "benchflow_verifier_completion_poll_raw_command_recorded",
        "benchflow_verifier_completion_poll_raw_output_recorded",
        "benchflow_setup_stall_timeout_enabled",
        "benchflow_setup_stall_timeout_triggered",
        "benchflow_setup_stall_raw_logs_read",
        "benchflow_setup_stall_before_agent_lifecycle",
        "benchflow_agent_install_started",
        "benchflow_setup_stall_task_cancel_requested",
        "benchflow_setup_stall_task_cancel_acknowledged",
        "benchflow_setup_stall_task_cancel_timeout",
        "benchflow_setup_stall_cleanup_requested",
        "benchflow_setup_stall_cleanup_raw_logs_read",
        "runner_interrupted_before_official_result",
        "runner_interruption_compact_closeout_expected",
        "runner_interruption_raw_material_recorded",
        "reduce_only_prerequisites_artifact_read",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    lifecycle = compact_benchmark_canonical_lifecycle(
        value.get("benchmark_canonical_lifecycle")
    )
    if lifecycle:
        compact["benchmark_canonical_lifecycle"] = lifecycle
    for field in (
        "codex_acp_runtime_launch_preflight_rc",
        "benchflow_agent_timeout_requested_sec",
        "benchflow_agent_timeout_original_sec",
        "benchflow_agent_timeout_effective_sec",
        "benchflow_agent_timeout_host_local_acp_exec_timeout_sec",
        "benchflow_agent_timeout_host_local_acp_task_output_quiet_timeout_sec",
        "benchflow_agent_timeout_host_local_acp_margin_sec",
        "host_local_acp_connect_return_arity",
        "benchflow_user_loop_recovery_round",
        "benchflow_user_loop_recovery_delta_events",
        "benchflow_user_loop_recovery_delta_tool_calls",
        "benchflow_user_loop_soft_verify_exception_count",
        "benchflow_user_loop_soft_verify_exception_round",
        "benchflow_user_loop_soft_verify_exception_delta_events",
        "benchflow_user_loop_soft_verify_exception_delta_tool_calls",
        "benchflow_user_loop_no_tool_exception_count",
        "benchflow_user_loop_no_tool_exception_round",
        "benchflow_user_loop_no_tool_exception_delta_events",
        "benchflow_user_loop_no_tool_exception_delta_tool_calls",
        "benchflow_intermediate_soft_verify_call_count",
        "benchflow_intermediate_soft_verify_skipped_count",
        "benchflow_intermediate_soft_verify_timeout_sec",
        "benchflow_intermediate_soft_verify_timeout_override_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_container_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_match_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_term_sent_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_kill_sent_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_alive_after_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_container_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_match_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_term_sent_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_kill_sent_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_alive_after_count",
        "host_local_acp_attempt_cleanup_match_count",
        "host_local_acp_attempt_cleanup_term_sent_count",
        "host_local_acp_attempt_cleanup_kill_sent_count",
        "host_local_acp_attempt_cleanup_alive_after_count",
        "benchflow_verifier_prep_timeout_sec",
        "benchflow_final_verifier_timeout_sec",
        "benchflow_final_verifier_timeout_override_count",
        "benchflow_final_verifier_outer_timeout_override_count",
        "benchflow_verifier_prep_timeout_override_count",
        "benchflow_verify_prep_timeout_override_count",
        "benchflow_soft_verify_prep_timeout_override_count",
        "benchflow_setup_stall_timeout_requested_sec",
        "benchflow_setup_stall_timeout_sec",
        "benchflow_setup_stall_cleanup_match_count",
        "benchflow_setup_stall_cleanup_term_sent_count",
        "benchflow_setup_stall_cleanup_kill_sent_count",
        "benchflow_setup_stall_cleanup_alive_after_count",
        "verifier_dependency_cache_env_key_count",
        "goal_start_planned_todo_count_expected",
        "remote_command_file_bridge_solver_trace_count",
        "remote_command_file_bridge_solver_probe_ready_count",
        "remote_command_file_bridge_solver_operation_count",
        "remote_command_file_bridge_agent_operation_trace_count",
        "remote_command_file_bridge_agent_request_count",
        "remote_command_file_bridge_agent_success_count",
        "remote_command_file_bridge_agent_failure_count",
        "remote_command_file_bridge_agent_loopx_cli_call_count",
        "remote_command_file_bridge_agent_loopx_state_read_count",
        "remote_command_file_bridge_agent_loopx_state_write_count",
        "remote_command_file_bridge_agent_task_facing_operation_count",
        "remote_command_file_bridge_agent_task_facing_success_count",
        "remote_command_file_bridge_agent_task_facing_failure_count",
        "remote_command_file_bridge_agent_probe_operation_count",
        "remote_command_file_bridge_agent_todo_closeout_count",
        "remote_command_file_bridge_agent_refresh_state_count",
        "remote_command_file_bridge_agent_quota_spend_slot_count",
        "remote_command_file_bridge_driver_lifecycle_trace_count",
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count",
        "remote_command_file_bridge_driver_lifecycle_request_count",
        "remote_command_file_bridge_driver_lifecycle_success_count",
        "remote_command_file_bridge_driver_lifecycle_failure_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count",
        "codex_cli_goal_tui_trace_count",
        "codex_cli_goal_tui_ok_count",
        "codex_cli_goal_tui_goal_active_observed_count",
        "codex_cli_goal_tui_goal_terminal_observed_count",
        "codex_cli_goal_tui_first_action_observed_count",
        "codex_cli_goal_tui_bridge_request_count",
        "codex_cli_goal_tui_task_facing_success_count",
        "codex_cli_goal_tui_pre_bridge_recovery_attempt_count",
        "codex_cli_goal_tui_post_bridge_recovery_attempt_count",
        "host_local_acp_sandbox_bridge_compose_file_count",
        "host_local_acp_target_env_key_count",
        "host_local_acp_pwd_probe_rc",
        "loopx_source_upload_fallback_file_count",
        "host_local_acp_codex_exec_preflight_attempt_count",
        "host_local_acp_codex_exec_preflight_bridge_trace_count",
        "host_local_acp_codex_exec_preflight_bridge_request_count",
        "host_local_acp_codex_exec_preflight_bridge_preflight_operation_count",
        "host_local_acp_codex_exec_preflight_bridge_task_facing_operation_count",
        "host_local_acp_codex_exec_preflight_bridge_success_count",
        "host_local_acp_codex_exec_preflight_bridge_failure_count",
        "host_local_acp_codex_exec_preflight_bridge_preflight_success_count",
        "host_local_acp_codex_exec_preflight_bridge_preflight_failure_count",
        "host_local_acp_codex_exec_preflight_bridge_task_facing_success_count",
        "host_local_acp_codex_exec_preflight_bridge_task_facing_failure_count",
        "host_local_acp_codex_exec_failure_trace_count",
        "host_local_acp_codex_exec_recoverable_failure_trace_count",
        "host_local_acp_codex_exec_fatal_failure_trace_count",
        "codex_api_reverse_tunnel_proxy_endpoint_port",
        "benchmark_egress_proxy_endpoint_port",
        "benchmark_egress_no_proxy_entry_count",
        "host_local_acp_proxy_endpoint_loopback_port",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    compact.update(runner_source.compact_runner_source_public_fields(value))
    compact.update(proxy_runtime.compact_base_image_prewarm_fields(value))
    compact.update(codex_runtime.compact_public_fields(value))
    target_keys = value.get("host_local_acp_target_env_keys")
    if isinstance(target_keys, list):
        compact["host_local_acp_target_env_keys"] = [
            key
            for key in target_keys
            if isinstance(key, str) and key in HOST_LOCAL_ACP_TARGET_ENV_KEYS
        ][: len(HOST_LOCAL_ACP_TARGET_ENV_KEYS)]
    planned_todo_ids = _goal_start_public_todo_id_list(value.get("planned_todo_ids"))
    if planned_todo_ids:
        compact["planned_todo_ids"] = planned_todo_ids
    planned_todo_texts = _goal_start_public_text_list(
        value.get("planned_todo_texts_public_safe")
    )
    if planned_todo_texts:
        compact["planned_todo_texts_public_safe"] = planned_todo_texts
    command_records = _goal_start_public_command_records(
        value.get("remote_command_file_bridge_agent_successful_loopx_command_records")
    )
    if command_records:
        compact[
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        ] = command_records
    for field in (
        "host_local_acp_codex_exec_preflight_bridge_returncode_counts",
        "host_local_acp_codex_exec_preflight_bridge_failure_category_counts",
        "remote_command_file_bridge_agent_operation_counts",
        "remote_command_file_bridge_agent_returncode_counts",
        "remote_command_file_bridge_agent_failure_category_counts",
        "remote_command_file_bridge_agent_loopx_subcommand_counts",
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts",
        "remote_command_file_bridge_driver_lifecycle_command_counts",
        "remote_command_file_bridge_driver_lifecycle_returncode_counts",
    ):
        raw_counts = value.get(field)
        if not isinstance(raw_counts, dict):
            continue
        counts: dict[str, int] = {}
        for key, count in raw_counts.items():
            if (
                isinstance(key, str)
                and key
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
            ):
                counts[key[:80]] = count
        if counts:
            compact[field] = dict(sorted(counts.items()))
    style = value.get("remote_command_file_bridge_driver_lifecycle_execution_style")
    if isinstance(style, str) and style:
        compact["remote_command_file_bridge_driver_lifecycle_execution_style"] = (
            style[:120]
        )
    stages = value.get("codex_cli_goal_tui_stages")
    if isinstance(stages, list):
        compact["codex_cli_goal_tui_stages"] = [
            stage[:80] for stage in stages if isinstance(stage, str) and stage
        ][:16]
    recovery_actions = value.get("codex_cli_goal_tui_post_bridge_recovery_actions")
    if isinstance(recovery_actions, list):
        compact["codex_cli_goal_tui_post_bridge_recovery_actions"] = [
            action[:40]
            for action in recovery_actions
            if isinstance(action, str) and action
        ][:8]
    pre_recovery_actions = value.get("codex_cli_goal_tui_pre_bridge_recovery_actions")
    if isinstance(pre_recovery_actions, list):
        compact["codex_cli_goal_tui_pre_bridge_recovery_actions"] = [
            action[:40]
            for action in pre_recovery_actions
            if isinstance(action, str) and action
        ][:8]
    recovery_skip_reasons = value.get(
        "codex_cli_goal_tui_post_bridge_recovery_skip_reasons"
    )
    if isinstance(recovery_skip_reasons, list):
        compact["codex_cli_goal_tui_post_bridge_recovery_skip_reasons"] = [
            reason[:80]
            for reason in recovery_skip_reasons
            if isinstance(reason, str) and reason
        ][:8]
    pre_recovery_skip_reasons = value.get(
        "codex_cli_goal_tui_pre_bridge_recovery_skip_reasons"
    )
    if isinstance(pre_recovery_skip_reasons, list):
        compact["codex_cli_goal_tui_pre_bridge_recovery_skip_reasons"] = [
            reason[:80]
            for reason in pre_recovery_skip_reasons
            if isinstance(reason, str) and reason
        ][:8]
    reasoning_efforts = value.get("codex_cli_goal_tui_reasoning_efforts")
    if isinstance(reasoning_efforts, list):
        compact["codex_cli_goal_tui_reasoning_efforts"] = [
            effort[:40]
            for effort in reasoning_efforts
            if isinstance(effort, str) and effort
        ][:8]
    return compact


def _runner_prerequisites_public_path(plan: dict[str, Any]) -> Path | None:
    jobs_dir = str(plan.get("jobs_dir") or "")
    job_name = str(plan.get("job_name") or "")
    if not jobs_dir or not job_name:
        return None
    return (
        Path(jobs_dir).expanduser()
        / job_name
        / RUNNER_PREREQUISITES_PUBLIC_FILENAME
    )


def _write_public_runner_prerequisites(plan: dict[str, Any]) -> Path | None:
    compact = _public_runner_prerequisites(plan.get("runner_prerequisites"))
    if not compact:
        return None
    path = _runner_prerequisites_public_path(plan)
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(compact, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return path


def _read_public_runner_prerequisites(plan: dict[str, Any]) -> dict[str, Any]:
    path = _runner_prerequisites_public_path(plan)
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("runner_prerequisites"), dict):
        payload = payload["runner_prerequisites"]
    compact = _public_runner_prerequisites(payload)
    if compact:
        compact["reduce_only_prerequisites_source"] = "persisted_public_job_artifact"
        compact["reduce_only_prerequisites_artifact_read"] = True
    return compact


def _hydrate_reduce_only_public_runner_prerequisites(
    plan: dict[str, Any],
) -> dict[str, Any]:
    compact = _read_public_runner_prerequisites(plan)
    if not compact:
        return {}
    plan["runner_prerequisites"] = compact
    return compact


def cleanup_benchflow_setup_stall_children(
    plan: dict[str, Any],
    *,
    grace_seconds: float = 5.0,
) -> dict[str, Any]:
    """Terminate docker compose/buildx processes scoped to this SkillsBench run."""

    prerequisites = plan.setdefault("runner_prerequisites", {})
    cleanup: dict[str, Any] = {
        "schema_version": "skillsbench_setup_stall_process_cleanup_v0",
        "requested": True,
        "raw_logs_read": False,
        "status": "not_attempted",
        "match_count": 0,
        "term_sent_count": 0,
        "kill_sent_count": 0,
        "alive_after_count": 0,
    }

    def publish() -> dict[str, Any]:
        prerequisites["benchflow_setup_stall_cleanup_requested"] = True
        prerequisites["benchflow_setup_stall_cleanup_raw_logs_read"] = False
        prerequisites["benchflow_setup_stall_cleanup_status"] = str(
            cleanup.get("status") or "unknown"
        )
        for source, target in (
            ("match_count", "benchflow_setup_stall_cleanup_match_count"),
            ("term_sent_count", "benchflow_setup_stall_cleanup_term_sent_count"),
            ("kill_sent_count", "benchflow_setup_stall_cleanup_kill_sent_count"),
            ("alive_after_count", "benchflow_setup_stall_cleanup_alive_after_count"),
        ):
            value = cleanup.get(source)
            if isinstance(value, int):
                prerequisites[target] = value
        return cleanup

    if os.name != "posix":
        cleanup["status"] = "unsupported_platform"
        return publish()

    job_name = str(plan.get("job_name") or "").strip()
    rollout_name = str(plan.get("rollout_name") or "").strip()
    if not job_name or not rollout_name:
        cleanup["status"] = "missing_run_identifiers"
        return publish()

    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,command="],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        cleanup["status"] = "process_table_unavailable"
        return publish()
    if proc.returncode != 0:
        cleanup["status"] = "process_table_unavailable"
        return publish()

    entries: dict[int, tuple[int, str]] = {}
    children: dict[int, set[int]] = {}
    for line in proc.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        command = parts[2]
        entries[pid] = (ppid, command)
        children.setdefault(ppid, set()).add(pid)

    docker_tokens = (
        "docker compose",
        "docker-compose",
        "docker-buildx",
        "buildx bake",
    )
    root_matches = {
        pid
        for pid, (_ppid, command) in entries.items()
        if pid != os.getpid()
        and job_name in command
        and rollout_name in command
        and any(token in command for token in docker_tokens)
    }
    to_terminate = set(root_matches)
    stack = list(root_matches)
    while stack:
        parent = stack.pop()
        for child in children.get(parent, set()):
            if child not in to_terminate and child != os.getpid():
                to_terminate.add(child)
                stack.append(child)

    cleanup["match_count"] = len(to_terminate)
    if not to_terminate:
        cleanup["status"] = "no_matching_processes"
        return publish()

    def is_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    term_sent = 0
    for pid in sorted(to_terminate, reverse=True):
        try:
            os.kill(pid, signal.SIGTERM)
            term_sent += 1
        except ProcessLookupError:
            continue
        except PermissionError:
            continue
    cleanup["term_sent_count"] = term_sent

    deadline = time.monotonic() + max(0.0, grace_seconds)
    alive = {pid for pid in to_terminate if is_alive(pid)}
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = {pid for pid in alive if is_alive(pid)}

    kill_sent = 0
    if alive:
        for pid in sorted(alive, reverse=True):
            try:
                os.kill(pid, signal.SIGKILL)
                kill_sent += 1
            except ProcessLookupError:
                continue
            except PermissionError:
                continue
        cleanup["kill_sent_count"] = kill_sent
        time.sleep(0.1)
        alive = {pid for pid in alive if is_alive(pid)}
    cleanup["alive_after_count"] = len(alive)
    if alive:
        cleanup["status"] = "cleanup_incomplete"
    elif kill_sent:
        cleanup["status"] = "killed"
    else:
        cleanup["status"] = "terminated"
    return publish()


def cleanup_host_local_acp_attempt_children(
    plan: dict[str, Any],
    *,
    grace_seconds: float = 3.0,
) -> dict[str, Any]:
    """Terminate host-local ACP/app-server worker processes scoped to one attempt."""

    prerequisites = plan.setdefault("runner_prerequisites", {})
    cleanup: dict[str, Any] = {
        "schema_version": "skillsbench_host_local_acp_attempt_cleanup_v0",
        "requested": True,
        "raw_logs_read": False,
        "raw_command_recorded": False,
        "status": "not_attempted",
        "match_count": 0,
        "term_sent_count": 0,
        "kill_sent_count": 0,
        "alive_after_count": 0,
    }

    def publish() -> dict[str, Any]:
        prerequisites["host_local_acp_attempt_cleanup_requested"] = True
        prerequisites["host_local_acp_attempt_cleanup_raw_logs_read"] = False
        prerequisites["host_local_acp_attempt_cleanup_raw_command_recorded"] = False
        prerequisites["host_local_acp_attempt_cleanup_status"] = str(
            cleanup.get("status") or "unknown"
        )
        for source, target in (
            ("match_count", "host_local_acp_attempt_cleanup_match_count"),
            ("term_sent_count", "host_local_acp_attempt_cleanup_term_sent_count"),
            ("kill_sent_count", "host_local_acp_attempt_cleanup_kill_sent_count"),
            ("alive_after_count", "host_local_acp_attempt_cleanup_alive_after_count"),
        ):
            value = cleanup.get(source)
            if isinstance(value, int):
                prerequisites[target] = value
        return cleanup

    if os.name != "posix":
        cleanup["status"] = "unsupported_platform"
        return publish()

    if (
        prerequisites.get("host_local_acp_launch") is not True
        and prerequisites.get("agent_execution_mode") != "host_local_acp"
    ):
        cleanup["status"] = "not_applicable_no_host_local_acp"
        return publish()

    identifiers = [
        str(value).strip()
        for value in (plan.get("job_name"), plan.get("rollout_name"))
        if str(value or "").strip()
    ]
    if not identifiers:
        cleanup["status"] = "missing_run_identifiers"
        return publish()

    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,command="],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        cleanup["status"] = "process_table_unavailable"
        return publish()
    if proc.returncode != 0:
        cleanup["status"] = "process_table_unavailable"
        return publish()

    entries: dict[int, tuple[int, str]] = {}
    children: dict[int, set[int]] = {}
    for line in proc.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        command = parts[2]
        entries[pid] = (ppid, command)
        children.setdefault(ppid, set()).add(pid)

    host_local_markers = (
        "skillsbench_local_acp_relay.py",
        "scripts/skillsbench_local_acp_relay.py",
        "skillsbench_host_codex_goal_worker.py",
        "scripts/skillsbench_host_codex_goal_worker.py",
        "skillsbench_remote_command_file_bridge",
        "remote_command_file_bridge",
        "json_file_bridge",
    )
    protected_pids = {os.getpid(), os.getppid()}
    root_matches = {
        pid
        for pid, (_ppid, command) in entries.items()
        if pid not in protected_pids
        and any(identifier in command for identifier in identifiers)
        and any(marker in command for marker in host_local_markers)
    }
    to_terminate = set(root_matches)
    stack = list(root_matches)
    while stack:
        parent = stack.pop()
        for child in children.get(parent, set()):
            if child not in to_terminate and child not in protected_pids:
                to_terminate.add(child)
                stack.append(child)

    cleanup["match_count"] = len(to_terminate)
    if not to_terminate:
        cleanup["status"] = "no_matching_processes"
        return publish()

    def is_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    term_sent = 0
    for pid in sorted(to_terminate, reverse=True):
        try:
            os.kill(pid, signal.SIGTERM)
            term_sent += 1
        except (ProcessLookupError, PermissionError):
            continue
    cleanup["term_sent_count"] = term_sent

    deadline = time.monotonic() + max(0.0, grace_seconds)
    alive = {pid for pid in to_terminate if is_alive(pid)}
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = {pid for pid in alive if is_alive(pid)}

    kill_sent = 0
    if alive:
        for pid in sorted(alive, reverse=True):
            try:
                os.kill(pid, signal.SIGKILL)
                kill_sent += 1
            except (ProcessLookupError, PermissionError):
                continue
        cleanup["kill_sent_count"] = kill_sent
        time.sleep(0.1)
        alive = {pid for pid in alive if is_alive(pid)}
    cleanup["alive_after_count"] = len(alive)
    if alive:
        cleanup["status"] = "cleanup_incomplete"
    elif kill_sent:
        cleanup["status"] = "killed"
    else:
        cleanup["status"] = "terminated"
    return publish()


def cleanup_benchflow_soft_verify_timeout_children(
    plan: dict[str, Any],
    *,
    trace: dict[str, Any] | None = None,
    grace_seconds: float = 3.0,
    metric_prefix: str = "benchflow_intermediate_soft_verify_timeout_cleanup",
    schema_version: str = "skillsbench_soft_verify_timeout_process_cleanup_v0",
) -> dict[str, Any]:
    """Terminate verifier process trees left behind by an intermediate timeout."""

    prerequisites = plan.setdefault("runner_prerequisites", {})
    cleanup: dict[str, Any] = {
        "schema_version": schema_version,
        "requested": True,
        "raw_logs_read": False,
        "raw_command_recorded": False,
        "status": "not_attempted",
        "container_count": 0,
        "match_count": 0,
        "term_sent_count": 0,
        "kill_sent_count": 0,
        "alive_after_count": 0,
    }

    def publish() -> dict[str, Any]:
        prerequisites[f"{metric_prefix}_requested"] = True
        prerequisites[f"{metric_prefix}_raw_logs_read"] = False
        prerequisites[f"{metric_prefix}_status"] = str(
            cleanup.get("status") or "unknown"
        )
        if isinstance(trace, dict):
            trace[f"{metric_prefix}_requested"] = True
            trace[f"{metric_prefix}_raw_logs_read"] = False
            trace[f"{metric_prefix}_status"] = str(
                cleanup.get("status") or "unknown"
            )
        for source, target in (
            ("container_count", f"{metric_prefix}_container_count"),
            ("match_count", f"{metric_prefix}_match_count"),
            ("term_sent_count", f"{metric_prefix}_term_sent_count"),
            ("kill_sent_count", f"{metric_prefix}_kill_sent_count"),
            ("alive_after_count", f"{metric_prefix}_alive_after_count"),
        ):
            value = cleanup.get(source)
            if isinstance(value, int):
                prerequisites[target] = value
                if isinstance(trace, dict):
                    trace[target] = value
        return cleanup

    if os.name != "posix":
        cleanup["status"] = "unsupported_platform"
        return publish()

    job_name = str(plan.get("job_name") or "").strip().lower()
    rollout_name = str(plan.get("rollout_name") or "").strip().lower()
    if not job_name and not rollout_name:
        cleanup["status"] = "missing_run_identifiers"
        return publish()

    try:
        proc = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        cleanup["status"] = "docker_unavailable"
        return publish()
    if proc.returncode != 0:
        cleanup["status"] = "docker_unavailable"
        return publish()

    containers: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        container_id, name = parts[0].strip(), parts[1].strip().lower()
        if not container_id:
            continue
        if (job_name and job_name in name) or (rollout_name and rollout_name in name):
            containers.append(container_id)
    cleanup["container_count"] = len(containers)
    if not containers:
        cleanup["status"] = "no_matching_container"
        return publish()

    total_matches = 0
    total_term_sent = 0
    total_kill_sent = 0
    total_alive_after = 0

    for container_id in containers:
        try:
            ps_proc = subprocess.run(
                ["docker", "exec", container_id, "ps", "-eo", "pid=,ppid=,comm=,args="],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            cleanup["status"] = "container_process_table_unavailable"
            return publish()
        if ps_proc.returncode != 0:
            cleanup["status"] = "container_process_table_unavailable"
            return publish()

        entries: dict[int, tuple[int, str, str]] = {}
        children: dict[int, set[int]] = {}
        for line in ps_proc.stdout.splitlines():
            parts = line.strip().split(maxsplit=3)
            if len(parts) < 3:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
            except ValueError:
                continue
            comm = parts[2]
            args = parts[3] if len(parts) > 3 else ""
            entries[pid] = (ppid, comm, args)
            children.setdefault(ppid, set()).add(pid)

        root_matches = {
            pid
            for pid, (_ppid, comm, args) in entries.items()
            if comm == "test.sh" or "/verifier/test.sh" in args
        }
        to_terminate = set(root_matches)
        stack = list(root_matches)
        while stack:
            parent = stack.pop()
            for child in children.get(parent, set()):
                if child not in to_terminate:
                    to_terminate.add(child)
                    stack.append(child)
        if not to_terminate:
            continue

        total_matches += len(to_terminate)

        def send_signal(sig: str, pids: set[int]) -> int:
            if not pids:
                return 0
            signal_proc = subprocess.run(
                ["docker", "exec", container_id, "kill", f"-{sig}", *map(str, sorted(pids))],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            return len(pids) if signal_proc.returncode == 0 else 0

        def alive_pids(pids: set[int]) -> set[int]:
            alive: set[int] = set()
            for pid in pids:
                probe = subprocess.run(
                    ["docker", "exec", container_id, "kill", "-0", str(pid)],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2,
                )
                if probe.returncode == 0:
                    alive.add(pid)
            return alive

        total_term_sent += send_signal("TERM", to_terminate)
        deadline = time.monotonic() + max(0.0, grace_seconds)
        alive = alive_pids(to_terminate)
        while alive and time.monotonic() < deadline:
            time.sleep(0.1)
            alive = alive_pids(alive)
        if alive:
            total_kill_sent += send_signal("KILL", alive)
            time.sleep(0.1)
            alive = alive_pids(alive)
        total_alive_after += len(alive)

    cleanup["match_count"] = total_matches
    cleanup["term_sent_count"] = total_term_sent
    cleanup["kill_sent_count"] = total_kill_sent
    cleanup["alive_after_count"] = total_alive_after
    if not total_matches:
        cleanup["status"] = "no_matching_processes"
    elif total_alive_after:
        cleanup["status"] = "cleanup_incomplete"
    elif total_kill_sent:
        cleanup["status"] = "killed"
    else:
        cleanup["status"] = "terminated"
    return publish()


def install_benchflow_verifier_prep_timeout_override(
    rollout_cls: Any,
    *,
    timeout_sec: int,
    final_verifier_timeout_sec: int = 0,
    soft_verifier_timeout_sec: int = DEFAULT_SOFT_VERIFIER_TIMEOUT_SEC,
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Raise verifier prep timeouts and bound verifier calls when requested."""

    original_verify = rollout_cls.verify
    original_soft_verify = rollout_cls.soft_verify
    prerequisites = plan.setdefault("runner_prerequisites", {})
    enabled = timeout_sec > 10
    final_timeout_enabled = final_verifier_timeout_sec > 0
    soft_timeout_enabled = soft_verifier_timeout_sec > 0
    prerequisites["benchflow_verifier_prep_timeout_override_enabled"] = enabled
    prerequisites["benchflow_verifier_prep_timeout_raw_command_recorded"] = False
    prerequisites["benchflow_final_verifier_timeout_enabled"] = final_timeout_enabled
    prerequisites["benchflow_final_verifier_timeout_raw_command_recorded"] = False
    prerequisites["benchflow_verifier_completion_poll_enabled"] = False
    prerequisites["benchflow_verifier_completion_poll_timeout_triggered"] = False
    prerequisites["benchflow_verifier_completion_poll_raw_command_recorded"] = False
    prerequisites["benchflow_verifier_completion_poll_raw_output_recorded"] = False
    prerequisites["benchflow_intermediate_soft_verify_timeout_enabled"] = (
        soft_timeout_enabled
    )
    prerequisites["benchflow_intermediate_soft_verify_timeout_raw_output_recorded"] = (
        False
    )
    if enabled:
        prerequisites["benchflow_verifier_prep_timeout_sec"] = timeout_sec
    if final_timeout_enabled:
        prerequisites["benchflow_final_verifier_timeout_sec"] = (
            final_verifier_timeout_sec
        )
    if soft_timeout_enabled:
        prerequisites["benchflow_intermediate_soft_verify_timeout_sec"] = (
            soft_verifier_timeout_sec
        )
    if isinstance(trace, dict):
        trace["benchflow_verifier_prep_timeout_override_enabled"] = enabled
        trace["benchflow_verifier_prep_timeout_raw_command_recorded"] = False
        trace["benchflow_final_verifier_timeout_enabled"] = final_timeout_enabled
        trace["benchflow_final_verifier_timeout_raw_command_recorded"] = False
        trace["benchflow_verifier_completion_poll_enabled"] = False
        trace["benchflow_verifier_completion_poll_timeout_triggered"] = False
        trace["benchflow_verifier_completion_poll_raw_command_recorded"] = False
        trace["benchflow_verifier_completion_poll_raw_output_recorded"] = False
        trace["benchflow_intermediate_soft_verify_timeout_enabled"] = (
            soft_timeout_enabled
        )
        trace["benchflow_intermediate_soft_verify_timeout_raw_output_recorded"] = (
            False
        )
        if enabled:
            trace["benchflow_verifier_prep_timeout_sec"] = timeout_sec
        if final_timeout_enabled:
            trace["benchflow_final_verifier_timeout_sec"] = final_verifier_timeout_sec
        if soft_timeout_enabled:
            trace["benchflow_intermediate_soft_verify_timeout_sec"] = (
                soft_verifier_timeout_sec
            )

    def _looks_like_final_verifier_exec(
        exec_args: tuple[Any, ...],
        exec_kwargs: dict[str, Any],
    ) -> bool:
        command = exec_kwargs.get("command")
        if command is None and exec_args:
            command = exec_args[0]
        if not isinstance(command, str):
            return False
        return "/verifier/test.sh" in command

    async def _run_with_override(self: Any, phase: str, original: Any) -> Any:
        if not enabled and not final_timeout_enabled and not soft_timeout_enabled:
            return await original(self)

        env = getattr(self, "_env", None)
        original_exec = getattr(env, "exec", None) if env is not None else None
        if original_exec is None:
            return await original(self)

        override_count = 0
        final_timeout_override_count = 0
        final_timeout_outer_override_count = 0
        soft_timeout_override_count = 0

        async def exec_with_verifier_prep_timeout(*args: Any, **kwargs: Any) -> Any:
            nonlocal override_count, final_timeout_override_count
            nonlocal soft_timeout_override_count
            if kwargs.get("timeout_sec") == 10:
                kwargs = dict(kwargs)
                kwargs["timeout_sec"] = timeout_sec
                override_count += 1
            if (
                phase == "verify"
                and final_timeout_enabled
                and _looks_like_final_verifier_exec(args, kwargs)
            ):
                current_timeout = kwargs.get("timeout_sec")
                if current_timeout != final_verifier_timeout_sec:
                    kwargs = dict(kwargs)
                    kwargs["timeout_sec"] = final_verifier_timeout_sec
                    final_timeout_override_count += 1
            if (
                phase == "soft_verify"
                and soft_timeout_enabled
                and _looks_like_final_verifier_exec(args, kwargs)
            ):
                current_timeout = kwargs.get("timeout_sec")
                if current_timeout != soft_verifier_timeout_sec:
                    kwargs = dict(kwargs)
                    kwargs["timeout_sec"] = soft_verifier_timeout_sec
                    soft_timeout_override_count += 1
            verifier_exec = _looks_like_final_verifier_exec(args, kwargs)
            try:
                completion_timeout = float(kwargs.get("timeout_sec") or 0)
            except (TypeError, ValueError):
                completion_timeout = 0
            docker_completion_poll = (
                verifier_exec
                and hasattr(env, "_run_docker_compose_command")
                and completion_timeout > 0
            )
            if not docker_completion_poll:
                return await original_exec(*args, **kwargs)

            command = kwargs.get("command")
            positional_command = command is None and bool(args)
            if command is None and positional_command:
                command = args[0]
            if not isinstance(command, str):
                return await original_exec(*args, **kwargs)

            call_kwargs = dict(kwargs)
            call_kwargs.pop("command", None)
            call_args = args[1:] if positional_command else args

            prerequisites["benchflow_verifier_completion_poll_enabled"] = True
            compose_fn = getattr(env, "_run_docker_compose_command", None)
            status_reader_fn = None
            if callable(compose_fn):
                async def status_reader_fn(
                    status_path: str,
                    service: str,
                    remaining: float,
                ) -> bytes | None:
                    return await read_container_file_via_compose_copy(
                        compose_fn,
                        status_path,
                        service=service,
                        timeout_sec=remaining,
                    )

                prerequisites["benchflow_verifier_completion_poll_reader"] = (
                    "compose_copy"
                )
            else:
                prerequisites["benchflow_verifier_completion_poll_reader"] = (
                    "exec_stdout"
                )
            if isinstance(trace, dict):
                trace["benchflow_verifier_completion_poll_enabled"] = True
                trace["benchflow_verifier_completion_poll_reader"] = prerequisites[
                    "benchflow_verifier_completion_poll_reader"
                ]

            try:
                return await run_container_command_with_exit_status(
                    original_exec,
                    command,
                    timeout_sec=completion_timeout,
                    exec_args=call_args,
                    exec_kwargs=call_kwargs,
                    status_reader_fn=status_reader_fn,
                )
            except asyncio.TimeoutError:
                prerequisites[
                    "benchflow_verifier_completion_poll_timeout_triggered"
                ] = True
                if isinstance(trace, dict):
                    trace[
                        "benchflow_verifier_completion_poll_timeout_triggered"
                    ] = True
                raise

        phase_timeout_sec = 0
        if phase == "verify" and final_timeout_enabled:
            phase_timeout_sec = final_verifier_timeout_sec
        elif phase == "soft_verify" and soft_timeout_enabled:
            phase_timeout_sec = soft_verifier_timeout_sec

        task_verifier_config = None
        original_task_verifier_timeout_sec = None
        task_verifier_timeout_overridden = False
        if phase == "verify" and final_timeout_enabled:
            task = getattr(self, "_task", None)
            task_config = getattr(task, "config", None)
            task_verifier_config = getattr(task_config, "verifier", None)
            original_task_verifier_timeout_sec = getattr(
                task_verifier_config,
                "timeout_sec",
                None,
            )
            if original_task_verifier_timeout_sec != final_verifier_timeout_sec:
                try:
                    setattr(
                        task_verifier_config,
                        "timeout_sec",
                        final_verifier_timeout_sec,
                    )
                    task_verifier_timeout_overridden = True
                    final_timeout_outer_override_count += 1
                except Exception:
                    task_verifier_config = None

        try:
            env.exec = exec_with_verifier_prep_timeout
            if phase_timeout_sec > 0:
                result = await asyncio.wait_for(
                    original(self),
                    timeout=phase_timeout_sec,
                )
            else:
                result = await original(self)
            if phase == "soft_verify" and soft_timeout_enabled:
                cleanup_benchflow_soft_verify_timeout_children(
                    plan,
                    trace=trace,
                    metric_prefix=(
                        "benchflow_intermediate_soft_verify_orphan_cleanup"
                    ),
                    schema_version=(
                        "skillsbench_soft_verify_orphan_process_cleanup_v0"
                    ),
                )
            return result
        except Exception as exc:
            timeout_exc = _runner_exception_indicates_timeout(exc)
            if (
                phase == "verify"
                and final_timeout_enabled
                and timeout_exc
            ):
                prerequisites["benchflow_final_verifier_timeout_triggered"] = True
                prerequisites["benchflow_final_verifier_timeout_raw_output_recorded"] = (
                    False
                )
                if isinstance(trace, dict):
                    trace["benchflow_final_verifier_timeout_triggered"] = True
                    trace["benchflow_final_verifier_timeout_raw_output_recorded"] = (
                        False
                    )
            if (
                phase == "soft_verify"
                and soft_timeout_enabled
                and timeout_exc
            ):
                prerequisites[
                    "benchflow_intermediate_soft_verify_timeout_triggered"
                ] = True
                prerequisites[
                    "benchflow_intermediate_soft_verify_timeout_stage"
                ] = "soft_verify"
                prerequisites[
                    "benchflow_intermediate_soft_verify_timeout_raw_output_recorded"
                ] = False
                if isinstance(trace, dict):
                    trace[
                        "benchflow_intermediate_soft_verify_timeout_triggered"
                    ] = True
                    trace[
                        "benchflow_intermediate_soft_verify_timeout_stage"
                    ] = "soft_verify"
                    trace[
                        "benchflow_intermediate_soft_verify_timeout_raw_output_recorded"
                    ] = False
                cleanup_benchflow_soft_verify_timeout_children(
                    plan,
                    trace=trace,
                )
            raise
        finally:
            env.exec = original_exec
            if task_verifier_timeout_overridden and task_verifier_config is not None:
                try:
                    setattr(
                        task_verifier_config,
                        "timeout_sec",
                        original_task_verifier_timeout_sec,
                    )
                except Exception:
                    pass
            phase_key = f"benchflow_{phase}_prep_timeout_override_count"
            total_key = "benchflow_verifier_prep_timeout_override_count"
            prerequisites[phase_key] = (
                int(prerequisites.get(phase_key) or 0) + override_count
            )
            prerequisites[total_key] = (
                int(prerequisites.get(total_key) or 0) + override_count
            )
            if isinstance(trace, dict):
                trace[phase_key] = int(trace.get(phase_key) or 0) + override_count
                trace[total_key] = int(trace.get(total_key) or 0) + override_count
            if final_timeout_override_count:
                count_key = "benchflow_final_verifier_timeout_override_count"
                prerequisites[count_key] = (
                    int(prerequisites.get(count_key) or 0)
                    + final_timeout_override_count
                )
                if isinstance(trace, dict):
                    trace[count_key] = (
                        int(trace.get(count_key) or 0)
                        + final_timeout_override_count
                    )
            if final_timeout_outer_override_count:
                count_key = (
                    "benchflow_final_verifier_outer_timeout_override_count"
                )
                prerequisites[count_key] = (
                    int(prerequisites.get(count_key) or 0)
                    + final_timeout_outer_override_count
                )
                if isinstance(trace, dict):
                    trace[count_key] = (
                        int(trace.get(count_key) or 0)
                        + final_timeout_outer_override_count
                    )
            if soft_timeout_override_count:
                count_key = (
                    "benchflow_intermediate_soft_verify_timeout_override_count"
                )
                prerequisites[count_key] = (
                    int(prerequisites.get(count_key) or 0)
                    + soft_timeout_override_count
                )
                if isinstance(trace, dict):
                    trace[count_key] = (
                        int(trace.get(count_key) or 0)
                        + soft_timeout_override_count
                    )

    async def verify_with_prep_timeout_override(self: Any) -> Any:
        return await _run_with_override(self, "verify", original_verify)

    async def soft_verify_with_prep_timeout_override(self: Any) -> Any:
        return await _run_with_override(self, "soft_verify", original_soft_verify)

    rollout_cls.verify = verify_with_prep_timeout_override
    rollout_cls.soft_verify = soft_verify_with_prep_timeout_override
    return original_verify, original_soft_verify


def _mark_user_loop_final_verify_recovery(
    *,
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
    stage: str,
    round_num: int,
    exception: Exception,
    delta_events: int,
    delta_tool_calls: int,
) -> None:
    prerequisites = plan.setdefault("runner_prerequisites", {})
    prerequisites["benchflow_user_loop_final_verify_recovery_enabled"] = True
    prerequisites["benchflow_user_loop_final_verify_recovery_triggered"] = True
    prerequisites["benchflow_user_loop_recovery_after_agent_activity"] = True
    prerequisites["benchflow_user_loop_recovery_preserved_final_verify"] = True
    prerequisites["benchflow_user_loop_recovery_raw_error_recorded"] = False
    prerequisites["benchflow_user_loop_recovery_stage"] = stage
    prerequisites["benchflow_user_loop_recovery_exception_type"] = type(
        exception
    ).__name__
    prerequisites["benchflow_user_loop_recovery_round"] = round_num
    prerequisites["benchflow_user_loop_recovery_delta_events"] = max(0, delta_events)
    prerequisites["benchflow_user_loop_recovery_delta_tool_calls"] = max(
        0,
        delta_tool_calls,
    )
    if isinstance(trace, dict):
        trace["benchflow_user_loop_final_verify_recovery_enabled"] = True
        trace["benchflow_user_loop_final_verify_recovery_triggered"] = True
        trace["benchflow_user_loop_recovery_after_agent_activity"] = True
        trace["benchflow_user_loop_recovery_preserved_final_verify"] = True
        trace["benchflow_user_loop_recovery_raw_error_recorded"] = False
        trace["benchflow_user_loop_recovery_stage"] = stage
        trace["benchflow_user_loop_recovery_exception_type"] = type(exception).__name__
        trace["benchflow_user_loop_recovery_round"] = round_num
        trace["benchflow_user_loop_recovery_delta_events"] = max(0, delta_events)
        trace["benchflow_user_loop_recovery_delta_tool_calls"] = max(
            0,
            delta_tool_calls,
        )
        trace["last_decision"] = "break_after_agent_round_preserve_final_verify"


def _mark_user_loop_soft_verify_exception_continuation(
    *,
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
    round_num: int,
    exception: Exception,
    delta_events: int,
    delta_tool_calls: int,
) -> None:
    prerequisites = plan.setdefault("runner_prerequisites", {})
    fields: dict[str, Any] = {
        "benchflow_user_loop_soft_verify_exception_continued": True,
        "benchflow_user_loop_soft_verify_exception_raw_error_recorded": False,
        "benchflow_user_loop_soft_verify_exception_stage": "soft_verify",
        "benchflow_user_loop_soft_verify_exception_type": type(exception).__name__,
        "benchflow_user_loop_soft_verify_exception_round": round_num,
        "benchflow_user_loop_soft_verify_exception_delta_events": max(
            0,
            delta_events,
        ),
        "benchflow_user_loop_soft_verify_exception_delta_tool_calls": max(
            0,
            delta_tool_calls,
        ),
    }
    current = prerequisites.get("benchflow_user_loop_soft_verify_exception_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    fields["benchflow_user_loop_soft_verify_exception_count"] = current + 1
    prerequisites.update(fields)
    if isinstance(trace, dict):
        trace_current = trace.get("benchflow_user_loop_soft_verify_exception_count")
        if not isinstance(trace_current, int) or isinstance(trace_current, bool):
            trace_current = 0
        trace_fields = dict(fields)
        trace_fields["benchflow_user_loop_soft_verify_exception_count"] = (
            trace_current + 1
        )
        trace.update(trace_fields)


def _mark_user_loop_no_tool_exception_continuation(
    *,
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
    round_num: int,
    exception: Exception,
    delta_events: int,
) -> None:
    prerequisites = plan.setdefault("runner_prerequisites", {})
    fields: dict[str, Any] = {
        "benchflow_user_loop_no_tool_exception_continued": True,
        "benchflow_user_loop_no_tool_exception_raw_error_recorded": False,
        "benchflow_user_loop_no_tool_exception_stage": "agent_execute",
        "benchflow_user_loop_no_tool_exception_type": type(exception).__name__,
        "benchflow_user_loop_no_tool_exception_round": round_num,
        "benchflow_user_loop_no_tool_exception_delta_events": max(0, delta_events),
        "benchflow_user_loop_no_tool_exception_delta_tool_calls": 0,
    }
    current = prerequisites.get("benchflow_user_loop_no_tool_exception_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    fields["benchflow_user_loop_no_tool_exception_count"] = current + 1
    prerequisites.update(fields)
    if isinstance(trace, dict):
        trace_current = trace.get("benchflow_user_loop_no_tool_exception_count")
        if not isinstance(trace_current, int) or isinstance(trace_current, bool):
            trace_current = 0
        trace_fields = dict(fields)
        trace_fields["benchflow_user_loop_no_tool_exception_count"] = (
            trace_current + 1
        )
        trace.update(trace_fields)
        trace["last_decision"] = "continue_after_agent_execute_no_tool_exception"


def install_benchflow_user_loop_final_verify_recovery(
    rollout_cls: Any,
    *,
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
    intermediate_soft_verify_policy: str = "every-round",
) -> Any:
    """Keep final official verify reachable after post-agent loop failures."""

    original_user_loop = rollout_cls._run_user_loop
    prerequisites = plan.setdefault("runner_prerequisites", {})
    prerequisites["benchflow_user_loop_final_verify_recovery_enabled"] = True
    if intermediate_soft_verify_policy not in {"every-round", "final-only"}:
        raise ValueError(
            "intermediate_soft_verify_policy must be 'every-round' or 'final-only'"
        )
    final_only_soft_verify = intermediate_soft_verify_policy == "final-only"
    for target in (prerequisites, trace if isinstance(trace, dict) else None):
        if target is None:
            continue
        target["benchflow_intermediate_soft_verify_policy"] = (
            intermediate_soft_verify_policy
        )
        target["benchflow_intermediate_soft_verify_final_only"] = (
            final_only_soft_verify
        )
        target["benchflow_intermediate_soft_verify_raw_output_recorded"] = False
        target.setdefault("benchflow_intermediate_soft_verify_call_count", 0)
        target.setdefault("benchflow_intermediate_soft_verify_skipped_count", 0)

    def record_soft_verify_counter(key: str) -> None:
        _inc_counter(prerequisites, key)
        if isinstance(trace, dict):
            _inc_counter(trace, key)

    async def run_user_loop_with_final_verify_recovery(self: Any) -> None:
        from benchflow.sandbox.user import RoundResult

        cfg = self._config
        user = cfg.user
        assert user is not None

        if len(cfg.effective_scenes) > 1:
            raise ValueError(
                "User-driven loops operate on a single scene. "
                f"Got {len(cfg.effective_scenes)} scenes."
            )
        scene = cfg.effective_scenes[0]
        if len(scene.roles) != 1:
            raise ValueError(
                "User-driven loops require a single-role scene. "
                f"Got {len(scene.roles)} roles."
            )
        role = scene.roles[0]

        instruction = (
            self._resolved_prompts[0]
            if self._resolved_prompts
            else ("Solve the task described in /app/instruction.md")
        )

        solution: str | None = None
        if cfg.oracle_access:
            cat = await self._env.exec(
                "cat /solution/solve.sh 2>/dev/null || true",
                user="root",
                timeout_sec=10,
            )
            solution = (cat.stdout or "").strip() or None

        await user.setup(instruction, solution)

        if cfg.oracle_access:
            await self._env.exec(
                "mv /solution /solution_oracle_backup 2>/dev/null || true",
                user="root",
                timeout_sec=10,
            )

        round_result: Any | None = None
        rounds_log: list[dict[str, Any]] = []

        for round_num in range(cfg.max_user_rounds):
            try:
                prompt = await user.run(round_num, instruction, round_result)
            except Exception as exc:
                self._error = f"user.run() failed at round {round_num}: {exc}"
                logging.getLogger(__name__).error(self._error, exc_info=True)
                break

            if prompt is None:
                logging.getLogger(__name__).info(
                    "[User] stopped at round %s",
                    round_num,
                )
                break

            logging.getLogger(__name__).info(
                "[User] round %s: prompt=%r...",
                round_num,
                prompt[:80],
            )

            traj_before = len(self._trajectory)
            connected = False
            try:
                await self.connect_as(role)
                connected = True
                await self.execute(prompts=[prompt])
            except Exception as exc:
                delta_events = max(0, len(self._trajectory) - traj_before)
                round_trajectory = self._trajectory[traj_before:]
                delta_tool_calls = sum(
                    1
                    for event in round_trajectory
                    if isinstance(event, dict) and event.get("type") == "tool_call"
                )
                if (not connected) or delta_events <= 0:
                    raise
                if delta_tool_calls <= 0 and round_num + 1 < cfg.max_user_rounds:
                    _mark_user_loop_no_tool_exception_continuation(
                        plan=plan,
                        trace=trace,
                        round_num=round_num,
                        exception=exc,
                        delta_events=delta_events,
                    )
                    round_result = RoundResult(
                        round=round_num,
                        trajectory=round_trajectory,
                        rewards=None,
                        verifier_output=None,
                        verifier_error=(
                            "public_safe_agent_execute_exception_before_tool_activity"
                        ),
                        n_tool_calls=0,
                    )
                    rounds_log.append(
                        {
                            "round": round_num,
                            "rewards": None,
                            "verifier_error": (
                                "public_safe_agent_execute_exception_before_tool_activity"
                            ),
                            "n_tool_calls": 0,
                            "n_trajectory_events": delta_events,
                        }
                    )
                    continue
                _mark_user_loop_final_verify_recovery(
                    plan=plan,
                    trace=trace,
                    stage="agent_execute",
                    round_num=round_num,
                    exception=exc,
                    delta_events=delta_events,
                    delta_tool_calls=delta_tool_calls,
                )
                rounds_log.append(
                    {
                        "round": round_num,
                        "rewards": None,
                        "verifier_error": "public_safe_agent_execute_exception_after_activity",
                        "n_tool_calls": delta_tool_calls,
                        "n_trajectory_events": delta_events,
                    }
                )
                break
            finally:
                await self.disconnect()

            round_trajectory = self._trajectory[traj_before:]
            round_tools = sum(
                1
                for event in round_trajectory
                if isinstance(event, dict) and event.get("type") == "tool_call"
            )

            if cfg.oracle_access:
                await self._env.exec(
                    "mv /solution_oracle_backup /solution 2>/dev/null || true",
                    user="root",
                    timeout_sec=10,
                )
            soft_verify_skipped = False
            try:
                if final_only_soft_verify:
                    soft_verify_skipped = True
                    record_soft_verify_counter(
                        "benchflow_intermediate_soft_verify_skipped_count"
                    )
                    rewards = None
                    verifier_output = None
                    verifier_error = None
                else:
                    record_soft_verify_counter(
                        "benchflow_intermediate_soft_verify_call_count"
                    )
                    rewards, verifier_output, verifier_error = await self.soft_verify()
            except Exception as exc:
                _mark_user_loop_soft_verify_exception_continuation(
                    plan=plan,
                    trace=trace,
                    round_num=round_num,
                    exception=exc,
                    delta_events=len(round_trajectory),
                    delta_tool_calls=round_tools,
                )
                rewards = None
                verifier_output = None
                verifier_error = "public_safe_soft_verify_exception_after_agent_round"
                soft_verify_skipped = False
            finally:
                if cfg.oracle_access:
                    await self._env.exec(
                        "mv /solution /solution_oracle_backup 2>/dev/null || true",
                        user="root",
                        timeout_sec=10,
                    )

            round_result = RoundResult(
                round=round_num,
                trajectory=round_trajectory,
                rewards=rewards,
                verifier_output=verifier_output,
                verifier_error=verifier_error,
                n_tool_calls=round_tools,
            )

            rounds_log.append(
                {
                    "round": round_num,
                    "prompt": prompt,
                    "rewards": rewards,
                    "verifier_error": verifier_error,
                    "soft_verify_policy": intermediate_soft_verify_policy,
                    "soft_verify_skipped": soft_verify_skipped,
                    "n_tool_calls": round_tools,
                    "n_trajectory_events": len(round_trajectory),
                }
            )

        if rounds_log and self._rollout_dir:
            log_path = self._rollout_dir / "user_rounds.jsonl"
            with log_path.open("w") as handle:
                for entry in rounds_log:
                    handle.write(json.dumps(entry) + "\n")

    rollout_cls._run_user_loop = run_user_loop_with_final_verify_recovery
    return original_user_loop


def _runner_prerequisite_failure_attribution(
    value: Any,
) -> tuple[str, str, list[str]] | None:
    """Classify runner failures from structured prereq state, not raw stderr."""

    if not isinstance(value, dict):
        return None

    def count(key: str) -> int:
        raw = value.get(key)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return max(0, raw)
        return 0

    orchestrated_driver_lifecycle_satisfied = bool(
        value.get("remote_command_file_bridge_driver_lifecycle_execution_style")
        == BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE
        and count("remote_command_file_bridge_driver_lifecycle_checkpoint_count") > 0
        and count("remote_command_file_bridge_driver_lifecycle_success_count") > 0
        and count("remote_command_file_bridge_driver_lifecycle_failure_count") == 0
        and count("remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count")
        > 0
        and count("remote_command_file_bridge_driver_lifecycle_loopx_state_read_count")
        > 0
        and count("remote_command_file_bridge_driver_lifecycle_loopx_state_write_count")
        > 0
    )
    orchestrated_driver_counts_as_product_mode = bool(
        orchestrated_driver_lifecycle_satisfied
        and (
            value.get("remote_command_file_bridge_agent_operation_trace_required")
            is not True
            or (
                value.get("remote_command_file_bridge_agent_command_instrumented")
                is True
                and value.get(
                    "remote_command_file_bridge_agent_operation_trace_satisfied"
                )
                is True
            )
        )
    )

    if (
        value.get("benchflow_setup_stall_timeout_triggered") is True
        and value.get("benchflow_setup_stall_before_agent_lifecycle") is True
    ):
        label = "skillsbench_docker_compose_build_stall_timeout"
        return label, label, [
            label,
            "skillsbench_docker_compose_setup_failure",
            "skillsbench_environment_setup_error",
        ]

    if value.get("runner_interrupted_before_official_result") is True:
        label = "skillsbench_runner_interrupted_before_official_result"
        return label, label, [
            label,
            "skillsbench_compact_closeout_recorded",
            "skillsbench_runner_error",
        ]

    if value.get("benchflow_verifier_completion_poll_timeout_triggered") is True:
        label = "skillsbench_verifier_completion_timeout"
        return label, label, [
            label,
            "skillsbench_verifier_timeout",
            "skillsbench_runner_error",
        ]

    if value.get("benchflow_final_verifier_timeout_triggered") is True:
        label = "skillsbench_final_verifier_timeout"
        return label, label, [
            label,
            "skillsbench_verifier_timeout",
            "skillsbench_runner_error",
        ]

    if value.get("benchflow_intermediate_soft_verify_timeout_triggered") is True:
        label = "skillsbench_intermediate_soft_verify_timeout"
        return label, label, [
            label,
            "skillsbench_verifier_timeout",
            "skillsbench_runner_error",
        ]

    if (
        value.get("preinstalled_benchflow_agent_runtime_required") is True
        and value.get("benchflow_agent_runtime_layer_ready") is False
    ):
        label = "skillsbench_preinstalled_benchflow_agent_runtime_missing"
        return label, label, [label, "skillsbench_runner_setup_error"]

    if (
        value.get("codex_acp_runtime_launch_preflight") is False
        and value.get("codex_acp_runtime_launch_preflight_status") == "failed"
    ):
        label = "skillsbench_codex_acp_launch_preflight_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]

    if (
        value.get("codex_acp_runtime_dependency_preflight") is False
        and value.get("codex_acp_runtime_launch_preflight_status") == "failed"
    ):
        label = "skillsbench_codex_acp_runtime_dependency_preflight_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]

    codex_preflight_failure = codex_runtime.failure_attribution(value)
    if codex_preflight_failure:
        return codex_preflight_failure

    if value.get("host_local_acp_launch_status") == "failed":
        label = "skillsbench_host_local_acp_launch_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]

    if value.get("host_local_acp_codex_exec_preflight_status") == "failed":
        category = str(value.get("host_local_acp_codex_exec_failure_category") or "")
        label = "skillsbench_host_local_acp_codex_exec_preflight_failed"
        if category:
            label = f"{label}_{category}"
        return label, label, [label, "skillsbench_runner_setup_error"]

    if (
        value.get("remote_command_file_bridge_agent_operation_trace_required") is True
        and not orchestrated_driver_counts_as_product_mode
        and value.get("remote_command_file_bridge_agent_operation_trace_satisfied")
        is False
    ):
        status = str(
            value.get("remote_command_file_bridge_agent_operation_trace_status") or ""
        )
        if (
            status == "relay_generated_wrapper_pending_prompt"
            and value.get("remote_command_file_bridge_consumption_status")
            == "sandbox_bridge_auto_wiring_pending"
        ):
            return None
        trace_count = value.get("remote_command_file_bridge_agent_operation_trace_count")
        request_count = value.get("remote_command_file_bridge_agent_request_count")
        if status == "agent_operation_trace_recorded_no_success":
            category = "bridge_operation_failed"
            counts = value.get("remote_command_file_bridge_agent_failure_category_counts")
            if isinstance(counts, dict):
                for key, count_value in sorted(counts.items()):
                    if (
                        isinstance(key, str)
                        and key
                        and isinstance(count_value, int)
                        and count_value > 0
                    ):
                        category = key[:80]
                        break
            label = f"skillsbench_remote_bridge_agent_operation_failed_{category}"
            return (
                label,
                label,
                [
                    label,
                    "skillsbench_product_mode_uncountable_treatment",
                    "skillsbench_runner_setup_error",
                ],
            )
        if (
            status == "agent_operation_trace_present_no_requests"
            or (
                isinstance(trace_count, int)
                and not isinstance(trace_count, bool)
                and trace_count > 0
                and (
                    not isinstance(request_count, int)
                    or isinstance(request_count, bool)
                    or request_count <= 0
                )
            )
        ):
            label = "skillsbench_remote_bridge_agent_no_requests"
            return (
                label,
                label,
                [
                    label,
                    "skillsbench_product_mode_uncountable_treatment",
                    "skillsbench_product_mode_lifecycle_missing",
                ],
            )
        label = "skillsbench_remote_bridge_agent_operation_trace_missing"
        return (
            label,
            label,
            [
                label,
                "skillsbench_product_mode_uncountable_treatment",
                "skillsbench_runner_setup_error",
            ],
        )

    if value.get("host_local_acp_codex_exec_failure_trace_present") is True:
        category = str(value.get("host_local_acp_codex_exec_failure_category") or "")
        label = "skillsbench_host_local_acp_codex_exec_failed"
        if category:
            label = f"{label}_{category}"
        return (
            label,
            label,
            [
                label,
                "skillsbench_host_local_acp_codex_exec_failed",
                "skillsbench_runner_setup_error",
            ],
        )

    if value.get("host_local_acp_launch_status") == "sandbox_install_failed":
        label = "skillsbench_host_local_acp_sandbox_install_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]

    if value.get("host_local_acp_launch_status") == "installing_sandbox":
        label = "skillsbench_host_local_acp_sandbox_install_incomplete"
        return label, label, [label, "skillsbench_runner_setup_error"]

    if (
        value.get("codex_acp_runtime_container_bootstrap") is True
        and value.get("codex_acp_runtime_dependency_preflight") is True
        and value.get("codex_acp_runtime_launch_preflight") is False
        and value.get("codex_acp_runtime_launch_preflight_stage")
        == "after_agent_install_before_acp_connect"
        and value.get("codex_acp_runtime_launch_preflight_status") == "pending"
    ):
        label = "skillsbench_runner_failed_before_agent_install"
        return label, label, [label, "skillsbench_runner_setup_error"]

    return None


def _agent_lifecycle_observed_for_setup_stall(plan: dict[str, Any]) -> bool:
    prerequisites = plan.get("runner_prerequisites")
    if not isinstance(prerequisites, dict):
        prerequisites = {}

    if prerequisites.get("benchflow_agent_install_started") is True:
        return True
    launch_status = str(
        prerequisites.get("codex_acp_runtime_launch_preflight_status") or ""
    )
    if launch_status not in {"", "pending", "not_requested"}:
        return True
    host_status = str(prerequisites.get("host_local_acp_launch_status") or "")
    if host_status not in {"", "pending", "not_requested"}:
        return True

    controller_trace = plan.get("controller_trace")
    if not isinstance(controller_trace, dict):
        return False
    return bool(
        controller_trace.get("case_goal_state_initialized_before_agent")
        or controller_trace.get("case_goal_state_init_rc") is not None
        or int(controller_trace.get("initial_prompt_count") or 0) > 0
        or int(controller_trace.get("heartbeat_count") or 0) > 0
        or int(controller_trace.get("controller_action_decisions") or 0) > 0
        or int(controller_trace.get("private_trajectory_round_count") or 0) > 0
        or int(controller_trace.get("loopx_cli_call_count") or 0) > 0
    )


def _runner_exception_indicates_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return "timeout" in text or "timed out" in text


def _runner_exception_indicates_interruption(exc: BaseException) -> bool:
    return isinstance(exc, (KeyboardInterrupt, SkillsBenchRunnerInterrupted))


def _ensure_runner_interruption_prerequisites(
    plan: dict[str, Any],
    exc: BaseException,
) -> None:
    if not _runner_exception_indicates_interruption(exc):
        return

    raw_prerequisites = plan.setdefault("runner_prerequisites", {})
    kind = (
        "sigterm"
        if isinstance(exc, SkillsBenchRunnerInterrupted)
        else "keyboard_interrupt"
    )
    raw_prerequisites.setdefault(
        "benchflow_run_stage", "interrupted_before_official_result"
    )
    raw_prerequisites.setdefault("runner_interrupted_before_official_result", True)
    raw_prerequisites.setdefault("runner_interruption_kind", kind)
    raw_prerequisites.setdefault(
        "runner_interruption_status", "compact_closeout_required"
    )
    raw_prerequisites.setdefault(
        "runner_interruption_compact_closeout_expected", True
    )
    raw_prerequisites.setdefault("runner_interruption_raw_material_recorded", False)


def _ensure_setup_stall_timeout_prerequisites(
    args: argparse.Namespace,
    plan: dict[str, Any],
    exc: BaseException,
    *,
    cleanup_if_missing: bool,
) -> None:
    """Backfill public setup-stall evidence when BenchFlow times out pre-agent."""

    requested_build_stall_timeout_sec = _requested_build_stall_timeout_sec(args)
    build_stall_timeout_sec = _effective_build_stall_timeout_sec(args)
    if build_stall_timeout_sec <= 0:
        return
    if not _runner_exception_indicates_timeout(exc):
        return
    if _agent_lifecycle_observed_for_setup_stall(plan):
        return

    raw_prerequisites = plan.setdefault("runner_prerequisites", {})
    raw_prerequisites.setdefault(
        "benchflow_run_stage", "build_or_setup_stall_before_agent"
    )
    raw_prerequisites.setdefault("benchflow_setup_stall_timeout_enabled", True)
    raw_prerequisites.setdefault(
        "benchflow_setup_stall_timeout_requested_sec",
        requested_build_stall_timeout_sec,
    )
    raw_prerequisites.setdefault(
        "benchflow_setup_stall_timeout_sec", build_stall_timeout_sec
    )
    raw_prerequisites.setdefault("benchflow_setup_stall_timeout_triggered", True)
    raw_prerequisites.setdefault(
        "benchflow_setup_stall_before_agent_lifecycle", True
    )
    raw_prerequisites.setdefault("benchflow_setup_stall_raw_logs_read", False)
    if cleanup_if_missing and not raw_prerequisites.get(
        "benchflow_setup_stall_cleanup_requested"
    ):
        cleanup_benchflow_setup_stall_children(plan)


def _apply_agent_message_only_no_tool_calls_attribution(
    compact: dict[str, Any],
) -> bool:
    counters = compact.get("interaction_counters")
    if not isinstance(counters, dict):
        return False

    event_count = counters.get("private_trajectory_event_count")
    round_count = counters.get("private_trajectory_round_count")
    tool_count = counters.get("private_trajectory_tool_call_count")
    controller_decisions = counters.get("controller_action_decisions")
    if not (
        isinstance(event_count, int)
        and event_count > 0
        and isinstance(round_count, int)
        and round_count > 0
        and tool_count == 0
        and isinstance(controller_decisions, int)
        and controller_decisions > 0
    ):
        return False

    bridge_request_count = counters.get(
        "remote_command_file_bridge_agent_request_count"
    )
    bridge_task_facing_count = counters.get(
        "remote_command_file_bridge_agent_task_facing_operation_count"
    )
    bridge_progress_status = str(
        counters.get("host_local_acp_bridge_progress_status") or ""
    )
    if (
        (
            isinstance(bridge_request_count, int)
            and not isinstance(bridge_request_count, bool)
            and bridge_request_count > 0
        )
        or (
            isinstance(bridge_task_facing_count, int)
            and not isinstance(bridge_task_facing_count, bool)
            and bridge_task_facing_count > 0
        )
        or bridge_progress_status.startswith("bridge_")
    ):
        return False

    label = "skillsbench_acp_agent_message_only_no_tool_calls"
    current_attribution = str(compact.get("score_failure_attribution") or "")
    preserve_attributions = {
        "skillsbench_codex_acp_provider_zero_activity",
    }
    preserve_current_attribution = (
        current_attribution in preserve_attributions
        or current_attribution.startswith(
            "skillsbench_host_local_acp_codex_exec_failed"
        )
    )
    if not preserve_current_attribution:
        compact["score_failure_attribution"] = label
        compact.setdefault("first_blocker", label)
    elif not compact.get("first_blocker"):
        compact["first_blocker"] = current_attribution
    existing_labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str)
    ]
    extra_labels = [label]
    if not preserve_current_attribution:
        extra_labels.append("skillsbench_agent_behavior_gap")
    for item in extra_labels:
        if item not in existing_labels:
            existing_labels.append(item)
        compact["failure_attribution_labels"] = existing_labels
    return True


def _apply_host_local_acp_prereq_failure_attribution(
    compact: dict[str, Any],
    runner_prerequisites: dict[str, Any],
) -> bool:
    """Prefer host Codex failures unless a completed verifier score is usable."""

    official_score = compact.get("official_score")
    validation = compact.get("validation")
    counters = compact.get("interaction_counters")
    task_activity_count = 0
    if isinstance(counters, dict):
        for key in (
            "remote_command_file_bridge_agent_task_facing_operation_count",
            "remote_command_file_bridge_agent_task_facing_success_count",
        ):
            value = counters.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                task_activity_count = max(task_activity_count, value)
    if (
        isinstance(official_score, (int, float))
        and not isinstance(official_score, bool)
        and compact.get("official_score_status") == "completed"
        and isinstance(validation, dict)
        and validation.get("official_verifier_validation_present") is True
        and validation.get("official_verifier_status") in {"completed", "passed"}
        and task_activity_count > 0
    ):
        return False

    prereq_failure = _runner_prerequisite_failure_attribution(runner_prerequisites)
    if prereq_failure is None:
        return False
    _exception_type, label, labels = prereq_failure
    if not (
        label.startswith("skillsbench_host_local_acp_codex_exec_failed")
        or label.startswith("skillsbench_host_local_acp_codex_exec_preflight_failed")
    ):
        return False

    compact["score_failure_attribution"] = label
    compact["first_blocker"] = label
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False
    existing_labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str)
        and item
        not in {
            "official_score_zero_case_failure",
            "official_verifier_solution_failure",
            "verifier_infrastructure_failure",
        }
    ]
    extra_labels = list(labels)
    if compact.get("product_mode") is True:
        extra_labels.append("skillsbench_product_mode_transport_failure")
    for item in extra_labels:
        if item and item not in existing_labels:
            existing_labels.append(item)
    compact["failure_attribution_labels"] = existing_labels
    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["exception_type"] = label
        runner_failure["failure_class"] = label
    attempt_accounting = compact.get("attempt_accounting")
    if isinstance(attempt_accounting, dict):
        attempt_accounting["failure_class"] = "job_materialization_failed"
        attempt_accounting["failure_label"] = label
        attempt_accounting["lifecycle_phase"] = "runner_accepted_args"
        for key in (
            "case_attempt_countable",
            "solver_attempt_countable",
            "verifier_attempt_countable",
            "official_score_attempt_countable",
        ):
            attempt_accounting[key] = False
        attempts = attempt_accounting.get("attempts")
        if isinstance(attempts, dict):
            for key in ("case", "solver", "verifier", "official_score"):
                attempt = attempts.get(key)
                if isinstance(attempt, dict):
                    attempt["countable"] = False
    return True


def _apply_native_goal_worker_finish_guard_attribution(
    compact: dict[str, Any],
) -> bool:
    official_score = compact.get("official_score")
    if (
        isinstance(official_score, (int, float))
        and not isinstance(official_score, bool)
        and official_score >= 1.0
    ):
        return False
    counters = compact.get("interaction_counters")
    if not isinstance(counters, dict):
        return False
    worker_contract = compact.get("native_goal_worker_contract")
    if not isinstance(worker_contract, dict):
        worker_contract = {}
    if counters.get("native_goal_worker_route") is not True:
        return False
    incomplete_count = counters.get(
        "native_goal_worker_incomplete_after_completion_event_count"
    )
    if not isinstance(incomplete_count, int) or isinstance(incomplete_count, bool):
        incomplete_count = worker_contract.get(
            "incomplete_after_completion_event_count"
        )
    if not (
        isinstance(incomplete_count, int)
        and not isinstance(incomplete_count, bool)
        and incomplete_count > 0
    ):
        return False
    task_ops = counters.get(
        "remote_command_file_bridge_agent_task_facing_operation_count"
    )
    task_success = counters.get(
        "remote_command_file_bridge_agent_task_facing_success_count"
    )
    if (
        isinstance(task_ops, int)
        and not isinstance(task_ops, bool)
        and task_ops > 0
    ) or (
        isinstance(task_success, int)
        and not isinstance(task_success, bool)
        and task_success > 0
    ):
        return False

    label = "skillsbench_native_goal_worker_incomplete_turn_without_task_activity"
    compact["score_failure_attribution"] = label
    compact["first_blocker"] = label
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False
    existing_labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str)
        and item
        not in {
            "official_score_zero_case_failure",
            "official_verifier_solution_failure",
            "verifier_infrastructure_failure",
        }
    ]
    for item in (label, "skillsbench_runner_setup_error"):
        if item not in existing_labels:
            existing_labels.append(item)
    compact["failure_attribution_labels"] = existing_labels
    runner_failure = compact.setdefault("runner_failure", {})
    if isinstance(runner_failure, dict):
        runner_failure["exception_type"] = label
        runner_failure["failure_class"] = label
        runner_failure["native_goal_worker"] = {
            "failure_category": label,
            "incomplete_after_completion_event_count": incomplete_count,
            "task_facing_operation_count": max(0, int(task_ops or 0)),
            "raw_material_recorded": False,
        }
    if isinstance(worker_contract, dict):
        worker_contract["countable_baseline"] = False
        worker_contract["failure_category"] = label
        worker_contract["first_blocker"] = label
        worker_contract["countability_source"] = "native_goal_worker_finish_guard"
    attempt_accounting = compact.get("attempt_accounting")
    if isinstance(attempt_accounting, dict):
        attempt_accounting["failure_class"] = "job_materialization_failed"
        attempt_accounting["failure_label"] = label
        attempt_accounting["lifecycle_phase"] = "runner_accepted_args"
        for key in (
            "case_attempt_countable",
            "solver_attempt_countable",
            "verifier_attempt_countable",
            "official_score_attempt_countable",
        ):
            attempt_accounting[key] = False
        attempts = attempt_accounting.get("attempts")
        if isinstance(attempts, dict):
            for key in ("case", "solver", "verifier", "official_score"):
                attempt = attempts.get(key)
                if isinstance(attempt, dict):
                    attempt["countable"] = False
    return True


def _apply_codex_cli_goal_countability_guard_attribution(
    compact: dict[str, Any],
) -> bool:
    runner_config = compact.get("runner_config")
    if not isinstance(runner_config, dict):
        runner_config = {}
    route = str(compact.get("route") or runner_config.get("route") or "")
    mode = str(compact.get("mode") or "")
    if (
        route != CODEX_CLI_GOAL_BASELINE_ROUTE
        and mode != "skillsbench_codex_cli_goal_baseline"
    ):
        return False
    if compact.get("official_score_status") != "completed":
        return False

    counters = compact.get("interaction_counters")
    if not isinstance(counters, dict):
        counters = {}
    runner_prerequisites = compact.get("runner_prerequisites")
    if not isinstance(runner_prerequisites, dict):
        runner_prerequisites = {}

    def max_counter(*fields: str) -> int:
        values: list[int] = []
        for source in (counters, runner_prerequisites):
            for field in fields:
                value = source.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    values.append(max(0, value))
        return max(values, default=0)

    task_facing_count = max_counter(
        "remote_command_file_bridge_agent_task_facing_success_count",
        "remote_command_file_bridge_agent_task_facing_operation_count",
        "codex_cli_goal_tui_task_facing_success_count",
    )
    request_count = max_counter(
        "remote_command_file_bridge_agent_request_count",
        "codex_cli_goal_tui_bridge_request_count",
    )
    ok_count = max_counter("codex_cli_goal_tui_ok_count")
    trace_present = bool(
        counters.get("codex_cli_goal_tui_trace_present") is True
        or runner_prerequisites.get("codex_cli_goal_tui_trace_present") is True
    )
    goal_stage = str(
        counters.get("codex_cli_goal_tui_stage")
        or runner_prerequisites.get("codex_cli_goal_tui_stage")
        or ""
    )[:120]
    operation_trace_status = str(
        counters.get("remote_command_file_bridge_agent_operation_trace_status")
        or runner_prerequisites.get(
            "remote_command_file_bridge_agent_operation_trace_status"
        )
        or ""
    )[:120]

    missing_task_activity = task_facing_count <= 0 or request_count <= 0
    completed_task_attempt_countable = (
        not missing_task_activity
        and str(compact.get("official_score_status") or "") == "completed"
    )
    terminal_goal_failure_stages = {
        "auth_refresh_token_revoked",
        "post_bridge_tui_model_timeout",
        "post_bridge_tui_error_prompt",
        "post_bridge_tui_rate_limit",
        "task_output_quiet_timeout",
    }
    goal_failed = (
        trace_present
        and ok_count <= 0
        and (
            not completed_task_attempt_countable
            or goal_stage in terminal_goal_failure_stages
        )
    )
    if not (missing_task_activity or goal_failed):
        compact["codex_cli_goal_countability_contract"] = {
            "schema_version": "skillsbench_codex_cli_goal_countability_contract_v0",
            "required": True,
            "countable_baseline": True,
            "countability_source": (
                "official_score_completed_with_task_facing_activity"
            ),
            "failure_category": "",
            "first_blocker": "",
            "trace_present": trace_present,
            "ok_count": ok_count,
            "goal_stage": goal_stage,
            "request_count": request_count,
            "task_facing_activity_count": task_facing_count,
            "operation_trace_status": operation_trace_status,
            "raw_material_recorded": False,
        }
        return False

    label = "skillsbench_codex_cli_goal_uncountable_no_task_activity"
    if goal_stage == "auth_refresh_token_revoked":
        label = "skillsbench_codex_cli_goal_uncountable_auth_refresh_token_revoked"
    elif goal_stage == "goal_active_timeout":
        label = "skillsbench_codex_cli_goal_uncountable_goal_active_timeout"
    elif goal_stage == "pre_bridge_tui_model_timeout":
        label = "skillsbench_codex_cli_goal_uncountable_pre_bridge_model_timeout"
    elif goal_stage == "pre_bridge_tui_error_prompt":
        label = "skillsbench_codex_cli_goal_uncountable_pre_bridge_tui_error"
    elif goal_stage == "pre_bridge_tui_rate_limit":
        label = "skillsbench_codex_cli_goal_uncountable_pre_bridge_rate_limit"
    elif goal_stage == "post_bridge_tui_model_timeout":
        label = "skillsbench_codex_cli_goal_uncountable_post_bridge_model_timeout"
    elif goal_stage == "post_bridge_tui_error_prompt":
        label = "skillsbench_codex_cli_goal_uncountable_post_bridge_tui_error"
    elif goal_stage == "post_bridge_tui_rate_limit":
        label = "skillsbench_codex_cli_goal_uncountable_post_bridge_rate_limit"
    elif goal_stage == "task_output_quiet_timeout":
        label = "skillsbench_codex_cli_goal_uncountable_task_output_quiet_timeout"
    if goal_failed and not missing_task_activity:
        label = {
            "post_bridge_tui_model_timeout": (
                "skillsbench_codex_cli_goal_uncountable_post_bridge_model_timeout"
            ),
            "post_bridge_tui_error_prompt": (
                "skillsbench_codex_cli_goal_uncountable_post_bridge_tui_error"
            ),
            "post_bridge_tui_rate_limit": (
                "skillsbench_codex_cli_goal_uncountable_post_bridge_rate_limit"
            ),
            "task_output_quiet_timeout": (
                "skillsbench_codex_cli_goal_uncountable_task_output_quiet_timeout"
            ),
        }.get(goal_stage, "skillsbench_codex_cli_goal_uncountable_goal_failed")
    compact["score_failure_attribution"] = label
    compact["first_blocker"] = label
    compact["repeat_blocked_by"] = label
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False
    existing_labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str)
        and item
        not in {
            "official_score_zero_case_failure",
            "official_verifier_solution_failure",
            "verifier_infrastructure_failure",
        }
    ]
    for item in (
        label,
        "skillsbench_codex_cli_goal_uncountable_baseline",
    ):
        if item not in existing_labels:
            existing_labels.append(item)
    compact["failure_attribution_labels"] = existing_labels
    compact["codex_cli_goal_countability_contract"] = {
        "schema_version": "skillsbench_codex_cli_goal_countability_contract_v0",
        "required": True,
        "countable_baseline": False,
        "countability_source": "codex_cli_goal_countability_guard",
        "failure_category": label,
        "first_blocker": label,
        "trace_present": trace_present,
        "ok_count": ok_count,
        "goal_stage": goal_stage,
        "request_count": request_count,
        "task_facing_activity_count": task_facing_count,
        "operation_trace_status": operation_trace_status,
        "raw_material_recorded": False,
    }
    runner_failure = compact.setdefault("runner_failure", {})
    if isinstance(runner_failure, dict):
        runner_failure["exception_type"] = label
        runner_failure["failure_class"] = label
        runner_failure["codex_cli_goal"] = {
            "failure_category": label,
            "trace_present": trace_present,
            "ok_count": ok_count,
            "goal_stage": goal_stage,
            "request_count": request_count,
            "task_facing_activity_count": task_facing_count,
            "raw_material_recorded": False,
        }
    attempt_accounting = compact.get("attempt_accounting")
    if isinstance(attempt_accounting, dict):
        attempt_accounting["failure_class"] = "job_materialization_failed"
        attempt_accounting["failure_label"] = label
        attempt_accounting["lifecycle_phase"] = "runner_accepted_args"
        for key in (
            "case_attempt_countable",
            "solver_attempt_countable",
            "verifier_attempt_countable",
            "official_score_attempt_countable",
        ):
            attempt_accounting[key] = False
        attempts = attempt_accounting.get("attempts")
        if isinstance(attempts, dict):
            for key in ("case", "solver", "verifier", "official_score"):
                attempt = attempts.get(key)
                if isinstance(attempt, dict):
                    attempt["countable"] = False
    return True


def _case_timeline_safe_string(value: Any, *, limit: int = 140) -> str:
    if not isinstance(value, str):
        return ""
    return value[:limit] if value else ""


def _case_timeline_public_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0.0, value)
    return None


def _case_timeline_max_int(*values: Any) -> int:
    safe_values = [
        value
        for value in (_case_timeline_public_number(item) for item in values)
        if isinstance(value, int)
    ]
    return max(safe_values) if safe_values else 0


def _append_case_timeline_event(
    events: list[dict[str, Any]],
    *,
    phase: str,
    event: str,
    status: str,
    **fields: Any,
) -> None:
    entry: dict[str, Any] = {
        "index": len(events) + 1,
        "phase": phase,
        "event": event,
        "status": status[:140],
    }
    for key, value in fields.items():
        if isinstance(value, bool):
            entry[key] = value
            continue
        number = _case_timeline_public_number(value)
        if number is not None:
            entry[key] = number
            continue
        text = _case_timeline_safe_string(value)
        if text:
            entry[key] = text
            continue
        if isinstance(value, list):
            safe_items: list[Any] = []
            for item in value:
                if isinstance(item, bool):
                    safe_items.append(item)
                else:
                    item_number = _case_timeline_public_number(item)
                    if item_number is not None:
                        safe_items.append(item_number)
                        continue
                    item_text = _case_timeline_safe_string(item, limit=80)
                    if item_text:
                        safe_items.append(item_text)
            if safe_items:
                entry[key] = safe_items[:8]
    events.append(entry)


def _build_goal_start_product_mode_control_score(
    compact: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    return build_goal_start_product_mode_control_score(
        compact,
        runner_prerequisites=_public_runner_prerequisites(
            plan.get("runner_prerequisites")
        ),
    )


def _build_case_event_timeline(
    compact: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Build a public-safe phase timeline from already-compacted signals."""

    counters = (
        compact.get("interaction_counters")
        if isinstance(compact.get("interaction_counters"), dict)
        else {}
    )
    runner_prerequisites = _public_runner_prerequisites(
        plan.get("runner_prerequisites")
    )
    compact_runner_prerequisites = compact.get("runner_prerequisites")
    if isinstance(compact_runner_prerequisites, dict):
        runner_prerequisites.update(compact_runner_prerequisites)
    lifecycle_contract = (
        compact.get("product_mode_lifecycle_contract")
        if isinstance(compact.get("product_mode_lifecycle_contract"), dict)
        else {}
    )
    runner_failure = (
        compact.get("runner_failure")
        if isinstance(compact.get("runner_failure"), dict)
        else {}
    )
    official_task_score = (
        compact.get("official_task_score")
        if isinstance(compact.get("official_task_score"), dict)
        else {}
    )
    events: list[dict[str, Any]] = []

    case_init_status = _case_timeline_safe_string(
        counters.get("case_goal_state_init_status")
    )
    if not case_init_status:
        if counters.get("case_goal_state_initialized_before_agent") is True:
            case_init_status = "passed"
        elif counters.get("case_goal_state_init_required") is True:
            case_init_status = "missing"
        elif compact.get("product_mode") is True or counters.get("product_mode") is True:
            case_init_status = "not_observed"
        else:
            case_init_status = "not_required"
    _append_case_timeline_event(
        events,
        phase="case_state",
        event="case_goal_state_init",
        status=case_init_status,
        required=counters.get("case_goal_state_init_required") is True,
        initialized_before_agent=(
            counters.get("case_goal_state_initialized_before_agent") is True
        ),
    )

    goal_start_control_score = (
        compact.get("goal_start_product_mode_control_score")
        if isinstance(compact.get("goal_start_product_mode_control_score"), dict)
        else _build_goal_start_product_mode_control_score(compact, plan)
    )
    if goal_start_control_score:
        if goal_start_control_score.get("satisfied") is True:
            goal_start_status = "satisfied"
        elif goal_start_control_score.get("goal_start_plan_observed") is True:
            goal_start_status = "partial"
        else:
            goal_start_status = "missing"
        _append_case_timeline_event(
            events,
            phase="goal_start_plan",
            event="ranked_todo_plan_selected_p0_lifecycle",
            status=goal_start_status,
            control_score=goal_start_control_score.get("score"),
            planned_todo_count=goal_start_control_score.get("planned_todo_count"),
            planned_todo_count_expected=goal_start_control_score.get(
                "planned_todo_count_expected"
            ),
            planned_p0_count=goal_start_control_score.get("planned_p0_count"),
            planner_before_todo_write=goal_start_control_score.get(
                "planner_before_todo_write"
            ),
            same_priority_order_preserved=goal_start_control_score.get(
                "same_priority_order_preserved"
            ),
            selected_p0_todo_id=goal_start_control_score.get("selected_p0_todo_id"),
            selected_todo_claimed=goal_start_control_score.get(
                "selected_todo_claimed"
            ),
            selected_todo_updated_before_solver=goal_start_control_score.get(
                "selected_todo_updated_before_solver"
            ),
            selected_todo_completed_before_spend=goal_start_control_score.get(
                "selected_todo_completed_before_spend"
            ),
            selected_todo_completed_observed=goal_start_control_score.get(
                "selected_todo_completed_observed"
            ),
            selected_todo_spend_observed=goal_start_control_score.get(
                "selected_todo_spend_observed"
            ),
            selected_todo_complete_count=goal_start_control_score.get(
                "selected_todo_complete_count"
            ),
            selected_todo_duplicate_complete_count=goal_start_control_score.get(
                "selected_todo_duplicate_complete_count"
            ),
            agent_todo_complete_unique_todo_count=goal_start_control_score.get(
                "agent_todo_complete_unique_todo_count"
            ),
            non_selected_todo_complete_count=goal_start_control_score.get(
                "non_selected_todo_complete_count"
            ),
            todo_complete_without_todo_id_count=goal_start_control_score.get(
                "todo_complete_without_todo_id_count"
            ),
            quota_spend_missing_after_repeated_complete=(
                goal_start_control_score.get(
                    "quota_spend_missing_after_repeated_complete"
                )
            ),
            non_selected_todos_preserved_open_or_deferred=(
                goal_start_control_score.get(
                    "non_selected_todos_preserved_open_or_deferred"
                )
            ),
            premature_done_signal_count=goal_start_control_score.get(
                "premature_done_signal_count"
            ),
            premature_done_stop_reason=goal_start_control_score.get(
                "premature_done_stop_reason"
            ),
        )

    driver_checkpoint_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_checkpoint_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_driver_lifecycle_checkpoint_count"
        ),
        lifecycle_contract.get("checkpoint_count"),
    )
    driver_state_read_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
        ),
        lifecycle_contract.get("driver_lifecycle_state_read_count"),
    )
    driver_state_write_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
        ),
        lifecycle_contract.get("driver_lifecycle_state_write_count"),
    )
    driver_status = "not_observed"
    if lifecycle_contract.get("orchestrated_driver_counts_as_product_mode") is True:
        driver_status = "satisfied"
    elif driver_checkpoint_count or driver_state_read_count or driver_state_write_count:
        driver_status = "observed"
    elif lifecycle_contract.get("checkpoint_required") is True:
        driver_status = "missing"
    _append_case_timeline_event(
        events,
        phase="driver_lifecycle",
        event="orchestrated_loopx_lifecycle",
        status=driver_status,
        checkpoint_count=driver_checkpoint_count,
        state_read_count=driver_state_read_count,
        state_write_count=driver_state_write_count,
        execution_style=(
            lifecycle_contract.get("execution_style")
            or counters.get("remote_command_file_bridge_driver_lifecycle_execution_style")
            or runner_prerequisites.get(
                "remote_command_file_bridge_driver_lifecycle_execution_style"
            )
        ),
    )

    solver_op_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_solver_operation_count"),
        runner_prerequisites.get("remote_command_file_bridge_solver_operation_count"),
    )
    solver_probe_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_solver_probe_ready_count"),
        runner_prerequisites.get("remote_command_file_bridge_solver_probe_ready_count"),
    )
    solver_consumed = (
        compact.get("remote_command_file_bridge_consumed_by_solver") is True
        or counters.get("remote_command_file_bridge_consumed_by_solver") is True
        or runner_prerequisites.get("remote_command_file_bridge_consumed_by_solver")
        is True
    )
    if solver_consumed:
        solver_status = "consumed"
    elif solver_op_count or solver_probe_count:
        solver_status = "observed_not_consumed"
    elif compact.get("product_mode") is True or counters.get("product_mode") is True:
        solver_status = "missing"
    else:
        solver_status = "not_required"
    _append_case_timeline_event(
        events,
        phase="solver_bridge",
        event="remote_command_bridge_consumption",
        status=solver_status,
        consumed_by_solver=solver_consumed,
        solver_operation_count=solver_op_count,
        solver_probe_ready_count=solver_probe_count,
    )

    trajectory_event_count = _case_timeline_max_int(
        counters.get("private_trajectory_event_count")
    )
    trajectory_round_count = _case_timeline_max_int(
        counters.get("private_trajectory_round_count")
    )
    trajectory_tool_call_count = _case_timeline_max_int(
        counters.get("private_trajectory_tool_call_count")
    )
    agent_request_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_agent_request_count"),
        runner_prerequisites.get("remote_command_file_bridge_agent_request_count"),
    )
    task_facing_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_agent_task_facing_operation_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_agent_task_facing_operation_count"
        ),
    )
    if trajectory_tool_call_count or task_facing_count:
        activity_status = "task_activity_observed"
    elif trajectory_event_count or agent_request_count:
        activity_status = "agent_messages_only"
    elif (
        counters.get("remote_command_file_bridge_agent_operation_trace_required")
        is True
        or runner_prerequisites.get(
            "remote_command_file_bridge_agent_operation_trace_required"
        )
        is True
    ):
        activity_status = "missing_agent_operation_trace"
    else:
        activity_status = "not_observed"
    _append_case_timeline_event(
        events,
        phase="agent_activity",
        event="task_facing_activity",
        status=activity_status,
        trajectory_event_count=trajectory_event_count,
        trajectory_round_count=trajectory_round_count,
        trajectory_tool_call_count=trajectory_tool_call_count,
        acp_protocol_tool_call_count=trajectory_tool_call_count,
        agent_bridge_request_count=agent_request_count,
        agent_bridge_task_facing_operation_count=task_facing_count,
        host_local_acp_bridge_progress_status=(
            counters.get("host_local_acp_bridge_progress_status")
            or runner_prerequisites.get("host_local_acp_bridge_progress_status")
        ),
        host_local_acp_bridge_progress_signal_source=(
            counters.get("host_local_acp_bridge_progress_signal_source")
            or runner_prerequisites.get("host_local_acp_bridge_progress_signal_source")
        ),
        agent_operation_trace_status=(
            counters.get("remote_command_file_bridge_agent_operation_trace_status")
            or runner_prerequisites.get(
                "remote_command_file_bridge_agent_operation_trace_status"
            )
        ),
    )

    round_reward_trace = (
        compact.get("round_reward_trace")
        if isinstance(compact.get("round_reward_trace"), dict)
        else {}
    )
    controller_status = "not_observed"
    if counters.get("controller_official_success_observed") is True:
        controller_status = "official_success_observed"
    elif counters.get("product_mode_typed_repair_terminal") is True:
        controller_status = "typed_repair_terminal"
    elif (
        counters.get("product_mode_host_local_idle_no_task_output_progress_stop")
        is True
    ):
        controller_status = "host_local_idle_no_task_output_progress_stop"
    elif (
        counters.get("product_mode_no_open_todo_below_passing_reward_stop")
        is True
    ):
        controller_status = "no_open_todo_below_passing_reward_stop"
    elif counters.get("product_mode_declared_done_below_passing_reward") is True:
        controller_status = "declared_done_below_passing_reward"
    elif counters.get("agent_declared_done") is True:
        controller_status = "agent_declared_done"
    elif _case_timeline_max_int(counters.get("controller_action_decisions")):
        controller_status = "rounds_observed"
    _append_case_timeline_event(
        events,
        phase="controller",
        event="controller_decision_loop",
        status=controller_status,
        action_decision_count=_case_timeline_max_int(
            counters.get("controller_action_decisions")
        ),
        initial_prompt_count=_case_timeline_max_int(
            counters.get("controller_initial_prompt_count")
        ),
        followup_prompt_count=_case_timeline_max_int(
            counters.get("controller_followup_prompt_count")
        ),
        stop_decision_count=_case_timeline_max_int(
            counters.get("controller_stop_decision_count")
        ),
        max_rounds_budget=_case_timeline_max_int(
            counters.get("controller_max_rounds_budget"),
            compact.get("controller_max_rounds_budget"),
        ),
        host_local_idle_no_task_output_progress_streak=_case_timeline_max_int(
            counters.get("product_mode_host_local_idle_no_task_output_progress_streak")
        ),
        host_local_idle_no_task_output_progress_streak_threshold=_case_timeline_max_int(
            counters.get(
                "product_mode_host_local_idle_no_task_output_progress_streak_threshold"
            )
        ),
        final_round=round_reward_trace.get("final_round"),
        best_round_reward=round_reward_trace.get("best_round_reward"),
        last_decision=(
            counters.get("last_decision") or compact.get("controller_last_decision")
        ),
    )

    recovery_exception = (
        runner_prerequisites.get("benchflow_user_loop_recovery_exception_type")
        or counters.get("benchflow_user_loop_recovery_exception_type")
    )
    runner_failure_class = runner_failure.get("failure_class")
    official_status_for_recovery = _case_timeline_safe_string(
        compact.get("official_score_status")
    )
    if recovery_exception and official_status_for_recovery == "completed":
        recovery_status = "runner_recovery_after_official_score"
    elif recovery_exception:
        recovery_status = "user_loop_recovery_triggered"
    elif runner_failure_class and official_status_for_recovery == "completed":
        recovery_status = "runner_failure_after_official_score"
    elif runner_failure_class:
        recovery_status = "runner_failure_recorded"
    else:
        recovery_status = "not_triggered"
    _append_case_timeline_event(
        events,
        phase="runner_recovery",
        event="timeout_or_failure_closeout",
        status=recovery_status,
        recovery_stage=(
            runner_prerequisites.get("benchflow_user_loop_recovery_stage")
            or counters.get("benchflow_user_loop_recovery_stage")
        ),
        recovery_exception_type=recovery_exception,
        recovery_delta_events=_case_timeline_max_int(
            runner_prerequisites.get("benchflow_user_loop_recovery_delta_events"),
            counters.get("benchflow_user_loop_recovery_delta_events"),
        ),
        recovery_delta_tool_calls=_case_timeline_max_int(
            runner_prerequisites.get("benchflow_user_loop_recovery_delta_tool_calls"),
            counters.get("benchflow_user_loop_recovery_delta_tool_calls"),
        ),
        runner_failure_class=runner_failure_class,
        benchflow_agent_timeout_effective_sec=runner_prerequisites.get(
            "benchflow_agent_timeout_effective_sec"
        ),
        local_codex_exec_timeout_sec=runner_prerequisites.get(
            "benchflow_agent_timeout_host_local_acp_exec_timeout_sec"
        ),
    )

    official_status = _case_timeline_safe_string(
        compact.get("official_score_status")
    ) or "unknown"
    score_value = official_task_score.get("value")
    if official_task_score.get("passed") is True:
        verifier_status = "passed"
    elif official_status == "completed":
        verifier_status = "completed_nonpassing"
    elif official_status == "missing":
        verifier_status = "missing"
    else:
        verifier_status = official_status
    _append_case_timeline_event(
        events,
        phase="verifier_score",
        event="official_score_closeout",
        status=verifier_status,
        official_score_status=official_status,
        official_score_value=score_value,
        official_score_passed=official_task_score.get("passed"),
        score_failure_attribution=compact.get("score_failure_attribution"),
        failure_attribution_labels=compact.get("failure_attribution_labels"),
    )

    closeout_todo_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_agent_todo_closeout_count"),
        runner_prerequisites.get("remote_command_file_bridge_agent_todo_closeout_count"),
        lifecycle_contract.get("agent_bridge_todo_closeout_count"),
    )
    closeout_refresh_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_agent_refresh_state_count"),
        runner_prerequisites.get("remote_command_file_bridge_agent_refresh_state_count"),
        lifecycle_contract.get("agent_bridge_refresh_state_count"),
    )
    closeout_spend_count = _case_timeline_max_int(
        counters.get("remote_command_file_bridge_agent_quota_spend_slot_count"),
        runner_prerequisites.get(
            "remote_command_file_bridge_agent_quota_spend_slot_count"
        ),
        lifecycle_contract.get("agent_bridge_quota_spend_slot_count"),
    )
    if lifecycle_contract.get("closeout_satisfied") is True:
        closeout_status = "satisfied"
    elif closeout_todo_count or closeout_refresh_count or closeout_spend_count:
        closeout_status = "partial"
    elif lifecycle_contract.get("closeout_required") is True:
        closeout_status = "missing"
    else:
        closeout_status = "not_required"
    _append_case_timeline_event(
        events,
        phase="loopx_closeout",
        event="agent_bridge_closeout",
        status=closeout_status,
        todo_closeout_count=closeout_todo_count,
        refresh_state_count=closeout_refresh_count,
        quota_spend_slot_count=closeout_spend_count,
    )

    return {
        "schema_version": "skillsbench_case_event_timeline_v0",
        "source": "compact_public_signals",
        "raw_material_recorded": False,
        "event_count": len(events),
        "events": events,
    }


def _public_task_staging(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in ("schema_version",):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            compact[field] = raw[:180]
    for field in (
        "staged",
        "include_task_skills",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_ubuntu_apt_mirror_patch_required",
        "dockerfile_ubuntu_apt_mirror_patch_applied",
        "dockerfile_ubuntu_apt_mirror_raw_url_recorded",
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
        "dockerfile_pip_bootstrap_patch_applied",
        "dockerfile_venv_pip_invocation_patch_required",
        "dockerfile_venv_pip_invocation_patch_applied",
        "dockerfile_gcr_mirror_configured",
        "dockerfile_gcr_mirror_patch_required",
        "dockerfile_gcr_mirror_patch_applied",
        "dockerfile_gcr_mirror_raw_prefix_recorded",
        "dockerfile_elan_toolchain_retry_patch_required",
        "dockerfile_elan_toolchain_retry_patch_applied",
        "dockerfile_wget_gpg_key_retry_patch_required",
        "dockerfile_wget_gpg_key_retry_patch_applied",
        "dockerfile_network_download_retry_patch_required",
        "dockerfile_network_download_retry_patch_applied",
        "dockerfile_uv_bootstrap_risk_detected",
        "dockerfile_uv_bootstrap_mirror_patch_required",
        "dockerfile_uv_bootstrap_mirror_patch_applied",
        "dockerfile_uv_bootstrap_pip_fallback_patch_applied",
        "dockerfile_apache_archive_mirror_patch_required",
        "dockerfile_apache_archive_mirror_patch_applied",
        "dockerfile_apache_archive_raw_url_recorded",
        "dockerfile_maven_mirror_patch_required",
        "dockerfile_maven_mirror_patch_applied",
        "dockerfile_maven_mirror_raw_url_recorded",
        "dockerfile_package_bootstrap_risk_preflight_blocked",
        "app_skills_mount_patch_applied",
        "apt_retry_patch_applied",
        "apt_risk_preflight_blocked",
        "bootstrap_light_preflight_blocked",
        "bootstrap_light_fail_fast_defaulted",
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_external_download_risk_detected",
        "verifier_package_install_risk_detected",
        "verifier_uv_bootstrap_mirror_patch_required",
        "verifier_uv_bootstrap_mirror_patch_applied",
        "verifier_uv_bootstrap_pip_fallback_patch_applied",
        "verifier_script_executable_required",
        "verifier_script_executable_ready",
        "verifier_dependency_cache_required",
        "verifier_dependency_cache_env_patch_applied",
        "verifier_dependency_cache_raw_path_recorded",
        "benchmark_egress_proxy_verifier_env_patch_required",
        "benchmark_egress_proxy_verifier_env_patch_applied",
        "benchmark_egress_proxy_verifier_env_raw_proxy_recorded",
        "benchmark_egress_proxy_dockerfile_env_patch_required",
        "benchmark_egress_proxy_dockerfile_env_patch_applied",
        "benchmark_egress_proxy_dockerfile_java_opts_patch_applied",
        "benchmark_egress_proxy_dockerfile_env_raw_proxy_recorded",
        "verifier_bootstrap_risk_preflight_blocked",
        "verifier_bootstrap_fail_fast_defaulted",
        "codex_acp_runtime_tools_patch_applied",
        "loopx_case_python_runtime_patch_required",
        "loopx_case_python_runtime_patch_applied",
        "task_skills_removed",
        "original_task_mutated",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "dockerfile_pip_index_host",
        "bootstrap_light_blocker_kind",
        "dockerfile_uv_bootstrap_version",
        "dockerfile_uv_bootstrap_mirror_host",
        "verifier_uv_bootstrap_version",
        "verifier_uv_bootstrap_mirror_host",
        "dockerfile_apache_archive_mirror_host",
        "dockerfile_maven_mirror_host",
        "dockerfile_ubuntu_apt_mirror_host",
    ):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            compact[field] = raw[:180]
    count = value.get("bootstrap_light_blocking_field_count")
    if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
        compact["bootstrap_light_blocking_field_count"] = count
    key_count = value.get("benchmark_egress_proxy_verifier_env_key_count")
    if isinstance(key_count, int) and not isinstance(key_count, bool) and key_count >= 0:
        compact["benchmark_egress_proxy_verifier_env_key_count"] = key_count
    key_count = value.get("verifier_dependency_cache_env_key_count")
    if isinstance(key_count, int) and not isinstance(key_count, bool) and key_count >= 0:
        compact["verifier_dependency_cache_env_key_count"] = key_count
    key_count = value.get("benchmark_egress_proxy_dockerfile_env_key_count")
    if isinstance(key_count, int) and not isinstance(key_count, bool) and key_count >= 0:
        compact["benchmark_egress_proxy_dockerfile_env_key_count"] = key_count
    categories = value.get("verifier_bootstrap_risk_categories")
    if isinstance(categories, list):
        compact["verifier_bootstrap_risk_categories"] = [
            item[:80]
            for item in categories
            if isinstance(item, str) and item
        ][:8]
    resource_cap = value.get("resource_cap_patch")
    if isinstance(resource_cap, dict):
        safe_cap: dict[str, Any] = {}
        for field in ("schema_version", "reason"):
            raw = resource_cap.get(field)
            if isinstance(raw, str) and raw:
                safe_cap[field] = raw[:180]
        for field in ("applied", "original_task_mutated"):
            if isinstance(resource_cap.get(field), bool):
                safe_cap[field] = resource_cap[field]
        for field in ("host_cpus", "requested_cpus", "effective_cpus"):
            raw = resource_cap.get(field)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                safe_cap[field] = raw
        if safe_cap:
            compact["resource_cap_patch"] = safe_cap
    return compact


def _discover_prepared_task_staging(plan: dict[str, Any]) -> dict[str, Any]:
    jobs_dir = Path(str(plan.get("jobs_dir") or "")).expanduser()
    job_name = str(plan.get("job_name") or "")
    task_id = str(plan.get("task_id") or "")
    if not job_name or not task_id:
        return {}
    prepared_task = jobs_dir / job_name / "prepared-tasks" / task_id
    if not prepared_task.exists():
        return {}
    dockerfile = prepared_task / "environment" / "Dockerfile"
    try:
        dockerfile_text = (
            dockerfile.read_text(encoding="utf-8", errors="replace")
            if dockerfile.exists()
            else ""
        )
    except OSError:
        dockerfile_text = ""
    verifier = proxy_runtime.skillsbench_verifier_script(prepared_task)
    try:
        verifier_text = (
            verifier.read_text(encoding="utf-8", errors="replace")
            if verifier.exists()
            else ""
        )
    except OSError:
        verifier_text = ""
    uv_versions = verifier_bootstrap.verifier_uv_bootstrap_versions(verifier_text)
    include_task_skills = bool(plan.get("include_task_skills"))
    discovered = {
        "schema_version": "skillsbench_task_staging_v0",
        "staged": True,
        "include_task_skills": include_task_skills,
        "app_skills_mount_patch_applied": (
            DOCKER_APP_SKILLS_MOUNT_BEGIN in dockerfile_text
        ),
        "apt_retry_patch_applied": DOCKER_APT_RETRY_BEGIN in dockerfile_text,
        "dockerfile_ubuntu_apt_mirror_patch_applied": (
            dockerfile_runtime.UBUNTU_APT_MIRROR_BEGIN in dockerfile_text
        ),
        "dockerfile_ubuntu_apt_mirror_host": (
            dockerfile_runtime.DEFAULT_UBUNTU_APT_MIRROR_HOST
            if dockerfile_runtime.UBUNTU_APT_MIRROR_BEGIN in dockerfile_text
            else ""
        ),
        "dockerfile_ubuntu_apt_mirror_raw_url_recorded": False,
        "dockerfile_pip_bootstrap_patch_applied": (
            DOCKER_PIP_BOOTSTRAP_BEGIN in dockerfile_text
        ),
        "dockerfile_venv_pip_invocation_patch_applied": (
            dockerfile_runtime.VENV_PIP_INVOCATION_MARKER in dockerfile_text
        ),
        "dockerfile_venv_pip_invocation_patch_required": (
            dockerfile_runtime.VENV_PIP_INVOCATION_MARKER in dockerfile_text
        ),
        "dockerfile_gcr_mirror_patch_applied": (
            DOCKER_GCR_MIRROR_BEGIN in dockerfile_text
        ),
        "dockerfile_gcr_mirror_raw_prefix_recorded": False,
        "dockerfile_elan_toolchain_retry_patch_applied": (
            DOCKER_ELAN_TOOLCHAIN_RETRY_BEGIN in dockerfile_text
        ),
        "dockerfile_wget_gpg_key_retry_patch_applied": (
            "curl -fsSL --retry 5 --retry-delay 2 --connect-timeout 30"
            in dockerfile_text
            and "| gpg --dearmor" in dockerfile_text
        ),
        "dockerfile_network_download_retry_patch_applied": (
            DOCKER_NETWORK_DOWNLOAD_RETRY_BEGIN in dockerfile_text
        ),
        "dockerfile_uv_bootstrap_mirror_patch_applied": (
            DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN in dockerfile_text
        ),
        "dockerfile_uv_bootstrap_pip_fallback_patch_applied": (
            DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN in dockerfile_text
            and "python3 -m pip install" in dockerfile_text
            and "uv==${LOOPX_SKILLSBENCH_UV_VERSION}" in dockerfile_text
        ),
        **uv_cache.discover_uv_binary_cache_metadata(prepared_task, dockerfile_text),
        "dockerfile_uv_bootstrap_mirror_host": (
            DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
            if DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN in dockerfile_text
            else ""
        ),
        "dockerfile_apache_archive_mirror_patch_applied": (
            DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST in dockerfile_text
        ),
        "dockerfile_apache_archive_mirror_host": (
            DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
            if DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST in dockerfile_text
            else ""
        ),
        "dockerfile_apache_archive_raw_url_recorded": False,
        "dockerfile_maven_mirror_patch_applied": (
            DOCKER_MAVEN_MIRROR_BEGIN in dockerfile_text
        ),
        "dockerfile_maven_mirror_host": (
            DEFAULT_DOCKER_MAVEN_MIRROR_HOST
            if DOCKER_MAVEN_MIRROR_BEGIN in dockerfile_text
            else ""
        ),
        "dockerfile_maven_mirror_raw_url_recorded": False,
        "codex_acp_runtime_tools_patch_applied": (
            DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN in dockerfile_text
        ),
        "loopx_case_python_runtime_patch_required": (
            DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN in dockerfile_text
        ),
        "loopx_case_python_runtime_patch_applied": (
            DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN in dockerfile_text
        ),
        "benchmark_egress_proxy_dockerfile_env_patch_applied": (
            DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN in dockerfile_text
        ),
        "benchmark_egress_proxy_dockerfile_java_opts_patch_applied": (
            "COURSIER_OPTS=${LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS}"
            in dockerfile_text
        ),
        "task_skills_removed": (
            not include_task_skills
            and not (prepared_task / "environment" / "skills").exists()
        ),
        "original_task_mutated": False,
        "verifier_script_executable_required": verifier.is_file(),
        "verifier_script_executable_ready": (
            verifier.is_file() and os.access(verifier, os.X_OK)
        ),
    }
    dockerfile_uv_versions = _dockerfile_uv_bootstrap_versions(dockerfile_text)
    if DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN in dockerfile_text:
        discovered.update(
            {
                "dockerfile_uv_bootstrap_risk_detected": True,
                "dockerfile_uv_bootstrap_mirror_patch_required": True,
                "dockerfile_uv_bootstrap_mirror_patch_applied": True,
            }
        )
        if dockerfile_uv_versions:
            discovered["dockerfile_uv_bootstrap_version"] = dockerfile_uv_versions[0]
    if verifier_bootstrap.VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN in verifier_text:
        discovered.update(
            {
                "verifier_uv_bootstrap_risk_detected": True,
                "verifier_uv_bootstrap_mirror_patch_required": True,
                "verifier_uv_bootstrap_mirror_patch_applied": True,
                "verifier_uv_bootstrap_pip_fallback_patch_applied": (
                    "python3 -m pip install" in verifier_text
                    and "uv==${loopx_uv_version}" in verifier_text
                ),
                "verifier_uv_env_source_guard_patch_applied": (
                    'if [ -f "$HOME/.local/bin/env" ]; then' in verifier_text
                    and '. "$HOME/.local/bin/env"' in verifier_text
                ),
                "verifier_uv_bootstrap_mirror_host": (
                    DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
                ),
            }
        )
        if uv_versions:
            discovered["verifier_uv_bootstrap_version"] = uv_versions[0]
    if VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN in verifier_text:
        discovered.update(
            {
                "benchmark_egress_proxy_verifier_env_patch_required": True,
                "benchmark_egress_proxy_verifier_env_patch_applied": True,
                "benchmark_egress_proxy_verifier_env_raw_proxy_recorded": False,
            }
        )
    if DOCKER_PIP_BOOTSTRAP_BEGIN in dockerfile_text:
        discovered.update(
            {
                "dockerfile_pip_install_risk_detected": True,
                "dockerfile_pip_bootstrap_patch_required": True,
                "dockerfile_pip_bootstrap_patch_applied": True,
                "dockerfile_pip_index_host": DEFAULT_DOCKER_PIP_INDEX_HOST,
            }
        )
    return discovered


def _effective_public_task_staging(plan: dict[str, Any]) -> dict[str, Any]:
    raw = plan.get("task_staging")
    if not isinstance(raw, dict):
        raw = {}
    if raw.get("staged") is not True:
        discovered = _discover_prepared_task_staging(plan)
        if discovered:
            merged = dict(raw)
            merged.update(discovered)
            raw = merged
            plan["task_staging"] = merged
    return _public_task_staging(raw)


def _public_task_setup_preflight(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "status",
        "sandbox",
        "task_id",
        "first_blocker",
        "alternate_source_kind",
        "canonical_equivalent_status",
        "registry_source_kind",
        "registry_source_status",
        "registry_task_path",
        "selection_recommendation",
    ):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            compact[field] = raw[:180]
    for field in (
        "raw_task_text_read",
        "raw_logs_read",
        "raw_trajectory_read",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
        "verifier_present",
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_external_download_risk_detected",
        "verifier_package_install_risk_detected",
        "dockerfile_present",
        "canonical_task_present",
        "alternate_source_supported_by_runner",
        "registry_task_present",
        "registry_task_path_recorded",
        "registry_excluded",
        "task_source_path_recorded",
        "task_source_content_recorded",
        "bootstrap_light_candidate_eligible",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in ("verifier_uv_bootstrap_version",):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            compact[field] = raw[:180]
    for field in (
        "nearest_canonical_task_ids",
        "verifier_bootstrap_risk_categories",
        "bootstrap_light_blocking_fields",
    ):
        raw_items = value.get(field)
        if isinstance(raw_items, list):
            compact[field] = [
                str(item)[:120]
                for item in raw_items[:5]
                if isinstance(item, str) and item
            ]
    return compact


def _public_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _requested_build_stall_timeout_sec(args: argparse.Namespace) -> int:
    return max(0, int(getattr(args, "build_stall_timeout_sec", 0) or 0))


def _effective_build_stall_timeout_sec(args: argparse.Namespace) -> int:
    return _requested_build_stall_timeout_sec(args)


def build_compose_setup_diagnostic(
    compact: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Return public-safe setup diagnostics for pre-agent SkillsBench failures."""

    labels = {
        str(label)
        for label in compact.get("failure_attribution_labels", [])
        if isinstance(label, str)
    }
    score_failure = str(compact.get("score_failure_attribution") or "")
    interaction = (
        compact.get("interaction_counters")
        if isinstance(compact.get("interaction_counters"), dict)
        else {}
    )
    progress = (
        compact.get("progress") if isinstance(compact.get("progress"), dict) else {}
    )
    fingerprint = (
        compact.get("runner_failure_fingerprint")
        if isinstance(compact.get("runner_failure_fingerprint"), dict)
        else {}
    )
    discovery = (
        compact.get("result_discovery")
        if isinstance(compact.get("result_discovery"), dict)
        else {}
    )
    runner_prerequisites = _public_runner_prerequisites(
        plan.get("runner_prerequisites")
    )
    task_staging = _effective_public_task_staging(plan)
    setup_preflight = _public_task_setup_preflight(
        plan.get("task_setup_preflight")
    )

    heartbeat_count = _public_int(interaction.get("heartbeat_count"))
    action_decision_count = _public_int(
        interaction.get("controller_action_decisions")
    )
    trajectory_round_count = _public_int(
        interaction.get("private_trajectory_round_count")
    )
    tool_call_count = _public_int(interaction.get("private_trajectory_tool_call_count"))
    loopx_cli_count = _public_int(interaction.get("loopx_cli_call_count"))
    round_reward_count = _public_int(interaction.get("controller_round_reward_count"))
    agent_rounds_started = any(
        value > 0
        for value in (
            heartbeat_count,
            action_decision_count,
            trajectory_round_count,
            tool_call_count,
            loopx_cli_count,
            round_reward_count,
        )
    )

    compose_setup_failure = (
        score_failure == "skillsbench_docker_compose_setup_failure"
        or "skillsbench_docker_compose_setup_failure" in labels
    )
    environment_setup_failure = (
        compose_setup_failure
        or "skillsbench_environment_setup_error" in labels
        or score_failure.startswith("skillsbench_docker_")
    )
    official_score_missing = compact.get("official_score_status") == "missing"
    official_result_materialized = (
        discovery.get("status") == "found"
        or compact.get("source_runner") == "official_skillsbench_benchflow_result"
    )
    unclassified = (
        "skillsbench_docker_compose_unclassified_setup_failure" in labels
    )
    docker_daemon_unavailable = (
        score_failure == "skillsbench_docker_daemon_unavailable"
        or "skillsbench_docker_daemon_unavailable" in labels
        or "docker_daemon_unavailable" in {
            str(item)
            for item in fingerprint.get("matched_patterns", [])
            if isinstance(item, str)
        }
    )
    volume_mount_failure = (
        score_failure == "skillsbench_docker_compose_volume_mount_failure"
        or "skillsbench_docker_compose_volume_mount_failure" in labels
        or "volume_mount_failure" in {
            str(item)
            for item in fingerprint.get("matched_patterns", [])
            if isinstance(item, str)
        }
    )
    if compose_setup_failure and not agent_rounds_started:
        status = "compose_setup_blocked_before_agent_rounds"
        if volume_mount_failure:
            next_action = "repair_task_volume_mount_setup_before_product_treatment"
        elif unclassified:
            next_action = "classify_sanitized_compose_setup_category_before_product_treatment"
        else:
            next_action = "repair_runner_setup_before_product_treatment"
    elif compose_setup_failure:
        status = "compose_setup_failed_after_agent_rounds_started"
        next_action = "separate_runner_setup_failure_from_agent_solution_quality"
    elif environment_setup_failure and not agent_rounds_started:
        status = "runner_setup_blocked_before_agent_rounds"
        next_action = "repair_runner_setup_before_case_accounting"
    else:
        status = "not_applicable"
        next_action = "no_compose_setup_diagnostic_action"

    resource_cap = task_staging.get("resource_cap_patch")
    diagnostic: dict[str, Any] = {
        "schema_version": "skillsbench_compose_setup_diagnostic_v0",
        "status": status,
        "route": str(plan.get("route") or compact.get("route") or "")[:120],
        "failure_class": score_failure[:160],
        "compose_setup_failure": compose_setup_failure,
        "unclassified_compose_failure": unclassified,
        "docker_daemon_unavailable": docker_daemon_unavailable,
        "volume_mount_failure": volume_mount_failure,
        "environment_setup_failure": environment_setup_failure,
        "agent_rounds_started": agent_rounds_started,
        "heartbeat_count": heartbeat_count,
        "controller_action_decision_count": action_decision_count,
        "trajectory_round_count": trajectory_round_count,
        "trajectory_tool_call_count": tool_call_count,
        "loopx_cli_call_count": loopx_cli_count,
        "round_reward_count": round_reward_count,
        "official_score_missing": official_score_missing,
        "official_result_json_materialized": official_result_materialized,
        "case_attempt_budget_should_count": not (
            environment_setup_failure and not agent_rounds_started
        ),
        "setup_stall_timeout_requested_sec": _public_int(
            runner_prerequisites.get("benchflow_setup_stall_timeout_requested_sec")
        ),
        "setup_stall_timeout_sec": _public_int(
            runner_prerequisites.get("benchflow_setup_stall_timeout_sec")
        ),
        "runner_prerequisite_status": str(
            runner_prerequisites.get(
                "codex_acp_runtime_launch_preflight_status", ""
            )
            or ""
        )[:120],
        "runner_launch_preflight_passed": runner_prerequisites.get(
            "codex_acp_runtime_launch_preflight"
        )
        is True,
        "task_setup_preflight_status": str(setup_preflight.get("status") or "")[:120],
        "apt_setup_risk_detected": setup_preflight.get(
            "apt_setup_risk_detected"
        )
        is True
        or task_staging.get("apt_setup_risk_detected") is True,
        "apt_retry_patch_required": setup_preflight.get(
            "apt_retry_patch_required"
        )
        is True
        or task_staging.get("apt_retry_patch_required") is True,
        "verifier_uv_bootstrap_risk_detected": setup_preflight.get(
            "verifier_uv_bootstrap_risk_detected"
        )
        is True
        or task_staging.get("verifier_uv_bootstrap_risk_detected") is True,
        "verifier_uv_bootstrap_mirror_patch_required": task_staging.get(
            "verifier_uv_bootstrap_mirror_patch_required"
        )
        is True,
        "verifier_uv_bootstrap_mirror_patch_applied": task_staging.get(
            "verifier_uv_bootstrap_mirror_patch_applied"
        )
        is True,
        "verifier_uv_bootstrap_pip_fallback_patch_applied": task_staging.get(
            "verifier_uv_bootstrap_pip_fallback_patch_applied"
        )
        is True,
        "staged_task_prepared": task_staging.get("staged") is True,
        "task_skills_removed": task_staging.get("task_skills_removed") is True,
        "codex_acp_runtime_tools_patch_applied": task_staging.get(
            "codex_acp_runtime_tools_patch_applied"
        )
        is True,
        "resource_cap_applied": (
            isinstance(resource_cap, dict) and resource_cap.get("applied") is True
        ),
        "fingerprint_matched_patterns": [
            str(item)[:120]
            for item in fingerprint.get("matched_patterns", [])
            if isinstance(item, str)
        ][:10],
        "fingerprint_confidence": str(
            fingerprint.get("fingerprint_confidence") or ""
        )[:120],
        "runner_error_len_bucket": str(
            fingerprint.get("error_len_bucket") or ""
        )[:80],
        "progress_completed_trials": _public_int(progress.get("n_completed_trials")),
        "progress_errored_trials": _public_int(progress.get("n_errored_trials")),
        "raw_error_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "next_diagnostic_action": next_action,
    }
    return diagnostic


def _strip_marker_block(text: str, begin: str, end: str) -> str:
    pattern = re.compile(
        rf"\n?{re.escape(begin)}\n.*?\n{re.escape(end)}\n?",
        flags=re.DOTALL,
    )
    return pattern.sub("\n", text).strip() + "\n"


def _write_text_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(f"{path.name}.loopx-tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def product_mode_case_state_seed_text(
    *,
    task_id: str,
    route: str,
    max_rounds: int,
) -> str:
    """Return a public-safe LoopX active-state skeleton for a case."""

    return benchmark_case_active_state_seed_text(
        benchmark_name="SkillsBench",
        goal_id=PRODUCT_MODE_CASE_GOAL_ID,
        task_id=task_id,
        route=route,
        max_rounds=max_rounds,
        case_state_path=PRODUCT_MODE_CASE_STATE_PATH,
    )


def _parse_cpu_value(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _format_cpu_value(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.2f}".rstrip("0")


def _task_requested_cpus(task_toml: Path) -> float | None:
    if not task_toml.exists():
        return None
    match = re.search(
        r"(?m)^(\s*cpus\s*=\s*)([0-9]+(?:\.[0-9]+)?)(\s*(?:#.*)?)$",
        task_toml.read_text(encoding="utf-8"),
    )
    if not match:
        return None
    return _parse_cpu_value(match.group(2))


def docker_host_cpu_count() -> float | None:
    """Return Docker daemon CPU capacity when cheaply discoverable."""

    env_value = os.environ.get(DOCKER_HOST_CPU_ENV, "").strip()
    if env_value:
        return _parse_cpu_value(env_value)
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.NCPU}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return _parse_cpu_value(proc.stdout.strip())


def patch_task_cpu_cap_for_local_docker(
    task_toml: Path,
    *,
    host_cpus: float | None,
) -> dict[str, Any]:
    """Cap staged SkillsBench CPU requests to the local Docker daemon limit."""

    metadata: dict[str, Any] = {
        "schema_version": "skillsbench_local_docker_resource_cap_v0",
        "applied": False,
        "host_cpus": host_cpus,
        "requested_cpus": None,
        "effective_cpus": None,
    }
    if host_cpus is None or not task_toml.exists():
        return metadata
    text = task_toml.read_text(encoding="utf-8")
    match = re.search(
        r"(?m)^(\s*cpus\s*=\s*)([0-9]+(?:\.[0-9]+)?)(\s*(?:#.*)?)$",
        text,
    )
    if not match:
        return metadata
    requested = _parse_cpu_value(match.group(2))
    metadata["requested_cpus"] = requested
    if requested is None or requested <= host_cpus:
        metadata["effective_cpus"] = requested
        return metadata
    effective = host_cpus
    patched = text[: match.start(2)] + _format_cpu_value(effective) + text[match.end(2) :]
    _write_text_atomic(task_toml, patched)
    metadata.update(
        {
            "applied": True,
            "effective_cpus": effective,
            "reason": "requested_cpus_exceeds_local_docker_daemon_capacity",
            "original_task_mutated": False,
        }
    )
    return metadata


def patch_dockerfile_app_skills_mount(dockerfile: Path) -> bool:
    """Ensure BenchFlow's task-skills upload target exists in staged Dockerfiles.

    BenchFlow uploads task-local ``environment/skills`` to ``/app/skills``
    after the container starts. Some official SkillsBench Dockerfiles use a
    different working directory and never create ``/app``. Patch only staged
    copies so the original benchmark task remains pristine.
    """

    if not dockerfile.exists():
        return False
    text = _strip_marker_block(
        dockerfile.read_text(encoding="utf-8"),
        DOCKER_APP_SKILLS_MOUNT_BEGIN,
        DOCKER_APP_SKILLS_MOUNT_END,
    )
    if re.search(r"^\s*FROM\s+scratch(?:\s|$)", text, flags=re.IGNORECASE | re.MULTILINE):
        return False
    keep_file = dockerfile.parent / DOCKER_APP_SKILLS_MOUNT_KEEP_FILE
    if not keep_file.exists():
        _write_text_atomic(keep_file, "LoopX SkillsBench app skills mount marker.\n")
    dockerignore = dockerfile.parent / ".dockerignore"
    if dockerignore.exists():
        dockerignore_text = _strip_marker_block(
            dockerignore.read_text(encoding="utf-8", errors="replace"),
            DOCKER_APP_SKILLS_DOCKERIGNORE_BEGIN,
            DOCKER_APP_SKILLS_DOCKERIGNORE_END,
        ).rstrip()
        dockerignore_block = (
            f"{DOCKER_APP_SKILLS_DOCKERIGNORE_BEGIN}\n"
            f"!{DOCKER_APP_SKILLS_MOUNT_KEEP_FILE}\n"
            f"{DOCKER_APP_SKILLS_DOCKERIGNORE_END}"
        )
        _write_text_atomic(
            dockerignore,
            (dockerignore_text + "\n\n" if dockerignore_text else "")
            + dockerignore_block
            + "\n",
        )
    block = (
        f"{DOCKER_APP_SKILLS_MOUNT_BEGIN}\n"
        f"COPY {DOCKER_APP_SKILLS_MOUNT_KEEP_FILE} /app/skills/.loopx_keep\n"
        f"{DOCKER_APP_SKILLS_MOUNT_END}"
    )
    patched_lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        patched_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("FROM ") and not inserted:
            patched_lines.extend(["", *block.splitlines(), ""])
            inserted = True
    if not inserted:
        patched_lines = [*block.splitlines(), "", *text.splitlines()]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == dockerfile.read_text(encoding="utf-8"):
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def dockerfile_needs_apt_retry_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8")
    if re.search(r"^\s*FROM\s+scratch(?:\s|$)", text, flags=re.IGNORECASE | re.MULTILINE):
        return False
    return bool(re.search(r"\bapt(?:-get)?\s+update\b", text, flags=re.IGNORECASE))


def dockerfile_needs_pip_bootstrap_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^\s*FROM\s+", text, flags=re.IGNORECASE | re.MULTILINE):
        return False
    return bool(
        re.search(
            r"(?:^|[;&|(\s])(?:python3?|python)\s+-m\s+pip\s+install\b|"
            r"(?:^|[;&|(\s])pip3?\s+install\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _normalized_docker_gcr_mirror_prefix(mirror_prefix: str | None) -> str:
    prefix = str(mirror_prefix or "").strip().rstrip("/")
    if not prefix or "://" in prefix or re.search(r"\s", prefix):
        return ""
    return prefix


def dockerfile_references_gcr_oss_fuzz_base(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"^\s*FROM(?:\s+--platform=[^\s]+)?\s+gcr\.io/oss-fuzz-base/",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return bool(pattern.search(text))


def dockerfile_needs_gcr_mirror_rewrite(
    dockerfile: Path,
    *,
    mirror_prefix: str | None,
) -> bool:
    if not _normalized_docker_gcr_mirror_prefix(mirror_prefix):
        return False
    return dockerfile_references_gcr_oss_fuzz_base(dockerfile)


def patch_dockerfile_gcr_mirror(
    dockerfile: Path,
    *,
    mirror_prefix: str | None,
) -> bool:
    """Rewrite staged GCR oss-fuzz base image refs to a configured mirror."""

    prefix = _normalized_docker_gcr_mirror_prefix(mirror_prefix)
    if not prefix or not dockerfile.exists():
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    text = _strip_marker_block(
        original,
        DOCKER_GCR_MIRROR_BEGIN,
        DOCKER_GCR_MIRROR_END,
    )
    pattern = re.compile(
        r"^(?P<lead>\s*FROM(?:\s+--platform=[^\s]+)?\s+)"
        r"(?P<image>gcr\.io/oss-fuzz-base/[^\s]+)"
        r"(?P<tail>.*)$",
        flags=re.IGNORECASE | re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        return (
            f"{match.group('lead')}{prefix}/{match.group('image')}"
            f"{match.group('tail')}"
        )

    rewritten, count = pattern.subn(replace, text)
    if count == 0:
        return False
    block = (
        f"{DOCKER_GCR_MIRROR_BEGIN}\n"
        "# Staged-only public base-image mirror rewrite; raw mirror prefix is\n"
        "# provided by private benchmark runtime configuration.\n"
        f"{DOCKER_GCR_MIRROR_END}"
    )
    patched = f"{block}\n{rewritten}".rstrip() + "\n"
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def _dockerfile_uv_bootstrap_versions(text: str) -> list[str]:
    versions: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"https?://astral\.sh/uv/(?P<version>[0-9A-Za-z][0-9A-Za-z._+-]*)/install\.sh",
        text,
    ):
        version = match.group("version")
        if version and version not in seen:
            versions.append(version)
            seen.add(version)
    for match in re.finditer(
        r"\bLOOPX_SKILLSBENCH_UV_VERSION=(?P<version>[0-9A-Za-z][0-9A-Za-z._+-]*)",
        text,
    ):
        version = match.group("version")
        if version and version not in seen:
            versions.append(version)
            seen.add(version)
    return versions


def dockerfile_needs_uv_bootstrap_mirror_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    text = _strip_marker_block(
        text,
        DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN,
        DOCKER_UV_BOOTSTRAP_MIRROR_END,
    )
    return bool(_dockerfile_uv_bootstrap_versions(text))


def _dockerfile_instruction_block_end(lines: list[str], start: int) -> int:
    """Return the exclusive end offset for a possibly continued instruction."""

    end = start + 1
    while end < len(lines) and lines[end - 1].rstrip().endswith("\\"):
        end += 1
    return end


def _dockerfile_curl_retry_all_errors_arg() -> str:
    return "$(curl --help all 2>/dev/null | grep -q -- '--retry-all-errors' && printf '%s' '--retry-all-errors' || true)"


def patch_dockerfile_uv_bootstrap_mirror(dockerfile: Path) -> dict[str, Any]:
    """Make staged Dockerfile uv bootstraps tolerate installer egress failures."""

    metadata: dict[str, Any] = {
        "dockerfile_uv_bootstrap_risk_detected": False,
        "dockerfile_uv_bootstrap_mirror_patch_required": False,
        "dockerfile_uv_bootstrap_mirror_patch_applied": False,
        "dockerfile_uv_bootstrap_pip_fallback_patch_applied": False,
        "dockerfile_uv_bootstrap_version": "",
        "dockerfile_uv_bootstrap_mirror_host": "",
    }
    if not dockerfile.exists():
        return metadata
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    text = _strip_marker_block(
        original,
        DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN,
        DOCKER_UV_BOOTSTRAP_MIRROR_END,
    )
    versions = _dockerfile_uv_bootstrap_versions(text)
    if not versions:
        return metadata
    version = versions[0]
    block = (
        f"{DOCKER_UV_BOOTSTRAP_MIRROR_BEGIN}\n"
        "# Prefer the PyPI uv wheel for Docker build bootstrap; keep the\n"
        "# official uv installer as a bounded mirror-backed fallback.\n"
        f"ARG LOOPX_SKILLSBENCH_UV_RELEASE_MIRROR={DEFAULT_VERIFIER_UV_RELEASE_MIRROR_BASE}\n"
        f"ARG LOOPX_SKILLSBENCH_UV_VERSION={version}\n"
        f"{uv_cache.dockerfile_uv_binary_cache_prelude()}"
        "    if command -v python3 >/dev/null 2>&1; then \\\n"
        "      loopx_pip_break_system_packages=''; \\\n"
        "      if python3 -m pip install --help 2>/dev/null | grep -q -- '--break-system-packages'; then \\\n"
        "        loopx_pip_break_system_packages='--break-system-packages'; \\\n"
        "      fi; \\\n"
        "      python3 -m pip install ${loopx_pip_break_system_packages} \\\n"
        "        --no-cache-dir --timeout 120 --retries 5 \\\n"
        f"        --index-url {DEFAULT_DOCKER_PIP_INDEX_URL} \\\n"
        f"        --extra-index-url {DEFAULT_DOCKER_PIP_EXTRA_INDEX_URL} \\\n"
        "        \"uv==${LOOPX_SKILLSBENCH_UV_VERSION}\" || true; \\\n"
        "    fi; \\\n"
        "    if ! command -v uvx >/dev/null 2>&1; then \\\n"
        "      export INSTALLER_DOWNLOAD_URL=\"${LOOPX_SKILLSBENCH_UV_RELEASE_MIRROR}/${LOOPX_SKILLSBENCH_UV_VERSION}\"; \\\n"
        f"      curl -LsSf --retry 5 {_dockerfile_curl_retry_all_errors_arg()} --retry-delay 2 --connect-timeout 30 \\\n"
        "        \"https://astral.sh/uv/${LOOPX_SKILLSBENCH_UV_VERSION}/install.sh\" | sh; \\\n"
        "    fi; \\\n"
        "    if [ -x \"${HOME}/.local/bin/uv\" ]; then install -m 0755 \"${HOME}/.local/bin/uv\" /usr/local/bin/uv; fi; \\\n"
        "    if [ -x \"${HOME}/.local/bin/uvx\" ]; then install -m 0755 \"${HOME}/.local/bin/uvx\" /usr/local/bin/uvx; fi; \\\n"
        "    command -v uv >/dev/null 2>&1; \\\n"
        "    command -v uvx >/dev/null 2>&1\n"
        f"{DOCKER_UV_BOOTSTRAP_MIRROR_END}"
    )
    lines = text.splitlines()
    patched_lines: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if (
            not replaced
            and re.match(r"^\s*RUN\b", line, flags=re.IGNORECASE)
            and "astral.sh/uv/" in line
            and "install.sh" in line
        ):
            block_end = _dockerfile_instruction_block_end(lines, index)
            patched_lines.extend(block.splitlines())
            index = block_end
            replaced = True
            continue
        patched_lines.append(line)
        index += 1
    if not replaced:
        patched_lines = [*block.splitlines(), "", *lines]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched != original:
        _write_text_atomic(dockerfile, patched)
    metadata.update(
        {
            "dockerfile_uv_bootstrap_risk_detected": True,
            "dockerfile_uv_bootstrap_mirror_patch_required": True,
            "dockerfile_uv_bootstrap_mirror_patch_applied": True,
            "dockerfile_uv_bootstrap_pip_fallback_patch_applied": True,
            "dockerfile_uv_binary_cache_dockerfile_patch_applied": True,
            "dockerfile_uv_bootstrap_version": version,
            "dockerfile_uv_bootstrap_mirror_host": (
                DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
            ),
        }
    )
    return metadata


def dockerfile_needs_elan_toolchain_retry_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    return bool(
        re.search(
            r"\belan\s+toolchain\s+install\s+\$\(cat\s+[^)]+lean-toolchain\)",
            text,
        )
    )


def patch_dockerfile_elan_toolchain_retry(dockerfile: Path) -> bool:
    """Add bounded retry around staged Lean toolchain downloads."""

    if not dockerfile_needs_elan_toolchain_retry_patch(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    text = _strip_marker_block(
        original,
        DOCKER_ELAN_TOOLCHAIN_RETRY_BEGIN,
        DOCKER_ELAN_TOOLCHAIN_RETRY_END,
    )
    pattern = re.compile(
        r"RUN\s+elan\s+toolchain\s+install\s+\$\(cat\s+"
        r"(?P<toolchain>[^)]+lean-toolchain)\)\s*&&\s*\\?\s*"
        r"(?:\n\s*)?elan\s+default\s+\$\(cat\s+(?P=toolchain)\)",
        flags=re.MULTILINE,
    )

    def replace(match: re.Match[str]) -> str:
        toolchain = match.group("toolchain").strip()
        return (
            f"{DOCKER_ELAN_TOOLCHAIN_RETRY_BEGIN}\n"
            "RUN set -eux; \\\n"
            f"    loopx_lean_toolchain=\"$(cat {toolchain})\"; \\\n"
            "    for loopx_attempt in 1 2 3 4 5; do \\\n"
            "      elan toolchain install \"${loopx_lean_toolchain}\" && break; \\\n"
            "      if [ \"${loopx_attempt}\" = \"5\" ]; then exit 1; fi; \\\n"
            "      sleep 10; \\\n"
            "    done; \\\n"
            "    elan default \"${loopx_lean_toolchain}\"\n"
            f"{DOCKER_ELAN_TOOLCHAIN_RETRY_END}"
        )

    patched, count = pattern.subn(replace, text, count=1)
    if count == 0:
        return False
    patched = patched.rstrip() + "\n"
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def dockerfile_needs_wget_gpg_key_retry_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    return bool(
        re.search(
            r"\bwget\s+(?:-qO\s+-|-q\s+-O\s+-|-O\s+-\s+-q)\s+"
            r"https?://[^\s|]+\s*\|\s*gpg\s+--dearmor",
            text,
        )
        or re.search(
            r"\bcurl\s+[^|\n]*https?://[^\s|]+\s*\|\s*gpg\s+--dearmor",
            text,
        )
    )


def patch_dockerfile_wget_gpg_key_retry(dockerfile: Path) -> bool:
    """Use curl retry semantics for staged public key download pipelines."""

    if not dockerfile_needs_wget_gpg_key_retry_patch(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"\bwget\s+(?:-qO\s+-|-q\s+-O\s+-|-O\s+-\s+-q)\s+"
        r"(?P<url>https?://[^\s|]+)\s*\|\s*gpg\s+--dearmor",
    )
    curl_pattern = re.compile(
        r"\bcurl\s+(?P<args>[^|\n]*?)"
        r"(?P<url>https?://[^\s|]+)\s*\|\s*gpg\s+--dearmor"
    )

    def gpg_key_curl_command(url: str) -> str:
        return (
            "curl -fsSL --retry 8 "
            f"{_dockerfile_curl_retry_all_errors_arg()} --retry-delay 3 "
            f"--connect-timeout 60 --max-time 300 {url} | gpg --dearmor"
        )

    def replace(match: re.Match[str]) -> str:
        return gpg_key_curl_command(match.group("url"))

    patched, count = pattern.subn(replace, original)
    patched, curl_count = curl_pattern.subn(
        lambda match: gpg_key_curl_command(match.group("url")),
        patched,
    )
    if (count + curl_count) == 0 or patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def dockerfile_needs_apache_archive_mirror_rewrite(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    return (
        "https://archive.apache.org/dist/druid/" in text
        or "http://archive.apache.org/dist/druid/" in text
    )


def patch_dockerfile_apache_archive_mirror(dockerfile: Path) -> bool:
    """Rewrite known slow Apache archive Druid downloads to a public mirror."""

    if not dockerfile_needs_apache_archive_mirror_rewrite(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    mirror_base = DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_BASE.rstrip("/")
    patched = original.replace(
        "https://archive.apache.org/dist/druid/",
        f"{mirror_base}/druid/",
    ).replace(
        "http://archive.apache.org/dist/druid/",
        f"{mirror_base}/druid/",
    )
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def _insert_dockerfile_block_after_first_from(text: str, block: str) -> str:
    patched_lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        patched_lines.append(line)
        if not inserted and _is_dockerfile_from_instruction(line.strip()):
            patched_lines.extend(["", *block.splitlines(), ""])
            inserted = True
    if not inserted:
        return "\n".join([*block.splitlines(), "", *text.splitlines()])
    return "\n".join(patched_lines)


def dockerfile_needs_maven_mirror_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"\bmvn\s+", text))


def patch_dockerfile_maven_mirror(dockerfile: Path) -> bool:
    """Route staged Docker build Maven downloads through a public mirror."""

    if not dockerfile_needs_maven_mirror_patch(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    text = _strip_marker_block(
        original,
        DOCKER_MAVEN_MIRROR_BEGIN,
        DOCKER_MAVEN_MIRROR_END,
    )
    settings_block = (
        f"{DOCKER_MAVEN_MIRROR_BEGIN}\n"
        "RUN mkdir -p /opt/loopx-maven && cat > "
        f"{DEFAULT_DOCKER_MAVEN_SETTINGS_PATH} "
        "<<'LOOPX_MAVEN_SETTINGS_EOF'\n"
        "<settings xmlns=\"http://maven.apache.org/SETTINGS/1.0.0\" "
        "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
        "xsi:schemaLocation=\"http://maven.apache.org/SETTINGS/1.0.0 "
        "https://maven.apache.org/xsd/settings-1.0.0.xsd\">\n"
        "  <mirrors>\n"
        "    <mirror>\n"
        "      <id>loopx-public-maven-mirror</id>\n"
        "      <mirrorOf>*</mirrorOf>\n"
        "      <url>"
        f"{DEFAULT_DOCKER_MAVEN_MIRROR_URL}"
        "</url>\n"
        "    </mirror>\n"
        "  </mirrors>\n"
        "</settings>\n"
        "LOOPX_MAVEN_SETTINGS_EOF\n"
        f"{DOCKER_MAVEN_MIRROR_END}"
    )
    if DOCKER_NETWORK_DOWNLOAD_RETRY_END in text:
        text = text.replace(
            DOCKER_NETWORK_DOWNLOAD_RETRY_END,
            f"{DOCKER_NETWORK_DOWNLOAD_RETRY_END}\n\n{settings_block}",
            1,
        )
    else:
        text = _insert_dockerfile_block_after_first_from(text, settings_block)
    text = re.sub(
        r"\bmvn(?!\s+(?:--settings|-s)\b)",
        f"mvn --settings {DEFAULT_DOCKER_MAVEN_SETTINGS_PATH}",
        text,
    )
    if text == original:
        return False
    _write_text_atomic(dockerfile, text.rstrip() + "\n")
    return True


def dockerfile_needs_network_download_retry_patch(dockerfile: Path) -> bool:
    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8", errors="replace")
    return bool(
        re.search(r"\bwget\s+[^;\n]*https?://", text)
        or re.search(r"\bcurl\s+[^;\n|]*https?://", text)
        or re.search(r"\bgit\s+clone\s+https?://", text)
        or re.search(r"\bmvn\s+", text)
    )


def patch_dockerfile_network_download_retry(dockerfile: Path) -> bool:
    """Add staged retry/timeout defaults for common build-time downloads."""

    if not dockerfile_needs_network_download_retry_patch(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8", errors="replace")
    text = _strip_marker_block(
        original,
        DOCKER_NETWORK_DOWNLOAD_RETRY_BEGIN,
        DOCKER_NETWORK_DOWNLOAD_RETRY_END,
    )
    wget_pattern = re.compile(
        r"\bwget(?P<args>(?:\s+(?!https?://)[^\s\\;&|]+)*)\s+"
        r"(?P<url>https?://[^\s\\;&|]+)"
    )
    curl_pattern = re.compile(
        r"\bcurl(?P<args>(?:\s+(?!https?://)[^\s\\;&|]+)*)\s+"
        r"(?P<url>https?://[^\s\\;&|]+)"
    )

    def replace_wget(match: re.Match[str]) -> str:
        args = match.group("args") or ""
        if "--tries" in args or "--timeout" in args:
            return match.group(0)
        return (
            f"wget{args} --tries=5 --timeout=120 --read-timeout=120 "
            f"--retry-connrefused {match.group('url')}"
        )

    def replace_curl(match: re.Match[str]) -> str:
        args = match.group("args") or ""
        if "--retry" in args or "--connect-timeout" in args:
            return match.group(0)
        return (
            "curl"
            f"{args} --retry 5 {_dockerfile_curl_retry_all_errors_arg()} --retry-delay 2 "
            f"--connect-timeout 60 --max-time 600 {match.group('url')}"
        )

    text = wget_pattern.sub(replace_wget, text)
    text = curl_pattern.sub(replace_curl, text)
    block = (
        f"{DOCKER_NETWORK_DOWNLOAD_RETRY_BEGIN}\n"
        "ENV GIT_HTTP_LOW_SPEED_LIMIT=1000 \\\n"
        "    GIT_HTTP_LOW_SPEED_TIME=120 \\\n"
        "    MAVEN_OPTS=\"-Dmaven.wagon.http.retryHandler.count=5 "
        "-Dmaven.wagon.httpconnectionManager.ttlSeconds=60 "
        "-Dhttp.keepAlive=false\"\n"
        f"{DOCKER_NETWORK_DOWNLOAD_RETRY_END}"
    )
    patched_lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        patched_lines.append(line)
        stripped = line.strip()
        if stripped.upper().startswith("FROM ") and " scratch" not in stripped.lower():
            patched_lines.extend(["", *block.splitlines(), ""])
            inserted = True
    if not inserted:
        patched_lines = [*block.splitlines(), "", *text.splitlines()]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def _skillsbench_public_task_label(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    cleaned = []
    for char in text:
        cleaned.append(
            char.lower() if char.isalnum() or char in {"-", "_", "."} else "-"
        )
    label = "".join(cleaned).strip("-_.")
    while "--" in label:
        label = label.replace("--", "-")
    return label[:limit]


def _skillsbench_task_id_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 2}


def _skillsbench_task_id_similarity(
    requested_task_id: str,
    canonical_task_id: str,
) -> tuple[float, bool]:
    requested = _skillsbench_public_task_label(requested_task_id).lower()
    canonical = _skillsbench_public_task_label(canonical_task_id).lower()
    if not requested or not canonical:
        return 0.0, False
    sequence_score = difflib.SequenceMatcher(None, requested, canonical).ratio()
    requested_tokens = _skillsbench_task_id_tokens(requested)
    canonical_tokens = _skillsbench_task_id_tokens(canonical)
    token_overlap = 0.0
    has_token_overlap = False
    if requested_tokens and canonical_tokens:
        intersection = requested_tokens & canonical_tokens
        union = requested_tokens | canonical_tokens
        token_overlap = len(intersection) / len(union)
        has_token_overlap = bool(intersection)
    return (sequence_score * 0.4) + (token_overlap * 0.6), has_token_overlap


def skillsbench_nearest_canonical_task_ids(
    *,
    requested_task_id: str,
    canonical_root: Path,
    limit: int = 5,
) -> tuple[list[str], str]:
    canonical_ids: list[str] = []
    if canonical_root.is_dir():
        for child in sorted(canonical_root.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            label = _skillsbench_public_task_label(child.name)
            if label:
                canonical_ids.append(label)
    if not canonical_ids:
        return [], "canonical_task_index_empty"

    ranked: list[tuple[float, bool, str]] = []
    for canonical_id in canonical_ids:
        score, has_token_overlap = _skillsbench_task_id_similarity(
            requested_task_id,
            canonical_id,
        )
        ranked.append((score, has_token_overlap, canonical_id))
    ranked.sort(key=lambda item: (-item[0], item[2]))
    best_score, best_has_token_overlap, _best_id = ranked[0]
    close_match = best_has_token_overlap or best_score >= 0.34
    if close_match:
        return [item[2] for item in ranked[:limit]], "close_canonical_match_found"
    return canonical_ids[:limit], "no_close_canonical_match"


SKILLSBENCH_BOOTSTRAP_LIGHT_BLOCKING_PREFLIGHT_FIELDS = (
    "apt_setup_risk_detected",
    "apt_retry_patch_required",
    "dockerfile_pip_install_risk_detected",
    "dockerfile_pip_bootstrap_patch_required",
    "verifier_bootstrap_risk_detected",
    "verifier_uv_bootstrap_risk_detected",
    "verifier_external_download_risk_detected",
    "verifier_package_install_risk_detected",
)


def skillsbench_bootstrap_light_blocking_fields(
    preflight: dict[str, Any],
) -> list[str]:
    if preflight.get("canonical_task_present") is False:
        return ["canonical_task_present"]
    return [
        field
        for field in SKILLSBENCH_BOOTSTRAP_LIGHT_BLOCKING_PREFLIGHT_FIELDS
        if preflight.get(field) is True
    ]


def _setup_preflight_public_blocking_fields(preflight: dict[str, Any]) -> list[str]:
    raw_fields = preflight.get("bootstrap_light_blocking_fields")
    if isinstance(raw_fields, list):
        return [
            field
            for field in raw_fields
            if isinstance(field, str)
            and field
            in (
                *SKILLSBENCH_BOOTSTRAP_LIGHT_BLOCKING_PREFLIGHT_FIELDS,
                "canonical_task_present",
            )
        ]
    return skillsbench_bootstrap_light_blocking_fields(preflight)


def _bootstrap_light_blocker_kind(blocking_fields: list[str]) -> str:
    fields = set(blocking_fields)
    if "canonical_task_present" in fields:
        return "task_source"
    if fields & {
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
    }:
        return "apt"
    if fields & {
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
    }:
        return "dockerfile_package"
    if fields & {
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_external_download_risk_detected",
        "verifier_package_install_risk_detected",
    }:
        return "verifier"
    return "setup"


def _bootstrap_light_preflight_block_required(
    args: argparse.Namespace,
    *,
    blocker_kind: str,
) -> bool:
    if getattr(args, "reduce_only", False):
        return False
    fail_fast_required = _formal_app_server_goal_bootstrap_light_fail_fast_required(
        args
    )
    if blocker_kind in {"apt", "dockerfile_package"}:
        return bool(args.fail_fast_on_apt_risk or fail_fast_required)
    if blocker_kind == "verifier":
        return bool(args.fail_fast_on_verifier_bootstrap_risk or fail_fast_required)
    return False


def _mark_bootstrap_light_preflight_blocked(
    *,
    staging: dict[str, Any],
    setup_preflight: dict[str, Any],
    blocking_fields: list[str],
    args: argparse.Namespace,
) -> str:
    blocker_kind = _bootstrap_light_blocker_kind(blocking_fields)
    staging["bootstrap_light_preflight_blocked"] = True
    staging["bootstrap_light_blocker_kind"] = blocker_kind
    staging["bootstrap_light_fail_fast_defaulted"] = bool(
        getattr(args, "bootstrap_light_fail_fast_defaulted", False)
    )
    staging["bootstrap_light_blocking_field_count"] = len(blocking_fields)
    if blocker_kind == "task_source":
        staging["task_source_preflight_blocked"] = True
    if blocker_kind in {"apt", "dockerfile_package"}:
        staging["apt_setup_risk_detected"] = bool(
            setup_preflight.get("apt_setup_risk_detected")
        )
        staging["apt_retry_patch_required"] = bool(
            setup_preflight.get("apt_retry_patch_required")
        )
        staging["dockerfile_pip_install_risk_detected"] = bool(
            setup_preflight.get("dockerfile_pip_install_risk_detected")
        )
        staging["dockerfile_pip_bootstrap_patch_required"] = bool(
            setup_preflight.get("dockerfile_pip_bootstrap_patch_required")
        )
        if blocker_kind == "apt":
            staging["apt_risk_preflight_blocked"] = True
        else:
            staging["dockerfile_package_bootstrap_risk_preflight_blocked"] = True
    if blocker_kind == "verifier":
        staging["verifier_bootstrap_risk_detected"] = bool(
            setup_preflight.get("verifier_bootstrap_risk_detected")
        )
        staging["verifier_bootstrap_risk_preflight_blocked"] = True
        staging["verifier_bootstrap_fail_fast_defaulted"] = bool(
            getattr(args, "verifier_bootstrap_fail_fast_defaulted", False)
        )
    return blocker_kind


def skillsbench_task_setup_preflight(
    *,
    task_path: Path,
    sandbox: str,
) -> dict[str, Any]:
    """Return public-safe setup-shape facts before spending a full run."""

    expanded_task_path = task_path.expanduser()
    public_task_id = _skillsbench_public_task_label(expanded_task_path.name)
    preflight: dict[str, Any] = {
        "schema_version": "skillsbench_task_setup_preflight_v0",
        "sandbox": sandbox,
        "task_id": public_task_id,
        "raw_task_text_read": False,
        "raw_logs_read": False,
        "raw_trajectory_read": False,
        "task_source_path_recorded": False,
        "task_source_content_recorded": False,
        "canonical_task_present": False,
        "alternate_source_supported_by_runner": False,
        "apt_setup_risk_detected": False,
        "apt_retry_patch_required": False,
        "dockerfile_pip_install_risk_detected": False,
        "dockerfile_pip_bootstrap_patch_required": False,
        "verifier_present": False,
        "verifier_bootstrap_risk_detected": False,
        "verifier_uv_bootstrap_risk_detected": False,
        "verifier_external_download_risk_detected": False,
        "verifier_package_install_risk_detected": False,
        "verifier_bootstrap_risk_categories": [],
        "bootstrap_light_candidate_eligible": False,
        "bootstrap_light_blocking_fields": [],
    }
    skillsbench_root = expanded_task_path.parent.parent
    canonical_task_exists = expanded_task_path.is_dir()
    preflight["canonical_task_present"] = canonical_task_exists
    if not canonical_task_exists:
        sanity_task = (
            skillsbench_root
            / "experiments"
            / "sanity-tasks"
            / expanded_task_path.name
        )
        nearest, canonical_equivalent_status = (
            skillsbench_nearest_canonical_task_ids(
                requested_task_id=public_task_id,
                canonical_root=skillsbench_root / "tasks",
            )
        )
        preflight.update(
            {
                **classify_missing_task_source(
                    skillsbench_root=skillsbench_root,
                    task_id=expanded_task_path.name,
                    sanity_task_exists=sanity_task.is_dir(),
                    canonical_equivalent_status=canonical_equivalent_status,
                ),
                "canonical_equivalent_status": canonical_equivalent_status,
                "nearest_canonical_task_ids": nearest,
            }
        )
        preflight["bootstrap_light_blocking_fields"] = (
            skillsbench_bootstrap_light_blocking_fields(preflight)
        )
        return preflight
    if sandbox != "docker":
        preflight["status"] = "not_applicable"
        preflight["bootstrap_light_candidate_eligible"] = True
        return preflight

    dockerfile = expanded_task_path / "environment" / "Dockerfile"
    dockerfile_exists = dockerfile.exists()
    preflight["dockerfile_present"] = dockerfile_exists
    if not dockerfile_exists:
        preflight["status"] = "no_dockerfile"
        preflight["bootstrap_light_candidate_eligible"] = True
        return preflight

    apt_risk = dockerfile_needs_apt_retry_patch(dockerfile)
    pip_risk = dockerfile_needs_pip_bootstrap_patch(dockerfile)
    verifier_risk = verifier_bootstrap.skillsbench_verifier_bootstrap_risk(
        expanded_task_path
    )
    preflight.update(verifier_risk)
    verifier_bootstrap_risk = bool(
        verifier_risk.get("verifier_bootstrap_risk_detected")
    )
    if (apt_risk or pip_risk) and verifier_bootstrap_risk:
        setup_status = "setup_bootstrap_risk_detected"
    elif apt_risk or pip_risk:
        setup_status = "dockerfile_package_bootstrap_risk_detected"
    elif verifier_bootstrap_risk:
        setup_status = "verifier_bootstrap_risk_detected"
    else:
        setup_status = "ok"
    risk_fields = skillsbench_bootstrap_light_blocking_fields(
        {
            **preflight,
            "apt_setup_risk_detected": apt_risk,
            "apt_retry_patch_required": apt_risk,
            "dockerfile_pip_install_risk_detected": pip_risk,
            "dockerfile_pip_bootstrap_patch_required": pip_risk,
        }
    )
    preflight.update(
        {
            "status": setup_status,
            "apt_setup_risk_detected": apt_risk,
            "apt_retry_patch_required": apt_risk,
            "dockerfile_pip_install_risk_detected": pip_risk,
            "dockerfile_pip_bootstrap_patch_required": pip_risk,
            "bootstrap_light_candidate_eligible": not risk_fields,
            "bootstrap_light_blocking_fields": risk_fields,
            "selection_recommendation": (
                "route_to_setup_repair_or_use_fail_fast_guard"
                if risk_fields
                else "eligible_for_bootstrap_light_full_pair"
            ),
        }
    )
    return preflight


def _verifier_benchmark_egress_proxy_exports(
    proxy_env: Mapping[str, str] | None,
) -> dict[str, str]:
    if not isinstance(proxy_env, Mapping):
        return {}
    proxy_url = str(proxy_env.get("LOOPX_SKILLSBENCH_EGRESS_PROXY") or "").strip()
    if not proxy_url:
        for key in BENCHMARK_EGRESS_PROXY_FORWARD_ENV_KEYS:
            proxy_url = str(proxy_env.get(key) or "").strip()
            if proxy_url:
                break
    if not proxy_url:
        return {}
    exports = {
        key: proxy_url
        for key in BENCHMARK_EGRESS_PROXY_FORWARD_ENV_KEYS
    }
    no_proxy = str(proxy_env.get("NO_PROXY") or proxy_env.get("no_proxy") or "").strip()
    if no_proxy:
        exports["NO_PROXY"] = no_proxy
        exports["no_proxy"] = no_proxy
    return exports


def patch_verifier_benchmark_egress_proxy_env(
    verifier: Path,
    *,
    proxy_env: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Forward the private benchmark egress proxy into staged verifier scripts."""

    exports = _verifier_benchmark_egress_proxy_exports(proxy_env)
    patch_required = bool(exports and verifier.exists())
    metadata: dict[str, Any] = {
        "benchmark_egress_proxy_verifier_env_patch_required": patch_required,
        "benchmark_egress_proxy_verifier_env_patch_applied": False,
        "benchmark_egress_proxy_verifier_env_key_count": (
            len(exports) if patch_required else 0
        ),
        "benchmark_egress_proxy_verifier_env_raw_proxy_recorded": False,
    }
    if not patch_required:
        return metadata
    try:
        original = verifier.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return metadata
    text = _strip_marker_block(
        original,
        VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN,
        VERIFIER_BENCHMARK_EGRESS_PROXY_END,
    )
    block_lines = [
        VERIFIER_BENCHMARK_EGRESS_PROXY_BEGIN,
        "# Forward the runtime benchmark egress proxy into verifier bootstrap commands.",
        "# The concrete proxy is staged only in the private prepared task copy.",
        "loopx_restore_xtrace=''",
        "case \"$-\" in *x*) loopx_restore_xtrace=1; set +x;; esac",
    ]
    for key in sorted(exports):
        block_lines.append(f"export {key}={shlex.quote(exports[key])}")
    block_lines.extend(
        [
            "[ -z \"${loopx_restore_xtrace}\" ] || set -x",
            "unset loopx_restore_xtrace",
            VERIFIER_BENCHMARK_EGRESS_PROXY_END,
        ]
    )
    block = "\n".join(block_lines)
    lines = text.splitlines()
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    patched_lines = [*lines[:insert_at], block, *lines[insert_at:]]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched != original:
        _write_text_atomic(verifier, patched)
    metadata["benchmark_egress_proxy_verifier_env_patch_applied"] = True
    return metadata


def patch_dockerfile_benchmark_egress_proxy_env(
    dockerfile: Path,
    *,
    proxy_env: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Forward the private benchmark egress proxy into staged Docker builds."""

    exports = _verifier_benchmark_egress_proxy_exports(proxy_env)
    proxy_url = str(exports.get("HTTPS_PROXY") or exports.get("HTTP_PROXY") or "")
    no_proxy = str(exports.get("NO_PROXY") or exports.get("no_proxy") or "")
    metadata: dict[str, Any] = {
        "benchmark_egress_proxy_dockerfile_env_patch_required": bool(proxy_url),
        "benchmark_egress_proxy_dockerfile_env_patch_applied": False,
        "benchmark_egress_proxy_dockerfile_java_opts_patch_applied": False,
        "benchmark_egress_proxy_dockerfile_env_key_count": len(exports),
        "benchmark_egress_proxy_dockerfile_env_raw_proxy_recorded": False,
    }
    if not dockerfile.exists() or not proxy_url:
        return metadata
    try:
        original = dockerfile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return metadata
    text = _strip_marker_block(
        original,
        DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN,
        DOCKER_BENCHMARK_EGRESS_PROXY_END,
    )
    proxy_host = ""
    proxy_port = 0
    try:
        _, proxy_host, proxy_port = _parse_proxy_endpoint(proxy_url)
    except Exception:
        proxy_host = ""
        proxy_port = 0
    block_lines = [
        DOCKER_BENCHMARK_EGRESS_PROXY_BEGIN,
        "# Forward the runtime benchmark egress proxy into Docker build steps.",
        "# The concrete proxy is staged only in the private prepared task copy.",
        f"ARG LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY={proxy_url}",
        f"ARG LOOPX_SKILLSBENCH_BENCHMARK_NO_PROXY={no_proxy}",
        "ENV HTTPS_PROXY=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY} \\",
        "    HTTP_PROXY=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY} \\",
        "    ALL_PROXY=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY} \\",
        "    https_proxy=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY} \\",
        "    http_proxy=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY} \\",
        "    all_proxy=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY} \\",
        "    NO_PROXY=${LOOPX_SKILLSBENCH_BENCHMARK_NO_PROXY} \\",
        "    no_proxy=${LOOPX_SKILLSBENCH_BENCHMARK_NO_PROXY}",
    ]
    if proxy_host and proxy_port:
        java_proxy_opts = (
            "-Dhttp.proxyHost=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_HOST} "
            "-Dhttp.proxyPort=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_PORT} "
            "-Dhttps.proxyHost=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_HOST} "
            "-Dhttps.proxyPort=${LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_PORT}"
        )
        block_lines.extend(
            [
                f"ARG LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_HOST={proxy_host}",
                f"ARG LOOPX_SKILLSBENCH_BENCHMARK_EGRESS_PROXY_PORT={proxy_port}",
                "ENV LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS=\""
                f"{java_proxy_opts}\" \\",
                "    JAVA_TOOL_OPTIONS=${LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS} \\",
                "    COURSIER_OPTS=${LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS} \\",
                "    SBT_OPTS=${LOOPX_SKILLSBENCH_JAVA_PROXY_OPTS}",
            ]
        )
        metadata["benchmark_egress_proxy_dockerfile_java_opts_patch_applied"] = True
    block_lines.append(DOCKER_BENCHMARK_EGRESS_PROXY_END)
    block = "\n".join(block_lines)
    patched_lines: list[str] = []
    inserted = False
    heredoc_delimiter: str | None = None
    for line in text.splitlines():
        patched_lines.append(line)
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = dockerfile_runtime.dockerfile_heredoc_delimiter(line)
        stripped = line.strip()
        if (
            _is_dockerfile_from_instruction(stripped)
            and " scratch" not in stripped.lower()
        ):
            patched_lines.extend(["", block, ""])
            inserted = True
    if not inserted:
        return metadata
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched != original:
        _write_text_atomic(dockerfile, patched)
    metadata["benchmark_egress_proxy_dockerfile_env_patch_applied"] = True
    return metadata


def patch_dockerfile_apt_retry(dockerfile: Path) -> bool:
    """Add public-safe apt retry/no-cache defaults to staged Dockerfiles."""

    if not dockerfile_needs_apt_retry_patch(dockerfile):
        return False
    text = _strip_marker_block(
        dockerfile.read_text(encoding="utf-8"),
        DOCKER_APT_RETRY_BEGIN,
        DOCKER_APT_RETRY_END,
    )
    block = (
        f"{DOCKER_APT_RETRY_BEGIN}\n"
        "RUN set -eux; \\\n"
        "    if mkdir -p /etc/apt/apt.conf.d 2>/dev/null && "
        "[ -w /etc/apt/apt.conf.d ]; then \\\n"
        "      printf '%s\\n' \\\n"
        "        'Acquire::Retries \"5\";' \\\n"
        "        'Acquire::http::No-Cache \"true\";' \\\n"
        "        'Acquire::https::No-Cache \"true\";' \\\n"
        "        'Acquire::Check-Valid-Until \"false\";' \\\n"
        "        > /etc/apt/apt.conf.d/80-loopx-retry; \\\n"
        "      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb; \\\n"
        "    else \\\n"
        "      echo 'loopx apt retry config skipped: apt config directory is not writable'; \\\n"
        "    fi\n"
        f"{DOCKER_APT_RETRY_END}"
    )
    patched_lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        patched_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("FROM ") and not inserted:
            patched_lines.extend(["", *block.splitlines(), ""])
            inserted = True
    if not inserted:
        patched_lines = [*block.splitlines(), "", *text.splitlines()]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == dockerfile.read_text(encoding="utf-8"):
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def patch_dockerfile_pip_bootstrap(dockerfile: Path) -> bool:
    """Add public-safe pip retry/index defaults to staged Dockerfiles."""

    if not dockerfile_needs_pip_bootstrap_patch(dockerfile):
        return False
    original = dockerfile.read_text(encoding="utf-8")
    text = _strip_marker_block(
        original,
        DOCKER_PIP_BOOTSTRAP_BEGIN,
        DOCKER_PIP_BOOTSTRAP_END,
    )
    block = (
        f"{DOCKER_PIP_BOOTSTRAP_BEGIN}\n"
        f"ARG LOOPX_SKILLSBENCH_PIP_INDEX_URL={DEFAULT_DOCKER_PIP_INDEX_URL}\n"
        f"ARG LOOPX_SKILLSBENCH_PIP_EXTRA_INDEX_URL={DEFAULT_DOCKER_PIP_EXTRA_INDEX_URL}\n"
        "ENV PIP_INDEX_URL=${LOOPX_SKILLSBENCH_PIP_INDEX_URL} \\\n"
        "    PIP_EXTRA_INDEX_URL=${LOOPX_SKILLSBENCH_PIP_EXTRA_INDEX_URL} \\\n"
        "    PIP_DEFAULT_TIMEOUT=120 \\\n"
        "    PIP_RETRIES=10 \\\n"
        "    PIP_DISABLE_PIP_VERSION_CHECK=1\n"
        f"{DOCKER_PIP_BOOTSTRAP_END}"
    )
    patched_lines: list[str] = []
    inserted = False
    heredoc_delimiter: str | None = None
    for line in text.splitlines():
        patched_lines.append(line)
        if heredoc_delimiter is not None:
            if line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = dockerfile_runtime.dockerfile_heredoc_delimiter(line)
        stripped = line.strip()
        if (
            _is_dockerfile_from_instruction(stripped)
            and " scratch" not in stripped.lower()
        ):
            patched_lines.extend(["", *block.splitlines(), ""])
            inserted = True
    if not inserted:
        patched_lines = [*block.splitlines(), "", *text.splitlines()]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def _is_dockerfile_from_instruction(stripped_line: str) -> bool:
    """Match Dockerfile ``FROM`` instructions without matching heredoc Python."""

    return bool(
        re.match(
            r"^FROM(?:\s+--platform=\S+)?\s+\S+(?:\s+AS\s+\S+)?\s*$",
            stripped_line,
            flags=re.IGNORECASE,
        )
    )


def patch_dockerfile_codex_acp_runtime_tools(dockerfile: Path) -> bool:
    """Preinstall tiny ACP runtime tools at image-build time, not run time."""

    if not dockerfile.exists():
        return False
    text = dockerfile.read_text(encoding="utf-8")
    if re.search(r"^\s*FROM\s+scratch(?:\s|$)", text, flags=re.IGNORECASE | re.MULTILINE):
        return False
    text = _strip_marker_block(
        text,
        DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN,
        DOCKER_CODEX_ACP_RUNTIME_TOOLS_END,
    )
    block = (
        f"{DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN}\n"
        "RUN set -eux; \\\n"
        "    if command -v curl >/dev/null 2>&1 && \\\n"
        "       command -v tar >/dev/null 2>&1 && \\\n"
        "       command -v xz >/dev/null 2>&1; then \\\n"
        "      exit 0; \\\n"
        "    fi; \\\n"
        "    if command -v apt-get >/dev/null 2>&1; then \\\n"
        "      mkdir -p /etc/apt/apt.conf.d; \\\n"
        "      printf '%s\\n' \\\n"
        "        'Acquire::Retries \"5\";' \\\n"
        "        'Acquire::http::No-Cache \"true\";' \\\n"
        "        'Acquire::https::No-Cache \"true\";' \\\n"
        "        'Acquire::Check-Valid-Until \"false\";' \\\n"
        "        > /etc/apt/apt.conf.d/80-loopx-retry; \\\n"
        "      apt-get update -qq; \\\n"
        "      apt-get install -y -qq --no-install-recommends ca-certificates curl tar xz-utils; \\\n"
        "      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb; \\\n"
        "    elif command -v apk >/dev/null 2>&1; then \\\n"
        "      apk add --no-cache ca-certificates curl tar xz; \\\n"
        "    elif command -v microdnf >/dev/null 2>&1; then \\\n"
        "      (microdnf install -y ca-certificates tar xz || microdnf install -y ca-certificates tar xz-utils); \\\n"
        "      if ! command -v curl >/dev/null 2>&1; then microdnf install -y curl-minimal || microdnf install -y curl; fi; \\\n"
        "    elif command -v dnf >/dev/null 2>&1; then \\\n"
        "      (dnf -y install ca-certificates tar xz || dnf -y install ca-certificates tar xz-utils); \\\n"
        "      if ! command -v curl >/dev/null 2>&1; then dnf -y install curl-minimal || dnf -y install curl; fi; \\\n"
        "    elif command -v yum >/dev/null 2>&1; then \\\n"
        "      (yum install -y ca-certificates tar xz || yum install -y ca-certificates tar xz-utils); \\\n"
        "      if ! command -v curl >/dev/null 2>&1; then yum install -y curl-minimal || yum install -y curl; fi; \\\n"
        "    else \\\n"
        "      echo 'Codex ACP runtime requires curl, tar, and xz' >&2; \\\n"
        "      exit 127; \\\n"
        "    fi; \\\n"
        "    command -v curl >/dev/null 2>&1; \\\n"
        "    command -v tar >/dev/null 2>&1; \\\n"
        "    command -v xz >/dev/null 2>&1\n"
        f"{DOCKER_CODEX_ACP_RUNTIME_TOOLS_END}"
    )
    patched_lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        patched_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("FROM ") and not inserted:
            patched_lines.extend(["", *block.splitlines(), ""])
            inserted = True
    if not inserted:
        patched_lines = [*block.splitlines(), "", *text.splitlines()]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == dockerfile.read_text(encoding="utf-8"):
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def patch_dockerfile_loopx_case_python_runtime(dockerfile: Path) -> bool:
    """Ensure the final task image can execute the case-local LoopX CLI."""

    if not dockerfile.exists():
        return False
    original = dockerfile.read_text(encoding="utf-8")
    text = _strip_marker_block(
        original,
        DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN,
        DOCKER_LOOPX_CASE_PYTHON_RUNTIME_END,
    )
    lines = text.splitlines()
    from_indexes = [
        index
        for index, line in enumerate(lines)
        if _is_dockerfile_from_instruction(line.strip())
    ]
    if not from_indexes:
        return False
    final_from_index = from_indexes[-1]
    if " scratch" in f" {lines[final_from_index].strip().lower()} ":
        return False
    block = (
        f"{DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN}\n"
        "RUN set -eux; \\\n"
        "    if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then \\\n"
        "      exit 0; \\\n"
        "    fi; \\\n"
        "    if command -v apt-get >/dev/null 2>&1; then \\\n"
        "      DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 update -qq; \\\n"
        "      DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 install -y -qq --no-install-recommends python3; \\\n"
        "      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb; \\\n"
        "    elif command -v apk >/dev/null 2>&1; then \\\n"
        "      apk add --no-cache python3; \\\n"
        "    elif command -v microdnf >/dev/null 2>&1; then \\\n"
        "      microdnf install -y python3; \\\n"
        "    elif command -v dnf >/dev/null 2>&1; then \\\n"
        "      dnf -y install python3; \\\n"
        "    elif command -v yum >/dev/null 2>&1; then \\\n"
        "      yum install -y python3; \\\n"
        "    else \\\n"
        "      echo 'LoopX case lifecycle requires Python in the final benchmark image' >&2; \\\n"
        "      exit 127; \\\n"
        "    fi; \\\n"
        "    command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1\n"
        f"{DOCKER_LOOPX_CASE_PYTHON_RUNTIME_END}"
    )
    trailing_lines = lines[final_from_index + 1 :]
    while trailing_lines and not trailing_lines[0].strip():
        trailing_lines.pop(0)
    patched_lines = [
        *lines[: final_from_index + 1],
        "",
        *block.splitlines(),
        "",
        *trailing_lines,
    ]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    if patched == original:
        return False
    _write_text_atomic(dockerfile, patched)
    return True


def dockerfile_references_skills_build_context(dockerfile: Path) -> bool:
    """Return whether the Dockerfile copies the local ``skills`` build context."""

    if not dockerfile.exists():
        return False
    try:
        text = dockerfile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    pattern = re.compile(r"^\s*(?:COPY|ADD)\b[^\n]*\bskills(?:\s|$)", re.MULTILINE)
    return bool(pattern.search(text))


def ensure_empty_skills_build_context(dockerfile: Path) -> bool:
    """Create an empty ``skills`` context when staging removed task skills."""

    if not dockerfile_references_skills_build_context(dockerfile):
        return False
    skills_dir = dockerfile.parent / "skills"
    if skills_dir.exists():
        return False
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / ".loopx_keep").write_text(
        "empty SkillsBench build context created by LoopX staging\n",
        encoding="utf-8",
    )
    return True


def ensure_verifier_script_executable(verifier: Path) -> bool:
    """Ensure a staged verifier remains executable after atomic text patches."""

    if not verifier.is_file():
        return False
    try:
        verifier.chmod(verifier.stat().st_mode | 0o111)
        return bool(verifier.stat().st_mode & 0o111)
    except OSError:
        return False


def stage_task_for_sandbox(
    *,
    task_path: Path,
    jobs_dir: Path,
    job_name: str,
    sandbox: str,
    include_task_skills: bool = True,
    benchmark_egress_proxy_env: Mapping[str, str] | None = None,
    docker_gcr_mirror_prefix: str = "",
    verifier_dependency_cache_enabled: bool = False,
    loopx_case_runtime_required: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Return the task path to run, staging Docker tasks when setup needs it."""

    task_path = task_path.expanduser().resolve()
    metadata: dict[str, Any] = {
        "schema_version": "skillsbench_task_staging_v0",
        "original_task_name": task_path.name,
        "sandbox": sandbox,
        "include_task_skills": include_task_skills,
        "staged": False,
        "app_skills_mount_patch_applied": False,
        "apt_retry_patch_applied": False,
        "dockerfile_ubuntu_apt_mirror_patch_required": False,
        "dockerfile_ubuntu_apt_mirror_patch_applied": False,
        "dockerfile_ubuntu_apt_mirror_host": "",
        "dockerfile_ubuntu_apt_mirror_raw_url_recorded": False,
        "dockerfile_pip_install_risk_detected": False,
        "dockerfile_pip_bootstrap_patch_required": False,
        "dockerfile_pip_bootstrap_patch_applied": False,
        "dockerfile_venv_pip_invocation_patch_required": False,
        "dockerfile_venv_pip_invocation_patch_applied": False,
        "dockerfile_gcr_mirror_configured": bool(
            _normalized_docker_gcr_mirror_prefix(docker_gcr_mirror_prefix)
        ),
        "dockerfile_gcr_mirror_patch_required": False,
        "dockerfile_gcr_mirror_patch_applied": False,
        "dockerfile_gcr_mirror_raw_prefix_recorded": False,
        "dockerfile_elan_toolchain_retry_patch_required": False,
        "dockerfile_elan_toolchain_retry_patch_applied": False,
        "dockerfile_wget_gpg_key_retry_patch_required": False,
        "dockerfile_wget_gpg_key_retry_patch_applied": False,
        "dockerfile_network_download_retry_patch_required": False,
        "dockerfile_network_download_retry_patch_applied": False,
        "dockerfile_uv_bootstrap_risk_detected": False,
        "dockerfile_uv_bootstrap_mirror_patch_required": False,
        "dockerfile_uv_bootstrap_mirror_patch_applied": False,
        "dockerfile_uv_bootstrap_pip_fallback_patch_applied": False,
        "dockerfile_apache_archive_mirror_patch_required": False,
        "dockerfile_apache_archive_mirror_patch_applied": False,
        "dockerfile_apache_archive_mirror_host": "",
        "dockerfile_apache_archive_raw_url_recorded": False,
        "dockerfile_maven_mirror_patch_required": False,
        "dockerfile_maven_mirror_patch_applied": False,
        "dockerfile_maven_mirror_host": "",
        "dockerfile_maven_mirror_raw_url_recorded": False,
        "codex_acp_runtime_tools_patch_applied": False,
        "loopx_case_python_runtime_patch_required": False,
        "loopx_case_python_runtime_patch_applied": False,
        "empty_skills_build_context_required": False,
        "empty_skills_build_context_created": False,
        "verifier_uv_bootstrap_risk_detected": False,
        "verifier_external_download_risk_detected": False,
        "verifier_package_install_risk_detected": False,
        "verifier_bootstrap_risk_categories": [],
        "verifier_uv_bootstrap_mirror_patch_required": False,
        "verifier_uv_bootstrap_mirror_patch_applied": False,
        "verifier_uv_bootstrap_pip_fallback_patch_applied": False,
        "verifier_script_executable_required": False,
        "verifier_script_executable_ready": False,
        "verifier_dependency_cache_required": False,
        "verifier_dependency_cache_env_patch_applied": False,
        "verifier_dependency_cache_env_key_count": 0,
        "verifier_dependency_cache_raw_path_recorded": False,
        "benchmark_egress_proxy_verifier_env_patch_required": False,
        "benchmark_egress_proxy_verifier_env_patch_applied": False,
        "benchmark_egress_proxy_verifier_env_key_count": 0,
        "benchmark_egress_proxy_verifier_env_raw_proxy_recorded": False,
        "benchmark_egress_proxy_dockerfile_env_patch_required": False,
        "benchmark_egress_proxy_dockerfile_env_patch_applied": False,
        "benchmark_egress_proxy_dockerfile_java_opts_patch_applied": False,
        "benchmark_egress_proxy_dockerfile_env_key_count": 0,
        "benchmark_egress_proxy_dockerfile_env_raw_proxy_recorded": False,
        "task_skills_removed": False,
        "resource_cap_patch": {
            "schema_version": "skillsbench_local_docker_resource_cap_v0",
            "applied": False,
        },
    }
    if sandbox != "docker":
        return task_path, metadata

    host_cpus = docker_host_cpu_count()
    requested_cpus = _task_requested_cpus(task_path / "task.toml")
    needs_resource_cap = (
        host_cpus is not None
        and requested_cpus is not None
        and requested_cpus > host_cpus
    )
    has_task_skills = (task_path / "environment" / "skills").is_dir()
    needs_apt_retry_patch = dockerfile_needs_apt_retry_patch(
        task_path / "environment" / "Dockerfile"
    )
    needs_ubuntu_apt_mirror_patch = (
        dockerfile_runtime.needs_ubuntu_apt_mirror_patch(
            task_path / "environment" / "Dockerfile"
        )
    )
    needs_pip_bootstrap_patch = dockerfile_needs_pip_bootstrap_patch(
        task_path / "environment" / "Dockerfile"
    )
    needs_venv_pip_invocation_patch = (
        dockerfile_runtime.needs_venv_pip_invocation_patch(
            task_path / "environment" / "Dockerfile"
        )
    )
    needs_gcr_mirror_patch = dockerfile_needs_gcr_mirror_rewrite(
        task_path / "environment" / "Dockerfile",
        mirror_prefix=docker_gcr_mirror_prefix,
    )
    needs_elan_toolchain_retry_patch = dockerfile_needs_elan_toolchain_retry_patch(
        task_path / "environment" / "Dockerfile"
    )
    needs_wget_gpg_key_retry_patch = dockerfile_needs_wget_gpg_key_retry_patch(
        task_path / "environment" / "Dockerfile"
    )
    needs_network_download_retry_patch = dockerfile_needs_network_download_retry_patch(
        task_path / "environment" / "Dockerfile"
    )
    needs_dockerfile_uv_mirror_patch = dockerfile_needs_uv_bootstrap_mirror_patch(
        task_path / "environment" / "Dockerfile"
    )
    needs_apache_archive_mirror_patch = (
        dockerfile_needs_apache_archive_mirror_rewrite(
            task_path / "environment" / "Dockerfile"
        )
    )
    needs_maven_mirror_patch = dockerfile_needs_maven_mirror_patch(
        task_path / "environment" / "Dockerfile"
    )
    verifier_risk = verifier_bootstrap.skillsbench_verifier_bootstrap_risk(task_path)
    needs_verifier_uv_mirror_patch = bool(
        verifier_risk.get("verifier_uv_bootstrap_risk_detected")
        and verifier_risk.get("verifier_uv_bootstrap_version")
    )
    verifier_proxy_exports = _verifier_benchmark_egress_proxy_exports(
        benchmark_egress_proxy_env
    )
    verifier_script = proxy_runtime.skillsbench_verifier_script(task_path)
    verifier_script_present = verifier_script.is_file()
    needs_verifier_proxy_env_patch = bool(
        verifier_proxy_exports and verifier_script_present
    )
    needs_verifier_dependency_cache = bool(
        verifier_dependency_cache_enabled
        and verifier_script_present
        and verifier_risk.get("verifier_bootstrap_risk_detected")
    )
    needs_dockerfile_proxy_env_patch = bool(
        verifier_proxy_exports and (task_path / "environment" / "Dockerfile").exists()
    )
    needs_runtime_tools_patch = (task_path / "environment" / "Dockerfile").exists()
    needs_loopx_case_python_runtime_patch = bool(
        loopx_case_runtime_required
        and (task_path / "environment" / "Dockerfile").exists()
    )
    metadata["apt_setup_risk_detected"] = needs_apt_retry_patch
    metadata["apt_retry_patch_required"] = needs_apt_retry_patch
    metadata["apt_risk_preflight_blocked"] = False
    metadata["dockerfile_ubuntu_apt_mirror_patch_required"] = (
        needs_ubuntu_apt_mirror_patch
    )
    if needs_ubuntu_apt_mirror_patch:
        metadata["dockerfile_ubuntu_apt_mirror_host"] = (
            dockerfile_runtime.DEFAULT_UBUNTU_APT_MIRROR_HOST
        )
    metadata["dockerfile_pip_install_risk_detected"] = needs_pip_bootstrap_patch
    metadata["dockerfile_pip_bootstrap_patch_required"] = needs_pip_bootstrap_patch
    metadata["dockerfile_venv_pip_invocation_patch_required"] = (
        needs_venv_pip_invocation_patch
    )
    if needs_pip_bootstrap_patch:
        metadata["dockerfile_pip_index_host"] = DEFAULT_DOCKER_PIP_INDEX_HOST
    metadata["dockerfile_gcr_mirror_patch_required"] = needs_gcr_mirror_patch
    metadata["dockerfile_elan_toolchain_retry_patch_required"] = (
        needs_elan_toolchain_retry_patch
    )
    metadata["dockerfile_wget_gpg_key_retry_patch_required"] = (
        needs_wget_gpg_key_retry_patch
    )
    metadata["dockerfile_network_download_retry_patch_required"] = (
        needs_network_download_retry_patch
    )
    metadata["dockerfile_uv_bootstrap_risk_detected"] = (
        needs_dockerfile_uv_mirror_patch
    )
    metadata["dockerfile_uv_bootstrap_mirror_patch_required"] = (
        needs_dockerfile_uv_mirror_patch
    )
    if needs_dockerfile_uv_mirror_patch:
        metadata["dockerfile_uv_bootstrap_mirror_host"] = (
            DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST
        )
        versions = _dockerfile_uv_bootstrap_versions(
            (task_path / "environment" / "Dockerfile").read_text(
                encoding="utf-8",
                errors="replace",
            )
        )
        if versions:
            metadata["dockerfile_uv_bootstrap_version"] = versions[0]
    metadata["dockerfile_apache_archive_mirror_patch_required"] = (
        needs_apache_archive_mirror_patch
    )
    if needs_apache_archive_mirror_patch:
        metadata["dockerfile_apache_archive_mirror_host"] = (
            DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
        )
    metadata["dockerfile_maven_mirror_patch_required"] = needs_maven_mirror_patch
    if needs_maven_mirror_patch:
        metadata["dockerfile_maven_mirror_host"] = DEFAULT_DOCKER_MAVEN_MIRROR_HOST
    metadata["verifier_bootstrap_risk_detected"] = bool(
        verifier_risk.get("verifier_bootstrap_risk_detected")
    )
    metadata["verifier_uv_bootstrap_risk_detected"] = bool(
        verifier_risk.get("verifier_uv_bootstrap_risk_detected")
    )
    metadata["verifier_external_download_risk_detected"] = bool(
        verifier_risk.get("verifier_external_download_risk_detected")
    )
    metadata["verifier_package_install_risk_detected"] = bool(
        verifier_risk.get("verifier_package_install_risk_detected")
    )
    metadata["verifier_bootstrap_risk_categories"] = list(
        verifier_risk.get("verifier_bootstrap_risk_categories") or []
    )
    metadata["verifier_uv_bootstrap_mirror_patch_required"] = (
        needs_verifier_uv_mirror_patch
    )
    metadata["verifier_script_executable_required"] = verifier_script_present
    metadata["verifier_dependency_cache_required"] = (
        needs_verifier_dependency_cache
    )
    metadata["benchmark_egress_proxy_verifier_env_patch_required"] = (
        needs_verifier_proxy_env_patch
    )
    metadata["benchmark_egress_proxy_verifier_env_key_count"] = len(
        verifier_proxy_exports
    )
    metadata["benchmark_egress_proxy_dockerfile_env_patch_required"] = (
        needs_dockerfile_proxy_env_patch
    )
    metadata["benchmark_egress_proxy_dockerfile_env_key_count"] = len(
        verifier_proxy_exports
    )
    if isinstance(verifier_risk.get("verifier_uv_bootstrap_version"), str):
        metadata["verifier_uv_bootstrap_version"] = verifier_risk[
            "verifier_uv_bootstrap_version"
        ]
    metadata["verifier_bootstrap_risk_preflight_blocked"] = False
    metadata["loopx_case_python_runtime_patch_required"] = (
        needs_loopx_case_python_runtime_patch
    )
    if (
        not has_task_skills
        and not needs_resource_cap
        and not needs_apt_retry_patch
        and not needs_ubuntu_apt_mirror_patch
        and not needs_pip_bootstrap_patch
        and not needs_venv_pip_invocation_patch
        and not needs_gcr_mirror_patch
        and not needs_elan_toolchain_retry_patch
        and not needs_wget_gpg_key_retry_patch
        and not needs_network_download_retry_patch
        and not needs_dockerfile_uv_mirror_patch
        and not needs_apache_archive_mirror_patch
        and not needs_maven_mirror_patch
        and not needs_runtime_tools_patch
        and not needs_loopx_case_python_runtime_patch
        and not needs_verifier_uv_mirror_patch
        and not verifier_script_present
        and not needs_verifier_proxy_env_patch
        and not needs_verifier_dependency_cache
        and not needs_dockerfile_proxy_env_patch
    ):
        metadata["resource_cap_patch"] = {
            "schema_version": "skillsbench_local_docker_resource_cap_v0",
            "applied": False,
            "host_cpus": host_cpus,
            "requested_cpus": requested_cpus,
            "effective_cpus": requested_cpus,
        }
        return task_path, metadata

    staged_root = jobs_dir.expanduser() / job_name / "prepared-tasks"
    staged_path = staged_root / task_path.name
    if staged_path.exists():
        shutil.rmtree(staged_path)
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        task_path,
        staged_path,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    staged_skills_dir = staged_path / "environment" / "skills"
    task_skills_removed = False
    if not include_task_skills and staged_skills_dir.exists():
        shutil.rmtree(staged_skills_dir)
        task_skills_removed = True
    empty_skills_context_required = dockerfile_references_skills_build_context(
        staged_path / "environment" / "Dockerfile"
    )
    empty_skills_context_created = ensure_empty_skills_build_context(
        staged_path / "environment" / "Dockerfile"
    )
    patched = patch_dockerfile_app_skills_mount(
        staged_path / "environment" / "Dockerfile"
    )
    loopx_case_python_runtime_patched = False
    if needs_loopx_case_python_runtime_patch:
        loopx_case_python_runtime_patched = (
            patch_dockerfile_loopx_case_python_runtime(
                staged_path / "environment" / "Dockerfile"
            )
        )
    dockerfile_proxy_metadata = patch_dockerfile_benchmark_egress_proxy_env(
        staged_path / "environment" / "Dockerfile",
        proxy_env=benchmark_egress_proxy_env,
    )
    apt_retry_patched = patch_dockerfile_apt_retry(
        staged_path / "environment" / "Dockerfile"
    )
    ubuntu_apt_mirror_patched = dockerfile_runtime.patch_ubuntu_apt_mirror(
        staged_path / "environment" / "Dockerfile"
    )
    pip_bootstrap_patched = patch_dockerfile_pip_bootstrap(
        staged_path / "environment" / "Dockerfile"
    )
    venv_pip_invocation_patched = dockerfile_runtime.patch_venv_pip_invocations(
        staged_path / "environment" / "Dockerfile"
    )
    gcr_mirror_patched = patch_dockerfile_gcr_mirror(
        staged_path / "environment" / "Dockerfile",
        mirror_prefix=docker_gcr_mirror_prefix,
    )
    elan_toolchain_retry_patched = patch_dockerfile_elan_toolchain_retry(
        staged_path / "environment" / "Dockerfile"
    )
    wget_gpg_key_retry_patched = patch_dockerfile_wget_gpg_key_retry(
        staged_path / "environment" / "Dockerfile"
    )
    dockerfile_uv_mirror_metadata = patch_dockerfile_uv_bootstrap_mirror(
        staged_path / "environment" / "Dockerfile"
    )
    apache_archive_mirror_patched = patch_dockerfile_apache_archive_mirror(
        staged_path / "environment" / "Dockerfile"
    )
    network_download_retry_patched = patch_dockerfile_network_download_retry(
        staged_path / "environment" / "Dockerfile"
    )
    maven_mirror_patched = patch_dockerfile_maven_mirror(
        staged_path / "environment" / "Dockerfile"
    )
    runtime_tools_patched = patch_dockerfile_codex_acp_runtime_tools(
        staged_path / "environment" / "Dockerfile"
    )
    staged_verifier_script = proxy_runtime.skillsbench_verifier_script(staged_path)
    uv_mirror_metadata = verifier_bootstrap.patch_verifier_uv_bootstrap_mirror(
        staged_verifier_script
    )
    verifier_proxy_metadata = patch_verifier_benchmark_egress_proxy_env(
        staged_verifier_script,
        proxy_env=benchmark_egress_proxy_env,
    )
    verifier_cache_metadata = verifier_cache.patch_verifier_dependency_cache_env(
        staged_verifier_script,
        enabled=needs_verifier_dependency_cache,
    )
    verifier_script_executable_ready = ensure_verifier_script_executable(
        staged_verifier_script
    )
    resource_cap_patch = patch_task_cpu_cap_for_local_docker(
        staged_path / "task.toml",
        host_cpus=host_cpus,
    )
    metadata.update(
        {
            "staged": True,
            "staged_task_path": str(staged_path),
            "app_skills_mount_patch_applied": patched,
            "apt_retry_patch_applied": apt_retry_patched,
            "dockerfile_ubuntu_apt_mirror_patch_applied": (
                ubuntu_apt_mirror_patched
            ),
            "dockerfile_ubuntu_apt_mirror_host": (
                dockerfile_runtime.DEFAULT_UBUNTU_APT_MIRROR_HOST
                if ubuntu_apt_mirror_patched
                else ""
            ),
            "dockerfile_ubuntu_apt_mirror_raw_url_recorded": False,
            "dockerfile_pip_bootstrap_patch_applied": pip_bootstrap_patched,
            "dockerfile_venv_pip_invocation_patch_applied": (
                venv_pip_invocation_patched
            ),
            "dockerfile_pip_index_host": (
                DEFAULT_DOCKER_PIP_INDEX_HOST if pip_bootstrap_patched else ""
            ),
            "dockerfile_gcr_mirror_patch_applied": gcr_mirror_patched,
            "dockerfile_gcr_mirror_raw_prefix_recorded": False,
            "dockerfile_elan_toolchain_retry_patch_applied": (
                elan_toolchain_retry_patched
            ),
            "dockerfile_wget_gpg_key_retry_patch_applied": (
                wget_gpg_key_retry_patched
            ),
            "dockerfile_network_download_retry_patch_applied": (
                network_download_retry_patched
            ),
            "dockerfile_uv_bootstrap_mirror_patch_applied": (
                bool(
                    dockerfile_uv_mirror_metadata.get(
                        "dockerfile_uv_bootstrap_mirror_patch_applied"
                    )
                )
            ),
            "dockerfile_uv_bootstrap_pip_fallback_patch_applied": (
                bool(
                    dockerfile_uv_mirror_metadata.get(
                        "dockerfile_uv_bootstrap_pip_fallback_patch_applied"
                    )
                )
            ),
            **uv_cache.stage_uv_binary_cache_context(staged_path / "environment"),
            "dockerfile_uv_bootstrap_mirror_host": (
                str(
                    dockerfile_uv_mirror_metadata.get(
                        "dockerfile_uv_bootstrap_mirror_host"
                    )
                    or ""
                )
            ),
            "dockerfile_apache_archive_mirror_patch_applied": (
                apache_archive_mirror_patched
            ),
            "dockerfile_apache_archive_mirror_host": (
                DEFAULT_DOCKER_APACHE_ARCHIVE_MIRROR_HOST
                if apache_archive_mirror_patched
                else ""
            ),
            "dockerfile_apache_archive_raw_url_recorded": False,
            "dockerfile_maven_mirror_patch_applied": maven_mirror_patched,
            "dockerfile_maven_mirror_host": (
                DEFAULT_DOCKER_MAVEN_MIRROR_HOST if maven_mirror_patched else ""
            ),
            "dockerfile_maven_mirror_raw_url_recorded": False,
            "codex_acp_runtime_tools_patch_applied": runtime_tools_patched,
            "loopx_case_python_runtime_patch_required": (
                needs_loopx_case_python_runtime_patch
            ),
            "loopx_case_python_runtime_patch_applied": (
                loopx_case_python_runtime_patched
            ),
            "empty_skills_build_context_required": empty_skills_context_required,
            "empty_skills_build_context_created": empty_skills_context_created,
            "verifier_script_executable_ready": verifier_script_executable_ready,
            "app_skills_mount_target": "/app/skills",
            "original_task_mutated": False,
            "task_skills_removed": task_skills_removed,
            "resource_cap_patch": resource_cap_patch,
        }
    )
    for key, value in uv_mirror_metadata.items():
        if (
            key == "verifier_uv_bootstrap_risk_detected"
            and value is False
            and metadata.get(key) is True
        ):
            continue
        metadata[key] = value
    for key, value in dockerfile_uv_mirror_metadata.items():
        if (
            key == "dockerfile_uv_bootstrap_risk_detected"
            and value is False
            and metadata.get(key) is True
        ):
            continue
        if value in ("", False) and metadata.get(key) not in ("", False, None):
            continue
        metadata[key] = value
    metadata.update(dockerfile_proxy_metadata)
    metadata.update(verifier_proxy_metadata)
    metadata.update(verifier_cache_metadata)
    if (
        metadata.get("verifier_script_executable_required") is True
        and metadata.get("verifier_script_executable_ready") is not True
    ):
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench staged verifier script is not executable"
        )
    if (
        metadata.get("benchmark_egress_proxy_verifier_env_patch_required") is True
        and metadata.get("benchmark_egress_proxy_verifier_env_patch_applied")
        is not True
    ):
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench verifier egress proxy patch required but not applied"
        )
    if (
        metadata.get("verifier_dependency_cache_required") is True
        and metadata.get("verifier_dependency_cache_env_patch_applied") is not True
    ):
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench verifier dependency cache required but not applied"
        )
    return staged_path, metadata


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    task_id = args.task_id
    route = args.route
    route_slug = route.replace("-", "_")
    intermediate_soft_verify_policy = product_mode_soft_verify_policy_for_route(
        route,
        args.product_mode_soft_verify_policy,
    )
    job_name = args.job_name or (
        f"skillsbench-{task_id}-{route}-{_now_stamp()}"
    )
    if route == LOOPX_GOAL_START_PRODUCT_MODE_ROUTE:
        rollout_suffix = "loopx_goal_start_product_mode"
    elif route == LOOPX_PRODUCT_MODE_ROUTE:
        rollout_suffix = "loopx_product_mode"
    elif route == "raw-codex-autonomous-max5":
        rollout_suffix = "raw_codex_autonomous_max5"
    elif route == CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE:
        rollout_suffix = "codex_acp_blind_loop"
    elif route == CODEX_CLI_GOAL_BASELINE_ROUTE:
        rollout_suffix = "codex_cli_goal"
    elif route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE:
        rollout_suffix = "codex_app_server_goal"
    else:
        rollout_suffix = route_slug
    rollout_name = args.rollout_name or f"{task_id}__{rollout_suffix}"
    jobs_dir = Path(args.jobs_dir).expanduser()
    result_path = jobs_dir / job_name / rollout_name / "result.json"
    compact_path = jobs_dir / job_name / rollout_name / "benchmark_run.compact.json"
    setup_only_preflight_path = (
        jobs_dir / job_name / "setup_only_preflight.public.json"
    )
    controller_trace_path = jobs_dir / job_name / "loopx_controller_trace.public.json"
    app_server_goal_worker_trace_dir = (
        jobs_dir / job_name / "app_server_goal_worker_traces"
    )
    host_local_acp_relay_trace_dir = (
        jobs_dir / job_name / "host_local_acp_relay_traces"
    )
    task_path = Path(args.skillsbench_root).expanduser() / "tasks" / task_id
    setup_preflight = skillsbench_task_setup_preflight(
        task_path=task_path,
        sandbox=args.sandbox,
    )
    agent_runtime_layer = _benchflow_agent_runtime_layer_contract(args)
    loopx_source_mount = _loopx_source_mount_contract(args)
    runner_source_fingerprint = runner_source.build_runner_source_fingerprint(repo_root=REPO_ROOT, expected_git_head=getattr(args, "expected_loopx_git_head", ""))
    requires_preinstalled_runtime = bool(agent_runtime_layer.get("required"))
    is_app_server_goal_route = route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
    is_codex_cli_goal_route = route == CODEX_CLI_GOAL_BASELINE_ROUTE
    reasoning_effort = _effective_reasoning_effort(args)
    app_server_reasoning_effort = _effective_app_server_reasoning_effort(args)
    codex_cli_reasoning_effort = _effective_codex_cli_reasoning_effort(args)
    app_server_goal_prompt_style = str(
        getattr(args, "app_server_goal_prompt_style", "bridge-only")
        or "bridge-only"
    )
    app_server_goal_followup_budget = (
        max(0, int(getattr(args, "app_server_goal_followup_max", 0) or 0))
        if is_app_server_goal_route
        else 0
    )
    independent_goal_attempt_budget = (
        max(1, int(getattr(args, "independent_goal_retries", 1) or 1))
        if route in INDEPENDENT_GOAL_RETRY_ROUTES
        else 1
    )
    codex_api_egress_preflight = _public_codex_api_egress_contract(
        args,
        status=(
            "pending"
            if _codex_api_egress_preflight_required(args)
            else "not_required"
        ),
        ready=not _codex_api_egress_preflight_required(args),
    )
    benchmark_egress_proxy = _public_benchmark_egress_proxy_contract(args)
    remote_command_file_bridge_materialized = bool(
        args.remote_command_file_bridge_ready
        or args.remote_command_file_bridge_probe
    )
    remote_command_file_bridge_probe_command_configured = bool(
        args.remote_command_file_bridge_probe_command
    )
    remote_command_file_bridge_solver_command_configured = bool(
        args.remote_command_file_bridge_solver_command
    )
    remote_command_file_bridge_agent_command_configured = bool(
        args.remote_command_file_bridge_agent_command
    )
    remote_command_file_bridge_solver_wiring_configured = bool(
        args.host_local_acp_launch
        and (
            route in HOST_LOCAL_BRIDGE_ROUTES
            or route == CODEX_CLI_GOAL_BASELINE_ROUTE
        )
        and remote_command_file_bridge_materialized
        and remote_command_file_bridge_solver_command_configured
    )
    remote_command_file_bridge_sandbox_auto_wiring_pending = bool(
        args.host_local_acp_launch
        and (
            route in HOST_LOCAL_BRIDGE_ROUTES
            or route == CODEX_CLI_GOAL_BASELINE_ROUTE
        )
        and remote_command_file_bridge_materialized
        and not remote_command_file_bridge_solver_command_configured
    )
    remote_command_file_bridge_agent_operation_trace_required = bool(
        (_is_case_loopx_route(route) or route == CODEX_CLI_GOAL_BASELINE_ROUTE)
        and (
            remote_command_file_bridge_solver_wiring_configured
            or remote_command_file_bridge_sandbox_auto_wiring_pending
        )
    )
    remote_command_file_bridge_agent_command_instrumented = bool(
        remote_command_file_bridge_solver_wiring_configured
    )
    if not remote_command_file_bridge_agent_operation_trace_required:
        remote_command_file_bridge_agent_operation_trace_status = "not_required"
    elif not remote_command_file_bridge_agent_command_configured:
        remote_command_file_bridge_agent_operation_trace_status = (
            "relay_generated_wrapper_pending_prompt"
        )
    elif remote_command_file_bridge_agent_command_instrumented:
        if (
            remote_command_file_bridge_agent_command_configured
            and not args.remote_command_file_bridge_agent_command_instrumented
        ):
            remote_command_file_bridge_agent_operation_trace_status = (
                "external_agent_command_relay_wrapped_pending_trace"
            )
        else:
            remote_command_file_bridge_agent_operation_trace_status = (
                "external_agent_command_declared_instrumented_pending_trace"
            )
    else:
        remote_command_file_bridge_agent_operation_trace_status = (
            "external_agent_command_uninstrumented"
        )
    remote_command_file_bridge_consumed_by_solver = False
    if remote_command_file_bridge_solver_wiring_configured:
        remote_command_file_bridge_consumption_status = (
            "solver_wiring_configured_pending_prompt"
        )
    elif remote_command_file_bridge_sandbox_auto_wiring_pending:
        remote_command_file_bridge_consumption_status = (
            "sandbox_bridge_auto_wiring_pending"
        )
    elif remote_command_file_bridge_materialized:
        remote_command_file_bridge_consumption_status = "probe_only_not_solver_wired"
    else:
        remote_command_file_bridge_consumption_status = "missing"
    app_server_goal_worker_contract = (
        build_skillsbench_app_server_goal_worker_contract(
            dataset=args.dataset,
            task_id=task_id,
            cwd="<skillsbench-task-workspace>",
            model=args.model,
            reasoning_effort=app_server_reasoning_effort,
            prompt_style=app_server_goal_prompt_style,
            sandbox="workspace-write",
            approval_policy="never",
            no_upload=True,
            submit_enabled=False,
            compact_reducer_ready=True,
            runner_integration_ready=bool(args.host_local_acp_launch),
        )
        if is_app_server_goal_route
        else None
    )
    run_permission_policy = build_skillsbench_run_permission_policy(
        route=route,
        max_wall_time_minutes=max(480, (int(args.outer_timeout_sec) + 59) // 60),
    )
    app_server_goal_round_semantics = (
        {
            "schema_version": "skillsbench_app_server_goal_round_semantics_v0",
            "route": CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
            "session_policy": (
                "single_thread_with_blinded_followups"
                if app_server_goal_followup_budget
                else "single_initial_goal_turn"
            ),
            "benchflow_max_rounds_budget": args.max_rounds,
            "max_rounds_budget_applies_to": (
                "benchflow_outer_controller_budget_not_native_goal_attempts"
            ),
            "initial_goal_turn_budget": 1,
            "same_thread_followup_budget": app_server_goal_followup_budget,
            "independent_attempt_budget": independent_goal_attempt_budget,
            "fresh_goal_thread_per_independent_attempt": True,
            "official_reward_feedback_forwarded_to_worker": False,
            "verifier_output_forwarded_to_worker": False,
        }
        if is_app_server_goal_route
        else {}
    )
    benchmark_canonical_lifecycle = canonical_lifecycle(
        process_started=True,
        runner_accepted_args=True,
    )
    launch_plan = {
        "schema_version": "skillsbench_runner_launch_plan_v0",
        "benchmark_id": args.dataset,
        "task_id": task_id,
        "route": route,
        "benchmark_canonical_lifecycle": benchmark_canonical_lifecycle,
        "agent": (
            "codex-app-server-goal"
            if is_app_server_goal_route
            else "codex-cli-goal"
            if is_codex_cli_goal_route
            else "codex-acp"
        ),
        "model": args.model,
        "reasoning_effort": reasoning_effort,
        "codex_cli_reasoning_effort": (
            codex_cli_reasoning_effort if not is_app_server_goal_route else ""
        ),
        "app_server_reasoning_effort": (
            app_server_reasoning_effort if is_app_server_goal_route else ""
        ),
        "app_server_goal_followup_max": app_server_goal_followup_budget,
        "app_server_goal_round_semantics": app_server_goal_round_semantics,
        "app_server_goal_prompt_style": (
            app_server_goal_prompt_style
            if is_app_server_goal_route
            else ""
        ),
        "run_group_id": str(args.run_group_id or ""),
        "sandbox": args.sandbox,
        "max_rounds": args.max_rounds,
        "independent_goal_retry": {
            "schema_version": "skillsbench_independent_goal_retry_config_v0",
            "enabled": bool(independent_goal_attempt_budget > 1),
            "attempt_budget": independent_goal_attempt_budget,
            "route_supported": route in INDEPENDENT_GOAL_RETRY_ROUTES,
            "fresh_goal_thread_per_attempt": True,
            "stop_policy": (
                "stop_after_first_official_reward_1_or_first_terminal_"
                "official_nonpassing_or_retry_budget"
            ),
            "official_reward_feedback_forwarded_to_agent": False,
            "verifier_output_forwarded_to_agent": False,
            "raw_task_text_read_into_public_state": False,
            "raw_trajectory_read_into_public_state": False,
            "raw_verifier_output_read_into_public_state": False,
        },
        "outer_timeout_sec": args.outer_timeout_sec,
        "sandbox_setup_timeout_sec": args.sandbox_setup_timeout,
        "agent_idle_timeout_sec": args.agent_idle_timeout,
        "local_codex_task_output_quiet_timeout_sec": (
            _effective_local_codex_task_output_quiet_timeout_sec(args)
        ),
        "include_task_skills": bool(args.include_task_skills),
        "host_local_acp_launch": bool(args.host_local_acp_launch),
        "codex_cli_goal_thread_prewarm": bool(getattr(args, "codex_cli_goal_thread_prewarm", False)),
        "bootstrap_light_candidate_required": bool(
            _formal_app_server_goal_bootstrap_light_guard_required(args)
        ),
        "bootstrap_light_fail_fast_required": bool(
            _formal_app_server_goal_bootstrap_light_fail_fast_required(args)
        ),
        "allow_staged_bootstrap_repair_run": bool(
            getattr(args, "allow_staged_bootstrap_repair_run", False)
        ),
        "fail_fast_on_apt_risk": bool(args.fail_fast_on_apt_risk),
        "apt_risk_fail_fast_defaulted": bool(
            getattr(args, "apt_risk_fail_fast_defaulted", False)
        ),
        "fail_fast_on_verifier_bootstrap_risk": bool(
            args.fail_fast_on_verifier_bootstrap_risk
        ),
        "verifier_bootstrap_fail_fast_defaulted": bool(
            getattr(args, "verifier_bootstrap_fail_fast_defaulted", False)
        ),
        "bootstrap_light_fail_fast_defaulted": bool(
            getattr(args, "bootstrap_light_fail_fast_defaulted", False)
        ),
        "remote_command_file_bridge_ready": bool(
            remote_command_file_bridge_materialized
        ),
        "benchflow_agent_runtime_layer": agent_runtime_layer,
        "loopx_source_mount": loopx_source_mount,
        "loopx_runner_source_fingerprint": runner_source_fingerprint,
        "skillsbench_root": str(Path(args.skillsbench_root).expanduser()),
        "jobs_dir": str(jobs_dir),
        "job_name": job_name,
        "rollout_name": rollout_name,
        "result_json": str(result_path),
        "compact_benchmark_run_json": str(compact_path),
        "setup_only_public_preflight": bool(
            getattr(args, "setup_only_public_preflight", False)
        ),
        "setup_only_public_preflight_json": str(setup_only_preflight_path),
        "controller_trace_json": str(controller_trace_path),
        "build_stall_timeout_requested_sec": _requested_build_stall_timeout_sec(args),
        "build_stall_timeout_sec": _effective_build_stall_timeout_sec(args),
        "app_server_goal_worker_trace_dir": (
            str(app_server_goal_worker_trace_dir)
            if is_app_server_goal_route
            else ""
        ),
        "host_local_acp_relay_trace_dir": (
            str(host_local_acp_relay_trace_dir)
            if args.host_local_acp_launch and not is_app_server_goal_route
            else ""
        ),
        "ledger_path": str(Path(args.ledger_path).expanduser()),
        "global_ledger_path": str(Path(args.global_ledger_path).expanduser()),
        "ledger_scope": _ledger_scope_label(
            Path(args.ledger_path).expanduser(),
            Path(args.global_ledger_path).expanduser(),
        ),
        "global_ledger_sync_enabled": not bool(args.skip_global_ledger_sync),
        "ledger_inherit_enabled": not bool(args.skip_ledger_inherit),
        "run_permission_policy": run_permission_policy,
        "task_setup_preflight": setup_preflight,
        "codex_api_egress_preflight": codex_api_egress_preflight,
        "benchmark_egress_proxy": benchmark_egress_proxy,
        "task_staging": {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": False,
            "sandbox": args.sandbox,
            "apt_setup_risk_detected": bool(
                setup_preflight.get("apt_setup_risk_detected")
            ),
            "apt_retry_patch_required": bool(
                setup_preflight.get("apt_retry_patch_required")
            ),
            "dockerfile_pip_install_risk_detected": bool(
                setup_preflight.get("dockerfile_pip_install_risk_detected")
            ),
            "dockerfile_pip_bootstrap_patch_required": bool(
                setup_preflight.get("dockerfile_pip_bootstrap_patch_required")
            ),
            "dockerfile_pip_bootstrap_patch_applied": False,
            "dockerfile_venv_pip_invocation_patch_required": False,
            "dockerfile_venv_pip_invocation_patch_applied": False,
            "dockerfile_pip_index_host": (
                DEFAULT_DOCKER_PIP_INDEX_HOST
                if setup_preflight.get("dockerfile_pip_bootstrap_patch_required")
                else ""
            ),
            "dockerfile_package_bootstrap_risk_preflight_blocked": False,
            "apt_risk_preflight_blocked": False,
            "bootstrap_light_preflight_blocked": False,
            "bootstrap_light_fail_fast_defaulted": bool(
                getattr(args, "bootstrap_light_fail_fast_defaulted", False)
            ),
            "verifier_bootstrap_risk_detected": bool(
                setup_preflight.get("verifier_bootstrap_risk_detected")
            ),
            "verifier_uv_bootstrap_risk_detected": bool(
                setup_preflight.get("verifier_uv_bootstrap_risk_detected")
            ),
            "verifier_uv_bootstrap_mirror_patch_required": bool(
                setup_preflight.get("verifier_uv_bootstrap_risk_detected")
                and setup_preflight.get("verifier_uv_bootstrap_version")
            ),
            "verifier_uv_bootstrap_mirror_patch_applied": False,
            "verifier_uv_bootstrap_pip_fallback_patch_applied": False,
            "benchmark_egress_proxy_verifier_env_patch_required": False,
            "benchmark_egress_proxy_verifier_env_patch_applied": False,
            "benchmark_egress_proxy_verifier_env_key_count": 0,
            "benchmark_egress_proxy_verifier_env_raw_proxy_recorded": False,
            "verifier_uv_bootstrap_version": (
                str(setup_preflight.get("verifier_uv_bootstrap_version"))
                if setup_preflight.get("verifier_uv_bootstrap_version")
                else ""
            ),
            "verifier_bootstrap_risk_preflight_blocked": False,
        },
        "runner_prerequisites": {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "benchmark_canonical_lifecycle": benchmark_canonical_lifecycle,
            "benchflow_setup_stall_timeout_enabled": (
                _effective_build_stall_timeout_sec(args) > 0
            ),
            "benchflow_setup_stall_timeout_requested_sec": (
                _requested_build_stall_timeout_sec(args)
            ),
            "benchflow_setup_stall_timeout_sec": int(
                _effective_build_stall_timeout_sec(args)
            ),
            "benchflow_setup_stall_raw_logs_read": False,
            "codex_acp_runtime_container_bootstrap": (
                False
                if is_app_server_goal_route
                else not requires_preinstalled_runtime
            ),
            "codex_acp_runtime_dependency_preflight": (
                False
                if is_app_server_goal_route
                else not requires_preinstalled_runtime
            ),
            "codex_acp_runtime_dependency_setup_skipped": (
                True
                if is_app_server_goal_route
                else requires_preinstalled_runtime
            ),
            "codex_acp_runtime_launch_preflight": False,
            "codex_acp_runtime_launch_preflight_stage": (
                "not_applicable_app_server_goal_worker"
                if is_app_server_goal_route
                else
                "preinstalled_benchflow_layer_before_acp_connect"
                if requires_preinstalled_runtime
                else "after_agent_install_before_acp_connect"
            ),
            "codex_acp_runtime_launch_preflight_status": (
                "not_requested" if is_app_server_goal_route else "pending"
            ),
            "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            "agent_execution_mode": (
                "host_codex_app_server_goal_worker"
                if is_app_server_goal_route
                else
                "host_local_acp"
                if args.host_local_acp_launch
                else "container_codex_acp_preinstalled_runtime"
                if requires_preinstalled_runtime
                else "container_codex_acp"
            ),
            "host_local_acp_launch": bool(args.host_local_acp_launch),
            "host_local_acp_launch_status": (
                "pending" if args.host_local_acp_launch else "not_requested"
            ),
            "codex_api_egress_preflight_required": bool(
                codex_api_egress_preflight.get("required")
            ),
            "codex_api_egress_preflight_ready": bool(
                codex_api_egress_preflight.get("ready")
            ),
            "codex_api_egress_preflight_status": str(
                codex_api_egress_preflight.get("status") or ""
            ),
            "codex_api_egress_preflight_error_kind": str(
                codex_api_egress_preflight.get("error_kind") or ""
            ),
            "codex_api_egress_mode_requested": str(
                codex_api_egress_preflight.get("requested_mode") or ""
            ),
            "codex_api_egress_mode_resolved": str(
                codex_api_egress_preflight.get("resolved_mode") or ""
            ),
            "codex_api_reverse_tunnel_required": bool(
                codex_api_egress_preflight.get("reverse_tunnel_required")
            ),
            "codex_api_reverse_tunnel_proxy_configured": bool(
                codex_api_egress_preflight.get("proxy_configured")
            ),
            "codex_api_reverse_tunnel_proxy_source": str(
                codex_api_egress_preflight.get("proxy_source") or ""
            ),
            "codex_api_reverse_tunnel_proxy_scheme": str(
                codex_api_egress_preflight.get("proxy_scheme") or ""
            ),
            "codex_api_reverse_tunnel_proxy_endpoint_kind": str(
                codex_api_egress_preflight.get("proxy_endpoint_kind") or ""
            ),
            "codex_api_reverse_tunnel_proxy_endpoint_port": int(
                codex_api_egress_preflight.get("proxy_endpoint_port") or 0
            ),
            "codex_api_reverse_tunnel_proxy_url_recorded": False,
            "benchmark_egress_proxy_ready": bool(
                benchmark_egress_proxy.get("ready")
            ),
            "benchmark_egress_proxy_configured": bool(
                benchmark_egress_proxy.get("proxy_configured")
            ),
            "benchmark_egress_proxy_required": bool(
                benchmark_egress_proxy.get("proxy_required")
            ),
            "benchmark_egress_proxy_status": str(
                benchmark_egress_proxy.get("status") or ""
            ),
            "benchmark_egress_proxy_error_kind": str(
                benchmark_egress_proxy.get("error_kind") or ""
            ),
            "benchmark_egress_proxy_mode_requested": str(
                benchmark_egress_proxy.get("requested_mode") or ""
            ),
            "benchmark_egress_proxy_source": str(
                benchmark_egress_proxy.get("proxy_source") or ""
            ),
            "benchmark_egress_proxy_env_key": str(
                benchmark_egress_proxy.get("proxy_env_key") or ""
            ),
            "benchmark_egress_proxy_scheme": str(
                benchmark_egress_proxy.get("proxy_scheme") or ""
            ),
            "benchmark_egress_proxy_endpoint_kind": str(
                benchmark_egress_proxy.get("proxy_endpoint_kind") or ""
            ),
            "benchmark_egress_proxy_endpoint_port": int(
                benchmark_egress_proxy.get("proxy_endpoint_port") or 0
            ),
            "benchmark_egress_no_proxy_configured": bool(
                benchmark_egress_proxy.get("no_proxy_configured")
            ),
            "benchmark_egress_no_proxy_entry_count": int(
                benchmark_egress_proxy.get("no_proxy_entry_count") or 0
            ),
            "benchmark_egress_no_proxy_raw_value_recorded": False,
            "benchmark_egress_proxy_url_recorded": False,
            "benchmark_egress_proxy_agent_env_injected": False,
            "benchmark_egress_proxy_docker_config_injected": False,
            "benchmark_egress_proxy_docker_config_path_recorded": False,
            "benchmark_egress_proxy_docker_config_raw_proxy_recorded": False,
            "loopx_workflow_lifecycle_checkpoint": bool(
                _is_loopx_product_mode_route(args.route)
                and not _is_goal_start_product_mode_route(args.route)
                and args.host_local_acp_launch
            ),
            **skillsbench_loopx_turn_runner_prerequisites(
                args.route,
                getattr(args, "loopx_turn_validation_command", None),
            ),
            "loopx_product_mode_lifecycle_driver_kind": (
                BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE
                if _is_loopx_product_mode_route(args.route)
                and not _is_goal_start_product_mode_route(args.route)
                and args.host_local_acp_launch
                else BENCHMARK_CASE_LOOPX_PROMPT_DRIVEN_EXECUTION_STYLE
                if _is_loopx_product_mode_route(args.route)
                else "not_applicable"
            ),
            "goal_start_product_mode": _is_goal_start_product_mode_route(args.route),
            "goal_start_plan_required": _is_goal_start_product_mode_route(args.route),
            "goal_start_guided_command_required": (
                _is_goal_start_product_mode_route(args.route)
            ),
            "goal_start_agent_authored_plan_required": (
                _is_goal_start_product_mode_route(args.route)
            ),
            "goal_start_host_preseed_forbidden": (
                _is_goal_start_product_mode_route(args.route)
            ),
            "goal_start_planned_todo_count_expected": (
                3 if _is_goal_start_product_mode_route(args.route) else 0
            ),
            "goal_start_selected_p0_lifecycle_required": (
                _is_goal_start_product_mode_route(args.route)
            ),
            "verifier_failure_feedback_todo_route": False,
            "verifier_failure_feedback_forwarded_to_agent": False,
            "verifier_failure_todo_required": False,
            "host_local_acp_codex_exec_preflight_requested": bool(
                _host_local_acp_codex_exec_preflight_should_run(args)
            ),
            "host_local_acp_codex_exec_preflight_ready": False,
            "host_local_acp_codex_exec_preflight_status": (
                "pending"
                if _host_local_acp_codex_exec_preflight_should_run(args)
                else "not_requested"
            ),
            "host_local_acp_codex_exec_preflight_attempt_count": 0,
            "host_local_acp_codex_exec_preflight_stage": "",
            "host_local_acp_codex_exec_preflight_first_blocker": "",
            "container_codex_acp_install_skipped": (
                True
                if (
                    is_app_server_goal_route
                    or is_codex_cli_goal_route
                    or args.host_local_acp_launch
                )
                else requires_preinstalled_runtime
            ),
            "benchflow_agent_install_skipped_by_runtime_layer": (
                True
                if is_app_server_goal_route or is_codex_cli_goal_route
                else requires_preinstalled_runtime
            ),
            "remote_command_file_bridge_materialized": bool(
                remote_command_file_bridge_materialized
            ),
            "remote_command_file_bridge_command_configured": bool(
                remote_command_file_bridge_solver_command_configured
            ),
            "remote_command_file_bridge_agent_command_configured": bool(
                remote_command_file_bridge_agent_command_configured
            ),
            "remote_command_file_bridge_agent_command_instrumented": bool(
                remote_command_file_bridge_agent_command_instrumented
            ),
            "remote_command_file_bridge_agent_operation_trace_required": bool(
                remote_command_file_bridge_agent_operation_trace_required
            ),
            "remote_command_file_bridge_agent_operation_trace_satisfied": False,
            "remote_command_file_bridge_agent_operation_trace_status": (
                remote_command_file_bridge_agent_operation_trace_status
            ),
            "remote_command_file_bridge_probe_command_configured": bool(
                remote_command_file_bridge_probe_command_configured
            ),
            "remote_command_file_bridge_solver_wiring_configured": bool(
                remote_command_file_bridge_solver_wiring_configured
            ),
            "remote_command_file_bridge_consumed_by_solver": (
                remote_command_file_bridge_consumed_by_solver
            ),
            "remote_command_file_bridge_consumption_status": (
                remote_command_file_bridge_consumption_status
            ),
            "remote_command_file_bridge_solver_trace_dir_present": False,
            "remote_command_file_bridge_solver_public_trace_read": False,
            "remote_command_file_bridge_solver_raw_material_recorded": False,
            "remote_command_file_bridge_solver_trace_count": 0,
            "remote_command_file_bridge_solver_probe_ready_count": 0,
            "remote_command_file_bridge_solver_operation_count": 0,
            "remote_command_file_bridge_agent_operation_trace_count": 0,
            "remote_command_file_bridge_agent_request_count": 0,
            "remote_command_file_bridge_agent_loopx_cli_call_count": 0,
            "remote_command_file_bridge_agent_loopx_state_read_count": 0,
            "remote_command_file_bridge_agent_loopx_state_write_count": 0,
            "remote_command_file_bridge_agent_task_facing_operation_count": 0,
            "preinstalled_benchflow_agent_runtime_required": (
                requires_preinstalled_runtime
            ),
            "benchflow_agent_runtime_layer_ready": bool(
                agent_runtime_layer.get("ready")
            ),
            "benchflow_agent_runtime_layer_status": str(
                agent_runtime_layer.get("status") or ""
            ),
            "benchflow_agent_runtime_layer_mount_target": (
                BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET
            ),
            "benchflow_agent_runtime_mount_injected": False,
            "benchflow_agent_runtime_mount_read_only": bool(
                requires_preinstalled_runtime
            ),
            "benchflow_agent_runtime_mount_source_recorded": False,
            "loopx_source_mount_requested": bool(
                loopx_source_mount.get("requested")
            ),
            "loopx_source_mount_ready": bool(loopx_source_mount.get("ready")),
            "loopx_source_mount_status": str(
                loopx_source_mount.get("status") or ""
            ),
            "loopx_source_mount_target": str(
                loopx_source_mount.get("mount_target") or ""
            ),
            "loopx_source_mount_injected": False,
            "loopx_source_mount_read_only": bool(loopx_source_mount.get("read_only")),
            "loopx_source_mount_source_recorded": False,
            **runner_source.runner_source_prerequisite_fields(runner_source_fingerprint),
            "benchflow_agent_timeout_original_sec": 0,
            "benchflow_agent_timeout_effective_sec": 0,
            "benchflow_agent_timeout_overridden": False,
            "codex_app_server_goal_worker_plan_schema": (
                app_server_goal_worker_contract["worker_plan"]["schema_version"]
                if app_server_goal_worker_contract
                else ""
            ),
            "codex_app_server_goal_worker_adapter_present": bool(
                app_server_goal_worker_contract
            ),
            "codex_app_server_goal_worker_turn_start_required": bool(
                app_server_goal_worker_contract
            ),
            "codex_app_server_goal_worker_goal_get_required": bool(
                app_server_goal_worker_contract
            ),
            "codex_app_server_goal_worker_runner_integration_ready": (
                bool(
                    app_server_goal_worker_contract.get(
                        "runner_integration_ready"
                    )
                )
                if app_server_goal_worker_contract
                else False
            ),
            "codex_app_server_goal_worker_remote_command_file_bridge_required": (
                bool(app_server_goal_worker_contract)
            ),
            "codex_app_server_goal_worker_remote_command_file_bridge_ready": (
                remote_command_file_bridge_materialized
                if app_server_goal_worker_contract
                else False
            ),
            "benchflow_intermediate_soft_verify_policy": (
                intermediate_soft_verify_policy
            ),
            "benchflow_intermediate_soft_verify_final_only": (
                intermediate_soft_verify_policy == "final-only"
            ),
            "benchflow_intermediate_soft_verify_call_count": 0,
            "benchflow_intermediate_soft_verify_skipped_count": 0,
            "benchflow_intermediate_soft_verify_raw_output_recorded": False,
            "benchflow_intermediate_soft_verify_timeout_enabled": (
                int(args.soft_verifier_timeout_sec or 0) > 0
            ),
            "benchflow_intermediate_soft_verify_timeout_sec": int(
                args.soft_verifier_timeout_sec or 0
            ),
            "benchflow_intermediate_soft_verify_timeout_raw_output_recorded": False,
            "benchflow_final_verifier_timeout_enabled": (
                int(args.final_verifier_timeout_sec or 0) > 0
            ),
            "benchflow_final_verifier_timeout_sec": int(
                args.final_verifier_timeout_sec or 0
            ),
            "benchflow_final_verifier_timeout_raw_command_recorded": False,
            "verifier_dependency_cache_mode": (
                args.verifier_dependency_cache_mode
            ),
            "verifier_dependency_cache_raw_path_recorded": False,
            "benchflow_verifier_prep_timeout_sec": int(
                args.verifier_prep_timeout_sec or 0
            ),
        },
        "public_boundary": {
            "leaderboard_upload": False,
            "public_submission": False,
            "public_raw_prompt": False,
            "public_raw_trajectory": False,
            "public_verifier_log": False,
            "public_secret_values": False,
        },
    }
    if app_server_goal_worker_contract:
        launch_plan["app_server_goal_worker_contract"] = (
            app_server_goal_worker_contract
        )
    launch_plan["observable_handle_registration"] = (
        build_benchmark_launch_observable_handle(
            benchmark_id=args.dataset,
            launch_mode="skillsbench_runner_launch_plan",
            run_label=rollout_name or job_name,
            job_basename=job_name,
            process_state="not_started",
            compact_artifact_refs=(
                "result.json",
                "compact-benchmark-run.json",
                "controller-trace.json",
                RUNNER_PREREQUISITES_PUBLIC_FILENAME,
            ),
            allowed_poll_command="skillsbench_runner_status_snapshot",
            scheduler_kind="skillsbench_automation_loop",
            will_execute=not bool(args.plan_only),
            read_boundary={
                "compact_only": True,
                "task_text_read": False,
                "raw_logs_read": False,
                "raw_artifacts_read": False,
                "trajectory_read": False,
                "local_paths_recorded": False,
                "private_handle_values_recorded": False,
            },
        )
    )
    launch_plan["runner_config"] = _public_runner_config(launch_plan)
    return launch_plan


def _private_runner_output_log_path(plan: dict[str, Any]) -> Path:
    return (
        Path(str(plan["jobs_dir"])).expanduser()
        / str(plan["job_name"])
        / "runner-output.private.log"
    )


def _public_runner_output_capture(plan: dict[str, Any]) -> dict[str, Any] | None:
    capture = plan.get("runner_output_capture")
    if not isinstance(capture, dict):
        return None
    return {
        "schema_version": "skillsbench_runner_output_capture_v0",
        "enabled": bool(capture.get("enabled")),
        "stdout_stderr_redirected": bool(capture.get("stdout_stderr_redirected")),
        "raw_output_public": False,
        "private_log_path_public": False,
    }


def _public_runner_config(plan: dict[str, Any]) -> dict[str, Any]:
    """Return stable public runner knobs needed for posthoc attribution."""

    config: dict[str, Any] = {
        "schema_version": "skillsbench_runner_config_v0",
        "raw_command_recorded": False,
        "raw_env_recorded": False,
        "ledger_path_recorded": False,
        "global_ledger_path_recorded": False,
    }
    string_fields = (
        "benchmark_id",
        "task_id",
        "route",
        "agent",
        "model",
        "reasoning_effort",
        "codex_cli_reasoning_effort",
        "app_server_reasoning_effort",
        "app_server_goal_prompt_style",
        "sandbox",
        "run_group_id",
        "job_name",
        "rollout_name",
        "ledger_scope",
    )
    for field in string_fields:
        value = plan.get(field)
        if isinstance(value, str) and value:
            config[field] = value[:180]
    int_fields = (
        "max_rounds",
        "outer_timeout_sec",
        "sandbox_setup_timeout_sec",
        "agent_idle_timeout_sec",
        "build_stall_timeout_requested_sec",
        "build_stall_timeout_sec",
        "local_codex_task_output_quiet_timeout_sec",
    )
    for field in int_fields:
        value = plan.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            config[field] = value
    for field in (
        "include_task_skills",
        "host_local_acp_launch",
        "codex_cli_goal_thread_prewarm",
        "bootstrap_light_candidate_required",
        "bootstrap_light_fail_fast_required",
        "allow_staged_bootstrap_repair_run",
        "fail_fast_on_apt_risk",
        "apt_risk_fail_fast_defaulted",
        "fail_fast_on_verifier_bootstrap_risk",
        "verifier_bootstrap_fail_fast_defaulted",
        "bootstrap_light_fail_fast_defaulted",
        "global_ledger_sync_enabled",
        "ledger_inherit_enabled",
    ):
        value = plan.get(field)
        if isinstance(value, bool):
            config[field] = value
    prerequisites = plan.get("runner_prerequisites")
    if isinstance(prerequisites, dict):
        policy = prerequisites.get("benchflow_intermediate_soft_verify_policy")
        if isinstance(policy, str) and policy:
            config["product_mode_soft_verify_policy"] = policy[:80]
        for source, target in (
            (
                "benchflow_intermediate_soft_verify_timeout_sec",
                "soft_verifier_timeout_sec",
            ),
            ("benchflow_final_verifier_timeout_sec", "final_verifier_timeout_sec"),
            ("benchflow_verifier_prep_timeout_sec", "verifier_prep_timeout_sec"),
            (
                "benchflow_agent_timeout_host_local_acp_exec_timeout_sec",
                "local_codex_exec_timeout_sec",
            ),
            (
                "benchflow_agent_timeout_host_local_acp_task_output_quiet_timeout_sec",
                "local_codex_task_output_quiet_timeout_sec",
            ),
        ):
            value = prerequisites.get(source)
            if isinstance(value, int) and not isinstance(value, bool):
                config[target] = value
        for field in (
            "codex_api_egress_preflight_required",
            "codex_api_egress_preflight_ready",
            "codex_api_reverse_tunnel_required",
            "codex_api_reverse_tunnel_proxy_configured",
            "codex_api_reverse_tunnel_proxy_url_recorded",
            "benchmark_egress_proxy_ready",
            "benchmark_egress_proxy_configured",
            "benchmark_egress_proxy_required",
            "benchmark_egress_proxy_url_recorded",
            "benchmark_egress_direct_fallback_allowed",
            "benchmark_egress_direct_fallback_active",
            "benchmark_egress_no_proxy_configured",
            "benchmark_egress_no_proxy_raw_value_recorded",
            "benchmark_egress_proxy_agent_env_injected",
            "benchmark_egress_proxy_docker_config_injected",
            "benchmark_egress_proxy_docker_config_path_recorded",
            "benchmark_egress_proxy_docker_config_raw_proxy_recorded",
        ):
            value = prerequisites.get(field)
            if isinstance(value, bool):
                config[field] = value
        for field in (
            "codex_api_egress_preflight_status",
            "codex_api_egress_preflight_error_kind",
            "codex_api_egress_mode_requested",
            "codex_api_egress_mode_resolved",
            "codex_api_reverse_tunnel_proxy_source",
            "codex_api_reverse_tunnel_proxy_scheme",
            "codex_api_reverse_tunnel_proxy_endpoint_kind",
            "benchmark_egress_proxy_status",
            "benchmark_egress_proxy_error_kind",
            "benchmark_egress_proxy_mode_requested",
            "benchmark_egress_proxy_mode_effective",
            "benchmark_egress_proxy_source",
            "benchmark_egress_proxy_env_key",
            "benchmark_egress_proxy_scheme",
            "benchmark_egress_proxy_endpoint_kind",
        ):
            value = prerequisites.get(field)
            if isinstance(value, str) and value:
                config[field] = value[:80]
        config.update(runner_source.compact_runner_source_public_fields(prerequisites))
        value = prerequisites.get("codex_api_reverse_tunnel_proxy_endpoint_port")
        if isinstance(value, int) and not isinstance(value, bool):
            config["codex_api_reverse_tunnel_proxy_endpoint_port"] = value
        value = prerequisites.get("benchmark_egress_proxy_endpoint_port")
        if isinstance(value, int) and not isinstance(value, bool):
            config["benchmark_egress_proxy_endpoint_port"] = value
        value = prerequisites.get("benchmark_egress_no_proxy_entry_count")
        if isinstance(value, int) and not isinstance(value, bool):
            config["benchmark_egress_no_proxy_entry_count"] = value
        config.update(proxy_runtime.compact_base_image_prewarm_fields(prerequisites))
    app_server_observability = _app_server_goal_worker_observability(plan)
    if app_server_observability:
        config["app_server_goal_worker_observability"] = app_server_observability
    return config


def _app_server_goal_worker_observability(
    plan: dict[str, Any],
    controller_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a public-safe attribution packet for app-server Goal launches."""

    if str(plan.get("route") or "") != "codex-app-server-goal-baseline":
        return {}

    trace_summary = plan.get("app_server_goal_worker_trace_summary")
    if not isinstance(trace_summary, dict):
        trace_summary = {}
    if isinstance(controller_trace, dict):
        trace_summary = {**trace_summary, **controller_trace}

    prereqs = plan.get("runner_prerequisites")
    if not isinstance(prereqs, dict):
        prereqs = {}
    egress = plan.get("codex_api_egress_preflight")
    if not isinstance(egress, dict):
        egress = {}

    requested_effort = str(plan.get("app_server_reasoning_effort") or "")[:40]
    observed_effort = str(
        trace_summary.get("native_goal_worker_reasoning_effort") or ""
    )[:40]
    if requested_effort and observed_effort:
        if requested_effort == observed_effort:
            effort_status = "matched"
        else:
            effort_status = "mismatch"
    elif requested_effort:
        effort_status = "requested_not_yet_observed"
    else:
        effort_status = "not_recorded"

    preflight_status = str(
        egress.get("status")
        or prereqs.get("codex_api_egress_preflight_status")
        or ""
    )[:80]
    preflight_required = bool(
        egress.get("required") or prereqs.get("codex_api_egress_preflight_required")
    )
    preflight_ready = bool(
        egress.get("ready") or prereqs.get("codex_api_egress_preflight_ready")
    )
    if not preflight_required:
        preflight_observation_status = "not_required"
    elif preflight_ready:
        preflight_observation_status = "executed_ready"
    elif preflight_status and preflight_status != "pending":
        preflight_observation_status = "executed_blocked"
    else:
        preflight_observation_status = "required_pending"

    def _int_field(name: str) -> int:
        value = trace_summary.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return 0

    summary: dict[str, Any] = {
        "schema_version": "skillsbench_app_server_goal_worker_observability_v0",
        "route": "codex-app-server-goal-baseline",
        "session_policy": str(
            trace_summary.get("native_goal_worker_session_policy")
            or (
                "single_thread_with_blinded_followups"
                if max(0, int(plan.get("app_server_goal_followup_max") or 0))
                else "single_initial_goal_turn"
            )
        )[:120],
        "max_rounds_budget_applies_to": str(
            trace_summary.get("native_goal_worker_max_rounds_budget_applies_to")
            or "benchflow_outer_controller_budget_not_native_goal_attempts"
        )[:120],
        "initial_goal_turn_budget": _int_field(
            "native_goal_worker_initial_goal_turn_budget"
        )
        or 1,
        "same_thread_followup_budget": max(
            0, int(plan.get("app_server_goal_followup_max") or 0)
        ),
        "independent_attempt_budget": (
            max(
                1,
                int(
                    (
                        plan.get("independent_goal_retry")
                        if isinstance(plan.get("independent_goal_retry"), dict)
                        else {}
                    ).get("attempt_budget")
                    or 1
                ),
            )
        ),
        "fresh_goal_thread_per_independent_attempt": True,
        "requested_reasoning_effort": requested_effort,
        "observed_reasoning_effort": observed_effort,
        "reasoning_effort_observation_status": effort_status,
        "reasoning_effort_matches_request": bool(
            requested_effort and observed_effort and requested_effort == observed_effort
        ),
        "requested_normal_followup_max": max(
            0, int(plan.get("app_server_goal_followup_max") or 0)
        ),
        "normal_followup_attempted_count": _int_field(
            "native_goal_worker_normal_followup_attempted_count"
        ),
        "normal_followup_succeeded_count": _int_field(
            "native_goal_worker_normal_followup_succeeded_count"
        ),
        "normal_followup_start_attempted_count": _int_field(
            "native_goal_worker_normal_followup_start_attempted_count"
        ),
        "normal_followup_start_succeeded_count": _int_field(
            "native_goal_worker_normal_followup_start_succeeded_count"
        ),
        "trace_dir_configured": bool(plan.get("app_server_goal_worker_trace_dir")),
        "trace_dir_present": bool(
            trace_summary.get("native_goal_worker_trace_dir_present")
        ),
        "public_trace_read": bool(
            trace_summary.get("native_goal_worker_public_trace_read")
        ),
        "trace_count": _int_field("native_goal_worker_trace_count"),
        "lifecycle_trace_count": _int_field(
            "native_goal_worker_lifecycle_trace_count"
        ),
        "prompt_received_count": _int_field(
            "native_goal_worker_prompt_received_count"
        ),
        "goal_get_count": _int_field("native_goal_worker_goal_get_count"),
        "turn_start_count": _int_field("native_goal_worker_turn_start_count"),
        "turn_completed_observed_count": _int_field(
            "native_goal_worker_turn_completed_observed_count"
        ),
        "assistant_message_present_count": _int_field(
            "native_goal_worker_assistant_message_present_count"
        ),
        "effective_action_observed_count": _int_field(
            "native_goal_worker_effective_action_observed_count"
        ),
        "first_action_observed_count": _int_field(
            "native_goal_worker_first_action_observed_count"
        ),
        "raw_material_recorded": bool(
            trace_summary.get("native_goal_worker_raw_material_recorded")
        ),
        "codex_api_egress_preflight_required": preflight_required,
        "codex_api_egress_preflight_ready": preflight_ready,
        "codex_api_egress_preflight_status": preflight_status,
        "codex_api_egress_preflight_observation_status": (
            preflight_observation_status
        ),
        "codex_api_egress_mode_resolved": str(
            egress.get("resolved_mode")
            or prereqs.get("codex_api_egress_mode_resolved")
            or ""
        )[:80],
        "codex_api_reverse_tunnel_required": bool(
            egress.get("reverse_tunnel_required")
            or prereqs.get("codex_api_reverse_tunnel_required")
        ),
        "codex_api_reverse_tunnel_proxy_configured": bool(
            egress.get("proxy_configured")
            or prereqs.get("codex_api_reverse_tunnel_proxy_configured")
        ),
        "codex_api_reverse_tunnel_proxy_source": str(
            egress.get("proxy_source")
            or prereqs.get("codex_api_reverse_tunnel_proxy_source")
            or ""
        )[:40],
        "codex_api_reverse_tunnel_proxy_scheme": str(
            egress.get("proxy_scheme")
            or prereqs.get("codex_api_reverse_tunnel_proxy_scheme")
            or ""
        )[:20],
        "codex_api_reverse_tunnel_proxy_endpoint_kind": str(
            egress.get("proxy_endpoint_kind")
            or prereqs.get("codex_api_reverse_tunnel_proxy_endpoint_kind")
            or ""
        )[:40],
        "codex_api_reverse_tunnel_proxy_endpoint_port": int(
            egress.get("proxy_endpoint_port")
            or prereqs.get("codex_api_reverse_tunnel_proxy_endpoint_port")
            or 0
        ),
        "codex_api_reverse_tunnel_proxy_url_recorded": False,
        "codex_api_egress_raw_probe_output_recorded": False,
    }

    for key in (
        "native_goal_worker_failure_category",
        "native_goal_worker_first_blocker",
    ):
        value = trace_summary.get(key)
        if isinstance(value, str) and value:
            summary[key] = value[:120]
    efforts = trace_summary.get("native_goal_worker_reasoning_efforts")
    if isinstance(efforts, list):
        compact_efforts = [
            item[:40]
            for item in efforts
            if isinstance(item, str) and item
        ][:8]
        if compact_efforts:
            summary["observed_reasoning_efforts"] = compact_efforts
    return summary


def _runner_config_public_path(plan: dict[str, Any]) -> Path | None:
    jobs_dir = str(plan.get("jobs_dir") or "")
    job_name = str(plan.get("job_name") or "")
    if not jobs_dir or not job_name:
        return None
    return Path(jobs_dir).expanduser() / job_name / RUNNER_CONFIG_PUBLIC_FILENAME


def _rollout_config_json_path(plan: dict[str, Any]) -> Path | None:
    result_json = str(plan.get("result_json") or "")
    if not result_json:
        return None
    return Path(result_json).expanduser().parent / "config.json"


def _write_public_runner_config(plan: dict[str, Any]) -> Path | None:
    config = _public_runner_config(plan)
    if not config:
        return None
    plan["runner_config"] = config
    path = _runner_config_public_path(plan)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(config, indent=2, sort_keys=True, default=_json_default)
            + "\n",
            encoding="utf-8",
        )
    rollout_config_path = _rollout_config_json_path(plan)
    if rollout_config_path is not None:
        payload: dict[str, Any] = {}
        if rollout_config_path.exists():
            try:
                loaded = json.loads(rollout_config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                payload = loaded
        payload["loopx_runner_config"] = config
        payload["loopx_runner_config_public"] = True
        payload["loopx_runner_config_raw_command_recorded"] = False
        payload["loopx_runner_config_raw_env_recorded"] = False
        rollout_config_path.parent.mkdir(parents=True, exist_ok=True)
        rollout_config_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=_json_default)
            + "\n",
            encoding="utf-8",
        )
    return path


async def run_benchflow_case_with_private_output(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> Path | dict[str, Any]:
    if getattr(args, "setup_only_public_preflight", False):
        plan["runner_output_capture"] = {
            "schema_version": "skillsbench_runner_output_capture_v0",
            "enabled": False,
            "stdout_stderr_redirected": True,
            "output_policy": "discard",
            "raw_output_public": False,
            "private_log_created": False,
            "private_log_path_public": False,
        }
        with open(os.devnull, "w", encoding="utf-8") as stream:
            with redirect_stdout(stream), redirect_stderr(stream):
                with _benchmark_egress_proxy_env_applied(args, plan=plan):
                    _write_public_runner_config(plan)
                    _write_public_runner_prerequisites(plan)
                    return await run_benchflow_case(args, plan)

    log_path = _private_runner_output_log_path(plan)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    plan["runner_output_capture"] = {
        "schema_version": "skillsbench_runner_output_capture_v0",
        "enabled": True,
        "stdout_stderr_redirected": True,
        "raw_output_public": False,
        "private_log_path_public": False,
    }
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n[{datetime.now().isoformat(timespec='seconds')}] "
            "begin private BenchFlow stdout/stderr capture\n"
        )
        stream.flush()
        try:
            with redirect_stdout(stream), redirect_stderr(stream):
                with _benchmark_egress_proxy_env_applied(args, plan=plan):
                    _write_public_runner_config(plan)
                    _write_public_runner_prerequisites(plan)
                    result = await run_benchflow_case(args, plan)
        finally:
            stream.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] "
                "end private BenchFlow stdout/stderr capture\n"
            )
    return result


def _safe_relative_to(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def discover_benchflow_result_path(plan: dict[str, Any]) -> Path:
    """Locate BenchFlow's official result.json for a single launch.

    BenchFlow may write the final result either to the explicit rollout path we
    pass in, or under an official nested ``jobs/<timestamp>/<rollout_id>`` tree.
    This discovery stays within the current job root and reads only official
    compact ``result.json`` metadata.
    """

    expected = Path(str(plan["result_json"]))
    jobs_dir = Path(str(plan["jobs_dir"])).expanduser()
    job_name = str(plan.get("job_name") or "")
    job_root = jobs_dir / job_name
    task_id = str(plan.get("task_id") or "")
    rollout_name = str(plan.get("rollout_name") or "")

    if expected.exists():
        plan["result_discovery"] = {
            "schema_version": "skillsbench_result_discovery_v0",
            "status": "found",
            "selection_policy": "planned_result_path",
            "candidate_count": 1,
            "selected_relative_to_job": _safe_relative_to(expected, job_root),
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }
        return expected

    candidates = sorted(
        path
        for path in job_root.rglob("result.json")
        if path.is_file() and path != expected
    )
    ranked: list[tuple[int, float, Path, list[str]]] = []
    for candidate in candidates:
        score = 0
        reasons: list[str] = []
        if candidate.parent.name == rollout_name:
            score += 100
            reasons.append("parent_matches_requested_rollout")
        elif task_id and candidate.parent.name.startswith(f"{task_id}__"):
            score += 30
            reasons.append("parent_matches_task_rollout_prefix")
        try:
            result = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = {}
        if isinstance(result, dict):
            if str(result.get("task_name") or "") == task_id:
                score += 50
                reasons.append("result_task_matches_request")
            result_rollout = str(result.get("rollout_name") or "")
            if result_rollout == rollout_name:
                score += 100
                reasons.append("result_rollout_matches_request")
            elif task_id and result_rollout.startswith(f"{task_id}__"):
                score += 20
                reasons.append("result_rollout_matches_task_prefix")
        if score > 0:
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                mtime = 0.0
            ranked.append((score, mtime, candidate, reasons))

    if not ranked:
        plan["result_discovery"] = {
            "schema_version": "skillsbench_result_discovery_v0",
            "status": "missing",
            "selection_policy": "planned_path_then_job_root_scan",
            "candidate_count": len(candidates),
            "matched_candidate_count": 0,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }
        return expected

    ranked.sort(key=lambda item: (item[0], item[1], str(item[2])), reverse=True)
    top_score, _top_mtime, selected, reasons = ranked[0]
    tied_top_count = sum(1 for score, _mtime, _path, _reasons in ranked if score == top_score)
    plan["result_discovery"] = {
        "schema_version": "skillsbench_result_discovery_v0",
        "status": "found",
        "selection_policy": "planned_path_then_job_root_scan_best_match",
        "tie_breaker": "highest_match_score_then_newest_mtime",
        "candidate_count": len(candidates),
        "matched_candidate_count": len(ranked),
        "top_score_candidate_count": tied_top_count,
        "selected_relative_to_job": _safe_relative_to(selected, job_root),
        "selection_reasons": reasons,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
    }
    return selected


def collect_runner_warning_labels(plan: dict[str, Any]) -> list[str]:
    """Reduce controller-side runner warnings into public-safe labels."""

    jobs_dir = Path(str(plan.get("jobs_dir") or "")).expanduser()
    job_name = str(plan.get("job_name") or "")
    if not jobs_dir or not job_name:
        return []
    controller_log = jobs_dir / job_name / "controller.log"
    if not controller_log.exists():
        return []
    try:
        text = controller_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    labels: list[str] = []
    if "Failed to set model via ACP" in text and "Method not found" in text:
        labels.append(CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL)
    return labels


def _reward_value(round_result: Any) -> float | None:
    if not round_result or not isinstance(round_result.rewards, dict):
        return None
    value = round_result.rewards.get("reward")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _tail(text: str | None, *, limit: int) -> str:
    if limit <= 0:
        return ""
    if not text:
        return ""
    cleaned = "\n".join(line.rstrip() for line in text.splitlines())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def _last_loopx_case_init_phase(text: str | None) -> str:
    if not text:
        return ""
    phases = re.findall(r"loopx_case_init_phase:([a-z0-9_:-]+)", text)
    return phases[-1] if phases else ""


def _loopx_case_init_failure_blocker(text: str | None) -> str:
    if not text:
        return ""
    lowered = text.lower()
    if "loopx/cli.py is missing" in lowered:
        return "loopx_case_source_cli_missing"
    if "python is missing" in lowered or "requires python inside" in lowered:
        return "loopx_case_python_missing"
    if "install-local.sh is missing" in lowered:
        return "loopx_case_install_local_missing"
    if "no module named loopx" in lowered:
        return "loopx_case_source_import_failed"
    if "permission denied" in lowered:
        return "loopx_case_init_permission_denied"
    if "/usr/bin/env" in lowered and "bash" in lowered:
        return "loopx_case_bash_missing"
    return "loopx_case_init_failed"


def _inc_counter(payload: dict[str, Any], key: str, amount: int = 1) -> None:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        value = 0
    payload[key] = value + amount


def _record_round_reward(
    trace: dict[str, Any],
    *,
    agent_round: int,
    round_result: Any,
) -> float | None:
    if round_result is None or agent_round <= 0:
        return None
    reward = _reward_value(round_result)
    reward_present = reward is not None
    passed = bool(reward is not None and reward >= 1.0)
    record: dict[str, Any] = {
        "agent_round": agent_round,
        "reward_present": reward_present,
        "passed": passed,
    }
    if reward is not None:
        record["reward"] = reward
    tool_calls = getattr(round_result, "n_tool_calls", None)
    if isinstance(tool_calls, int) and not isinstance(tool_calls, bool):
        record["tool_calls"] = tool_calls
    _upsert_round_reward_record(trace, record)
    return reward


def _upsert_round_reward_record(
    trace: dict[str, Any],
    record: dict[str, Any],
) -> None:
    agent_round = record.get("agent_round")
    if not isinstance(agent_round, int) or isinstance(agent_round, bool):
        return
    if agent_round <= 0:
        return
    records = trace.setdefault("round_rewards", [])
    if isinstance(records, list):
        records[:] = [
            item
            for item in records
            if not (
                isinstance(item, dict)
                and item.get("agent_round") == agent_round
            )
        ]
        records.append(dict(record))
        records.sort(
            key=lambda item: (
                item.get("agent_round")
                if isinstance(item, dict)
                and isinstance(item.get("agent_round"), int)
                and not isinstance(item.get("agent_round"), bool)
                else 10**9
            )
        )
    _recompute_round_reward_counters(trace)


def _recompute_round_reward_counters(trace: dict[str, Any]) -> None:
    records = trace.get("round_rewards")
    if not isinstance(records, list):
        trace["round_rewards"] = []
        records = []
    reward_count = 0
    success_count = 0
    first_success_round: int | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("reward_present") is True:
            reward_count += 1
        agent_round = record.get("agent_round")
        if (
            record.get("passed") is True
            and isinstance(agent_round, int)
            and not isinstance(agent_round, bool)
            and agent_round > 0
        ):
            success_count += 1
            if first_success_round is None or agent_round < first_success_round:
                first_success_round = agent_round
    trace["reward_observation_count"] = reward_count
    trace["official_success_observation_count"] = success_count
    trace["official_success_observed"] = first_success_round is not None
    trace["first_success_round"] = first_success_round


def _final_result_reward_value(result_json: dict[str, Any]) -> float | None:
    rewards = result_json.get("rewards")
    if not isinstance(rewards, dict):
        return None
    value = rewards.get("reward")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _last_decision_sent_agent_prompt(last_decision: str) -> bool:
    return last_decision.startswith("send_") or last_decision in {
        "continue_after_declared_done_depth_gate_gap",
    }


def _merge_final_result_round_reward(
    trace: dict[str, Any] | None,
    result_path: Path,
) -> None:
    if not trace:
        return
    last_decision = str(trace.get("last_decision") or "")
    if not _last_decision_sent_agent_prompt(last_decision):
        return
    max_round_observed = trace.get("max_round_observed")
    if not isinstance(max_round_observed, int) or isinstance(max_round_observed, bool):
        return
    agent_round = max_round_observed + 1
    if agent_round <= 0:
        return
    try:
        result_json = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(result_json, dict):
        return
    reward = _final_result_reward_value(result_json)
    reward_present = reward is not None
    record: dict[str, Any] = {
        "agent_round": agent_round,
        "reward_present": reward_present,
        "passed": bool(reward is not None and reward >= 1.0),
        "source": "benchflow_final_result",
    }
    if reward is not None:
        record["reward"] = reward
    n_tool_calls = result_json.get("n_tool_calls")
    if isinstance(n_tool_calls, int) and not isinstance(n_tool_calls, bool):
        record["cumulative_tool_calls"] = n_tool_calls
    _upsert_round_reward_record(trace, record)
    trace["final_result_round"] = agent_round
    trace["final_result_ingested"] = True
    if trace.get("blind_loop") is True and reward_present:
        current = trace.get("official_feedback_blinded_count")
        if not isinstance(current, int) or isinstance(current, bool):
            current = 0
        observed = trace.get("reward_observation_count")
        if isinstance(observed, int) and not isinstance(observed, bool):
            trace["official_feedback_blinded_count"] = max(current, observed)


def _new_controller_trace(route: str, *, max_rounds: int | None = None) -> dict[str, Any]:
    trace = build_benchmark_loop_controller_trace(
        route=route,
        max_rounds=max_rounds,
        schema_version="skillsbench_loopx_controller_trace_v0",
    )
    loopx_product_mode = _is_loopx_product_mode_route(route)
    loopx_case_runtime = _is_case_loopx_route(route)
    goal_start_product_mode = _is_goal_start_product_mode_route(route)
    trace.update(
        {
        "case_goal_state_packet_present": False,
        "case_goal_state_init_required": loopx_case_runtime,
        "case_goal_state_initialized_before_agent": False,
        "case_goal_state_init_status": "not_applicable",
        "case_goal_state_path": (
            PRODUCT_MODE_CASE_STATE_PATH
            if loopx_case_runtime
            else ""
        ),
        "case_goal_state_schema_version": (
            PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION
            if loopx_case_runtime
            else ""
        ),
        "declared_done_requires_no_remaining_goals": loopx_product_mode,
        "goal_start_product_mode": goal_start_product_mode,
        "verifier_failure_feedback_todo_route": False,
        "verifier_failure_feedback_forwarded_to_agent": False,
        "verifier_failure_todo_required": False,
        "verifier_failure_feedback_todo_prompt_count": 0,
        "verifier_failure_feedback_todo_round": None,
        "official_feedback_forwarded_count": 0,
        "goal_start_plan_observed": False,
        "planned_todo_count": 0,
        "planned_p0_count": 0,
        "planner_before_todo_write": False,
        "same_priority_order_preserved": False,
        "selected_p0_todo_id": "",
        "selected_todo_claimed": False,
        "selected_todo_updated_before_solver": False,
        "selected_todo_completed_before_spend": False,
        "non_selected_todos_preserved_open_or_deferred": False,
        "agent_declared_done": False,
        "agent_declared_no_remaining_goals": False,
        "declared_done_round": None,
        "declared_done_score": None,
        "product_mode_no_open_todo_below_passing_reward_stop": False,
        "product_mode_no_open_todo_below_passing_reward_streak": 0,
        "product_mode_no_open_todo_below_passing_reward_streak_threshold": (
            PRODUCT_MODE_NO_OPEN_TODO_STOP_STREAK_THRESHOLD
            if loopx_product_mode
            else 0
        ),
        "loopx_state_reads": 0,
        "loopx_state_writes": 0,
        "loopx_case_state_reads": 0,
        "loopx_case_state_writes": 0,
        "native_goal_worker_route": route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
        "native_goal_worker_session_policy": (
            "single_initial_goal_turn"
            if route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
            else ""
        ),
        "native_goal_worker_max_rounds_budget_applies_to": (
            "benchflow_outer_controller_budget_not_native_goal_attempts"
            if route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
            else ""
        ),
        "native_goal_worker_initial_goal_turn_budget": (
            1 if route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE else 0
        ),
        "native_goal_worker_same_thread_followup_budget": 0,
        "native_goal_worker_independent_attempt_budget": (
            1 if route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE else 0
        ),
        "native_goal_worker_fresh_goal_thread_per_independent_attempt": (
            route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
        ),
        "native_goal_worker_connected": False,
        "native_goal_worker_connect_count": 0,
        "native_goal_worker_trace_dir_present": False,
        "native_goal_worker_trace_count": 0,
        "native_goal_worker_ok_count": 0,
        "native_goal_worker_goal_get_count": 0,
        "native_goal_worker_turn_start_count": 0,
        "native_goal_worker_turn_completed_observed_count": 0,
        "native_goal_worker_assistant_message_present_count": 0,
        "native_goal_worker_public_trace_read": False,
        "native_goal_worker_raw_material_recorded": False,
        }
    )
    return trace


def _apply_app_server_goal_round_semantics_to_controller_trace(
    trace: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    round_semantics = (
        plan.get("app_server_goal_round_semantics")
        if isinstance(plan.get("app_server_goal_round_semantics"), dict)
        else {}
    )
    independent_retry = (
        plan.get("independent_goal_retry")
        if isinstance(plan.get("independent_goal_retry"), dict)
        else {}
    )
    same_thread_followup_budget = max(
        0,
        int(
            round_semantics.get("same_thread_followup_budget")
            if isinstance(round_semantics.get("same_thread_followup_budget"), int)
            and not isinstance(round_semantics.get("same_thread_followup_budget"), bool)
            else plan.get("app_server_goal_followup_max")
            or 0
        ),
    )
    independent_attempt_budget = max(
        1,
        int(
            round_semantics.get("independent_attempt_budget")
            if isinstance(round_semantics.get("independent_attempt_budget"), int)
            and not isinstance(round_semantics.get("independent_attempt_budget"), bool)
            else independent_retry.get("attempt_budget")
            or 1
        ),
    )
    trace["native_goal_worker_route"] = True
    trace["native_goal_worker_session_policy"] = str(
        round_semantics.get("session_policy")
        or (
            "single_thread_with_blinded_followups"
            if same_thread_followup_budget
            else "single_initial_goal_turn"
        )
    )[:120]
    trace["native_goal_worker_same_thread_followup_budget"] = (
        same_thread_followup_budget
    )
    trace["native_goal_worker_independent_attempt_budget"] = (
        independent_attempt_budget
    )


def _write_controller_trace(plan: dict[str, Any], trace: dict[str, Any] | None) -> None:
    if not trace:
        return
    raw_trace_path = plan.get("controller_trace_json")
    if not isinstance(raw_trace_path, str) or not raw_trace_path.strip():
        return
    trace_path = Path(raw_trace_path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _read_controller_trace(plan: dict[str, Any]) -> dict[str, Any] | None:
    raw_trace_path = plan.get("controller_trace_json")
    if not isinstance(raw_trace_path, str) or not raw_trace_path.strip():
        return None
    trace_path = Path(raw_trace_path)
    if not trace_path.exists():
        return None
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _merge_app_server_goal_worker_trace_summary(
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
) -> None:
    if not isinstance(trace, dict):
        return
    raw_trace_dir = plan.get("app_server_goal_worker_trace_dir")
    if not isinstance(raw_trace_dir, str) or not raw_trace_dir.strip():
        return
    trace_dir = Path(raw_trace_dir)
    files = sorted(trace_dir.glob("*.compact.json")) if trace_dir.exists() else []
    worker_trace_count = 0
    lifecycle_trace_count = 0
    prompt_received_count = 0
    ok_count = 0
    failure_trace_count = 0
    failure_categories: list[str] = []
    first_blockers: list[str] = []
    goal_get_count = 0
    turn_start_count = 0
    turn_completed_count = 0
    assistant_message_count = 0
    context_only_assistant_message_count = 0
    context_only_recovery_attempted_count = 0
    context_only_recovery_succeeded_count = 0
    context_only_followup_start_attempted_count = 0
    context_only_followup_start_succeeded_count = 0
    normal_followup_attempted_count = 0
    normal_followup_succeeded_count = 0
    normal_followup_start_attempted_count = 0
    normal_followup_start_succeeded_count = 0
    finish_guard_followup_attempted_count = 0
    finish_guard_followup_succeeded_count = 0
    finish_guard_followup_start_attempted_count = 0
    finish_guard_followup_start_succeeded_count = 0
    incomplete_turn_status_count = 0
    incomplete_after_completion_event_count = 0
    incomplete_turn_statuses: list[str] = []
    transport_reconnect_attempted_count = 0
    transport_reconnect_succeeded_count = 0
    goal_reactivation_attempted_count = 0
    goal_reactivation_succeeded_count = 0
    post_context_assistant_chars_total = 0
    first_action_count = 0
    effective_action_count = 0
    reasoning_efforts: list[str] = []
    raw_material_recorded = False
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("schema_version")
            != "skillsbench_host_codex_goal_worker_public_trace_v0"
        ):
            continue
        worker_trace_count += 1
        relay = payload.get("relay") if isinstance(payload.get("relay"), dict) else {}
        if payload.get("trace_kind") == "relay_lifecycle":
            lifecycle_trace_count += 1
            if relay.get("stage") == "prompt_received":
                prompt_received_count += 1
        if payload.get("ok") is True:
            ok_count += 1
        worker_contract = (
            payload.get("worker_contract")
            if isinstance(payload.get("worker_contract"), dict)
            else {}
        )
        first_blocker = worker_contract.get("first_blocker")
        if isinstance(first_blocker, str) and first_blocker:
            safe_blocker = first_blocker[:120]
            if safe_blocker not in first_blockers:
                first_blockers.append(safe_blocker)
        trace_kind = str(payload.get("trace_kind") or "")
        worker_process = (
            payload.get("worker_process")
            if isinstance(payload.get("worker_process"), dict)
            else {}
        )
        if payload.get("ok") is not True and trace_kind != "relay_lifecycle":
            failure_trace_count += 1
            category = worker_process.get("failure_category") or first_blocker
            if isinstance(category, str) and category:
                safe_category = category[:120]
                if safe_category not in failure_categories:
                    failure_categories.append(safe_category)
        turn = payload.get("turn") if isinstance(payload.get("turn"), dict) else {}
        turn_attempts = turn.get("turn_attempt_count")
        if not isinstance(turn_attempts, int) or isinstance(turn_attempts, bool):
            turn_attempts = 1
        turn_attempts = max(1, turn_attempts)
        if turn.get("goal_get_present") is True:
            goal_get_count += turn_attempts
        if turn.get("turn_id_present") is True:
            turn_start_count += turn_attempts
        completed_attempts = turn.get("turn_completed_attempt_count")
        if isinstance(completed_attempts, int) and not isinstance(
            completed_attempts, bool
        ):
            turn_completed_count += max(0, completed_attempts)
        elif turn.get("turn_completed_observed") is True:
            turn_completed_count += 1
        assistant_attempts = turn.get("assistant_message_attempt_count")
        if isinstance(assistant_attempts, int) and not isinstance(
            assistant_attempts, bool
        ):
            assistant_message_count += max(0, assistant_attempts)
        elif turn.get("assistant_message_present") is True:
            assistant_message_count += 1
        context_only_attempts = turn.get("context_only_turn_count")
        if isinstance(context_only_attempts, int) and not isinstance(
            context_only_attempts, bool
        ):
            context_only_assistant_message_count += max(0, context_only_attempts)
        elif turn.get("assistant_message_context_only") is True:
            context_only_assistant_message_count += 1
        recovery = (
            payload.get("context_only_recovery")
            if isinstance(payload.get("context_only_recovery"), dict)
            else {}
        )
        if (
            turn.get("context_only_recovery_attempted") is True
            or recovery.get("attempted") is True
        ):
            context_only_recovery_attempted_count += 1
        if (
            turn.get("context_only_recovery_succeeded") is True
            or recovery.get("succeeded") is True
        ):
            context_only_recovery_succeeded_count += 1
        if (
            turn.get("context_only_followup_start_attempted") is True
            or recovery.get("followup_start_attempted") is True
        ):
            context_only_followup_start_attempted_count += 1
        if (
            turn.get("context_only_followup_start_succeeded") is True
            or recovery.get("followup_start_succeeded") is True
        ):
            context_only_followup_start_succeeded_count += 1
        normal_followup = (
            payload.get("normal_followup")
            if isinstance(payload.get("normal_followup"), dict)
            else {}
        )
        if (
            turn.get("normal_followup_attempted") is True
            or normal_followup.get("attempted") is True
        ):
            normal_followup_attempted_count += 1
        if (
            turn.get("normal_followup_succeeded") is True
            or normal_followup.get("succeeded") is True
        ):
            normal_followup_succeeded_count += 1
        normal_attempts = turn.get("normal_followup_start_attempted_count")
        if isinstance(normal_attempts, int) and not isinstance(
            normal_attempts, bool
        ):
            normal_followup_start_attempted_count += max(0, normal_attempts)
        else:
            normal_attempts = normal_followup.get("followup_start_attempted_count")
            if isinstance(normal_attempts, int) and not isinstance(
                normal_attempts, bool
            ):
                normal_followup_start_attempted_count += max(0, normal_attempts)
        normal_successes = turn.get("normal_followup_start_succeeded_count")
        if isinstance(normal_successes, int) and not isinstance(
            normal_successes, bool
        ):
            normal_followup_start_succeeded_count += max(0, normal_successes)
        else:
            normal_successes = normal_followup.get("followup_start_succeeded_count")
            if isinstance(normal_successes, int) and not isinstance(
                normal_successes, bool
            ):
                normal_followup_start_succeeded_count += max(0, normal_successes)
        finish_guard_followup = (
            payload.get("finish_guard_followup")
            if isinstance(payload.get("finish_guard_followup"), dict)
            else {}
        )
        if (
            turn.get("finish_guard_followup_attempted") is True
            or finish_guard_followup.get("attempted") is True
        ):
            finish_guard_followup_attempted_count += 1
        if (
            turn.get("finish_guard_followup_succeeded") is True
            or finish_guard_followup.get("succeeded") is True
        ):
            finish_guard_followup_succeeded_count += 1
        finish_attempts = turn.get("finish_guard_followup_start_attempted_count")
        if isinstance(finish_attempts, int) and not isinstance(
            finish_attempts, bool
        ):
            finish_guard_followup_start_attempted_count += max(0, finish_attempts)
        else:
            finish_attempts = finish_guard_followup.get(
                "followup_start_attempted_count"
            )
            if isinstance(finish_attempts, int) and not isinstance(
                finish_attempts, bool
            ):
                finish_guard_followup_start_attempted_count += max(
                    0, finish_attempts
                )
        finish_successes = turn.get("finish_guard_followup_start_succeeded_count")
        if isinstance(finish_successes, int) and not isinstance(
            finish_successes, bool
        ):
            finish_guard_followup_start_succeeded_count += max(0, finish_successes)
        else:
            finish_successes = finish_guard_followup.get(
                "followup_start_succeeded_count"
            )
            if isinstance(finish_successes, int) and not isinstance(
                finish_successes, bool
            ):
                finish_guard_followup_start_succeeded_count += max(
                    0, finish_successes
                )
        turn_status = str(turn.get("turn_status") or "").strip()
        if turn_status and turn_status != "completed":
            incomplete_turn_status_count += 1
            if turn_status[:80] not in incomplete_turn_statuses:
                incomplete_turn_statuses.append(turn_status[:80])
            if turn.get("turn_completed_observed") is True:
                incomplete_after_completion_event_count += 1
        if turn.get("transport_reconnect_attempted") is True:
            transport_reconnect_attempted_count += 1
        if turn.get("transport_reconnect_succeeded") is True:
            transport_reconnect_succeeded_count += 1
        if turn.get("goal_reactivation_attempted") is True:
            goal_reactivation_attempted_count += 1
        if turn.get("goal_reactivation_succeeded") is True:
            goal_reactivation_succeeded_count += 1
        post_context_chars = turn.get("post_context_assistant_chars")
        if isinstance(post_context_chars, int) and not isinstance(
            post_context_chars, bool
        ):
            post_context_assistant_chars_total += max(0, post_context_chars)
        effort = turn.get("reasoning_effort")
        if isinstance(effort, str) and effort and effort not in reasoning_efforts:
            reasoning_efforts.append(effort[:40])
        worker_adapter = (
            payload.get("worker_adapter")
            if isinstance(payload.get("worker_adapter"), dict)
            else {}
        )
        adapter_effort = worker_adapter.get("reasoning_effort")
        if (
            isinstance(adapter_effort, str)
            and adapter_effort
            and adapter_effort not in reasoning_efforts
        ):
            reasoning_efforts.append(adapter_effort[:40])
        if turn.get("first_action_observed") is True:
            first_action_count += 1
        if turn.get("effective_action_observed") is True:
            effective_action_count += 1
        boundary = (
            payload.get("boundary")
            if isinstance(payload.get("boundary"), dict)
            else {}
        )
        raw_material_recorded = raw_material_recorded or any(
            boundary.get(field) is True
            for field in (
                "raw_task_text_recorded",
                "raw_logs_recorded",
                "raw_trajectory_recorded",
                "credential_values_recorded",
                "host_paths_recorded",
            )
        )
        raw_material_recorded = raw_material_recorded or (
            turn.get("raw_transcript_recorded") is True
            or turn.get("raw_assistant_message_recorded") is True
        )
    is_native_goal_route = plan.get("route") == "codex-app-server-goal-baseline"
    round_semantics = (
        plan.get("app_server_goal_round_semantics")
        if isinstance(plan.get("app_server_goal_round_semantics"), dict)
        else {}
    )
    independent_retry = (
        plan.get("independent_goal_retry")
        if isinstance(plan.get("independent_goal_retry"), dict)
        else {}
    )
    requested_followup_budget = max(
        0,
        int(
            round_semantics.get("same_thread_followup_budget")
            if isinstance(round_semantics.get("same_thread_followup_budget"), int)
            and not isinstance(round_semantics.get("same_thread_followup_budget"), bool)
            else plan.get("app_server_goal_followup_max")
            or 0
        ),
    )
    independent_attempt_budget = max(
        1,
        int(
            round_semantics.get("independent_attempt_budget")
            if isinstance(round_semantics.get("independent_attempt_budget"), int)
            and not isinstance(round_semantics.get("independent_attempt_budget"), bool)
            else independent_retry.get("attempt_budget")
            or 1
        ),
    )
    trace["native_goal_worker_route"] = is_native_goal_route
    trace["native_goal_worker_session_policy"] = str(
        round_semantics.get("session_policy")
        or (
            "single_thread_with_blinded_followups"
            if requested_followup_budget
            else "single_initial_goal_turn"
        )
    )[:120] if is_native_goal_route else ""
    trace["native_goal_worker_max_rounds_budget_applies_to"] = str(
        round_semantics.get("max_rounds_budget_applies_to")
        or "benchflow_outer_controller_budget_not_native_goal_attempts"
    )[:120] if is_native_goal_route else ""
    trace["native_goal_worker_initial_goal_turn_budget"] = (
        1 if is_native_goal_route else 0
    )
    trace["native_goal_worker_same_thread_followup_budget"] = (
        requested_followup_budget if is_native_goal_route else 0
    )
    trace["native_goal_worker_independent_attempt_budget"] = (
        independent_attempt_budget if is_native_goal_route else 0
    )
    trace["native_goal_worker_fresh_goal_thread_per_independent_attempt"] = bool(
        is_native_goal_route
        and round_semantics.get("fresh_goal_thread_per_independent_attempt") is not False
    )
    trace["native_goal_worker_trace_dir_present"] = trace_dir.exists()
    trace["native_goal_worker_trace_count"] = worker_trace_count
    trace["native_goal_worker_lifecycle_trace_count"] = lifecycle_trace_count
    trace["native_goal_worker_prompt_received_count"] = prompt_received_count
    trace["native_goal_worker_ok_count"] = ok_count
    trace["native_goal_worker_failure_trace_count"] = failure_trace_count
    trace["native_goal_worker_failure_categories"] = failure_categories
    trace["native_goal_worker_failure_category"] = (
        failure_categories[0] if failure_categories else ""
    )
    trace["native_goal_worker_first_blockers"] = first_blockers
    trace["native_goal_worker_first_blocker"] = (
        first_blockers[0] if first_blockers else ""
    )
    trace["native_goal_worker_goal_get_count"] = goal_get_count
    trace["native_goal_worker_turn_start_count"] = turn_start_count
    trace["native_goal_worker_turn_completed_observed_count"] = turn_completed_count
    trace["native_goal_worker_assistant_message_present_count"] = (
        assistant_message_count
    )
    trace["native_goal_worker_assistant_context_only_count"] = (
        context_only_assistant_message_count
    )
    trace["native_goal_worker_context_only_recovery_attempted_count"] = (
        context_only_recovery_attempted_count
    )
    trace["native_goal_worker_context_only_recovery_succeeded_count"] = (
        context_only_recovery_succeeded_count
    )
    trace["native_goal_worker_context_only_followup_start_attempted_count"] = (
        context_only_followup_start_attempted_count
    )
    trace["native_goal_worker_context_only_followup_start_succeeded_count"] = (
        context_only_followup_start_succeeded_count
    )
    trace["native_goal_worker_normal_followup_attempted_count"] = (
        normal_followup_attempted_count
    )
    trace["native_goal_worker_normal_followup_succeeded_count"] = (
        normal_followup_succeeded_count
    )
    trace["native_goal_worker_normal_followup_start_attempted_count"] = (
        normal_followup_start_attempted_count
    )
    trace["native_goal_worker_normal_followup_start_succeeded_count"] = (
        normal_followup_start_succeeded_count
    )
    trace["native_goal_worker_finish_guard_followup_attempted_count"] = (
        finish_guard_followup_attempted_count
    )
    trace["native_goal_worker_finish_guard_followup_succeeded_count"] = (
        finish_guard_followup_succeeded_count
    )
    trace["native_goal_worker_finish_guard_followup_start_attempted_count"] = (
        finish_guard_followup_start_attempted_count
    )
    trace["native_goal_worker_finish_guard_followup_start_succeeded_count"] = (
        finish_guard_followup_start_succeeded_count
    )
    trace["native_goal_worker_incomplete_turn_status_count"] = (
        incomplete_turn_status_count
    )
    trace["native_goal_worker_incomplete_after_completion_event_count"] = (
        incomplete_after_completion_event_count
    )
    trace["native_goal_worker_incomplete_turn_statuses"] = incomplete_turn_statuses
    trace["native_goal_worker_transport_reconnect_attempted_count"] = (
        transport_reconnect_attempted_count
    )
    trace["native_goal_worker_transport_reconnect_succeeded_count"] = (
        transport_reconnect_succeeded_count
    )
    trace["native_goal_worker_goal_reactivation_attempted_count"] = (
        goal_reactivation_attempted_count
    )
    trace["native_goal_worker_goal_reactivation_succeeded_count"] = (
        goal_reactivation_succeeded_count
    )
    trace["native_goal_worker_post_context_assistant_chars_total"] = (
        post_context_assistant_chars_total
    )
    trace["native_goal_worker_reasoning_efforts"] = reasoning_efforts
    trace["native_goal_worker_reasoning_effort"] = (
        reasoning_efforts[0] if reasoning_efforts else ""
    )
    trace["native_goal_worker_first_action_observed_count"] = first_action_count
    trace["native_goal_worker_effective_action_observed_count"] = (
        effective_action_count
    )
    trace["native_goal_worker_public_trace_read"] = worker_trace_count > 0
    trace["native_goal_worker_raw_material_recorded"] = raw_material_recorded
    public_summary_keys = (
        "native_goal_worker_route",
        "native_goal_worker_trace_dir_present",
        "native_goal_worker_trace_count",
        "native_goal_worker_lifecycle_trace_count",
        "native_goal_worker_prompt_received_count",
        "native_goal_worker_ok_count",
        "native_goal_worker_failure_trace_count",
        "native_goal_worker_failure_categories",
        "native_goal_worker_failure_category",
        "native_goal_worker_first_blockers",
        "native_goal_worker_first_blocker",
        "native_goal_worker_goal_get_count",
        "native_goal_worker_turn_start_count",
        "native_goal_worker_turn_completed_observed_count",
        "native_goal_worker_assistant_message_present_count",
        "native_goal_worker_assistant_context_only_count",
        "native_goal_worker_context_only_recovery_attempted_count",
        "native_goal_worker_context_only_recovery_succeeded_count",
        "native_goal_worker_context_only_followup_start_attempted_count",
        "native_goal_worker_context_only_followup_start_succeeded_count",
        "native_goal_worker_normal_followup_attempted_count",
        "native_goal_worker_normal_followup_succeeded_count",
        "native_goal_worker_normal_followup_start_attempted_count",
        "native_goal_worker_normal_followup_start_succeeded_count",
        "native_goal_worker_finish_guard_followup_attempted_count",
        "native_goal_worker_finish_guard_followup_succeeded_count",
        "native_goal_worker_finish_guard_followup_start_attempted_count",
        "native_goal_worker_finish_guard_followup_start_succeeded_count",
        "native_goal_worker_incomplete_turn_status_count",
        "native_goal_worker_incomplete_after_completion_event_count",
        "native_goal_worker_incomplete_turn_statuses",
        "native_goal_worker_transport_reconnect_attempted_count",
        "native_goal_worker_transport_reconnect_succeeded_count",
        "native_goal_worker_goal_reactivation_attempted_count",
        "native_goal_worker_goal_reactivation_succeeded_count",
        "native_goal_worker_post_context_assistant_chars_total",
        "native_goal_worker_reasoning_efforts",
        "native_goal_worker_reasoning_effort",
        "native_goal_worker_first_action_observed_count",
        "native_goal_worker_effective_action_observed_count",
        "native_goal_worker_public_trace_read",
        "native_goal_worker_raw_material_recorded",
    )
    plan["app_server_goal_worker_trace_summary"] = {
        key: trace[key]
        for key in public_summary_keys
        if key in trace
    }
    if worker_trace_count:
        trace["last_decision"] = "host_app_server_goal_worker_trace_recorded"


def _merge_host_local_acp_relay_trace_summary(
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
) -> None:
    if not isinstance(trace, dict):
        return
    raw_trace_dir = plan.get("host_local_acp_relay_trace_dir")
    if not isinstance(raw_trace_dir, str) or not raw_trace_dir.strip():
        if plan.get("route") != "codex-app-server-goal-baseline":
            return
        raw_trace_dir = plan.get("app_server_goal_worker_trace_dir")
        if not isinstance(raw_trace_dir, str) or not raw_trace_dir.strip():
            return
    trace_dir = Path(raw_trace_dir)
    files = sorted(trace_dir.glob("*.compact.json")) if trace_dir.exists() else []
    solver_trace_count = 0
    probe_ready_count = 0
    operation_count = 0
    codex_exec_failure_trace_count = 0
    codex_exec_recoverable_failure_trace_count = 0
    codex_exec_fatal_failure_trace_count = 0
    codex_exec_failure_categories: list[str] = []
    agent_bridge_trace_count = 0
    agent_bridge_request_count = 0
    agent_bridge_success_count = 0
    agent_bridge_failure_count = 0
    agent_bridge_loopx_cli_call_count = 0
    agent_bridge_loopx_state_read_count = 0
    agent_bridge_loopx_state_write_count = 0
    agent_bridge_task_facing_operation_count = 0
    agent_bridge_task_facing_success_count = 0
    agent_bridge_task_facing_failure_count = 0
    agent_bridge_probe_operation_count = 0
    agent_bridge_operation_counts: dict[str, int] = {}
    agent_bridge_loopx_subcommand_counts: dict[str, int] = {}
    agent_bridge_successful_loopx_subcommand_counts: dict[str, int] = {}
    agent_bridge_successful_loopx_command_records: list[dict[str, str]] = []
    agent_bridge_returncode_counts: dict[str, int] = {}
    agent_bridge_failure_category_counts: dict[str, int] = {}
    driver_lifecycle_trace_count = 0
    driver_lifecycle_checkpoint_count = 0
    driver_lifecycle_request_count = 0
    driver_lifecycle_success_count = 0
    driver_lifecycle_failure_count = 0
    driver_lifecycle_loopx_cli_call_count = 0
    driver_lifecycle_loopx_state_read_count = 0
    driver_lifecycle_loopx_state_write_count = 0
    driver_lifecycle_command_counts: dict[str, int] = {}
    driver_lifecycle_returncode_counts: dict[str, int] = {}
    driver_lifecycle_execution_style = ""
    codex_cli_goal_trace_count = 0
    codex_cli_goal_ok_count = 0
    codex_cli_goal_active_count = 0
    codex_cli_goal_terminal_count = 0
    codex_cli_goal_first_action_count = 0
    codex_cli_goal_bridge_request_count = 0
    codex_cli_goal_task_facing_success_count = 0
    codex_cli_goal_recovery_summary = new_codex_cli_goal_recovery_summary()
    codex_cli_goal_stages: list[str] = []
    codex_cli_goal_reasoning_efforts: list[str] = []
    loopx_turn_summary = SkillsBenchTurnTraceSummary()
    raw_material_recorded = False
    payloads: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("schema_version")
            != "skillsbench_host_local_acp_relay_public_trace_v0"
        ):
            continue
        payloads.append(payload)

    latest_agent_snapshot_indexes: dict[str, tuple[int, int]] = {}
    for payload_index, payload in enumerate(payloads):
        if payload.get("trace_kind") != "remote_command_file_bridge_agent_operations":
            continue
        agent_ops = payload.get("remote_command_file_bridge_agent_operations")
        if not isinstance(agent_ops, dict):
            continue
        snapshot_id = agent_ops.get("snapshot_id")
        snapshot_index = agent_ops.get("snapshot_index")
        if (
            agent_ops.get("snapshot_semantics") != "cumulative"
            or not isinstance(snapshot_id, str)
            or not snapshot_id
            or len(snapshot_id) > 128
            or not isinstance(snapshot_index, int)
            or isinstance(snapshot_index, bool)
            or snapshot_index < 1
        ):
            continue
        current = latest_agent_snapshot_indexes.get(snapshot_id)
        if current is None or snapshot_index >= current[0]:
            latest_agent_snapshot_indexes[snapshot_id] = (
                snapshot_index,
                payload_index,
            )

    superseded_agent_snapshot_count = 0
    for payload_index, payload in enumerate(payloads):
        boundary = (
            payload.get("boundary")
            if isinstance(payload.get("boundary"), dict)
            else {}
        )
        raw_material_recorded = raw_material_recorded or any(
            boundary.get(field) is True
            for field in (
                "raw_command_recorded",
                "raw_stdout_recorded",
                "raw_stderr_recorded",
                "raw_task_text_recorded",
                "raw_logs_recorded",
                "raw_trajectory_recorded",
                "credential_values_recorded",
                "host_paths_recorded",
                "remote_paths_recorded",
                "upload_performed",
                "submit_performed",
            )
        )
        trace_kind = payload.get("trace_kind")
        if trace_kind == "remote_command_file_bridge_solver_consumption":
            bridge = (
                payload.get("remote_command_file_bridge")
                if isinstance(payload.get("remote_command_file_bridge"), dict)
                else {}
            )
            solver_trace_count += 1
            if bridge.get("probe_ready") is True:
                probe_ready_count += 1
            bridge_operations = bridge.get("operation_count")
            if isinstance(bridge_operations, int) and not isinstance(
                bridge_operations, bool
            ):
                operation_count += max(0, bridge_operations)
        elif trace_kind == "codex_exec_process_failure":
            process = (
                payload.get("codex_exec_process")
                if isinstance(payload.get("codex_exec_process"), dict)
                else {}
            )
            codex_exec_failure_trace_count += 1
            category = process.get("failure_category")
            recoverable_turn_failure = process.get("recoverable_turn_failure")
            if not isinstance(recoverable_turn_failure, bool):
                recoverable_turn_failure = (
                    isinstance(category, str)
                    and category in RECOVERABLE_CODEX_TURN_FAILURE_CATEGORIES
                )
            if recoverable_turn_failure:
                codex_exec_recoverable_failure_trace_count += 1
            else:
                codex_exec_fatal_failure_trace_count += 1
            if (
                isinstance(category, str)
                and category
                and category not in codex_exec_failure_categories
            ):
                codex_exec_failure_categories.append(category[:120])
        elif trace_kind == "remote_command_file_bridge_agent_operations":
            agent_ops = (
                payload.get("remote_command_file_bridge_agent_operations")
                if isinstance(
                    payload.get("remote_command_file_bridge_agent_operations"),
                    dict,
                )
                else {}
            )
            agent_bridge_trace_count += 1
            raw_material_recorded = raw_material_recorded or (
                agent_ops.get("raw_material_recorded") is True
            )
            snapshot_id = agent_ops.get("snapshot_id")
            snapshot_index = agent_ops.get("snapshot_index")
            if (
                agent_ops.get("snapshot_semantics") == "cumulative"
                and isinstance(snapshot_id, str)
                and snapshot_id in latest_agent_snapshot_indexes
                and latest_agent_snapshot_indexes[snapshot_id]
                != (snapshot_index, payload_index)
            ):
                superseded_agent_snapshot_count += 1
                continue
            count_fields = {
                "request_count": "request",
                "success_count": "success",
                "failure_count": "failure",
                "loopx_cli_call_count": "loopx_cli",
                "loopx_state_read_count": "state_read",
                "loopx_state_write_count": "state_write",
                "task_facing_operation_count": "task_facing",
                "task_facing_success_count": "task_facing_success",
                "task_facing_failure_count": "task_facing_failure",
                "probe_operation_count": "probe",
            }
            for field, target in count_fields.items():
                value = agent_ops.get(field)
                if not isinstance(value, int) or isinstance(value, bool):
                    value = 0
                value = max(0, value)
                if target == "request":
                    agent_bridge_request_count += value
                elif target == "success":
                    agent_bridge_success_count += value
                elif target == "failure":
                    agent_bridge_failure_count += value
                elif target == "loopx_cli":
                    agent_bridge_loopx_cli_call_count += value
                elif target == "state_read":
                    agent_bridge_loopx_state_read_count += value
                elif target == "state_write":
                    agent_bridge_loopx_state_write_count += value
                elif target == "task_facing":
                    agent_bridge_task_facing_operation_count += value
                elif target == "task_facing_success":
                    agent_bridge_task_facing_success_count += value
                elif target == "task_facing_failure":
                    agent_bridge_task_facing_failure_count += value
                elif target == "probe":
                    agent_bridge_probe_operation_count += value
            for source_key, target_counts in (
                ("operation_counts", agent_bridge_operation_counts),
                ("loopx_cli_subcommand_counts", agent_bridge_loopx_subcommand_counts),
                (
                    "successful_loopx_cli_subcommand_counts",
                    agent_bridge_successful_loopx_subcommand_counts,
                ),
                ("returncode_counts", agent_bridge_returncode_counts),
                ("failure_category_counts", agent_bridge_failure_category_counts),
            ):
                source_counts = agent_ops.get(source_key)
                if not isinstance(source_counts, dict):
                    continue
                for key, value in source_counts.items():
                    if not isinstance(key, str) or not key:
                        continue
                    if not isinstance(value, int) or isinstance(value, bool):
                        continue
                    safe_key = key[:80]
                    target_counts[safe_key] = (
                        target_counts.get(safe_key, 0) + max(0, value)
                    )
            agent_bridge_successful_loopx_command_records.extend(
                _goal_start_public_command_records(
                    agent_ops.get("successful_loopx_cli_command_records")
                )
            )
            if len(agent_bridge_successful_loopx_command_records) > 128:
                agent_bridge_successful_loopx_command_records = (
                    agent_bridge_successful_loopx_command_records[:128]
                )
        elif trace_kind == "remote_command_file_bridge_driver_lifecycle_checkpoint":
            checkpoint = (
                payload.get("remote_command_file_bridge_driver_lifecycle_checkpoint")
                if isinstance(
                    payload.get(
                        "remote_command_file_bridge_driver_lifecycle_checkpoint"
                    ),
                    dict,
                )
                else {}
            )
            driver_lifecycle_trace_count += 1
            raw_material_recorded = raw_material_recorded or (
                checkpoint.get("raw_material_recorded") is True
            )
            style = checkpoint.get("execution_style")
            if isinstance(style, str) and style and not driver_lifecycle_execution_style:
                driver_lifecycle_execution_style = style[:120]
            count_fields = {
                "checkpoint_count": "checkpoint",
                "request_count": "request",
                "success_count": "success",
                "failure_count": "failure",
                "loopx_cli_call_count": "loopx_cli",
                "loopx_state_read_count": "state_read",
                "loopx_state_write_count": "state_write",
            }
            for field, target in count_fields.items():
                value = checkpoint.get(field)
                if not isinstance(value, int) or isinstance(value, bool):
                    value = 0
                value = max(0, value)
                if target == "checkpoint":
                    driver_lifecycle_checkpoint_count += value
                elif target == "request":
                    driver_lifecycle_request_count += value
                elif target == "success":
                    driver_lifecycle_success_count += value
                elif target == "failure":
                    driver_lifecycle_failure_count += value
                elif target == "loopx_cli":
                    driver_lifecycle_loopx_cli_call_count += value
                elif target == "state_read":
                    driver_lifecycle_loopx_state_read_count += value
                elif target == "state_write":
                    driver_lifecycle_loopx_state_write_count += value
            for source_key, target_counts in (
                ("command_counts", driver_lifecycle_command_counts),
                ("returncode_counts", driver_lifecycle_returncode_counts),
            ):
                source_counts = checkpoint.get(source_key)
                if not isinstance(source_counts, dict):
                    continue
                for key, value in source_counts.items():
                    if not isinstance(key, str) or not key:
                        continue
                    if not isinstance(value, int) or isinstance(value, bool):
                        continue
                    safe_key = key[:80]
                    target_counts[safe_key] = (
                        target_counts.get(safe_key, 0) + max(0, value)
                    )
        elif trace_kind == "codex_cli_goal_tui":
            goal_trace = (
                payload.get("codex_cli_goal")
                if isinstance(payload.get("codex_cli_goal"), dict)
                else {}
            )
            codex_cli_goal_trace_count += 1
            if payload.get("ok") is True:
                codex_cli_goal_ok_count += 1
            if goal_trace.get("goal_active_observed") is True:
                codex_cli_goal_active_count += 1
            if goal_trace.get("goal_terminal_observed") is True:
                codex_cli_goal_terminal_count += 1
            if goal_trace.get("first_action_observed") is True:
                codex_cli_goal_first_action_count += 1
            bridge_requests = goal_trace.get("bridge_request_count")
            if isinstance(bridge_requests, int) and not isinstance(
                bridge_requests, bool
            ):
                codex_cli_goal_bridge_request_count += max(0, bridge_requests)
            task_facing_successes = goal_trace.get("task_facing_success_count")
            if isinstance(task_facing_successes, int) and not isinstance(
                task_facing_successes, bool
            ):
                codex_cli_goal_task_facing_success_count += max(
                    0,
                    task_facing_successes,
                )
            merge_codex_cli_goal_recovery_trace(
                codex_cli_goal_recovery_summary,
                goal_trace,
            )
            stage = goal_trace.get("stage")
            if isinstance(stage, str) and stage:
                safe_stage = stage[:80]
                if safe_stage not in codex_cli_goal_stages:
                    codex_cli_goal_stages.append(safe_stage)
            effort = goal_trace.get("reasoning_effort")
            if isinstance(effort, str) and effort:
                safe_effort = effort[:40]
                if safe_effort not in codex_cli_goal_reasoning_efforts:
                    codex_cli_goal_reasoning_efforts.append(safe_effort)
            raw_material_recorded = raw_material_recorded or any(
                goal_trace.get(field) is True
                for field in (
                    "raw_tui_capture_recorded",
                    "raw_task_text_recorded",
                    "raw_stdout_recorded",
                    "raw_stderr_recorded",
                    "credential_values_recorded",
                )
            )
        elif trace_kind == "loopx_turn_execution":
            loopx_turn_summary.merge(payload, boundary)
        else:
            continue
    consumed_by_solver = solver_trace_count > 0 and probe_ready_count > 0
    agent_bridge_failure_category = ""
    for category, count in sorted(agent_bridge_failure_category_counts.items()):
        if count > 0:
            agent_bridge_failure_category = category[:120]
            break
    host_local_acp_codex_exec_failure_category = (
        codex_exec_failure_categories[0]
        if codex_exec_failure_categories
        else agent_bridge_failure_category
    )
    trace["remote_command_file_bridge_solver_trace_dir_present"] = trace_dir.exists()
    trace["remote_command_file_bridge_solver_public_trace_read"] = (
        solver_trace_count > 0
    )
    trace["remote_command_file_bridge_consumed_by_solver"] = consumed_by_solver
    trace["remote_command_file_bridge_solver_trace_count"] = solver_trace_count
    trace["remote_command_file_bridge_solver_probe_ready_count"] = probe_ready_count
    trace["remote_command_file_bridge_solver_operation_count"] = operation_count
    trace["remote_command_file_bridge_solver_raw_material_recorded"] = (
        raw_material_recorded
    )
    trace["host_local_acp_codex_exec_failure_trace_count"] = (
        codex_exec_failure_trace_count
    )
    trace["host_local_acp_codex_exec_recoverable_failure_trace_count"] = (
        codex_exec_recoverable_failure_trace_count
    )
    trace["host_local_acp_codex_exec_fatal_failure_trace_count"] = (
        codex_exec_fatal_failure_trace_count
    )
    trace["host_local_acp_codex_exec_failure_trace_present"] = (
        codex_exec_failure_trace_count > 0
    )
    trace["host_local_acp_codex_exec_failure_categories"] = (
        codex_exec_failure_categories
    )
    trace["host_local_acp_codex_exec_failure_category"] = (
        host_local_acp_codex_exec_failure_category
    )
    trace["host_local_acp_codex_exec_failure_raw_material_recorded"] = (
        raw_material_recorded
    )
    trace["remote_command_file_bridge_agent_operation_trace_count"] = (
        agent_bridge_trace_count
    )
    trace["remote_command_file_bridge_agent_operation_trace_present"] = (
        agent_bridge_trace_count > 0
    )
    trace["remote_command_file_bridge_agent_superseded_snapshot_count"] = (
        superseded_agent_snapshot_count
    )
    prerequisites = plan.setdefault("runner_prerequisites", {})
    agent_trace_required = (
        prerequisites.get("remote_command_file_bridge_agent_operation_trace_required")
        is True
    )
    agent_trace_satisfied = bool(
        (not agent_trace_required)
        or (
            agent_bridge_trace_count > 0
            and agent_bridge_request_count > 0
            and agent_bridge_task_facing_success_count > 0
        )
    )
    if agent_trace_required:
        if agent_trace_satisfied:
            agent_trace_status = "agent_operation_trace_recorded"
        elif agent_bridge_trace_count > 0 and agent_bridge_request_count > 0:
            agent_trace_status = "agent_operation_trace_recorded_no_success"
        elif agent_bridge_trace_count > 0:
            agent_trace_status = "agent_operation_trace_present_no_requests"
        else:
            agent_trace_status = "agent_operation_trace_missing"
    else:
        agent_trace_status = str(
            prerequisites.get("remote_command_file_bridge_agent_operation_trace_status")
            or "not_required"
        )
    if agent_bridge_task_facing_success_count > 0:
        host_local_acp_bridge_progress_status = (
            "bridge_task_facing_success_observed"
        )
    elif agent_bridge_task_facing_operation_count > 0:
        host_local_acp_bridge_progress_status = (
            "bridge_task_facing_operation_observed_without_success"
        )
    elif agent_bridge_request_count > 0:
        host_local_acp_bridge_progress_status = (
            "bridge_agent_request_observed_no_task_facing"
        )
    elif host_local_acp_codex_exec_failure_category == "codex_exec_bridge_idle_timeout":
        host_local_acp_bridge_progress_status = (
            "codex_exec_bridge_idle_timeout_no_bridge_progress"
        )
    elif agent_trace_required:
        host_local_acp_bridge_progress_status = "agent_operation_trace_missing"
    else:
        host_local_acp_bridge_progress_status = "not_required"
    trace["remote_command_file_bridge_agent_command_configured"] = (
        prerequisites.get("remote_command_file_bridge_agent_command_configured") is True
    )
    trace["remote_command_file_bridge_agent_command_instrumented"] = (
        prerequisites.get("remote_command_file_bridge_agent_command_instrumented")
        is True
    )
    trace["remote_command_file_bridge_agent_operation_trace_required"] = (
        agent_trace_required
    )
    trace["remote_command_file_bridge_agent_operation_trace_satisfied"] = (
        agent_trace_satisfied
    )
    trace["remote_command_file_bridge_agent_operation_trace_status"] = (
        agent_trace_status
    )
    trace["host_local_acp_bridge_progress_status"] = (
        host_local_acp_bridge_progress_status
    )
    trace["host_local_acp_bridge_progress_signal_source"] = (
        "remote_command_file_bridge_agent_operations"
    )
    trace["remote_command_file_bridge_agent_request_count"] = (
        agent_bridge_request_count
    )
    trace["remote_command_file_bridge_agent_success_count"] = (
        agent_bridge_success_count
    )
    trace["remote_command_file_bridge_agent_failure_count"] = (
        agent_bridge_failure_count
    )
    trace["remote_command_file_bridge_agent_loopx_cli_call_count"] = (
        agent_bridge_loopx_cli_call_count
    )
    trace["remote_command_file_bridge_agent_loopx_state_read_count"] = (
        agent_bridge_loopx_state_read_count
    )
    trace["remote_command_file_bridge_agent_loopx_state_write_count"] = (
        agent_bridge_loopx_state_write_count
    )
    trace["remote_command_file_bridge_agent_task_facing_operation_count"] = (
        agent_bridge_task_facing_operation_count
    )
    trace["remote_command_file_bridge_agent_task_facing_success_count"] = (
        agent_bridge_task_facing_success_count
    )
    trace["remote_command_file_bridge_agent_task_facing_failure_count"] = (
        agent_bridge_task_facing_failure_count
    )
    trace["remote_command_file_bridge_agent_probe_operation_count"] = (
        agent_bridge_probe_operation_count
    )
    trace["remote_command_file_bridge_agent_operation_counts"] = dict(
        sorted(agent_bridge_operation_counts.items())
    )
    trace["remote_command_file_bridge_agent_loopx_subcommand_counts"] = dict(
        sorted(agent_bridge_loopx_subcommand_counts.items())
    )
    trace[
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts"
    ] = dict(sorted(agent_bridge_successful_loopx_subcommand_counts.items()))
    trace[
        "remote_command_file_bridge_agent_successful_loopx_command_records"
    ] = agent_bridge_successful_loopx_command_records
    trace["remote_command_file_bridge_agent_returncode_counts"] = dict(
        sorted(agent_bridge_returncode_counts.items())
    )
    trace["remote_command_file_bridge_agent_failure_category_counts"] = dict(
        sorted(agent_bridge_failure_category_counts.items())
    )
    trace["remote_command_file_bridge_agent_todo_closeout_count"] = (
        _subcommand_family_count(
            agent_bridge_successful_loopx_subcommand_counts,
            "todo complete",
            "todo update",
        )
    )
    trace["remote_command_file_bridge_agent_refresh_state_count"] = (
        _subcommand_family_count(
            agent_bridge_successful_loopx_subcommand_counts,
            "refresh-state",
        )
    )
    trace["remote_command_file_bridge_agent_quota_spend_slot_count"] = (
        _subcommand_family_count(
            agent_bridge_successful_loopx_subcommand_counts,
            "quota spend-slot",
        )
    )
    trace["remote_command_file_bridge_driver_lifecycle_trace_count"] = (
        driver_lifecycle_trace_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_trace_present"] = (
        driver_lifecycle_trace_count > 0
    )
    trace["remote_command_file_bridge_driver_lifecycle_execution_style"] = (
        driver_lifecycle_execution_style
    )
    trace["remote_command_file_bridge_driver_lifecycle_checkpoint_count"] = (
        driver_lifecycle_checkpoint_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_request_count"] = (
        driver_lifecycle_request_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_success_count"] = (
        driver_lifecycle_success_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_failure_count"] = (
        driver_lifecycle_failure_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count"] = (
        driver_lifecycle_loopx_cli_call_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"] = (
        driver_lifecycle_loopx_state_read_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"] = (
        driver_lifecycle_loopx_state_write_count
    )
    trace["remote_command_file_bridge_driver_lifecycle_command_counts"] = dict(
        sorted(driver_lifecycle_command_counts.items())
    )
    trace["remote_command_file_bridge_driver_lifecycle_returncode_counts"] = dict(
        sorted(driver_lifecycle_returncode_counts.items())
    )
    trace["remote_command_file_bridge_driver_lifecycle_raw_material_recorded"] = (
        raw_material_recorded
    )
    trace["codex_cli_goal_tui_trace_count"] = codex_cli_goal_trace_count
    trace["codex_cli_goal_tui_trace_present"] = codex_cli_goal_trace_count > 0
    trace["codex_cli_goal_tui_ok_count"] = codex_cli_goal_ok_count
    trace["codex_cli_goal_tui_goal_active_observed_count"] = (
        codex_cli_goal_active_count
    )
    trace["codex_cli_goal_tui_goal_terminal_observed_count"] = (
        codex_cli_goal_terminal_count
    )
    trace["codex_cli_goal_tui_first_action_observed_count"] = (
        codex_cli_goal_first_action_count
    )
    trace["codex_cli_goal_tui_bridge_request_count"] = (
        codex_cli_goal_bridge_request_count
    )
    trace["codex_cli_goal_tui_task_facing_success_count"] = (
        codex_cli_goal_task_facing_success_count
    )
    trace.update(codex_cli_goal_recovery_public_fields(codex_cli_goal_recovery_summary))
    trace["codex_cli_goal_tui_stages"] = codex_cli_goal_stages
    trace["codex_cli_goal_tui_stage"] = (
        codex_cli_goal_stages[0] if codex_cli_goal_stages else ""
    )
    trace["codex_cli_goal_tui_reasoning_efforts"] = (
        codex_cli_goal_reasoning_efforts
    )
    trace["codex_cli_goal_tui_reasoning_effort"] = (
        codex_cli_goal_reasoning_efforts[0]
        if codex_cli_goal_reasoning_efforts
        else ""
    )
    trace["codex_cli_goal_tui_raw_material_recorded"] = raw_material_recorded
    loopx_turn_summary.apply(trace)
    prerequisites["remote_command_file_bridge_solver_trace_dir_present"] = (
        trace_dir.exists()
    )
    prerequisites["remote_command_file_bridge_solver_public_trace_read"] = (
        solver_trace_count > 0
    )
    prerequisites["remote_command_file_bridge_consumed_by_solver"] = (
        consumed_by_solver
    )
    prerequisites["remote_command_file_bridge_solver_trace_count"] = (
        solver_trace_count
    )
    prerequisites["remote_command_file_bridge_solver_probe_ready_count"] = (
        probe_ready_count
    )
    prerequisites["remote_command_file_bridge_solver_operation_count"] = (
        operation_count
    )
    prerequisites["remote_command_file_bridge_solver_raw_material_recorded"] = (
        raw_material_recorded
    )
    prerequisites["host_local_acp_codex_exec_failure_trace_count"] = (
        codex_exec_failure_trace_count
    )
    prerequisites["host_local_acp_codex_exec_recoverable_failure_trace_count"] = (
        codex_exec_recoverable_failure_trace_count
    )
    prerequisites["host_local_acp_codex_exec_fatal_failure_trace_count"] = (
        codex_exec_fatal_failure_trace_count
    )
    prerequisites["host_local_acp_codex_exec_failure_trace_present"] = (
        codex_exec_failure_trace_count > 0
    )
    prerequisites["host_local_acp_codex_exec_failure_categories"] = (
        codex_exec_failure_categories
    )
    prerequisites["host_local_acp_codex_exec_failure_category"] = (
        host_local_acp_codex_exec_failure_category
    )
    prerequisites["host_local_acp_codex_exec_failure_raw_material_recorded"] = (
        raw_material_recorded
    )
    prerequisites["remote_command_file_bridge_agent_operation_trace_count"] = (
        agent_bridge_trace_count
    )
    prerequisites["remote_command_file_bridge_agent_operation_trace_present"] = (
        agent_bridge_trace_count > 0
    )
    prerequisites["remote_command_file_bridge_agent_operation_trace_required"] = (
        agent_trace_required
    )
    prerequisites["remote_command_file_bridge_agent_operation_trace_satisfied"] = (
        agent_trace_satisfied
    )
    prerequisites["remote_command_file_bridge_agent_operation_trace_status"] = (
        agent_trace_status
    )
    prerequisites["host_local_acp_bridge_progress_status"] = (
        host_local_acp_bridge_progress_status
    )
    prerequisites["host_local_acp_bridge_progress_signal_source"] = (
        "remote_command_file_bridge_agent_operations"
    )
    prerequisites["remote_command_file_bridge_agent_request_count"] = (
        agent_bridge_request_count
    )
    prerequisites["remote_command_file_bridge_agent_success_count"] = (
        agent_bridge_success_count
    )
    prerequisites["remote_command_file_bridge_agent_failure_count"] = (
        agent_bridge_failure_count
    )
    prerequisites["remote_command_file_bridge_agent_loopx_cli_call_count"] = (
        agent_bridge_loopx_cli_call_count
    )
    prerequisites["remote_command_file_bridge_agent_loopx_state_read_count"] = (
        agent_bridge_loopx_state_read_count
    )
    prerequisites["remote_command_file_bridge_agent_loopx_state_write_count"] = (
        agent_bridge_loopx_state_write_count
    )
    prerequisites["remote_command_file_bridge_agent_task_facing_operation_count"] = (
        agent_bridge_task_facing_operation_count
    )
    prerequisites["remote_command_file_bridge_agent_task_facing_success_count"] = (
        agent_bridge_task_facing_success_count
    )
    prerequisites["remote_command_file_bridge_agent_task_facing_failure_count"] = (
        agent_bridge_task_facing_failure_count
    )
    prerequisites["remote_command_file_bridge_agent_probe_operation_count"] = (
        agent_bridge_probe_operation_count
    )
    prerequisites["remote_command_file_bridge_agent_operation_counts"] = dict(
        sorted(agent_bridge_operation_counts.items())
    )
    prerequisites["remote_command_file_bridge_agent_loopx_subcommand_counts"] = dict(
        sorted(agent_bridge_loopx_subcommand_counts.items())
    )
    prerequisites[
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts"
    ] = dict(sorted(agent_bridge_successful_loopx_subcommand_counts.items()))
    prerequisites[
        "remote_command_file_bridge_agent_successful_loopx_command_records"
    ] = agent_bridge_successful_loopx_command_records
    prerequisites["remote_command_file_bridge_agent_returncode_counts"] = dict(
        sorted(agent_bridge_returncode_counts.items())
    )
    prerequisites["remote_command_file_bridge_agent_failure_category_counts"] = dict(
        sorted(agent_bridge_failure_category_counts.items())
    )
    prerequisites["remote_command_file_bridge_agent_todo_closeout_count"] = trace[
        "remote_command_file_bridge_agent_todo_closeout_count"
    ]
    prerequisites["remote_command_file_bridge_agent_refresh_state_count"] = trace[
        "remote_command_file_bridge_agent_refresh_state_count"
    ]
    prerequisites["remote_command_file_bridge_agent_quota_spend_slot_count"] = trace[
        "remote_command_file_bridge_agent_quota_spend_slot_count"
    ]
    prerequisites["remote_command_file_bridge_driver_lifecycle_trace_count"] = (
        driver_lifecycle_trace_count
    )
    prerequisites["remote_command_file_bridge_driver_lifecycle_trace_present"] = (
        driver_lifecycle_trace_count > 0
    )
    prerequisites["remote_command_file_bridge_driver_lifecycle_execution_style"] = (
        driver_lifecycle_execution_style
    )
    prerequisites["remote_command_file_bridge_driver_lifecycle_checkpoint_count"] = (
        driver_lifecycle_checkpoint_count
    )
    prerequisites["remote_command_file_bridge_driver_lifecycle_request_count"] = (
        driver_lifecycle_request_count
    )
    prerequisites["remote_command_file_bridge_driver_lifecycle_success_count"] = (
        driver_lifecycle_success_count
    )
    prerequisites["remote_command_file_bridge_driver_lifecycle_failure_count"] = (
        driver_lifecycle_failure_count
    )
    prerequisites[
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count"
    ] = driver_lifecycle_loopx_cli_call_count
    prerequisites[
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
    ] = driver_lifecycle_loopx_state_read_count
    prerequisites[
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
    ] = driver_lifecycle_loopx_state_write_count
    prerequisites["remote_command_file_bridge_driver_lifecycle_command_counts"] = (
        dict(sorted(driver_lifecycle_command_counts.items()))
    )
    prerequisites[
        "remote_command_file_bridge_driver_lifecycle_returncode_counts"
    ] = dict(sorted(driver_lifecycle_returncode_counts.items()))
    prerequisites[
        "remote_command_file_bridge_driver_lifecycle_raw_material_recorded"
    ] = raw_material_recorded
    prerequisites["codex_cli_goal_tui_trace_count"] = codex_cli_goal_trace_count
    prerequisites["codex_cli_goal_tui_trace_present"] = (
        codex_cli_goal_trace_count > 0
    )
    prerequisites["codex_cli_goal_tui_ok_count"] = codex_cli_goal_ok_count
    prerequisites["codex_cli_goal_tui_goal_active_observed_count"] = (
        codex_cli_goal_active_count
    )
    prerequisites["codex_cli_goal_tui_goal_terminal_observed_count"] = (
        codex_cli_goal_terminal_count
    )
    prerequisites["codex_cli_goal_tui_first_action_observed_count"] = (
        codex_cli_goal_first_action_count
    )
    prerequisites["codex_cli_goal_tui_bridge_request_count"] = (
        codex_cli_goal_bridge_request_count
    )
    prerequisites["codex_cli_goal_tui_task_facing_success_count"] = (
        codex_cli_goal_task_facing_success_count
    )
    prerequisites.update(
        codex_cli_goal_recovery_public_fields(codex_cli_goal_recovery_summary)
    )
    prerequisites["codex_cli_goal_tui_stages"] = codex_cli_goal_stages
    prerequisites["codex_cli_goal_tui_stage"] = (
        codex_cli_goal_stages[0] if codex_cli_goal_stages else ""
    )
    prerequisites["codex_cli_goal_tui_reasoning_efforts"] = (
        codex_cli_goal_reasoning_efforts
    )
    prerequisites["codex_cli_goal_tui_reasoning_effort"] = (
        codex_cli_goal_reasoning_efforts[0]
        if codex_cli_goal_reasoning_efforts
        else ""
    )
    prerequisites["codex_cli_goal_tui_raw_material_recorded"] = (
        raw_material_recorded
    )
    if consumed_by_solver:
        prerequisites["remote_command_file_bridge_consumption_status"] = (
            "solver_prompt_probe_ready"
        )
        trace["remote_command_file_bridge_consumption_decision"] = (
            "remote_command_file_bridge_solver_trace_recorded"
        )
    elif solver_trace_count:
        prerequisites["remote_command_file_bridge_consumption_status"] = (
            "solver_prompt_probe_failed"
        )
    elif prerequisites.get("remote_command_file_bridge_solver_wiring_configured"):
        prerequisites["remote_command_file_bridge_consumption_status"] = (
            "solver_trace_missing"
        )


def _round_count_key(round_index: int) -> str:
    return str(max(0, int(round_index)))


def _top_counts(counter: dict[str, int], *, limit: int = 12) -> dict[str, int]:
    return {
        key: count
        for key, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
        if count > 0
    }


def _subcommand_family_count(counter: dict[str, int], *families: str) -> int:
    total = 0
    for command, count in counter.items():
        if not isinstance(command, str) or not command:
            continue
        if not isinstance(count, int) or isinstance(count, bool):
            continue
        normalized = " ".join(command.split())
        if any(
            normalized == family or normalized.startswith(f"{family} ")
            for family in families
        ):
            total += max(0, count)
    return total


def _tool_title_kind(title: str) -> str:
    text = " ".join(str(title or "").strip().split())
    if not text:
        return "unknown"
    lower = text.lower()
    if LOOPX_CLI_RE.search(text):
        return "loopx_cli"
    if lower.startswith("read "):
        return "read_file"
    if lower.startswith("search "):
        return "search"
    if lower.startswith("list "):
        return "list"
    if lower == "pwd" or lower.startswith("pwd "):
        return "pwd"
    if lower.startswith("python -m py_compile"):
        return "python_py_compile"
    if lower.startswith("python"):
        return "python"
    if lower.startswith("pytest"):
        return "pytest"
    if lower.startswith("git "):
        return "git"
    if SHELL_EDIT_RE.search(text):
        return "shell_edit"
    return lower.split()[0][:40]


def _normalized_loopx_cli_call(
    title: str,
    *,
    round_index: int,
) -> dict[str, Any]:
    text = " ".join(str(title or "").strip().split())
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    command_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if token == "loopx" or token.endswith("/loopx")
        ),
        -1,
    )
    after = tokens[command_index + 1 :] if command_index >= 0 else []
    subcommands: list[str] = []
    flags: list[str] = []
    skip_next = False
    for token in after:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("--"):
            flag = token.split("=", 1)[0][:60]
            flags.append(flag)
            if "=" not in token and flag in LOOPX_FLAG_VALUE_OPTIONS:
                skip_next = True
            continue
        if token.startswith("-"):
            flags.append(token[:20])
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$", token):
            subcommands.append(token)
            if len(subcommands) >= 2:
                break
    command = " ".join(["loopx", *subcommands])
    return {
        "round": max(1, round_index),
        "command": command,
        "subcommands": subcommands,
        "flags": sorted(set(flags))[:8],
        "raw_title_copied": False,
        "raw_output_copied": False,
    }


def _sandbox_paths(text: str) -> list[str]:
    paths = sorted(set(SANDBOX_PATH_RE.findall(text or "")))
    return [path.rstrip(".,:;)`]") for path in paths if path.strip()]


def _protected_paths_from_instruction(text: str) -> list[str]:
    protected: set[str] = set()
    for chunk in re.split(r"(?<=[A-Za-z0-9_)\]])\.\s+|[\n。!?；;]+", text or ""):
        if PROTECTED_DIRECTIVE_RE.search(chunk):
            protected.update(_sandbox_paths(chunk))
    return sorted(protected)


def _protected_paths_continuation_clause(instruction: str) -> str:
    protected_paths = _protected_paths_from_instruction(instruction)
    if not protected_paths:
        return ""
    joined = ", ".join(protected_paths[:12])
    return (
        " Durable task constraints from round 1 still apply: do not modify "
        f"these protected path(s) unless the task instruction explicitly changes "
        f"that boundary: {joined}."
    )


def _blind_loop_persistent_continuation_clause(instruction: str) -> str:
    return (
        " Durable controller constraints from round 1 still apply: do not "
        "invoke /goal mode, external LoopX CLI, upload, submit, or ask "
        "the human for routine execution choices."
        f"{_protected_paths_continuation_clause(instruction)}"
    )


def _trajectory_text_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    if isinstance(value, str):
        if value:
            fragments.append(value)
        return fragments
    if isinstance(value, dict):
        for nested in value.values():
            fragments.extend(_trajectory_text_fragments(nested))
        return fragments
    if isinstance(value, list):
        for nested in value:
            fragments.extend(_trajectory_text_fragments(nested))
    return fragments


def _trajectory_agent_output_fragments(value: Any) -> list[str]:
    """Return text fragments authored by the agent/assistant, not the user prompt."""

    fragments: list[str] = []

    def role_is_agent(role: Any) -> bool:
        return str(role or "").strip().lower() in {
            "agent",
            "assistant",
            "assistant_message",
            "model",
            "worker",
        }

    def type_is_agent_message(event_type: Any) -> bool:
        text = str(event_type or "").strip().lower()
        return bool(
            text
            and (
                "assistant" in text
                or "agent_message" in text
                or text in {"message", "final_message", "response"}
            )
        )

    def add_text(value: Any) -> None:
        if isinstance(value, str) and value:
            fragments.append(value)
        elif isinstance(value, list):
            fragments.extend(_trajectory_text_fragments(value))
        elif isinstance(value, dict):
            fragments.extend(_trajectory_text_fragments(value))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            role = node.get("role") or node.get("author") or node.get("speaker")
            event_type = node.get("type") or node.get("event") or node.get("kind")
            role_present = bool(str(role or "").strip())
            if role_is_agent(role) or (
                not role_present and type_is_agent_message(event_type)
            ):
                for key in (
                    "content",
                    "text",
                    "message",
                    "final_message",
                    "response",
                    "output",
                ):
                    if key in node:
                        add_text(node.get(key))
                return
            if role_present:
                return
            for nested in node.values():
                walk(nested)
            return
        if isinstance(node, list):
            for nested in node:
                walk(nested)

    walk(value)
    return fragments


def _trajectory_tool_call_titles(value: Any) -> list[str]:
    titles: list[str] = []
    if isinstance(value, dict):
        title = str(value.get("title") or "").strip()
        event_type = str(value.get("type") or "").strip()
        if title and (event_type == "tool_call" or "tool" in event_type):
            titles.append(title)
        for nested in value.values():
            titles.extend(_trajectory_tool_call_titles(nested))
        return titles
    if isinstance(value, list):
        for nested in value:
            titles.extend(_trajectory_tool_call_titles(nested))
    return titles


def _merge_round_result_trajectory_lifecycle_summary(
    round_result: Any,
    trace: dict[str, Any],
) -> None:
    def trace_int(name: str) -> int:
        value = trace.get(name, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    trajectory = getattr(round_result, "trajectory", None)
    if not isinstance(trajectory, list):
        return
    read_count = 0
    write_count = 0
    call_count = 0
    for title in _trajectory_tool_call_titles(trajectory):
        if not re.search(r"(?:^|\s|/)loopx(?:\s|$)", title):
            continue
        call = normalized_loopx_cli_call(title, round_index=0)
        usage = loopx_cli_state_usage(call)
        call_count += 1
        if usage == "state_read":
            read_count += 1
        elif usage == "state_write":
            write_count += 1
    if call_count <= 0:
        return
    trace["round_result_trajectory_lifecycle_summary_present"] = True
    trace["round_result_loopx_cli_call_count"] = max(
        trace_int("round_result_loopx_cli_call_count"),
        call_count,
    )
    trace["round_result_loopx_cli_state_read_count"] = max(
        trace_int("round_result_loopx_cli_state_read_count"),
        read_count,
    )
    trace["round_result_loopx_cli_state_write_count"] = max(
        trace_int("round_result_loopx_cli_state_write_count"),
        write_count,
    )
    trace["loopx_state_reads"] = max(
        trace_int("loopx_state_reads"),
        read_count,
    )
    trace["loopx_state_writes"] = max(
        trace_int("loopx_state_writes"),
        write_count,
    )
    trace["raw_round_result_trajectory_recorded"] = False


def _round_result_declared_done(round_result: Any) -> bool:
    trajectory = getattr(round_result, "trajectory", None)
    if not isinstance(trajectory, list):
        return False
    return any(
        DECLARED_DONE_MARKER in text
        for text in _trajectory_agent_output_fragments(trajectory)
    )


def _record_declared_done(
    trace: dict[str, Any],
    *,
    agent_round: int,
    reward: float | None,
) -> None:
    trace["agent_declared_done"] = True
    trace["agent_declared_no_remaining_goals"] = True
    trace["declared_done_round"] = agent_round
    if reward is not None:
        trace["declared_done_score"] = reward


def _record_product_mode_declared_done_below_passing_reward(
    trace: dict[str, Any],
    *,
    agent_round: int,
    reward: float | None,
) -> None:
    trace["product_mode_declared_done_below_passing_reward"] = True
    trace["product_mode_declared_done_below_passing_reward_round"] = agent_round
    if reward is None:
        trace["product_mode_declared_done_below_passing_reward_score_status"] = (
            "missing"
        )
    else:
        trace["product_mode_declared_done_below_passing_reward_score"] = reward
        trace["product_mode_declared_done_below_passing_reward_score_status"] = (
            "observed_below_passing"
        )
    trace["product_mode_declared_done_policy"] = (
        "continue_until_official_success_or_budget"
    )
    current = trace.get("product_mode_declared_done_below_passing_reward_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    trace["product_mode_declared_done_below_passing_reward_count"] = current + 1


def _product_mode_depth_gate_satisfied(trace: dict[str, Any]) -> bool:
    if _product_mode_agent_lifecycle_gate_satisfied(trace):
        return True

    def count(*fields: str) -> int:
        values = [
            trace.get(field)
            for field in fields
            if isinstance(trace.get(field), int)
            and not isinstance(trace.get(field), bool)
        ]
        return max(values, default=0)

    driver_reads = count(
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
    )
    driver_writes = count(
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
    )
    driver_checkpoints = count(
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count"
    )
    driver_successes = count(
        "remote_command_file_bridge_driver_lifecycle_success_count"
    )
    driver_failures = count(
        "remote_command_file_bridge_driver_lifecycle_failure_count"
    )
    driver_loopx_calls = count(
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count"
    )
    if (
        trace.get("remote_command_file_bridge_driver_lifecycle_execution_style")
        == BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE
        and driver_checkpoints > 0
        and driver_successes > 0
        and driver_failures == 0
        and driver_loopx_calls > 0
        and driver_reads > 0
        and driver_writes > 0
    ):
        return True

    reads = count(
        "loopx_state_reads",
        "loopx_cli_state_read_count",
        "loopx_case_state_reads",
    )
    writes = count(
        "loopx_state_writes",
        "loopx_cli_state_write_count",
        "loopx_case_state_writes",
    )
    return (
        isinstance(reads, int)
        and not isinstance(reads, bool)
        and reads > 0
        and isinstance(writes, int)
        and not isinstance(writes, bool)
        and writes > 0
    )


def _product_mode_agent_lifecycle_gate_satisfied(trace: dict[str, Any]) -> bool:
    """Return true only after the solver agent, not only the driver, touched LoopX."""

    # Relay snapshots may expose successful commands before cumulative counters catch up.
    successful_commands = {
        record.get("subcommand")
        for record in _goal_start_public_command_records(
            trace.get(
                "remote_command_file_bridge_agent_successful_loopx_command_records"
            )
        )
    }
    successful_read_observed = bool(
        successful_commands
        & {"start-goal", "quota should-run", "status", "diagnose"}
    )
    successful_write_observed = bool(
        successful_commands
        & {
            "refresh-state",
            "quota spend-slot",
            "todo add",
            "todo claim",
            "todo update",
            "todo complete",
            "todo supersede",
            "todo archive-completed",
        }
    )
    successful_lifecycle_observed = bool(
        successful_read_observed and successful_write_observed
    )
    if successful_lifecycle_observed:
        return True

    remote_agent_trace_required = (
        trace.get("remote_command_file_bridge_agent_operation_trace_required") is True
    )
    if remote_agent_trace_required:
        return (
            _trace_max_int(trace, "remote_command_file_bridge_agent_request_count") > 0
            and _trace_max_int(
                trace,
                "remote_command_file_bridge_agent_loopx_cli_call_count",
            )
            > 0
            and _trace_max_int(
                trace,
                "remote_command_file_bridge_agent_loopx_state_read_count",
            )
            > 0
            and _trace_max_int(
                trace,
                "remote_command_file_bridge_agent_loopx_state_write_count",
            )
            > 0
        )

    return (
        _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_loopx_state_read_count",
            "round_result_loopx_cli_state_read_count",
            "loopx_case_state_reads",
        )
        > 0
        and _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_loopx_state_write_count",
            "round_result_loopx_cli_state_write_count",
            "loopx_case_state_writes",
        )
        > 0
    )


def _trace_max_int(trace: dict[str, Any], *fields: str) -> int:
    values = [
        trace.get(field)
        for field in fields
        if isinstance(trace.get(field), int) and not isinstance(trace.get(field), bool)
    ]
    return max(values, default=0)


def _product_mode_agent_bridge_closeout_observed(trace: dict[str, Any]) -> bool:
    return bool(
        _trace_max_int(trace, "remote_command_file_bridge_agent_todo_closeout_count")
        > 0
        and _trace_max_int(trace, "remote_command_file_bridge_agent_refresh_state_count")
        > 0
        and _trace_max_int(
            trace, "remote_command_file_bridge_agent_quota_spend_slot_count"
        )
        > 0
    )


def _product_mode_host_local_idle_no_task_output_progress_applicable(
    trace: dict[str, Any],
    round_result: Any | None,
    *,
    reward: float | None,
) -> bool:
    if isinstance(reward, (int, float)) and not isinstance(reward, bool) and reward >= 1.0:
        return False
    if _product_mode_agent_bridge_closeout_observed(trace):
        return False
    if trace.get("host_local_acp_codex_exec_failure_category") != (
        "codex_exec_bridge_idle_timeout"
    ):
        return False
    failure_trace_count = _trace_max_int(
        trace,
        "host_local_acp_codex_exec_failure_trace_count",
    )
    if failure_trace_count <= 0:
        return False
    last_counted = _trace_max_int(
        trace,
        "product_mode_host_local_idle_no_task_output_progress_last_failure_trace_count",
    )
    if failure_trace_count <= last_counted:
        return False
    tool_call_count = (
        _round_result_tool_call_count(round_result)
        if round_result is not None
        else None
    )
    return bool(
        (isinstance(tool_call_count, int) and tool_call_count == 0)
        or _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_task_facing_operation_count",
            "remote_command_file_bridge_agent_request_count",
        )
        > 0
    )


def _record_product_mode_host_local_idle_no_task_output_progress(
    trace: dict[str, Any],
    *,
    agent_round: int,
    reward: float | None,
    round_result: Any | None,
) -> bool:
    current = trace.get("product_mode_host_local_idle_no_task_output_progress_streak")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    streak = current + 1
    threshold = PRODUCT_MODE_HOST_LOCAL_IDLE_NO_PROGRESS_STREAK_THRESHOLD
    trace["product_mode_host_local_idle_no_task_output_progress"] = True
    trace["product_mode_host_local_idle_no_task_output_progress_round"] = agent_round
    trace["product_mode_host_local_idle_no_task_output_progress_streak"] = streak
    trace["product_mode_host_local_idle_no_task_output_progress_streak_threshold"] = (
        threshold
    )
    trace["product_mode_host_local_idle_no_task_output_progress_category"] = (
        "codex_exec_bridge_idle_timeout"
    )
    trace[
        "product_mode_host_local_idle_no_task_output_progress_last_failure_trace_count"
    ] = _trace_max_int(trace, "host_local_acp_codex_exec_failure_trace_count")
    tool_call_count = (
        _round_result_tool_call_count(round_result)
        if round_result is not None
        else None
    )
    trace["product_mode_host_local_idle_no_task_output_progress_acp_tool_calls"] = (
        tool_call_count if isinstance(tool_call_count, int) else 0
    )
    trace[
        "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops"
    ] = _trace_max_int(
        trace,
        "remote_command_file_bridge_agent_task_facing_operation_count",
    )
    trace[
        "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes"
    ] = _trace_max_int(
        trace,
        "remote_command_file_bridge_agent_task_facing_success_count",
    )
    if reward is None:
        trace["product_mode_host_local_idle_no_task_output_progress_score_status"] = (
            "missing"
        )
    else:
        trace["product_mode_host_local_idle_no_task_output_progress_score"] = reward
        trace["product_mode_host_local_idle_no_task_output_progress_score_status"] = (
            "observed_below_passing"
        )
    if streak < threshold:
        return False
    trace["product_mode_host_local_idle_no_task_output_progress_stop"] = True
    trace["product_mode_host_local_idle_no_task_output_progress_stop_round"] = (
        agent_round
    )
    trace["product_mode_host_local_idle_no_task_output_progress_policy"] = (
        "stop_after_two_host_local_idle_rounds_without_task_output_or_closeout"
    )
    stop_count = trace.get(
        "product_mode_host_local_idle_no_task_output_progress_stop_count"
    )
    if not isinstance(stop_count, int) or isinstance(stop_count, bool):
        stop_count = 0
    trace["product_mode_host_local_idle_no_task_output_progress_stop_count"] = (
        stop_count + 1
    )
    return True


def _product_mode_solver_activity_observed(
    trace: dict[str, Any],
    round_result: Any | None,
) -> bool:
    tool_call_count = (
        _round_result_tool_call_count(round_result)
        if round_result is not None
        else None
    )
    task_activity_observed = (
        (isinstance(tool_call_count, int) and tool_call_count > 0)
        or _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_task_facing_operation_count",
        )
        > 0
    )
    agent_state_write_observed = (
        _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_loopx_state_write_count",
            "round_result_loopx_cli_state_write_count",
            "loopx_case_state_writes",
        )
        > 0
    )
    bridge_success_count = _trace_max_int(
        trace,
        "remote_command_file_bridge_agent_success_count",
    )
    bridge_failure_count = _trace_max_int(
        trace,
        "remote_command_file_bridge_agent_failure_count",
    )
    legacy_recorded_without_success_counters = bool(
        bridge_success_count == 0
        and bridge_failure_count == 0
        and trace.get("remote_command_file_bridge_agent_operation_trace_status")
        == "agent_operation_trace_recorded"
    )
    bridge_activity_observed = (
        bridge_success_count > 0
        or trace.get("remote_command_file_bridge_agent_operation_trace_satisfied")
        is True
        or legacy_recorded_without_success_counters
    )
    if bridge_activity_observed:
        return task_activity_observed and _product_mode_agent_bridge_closeout_observed(
            trace
        )
    return task_activity_observed and agent_state_write_observed


def _sync_relay_closeout_counts_into_compact(
    compact: dict[str, Any],
    runner_prerequisites: dict[str, Any],
) -> None:
    if not runner_prerequisites:
        return
    interaction_counters = compact.get("interaction_counters")
    if not isinstance(interaction_counters, dict):
        interaction_counters = {}
        compact["interaction_counters"] = interaction_counters
    product_contract = compact.get("product_mode_lifecycle_contract")
    if not isinstance(product_contract, dict):
        product_contract = {}
        compact["product_mode_lifecycle_contract"] = product_contract
    for runner_field, contract_field in (
        (
            "remote_command_file_bridge_agent_todo_closeout_count",
            "agent_bridge_todo_closeout_count",
        ),
        (
            "remote_command_file_bridge_agent_refresh_state_count",
            "agent_bridge_refresh_state_count",
        ),
        (
            "remote_command_file_bridge_agent_quota_spend_slot_count",
            "agent_bridge_quota_spend_slot_count",
        ),
    ):
        value = runner_prerequisites.get(runner_field)
        if not isinstance(value, int) or isinstance(value, bool):
            continue
        value = max(0, value)
        current_counter = interaction_counters.get(runner_field)
        if not isinstance(current_counter, int) or isinstance(current_counter, bool):
            current_counter = 0
        interaction_counters[runner_field] = max(current_counter, value)
        current_contract = product_contract.get(contract_field)
        if not isinstance(current_contract, int) or isinstance(current_contract, bool):
            current_contract = 0
        product_contract[contract_field] = max(current_contract, value)
    if all(
        product_contract.get(field, 0) > 0
        for field in (
            "agent_bridge_todo_closeout_count",
            "agent_bridge_refresh_state_count",
            "agent_bridge_quota_spend_slot_count",
        )
    ):
        product_contract["closeout_satisfied"] = True
    elif (
        product_contract.get("agent_bridge_todo_closeout_count", 0) > 1
        and product_contract.get("agent_bridge_refresh_state_count", 0) > 0
        and product_contract.get("agent_bridge_quota_spend_slot_count", 0) <= 0
    ):
        product_contract["quota_spend_missing_after_repeated_complete"] = True
        product_contract["missing_reason"] = (
            "quota_spend_missing_after_repeated_todo_closeout"
        )
    command_records = _goal_start_public_command_records(
        runner_prerequisites.get(
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        )
    )
    if command_records:
        interaction_counters[
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        ] = command_records


def _record_product_mode_depth_gate_gap(
    trace: dict[str, Any],
    *,
    agent_round: int,
) -> None:
    trace["product_mode_depth_gate_gap"] = True
    trace["product_mode_depth_gate_gap_round"] = agent_round
    current = trace.get("product_mode_depth_gate_gap_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    trace["product_mode_depth_gate_gap_count"] = current + 1


def _record_product_mode_solver_activity_gap(
    trace: dict[str, Any],
    *,
    agent_round: int,
) -> None:
    trace["product_mode_solver_activity_required"] = True
    trace["product_mode_solver_activity_gap"] = True
    trace["product_mode_solver_activity_gap_round"] = agent_round
    trace["product_mode_solver_activity_missing_reason"] = (
        "missing_task_facing_activity_or_agent_closeout_before_declared_done"
    )
    current = trace.get("product_mode_solver_activity_gap_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    trace["product_mode_solver_activity_gap_count"] = current + 1


def _record_product_mode_lifecycle_checkpoint_gap(
    trace: dict[str, Any],
    *,
    agent_round: int,
) -> None:
    trace["product_mode_lifecycle_checkpoint_required"] = True
    trace["product_mode_lifecycle_checkpoint_round"] = agent_round
    trace["product_mode_lifecycle_checkpoint_missing_reason"] = (
        "missing_case_local_loopx_state_read_or_write"
    )
    current = trace.get("product_mode_lifecycle_checkpoint_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    trace["product_mode_lifecycle_checkpoint_count"] = current + 1


def _round_result_tool_call_count(round_result: Any) -> int | None:
    value = getattr(round_result, "n_tool_calls", None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _record_product_mode_no_tool_call_lifecycle_abort(
    trace: dict[str, Any],
    *,
    agent_round: int,
) -> None:
    trace["product_mode_no_tool_call_lifecycle_abort"] = True
    trace["product_mode_no_tool_call_lifecycle_abort_round"] = agent_round
    current = trace.get("product_mode_no_tool_call_lifecycle_abort_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    trace["product_mode_no_tool_call_lifecycle_abort_count"] = current + 1


def _record_product_mode_no_lifecycle_request_abort(
    trace: dict[str, Any],
    *,
    agent_round: int,
) -> None:
    trace["product_mode_no_lifecycle_request_abort"] = True
    trace["product_mode_no_lifecycle_request_abort_round"] = agent_round
    current = trace.get("product_mode_no_lifecycle_request_abort_count")
    if not isinstance(current, int) or isinstance(current, bool):
        current = 0
    trace["product_mode_no_lifecycle_request_abort_count"] = current + 1


def _trajectory_candidate_paths(plan: dict[str, Any]) -> list[Path]:
    jobs_dir = Path(str(plan.get("jobs_dir") or "")).expanduser()
    job_name = str(plan.get("job_name") or "").strip()
    rollout_name = str(plan.get("rollout_name") or "").strip()
    if not job_name or not rollout_name:
        return []
    run_dir = jobs_dir / job_name / rollout_name
    return [
        run_dir / "agent" / "acp_trajectory.jsonl",
        run_dir / "trajectory" / "acp_trajectory.jsonl",
    ]


def _codex_acp_text_path(plan: dict[str, Any]) -> Path | None:
    jobs_dir = Path(str(plan.get("jobs_dir") or "")).expanduser()
    job_name = str(plan.get("job_name") or "").strip()
    rollout_name = str(plan.get("rollout_name") or "").strip()
    if not job_name or not rollout_name:
        return None
    return jobs_dir / job_name / rollout_name / "agent" / "codex_acp.txt"


def summarize_acp_trajectory(path: Path) -> dict[str, Any]:
    return summarize_public_acp_trajectory(
        path,
        schema_version=ACP_TRAJECTORY_SUMMARY_SCHEMA_VERSION,
    )


def _merge_acp_trajectory_summary(
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
) -> None:
    if not isinstance(trace, dict):
        return
    for candidate in _trajectory_candidate_paths(plan):
        if not candidate.exists():
            continue
        summary = summarize_acp_trajectory(candidate)
        codex_acp_path = _codex_acp_text_path(plan)
        if codex_acp_path is not None:
            try:
                codex_acp_size = codex_acp_path.stat().st_size
            except OSError:
                codex_acp_size = 0
            summary["codex_acp_text_present"] = codex_acp_size > 0
            summary["codex_acp_text_bytes"] = codex_acp_size
        cli_state_reads = summary.get("loopx_cli_state_read_count", 0)
        cli_state_writes = summary.get("loopx_cli_state_write_count", 0)
        case_state_reads = summary.get("loopx_case_state_read_count", 0)
        case_state_writes = summary.get("loopx_case_state_write_count", 0)
        if isinstance(case_state_reads, int) and not isinstance(case_state_reads, bool):
            trace["loopx_case_state_reads"] = max(
                int(trace.get("loopx_case_state_reads", 0)),
                case_state_reads,
            )
        if isinstance(case_state_writes, int) and not isinstance(case_state_writes, bool):
            trace["loopx_case_state_writes"] = max(
                int(trace.get("loopx_case_state_writes", 0)),
                case_state_writes,
            )
        if isinstance(cli_state_reads, int) and isinstance(case_state_reads, int):
            trace["loopx_state_reads"] = max(
                int(trace.get("loopx_state_reads", 0)),
                cli_state_reads + case_state_reads,
            )
        if isinstance(cli_state_writes, int) and isinstance(case_state_writes, int):
            trace["loopx_state_writes"] = max(
                int(trace.get("loopx_state_writes", 0)),
                cli_state_writes + case_state_writes,
            )
        trace["private_agent_trajectory_present"] = True
        trace["private_agent_trajectory_summary_recorded"] = True
        trace["raw_agent_trajectory_recorded"] = False
        trace["acp_trajectory_summary"] = summary
        return
    trace["private_agent_trajectory_present"] = False
    trace["private_agent_trajectory_summary_recorded"] = False


def _build_blind_loop_user(
    *,
    route: str,
    max_rounds: int,
    trace: dict[str, Any],
):
    from benchflow.sandbox.user import BaseUser, RoundResult

    class BlindLoopUser(BaseUser):
        """Scheduler-side user that withholds official verifier feedback.

        The configured budget controls scheduled agent rounds, but the loop
        stops early as soon as official scoring reaches the pass threshold. That
        reward is recorded for offline analysis and never sent back to the
        agent.
        """

        def __init__(self) -> None:
            super().__init__()
            self._persistent_constraint_clause = ""

        async def run(
            self,
            round: int,
            instruction: str,
            round_result: RoundResult | None = None,
        ) -> str | None:
            _inc_counter(trace, "heartbeat_count")
            trace["max_round_observed"] = max(int(trace.get("max_round_observed", -1)), round)
            reward = _record_round_reward(
                trace,
                agent_round=round,
                round_result=round_result,
            )
            if round_result is not None:
                _inc_counter(trace, "official_feedback_blinded_count")
            if reward is not None and reward >= 1.0:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = (
                    "stop_after_blind_loop_official_success_observed_without_feedback"
                )
                return None
            if round >= max_rounds:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = "stop_after_blind_loop_budget"
                return None
            if round == 0:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "initial_prompt_count")
                trace["last_decision"] = "send_initial_blind_loop_prompt"
                self._persistent_constraint_clause = _blind_loop_persistent_continuation_clause(
                    instruction
                )
                trace["persistent_constraint_projection_enabled"] = True
                trace["persistent_constraint_projection_source"] = (
                    "round_1_controller_contract"
                )
                protected_paths = _protected_paths_from_instruction(instruction)
                if protected_paths:
                    trace["persistent_constraint_protected_paths"] = protected_paths
                return build_blind_loop_initial_prompt(
                    route=route,
                    instruction=instruction,
                    benchmark_surface="official SkillsBench sandbox",
                )

            _inc_counter(trace, "controller_action_decisions")
            _inc_counter(trace, "followup_prompt_count")
            trace["last_decision"] = "send_blind_scheduled_continuation"
            return build_blind_loop_continuation_prompt(
                scheduled_round=round + 1,
                max_rounds=max_rounds,
                persistent_constraint_clause=self._persistent_constraint_clause,
                route=route,
            )

    return BlindLoopUser()


def _build_product_mode_user(
    *,
    route: str,
    max_rounds: int,
    trace: dict[str, Any],
    plan: dict[str, Any] | None = None,
    case_payload: dict[str, Any] | None = None,
):
    from benchflow.sandbox.user import BaseUser, RoundResult

    treatment = _is_loopx_product_mode_route(route)
    goal_start_product_mode = _is_goal_start_product_mode_route(route)
    payload = case_payload or {}
    case_state_path = str(
        payload.get("case_state_path") or PRODUCT_MODE_CASE_STATE_PATH
    )
    case_goal_id = str(payload.get("benchmark_case_goal_id") or PRODUCT_MODE_CASE_GOAL_ID)
    case_agent_id = str(payload.get("case_agent_id") or BENCHMARK_CASE_LOOPX_AGENT_ID)
    case_todo_id = str(payload.get("case_todo_id") or BENCHMARK_CASE_LOOPX_TODO_ID)
    planned_todo_count = payload.get("planned_todo_count")
    case_cli_prefix = benchmark_case_loopx_command_prefix(
        case_cli_path=str(payload.get("case_cli_path") or "/app/.local/bin/loopx"),
        case_registry_path=str(payload.get("case_registry_path") or "/app/.loopx/registry.json"),
        case_runtime_root=str(payload.get("case_runtime_root") or "/app/.loopx/runtime"),
    )
    plan_prerequisites = (
        (plan or {}).get("runner_prerequisites")
        if isinstance(plan, dict)
        else None
    )
    if not isinstance(plan_prerequisites, dict):
        plan_prerequisites = {}
    workflow_lifecycle_driver = bool(
        treatment
        and not goal_start_product_mode
        and payload.get("canonical_product_mode_lifecycle_driver") is True
        and (
            plan_prerequisites.get("loopx_workflow_lifecycle_checkpoint") is True
            or plan_prerequisites.get("loopx_product_mode_lifecycle_driver_kind")
            == BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE
        )
    )

    feedback_policy_clause = (
        "No official reward, pass/fail status, verifier error, verifier output, "
        "or verifier tail will be shown during this run.\n\n"
    )

    def goal_start_loop_alignment_contract() -> str:
        if not goal_start_product_mode:
            return ""
        return (
            "Slash-command alignment: this benchmark treatment executes the "
            "actual agent contract for `/loopx <task objective>`, not a "
            "host-preseeded approximation and not a live-user chat. The host "
            "only connected the case-local registry and registered the agent; "
            "it did not create the ranked plan, write todos, refresh state, or "
            "run quota on the solver's behalf. The case-local `quota "
            "should-run` guard carries "
            "the same machine loop fields as `heartbeat-prompt` and Codex CLI "
            "TUI `/goal`: read `interaction_contract`, `workspace_guard`, "
            "`goal_boundary`, `execution_obligation`, and `scheduler_hint` "
            "before choosing work. In this benchmark route there is no human "
            "available for routine next-step decisions, so do not ask or wait "
            "for the user when the task can proceed. `scheduler_hint` is only "
            "scheduling/final-check/self-stop policy and never authorizes quota "
            "spend. Proceed with the task-facing work available to the official "
            "runner instead of projecting permission boundaries. Only record a "
            "blocker when the sandbox bridge, task workspace, or required "
            "tooling is technically unavailable. Do not turn ordinary benchmark "
            "routing, verifier failure, or uncertainty into a user gate. If "
            "delivery is possible, continue with one bounded task-facing "
            "segment, validate it, write back the selected P0 todo, and spend "
            "exactly once only after the validated closeout sequence. "
        )

    def bridge_request_command_sequence(commands: list[str]) -> str:
        return "".join(
            f"- Send one separate `operation=exec` bridge request: `{command}`\n"
            for command in commands
        )

    def goal_start_plan_write_contract(planned_count: int) -> str:
        todo_template = (
            f"{case_cli_prefix} todo add --goal-id {case_goal_id} --role agent "
            "--todo-id <TODO_ID> --text <SHELL_QUOTED_TODO_TEXT> "
            "--task-class advancement_task --action-kind <ACTION_KIND>"
        )
        commands = [todo_template for _ in range(planned_count)]
        commands.extend(
            [
                (
                    f"{case_cli_prefix} refresh-state --goal-id {case_goal_id} "
                    "--classification benchmark_case_agent_goal_start "
                    "--delivery-batch-scale single_surface "
                    "--delivery-outcome surface_only --no-global-sync"
                ),
                (
                    f"{case_cli_prefix} quota should-run --goal-id {case_goal_id} "
                    f"--agent-id {case_agent_id}"
                ),
                (
                    f"{case_cli_prefix} todo claim --goal-id {case_goal_id} "
                    f"--todo-id <SELECTED_TODO_ID> --claimed-by {case_agent_id}"
                ),
            ]
        )
        return (
            f"Author exactly {planned_count} ordered public-safe todos from the "
            "guided transaction. Choose the todo ids, texts, and action kinds "
            "yourself; ids must be unique. Replace every placeholder below, "
            "select the first ranked todo or an explicit P0 you authored, and "
            "preserve write order as plan order. Exactly one LoopX CLI command "
            "is allowed in each `operation=exec` bridge request: never batch "
            "commands with a newline, semicolon, `&&`, `||`, or pipe.\n"
            + bridge_request_command_sequence(commands)
        )

    def treatment_state_contract() -> str:
        goal_start_clause = ""
        goal_start_alignment = goal_start_loop_alignment_contract()
        if goal_start_product_mode:
            planned_count = (
                planned_todo_count
                if isinstance(planned_todo_count, int)
                and not isinstance(planned_todo_count, bool)
                and planned_todo_count > 0
                else 3
            )
            goal_start_clause = (
                "This route executes `/loopx <task objective>`: "
                f"the agent must author a compact ranked {planned_count}-todo "
                "plan after the guided preview and before todo writes, "
                "with the first ranked todo or an explicit P0 authored by the "
                "agent entering the lifecycle. Non-selected todos remain open or "
                "deferred until the selected P0 is validated. "
            )
            return (
                "LoopX slash-command treatment contract: official case-local "
                f"LoopX is connected before the agent starts at `{case_state_path}`, "
                "but no plan or todo has been seeded. The benchmark task remains "
                "the primary objective. After the bridge packet's required "
                "connectivity probe and before prose planning, your first LoopX "
                "CLI action must invoke `start-goal --guided --project /app` "
                "through the private JSON bridge. Pass the exact visible TASK "
                "INSTRUCTION as one shell-safe `--goal-text` argument; also pass "
                f"`--goal-id {case_goal_id}`, `--agent-id {case_agent_id}`, and "
                "`--host-surface shell`. Do not summarize, truncate, or replace "
                "the task text, and do not expose that private command or its "
                "output in public artifacts. Read the guided transaction, then "
                "author and write the plan through the same bridge:\n\n"
                f"{goal_start_plan_write_contract(planned_count)}"
                "The benchmark controller is the already-active host loop, so "
                "do not create or modify an external automation. Only after the "
                "guided start, ordered todo writeback, refresh, quota guard, and "
                "selected P0 claim may task-facing solving begin. "
                f"{goal_start_clause}"
                f"{goal_start_alignment}"
                "After meaningful local task evidence or validation, update the "
                "selected todo. Only after task-facing work indicates completion "
                "may you use `todo complete`, then `refresh-state`, then `quota "
                "spend-slot --source adapter --execute`. Do not run closeout as "
                "setup, edit Markdown state as the source of truth, or answer "
                "with prose only. "
            )
        if workflow_lifecycle_driver:
            return (
                "LoopX product-mode lifecycle contract: official case-local "
                f"LoopX is initialized before the agent starts. Active state: "
                f"`{case_state_path}`. This is the only formal treatment "
                "lifecycle; runner polling is only the outer transport. The "
                "canonical workflow lifecycle driver has already executed the "
                "case-local `quota should-run`, `todo claim`, `todo update`, "
                "and `refresh-state` checkpoint through the sandbox bridge "
                "before this prompt. "
                f"{goal_start_clause}"
                f"{goal_start_alignment}"
                "Do not repeat that setup checkpoint as "
                "your first action. The benchmark task remains the primary "
                "objective; LoopX commands track control-plane state and do "
                "not themselves complete the task. Before prose planning, "
                "solving narrative, or final answer, your first agent action "
                "must be a task-facing shell/tool call through the available "
                "sandbox bridge, using an `operation=exec` request with "
                "`cwd=/app`; if the bridge packet includes `FIRST ACTION "
                "REQUIRED`, copy and run that exact command. A minimal valid "
                "first command is `pwd && ls -la`. "
                "After meaningful local task evidence or validation, update "
                "the todo through LoopX CLI. Only after task-facing work "
                "indicates the benchmark task is complete may you use "
                "`todo complete`, then `refresh-state`, then "
                "`quota spend-slot --source adapter --execute` with this case "
                "goal and agent id. Do not run closeout as a setup step. Do "
                "not rely on only reading or editing the Markdown state file, "
                "and do not write a separate marker as the source of truth. "
            )
        return (
            "LoopX product-mode lifecycle contract: official case-local "
            f"LoopX is initialized before the agent starts. Active state: "
            f"`{case_state_path}`. This is the only formal treatment "
            "lifecycle; runner polling is only the outer transport. The "
            "benchmark task remains the primary objective; LoopX commands track "
            "control-plane state and do not themselves complete the task. As "
            "the first control-plane action, run the following commands inside "
            "the scored sandbox, then wait for the scheduler to send the task "
            "packet. "
            f"{goal_start_clause}"
            f"{goal_start_alignment}"
            "Before reading, planning, solving, or answering the task, your first "
            "agent action must be a shell/tool call that sends the case-local "
            "LoopX CLI commands through the available sandbox bridge; a prose-only "
            "response or final answer before that bridge request is invalid. "
            "If a LoopX SkillsBench remote workspace bridge packet is present, "
            "invoke that private JSON bridge from your shell tool and send each "
            "command as an `operation=exec` request with `cwd=/app`; do not try "
            "to run `/app/...` commands directly in the host-local temp cwd. "
            f"`{case_cli_prefix} quota should-run --goal-id {case_goal_id} "
            f"--agent-id {case_agent_id}` and claim the selected case todo "
            f"with `{case_cli_prefix} todo claim --goal-id {case_goal_id} "
            f"--todo-id {case_todo_id} --claimed-by {case_agent_id}`. "
            "After meaningful local task evidence or validation, update the "
            "todo through LoopX CLI. Only after task-facing work indicates the "
            "benchmark task is complete may you use `todo complete`, then "
            "`refresh-state`, then `quota spend-slot --source adapter "
            "--execute` with this case goal and agent id. Do not run closeout "
            "as a setup step. Do not rely on only reading or editing the "
            "Markdown state file, and do not write a separate marker as the "
            "source of truth. "
        )

    def entry_lifecycle_requirement() -> str:
        if goal_start_product_mode:
            return (
                "run the guided `start-goal` preview with the exact task text, "
                "then author the ordered P0/P1/P2 todos, refresh state, run "
                "quota, and claim the selected P0 through the solver bridge "
                "before task-facing solving"
            )
        return (
            "run the case-local quota/todo commands through the solver bridge "
            "before task inspection or solving"
        )

    def lifecycle_checkpoint_commands(round_number: int) -> str:
        if goal_start_product_mode:
            planned_count = (
                planned_todo_count
                if isinstance(planned_todo_count, int)
                and not isinstance(planned_todo_count, bool)
                and planned_todo_count > 0
                else 3
            )
            return (
                "First invoke `start-goal --guided --project /app` through the "
                "private bridge with the exact TASK INSTRUCTION from the prior "
                "turn as the single shell-safe `--goal-text` value. After "
                "reading that private guided transaction, author and write the "
                "ordered public-safe plan.\n\n"
                f"{goal_start_plan_write_contract(planned_count)}"
            )
        safe_round = max(1, round_number)
        checkpoint_note = shlex.quote(
            f"round {safe_round} product-mode lifecycle checkpoint"
        )
        checkpoint_evidence = shlex.quote(
            "public-safe checkpoint: case-local LoopX lifecycle touched"
        )
        classification = shlex.quote("benchmark_case_lifecycle_checkpoint")
        return (
            "```bash\n"
            f"{case_cli_prefix} quota should-run --goal-id {case_goal_id} "
            f"--agent-id {case_agent_id}\n"
            f"{case_cli_prefix} todo claim --goal-id {case_goal_id} "
            f"--todo-id {case_todo_id} --claimed-by {case_agent_id}\n"
            f"{case_cli_prefix} todo update --goal-id {case_goal_id} "
            f"--todo-id {case_todo_id} --status open "
            f"--note {checkpoint_note} --evidence {checkpoint_evidence}\n"
            f"{case_cli_prefix} refresh-state --goal-id {case_goal_id} "
            f"--classification {classification} "
            "--delivery-batch-scale single_surface "
            "--delivery-outcome surface_only --no-global-sync\n"
            "```\n"
        )

    def closeout_commands(round_number: int) -> str:
        safe_round = max(1, round_number)
        complete_note = shlex.quote(
            f"round {safe_round} product-mode task validated and ready for verifier"
        )
        complete_evidence = shlex.quote(
            "public-safe closeout: task-facing work validated and case todo complete"
        )
        classification = shlex.quote("benchmark_case_agent_closeout")
        selected_todo_ref = (
            "<SELECTED_TODO_ID>" if goal_start_product_mode else case_todo_id
        )
        commands = [
            f"{case_cli_prefix} todo complete --goal-id {case_goal_id} "
            f"--todo-id {selected_todo_ref} --note {complete_note} "
            f"--evidence {complete_evidence}",
            f"{case_cli_prefix} refresh-state --goal-id {case_goal_id} "
            f"--classification {classification} "
            "--delivery-batch-scale implementation "
            "--delivery-outcome primary_goal_outcome "
            f"--agent-id {case_agent_id} --agent-lane benchmark_case "
            "--no-global-sync",
            f"{case_cli_prefix} quota spend-slot --goal-id {case_goal_id} "
            f"--agent-id {case_agent_id} --source adapter --execute",
        ]
        placeholder_clause = (
            "Replace `<SELECTED_TODO_ID>` with the selected id from your own "
            "ranked plan. "
            if goal_start_product_mode
            else ""
        )
        return (
            placeholder_clause
            + "Send each closeout command in its own bridge request. "
            "Do not batch the sequence into one shell command.\n"
            + bridge_request_command_sequence(commands)
        )

    def lifecycle_checkpoint_prompt(round_number: int) -> str:
        return (
            f"Mandatory LoopX lifecycle checkpoint before round {round_number} "
            "continues. The previous product-mode round did not produce public "
            "evidence of case-local LoopX state read/write. This is not "
            "official verifier feedback and says nothing about task success. "
            "Before doing any more task work or declaring done, run these "
            "case-local LoopX CLI commands exactly from the sandbox, then "
            f"continue solving from the updated case state at `{case_state_path}`. "
            "Do not answer with prose only.\n\n"
            f"{lifecycle_checkpoint_commands(round_number)}"
            "After meaningful local validation or completion, update the same "
            "case todo again; only spend quota after validated work or final "
            "closeout."
        )

    def solver_activity_prompt(
        round_number: int,
        *,
        task_instruction: str | None = None,
    ) -> str:
        task_clause = ""
        if task_instruction:
            task_clause = (
                "\n\n--- TASK INSTRUCTION ---\n"
                f"{task_instruction}\n\n"
                "The task above remains the primary objective for this turn. "
                "Do not spend the turn only proving bridge access or repeating "
                "status; use the bridge to finish the task-facing work, and if "
                "the task names a scored output path, write or validate that "
                "path before closeout."
            )
        return (
            f"Mandatory product-mode solver checkpoint before round {round_number} "
            "continues. The previous round produced enough LoopX lifecycle "
            "evidence to make the treatment countable, but it did not produce "
            "the selected P0 solver/closeout evidence. The next agent turn "
            "must start with either a task-facing sandbox bridge operation "
            "from `/app`, or, if local validation already proves the selected "
            "P0 is complete, the selected P0 closeout sequence: "
            "`todo complete`, `refresh-state`, and `quota spend-slot "
            "--source adapter --execute`. Read-only LoopX calls such as "
            "`quota should-run`, or state edits without a spend event, are not "
            "enough to declare completion. This is not official reward, "
            "pass/fail, or verifier feedback and says nothing about task "
            "success. If the task is not "
            "complete, use the available sandbox tool or command-file bridge "
            "to inspect the task workspace, make or verify the required "
            "changes, and continue solving. If local evidence shows the "
            "selected P0 is complete, run this exact case-local closeout "
            "sequence from `/app`:\n\n"
            f"{goal_start_loop_alignment_contract()}"
            f"{closeout_commands(round_number)}"
            f"{task_clause}\n\n"
            "Do not answer with prose only, and only end with "
            f"{DECLARED_DONE_MARKER} after meaningful local task work or "
            "validation and the corresponding LoopX closeout/spend evidence "
            "has been recorded."
        )

    def host_local_idle_no_progress_prompt(
        round_number: int,
        *,
        task_instruction: str | None = None,
    ) -> str:
        task_clause = ""
        if task_instruction:
            task_clause = (
                "\n\n--- TASK INSTRUCTION ---\n"
                f"{task_instruction}\n\n"
            )
        return (
            f"Mandatory host-local bridge recovery checkpoint before round "
            f"{round_number}. The previous host-local Codex exec turn idled "
            "after bridge activity and did not produce scored task output or "
            "case closeout. This is not official reward or verifier feedback. "
            "Do not wait for another local Codex process and do not answer with "
            "status-only prose. Use the existing sandbox command/file bridge "
            "now for one concrete task-facing action from `/app`: inspect the "
            "task workspace, write or validate the scored output path if the "
            "task names one, or record a compact blocker in the selected P0 "
            "todo. If local task evidence proves completion, run the exact "
            "case-local closeout sequence (`todo complete`, `refresh-state`, "
            "`quota spend-slot --source adapter --execute`) before declaring "
            "done.\n\n"
            f"{goal_start_loop_alignment_contract()}"
            f"{closeout_commands(round_number)}"
            f"{task_clause}"
        )

    def final_closeout_prompt(round_number: int) -> str:
        return (
            f"Mandatory product-mode closeout checkpoint before finalization "
            f"round {round_number}. The controller is at a finalization "
            "boundary, but the selected P0 todo has not produced the required "
            "`todo complete`, `refresh-state`, and `quota spend-slot "
            "--source adapter --execute` evidence. This is not official "
            "reward, pass/fail, verifier error, verifier output, or verifier "
            "tail feedback. Do not answer with prose only and do not start a "
            "new broad exploration loop. If local task-facing validation "
            "indicates the selected P0 is complete, run this exact case-local "
            "closeout sequence from `/app` now:\n\n"
            f"{goal_start_loop_alignment_contract()}"
            f"{closeout_commands(round_number)}"
            "If local validation does not support closeout, perform one "
            "focused task-facing validation or repair operation from `/app`, "
            "update the selected P0 todo with the concrete blocker evidence, "
            f"and do not end with {DECLARED_DONE_MARKER}."
        )

    def final_closeout_checkpoint_budget_exhausted() -> bool:
        return (
            _trace_max_int(trace, "product_mode_final_closeout_checkpoint_count")
            >= PRODUCT_MODE_FINAL_CLOSEOUT_MAX_CHECKPOINTS
        )

    def record_final_closeout_checkpoint(
        *,
        agent_round: int,
        reason: str,
    ) -> None:
        trace["product_mode_final_closeout_required"] = True
        trace["product_mode_final_closeout_checkpoint_max"] = (
            PRODUCT_MODE_FINAL_CLOSEOUT_MAX_CHECKPOINTS
        )
        trace["product_mode_final_closeout_checkpoint_round"] = agent_round
        trace["product_mode_final_closeout_reason"] = reason
        current = trace.get("product_mode_final_closeout_checkpoint_count")
        if not isinstance(current, int) or isinstance(current, bool):
            current = 0
        trace["product_mode_final_closeout_checkpoint_count"] = current + 1

    def final_closeout_checkpoint_needed(
        round_result: Any | None,
        *,
        task_instruction_sent: bool,
    ) -> bool:
        return bool(
            treatment
            and task_instruction_sent
            and product_mode_entry_lifecycle_gate_satisfied()
            and not _product_mode_solver_activity_observed(trace, round_result)
            and not final_closeout_checkpoint_budget_exhausted()
        )

    def product_mode_workflow_entry_activity_satisfied() -> bool:
        if not workflow_lifecycle_driver or not _product_mode_depth_gate_satisfied(trace):
            return False
        task_facing_success_count = _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_task_facing_success_count",
        )
        task_facing_failure_count = _trace_max_int(
            trace,
            "remote_command_file_bridge_agent_task_facing_failure_count",
        )
        legacy_task_facing_recorded = bool(
            task_facing_success_count == 0
            and task_facing_failure_count == 0
            and trace.get("remote_command_file_bridge_agent_operation_trace_status")
            == "agent_operation_trace_recorded"
            and _trace_max_int(
                trace,
                "remote_command_file_bridge_agent_task_facing_operation_count",
            )
            > 0
        )
        return bool(
            task_facing_success_count > 0
            or trace.get("remote_command_file_bridge_agent_operation_trace_satisfied")
            is True
            or legacy_task_facing_recorded
        )

    def product_mode_entry_lifecycle_gate_satisfied() -> bool:
        return bool(
            _product_mode_agent_lifecycle_gate_satisfied(trace)
            or product_mode_workflow_entry_activity_satisfied()
        )

    class ProductModeUser(BaseUser):
        """Main-table autonomous product-mode controller."""

        def __init__(self) -> None:
            super().__init__()
            self._persistent_constraint_clause = ""
            self._task_instruction_sent = False

        def _scheduled_continuation_prompt(
            self,
            *,
            scheduled_round: int,
            declared_done_continuation: bool = False,
            task_instruction: str | None = None,
        ) -> str:
            if treatment:
                mode_clause = (
                    "Continue from your LoopX case state at "
                    f"`{case_state_path}` and todo/replan ledger; "
                    "re-read and update them if local evidence changed."
                )
            else:
                mode_clause = (
                    "Continue from your own local plan/todo notes; do not use "
                    "LoopX CLI/state/ledger."
                )
            done_clause = (
                "A previous response included the done marker, but this "
                "protocol uses success-or-budget stopping; keep using the "
                "remaining fixed budget for local inspection, implementation, "
                "and validation. "
                if declared_done_continuation
                else ""
            )
            task_clause = ""
            if task_instruction is not None:
                task_clause = (
                    "\n\n--- TASK INSTRUCTION ---\n"
                    f"{task_instruction}\n\n"
                    "The task packet is now available because the solver-side "
                    "LoopX lifecycle checkpoint was observed. The benchmark "
                    "task is the primary objective from this round onward. "
                    "Keep the lifecycle ledger current while solving, but do "
                    "not run closeout or declare done until after meaningful "
                    "task-facing work or local validation."
                )
            return (
                f"Scheduled product-mode continuation round {scheduled_round} of "
                f"{max_rounds}. This is part of the fixed autonomous budget and "
                "is not by itself evidence that the official verifier passed or "
                "failed. "
                + (
                    "You are not being shown official reward, pass/fail status, "
                    "verifier error, or verifier output. "
                )
                +
                f"{goal_start_loop_alignment_contract()}"
                f"{done_clause}"
                f"{self._persistent_constraint_clause} {mode_clause} Keep scope "
                "narrow, validate locally, and if there are no remaining goals, "
                f"end with {DECLARED_DONE_MARKER}."
                f"{task_clause}"
            )

        async def run(
            self,
            round: int,
            instruction: str,
            round_result: RoundResult | None = None,
        ) -> str | None:
            _inc_counter(trace, "heartbeat_count")
            trace["max_round_observed"] = max(int(trace.get("max_round_observed", -1)), round)
            reward = _record_round_reward(
                trace,
                agent_round=round,
                round_result=round_result,
            )
            if round_result is not None:
                _inc_counter(trace, "official_feedback_blinded_count")
                if treatment:
                    _merge_round_result_trajectory_lifecycle_summary(round_result, trace)
                    _merge_acp_trajectory_summary(plan or {}, trace)
                    _merge_host_local_acp_relay_trace_summary(plan or {}, trace)
                    no_tool_calls = _round_result_tool_call_count(round_result) == 0
                    no_lifecycle_requests = (
                        trace.get(
                            "remote_command_file_bridge_agent_operation_trace_status"
                        )
                        == "agent_operation_trace_present_no_requests"
                    )
                    workflow_entry_activity_satisfied = (
                        product_mode_workflow_entry_activity_satisfied()
                    )
                    lifecycle_entry_satisfied = (
                        product_mode_entry_lifecycle_gate_satisfied()
                    )
                    if (
                        (
                            (no_tool_calls and not workflow_entry_activity_satisfied)
                            or no_lifecycle_requests
                        )
                        and not lifecycle_entry_satisfied
                    ):
                        _record_product_mode_lifecycle_checkpoint_gap(
                            trace,
                            agent_round=round,
                        )
                        _inc_counter(trace, "controller_action_decisions")
                        if round < max_rounds:
                            _inc_counter(trace, "followup_prompt_count")
                            trace["last_decision"] = (
                                "send_followup_after_product_mode_no_tool_calls_without_lifecycle"
                                if no_tool_calls
                                else "send_followup_after_product_mode_agent_no_lifecycle_requests"
                            )
                            return (
                                f"Scheduled product-mode continuation round {round + 1} "
                                f"of {max_rounds}. The previous round did not create "
                                "task-facing bridge activity for the selected P0 todo, "
                                "so it is not a valid closeout. Do not answer with "
                                "status-only prose. Use the available sandbox "
                                "command/file bridge now to inspect or modify the task "
                                "workspace, then update the selected LoopX todo with "
                                "public-safe evidence before any done/closeout claim. "
                                f"{goal_start_loop_alignment_contract()}"
                            )
                        if no_tool_calls:
                            _record_product_mode_no_tool_call_lifecycle_abort(
                                trace,
                                agent_round=round,
                            )
                        if no_lifecycle_requests:
                            _record_product_mode_no_lifecycle_request_abort(
                                trace,
                                agent_round=round,
                            )
                        _inc_counter(trace, "stop_decision_count")
                        trace["last_decision"] = (
                            "stop_after_product_mode_agent_no_lifecycle_requests"
                            if no_lifecycle_requests
                            else "stop_after_product_mode_no_tool_calls_without_lifecycle"
                        )
                        raise SkillsBenchProductModeNoLifecycleRequests(
                            "loopx-product-mode agent produced no case-local "
                            "LoopX lifecycle request before official verifier"
                        )
                    if (
                        product_mode_entry_lifecycle_gate_satisfied()
                        and not self._task_instruction_sent
                    ):
                        self._task_instruction_sent = True
                        trace[
                            "product_mode_task_instruction_deferred_until_agent_lifecycle"
                        ] = True
                        trace[
                            "product_mode_task_instruction_sent_after_agent_lifecycle"
                        ] = True
                        _inc_counter(trace, "controller_action_decisions")
                        _inc_counter(trace, "followup_prompt_count")
                        trace["last_decision"] = (
                            "send_product_mode_task_instruction_after_agent_lifecycle"
                        )
                        return self._scheduled_continuation_prompt(
                            scheduled_round=round + 1,
                            task_instruction=instruction,
                        )
                    repair_decision = advance_skillsbench_typed_repair_controller(
                        trace,
                        agent_round=round,
                        scheduled_round=round + 1,
                        max_rounds=max_rounds,
                        task_instruction_sent=self._task_instruction_sent,
                    )
                    if repair_decision:
                        _inc_counter(trace, "controller_action_decisions")
                        trace["last_decision"] = repair_decision["last_decision"]
                        if repair_decision["action"] == "stop":
                            _inc_counter(trace, "stop_decision_count")
                            return None
                        _inc_counter(trace, "followup_prompt_count")
                        if repair_decision["action"] == "continue":
                            return self._scheduled_continuation_prompt(
                                scheduled_round=round + 1,
                            )
                        return build_skillsbench_typed_repair_prompt(
                            scheduled_round=round + 1,
                            max_rounds=max_rounds,
                            case_state_path=case_state_path,
                            loop_alignment_contract=goal_start_loop_alignment_contract(),
                            persistent_constraint_clause=(
                                self._persistent_constraint_clause
                            ),
                            trigger_kind=repair_decision.get("trigger_kind", ""),
                        )
                    if (
                        self._task_instruction_sent
                        and product_mode_entry_lifecycle_gate_satisfied()
                        and _product_mode_host_local_idle_no_task_output_progress_applicable(
                            trace,
                            round_result,
                            reward=(
                                float(reward)
                                if isinstance(reward, (int, float))
                                and not isinstance(reward, bool)
                                else None
                            ),
                        )
                    ):
                        host_idle_stop = (
                            _record_product_mode_host_local_idle_no_task_output_progress(
                                trace,
                                agent_round=round,
                                reward=(
                                    float(reward)
                                    if isinstance(reward, (int, float))
                                    and not isinstance(reward, bool)
                                    else None
                                ),
                                round_result=round_result,
                            )
                        )
                        _inc_counter(trace, "controller_action_decisions")
                        if host_idle_stop or round >= max_rounds:
                            _inc_counter(trace, "stop_decision_count")
                            trace["last_decision"] = (
                                "stop_after_product_mode_host_local_idle_no_"
                                "task_output_progress"
                            )
                            return None
                        _inc_counter(trace, "followup_prompt_count")
                        trace["last_decision"] = (
                            "send_product_mode_host_local_idle_no_task_output_"
                            "progress_recovery"
                        )
                        return host_local_idle_no_progress_prompt(
                            round + 1,
                            task_instruction=instruction,
                        )
                if _round_result_declared_done(round_result):
                    if treatment:
                        if not _product_mode_depth_gate_satisfied(trace):
                            _record_product_mode_depth_gate_gap(
                                trace,
                                agent_round=round,
                            )
                            _record_product_mode_lifecycle_checkpoint_gap(
                                trace,
                                agent_round=round,
                            )
                            _inc_counter(trace, "controller_action_decisions")
                            if round >= max_rounds:
                                _inc_counter(trace, "stop_decision_count")
                                trace["last_decision"] = (
                                    "stop_after_budget_with_declared_done_depth_gate_gap"
                                )
                                return None
                            _inc_counter(trace, "followup_prompt_count")
                            trace["last_decision"] = (
                                "send_product_mode_lifecycle_checkpoint_continuation"
                            )
                            return (
                                lifecycle_checkpoint_prompt(round + 1)
                                + "\n\nYou declared done, but the required "
                                "LoopX case-state interaction was not "
                                "observed. Re-read the updated case state, "
                                "validate locally, and only end with "
                                f"{DECLARED_DONE_MARKER} after it records no "
                                "open agent todos and no remaining goals."
                            )
                        if not _product_mode_solver_activity_observed(
                            trace,
                            round_result,
                        ):
                            _record_product_mode_solver_activity_gap(
                                trace,
                                agent_round=round,
                            )
                            _inc_counter(trace, "controller_action_decisions")
                            if round >= max_rounds:
                                if final_closeout_checkpoint_needed(
                                    round_result,
                                    task_instruction_sent=self._task_instruction_sent,
                                ):
                                    record_final_closeout_checkpoint(
                                        agent_round=round,
                                        reason=(
                                            "declared_done_at_budget_without_selected_p0_closeout"
                                        ),
                                    )
                                    _inc_counter(trace, "followup_prompt_count")
                                    trace["last_decision"] = (
                                        "send_product_mode_final_closeout_after_"
                                        "declared_done_budget_boundary"
                                    )
                                    return final_closeout_prompt(round + 1)
                                _inc_counter(trace, "stop_decision_count")
                                trace["last_decision"] = (
                                    "stop_after_budget_with_declared_done_solver_activity_gap"
                                )
                                return None
                            _inc_counter(trace, "followup_prompt_count")
                            trace["last_decision"] = (
                                "send_product_mode_solver_activity_continuation"
                            )
                            return solver_activity_prompt(
                                round + 1,
                                task_instruction=instruction,
                            )
                    if treatment:
                        _record_declared_done(
                            trace,
                            agent_round=round,
                            reward=reward,
                        )
                        if (
                            isinstance(reward, (int, float))
                            and not isinstance(reward, bool)
                            and reward >= 1.0
                        ):
                            _inc_counter(trace, "controller_action_decisions")
                            _inc_counter(trace, "stop_decision_count")
                            trace["last_decision"] = (
                                "stop_after_product_mode_official_success_observed_without_feedback"
                            )
                            return None
                        _record_product_mode_declared_done_below_passing_reward(
                            trace,
                            agent_round=round,
                            reward=(
                                float(reward)
                                if isinstance(reward, (int, float))
                                and not isinstance(reward, bool)
                                else None
                            ),
                        )
                        _inc_counter(trace, "controller_action_decisions")
                        if round >= max_rounds:
                            _inc_counter(trace, "stop_decision_count")
                            trace["last_decision"] = (
                                "stop_after_product_mode_budget_with_"
                                "declared_done_below_passing_reward"
                            )
                            return None
                        if not (
                            isinstance(reward, (int, float))
                            and not isinstance(reward, bool)
                            and reward < 1.0
                            and _product_mode_agent_bridge_closeout_observed(trace)
                            and skillsbench_projected_open_todo_count(trace) == 0
                        ):
                            _inc_counter(trace, "followup_prompt_count")
                            trace["last_decision"] = (
                                "send_product_mode_success_or_budget_"
                                "continuation_after_declared_done"
                            )
                            return self._scheduled_continuation_prompt(
                                scheduled_round=round + 1,
                                declared_done_continuation=True,
                            )
                        repair_started = begin_skillsbench_typed_repair(
                            trace,
                            trigger_round=round,
                            scheduled_round=round + 1,
                        )
                        if not repair_started:
                            record_skillsbench_typed_repair_terminal(
                                trace,
                                agent_round=round,
                                reason="unchanged_frontier_already_repaired",
                            )
                            _inc_counter(trace, "stop_decision_count")
                            trace["last_decision"] = (
                                "stop_after_product_mode_typed_repair_repeated_frontier"
                            )
                            return None
                        _inc_counter(trace, "followup_prompt_count")
                        trace["last_decision"] = (
                            "send_product_mode_typed_repair_after_declared_done"
                        )
                        return build_skillsbench_typed_repair_prompt(
                            scheduled_round=round + 1,
                            max_rounds=max_rounds,
                            case_state_path=case_state_path,
                            loop_alignment_contract=(
                                goal_start_loop_alignment_contract()
                            ),
                            persistent_constraint_clause=(
                                self._persistent_constraint_clause
                            ),
                        )
                    _inc_counter(trace, "controller_action_decisions")
                    _inc_counter(trace, "stop_decision_count")
                    _record_declared_done(trace, agent_round=round, reward=reward)
                    trace["last_decision"] = "stop_after_agent_declared_done"
                    return None
            if reward is not None and reward >= 1.0:
                _inc_counter(trace, "controller_action_decisions")
                if final_closeout_checkpoint_needed(
                    round_result,
                    task_instruction_sent=self._task_instruction_sent,
                ):
                    trace[
                        "product_mode_final_closeout_superseded_by_official_success"
                    ] = True
                    trace["product_mode_final_closeout_superseded_round"] = round
                    trace["product_mode_final_closeout_superseded_reason"] = (
                        "official_success_observed_before_selected_p0_closeout"
                    )
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = (
                    "stop_after_product_mode_official_success_observed_without_feedback"
                )
                return None
            if round >= max_rounds:
                _inc_counter(trace, "controller_action_decisions")
                if final_closeout_checkpoint_needed(
                    round_result,
                    task_instruction_sent=self._task_instruction_sent,
                ):
                    _record_product_mode_solver_activity_gap(
                        trace,
                        agent_round=round,
                    )
                    record_final_closeout_checkpoint(
                        agent_round=round,
                        reason="budget_boundary_without_selected_p0_closeout",
                    )
                    _inc_counter(trace, "followup_prompt_count")
                    trace["last_decision"] = (
                        "send_product_mode_final_closeout_after_budget_boundary"
                    )
                    return final_closeout_prompt(round + 1)
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = "stop_after_product_mode_budget"
                return None
            if (
                treatment
                and round_result is not None
                and self._task_instruction_sent
                and product_mode_entry_lifecycle_gate_satisfied()
                and not _product_mode_solver_activity_observed(
                    trace,
                    round_result,
                )
            ):
                _record_product_mode_solver_activity_gap(
                    trace,
                    agent_round=round,
                )
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "followup_prompt_count")
                trace["last_decision"] = (
                    "send_product_mode_solver_activity_continuation"
                )
                return solver_activity_prompt(
                    round + 1,
                    task_instruction=instruction,
                )
            if round == 0:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "initial_prompt_count")
                trace["last_decision"] = "send_initial_product_mode_prompt"
                self._persistent_constraint_clause = _protected_paths_continuation_clause(
                    instruction
                )
                protected_paths = _protected_paths_from_instruction(instruction)
                if protected_paths:
                    trace["persistent_constraint_protected_paths"] = protected_paths
                if treatment:
                    prefix = "LoopX product-mode treatment round 1. "
                    trace["case_goal_state_packet_present"] = True
                    self._task_instruction_sent = True
                    trace[
                        "product_mode_task_instruction_deferred_until_agent_lifecycle"
                    ] = False
                    trace["product_mode_task_instruction_sent_initially"] = True
                    control_clause = (
                        "Use LoopX as your product control plane: create "
                        "a compact goal state, maintain todos, replan when local "
                        "evidence changes, and use LoopX CLI/status/ledger "
                        "surfaces when available. "
                        + treatment_state_contract()
                    )
                    return (
                        prefix
                        + "You are running inside the official SkillsBench sandbox. "
                        + feedback_policy_clause
                        + "--- LOOPX PRODUCT-MODE CONTROL PLANE ---\n"
                        f"{control_clause}"
                        "For this treatment, LoopX lifecycle evidence is a "
                        "hard product-mode requirement: "
                        + (
                            "the canonical workflow lifecycle driver has already "
                            "completed the case-local quota/todo/update/refresh "
                            "checkpoint through the solver bridge before this "
                            "prompt. Do not repeat setup lifecycle as your first "
                            "action. Make the first agent action a task-facing "
                            "sandbox bridge exec from `/app`, such as "
                            "`pwd && ls -la`, by copying and running the bridge "
                            "packet's `FIRST ACTION REQUIRED` command before "
                            "any prose planning, solving narrative, or final "
                            "answer. "
                            if workflow_lifecycle_driver
                            else
                            f"{entry_lifecycle_requirement()} before any final "
                            "answer. "
                        )
                        + "The benchmark task instruction is visible in this "
                        "first round so the task semantics stay aligned with the "
                        "baseline. Do not run case closeout or declare done "
                        "during this setup checkpoint.\n\n"
                        "--- TASK INSTRUCTION ---\n"
                        f"{instruction}"
                    )
                else:
                    prefix = "Raw Codex autonomous max5 baseline round 1. "
                    control_clause = (
                        "Use ordinary Codex autonomous behavior. You may keep a "
                        "brief local plan or todo list, but do not use Goal "
                        "Harness state, todo, replan, ledger, CLI surfaces, or "
                    f"`{case_state_path}`. "
                    )
                return (
                    prefix
                    + "You are running inside the official SkillsBench sandbox. "
                    + "No official reward, pass/fail status, verifier error, "
                    "verifier output, or verifier tail will be shown during this "
                    "run. If you believe the task is complete and there are no "
                    "remaining goals, end your response with "
                    f"{DECLARED_DONE_MARKER}.\n\n"
                    "--- TASK INSTRUCTION ---\n"
                    f"{instruction}"
                    + (
                        "\n\n--- LOOPX PRODUCT-MODE CONTROL PLANE ---\n"
                        f"{control_clause}"
                        "For this treatment, LoopX lifecycle evidence is a "
                        "hard product-mode requirement: "
                        f"{entry_lifecycle_requirement()}, then solve and "
                        "validate the benchmark task. Do not run case closeout "
                        "or declare done until after meaningful task-facing work "
                        "or local validation. If you later declare done without "
                        "task-facing closeout evidence, the controller will ask "
                        "for the exact closeout sequence without exposing "
                        "official reward or verifier output."
                        if treatment
                        else "\n\n" + control_clause
                    )
                )

            _inc_counter(trace, "controller_action_decisions")
            _inc_counter(trace, "followup_prompt_count")
            if treatment:
                _merge_acp_trajectory_summary(plan or {}, trace)
                if not product_mode_entry_lifecycle_gate_satisfied():
                    _record_product_mode_lifecycle_checkpoint_gap(
                        trace,
                        agent_round=round,
                    )
                    trace["last_decision"] = (
                        "send_product_mode_lifecycle_checkpoint_continuation"
                    )
                    return lifecycle_checkpoint_prompt(round + 1)
                if not self._task_instruction_sent:
                    self._task_instruction_sent = True
                    trace[
                        "product_mode_task_instruction_deferred_until_agent_lifecycle"
                    ] = True
                    trace[
                        "product_mode_task_instruction_sent_after_agent_lifecycle"
                    ] = True
                    trace["last_decision"] = (
                        "send_product_mode_task_instruction_after_agent_lifecycle"
                    )
                    return self._scheduled_continuation_prompt(
                        scheduled_round=round + 1,
                        task_instruction=instruction,
                    )
            trace["last_decision"] = "send_product_mode_scheduled_continuation"
            return self._scheduled_continuation_prompt(scheduled_round=round + 1)

    return ProductModeUser()


async def run_benchflow_case(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> Path | dict[str, Any]:
    prerequisites = plan.setdefault("runner_prerequisites", {})
    prerequisites["benchflow_run_stage"] = "entered"
    source_fingerprint = plan.get("loopx_runner_source_fingerprint")
    if isinstance(source_fingerprint, dict) and source_fingerprint.get("first_blocker"):
        prerequisites["benchflow_run_stage"] = "runner_source_fingerprint_check"
        raise RuntimeError(str(source_fingerprint["first_blocker"]))
    skillsbench_root = Path(args.skillsbench_root).expanduser().resolve()
    prerequisites["benchflow_run_stage"] = "task_path_check"
    task_path = skillsbench_root / "tasks" / args.task_id
    if not task_path.exists():
        raise FileNotFoundError(f"SkillsBench task not found: {task_path}")
    prerequisites["benchflow_run_stage"] = "loopx_source_preflight"
    loopx_source_contract = _loopx_source_mount_contract(args)
    if loopx_source_contract.get("requested") and not loopx_source_contract.get("ready"):
        raise FileNotFoundError(
            "LoopX source mount requested but local source files are missing; "
            "use --no-loopx-source-mount to test the public GitHub installer instead"
        )
    verifier_dependency_cache_policy_enabled = verifier_cache.dependency_cache_enabled(
        sandbox=args.sandbox,
        mode=args.verifier_dependency_cache_mode,
    )
    prerequisites["benchflow_run_stage"] = "task_staging"
    effective_task_path, staging_metadata = stage_task_for_sandbox(
        task_path=task_path,
        jobs_dir=Path(plan["jobs_dir"]),
        job_name=str(plan["job_name"]),
        sandbox=args.sandbox,
        include_task_skills=bool(args.include_task_skills),
        benchmark_egress_proxy_env=_benchmark_egress_proxy_env(args),
        docker_gcr_mirror_prefix=args.docker_gcr_mirror_prefix,
        verifier_dependency_cache_enabled=(
            verifier_dependency_cache_policy_enabled
        ),
        loopx_case_runtime_required=_is_case_loopx_route(args.route),
    )
    plan["task_staging"] = staging_metadata
    plan["effective_task_path"] = str(effective_task_path)
    verifier_dependency_cache_root, verifier_dependency_cache_contract = (
        verifier_cache.prepare_dependency_cache(
            args.verifier_dependency_cache_root,
            requested=bool(
                staging_metadata.get("verifier_dependency_cache_required")
            ),
            sandbox_user=str(args.sandbox_user),
        )
    )
    verifier_dependency_cache_contract["verifier_dependency_cache_mode"] = (
        args.verifier_dependency_cache_mode
    )
    prerequisites.update(verifier_dependency_cache_contract)
    prerequisites["benchflow_run_stage"] = "base_image_prewarm"
    _write_public_runner_config(plan)
    _write_public_runner_prerequisites(plan)
    prerequisites.update(
        proxy_runtime.prewarm_dockerfile_base_images(
            effective_task_path / "environment" / "Dockerfile",
            enabled=(
                args.sandbox == "docker"
                and bool(_benchmark_egress_proxy_env(args))
            ),
        )
    )
    prerequisites["benchflow_run_stage"] = "base_image_prewarm_complete"
    _write_public_runner_config(plan)
    _write_public_runner_prerequisites(plan)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    prerequisites["benchflow_run_stage"] = "benchflow_import"
    import benchflow.acp.runtime as benchflow_acp_runtime
    import benchflow.rollout as benchflow_rollout_module
    import benchflow.sandbox.setup as benchflow_sandbox_setup_module
    try:
        benchflow_rollout_planes_module = importlib.import_module(
            "benchflow.rollout_planes"
        )
    except ModuleNotFoundError as exc:
        if exc.name != "benchflow.rollout_planes":
            raise
        benchflow_rollout_planes_module = None
    from benchflow.rollout import Rollout, RolloutConfig
    from benchflow.runtime import run as benchflow_run
    prerequisites["benchflow_rollout_planes_module_available"] = (
        benchflow_rollout_planes_module is not None
    )
    connect_as_return_arity = _benchflow_connect_as_unpack_arity(Rollout.connect_as)
    if connect_as_return_arity is not None:
        prerequisites["host_local_acp_connect_as_unpack_return_arity"] = (
            connect_as_return_arity
        )
    prerequisites["benchflow_run_stage"] = "runtime_prepare"

    host_local_acp_command = _host_local_acp_launch_command(args, plan)
    runtime_mounts = (
        _benchflow_agent_runtime_mounts(args)
        if args.require_preinstalled_benchflow_agent_runtime
        else []
    )
    loopx_source_mounts = _loopx_source_mounts(args)
    verifier_dependency_cache_mounts = verifier_cache.dependency_cache_mount(
        verifier_dependency_cache_root
    )
    container_mounts = [
        *runtime_mounts,
        *loopx_source_mounts,
        *verifier_dependency_cache_mounts,
    ]

    async def connect_host_local_acp(
        env: Any,
        agent: str,
        agent_launch: str,
        agent_env: dict[str, str],
        sandbox_user: str | None,
        model: str | None,
        rollout_dir: Path,
        environment: str,
        agent_cwd: str,
        reasoning_effort: str | None = None,
        mcp_servers: list[Any] | None = None,
        **_ignored: Any,
    ) -> tuple[Any, ...]:
        del (
            agent_launch,
            sandbox_user,
            rollout_dir,
            environment,
            reasoning_effort,
        )
        from benchflow.acp.client import ACPClient
        from benchflow.acp.transport import StdioTransport

        prerequisites = plan.setdefault("runner_prerequisites", {})
        prerequisites["host_local_acp_launch_status"] = "connecting"
        local_acp_command = list(host_local_acp_command)
        sandbox_bridge_command = _host_local_acp_docker_bridge_command(
            env,
            args,
            plan,
        )
        if sandbox_bridge_command:
            local_acp_command = _set_option_value(
                local_acp_command,
                "--remote-command-file-bridge-command",
                sandbox_bridge_command,
            )
            local_acp_command = _set_option_value(
                local_acp_command,
                "--remote-command-file-bridge-agent-command",
                sandbox_bridge_command,
            )
            prerequisites["remote_command_file_bridge_command_configured"] = True
            prerequisites["remote_command_file_bridge_agent_command_configured"] = True
            prerequisites["remote_command_file_bridge_agent_command_instrumented"] = True
            prerequisites["remote_command_file_bridge_agent_transport_mode"] = (
                "json_file_queue"
            )
            prerequisites["remote_command_file_bridge_agent_queue_configured"] = True
            prerequisites["remote_command_file_bridge_agent_queue_path_recorded"] = False
            prerequisites["remote_command_file_bridge_solver_wiring_configured"] = True
            prerequisites["remote_command_file_bridge_consumption_status"] = (
                "solver_wiring_configured_pending_prompt"
            )
            if _is_case_loopx_route(args.route):
                prerequisites[
                    "remote_command_file_bridge_agent_operation_trace_required"
                ] = True
                prerequisites[
                    "remote_command_file_bridge_agent_operation_trace_status"
                ] = "external_agent_command_relay_wrapped_pending_trace"
        else:
            prerequisites.setdefault(
                "host_local_acp_sandbox_bridge_mode",
                "configured_command_fallback",
            )
            prerequisites.setdefault("host_local_acp_sandbox_bridge_configured", False)
            prerequisites.setdefault("host_local_acp_sandbox_bridge_path_recorded", False)
        target_env = _host_local_acp_target_env(agent_env, args=args)
        prerequisites["host_local_acp_target_env_forwarded"] = bool(target_env)
        prerequisites["host_local_acp_target_env_key_count"] = len(target_env)
        prerequisites["host_local_acp_target_env_keys"] = sorted(target_env)
        client = ACPClient(
            StdioTransport(
                command=local_acp_command[0],
                args=local_acp_command[1:],
                env=target_env,
                cwd=str(REPO_ROOT),
            )
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=60)
            init_result = await asyncio.wait_for(client.initialize(), timeout=60)
            session_new_kwargs: dict[str, Any] = {"cwd": agent_cwd}
            if "mcp_servers" in inspect.signature(client.session_new).parameters:
                session_new_kwargs["mcp_servers"] = mcp_servers
            session = await asyncio.wait_for(
                client.session_new(**session_new_kwargs),
                timeout=60,
            )
            agent_name = (
                init_result.agent_info.name if init_result.agent_info else agent
            )
            if model:
                await asyncio.wait_for(client.set_model(model), timeout=60)
            prerequisites["host_local_acp_launch_status"] = "connected"
            if isinstance(controller_trace, dict):
                controller_trace["native_goal_worker_route"] = (
                    args.route == "codex-app-server-goal-baseline"
                )
                controller_trace["native_goal_worker_connect_count"] = int(
                    controller_trace.get("native_goal_worker_connect_count") or 0
                ) + 1
                controller_trace["native_goal_worker_connected"] = True
                controller_trace["last_decision"] = (
                    "host_app_server_goal_worker_connected"
                )
            return_arity = connect_as_return_arity or _benchflow_connect_acp_return_arity(
                original_runtime_connect_acp
            )
            prerequisites["host_local_acp_connect_return_arity"] = return_arity
            if return_arity >= 4:
                try:
                    from benchflow.agents.protocol import ACPSessionAdapter

                    session_adapter = ACPSessionAdapter(client)
                    prerequisites["host_local_acp_session_adapter_status"] = (
                        "benchflow_agents_protocol"
                    )
                except ModuleNotFoundError:
                    session_adapter = client
                    prerequisites["host_local_acp_session_adapter_status"] = (
                        "fallback_client"
                    )
                return client, session, session_adapter, agent_name
            return client, session, agent_name
        except Exception:
            prerequisites["host_local_acp_launch_status"] = "failed"
            with contextlib.suppress(Exception):
                await client.close()
            raise

    async def connect_host_local_acp_method(
        self: Any,
        *call_args: Any,
        **call_kwargs: Any,
    ) -> tuple[Any, ...]:
        del self
        return await connect_host_local_acp(*call_args, **call_kwargs)

    async def ensure_codex_acp_runtime_deps(env: Any) -> None:
        bootstrap = await env.exec(
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD,
            timeout_sec=600,
        )
        if bootstrap.return_code != 0:
            stderr = (getattr(bootstrap, "stderr", "") or "").strip()
            stdout = (getattr(bootstrap, "stdout", "") or "").strip()
            detail = stderr or stdout or "no output"
            raise RuntimeError(
                "codex-acp runtime container bootstrap failed: "
                + detail[:1000]
            )
        result = await env.exec(CODEX_ACP_RUNTIME_DEPS_SETUP_CMD, timeout_sec=300)
        if result.return_code != 0:
            stderr = (getattr(result, "stderr", "") or "").strip()
            stdout = (getattr(result, "stdout", "") or "").strip()
            detail = stderr or stdout or "no output"
            raise RuntimeError(
                "codex-acp runtime dependency setup failed: "
                + detail[:1000]
            )

    async def run_codex_acp_launch_preflight(env: Any) -> None:
        prerequisites = plan.setdefault("runner_prerequisites", {})
        prerequisites["codex_acp_runtime_launch_preflight_stage"] = (
            "preinstalled_benchflow_layer_after_sandbox_setup_before_acp_connect"
            if args.require_preinstalled_benchflow_agent_runtime
            else "after_agent_install_before_acp_connect"
        )
        prerequisites["codex_acp_runtime_launch_preflight_status"] = "running"
        prerequisites["codex_acp_runtime_launch_preflight_raw_logs_read"] = False
        result = await env.exec(
            CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD,
            timeout_sec=CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_TIMEOUT_SEC,
        )
        prerequisites["codex_acp_runtime_launch_preflight_rc"] = int(
            result.return_code
        )
        if result.return_code != 0:
            stderr = (getattr(result, "stderr", "") or "").strip()
            stdout = (getattr(result, "stdout", "") or "").strip()
            detail = stderr or stdout or "no output"
            prerequisites["codex_acp_runtime_launch_preflight"] = False
            prerequisites["codex_acp_runtime_launch_preflight_status"] = "failed"
            raise RuntimeError(
                "codex-acp runtime launch preflight failed: " + detail[:1000]
            )
        prerequisites["codex_acp_runtime_launch_preflight"] = True
        prerequisites["codex_acp_runtime_launch_preflight_status"] = "passed"

    async def seed_product_mode_case_state(env: Any) -> None:
        if not _is_case_loopx_route(args.route):
            return
        payload = benchmark_case_loopx_install_payload(
            benchmark_id="skillsbench",
            case_id=args.task_id,
            arm_id=_loopx_case_arm_id_for_route(args.route),
            route=args.route,
            max_rounds=args.max_rounds,
            case_loopx_source_path=_loopx_case_source_path_for_container(args),
            goal_start_product_mode=_is_goal_start_product_mode_route(args.route),
        )
        trace = controller_trace if isinstance(controller_trace, dict) else {}
        trace["case_goal_state_init_required"] = True
        trace["case_goal_state_path"] = payload.get("case_state_path") or ""
        trace["case_goal_state_schema_version"] = payload.get("schema_version") or ""
        trace["loopx_lifecycle_driver_schema_version"] = (
            payload.get("lifecycle_driver_schema_version") or ""
        )
        trace["loopx_formal_treatment_semantics"] = (
            payload.get("formal_treatment_semantics") or ""
        )
        trace["loopx_canonical_product_mode_lifecycle_driver"] = bool(
            payload.get("canonical_product_mode_lifecycle_driver")
        )
        trace["loopx_execution_style"] = payload.get("execution_style") or ""
        trace["loopx_case_cli_path"] = payload.get("case_cli_path") or ""
        trace["loopx_case_source_install_requested"] = bool(
            payload.get("case_loopx_source_install_requested")
        )
        trace["loopx_case_source_path_recorded"] = bool(
            payload.get("case_loopx_source_path_recorded")
        )
        trace["loopx_case_registry_path"] = payload.get("case_registry_path") or ""
        trace["loopx_case_runtime_root"] = payload.get("case_runtime_root") or ""
        trace["loopx_case_agent_id"] = payload.get("case_agent_id") or ""
        trace["loopx_case_todo_id"] = payload.get("case_todo_id") or ""
        trace["loopx_case_todo_seeded"] = bool(payload.get("case_todo_seeded"))
        trace["loopx_case_todo_preclaimed"] = bool(payload.get("case_todo_preclaimed"))
        for key in (
            "goal_start_product_mode",
            "goal_start_plan_observed",
            "planned_todo_count",
            "planned_todo_ids",
            "planned_todo_texts_public_safe",
            "planned_p0_count",
            "planner_before_todo_write",
            "same_priority_order_preserved",
            "selected_p0_todo_id",
            "selected_todo_claimed",
            "selected_todo_updated_before_solver",
            "selected_todo_completed_before_spend",
            "non_selected_todos_preserved_open_or_deferred",
        ):
            trace[key] = payload.get(key)
        trace["case_goal_state_initialized_before_agent"] = False
        result = await env.exec(str(payload["command"]), timeout_sec=180)
        trace["case_goal_state_init_rc"] = int(result.return_code)
        if result.return_code != 0:
            stderr = (getattr(result, "stderr", "") or "").strip()
            stdout = (getattr(result, "stdout", "") or "").strip()
            detail = stderr or stdout or "no output"
            failed_phase = _last_loopx_case_init_phase(detail)
            if failed_phase:
                trace["case_goal_state_init_failed_phase"] = failed_phase
            blocker = _loopx_case_init_failure_blocker(detail)
            if blocker:
                trace["case_goal_state_init_first_blocker"] = blocker
            trace["case_goal_state_init_status"] = "failed"
            raise RuntimeError(
                "LoopX official case lifecycle init failed: " + detail[:1000]
            )
        trace["case_goal_state_initialized_before_agent"] = True
        trace["case_goal_state_init_status"] = "passed"
        trace["loopx_case_cli_installed_before_agent"] = True

    async def ensure_loopx_source_available(env: Any) -> None:
        if not _is_case_loopx_route(args.route):
            return
        prerequisites = plan.setdefault("runner_prerequisites", {})
        source_contract = _loopx_source_mount_contract(args)
        if not source_contract.get("requested"):
            prerequisites["loopx_source_upload_fallback_status"] = "not_requested"
            return
        prerequisites["loopx_source_upload_target"] = (
            BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET
        )
        prerequisites["loopx_source_upload_raw_material_recorded"] = False
        source_cli = (
            f"{BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET.rstrip('/')}/loopx/cli.py"
        )
        try:
            visible_before = bool(await env.is_file(source_cli))
        except Exception as exc:
            visible_before = False
            prerequisites["loopx_source_upload_fallback_exception_type"] = type(
                exc
            ).__name__
        prerequisites["loopx_source_visible_before_upload"] = visible_before
        if visible_before:
            prerequisites["loopx_source_visible_after_upload"] = True
            prerequisites["loopx_source_upload_fallback_supported"] = True
            prerequisites["loopx_source_upload_fallback_attempted"] = False
            prerequisites["loopx_source_upload_fallback_status"] = "not_needed"
            return
        upload_dir = getattr(env, "upload_dir", None)
        prerequisites["loopx_source_upload_fallback_supported"] = callable(upload_dir)
        if not callable(upload_dir):
            prerequisites["loopx_source_visible_after_upload"] = False
            prerequisites["loopx_source_upload_fallback_attempted"] = False
            prerequisites["loopx_source_upload_fallback_status"] = "unsupported"
            raise RuntimeError("LoopX source is not visible and sandbox upload is unsupported")
        source_dir = Path(str(args.loopx_source_dir)).expanduser()
        prerequisites["loopx_source_upload_fallback_attempted"] = True
        try:
            with tempfile.TemporaryDirectory(prefix="loopx-source-upload-") as tmp:
                staged_source = Path(tmp) / "source"
                staged_source.mkdir()
                file_count = _copy_loopx_source_subset(source_dir, staged_source)
                prerequisites["loopx_source_upload_fallback_file_count"] = file_count
                if file_count <= 0:
                    prerequisites["loopx_source_visible_after_upload"] = False
                    prerequisites["loopx_source_upload_fallback_status"] = (
                        "empty_source_subset"
                    )
                    raise RuntimeError("LoopX source upload subset is empty")
                await env.exec(
                    f"mkdir -p {shlex.quote(BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET)}",
                    timeout_sec=10,
                )
                await upload_dir(staged_source, BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET)
        except Exception as exc:
            prerequisites["loopx_source_upload_fallback_exception_type"] = type(
                exc
            ).__name__
            prerequisites["loopx_source_upload_fallback_status"] = "failed"
            raise
        visible_after = bool(await env.is_file(source_cli))
        prerequisites["loopx_source_visible_after_upload"] = visible_after
        prerequisites["loopx_source_upload_fallback_status"] = (
            "uploaded" if visible_after else "uploaded_but_not_visible"
        )
        if not visible_after:
            raise RuntimeError("LoopX uploaded source is still not visible in sandbox")

    original_install_agent = Rollout.install_agent
    original_runtime_connect_acp = benchflow_acp_runtime.connect_acp
    original_rollout_create_environment = getattr(
        benchflow_rollout_module,
        "_create_environment",
        _MISSING,
    )
    original_setup_create_environment = getattr(
        benchflow_sandbox_setup_module,
        "_create_environment",
        _MISSING,
    )
    original_rollout_connect_acp = getattr(
        benchflow_rollout_module, "connect_acp", _MISSING
    )
    original_rollout_planes_connect_acp = (
        getattr(benchflow_rollout_planes_module, "connect_acp", _MISSING)
        if benchflow_rollout_planes_module is not None
        else _MISSING
    )
    rollout_planes_class = _benchflow_rollout_planes_class(
        benchflow_rollout_planes_module
    )
    original_rollout_planes_class_connect_acp = (
        getattr(rollout_planes_class, "connect_acp", None)
        if rollout_planes_class is not None
        else None
    )
    original_create_environment = (
        getattr(rollout_planes_class, "create_environment", None)
        if rollout_planes_class is not None
        else None
    )

    def create_environment_with_runtime_mount(self: Any, *call_args: Any, **call_kwargs: Any) -> Any:
        if original_create_environment is None:
            raise RuntimeError("BenchFlow rollout planes create_environment missing")
        env = original_create_environment(self, *call_args, **call_kwargs)
        environment = str(call_args[0]) if call_args else ""
        return _record_container_mount_injection(env, environment)

    def _record_container_mount_injection(env: Any, environment: str) -> Any:
        prerequisites = plan.setdefault("runner_prerequisites", {})
        if container_mounts and environment == "docker":
            existing_mounts = getattr(env, "_mounts_json", None) or []
            missing_mounts = [
                mount for mount in container_mounts if mount not in existing_mounts
            ]
            setattr(env, "_mounts_json", [*existing_mounts, *missing_mounts])
            if runtime_mounts:
                prerequisites["benchflow_agent_runtime_mount_injected"] = True
                prerequisites["benchflow_agent_runtime_mount_read_only"] = True
                prerequisites["benchflow_agent_runtime_mount_source_recorded"] = False
            if loopx_source_mounts:
                prerequisites["loopx_source_mount_injected"] = True
                prerequisites["loopx_source_mount_read_only"] = True
                prerequisites["loopx_source_mount_source_recorded"] = False
            if verifier_dependency_cache_mounts:
                prerequisites["verifier_dependency_cache_mount_injected"] = True
                prerequisites["verifier_dependency_cache_raw_path_recorded"] = False
        elif container_mounts:
            if runtime_mounts:
                prerequisites["benchflow_agent_runtime_mount_injected"] = False
                prerequisites["benchflow_agent_runtime_mount_read_only"] = True
                prerequisites["benchflow_agent_runtime_mount_source_recorded"] = False
            if loopx_source_mounts:
                prerequisites["loopx_source_mount_injected"] = False
                prerequisites["loopx_source_mount_read_only"] = True
                prerequisites["loopx_source_mount_source_recorded"] = False
            if verifier_dependency_cache_mounts:
                prerequisites["verifier_dependency_cache_mount_injected"] = False
                prerequisites["verifier_dependency_cache_raw_path_recorded"] = False
        return env

    def create_environment_function_with_runtime_mount(
        environment: str,
        *call_args: Any,
        **call_kwargs: Any,
    ) -> Any:
        if original_rollout_create_environment is _MISSING:
            raise RuntimeError("BenchFlow rollout _create_environment missing")
        env = original_rollout_create_environment(
            environment,
            *call_args,
            **call_kwargs,
        )
        return _record_container_mount_injection(env, environment)

    async def install_agent_host_local_acp(self: Any) -> None:
        cfg = self._config
        prerequisites = plan.setdefault("runner_prerequisites", {})
        prerequisites["agent_execution_mode"] = (
            "host_codex_app_server_goal_worker"
            if args.route == "codex-app-server-goal-baseline"
            else "host_local_acp"
        )
        prerequisites["host_local_acp_launch"] = True
        prerequisites["host_local_acp_launch_status"] = "installing_sandbox"
        prerequisites["container_codex_acp_install_skipped"] = True
        prerequisites["codex_acp_runtime_container_bootstrap"] = False
        prerequisites["codex_acp_runtime_dependency_preflight"] = False
        prerequisites["codex_acp_runtime_launch_preflight"] = True
        prerequisites["codex_acp_runtime_launch_preflight_stage"] = (
            "host_local_acp_container_install_skipped"
        )
        prerequisites["codex_acp_runtime_launch_preflight_status"] = "skipped"
        prerequisites["codex_acp_runtime_launch_preflight_raw_logs_read"] = False
        try:
            prerequisites["host_local_acp_install_stage"] = "pwd_probe"
            try:
                cwd_result = await self._env.exec("pwd", timeout_sec=10)
                prerequisites["host_local_acp_pwd_probe_rc"] = int(
                    getattr(cwd_result, "return_code", 0)
                )
                prerequisites["host_local_acp_pwd_probe_status"] = (
                    "passed"
                    if int(getattr(cwd_result, "return_code", 0)) == 0
                    else "failed"
                )
            except Exception as exc:
                prerequisites["host_local_acp_pwd_probe_status"] = "exception"
                prerequisites["host_local_acp_pwd_probe_exception_type"] = type(
                    exc
                ).__name__
                raise
            if prerequisites["host_local_acp_pwd_probe_status"] != "passed":
                raise RuntimeError("host-local ACP sandbox pwd probe failed")
            cwd_stdout = getattr(cwd_result, "stdout", "") or ""
            if isinstance(cwd_stdout, bytes):
                cwd_stdout = cwd_stdout.decode("utf-8", errors="replace")
                prerequisites["host_local_acp_pwd_probe_stdout_type"] = "bytes"
            else:
                prerequisites["host_local_acp_pwd_probe_stdout_type"] = type(
                    cwd_stdout
                ).__name__
            self._agent_cwd = str(cwd_stdout).strip() or "/app"
            prerequisites["host_local_acp_pwd_probe_cwd_present"] = bool(
                self._agent_cwd
            )
            self._agent_cfg = None
            planes = getattr(self, "_planes", None)
            prerequisites["host_local_acp_rollout_planes_available"] = (
                planes is not None
            )
            if cfg.sandbox_user:
                prerequisites["host_local_acp_install_stage"] = "sandbox_user_setup"
                if planes is not None:
                    self._agent_cwd = await planes.setup_sandbox_user(
                        self._env,
                        cfg.sandbox_user,
                        workspace=self._agent_cwd,
                        timeout_sec=cfg.sandbox_setup_timeout,
                    )
                else:
                    self._agent_cwd = await benchflow_rollout_module.setup_sandbox_user(
                        self._env,
                        cfg.sandbox_user,
                        workspace=self._agent_cwd,
                        timeout_sec=cfg.sandbox_setup_timeout,
                    )
            prerequisites["host_local_acp_install_stage"] = "snapshot_build_config"
            if planes is not None:
                await planes.snapshot_build_config(self._env, workspace=self._agent_cwd)
            else:
                await benchflow_rollout_module._snapshot_build_config(
                    self._env, workspace=self._agent_cwd
                )
            prerequisites["host_local_acp_install_stage"] = "seed_verifier_workspace"
            if planes is not None:
                await planes.seed_verifier_workspace(
                    self._env, workspace=self._agent_cwd, sandbox_user=cfg.sandbox_user
                )
            else:
                await benchflow_rollout_module._seed_verifier_workspace(
                    self._env, workspace=self._agent_cwd, sandbox_user=cfg.sandbox_user
                )
            prerequisites["host_local_acp_install_stage"] = "deploy_skills"
            effective_task_path = getattr(self, "_effective_task_path", cfg.task_path)
            effective_skills_dir = getattr(self, "_effective_skills_dir", cfg.skills_dir)
            effective_skills_sandbox_dir = getattr(
                self,
                "_effective_skills_sandbox_dir",
                getattr(cfg, "skills_sandbox_dir", "/app/skills"),
            )
            if planes is not None:
                await planes.deploy_skills(
                    self._env,
                    effective_task_path,
                    effective_skills_dir,
                    None,
                    cfg.sandbox_user,
                    self._agent_cwd,
                    skills_sandbox_dir=effective_skills_sandbox_dir,
                )
            else:
                await benchflow_rollout_module.deploy_skills(
                    self._env,
                    effective_task_path,
                    effective_skills_dir,
                    None,
                    cfg.sandbox_user,
                    self._agent_cwd,
                    getattr(self, "_task", None),
                    include_task_skills=cfg.include_task_skills,
                )
            if _is_case_loopx_route(args.route):
                prerequisites["host_local_acp_install_stage"] = (
                    "loopx_source_upload_fallback"
                )
                await ensure_loopx_source_available(self._env)
            if cfg.export_generated_skills_to:
                prerequisites["host_local_acp_install_stage"] = (
                    "ensure_generated_skills_dir"
                )
                ensure_sandbox_dir = getattr(
                    benchflow_rollout_module, "_ensure_sandbox_dir", None
                )
                if ensure_sandbox_dir is None:
                    raise RuntimeError("BenchFlow ensure_sandbox_dir unavailable")
                await ensure_sandbox_dir(
                    self._env, cfg.generated_skills_root, cfg.sandbox_user
                )
            prerequisites["host_local_acp_install_stage"] = "lockdown_paths"
            if planes is not None:
                await planes.lockdown_paths(self._env, self._effective_locked)
            else:
                await benchflow_rollout_module.lockdown_paths(
                    self._env, self._effective_locked
                )
            if _is_case_loopx_route(args.route):
                prerequisites["host_local_acp_install_stage"] = "seed_loopx_case_state"
                if isinstance(controller_trace, dict):
                    controller_trace["case_goal_state_init_invocation_stage"] = (
                        "host_local_acp_after_sandbox_install"
                    )
                await seed_product_mode_case_state(self._env)
        except Exception:
            prerequisites["host_local_acp_install_failed_stage"] = str(
                prerequisites.get("host_local_acp_install_stage") or "unknown"
            )
            prerequisites["host_local_acp_launch_status"] = "sandbox_install_failed"
            raise
        prerequisites["host_local_acp_install_stage"] = "sandbox_installed"
        prerequisites["host_local_acp_launch_status"] = "sandbox_installed"
        self._phase = "installed"

    async def install_agent_with_launch_preflight(self: Any) -> Any:
        prerequisites = plan.setdefault("runner_prerequisites", {})
        prerequisites["benchflow_agent_install_started"] = True
        prerequisites["benchflow_run_stage"] = "agent_install_started"
        original_timeout = getattr(self, "_timeout", None)
        requested_timeout = _effective_benchflow_agent_timeout_sec(args)
        prerequisites["benchflow_agent_timeout_requested_sec"] = requested_timeout
        if args.host_local_acp_launch:
            prerequisites["benchflow_agent_timeout_host_local_acp_exec_timeout_sec"] = (
                _effective_local_codex_exec_timeout_sec(args)
            )
            prerequisites[
                "benchflow_agent_timeout_host_local_acp_task_output_quiet_timeout_sec"
            ] = _effective_local_codex_task_output_quiet_timeout_sec(args)
            prerequisites["benchflow_agent_timeout_host_local_acp_margin_sec"] = (
                HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC
            )
        if (
            isinstance(original_timeout, int)
            and not isinstance(original_timeout, bool)
            and requested_timeout > 0
        ):
            prerequisites["benchflow_agent_timeout_original_sec"] = original_timeout
            effective_timeout = max(original_timeout, requested_timeout)
            prerequisites["benchflow_agent_timeout_effective_sec"] = effective_timeout
            prerequisites["benchflow_agent_timeout_overridden"] = (
                effective_timeout != original_timeout
            )
            self._timeout = effective_timeout
        if args.host_local_acp_launch:
            return await install_agent_host_local_acp(self)
        result = await original_install_agent(self)
        if prerequisites.get("codex_acp_runtime_launch_preflight_status") != "passed":
            env = getattr(self, "_env", None)
            if env is None:
                prerequisites["codex_acp_runtime_launch_preflight"] = False
                prerequisites["codex_acp_runtime_launch_preflight_status"] = "failed"
                raise RuntimeError(
                    "codex-acp runtime launch preflight failed: rollout env missing"
                )
            await run_codex_acp_launch_preflight(env)
        return result

    setup_only_public_preflight = bool(
        getattr(args, "setup_only_public_preflight", False)
    )
    controller_user = None
    controller_trace: dict[str, Any] | None = None
    product_mode_case_payload: dict[str, Any] | None = None
    if not setup_only_public_preflight and _is_loopx_product_mode_route(args.route):
        product_mode_case_payload = benchmark_case_loopx_install_payload(
            benchmark_id="skillsbench",
            case_id=args.task_id,
            arm_id=_product_mode_arm_id_for_route(args.route),
            route=args.route,
            max_rounds=args.max_rounds,
            case_loopx_source_path=_loopx_case_source_path_for_container(args),
            goal_start_product_mode=_is_goal_start_product_mode_route(args.route),
        )
    if not setup_only_public_preflight and args.route in {
        CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
        LOOPX_TURN_AGENT_CLI_ROUTE,
    }:
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_user = _build_blind_loop_user(
            route=args.route,
            max_rounds=args.max_rounds,
            trace=controller_trace,
        )
    elif not setup_only_public_preflight and args.route in PRODUCT_MODE_CONTROLLER_ROUTES:
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_user = _build_product_mode_user(
            route=args.route,
            max_rounds=args.max_rounds,
            trace=controller_trace,
            plan=plan,
            case_payload=product_mode_case_payload,
        )
    elif not setup_only_public_preflight and args.route == CODEX_CLI_GOAL_BASELINE_ROUTE:
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_trace["last_decision"] = "host_codex_cli_tui_goal_worker_selected"
    elif (
        not setup_only_public_preflight
        and args.route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
    ):
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        _apply_app_server_goal_round_semantics_to_controller_trace(
            controller_trace,
            plan,
        )
        controller_trace["last_decision"] = "host_app_server_goal_worker_selected"

    original_user_loop = install_benchflow_user_loop_final_verify_recovery(
        Rollout,
        plan=plan,
        trace=controller_trace,
        intermediate_soft_verify_policy=product_mode_soft_verify_policy_for_route(
            args.route,
            args.product_mode_soft_verify_policy,
        ),
    )
    original_verify, original_soft_verify = (
        install_benchflow_verifier_prep_timeout_override(
            Rollout,
            timeout_sec=args.verifier_prep_timeout_sec,
            final_verifier_timeout_sec=args.final_verifier_timeout_sec,
            soft_verifier_timeout_sec=args.soft_verifier_timeout_sec,
            plan=plan,
            trace=controller_trace,
        )
    )

    pre_agent_hooks = (
        []
        if setup_only_public_preflight
        or args.host_local_acp_launch
        or args.require_preinstalled_benchflow_agent_runtime
        else [ensure_codex_acp_runtime_deps]
    )
    if _is_case_loopx_route(args.route) and not args.host_local_acp_launch:
        if not setup_only_public_preflight:
            pre_agent_hooks.append(seed_product_mode_case_state)

    agent_env: dict[str, str] = {}
    if runtime_mounts:
        agent_env["PATH"] = BENCHFLOW_AGENT_RUNTIME_CONTAINER_PATH
        agent_env["CODEX_ACP_RUNTIME_HOME"] = BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET
    benchmark_proxy_env = _benchmark_egress_proxy_env(args)
    if benchmark_proxy_env:
        agent_env.update(benchmark_proxy_env)
        prerequisites = plan.setdefault("runner_prerequisites", {})
        prerequisites["benchmark_egress_proxy_agent_env_injected"] = True
        prerequisites["benchmark_egress_proxy_docker_config_injected"] = True
        prerequisites["benchmark_egress_proxy_docker_config_path_recorded"] = False
        prerequisites["benchmark_egress_proxy_docker_config_raw_proxy_recorded"] = False

    rollout_config_kwargs = {
        "task_path": effective_task_path,
        "environment": args.sandbox,
        "sandbox_user": args.sandbox_user,
        "sandbox_setup_timeout": args.sandbox_setup_timeout,
        "job_name": plan["job_name"],
        "rollout_name": plan["rollout_name"],
        "jobs_dir": Path(plan["jobs_dir"]),
        "user": controller_user,
        "max_user_rounds": args.max_rounds,
        "agent": "codex-acp",
        "model": args.model,
        "agent_idle_timeout": args.agent_idle_timeout,
        "include_task_skills": bool(args.include_task_skills),
        "pre_agent_hooks": pre_agent_hooks,
        "agent_env": agent_env or None,
        "skip_agent_install": bool(args.require_preinstalled_benchflow_agent_runtime),
    }
    config = RolloutConfig(
        **_filter_kwargs_for_signature(RolloutConfig, rollout_config_kwargs)
    )
    result_path: Path | None = None
    prerequisites = plan.setdefault("runner_prerequisites", {})
    requested_build_stall_timeout_sec = _requested_build_stall_timeout_sec(args)
    build_stall_timeout_sec = _effective_build_stall_timeout_sec(args)
    prerequisites["benchflow_setup_stall_timeout_enabled"] = (
        build_stall_timeout_sec > 0
    )
    prerequisites["benchflow_setup_stall_timeout_requested_sec"] = (
        requested_build_stall_timeout_sec
    )
    prerequisites["benchflow_setup_stall_timeout_sec"] = build_stall_timeout_sec
    prerequisites["benchflow_setup_stall_raw_logs_read"] = False
    prerequisites["benchflow_run_stage"] = "before_benchflow_run"

    def agent_lifecycle_started() -> bool:
        if prerequisites.get("benchflow_agent_install_started") is True:
            return True
        launch_status = str(
            prerequisites.get("codex_acp_runtime_launch_preflight_status") or ""
        )
        if launch_status not in {"", "pending", "not_requested"}:
            return True
        host_status = str(prerequisites.get("host_local_acp_launch_status") or "")
        if host_status not in {"", "pending", "not_requested"}:
            return True
        if isinstance(controller_trace, dict):
            return bool(
                controller_trace.get("case_goal_state_initialized_before_agent")
                or controller_trace.get("case_goal_state_init_rc") is not None
                or int(controller_trace.get("initial_prompt_count") or 0) > 0
                or int(controller_trace.get("heartbeat_count") or 0) > 0
                or int(controller_trace.get("controller_action_decisions") or 0) > 0
                or int(controller_trace.get("private_trajectory_round_count") or 0) > 0
                or int(controller_trace.get("loopx_cli_call_count") or 0) > 0
            )
        return False

    async def run_benchflow_with_setup_stall_watchdog() -> None:
        prerequisites["benchflow_run_stage"] = "benchflow_run_started"
        task = asyncio.create_task(benchflow_run(config))
        if build_stall_timeout_sec <= 0:
            await task
            prerequisites["benchflow_run_stage"] = "benchflow_run_completed"
            return
        done, _pending = await asyncio.wait(
            {task},
            timeout=build_stall_timeout_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if done:
            await task
            prerequisites["benchflow_run_stage"] = "benchflow_run_completed"
            return
        if agent_lifecycle_started():
            prerequisites["benchflow_run_stage"] = (
                "benchflow_run_continues_after_agent_lifecycle_started"
            )
            await task
            prerequisites["benchflow_run_stage"] = "benchflow_run_completed"
            return
        prerequisites["benchflow_setup_stall_timeout_triggered"] = True
        prerequisites["benchflow_setup_stall_before_agent_lifecycle"] = True
        prerequisites["benchflow_run_stage"] = "build_or_setup_stall_before_agent"
        prerequisites["benchflow_setup_stall_task_cancel_requested"] = True
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=5)
        except asyncio.CancelledError:
            prerequisites["benchflow_setup_stall_task_cancel_acknowledged"] = True
        except asyncio.TimeoutError:
            prerequisites["benchflow_setup_stall_task_cancel_timeout"] = True
        cleanup_benchflow_setup_stall_children(plan)
        raise asyncio.TimeoutError(
            "skillsbench docker compose build/setup stall timeout before agent lifecycle"
        )

    Rollout.install_agent = install_agent_with_launch_preflight
    if container_mounts and rollout_planes_class is not None:
        rollout_planes_class.create_environment = create_environment_with_runtime_mount
    if container_mounts and original_rollout_create_environment is not _MISSING:
        benchflow_rollout_module._create_environment = (
            create_environment_function_with_runtime_mount
        )
    if container_mounts and original_setup_create_environment is not _MISSING:
        benchflow_sandbox_setup_module._create_environment = (
            create_environment_function_with_runtime_mount
        )
    if args.host_local_acp_launch:
        benchflow_acp_runtime.connect_acp = connect_host_local_acp
        if original_rollout_connect_acp is not _MISSING:
            benchflow_rollout_module.connect_acp = connect_host_local_acp
        if (
            benchflow_rollout_planes_module is not None
            and original_rollout_planes_connect_acp is not _MISSING
        ):
            benchflow_rollout_planes_module.connect_acp = connect_host_local_acp
        if (
            rollout_planes_class is not None
            and original_rollout_planes_class_connect_acp is not None
        ):
            rollout_planes_class.connect_acp = connect_host_local_acp_method
    setup_only_result: dict[str, Any] | None = None
    try:
        if setup_only_public_preflight:
            setup_only_result = await run_setup_only_public_preflight(
                rollout_type=Rollout,
                config=config,
                task_staging=plan.get("task_staging"),
                setup_preflight=plan.get("task_setup_preflight"),
                stage_timeout_sec=float(args.sandbox_setup_timeout),
            )
            plan["setup_only_public_preflight_result"] = setup_only_result
            prerequisites["benchflow_run_stage"] = str(
                setup_only_result.get("stage") or "setup_only_preflight_complete"
            )
        else:
            await run_benchflow_with_setup_stall_watchdog()
            result_path = discover_benchflow_result_path(plan)
            if result_path.exists():
                _merge_final_result_round_reward(controller_trace, result_path)
    finally:
        Rollout.install_agent = original_install_agent
        Rollout._run_user_loop = original_user_loop
        Rollout.verify = original_verify
        Rollout.soft_verify = original_soft_verify
        if (
            container_mounts
            and rollout_planes_class is not None
            and original_create_environment is not None
        ):
            rollout_planes_class.create_environment = original_create_environment
        if original_rollout_create_environment is not _MISSING:
            benchflow_rollout_module._create_environment = (
                original_rollout_create_environment
            )
        if original_setup_create_environment is not _MISSING:
            benchflow_sandbox_setup_module._create_environment = (
                original_setup_create_environment
            )
        benchflow_acp_runtime.connect_acp = original_runtime_connect_acp
        if original_rollout_connect_acp is not _MISSING:
            benchflow_rollout_module.connect_acp = original_rollout_connect_acp
        if (
            benchflow_rollout_planes_module is not None
            and original_rollout_planes_connect_acp is not _MISSING
        ):
            benchflow_rollout_planes_module.connect_acp = (
                original_rollout_planes_connect_acp
            )
        if (
            rollout_planes_class is not None
            and original_rollout_planes_class_connect_acp is not None
        ):
            rollout_planes_class.connect_acp = original_rollout_planes_class_connect_acp
        _merge_acp_trajectory_summary(plan, controller_trace)
        _merge_app_server_goal_worker_trace_summary(plan, controller_trace)
        _merge_host_local_acp_relay_trace_summary(plan, controller_trace)
        _write_controller_trace(plan, controller_trace)
    if setup_only_result is not None:
        return setup_only_result
    if result_path is None:
        result_path = discover_benchflow_result_path(plan)
    if not result_path.exists():
        raise FileNotFoundError(f"BenchFlow result.json not found: {result_path}")
    return result_path


def reduce_result(
    args: argparse.Namespace,
    result_path: Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark import (
        build_skillsbench_benchflow_result_benchmark_run,
    )
    from loopx.status import (
        build_skillsbench_post_run_debug_gate,
        compact_benchmark_run,
    )

    controller_trace = _read_controller_trace(plan)
    _merge_acp_trajectory_summary(plan, controller_trace)
    _merge_app_server_goal_worker_trace_summary(plan, controller_trace)
    _merge_host_local_acp_relay_trace_summary(plan, controller_trace)
    _write_controller_trace(plan, controller_trace)

    benchmark_run = build_skillsbench_benchflow_result_benchmark_run(
        result_path,
        route=args.route,
        dataset=args.dataset,
        agent="codex",
        model=args.model,
        runner_warning_labels=collect_runner_warning_labels(plan),
        controller_trace=controller_trace,
    )
    runner_prerequisites = _public_runner_prerequisites(
        plan.get("runner_prerequisites")
    )
    if runner_prerequisites:
        benchmark_run["runner_prerequisites"] = runner_prerequisites
    task_staging = _effective_public_task_staging(plan)
    if task_staging:
        benchmark_run["task_staging"] = task_staging
    compact = compact_benchmark_run(benchmark_run)
    if compact is None:
        raise RuntimeError("SkillsBench treatment reducer produced non-compact run")
    sync_skillsbench_loopx_turn_trace_into_compact(compact, controller_trace)
    if runner_prerequisites:
        compact["runner_prerequisites"] = runner_prerequisites
        _sync_relay_closeout_counts_into_compact(compact, runner_prerequisites)
        _apply_host_local_acp_prereq_failure_attribution(
            compact,
            runner_prerequisites,
        )
    _apply_native_goal_worker_finish_guard_attribution(compact)
    _apply_codex_cli_goal_countability_guard_attribution(compact)
    prereq_failure = _runner_prerequisite_failure_attribution(
        plan.get("runner_prerequisites")
    )
    if compact.get("official_score_status") == "missing":
        has_agent_message_only_evidence = (
            _apply_agent_message_only_no_tool_calls_attribution(compact)
        )
    else:
        has_agent_message_only_evidence = False
    if compact.get("official_score_status") == "missing":
        current_attribution = str(compact.get("score_failure_attribution") or "")
        if (
            prereq_failure is not None
            and not has_agent_message_only_evidence
            and current_attribution in {"", "none", "skillsbench_runner_error"}
        ):
            _exception_type, score_failure_attribution, labels = prereq_failure
            compact["score_failure_attribution"] = score_failure_attribution
            compact.setdefault("first_blocker", score_failure_attribution)
            existing_labels = [
                label
                for label in compact.get("failure_attribution_labels", [])
                if isinstance(label, str)
            ]
            for label in labels:
                if label not in existing_labels:
                    existing_labels.append(label)
            compact["failure_attribution_labels"] = existing_labels
        elif (
            not has_agent_message_only_evidence
            and runner_prerequisites.get("agent_execution_mode") == "host_local_acp"
            and runner_prerequisites.get("host_local_acp_launch_status")
            == "sandbox_installed"
        ):
            counters = compact.get("interaction_counters")
            if isinstance(counters, dict):
                event_count = counters.get("private_trajectory_event_count")
                tool_count = counters.get("private_trajectory_tool_call_count")
                summary_present = counters.get("private_trajectory_summary_present")
                if (
                    summary_present is True
                    and event_count == 0
                    and tool_count == 0
                ):
                    label = "skillsbench_host_local_acp_empty_trajectory_after_install"
                    compact["score_failure_attribution"] = label
                    compact.setdefault("first_blocker", label)
                    existing_labels = [
                        item
                        for item in compact.get("failure_attribution_labels", [])
                        if isinstance(item, str)
                    ]
                    for item in (label, "skillsbench_runner_setup_error"):
                        if item not in existing_labels:
                            existing_labels.append(item)
                    compact["failure_attribution_labels"] = existing_labels
    verifier_bootstrap.apply_skillsbench_verifier_bootstrap_missing_score_attribution(
        compact,
        task_staging=task_staging,
        setup_preflight=_public_task_setup_preflight(
            plan.get("task_setup_preflight")
        ),
    )
    if task_staging:
        compact["task_staging"] = task_staging
    discovery = plan.get("result_discovery")
    if isinstance(discovery, dict):
        compact["result_discovery"] = {
            key: value
            for key, value in discovery.items()
            if key
            in {
                "schema_version",
                "status",
                "selection_policy",
                "tie_breaker",
                "candidate_count",
                "matched_candidate_count",
                "top_score_candidate_count",
                "selected_relative_to_job",
                "selection_reasons",
                "raw_logs_read",
                "raw_task_text_read",
                "raw_trajectory_read",
            }
        }
    diagnostic = build_compose_setup_diagnostic(compact, plan)
    if diagnostic.get("status") != "not_applicable":
        compact["compose_setup_diagnostic"] = diagnostic
        apply_skillsbench_pre_agent_setup_diagnostic_attribution(compact)
    runner_output_capture = _public_runner_output_capture(plan)
    if runner_output_capture:
        compact["runner_output_capture"] = runner_output_capture
    runner_config = _public_runner_config(plan)
    if runner_config:
        compact["runner_config"] = runner_config
    app_server_observability = _app_server_goal_worker_observability(
        plan,
        controller_trace,
    )
    if app_server_observability:
        compact["app_server_goal_worker_observability"] = app_server_observability
    goal_start_control_score = _build_goal_start_product_mode_control_score(
        compact,
        plan,
    )
    if goal_start_control_score:
        compact["goal_start_product_mode_control_score"] = goal_start_control_score
    compact["case_event_timeline"] = _build_case_event_timeline(compact, plan)
    post_run_debug_gate = build_skillsbench_post_run_debug_gate(compact)
    compact["post_run_debug_gate"] = post_run_debug_gate
    solution_quality = post_run_debug_gate.get("solution_quality")
    if isinstance(solution_quality, dict):
        compact["solution_quality_signals"] = solution_quality
    return compact


def reduce_official_result_after_runner_exception(
    args: argparse.Namespace,
    plan: dict[str, Any],
    exc: BaseException,
) -> dict[str, Any] | None:
    """Recover an official result that BenchFlow wrote before raising.

    BenchFlow can raise for the rollout while still leaving a valid
    ``result.json``/``timing.json`` behind. In that case the public benchmark
    truth is the official result, not a synthetic "missing result" closeout.
    This path still reads only the official compact result artifacts.
    """

    try:
        result_path = discover_benchflow_result_path(plan)
    except Exception:
        return None
    if not result_path.exists():
        return None

    compact = reduce_result(args, result_path, plan)
    _write_public_runner_config(plan)
    _write_public_runner_prerequisites(plan)
    compact["runner_return_status"] = (
        "official_result_recovered_after_runner_exception"
    )
    compact["result_recovery"] = {
        "schema_version": "skillsbench_result_recovery_v0",
        "status": "official_result_recovered_after_runner_exception",
        "exception_type": type(exc).__name__,
        "official_result_json_materialized": True,
        "raw_exception_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
    }
    compact_path = Path(plan["compact_benchmark_run_json"])
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text(
        json.dumps(compact, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    ledger_update = update_ledger(args, compact, compact_path=compact_path)
    history_append = append_history(args, compact_path)
    return {
        "ok": True,
        "plan_only": False,
        "recovered_after_runner_exception": True,
        "runner_exception_type": type(exc).__name__,
        "result_json": str(result_path),
        "compact_benchmark_run_json": str(compact_path),
        "result_discovery": plan.get("result_discovery"),
        "official_task_score": compact.get("official_task_score"),
        "score_failure_attribution": compact.get("score_failure_attribution"),
        "ledger_update": ledger_update,
        "history_append": history_append,
    }


def _nonbool_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _nonbool_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _runner_failure_trace_score_attribution(
    *,
    reward: float,
    passed: bool,
) -> str:
    if passed:
        return "none"
    if reward == 0:
        return "official_score_zero_case_failure"
    return "official_verifier_solution_failure"


def _product_mode_lifecycle_contract_from_controller_counters(
    counters: dict[str, Any],
) -> dict[str, Any]:
    required = bool(
        counters.get("product_mode") is True
        or counters.get("goal_start_product_mode") is True
    )
    driver_read_count = _nonbool_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_loopx_state_read_count")
    )
    driver_write_count = _nonbool_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_loopx_state_write_count")
    )
    driver_checkpoint_count = _nonbool_int(
        counters.get("remote_command_file_bridge_driver_lifecycle_checkpoint_count")
    )
    agent_read_count = _nonbool_int(
        counters.get("remote_command_file_bridge_agent_loopx_state_read_count")
    )
    agent_write_count = _nonbool_int(
        counters.get("remote_command_file_bridge_agent_loopx_state_write_count")
    )
    todo_closeout_count = _nonbool_int(
        counters.get("remote_command_file_bridge_agent_todo_closeout_count")
    )
    refresh_state_count = _nonbool_int(
        counters.get("remote_command_file_bridge_agent_refresh_state_count")
    )
    quota_spend_count = _nonbool_int(
        counters.get("remote_command_file_bridge_agent_quota_spend_slot_count")
    )
    closeout_satisfied = bool(
        todo_closeout_count > 0
        and refresh_state_count > 0
        and quota_spend_count > 0
    )
    quota_spend_missing_after_repeated_complete = bool(
        todo_closeout_count > 1
        and refresh_state_count > 0
        and quota_spend_count <= 0
    )
    operation_trace_status = str(
        counters.get("remote_command_file_bridge_agent_operation_trace_status")
        or ""
    )[:120]
    operation_trace_satisfied = bool(
        counters.get("remote_command_file_bridge_agent_operation_trace_satisfied")
        is True
        or _nonbool_int(
            counters.get("remote_command_file_bridge_agent_task_facing_operation_count")
        )
        > 0
    )
    operation_trace_missing = bool(required and not operation_trace_satisfied)
    state_read_count = max(driver_read_count, agent_read_count)
    state_write_count = max(driver_write_count, agent_write_count)
    orchestrated_driver_satisfied = bool(
        driver_read_count > 0 and driver_write_count > 0
    )
    satisfied = bool(
        not required
        or (
            not operation_trace_missing
            and state_read_count > 0
            and state_write_count > 0
            and closeout_satisfied
        )
    )
    missing_reason = ""
    if required and not satisfied:
        if operation_trace_missing:
            missing_reason = "remote_command_file_bridge_agent_operation_trace_missing"
        elif state_read_count <= 0 or state_write_count <= 0:
            missing_reason = "missing_case_local_loopx_state_read_or_write"
        elif not closeout_satisfied:
            if quota_spend_missing_after_repeated_complete:
                missing_reason = "quota_spend_missing_after_repeated_todo_closeout"
            else:
                missing_reason = "missing_case_local_loopx_closeout"

    contract: dict[str, Any] = {
        "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
        "required": required,
        "satisfied": satisfied,
        "countable_treatment": satisfied,
        "state_read_count": state_read_count,
        "state_write_count": state_write_count,
        "checkpoint_required": required,
        "checkpoint_count": driver_checkpoint_count,
        "closeout_required": required,
        "closeout_satisfied": closeout_satisfied,
        "quota_spend_missing_after_repeated_complete": (
            quota_spend_missing_after_repeated_complete
        ),
        "agent_operation_trace_required": required,
        "agent_operation_trace_satisfied": operation_trace_satisfied,
        "agent_operation_trace_status": operation_trace_status,
        "agent_operation_trace_missing": operation_trace_missing,
        "orchestrated_driver_lifecycle_satisfied": orchestrated_driver_satisfied,
        "orchestrated_driver_counts_as_product_mode": orchestrated_driver_satisfied,
        "agent_bridge_state_read_count": agent_read_count,
        "agent_bridge_state_write_count": agent_write_count,
        "agent_bridge_todo_closeout_count": todo_closeout_count,
        "agent_bridge_refresh_state_count": refresh_state_count,
        "agent_bridge_quota_spend_slot_count": quota_spend_count,
        "driver_lifecycle_state_read_count": driver_read_count,
        "driver_lifecycle_state_write_count": driver_write_count,
        "checkpoint_round": _nonbool_int(
            counters.get("product_mode_lifecycle_checkpoint_round")
        ),
        "missing_reason": missing_reason,
    }
    execution_style = counters.get(
        "remote_command_file_bridge_driver_lifecycle_execution_style"
    )
    if isinstance(execution_style, str) and execution_style:
        contract["execution_style"] = execution_style
    return contract


def _recover_runner_failure_score_from_controller_trace(
    compact: dict[str, Any],
    plan: dict[str, Any],
) -> bool:
    controller_trace = _read_controller_trace(plan)
    if not isinstance(controller_trace, dict):
        return False

    from loopx.benchmark_adapters.skillsbench import (
        _round_reward_trace_stats,
        _skillsbench_controller_trace_counters,
    )
    from loopx.benchmark_core import (
        BenchmarkFailureClass,
        build_benchmark_attempt_accounting,
        canonical_lifecycle,
    )

    counters = _skillsbench_controller_trace_counters(controller_trace)
    records = counters.get("round_rewards")
    if not isinstance(records, list):
        return False
    stats = _round_reward_trace_stats(records)
    final_reward = _nonbool_float(stats.get("final_round_reward"))
    if final_reward is None:
        return False
    passed = stats.get("final_round_passed") is True or final_reward >= 1.0
    attribution = _runner_failure_trace_score_attribution(
        reward=final_reward,
        passed=passed,
    )
    round_reward_trace: dict[str, Any] = {
        "schema_version": "benchmark_round_reward_trace_v0",
        "source": "loopx_controller_trace",
        "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
        "records": records,
        "first_success_round": counters.get("first_success_round"),
        "success_observed": counters.get("official_success_observed") is True,
        "max_rounds_budget": counters.get("max_rounds_budget", 0),
        "official_feedback_returned_to_agent": (
            counters.get("official_feedback_forwarded") is True
        ),
        "official_feedback_blinded": (
            _nonbool_int(counters.get("official_feedback_blinded_count")) > 0
        ),
        "reward_feedback_forwarded": counters.get("official_feedback_forwarded")
        is True,
        "agent_declared_done": counters.get("agent_declared_done") is True,
        "declared_done_requires_no_remaining_goals": (
            counters.get("declared_done_requires_no_remaining_goals") is True
        ),
        "agent_declared_no_remaining_goals": (
            counters.get("agent_declared_no_remaining_goals") is True
        ),
        "product_mode_no_open_todo_below_passing_reward_stop": (
            counters.get("product_mode_no_open_todo_below_passing_reward_stop")
            is True
        ),
        "product_mode_typed_repair_required": (
            counters.get("product_mode_typed_repair_required") is True
        ),
        "product_mode_typed_repair_todo_identity_observed": (
            counters.get("product_mode_typed_repair_todo_identity_observed") is True
        ),
        "product_mode_typed_repair_task_or_validation_delta": (
            counters.get("product_mode_typed_repair_task_or_validation_delta") is True
        ),
        "product_mode_typed_repair_delta_observed": (
            counters.get("product_mode_typed_repair_delta_observed") is True
        ),
        "product_mode_typed_repair_terminal": (
            counters.get("product_mode_typed_repair_terminal") is True
        ),
        "product_mode_typed_repair_terminal_receipt_consistent": (
            counters.get("product_mode_typed_repair_terminal_receipt_consistent")
            is True
        ),
        "official_score_policy": (
            "final_observed_controller_trace_reward_after_runner_interruption"
        ),
        "official_score_recovered_from_controller_trace": True,
        "official_score_recovered_round": stats.get("final_round"),
    }
    for source_key in (
        "product_mode_no_open_todo_below_passing_reward_streak",
        "product_mode_no_open_todo_below_passing_reward_streak_threshold",
        "product_mode_no_open_todo_below_passing_reward_round",
        "product_mode_no_open_todo_below_passing_reward_stop_round",
        "product_mode_no_open_todo_below_passing_reward_open_todo_count_public",
        "product_mode_typed_repair_trigger_round",
        "product_mode_typed_repair_round_entered",
        "product_mode_typed_repair_round_entered_count",
        "product_mode_typed_repair_resolved_round",
        "product_mode_typed_repair_task_facing_success_delta",
        "product_mode_typed_repair_terminal_round",
        "product_mode_typed_repair_open_todo_count_public",
    ):
        value = counters.get(source_key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            round_reward_trace[source_key] = value
    score_status = counters.get(
        "product_mode_no_open_todo_below_passing_reward_score_status"
    )
    if isinstance(score_status, str) and score_status:
        round_reward_trace[
            "product_mode_no_open_todo_below_passing_reward_score_status"
        ] = score_status
    no_open_todo_score = _nonbool_float(
        counters.get("product_mode_no_open_todo_below_passing_reward_score")
    )
    if no_open_todo_score is not None:
        round_reward_trace[
            "product_mode_no_open_todo_below_passing_reward_score"
        ] = no_open_todo_score
    for source_key in (
        "product_mode_typed_repair_policy_id",
        "product_mode_typed_repair_terminal_reason",
    ):
        value = counters.get(source_key)
        if isinstance(value, str) and value:
            round_reward_trace[source_key] = value
    round_reward_trace.update(stats)

    interaction_counters = compact.get("interaction_counters")
    if not isinstance(interaction_counters, dict):
        interaction_counters = {
            "schema_version": "skillsbench_interaction_counters_v0",
        }
    interaction_counters.update(counters)
    for raw_key, compact_key in (
        ("initial_prompt_count", "controller_initial_prompt_count"),
        ("followup_prompt_count", "controller_followup_prompt_count"),
        ("stop_decision_count", "controller_stop_decision_count"),
        ("max_rounds_budget", "controller_max_rounds_budget"),
    ):
        value = counters.get(raw_key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            interaction_counters[compact_key] = value
    if counters.get("official_success_observed") is True:
        interaction_counters["controller_official_success_observed"] = True
    compact["interaction_counters"] = interaction_counters
    compact["product_mode"] = bool(
        compact.get("product_mode") is True or counters.get("product_mode") is True
    )
    if counters.get("goal_start_product_mode") is True:
        compact["goal_start_product_mode"] = True
    compact["round_reward_trace"] = round_reward_trace
    compact["runner_return_status"] = (
        "interrupted_after_controller_reward_observation"
    )
    compact["official_score_status"] = "completed"
    compact["official_score"] = final_reward
    compact["official_task_score"] = {
        "kind": "skillsbench_verifier_reward_recovered_from_controller_trace",
        "value": final_reward,
        "passed": passed,
    }
    compact["official_score_source"] = (
        "loopx_controller_trace_every_round_verifier_reward"
    )
    compact["score_failure_attribution"] = attribution
    compact["first_blocker"] = attribution
    compact["repeat_blocked_by"] = attribution
    stale_missing_score_labels = {
        "skillsbench_runner_interrupted_before_official_result",
        "skillsbench_result_json_missing_after_runner_exit",
        "official_score_missing",
        "skillsbench_runner_failed_before_agent_install",
        "skillsbench_runner_setup_error",
    }
    labels = [
        label
        for label in compact.get("failure_attribution_labels", [])
        if isinstance(label, str) and label and label not in stale_missing_score_labels
    ]
    for label in (
        attribution,
        "skillsbench_runner_interrupted_after_controller_reward_observation",
    ):
        if label != "none" and label not in labels:
            labels.append(label)
    compact["failure_attribution_labels"] = labels
    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["failure_class"] = (
            "skillsbench_runner_interrupted_after_controller_reward_observation"
        )
        runner_failure["score_recovered_from_controller_trace"] = True
    compact["product_mode_lifecycle_contract"] = (
        _product_mode_lifecycle_contract_from_controller_counters(counters)
    )
    compact["attempt_accounting"] = build_benchmark_attempt_accounting(
        lifecycle=canonical_lifecycle(
            process_started=True,
            runner_accepted_args=True,
            job_root_materialized=True,
            trial_started=True,
            worker_started=True,
            result_written=True,
            verifier_scored=True,
        ),
        failure_label=attribution,
        failure_class=(
            BenchmarkFailureClass.NONE
            if passed
            else BenchmarkFailureClass.SOLVER_FAILED
        ),
        official_score_attempted=True,
    )
    progress = compact.get("progress")
    if isinstance(progress, dict):
        progress.update(
            {
                "n_completed_trials": 1,
                "n_errored_trials": 0,
                "n_running_trials": 0,
                "n_pending_trials": 0,
            }
        )
    validation = compact.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    validation.update(
        {
            "official_verifier_status": "completed",
            "official_verifier_validation_present": True,
            "official_case_success": passed,
            "controller_trace_read": True,
            "controller_trace_score_recovered": True,
            "runner_failure_after_controller_reward_observation": True,
        }
    )
    compact["validation"] = validation
    return True


def _read_verifier_reward_artifact(path: Path) -> float | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not text:
        return None
    first_token = text.split()[0]
    try:
        value = float(first_token)
    except ValueError:
        return None
    if value != value:
        return None
    return value


def _read_verifier_ctrf_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    compact: dict[str, Any] = {
        "schema_version": "skillsbench_verifier_ctrf_summary_v0",
        "raw_output_recorded": False,
    }
    for field in (
        "tests",
        "passed",
        "failed",
        "pending",
        "skipped",
        "other",
        "suites",
    ):
        value = summary.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            compact[field] = value
    for field in ("start", "stop"):
        value = summary.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            compact[field] = float(value)
    return compact


def _discover_verifier_reward_artifact(plan: dict[str, Any]) -> dict[str, Any] | None:
    result_path = Path(str(plan.get("result_json") or "")).expanduser()
    jobs_dir = Path(str(plan.get("jobs_dir") or "")).expanduser()
    job_name = str(plan.get("job_name") or "")
    job_root = jobs_dir / job_name
    rollout_name = str(plan.get("rollout_name") or "")
    task_id = str(plan.get("task_id") or "")
    expected = result_path.parent / "verifier" / "reward.txt"
    candidates: list[Path] = []
    if expected.exists():
        candidates.append(expected)
    if job_root.exists():
        for path in job_root.rglob("verifier/reward.txt"):
            if path.is_file() and path not in candidates:
                candidates.append(path)
    ranked: list[tuple[int, float, Path, list[str]]] = []
    for candidate in candidates:
        score = 0
        reasons: list[str] = []
        rollout_dir = candidate.parent.parent
        if candidate == expected:
            score += 100
            reasons.append("planned_rollout_verifier_reward_path")
        if rollout_name and rollout_dir.name == rollout_name:
            score += 80
            reasons.append("parent_matches_requested_rollout")
        elif task_id and rollout_dir.name.startswith(f"{task_id}__"):
            score += 20
            reasons.append("parent_matches_task_rollout_prefix")
        reward = _read_verifier_reward_artifact(candidate)
        if reward is not None:
            score += 50
            reasons.append("reward_txt_parseable")
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            mtime = 0.0
        if score > 0:
            ranked.append((score, mtime, candidate, reasons))
    discovery: dict[str, Any] = {
        "schema_version": "skillsbench_verifier_reward_artifact_discovery_v0",
        "selection_policy": "planned_reward_path_then_job_root_scan",
        "candidate_count": len(candidates),
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "raw_verifier_output_read": False,
    }
    if not ranked:
        discovery["status"] = "missing"
        plan["verifier_reward_artifact_discovery"] = discovery
        return None
    ranked.sort(key=lambda item: (item[0], item[1], str(item[2])), reverse=True)
    top_score, _mtime, selected, reasons = ranked[0]
    reward = _read_verifier_reward_artifact(selected)
    if reward is None:
        discovery["status"] = "unparseable"
        plan["verifier_reward_artifact_discovery"] = discovery
        return None
    tied_top_count = sum(1 for score, _mtime, _path, _reasons in ranked if score == top_score)
    discovery.update(
        {
            "status": "found",
            "matched_candidate_count": len(ranked),
            "top_score_candidate_count": tied_top_count,
            "selected_relative_to_job": _safe_relative_to(selected, job_root),
            "selection_reasons": reasons,
            "reward_present": True,
        }
    )
    ctrf_summary = _read_verifier_ctrf_summary(selected.parent / "ctrf.json")
    if ctrf_summary:
        discovery["ctrf_summary_present"] = True
    plan["verifier_reward_artifact_discovery"] = discovery
    return {
        "reward_path": selected,
        "reward": reward,
        "passed": reward >= 1.0,
        "discovery": discovery,
        "ctrf_summary": ctrf_summary,
    }


def _recover_runner_failure_score_from_verifier_artifact(
    compact: dict[str, Any],
    plan: dict[str, Any],
) -> bool:
    artifact = _discover_verifier_reward_artifact(plan)
    if artifact is None:
        return False

    from loopx.benchmark_core import (
        BenchmarkFailureClass,
        build_benchmark_attempt_accounting,
        canonical_lifecycle,
    )

    reward = float(artifact["reward"])
    passed = bool(artifact["passed"])
    attribution = _runner_failure_trace_score_attribution(
        reward=reward,
        passed=passed,
    )
    compact["runner_return_status"] = "interrupted_after_verifier_reward_artifact"
    compact["official_score_status"] = "completed"
    compact["official_score"] = reward
    compact["official_task_score"] = {
        "kind": "skillsbench_verifier_reward_recovered_from_verifier_artifact",
        "value": reward,
        "passed": passed,
    }
    compact["official_score_source"] = (
        "official_skillsbench_rollout_verifier_reward_txt_after_runner_interruption"
    )
    compact["score_failure_attribution"] = attribution
    compact["first_blocker"] = attribution
    compact["repeat_blocked_by"] = attribution
    compact["verifier_reward_artifact_recovery"] = {
        "schema_version": "skillsbench_verifier_reward_artifact_recovery_v0",
        "status": "official_score_recovered_from_verifier_reward_artifact",
        "official_result_json_materialized": False,
        "reward_present": True,
        "reward": reward,
        "passed": passed,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "raw_verifier_output_read": False,
    }
    discovery = artifact.get("discovery")
    if isinstance(discovery, dict):
        compact["verifier_reward_artifact_discovery"] = discovery
    ctrf_summary = artifact.get("ctrf_summary")
    if isinstance(ctrf_summary, dict):
        compact["verifier_ctrf_summary"] = ctrf_summary
    stale_missing_score_labels = {
        "skillsbench_runner_interrupted_before_official_result",
        "skillsbench_result_json_missing_after_runner_exit",
        "official_score_missing",
        "skillsbench_runner_failed_before_agent_install",
        "skillsbench_runner_setup_error",
    }
    labels = [
        label
        for label in compact.get("failure_attribution_labels", [])
        if isinstance(label, str) and label and label not in stale_missing_score_labels
    ]
    for label in (
        attribution,
        "skillsbench_runner_interrupted_after_verifier_reward_artifact",
    ):
        if label != "none" and label not in labels:
            labels.append(label)
    compact["failure_attribution_labels"] = labels
    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["failure_class"] = (
            "skillsbench_runner_interrupted_after_verifier_reward_artifact"
        )
        runner_failure["score_recovered_from_verifier_artifact"] = True
    compact["attempt_accounting"] = build_benchmark_attempt_accounting(
        lifecycle=canonical_lifecycle(
            process_started=True,
            runner_accepted_args=True,
            job_root_materialized=True,
            trial_started=True,
            worker_started=True,
            result_written=False,
            verifier_scored=True,
        ),
        failure_label=attribution,
        failure_class=(
            BenchmarkFailureClass.NONE
            if passed
            else BenchmarkFailureClass.SOLVER_FAILED
        ),
        official_score_attempted=True,
    )
    progress = compact.get("progress")
    if isinstance(progress, dict):
        progress.update(
            {
                "n_completed_trials": 1,
                "n_errored_trials": 0,
                "n_running_trials": 0,
                "n_pending_trials": 0,
            }
        )
    validation = compact.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    validation.update(
        {
            "official_verifier_status": "passed" if passed else "completed",
            "official_verifier_validation_present": True,
            "official_case_success": passed,
            "verifier_reward_artifact_recovered": True,
            "official_result_json_materialized": False,
            "raw_verifier_output_read": False,
        }
    )
    compact["validation"] = validation
    return True


def build_runner_failure_compact(
    args: argparse.Namespace,
    plan: dict[str, Any],
    exc: BaseException,
) -> dict[str, Any]:
    """Build a public-safe compact closeout when BenchFlow exits before result.json."""

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark import build_skillsbench_benchmark_run
    from loopx.benchmark_adapters.skillsbench import (
        skillsbench_runner_error_attribution,
        skillsbench_runner_error_fingerprint,
    )
    from loopx.status import (
        build_skillsbench_post_run_debug_gate,
        compact_benchmark_run,
    )

    plan.setdefault("runner_prerequisites", {})
    _ensure_runner_interruption_prerequisites(plan, exc)
    _ensure_setup_stall_timeout_prerequisites(
        args,
        plan,
        exc,
        cleanup_if_missing=True,
    )
    controller_trace = _read_controller_trace(plan)
    _merge_app_server_goal_worker_trace_summary(plan, controller_trace)
    _merge_host_local_acp_relay_trace_summary(plan, controller_trace)
    _write_controller_trace(plan, controller_trace)
    _write_public_runner_config(plan)
    _write_public_runner_prerequisites(plan)

    exception_type, attribution, labels = skillsbench_runner_error_attribution(
        str(exc)
    )
    runner_prerequisites = _public_runner_prerequisites(
        plan.get("runner_prerequisites")
    )
    prerequisite_attribution = _runner_prerequisite_failure_attribution(
        runner_prerequisites
    )
    if prerequisite_attribution and exception_type == "skillsbench_runner_error":
        exception_type, attribution, labels = prerequisite_attribution
    compact = build_skillsbench_benchmark_run(
        route=args.route,
        dataset=args.dataset,
        task_id=args.task_id,
        agent="codex",
        model=args.model,
    )
    compact.update(
        {
            "source_runner": "official_skillsbench_benchflow_launch_failure",
            "job_name": str(plan.get("job_name") or compact.get("job_name") or ""),
            "real_run": True,
            "runner_return_status": "failed_before_official_result",
            "official_score_status": "missing",
            "official_score": None,
            "official_task_score": {
                "kind": "skillsbench_verifier_reward_missing",
                "value": None,
                "passed": False,
            },
            "score_failure_attribution": attribution,
            "failure_attribution_labels": labels,
            "first_blocker": exception_type,
            "repeat_blocked_by": exception_type,
            "trace_publicness": "compact_failure_only_no_raw_task_log_or_trajectory",
            "runner_failure": {
                "schema_version": "skillsbench_runner_failure_v0",
                "exception_type": type(exc).__name__,
                "failure_class": exception_type,
                "raw_error_recorded": False,
                "raw_logs_read": False,
                "raw_task_text_read": False,
                "raw_trajectory_read": False,
            },
            "progress": {
                "n_total_trials": 1,
                "n_completed_trials": 0,
                "n_errored_trials": 1,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
            },
            "redaction": {
                "secret_values_recorded": False,
                "raw_sessions_recorded": False,
                "host_paths_recorded": False,
                "raw_prompts_recorded": False,
                "raw_solutions_recorded": False,
                "raw_logs_recorded": False,
            },
            "stop_conditions": [
                "classify_compact_runner_failure_before_rerun",
                "do_not_read_raw_task_prompt_solution_log_or_trajectory",
                "do_not_upload_or_submit_leaderboard",
                "do_not_record_secrets_or_raw_sessions",
            ],
        }
    )
    if runner_prerequisites:
        compact["runner_prerequisites"] = runner_prerequisites
        _sync_relay_closeout_counts_into_compact(compact, runner_prerequisites)
    task_setup_preflight = _public_task_setup_preflight(
        plan.get("task_setup_preflight")
    )
    if task_setup_preflight:
        compact["task_setup_preflight"] = task_setup_preflight
    task_staging = _effective_public_task_staging(plan)
    if task_staging:
        compact["task_staging"] = task_staging
    fingerprint = skillsbench_runner_error_fingerprint(str(exc))
    if fingerprint:
        compact["runner_failure_fingerprint"] = fingerprint
    diagnostic = build_compose_setup_diagnostic(compact, plan)
    if diagnostic.get("status") != "not_applicable":
        compact["compose_setup_diagnostic"] = diagnostic
        apply_skillsbench_pre_agent_setup_diagnostic_attribution(compact)
    trials = compact.get("trials")
    if isinstance(trials, list) and trials:
        trial = trials[0]
        if isinstance(trial, dict):
            trial.update(
                {
                    "exception_type": exception_type,
                    "reward": {"reward": None},
                    "verifier_reward_present": False,
                    "trial_result_present": False,
                }
            )
    compact["validation"] = {
        "all_passed": False,
        "runner_failure_compact_recorded": True,
        "no_raw_logs_read": True,
        "no_raw_task_text_read": True,
        "no_raw_trajectory_read": True,
        "no_leaderboard_upload_requested": True,
    }
    reduced = compact_benchmark_run(compact)
    if reduced is None:
        raise RuntimeError("SkillsBench runner failure reducer produced non-compact run")
    closeout_metadata = {
        "task_id": args.task_id,
        "route": args.route,
        "run_group_id": args.run_group_id or plan.get("run_group_id"),
        "rollout_name": plan.get("rollout_name"),
    }
    for key, value in closeout_metadata.items():
        if value:
            reduced[key] = str(value)
    runner_output_capture = _public_runner_output_capture(plan)
    if runner_output_capture:
        reduced["runner_output_capture"] = runner_output_capture
    runner_config = _public_runner_config(plan)
    if runner_config:
        reduced["runner_config"] = runner_config
    app_server_observability = _app_server_goal_worker_observability(
        plan,
        controller_trace,
    )
    if app_server_observability:
        reduced["app_server_goal_worker_observability"] = app_server_observability
    recovered = _recover_runner_failure_score_from_controller_trace(reduced, plan)
    if not recovered:
        _recover_runner_failure_score_from_verifier_artifact(reduced, plan)
    _apply_codex_cli_goal_countability_guard_attribution(reduced)
    verifier_bootstrap.apply_skillsbench_verifier_bootstrap_missing_score_attribution(
        reduced,
        task_staging=_effective_public_task_staging(plan),
        setup_preflight=_public_task_setup_preflight(
            plan.get("task_setup_preflight")
        ),
    )
    reduced["case_event_timeline"] = _build_case_event_timeline(reduced, plan)
    post_run_debug_gate = build_skillsbench_post_run_debug_gate(reduced)
    reduced["post_run_debug_gate"] = post_run_debug_gate
    solution_quality = post_run_debug_gate.get("solution_quality")
    if isinstance(solution_quality, dict):
        reduced["solution_quality_signals"] = solution_quality
    return reduced


def update_ledger(
    args: argparse.Namespace,
    compact: dict[str, Any],
    *,
    compact_path: Path | None = None,
) -> dict[str, Any]:
    from loopx.benchmark_ledger import (
        build_benchmark_run_ledger_current_aggregate,
        load_benchmark_run_ledger,
        update_benchmark_run_ledger,
    )

    note_route = (
        "Codex ACP blind-loop baseline"
        if args.route == "codex-acp-blind-loop-baseline"
        else "Codex CLI /goal baseline"
        if args.route == CODEX_CLI_GOAL_BASELINE_ROUTE
        else "LoopX goal-start product-mode treatment"
        if args.route == LOOPX_GOAL_START_PRODUCT_MODE_ROUTE
        else "LoopX product-mode treatment"
        if args.route == LOOPX_PRODUCT_MODE_ROUTE
        else "raw Codex autonomous max5 baseline"
        if args.route == "raw-codex-autonomous-max5"
        else "Codex ACP baseline"
    )
    primary_ledger_path = _expanded_path(args.ledger_path)
    global_ledger_path = _expanded_path(args.global_ledger_path)
    dry_run = not args.update_ledger
    ledger_inheritance = _inherit_global_ledger_snapshot(
        primary_path=primary_ledger_path,
        global_path=global_ledger_path,
        dry_run=dry_run,
        enabled=not bool(args.skip_ledger_inherit),
    )
    primary_update = update_benchmark_run_ledger(
        ledger_path=primary_ledger_path,
        benchmark_run=compact,
        compact_artifact_ref=compact_path,
        run_group_id=args.run_group_id,
        notes=(
            f"official SkillsBench BenchFlow {note_route}; compact result only; "
            "no raw task/log/trajectory read into public state"
        ),
        cwd=REPO_ROOT,
        dry_run=dry_run,
    )
    global_update: dict[str, Any] | None = None
    if (
        not args.skip_global_ledger_sync
        and not _same_ledger_path(primary_ledger_path, global_ledger_path)
    ):
        global_update = update_benchmark_run_ledger(
            ledger_path=global_ledger_path,
            benchmark_run=compact,
            compact_artifact_ref=compact_path,
            run_group_id=args.run_group_id,
            notes=(
                f"official SkillsBench BenchFlow {note_route}; compact result only; "
                "no raw task/log/trajectory read into public state"
            ),
            cwd=REPO_ROOT,
            dry_run=dry_run,
        )

    current_aggregate_update: dict[str, Any] = {
        "schema_version": "skillsbench_current_aggregate_update_v0",
        "requested": bool(args.update_current_aggregate),
        "updated": False,
    }
    if args.update_current_aggregate:
        current_aggregate_path = _expanded_path(args.current_aggregate_path)
        current_aggregate_update.update(
            {
                "output_path": str(current_aggregate_path),
                "raw_logs_read": False,
                "raw_task_text_read": False,
                "raw_trajectory_read": False,
            }
        )
        if dry_run:
            current_aggregate_update["status"] = "dry_run"
        else:
            ledger_for_aggregate_path = (
                global_ledger_path
                if not args.skip_global_ledger_sync
                else primary_ledger_path
            )
            ledger_for_aggregate = load_benchmark_run_ledger(ledger_for_aggregate_path)
            aggregate = build_benchmark_run_ledger_current_aggregate(
                ledger_for_aggregate,
                benchmark_id="skillsbench@1.1",
                source_ledger_count=1,
            )
            current_aggregate_path.parent.mkdir(parents=True, exist_ok=True)
            current_aggregate_path.write_text(
                json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            current_aggregate_update.update(
                {
                    "status": "updated",
                    "updated": True,
                    "canonical_total": aggregate.get("canonical_total"),
                    "canonical_covered": aggregate.get("canonical_covered"),
                    "distribution": aggregate.get("distribution"),
                }
            )

    result = dict(primary_update)
    result["ledger_scope"] = _ledger_scope_label(primary_ledger_path, global_ledger_path)
    result["primary_ledger_update"] = primary_update
    result["global_ledger_path"] = str(global_ledger_path)
    result["global_ledger_sync_enabled"] = not bool(args.skip_global_ledger_sync)
    result["global_ledger_update"] = global_update
    result["global_ledger_inheritance"] = ledger_inheritance
    result["current_aggregate_update"] = current_aggregate_update
    return result


def append_history(args: argparse.Namespace, compact_path: Path) -> dict[str, Any]:
    if not args.append_history:
        return {
            "schema_version": "skillsbench_history_append_result_v0",
            "requested": False,
            "appended": False,
        }
    classification_by_route = {
        "codex-acp-blind-loop-baseline": "skillsbench_codex_acp_blind_loop_baseline_result_v0",
        "codex-cli-goal-baseline": "skillsbench_codex_cli_goal_baseline_result_v0",
        "loopx-product-mode": "skillsbench_loopx_product_mode_result_v0",
        "loopx-goal-start-product-mode": "skillsbench_loopx_goal_start_product_mode_result_v0",
        "loopx-turn-agent-cli": "skillsbench_loopx_turn_agent_cli_result_v0",
        "raw-codex-autonomous-max5": "skillsbench_raw_codex_autonomous_max5_result_v0",
        "codex-app-server-goal-baseline": "skillsbench_codex_app_server_goal_baseline_result_v0",
    }
    classification = classification_by_route.get(
        args.route,
        "skillsbench_unknown_route_result_v0",
    )
    cmd = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(Path(args.registry).expanduser()),
        "--runtime-root",
        str(Path(args.runtime_root).expanduser()),
        "--format",
        "json",
        "history",
        "append-benchmark-run",
        "--goal-id",
        args.goal_id,
        "--benchmark-run-json",
        str(compact_path),
        "--classification",
        classification,
        "--execute",
    ]
    registry_exists = Path(args.registry).expanduser().exists()
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return {
            "schema_version": "skillsbench_history_append_result_v0",
            "requested": True,
            "appended": True,
            "classification": classification,
            "raw_cli_output_recorded": False,
        }
    combined = f"{proc.stdout}\n{proc.stderr}"
    failure_kind = "cli_failed"
    if not registry_exists or "registry file does not exist" in combined:
        failure_kind = "missing_registry"
    return {
        "schema_version": "skillsbench_history_append_result_v0",
        "requested": True,
        "appended": False,
        "classification": classification,
        "failure_kind": failure_kind,
        "returncode": proc.returncode,
        "registry_exists": registry_exists,
        "raw_cli_output_recorded": False,
    }


def _build_runner_exception_closeout_payload(
    args: argparse.Namespace,
    plan: dict[str, Any],
    exc: BaseException,
) -> tuple[dict[str, Any], int]:
    recovered_payload = reduce_official_result_after_runner_exception(args, plan, exc)
    if recovered_payload is not None:
        return recovered_payload, 0

    closeout_recorded = False
    recovered_after_runner_exception = False
    official_task_score = None
    score_failure_attribution = None
    try:
        compact = build_runner_failure_compact(args, plan, exc)
        compact_path = Path(plan["compact_benchmark_run_json"])
        compact_path.parent.mkdir(parents=True, exist_ok=True)
        compact_path.write_text(
            json.dumps(compact, indent=2, sort_keys=True, default=_json_default)
            + "\n",
            encoding="utf-8",
        )
        ledger_update = update_ledger(args, compact, compact_path=compact_path)
        history_append = append_history(args, compact_path)
        closeout_recorded = True
        recovered_after_runner_exception = (
            compact.get("official_score_status") == "completed"
        )
        official_task_score = compact.get("official_task_score")
        score_failure_attribution = compact.get("score_failure_attribution")
    except Exception:
        compact_path = None
        ledger_update = None
        history_append = None
    payload = {
        "ok": recovered_after_runner_exception,
        "error_type": type(exc).__name__,
        "error_recorded": closeout_recorded,
        "compact_closeout_recorded": closeout_recorded,
        "recovered_after_runner_exception": recovered_after_runner_exception,
        "task_id": args.task_id,
        "compact_benchmark_run_json": str(compact_path) if compact_path else None,
        "official_task_score": official_task_score,
        "score_failure_attribution": score_failure_attribution,
        "ledger_update": ledger_update,
        "history_append": history_append,
    }
    return payload, 0 if closeout_recorded else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    raw_argv = list(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default="react-performance-debugging")
    parser.add_argument(
        "--task-ids",
        default=None,
        help=(
            "Comma- or whitespace-separated SkillsBench task ids to run as a "
            "batch. When set, this replaces --task-id for the main runner path."
        ),
    )
    parser.add_argument(
        "--parallel-cases",
        type=int,
        default=1,
        help=(
            "Maximum number of SkillsBench cases to run concurrently when "
            "--task-ids contains more than one task. Defaults to serial single "
            "case behavior."
        ),
    )
    parser.add_argument(
        "--batch-case-start-gap-sec",
        type=float,
        default=0.0,
        help=(
            "Minimum delay between starting consecutive cases in a "
            "--task-ids batch. This is useful for host-agent routes whose "
            "backend session startup is rate limited; 0 preserves the "
            "previous immediate-start behavior."
        ),
    )
    parser.add_argument("--dataset", default="skillsbench@1.1")
    parser.add_argument(
        "--route",
        default=DEFAULT_ROUTE,
        help=(
            "codex-cli-goal-baseline is the canonical Codex Goal baseline "
            "using the host Codex CLI TUI /goal slash command; "
            "codex-acp-blind-loop-baseline is the ordinary Codex no-goal "
            "baseline with a fixed no-feedback loop budget; "
            "raw-codex-autonomous-max5 and loopx-goal-start-product-mode are "
            "the main-table raw/new comparison routes; "
            "loopx-goal-start-product-mode adds /loopx goal-start planning "
            "with a compact ranked todo plan before selected-P0 lifecycle; "
            "codex-app-server-goal-baseline is a deprecated legacy app-server "
            "Goal route retained for explicit compatibility experiments only; "
            "Routes that return official verifier feedback to the agent are "
            "unsupported because they leak oracle signal into the loop."
        ),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        help=(
            "Generic Codex reasoning effort for routes backed by Codex. "
            "For codex-acp routes this is forwarded to codex exec via "
            "-c model_reasoning_effort=...; for native app-server Goal routes "
            "it overrides --app-server-reasoning-effort."
        ),
    )
    parser.add_argument(
        "--app-server-reasoning-effort",
        default="high",
        help=(
            "Legacy/native app-server-only reasoning effort passed as "
            "turn/start effort for codex-app-server-goal-baseline runs. "
            "Prefer --reasoning-effort for cross-route benchmark runs."
        ),
    )
    parser.add_argument("--sandbox", default="docker")
    parser.add_argument("--sandbox-user", default="agent")
    parser.add_argument(
        "--include-task-skills",
        action="store_true",
        help=(
            "Ask BenchFlow to include task-provided skills. Defaults to false "
            "for the no-skill baseline/treatment comparison route."
        ),
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help=(
            "Maximum scheduled agent rounds per arm before budget stop. "
            f"Defaults to {DEFAULT_MAX_ROUNDS}; blind-loop and product-mode "
            "routes still stop early once official reward reaches 1.0, without "
            "forwarding that reward to the agent."
        ),
    )
    parser.add_argument(
        "--independent-goal-retries",
        type=int,
        default=1,
        help=(
            "Run the same native Goal case as multiple independent attempts "
            "for supported goal routes. Each attempt gets a fresh "
            "job/rollout/thread; official verifier reward is observed only by "
            "the runner to decide whether to stop before the retry budget, and "
            "is never forwarded to the worker."
        ),
    )
    parser.add_argument(
        "--allow-deprecated-app-server-goal-route",
        action="store_true",
        help=(
            "Allow codex-app-server-goal-baseline to execute as an explicit "
            "legacy compatibility experiment. Normal SkillsBench Goal baselines "
            "must use codex-cli-goal-baseline."
        ),
    )
    parser.add_argument("--outer-timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--sandbox-setup-timeout", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument(
        "--build-stall-timeout-sec",
        type=int,
        default=DEFAULT_BUILD_STALL_TIMEOUT_SEC,
        help=(
            "Optional public-safe watchdog for Docker build/setup before any "
            "agent lifecycle starts. Defaults to "
            f"{DEFAULT_BUILD_STALL_TIMEOUT_SEC}s; pass 0 to disable the "
            "watchdog. Positive values are honored for setup-stall attribution."
        ),
    )
    parser.add_argument("--agent-idle-timeout", type=int, default=900)
    parser.add_argument(
        "--verifier-prep-timeout-sec",
        type=int,
        default=DEFAULT_VERIFIER_PREP_TIMEOUT_SEC,
        help=(
            "Timeout for BenchFlow verifier-phase prep/hardening shell calls. "
            "This does not change the task verifier scoring timeout."
        ),
    )
    parser.add_argument(
        "--final-verifier-timeout-sec",
        type=int,
        default=0,
        help=(
            "Optional timeout for the final official verifier command. "
            "0 preserves upstream verifier behavior; nonzero failures close "
            "out with compact public-safe verifier-timeout attribution and no "
            "raw verifier output."
        ),
    )
    parser.add_argument(
        "--verifier-dependency-cache-mode",
        choices=("off", "shared"),
        default="shared",
        help=(
            "Reuse package-manager and browser artifacts for Docker verifier "
            "bootstrap. shared is the default; tasks without detected verifier "
            "bootstrap risk do not receive the cache mount."
        ),
    )
    parser.add_argument(
        "--verifier-dependency-cache-root",
        default=os.environ.get(
            "LOOPX_SKILLSBENCH_VERIFIER_DEPENDENCY_CACHE_ROOT",
            verifier_cache.DEFAULT_VERIFIER_DEPENDENCY_CACHE_ROOT,
        ),
        help=(
            "Private host cache root for verifier dependency artifacts. The "
            "path is never written to public benchmark output."
        ),
    )
    parser.add_argument(
        "--soft-verifier-timeout-sec",
        type=int,
        default=DEFAULT_SOFT_VERIFIER_TIMEOUT_SEC,
        help=(
            "Timeout for every-round intermediate soft verifier commands. "
            "This keeps product-mode private reward sampling from hanging on "
            "task verifier network calls while still withholding reward, "
            "pass/fail, and verifier output from the agent."
        ),
    )
    parser.add_argument(
        "--product-mode-soft-verify-policy",
        choices=("final-only", "every-round"),
        default=DEFAULT_PRODUCT_MODE_SOFT_VERIFY_POLICY,
        help=(
            "Intermediate BenchFlow soft-verify policy for the main-table "
            "product-mode routes. every-round privately samples verifier reward "
            "after each agent round so the controller can stop at reward 1.0 "
            "without forwarding reward/pass/fail/verifier output to the agent. "
            "final-only is an explicit ablation that waits for final official "
            "scoring before observing reward."
        ),
    )
    parser.add_argument(
        "--app-server-acp-heartbeat-interval-sec",
        type=float,
        default=120.0,
        help=(
            "Public-safe ACP thought keepalive interval while a host "
            "app-server Goal worker is active. Must stay below "
            "--agent-idle-timeout for long-running native Goal cases."
        ),
    )
    parser.add_argument(
        "--app-server-goal-followup-max",
        type=int,
        default=0,
        help=(
            "Experimental same-thread continuation budget for ordinary "
            "completed codex-app-server-goal-baseline turns. The follow-up "
            "prompt provides no verifier/reward/pass-fail feedback to the "
            "worker. 0 preserves the native single-turn baseline."
        ),
    )
    parser.add_argument(
        "--app-server-goal-prompt-style",
        choices=("bridge-only", "native-goal", "cli-exec-like"),
        default="bridge-only",
        help=(
            "Prompt framing for codex-app-server-goal-baseline. bridge-only "
            "keeps the bare app-server baseline to task prompt plus sandbox "
            "bridge; native-goal adds app closeout framing; cli-exec-like keeps "
            "the worker prompt closer to Codex exec for diagnostic compatibility."
        ),
    )
    parser.add_argument("--max-verifier-output-chars", type=int, default=0)
    parser.add_argument("--skillsbench-root", default=str(DEFAULT_SKILLSBENCH_ROOT))
    parser.add_argument("--loopx-source-dir", default=str(REPO_ROOT), help="Local LoopX checkout for product-mode source mount/upload; the path is not recorded.")
    parser.add_argument("--expected-loopx-git-head", default="", help="Fail before task execution unless runner LoopX checkout HEAD starts with this public commit prefix.")
    parser.add_argument("--no-loopx-source-mount", action="store_true", help="Disable product-mode LoopX source mount/upload and use the public installer path.")
    parser.add_argument(
        "--jobs-dir",
        default=str(REPO_ROOT / ".local/private-benchmark-jobs"),
    )
    parser.add_argument("--job-name")
    parser.add_argument("--rollout-name")
    parser.add_argument(
        "--run-group-id",
        default=None,
    )
    parser.add_argument("--ledger-path", default=None)
    parser.add_argument(
        "--global-ledger-path",
        default=None,
        help=(
            "Canonical benchmark_run_ledger_v0 JSON. Defaults to a private "
            ".local ledger unless --publish-public-ledger is set. When "
            "--ledger-path points to a run-group/local ledger, the runner "
            "inherits this ledger first and syncs the new row back here unless "
            "--skip-global-ledger-sync is set."
        ),
    )
    parser.add_argument(
        "--publish-public-ledger",
        action="store_true",
        help=(
            "Use the repository research ledger as the default --ledger-path "
            "and --global-ledger-path. Without this explicit publish intent, "
            "benchmark update-ledger writes default to a private .local ledger."
        ),
    )
    parser.add_argument(
        "--skip-global-ledger-sync",
        action="store_true",
        help="Do not upsert run-group/local ledger rows back into --global-ledger-path.",
    )
    parser.add_argument(
        "--skip-ledger-inherit",
        action="store_true",
        help="Do not initialize a missing run-group/local ledger from --global-ledger-path.",
    )
    parser.add_argument(
        "--current-aggregate-path",
        default=None,
        help=(
            "Path for the public-safe current aggregate projection refreshed "
            "after --update-ledger. Defaults to current-aggregate-status.v3.json "
            "next to --global-ledger-path."
        ),
    )
    parser.add_argument(
        "--skip-current-aggregate-update",
        dest="update_current_aggregate",
        action="store_false",
        help="Do not refresh the current aggregate projection after writing the run ledger.",
    )
    parser.set_defaults(update_current_aggregate=True)
    parser.add_argument("--goal-id", default=DEFAULT_GOAL_ID)
    parser.add_argument("--registry", default=str(REPO_ROOT / ".loopx/registry.json"))
    parser.add_argument("--runtime-root", default=str(REPO_ROOT / ".local"))
    parser.add_argument("--append-history", action="store_true")
    parser.add_argument("--update-ledger", action="store_true")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Print launch plan without importing BenchFlow or running a task.",
    )
    parser.add_argument(
        "--setup-only-public-preflight",
        action="store_true",
        help=(
            "Materialize the BenchFlow job root and environment, then stop "
            "before agent install, agent execution, and verification. Emit only "
            "a compact public-safe setup classification."
        ),
    )
    parser.add_argument(
        "--reduce-only",
        action="store_true",
        help="Reduce an existing result.json for the selected job without rerunning the task.",
    )
    parser.add_argument(
        "--local-codex-participant-ping",
        action="store_true",
        help=(
            "Run a fixed local Codex CLI participant materialization ping and "
            "print compact public-safe readiness JSON. This does not launch "
            "BenchFlow or claim the A2A worker handshake is wired."
        ),
    )
    parser.add_argument(
        "--local-codex-bin",
        default="codex",
        help="Codex CLI binary for --local-codex-participant-ping.",
    )
    parser.add_argument(
        "--local-codex-sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
        help=(
            "Sandbox mode used by the host-local ACP relay when it invokes "
            "local Codex for a full SkillsBench launch."
        ),
    )
    parser.add_argument(
        "--local-codex-exec-timeout-sec",
        type=int,
        default=None,
        help=(
            "Per-prompt timeout for local Codex exec in host-local ACP launch "
            "mode. Omit to use the host-local bridge idle timeout plus a small "
            "agent timeout margin, except codex-app-server-goal-baseline which "
            "uses the longer of the default exec timeout and --outer-timeout-sec."
        ),
    )
    parser.add_argument(
        "--local-codex-first-action-timeout-sec",
        type=int,
        default=None,
        help=(
            "Optional watchdog for the first sandbox bridge operation from a "
            "host-local Codex turn. Omit to use the Codex CLI Goal default "
            f"({DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC}s) for "
            "codex-cli-goal-baseline, or the app-server Goal default "
            f"({DEFAULT_APP_SERVER_GOAL_FIRST_ACTION_TIMEOUT_SEC}s) for "
            "codex-app-server-goal-baseline; 0 disables the watchdog."
        ),
    )
    parser.add_argument(
        "--local-codex-goal-active-timeout-sec",
        type=int,
        default=None,
        help=(
            "Optional watchdog for observing Codex CLI /goal active state before "
            "the first sandbox bridge operation. Omit to use the independent "
            f"codex-cli-goal-baseline startup watchdog ({DEFAULT_CODEX_CLI_GOAL_ACTIVE_TIMEOUT_SEC}s); "
            "0 disables this startup watchdog."
        ),
    )
    parser.add_argument(
        "--local-codex-bridge-idle-timeout-sec",
        type=int,
        default=None,
        help=(
            "Optional watchdog after the most recent sandbox bridge operation "
            "from a host-local Codex turn. Omit to use the host-local default "
            f"({DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC}s); 0 disables "
            "the watchdog."
        ),
    )
    parser.add_argument(
        "--local-codex-task-output-quiet-timeout-sec",
        type=int,
        default=None,
        help=(
            "Optional watchdog after a successful task-facing file write and no "
            "inflight bridge operation. Omit to use the host-local default "
            f"({DEFAULT_HOST_LOCAL_CODEX_TASK_OUTPUT_QUIET_TIMEOUT_SEC}s); "
            "0 disables the watchdog."
        ),
    )
    parser.add_argument("--local-codex-ping-timeout-sec", type=int, default=120, help="Timeout for --local-codex-participant-ping.")
    parser.add_argument("--codex-cli-goal-thread-prewarm", action="store_true", help="Prewarm the Codex CLI TUI thread before codex-cli-goal /goal startup canaries.")
    parser.add_argument(
        "--local-driver-worker-handshake-preflight",
        action="store_true",
        help=(
            "Inspect the local SkillsBench/BenchFlow worker protocol contract "
            "and print compact readiness JSON. This does not launch a task or "
            "invoke Codex."
        ),
    )
    parser.add_argument(
        "--local-codex-cli-participant-ready",
        action="store_true",
        help=(
            "Tell --local-driver-worker-handshake-preflight that a prior local "
            "Codex CLI participant ping is already materialized."
        ),
    )
    parser.add_argument(
        "--local-acp-relay-probe",
        action="store_true",
        help=(
            "During --local-driver-worker-handshake-preflight, launch a local "
            "ACP stdio relay handshake probe. The default probe uses the "
            "LoopX dry-run relay and does not invoke Codex."
        ),
    )
    parser.add_argument(
        "--local-acp-relay-command",
        default=None,
        help=(
            "Optional command for --local-acp-relay-probe. Omit to use the "
            "LoopX dry-run relay."
        ),
    )
    parser.add_argument(
        "--local-acp-relay-probe-timeout-sec",
        type=float,
        default=10.0,
        help="Timeout for --local-acp-relay-probe.",
    )
    parser.add_argument(
        "--host-local-acp-transport-probe",
        action="store_true",
        help=(
            "During --local-driver-worker-handshake-preflight, use BenchFlow's "
            "ACPClient over host-local stdio to talk to the local relay. This "
            "does not launch a task or invoke Codex."
        ),
    )
    parser.add_argument(
        "--host-local-acp-transport-probe-timeout-sec",
        type=float,
        default=10.0,
        help="Timeout for --host-local-acp-transport-probe.",
    )
    parser.add_argument(
        "--host-local-acp-launch",
        action="store_true",
        help=(
            "Run the official BenchFlow rollout with the ACP agent hosted by "
            "the local stdio relay instead of container-local codex-acp. "
            "This keeps Codex auth/model/state local; remote execution still "
            "requires a separate command/file bridge visible to the local Codex "
            "worker."
        ),
    )
    parser.add_argument(
        "--codex-api-reverse-tunnel-proxy",
        default=os.environ.get("LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY", ""),
        help=(
            "HTTP proxy URL for a reverse tunnel that lets a remote host-side "
            "Codex app-server reach the Codex backend. The URL is forwarded "
            "only to the private worker environment and is never written to "
            "public compact artifacts; public artifacts record only a redacted "
            "proxy source/scheme/port summary."
        ),
    )
    parser.add_argument(
        "--codex-api-egress-mode",
        choices=CODEX_API_EGRESS_MODE_CHOICES,
        default=os.environ.get("LOOPX_CODEX_API_EGRESS_MODE", "auto"),
        help=(
            "How host-local Codex workers reach the Codex backend. For formal "
            "host-local app-server benchmark runs, auto resolves to "
            "reverse-tunnel so the runner fails fast unless a checked HTTP "
            "CONNECT reverse tunnel proxy is configured. For other host-local "
            "routes, explicit reverse-tunnel/direct requests are honored; "
            "direct is intended only for explicit local debugging."
        ),
    )
    parser.add_argument(
        "--codex-api-egress-preflight-timeout-sec",
        type=float,
        default=DEFAULT_CODEX_API_EGRESS_PREFLIGHT_TIMEOUT_SEC,
        help=(
            "Timeout for the native app-server Codex API egress preflight. "
            "For remote benchmark hosts, configure a reverse tunnel proxy "
            "before running formal codex-app-server-goal-baseline cases."
        ),
    )
    parser.add_argument(
        "--benchmark-egress-proxy",
        default="",
        help=(
            "Optional HTTP proxy URL for benchmark setup/verifier egress. "
            "Omit the flag and set LOOPX_SKILLSBENCH_EGRESS_PROXY in the "
            "private runtime environment for default benchmark runs. The URL "
            "is applied only to private subprocess/worker environments; public "
            "artifacts record only source/scheme/kind/port summaries."
        ),
    )
    parser.add_argument(
        "--benchmark-egress-proxy-mode",
        choices=BENCHMARK_EGRESS_PROXY_MODE_CHOICES,
        default=os.environ.get("LOOPX_SKILLSBENCH_EGRESS_PROXY_MODE", "auto"),
        help=(
            "Benchmark setup/verifier proxy policy. auto uses "
            "LOOPX_SKILLSBENCH_EGRESS_PROXY when present, off disables proxy "
            "injection, and require fails before a run unless a valid private "
            "HTTP CONNECT proxy is configured."
        ),
    )
    parser.add_argument(
        "--benchmark-egress-no-proxy",
        default=os.environ.get("LOOPX_SKILLSBENCH_EGRESS_NO_PROXY", ""),
        help=(
            "Comma-separated NO_PROXY additions for benchmark setup/verifier "
            "egress. The value is merged with loopback and public benchmark "
            "endpoint defaults, forwarded only to private subprocess/worker "
            "environments, and never recorded raw in public artifacts."
        ),
    )
    parser.add_argument(
        "--benchmark-egress-proxy-preflight-timeout-sec",
        type=float,
        default=DEFAULT_BENCHMARK_EGRESS_PROXY_PREFLIGHT_TIMEOUT_SEC,
        help=(
            "Timeout for the benchmark setup/verifier egress proxy preflight. "
            "The probe records no raw proxy URL or raw response output."
        ),
    )
    parser.add_argument(
        "--docker-gcr-mirror-prefix",
        default=os.environ.get("LOOPX_SKILLSBENCH_GCR_MIRROR_PREFIX", ""),
        help=(
            "Optional private runtime registry prefix used only for staged "
            "Dockerfile FROM rewrites of gcr.io/oss-fuzz-base images. Public "
            "artifacts record only booleans and never the raw prefix."
        ),
    )
    parser.add_argument(
        "--host-local-acp-codex-exec-preflight",
        action="store_true",
        help=(
            "Before a full host-local ACP task launch, run a task-free relay "
            "prompt through the configured local Codex exec command. Use this "
            "for remote reverse-channel product-mode runs so a missing Codex "
            "reverse server fails before BenchFlow starts a scored case."
        ),
    )
    parser.add_argument(
        "--host-local-acp-codex-exec-preflight-timeout-sec",
        type=float,
        default=120.0,
        help="Timeout for --host-local-acp-codex-exec-preflight.",
    )
    parser.add_argument(
        "--host-local-acp-codex-exec-preflight-attempts",
        type=int,
        default=3,
        help=(
            "Number of task-free Codex exec preflight attempts. Retries are "
            "only useful for transient reverse-channel readiness races."
        ),
    )
    parser.add_argument(
        "--benchflow-agent-runtime-dir",
        default=None,
        help=(
            "Host-side BenchFlow agent runtime layer built by "
            "scripts/skillsbench_agent_runtime_layer.py. The path is used only "
            "for local readiness checks and is not written to public output."
        ),
    )
    parser.add_argument(
        "--require-preinstalled-benchflow-agent-runtime",
        action="store_true",
        help=(
            "Fail fast before a full case run unless --benchflow-agent-runtime-dir "
            "contains bin/node, bin/npm, and bin/codex-acp. Use this for "
            "container-local Codex ACP routes so case containers do not spend "
            "attempts on per-case Node/npm/agent runtime materialization."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-ready",
        action="store_true",
        help=(
            "Tell --local-driver-worker-handshake-preflight that the bounded "
            "remote command/file bridge is already materialized."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-probe",
        action="store_true",
        help=(
            "During --local-driver-worker-handshake-preflight, call a bounded "
            "remote command/file bridge probe command and derive readiness from "
            "its compact response."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-probe-command",
        default=None,
        help=(
            "Command used by --remote-command-file-bridge-probe. It must read "
            "the probe JSON from stdin and write compact probe JSON to stdout."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-solver-command",
        default=None,
        help=(
            "Private command injected into host-local product-mode solver prompts "
            "to operate on the scored SkillsBench sandbox. This is separate from "
            "the public-safe probe command; fixture-only probe helpers must not "
            "be used here."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-agent-command",
        default=None,
        help=(
            "Optional private command injected into the local Codex solver "
            "prompt when --remote-command-file-bridge-solver-command is only "
            "valid from the remote relay host. The command text is never "
            "written to public compact traces."
        ),
    )
    parser.add_argument(
        "--remote-command-file-bridge-agent-command-instrumented",
        action="store_true",
        help=(
            "Compatibility declaration for externally instrumented agent bridge "
            "commands. The host-local relay still wraps explicit agent bridge "
            "commands with its own public-safe operation counter; countable "
            "product-mode treatment continues to require nonzero agent lifecycle "
            "requests, not only driver checkpoints."
        ),
    )
    add_skillsbench_loopx_turn_arguments(parser)
    parser.add_argument(
        "--remote-command-file-bridge-probe-timeout-sec",
        type=float,
        default=10.0,
        help="Timeout for --remote-command-file-bridge-probe.",
    )
    parser.add_argument(
        "--fail-fast-on-apt-risk",
        action="store_true",
        help=(
            "Before a full run, block Docker tasks whose public setup preflight "
            "detects apt-based setup risk; writes a compact setup-preflight "
            "failure instead of spending a full case attempt."
        ),
    )
    parser.add_argument(
        "--fail-fast-on-verifier-bootstrap-risk",
        action="store_true",
        help=(
            "Before a full run, block Docker tasks whose public verifier "
            "preflight detects network/package bootstrap risk such as uv, "
            "curl/wget downloads, pip, npm, or apt commands; writes a compact "
            "setup-preflight failure instead of spending a full case attempt."
        ),
    )
    parser.add_argument(
        "--allow-staged-bootstrap-repair-run",
        action="store_true",
        help=(
            "For formal reverse-tunnel app-server Goal runs, allow the runner "
            "to stage an isolated task copy and apply existing public-safe "
            "Dockerfile/verifier bootstrap repairs instead of treating those "
            "repairable setup risks as automatic preflight blockers. Explicit "
            "--fail-fast-on-* flags still block."
        ),
    )
    apt_fail_fast_explicit = "--fail-fast-on-apt-risk" in raw_argv
    verifier_fail_fast_explicit = "--fail-fast-on-verifier-bootstrap-risk" in raw_argv
    args = parser.parse_args(raw_argv)
    if args.route in HISTORICAL_REDUCER_ROUTES:
        if not args.reduce_only:
            parser.error(
                "historical prompt-polling routes are read-only and require "
                "--reduce-only"
            )
    elif args.route not in SUPPORTED_ROUTES:
        parser.error(
            f"unsupported --route {args.route!r}; choose one of "
            + ", ".join(SUPPORTED_ROUTES)
        )
    if args.setup_only_public_preflight and (args.plan_only or args.reduce_only):
        parser.error(
            "--setup-only-public-preflight is incompatible with --plan-only "
            "and --reduce-only"
        )
    if args.setup_only_public_preflight and (args.append_history or args.update_ledger):
        parser.error(
            "--setup-only-public-preflight does not append history or update ledgers"
        )
    default_ledger = (
        PUBLIC_BENCHMARK_RUN_LEDGER if args.publish_public_ledger else DEFAULT_LEDGER
    )
    if args.ledger_path is None:
        args.ledger_path = str(default_ledger)
    if args.global_ledger_path is None:
        args.global_ledger_path = str(default_ledger)
    if args.current_aggregate_path is None:
        args.current_aggregate_path = str(
            Path(args.global_ledger_path).expanduser().parent
            / DEFAULT_CURRENT_AGGREGATE_FILENAME
        )
    args.apt_risk_fail_fast_defaulted = False
    args.verifier_bootstrap_fail_fast_defaulted = False
    args.bootstrap_light_fail_fast_defaulted = False
    if (
        _formal_app_server_goal_bootstrap_light_fail_fast_required(args)
        and not args.fail_fast_on_apt_risk
    ):
        args.fail_fast_on_apt_risk = True
        args.apt_risk_fail_fast_defaulted = not apt_fail_fast_explicit
    if (
        _formal_app_server_goal_bootstrap_light_fail_fast_required(args)
        and not args.fail_fast_on_verifier_bootstrap_risk
    ):
        args.fail_fast_on_verifier_bootstrap_risk = True
        args.verifier_bootstrap_fail_fast_defaulted = not verifier_fail_fast_explicit
    args.bootstrap_light_fail_fast_defaulted = bool(
        _formal_app_server_goal_bootstrap_light_fail_fast_required(args)
        and (
            args.apt_risk_fail_fast_defaulted
            or args.verifier_bootstrap_fail_fast_defaulted
        )
    )
    if args.parallel_cases < 1:
        parser.error("--parallel-cases must be >= 1")
    if args.batch_case_start_gap_sec < 0:
        parser.error("--batch-case-start-gap-sec must be >= 0")
    batch_task_ids = _split_task_ids_arg(args.task_ids)
    if args.task_ids is not None and not batch_task_ids:
        parser.error("--task-ids must contain at least one task id")
    if len(set(batch_task_ids)) != len(batch_task_ids):
        parser.error("--task-ids must not contain duplicate task ids")
    if args.task_ids is not None and len(batch_task_ids) == 1:
        args.task_id = batch_task_ids[0]
    if args.independent_goal_retries < 1:
        parser.error("--independent-goal-retries must be >= 1")
    if args.independent_goal_retries > 1:
        if args.setup_only_public_preflight:
            parser.error(
                "--setup-only-public-preflight does not use independent goal retries"
            )
        if args.route not in INDEPENDENT_GOAL_RETRY_ROUTES:
            parser.error(
                "--independent-goal-retries currently applies only to "
                "native Goal routes"
            )
        if args.reduce_only:
            parser.error("--independent-goal-retries is not compatible with --reduce-only")
        if len(batch_task_ids) > 1:
            parser.error(
                "--independent-goal-retries is not compatible with multi-case "
                "--task-ids; retry one case at a time"
            )
    if (
        args.route in PRODUCT_MODE_CONTROLLER_ROUTES
        and not args.plan_only
        and not args.reduce_only
        and not args.setup_only_public_preflight
        and args.max_rounds < PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS
    ):
        parser.error(
            "--max-rounds below "
            f"{PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS} is not allowed for formal "
            "product-mode/paired autonomous runs; use the default "
            f"{DEFAULT_MAX_ROUNDS}, pass at least "
            f"{PRODUCT_MODE_MIN_FORMAL_MAX_ROUNDS}, or use --plan-only/"
            "--reduce-only for fixture inspection."
        )
    return args


async def async_main(
    args: argparse.Namespace,
    *,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if args.run_group_id is None:
        args.run_group_id = (
            f"skillsbench-{args.task_id}-{args.route}-{_now_stamp()}"
        )
    if plan is None:
        plan = build_plan(args)
    if args.plan_only:
        return {"ok": True, "plan_only": True, "launch_plan": plan}
    if not args.reduce_only:
        write_benchmark_run_observable_status(
            jobs_dir=plan.get("jobs_dir"),
            job_name=plan.get("job_name"),
            status="running",
            record_pid=True,
        )
    runner_status_written = False
    try:
        return await _async_main_with_observable_handle(args, plan)
    except BaseException as exc:
        if not args.reduce_only:
            write_benchmark_run_observable_status(
                jobs_dir=plan.get("jobs_dir"),
                job_name=plan.get("job_name"),
                status=f"exception={type(exc).__name__}",
            )
            runner_status_written = True
        raise
    finally:
        if not args.reduce_only and not runner_status_written:
            write_benchmark_run_observable_status(
                jobs_dir=plan.get("jobs_dir"),
                job_name=plan.get("job_name"),
                status="rc=0",
            )


async def _async_main_with_observable_handle(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> dict[str, Any]:
    runtime_layer = (
        plan.get("benchflow_agent_runtime_layer")
        if isinstance(plan.get("benchflow_agent_runtime_layer"), dict)
        else {}
    )
    if (
        getattr(args, "require_preinstalled_benchflow_agent_runtime", False)
        and not args.setup_only_public_preflight
        and runtime_layer.get("ready") is not True
    ):
        prerequisites = plan.setdefault("runner_prerequisites", {})
        if isinstance(prerequisites, dict):
            prerequisites["preinstalled_benchflow_agent_runtime_required"] = True
            prerequisites["benchflow_agent_runtime_layer_ready"] = False
            prerequisites["benchflow_agent_runtime_layer_status"] = str(
                runtime_layer.get("status") or "missing_runtime_files"
            )
            prerequisites["codex_acp_runtime_launch_preflight_status"] = "blocked"
            prerequisites["codex_acp_runtime_launch_preflight_stage"] = (
                "preinstalled_benchflow_layer_missing_before_benchflow_run"
            )
        raise SkillsBenchSetupPreflightBlocked(
            "preinstalled BenchFlow agent runtime layer missing before full case run"
        )
    setup_preflight = (
        plan.get("task_setup_preflight")
        if isinstance(plan.get("task_setup_preflight"), dict)
        else {}
    )
    bootstrap_light_blocking_fields = _setup_preflight_public_blocking_fields(
        setup_preflight
    )
    bootstrap_light_blocker_kind = _bootstrap_light_blocker_kind(
        bootstrap_light_blocking_fields
    )
    if (
        _bootstrap_light_preflight_block_required(
            args,
            blocker_kind=bootstrap_light_blocker_kind,
        )
        and bootstrap_light_blocker_kind in {"apt", "dockerfile_package"}
    ):
        staging = plan.setdefault("task_staging", {})
        if isinstance(staging, dict):
            bootstrap_light_blocker_kind = _mark_bootstrap_light_preflight_blocked(
                staging=staging,
                setup_preflight=setup_preflight,
                blocking_fields=bootstrap_light_blocking_fields,
                args=args,
            )
        if bootstrap_light_blocker_kind == "apt":
            raise SkillsBenchSetupPreflightBlocked(
                "skillsbench apt setup risk preflight blocked: "
                "apt-based Docker setup risk detected before full case run"
            )
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench dockerfile package bootstrap risk preflight blocked: "
            "Dockerfile package bootstrap risk detected before full case run"
        )
    if (
        _bootstrap_light_preflight_block_required(
            args,
            blocker_kind=bootstrap_light_blocker_kind,
        )
        and bootstrap_light_blocker_kind == "verifier"
    ):
        staging = plan.setdefault("task_staging", {})
        if isinstance(staging, dict):
            _mark_bootstrap_light_preflight_blocked(
                staging=staging,
                setup_preflight=setup_preflight,
                blocking_fields=bootstrap_light_blocking_fields,
                args=args,
            )
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench verifier bootstrap risk preflight blocked: "
            "verifier dependency bootstrap risk detected before full case run"
        )
    if (
        not args.reduce_only
        and setup_preflight.get("status")
        in {
            "task_missing_from_canonical_tasks",
            "task_excluded_from_formal_tasks",
        }
    ):
        staging = plan.setdefault("task_staging", {})
        if isinstance(staging, dict):
            if _formal_app_server_goal_bootstrap_light_guard_required(args):
                _mark_bootstrap_light_preflight_blocked(
                    staging=staging,
                    setup_preflight=setup_preflight,
                    blocking_fields=bootstrap_light_blocking_fields,
                    args=args,
                )
            staging["task_source_preflight_blocked"] = True
            if setup_preflight.get("status") == "task_excluded_from_formal_tasks":
                staging["task_source_excluded_preflight_blocked"] = True
                staging["task_source_excluded"] = True
        if setup_preflight.get("status") == "task_excluded_from_formal_tasks":
            raise SkillsBenchSetupPreflightBlocked(
                "skillsbench task source excluded: "
                "task is excluded from formal tasks source before full case run"
            )
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench task source preflight blocked: "
            "task missing from canonical tasks source before full case run"
        )

    codex_runtime.run_preflight_if_required(
        args,
        plan,
        writeback=lambda: (
            _write_public_runner_config(plan),
            _write_public_runner_prerequisites(plan),
        ),
    )

    if (
        _codex_api_egress_preflight_required(args)
        and not args.reduce_only
        and not args.setup_only_public_preflight
    ):
        try:
            _run_codex_api_egress_preflight(args, plan)
        finally:
            _write_public_runner_config(plan)
            _write_public_runner_prerequisites(plan)

    if not args.reduce_only:
        try:
            _run_benchmark_egress_proxy_preflight(args, plan)
        finally:
            _write_public_runner_config(plan)
            _write_public_runner_prerequisites(plan)

    if (
        _host_local_acp_codex_exec_preflight_should_run(args)
        and args.host_local_acp_launch
        and not args.reduce_only
        and not args.setup_only_public_preflight
    ):
        _run_host_local_acp_codex_exec_preflight(args, plan)

    if not args.reduce_only:
        _write_public_runner_config(plan)
    ensure_benchflow_runtime(args)
    if args.reduce_only:
        _hydrate_reduce_only_public_runner_prerequisites(plan)
        result_path = discover_benchflow_result_path(plan)
        if not result_path.exists():
            raise FileNotFoundError(
                f"BenchFlow result.json not found for --reduce-only: {result_path}"
            )
        controller_trace = _read_controller_trace(plan)
        _merge_final_result_round_reward(controller_trace, result_path)
        _write_controller_trace(plan, controller_trace)
    else:
        case_result = await asyncio.wait_for(
            run_benchflow_case_with_private_output(args, plan),
            timeout=args.outer_timeout_sec,
        )
        if args.setup_only_public_preflight:
            if not isinstance(case_result, dict):
                raise TypeError("setup-only preflight returned a non-object result")
            preflight_path = Path(plan["setup_only_public_preflight_json"])
            preflight_path.parent.mkdir(parents=True, exist_ok=True)
            preflight_path.write_text(
                json.dumps(
                    case_result,
                    indent=2,
                    sort_keys=True,
                    default=_json_default,
                )
                + "\n",
                encoding="utf-8",
            )
            _write_public_runner_config(plan)
            _write_public_runner_prerequisites(plan)
            passed = case_result.get("status") == "passed"
            return {
                "ok": passed,
                "setup_only_public_preflight": True,
                "task_id": str(args.task_id),
                "route": str(args.route),
                "run_group_id": str(args.run_group_id or ""),
                "job_name": str(plan.get("job_name") or ""),
                "preflight": case_result,
                "setup_only_public_preflight_json": preflight_path.name,
                "compact_closeout_recorded": True,
                "runner_returncode": 0 if passed else 1,
            }
        if not isinstance(case_result, Path):
            raise TypeError("SkillsBench case returned a non-path result")
        result_path = case_result
    compact = reduce_result(args, result_path, plan)
    compact_path = Path(plan["compact_benchmark_run_json"])
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text(
        json.dumps(compact, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    ledger_update = update_ledger(args, compact, compact_path=compact_path)
    history_append = append_history(args, compact_path)
    return {
        "ok": True,
        "plan_only": False,
        "launch_plan": plan,
        "result_json": str(result_path),
        "compact_benchmark_run_json": str(compact_path),
        "result_discovery": plan.get("result_discovery"),
        "official_task_score": compact.get("official_task_score"),
        "score_failure_attribution": compact.get("score_failure_attribution"),
        "ledger_update": ledger_update,
        "history_append": history_append,
    }


def _load_json_object_from_mixed_text(text: str) -> tuple[dict[str, Any], bool]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty child payload")
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload, False
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload, True
    raise ValueError("child payload did not contain a JSON object")


def _extract_batch_case_subprocess_payload(
    *,
    case_args: argparse.Namespace,
    returncode: int,
    stdout: bytes,
    stderr: bytes,
) -> dict[str, Any]:
    streams = [
        ("stdout", stdout.decode("utf-8", errors="replace")),
        ("stderr", stderr.decode("utf-8", errors="replace")),
    ]
    if stdout and stderr:
        streams.append(
            (
                "combined",
                (
                    stdout.decode("utf-8", errors="replace")
                    + "\n"
                    + stderr.decode("utf-8", errors="replace")
                ),
            )
        )
    last_exc: Exception | None = None
    try:
        payload: dict[str, Any] | None = None
        mixed_output = False
        payload_source = ""
        for payload_source, text in streams:
            try:
                payload, mixed_output = _load_json_object_from_mixed_text(text)
                break
            except Exception as exc:
                last_exc = exc
        if payload is None:
            raise last_exc or ValueError("child payload missing")
        payload["batch_case_subprocess_payload_source"] = payload_source
        payload["batch_case_subprocess_payload_mixed_output"] = mixed_output
    except Exception as exc:
        payload = {
            "ok": False,
            "task_id": str(case_args.task_id),
            "run_group_id": str(case_args.run_group_id or ""),
            "route": str(case_args.route),
            "error_type": "SkillsBenchBatchCaseSubprocessPayloadError",
            "error_class": type(exc).__name__,
            "payload_error_class": (
                type(last_exc).__name__ if last_exc is not None else type(exc).__name__
            ),
            "child_returncode": int(returncode),
            "child_stdout_bytes": len(stdout),
            "child_stderr_bytes": len(stderr),
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "compact_closeout_recorded": False,
        }
    payload["batch_case_subprocess"] = True
    payload["runner_returncode"] = int(returncode)
    return payload


async def _run_batch_case_subprocess(
    case_args: argparse.Namespace,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        *_batch_case_args_to_cli(case_args),
    ]
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return _extract_batch_case_subprocess_payload(
        case_args=case_args,
        returncode=int(proc.returncode or 0),
        stdout=stdout,
        stderr=stderr,
    )


async def async_batch_main(
    args: argparse.Namespace,
    *,
    task_ids: list[str] | None = None,
) -> dict[str, Any]:
    selected_task_ids = list(task_ids or _batch_task_ids(args))
    run_group_id = str(
        args.run_group_id
        or f"skillsbench-batch-{args.route}-{_now_stamp()}"
    )
    parallel_cases = min(max(1, int(args.parallel_cases or 1)), len(selected_task_ids))
    semaphore = asyncio.Semaphore(parallel_cases)
    isolate_case_processes = _parallel_isolation_required(parallel_cases)
    case_start_pacer = BatchCaseStartPacer(args.batch_case_start_gap_sec)

    async def run_one(index: int, task_id: str) -> dict[str, Any]:
        case_args = _clone_args_for_batch_case(
            args,
            task_id=task_id,
            index=index,
            total=len(selected_task_ids),
            run_group_id=run_group_id,
        )
        async with semaphore:
            case_start_wait_sec = await case_start_pacer.wait_for_slot()
            case_plan = build_plan(case_args)
            try:
                if isolate_case_processes:
                    return case_start_pacer.annotate_payload(
                        await _run_batch_case_subprocess(case_args),
                        case_start_wait_sec,
                    )
                payload = await async_main(case_args, plan=case_plan)
                payload.setdefault("runner_returncode", 0)
                return case_start_pacer.annotate_payload(payload, case_start_wait_sec)
            except Exception as exc:
                payload, returncode = _build_runner_exception_closeout_payload(
                    case_args,
                    case_plan,
                    exc,
                )
                payload["runner_returncode"] = returncode
                return case_start_pacer.annotate_payload(payload, case_start_wait_sec)

    results = await asyncio.gather(
        *(run_one(index, task_id) for index, task_id in enumerate(selected_task_ids))
    )
    returncode = max(int(result.get("runner_returncode") or 0) for result in results)
    return {
        "ok": all(result.get("ok") is True for result in results),
        "batch": True,
        "task_count": len(selected_task_ids),
        "parallel_cases": parallel_cases,
        "case_process_isolation": isolate_case_processes,
        "case_start_gap_sec": case_start_pacer.start_gap_sec,
        "run_group_id": run_group_id,
        "results": results,
        "runner_returncode": returncode,
    }


def _independent_goal_retry_enabled(args: argparse.Namespace) -> bool:
    return int(getattr(args, "independent_goal_retries", 1) or 1) > 1


def _safe_retry_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "retry"


def _clone_args_for_independent_goal_retry(
    args: argparse.Namespace,
    *,
    attempt_index: int,
    run_group_id: str,
    base_job_name: str,
) -> argparse.Namespace:
    attempt_number = attempt_index + 1
    attempt_args = argparse.Namespace(**vars(args))
    attempt_args.independent_goal_retries = 1
    attempt_args.task_ids = None
    attempt_args.parallel_cases = 1
    attempt_args.run_group_id = run_group_id
    attempt_args.job_name = f"{base_job_name}-attempt-{attempt_number:02d}"
    route_slug = _safe_retry_slug(str(args.route).replace("-", "_"))
    attempt_args.rollout_name = (
        f"{args.task_id}__{route_slug}_independent_attempt_{attempt_number:02d}"
    )
    return attempt_args


def _official_reward_from_payload(payload: dict[str, Any]) -> float | None:
    official_task_score = payload.get("official_task_score")
    if isinstance(official_task_score, dict):
        value = official_task_score.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    value = payload.get("official_score")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _official_success_from_payload(payload: dict[str, Any]) -> bool:
    official_task_score = payload.get("official_task_score")
    if isinstance(official_task_score, dict):
        if official_task_score.get("passed") is True:
            return True
    reward = _official_reward_from_payload(payload)
    return bool(reward is not None and reward >= 1.0)


def _terminal_official_nonpassing_from_payload(payload: dict[str, Any]) -> bool:
    reward = _official_reward_from_payload(payload)
    if reward is None or _official_success_from_payload(payload):
        return False
    return (
        str(payload.get("score_failure_attribution") or "")
        in TERMINAL_OFFICIAL_NONPASSING_ATTRIBUTIONS
    )


def _independent_goal_retry_attempt_summary(
    payload: dict[str, Any],
    *,
    attempt_index: int,
) -> dict[str, Any]:
    launch_plan = payload.get("launch_plan")
    if not isinstance(launch_plan, dict):
        launch_plan = {}
    official_reward = _official_reward_from_payload(payload)
    official_success = _official_success_from_payload(payload)
    terminal_official_nonpassing = _terminal_official_nonpassing_from_payload(payload)
    summary: dict[str, Any] = {
        "schema_version": "skillsbench_independent_goal_retry_attempt_v0",
        "attempt_index": attempt_index,
        "attempt_number": attempt_index + 1,
        "ok": payload.get("ok") is True,
        "runner_returncode": int(payload.get("runner_returncode") or 0),
        "official_success": official_success,
        "official_reward": official_reward,
        "terminal_official_nonpassing": terminal_official_nonpassing,
        "score_failure_attribution": str(
            payload.get("score_failure_attribution") or ""
        ),
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "raw_verifier_output_read": False,
    }
    for key in (
        "task_id",
        "route",
        "run_group_id",
        "job_name",
        "rollout_name",
        "compact_benchmark_run_json",
        "result_json",
    ):
        value = payload.get(key) or launch_plan.get(key)
        if value:
            summary[key] = str(value)
    if not summary.get("compact_benchmark_run_json") and launch_plan.get(
        "compact_benchmark_run_json"
    ):
        summary["compact_benchmark_run_json"] = str(
            launch_plan.get("compact_benchmark_run_json")
        )
    if not summary.get("result_json") and launch_plan.get("result_json"):
        summary["result_json"] = str(launch_plan.get("result_json"))
    cleanup = payload.get("host_local_acp_attempt_cleanup")
    if isinstance(cleanup, dict):
        summary["host_local_acp_attempt_cleanup"] = {
            "schema_version": str(
                cleanup.get("schema_version")
                or "skillsbench_host_local_acp_attempt_cleanup_v0"
            )[:120],
            "requested": cleanup.get("requested") is True,
            "raw_logs_read": cleanup.get("raw_logs_read") is True,
            "raw_command_recorded": cleanup.get("raw_command_recorded") is True,
            "status": str(cleanup.get("status") or "unknown")[:120],
            "match_count": int(cleanup.get("match_count") or 0),
            "term_sent_count": int(cleanup.get("term_sent_count") or 0),
            "kill_sent_count": int(cleanup.get("kill_sent_count") or 0),
            "alive_after_count": int(cleanup.get("alive_after_count") or 0),
        }
    return summary


async def async_independent_goal_retry_main(args: argparse.Namespace) -> dict[str, Any]:
    attempt_budget = max(1, int(getattr(args, "independent_goal_retries", 1) or 1))
    run_group_id = str(
        args.run_group_id
        or f"skillsbench-{args.task_id}-{args.route}-independent-retry-{_now_stamp()}"
    )
    base_job_name = _safe_retry_slug(
        str(
            args.job_name
            or f"skillsbench-{args.task_id}-{args.route}-independent-retry-{_now_stamp()}"
        )
    )
    jobs_dir = Path(args.jobs_dir).expanduser()
    attempts: list[dict[str, Any]] = []
    success_observed = False
    first_success_attempt: int | None = None
    terminal_official_nonpassing_observed = False
    first_terminal_official_nonpassing_attempt: int | None = None

    for attempt_index in range(attempt_budget):
        attempt_args = _clone_args_for_independent_goal_retry(
            args,
            attempt_index=attempt_index,
            run_group_id=run_group_id,
            base_job_name=base_job_name,
        )
        attempt_plan = build_plan(attempt_args)
        attempt_cleanup: dict[str, Any] | None = None
        try:
            payload = await async_main(attempt_args, plan=attempt_plan)
            payload["runner_returncode"] = 0
        except Exception as exc:
            attempt_cleanup = cleanup_host_local_acp_attempt_children(attempt_plan)
            payload, returncode = _build_runner_exception_closeout_payload(
                attempt_args,
                attempt_plan,
                exc,
            )
            payload["runner_returncode"] = returncode
        else:
            attempt_cleanup = cleanup_host_local_acp_attempt_children(attempt_plan)
            _write_public_runner_prerequisites(attempt_plan)
        payload.setdefault("launch_plan", attempt_plan)
        if attempt_cleanup is not None:
            payload["host_local_acp_attempt_cleanup"] = attempt_cleanup
        attempt_summary = _independent_goal_retry_attempt_summary(
            payload,
            attempt_index=attempt_index,
        )
        attempts.append(attempt_summary)
        if attempt_summary.get("official_success") is True:
            success_observed = True
            first_success_attempt = attempt_index + 1
            break
        if attempt_summary.get("terminal_official_nonpassing") is True:
            terminal_official_nonpassing_observed = True
            first_terminal_official_nonpassing_attempt = attempt_index + 1
            break

    if success_observed:
        stop_reason = "stop_after_first_official_reward_1_without_feedback"
    elif terminal_official_nonpassing_observed:
        stop_reason = "stop_after_first_terminal_official_nonpassing_verifier_result"
    else:
        stop_reason = "stop_after_independent_goal_retry_budget"
    observed_rewards = [
        float(attempt["official_reward"])
        for attempt in attempts
        if isinstance(attempt.get("official_reward"), (int, float))
        and not isinstance(attempt.get("official_reward"), bool)
    ]
    best_official_reward = max(observed_rewards) if observed_rewards else None
    final_official_reward = observed_rewards[-1] if observed_rewards else None
    retry_summary = {
        "schema_version": "skillsbench_independent_goal_retry_summary_v0",
        "ok": success_observed,
        "independent_goal_retry": True,
        "task_id": str(args.task_id),
        "route": str(args.route),
        "run_group_id": run_group_id,
        "attempt_budget": attempt_budget,
        "attempts_started": len(attempts),
        "attempts_completed": len(attempts),
        "success_observed": success_observed,
        "first_success_attempt": first_success_attempt,
        "terminal_official_nonpassing_observed": (
            terminal_official_nonpassing_observed
        ),
        "first_terminal_official_nonpassing_attempt": (
            first_terminal_official_nonpassing_attempt
        ),
        "best_official_reward": best_official_reward,
        "final_official_reward": final_official_reward,
        "official_task_score": {
            "kind": "skillsbench_independent_goal_retry_best_reward",
            "value": best_official_reward,
            "passed": success_observed,
        },
        "stop_reason": stop_reason,
        "fresh_goal_thread_per_attempt": True,
        "official_reward_feedback_forwarded_to_agent": False,
        "verifier_output_forwarded_to_agent": False,
        "reward_feedback_forwarded": False,
        "raw_task_text_read_into_public_state": False,
        "raw_trajectory_read_into_public_state": False,
        "raw_verifier_output_read_into_public_state": False,
        "attempts": attempts,
        "runner_returncode": 0 if success_observed else max(
            int(attempt.get("runner_returncode") or 0) for attempt in attempts
        ),
    }
    summary_path = jobs_dir / base_job_name / "independent_goal_retry_summary.public.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(retry_summary, indent=2, sort_keys=True, default=_json_default)
        + "\n",
        encoding="utf-8",
    )
    retry_summary["retry_summary_json"] = str(summary_path)
    return retry_summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    logging.getLogger().setLevel(logging.WARNING)
    if (
        args.route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
        and not args.plan_only
        and not args.reduce_only
        and not args.setup_only_public_preflight
        and not args.allow_deprecated_app_server_goal_route
    ):
        payload = {
            "ok": False,
            "error_type": "SkillsBenchAppServerGoalRouteDeprecated",
            "route": args.route,
            "reason": (
                "codex-app-server-goal-baseline is deprecated for normal "
                "SkillsBench baseline/treatment collection. It exercises the "
                "Codex app-server surface, while the current LoopX treatment "
                "and baseline policy requires the Codex CLI TUI /goal product "
                "path."
            ),
            "next_action": (
                "rerun with --route codex-cli-goal-baseline --reasoning-effort "
                "xhigh --host-local-acp-launch and a materialized command/file "
                "bridge; use --allow-deprecated-app-server-goal-route only for "
                "explicit legacy compatibility experiments"
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if (
        args.route == CODEX_CLI_GOAL_BASELINE_ROUTE
        and not args.plan_only
        and not args.reduce_only
        and not args.setup_only_public_preflight
    ):
        bridge_ready = bool(
            args.remote_command_file_bridge_ready
            or args.remote_command_file_bridge_probe
        )
        bridge_command_configured = bool(args.remote_command_file_bridge_solver_command)
        bridge_sandbox_auto_wiring_pending = bool(
            args.host_local_acp_launch
            and bridge_ready
            and not bridge_command_configured
        )
        if (
            not args.host_local_acp_launch
            or not bridge_ready
            or not (bridge_command_configured or bridge_sandbox_auto_wiring_pending)
        ):
            payload = {
                "ok": False,
                "error_type": "SkillsBenchCodexCliGoalDriverRequired",
                "route": args.route,
                "reason": (
                    "codex-cli-goal-baseline must run the host Codex CLI TUI "
                    "with a real /goal slash command and a materialized "
                    "command/file bridge into the scored SkillsBench sandbox. "
                    "A container-local codex-acp or slash-prefix prompt would "
                    "not prove native CLI Goal mode."
                ),
                "next_action": (
                    "rerun with --host-local-acp-launch plus "
                    "--remote-command-file-bridge-ready or "
                    "--remote-command-file-bridge-probe after provisioning the "
                    "sandbox bridge, and pass "
                    "--remote-command-file-bridge-solver-command so the host "
                    "CLI goal worker can operate on the scored sandbox"
                ),
                "canonical_codex_cli_goal_driver_required": True,
                "host_local_acp_launch": bool(args.host_local_acp_launch),
                "remote_command_file_bridge_ready": bridge_ready,
                "remote_command_file_bridge_solver_command_configured": (
                    bridge_command_configured
                ),
                "remote_command_file_bridge_sandbox_auto_wiring_pending": (
                    bridge_sandbox_auto_wiring_pending
                ),
            }
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
            return 2
    if (
        args.route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE
        and not args.plan_only
        and not args.reduce_only
        and not args.setup_only_public_preflight
    ):
        bridge_ready = bool(
            args.remote_command_file_bridge_ready
            or args.remote_command_file_bridge_probe
        )
        runner_integration_ready = bool(args.host_local_acp_launch)
        if not bridge_ready:
            payload = {
                "ok": False,
                "error_type": "SkillsBenchNativeGoalWorkerBridgePending",
                "route": args.route,
                "reason": (
                    "codex-app-server-goal-baseline runs Codex on the host, but "
                    "SkillsBench task files and edits live inside the BenchFlow "
                    "sandbox. A bounded command/file bridge must be materialized "
                    "before a host app-server Goal turn can operate on the "
                    "scored workspace."
                ),
                "next_action": (
                    "materialize and probe the SkillsBench remote command/file "
                    "bridge, then wire the host app-server Goal worker into the "
                    "BenchFlow ACP transport; do not fall back to codex-acp or "
                    "a host cwd that cannot see the sandbox"
                ),
            }
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
            return 2
        if runner_integration_ready:
            args.host_local_acp_launch = True
        else:
            payload = {
                "ok": False,
                "error_type": "SkillsBenchNativeGoalWorkerIntegrationPending",
                "route": args.route,
                "reason": (
                    "codex-app-server-goal-baseline requires --host-local-acp-launch "
                    "so BenchFlow connects to the LoopX ACP relay that "
                    "delegates prompts to the host Codex app-server Goal worker; "
                    "the current runner must not fall back to codex-acp"
                ),
                "next_action": (
                    "rerun with --remote-command-file-bridge-ready and "
                    "--host-local-acp-launch after probing the command/file bridge"
                ),
            }
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
            return 2
    product_host_local_bridge_materialized = bool(
        args.remote_command_file_bridge_ready
        or args.remote_command_file_bridge_probe
    )
    product_host_local_bridge_probe_command_configured = bool(
        args.remote_command_file_bridge_probe_command
    )
    product_host_local_bridge_command_configured = bool(
        args.remote_command_file_bridge_solver_command
    )
    product_host_local_bridge_sandbox_auto_wiring_pending = bool(
        args.route in HOST_LOCAL_BRIDGE_ROUTES
        and args.host_local_acp_launch
        and product_host_local_bridge_materialized
        and not product_host_local_bridge_command_configured
    )
    if (
        _is_loopx_product_mode_route(args.route)
        and not args.host_local_acp_launch
        and not args.local_driver_worker_handshake_preflight
        and not args.plan_only
        and not args.reduce_only
        and not args.setup_only_public_preflight
    ):
        payload = {
            "ok": False,
            "error_type": "SkillsBenchProductModeCanonicalDriverRequired",
            "route": args.route,
            "reason": (
                "LoopX product-mode treatment routes must use the canonical "
                "host-local ACP lifecycle driver. A container-local codex-acp "
                "fallback can solve the task but cannot produce the required "
                "case-local quota/todo/update/refresh/spend lifecycle evidence."
            ),
            "next_action": (
                "rerun with --host-local-acp-launch and a materialized "
                "command/file bridge, or use --plan-only/--reduce-only for "
                "non-executing inspection"
            ),
            "canonical_product_mode_lifecycle_driver_required": True,
            "host_local_acp_launch": False,
            "raw_logs_recorded": False,
            "raw_task_text_read": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if payload := skillsbench_loopx_turn_launch_error(args):
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    product_host_local_bridge_fixture_solver = (
        skillsbench_remote_command_file_bridge_command_is_fixture_probe(
            args.remote_command_file_bridge_solver_command
        )
    )
    if (
        args.route in HOST_LOCAL_BRIDGE_ROUTES
        and args.host_local_acp_launch
        and product_host_local_bridge_fixture_solver
        and not args.local_driver_worker_handshake_preflight
        and not args.plan_only
        and not args.setup_only_public_preflight
    ):
        payload = {
            "ok": False,
            "error_type": "SkillsBenchReverseChannelBridgeFixtureOnlySolverCommand",
            "route": args.route,
            "reason": (
                "the configured solver bridge is the repo fixture-only probe "
                "helper. That helper validates readiness but cannot execute, "
                "read, write, or clean up inside the scored BenchFlow sandbox."
            ),
            "next_action": (
                "use a real sandbox workspace bridge or switch to the cloud-host "
                "co-located product path; do not inject the fixture probe command "
                "into the solver prompt"
            ),
            "remote_command_file_bridge_materialized": (
                product_host_local_bridge_materialized
            ),
            "remote_command_file_bridge_probe_command_configured": (
                product_host_local_bridge_probe_command_configured
            ),
            "remote_command_file_bridge_command_configured": True,
            "remote_command_file_bridge_solver_wiring_configured": False,
            "remote_command_file_bridge_consumed_by_solver": False,
            "raw_logs_recorded": False,
            "raw_task_text_read": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if (
        args.route in HOST_LOCAL_BRIDGE_ROUTES
        and args.host_local_acp_launch
        and not (
            product_host_local_bridge_materialized
            and (
                product_host_local_bridge_command_configured
                or product_host_local_bridge_sandbox_auto_wiring_pending
            )
        )
        and not args.local_driver_worker_handshake_preflight
        and not args.plan_only
        and not args.setup_only_public_preflight
    ):
        payload = {
            "ok": False,
            "error_type": "SkillsBenchReverseChannelBridgeNotSolverWired",
            "route": args.route,
            "reason": (
                "product-mode host-local ACP runs execute Codex on the host while "
                "the scored workspace lives in the BenchFlow sandbox; a materialized "
                "remote command/file bridge and its private solver command are both "
                "required before this is a countable reverse-channel treatment, unless "
                "the BenchFlow sandbox docker bridge can be generated after environment "
                "materialization"
            ),
            "next_action": (
                "wire the remote command/file bridge into the solver worker or "
                "use a route whose compact public trace proves nonzero bridge "
                "read/write during the agent turn before launching a scored case"
            ),
            "remote_command_file_bridge_materialized": (
                product_host_local_bridge_materialized
            ),
            "remote_command_file_bridge_probe_command_configured": (
                product_host_local_bridge_probe_command_configured
            ),
            "remote_command_file_bridge_command_configured": (
                product_host_local_bridge_command_configured
            ),
            "remote_command_file_bridge_solver_wiring_configured": False,
            "remote_command_file_bridge_consumed_by_solver": False,
            "raw_logs_recorded": False,
            "raw_task_text_read": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if args.local_codex_participant_ping:
        payload = codex_runtime.materialize_local_codex_participant(
            codex_bin=args.local_codex_bin,
            timeout_sec=args.local_codex_ping_timeout_sec,
        )
        print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
        return 0 if payload.get("codex_cli_invoked") is True else 1
    if args.local_driver_worker_handshake_preflight:
        ensure_skillsbench_dependency_python(args)
        payload = inspect_skillsbench_worker_handshake(
            skillsbench_root=args.skillsbench_root,
            dataset=args.dataset,
            task_id=args.task_id,
            local_codex_cli_participant_ready=args.local_codex_cli_participant_ready,
            local_acp_relay_command=args.local_acp_relay_command,
            probe_local_acp_relay=args.local_acp_relay_probe,
            local_acp_relay_probe_timeout_sec=args.local_acp_relay_probe_timeout_sec,
            probe_host_local_acp_transport=args.host_local_acp_transport_probe,
            host_local_acp_transport_probe_timeout_sec=(
                args.host_local_acp_transport_probe_timeout_sec
            ),
            probe_remote_command_file_bridge=args.remote_command_file_bridge_probe,
            remote_command_file_bridge_probe_command=(
                args.remote_command_file_bridge_probe_command
            ),
            remote_command_file_bridge_probe_timeout_sec=(
                args.remote_command_file_bridge_probe_timeout_sec
            ),
            remote_command_file_bridge_ready=args.remote_command_file_bridge_ready,
            remote_executor_ready=True,
            remote_task_data_ready=True,
        )
        print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
        return 0
    task_ids = _batch_task_ids(args)
    batch_mode = len(task_ids) > 1
    independent_retry_mode = _independent_goal_retry_enabled(args) and not args.plan_only
    if args.run_group_id is None:
        args.run_group_id = (
            f"skillsbench-batch-{args.route}-{_now_stamp()}"
            if batch_mode
            else f"skillsbench-{args.task_id}-{args.route}-independent-retry-{_now_stamp()}"
            if independent_retry_mode
            else f"skillsbench-{args.task_id}-{args.route}-{_now_stamp()}"
        )
    plan = None if batch_mode or independent_retry_mode else build_plan(args)
    previous_sigterm_handler = signal.getsignal(signal.SIGTERM)

    def _closeout_sigterm_handler(signum: int, frame: Any) -> None:
        raise SkillsBenchRunnerInterrupted(
            "skillsbench_runner_received_sigterm_before_official_result"
        )

    signal.signal(signal.SIGTERM, _closeout_sigterm_handler)
    try:
        if batch_mode:
            payload = asyncio.run(async_batch_main(args, task_ids=task_ids))
        elif independent_retry_mode:
            payload = asyncio.run(async_independent_goal_retry_main(args))
        else:
            payload = asyncio.run(async_main(args, plan=plan))
    except (KeyboardInterrupt, SkillsBenchRunnerInterrupted) as exc:
        if plan is None:
            if independent_retry_mode:
                payload = {
                    "ok": False,
                    "independent_goal_retry": True,
                    "task_id": str(args.task_id),
                    "route": str(args.route),
                    "attempt_budget": int(args.independent_goal_retries),
                    "run_group_id": args.run_group_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "compact_closeout_recorded": False,
                }
                print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
                return 1
            payload = {
                "ok": False,
                "batch": True,
                "task_count": len(task_ids),
                "parallel_cases": min(
                    max(1, int(args.parallel_cases or 1)),
                    len(task_ids),
                ),
                "run_group_id": args.run_group_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "compact_closeout_recorded": False,
            }
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
            return 1
        payload, returncode = _build_runner_exception_closeout_payload(
            args, plan, exc
        )
        output_stream = (
            sys.stdout
            if payload.get("recovered_after_runner_exception") is True
            else sys.stderr
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=output_stream)
        return returncode
    except Exception as exc:
        if plan is None:
            if independent_retry_mode:
                payload = {
                    "ok": False,
                    "independent_goal_retry": True,
                    "task_id": str(args.task_id),
                    "route": str(args.route),
                    "attempt_budget": int(args.independent_goal_retries),
                    "run_group_id": args.run_group_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "compact_closeout_recorded": False,
                }
                print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
                return 1
            payload = {
                "ok": False,
                "batch": True,
                "task_count": len(task_ids),
                "parallel_cases": min(
                    max(1, int(args.parallel_cases or 1)),
                    len(task_ids),
                ),
                "run_group_id": args.run_group_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "compact_closeout_recorded": False,
            }
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
            return 1
        payload, returncode = _build_runner_exception_closeout_payload(
            args, plan, exc
        )
        output_stream = (
            sys.stdout
            if payload.get("recovered_after_runner_exception") is True
            else sys.stderr
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=output_stream)
        return returncode
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)
    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
    return int(payload.get("runner_returncode") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
