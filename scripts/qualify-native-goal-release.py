#!/usr/bin/env python3
"""Opt-in, release-only Codex Goal qualification. Default execution costs no tokens."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
FIXTURE = REPO / "tests/fixtures/native_goal_ledger"
GOAL = "heartbeat-flow-main-control"
AGENT = "worker-a"
TODOS = {"todo_reducer", "todo_cli"}


def isolated_environment(root: Path, launcher: Path) -> dict[str, str]:
    """Only execution essentials cross into a release model's process tree."""
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT", "WINDIR")
           if key in os.environ}
    for key, directory in {
        "HOME": "home", "USERPROFILE": "home", "XDG_CONFIG_HOME": "config",
        "XDG_CACHE_HOME": "cache", "XDG_DATA_HOME": "data", "TMPDIR": "tmp",
        "TMP": "tmp", "TEMP": "tmp",
        "CODEX_HOME": "codex", "CLAUDE_CONFIG_DIR": "claude-config",
    }.items():
        path = root / directory
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        env[key] = str(path)
    env.update(PATH=str(launcher.parent) + os.pathsep + env.get("PATH", ""),
               PYTHONPATH=str(REPO))
    return env


def host_environment(root: Path, launcher: Path) -> dict[str, str]:
    env = isolated_environment(root, launcher)
    # Copy only the selected Codex authentication, never user config, MCP
    # servers, history or unrelated provider credentials.
    if os.environ.get("OPENAI_API_KEY"):
        env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    else:
        source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
        if source.is_file():
            target = Path(env["CODEX_HOME"]) / "auth.json"
            target.write_bytes(source.read_bytes())
            target.chmod(0o600)
    return env


def prerequisite_failure(codex: str) -> str | None:
    for executable in (codex, "git", "node"):
        if not shutil.which(executable):
            return "required_executable_unavailable"
    for command, reason in (
        ([codex, "login", "status"], "codex_auth_unavailable"),
        ([codex, "features", "list"], "native_goals_unavailable"),
    ):
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode:
            return reason
        if command[1] == "features" and not any(
            line.split()[:1] == ["goals"] for line in result.stdout.splitlines()
        ):
            return reason
    return None


def setup(root: Path) -> tuple[Path, Path, Path]:
    # Reuse the existing real CLI fixture, not an alternate registry contract.
    spec = importlib.util.spec_from_file_location(
        "heartbeat_fixture", REPO / "examples/control_plane/heartbeat-quota-flow-smoke.py",
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    project, runtime, registry = fixture.write_fixture(root)
    config = json.loads(registry.read_text())
    goal = config["goals"][0]
    goal.update(state_file="ACTIVE_GOAL_STATE.md", coordination={"registered_agents": [AGENT]})
    goal["quota"]["allowed_slots"] = 12
    registry.write_text(json.dumps(config))
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "registry.global.json").write_text(json.dumps(config))
    (project / "ACTIVE_GOAL_STATE.md").write_text(
        '---\nstatus: active-read-only\nowner_mode: goal\n'
        'objective: "Deliver the finite local ledger specification."\n---\n\n'
        '# Ledger\n\n## Objective\n\nDeliver and validate TASK.md.\n\n'
        '## Next Action\n\nImplement the reducer, then the CLI.\n\n'
        '## User Todo\n\n## Agent Todo\n\n'
        '- [ ] [P1] Implement and validate the TASK.md reducer.\n'
        '  <!-- loopx:todo todo_id=todo_reducer status=open task_class=advancement_task '
        'action_kind=implement claimed_by=worker-a task_repository=git:example.com/ledger '
        'required_capabilities=filesystem_write -->\n'
        '- [ ] [P1] Implement the CLI, verify full acceptance and close this finite Goal.\n'
        '  <!-- loopx:todo todo_id=todo_cli status=open task_class=advancement_task '
        'action_kind=implement claimed_by=worker-a resume_when=todo_done:todo_reducer '
        'task_repository=git:example.com/ledger required_capabilities=filesystem_write -->\n',
        encoding="utf-8",
    )
    shutil.copyfile(FIXTURE / "TASK.md", project / "TASK.md")
    launcher = project / "bin/loopx"
    launcher.parent.mkdir()
    launcher.write_text(
        "#!/bin/sh\nexport LOOPX_PYTHON=" + shlex.quote(sys.executable) + "\nexec "
        + shlex.join([str(REPO / "scripts/loopx"), "--registry", str(registry),
                      "--runtime-root", str(runtime)]) + ' "$@"\n',
    )
    launcher.chmod(0o700)
    git = ["git", "-C", str(project), "-c", "core.hooksPath=/dev/null",
           "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com"]
    for args in (("init", "-q"), ("remote", "add", "origin", "https://example.com/ledger.git"),
                 ("add", "TASK.md"), ("commit", "-qm", "Initialize synthetic acceptance")):
        subprocess.run([*git, *args], check=True, capture_output=True, timeout=30)
    return project, runtime, launcher


