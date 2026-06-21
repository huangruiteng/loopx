#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


GOAL_ID = "reward-api-smoke-goal"
RUN_GENERATED_AT = "2026-01-01T00:00:00+00:00"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, *, origin: str | None = None) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        return int(error.code), json.loads(raw)


def wait_for_health(base_url: str) -> None:
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, payload = request_json("GET", f"{base_url}/healthz")
            if status == 200 and payload.get("ok") is True:
                return
        except Exception as exc:  # noqa: BLE001 - preserve startup diagnostics.
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"server did not become healthy: {last_error}")


def start_server(repo_root: Path, registry: Path, runtime_root: Path, port: int, *, write_enabled: bool) -> subprocess.Popen[str]:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime_root),
        "serve-status",
        "--port",
        str(port),
        "--scan-root",
        str(registry.parent),
    ]
    if write_enabled:
        command.append("--enable-reward-write-api")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    server = subprocess.Popen(
        command,
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    wait_for_health(f"http://127.0.0.1:{port}")
    return server


def stop_server(server: subprocess.Popen[str]) -> None:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    runtime_root = root / "runtime"
    project = root / "project"
    project.mkdir(parents=True)
    state_file = project / "ACTIVE_GOAL_STATE.md"
    state_file.write_text("---\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n\n## Progress Ledger\n\n", encoding="utf-8")

    run_dir = runtime_root / "goals" / GOAL_ID / "runs"
    run_dir.mkdir(parents=True)
    json_artifact = run_dir / "run.json"
    markdown_artifact = run_dir / "run.md"
    json_artifact.write_text(json.dumps({"ok": True}), encoding="utf-8")
    markdown_artifact.write_text("# Smoke Run\n", encoding="utf-8")
    index_path = run_dir / "index.jsonl"
    index_path.write_text(
        json.dumps(
            {
                "generated_at": RUN_GENERATED_AT,
                "goal_id": GOAL_ID,
                "classification": "adapter_inspected",
                "recommended_action": "judge whether the inspected route should continue",
                "json_path": str(json_artifact),
                "markdown_path": str(markdown_artifact),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    registry = root / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": "ACTIVE_GOAL_STATE.md",
                        "domain": "smoke",
                        "status": "connected-read-only",
                        "adapter": {"kind": "smoke", "status": "connected-read-only"},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry, runtime_root, state_file


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as raw_tmp:
        registry, runtime_root, state_file = write_fixture(Path(raw_tmp))
        disabled_port = free_port()
        disabled_server = start_server(repo_root, registry, runtime_root, disabled_port, write_enabled=False)
        try:
            status, payload = request_json(
                "POST",
                f"http://127.0.0.1:{disabled_port}/reward/append",
                {"preview_id": "missing"},
                origin="http://127.0.0.1:5173",
            )
            assert status == 403, payload
            assert payload["appended"] is False, payload
        finally:
            stop_server(disabled_server)

        non_loopback = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "serve-status",
                "--host",
                "0.0.0.0",
                "--port",
                str(free_port()),
                "--enable-reward-write-api",
            ],
            cwd=repo_root,
            env={**os.environ, "PYTHONPATH": str(repo_root)},
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert non_loopback.returncode == 1, non_loopback.stdout + non_loopback.stderr
        assert "requires a loopback" in json.loads(non_loopback.stdout)["error"], non_loopback.stdout

        port = free_port()
        server = start_server(repo_root, registry, runtime_root, port, write_enabled=True)
        try:
            base_url = f"http://127.0.0.1:{port}"
            reward_payload = {
                "goal_id": GOAL_ID,
                "run_generated_at": RUN_GENERATED_AT,
                "decision": "continue_route",
                "reward": "positive",
                "reason_summary": "smoke route has enough public-safe evidence to continue",
                "follow_up": "let the project agent read history before the next turn",
            }
            status, preview = request_json(
                "POST",
                f"{base_url}/reward/dry-run",
                reward_payload,
                origin="http://127.0.0.1:5173",
            )
            assert status == 200, preview
            assert preview["appended"] is False, preview
            assert preview["preview_id"], preview

            status, stale = request_json(
                "POST",
                f"{base_url}/reward/append",
                {**reward_payload, "preview_id": "stale-preview", "write_active_state_summary": True},
                origin="http://127.0.0.1:5173",
            )
            assert status == 409, stale
            assert stale["appended"] is False, stale

            status, forbidden_preview = request_json(
                "POST",
                f"{base_url}/reward/dry-run",
                reward_payload,
                origin="http://127.0.0.1:5173",
            )
            assert status == 200, forbidden_preview
            assert forbidden_preview["preview_id"], forbidden_preview

            status, forbidden = request_json(
                "POST",
                f"{base_url}/reward/append",
                {**reward_payload, "preview_id": forbidden_preview["preview_id"], "write_active_state_summary": True},
                origin="https://example.com",
            )
            assert status == 403, forbidden
            assert forbidden["appended"] is False, forbidden

            status, appended = request_json(
                "POST",
                f"{base_url}/reward/append",
                {**reward_payload, "preview_id": preview["preview_id"], "write_active_state_summary": True},
                origin="http://127.0.0.1:5173",
            )
            assert status == 200, appended
            assert appended["appended"] is True, appended
            assert appended["human_reward"]["reward"] == "positive", appended

            status, refreshed = request_json("GET", f"{base_url}/status.json")
            assert status == 200, refreshed
            latest = refreshed["run_history"]["goals"][0]["latest_runs"][0]
            assert latest["human_reward"]["decision"] == "continue_route", latest
            assert "human_reward=positive" in state_file.read_text(encoding="utf-8")
        finally:
            stop_server(server)

    print("reward-append-api-smoke ok")


if __name__ == "__main__":
    main()
