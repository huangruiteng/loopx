"""Terminal-Bench custom agent that drives host Codex TUI goal mode.

This module is intended to be passed to Terminal-Bench with:

    --agent-import-path terminal_bench_host_codex_goal_agent:HostCodexGoalAgent

The agent runs Codex on the host and tells it to operate on the task container
with `docker exec`. That keeps Codex authentication and agent runtime on the
stable host layer while the benchmark case container only runs task commands.
"""

from __future__ import annotations

import shlex
import subprocess
import time
import uuid
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for _path in (SCRIPT_DIR, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from codex_app_server_goal_driver import (
    CodexAppServerGoalDriverError,
    compact_turn_metadata,
    observe_codex_app_server_goal_turn,
    start_codex_app_server_goal_turn,
)
from loopx.benchmark_case_state import (
    benchmark_case_lifecycle_contract,
    render_benchmark_case_lifecycle_contract_lines,
)

LONG_RUN_DEFAULT_GOAL_TIMEOUT_SEC = 10800.0


try:  # pragma: no cover - exercised on the benchmark host.
    from terminal_bench.agents.base_agent import AgentResult, BaseAgent
    from terminal_bench.agents.failure_mode import FailureMode
except Exception:  # pragma: no cover - keeps local smoke import dependency-free.

    class BaseAgent:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class AgentResult:  # type: ignore[no-redef]
        def __init__(
            self,
            *,
            total_input_tokens: int = 0,
            total_output_tokens: int = 0,
            failure_mode: Any = None,
        ) -> None:
            self.total_input_tokens = total_input_tokens
            self.total_output_tokens = total_output_tokens
            self.failure_mode = failure_mode

    class FailureMode:  # type: ignore[no-redef]
        AGENT_TIMEOUT = "agent_timeout"


def build_codex_tui_command(*, codex_bin: str = "codex", model_name: str | None = None) -> list[str]:
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
    container_name: str,
    instruction: str,
    marker_path: Path,
    task_workdir: str = "/app",
    loopx_case_lifecycle_packet: str = "",
) -> str:
    marker_cmd = f"touch {shlex.quote(str(marker_path))}"
    docker_exec = (
        f"docker exec {shlex.quote(container_name)} "
        f"bash -lc 'cd {shlex.quote(task_workdir)} && <command>'"
    )
    prompt = f"""
You are solving a Terminal-Bench task on this host using native Codex Goal mode.

Task container name: {container_name}
Task working directory inside the container: {task_workdir}
Use host shell commands such as:
  {docker_exec}

Before planning or editing, first verify container command execution with:
  docker exec {shlex.quote(container_name)} bash -lc 'cd {shlex.quote(task_workdir)} && pwd'

Do not modify tests. Complete the task inside the task container only.

Task instruction:
{instruction}

When and only when the task is complete, run this exact host command so the harness can observe completion:
{marker_cmd}
""".strip()
    packet = loopx_case_lifecycle_packet.strip()
    if packet:
        prompt += (
            "\n\nLoopX case lifecycle packet:\n"
            f"{packet}\n\n"
            "Use this packet as observational control-plane context. Keep the official "
            "Terminal-Bench scorer authoritative, do not expose reward or verifier output "
            "during the agent loop, and do not rely on runner-internal polling alone when "
            "claiming LoopX treatment evidence."
        )
    return prompt


def build_loopx_case_lifecycle_packet(
    *,
    mode: str = "codex_goal_mode_baseline",
    packet_mode: str = "none",
    benchmark_id: str = "terminal-bench",
    case_id: str = "current-case",
    arm_id: str = "codex_loopx_treatment",
    max_rounds: int = 5,
) -> tuple[str, dict[str, object] | None]:
    if mode != "codex_loopx" or packet_mode == "none":
        return "", None
    contract = benchmark_case_lifecycle_contract(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arm_id=arm_id,
        max_rounds=max_rounds,
    )
    lines = [
        "terminal_bench_loopx_case_lifecycle_packet_v0:",
        f"  packet_mode: {packet_mode}",
        "  benchmark_family: harbor",
    ]
    lines.extend(render_benchmark_case_lifecycle_contract_lines(contract))
    return "\n".join(lines), contract


class HostCodexGoalAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "host-codex-goal"

    def __init__(
        self,
        model_name: str | None = None,
        goal_timeout_sec: str | int | float = LONG_RUN_DEFAULT_GOAL_TIMEOUT_SEC,
        work_root: str = "/tmp/loopx-terminal-bench",
        network_bootstrap_script: str = "",
        task_workdir: str = "/app",
        codex_bin: str = "codex",
        goal_surface: str = "tui",
        reasoning_effort: str | None = "high",
        app_server_wait_for_completion: str | bool = False,
        app_server_response_timeout_sec: str | int | float = 30,
        startup_delay_sec: str | int | float = 5,
        poll_interval_sec: str | int | float = 5,
        loopx_mode: str = "codex_goal_mode_baseline",
        loopx_access_packet_mode: str = "none",
        loopx_benchmark_id: str = "terminal-bench",
        loopx_case_id: str = "current-case",
        loopx_arm_id: str = "codex_loopx_treatment",
        loopx_max_rounds: str | int = 5,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.goal_timeout_sec = float(goal_timeout_sec)
        self.work_root = Path(work_root).expanduser()
        self.network_bootstrap_script = (
            Path(network_bootstrap_script).expanduser()
            if network_bootstrap_script
            else None
        )
        self.task_workdir = task_workdir
        self.codex_bin = codex_bin
        self.goal_surface = goal_surface
        self.reasoning_effort = reasoning_effort
        self.app_server_wait_for_completion = _coerce_bool(app_server_wait_for_completion)
        self.app_server_response_timeout_sec = float(app_server_response_timeout_sec)
        self.startup_delay_sec = float(startup_delay_sec)
        self.poll_interval_sec = float(poll_interval_sec)
        self.loopx_mode = loopx_mode
        self.loopx_access_packet_mode = loopx_access_packet_mode
        self.loopx_benchmark_id = loopx_benchmark_id
        self.loopx_case_id = loopx_case_id
        self.loopx_arm_id = loopx_arm_id
        self.loopx_max_rounds = int(loopx_max_rounds)

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

    def _prepare_container_network(self, session: Any) -> None:
        if not self.network_bootstrap_script:
            return
        if not self.network_bootstrap_script.is_file():
            raise RuntimeError("network bootstrap script not found")
        session.copy_to_container(
            self.network_bootstrap_script,
            container_dir="/tmp",
            container_filename="prepare_tbench_network.sh",
        )
        result = session.container.exec_run(["bash", "/tmp/prepare_tbench_network.sh"])
        if result.exit_code != 0:
            detail = result.output.decode(errors="replace")[-2000:]
            raise RuntimeError(f"network bootstrap failed: {detail}")

    def perform_task(
        self,
        instruction: str,
        session: Any,
        logging_dir: Path | None = None,
    ) -> AgentResult:
        del logging_dir
        self._prepare_container_network(session)
        container_name = session.container.name
        run_id = uuid.uuid4().hex[:10]
        work_dir = self.work_root / f"host-codex-goal-{run_id}"
        work_dir.mkdir(parents=True, exist_ok=True)
        marker = work_dir / "done.marker"
        capture_path = work_dir / "tmux_capture.txt"
        prompt_path = work_dir / "prompt.txt"
        tmux_name = f"gh_tb_goal_{run_id}"
        loopx_packet, case_lifecycle_contract = build_loopx_case_lifecycle_packet(
            mode=self.loopx_mode,
            packet_mode=self.loopx_access_packet_mode,
            benchmark_id=self.loopx_benchmark_id,
            case_id=self.loopx_case_id,
            arm_id=self.loopx_arm_id,
            max_rounds=self.loopx_max_rounds,
        )

        prompt = build_host_goal_prompt(
            container_name=container_name,
            instruction=instruction,
            marker_path=marker,
            task_workdir=self.task_workdir,
            loopx_case_lifecycle_packet=loopx_packet,
        )
        prompt_path.write_text(prompt, encoding="utf-8")

        if self.goal_surface == "app_server":
            try:
                turn = start_codex_app_server_goal_turn(
                    codex_bin=self.codex_bin,
                    work_dir=work_dir,
                    objective="Complete the Terminal-Bench task using the task container.",
                    prompt=prompt,
                    model_name=self.model_name,
                    reasoning_effort=self.reasoning_effort,
                    response_timeout_sec=self.app_server_response_timeout_sec,
                    wait_for_completion=False,
                )
            except CodexAppServerGoalDriverError as exc:
                (work_dir / "app_server_goal_turn.compact.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "terminal_bench_host_codex_goal_agent_v0",
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
                return AgentResult(
                    total_input_tokens=0,
                    total_output_tokens=0,
                    failure_mode=FailureMode.AGENT_TIMEOUT,
                )

            def write_compact(first_blocker: str = "") -> None:
                compact = compact_turn_metadata(turn)
                compact.update(
                    {
                        "goal_surface": "app_server",
                        "app_server_wait_for_completion_requested": self.app_server_wait_for_completion,
                        "app_server_completion_hard_gate": False,
                        "completion_marker_observed": marker.exists(),
                        "first_blocker": first_blocker,
                        "loopx_mode": self.loopx_mode,
                        "loopx_access_packet_mode": self.loopx_access_packet_mode,
                        "loopx_case_lifecycle_packet_injected": bool(
                            loopx_packet
                        ),
                        "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                    }
                )
                (work_dir / "app_server_goal_turn.compact.json").write_text(
                    json.dumps(compact, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

            deadline = time.time() + self.goal_timeout_sec
            try:
                while time.time() < deadline:
                    observe_codex_app_server_goal_turn(turn)
                    if marker.exists():
                        observe_codex_app_server_goal_turn(
                            turn,
                            timeout_sec=min(2.0, self.poll_interval_sec),
                        )
                        write_compact()
                        turn.terminate()
                        return AgentResult(total_input_tokens=0, total_output_tokens=0)
                    time.sleep(self.poll_interval_sec)
                observe_codex_app_server_goal_turn(turn)
                write_compact("terminal_bench_completion_marker_missing_before_timeout")
                return AgentResult(
                    total_input_tokens=0,
                    total_output_tokens=0,
                    failure_mode=FailureMode.AGENT_TIMEOUT,
                )
            finally:
                turn.terminate()

        if self.goal_surface != "tui":
            raise ValueError(f"unsupported goal_surface: {self.goal_surface}")

        command = build_codex_tui_command(
            codex_bin=self.codex_bin,
            model_name=self.model_name,
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
                " ".join(shlex.quote(part) for part in command),
            ],
            check=True,
        )
        time.sleep(self.startup_delay_sec)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)
        time.sleep(self.startup_delay_sec)
        self._tmux("send-keys", "-t", tmux_name, "/goal", "C-m", check=False)
        time.sleep(self.startup_delay_sec)
        self._tmux("load-buffer", "-b", f"gh_prompt_{run_id}", str(prompt_path), check=True)
        self._tmux("paste-buffer", "-d", "-b", f"gh_prompt_{run_id}", "-t", tmux_name, check=True)
        time.sleep(1)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)
        time.sleep(1)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)

        deadline = time.time() + self.goal_timeout_sec
        while time.time() < deadline:
            if marker.exists():
                capture_path.write_text(self._capture(tmux_name), encoding="utf-8")
                self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
                return AgentResult(total_input_tokens=0, total_output_tokens=0)
            time.sleep(self.poll_interval_sec)
            capture_path.write_text(self._capture(tmux_name), encoding="utf-8")

        self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
        return AgentResult(
            total_input_tokens=0,
            total_output_tokens=0,
            failure_mode=FailureMode.AGENT_TIMEOUT,
        )
