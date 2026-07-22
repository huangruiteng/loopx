from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.control_plane.turn_driver.codex_cli import (
    CODEX_CLI_SESSION_SCHEMA_VERSION,
    _cli_dialect,
    _codex_command,
    _advisor_workspace_context,
    _normalize_advisor_result,
    codex_cli_result_schema,
    codex_cli_session_binding,
    load_codex_cli_session,
    run_codex_cli_host,
)
from loopx.control_plane.turn_driver.executor import BuiltInHostError
from loopx.control_plane.turn_driver.model_usage import event_usage, normalize_provider_usage


def test_provider_usage_rejects_internally_inconsistent_total() -> None:
    assert (
        normalize_provider_usage(
            {"input_tokens": 40, "output_tokens": 8, "total_tokens": 999}
        )
        is None
    )


def test_provider_usage_rejects_fractional_counters() -> None:
    assert (
        normalize_provider_usage(
            {"input_tokens": 40, "output_tokens": 1.9, "total_tokens": 41}
        )
        is None
    )


def test_event_usage_prefers_cumulative_total_over_last_segment() -> None:
    assert event_usage(
        {
            "payload": {
                "info": {
                    "last_token_usage": {
                        "input_tokens": 40,
                        "output_tokens": 8,
                        "total_tokens": 48,
                    },
                    "total_token_usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                    },
                }
            }
        }
    ) == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}


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
prompt_log = os.environ.get("FAKE_CODEX_PROMPT_LOG")
if prompt_log:
    with pathlib.Path(prompt_log).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(prompt) + "\\n")
turn_key = re.search(r'"turn_key":"([^"]+)"', prompt).group(1)
print(json.dumps({
    "type": "thread.started",
    "thread_id": "session-fixture-0001",
    "raw_trajectory": "must-not-persist",
    "private_material": "must-not-persist"
}), flush=True)
model = args[args.index("--model") + 1] if "--model" in args else ""
advisor = model == "advisor-fixture"
if os.environ.get("FAKE_CODEX_USAGE") == "1" and not (
    os.environ.get("FAKE_CODEX_SKIP_RESUME_USAGE") == "1" and "resume" in args
):
    print(json.dumps({
        "type": "turn.completed",
        "usage": {
            "input_tokens": 40 if advisor else 120,
            "cached_input_tokens": 5 if advisor else 20,
            "output_tokens": 8 if advisor else 30,
            "reasoning_output_tokens": 3 if advisor else 10,
            "total_tokens": 48 if advisor else 150
        }
    }), flush=True)
if os.environ.get("FAKE_CODEX_FAIL_ADVISOR") == "1" and advisor:
    print("Rate limit exceeded.", file=sys.stderr)
    raise SystemExit(9)
if os.environ.get("FAKE_CODEX_FAIL") == "1":
    if os.environ.get("FAKE_CODEX_FAILURE_CATEGORY") == "model":
        print("This model requires a newer version of Codex.", file=sys.stderr)
    if os.environ.get("FAKE_CODEX_FAILURE_CATEGORY") == "session":
        print("Session not found.", file=sys.stderr)
    raise SystemExit(9)
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
schema_path = pathlib.Path(args[args.index("--output-schema") + 1])
schema = schema_path.read_text(encoding="utf-8")
if "loopx_turn_complexity_checkpoint_v0" in schema:
    complexity = os.environ.get("FAKE_CODEX_COMPLEXITY", "simple")
    complex_case = complexity == "complex"
    if os.environ.get("FAKE_CODEX_SKIP_CHECKPOINT_INSPECTION") != "1":
        print(json.dumps({
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "inspect fixture"}
        }), flush=True)
    output_path.write_text(json.dumps({
        "schema_version": "loopx_turn_complexity_checkpoint_v0",
        "turn_key": turn_key,
        "complexity": complexity,
        "signals": ["ambiguous_root_cause"] if complex_case else [],
        "evidence_summary": (
            "Two plausible production paths remain after inspecting the fixture."
            if complex_case else
            "The fixture has one obvious bounded change."
        ),
        "relevant_paths": ["calculator.py"],
        "open_questions": ["Which path preserves the invariant?"] if complex_case else []
    }), encoding="utf-8")
    raise SystemExit(0)
