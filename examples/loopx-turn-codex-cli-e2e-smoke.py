#!/usr/bin/env python3
"""Qualify one or two LoopX Turn transactions with a Codex CLI host."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.cli import main as cli_main  # noqa: E402
from loopx.control_plane.turn_driver import (  # noqa: E402
    load_loopx_turn_plan_from_journal,
)


GOAL_ID = "loopx-turn-real-cli-e2e"
AGENT_ID = "codex-turn-e2e"
TODO_ID = "todo_turnreale2e01"
MARKER_NAME = "docs/turn-e2e-marker.txt"
MARKER_VALUES = (
    "loopx-turn-real-e2e-step-one",
    "loopx-turn-real-e2e-step-two",
)


def _write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    workspace = root / "workspace"
    runtime.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (workspace / "docs").mkdir()
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# LoopX Turn Real CLI E2E",
                "",
                "## Agent Todo",
                "",
                (
                    f"- [ ] [P0] Advance `{MARKER_NAME}` by exactly one step per "
                    f"Turn: missing -> `{MARKER_VALUES[0]}` -> `{MARKER_VALUES[1]}`. "
                    "Report validated progress after each step."
                ),
                (
                    f"  <!-- loopx:todo todo_id={TODO_ID} status=open "
                    "task_class=advancement_task action_kind=real_cli_e2e "
                    f"claimed_by={AGENT_ID} priority=P0 -->"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "loopx-turn-public-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                        "adapter": {
                            "kind": "fixture_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                            "agent_profiles": {
                                AGENT_ID: {
                                    "schema_version": "agent_profile_v1",
                                    "profile_role": "fixture",
                                    "scope": "public qualification",
                                }
                            },
                            "write_scope": ["docs/**"],
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
    return project, runtime, workspace, registry


def _write_fake_codex(root: Path) -> Path:
    executable = root / "fake-codex"
    executable.write_text(
        f"""#!/usr/bin/env python3
import json
import pathlib
import re
import sys

