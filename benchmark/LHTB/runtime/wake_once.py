#!/usr/bin/env python3
"""Run one LoopX heartbeat as one fresh, non-resumed Codex exec session."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


GLOBAL_REGISTRY_TOKEN = "$HOME/.codex/loopx/registry.global.json"


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def parse_json_output(text: str, *, command: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{command} returned invalid JSON: {value[:300]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{command} returned a non-object JSON value")
    return payload


def run_loopx(argv: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"LoopX exited {completed.returncode}: "
            f"{(completed.stderr or completed.stdout)[-500:]}"
        )
    return parse_json_output(completed.stdout, command="heartbeat-prompt")


def build_heartbeat_argv(
    *, cli: str, registry: str, runtime_root: str, goal_id: str,
    agent_id: str, turn_id: str,
) -> list[str]:
    return [
        cli,
        "--format", "json",
        "--registry", registry,
        "--runtime-root", runtime_root,
        "heartbeat-prompt",
        "--thin",
        "--runtime-profile", "generic_cli",
        "--goal-id", goal_id,
        "--agent-id", agent_id,
        "--turn-instance-id", turn_id,
        "--cli-bin", cli,
        "--available-capability", "shell",
        "--available-capability", "filesystem_write",
    ]


def build_codex_argv(*, codex_bin: str, model: str, effort: str, cwd: str) -> list[str]:
    # Deliberately contains no `resume`: every heartbeat is a new Codex session.
    return [
        codex_bin,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "--cd", cwd,
        "--model", model,
        "--json",
        "--enable", "unified_exec",
        "-c", f'model_reasoning_effort="{effort}"',
        "-c", "features.goals=false",
        "-c", 'web_search="disabled"',
        "-c", "model_providers.harbor.request_max_retries=8",
        "-c", "model_providers.harbor.stream_max_retries=8",
        "-c", "model_providers.harbor.stream_idle_timeout_ms=300000",
        "-",
    ]


def write_codex_home(
    path: Path, *, base_url: str, api_key: str, wire_api: str,
    workspace: str, shared_skills: Path,
) -> None:
    path.mkdir(parents=True, exist_ok=False)
    (path / "auth.json").write_text(
        json.dumps({"OPENAI_API_KEY": api_key}) + "\n", encoding="utf-8"
    )
    (path / "auth.json").chmod(0o600)
    quoted_workspace = json.dumps(workspace)
    config = "\n".join(
        [
            'web_search = "disabled"',
            'sandbox_mode = "danger-full-access"',
            'model_provider = "harbor"',
            f"[projects.{quoted_workspace}]",
            'trust_level = "trusted"',
            "[model_providers.harbor]",
            'name = "harbor"',
            f"base_url = {json.dumps(base_url)}",
            f"wire_api = {json.dumps(wire_api)}",
            'env_key = "OPENAI_API_KEY"',
            "request_max_retries = 8",
            "stream_max_retries = 8",
            "stream_idle_timeout_ms = 300000",
            "",
        ]
    )
    (path / "config.toml").write_text(config, encoding="utf-8")
    if shared_skills.is_dir():
        (path / "skills").symlink_to(shared_skills, target_is_directory=True)


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main() -> int:
    cli = required_env("LOOPX_CLI")
    registry = required_env("LOOPX_REGISTRY")
    runtime_root = required_env("LOOPX_RUNTIME_ROOT")
    goal_id = required_env("LOOPX_GOAL_ID")
    agent_id = required_env("LOOPX_AGENT_ID")
    workspace = required_env("LOOPX_PROJECT")
    codex_bin = required_env("CODEX_BIN")
    model = required_env("MODEL_NAME").split("/")[-1]
    effort = required_env("REASONING_EFFORT")
    base_url = required_env("OPENAI_BASE_URL")
    api_key = required_env("OPENAI_API_KEY")
    wire_api = os.environ.get("CODEX_WIRE_API", "responses").strip() or "responses"
    output_root = Path(required_env("LOOPX_WAKE_LOG_DIR"))
    turn_root = Path(required_env("LOOPX_TURN_ROOT"))
    shared_skills = Path(required_env("LOOPX_SHARED_SKILLS"))
    timeout_seconds = float(os.environ.get("LOOPX_CODEX_TURN_TIMEOUT_SEC", "4700"))

    turn_id = f"lhtb-{time.time_ns()}-{uuid.uuid4().hex[:16]}"
    wake_dir = output_root / turn_id
    wake_dir.mkdir(parents=True, exist_ok=False)
    turn_dir = turn_root / turn_id
    codex_home = turn_dir / "codex-home"
    turn_dir.mkdir(parents=True, exist_ok=False)

    env = dict(os.environ)
    env["LOOPX_TURN"] = turn_id
    heartbeat_argv = build_heartbeat_argv(
        cli=cli,
        registry=registry,
        runtime_root=runtime_root,
        goal_id=goal_id,
        agent_id=agent_id,
        turn_id=turn_id,
    )
    payload = run_loopx(heartbeat_argv, cwd=Path(workspace), env=env)
    (wake_dir / "heartbeat.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if payload.get("ok") is not True:
        raise RuntimeError(f"heartbeat-prompt not ready: {payload.get('error')}")
    if payload.get("turn_instance_id") != turn_id:
        raise RuntimeError(
            "heartbeat Turn identity mismatch: "
            f"expected {turn_id!r}, got {payload.get('turn_instance_id')!r}"
        )
    body = payload.get("task_body")
    if not isinstance(body, str) or not body.strip():
        raise RuntimeError("heartbeat-prompt returned no task_body")
    if "--runtime-profile generic_cli" not in body:
        raise RuntimeError("heartbeat task_body is not bound to generic_cli")
    body = body.replace(GLOBAL_REGISTRY_TOKEN, registry)
    if GLOBAL_REGISTRY_TOKEN in body:
        raise RuntimeError("heartbeat task_body retained the global registry token")
    (wake_dir / "task-body.md").write_text(body, encoding="utf-8")

    write_codex_home(
        codex_home,
        base_url=base_url,
        api_key=api_key,
        wire_api=wire_api,
        workspace=workspace,
        shared_skills=shared_skills,
    )
    codex_env = dict(env)
    codex_env["CODEX_HOME"] = str(codex_home)
    codex_argv = build_codex_argv(
        codex_bin=codex_bin,
        model=model,
        effort=effort,
        cwd=workspace,
    )
    (wake_dir / "invocation.json").write_text(
        json.dumps(
            {
                "turn_id": turn_id,
                "runtime_profile": "generic_cli",
                "model": model,
                "reasoning_effort": effort,
                "fresh_codex_exec": True,
                "resume": False,
                "web_search": "disabled",
                "argv": codex_argv,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    timed_out = False
    return_code = 1
    with (wake_dir / "codex-events.jsonl").open("wb") as stdout_handle, (
        wake_dir / "codex-stderr.log"
    ).open("wb") as stderr_handle:
        process = subprocess.Popen(
            codex_argv,
            cwd=workspace,
            env=codex_env,
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        try:
            process.communicate(input=body.encode("utf-8"), timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_group(process)
        return_code = process.returncode if process.returncode is not None else 124

    sessions = codex_home / "sessions"
    if sessions.is_dir():
        shutil.copytree(sessions, wake_dir / "sessions", dirs_exist_ok=True)
    receipt = {
        "ok": return_code == 0 and not timed_out,
        "turn_id": turn_id,
        "codex_return_code": return_code,
        "timed_out": timed_out,
        "fresh_codex_exec": True,
        "resume": False,
        "task_body_sha256": __import__("hashlib").sha256(body.encode()).hexdigest(),
    }
    (wake_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(turn_dir, ignore_errors=True)
    print(json.dumps(receipt, separators=(",", ":")), flush=True)
    return 0 if receipt["ok"] else (124 if timed_out else max(1, return_code))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise
