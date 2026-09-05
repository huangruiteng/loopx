from __future__ import annotations

import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.capabilities.benchmark_toolkit.external_agent import (
    EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION,
    EXTERNAL_AGENT_RESULT_SCHEMA_VERSION,
)
from loopx.capabilities.benchmark_toolkit.external_agent_continuation import (
    BENCHMARK_CONTINUATION_PRIVATE_EVIDENCE_SCHEMA_VERSION,
    BenchmarkSegmentTimeout,
    _run_progress_probe,
    _run_solver_segment,
    execute_external_agent_continuation_request,
    run_external_agent_continuation_phase,
)
from loopx.cli import main


def _request(workspace: Path) -> dict[str, object]:
    return {
        "schema_version": EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION,
        "instruction": "Implement the complete benchmark task.",
        "workspace": str(workspace),
        "timeout_seconds": 10,
        "containment": {
            "schema_version": "external_agent_containment_v1",
            "kind": "container",
            "timeout_owner": "runner",
            "termination_postcondition": "drained_before_result_consumption",
            "verification": {
                "schema_version": "external_agent_containment_verification_v1",
                "status": "verified",
                "authority": "runner",
                "receipt_ref": "runner-containment-test",
            },
        },
    }


def _progress(completed: int, total: int = 5) -> dict[str, object]:
    return {
        "schema_version": "benchmark_public_progress_v0",
        "total_unit_count": total,
        "completed_unit_count": completed,
    }


def _prompt_digest(request: dict[str, object]) -> str:
    return hashlib.sha256(str(request["instruction"]).encode("utf-8")).hexdigest()


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_default_segment_runner_terminates_process_group_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdout_path = tmp_path / "segment.jsonl"
    observed: dict[str, object] = {}

    class TimedOutProcess:
        pid = 4242
        returncode: int | None = None

        def communicate(self, instruction: str, *, timeout: float):
            observed["instruction"] = instruction
            observed["timeout"] = timeout
            raise subprocess.TimeoutExpired(["solver"], timeout)

        def wait(self, *, timeout: float | None = None) -> int:
            observed["wait_timeout"] = timeout
            self.returncode = -signal.SIGTERM
            return self.returncode

    def fake_popen(*_args, **kwargs):
        observed["start_new_session"] = kwargs.get("start_new_session")
        return TimedOutProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        os, "killpg", lambda pid, sig: observed.update(killpg=(pid, sig))
    )

    with pytest.raises(BenchmarkSegmentTimeout):
        _run_solver_segment(
            ["solver"],
            tmp_path,
            {
                "PATH": os.environ.get("PATH", ""),
                "LOOPX_BENCHMARK_SEGMENT_TIMEOUT_MS": "50",
            },
            "prompt",
            stdout_path,
        )

    assert observed == {
        "start_new_session": True,
        "instruction": "prompt",
        "timeout": 0.05,
        "killpg": (4242, signal.SIGTERM),
        "wait_timeout": 1,
    }


def test_default_segment_runner_preserves_stdout(tmp_path: Path) -> None:
    stdout_path = tmp_path / "segment.jsonl"

    exit_code = _run_solver_segment(
        [sys.executable, "-c", "print('completed')"],
        tmp_path,
        {
            "PATH": os.environ.get("PATH", ""),
            "LOOPX_BENCHMARK_SEGMENT_TIMEOUT_MS": "5000",
        },
        "prompt",
        stdout_path,
    )

    assert exit_code == 0
    assert stdout_path.read_text(encoding="utf-8").strip() == "completed"