if "loopx_turn_advisor_v0" in schema:
    output_path.write_text(json.dumps({
        "schema_version": "loopx_turn_advisor_v0",
        "turn_key": turn_key,
        "summary": "Inspect the boundary before changing the fixture.",
        "recommendations": ["Keep the edit bounded to the selected todo."],
        "risks": ["Do not overwrite unrelated files."],
        "validation_focus": ["Verify the exact marker value."]
    }), encoding="utf-8")
    raise SystemExit(0)
if os.environ.get("FAKE_CODEX_INVALID_FINAL_RESULT") == "1" and "resume" not in args:
    output_path.write_text(json.dumps({
        "schema_version": "loopx_turn_result_v0",
        "turn_key": turn_key,
        "result_kind": "user_action_required",
        "completed_phases": ["host_execute", "typed_result"],
        "classification": "",
        "recommended_action": "",
        "next_action": "",
        "delivery_batch_scale": "",
        "delivery_outcome": "",
        "path_delta_mode": "unchanged",
        "agent_vision_json": "",
        "vision_unchanged_reason": "The fixture objective remains unchanged.",
        "summary": "A user action is required."
    }), encoding="utf-8")
    raise SystemExit(0)
if os.environ.get("FAKE_CODEX_SKIP_FINAL_EXECUTION") != "1" or (
    "EXECUTION RETRY" in prompt
):
    print(json.dumps({
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "update fixture"}
    }), flush=True)
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


def _fake_traex(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "traex"
    log_path = tmp_path / "traex-argv.jsonl"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import re
import sys

args = sys.argv[1:]
prompt = sys.stdin.read()
log = pathlib.Path(os.environ["FAKE_TRAEX_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": args, "prompt": prompt}) + "\\n")
match = re.search(r'"turn_key":"([^"]+)"', prompt)
turn_key = match.group(1) if match else "sha256:" + "a" * 64
print(json.dumps({"type": "thread.started", "thread_id": "traex-session-fixture-0001"}), flush=True)
print(json.dumps({
    "type": "turn.completed",
    "usage": {
        "input_tokens": 120,
        "cached_input_tokens": 20,
        "output_tokens": 30,
        "reasoning_output_tokens": 10,
        "total_tokens": 150
    }
}), flush=True)
output_path = pathlib.Path(args[args.index("--output-last-message") + 1])
if prompt.rfind("loopx_turn_complexity_checkpoint_v0") > prompt.rfind("loopx_turn_result_v0"):
    print(json.dumps({
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "inspect fixture"}
    }), flush=True)
    output_path.write_text(json.dumps({
        "schema_version": "loopx_turn_complexity_checkpoint_v0",
        "turn_key": turn_key,
        "complexity": "complex",
        "signals": ["ambiguous_root_cause"],
        "evidence_summary": "Two plausible fixture paths require review.",
        "relevant_paths": ["calculator.py"],
        "open_questions": ["Which path preserves the invariant?"]
    }), encoding="utf-8")
    raise SystemExit(0)
if prompt.rfind("loopx_turn_advisor_v0") > prompt.rfind("loopx_turn_result_v0"):
    result = {
        "schema_version": "loopx_turn_advisor_v0",
        "turn_key": turn_key,
        "summary": "Inspect the boundary before changing the fixture.",
        "recommendations": ["Keep the edit bounded to the selected todo."],
        "risks": ["Do not overwrite unrelated files."],
        "validation_focus": ["Verify the exact marker value."]
    }
    if "resume" not in args:
        del result["validation_focus"]
    output_path.write_text(json.dumps(result), encoding="utf-8")
    raise SystemExit(0)
if "resume" not in args:
    output_path.write_text("The requested fixture work is complete.", encoding="utf-8")
    raise SystemExit(0)
print(json.dumps({
    "type": "item.completed",
    "item": {"type": "command_execution", "command": "update fixture"}
}), flush=True)
result = {
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
}
output_path.write_text("Receipt follows.\\n```json\\n" + json.dumps(result) + "\\n```", encoding="utf-8")
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable, log_path


