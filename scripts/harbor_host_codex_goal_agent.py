"""Harbor custom agent that drives host Codex TUI goal mode.

Pass this module to Harbor with:

    --agent-import-path harbor_host_codex_goal_agent:HarborHostCodexGoalAgent

Codex runs on the benchmark host.  A tiny host-side command bridge forwards
commands into Harbor's environment through ``environment.exec()``, so the task
container does not need Codex auth or agent runtime downloads.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from codex_app_server_goal_driver import (
    CodexAppServerGoalDriverError,
    compact_turn_metadata,
    start_codex_app_server_goal_turn,
)


try:  # pragma: no cover - exercised on the benchmark host.
    from harbor.agents.base import BaseAgent
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext
except Exception:  # pragma: no cover - keeps local smoke import dependency-free.

    class BaseAgent:  # type: ignore[no-redef]
        def __init__(
            self,
            logs_dir: Path,
            model_name: str | None = None,
            **kwargs: Any,
        ) -> None:
            del kwargs
            self.logs_dir = Path(logs_dir)
            self.model_name = model_name

    class BaseEnvironment:  # type: ignore[no-redef]
        pass

    class AgentContext:  # type: ignore[no-redef]
        metadata: dict[str, Any] | None = None


BRIDGE_SCRIPT_TEMPLATE = """#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
import time
import uuid

REQUEST_DIR = pathlib.Path("__GOAL_HARNESS_REQUEST_DIR__")

parser = argparse.ArgumentParser(description="Forward a command into Harbor environment.exec")
parser.add_argument("--cwd", default="")
parser.add_argument("--timeout-sec", type=float, default=600)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()

if not args.command:
    print("missing command", file=sys.stderr)
    raise SystemExit(2)

if args.command[0] == "--":
    args.command = args.command[1:]

command = " ".join(args.command) if len(args.command) > 1 else args.command[0]
request_id = uuid.uuid4().hex
request = REQUEST_DIR / f"{request_id}.request.json"
response = REQUEST_DIR / f"{request_id}.response.json"
tmp = REQUEST_DIR / f"{request_id}.tmp"
tmp.write_text(json.dumps({
    "command": command,
    "cwd": args.cwd,
    "timeout_sec": args.timeout_sec,
}, ensure_ascii=False))
tmp.rename(request)
deadline = time.time() + args.timeout_sec + 30
while time.time() < deadline:
    if response.exists():
        payload = json.loads(response.read_text())
        stdout = payload.get("stdout") or ""
        stderr = payload.get("stderr") or ""
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        raise SystemExit(int(payload.get("return_code") or 0))
    time.sleep(0.5)

print("harbor-env-exec timed out waiting for response", file=sys.stderr)
raise SystemExit(124)
"""


def build_codex_tui_command(
    *,
    codex_bin: str = "codex",
    model_name: str | None = None,
) -> list[str]:
    command = [
        codex_bin,
        "--no-alt-screen",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "danger-full-access",
    ]
    if model_name:
        command.extend(["--model", model_name])
    return command


def _coerce_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() not in {"0", "false", "no", "off"}


def build_host_goal_prompt(
    *,
    instruction: str,
    bridge_command: Path,
    marker_path: Path,
    task_workdir: str = "/app",
) -> str:
    bridge = shlex.quote(str(bridge_command))
    marker_cmd = f"touch {shlex.quote(str(marker_path))}"
    task_workdir_arg = shlex.quote(task_workdir)
    return f"""
You are solving a Harbor benchmark task using native Codex Goal mode on the host.

Run task-environment commands through this host bridge:
  {bridge} --cwd {task_workdir_arg} -- <command>

Before planning or editing, first verify the bridge with this harmless command:
  {bridge} --cwd {task_workdir_arg} -- pwd

Do not modify tests. Complete the task inside the Harbor environment only.

Task instruction:
{instruction}