def test_default_progress_probe_uses_allocated_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        observed["command"] = args[0]
        observed["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(_progress(0)),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    progress = _run_progress_probe(["progress"], tmp_path, {}, 125)

    assert progress == _progress(0)
    assert observed == {"command": ["progress"], "timeout": 0.125}


def test_initial_progress_probe_uses_remaining_shared_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request["timeout_seconds"] = 0.05
    probe_timeouts: list[int] = []

    def timed_out_probe(_command, _cwd, _environment, timeout_ms):
        probe_timeouts.append(timeout_ms)
        raise subprocess.TimeoutExpired(["progress"], timeout_ms / 1000)

    result = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=_prompt_digest(request),
        expected_total_unit_count=5,
        max_agent_segments=2,
        private_evidence_root=tmp_path / "evidence",
        progress_runner=timed_out_probe,
        clock=lambda: 0.0,
    )

    assert probe_timeouts == [50]
    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == (
        "continuation_progress_probe_timed_out"
    )


def test_post_segment_progress_probe_uses_remaining_shared_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request["timeout_seconds"] = 0.1
    now = 0.0
    probe_timeouts: list[int] = []

    def segment_runner(_command, _cwd, _environment, _instruction, stdout_path):
        nonlocal now
        stdout_path.write_text('{"type":"turn.completed"}\n', encoding="utf-8")
        now = 0.075
        return 0

    def progress_runner(_command, _cwd, _environment, timeout_ms):
        probe_timeouts.append(timeout_ms)
        if len(probe_timeouts) == 1:
            return _progress(0)
        raise subprocess.TimeoutExpired(["progress"], timeout_ms / 1000)

    result = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=_prompt_digest(request),
        expected_total_unit_count=5,
        max_agent_segments=1,
        private_evidence_root=tmp_path / "evidence",
        segment_runner=segment_runner,
        progress_runner=progress_runner,
        clock=lambda: now,
    )

    assert probe_timeouts == [100, 25]
    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == (
        "continuation_progress_probe_timed_out"
    )
    evidence = json.loads(
        (tmp_path / "evidence" / "continuation-private.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["segments"][0]["progress_probe_status"] == "timed_out"


def test_continuation_phase_uses_remaining_budget_after_segment_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)

    calls = 0

    def timed_out_segment(_command, _cwd, _environment, _instruction, stdout_path):
        nonlocal calls
        calls += 1
        stdout_path.write_text('{"type":"thread.started"}\n', encoding="utf-8")
        if calls == 1:
            raise BenchmarkSegmentTimeout
        return 0

    progress_values = iter([_progress(0), _progress(1), _progress(5)])

    result = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=_prompt_digest(request),
        expected_total_unit_count=5,
        max_agent_segments=2,
        private_evidence_root=tmp_path / "evidence",
        segment_runner=timed_out_segment,
        progress_runner=lambda *_args: next(progress_values),
    )

    assert result["status"] == "succeeded"
    assert result["receipt"]["classification"] == "solver_completed"
    evidence = json.loads(
        (tmp_path / "evidence" / "continuation-private.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["terminal_decision"] == "stop_complete"
    assert evidence["segments"][0]["timed_out"] is True
    assert evidence["segments"][1]["timed_out"] is False


def test_continuation_phase_runs_bounded_segments_and_writes_private_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    evidence_root = tmp_path / "evidence"
    prompts: list[str] = []
    environments: list[dict[str, str]] = []
    progress_values = iter(
        [_progress(0, total=3), _progress(1, total=3), _progress(3, total=3)]
    )
    def segment_runner(command, cwd, environment, instruction, stdout_path):
        assert command == ["solver"]
        assert cwd == workspace
        prompts.append(instruction)
        environments.append(dict(environment))
        stdout_path.write_text('{"type":"turn.completed"}\n', encoding="utf-8")
        stdout_path.chmod(0o600)
        return 0

    def progress_runner(command, cwd, environment, timeout_ms):
        assert command == ["progress"]
        assert cwd == workspace
        assert "SYNTHETIC_AGENT_SECRET" not in environment
        assert timeout_ms > 0
        return next(progress_values)

    monkeypatch.setenv("SYNTHETIC_AGENT_SECRET", "must-not-cross")
    request = _request(workspace)
    result = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=_prompt_digest(request),
        expected_total_unit_count=3,
        max_agent_segments=3,
        private_evidence_root=evidence_root,
        segment_runner=segment_runner,
        progress_runner=progress_runner,
        clock=lambda: 0.0,
    )

    assert result["status"] == "succeeded"
    assert result["receipt"]["classification"] == "solver_completed"
    instruction = str(request["instruction"])
    assert prompts[0] == instruction
    assert prompts[1].startswith(instruction + "\n\nLoopX continuation:\n")
    assert "Public progress: 1/3 units complete." in prompts[1]
    assert [item["LOOPX_BENCHMARK_SEGMENT_INDEX"] for item in environments] == [
        "1",
        "2",
    ]
    assert all(item["LOOPX_BENCHMARK_SEGMENT_TIMEOUT_MS"] for item in environments)
    evidence_path = evidence_root / "continuation-private.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == (
        BENCHMARK_CONTINUATION_PRIVATE_EVIDENCE_SCHEMA_VERSION
    )
    assert evidence["terminal_decision"] == "stop_complete"
    assert len(evidence["segments"]) == 2
    assert all(segment["timed_out"] is False for segment in evidence["segments"])
    assert evidence["raw_task_recorded"] is False
    if os.name == "posix":
        assert stat.S_IMODE(evidence_root.stat().st_mode) == 0o700
        assert stat.S_IMODE(evidence_path.stat().st_mode) == 0o600
        assert all(
            stat.S_IMODE((evidence_root / segment["stdout_file"]).stat().st_mode)
            == 0o600
            for segment in evidence["segments"]
        )