def test_traex_cli_dialect_uses_prompt_schema_instead_of_provider_schema(
    tmp_path: Path,
) -> None:
    schema = tmp_path / "schema.json"
    output = tmp_path / "output.json"
    schema.write_text("{}", encoding="utf-8")

    assert _cli_dialect("/usr/local/bin/traex") == "traex"
    command = _codex_command(
        codex_bin="/usr/local/bin/traex",
        project=tmp_path,
        schema_path=schema,
        output_path=output,
        sandbox="workspace-write",
        model="DeepSeek-V4-Flash",
        session_id=None,
    )

    assert "--output-schema" not in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command

    resumed = _codex_command(
        codex_bin="/usr/local/bin/traex",
        project=tmp_path,
        schema_path=schema,
        output_path=output,
        sandbox="workspace-write",
        model="DeepSeek-V4-Flash",
        session_id="session-fixture",
    )
    assert resumed[resumed.index("--permission-mode") + 1] == "custom"
    assert 'approval_policy="never"' in resumed
    assert 'sandbox_mode="workspace-write"' in resumed


def test_traex_cli_repairs_invalid_final_receipt_in_same_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_traex(tmp_path)
    monkeypatch.setenv("FAKE_TRAEX_LOG", str(log_path))
    project = tmp_path / "project"
    project.mkdir()

    result = run_codex_cli_host(
        _request(),
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        model="DeepSeek-V4-Flash",
        timeout_seconds=5,
    )

    rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 2
    assert "resume" not in rows[0]["args"]
    assert "resume" in rows[1]["args"]
    assert "--output-schema" not in rows[0]["args"]
    assert "loopx_turn_result_v0" in rows[0]["prompt"]
    assert "Do not perform more workspace work" in rows[1]["prompt"]
    assert result["result_kind"] == "validated_progress"
    assert result["model_usage"]["executor"]["total_tokens"] == 300


def test_traex_cli_repairs_invalid_advisor_receipt_in_same_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_traex(tmp_path)
    monkeypatch.setenv("FAKE_TRAEX_LOG", str(log_path))
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="DeepSeek-V4-Flash",
        advisor_model="DeepSeek-V4-Pro",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 4
    assert "loopx_turn_advisor_v0" in rows[1]["prompt"]
    assert "resume" in rows[2]["args"]
    assert "Re-emit only the Advisor receipt" in rows[2]["prompt"]
    assert result["model_usage"]["advisor_applied"] is True
    assert result["model_usage"]["advisor"]["total_tokens"] == 300


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


def test_codex_cli_advisor_compacts_overlong_public_safe_guidance() -> None:
    turn_key = "sha256:" + "a" * 64
    advice = _normalize_advisor_result(
        {
            "schema_version": "loopx_turn_advisor_v0",
            "turn_key": turn_key,
            "summary": "Inspect the repository boundary. " * 20,
            "recommendations": ["Keep the patch focused."],
            "risks": ["Preserve existing behavior."],
            "validation_focus": ["Run the targeted regression test."],
        },
        turn_key=turn_key,
    )

    assert len(advice["summary"]) == 400
    assert advice["summary"].endswith("...")
    assert advice["recommendations"] == ["Keep the patch focused."]


def test_codex_cli_advisor_rejects_conditional_recommendations() -> None:
    turn_key = "sha256:" + "a" * 64

    with pytest.raises(BuiltInHostError):
        _normalize_advisor_result(
            {
                "schema_version": "loopx_turn_advisor_v0",
                "turn_key": turn_key,
                "summary": "The dependency boundary needs a decision.",
                "recommendations": [
                    "Optionally patch the dependency if its public contract matters."
                ],
                "risks": ["The caller-only patch leaves direct callers broken."],
                "validation_focus": ["Exercise the dependency directly."],
            },
            turn_key=turn_key,
        )


def test_codex_cli_advisor_context_extracts_large_source_and_direct_dependency(
    tmp_path: Path,
) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "header.py").write_text(
        "from .card import Card\n"
        + "padding = 0\n" * 2_000
        + "def fromstring(data):\n    return Card.fromstring(data)\n"
        + "tail = 0\n" * 2_000,
        encoding="utf-8",
    )
    (package / "card.py").write_text(
        "prefix = 0\n" * 2_000
        + "def fromstring(image):\n    return image.strip()\n"
        + "suffix = 0\n" * 2_000,
        encoding="utf-8",
    )
    request = _request()
    request["turn_envelope"]["action"]["recommended_action"] = (
        "Repair Header.fromstring bytes handling"
    )
    request["turn_envelope"]["boundary"] = {"write_scope": []}

    context = _advisor_workspace_context(
        request,
        project=tmp_path,
        complexity_checkpoint={"relevant_paths": ["pkg/header.py"]},
    )

    assert [item["path"] for item in context["files"]] == [
        "pkg/header.py",
        "pkg/card.py",
    ]
    assert "def fromstring(data)" in context["files"][0]["content"]
    assert "Card.fromstring(data)" in context["files"][0]["content"]
    assert "def fromstring(image)" in context["files"][1]["content"]
    assert sum(
        len(item["content"].encode("utf-8")) for item in context["files"]
    ) <= 24_000


