from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from loopx.control_plane.turn_driver.codex_cli import (
    CODEX_CLI_SESSION_SCHEMA_VERSION,
    codex_cli_result_schema,
    codex_cli_session_binding,
    load_codex_cli_session,
    run_codex_cli_host,
)


def _request(
    *,
    turn_key: str = "sha256:" + "a" * 64,
    session_action: str = "start_new",
) -> dict[str, object]:
    return {
        "schema_version": "loopx_turn_host_request_v0",
        "turn_key": turn_key,
        "route": "ready_for_host",
        "session": {
            "schema_version": "loopx_turn_session_binding_v0",
            "action": session_action,
        },
        "turn_envelope": {
            "schema_version": "loopx_turn_envelope_v0",
            "goal_id": "fixture-goal",
            "agent_id": "codex-fixture",
            "action": {
                "selected_todo": {
                    "todo_id": "todo_fixture0001",
                    "text": "Advance one public fixture",
                }
            },
        },
        "result_contract": {
            "schema_version": "loopx_turn_result_v0",
            "completed_phases": ["host_execute", "typed_result"],
        },
    }


def _fake_codex(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "fake-codex"
    log_path = tmp_path / "codex-argv.jsonl"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import re
import sys
import time

args = sys.argv[1:]
prompt = sys.stdin.read()
log = pathlib.Path(os.environ["FAKE_CODEX_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
turn_key = re.search(r'"turn_key":"([^"]+)"', prompt).group(1)
print(json.dumps({
    "type": "thread.started",
    "thread_id": "session-fixture-0001",
    "raw_trajectory": "must-not-persist",
    "private_material": "must-not-persist"
}), flush=True)
if os.environ.get("FAKE_CODEX_FAIL") == "1":
    if os.environ.get("FAKE_CODEX_FAILURE_CATEGORY") == "model":
        print("This model requires a newer version of Codex.", file=sys.stderr)
    if os.environ.get("FAKE_CODEX_FAILURE_CATEGORY") == "session":
        print("Session not found.", file=sys.stderr)
    raise SystemExit(9)
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
output_path.write_text(json.dumps({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": turn_key,
    "result_kind": "validated_progress",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "fixture_progress",
    "recommended_action": "Continue the public fixture",
    "next_action": "Run the next public fixture check",
    "delivery_batch_scale": "implementation",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The fixture objective remains unchanged.",
    "summary": "One public fixture advanced."
}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable, log_path


def test_codex_cli_result_schema_requires_only_bounded_contract_fields() -> None:
    schema = codex_cli_result_schema()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "raw_trajectory" not in schema["properties"]
    assert "stdout" not in schema["properties"]
    assert {
        field: schema["properties"][field]["maxLength"]
        for field in (
            "classification",
            "recommended_action",
            "next_action",
            "vision_unchanged_reason",
            "summary",
        )
    } == {
        "classification": 120,
        "recommended_action": 1_200,
        "next_action": 1_200,
        "vision_unchanged_reason": 240,
        "summary": 400,
    }


def test_codex_cli_host_starts_then_resumes_opaque_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    project.mkdir()
    first_request = _request()

    first = run_codex_cli_host(
        first_request,
        runtime_root=runtime_root,
        project=project,
        codex_bin=str(executable),
        timeout_seconds=5,
    )
    with pytest.raises(RuntimeError, match="binding changed after planning"):
        run_codex_cli_host(
            _request(turn_key="sha256:" + "c" * 64),
            runtime_root=runtime_root,
            project=project,
            codex_bin=str(executable),
            timeout_seconds=5,
        )
    second_request = _request(
        turn_key="sha256:" + "b" * 64,
        session_action="resume",
    )
    second = run_codex_cli_host(
        second_request,
        runtime_root=runtime_root,
        project=project,
        codex_bin=str(executable),
        timeout_seconds=5,
    )

    assert first["turn_key"] == first_request["turn_key"]
    assert second["turn_key"] == second_request["turn_key"]
    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "resume" not in argv_rows[0]
    assert "resume" in argv_rows[1]
    assert "session-fixture-0001" in argv_rows[1]

    envelope = first_request["turn_envelope"]
    assert isinstance(envelope, dict)
    binding = codex_cli_session_binding(runtime_root, envelope)
    assert binding == {
        "schema_version": "loopx_turn_session_binding_v0",
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "todo_id": "todo_fixture0001",
    }
    lineage = {key: binding[key] for key in ("goal_id", "agent_id", "todo_id")}
    session = load_codex_cli_session(runtime_root, lineage=lineage)
    assert session is not None
    assert session["schema_version"] == CODEX_CLI_SESSION_SCHEMA_VERSION
    assert set(session) == {
        "schema_version",
        "goal_id",
        "agent_id",
        "todo_id",
        "host",
        "session_id",
    }
    session_paths = list(runtime_root.glob("goals/*/turn-sessions/*.json"))
    assert len(session_paths) == 1
    assert stat.S_IMODE(session_paths[0].stat().st_mode) == 0o600
    persisted = session_paths[0].read_text(encoding="utf-8")
    assert "raw_trajectory" not in persisted
    assert "private_material" not in persisted


def test_codex_cli_host_ignores_legacy_session_eligibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    project.mkdir()
    request = _request()
    run_codex_cli_host(
        request,
        runtime_root=runtime_root,
        project=project,
        codex_bin=str(executable),
        timeout_seconds=5,
    )
    session_path = next(runtime_root.glob("goals/*/turn-sessions/*.json"))
    legacy = json.loads(session_path.read_text(encoding="utf-8"))
    legacy["schema_version"] = "loopx_codex_cli_session_v0"
    session_path.write_text(json.dumps(legacy), encoding="utf-8")

    envelope = request["turn_envelope"]
    assert isinstance(envelope, dict)
    assert codex_cli_session_binding(runtime_root, envelope) is None


def test_codex_cli_host_preserves_session_after_failed_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_FAIL", "1")
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    project.mkdir()
    request = _request()

    with pytest.raises(RuntimeError, match="codex_cli_exit_nonzero"):
        run_codex_cli_host(
            request,
            runtime_root=runtime_root,
            project=project,
            codex_bin=str(executable),
            timeout_seconds=5,
        )

    envelope = request["turn_envelope"]
    assert isinstance(envelope, dict)
    assert codex_cli_session_binding(runtime_root, envelope) is not None


def test_codex_cli_host_preserves_observed_session_after_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_SLEEP", "2")
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    project.mkdir()
    request = _request()

    with pytest.raises(RuntimeError, match="codex_cli_timeout"):
        run_codex_cli_host(
            request,
            runtime_root=runtime_root,
            project=project,
            codex_bin=str(executable),
            timeout_seconds=0.1,
        )

    envelope = request["turn_envelope"]
    assert isinstance(envelope, dict)
    assert codex_cli_session_binding(runtime_root, envelope) is not None


def test_codex_cli_host_classifies_failure_without_persisting_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_FAIL", "1")
    monkeypatch.setenv("FAKE_CODEX_FAILURE_CATEGORY", "model")
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(
        RuntimeError,
        match="codex_cli_model_requires_newer_codex",
    ):
        run_codex_cli_host(
            _request(),
            runtime_root=runtime_root,
            project=project,
            codex_bin=str(executable),
            timeout_seconds=5,
        )

    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in runtime_root.rglob("*.json")
    )
    assert "requires a newer version" not in persisted
    envelope = _request()["turn_envelope"]
    assert isinstance(envelope, dict)
    assert codex_cli_session_binding(runtime_root, envelope) is None

    monkeypatch.delenv("FAKE_CODEX_FAIL")
    monkeypatch.delenv("FAKE_CODEX_FAILURE_CATEGORY")
    recovered = run_codex_cli_host(
        _request(turn_key="sha256:" + "d" * 64),
        runtime_root=runtime_root,
        project=project,
        codex_bin=str(executable),
        timeout_seconds=5,
    )
    assert recovered["result_kind"] == "validated_progress"
    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "resume" not in argv_rows[1]


def test_codex_cli_host_discards_missing_resume_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    runtime_root = tmp_path / "runtime"
    project = tmp_path / "project"
    project.mkdir()
    first_request = _request()
    run_codex_cli_host(
        first_request,
        runtime_root=runtime_root,
        project=project,
        codex_bin=str(executable),
        timeout_seconds=5,
    )

    monkeypatch.setenv("FAKE_CODEX_FAIL", "1")
    monkeypatch.setenv("FAKE_CODEX_FAILURE_CATEGORY", "session")
    with pytest.raises(RuntimeError, match="codex_cli_session_missing"):
        run_codex_cli_host(
            _request(
                turn_key="sha256:" + "f" * 64,
                session_action="resume",
            ),
            runtime_root=runtime_root,
            project=project,
            codex_bin=str(executable),
            timeout_seconds=5,
        )

    envelope = first_request["turn_envelope"]
    assert isinstance(envelope, dict)
    assert codex_cli_session_binding(runtime_root, envelope) is None
