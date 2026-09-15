"""Harbor agent for LoopX generic_cli heartbeat + fresh Codex exec wakes."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from harbor.agents.installed.base import with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trajectories import FinalMetrics, Trajectory
from harbor.utils.trajectory_utils import format_trajectory_json

from codex_offline import CodexOffline


_ROOT = "/opt/loopx-lhtb"
_SRC = f"{_ROOT}/source"
_PYTHON = f"{_ROOT}/python"
_NODE = f"{_ROOT}/node"
_PROFILE = f"{_ROOT}/profile"
_PROFILE_HOME = f"{_PROFILE}/home"
_SHARED_CODEX_HOME = f"{_PROFILE}/codex-home"
_SHARED_SKILLS = f"{_SHARED_CODEX_HOME}/skills"
_CLI = f"{_PROFILE}/bin/loopx"
_CONTROL = f"{_ROOT}/control"
_REGISTRY = f"{_CONTROL}/registry.json"
_LOOPX_RUNTIME = f"{_ROOT}/state/runtime"
_SCHEDULER_STATE = f"{_CONTROL}/scheduler-state.json"
_TASK_DOC = f"{_CONTROL}/task.md"
_BASH_ENV = f"{_CONTROL}/bash-env"
_TURN_ROOT = f"{_ROOT}/turns"
_WAKE_SCRIPT = f"{_ROOT}/runtime/wake_once.py"
_WAKE_LOG_DIR = "/logs/agent/wakes"
_GOAL_ID = "lhtb-heartbeat-goal"
_AGENT_ID = "lhtb-codex-heartbeat"
_REPLAN_AFTER_TODOS = 3


class LoopxHeartbeatCodex(CodexOffline):
    """One independent LoopX control plane per Harbor trial."""

    _phase_number = 0

    @staticmethod
    def name() -> str:
        return "loopx-generic-cli-heartbeat-codex"

    def _container_id(self, environment: BaseEnvironment) -> str:
        from harbor.environments.docker.docker import (
            _sanitize_docker_compose_project_name,
        )

        project = _sanitize_docker_compose_project_name(environment.session_id)
        completed = subprocess.run(
            [
                "docker", "ps", "-q",
                "--filter", f"label=com.docker.compose.project={project}",
                "--filter", "label=com.docker.compose.service=main",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        ids = completed.stdout.split()
        if len(ids) != 1:
            raise RuntimeError(
                f"expected one main container for compose project {project}, got {ids}"
            )
        return ids[0]

    @staticmethod
    def _copy_tree(container_id: str, source: Path, destination: str) -> None:
        if not source.is_dir():
            raise FileNotFoundError(f"required directory is missing: {source}")
        completed = subprocess.run(
            ["docker", "cp", f"{source}/.", f"{container_id}:{destination}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1200,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"docker cp {source} failed: {(completed.stderr or completed.stdout)[-500:]}"
            )

    @staticmethod
    def _copy_git_snapshot(container_id: str, source: Path, destination: str) -> None:
        """Stage only files tracked by the pinned LoopX commit.

        The LoopX checkout also hosts benchmark runs. Copying the working tree
        would expose prior trajectories and artifacts inside the agent container.
        """
        archive = subprocess.Popen(
            ["git", "-C", str(source), "archive", "--format=tar", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if archive.stdout is None:
            archive.kill()
            raise RuntimeError("could not open LoopX git archive stream")
        extract = subprocess.Popen(
            ["docker", "exec", "-i", container_id, "tar", "-x", "-C", destination],
            stdin=archive.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        archive.stdout.close()
        try:
            extract_stdout, extract_stderr = extract.communicate(timeout=1200)
        except subprocess.TimeoutExpired:
            extract.kill()
            archive.kill()
            extract.communicate()
            archive.communicate()
            raise RuntimeError("timed out staging the LoopX git snapshot")
        archive_stderr = archive.stderr.read() if archive.stderr is not None else b""
        archive_returncode = archive.wait(timeout=30)
        if archive_returncode != 0 or extract.returncode != 0:
            detail = archive_stderr or extract_stderr or extract_stdout
            raise RuntimeError(
                "failed to stage clean LoopX git snapshot: "
                + detail.decode("utf-8", errors="replace")[-500:]
            )

    def _profile_env(self) -> dict[str, str]:
        return {
            "HOME": _PROFILE_HOME,
            "CODEX_HOME": _SHARED_CODEX_HOME,
            "PATH": f"{_NODE}/bin:{_PROFILE}/bin:/usr/local/bin:/usr/bin:/bin",
            "LOOPX_PYTHON": f"{_PYTHON}/bin/python3",
            "LOOPX_PROMOTE_DEFAULT": "1",
            "LOOPX_INSTALL_CANARY": "0",
            "LOOPX_BIN_DIR": f"{_PROFILE}/bin",
            "LOOPX_RELEASES_DIR": f"{_PROFILE}/releases",
            "LOOPX_RELEASE_ID": "lhtb-generic-cli-heartbeat",
            "LOOPX_MAN_ROOT": f"{_PROFILE}/man",
            "LOOPX_MAN_DIR": f"{_PROFILE}/man/man1",
            "LOOPX_SHELL_PROFILE": f"{_PROFILE_HOME}/.profile",
            "LOOPX_SKILLS_DIR": _SHARED_SKILLS,
            "LOOPX_INSTALL_SLASH_COMMANDS": "0",
            "LOOPX_INSTALL_OPENCODE": "0",
            "LOOPX_INSTALL_CLAUDE": "0",
            "LOOPX_SKILL_DEDUPE_OTHER_ROOT": "0",
            # Codex tool calls use `bash -lc`, whose login profile may replace
            # PATH. BASH_ENV restores the staged Node for LoopX subprocesses.
            "BASH_ENV": _BASH_ENV,
        }

    async def install(self, environment: BaseEnvironment) -> None:
        await super().install(environment)

        loopx_src = Path(os.environ["LOOPX_SRC_DIR"]).resolve()
        portable_python = Path(os.environ["LOOPX_PORTABLE_PYTHON"]).resolve()
        node_root = Path(os.environ["LOOPX_NODE_DIR"]).resolve()
        wake_source = Path(__file__).resolve().parent.parent / "runtime" / "wake_once.py"
        expected_commit = os.environ.get("LOOPX_EXPECTED_COMMIT", "").strip()

        actual_commit = subprocess.run(
            ["git", "-C", str(loopx_src), "rev-parse", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        ).stdout.strip()
        if expected_commit and actual_commit != expected_commit:
            raise RuntimeError(
                f"LoopX commit mismatch: expected {expected_commit}, got {actual_commit}"
            )

        await self.exec_as_root(
            environment,
            command=(
                f"mkdir -p {_SRC} {_PYTHON} {_NODE} {_PROFILE_HOME} "
                f"{_SHARED_CODEX_HOME} {_PROFILE}/bin {_PROFILE}/releases {_PROFILE}/man "
                f"{_CONTROL} "
                f"{_LOOPX_RUNTIME} {_TURN_ROOT} {os.path.dirname(_WAKE_SCRIPT)} "
                f"{_WAKE_LOG_DIR}; chmod -R 0777 {_ROOT} {_WAKE_LOG_DIR}"
            ),
            timeout_sec=180,
        )
        container_id = self._container_id(environment)
        self._copy_git_snapshot(container_id, loopx_src, _SRC)
        self._copy_tree(container_id, portable_python, _PYTHON)
        self._copy_tree(container_id, node_root, _NODE)
        await environment.upload_file(wake_source, _WAKE_SCRIPT)
        await self.exec_as_root(
            environment,
            command=(
                f"chmod 0755 {_WAKE_SCRIPT}; "
                f"printf '%s\\n' 'export PATH={_NODE}/bin:$PATH' > {_BASH_ENV}; "
                f"chmod 0644 {_BASH_ENV}; "
                f"find {_SRC} -maxdepth 2 \\( -name '*.egg-info' -o "
                f"-name '*.dist-info' \\) -exec rm -rf {{}} +; "
                f"chmod -R a+rX {_SRC} {_PYTHON} {_NODE}; "
                f"chmod -R a+rwX {_PROFILE} {_CONTROL} {_TURN_ROOT} {_WAKE_LOG_DIR}"
            ),
            timeout_sec=300,
        )
        install = await self.exec_as_agent(
            environment,
            command=f"bash {_SRC}/scripts/install-local.sh",
            env=self._profile_env(),
            timeout_sec=1200,
        )
        if "error" in (install.stderr or "").lower():
            self.logger.debug("LoopX installer stderr: %s", install.stderr[-1000:])

        doctor = await self.exec_as_agent(
            environment,
            command=f"{_CLI} --format json doctor --agent-type codex-cli",
            env=self._profile_env(),
            timeout_sec=300,
        )
        try:
            doctor_payload = json.loads(doctor.stdout or "")
        except json.JSONDecodeError as exc:
            raise RuntimeError("LoopX doctor returned invalid JSON") from exc
        if doctor_payload.get("ok") is not True:
            raise RuntimeError(f"LoopX doctor failed: {doctor_payload}")

        receipt = {
            "loopx_commit": actual_commit,
            "runtime_profile": "generic_cli",
            "codex_driver": "fresh_exec_per_wake",
            "onboarding_connection_validation": "provider-prevalidated",
            "login_shell_node_path": _BASH_ENV,
            "scheduler_terminal_packet_compatibility": True,
            "replan_after_completed_todos": _REPLAN_AFTER_TODOS,
        }
        await self.exec_as_agent(
            environment,
            command=(
                f"printf %s {shlex.quote(json.dumps(receipt, sort_keys=True))} "
                f"> /logs/agent/loopx-install.json"
            ),
            env=self._profile_env(),
        )

    async def _write_task_document(
        self, environment: BaseEnvironment, instruction: str
    ) -> None:
        descriptor, name = tempfile.mkstemp(prefix="lhtb-loopx-task-", suffix=".md")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write("# Current LHTB task\n\n")
                handle.write(instruction.strip())
                handle.write("\n")
            await environment.upload_file(Path(name), _TASK_DOC)
            await self.exec_as_root(
                environment,
                command=f"chmod 0644 {_TASK_DOC}",
            )
        finally:
            Path(name).unlink(missing_ok=True)

    async def _loopx(
        self,
        environment: BaseEnvironment,
        args: list[str],
        *,
        cwd: str,
        require_ok: bool = True,
    ) -> dict:
        argv = [
            _CLI,
            "--format", "json",
            "--registry", _REGISTRY,
            "--runtime-root", _LOOPX_RUNTIME,
            *args,
        ]
        result = await self.exec_as_agent(
            environment,
            command=shlex.join(argv),
            env=self._profile_env(),
            cwd=cwd,
            timeout_sec=300,
        )
        text = (result.stdout or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LoopX command returned invalid JSON: {text[:300]}") from exc
        if require_ok and payload.get("ok") is False:
            raise RuntimeError(f"LoopX command failed: {payload.get('error')}")
        return payload

    async def _registry_exists(self, environment: BaseEnvironment) -> bool:
        result = await environment.exec(command=f"test -s {_REGISTRY}")
        return result.return_code == 0

    async def _prepare_phase(
        self, environment: BaseEnvironment, instruction: str, *, cwd: str
    ) -> None:
        await self._write_task_document(environment, instruction)
        if not await self._registry_exists(environment):
            await self._loopx(
                environment,
                [
                    "bootstrap",
                    "--project", ".",
                    "--goal-id", _GOAL_ID,
                    "--objective",
                    "Complete the current LHTB task through validated LoopX Todos.",
                    "--goal-doc", _TASK_DOC,
                    "--adapter-kind", "read_only_project_map_v0",
                    "--adapter-status", "connected-read-only",
                    "--write-scope", "**",
                    "--no-onboarding-scan",
                    "--onboarding-connection-validation", "provider-prevalidated",
                    "--begin-autonomous-advance",
                    "--codex-app-heartbeat", "no",
                    "--no-global-sync",
                ],
                cwd=cwd,
            )
            await self._loopx(
                environment,
                [
                    "configure-goal",
                    "--goal-id", _GOAL_ID,
                    "--registered-agent", _AGENT_ID,
                    "--execution-replan-after-todos", str(_REPLAN_AFTER_TODOS),
                    "--agent-work-mode", f"{_AGENT_ID}=active",
                    "--execute",
                ],
                cwd=cwd,
            )
        else:
            await self._loopx(
                environment,
                [
                    "configure-goal",
                    "--goal-id", _GOAL_ID,
                    "--execution-replan-after-todos", str(_REPLAN_AFTER_TODOS),
                    "--clear-waiting-on",
                    "--agent-work-mode", f"{_AGENT_ID}=active",
                    "--execute",
                ],
                cwd=cwd,
            )

        todo_id = f"lhtb-task-phase-{self._phase_number:03d}"
        await self._loopx(
            environment,
            [
                "todo", "add",
                "--goal-id", _GOAL_ID,
                "--role", "agent",
                "--todo-id", todo_id,
                "--text",
                (
                    f"[P0] Execute benchmark phase {self._phase_number}. Read the exact "
                    f"current task from {_TASK_DOC}; inspect the workspace, implement and "
                    "validate it, and create bounded successor Todos for remaining work."
                ),
                "--task-class", "advancement_task",
                "--action-kind", "lhtb_benchmark_task",
                "--claimed-by", _AGENT_ID,
                "--status", "open",
                "--execute",
            ],
            cwd=cwd,
        )

        cadence = await self._loopx(
            environment,
            ["configure-goal", "--goal-id", _GOAL_ID],
            cwd=cwd,
        )
        configured_state = cadence.get("after") or cadence.get("before") or {}
        configured = configured_state.get("execution_profile", {}).get(
            "replan_after_completed_todos"
        )
        if configured != _REPLAN_AFTER_TODOS:
            raise RuntimeError(
                f"replan cadence readback mismatch: expected 3, got {configured!r}"
            )

    def _worker_env(self, *, cwd: str) -> dict[str, str]:
        return {
            **self._profile_env(),
            "LOOPX_CLI": _CLI,
            "LOOPX_REGISTRY": _REGISTRY,
            "LOOPX_RUNTIME_ROOT": _LOOPX_RUNTIME,
            "LOOPX_GOAL_ID": _GOAL_ID,
            "LOOPX_AGENT_ID": _AGENT_ID,
            "LOOPX_PROJECT": cwd,
            "LOOPX_WAKE_LOG_DIR": _WAKE_LOG_DIR,
            "LOOPX_TURN_ROOT": _TURN_ROOT,
            "LOOPX_SHARED_SKILLS": _SHARED_SKILLS,
            "LOOPX_CODEX_TURN_TIMEOUT_SEC": os.environ.get(
                "LOOPX_CODEX_TURN_TIMEOUT_SEC", "4700"
            ),
            "CODEX_BIN": "/usr/local/bin/codex",
            "MODEL_NAME": self.model_name or "",
            "REASONING_EFFORT": str(
                self._resolved_flags.get("reasoning_effort", "max")
            ),
            "OPENAI_BASE_URL": self._get_env("OPENAI_BASE_URL") or "",
            "OPENAI_API_KEY": self._get_env("OPENAI_API_KEY") or "",
            "CODEX_WIRE_API": self._get_env("CODEX_WIRE_API") or "responses",
        }

    def _session_trajectories(self, roots: Iterable[Path]) -> list[Trajectory]:
        parents: set[Path] = set()
        for root in roots:
            if root.is_dir():
                parents.update(path.parent for path in root.glob("sessions/**/*.jsonl"))
        trajectories: list[Trajectory] = []
        for parent in sorted(parents):
            try:
                trajectory = self._convert_events_to_trajectory(parent)
            except Exception:
                self.logger.exception("failed to parse Codex session under %s", parent)
                continue
            if trajectory is not None:
                trajectories.append(trajectory)
        return trajectories

    @staticmethod
    def _totals(trajectories: Iterable[Trajectory]) -> dict[str, int | float | None]:
        prompt = completion = cached = 0
        costs: list[float] = []
        for trajectory in trajectories:
            metrics = trajectory.final_metrics
            if metrics is None:
                continue
            prompt += metrics.total_prompt_tokens or 0
            completion += metrics.total_completion_tokens or 0
            cached += metrics.total_cached_tokens or 0
            if metrics.total_cost_usd is not None:
                costs.append(metrics.total_cost_usd)
        return {
            "prompt": prompt,
            "completion": completion,
            "cached": cached,
            "cost": sum(costs) if costs else None,
        }

    def _write_aggregate_trajectory(self) -> list[Trajectory]:
        wake_root = self.logs_dir / "wakes"
        wake_dirs = sorted(path for path in wake_root.iterdir() if path.is_dir()) if wake_root.is_dir() else []
        trajectories = self._session_trajectories(wake_dirs)
        if not trajectories:
            return []
        steps = []
        for trajectory in trajectories:
            for step in trajectory.steps:
                copied = step.model_copy(deep=True)
                copied.step_id = len(steps) + 1
                steps.append(copied)
        totals = self._totals(trajectories)
        aggregate = Trajectory(
            schema_version="ATIF-v1.5",
            session_id=f"loopx-heartbeat-{self.logs_dir.parent.name}",
            agent=trajectories[0].agent,
            steps=steps,
            final_metrics=FinalMetrics(
                total_prompt_tokens=totals["prompt"] or None,
                total_completion_tokens=totals["completion"] or None,
                total_cached_tokens=totals["cached"] or None,
                total_cost_usd=totals["cost"],
                total_steps=len(steps),
                extra={"heartbeat_wakes": len(trajectories)},
            ),
        )
        (self.logs_dir / "trajectory.json").write_text(
            format_trajectory_json(aggregate.to_json_dict()), encoding="utf-8"
        )
        return trajectories

    def _populate_context(self, context: AgentContext, wake_dirs: list[Path]) -> None:
        phase_trajectories = self._session_trajectories(wake_dirs)
        totals = self._totals(phase_trajectories)
        context.n_input_tokens = int(totals["prompt"] or 0)
        context.n_output_tokens = int(totals["completion"] or 0)
        context.n_cache_tokens = int(totals["cached"] or 0)
        context.cost_usd = totals["cost"]
        context.metadata = {
            "loopx_runtime_profile": "generic_cli",
            "codex_session_policy": "fresh_exec_per_wake",
            "codex_resume_used": False,
            "replan_after_completed_todos": _REPLAN_AFTER_TODOS,
            "onboarding_connection_validation": "provider-prevalidated",
            "login_shell_node_path": _BASH_ENV,
            "scheduler_terminal_packet_compatibility": True,
            "heartbeat_wakes": len(wake_dirs),
            "benchmark_phase": self._phase_number,
        }
        self._write_aggregate_trajectory()

    def populate_context_post_run(self, context: AgentContext) -> None:
        wake_root = self.logs_dir / "wakes"
        wake_dirs = sorted(path for path in wake_root.iterdir() if path.is_dir()) if wake_root.is_dir() else []
        self._populate_context(context, wake_dirs)

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self.model_name:
            raise ValueError("model_name is required")
        self._phase_number += 1
        pwd = await self.exec_as_agent(environment, command="pwd", timeout_sec=30)
        cwd = (pwd.stdout or "").strip()
        if not cwd.startswith("/"):
            raise RuntimeError(f"could not resolve container working directory: {cwd!r}")

        wake_root = self.logs_dir / "wakes"
        before = {path.name for path in wake_root.iterdir() if path.is_dir()} if wake_root.is_dir() else set()
        try:
            await self._prepare_phase(environment, instruction, cwd=cwd)
            wake_command = shlex.join([f"{_PYTHON}/bin/python3", _WAKE_SCRIPT])
            worker_argv = [
                f"{_PYTHON}/bin/python3",
                f"{_SRC}/scripts/external_scheduler_worker.py",
                "--cli-bin", _CLI,
                "--registry", _REGISTRY,
                "--runtime-root", _LOOPX_RUNTIME,
                "--runtime-profile", "generic_cli",
                "--goal-id", _GOAL_ID,
                "--agent-id", _AGENT_ID,
                "--state-file", _SCHEDULER_STATE,
                "--wake-cmd", wake_command,
                "--wake-timeout-seconds", os.environ.get(
                    "LOOPX_WAKE_TIMEOUT_SEC", "4800"
                ),
                "--quota-timeout-seconds", "30",
                "--error-backoff-seconds", "15",
            ]
            scheduler_timeout = int(os.environ.get("LOOPX_SCHEDULER_TIMEOUT_SEC", "5080"))
            phase_log = f"/logs/agent/loopx-worker-phase-{self._phase_number:03d}.log"
            shell = (
                "set +e; "
                f"timeout --signal=TERM --kill-after=15 {scheduler_timeout}s "
                f"{shlex.join(worker_argv)} >> {shlex.quote(phase_log)} 2>&1; "
                "rc=$?; set -e; "
                f"if [ \"$rc\" -eq 124 ]; then echo scheduler_timeout >> {shlex.quote(phase_log)}; exit 0; fi; "
                "exit \"$rc\""
            )
            await self.exec_as_agent(
                environment,
                command=shell,
                env=self._worker_env(cwd=cwd),
                cwd=cwd,
                timeout_sec=scheduler_timeout + 60,
            )
        finally:
            after_dirs = (
                sorted(path for path in wake_root.iterdir() if path.is_dir() and path.name not in before)
                if wake_root.is_dir()
                else []
            )
            self._populate_context(context, after_dirs)


def safe_trial_slug(value: str) -> str:
    """Retained for receipts and tests that need a public-safe trial label."""

    normalized = re.sub(r"[^A-Za-z0-9._-]", "-", value).strip("-._")
    return normalized or "lhtb-trial"