def test_codex_cli_host_reports_compact_provider_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    project = tmp_path / "project"
    project.mkdir()

    result = run_codex_cli_host(
        _request(),
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        model="executor-fixture",
        timeout_seconds=5,
    )

    assert result["model_usage"] == {
        "schema_version": "loopx_turn_model_usage_v0",
        "mode": "direct",
        "advisor_applied": False,
        "executor": {
            "input_tokens": 120,
            "cache_tokens": 20,
            "output_tokens": 30,
            "reasoning_output_tokens": 10,
            "total_tokens": 150,
        },
        "total": {
            "input_tokens": 120,
            "cache_tokens": 20,
            "output_tokens": 30,
            "reasoning_output_tokens": 10,
            "total_tokens": 150,
        },
    }


def test_codex_cli_repairs_semantically_invalid_final_receipt_in_same_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_INVALID_FINAL_RESULT", "1")
    project = tmp_path / "project"
    project.mkdir()

    result = run_codex_cli_host(
        _request(),
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        timeout_seconds=5,
    )

    rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 2
    assert "resume" in rows[1]
    assert result["result_kind"] == "validated_progress"
    assert result["model_usage"]["executor"]["total_tokens"] == 300


def test_codex_cli_advisor_guides_cheaper_executor_and_aggregates_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    prompt_log = tmp_path / "codex-prompts.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_PROMPT_LOG", str(prompt_log))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_COMPLEXITY", "complex")
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(argv_rows) == 3
    assert argv_rows[0][argv_rows[0].index("--model") + 1] == "executor-fixture"
    assert argv_rows[1][argv_rows[1].index("--model") + 1] == "advisor-fixture"
    assert argv_rows[1][argv_rows[1].index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in argv_rows[1]
    advisor_project = Path(argv_rows[1][argv_rows[1].index("-C") + 1])
    assert advisor_project != project
    assert argv_rows[2][argv_rows[2].index("--model") + 1] == "executor-fixture"
    assert "resume" in argv_rows[2]
    prompts = [
        json.loads(line) for line in prompt_log.read_text(encoding="utf-8").splitlines()
    ]
    assert '"path":"calculator.py"' in prompts[1]
    assert "return a - b" in prompts[1]
    assert "Do not invoke workspace tools" in prompts[1]
    assert "directly called public dependency" in prompts[1]
    assert "counterpart explicitly named by the task" in prompts[1]
    assert "Inspect the boundary before changing the fixture." in prompts[2]
    assert result["model_usage"]["mode"] == "advisor"
    assert result["model_usage"]["advisor_applied"] is True
    assert result["model_usage"]["advisor"]["total_tokens"] == 48
    assert result["model_usage"]["executor"]["total_tokens"] == 300
    assert result["model_usage"]["total"]["total_tokens"] == 348
    assert result["model_usage"]["advice_digest"].startswith("sha256:")
    assert "summary" not in result["model_usage"]


def test_codex_cli_advisor_retries_executor_that_did_not_use_workspace_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    prompt_log = tmp_path / "codex-prompts.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_PROMPT_LOG", str(prompt_log))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_COMPLEXITY", "complex")
    monkeypatch.setenv("FAKE_CODEX_SKIP_FINAL_EXECUTION", "1")
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    prompts = [
        json.loads(line) for line in prompt_log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(prompts) == 4
    assert "EXECUTION RETRY" in prompts[3]
    assert "Turn request:" not in prompts[3]
    assert result["model_usage"]["advisor_applied"] is True
    assert result["model_usage"]["executor"]["total_tokens"] == 450


def test_codex_cli_advisor_skips_strong_model_for_simple_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    prompt_log = tmp_path / "codex-prompts.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_PROMPT_LOG", str(prompt_log))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row[row.index("--model") + 1] for row in argv_rows] == [
        "executor-fixture",
        "executor-fixture",
    ]
    assert "resume" not in argv_rows[0]
    assert "resume" in argv_rows[1]
    prompts = [
        json.loads(line) for line in prompt_log.read_text(encoding="utf-8").splitlines()
    ]
    assert "complexity checkpoint" in prompts[0]
    assert len(prompts) == 2
    assert "Now execute and validate the bounded Turn normally" in prompts[1]
    assert result["model_usage"]["mode"] == "direct"
    assert result["model_usage"]["advisor_applied"] is False
    assert result["model_usage"]["executor"]["total_tokens"] == 300
    assert result["model_usage"]["advisor_decision"] == {
        "schema_version": "loopx_turn_advisor_decision_v0",
        "decision": "skipped_simple",
        "signals": [],
        "checkpoint_digest": result["model_usage"]["advisor_decision"][
            "checkpoint_digest"
        ],
    }
    assert result["model_usage"]["advisor_decision"]["checkpoint_digest"].startswith(
        "sha256:"
    )


