#!/usr/bin/env python3
"""Release-only Claude Code + Doubao work-loop qualification, never a default live test."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
spec = importlib.util.spec_from_file_location("goal_release", REPO / "scripts/qualify-native-goal-release.py")
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)

from loopx.control_plane.testing.doubao_model_behavior_actor import (  # noqa: E402
    DOUBAO_SEED_EVOLVING_MODEL,
)

ARK_ANTHROPIC_BASE = "https://ark.cn-beijing.volces.com/api/compatible"


def run_host(command: list[str], *, cwd: Path, env: dict, timeout: float) -> str:
    """Bound output memory and clean this test's process group, including on timeout."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        finally:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait(timeout=10)
        assert code == 0, "claude_host_failed"
        stdout.seek(0)
        output = stdout.read(32 * 1024 * 1024 + 1)
        assert len(output) <= 32 * 1024 * 1024, "claude_output_exceeded_limit"
        return output.decode("utf-8")


def prerequisite_failure(claude: str) -> str | None:
    if not all(shutil.which(command) for command in (claude, "node", "git")):
        return "required_executable_unavailable"
    if not os.environ.get("ARK_API_KEY"):
        return "ark_api_key_unavailable"
    try:
        import mcp.server.fastmcp  # noqa: F401
    except ImportError:
        return "mcp_sdk_v1_unavailable"
    return None


def host_environment(root: Path, launcher: Path) -> dict[str, str]:
    # No user settings, OAuth/keychain import or persistent host installation.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDE_"))}
    env.update(
        ANTHROPIC_API_KEY=os.environ["ARK_API_KEY"],
        ANTHROPIC_BASE_URL=ARK_ANTHROPIC_BASE,
        ANTHROPIC_MODEL=DOUBAO_SEED_EVOLVING_MODEL,
        ANTHROPIC_DEFAULT_HAIKU_MODEL=DOUBAO_SEED_EVOLVING_MODEL,
        ANTHROPIC_DEFAULT_SONNET_MODEL=DOUBAO_SEED_EVOLVING_MODEL,
        ANTHROPIC_DEFAULT_OPUS_MODEL=DOUBAO_SEED_EVOLVING_MODEL,
        CLAUDE_CONFIG_DIR=str(root / "claude-config"),
        CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
        PATH=str(launcher.parent) + os.pathsep + os.environ.get("PATH", ""),
        PYTHONPATH=str(REPO),
    )
    return env


def qualify(root: Path, claude: str, timeout: int) -> dict:
    from loopx.claude_goal_mode.scripts.goalmode_cmd import write_loop_md

    project, runtime, launcher = shared.setup(root)
    write_loop_md(project, shared.GOAL, shared.AGENT)
    config = root / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"loopx": {
        "command": sys.executable,
        "args": [str(REPO / "loopx/claude_goal_mode/mcp/loopx_mcp.py")],
    }}}))
    command = [
        claude, "--bare", "--setting-sources", "", "--no-session-persistence",
        "--strict-mcp-config", "--mcp-config", str(config),
        "--model", DOUBAO_SEED_EVOLVING_MODEL,
        "--permission-mode", "dontAsk", "--allowedTools",
        "Read", "Edit", "Write", "Bash", "mcp__loopx__*",
        "--output-format", "stream-json", "--verbose", "-p",
        "Read .claude/loop.md and follow this project's active LoopX work contract. "
        "Read TASK.md for acceptance. Use the bound LoopX MCP tools; preserve the "
        "isolated project binding. Do not create timers in this headless qualification.",
    ]
    # This executes the actual per-iteration adapter, not Claude's interactive
    # /loop timer. Never report headless delivery as scheduler qualification.
    output = run_host(command, cwd=project, env=host_environment(root, launcher), timeout=timeout)
    events = [json.loads(line) for line in output.splitlines() if line.strip()]
    results = [e for e in events if e.get("type") == "result"]
    assert len(results) == 1 and results[0].get("is_error") is False, "claude_turn_failed"
    calls = [block.get("name") for event in events if event.get("type") == "assistant"
             for block in (event.get("message") or {}).get("content", [])
             if block.get("type") == "tool_use"]
    assert "mcp__loopx__should_run" in calls and "mcp__loopx__complete_task" in calls, "mcp_not_exercised"
    return {"status": "passed", "model_executed": True, "model": DOUBAO_SEED_EVOLVING_MODEL,
            "host": "claude_code", "scheduler_qualification": "not_run_headless",
            "mcp_tool_calls": sum(str(c).startswith("mcp__loopx__") for c in calls),
            **shared.verify_delivery(project, runtime, launcher, "claude_code")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-live", action="store_true")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("timeout must be positive")
    if not args.release_live:
        result = {"status": "skipped", "reason": "release_opt_in_required", "model_executed": False}
    else:
        try:
            reason = prerequisite_failure(args.claude_bin)
            if reason:
                result = {"status": "skipped", "reason": reason, "model_executed": False}
            else:
                with tempfile.TemporaryDirectory(prefix="loopx-claude-release-") as raw:
                    result = qualify(Path(raw), args.claude_bin, args.timeout_seconds)
        except Exception as exc:
            result = {"status": "failed", "error_kind": type(exc).__name__}
    print(json.dumps(result, sort_keys=True))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