args = sys.argv[1:]
prompt = sys.stdin.read()
turn_key = re.search(r'"turn_key":"([^"]+)"', prompt).group(1)
resumed = "resume" in args
marker_value = {MARKER_VALUES[1]!r} if resumed else {MARKER_VALUES[0]!r}
pathlib.Path({MARKER_NAME!r}).write_text(marker_value, encoding="utf-8")
print(json.dumps({{
    "type": "thread.started",
    "thread_id": "session-fixture-0001",
}}), flush=True)
output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
output_path.write_text(json.dumps({{
    "schema_version": "loopx_turn_result_v0",
    "turn_key": turn_key,
    "result_kind": "validated_progress",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "real_cli_e2e_fixture_progress",
    "recommended_action": "Keep the qualified Turn path available.",
    "next_action": "No follow-up is required for this fixture.",
    "delivery_batch_scale": "single_surface",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The fixture objective remains unchanged.",
    "summary": "The isolated public marker was created.",
}}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _validator_command(expected_marker: str) -> list[str]:
    program = (
        "import json,pathlib,sys; "
        "json.load(sys.stdin); "
        f"p=pathlib.Path({MARKER_NAME!r}); "
        "raise SystemExit(0 if p.is_file() and "
        f"p.read_text(encoding='utf-8').strip() == {expected_marker!r} else 9)"
    )
    return [sys.executable, "-c", program]


def _run_cli(argv: list[str]) -> tuple[int, dict[str, Any]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(argv)
    payload = json.loads(output.getvalue())
    assert isinstance(payload, dict), payload
    return exit_code, payload


def _base_argv(
    *,
    registry: Path,
    runtime: Path,
    workspace: Path,
    codex_bin: Path,
    model: str | None,
    timeout_seconds: float,
    expected_marker: str,
) -> list[str]:
    argv = [
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "turn",
        "run-once",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--host",
        "codex-cli",
        "--execution-mode",
        "isolated-headless",
        "--project",
        str(workspace),
        "--codex-bin",
        str(codex_bin),
        "--codex-sandbox",
        "workspace-write",
        "--validation-command-json",
        json.dumps(_validator_command(expected_marker)),
        "--scan-root",
        str(registry.parent.parent),
        "--no-global-sync",
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    if model:
        argv.extend(["--codex-model", model])
    return argv


def _quota_spend_count(runtime: Path) -> int:
    index = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    if not index.is_file():
        return 0
    return sum(
        1
        for line in index.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("classification") == "quota_slot_spent"
    )


def _marker_matches(workspace: Path, expected: str) -> bool:
    marker = workspace / MARKER_NAME
    return marker.is_file() and marker.read_text(encoding="utf-8").strip() == expected


def _session_action(runtime: Path, turn_key: object) -> str | None:
    if not isinstance(turn_key, str):
        return None
    plan = load_loopx_turn_plan_from_journal(
        runtime,
        goal_id=GOAL_ID,
        turn_key=turn_key,
    )
    session = plan.get("session")
    return str(session.get("action")) if isinstance(session, dict) else None


def _summary(
    *,
    real_codex_cli: bool,
    two_turn_resume: bool,
    first_exit_code: int,
    first: dict[str, Any],
    first_marker_valid: bool,
    second_exit_code: int | None,
    second: dict[str, Any] | None,
    second_marker_valid: bool | None,
    replay_exit_code: int | None,
    replay: dict[str, Any] | None,
    runtime: Path,
    workspace: Path,
    model_explicit: bool,
) -> dict[str, Any]:
    validation = first.get("validation")
    effects = first.get("effects")
    receipt = first.get("receipt")
    return {
        "schema_version": "loopx_turn_real_cli_e2e_v0",
        "real_codex_cli_invoked": real_codex_cli,
        "two_turn_resume_requested": two_turn_resume,
        "model_explicit": model_explicit,
        "first_exit_code": first_exit_code,
        "first_session_action": _session_action(
            runtime, first.get("resume_turn_key")
        ),
        "status": first.get("status"),
        "reason": first.get("reason"),
        "result_kind": first.get("result_kind"),
        "receipt_status": receipt.get("status") if isinstance(receipt, dict) else None,
        "validation_status": (
            validation.get("status") if isinstance(validation, dict) else None
        ),
        "effects": effects if isinstance(effects, dict) else {},
        "first_marker_valid": first_marker_valid,
        "second_exit_code": second_exit_code,
        "second_status": second.get("status") if isinstance(second, dict) else None,
        "second_receipt_status": (
            second.get("receipt", {}).get("status")
            if isinstance(second, dict) and isinstance(second.get("receipt"), dict)
            else None
        ),
        "second_validation_status": (
            second.get("validation", {}).get("status")
            if isinstance(second, dict) and isinstance(second.get("validation"), dict)
            else None
        ),
        "second_effects": (
            second.get("effects") if isinstance(second, dict) else None
        ),
        "second_session_action": (
            _session_action(runtime, second.get("resume_turn_key"))
            if isinstance(second, dict)
            else None
        ),
        "second_marker_valid": second_marker_valid,
        "session_resumed": (
            isinstance(second, dict)
            and _session_action(runtime, second.get("resume_turn_key")) == "resume"
        ),
        "marker_valid": _marker_matches(
            workspace,
            MARKER_VALUES[1] if two_turn_resume else MARKER_VALUES[0],
        ),
        "quota_slot_spend_count": _quota_spend_count(runtime),
        "replay_exit_code": replay_exit_code,
        "replay_effects": replay.get("effects") if isinstance(replay, dict) else None,
        "loopx_raw_host_output_recorded": False,
        "global_registry_synced": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-codex-cli",
        action="store_true",
        help="Invoke the real Codex CLI host instead of the no-model fixture binary.",
    )
    parser.add_argument("--codex-bin", type=Path)
    parser.add_argument("--codex-model")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--two-turn-resume",
        action="store_true",
        help=(
            "Run two separately validated transactions on one opaque Codex CLI "
            "session, then replay the second transaction idempotently."
        ),
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="loopx-turn-real-cli-e2e-") as directory:
        root = Path(directory)
        project, runtime, workspace, registry = _write_fixture(root)
        if args.real_codex_cli:
            candidate = args.codex_bin or (
                Path(found) if (found := shutil.which("codex")) else None
            )
            if candidate is None or not candidate.exists():
                raise SystemExit("codex CLI is required for --real-codex-cli")
            codex_bin = candidate
        else:
            codex_bin = _write_fake_codex(root)

        base = _base_argv(
            registry=registry,
            runtime=runtime,
            workspace=workspace,
            codex_bin=codex_bin,
            model=args.codex_model,
            timeout_seconds=args.timeout_seconds,
            expected_marker=MARKER_VALUES[0],
        )
        first_exit_code, first = _run_cli([*base, "--execute"])
        first_marker_valid = _marker_matches(workspace, MARKER_VALUES[0])
        second_exit_code: int | None = None
        second: dict[str, Any] | None = None
        second_marker_valid: bool | None = None
        if args.two_turn_resume and first_exit_code == 0:
            second_base = _base_argv(
                registry=registry,
                runtime=runtime,
                workspace=workspace,
                codex_bin=codex_bin,
                model=args.codex_model,
                timeout_seconds=args.timeout_seconds,
                expected_marker=MARKER_VALUES[1],
            )
            second_exit_code, second = _run_cli([*second_base, "--execute"])
            second_marker_valid = _marker_matches(workspace, MARKER_VALUES[1])
        replay_exit_code: int | None = None
        replay: dict[str, Any] | None = None
        replay_source = second if isinstance(second, dict) else first
        turn_key = replay_source.get("resume_turn_key")
        if first_exit_code == 0 and isinstance(turn_key, str):
            replay_exit_code, replay = _run_cli(
                [*base, "--resume-turn-key", turn_key, "--execute"]
            )
        summary = _summary(
            real_codex_cli=bool(args.real_codex_cli),
            two_turn_resume=bool(args.two_turn_resume),
            first_exit_code=first_exit_code,
            first=first,
            first_marker_valid=first_marker_valid,
            second_exit_code=second_exit_code,
            second=second,
            second_marker_valid=second_marker_valid,
            replay_exit_code=replay_exit_code,
            replay=replay,
            runtime=runtime,
            workspace=workspace,
            model_explicit=bool(args.codex_model),
        )

    print(json.dumps(summary, indent=2, sort_keys=True))
    expected_effects = {
        "host_invoked": True,
        "state_written": True,
        "quota_spent": True,
        "scheduler_acknowledged": False,
    }
    replay_effects = {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    committed_effects = expected_effects
    two_turn_ok = (
        summary["second_exit_code"] == 0
        and summary["second_status"] == "committed"
        and summary["second_receipt_status"] == "committed"
        and summary["second_validation_status"] == "passed"
        and summary["second_effects"] == committed_effects
        and summary["second_marker_valid"] is True
        and summary["second_session_action"] == "resume"
        and summary["session_resumed"] is True
    ) if args.two_turn_resume else True
    return 0 if (
        summary["first_exit_code"] == 0
        and summary["status"] == "committed"
        and summary["receipt_status"] == "committed"
        and summary["validation_status"] == "passed"
        and summary["effects"] == expected_effects
        and summary["marker_valid"] is True
        and summary["first_marker_valid"] is True
        and summary["quota_slot_spend_count"] == (2 if args.two_turn_resume else 1)
        and two_turn_ok
        and summary["replay_exit_code"] == 0
        and summary["replay_effects"] == replay_effects
        and summary["loopx_raw_host_output_recorded"] is False
        and summary["global_registry_synced"] is False
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
