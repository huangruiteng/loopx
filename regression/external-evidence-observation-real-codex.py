#!/usr/bin/env python3
"""Opt-in real Codex CLI regression for external-evidence observation.

The default path builds a Goal Harness quota payload and verifies the machine
contract locally. Pass --real-codex to also invoke the host Codex CLI in an
isolated read-only fixture and verify that it interprets the quota contract as
an observation/blocker task rather than a quiet no-op or benchmark execution.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "external-evidence-real-codex-fixture"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-codex",
        action="store_true",
        help="Invoke the real host Codex CLI. This consumes a real Codex run.",
    )
    parser.add_argument(
        "--codex-cli",
        default="codex",
        help="Codex CLI executable to use with --real-codex.",
    )
    parser.add_argument(
        "--codex-model",
        default="gpt-5.4-mini",
        help="Codex model for the opt-in real CLI call.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Timeout for the opt-in real Codex CLI call.",
    )
    return parser.parse_args()


def run_goal_harness(root: Path, *args: str, registry: Path, runtime: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".goal-harness" / "registry.json"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: waiting-for-external-worker\n"
        "owner_mode: goal\n"
        'objective: "Exercise real Codex interpretation of an external evidence guard."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# External Evidence Real Codex Fixture\n\n"
        "## Next Action\n\n"
        "- Observe for a compact result from a separate benchmark execution thread.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Target execution-thread result monitor: observe whether the relay packet has produced a compact execution result or blocker from a separate benchmark execution thread. If no new compact result/blocker exists, quiet no-op without quota spend; do not run Docker/Codex/model APIs from the meta heartbeat.\n",
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
                        "domain": "external-evidence-real-codex-fixture",
                        "status": "waiting-for-external-worker",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "waiting_on": "external_evidence",
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
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
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    progress_record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "waiting_for_external_worker_result_v0",
        "recommended_action": "Observe for a compact result from a separate benchmark execution thread.",
        "health_check": "state_file 1/1; registry_goal 1/1",
        "delivery_batch_scale": "single_surface",
        "json_path": str(runs_dir / "2026-01-01T00-00-00+00-00.json"),
        "markdown_path": str(runs_dir / "2026-01-01T00-00-00+00-00.md"),
    }
    Path(progress_record["json_path"]).write_text(json.dumps(progress_record) + "\n", encoding="utf-8")
    Path(progress_record["markdown_path"]).write_text("# Fixture External Evidence Wait\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(progress_record) + "\n")
    return project, runtime, registry_path


def compact_guard_for_codex(guard: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal_id": guard.get("goal_id"),
        "state": guard.get("state"),
        "waiting_on": guard.get("waiting_on"),
        "should_run": guard.get("should_run"),
        "effective_action": guard.get("effective_action"),
        "heartbeat_recommendation": guard.get("heartbeat_recommendation"),
        "execution_obligation": guard.get("execution_obligation"),
        "external_evidence_observation": guard.get("external_evidence_observation"),
        "fixture_observed_handle_present": False,
    }


def write_output_schema(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "action_kind",
                    "quiet_noop_allowed",
                    "benchmark_execution_allowed",
                    "reason",
                ],
                "properties": {
                    "action_kind": {
                        "type": "string",
                        "enum": [
                            "read_only_observation",
                            "compact_blocker_writeback",
                            "quiet_noop",
                            "benchmark_execution",
                        ],
                    },
                    "quiet_noop_allowed": {"type": "boolean"},
                    "benchmark_execution_allowed": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def codex_prompt(guard: dict[str, Any]) -> str:
    return (
        "You are a Codex executor compatibility probe for Goal Harness.\n"
        "Use only the JSON quota guard below. Do not read files, run shell "
        "commands, start Docker, invoke benchmark/model APIs, upload, submit, "
        "or inspect credentials.\n\n"
        "Rules:\n"
        "- If execution_obligation.kind is external_evidence_observation_required, "
        "quiet_noop_allowed must be false.\n"
        "- If fixture_observed_handle_present is false and "
        "external_evidence_observation.requires_observable_handle is true, choose "
        "action_kind compact_blocker_writeback.\n"
        "- benchmark_execution_allowed must be false unless the guard explicitly "
        "says delivery_allowed true, which this fixture does not.\n"
        "- Return only JSON matching the schema.\n\n"
        "Quota guard JSON:\n"
        f"{json.dumps(guard, ensure_ascii=False, indent=2, sort_keys=True)}\n"
    )


def run_real_codex(
    *,
    codex_cli: str,
    codex_model: str,
    guard: dict[str, Any],
    timeout_seconds: int,
    workdir: Path,
) -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    schema_path = workdir / "codex-output-schema.json"
    output_path = workdir / "codex-last-message.json"
    write_output_schema(schema_path)
    command = [
        codex_cli,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--model",
        codex_model,
        "--sandbox",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-C",
        str(workdir),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        codex_prompt(guard),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=workdir,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "real Codex CLI regression timed out: "
            f"stdout_tail={(exc.stdout or '')[-500:] if isinstance(exc.stdout, str) else ''} "
            f"stderr_tail={(exc.stderr or '')[-500:] if isinstance(exc.stderr, str) else ''}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            "real Codex CLI regression failed: "
            f"returncode={exc.returncode} "
            f"stdout_tail={exc.stdout[-500:] if isinstance(exc.stdout, str) else ''} "
            f"stderr_tail={exc.stderr[-1000:] if isinstance(exc.stderr, str) else ''}"
        ) from exc
    text = output_path.read_text(encoding="utf-8").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Codex output was not valid JSON: {text[:500]}\nstdout={result.stdout[-500:]}\nstderr={result.stderr[-500:]}"
        ) from exc
    parsed["_stdout_chars"] = len(result.stdout)
    parsed["_stderr_chars"] = len(result.stderr)
    return parsed


def assert_contract(guard: dict[str, Any]) -> None:
    assert guard["should_run"] is False, guard
    assert guard["state"] == "waiting", guard
    assert guard["waiting_on"] == "external_evidence", guard
    assert guard["effective_action"] == "external_evidence_observe", guard
    observation = guard["external_evidence_observation"]
    assert observation["required"] is True, observation
    assert observation["requires_observable_handle"] is True, observation
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    assert (
        guard["execution_obligation"]["kind"]
        == "external_evidence_observation_required"
    ), guard


def assert_real_codex_decision(decision: dict[str, Any]) -> None:
    assert decision["action_kind"] == "compact_blocker_writeback", decision
    assert decision["quiet_noop_allowed"] is False, decision
    assert decision["benchmark_execution_allowed"] is False, decision


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="goal-harness-real-codex-observation-") as raw_tmp:
        root = Path(raw_tmp)
        project, runtime, registry = write_fixture(root)
        guard = run_goal_harness(
            root,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--scan-path",
            str(project),
            registry=registry,
            runtime=runtime,
        )
        assert_contract(guard)
        compact = compact_guard_for_codex(guard)
        if args.real_codex:
            decision = run_real_codex(
                codex_cli=args.codex_cli,
                codex_model=args.codex_model,
                guard=compact,
                timeout_seconds=args.timeout_seconds,
                workdir=root / "codex-workdir",
            )
            assert_real_codex_decision(decision)
            print(
                "external-evidence-observation-real-codex-smoke ok "
                "mode=real-codex action=compact_blocker_writeback"
            )
        else:
            print(
                "external-evidence-observation-real-codex-smoke ok "
                "mode=contract-only; pass --real-codex to invoke host Codex CLI"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
