#!/usr/bin/env python3
"""Plan benchmark-specific preinstalled agent runtime layers.

The benchmark case container should run the task, not rebuild the agent runtime
on every attempt.  This script emits a public-safe contract for the host-side
runtime layer each benchmark family expects before an official no-upload case
run is launched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "benchmark_agent_runtime_layer_plan_v0"
DEFAULT_WORKSPACE = "~/loopx-bench"
HARBOR_TARGET = "/opt/harbor-agent-tools"
BENCHFLOW_TARGET = "/opt/benchflow"


FORBIDDEN_CASE_RUNTIME_STEPS = (
    "apt_get_agent_runtime_install_per_case",
    "nvm_install_per_case",
    "nodejs_org_download_per_case",
    "npm_global_agent_runtime_install_per_case",
    "openai_codex_cli_download_per_case",
    "codex_acp_download_per_case",
)


def _public_source_placeholder(name: str) -> str:
    return f"<workspace>/{name}"


def _source_value(path: Path, *, private: bool, placeholder: str) -> str:
    if private:
        return str(path.expanduser())
    return placeholder


def _harbor_mount(source: str) -> dict[str, Any]:
    return {
        "type": "bind",
        "source": source,
        "target": HARBOR_TARGET,
        "read_only": True,
    }


def _harbor_profile(
    *,
    benchmark_id: str,
    harbor_tools_dir: Path,
    private: bool,
) -> dict[str, Any]:
    source = _source_value(
        harbor_tools_dir,
        private=private,
        placeholder=_public_source_placeholder("harbor-agent-tools"),
    )
    mount = _harbor_mount(source)
    runner_fragments: dict[str, Any] = {
        "recommended_agent": "codex-api-key-no-search",
        "local_harbor_checkout_command_prefix": (
            "UV_LINK_MODE=copy uv run --no-default-groups harbor run"
        ),
        "harbor_cli_args": [
            "--mounts",
            json.dumps([mount], separators=(",", ":")),
            "--agent-env",
            f"PATH={HARBOR_TARGET}/bin:${{PATH}}",
            "--agent-kwarg",
            "loopx_codex_install_strategy=require_existing_codex",
            "--agent-kwarg",
            (
                "loopx_worker_codex_materialization_strategy="
                "worker_path_preprovisioned"
            ),
        ],
        "job_config_mount": mount,
    }
    notes = [
        (
            "Terminal-Bench and SWE-Marathon use Harbor-family containers: "
            "mount the same Codex CLI tools bundle into each task container."
        ),
        (
            "curl is optional because host-copied dynamic curl binaries are "
            "not portable across all task images; use the container curl or a "
            "static curl only when a runner explicitly needs it."
        ),
        (
            "For SWE-Marathon, prefer running Harbor from an already "
            "materialized local Harbor checkout with uv --no-default-groups; "
            "the SWE-Marathon pyproject may otherwise fetch Harbor from "
            "GitHub or install cloud/GPU extras before a case starts."
        ),
    ]
    if benchmark_id == "swe-marathon":
        runner_fragments["harbor_host_codex_goal_agent"] = {
            "agent_import_path": (
                "harbor_host_codex_goal_agent:HarborHostCodexGoalAgent"
            ),
            "pythonpath_source": "scripts/",
            "required_host_commands": ["codex", "tmux"],
            "recommended_harbor_args": [
                "--agent-import-path",
                "harbor_host_codex_goal_agent:HarborHostCodexGoalAgent",
                "--agent-kwarg",
                "goal_surface=app_server",
                "--agent-kwarg",
                "goal_timeout_sec=<seconds>",
                "--agent-kwarg",
                "task_workdir=<task-workdir>",
            ],
            "command_bridge": "harbor-env-exec",
            "goal_surface": "app_server",
            "fallback_goal_surface": "tui",
            "task_workdir_default": "/app",
            "preflight_gate": (
                "codex app-server generate-json-schema --enable goals must "
                "include thread/goal/set, thread/goal/get, and turn/start; "
                "a marker-file app-server Goal probe should pass on the run host"
            ),
        }
        notes.append(
            "For SWE-Marathon, use the Harbor host Codex Goal custom agent "
            "when Codex auth should stay on the host. It bridges host Codex "
            "commands into Harbor environment.exec instead of installing "
            "Codex inside the task container."
        )
    if benchmark_id == "terminal-bench":
        runner_fragments["terminal_bench_no_rebuild_guard_command"] = (
            "python3 scripts/terminal_bench_no_rebuild_guard.py "
            "--terminal-bench-root <terminal-bench-checkout> --apply --pretty"
        )
        runner_fragments["terminal_bench_task_image_bootstrap_command"] = (
            "python3 scripts/terminal_bench_task_image_bootstrap.py "
            "--source-image <prebuilt-task-image> "
            "--target-image tb__<task-id>__client "
            "--work-dir <workspace>/image-bootstrap/<task-id> "
            "--network-host --execute --pretty"
        )
        runner_fragments["terminal_bench_safe_run_id_command"] = (
            "python3 scripts/terminal_bench_safe_run_id.py "
            "--prefix <task-id>-host-codex-goal --pretty"
        )
        runner_fragments["terminal_bench_host_codex_goal_agent"] = {
            "agent_import_path": (
                "terminal_bench_host_codex_goal_agent:HostCodexGoalAgent"
            ),
            "pythonpath_source": "scripts/",
            "required_host_commands": ["codex", "tmux", "docker"],
            "recommended_tb_args": [
                "--agent-import-path",
                "terminal_bench_host_codex_goal_agent:HostCodexGoalAgent",
                "--agent-kwarg",
                "goal_surface=app_server",
                "--agent-kwarg",
                "goal_timeout_sec=<seconds>",
            ],
            "goal_surface": "app_server",
            "fallback_goal_surface": "tui",
            "preflight_gate": (
                "codex app-server generate-json-schema --enable goals must "
                "include thread/goal/set, thread/goal/get, and turn/start; "
                "a marker-file app-server Goal probe should pass on the run host"
            ),
        }
        notes.append(
            "For direct Terminal-Bench tb run with --no-rebuild, apply the "
            "no-rebuild guard first so docker compose up also uses --no-build "
            "and cannot silently rebuild a prewarmed task image."
        )
        notes.append(
            "If the prewarmed task image starts but lacks runner utilities such "
            "as tmux or asciinema, derive one task-image bootstrap layer and "
            "retag it to the Terminal-Bench client image name before rerunning "
            "the case."
        )
        notes.append(
            "Generate a lowercase Docker Compose-safe run id before launching "
            "Terminal-Bench; the runner reuses the run id in compose project "
            "and container names."
        )
        notes.append(
            "Use the host Codex Goal custom agent when the benchmark container "
            "should not own Codex auth or download agent runtime. The agent "
            "runs Codex on the benchmark host and operates on the task "
            "container through docker exec."
        )
    return {
        "benchmark_id": benchmark_id,
        "runtime_family": "harbor",
        "layer_id": "harbor_codex_cli_tools",
        "layer_target": HARBOR_TARGET,
        "host_materialization": {
            "script": "scripts/harbor_agent_tools_bundle.py",
            "command": (
                "python3 scripts/harbor_agent_tools_bundle.py "
                "--output <workspace>/harbor-agent-tools --pretty"
            ),
            "source": source,
            "source_basename": harbor_tools_dir.expanduser().name,
        },
        "container_contract": {
            "required_commands": ["codex", "rg"],
            "optional_commands": ["curl"],
            "path_prefix": f"{HARBOR_TARGET}/bin",
            "mounts": [mount],
            "environment": {
                "PATH": f"{HARBOR_TARGET}/bin:${{PATH}}",
                "CODEX_OPENAI_PROXY": "${CODEX_OPENAI_PROXY:-}",
            },
            "preflight_command": (
                f"PATH={HARBOR_TARGET}/bin:$PATH "
                "command -v codex >/dev/null && codex --version >/dev/null && "
                "command -v rg >/dev/null && rg --version >/dev/null"
            ),
        },
        "runner_fragments": runner_fragments,
        "case_container_rule": "agent_runtime_preinstalled_before_case_start",
        "preflight_required_before_official_case_attempt": True,
        "forbidden_case_runtime_steps": list(FORBIDDEN_CASE_RUNTIME_STEPS),
        "notes": notes,
    }


def _benchflow_profile(
    *,
    benchflow_tools_dir: Path,
    private: bool,
) -> dict[str, Any]:
    source = _source_value(
        benchflow_tools_dir,
        private=private,
        placeholder=_public_source_placeholder("benchflow-agent-runtime"),
    )
    mount = {
        "type": "bind",
        "source": source,
        "target": BENCHFLOW_TARGET,
        "read_only": True,
    }
    return {
        "benchmark_id": "skillsbench",
        "runtime_family": "benchflow",
        "layer_id": "benchflow_js_agent_runtime",
        "layer_target": BENCHFLOW_TARGET,
        "host_materialization": {
            "materializer_status": "implemented",
            "script": "scripts/skillsbench_agent_runtime_layer.py",
            "command": (
                "python3 scripts/skillsbench_agent_runtime_layer.py "
                "--output <workspace>/benchflow-agent-runtime "
                "--node-root <cached-node-root> "
                "--codex-acp-bin <cached-codex-acp-bin> --pretty"
            ),
            "source": source,
            "source_basename": benchflow_tools_dir.expanduser().name,
        },
        "container_contract": {
            "required_commands": ["node", "npm", "codex-acp"],
            "optional_commands": [],
            "path_prefixes": [
                f"{BENCHFLOW_TARGET}/bin",
                f"{BENCHFLOW_TARGET}/js-agents/bin",
                f"{BENCHFLOW_TARGET}/node/bin",
            ],
            "mounts": [mount],
            "environment": {
                "PATH": (
                    f"{BENCHFLOW_TARGET}/bin:"
                    f"{BENCHFLOW_TARGET}/js-agents/bin:"
                    f"{BENCHFLOW_TARGET}/node/bin:${{PATH}}"
                ),
                "CODEX_ACP_RUNTIME_HOME": BENCHFLOW_TARGET,
            },
            "preflight_command": (
                "agent_bin=/opt/benchflow/bin/codex-acp; "
                "if [ ! -x \"$agent_bin\" ]; then "
                "agent_bin=$(command -v codex-acp); fi; "
                "command -v node >/dev/null && "
                "command -v npm >/dev/null && "
                "\"$agent_bin\" --version >/dev/null 2>&1 || "
                "\"$agent_bin\" --help >/dev/null 2>&1"
            ),
        },
        "runner_fragments": {
            "benchflow_mount": mount,
            "benchflow_env": {
                "PATH": (
                    f"{BENCHFLOW_TARGET}/bin:"
                    f"{BENCHFLOW_TARGET}/js-agents/bin:"
                    f"{BENCHFLOW_TARGET}/node/bin:${{PATH}}"
                )
            },
            "integration_point": (
                "BenchFlow compose override, wrapper image, or runner-side "
                "mount/env hook before run_task starts the agent process."
            ),
        },
        "case_container_rule": "agent_runtime_preinstalled_before_case_start",
        "preflight_required_before_official_case_attempt": True,
        "forbidden_case_runtime_steps": list(FORBIDDEN_CASE_RUNTIME_STEPS),
        "notes": [
            (
                "SkillsBench uses BenchFlow/ACP: prewarm Node.js plus "
                "codex-acp once, then mount that layer into task containers."
            ),
            (
                "Verifier dependency prewarm is a separate oracle concern; this "
                "profile only covers the agent runtime used to execute the case."
            ),
        ],
    }


def build_plan(
    *,
    benchmark: str,
    workspace: Path,
    harbor_tools_dir: Path | None = None,
    benchflow_tools_dir: Path | None = None,
    emit_private_runner_fragments: bool = False,
) -> dict[str, Any]:
    workspace = workspace.expanduser()
    harbor_tools_dir = harbor_tools_dir or (workspace / "harbor-agent-tools")
    benchflow_tools_dir = benchflow_tools_dir or (
        workspace / "benchflow-agent-runtime"
    )

    profiles: list[dict[str, Any]] = []
    requested = (
        ["terminal-bench", "swe-marathon", "skillsbench"]
        if benchmark == "all"
        else [benchmark]
    )
    for benchmark_id in requested:
        if benchmark_id in {"terminal-bench", "swe-marathon"}:
            profiles.append(
                _harbor_profile(
                    benchmark_id=benchmark_id,
                    harbor_tools_dir=harbor_tools_dir,
                    private=emit_private_runner_fragments,
                )
            )
        elif benchmark_id == "skillsbench":
            profiles.append(
                _benchflow_profile(
                    benchflow_tools_dir=benchflow_tools_dir,
                    private=emit_private_runner_fragments,
                )
            )
        else:
            raise ValueError(f"unsupported benchmark: {benchmark_id}")

    return {
        "schema_version": SCHEMA_VERSION,
        "ready": True,
        "first_blocker": "",
        "requested_benchmark": benchmark,
        "workspace": {
            "basename": workspace.name,
            "path_recorded": emit_private_runner_fragments,
        },
        "contract": {
            "case_container_rule": "agent_runtime_preinstalled_before_case_start",
            "preflight_required_before_official_case_attempt": True,
            "loopx_role": (
                "produce public-safe runtime-layer plans and compact evidence; "
                "benchmark runners still own task execution and scoring"
            ),
        },
        "profiles": profiles,
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_read": False,
            "private_paths_recorded": emit_private_runner_fragments,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Emit benchmark-specific preinstalled agent runtime layer contracts."
        )
    )
    parser.add_argument(
        "--benchmark",
        choices=("terminal-bench", "swe-marathon", "skillsbench", "all"),
        default="all",
    )
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--harbor-tools-dir")
    parser.add_argument("--benchflow-tools-dir")
    parser.add_argument(
        "--emit-private-runner-fragments",
        action="store_true",
        help="Include expanded local paths for private runner launch use.",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = build_plan(
        benchmark=args.benchmark,
        workspace=Path(args.workspace),
        harbor_tools_dir=Path(args.harbor_tools_dir)
        if args.harbor_tools_dir
        else None,
        benchflow_tools_dir=Path(args.benchflow_tools_dir)
        if args.benchflow_tools_dir
        else None,
        emit_private_runner_fragments=args.emit_private_runner_fragments,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
