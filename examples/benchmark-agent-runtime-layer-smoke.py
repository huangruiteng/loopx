#!/usr/bin/env python3
"""Smoke-test benchmark-specific agent runtime layer plans."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "benchmark_agent_runtime_layer.py"


def _run_json(args: list[str]) -> dict:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gh-runtime-layer-") as tmp:
        workspace = Path(tmp) / "goal-harness-bench"
        public = _run_json(
            [
                "--benchmark",
                "all",
                "--workspace",
                str(workspace),
                "--pretty",
            ]
        )
        public_text = json.dumps(public, sort_keys=True)

        assert (
            public["schema_version"] == "benchmark_agent_runtime_layer_plan_v0"
        ), public
        assert public["ready"] is True, public
        assert public["boundary"]["private_paths_recorded"] is False, public
        assert public["workspace"]["path_recorded"] is False, public
        assert str(workspace) not in public_text, public_text

        profiles = {
            profile["benchmark_id"]: profile for profile in public["profiles"]
        }
        assert set(profiles) == {
            "terminal-bench",
            "swe-marathon",
            "skillsbench",
        }, profiles
        assert (
            profiles["terminal-bench"]["layer_id"]
            == profiles["swe-marathon"]["layer_id"]
            == "harbor_codex_cli_tools"
        ), profiles
        assert profiles["skillsbench"]["layer_id"] == "benchflow_js_agent_runtime"
        assert profiles["skillsbench"]["runtime_family"] == "benchflow"

        terminal = profiles["terminal-bench"]
        terminal_args = terminal["runner_fragments"]["harbor_cli_args"]
        assert "--mounts" in terminal_args, terminal_args
        assert "--agent-env" in terminal_args, terminal_args
        assert (
            "goal_harness_codex_install_strategy=require_existing_codex"
            in terminal_args
        ), terminal_args
        assert terminal["container_contract"]["required_commands"] == [
            "codex",
            "rg",
        ], terminal
        assert terminal["container_contract"]["optional_commands"] == ["curl"]
        assert "nvm_install_per_case" in terminal["forbidden_case_runtime_steps"]
        assert "npm_global_agent_runtime_install_per_case" in (
            terminal["forbidden_case_runtime_steps"]
        )

        skillsbench = profiles["skillsbench"]
        assert (
            skillsbench["host_materialization"]["materializer_status"]
            == "implemented"
        )
        assert (
            skillsbench["host_materialization"]["script"]
            == "scripts/skillsbench_agent_runtime_layer.py"
        )
        assert "codex-acp" in skillsbench["container_contract"]["required_commands"]
        assert "/opt/benchflow" in skillsbench["container_contract"]["environment"][
            "PATH"
        ]

        private = _run_json(
            [
                "--benchmark",
                "terminal-bench",
                "--workspace",
                str(workspace),
                "--emit-private-runner-fragments",
            ]
        )
        assert private["boundary"]["private_paths_recorded"] is True, private
        assert private["workspace"]["path_recorded"] is True, private
        assert str(workspace) in json.dumps(private), private

    print("benchmark-agent-runtime-layer smoke passed")


if __name__ == "__main__":
    main()