@pytest.mark.parametrize(
    ("expected_digest", "progress_values", "classification"),
    [
        ("b" * 64, [_progress(0)], "continuation_first_prompt_mismatch"),
        (None, [_progress(2), _progress(1)], "continuation_contract_mismatch"),
    ],
)
def test_continuation_phase_fails_closed_before_or_after_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expected_digest: str | None,
    progress_values: list[dict[str, object]],
    classification: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    provider_calls = 0
    progress = iter(progress_values)

    def segment_runner(_command, _cwd, _environment, _instruction, stdout_path):
        nonlocal provider_calls
        provider_calls += 1
        stdout_path.write_text('{"type":"turn.completed"}\n', encoding="utf-8")
        return 0

    result = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=expected_digest or _prompt_digest(request),
        expected_total_unit_count=5,
        max_agent_segments=2,
        private_evidence_root=tmp_path / "evidence",
        segment_runner=segment_runner,
        progress_runner=lambda *_args: next(progress),
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == classification
    assert provider_calls == (0 if expected_digest else 1)


def test_continuation_phase_skips_complete_and_rejects_missing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    called = False

    def segment_runner(*_args):
        nonlocal called
        called = True
        return 0

    complete = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=_prompt_digest(request),
        expected_total_unit_count=5,
        max_agent_segments=2,
        private_evidence_root=tmp_path / "complete-evidence",
        segment_runner=segment_runner,
        progress_runner=lambda *_args: _progress(5),
    )
    assert complete["receipt"]["classification"] == ("continuation_not_needed_complete")
    assert called is False

    def empty_segment(_command, _cwd, _environment, _instruction, stdout_path):
        stdout_path.touch()
        return 0

    missing = run_external_agent_continuation_phase(
        request,
        solver_command=["solver"],
        progress_command=["progress"],
        expected_first_prompt_sha256=_prompt_digest(request),
        expected_total_unit_count=5,
        max_agent_segments=2,
        private_evidence_root=tmp_path / "missing-evidence",
        segment_runner=empty_segment,
        progress_runner=lambda *_args: _progress(0),
    )
    assert missing["receipt"]["classification"] == (
        "continuation_segment_evidence_missing"
    )


