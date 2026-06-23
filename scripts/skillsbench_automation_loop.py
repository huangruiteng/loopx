#!/usr/bin/env python3
"""Run one SkillsBench task through the compact SkillsBench runner bridge.

This is a thin launcher around the official SkillsBench/BenchFlow runner.  It
keeps task execution and verification inside BenchFlow, then reduces only the
official result/timing files into ``benchmark_run_v0``.

The ``codex-app-server-goal-baseline`` route is the native Codex Goal baseline
surface. The comparable LoopX test route is
``loopx-prompt-polling-test``: it uses BenchFlow's ``BaseUser``
progressive-disclosure hook as the outer LoopX polling controller
without forwarding official reward, pass/fail, verifier errors, or verifier
output back to the agent:

- round 0 sends the task instruction with a LoopX controller header;
- later rounds are scheduled continuations that explicitly say they are not
  evidence of verifier success or failure;
- public closeout reads only official ``result.json`` and ``timing.json``.

The historical ``loopx-blind-loop-treatment`` route is kept as an alias
for existing SkillsBench rows that used the same no-feedback polling semantics.
The ``codex-acp-blind-loop-baseline`` route uses the same no-reward loop budget
with an ordinary Codex prompt and no LoopX controller semantics. The
older ``automation-loop-treatment`` route intentionally forwards failed-reward
feedback and is kept only as a reward-feedback ablation.

For the ``codex-goal-mode-baseline`` route it uses BenchFlow's user hook only
to request a slash-goal-style initial prompt, with no reward follow-up, no Goal
Harness controller state, and no verifier feedback. This is not sufficient by
itself to prove native Codex CLI goal mode; that requires separate CLI
slash-command/goal-state evidence. Full execution of this route is blocked by
default until that evidence exists; use it only for explicit slash-prefix
experiments.

The native Goal baseline requires a host-side Codex app-server worker using
``thread/start``, ``thread/goal/set``, ``thread/goal/get``, and ``turn/start``.
Until the BenchFlow worker integration is wired, full execution fails closed;
``--plan-only`` still emits the public-safe launch contract.

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
import asyncio
import contextlib
import importlib
import inspect
import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from loopx.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LOOPX_AGENT_ID,
    BENCHMARK_CASE_LOOPX_TODO_ID,
    BENCHMARK_CASE_LOOPX_SOURCE_MOUNT_TARGET,
    benchmark_case_loopx_command_prefix,
    benchmark_case_loopx_install_payload,
    benchmark_case_active_state_path,
    benchmark_case_active_state_seed_text,
    benchmark_case_active_state_write_command,
)
from loopx.benchmark_adapters.skillsbench import (  # noqa: E402
    build_skillsbench_app_server_goal_worker_contract,
    build_skillsbench_run_permission_policy,
    build_skillsbench_worker_handshake_preflight,
)
from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    default_skillsbench_local_acp_relay_command,
    run_skillsbench_host_local_acp_transport_probe,
    run_skillsbench_local_acp_relay_probe,
)
from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    run_skillsbench_remote_command_file_bridge_probe,
    skillsbench_remote_command_file_bridge_command_is_fixture_probe,
)
from loopx.benchmark_core.loop_protocol import (  # noqa: E402
    AUTOMATION_LOOP_TREATMENT_ROUTE,
    BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
    CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
    LOOPX_PRODUCT_MODE_ROUTE,
    LOOPX_PROMPT_POLLING_TEST_ROUTE,
    RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
    build_benchmark_loop_controller_trace,
    build_blind_loop_continuation_prompt,
    build_blind_loop_initial_prompt,
)
from loopx.benchmark_trajectory import summarize_public_acp_trajectory

DEFAULT_SKILLSBENCH_ROOT = REPO_ROOT / ".local/benchmark/externals/skillsbench"
DEFAULT_LEDGER = (
    REPO_ROOT
    / "docs/research/long-horizon-agent-benchmarks/benchmark-run-ledger.json"
)
DEFAULT_GOAL_ID = "loopx-meta"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_TIMEOUT_SEC = 7200
DEFAULT_VERIFIER_PREP_TIMEOUT_SEC = 120
DEFAULT_PRODUCT_MODE_SOFT_VERIFY_POLICY = "final-only"
DEFAULT_MAX_ROUNDS = 8
_MISSING = object()
SUPPORTED_ROUTES = (
    CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
    LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
    LOOPX_PROMPT_POLLING_TEST_ROUTE,
    RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
    LOOPX_PRODUCT_MODE_ROUTE,
    CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
    "codex-goal-mode-baseline",
    AUTOMATION_LOOP_TREATMENT_ROUTE,
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


def product_mode_soft_verify_policy_for_route(
    route: str,
    requested_policy: str,
) -> str:
    if route in {"raw-codex-autonomous-max5", "loopx-product-mode"}:
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


DOCKER_APP_SKILLS_MOUNT_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_APP_SKILLS_MOUNT"
DOCKER_APP_SKILLS_MOUNT_END = "# END LOOPX_SKILLSBENCH_APP_SKILLS_MOUNT"
DOCKER_APT_RETRY_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_APT_RETRY"
DOCKER_APT_RETRY_END = "# END LOOPX_SKILLSBENCH_APT_RETRY"
DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_CODEX_ACP_RUNTIME_TOOLS"
)
DOCKER_CODEX_ACP_RUNTIME_TOOLS_END = (
    "# END LOOPX_SKILLSBENCH_CODEX_ACP_RUNTIME_TOOLS"
)
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
    if not venv_python.exists() or _same_executable(venv_python, current_python):
        raise
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


def materialize_local_codex_participant(
    *,
    codex_bin: str = "codex",
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """Run a fixed local Codex CLI ping and return a compact materialization proof.

    This proves only the local CLI participant. It does not claim that the
    SkillsBench A2A/worker handshake is wired, and it deliberately drops raw
    JSONL events, stderr, prompts, paths, and credentials.
    """

    resolved = shutil.which(codex_bin) if os.sep not in codex_bin else codex_bin
    if not resolved or (os.sep in str(resolved) and not Path(resolved).exists()):
        return {
            "schema_version": LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
            "ready": False,
            "first_blocker": "local_codex_cli_not_on_path",
            "codex_cli_available": False,
            "codex_cli_invoked": False,
            "raw_output_recorded": False,
            "raw_event_jsonl_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "a2a_worker_handshake_ready": False,
        }

    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-codex-") as tmp:
        tmpdir = Path(tmp)
        output_path = tmpdir / "last-message.txt"
        prompt = (
            "Respond with exactly this single line and nothing else: "
            f"{LOCAL_CODEX_PARTICIPANT_READY_MARKER}"
        )
        cmd = [
            resolved,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-C",
            str(tmpdir),
            "--output-last-message",
            str(output_path),
            "--json",
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "schema_version": LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
                "ready": False,
                "first_blocker": "local_codex_cli_participant_timeout",
                "codex_cli_available": True,
                "codex_cli_invoked": True,
                "exit_code": None,
                "timeout_sec": timeout_sec,
                "stdout_len_bucket": _compact_size_bucket(
                    len(exc.stdout or "")
                    if isinstance(exc.stdout, str)
                    else len(exc.stdout or b"")
                ),
                "stderr_len_bucket": _compact_size_bucket(
                    len(exc.stderr or "")
                    if isinstance(exc.stderr, str)
                    else len(exc.stderr or b"")
                ),
                "raw_output_recorded": False,
                "raw_event_jsonl_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "a2a_worker_handshake_ready": False,
            }

        marker = ""
        if output_path.exists():
            try:
                marker = output_path.read_text(encoding="utf-8").strip()
            except OSError:
                marker = ""
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        event_count = len([line for line in stdout.splitlines() if line.strip()])
        ready = proc.returncode == 0 and marker == LOCAL_CODEX_PARTICIPANT_READY_MARKER
        if ready:
            first_blocker = "local_codex_cli_participant_ready"
        elif proc.returncode != 0:
            first_blocker = "local_codex_cli_participant_exit_nonzero"
        else:
            first_blocker = "local_codex_cli_participant_marker_missing"
        return {
            "schema_version": LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
            "ready": ready,
            "first_blocker": first_blocker,
            "codex_cli_available": True,
            "codex_cli_invoked": True,
            "exit_code": proc.returncode,
            "marker_matched": marker == LOCAL_CODEX_PARTICIPANT_READY_MARKER,
            "json_event_count": event_count,
            "stdout_len_bucket": _compact_size_bucket(len(stdout)),
            "stderr_len_bucket": _compact_size_bucket(len(stderr)),
            "raw_output_recorded": False,
            "raw_event_jsonl_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "a2a_worker_handshake_ready": False,
            "next_blocker_after_ready": (
                "skillsbench_local_acp_relay_missing"
                if ready
                else first_blocker
            ),
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
    if args.route == "codex-app-server-goal-baseline":
        worker_trace_dir = str(plan.get("app_server_goal_worker_trace_dir") or "")
        command.extend(
            [
                "--app-server-goal-worker",
                "--approval-policy",
                "never",
                "--reasoning-effort",
                args.app_server_reasoning_effort,
                "--response-timeout-sec",
                "30",
                "--stream-heartbeat-interval-sec",
                str(args.app_server_acp_heartbeat_interval_sec),
            ]
        )
        if worker_trace_dir:
            command.extend(["--worker-public-trace-dir", worker_trace_dir])
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
            "--codex-bin",
            args.local_codex_bin,
            "--sandbox",
            args.local_codex_sandbox,
            "--timeout-sec",
            str(args.local_codex_exec_timeout_sec),
        ]
    )
    if args.model:
        command.extend(["--model", args.model])
    if (
        args.route in {"raw-codex-autonomous-max5", "loopx-product-mode"}
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
    return command


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
        args.route == LOOPX_PRODUCT_MODE_ROUTE
        and args.sandbox == "docker"
        and not disabled
        and source_dir is not None
    )
    ready = bool(
        requested
        and source_dir is not None
        and (source_dir / "scripts" / "install-local.sh").exists()
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
        "codex_app_server_goal_worker_plan_schema",
        "benchflow_user_loop_recovery_exception_type",
        "benchflow_user_loop_recovery_stage",
        "benchflow_intermediate_soft_verify_policy",
        "benchflow_setup_stall_cleanup_status",
        "remote_command_file_bridge_consumption_status",
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
        "container_codex_acp_install_skipped",
        "benchflow_agent_install_skipped_by_runtime_layer",
        "remote_command_file_bridge_materialized",
        "remote_command_file_bridge_command_configured",
        "remote_command_file_bridge_probe_command_configured",
        "remote_command_file_bridge_solver_wiring_configured",
        "remote_command_file_bridge_consumed_by_solver",
        "remote_command_file_bridge_solver_trace_dir_present",
        "remote_command_file_bridge_solver_public_trace_read",
        "remote_command_file_bridge_solver_raw_material_recorded",
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
        "benchflow_intermediate_soft_verify_final_only",
        "benchflow_intermediate_soft_verify_raw_output_recorded",
        "benchflow_verifier_prep_timeout_override_enabled",
        "benchflow_verifier_prep_timeout_raw_command_recorded",
        "benchflow_final_verifier_timeout_enabled",
        "benchflow_final_verifier_timeout_triggered",
        "benchflow_final_verifier_timeout_raw_command_recorded",
        "benchflow_final_verifier_timeout_raw_output_recorded",
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
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "codex_acp_runtime_launch_preflight_rc",
        "benchflow_agent_timeout_original_sec",
        "benchflow_agent_timeout_effective_sec",
        "benchflow_user_loop_recovery_round",
        "benchflow_user_loop_recovery_delta_events",
        "benchflow_user_loop_recovery_delta_tool_calls",
        "benchflow_intermediate_soft_verify_call_count",
        "benchflow_intermediate_soft_verify_skipped_count",
        "benchflow_verifier_prep_timeout_sec",
        "benchflow_final_verifier_timeout_sec",
        "benchflow_final_verifier_timeout_override_count",
        "benchflow_verifier_prep_timeout_override_count",
        "benchflow_verify_prep_timeout_override_count",
        "benchflow_soft_verify_prep_timeout_override_count",
        "benchflow_setup_stall_timeout_sec",
        "benchflow_setup_stall_cleanup_match_count",
        "benchflow_setup_stall_cleanup_term_sent_count",
        "benchflow_setup_stall_cleanup_kill_sent_count",
        "benchflow_setup_stall_cleanup_alive_after_count",
        "remote_command_file_bridge_solver_trace_count",
        "remote_command_file_bridge_solver_probe_ready_count",
        "remote_command_file_bridge_solver_operation_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
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


def install_benchflow_verifier_prep_timeout_override(
    rollout_cls: Any,
    *,
    timeout_sec: int,
    final_verifier_timeout_sec: int = 0,
    plan: dict[str, Any],
    trace: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Raise verifier prep timeouts and optionally bound final official verify."""

    original_verify = rollout_cls.verify
    original_soft_verify = rollout_cls.soft_verify
    prerequisites = plan.setdefault("runner_prerequisites", {})
    enabled = timeout_sec > 10
    final_timeout_enabled = final_verifier_timeout_sec > 0
    prerequisites["benchflow_verifier_prep_timeout_override_enabled"] = enabled
    prerequisites["benchflow_verifier_prep_timeout_raw_command_recorded"] = False
    prerequisites["benchflow_final_verifier_timeout_enabled"] = final_timeout_enabled
    prerequisites["benchflow_final_verifier_timeout_raw_command_recorded"] = False
    if enabled:
        prerequisites["benchflow_verifier_prep_timeout_sec"] = timeout_sec
    if final_timeout_enabled:
        prerequisites["benchflow_final_verifier_timeout_sec"] = (
            final_verifier_timeout_sec
        )
    if isinstance(trace, dict):
        trace["benchflow_verifier_prep_timeout_override_enabled"] = enabled
        trace["benchflow_verifier_prep_timeout_raw_command_recorded"] = False
        trace["benchflow_final_verifier_timeout_enabled"] = final_timeout_enabled
        trace["benchflow_final_verifier_timeout_raw_command_recorded"] = False
        if enabled:
            trace["benchflow_verifier_prep_timeout_sec"] = timeout_sec
        if final_timeout_enabled:
            trace["benchflow_final_verifier_timeout_sec"] = final_verifier_timeout_sec

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
        if not enabled and not final_timeout_enabled:
            return await original(self)

        env = getattr(self, "_env", None)
        original_exec = getattr(env, "exec", None) if env is not None else None
        if original_exec is None:
            return await original(self)

        override_count = 0
        final_timeout_override_count = 0

        async def exec_with_verifier_prep_timeout(*args: Any, **kwargs: Any) -> Any:
            nonlocal override_count, final_timeout_override_count
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
                if (
                    not isinstance(current_timeout, (int, float))
                    or current_timeout <= 0
                    or current_timeout > final_verifier_timeout_sec
                ):
                    kwargs = dict(kwargs)
                    kwargs["timeout_sec"] = final_verifier_timeout_sec
                    final_timeout_override_count += 1
            return await original_exec(*args, **kwargs)

        try:
            env.exec = exec_with_verifier_prep_timeout
            return await original(self)
        except Exception as exc:
            if final_timeout_override_count and _runner_exception_indicates_timeout(exc):
                prerequisites["benchflow_final_verifier_timeout_triggered"] = True
                prerequisites["benchflow_final_verifier_timeout_raw_output_recorded"] = (
                    False
                )
                if isinstance(trace, dict):
                    trace["benchflow_final_verifier_timeout_triggered"] = True
                    trace["benchflow_final_verifier_timeout_raw_output_recorded"] = (
                        False
                    )
            raise
        finally:
            env.exec = original_exec
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
                _mark_user_loop_final_verify_recovery(
                    plan=plan,
                    trace=trace,
                    stage="soft_verify",
                    round_num=round_num,
                    exception=exc,
                    delta_events=len(round_trajectory),
                    delta_tool_calls=round_tools,
                )
                rounds_log.append(
                    {
                        "round": round_num,
                        "rewards": None,
                        "verifier_error": "public_safe_soft_verify_exception_after_agent_round",
                        "soft_verify_policy": intermediate_soft_verify_policy,
                        "soft_verify_skipped": False,
                        "n_tool_calls": round_tools,
                        "n_trajectory_events": len(round_trajectory),
                    }
                )
                break
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

    if value.get("benchflow_final_verifier_timeout_triggered") is True:
        label = "skillsbench_final_verifier_timeout"
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

    if value.get("host_local_acp_launch_status") == "failed":
        label = "skillsbench_host_local_acp_launch_failed"
        return label, label, [label, "skillsbench_runner_setup_error"]

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
    text = f"{type(exc).__name__} {exc}".lower()
    return "timeout" in text or "timed out" in text