def test_codex_cli_advisor_escalates_simple_checkpoint_without_workspace_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_SKIP_CHECKPOINT_INSPECTION", "1")
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row[row.index("--model") + 1] for row in argv_rows] == [
        "executor-fixture",
        "advisor-fixture",
        "executor-fixture",
    ]
    assert result["model_usage"]["advisor_applied"] is True
    assert result["model_usage"]["advisor_decision"]["decision"] == (
        "applied_complexity"
    )
    assert result["model_usage"]["advisor_decision"]["signals"] == [
        "validation_uncertainty"
    ]
def test_codex_cli_advisor_reviews_complex_checkpoint_before_executor_resumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    prompt_log = tmp_path / "codex-prompts.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_PROMPT_LOG", str(prompt_log))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_COMPLEXITY", "complex")
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row[row.index("--model") + 1] for row in argv_rows] == [
        "executor-fixture",
        "advisor-fixture",
        "executor-fixture",
    ]
    assert "resume" in argv_rows[2]
    prompts = [
        json.loads(line) for line in prompt_log.read_text(encoding="utf-8").splitlines()
    ]
    assert "complexity checkpoint" in prompts[0]
    assert "Two plausible production paths remain" in prompts[1]
    assert "Which path preserves the invariant?" in prompts[1]
    assert "Inspect the boundary before changing the fixture." in prompts[2]
    assert result["model_usage"]["mode"] == "advisor"
    assert result["model_usage"]["advisor_applied"] is True
    assert result["model_usage"]["advisor"]["total_tokens"] == 48
    assert result["model_usage"]["executor"]["total_tokens"] == 300
    assert result["model_usage"]["total"]["total_tokens"] == 348
    assert result["model_usage"]["advisor_decision"]["decision"] == (
        "applied_complexity"
    )
    assert result["model_usage"]["advisor_decision"]["signals"] == [
        "ambiguous_root_cause"
    ]


def test_codex_cli_complex_advisor_failure_falls_back_to_executor_and_counts_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    prompt_log = tmp_path / "codex-prompts.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_PROMPT_LOG", str(prompt_log))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_COMPLEXITY", "complex")
    monkeypatch.setenv("FAKE_CODEX_FAIL_ADVISOR", "1")
    project = tmp_path / "project"
    project.mkdir()
    (project / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["calculator.py"]}

    result = run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row[row.index("--model") + 1] for row in argv_rows] == [
        "executor-fixture",
        "advisor-fixture",
        "executor-fixture",
    ]
    prompts = [
        json.loads(line) for line in prompt_log.read_text(encoding="utf-8").splitlines()
    ]
    assert "Advisor review was triggered but unavailable" in prompts[2]
    assert "rate_limited" in prompts[2]
    assert result["model_usage"]["mode"] == "direct"
    assert result["model_usage"]["advisor_applied"] is False
    assert result["model_usage"]["executor"]["total_tokens"] == 300
    assert result["model_usage"]["advisor_attempt"]["total_tokens"] == 48
    assert result["model_usage"]["total"]["total_tokens"] == 348
    assert result["model_usage"]["usage_complete"] is True
    assert result["model_usage"]["advisor_decision"]["decision"] == (
        "fallback_failure"
    )
    assert result["model_usage"]["advisor_decision"]["failure_category"] == (
        "rate_limited"
    )