def cli(launcher: Path, *args: str) -> dict:
    result = subprocess.run(
        [str(launcher), "--format", "json", *args], cwd=launcher.parent.parent,
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        raise RuntimeError("fixture_cli_failed")
    packet = json.loads(result.stdout)
    if packet.get("ok") is not True:
        raise RuntimeError("fixture_cli_not_ok")
    return packet


def verify_settlement(runtime: Path, todos: list[dict]) -> int:
    from loopx.control_plane.effect_program import SettlementStepKind
    from loopx.control_plane.quota.settlement import read_heartbeat_settlement

    assert len(todos) == len(TODOS) and {t["todo_id"] for t in todos} == TODOS
    assert all(t.get("status") == "done" for t in todos)
    rows = [json.loads(line) for line in
            (runtime / "goals" / GOAL / "runs/index.jsonl").read_text().splitlines()]
    spends = [r for r in rows if r.get("classification") == "quota_slot_spent"]
    assert {r.get("todo_id") for r in spends if r.get("todo_id")} == TODOS
    assert all(isinstance(r.get("settlement_identity"), dict) for r in spends), "unbound_spend"
    identities = [r["settlement_identity"]["effect_id"] for r in spends]
    assert len(identities) == len(set(identities)), "duplicate_spend"
    for row in spends:
        readback = read_heartbeat_settlement(
            runtime, goal_id=GOAL, agent_id=AGENT, todo_id=row.get("todo_id"),
            replan_obligation_id=row.get("replan_obligation_id"),
            turn_instance_id=row["turn_instance_id"],
        )
        assert readback is not None, "missing_settlement_readback"
        assert readback.settlement.failure is None, "incomplete_settlement"
        assert {r.step_kind for r in readback.settlement.receipts} >= {
            SettlementStepKind.VALIDATION, SettlementStepKind.DURABLE_WRITEBACK,
            SettlementStepKind.QUOTA_SPEND,
        }, "missing_settlement_receipts"
        assert readback.writeback_run is not None and readback.spend_run is not None
    return len(spends)


def verify_delivery(project: Path, runtime: Path, launcher: Path, profile: str) -> dict:
    assert (project / "TASK.md").read_bytes() == (FIXTURE / "TASK.md").read_bytes()
    oracle = subprocess.run([sys.executable, str(FIXTURE / "verify.py"), str(project)],
                            capture_output=True, timeout=60)
    assert oracle.returncode == 0, "independent_acceptance_failed"
    todos = cli(launcher, "todo", "list", "--goal-id", GOAL, "--role", "agent")["todos"]
    spends = verify_settlement(runtime, todos)
    quota = cli(launcher, "quota", "should-run", "--goal-id", GOAL,
                "--agent-id", AGENT, "--runtime-profile", profile)
    assert quota["should_run"] is False
    assert quota["interaction_contract"]["mode"] == "terminal_no_followup"
    return {"settled_spends": spends, "independent_acceptance": "passed"}


def qualify(root: Path, codex: str, timeout: int) -> dict:
    from loopx.capabilities.benchmark_toolkit.native_codex_goal import (
        NativeGoalConfig, StdioNativeGoalTransport, run_native_goal_until_terminal,
    )

    project, runtime, launcher = setup(root)
    prompt = cli(launcher, "heartbeat-prompt", "--runtime-profile", "codex_cli",
                 "--goal-id", GOAL, "--agent-id", AGENT, "--cli-bin", str(launcher))
    cli(launcher, "quota", "should-run", "--runtime-profile", "codex_cli",
        "--goal-id", GOAL, "--agent-id", AGENT)
    config = NativeGoalConfig(
        cwd=str(project), objective=prompt["task_body"],
        task_instruction="Proceed with the active Goal. Read TASK.md. Use bin/loopx "
                         "for projected LoopX commands; preserve its isolated binding.",
        sandbox_policy={"type": "workspaceWrite", "writableRoots": [str(root)],
                        "networkAccess": True},  # Local TS worker needs loopback.
    )
    env = host_environment(root, launcher)
    shell_env = {key: value for key, value in env.items() if key != "OPENAI_API_KEY"}
    shell_settings = "{" + ", ".join(f"{key}={json.dumps(value)}" for key, value in shell_env.items()) + "}"
    command = [codex, "--enable", "goals", "-c", 'shell_environment_policy.inherit="none"',
               "-c", f"shell_environment_policy.set={shell_settings}",
               "-c", "project_doc_max_bytes=0", "app-server", "--stdio"]
    with tempfile.TemporaryFile(mode="w+") as stderr:
        with StdioNativeGoalTransport.spawn(command, cwd=str(project), env=env,
                                            stderr=stderr) as transport:
            turn = run_native_goal_until_terminal(transport, config, timeout_sec=timeout)
    assert turn.post_goal_status == "complete", "native_goal_did_not_complete"
    return {"status": "passed", "model_executed": True,
            "native_turns": turn.turn_completed_count,
            **verify_delivery(project, runtime, launcher, "codex_cli")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-live", action="store_true",
                        help="Explicit release qualification; permits real model cost.")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("timeout must be positive")
    if not args.release_live:
        result = {"status": "skipped", "reason": "release_opt_in_required", "model_executed": False}
    else:
        try:
            reason = prerequisite_failure(args.codex_bin)
            if reason:
                result = {"status": "skipped", "reason": reason, "model_executed": False}
            else:
                with tempfile.TemporaryDirectory(prefix="loopx-release-goal-") as raw:
                    result = qualify(Path(raw), args.codex_bin, args.timeout_seconds)
        except Exception as exc:
            # Never turn an attempted-but-failing qualification into an environment skip.
            # Raw errors can contain host paths, prompts or account details.
            result = {"status": "failed", "error_kind": type(exc).__name__}
    print(json.dumps(result, sort_keys=True))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
