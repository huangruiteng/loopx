#!/usr/bin/env python3
"""Smoke-test fresh no-scan onboarding state and todo projection parity."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "fresh-no-scan-projection"
DOMAIN_GOAL_ID = "fresh-domain-owned-projection"


def run_cli(registry: Path, runtime: Path, *args: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def initialize_project(root: Path, name: str) -> tuple[Path, Path]:
    project = root / name
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    readme = project / "README.md"
    readme.write_text("# Synthetic LoopX onboarding fixture\n", encoding="utf-8")
    (project / ".gitignore").write_text(".loopx/\n.codex/\n.local/\n", encoding="utf-8")
    return project, readme


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-no-scan-projection-") as tmp:
        root = Path(tmp)
        project, readme = initialize_project(root, "project")

        registry = project / ".loopx" / "registry.json"
        runtime = root / "runtime"
        connected = run_cli(
            registry,
            runtime,
            "connect",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
            "--objective",
            "Validate fresh read-only onboarding.",
            "--domain",
            "engineering",
            "--goal-doc",
            str(readme),
            "--adapter-kind",
            "read_only_project_map_v0",
            "--adapter-status",
            "connected-read-only",
            "--codex-app-heartbeat",
            "no",
            "--no-onboarding-scan",
            "--no-global-sync",
        )
        assert connected["ok"] is True, connected

        mapped = run_cli(
            registry,
            runtime,
            "read-only-map",
            "--goal-id",
            GOAL_ID,
            "--no-global-sync",
        )
        assert mapped["ok"] is True, mapped

        state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        state_text = state_file.read_text(encoding="utf-8")
        assert state_text.count("action_kind=onboarding_connection_validation") == 1, state_text
        assert "## Next Action" in state_text, state_text

        healthy_check = run_cli(registry, runtime, "check", "--scan-path", str(readme))
        assert healthy_check["ok"] is True, healthy_check
        assert healthy_check["summary"]["warnings"] == 0, healthy_check

        quota = run_cli(registry, runtime, "quota", "should-run", "--goal-id", GOAL_ID)
        assert quota["decision"] == "run", quota
        assert quota["normal_delivery_allowed"] is True, quota
        assert quota["effective_action"] == "normal_run", quota
        assert quota.get("state_projection_gap") is None, quota

        broken_lines = [
            line
            for line in state_text.splitlines()
            if "action_kind=onboarding_connection_validation" not in line
            and not line.startswith("- [ ] [P1] Run `loopx check` against the project registry")
        ]
        state_file.write_text("\n".join(broken_lines) + "\n", encoding="utf-8")

        broken_check = run_cli(registry, runtime, "check", "--scan-path", str(readme))
        assert broken_check["ok"] is True, broken_check
        assert broken_check["summary"]["warnings"] == 1, broken_check
        assert any("state_projection_gap" in warning for warning in broken_check["warnings"]), broken_check

        domain_project, domain_readme = initialize_project(root, "domain-project")
        domain_registry = domain_project / ".loopx" / "registry.json"
        domain_connected = run_cli(
            domain_registry,
            runtime,
            "connect",
            "--project",
            str(domain_project),
            "--goal-id",
            DOMAIN_GOAL_ID,
            "--objective",
            "Validate domain-owned onboarding routing.",
            "--domain",
            "engineering",
            "--goal-doc",
            str(domain_readme),
            "--adapter-kind",
            "domain_fixture_v0",
            "--adapter-status",
            "connected-read-only",
            "--codex-app-heartbeat",
            "no",
            "--no-onboarding-scan",
            "--no-global-sync",
        )
        assert domain_connected["ok"] is True, domain_connected

        domain_state_file = (
            domain_project
            / ".codex"
            / "goals"
            / DOMAIN_GOAL_ID
            / "ACTIVE_GOAL_STATE.md"
        )
        domain_state_text = domain_state_file.read_text(encoding="utf-8")
        assert "action_kind=onboarding_connection_validation" not in domain_state_text
        assert "Initial routing is owned by the connected domain adapter." in domain_state_text

        domain_check = run_cli(
            domain_registry,
            runtime,
            "check",
            "--scan-path",
            str(domain_readme),
        )
        assert domain_check["ok"] is True, domain_check
        assert domain_check["summary"]["warnings"] == 0, domain_check

    print("onboarding-no-scan-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