def test_continuation_phase_rejects_evidence_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    with pytest.raises(
        ValueError, match="benchmark_private_evidence_root_overlaps_workspace"
    ):
        run_external_agent_continuation_phase(
            request,
            solver_command=["solver"],
            progress_command=["progress"],
            expected_first_prompt_sha256=_prompt_digest(request),
            expected_total_unit_count=5,
            max_agent_segments=2,
            private_evidence_root=workspace / "evidence",
            progress_runner=lambda *_args: _progress(0),
        )


def test_continuation_agent_phase_cli_runs_fake_provider_segments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    evidence_root = tmp_path / "evidence"
    (workspace / "progress.txt").write_text("0", encoding="utf-8")
    request = _request(workspace)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    solver_code = (
        "import json, pathlib, sys; root=pathlib.Path('.'); "
        "prompt=sys.stdin.read(); p=root/'prompts.jsonl'; "
        "p.open('a').write(json.dumps(prompt)+'\\n'); "
        "s=root/'progress.txt'; n=int(s.read_text())+1; s.write_text(str(n)); "
        "print(json.dumps({'type':'turn.completed','segment':n}))"
    )
    progress_code = (
        "import json, pathlib; n=int(pathlib.Path('progress.txt').read_text()); "
        "print(json.dumps({'schema_version':'benchmark_public_progress_v0',"
        "'total_unit_count':2,'completed_unit_count':n}))"
    )

    exit_code = main(
        [
            "--format",
            "json",
            "benchmark",
            "continuation-agent-phase",
            "--request",
            str(request_path),
            "--result",
            str(result_path),
            "--solver-command-json",
            json.dumps([sys.executable, "-c", solver_code]),
            "--progress-command-json",
            json.dumps([sys.executable, "-c", progress_code]),
            "--expected-first-prompt-sha256",
            _prompt_digest(request),
            "--expected-total-unit-count",
            "2",
            "--max-agent-segments",
            "2",
            "--private-evidence-root",
            str(evidence_root),
            "--execute",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    persisted = json.loads(result_path.read_text(encoding="utf-8"))
    evidence = json.loads(
        (evidence_root / "continuation-private.json").read_text(encoding="utf-8")
    )
    prompts = [
        json.loads(line)
        for line in (workspace / "prompts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert exit_code == 0
    assert output == persisted
    assert persisted["schema_version"] == EXTERNAL_AGENT_RESULT_SCHEMA_VERSION
    assert prompts[0] == request["instruction"]
    assert prompts[1].startswith(str(request["instruction"]) + "\n\n")
    assert evidence["terminal_decision"] == "stop_complete"
    assert all(
        (evidence_root / segment["stdout_file"]).stat().st_size > 0
        for segment in evidence["segments"]
    )


def test_continuation_agent_phase_preview_and_result_path_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    evidence_root = tmp_path / "evidence"
    request = _request(workspace)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    common = [
        "--request",
        str(request_path),
        "--solver-command-json",
        '["solver"]',
        "--progress-command-json",
        '["progress"]',
        "--expected-first-prompt-sha256",
        _prompt_digest(request),
        "--expected-total-unit-count",
        "2",
        "--max-agent-segments",
        "2",
        "--private-evidence-root",
        str(evidence_root),
    ]
    exit_code = main(
        [
            "--format",
            "json",
            "benchmark",
            "continuation-agent-phase",
            "--result",
            str(result_path),
            *common,
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["receipt"]["classification"] == (
        "continuation_request_validated_not_executed"
    )
    assert result_path.is_file()
    assert not evidence_root.exists()

    with pytest.raises(
        ValueError, match="benchmark_private_evidence_result_path_overlap"
    ):
        execute_external_agent_continuation_request(
            request_path=request_path,
            result_path=evidence_root / "result.json",
            solver_command=["solver"],
            progress_command=["progress"],
            expected_first_prompt_sha256=_prompt_digest(request),
            expected_total_unit_count=2,
            max_agent_segments=2,
            private_evidence_root=evidence_root,
            execute=False,
        )
