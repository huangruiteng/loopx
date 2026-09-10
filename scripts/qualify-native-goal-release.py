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
        '# Ledger\n\n## Objective\n\nDeliver TASK.md, validate and settle both Todos.\n\n'
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
    from loopx.control_plane.quota.settlement import read_heartbeat_settlement

    assert {t["todo_id"] for t in todos if t.get("status") == "done"} == TODOS
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
        assert readback and readback.writeback and readback.spend
    return len(spends)


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
    command = [codex, "--enable", "goals", "-c", 'shell_environment_policy.inherit="all"',
               "-c", "project_doc_max_bytes=0", "app-server", "--stdio"]
    with tempfile.TemporaryFile(mode="w+") as stderr:
        with StdioNativeGoalTransport.spawn(command, cwd=str(project), env=dict(os.environ),
                                            stderr=stderr) as transport:
            turn = run_native_goal_until_terminal(transport, config, timeout_sec=timeout)
    assert turn.post_goal_status == "complete", "native_goal_did_not_complete"
    assert (project / "TASK.md").read_bytes() == (FIXTURE / "TASK.md").read_bytes()
    oracle = subprocess.run([sys.executable, str(FIXTURE / "verify.py"), str(project)],
                            capture_output=True, timeout=60)
    assert oracle.returncode == 0, "independent_acceptance_failed"
    todos = cli(launcher, "todo", "list", "--goal-id", GOAL, "--role", "agent")["todos"]
    spends = verify_settlement(runtime, todos)
    quota = cli(launcher, "quota", "should-run", "--goal-id", GOAL,
                "--agent-id", AGENT, "--runtime-profile", "codex_cli")
    assert quota["should_run"] is False
    assert quota["interaction_contract"]["mode"] == "terminal_no_followup"
    return {"status": "passed", "model_executed": True,
            "native_turns": turn.turn_completed_count, "settled_spends": spends,
            "independent_acceptance": "passed"}


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