When and only when the task is complete, run this exact host command so the
harness can observe completion:
{marker_cmd}
""".strip()


class HarborHostCodexGoalAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "harbor-host-codex-goal"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        goal_timeout_sec: str | int | float = 300,
        codex_bin: str = "codex",
        task_workdir: str = "/app",
        goal_surface: str = "tui",
        reasoning_effort: str | None = "high",
        app_server_wait_for_completion: str | bool = True,
        app_server_response_timeout_sec: str | int | float = 30,
        startup_delay_sec: str | int | float = 5,
        poll_interval_sec: str | int | float = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.goal_timeout_sec = float(goal_timeout_sec)
        self.codex_bin = codex_bin
        self.task_workdir = task_workdir
        self.goal_surface = goal_surface
        self.reasoning_effort = reasoning_effort
        self.app_server_wait_for_completion = _coerce_bool(app_server_wait_for_completion)
        self.app_server_response_timeout_sec = float(app_server_response_timeout_sec)
        self.startup_delay_sec = float(startup_delay_sec)
        self.poll_interval_sec = float(poll_interval_sec)
        self._served_request_count = 0

    def version(self) -> str:
        return "0.3.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        del environment

    def _tmux(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["tmux", *args],
            check=check,
            capture_output=True,
            text=True,
        )

    def _capture(self, session_name: str) -> str:
        result = self._tmux("capture-pane", "-pt", session_name, "-S", "-300", check=False)
        return result.stdout or result.stderr or ""

    @staticmethod
    def _write_bridge_script(path: Path, request_dir: Path) -> None:
        path.write_text(
            BRIDGE_SCRIPT_TEMPLATE.replace(
                "__GOAL_HARNESS_REQUEST_DIR__",
                str(request_dir),
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)

    async def _serve_bridge_requests(
        self,
        environment: BaseEnvironment,
        request_dir: Path,
    ) -> None:
        for request in sorted(request_dir.glob("*.request.json")):
            request_id = request.name.removesuffix(".request.json")
            running = request_dir / f"{request_id}.running.json"
            response = request_dir / f"{request_id}.response.json"
            try:
                request.rename(running)
            except FileNotFoundError:
                continue
            try:
                payload = json.loads(running.read_text(encoding="utf-8"))
                timeout_sec = int(float(payload.get("timeout_sec") or 600))
                cwd = payload.get("cwd") or None
                result = await environment.exec(
                    command=str(payload["command"]),
                    cwd=cwd,
                    timeout_sec=timeout_sec,
                )
                response.write_text(
                    json.dumps(
                        {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "return_code": result.return_code,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception as exc:  # pragma: no cover - benchmark-host failure path.
                response.write_text(
                    json.dumps(
                        {
                            "stdout": "",
                            "stderr": f"harbor-env-exec bridge failed: {exc}",
                            "return_code": 125,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            finally:
                self._served_request_count += 1
                running.unlink(missing_ok=True)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        run_id = uuid.uuid4().hex[:10]
        work_dir = self.logs_dir / f"host-codex-goal-{run_id}"
        request_dir = work_dir / "requests"
        bin_dir = work_dir / "bin"
        work_dir.mkdir(parents=True, exist_ok=True)
        request_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.mkdir(parents=True, exist_ok=True)

        bridge = bin_dir / "harbor-env-exec"
        marker = work_dir / "done.marker"
        prompt_path = work_dir / "prompt.txt"
        capture_path = work_dir / "tmux_capture.txt"
        tmux_name = f"gh_harbor_goal_{run_id}"
        self._write_bridge_script(bridge, request_dir)

        prompt = build_host_goal_prompt(
            instruction=instruction,
            bridge_command=bridge,
            marker_path=marker,
            task_workdir=self.task_workdir,
        )
        prompt_path.write_text(prompt, encoding="utf-8")

        if self.goal_surface == "app_server":
            try:
                turn_task = asyncio.create_task(
                    asyncio.to_thread(
                        start_codex_app_server_goal_turn,
                        codex_bin=self.codex_bin,
                        work_dir=work_dir,
                        objective="Complete the Harbor benchmark task using the task environment bridge.",
                        prompt=prompt,
                        model_name=self.model_name,
                        reasoning_effort=self.reasoning_effort,
                        response_timeout_sec=self.app_server_response_timeout_sec,
                        wait_for_completion=self.app_server_wait_for_completion,
                        turn_timeout_sec=self.goal_timeout_sec,
                    )
                )
                while not turn_task.done():
                    await self._serve_bridge_requests(environment, request_dir)
                    await asyncio.sleep(self.poll_interval_sec)
                turn = await turn_task
            except CodexAppServerGoalDriverError as exc:
                (work_dir / "app_server_goal_turn.compact.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "harbor_host_codex_goal_agent_v0",
                            "goal_surface": "app_server",
                            "ok": False,
                            "first_blocker": "codex_app_server_goal_turn_failed",
                            "error_type": type(exc).__name__,
                            "raw_transcript_recorded": False,
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                context.metadata = {
                    "goal_harness_agent": self.name(),
                    "completion_marker_observed": False,
                    "bridge_request_count": self._served_request_count,
                    "first_blocker": "codex_app_server_goal_turn_failed",
                }
                return
            await self._serve_bridge_requests(environment, request_dir)
            compact = compact_turn_metadata(turn)
            compact.update(
                {
                    "goal_surface": "app_server",
                    "app_server_wait_for_completion": self.app_server_wait_for_completion,
                    "completion_marker_observed": marker.exists(),
                    "bridge_request_count": self._served_request_count,
                    "first_blocker": ""
                    if marker.exists()
                    else "harbor_completion_marker_missing_after_turn_completed",
                }
            )
            (work_dir / "app_server_goal_turn.compact.json").write_text(
                json.dumps(compact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if self.app_server_wait_for_completion:
                turn.terminate()
                context.metadata = {
                    "goal_harness_agent": self.name(),
                    "completion_marker_observed": marker.exists(),
                    "bridge_request_count": self._served_request_count,
                    "goal_surface": "app_server",
                    "turn_completed_observed": bool(turn.turn_completed_observed),
                    "first_blocker": ""
                    if marker.exists()
                    else "harbor_completion_marker_missing_after_turn_completed",
                }
                return
            deadline = time.time() + self.goal_timeout_sec
            try:
                while time.time() < deadline:
                    await self._serve_bridge_requests(environment, request_dir)
                    if marker.exists():
                        turn.terminate()
                        context.metadata = {
                            "goal_harness_agent": self.name(),
                            "completion_marker_observed": True,
                            "bridge_request_count": self._served_request_count,
                            "goal_surface": "app_server",
                        }
                        return
                    await asyncio.sleep(self.poll_interval_sec)
            finally:
                turn.terminate()
            context.metadata = {
                "goal_harness_agent": self.name(),
                "completion_marker_observed": False,
                "bridge_request_count": self._served_request_count,
                "goal_surface": "app_server",
                "first_blocker": "harbor_host_codex_app_server_goal_timeout",
            }
            return

        if self.goal_surface != "tui":
            raise ValueError(f"unsupported goal_surface: {self.goal_surface}")

        command = build_codex_tui_command(
            codex_bin=self.codex_bin,
            model_name=self.model_name,
        )
        shell_command = (
            f"PATH={shlex.quote(str(bin_dir))}:$PATH "
            + " ".join(shlex.quote(part) for part in command)
        )
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                tmux_name,
                "-c",
                str(work_dir),
                shell_command,
            ],
            check=True,
        )
        await asyncio.sleep(self.startup_delay_sec)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)
        await asyncio.sleep(self.startup_delay_sec)
        self._tmux("send-keys", "-t", tmux_name, "/goal", "C-m", check=False)
        await asyncio.sleep(self.startup_delay_sec)
        self._tmux("load-buffer", "-b", f"gh_prompt_{run_id}", str(prompt_path), check=True)
        self._tmux("paste-buffer", "-d", "-b", f"gh_prompt_{run_id}", "-t", tmux_name, check=True)
        await asyncio.sleep(1)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)
        await asyncio.sleep(1)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)

        deadline = time.time() + self.goal_timeout_sec
        while time.time() < deadline:
            await self._serve_bridge_requests(environment, request_dir)
            if marker.exists():
                capture_path.write_text(self._capture(tmux_name), encoding="utf-8")
                self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
                context.metadata = {
                    "goal_harness_agent": self.name(),
                    "completion_marker_observed": True,
                    "bridge_request_count": self._served_request_count,
                }
                return
            capture_path.write_text(self._capture(tmux_name), encoding="utf-8")
            await asyncio.sleep(self.poll_interval_sec)

        self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
        context.metadata = {
            "goal_harness_agent": self.name(),
            "completion_marker_observed": False,
            "bridge_request_count": self._served_request_count,
            "first_blocker": "harbor_host_codex_goal_timeout",
        }
