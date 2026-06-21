#!/usr/bin/env python3
"""Smoke-test autonomous replan obligation projection in status and quota."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx import cli as loopx_cli

GOAL_ID = "autonomous-replan-fixture"
CLI_TIMEOUT_SECONDS = 30
USE_SUBPROCESS_CLI = False


def run_cli(
    *args: str,
    registry_path: Path,
    runtime: Path,
    timeout: int = CLI_TIMEOUT_SECONDS,
    use_subprocess: bool | None = None,
) -> dict:
    use_subprocess = USE_SUBPROCESS_CLI if use_subprocess is None else use_subprocess
    project_root = registry_path.parent.parent
    scan_path_args = ["--scan-path", str(project_root)] if args and args[0] in {"status", "quota"} else []
    argv = [
        "--registry",
        str(registry_path),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        *args,
        *scan_path_args,
    ]
    if not use_subprocess:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = loopx_cli.main(argv)
        if exit_code != 0:
            public_args = " ".join(args)
            raise AssertionError(
                f"loopx fixture command failed with exit {exit_code}: {public_args}\n"
                f"{stderr.getvalue().strip()}"
            )
        return json.loads(stdout.getvalue())

    command = [sys.executable, "-m", "loopx.cli", *argv]
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        public_args = " ".join(args)
        raise AssertionError(
            f"loopx fixture command timed out after {timeout}s: {public_args}"
        ) from exc
    return json.loads(result.stdout)


def append_run_record(runs_dir: Path, record: dict) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    generated_at = str(record["generated_at"])
    json_path = runs_dir / f"{generated_at.replace(':', '-')}.json"
    markdown_path = runs_dir / f"{generated_at.replace(':', '-')}.md"
    record = {
        **record,
        "goal_id": GOAL_ID,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    json_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        "# Fixture Run\n\n"
        f"- classification: `{record['classification']}`\n"
        f"- recommended_action: {record.get('recommended_action', '')}\n",
        encoding="utf-8",
    )
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def write_fixture(
    root: Path,
    *,
    include_replan_signals: bool,
    include_run_history_stalls: bool = False,
    periodic_run_count: int = 0,
    include_recent_replan_ack: bool = False,
) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    replan_section = ""
    if include_replan_signals:
        replan_section = (
            "## Operating Lessons\n\n"
            "- no-progress streak: two eligible heartbeats repeated the same dependency observation.\n"
            "- repeated-action loop: the same monitor-only next action appeared again.\n"
            "- phase transition: readiness work is done and the next phase should advance planning-trigger work.\n\n"
        )
    historical_noise_section = ""
    done_todo_line = ""
    if not include_replan_signals:
        historical_noise_section = (
            "## Recent Progress\n\n"
            "- 2026-01-01: An older no-progress streak repair was already completed.\n\n"
        )
        done_todo_line = (
            "- [x] [P1] Completed autonomous planning-trigger work with a replan obligation.\n"
        )
    todo_text = (
        "[P1] Autonomous planning-trigger implementation slice: emit a machine-readable replan obligation."
        if include_replan_signals
        else "[P1] Advance the next bounded project hardening slice."
    )
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Autonomous Replan Fixture\n\n"
        "## Next Action\n\n"
        "- Advance the first executable agent todo after observing current state.\n\n"
        f"{replan_section}"
        f"{historical_noise_section}"
        "## Agent Todo\n\n"
        f"{done_todo_line}"
        f"- [ ] {todo_text}\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "autonomous-replan-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if include_run_history_stalls or periodic_run_count or include_recent_replan_ack:
        runs_dir = runtime / "goals" / GOAL_ID / "runs"
        if include_recent_replan_ack:
            append_run_record(
                runs_dir,
                {
                    "generated_at": "2026-01-02T00:30:00+00:00",
                    "classification": "autonomous_replan_recorded",
                    "recommended_action": "Periodic review was recorded; continue selected next slice.",
                    "health_check": "compact replan ack",
                    "delivery_outcome": "outcome_progress",
                },
            )
    if periodic_run_count:
        runs_dir = runtime / "goals" / GOAL_ID / "runs"
        for offset in range(periodic_run_count):
            minute = periodic_run_count - offset
            append_run_record(
                runs_dir,
                {
                    "generated_at": f"2026-01-01T00:{minute:02d}:00+00:00",
                    "classification": "benchmark_rotation_iteration",
                    "recommended_action": f"Advance bounded benchmark/control-plane slice {minute}.",
                    "health_check": "compact durable run event",
                    "delivery_outcome": "outcome_progress",
                },
            )
    if include_run_history_stalls:
        runs_dir = runtime / "goals" / GOAL_ID / "runs"
        repeated_action = "Observe dependency state; no material transition yet."
        for generated_at in (
            "2026-01-01T00:04:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ):
            append_run_record(
                runs_dir,
                {
                    "generated_at": generated_at,
                    "classification": "dependency_observation_monitor",
                    "recommended_action": repeated_action,
                    "health_check": "monitor-only observation unchanged",
                    "delivery_outcome": "surface_only",
                },
            )
    return registry_path, runtime


def attention_item(status_payload: dict) -> dict:
    items = status_payload.get("attention_queue", {}).get("items") or []
    assert len(items) == 1, status_payload
    return items[0]


def assert_replan_obligation_projected() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(Path(tmp), include_replan_signals=True)
        status_payload = run_cli("status", registry_path=registry_path, runtime=runtime)
        item = attention_item(status_payload)
        obligation = item["project_asset"]["autonomous_replan_obligation"]
        assert obligation["schema_version"] == "autonomous_replan_obligation_v0", obligation
        assert obligation["required"] is True, obligation
        assert obligation["stall_threshold"] == 2, obligation
        assert obligation["trigger_count"] == 3, obligation
        assert [trigger["kind"] for trigger in obligation["triggers"]] == [
            "no_progress_streak",
            "repeated_action_loop",
            "phase_transition",
        ], obligation
        assert item["autonomous_replan_obligation"] == obligation, item
        assert obligation["next_validation_command"] == (
            "python3 examples/autonomous-replan-obligation-smoke.py"
        ), obligation
        assert obligation["todo_actions"][0]["action"] == "split", obligation
        assert obligation["todo_actions"][1]["action"] == "add", obligation
        assert obligation["todo_actions"][2]["action"] == "retire", obligation

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert guard["should_run"] is True, guard
        assert guard["autonomous_replan_obligation"] == obligation, guard
        recommendation = guard["heartbeat_recommendation"]
        assert recommendation["recommended_mode"] == "autonomous_replan_required", recommendation
        assert recommendation["replan_obligation"]["stall_threshold"] == 2, recommendation
        assert recommendation["replan_obligation"]["trigger_count"] == 3, recommendation
        assert guard["execution_obligation"]["must_attempt_work"] is True, guard
        assert guard["execution_obligation"]["kind"] == "autonomous_replan_required", guard
        assert guard["execution_obligation"]["stall_threshold"] == 2, guard
        assert guard["automation_liveness"]["automation_action"] == "execute_bounded_work", guard
        assert guard["automation_liveness"]["keep_active"] is True, guard
        assert guard["automation_liveness"]["pause_allowed"] is False, guard


def assert_replan_obligation_projected_from_run_history() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(
            Path(tmp),
            include_replan_signals=False,
            include_run_history_stalls=True,
        )
        status_payload = run_cli("status", registry_path=registry_path, runtime=runtime)
        item = attention_item(status_payload)
        obligation = item["project_asset"]["autonomous_replan_obligation"]
        assert obligation["schema_version"] == "autonomous_replan_obligation_v0", obligation
        assert obligation["required"] is True, obligation
        assert obligation["stall_threshold"] == 2, obligation
        assert obligation["trigger_count"] == 1, obligation
        assert obligation["triggers"][0]["kind"] == "run_history_no_progress_repeat", obligation
        assert obligation["triggers"][0]["section"] == "run_history", obligation

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert guard["should_run"] is True, guard
        assert guard["autonomous_replan_obligation"] == obligation, guard
        recommendation = guard["heartbeat_recommendation"]
        assert recommendation["recommended_mode"] == "autonomous_replan_required", recommendation
        assert recommendation["replan_obligation"]["stall_threshold"] == 2, recommendation
        assert guard["execution_obligation"]["kind"] == "autonomous_replan_required", guard
        assert guard["automation_liveness"]["automation_action"] == "execute_bounded_work", guard
        assert guard["automation_liveness"]["pause_allowed"] is False, guard


def assert_periodic_replan_obligation_projected_from_run_history() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(
            Path(tmp),
            include_replan_signals=False,
            periodic_run_count=20,
        )
        status_payload = run_cli(
            "status",
            "--limit",
            "30",
            registry_path=registry_path,
            runtime=runtime,
        )
        item = attention_item(status_payload)
        obligation = item["project_asset"]["autonomous_replan_obligation"]
        assert obligation["schema_version"] == "autonomous_replan_obligation_v0", obligation
        assert obligation["required"] is True, obligation
        assert obligation["trigger_count"] == 1, obligation
        assert obligation["triggers"][0]["kind"] == "periodic_review_due", obligation
        assert obligation["triggers"][0]["section"] == "run_history", obligation
        assert obligation["triggers"][0]["run_count"] == 20, obligation
        assert obligation["triggers"][0]["threshold"] == 20, obligation
        assert obligation["guidance_actions"] == [
            "keep",
            "split",
            "add",
            "retire",
            "ask_decision",
        ], obligation
        assert obligation["todo_actions"][0]["action"] == "split", obligation
        assert obligation["todo_actions"][1]["action"] == "add", obligation
        assert obligation["todo_actions"][2]["action"] == "ask_decision", obligation
        assert "bounded autonomous periodic review" in obligation["recommended_action"], obligation

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert guard["should_run"] is True, guard
        assert guard["autonomous_replan_obligation"] == obligation, guard
        recommendation = guard["heartbeat_recommendation"]
        assert recommendation["recommended_mode"] == "autonomous_replan_required", recommendation
        assert guard["execution_obligation"]["kind"] == "autonomous_replan_required", guard
        assert guard["automation_liveness"]["automation_action"] == "execute_bounded_work", guard


def assert_no_periodic_replan_before_threshold_or_after_ack() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(
            Path(tmp),
            include_replan_signals=False,
            periodic_run_count=19,
        )
        status_payload = run_cli(
            "status",
            "--limit",
            "30",
            registry_path=registry_path,
            runtime=runtime,
        )
        item = attention_item(status_payload)
        assert "autonomous_replan_obligation" not in item, item
        assert "autonomous_replan_obligation" not in item["project_asset"], item

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert "autonomous_replan_obligation" not in guard, guard
        assert guard["heartbeat_recommendation"]["recommended_mode"] != "autonomous_replan_required", guard

    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(
            Path(tmp),
            include_replan_signals=False,
            periodic_run_count=20,
            include_recent_replan_ack=True,
        )
        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert "autonomous_replan_obligation" not in guard, guard
        assert guard["heartbeat_recommendation"]["recommended_mode"] != "autonomous_replan_required", guard


def assert_validated_classification_without_ack_does_not_clear_replan() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(
            Path(tmp),
            include_replan_signals=False,
            periodic_run_count=20,
        )
        append_run_record(
            runtime / "goals" / GOAL_ID / "runs",
            {
                "generated_at": "2026-01-02T00:30:00+00:00",
                "classification": "autonomous_replan_validated_20260621",
                "recommended_action": "A progress refresh was written, but no explicit replan ACK was recorded.",
                "health_check": "compact progress refresh",
                "delivery_outcome": "surface_only",
            },
        )
        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        obligation = guard["autonomous_replan_obligation"]
        assert obligation["required"] is True, guard
        assert obligation["triggers"][0]["kind"] == "periodic_review_due", guard
        assert guard["heartbeat_recommendation"]["recommended_mode"] == "autonomous_replan_required", guard


def assert_refresh_state_structured_ack_clears_replan() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(
            Path(tmp),
            include_replan_signals=False,
            periodic_run_count=20,
        )
        refresh = run_cli(
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--classification",
            "autonomous_replan_validated_20260621",
            "--autonomous-replan-recorded",
            "--delivery-batch-scale",
            "single_surface",
            "--delivery-outcome",
            "surface_only",
            "--recommended-action",
            "Explicit bounded replan ACK recorded; continue the selected next slice.",
            registry_path=registry_path,
            runtime=runtime,
        )
        assert refresh["autonomous_replan_recorded"] is True, refresh
        json_path = Path(refresh["json_path"])
        record = json.loads(json_path.read_text(encoding="utf-8"))
        assert record["autonomous_replan_ack"]["recorded"] is True, record

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert "autonomous_replan_obligation" not in guard, guard
        assert guard["heartbeat_recommendation"]["recommended_mode"] != "autonomous_replan_required", guard


def assert_no_replan_obligation_without_signal() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-autonomous-replan-") as tmp:
        registry_path, runtime = write_fixture(Path(tmp), include_replan_signals=False)
        status_payload = run_cli("status", registry_path=registry_path, runtime=runtime)
        item = attention_item(status_payload)
        assert "autonomous_replan_obligation" not in item, item
        assert "autonomous_replan_obligation" not in item["project_asset"], item

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert "autonomous_replan_obligation" not in guard, guard
        assert guard["heartbeat_recommendation"]["recommended_mode"] != "autonomous_replan_required", guard


def main() -> int:
    global USE_SUBPROCESS_CLI
    argv = sys.argv[1:]
    unknown_args = sorted(set(argv) - {"--subprocess-cli"})
    if unknown_args:
        raise SystemExit(f"unknown arguments: {' '.join(unknown_args)}")
    USE_SUBPROCESS_CLI = "--subprocess-cli" in argv
    assert_replan_obligation_projected()
    assert_replan_obligation_projected_from_run_history()
    assert_periodic_replan_obligation_projected_from_run_history()
    assert_no_periodic_replan_before_threshold_or_after_ack()
    assert_validated_classification_without_ack_does_not_clear_replan()
    assert_refresh_state_structured_ack_clears_replan()
    assert_no_replan_obligation_without_signal()
    print("autonomous-replan-obligation-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