def test_codex_cli_complexity_checkpoint_fails_before_advisor_when_usage_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    project = tmp_path / "project"
    project.mkdir()
    (project / "fixture.txt").write_text("fixture", encoding="utf-8")
    request = _request()
    request["turn_envelope"]["boundary"] = {"write_scope": ["fixture.txt"]}

    with pytest.raises(
        RuntimeError, match="codex_cli_complexity_checkpoint_usage_missing"
    ):
        run_codex_cli_host(
            request,
            runtime_root=tmp_path / "runtime",
            project=project,
            codex_bin=str(executable),
            model="executor-fixture",
            advisor_model="advisor-fixture",
            timeout_seconds=5,
        )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(argv_rows) == 1
    assert argv_rows[0][argv_rows[0].index("--model") + 1] == "executor-fixture"


def test_codex_cli_adaptive_mode_rejects_missing_final_executor_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_SKIP_RESUME_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_COMPLEXITY", "complex")
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(RuntimeError, match="codex_cli_executor_usage_missing"):
        run_codex_cli_host(
            _request(),
            runtime_root=tmp_path / "runtime",
            project=project,
            codex_bin=str(executable),
            model="executor-fixture",
            advisor_model="advisor-fixture",
            timeout_seconds=5,
        )

    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


def test_codex_cli_skips_advisor_when_bounded_context_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    project = tmp_path / "project"
    project.mkdir()

    result = run_codex_cli_host(
        _request(),
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    argv_rows = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(argv_rows) == 2
    assert all(
        row[row.index("--model") + 1] == "executor-fixture" for row in argv_rows
    )
    assert result["model_usage"]["mode"] == "direct"
    assert result["model_usage"]["advisor_applied"] is False
    assert result["model_usage"]["executor"]["total_tokens"] == 300


def test_codex_cli_advisor_context_rejects_unbounded_or_linked_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable, log_path = _fake_codex(tmp_path)
    prompt_log = tmp_path / "codex-prompts.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log_path))
    monkeypatch.setenv("FAKE_CODEX_PROMPT_LOG", str(prompt_log))
    monkeypatch.setenv("FAKE_CODEX_USAGE", "1")
    monkeypatch.setenv("FAKE_CODEX_COMPLEXITY", "complex")
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("must-not-enter-advisor-context", encoding="utf-8")
    (project / "linked.txt").symlink_to(outside)
    (project / "visible.txt").write_text("bounded-context", encoding="utf-8")
    request = _request()
    request["turn_envelope"]["boundary"] = {
        "write_scope": ["*.txt", "../outside.txt", "linked.txt", "visible.txt"]
    }

    run_codex_cli_host(
        request,
        runtime_root=tmp_path / "runtime",
        project=project,
        codex_bin=str(executable),
        sandbox="workspace-write",
        model="executor-fixture",
        advisor_model="advisor-fixture",
        advisor_timeout_seconds=5,
        timeout_seconds=5,
    )

    advisor_prompt = json.loads(
        prompt_log.read_text(encoding="utf-8").splitlines()[1]
    )
    assert "bounded-context" in advisor_prompt
    assert "must-not-enter-advisor-context" not in advisor_prompt


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


def test_public_e2e_smoke_runs_n_transactions_on_one_session() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "loopx-turn-codex-cli-e2e-smoke.py"),
            "--turn-count",
            "3",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["requested_turn_count"] == 3
    assert payload["observed_turn_count"] == 3
    assert payload["committed_turn_count"] == 3
    assert [turn["turn_number"] for turn in payload["turns"]] == [1, 2, 3]
    assert payload["session_actions"] == ["start_new", "resume", "resume"]
    assert payload["session_resumed"] is True
    assert all(turn["marker_valid"] for turn in payload["turns"])
    assert payload["marker_valid"] is True
    assert payload["quota_slot_spend_count"] == 3
    assert payload["replay_effects"] == {
        "host_invoked": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
        "state_written": False,
    }


