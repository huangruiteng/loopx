#!/usr/bin/env python3
"""Run the first isolated long-run regression shim.

This intentionally uses LoopX CLI commands, not Codex CLI, so the
fixture, JSONL log, quota, writeback, and spend contracts can stabilize before a
real worker process is introduced.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "codex-cli-long-run-fixture"
STEP_COUNT = 3
GOAL_TICK_PROTOCOL_VERSION = "goal_tick_output_protocol_v0"
DEFAULT_CODEX_TIMEOUT_SECONDS = 120
GOAL_TICK_PHASES = (
    "read_state",
    "propose_step",
    "execute",
    "validate",
    "critic",
    "writeback",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worker-mode",
        choices=("shim", "real-codex"),
        default="shim",
        help="Use the deterministic local shim by default, or explicitly invoke Codex CLI.",
    )
    parser.add_argument(
        "--codex-cli",
        default="codex",
        help="Codex CLI executable to use only with --worker-mode real-codex.",
    )
    parser.add_argument(
        "--codex-timeout-seconds",
        type=int,
        default=DEFAULT_CODEX_TIMEOUT_SECONDS,
        help="Timeout for each opt-in real Codex CLI worker step.",
    )
    parser.add_argument(
        "--step-count",
        type=int,
        default=STEP_COUNT,
        help="Number of isolated worker steps to run; pass criteria require 3-5.",
    )
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_registry(root: Path) -> tuple[Path, Path, Path]:
    home = root / "home"
    project = root / "project"
    runtime = home / ".codex" / "loopx"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Codex CLI Long-Run Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Complete three isolated worker steps with validation and spend accounting.\n\n"
        "## Progress Ledger\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "codex-cli-long-run-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_readonly_v0",
                            "status": "connected-read-only",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, project, runtime


def run_cli(
    *,
    registry_path: Path,
    runtime_root: Path,
    home: Path,
    args: list[str],
    scan_root: Path | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        *args,
    ]
    if scan_root is not None:
        command.extend(["--scan-root", str(scan_root)])
    env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(REPO_ROOT)}
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def queue_status(status_payload: dict[str, Any]) -> str:
    items = status_payload.get("attention_queue", {}).get("items", [])
    for item in items:
        if isinstance(item, dict) and item.get("goal_id") == GOAL_ID:
            return str(item.get("status") or "")
    return "missing"


def append_progress(project: Path, *, step_index: int, artifact_path: str) -> None:
    state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    with state_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n- step {step_index}: validated `{artifact_path}`\n")


def real_codex_prompt(*, step_index: int, artifact_rel: str, marker: str) -> str:
    return (
        "You are running a LoopX isolated long-run regression step. "
        "Use only the current working directory. Do not read session history, "
        "user config, external services, or files outside this fixture. "
        f"Step {step_index}: create or overwrite `{artifact_rel}` with exactly "
        f"`{marker}` followed by a newline, then stop."
    )


def run_real_codex_worker(
    *,
    codex_cli: str,
    timeout_seconds: int,
    home: Path,
    project: Path,
    step_index: int,
    artifact_rel: str,
    marker: str,
) -> dict[str, Any]:
    command = [
        codex_cli,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "-C",
        str(project),
        real_codex_prompt(step_index=step_index, artifact_rel=artifact_rel, marker=marker),
    ]
    env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "LOOPX_LONG_RUN_GOAL_ID": GOAL_ID,
        "LOOPX_LONG_RUN_PROJECT": str(project),
        "LOOPX_LONG_RUN_STEP_INDEX": str(step_index),
        "LOOPX_LONG_RUN_ARTIFACT_REL": artifact_rel,
        "LOOPX_LONG_RUN_MARKER": marker,
    }
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=project,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "kind": "timeout",
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "returncode": None,
            "stdout_tail": (exc.stdout or "")[-200:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-200:] if isinstance(exc.stderr, str) else "",
        }
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "kind": "process_error",
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "returncode": exc.returncode,
            "stdout_tail": exc.stdout[-200:],
            "stderr_tail": exc.stderr[-200:],
        }
    return {
        "ok": True,
        "kind": "completed",
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-200:],
        "stderr_tail": result.stderr[-200:],
    }


def execute_worker_step(
    *,
    args: argparse.Namespace,
    home: Path,
    project: Path,
    step_index: int,
) -> tuple[str, str, dict[str, Any]]:
    artifact = project / "artifacts" / f"step-{step_index}.txt"
    artifact_rel = artifact.relative_to(project).as_posix()
    marker = f"validated step {step_index}"
    if args.worker_mode == "shim":
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(marker + "\n", encoding="utf-8")
        return marker, artifact_rel, {
            "mode": "shim",
            "kind": "local_fixture_write",
            "ok": True,
        }

    worker = run_real_codex_worker(
        codex_cli=str(args.codex_cli),
        timeout_seconds=int(args.codex_timeout_seconds),
        home=home,
        project=project,
        step_index=step_index,
        artifact_rel=artifact_rel,
        marker=marker,
    )
    worker.update(
        {
            "mode": "real-codex",
            "cli_name": Path(str(args.codex_cli)).name,
            "ephemeral": True,
            "ignore_user_config": True,
            "sandbox": "workspace-write",
            "cwd": "fixture_project",
        }
    )
    return marker, artifact_rel, worker


def tick_phase(name: str, *, status: str, evidence: dict[str, Any]) -> dict[str, Any]:
    assert name in GOAL_TICK_PHASES, name
    assert status in {"passed", "blocked", "skipped"}, status
    return {
        "phase": name,
        "status": status,
        "evidence": evidence,
    }


def goal_tick_protocol(phases: list[dict[str, Any]]) -> dict[str, Any]:
    names = [str(phase.get("phase")) for phase in phases]
    assert names == list(GOAL_TICK_PHASES), names
    return {
        "schema_version": GOAL_TICK_PROTOCOL_VERSION,
        "phases": phases,
    }


def assert_goal_tick_protocol(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        protocol = row.get("goal_tick_output_protocol")
        assert isinstance(protocol, dict), row
        assert protocol.get("schema_version") == GOAL_TICK_PROTOCOL_VERSION, protocol
        phases = protocol.get("phases")
        assert isinstance(phases, list), protocol
        assert [phase.get("phase") for phase in phases] == list(GOAL_TICK_PHASES), phases
        for phase in phases:
            assert phase.get("status") in {"passed", "blocked", "skipped"}, phase
            assert isinstance(phase.get("evidence"), dict), phase

        if row.get("action_kind") in {"no_spend_stop", "worker_blocker"}:
            assert row.get("spend_event") is None, row
            continue

        assert all(phase.get("status") == "passed" for phase in phases), phases
        writeback = phases[-1].get("evidence", {})
        assert writeback.get("writeback_event", {}).get("classification"), writeback
        assert writeback.get("spend_event", {}).get("classification") == "quota_slot_spent", writeback


def assert_public_log(rows: list[dict[str, Any]]) -> None:
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    forbidden = ("/Users/", "~/.codex/sessions", "raw_thread", "session_history")
    for marker in forbidden:
        assert marker not in text, marker


def main() -> int:
    args = parse_args()
    assert 3 <= int(args.step_count) <= 5, args.step_count
    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-long-run-") as tmp:
        root = Path(tmp)
        registry_path, project, runtime_root = write_registry(root)
        home = root / "home"
        log_path = root / "run-log.jsonl"
        rows: list[dict[str, Any]] = []

        for step_index in range(1, int(args.step_count) + 1):
            started_at = iso_now()
            started = time.perf_counter()
            status_before = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=["status"],
                scan_root=project,
            )
            quota_before = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=["quota", "should-run", "--goal-id", GOAL_ID],
                scan_root=project,
            )
            should_run = bool(quota_before.get("should_run"))
            row: dict[str, Any] = {
                "step_index": step_index,
                "started_at": started_at,
                "goal_id": GOAL_ID,
                "status_before": queue_status(status_before),
                "should_run_before": should_run,
            }
            if not should_run:
                row.update(
                    {
                        "action_kind": "no_spend_stop",
                        "artifact_path": None,
                        "validation": {"passed": False, "command": "quota should-run"},
                        "writeback_event": None,
                        "spend_event": None,
                    }
                )
                row["goal_tick_output_protocol"] = goal_tick_protocol(
                    [
                        tick_phase(
                            "read_state",
                            status="passed",
                            evidence={
                                "status_before": row["status_before"],
                                "should_run_before": should_run,
                            },
                        ),
                        tick_phase(
                            "propose_step",
                            status="blocked",
                            evidence={"action_kind": "no_spend_stop"},
                        ),
                        tick_phase("execute", status="skipped", evidence={"reason": "should_run_false"}),
                        tick_phase("validate", status="skipped", evidence=row["validation"]),
                        tick_phase(
                            "critic",
                            status="blocked",
                            evidence={"decision": "stop", "reason": "quota_guard_false"},
                        ),
                        tick_phase(
                            "writeback",
                            status="skipped",
                            evidence={"writeback_event": None, "spend_event": None},
                        ),
                    ]
                )
                rows.append(row)
                break

            marker, artifact_rel, worker_invocation = execute_worker_step(
                args=args,
                home=home,
                project=project,
                step_index=step_index,
            )
            artifact = project / artifact_rel
            worker_ok = bool(worker_invocation.get("ok"))
            validation_passed = artifact.exists() and marker in artifact.read_text(encoding="utf-8")
            if not worker_ok or not validation_passed:
                refresh = run_cli(
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    home=home,
                    args=[
                        "refresh-state",
                        "--goal-id",
                        GOAL_ID,
                        "--classification",
                        "long_run_regression_real_worker_blocker",
                        "--recommended-action",
                        "Opt-in real Codex CLI worker did not produce the expected isolated artifact; inspect the public-safe blocker row before retry.",
                        "--delivery-batch-scale",
                        "single_surface",
                        "--delivery-outcome",
                        "blocker",
                    ],
                )
                status_after = run_cli(
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    home=home,
                    args=["status"],
                    scan_root=project,
                )
                row.update(
                    {
                        "finished_at": iso_now(),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        "status_after": queue_status(status_after),
                        "action_kind": "worker_blocker",
                        "artifact_path": artifact_rel,
                        "worker_mode": args.worker_mode,
                        "worker_invocation": worker_invocation,
                        "validation": {
                            "command": f"artifact contains {marker!r}",
                            "passed": validation_passed,
                        },
                        "writeback_event": {
                            "classification": refresh.get("classification"),
                            "json_path": Path(str(refresh.get("json_path"))).name,
                        },
                        "spend_event": None,
                    }
                )
                row["goal_tick_output_protocol"] = goal_tick_protocol(
                    [
                        tick_phase(
                            "read_state",
                            status="passed",
                            evidence={
                                "status_before": row["status_before"],
                                "should_run_before": row["should_run_before"],
                            },
                        ),
                        tick_phase(
                            "propose_step",
                            status="passed",
                            evidence={
                                "action_kind": row["action_kind"],
                                "artifact_path": row["artifact_path"],
                            },
                        ),
                        tick_phase(
                            "execute",
                            status="blocked",
                            evidence={"worker_invocation": row["worker_invocation"]},
                        ),
                        tick_phase("validate", status="blocked", evidence=row["validation"]),
                        tick_phase(
                            "critic",
                            status="blocked",
                            evidence={
                                "decision": "stop",
                                "reason": "real_codex_worker_artifact_missing_or_failed",
                            },
                        ),
                        tick_phase(
                            "writeback",
                            status="passed",
                            evidence={
                                "writeback_event": row["writeback_event"],
                                "spend_event": None,
                            },
                        ),
                    ]
                )
                rows.append(row)
                break

            append_progress(project, step_index=step_index, artifact_path=artifact_rel)

            classification = (
                "long_run_regression_terminal"
                if step_index == int(args.step_count)
                else f"long_run_regression_step_{step_index}"
            )
            refresh = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=[
                    "refresh-state",
                    "--goal-id",
                    GOAL_ID,
                    "--classification",
                    classification,
                    "--recommended-action",
                    f"Fixture step {step_index} validated {artifact_rel}.",
                    "--delivery-batch-scale",
                    "implementation",
                    "--delivery-outcome",
                    "outcome_progress",
                ],
            )
            spend = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=[
                    "quota",
                    "spend-slot",
                    "--goal-id",
                    GOAL_ID,
                    "--slots",
                    "1",
                    "--source",
                    "heartbeat",
                    "--execute",
                ],
                scan_root=project,
            )
            status_after = run_cli(
                registry_path=registry_path,
                runtime_root=runtime_root,
                home=home,
                args=["status"],
                scan_root=project,
            )
            finished_at = iso_now()
            row.update(
                {
                    "finished_at": finished_at,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "status_after": queue_status(status_after),
                    "action_kind": "fixture_artifact_write",
                    "artifact_path": artifact_rel,
                    "worker_mode": args.worker_mode,
                    "worker_invocation": worker_invocation,
                    "validation": {
                        "command": f"artifact contains {marker!r}",
                        "passed": validation_passed,
                    },
                    "writeback_event": {
                        "classification": refresh.get("classification"),
                        "json_path": Path(str(refresh.get("json_path"))).name,
                    },
                    "spend_event": {
                        "classification": spend.get("classification"),
                        "json_path": Path(str(spend.get("json_path"))).name,
                    },
                }
            )
            row["goal_tick_output_protocol"] = goal_tick_protocol(
                [
                    tick_phase(
                        "read_state",
                        status="passed",
                        evidence={
                            "status_before": row["status_before"],
                            "should_run_before": row["should_run_before"],
                        },
                    ),
                    tick_phase(
                        "propose_step",
                        status="passed",
                        evidence={
                            "action_kind": row["action_kind"],
                            "artifact_path": row["artifact_path"],
                        },
                    ),
                    tick_phase(
                        "execute",
                        status="passed",
                        evidence={
                            "artifact_path": row["artifact_path"],
                            "marker": marker,
                            "worker_invocation": row["worker_invocation"],
                        },
                    ),
                    tick_phase("validate", status="passed", evidence=row["validation"]),
                    tick_phase(
                        "critic",
                        status="passed",
                        evidence={
                            "decision": "terminal" if step_index == STEP_COUNT else "continue",
                            "classification": classification,
                            "risk": "isolated_public_fixture",
                        },
                    ),
                    tick_phase(
                        "writeback",
                        status="passed",
                        evidence={
                            "writeback_event": row["writeback_event"],
                            "spend_event": row["spend_event"],
                        },
                    ),
                ]
            )
            rows.append(row)

        log_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

        terminal = rows[-1]["status_after"] == "long_run_regression_terminal"
        blocker = rows[-1].get("action_kind") == "worker_blocker"
        if args.worker_mode == "shim":
            assert len(rows) == int(args.step_count), rows
            assert terminal, rows[-1]
        else:
            assert terminal or blocker, rows[-1]
        for row in rows:
            assert row["should_run_before"] is True, row
            assert row["duration_ms"] >= 0, row
            assert row["writeback_event"]["classification"], row
            if row["action_kind"] == "worker_blocker":
                assert row["validation"]["passed"] is False, row
                assert row["spend_event"] is None, row
            else:
                assert row["validation"]["passed"] is True, row
                assert row["spend_event"]["classification"] == "quota_slot_spent", row
                assert (project / str(row["artifact_path"])).exists(), row
            assert row["worker_mode"] in {"shim", "real-codex"}, row

        run_index = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
        classifications = [
            json.loads(line)["classification"]
            for line in run_index.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if blocker:
            assert classifications.count("quota_slot_spent") == len(rows) - 1, classifications
            assert "long_run_regression_real_worker_blocker" in classifications, classifications
        else:
            assert classifications.count("quota_slot_spent") == int(args.step_count), classifications
            assert "long_run_regression_terminal" in classifications, classifications
        assert_goal_tick_protocol(rows)
        assert_public_log(rows)

        print(
            f"worker_mode={args.worker_mode} "
            f"steps={len(rows)} log_rows={len(log_path.read_text(encoding='utf-8').splitlines())}"
        )
    print("codex-cli-long-run-regression-runner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