def _ensure_setup_stall_timeout_prerequisites(
    args: argparse.Namespace,
    plan: dict[str, Any],
    exc: BaseException,
    *,
    cleanup_if_missing: bool,
) -> None:
    """Backfill public setup-stall evidence when BenchFlow times out pre-agent."""

    build_stall_timeout_sec = int(args.build_stall_timeout_sec or 0)
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

    label = "skillsbench_acp_agent_message_only_no_tool_calls"
    current_attribution = str(compact.get("score_failure_attribution") or "")
    preserve_attributions = {
        "skillsbench_codex_acp_provider_zero_activity",
    }
    if current_attribution not in preserve_attributions:
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
    if current_attribution not in preserve_attributions:
        extra_labels.append("skillsbench_agent_behavior_gap")
    for item in extra_labels:
        if item not in existing_labels:
            existing_labels.append(item)
    compact["failure_attribution_labels"] = existing_labels
    return True


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
        "app_skills_mount_patch_applied",
        "apt_retry_patch_applied",
        "apt_risk_preflight_blocked",
        "codex_acp_runtime_tools_patch_applied",
        "task_skills_removed",
        "original_task_mutated",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
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
    include_task_skills = bool(plan.get("include_task_skills"))
    return {
        "schema_version": "skillsbench_task_staging_v0",
        "staged": True,
        "include_task_skills": include_task_skills,
        "app_skills_mount_patch_applied": (
            DOCKER_APP_SKILLS_MOUNT_BEGIN in dockerfile_text
        ),
        "apt_retry_patch_applied": DOCKER_APT_RETRY_BEGIN in dockerfile_text,
        "codex_acp_runtime_tools_patch_applied": (
            DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN in dockerfile_text
        ),
        "task_skills_removed": (
            not include_task_skills
            and not (prepared_task / "environment" / "skills").exists()
        ),
        "original_task_mutated": False,
    }


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
    for field in ("schema_version", "status", "sandbox", "selection_recommendation"):
        raw = value.get(field)
        if isinstance(raw, str) and raw:
            compact[field] = raw[:180]
    for field in (
        "raw_task_text_read",
        "raw_logs_read",
        "raw_trajectory_read",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_present",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    return compact


def _public_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


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
    block = (
        f"{DOCKER_APP_SKILLS_MOUNT_BEGIN}\n"
        "RUN mkdir -p /app /app/skills\n"
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


def skillsbench_task_setup_preflight(
    *,
    task_path: Path,
    sandbox: str,
) -> dict[str, Any]:
    """Return public-safe setup-shape facts before spending a full run."""

    preflight: dict[str, Any] = {
        "schema_version": "skillsbench_task_setup_preflight_v0",
        "sandbox": sandbox,
        "raw_task_text_read": False,
        "raw_logs_read": False,
        "raw_trajectory_read": False,
        "apt_setup_risk_detected": False,
        "apt_retry_patch_required": False,
    }
    if sandbox != "docker":
        preflight["status"] = "not_applicable"
        return preflight

    dockerfile = task_path.expanduser() / "environment" / "Dockerfile"
    dockerfile_exists = dockerfile.exists()
    preflight["dockerfile_present"] = dockerfile_exists
    if not dockerfile_exists:
        preflight["status"] = "no_dockerfile"
        return preflight

    apt_risk = dockerfile_needs_apt_retry_patch(dockerfile)
    preflight.update(
        {
            "status": "apt_risk_detected" if apt_risk else "ok",
            "apt_setup_risk_detected": apt_risk,
            "apt_retry_patch_required": apt_risk,
            "selection_recommendation": (
                "route_to_setup_repair_or_use_fail_fast_guard"
                if apt_risk
                else "eligible_for_full_pair"
            ),
        }
    )
    return preflight


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
        "    mkdir -p /etc/apt/apt.conf.d; \\\n"
        "    printf '%s\\n' \\\n"
        "      'Acquire::Retries \"5\";' \\\n"
        "      'Acquire::http::No-Cache \"true\";' \\\n"
        "      'Acquire::https::No-Cache \"true\";' \\\n"
        "      'Acquire::Check-Valid-Until \"false\";' \\\n"
        "      > /etc/apt/apt.conf.d/80-loopx-retry; \\\n"
        "    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb\n"
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


def stage_task_for_sandbox(
    *,
    task_path: Path,
    jobs_dir: Path,
    job_name: str,
    sandbox: str,
    include_task_skills: bool = True,
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
        "codex_acp_runtime_tools_patch_applied": False,
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
    needs_runtime_tools_patch = (task_path / "environment" / "Dockerfile").exists()
    metadata["apt_setup_risk_detected"] = needs_apt_retry_patch
    metadata["apt_retry_patch_required"] = needs_apt_retry_patch
    metadata["apt_risk_preflight_blocked"] = False
    if (
        not has_task_skills
        and not needs_resource_cap
        and not needs_apt_retry_patch
        and not needs_runtime_tools_patch
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
    patched = patch_dockerfile_app_skills_mount(
        staged_path / "environment" / "Dockerfile"
    )
    apt_retry_patched = patch_dockerfile_apt_retry(
        staged_path / "environment" / "Dockerfile"
    )
    runtime_tools_patched = patch_dockerfile_codex_acp_runtime_tools(
        staged_path / "environment" / "Dockerfile"
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
            "codex_acp_runtime_tools_patch_applied": runtime_tools_patched,
            "app_skills_mount_target": "/app/skills",
            "original_task_mutated": False,
            "task_skills_removed": task_skills_removed,
            "resource_cap_patch": resource_cap_patch,
        }
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
    if route == LOOPX_PROMPT_POLLING_TEST_ROUTE:
        rollout_suffix = "loopx_prompt_polling_test"
    elif route == LOOPX_BLIND_LOOP_TREATMENT_ROUTE:
        rollout_suffix = "loopx_blind_loop"
    elif route == "loopx-product-mode":
        rollout_suffix = "loopx_product_mode"
    elif route == "raw-codex-autonomous-max5":
        rollout_suffix = "raw_codex_autonomous_max5"
    elif route == "codex-acp-blind-loop-baseline":
        rollout_suffix = "codex_acp_blind_loop"
    elif route == "codex-app-server-goal-baseline":
        rollout_suffix = "codex_app_server_goal"
    elif route == "automation-loop-treatment":
        rollout_suffix = "loopx_reward_feedback_ablation"
    else:
        rollout_suffix = route_slug
    rollout_name = args.rollout_name or f"{task_id}__{rollout_suffix}"
    jobs_dir = Path(args.jobs_dir).expanduser()
    result_path = jobs_dir / job_name / rollout_name / "result.json"
    compact_path = jobs_dir / job_name / rollout_name / "benchmark_run.compact.json"
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
    requires_preinstalled_runtime = bool(agent_runtime_layer.get("required"))
    is_app_server_goal_route = route == "codex-app-server-goal-baseline"
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
    remote_command_file_bridge_solver_wiring_configured = bool(
        args.host_local_acp_launch
        and route in {"raw-codex-autonomous-max5", "loopx-product-mode"}
        and remote_command_file_bridge_materialized
        and remote_command_file_bridge_solver_command_configured
    )
    remote_command_file_bridge_consumed_by_solver = False
    if remote_command_file_bridge_solver_wiring_configured:
        remote_command_file_bridge_consumption_status = (
            "solver_wiring_configured_pending_prompt"
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
            reasoning_effort=args.app_server_reasoning_effort,
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
    launch_plan = {
        "schema_version": "skillsbench_runner_launch_plan_v0",
        "benchmark_id": args.dataset,
        "task_id": task_id,
        "route": route,
        "agent": (
            "codex-app-server-goal"
            if is_app_server_goal_route
            else "codex-acp"
        ),
        "model": args.model,
        "sandbox": args.sandbox,
        "max_rounds": args.max_rounds,
        "treatment_prompt_style": args.treatment_prompt_style,
        "outer_timeout_sec": args.outer_timeout_sec,
        "sandbox_setup_timeout_sec": args.sandbox_setup_timeout,
        "agent_idle_timeout_sec": args.agent_idle_timeout,
        "include_task_skills": bool(args.include_task_skills),
        "host_local_acp_launch": bool(args.host_local_acp_launch),
        "remote_command_file_bridge_ready": bool(
            remote_command_file_bridge_materialized
        ),
        "benchflow_agent_runtime_layer": agent_runtime_layer,
        "loopx_source_mount": loopx_source_mount,
        "skillsbench_root": str(Path(args.skillsbench_root).expanduser()),
        "jobs_dir": str(jobs_dir),
        "job_name": job_name,
        "rollout_name": rollout_name,
        "result_json": str(result_path),
        "compact_benchmark_run_json": str(compact_path),
        "controller_trace_json": str(controller_trace_path),
        "build_stall_timeout_sec": int(args.build_stall_timeout_sec or 0),
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
        "run_permission_policy": run_permission_policy,
        "task_setup_preflight": setup_preflight,
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
            "apt_risk_preflight_blocked": False,
        },
        "runner_prerequisites": {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "benchflow_setup_stall_timeout_enabled": (
                int(args.build_stall_timeout_sec or 0) > 0
            ),
            "benchflow_setup_stall_timeout_sec": int(
                args.build_stall_timeout_sec or 0
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
            "container_codex_acp_install_skipped": (
                True if is_app_server_goal_route else requires_preinstalled_runtime
            ),
            "benchflow_agent_install_skipped_by_runtime_layer": (
                True if is_app_server_goal_route else requires_preinstalled_runtime
            ),
            "remote_command_file_bridge_materialized": bool(
                remote_command_file_bridge_materialized
            ),
            "remote_command_file_bridge_command_configured": bool(
                remote_command_file_bridge_solver_command_configured
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
            "benchflow_final_verifier_timeout_enabled": (
                int(args.final_verifier_timeout_sec or 0) > 0
            ),
            "benchflow_final_verifier_timeout_raw_command_recorded": False,
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


async def run_benchflow_case_with_private_output(
    args: argparse.Namespace,
    plan: dict[str, Any],
) -> Path:
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
    trace.update(
        {
        "case_goal_state_packet_present": False,
        "case_goal_state_init_required": route == LOOPX_PRODUCT_MODE_ROUTE,
        "case_goal_state_initialized_before_agent": False,
        "case_goal_state_init_status": "not_applicable",
        "case_goal_state_path": (
            PRODUCT_MODE_CASE_STATE_PATH
            if route == LOOPX_PRODUCT_MODE_ROUTE
            else ""
        ),
        "case_goal_state_schema_version": (
            PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION
            if route == LOOPX_PRODUCT_MODE_ROUTE
            else ""
        ),
        "declared_done_requires_no_remaining_goals": route
        == LOOPX_PRODUCT_MODE_ROUTE,
        "agent_declared_done": False,
        "agent_declared_no_remaining_goals": False,
        "declared_done_round": None,
        "declared_done_score": None,
        "loopx_state_reads": 0,
        "loopx_state_writes": 0,
        "loopx_case_state_reads": 0,
        "loopx_case_state_writes": 0,
        "native_goal_worker_route": route == CODEX_APP_SERVER_GOAL_BASELINE_ROUTE,
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
    goal_get_count = 0
    turn_start_count = 0
    turn_completed_count = 0
    assistant_message_count = 0
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
        turn = payload.get("turn") if isinstance(payload.get("turn"), dict) else {}
        if turn.get("goal_get_present") is True:
            goal_get_count += 1
        if turn.get("turn_id_present") is True:
            turn_start_count += 1
        if turn.get("turn_completed_observed") is True:
            turn_completed_count += 1
        if turn.get("assistant_message_present") is True:
            assistant_message_count += 1
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
    trace["native_goal_worker_route"] = plan.get("route") == "codex-app-server-goal-baseline"
    trace["native_goal_worker_trace_dir_present"] = trace_dir.exists()
    trace["native_goal_worker_trace_count"] = worker_trace_count
    trace["native_goal_worker_lifecycle_trace_count"] = lifecycle_trace_count
    trace["native_goal_worker_prompt_received_count"] = prompt_received_count
    trace["native_goal_worker_ok_count"] = ok_count
    trace["native_goal_worker_goal_get_count"] = goal_get_count
    trace["native_goal_worker_turn_start_count"] = turn_start_count
    trace["native_goal_worker_turn_completed_observed_count"] = turn_completed_count
    trace["native_goal_worker_assistant_message_present_count"] = (
        assistant_message_count
    )
    trace["native_goal_worker_public_trace_read"] = worker_trace_count > 0
    trace["native_goal_worker_raw_material_recorded"] = raw_material_recorded
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
        return
    trace_dir = Path(raw_trace_dir)
    files = sorted(trace_dir.glob("*.compact.json")) if trace_dir.exists() else []
    solver_trace_count = 0
    probe_ready_count = 0
    operation_count = 0
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
            != "skillsbench_host_local_acp_relay_public_trace_v0"
        ):
            continue
        if payload.get("trace_kind") != "remote_command_file_bridge_solver_consumption":
            continue
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
    consumed_by_solver = solver_trace_count > 0 and probe_ready_count > 0
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
    prerequisites = plan.setdefault("runner_prerequisites", {})
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
    if consumed_by_solver:
        prerequisites["remote_command_file_bridge_consumption_status"] = (
            "solver_prompt_probe_ready"
        )
        trace["last_decision"] = "remote_command_file_bridge_solver_trace_recorded"
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


def _round_result_declared_done(round_result: Any) -> bool:
    trajectory = getattr(round_result, "trajectory", None)
    if not isinstance(trajectory, list):
        return False
    return any(DECLARED_DONE_MARKER in text for text in _trajectory_text_fragments(trajectory))


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


def _product_mode_depth_gate_satisfied(trace: dict[str, Any]) -> bool:
    def count(*fields: str) -> int:
        values = [
            trace.get(field)
            for field in fields
            if isinstance(trace.get(field), int)
            and not isinstance(trace.get(field), bool)
        ]
        return max(values, default=0)

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


def _build_controller_user(max_output_chars: int, trace: dict[str, Any]):
    from benchflow.sandbox.user import BaseUser, RoundResult

    class GoalHarnessAutomationUser(BaseUser):
        """Private scheduler-side user for one SkillsBench task."""

        async def run(
            self,
            round: int,
            instruction: str,
            round_result: RoundResult | None = None,
        ) -> str | None:
            _inc_counter(trace, "heartbeat_count")
            trace["max_round_observed"] = max(int(trace.get("max_round_observed", -1)), round)
            if round == 0:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "initial_prompt_count")
                trace["last_decision"] = "send_initial_controller_prompt"
                return (
                    "LoopX automation-loop round 1. "
                    "You are running inside the official SkillsBench sandbox. "
                    "Solve the benchmark task using ordinary Codex agent behavior; "
                    "do not invoke /goal mode, external LoopX CLI, upload, "
                    "submit, or ask the human for routine execution choices. "
                    "Inspect the workspace, implement the fix, and run local "
                    "validation before finishing.\n\n"
                    "--- TASK INSTRUCTION ---\n"
                    f"{instruction}"
                )

            reward = _record_round_reward(
                trace,
                agent_round=round,
                round_result=round_result,
            )
            if reward is not None and reward >= 1.0:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = "stop_after_official_reward_pass"
                return None

            verifier_error = (
                round_result.verifier_error if round_result else None
            ) or "none"
            if round_result and (round_result.verifier_error or round_result.verifier_output):
                _inc_counter(trace, "verifier_feedback_observation_count")
            verifier_tail = _tail(
                round_result.verifier_output if round_result else None,
                limit=max_output_chars,
            )
            feedback = [
                f"previous_reward={reward if reward is not None else 'missing'}",
                f"previous_verifier_error={verifier_error}",
                f"previous_tool_calls={round_result.n_tool_calls if round_result else 0}",
            ]
            if verifier_tail:
                feedback.append("private_verifier_output_tail:\n" + verifier_tail)
            _inc_counter(trace, "controller_action_decisions")
            _inc_counter(trace, "followup_prompt_count")
            trace["last_decision"] = "send_followup_after_failed_reward"
            return (
                f"LoopX automation-loop follow-up round {round + 1}. "
                "The previous attempt did not pass the verifier. Continue in the "
                "same workspace, read /app/instruction.md if needed, inspect the "
                "failure, make the smallest correct fix, and rerun validation. "
                "Do not ask the human unless protected material or credentials are "
                "required.\n\n"
                + "\n".join(feedback)
            )

    return GoalHarnessAutomationUser()


def _build_blind_loop_user(
    *,
    route: str,
    max_rounds: int,
    trace: dict[str, Any],
    treatment_prompt_style: str = "structured",
):
    from benchflow.sandbox.user import BaseUser, RoundResult

    class BlindLoopUser(BaseUser):
        """Scheduler-side user that withholds official verifier feedback.

        The default budget is five scheduled agent rounds, but the loop stops
        early as soon as official scoring reaches the pass threshold. That
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
                    treatment_prompt_style=treatment_prompt_style,
                    benchmark_surface="official SkillsBench sandbox",
                )

            _inc_counter(trace, "controller_action_decisions")
            _inc_counter(trace, "followup_prompt_count")
            trace["last_decision"] = "send_blind_scheduled_continuation"
            return build_blind_loop_continuation_prompt(
                scheduled_round=round + 1,
                max_rounds=max_rounds,
                persistent_constraint_clause=self._persistent_constraint_clause,
            )

    return BlindLoopUser()


def _build_codex_goal_mode_baseline_user():
    from benchflow.sandbox.user import BaseUser, RoundResult

    class CodexGoalModeBaselineUser(BaseUser):
        """Scheduler-side user that sends one slash-goal-style prompt request."""

        async def run(
            self,
            round: int,
            instruction: str,
            round_result: RoundResult | None = None,
        ) -> str | None:
            if round != 0:
                return None
            return (
                "/goal Complete the following SkillsBench task. Keep working "
                "until the task is done, validated, or blocked by the benchmark "
                "environment. Do not use external LoopX CLI, upload, "
                "submit, or ask the human for routine execution choices.\n\n"
                "--- TASK INSTRUCTION ---\n"
                f"{instruction}"
            )

    return CodexGoalModeBaselineUser()


def _build_product_mode_user(
    *,
    route: str,
    max_rounds: int,
    trace: dict[str, Any],
    plan: dict[str, Any] | None = None,
    case_payload: dict[str, Any] | None = None,
):
    from benchflow.sandbox.user import BaseUser, RoundResult

    treatment = route == "loopx-product-mode"
    payload = case_payload or {}
    case_state_path = str(
        payload.get("case_state_path") or PRODUCT_MODE_CASE_STATE_PATH
    )
    case_goal_id = str(payload.get("benchmark_case_goal_id") or PRODUCT_MODE_CASE_GOAL_ID)
    case_agent_id = str(payload.get("case_agent_id") or BENCHMARK_CASE_LOOPX_AGENT_ID)
    case_todo_id = str(payload.get("case_todo_id") or BENCHMARK_CASE_LOOPX_TODO_ID)
    case_cli_prefix = benchmark_case_loopx_command_prefix(
        case_cli_path=str(payload.get("case_cli_path") or "/app/.local/bin/loopx"),
        case_registry_path=str(payload.get("case_registry_path") or "/app/.loopx/registry.json"),
        case_runtime_root=str(payload.get("case_runtime_root") or "/app/.loopx/runtime"),
    )

    def treatment_state_contract() -> str:
        return (
            "LoopX product-mode lifecycle contract: official case-local "
            f"LoopX is initialized before the agent starts. Active state: "
            f"`{case_state_path}`. This is the only formal treatment "
            "lifecycle; runner polling is only the outer transport. Before "
            "planning, run "
            f"`{case_cli_prefix} quota should-run --goal-id {case_goal_id} "
            f"--agent-id {case_agent_id}` and claim the selected case todo "
            f"with `{case_cli_prefix} todo claim --goal-id {case_goal_id} "
            f"--todo-id {case_todo_id} --claimed-by {case_agent_id}`. "
            "After meaningful local evidence or validation, update the todo "
            "through LoopX CLI; when complete, use `todo complete`, then "
            "`refresh-state`, then `quota spend-slot --execute`. Do not rely "
            "on only reading or editing the Markdown state file, and do not "
            "write a separate marker as the source of truth. "
        )

    def lifecycle_checkpoint_commands(round_number: int) -> str:
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

    class ProductModeUser(BaseUser):
        """Main-table autonomous product-mode controller."""

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
                if treatment:
                    _merge_acp_trajectory_summary(plan or {}, trace)
                    if (
                        _round_result_tool_call_count(round_result) == 0
                        and not _product_mode_depth_gate_satisfied(trace)
                    ):
                        _record_product_mode_lifecycle_checkpoint_gap(
                            trace,
                            agent_round=round,
                        )
                        _record_product_mode_no_tool_call_lifecycle_abort(
                            trace,
                            agent_round=round,
                        )
                        _inc_counter(trace, "controller_action_decisions")
                        _inc_counter(trace, "stop_decision_count")
                        trace["last_decision"] = (
                            "stop_after_product_mode_no_tool_calls_without_lifecycle"
                        )
                        return None
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
                    _inc_counter(trace, "controller_action_decisions")
                    _inc_counter(trace, "stop_decision_count")
                    _record_declared_done(trace, agent_round=round, reward=reward)
                    trace["last_decision"] = "stop_after_agent_declared_done"
                    return None
            if reward is not None and reward >= 1.0:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = (
                    "stop_after_product_mode_official_success_observed_without_feedback"
                )
                return None
            if round >= max_rounds:
                _inc_counter(trace, "controller_action_decisions")
                _inc_counter(trace, "stop_decision_count")
                trace["last_decision"] = "stop_after_product_mode_budget"
                return None
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
                    control_clause = (
                        "Use LoopX as your product control plane: create "
                        "a compact goal state, maintain todos, replan when local "
                        "evidence changes, and use LoopX CLI/status/ledger "
                        "surfaces when available. "
                        + treatment_state_contract()
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
                    + control_clause
                    + (
                        "For this treatment, LoopX lifecycle evidence is a "
                        "hard product-mode requirement: first run the "
                        "case-local quota/todo commands above before "
                        "substantive task work. "
                        if treatment
                        else ""
                    )
                    + "No official reward, pass/fail status, verifier error, "
                    "verifier output, or verifier tail will be shown during this "
                    "run. If you believe the task is complete and there are no "
                    "remaining goals, end your response with "
                    f"{DECLARED_DONE_MARKER}.\n\n"
                    "--- TASK INSTRUCTION ---\n"
                    f"{instruction}"
                )

            _inc_counter(trace, "controller_action_decisions")
            _inc_counter(trace, "followup_prompt_count")
            if treatment:
                _merge_acp_trajectory_summary(plan or {}, trace)
                if not _product_mode_depth_gate_satisfied(trace):
                    _record_product_mode_lifecycle_checkpoint_gap(
                        trace,
                        agent_round=round,
                    )
                    trace["last_decision"] = (
                        "send_product_mode_lifecycle_checkpoint_continuation"
                    )
                    return lifecycle_checkpoint_prompt(round + 1)
            trace["last_decision"] = "send_product_mode_scheduled_continuation"
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
            return (
                f"Scheduled product-mode continuation round {round + 1} of "
                f"{max_rounds}. This is part of the fixed autonomous budget and "
                "is not evidence that the official verifier passed or failed. "
                "You are not being shown official reward, pass/fail status, "
                "verifier error, or verifier output."
                f"{self._persistent_constraint_clause} {mode_clause} Keep scope "
                "narrow, validate locally, and if there are no remaining goals, "
                f"end with {DECLARED_DONE_MARKER}."
            )

    return ProductModeUser()


async def run_benchflow_case(args: argparse.Namespace, plan: dict[str, Any]) -> Path:
    skillsbench_root = Path(args.skillsbench_root).expanduser().resolve()
    task_path = skillsbench_root / "tasks" / args.task_id
    if not task_path.exists():
        raise FileNotFoundError(f"SkillsBench task not found: {task_path}")
    loopx_source_contract = _loopx_source_mount_contract(args)
    if loopx_source_contract.get("requested") and not loopx_source_contract.get("ready"):
        raise FileNotFoundError(
            "LoopX source mount requested but local source files are missing; "
            "use --no-loopx-source-mount to test the public GitHub installer instead"
        )
    effective_task_path, staging_metadata = stage_task_for_sandbox(
        task_path=task_path,
        jobs_dir=Path(plan["jobs_dir"]),
        job_name=str(plan["job_name"]),
        sandbox=args.sandbox,
        include_task_skills=bool(args.include_task_skills),
    )
    plan["task_staging"] = staging_metadata
    plan["effective_task_path"] = str(effective_task_path)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

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
    plan.setdefault("runner_prerequisites", {})[
        "benchflow_rollout_planes_module_available"
    ] = benchflow_rollout_planes_module is not None

    host_local_acp_command = _host_local_acp_launch_command(args, plan)
    runtime_mounts = (
        _benchflow_agent_runtime_mounts(args)
        if args.require_preinstalled_benchflow_agent_runtime
        else []
    )
    loopx_source_mounts = _loopx_source_mounts(args)
    container_mounts = [*runtime_mounts, *loopx_source_mounts]

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
    ) -> tuple[Any, Any, Any, str]:
        del (
            env,
            agent_launch,
            agent_env,
            sandbox_user,
            rollout_dir,
            environment,
            reasoning_effort,
        )
        from benchflow.agents.protocol import ACPSessionAdapter
        from benchflow.acp.client import ACPClient
        from benchflow.acp.transport import StdioTransport

        prerequisites = plan.setdefault("runner_prerequisites", {})
        prerequisites["host_local_acp_launch_status"] = "connecting"
        client = ACPClient(
            StdioTransport(
                command=host_local_acp_command[0],
                args=host_local_acp_command[1:],
                cwd=str(REPO_ROOT),
            )
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=60)
            init_result = await asyncio.wait_for(client.initialize(), timeout=60)
            session = await asyncio.wait_for(
                client.session_new(cwd=agent_cwd, mcp_servers=mcp_servers),
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
            return client, session, ACPSessionAdapter(client), agent_name
        except Exception:
            prerequisites["host_local_acp_launch_status"] = "failed"
            with contextlib.suppress(Exception):
                await client.close()
            raise

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
        if args.route != "loopx-product-mode":
            return
        payload = benchmark_case_loopx_install_payload(
            benchmark_id="skillsbench",
            case_id=args.task_id,
            arm_id="loopx_product_mode",
            route=args.route,
            max_rounds=args.max_rounds,
            case_loopx_source_path=_loopx_case_source_path_for_container(args),
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
            trace["case_goal_state_init_status"] = "failed"
            raise RuntimeError(
                "LoopX official case lifecycle init failed: " + detail[:1000]
            )
        trace["case_goal_state_initialized_before_agent"] = True
        trace["case_goal_state_init_status"] = "passed"
        trace["loopx_case_cli_installed_before_agent"] = True

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
    rollout_planes_class = (
        getattr(benchflow_rollout_planes_module, "DefaultRolloutPlanes", None)
        if benchflow_rollout_planes_module is not None
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
        prerequisites = plan.setdefault("runner_prerequisites", {})
        environment = str(call_args[0]) if call_args else ""
        if container_mounts and environment == "docker":
            existing_mounts = getattr(env, "_mounts_json", None) or []
            setattr(env, "_mounts_json", [*existing_mounts, *container_mounts])
            if runtime_mounts:
                prerequisites["benchflow_agent_runtime_mount_injected"] = True
                prerequisites["benchflow_agent_runtime_mount_read_only"] = True
                prerequisites["benchflow_agent_runtime_mount_source_recorded"] = False
            if loopx_source_mounts:
                prerequisites["loopx_source_mount_injected"] = True
                prerequisites["loopx_source_mount_read_only"] = True
                prerequisites["loopx_source_mount_source_recorded"] = False
        elif container_mounts:
            if runtime_mounts:
                prerequisites["benchflow_agent_runtime_mount_injected"] = False
                prerequisites["benchflow_agent_runtime_mount_read_only"] = True
                prerequisites["benchflow_agent_runtime_mount_source_recorded"] = False
            if loopx_source_mounts:
                prerequisites["loopx_source_mount_injected"] = False
                prerequisites["loopx_source_mount_read_only"] = True
                prerequisites["loopx_source_mount_source_recorded"] = False
        return env

    def _record_container_mount_injection(env: Any, environment: str) -> Any:
        prerequisites = plan.setdefault("runner_prerequisites", {})
        if container_mounts and environment == "docker":
            existing_mounts = getattr(env, "_mounts_json", None) or []
            setattr(env, "_mounts_json", [*existing_mounts, *container_mounts])
            if runtime_mounts:
                prerequisites["benchflow_agent_runtime_mount_injected"] = True
                prerequisites["benchflow_agent_runtime_mount_read_only"] = True
                prerequisites["benchflow_agent_runtime_mount_source_recorded"] = False
            if loopx_source_mounts:
                prerequisites["loopx_source_mount_injected"] = True
                prerequisites["loopx_source_mount_read_only"] = True
                prerequisites["loopx_source_mount_source_recorded"] = False
        elif container_mounts:
            if runtime_mounts:
                prerequisites["benchflow_agent_runtime_mount_injected"] = False
                prerequisites["benchflow_agent_runtime_mount_read_only"] = True
                prerequisites["benchflow_agent_runtime_mount_source_recorded"] = False
            if loopx_source_mounts:
                prerequisites["loopx_source_mount_injected"] = False
                prerequisites["loopx_source_mount_read_only"] = True
                prerequisites["loopx_source_mount_source_recorded"] = False
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
            cwd_result = await self._env.exec("pwd", timeout_sec=10)
            self._agent_cwd = (cwd_result.stdout or "").strip() or "/app"
            self._agent_cfg = None
            planes = getattr(self, "_planes", None)
            if planes is None:
                raise RuntimeError("BenchFlow rollout planes unavailable")
            if cfg.sandbox_user:
                prerequisites["host_local_acp_install_stage"] = "sandbox_user_setup"
                self._agent_cwd = await planes.setup_sandbox_user(
                    self._env,
                    cfg.sandbox_user,
                    workspace=self._agent_cwd,
                    timeout_sec=cfg.sandbox_setup_timeout,
                )
            prerequisites["host_local_acp_install_stage"] = "snapshot_build_config"
            await planes.snapshot_build_config(self._env, workspace=self._agent_cwd)
            prerequisites["host_local_acp_install_stage"] = "seed_verifier_workspace"
            await planes.seed_verifier_workspace(
                self._env, workspace=self._agent_cwd, sandbox_user=cfg.sandbox_user
            )
            prerequisites["host_local_acp_install_stage"] = "deploy_skills"
            await planes.deploy_skills(
                self._env,
                getattr(self, "_effective_task_path", cfg.task_path),
                getattr(self, "_effective_skills_dir", cfg.skills_dir),
                None,
                cfg.sandbox_user,
                self._agent_cwd,
                skills_sandbox_dir=getattr(
                    self,
                    "_effective_skills_sandbox_dir",
                    getattr(cfg, "skills_sandbox_dir", "/app/skills"),
                ),
            )
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
            await planes.lockdown_paths(self._env, self._effective_locked)
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
        requested_timeout = max(0, int(args.agent_idle_timeout or 0))
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

    controller_user = None
    controller_trace: dict[str, Any] | None = None
    product_mode_case_payload: dict[str, Any] | None = None
    if args.route == "loopx-product-mode":
        product_mode_case_payload = benchmark_case_loopx_install_payload(
            benchmark_id="skillsbench",
            case_id=args.task_id,
            arm_id="loopx_product_mode",
            route=args.route,
            max_rounds=args.max_rounds,
            case_loopx_source_path=_loopx_case_source_path_for_container(args),
        )
    if args.route == "automation-loop-treatment":
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_user = _build_controller_user(
            args.max_verifier_output_chars,
            controller_trace,
        )
    elif args.route in {
        CODEX_ACP_BLIND_LOOP_BASELINE_ROUTE,
        LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        LOOPX_PROMPT_POLLING_TEST_ROUTE,
    }:
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_user = _build_blind_loop_user(
            route=args.route,
            max_rounds=args.max_rounds,
            trace=controller_trace,
            treatment_prompt_style=args.treatment_prompt_style,
        )
    elif args.route in {
        "raw-codex-autonomous-max5",
        "loopx-product-mode",
    }:
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_user = _build_product_mode_user(
            route=args.route,
            max_rounds=args.max_rounds,
            trace=controller_trace,
            plan=plan,
            case_payload=product_mode_case_payload,
        )
    elif args.route == "codex-goal-mode-baseline":
        controller_user = _build_codex_goal_mode_baseline_user()
    elif args.route == "codex-app-server-goal-baseline":
        controller_trace = _new_controller_trace(args.route, max_rounds=args.max_rounds)
        controller_trace["native_goal_worker_route"] = True
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
            plan=plan,
            trace=controller_trace,
        )
    )

    pre_agent_hooks = (
        []
        if args.host_local_acp_launch
        or args.require_preinstalled_benchflow_agent_runtime
        else [ensure_codex_acp_runtime_deps]
    )
    if args.route == "loopx-product-mode":
        pre_agent_hooks.append(seed_product_mode_case_state)

    agent_env: dict[str, str] = {}
    if runtime_mounts:
        agent_env["PATH"] = BENCHFLOW_AGENT_RUNTIME_CONTAINER_PATH
        agent_env["CODEX_ACP_RUNTIME_HOME"] = BENCHFLOW_AGENT_RUNTIME_MOUNT_TARGET

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
    build_stall_timeout_sec = max(0, int(args.build_stall_timeout_sec or 0))
    prerequisites["benchflow_setup_stall_timeout_enabled"] = (
        build_stall_timeout_sec > 0
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
    try:
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
        _merge_acp_trajectory_summary(plan, controller_trace)
        _merge_app_server_goal_worker_trace_summary(plan, controller_trace)
        _merge_host_local_acp_relay_trace_summary(plan, controller_trace)
        _write_controller_trace(plan, controller_trace)
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
    from loopx.status import compact_benchmark_run

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
    if runner_prerequisites:
        compact["runner_prerequisites"] = runner_prerequisites
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
    runner_output_capture = _public_runner_output_capture(plan)
    if runner_output_capture:
        compact["runner_output_capture"] = runner_output_capture
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
    from loopx.status import compact_benchmark_run

    plan.setdefault("runner_prerequisites", {})
    _ensure_setup_stall_timeout_prerequisites(
        args,
        plan,
        exc,
        cleanup_if_missing=True,
    )

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
    task_staging = _effective_public_task_staging(plan)
    if task_staging:
        compact["task_staging"] = task_staging
    fingerprint = skillsbench_runner_error_fingerprint(str(exc))
    if fingerprint:
        compact["runner_failure_fingerprint"] = fingerprint
    diagnostic = build_compose_setup_diagnostic(compact, plan)
    if diagnostic.get("status") != "not_applicable":
        compact["compose_setup_diagnostic"] = diagnostic
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
    runner_output_capture = _public_runner_output_capture(plan)
    if runner_output_capture:
        reduced["runner_output_capture"] = runner_output_capture
    return reduced


def update_ledger(
    args: argparse.Namespace,
    compact: dict[str, Any],
    *,
    compact_path: Path | None = None,
) -> dict[str, Any]:
    from loopx.benchmark_ledger import update_benchmark_run_ledger

    note_route = (
        "LoopX prompt-driven polling test"
        if args.route == LOOPX_PROMPT_POLLING_TEST_ROUTE
        else "LoopX blind-loop treatment"
        if args.route == LOOPX_BLIND_LOOP_TREATMENT_ROUTE
        else "Codex ACP blind-loop baseline"
        if args.route == "codex-acp-blind-loop-baseline"
        else "LoopX product-mode treatment"
        if args.route == "loopx-product-mode"
        else "raw Codex autonomous max5 baseline"
        if args.route == "raw-codex-autonomous-max5"
        else "LoopX reward-feedback ablation"
        if args.route == "automation-loop-treatment"
        else "Codex ACP baseline"
    )
    return update_benchmark_run_ledger(
        ledger_path=Path(args.ledger_path).expanduser(),
        benchmark_run=compact,
        compact_artifact_ref=compact_path,
        run_group_id=args.run_group_id,
        notes=(
            f"official SkillsBench BenchFlow {note_route}; compact result only; "
            "no raw task/log/trajectory read into public state"
        ),
        cwd=REPO_ROOT,
        dry_run=not args.update_ledger,
    )


def append_history(args: argparse.Namespace, compact_path: Path) -> dict[str, Any]:
    if not args.append_history:
        return {
            "schema_version": "skillsbench_history_append_result_v0",
            "requested": False,
            "appended": False,
        }
    classification_by_route = {
        "loopx-blind-loop-treatment": "skillsbench_loopx_blind_loop_treatment_result_v0",
        "loopx-prompt-polling-test": "skillsbench_loopx_prompt_polling_test_result_v0",
        "codex-acp-blind-loop-baseline": "skillsbench_codex_acp_blind_loop_baseline_result_v0",
        "loopx-product-mode": "skillsbench_loopx_product_mode_result_v0",
        "raw-codex-autonomous-max5": "skillsbench_raw_codex_autonomous_max5_result_v0",
        "automation-loop-treatment": "skillsbench_reward_feedback_ablation_result_v0",
        "codex-app-server-goal-baseline": "skillsbench_codex_app_server_goal_baseline_result_v0",
        "codex-goal-mode-baseline": "skillsbench_codex_goal_mode_baseline_result_v0",
    }
    classification = classification_by_route.get(
        args.route,
        "skillsbench_codex_goal_mode_baseline_result_v0",
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default="react-performance-debugging")
    parser.add_argument("--dataset", default="skillsbench@1.1")
    parser.add_argument(
        "--route",
        choices=SUPPORTED_ROUTES,
        default=DEFAULT_ROUTE,
        help=(
            "codex-app-server-goal-baseline is the native Codex Goal baseline; "
            "loopx-prompt-polling-test is the current no-reward-feedback "
            "test route with scheduled continuation prompts; "
            "loopx-blind-loop-treatment is the historical SkillsBench "
            "alias for the same polling semantics; codex-acp-blind-loop-baseline "
            "is the ordinary Codex no-goal baseline with the same loop budget; "
            "raw-codex-autonomous-max5 and loopx-product-mode are the "
            "main-table product-mode comparison routes; "
            "codex-app-server-goal-baseline is the native Codex Goal baseline "
            "contract using app-server thread/goal/set/get and turn/start; "
            "codex-goal-mode-baseline sends one /goal-prefixed prompt request "
            "with no reward follow-up, but native goal-mode invocation remains "
            "unconfirmed without CLI slash-command/goal-state evidence and is "
            "blocked by default except for --plan-only or explicit experiments; "
            "automation-loop-treatment is a reward-feedback ablation."
        ),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--app-server-reasoning-effort",
        default="high",
        help=(
            "Reasoning effort passed as turn/start effort for native "
            "codex-app-server-goal-baseline runs. Formal benchmark runs "
            "default to high."
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
            f"Defaults to {DEFAULT_MAX_ROUNDS}; blind-loop routes still stop "
            "early once official reward reaches 1.0, without forwarding that "
            "reward to the agent."
        ),
    )
    parser.add_argument(
        "--treatment-prompt-style",
        choices=("structured", "baseline-safe"),
        default="structured",
        help=(
            "Diagnostic prompt wrapper for loopx-blind-loop-treatment. "
            "Also applies to loopx-prompt-polling-test. "
            "baseline-safe keeps treatment routing/ledger metadata while using "
            "the baseline-style first prompt to isolate ACP prompt-wrapper issues."
        ),
    )
    parser.add_argument(
        "--allow-unverified-goal-prefix-baseline",
        action="store_true",
        help=(
            "Allow the codex-goal-mode-baseline route to run as an explicit "
            "slash-prefix experiment. This does not prove native Codex Goal "
            "mode and must not be used for A/B uplift claims."
        ),
    )
    parser.add_argument("--outer-timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--sandbox-setup-timeout", type=int, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument(
        "--build-stall-timeout-sec",
        type=int,
        default=0,
        help=(
            "Optional public-safe watchdog for Docker build/setup before any "
            "agent lifecycle starts. 0 keeps the historical behavior and relies "
            "only on --outer-timeout-sec."
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
        "--product-mode-soft-verify-policy",
        choices=("final-only", "every-round"),
        default=DEFAULT_PRODUCT_MODE_SOFT_VERIFY_POLICY,
        help=(
            "Intermediate BenchFlow soft-verify policy for the main-table "
            "product-mode routes. final-only preserves official final scoring "
            "without per-round verifier reward/output observations."
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
    parser.add_argument("--max-verifier-output-chars", type=int, default=0)
    parser.add_argument("--skillsbench-root", default=str(DEFAULT_SKILLSBENCH_ROOT))
    parser.add_argument(
        "--loopx-source-dir",
        default=str(REPO_ROOT),
        help=(
            "Local LoopX checkout mounted read-only into docker product-mode "
            "runs and installed with scripts/install-local.sh. Public compact "
            "artifacts record only the mount target, not this host path."
        ),
    )
    parser.add_argument(
        "--no-loopx-source-mount",
        action="store_true",
        help=(
            "Do not mount the local LoopX checkout for product-mode runs; the "
            "case init falls back to the README GitHub installer."
        ),
    )
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
    parser.add_argument("--ledger-path", default=str(DEFAULT_LEDGER))
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
        default=DEFAULT_TIMEOUT_SEC,
        help="Per-prompt timeout for local Codex exec in host-local ACP launch mode.",
    )
    parser.add_argument(
        "--local-codex-ping-timeout-sec",
        type=int,
        default=120,
        help="Timeout for --local-codex-participant-ping.",
    )
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
    return parser.parse_args(argv)


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
    runtime_layer = (
        plan.get("benchflow_agent_runtime_layer")
        if isinstance(plan.get("benchflow_agent_runtime_layer"), dict)
        else {}
    )
    if (
        getattr(args, "require_preinstalled_benchflow_agent_runtime", False)
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
    if (
        args.fail_fast_on_apt_risk
        and not args.reduce_only
        and setup_preflight.get("apt_setup_risk_detected") is True
    ):
        staging = plan.setdefault("task_staging", {})
        if isinstance(staging, dict):
            staging["apt_setup_risk_detected"] = True
            staging["apt_retry_patch_required"] = True
            staging["apt_risk_preflight_blocked"] = True
        raise SkillsBenchSetupPreflightBlocked(
            "skillsbench apt setup risk preflight blocked: "
            "apt-based Docker setup risk detected before full case run"
        )

    ensure_benchflow_runtime(args)
    if args.reduce_only:
        result_path = discover_benchflow_result_path(plan)
        if not result_path.exists():
            raise FileNotFoundError(
                f"BenchFlow result.json not found for --reduce-only: {result_path}"
            )
        controller_trace = _read_controller_trace(plan)
        _merge_final_result_round_reward(controller_trace, result_path)
        _write_controller_trace(plan, controller_trace)
    else:
        result_path = await asyncio.wait_for(
            run_benchflow_case_with_private_output(args, plan),
            timeout=args.outer_timeout_sec,
        )
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    logging.getLogger().setLevel(logging.WARNING)
    if (
        args.route == "codex-goal-mode-baseline"
        and not args.plan_only
        and not args.allow_unverified_goal_prefix_baseline
    ):
        payload = {
            "ok": False,
            "error_type": "CodexGoalModeBaselineUnverified",
            "route": args.route,
            "reason": (
                "codex-goal-mode-baseline currently sends a slash-goal-style "
                "prompt through BenchFlow; it is not proven to enter native "
                "Codex Goal mode or attach persistent goal state"
            ),
            "next_action": (
                "prove a stable Codex CLI /goal trigger with goal-state evidence, "
                "or rerun with --allow-unverified-goal-prefix-baseline only as a "
                "non-claiming slash-prefix experiment"
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if args.route == "codex-app-server-goal-baseline" and not args.plan_only:
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
    product_host_local_bridge_fixture_solver = (
        skillsbench_remote_command_file_bridge_command_is_fixture_probe(
            args.remote_command_file_bridge_solver_command
        )
    )
    if (
        args.route in {"raw-codex-autonomous-max5", "loopx-product-mode"}
        and args.host_local_acp_launch
        and product_host_local_bridge_fixture_solver
        and not args.local_driver_worker_handshake_preflight
        and not args.plan_only
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
        args.route in {"raw-codex-autonomous-max5", "loopx-product-mode"}
        and args.host_local_acp_launch
        and not (
            product_host_local_bridge_materialized
            and product_host_local_bridge_command_configured
        )
        and not args.local_driver_worker_handshake_preflight
        and not args.plan_only
    ):
        payload = {
            "ok": False,
            "error_type": "SkillsBenchReverseChannelBridgeNotSolverWired",
            "route": args.route,
            "reason": (
                "product-mode host-local ACP runs execute Codex on the host while "
                "the scored workspace lives in the BenchFlow sandbox; a materialized "
                "remote command/file bridge and its private solver command are both "
                "required before this is a countable reverse-channel treatment"
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
        payload = materialize_local_codex_participant(
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
    closeout_recorded = False
    if args.run_group_id is None:
        args.run_group_id = (
            f"skillsbench-{args.task_id}-{args.route}-{_now_stamp()}"
        )
    plan = build_plan(args)
    try:
        payload = asyncio.run(async_main(args, plan=plan))
    except Exception as exc:
        recovered_payload = reduce_official_result_after_runner_exception(
            args, plan, exc
        )
        if recovered_payload is not None:
            print(json.dumps(recovered_payload, indent=2, sort_keys=True))
            return 0
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
        except Exception:
            compact = None
            compact_path = None
            ledger_update = None
            history_append = None
        payload = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_recorded": closeout_recorded,
            "compact_closeout_recorded": closeout_recorded,
            "task_id": args.task_id,
            "compact_benchmark_run_json": str(compact_path) if compact_path else None,
            "ledger_update": ledger_update,
            "history_append": history_append,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 0 if closeout_recorded else 1
    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