def test_public_e2e_smoke_triggers_advisor_between_checkpoint_and_executor() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "loopx-turn-codex-cli-e2e-smoke.py"),
            "--codex-model",
            "executor-fixture",
            "--advisor-model",
            "advisor-fixture",
            "--case-id",
            "arithmetic-fix",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["advisor_mode"] is True
    assert payload["model_usage"]["mode"] == "advisor"
    assert payload["model_usage"]["advisor_applied"] is True
    assert payload["model_usage"]["advisor"]["total_tokens"] == 22
    assert payload["model_usage"]["executor"]["total_tokens"] == 70
    assert payload["model_usage"]["total"]["total_tokens"] == 92
    assert payload["model_usage"]["usage_complete"] is True
    assert payload["turns"][0]["model_usage"]["advisor_decision"]["decision"] == (
        "applied_complexity"
    )
    assert payload["marker_valid"] is True
    assert payload["validation_status"] == "passed"


def test_public_e2e_smoke_auto_selects_qualified_models() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "loopx-turn-codex-cli-e2e-smoke.py"),
            "--advisor-mode",
            "auto",
            "--case-id",
            "arithmetic-fix",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["model_selection"] == {
        "schema_version": "loopx_turn_model_selection_v0",
        "requested_mode": "auto",
        "profile_id": "experimental-codex-sol-luna-v1",
        "advisor_model": "gpt-5.6-sol",
        "executor_model": "gpt-5.6-luna",
        "selection_reason": "highest_priority_available_experimental_pair",
    }
    assert payload["model_usage"]["mode"] == "advisor"
    assert payload["model_usage"]["total"]["total_tokens"] == 92
    assert payload["validation_status"] == "passed"


def test_public_e2e_smoke_supports_an_independent_arithmetic_fix_case() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "loopx-turn-codex-cli-e2e-smoke.py"),
            "--case-id",
            "arithmetic-fix",
            "--codex-model",
            "executor-fixture",
            "--advisor-model",
            "advisor-fixture",
            "--advisor-timeout-seconds",
            "7",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["case_id"] == "arithmetic-fix"
    assert payload["case_valid"] is True
    assert payload["committed_turn_count"] == 1


def test_multi_file_docs_validator_accepts_semantically_equivalent_copy(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\nStatus: Stable\n", encoding="utf-8"
    )
    (docs / "index.md").write_text(
        "# Index\n\n- [Guide](./guide.md)\n", encoding="utf-8"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(root / "examples" / "fixtures" / "validate-loopx-turn-case.py"),
            "multi-file-docs",
            "",
        ],
        cwd=tmp_path,
        input="{}",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_advisor_qualification_compares_quality_and_total_tokens() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "qualify-loopx-turn-advisor-live.py"),
            "--fixture",
            "--baseline-model",
            "advisor-fixture",
            "--advisor-model",
            "advisor-fixture",
            "--executor-model",
            "executor-fixture",
            "--case-id",
            "arithmetic-fix",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "loopx_turn_advisor_qualification_v0"
    assert payload["real_codex_cli_invoked"] is False
    assert payload["quality_ok"] is True
    assert payload["baseline"]["total_tokens"] == 150
    assert payload["baseline"]["model"] == "advisor-fixture"
    assert payload["baseline"]["exit_code"] == 0
    assert payload["baseline"]["status"] == "committed"
    assert payload["baseline"]["validation_status"] == "passed"
    assert payload["advisor"]["model"] == "advisor-fixture"
    assert payload["advisor"]["executor_model"] == "executor-fixture"
    assert payload["advisor"]["exit_code"] == 0
    assert payload["advisor"]["status"] == "committed"
    assert payload["advisor"]["validation_status"] == "passed"
    assert payload["advisor"]["advisor_applied"] is True
    assert payload["advisor"]["advisor_tokens"] == 22
    assert payload["advisor"]["executor_tokens"] == 70
    assert payload["advisor"]["total_tokens"] == 92
    assert payload["token_delta"] == -58
    assert payload["token_reduction_ratio"] == 0.3867
    assert payload["token_reduced"] is True
    assert payload["raw_model_output_recorded"] is False


def test_advisor_qualification_requires_same_strong_model_for_both_arms() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "qualify-loopx-turn-advisor-live.py"),
            "--fixture",
            "--baseline-model",
            "different-strong-model",
            "--advisor-model",
            "advisor-fixture",
            "--executor-model",
            "executor-fixture",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "baseline and advisor models must be identical" in result.stderr
