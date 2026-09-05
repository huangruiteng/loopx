from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import sys
from argparse import Namespace
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

import loopx.capabilities.benchmark_toolkit.traex_evidence as traex_evidence_module
import loopx.cli_commands.benchmark_boundary as benchmark_boundary_module
import loopx.file_lock as file_lock
from loopx.capabilities.benchmark_toolkit import (
    BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION,
    BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION,
    BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_SCHEMA_VERSION,
    REQUIRED_RUNTIME_ATTESTATIONS,
    build_benchmark_integrity_qualification,
    build_traex_model_route_receipt,
    capture_traex_benchmark_evidence,
    convert_traex_events_to_atif,
    normalize_benchmark_model_route_receipt_v1,
)
from loopx.capabilities.benchmark_toolkit.route_receipt import (
    PublicIdentityKind,
    public_identity_digest,
)
from loopx.file_lock import LockAcquireTimeoutError, fcntl

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUND_ROUTE = {
    "run_id": "run-1",
    "arm_id": "loopx-domain-hint",
    "launch_binding_digest": "a" * 64,
    "authority": "trae-adapter",
}
BOUND_ROUTE_FLAGS = {
    "run_id": "--run-id",
    "arm_id": "--arm-id",
    "launch_binding_digest": "--launch-binding-digest",
    "authority": "--authority",
}


class _TestLockLease:
    def check(self) -> None:
        pass


def _failing_pair_writer(
    source: str,
    atif: str,
    route_receipt: str,
    second_write_reached: Any,
    release_failure: Any,
    result_queue: Any,
) -> None:
    real_atomic_write_json = traex_evidence_module.atomic_write_json
    route_path = Path(route_receipt)

    def fail_second_write(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        if path == route_path:
            second_write_reached.set()
            if not release_failure.wait(timeout=10):
                raise RuntimeError("test did not release the failing writer")
            raise OSError("injected route receipt publish failure")
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)

    traex_evidence_module.atomic_write_json = fail_second_write
    try:
        traex_evidence_module.capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )
    except traex_evidence_module.TraexEvidencePairPublishError as error:
        result_queue.put(
            {
                "classification": error.classification,
                "write_state": error.write_state,
                "rollback_verified": error.rollback_verified,
            }
        )
    except BaseException as error:  # pragma: no cover - child diagnostics
        result_queue.put({"unexpected": type(error).__name__, "message": str(error)})


def _successful_pair_writer(
    source: str,
    atif: str,
    route_receipt: str,
    lock_attempted: Any,
    first_write_reached: Any,
    result_queue: Any,
) -> None:
    real_atomic_write_json = traex_evidence_module.atomic_write_json
    real_exclusive_file_lock = traex_evidence_module.exclusive_file_lock

    def observe_first_write(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        first_write_reached.set()
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)

    @contextmanager
    def observe_lock_attempt(*args: Any, **kwargs: Any) -> Any:
        lock_attempted.set()
        with real_exclusive_file_lock(*args, **kwargs) as lock_path:
            yield lock_path

    traex_evidence_module.atomic_write_json = observe_first_write
    traex_evidence_module.exclusive_file_lock = observe_lock_attempt
    try:
        result = traex_evidence_module.capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.5",
            execute=True,
        )
        result_queue.put({"status": result["status"]})
    except BaseException as error:  # pragma: no cover - child diagnostics
        result_queue.put({"unexpected": type(error).__name__, "message": str(error)})


def _overlapping_pair_writer(
    source: str,
    atif: str,
    route_receipt: str,
    shared_lock_attempted: Any,
    first_write_reached: Any,
    result_queue: Any,
) -> None:
    real_atomic_write_json = traex_evidence_module.atomic_write_json
    real_exclusive_file_lock = traex_evidence_module.exclusive_file_lock
    shared_lock = traex_evidence_module._evidence_output_lock_target(
        traex_evidence_module._evidence_output_identity(Path(atif))
    )

    @contextmanager
    def observe_lock_attempt(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == shared_lock:
            shared_lock_attempted.set()
        with real_exclusive_file_lock(path, *args, **kwargs) as lock_path:
            yield lock_path

    def observe_first_write(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        first_write_reached.set()
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)

    traex_evidence_module.exclusive_file_lock = observe_lock_attempt
    traex_evidence_module.atomic_write_json = observe_first_write
    try:
        result = traex_evidence_module.capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.5",
            execute=True,
        )
        result_queue.put({"status": result["status"]})
    except BaseException as error:  # pragma: no cover - child diagnostics
        result_queue.put({"unexpected": type(error).__name__, "message": str(error)})


def _paused_pair_writer(
    atif: str,
    route_receipt: str,
    paused: Any,
    release: Any,
    result_queue: Any,
) -> None:
    real_atomic_write_json = traex_evidence_module.atomic_write_json
    writes = 0

    def pause_after_first_write(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        nonlocal writes
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)
        writes += 1
        if writes == 1:
            paused.set()
            if not release.wait(timeout=10):
                raise RuntimeError("test did not release the first writer")

    traex_evidence_module.atomic_write_json = pause_after_first_write
    try:
        traex_evidence_module._publish_evidence_pair(
            Path(atif),
            {"schema_version": "ATIF-v1.7", "writer": "first"},
            Path(route_receipt),
            {"writer": "first"},
        )
        result_queue.put({"writer": "first", "status": "success"})
    except traex_evidence_module.TraexEvidencePairPublishError as error:
        result_queue.put(
            {
                "writer": "first",
                "status": "error",
                "write_state": error.write_state,
            }
        )


def _replacement_pair_writer(atif: str, route_receipt: str, result_queue: Any) -> None:
    try:
        traex_evidence_module._publish_evidence_pair(
            Path(atif),
            {"schema_version": "ATIF-v1.7", "writer": "second"},
            Path(route_receipt),
            {"writer": "second"},
        )
        result_queue.put({"writer": "second", "status": "success"})
    except traex_evidence_module.TraexEvidencePairPublishError as error:
        result_queue.put(
            {
                "writer": "second",
                "status": "error",
                "write_state": error.write_state,
            }
        )


@contextmanager
def _activate_pinned_output(path: Path) -> Any:
    output = traex_evidence_module._pin_evidence_output(path)
    token = traex_evidence_module._ACTIVE_PINNED_OUTPUTS.set({output.identity: output})
    try:
        yield output
    finally:
        traex_evidence_module._ACTIVE_PINNED_OUTPUTS.reset(token)
        traex_evidence_module.os.close(output.parent_fd)


def _bound_route_args(binding: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        item
        for field, flag in BOUND_ROUTE_FLAGS.items()
        if field in binding
        for item in (flag, binding[field])
    )


def _run_traex_evidence_cli(
    *,
    source: Path,
    atif: Path,
    route_receipt: Path,
    route_source: Path | None = None,
    extra_args: tuple[str, ...] = (),
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(REPO_ROOT / "scripts/loopx"),
        "benchmark",
        "traex-evidence",
        "--source-jsonl",
        str(source),
    ]
    if route_source is not None:
        command.extend(("--route-source-jsonl", str(route_source)))
    command.extend(
        (
            "--atif-output",
            str(atif),
            "--route-receipt-output",
            str(route_receipt),
            "--requested-model",
            "GPT-5.4",
            *extra_args,
            "--format",
            "json",
        )
    )
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env={**os.environ, "LOOPX_PYTHON": sys.executable},
        text=True,
        capture_output=True,
        check=check,
    )


def _route_event(model: str, provider: str = "trae") -> dict[str, object]:
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "context": {
                "model": model,
                "modelProviderId": provider,
                "modelBackendVariant": "stable",
            },
        },
    }


def _v1_route_receipt(
    status: str, *, include_backend: bool = False
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_version": BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION,
        "runtime": "traex",
        "requested_model": "GPT-5.4",
        "requested_provider": "trae",
        "status": status,
        "raw_content_recorded": False,
        "input_path_recorded": False,
        **BOUND_ROUTE,
    }
    if status == "route_requested_not_runtime_audited":
        receipt.update(runtime_audited=False, matched=False, observed_route_count=0)
    elif status == "runtime_route_ambiguous":
        receipt.update(runtime_audited=True, matched=False, observed_route_count=2)
    elif status == "runtime_route_mismatch":
        receipt.update(
            runtime_audited=True,
            matched=False,
            observed_route_count=1,
            observed_model="GPT-5.5",
            observed_provider="trae",
        )
    elif status == "runtime_route_verified":
        receipt.update(
            runtime_audited=True,
            matched=True,
            observed_route_count=1,
            observed_model="gpt-5.4",
            observed_provider="TRAE",
        )
    else:
        raise AssertionError(f"unsupported test status: {status}")
    if include_backend:
        receipt["observed_backend_variant"] = "stable"
    return receipt


def _session_meta(thread_id: str = "thread-1") -> dict[str, object]:
    return {"type": "session_meta", "payload": {"id": thread_id}}


def _stdout_events(
    private_value: str = "private-task-value",
) -> list[dict[str, object]]:
    return [
        {"type": "thread.started", "thread_id": "thread-1"},
        {
            "type": "item.completed",
            "item": {"id": "warning", "type": "error", "message": "warning"},
        },
        {
            "type": "item.completed",
            "item": {
                "id": "command-1",
                "type": "command_execution",
                "command": f"printf {private_value}",
                "aggregated_output": private_value,
                "exit_code": 0,
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "file-1",
                "type": "file_change",
                "changes": [{"path": "private-file.txt", "kind": "add"}],
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {"id": "message-1", "type": "agent_message", "text": "done"},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1}},
    ]


def test_stdout_items_convert_to_private_atif() -> None:
    trajectory = convert_traex_events_to_atif(_stdout_events())

    assert trajectory["schema_version"] == "ATIF-v1.7"
    assert trajectory["steps"] == [
        {
            "step_id": "1",
            "source": "agent",
            "message": "",
            "tool_calls": [
                {
                    "function_name": "exec_command",
                    "arguments": {"cmd": "printf private-task-value"},
                }
            ],
            "observation": {"output": "private-task-value", "exit_code": 0},
        },
        {
            "step_id": "2",
            "source": "agent",
            "message": "",
            "tool_calls": [
                {
                    "function_name": "apply_patch",
                    "arguments": {
                        "changes": [{"path": "private-file.txt", "kind": "add"}]
                    },
                }
            ],
            "observation": {"status": "completed"},
        },
        {
            "step_id": "3",
            "source": "agent",
            "message": "done",
            "tool_calls": [],
        },
    ]


def test_converted_stdout_is_accepted_by_integrity_qualification() -> None:
    trajectory = convert_traex_events_to_atif(_stdout_events())
    attestation = {
        "schema_version": BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_SCHEMA_VERSION,
        "authority": "runner",
        "benchmark_id": "fixture@v0",
        "case_id": "case-1",
        **{field: True for field in REQUIRED_RUNTIME_ATTESTATIONS},
    }

    receipt = build_benchmark_integrity_qualification(
        trajectory=trajectory,
        runtime_attestation=attestation,
    )

    assert receipt["integrity_qualified"] is True
    assert receipt["score_claim_eligible"] is True


def test_archive_prefers_response_items_over_duplicate_history_mutations() -> None:
    call = {
        "type": "function_call",
        "name": "exec",
        "arguments": '{"cmd":"pwd"}',
        "call_id": "call-1",
    }
    output = {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "/workspace\n",
    }
    events = [
        {"type": "response_item", "payload": call},
        {"type": "response_item", "payload": output},
        {
            "type": "history_mutation",
            "payload": {"operation": "append", "items": [call, output]},
        },
    ]

    trajectory = convert_traex_events_to_atif(events)

    assert len(trajectory["steps"]) == 1
    assert trajectory["steps"][0]["tool_calls"][0] == {
        "function_name": "exec",
        "arguments": {"cmd": "pwd"},
    }


def test_archive_history_mutation_is_supported_when_response_items_are_absent() -> None:
    trajectory = convert_traex_events_to_atif(
        [
            {
                "type": "history_mutation",
                "payload": {
                    "operation": "append",
                    "items": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "done"}],
                        }
                    ],
                },
            }
        ]
    )

    assert trajectory["steps"][0]["message"] == "done"


def test_archive_custom_tool_pair_converts_without_losing_action() -> None:
    trajectory = convert_traex_events_to_atif(
        [
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "input": "*** Begin Patch\n*** End Patch",
                    "call_id": "call-custom-1",
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "call-custom-1",
                    "output": "Done!",
                },
            },
        ]
    )

    assert trajectory["steps"] == [
        {
            "step_id": "1",
            "source": "agent",
            "message": "",
            "tool_calls": [
                {
                    "function_name": "apply_patch",
                    "arguments": "*** Begin Patch\n*** End Patch",
                }
            ],
            "observation": "Done!",
        }
    ]


def test_archive_unknown_action_fails_closed_before_integrity_qualification() -> None:
    with pytest.raises(ValueError, match="traex_archive_action_unsupported"):
        convert_traex_events_to_atif(
            [
                {
                    "type": "response_item",
                    "payload": {"type": "computer_call", "id": "action-1"},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"text": "done"}],
                    },
                },
            ]
        )


def test_archive_malformed_response_item_fails_closed() -> None:
    with pytest.raises(ValueError, match="traex_archive_response_item_invalid"):
        convert_traex_events_to_atif(
            [
                {"type": "response_item", "payload": "unparsed-action"},
                {
                    "type": "history_mutation",
                    "payload": {
                        "operation": "append",
                        "items": [
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"text": "done"}],
                            }
                        ],
                    },
                },
            ]
        )


def test_archive_ignores_only_known_non_action_items() -> None:
    trajectory = convert_traex_events_to_atif(
        [
            {"type": "response_item", "payload": {"type": "reasoning"}},
            *[
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": role,
                        "content": [{"text": f"{role}-prompt"}],
                    },
                }
                for role in ("developer", "system", "user")
            ],
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"text": "done"}],
                },
            },
        ]
    )

    assert trajectory["steps"] == [
        {
            "step_id": "1",
            "source": "agent",
            "message": "done",
            "tool_calls": [],
        }
    ]


def test_archive_unknown_message_role_fails_closed() -> None:
    with pytest.raises(ValueError, match="traex_archive_message_role_unsupported"):
        convert_traex_events_to_atif(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "tool",
                        "content": [{"text": "hidden action"}],
                    },
                }
            ]
        )


def test_archive_history_replace_supersedes_prior_items() -> None:
    trajectory = convert_traex_events_to_atif(
        [
            {
                "type": "history_mutation",
                "payload": {
                    "operation": "append",
                    "items": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"text": "superseded"}],
                        }
                    ],
                },
            },
            {
                "type": "history_mutation",
                "payload": {
                    "operation": "replace",
                    "items": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"text": "current"}],
                        }
                    ],
                },
            },
        ]
    )

    assert [step["message"] for step in trajectory["steps"]] == ["current"]


def test_stdout_unknown_completed_action_fails_closed() -> None:
    with pytest.raises(ValueError, match="traex_stdout_action_unsupported"):
        convert_traex_events_to_atif(
            [
                {
                    "type": "item.completed",
                    "item": {"id": "unknown", "type": "mystery_action"},
                }
            ]
        )


@pytest.mark.parametrize(
    ("events", "status", "audited", "matched"),
    [
        ([], "route_requested_not_runtime_audited", False, False),
        ([_route_event("GPT-5.4")], "runtime_route_verified", True, True),
        ([_route_event("GPT-5.5")], "runtime_route_mismatch", True, False),
        (
            [_route_event("GPT-5.4"), _route_event("GPT-5.5")],
            "runtime_route_ambiguous",
            True,
            False,
        ),
    ],
)
def test_model_route_receipt_has_explicit_audit_state(
    events: list[dict[str, object]],
    status: str,
    audited: bool,
    matched: bool,
) -> None:
    receipt = build_traex_model_route_receipt(
        events,
        requested_model="GPT-5.4",
    )

    assert receipt["schema_version"] == BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION
    assert receipt["runtime"] == "traex"
    assert receipt["status"] == status
    assert receipt["runtime_audited"] is audited
    assert receipt["matched"] is matched
    assert receipt["raw_content_recorded"] is False
    assert receipt["input_path_recorded"] is False
    assert not set(BOUND_ROUTE) & set(receipt)
    assert ("observed_model" in receipt) is (len(events) == 1)
    assert ("observed_provider" in receipt) is (len(events) == 1)
    assert ("observed_backend_variant" in receipt) is (len(events) == 1)


@pytest.mark.parametrize(
    ("status", "include_backend"),
    [
        ("route_requested_not_runtime_audited", False),
        ("runtime_route_ambiguous", False),
        ("runtime_route_mismatch", False),
        ("runtime_route_mismatch", True),
        ("runtime_route_verified", False),
        ("runtime_route_verified", True),
    ],
)
def test_v1_route_receipt_normalizer_accepts_exact_state_matrix(
    status: str, include_backend: bool
) -> None:
    receipt = _v1_route_receipt(status, include_backend=include_backend)

    assert normalize_benchmark_model_route_receipt_v1(receipt) == receipt


@pytest.mark.parametrize(
    ("status", "updates"),
    [
        ("route_requested_not_runtime_audited", {"runtime_audited": True}),
        ("route_requested_not_runtime_audited", {"matched": True}),
        ("route_requested_not_runtime_audited", {"observed_route_count": 1}),
        (
            "route_requested_not_runtime_audited",
            {"observed_model": "GPT-5.4"},
        ),
        (
            "route_requested_not_runtime_audited",
            {"observed_provider": "trae"},
        ),
        (
            "route_requested_not_runtime_audited",
            {"observed_backend_variant": "stable"},
        ),
        ("runtime_route_ambiguous", {"runtime_audited": False}),
        ("runtime_route_ambiguous", {"matched": True}),
        ("runtime_route_ambiguous", {"observed_route_count": 0}),
        ("runtime_route_ambiguous", {"observed_route_count": 1}),
        ("runtime_route_ambiguous", {"observed_model": "GPT-5.4"}),
        ("runtime_route_ambiguous", {"observed_provider": "trae"}),
        (
            "runtime_route_ambiguous",
            {"observed_backend_variant": "stable"},
        ),
        ("runtime_route_mismatch", {"runtime_audited": False}),
        ("runtime_route_mismatch", {"matched": True}),
        ("runtime_route_mismatch", {"observed_route_count": 0}),
        ("runtime_route_mismatch", {"observed_route_count": 2}),
        ("runtime_route_mismatch", {"observed_model": None}),
        ("runtime_route_mismatch", {"observed_provider": None}),
        (
            "runtime_route_mismatch",
            {"observed_model": None, "observed_backend_variant": "stable"},
        ),
        (
            "runtime_route_mismatch",
            {"observed_provider": None, "observed_backend_variant": "stable"},
        ),
        ("runtime_route_mismatch", {"observed_model": "gpt-5.4"}),
        ("runtime_route_verified", {"runtime_audited": False}),
        ("runtime_route_verified", {"matched": False}),
        ("runtime_route_verified", {"observed_route_count": 0}),
        ("runtime_route_verified", {"observed_route_count": 2}),
        ("runtime_route_verified", {"observed_model": None}),
        ("runtime_route_verified", {"observed_provider": None}),
        (
            "runtime_route_verified",
            {"observed_model": None, "observed_backend_variant": "stable"},
        ),
        (
            "runtime_route_verified",
            {"observed_provider": None, "observed_backend_variant": "stable"},
        ),
        ("runtime_route_verified", {"observed_model": "GPT-5.5"}),
        ("runtime_route_verified", {"observed_provider": "other"}),
    ],
)
def test_v1_route_receipt_normalizer_rejects_invalid_state_matrix(
    status: str, updates: dict[str, object]
) -> None:
    receipt = _v1_route_receipt(status)
    for field, value in updates.items():
        if value is None:
            receipt.pop(field)
        else:
            receipt[field] = value

    with pytest.raises(ValueError, match="benchmark_model_route_state_inconsistent"):
        normalize_benchmark_model_route_receipt_v1(receipt)


def test_v1_route_receipt_normalizer_accepts_mismatch_in_either_route_part() -> None:
    receipt = _v1_route_receipt("runtime_route_mismatch", include_backend=True)
    receipt["observed_model"] = "GPT-5.4"
    receipt["observed_provider"] = "other-provider"

    assert normalize_benchmark_model_route_receipt_v1(receipt) == receipt


@pytest.mark.parametrize(
    ("runtime", "expected"),
    [("codex", "codex"), ("TraeX", "TraeX"), (" traex ", "traex")],
)
def test_v1_route_receipt_normalizer_accepts_provider_neutral_runtime(
    runtime: str, expected: str
) -> None:
    receipt = _v1_route_receipt("runtime_route_verified")
    receipt["runtime"] = runtime

    assert normalize_benchmark_model_route_receipt_v1(receipt)["runtime"] == expected


def test_capture_preview_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "stdout.jsonl"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    atif = tmp_path / "private" / "trajectory.json"
    receipt = tmp_path / "public" / "route.json"

    def unexpected_lock(*args: object, **kwargs: object) -> None:
        raise AssertionError("dry-run must not create or acquire the pair lock")

    monkeypatch.setattr(
        traex_evidence_module, "exclusive_file_lock", unexpected_lock, raising=False
    )

    result = capture_traex_benchmark_evidence(
        source_jsonl=source,
        atif_output=atif,
        route_receipt_output=receipt,
        requested_model="GPT-5.4",
    )

    assert result["status"] == "previewed"
    assert result["write_performed"] is False
    assert (
        result["model_route"]["schema_version"]
        == BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION
    )
    assert not atif.exists()
    assert not receipt.exists()
    assert not atif.parent.exists()
    assert not receipt.parent.exists()
    assert result["publication_contract"] == {
        "isolation": "ordered_per_output_lock_leases",
        "failure_recovery": "ownership_checked_rollback",
        "crash_atomic": False,
    }


@pytest.mark.parametrize(
    ("route_events", "status", "audited", "matched", "route_count"),
    [
        ([], "route_requested_not_runtime_audited", False, False, 0),
        ([_route_event("GPT-5.4")], "runtime_route_verified", True, True, 1),
        ([_route_event("GPT-5.5")], "runtime_route_mismatch", True, False, 1),
        (
            [_route_event("GPT-5.4"), _route_event("GPT-5.5")],
            "runtime_route_ambiguous",
            True,
            False,
            2,
        ),
    ],
)
def test_capture_builds_strict_bound_route_receipt_for_each_audit_state(
    tmp_path: Path,
    route_events: list[dict[str, object]],
    status: str,
    audited: bool,
    matched: bool,
    route_count: int,
) -> None:
    source = tmp_path / "stdout.jsonl"
    source.write_text(
        "\n".join(json.dumps(event) for event in [*_stdout_events(), *route_events])
        + "\n",
        encoding="utf-8",
    )

    result = capture_traex_benchmark_evidence(
        source_jsonl=source,
        atif_output=tmp_path / "trajectory.json",
        route_receipt_output=tmp_path / "receipt.json",
        requested_model="GPT-5.4",
        **BOUND_ROUTE,
    )

    route = result["model_route"]
    assert route["schema_version"] == BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
    assert route["status"] == status
    assert route["runtime_audited"] is audited
    assert route["matched"] is matched
    assert route["observed_route_count"] == route_count
    assert {field: route[field] for field in BOUND_ROUTE} == BOUND_ROUTE
    assert route["runtime"] == "traex"
    assert ("observed_model" in route) is (route_count == 1)
    assert ("observed_provider" in route) is (route_count == 1)
    assert ("observed_backend_variant" in route) is (route_count == 1)
    assert normalize_benchmark_model_route_receipt_v1(route) == route


@pytest.mark.parametrize("missing_field", tuple(BOUND_ROUTE))
def test_capture_rejects_partial_bound_route_before_reading_source(
    tmp_path: Path, missing_field: str
) -> None:
    binding = dict(BOUND_ROUTE)
    binding.pop(missing_field)
    atif = tmp_path / "trajectory.json"
    receipt = tmp_path / "receipt.json"

    with pytest.raises(ValueError, match="benchmark_model_route_binding_incomplete"):
        capture_traex_benchmark_evidence(
            source_jsonl=tmp_path / "missing-private-source.jsonl",
            atif_output=atif,
            route_receipt_output=receipt,
            requested_model="GPT-5.4",
            **binding,
        )

    assert not atif.exists()
    assert not receipt.exists()


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        (
            "launch_binding_digest",
            "not-a-digest",
            "benchmark_model_route_launch_binding_digest_invalid",
        ),
        ("run_id", "not/a/token", "run_id must be a compact public-safe token"),
        ("arm_id", "not an arm", "arm_id must be a compact public-safe token"),
        (
            "authority",
            "not an authority",
            "authority must be a compact public-safe token",
        ),
    ],
)
def test_capture_rejects_invalid_bound_route_before_reading_source(
    tmp_path: Path, field: str, value: str, error: str
) -> None:
    binding = dict(BOUND_ROUTE)
    binding[field] = value

    with pytest.raises(ValueError, match=error):
        capture_traex_benchmark_evidence(
            source_jsonl=tmp_path / "missing-private-source.jsonl",
            atif_output=tmp_path / "trajectory.json",
            route_receipt_output=tmp_path / "receipt.json",
            requested_model="GPT-5.4",
            **binding,
        )


@pytest.mark.parametrize(
    "field", ("requested_model", "requested_provider", *BOUND_ROUTE)
)
@pytest.mark.parametrize("value", (True, 7))
def test_route_binding_rejects_non_string_identity_fields(
    field: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "requested_model": "GPT-5.4",
        "requested_provider": "trae",
        **BOUND_ROUTE,
    }
    arguments[field] = value

    with pytest.raises(TypeError):
        build_traex_model_route_receipt([], **arguments)


def test_output_lock_identities_are_ordered_opaque_and_overlap_aware(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "shared-secret-name" / "trajectory.json"
    second = tmp_path / "customer-secret-name" / "route.json"
    third = tmp_path / "other-secret-name" / "route.json"

    first_pair = traex_evidence_module._ordered_evidence_lock_targets((shared, second))
    reversed_pair = traex_evidence_module._ordered_evidence_lock_targets(
        (second, shared)
    )
    overlapping_pair = traex_evidence_module._ordered_evidence_lock_targets(
        (shared, third)
    )

    assert first_pair == reversed_pair
    assert len(set(first_pair) & set(overlapping_pair)) == 1
    rendered = " ".join(str(path) for path in (*first_pair, *overlapping_pair))
    assert shared.name not in rendered
    assert second.name not in rendered
    assert "shared-secret-name" not in rendered
    assert "customer-secret-name" not in rendered


def test_output_lock_identity_stays_stable_when_symlink_is_replaced(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("target bytes\n", encoding="utf-8")
    other_target = tmp_path / "other-target.json"
    other_target.write_text("other target bytes\n", encoding="utf-8")
    output = tmp_path / "output.json"
    output.symlink_to(target.name)

    symlink_identity = traex_evidence_module._evidence_output_identity(output)
    symlink_lock = traex_evidence_module._evidence_output_lock_target(symlink_identity)
    output.unlink()
    output.symlink_to(other_target.name)
    retargeted_identity = traex_evidence_module._evidence_output_identity(output)
    retargeted_lock = traex_evidence_module._evidence_output_lock_target(
        retargeted_identity
    )
    output.unlink()
    output.write_text("regular bytes\n", encoding="utf-8")
    regular_identity = traex_evidence_module._evidence_output_identity(output)
    regular_lock = traex_evidence_module._evidence_output_lock_target(regular_identity)

    assert symlink_identity == retargeted_identity == regular_identity
    assert symlink_lock == retargeted_lock == regular_lock
    expected_identity = os.path.normcase(os.path.abspath(os.fspath(output)))
    if traex_evidence_module._directory_supports_case_insensitive_aliases(
        output.parent
    ):
        expected_identity = expected_identity.casefold()
    assert symlink_identity == expected_identity
    assert symlink_identity != os.path.normcase(os.path.abspath(os.fspath(target)))


def test_output_lock_identity_collapses_lexical_aliases(tmp_path: Path) -> None:
    output = tmp_path / "existing" / "trajectory.json"
    alias_marker = tmp_path / "alias-marker"
    output.parent.mkdir()
    alias_marker.mkdir()
    alias = alias_marker / ".." / "existing" / "trajectory.json"

    output_identity = traex_evidence_module._evidence_output_identity(output)
    alias_identity = traex_evidence_module._evidence_output_identity(alias)

    assert output_identity == alias_identity
    assert traex_evidence_module._ordered_evidence_lock_targets((output,)) == (
        traex_evidence_module._evidence_output_lock_target(alias_identity),
    )


def test_output_lock_identity_collapses_case_insensitive_aliases(
    tmp_path: Path,
) -> None:
    output = tmp_path / "CaseDir" / "Trajectory.JSON"
    output.parent.mkdir()
    alias = Path(os.fspath(output).swapcase())
    try:
        if not alias.parent.samefile(output.parent):
            pytest.skip("case-insensitive aliases unavailable on this filesystem")
    except OSError:
        pytest.skip("case-insensitive aliases unavailable on this filesystem")

    output_identity = traex_evidence_module._evidence_output_identity(output)
    alias_identity = traex_evidence_module._evidence_output_identity(alias)

    assert output_identity == alias_identity
    assert traex_evidence_module._paths_overlap(output, alias) is True
    assert traex_evidence_module._ordered_evidence_lock_targets((output,)) == (
        traex_evidence_module._evidence_output_lock_target(alias_identity),
    )


def test_output_lock_identity_stays_stable_for_missing_case_aliases(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "CaseDir"
    parent.mkdir()
    alias_parent = Path(os.fspath(parent).swapcase())
    try:
        if not alias_parent.samefile(parent):
            pytest.skip("case-insensitive aliases unavailable on this filesystem")
    except OSError:
        pytest.skip("case-insensitive aliases unavailable on this filesystem")

    output = parent / "Trajectory.JSON"
    alias = alias_parent / "tRAJECTORY.json"

    assert traex_evidence_module._evidence_output_identity(output) == (
        traex_evidence_module._evidence_output_identity(alias)
    )
    assert traex_evidence_module._paths_overlap(output, alias) is True


def test_capture_rejects_case_insensitive_input_output_overlap(
    tmp_path: Path,
) -> None:
    source = tmp_path / "CaseDir" / "Source.JSONL"
    source.parent.mkdir()
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    atif_alias = Path(os.fspath(source).swapcase())
    try:
        if not atif_alias.samefile(source):
            pytest.skip("case-insensitive aliases unavailable on this filesystem")
    except OSError:
        pytest.skip("case-insensitive aliases unavailable on this filesystem")

    with pytest.raises(ValueError, match="traex_evidence_paths_overlap"):
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif_alias,
            route_receipt_output=tmp_path / "route.json",
            requested_model="GPT-5.4",
        )


@pytest.mark.parametrize("symlink_output", ("atif", "route_receipt"))
@pytest.mark.parametrize("target_exists", (True, False), ids=("symlink", "dangling"))
def test_capture_rejects_either_symlink_output_before_publication_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    symlink_output: str,
    target_exists: bool,
) -> None:
    target = tmp_path / "target.json"
    if target_exists:
        target.write_bytes(b"target bytes\n")
    link = tmp_path / "output-link.json"
    link.symlink_to(target.name)
    other_output = tmp_path / "new-output-parent" / "other.json"
    atif = link if symlink_output == "atif" else other_output
    route_receipt = link if symlink_output == "route_receipt" else other_output
    original_link = os.readlink(link)
    original_target = target.read_bytes() if target_exists else None
    calls: list[str] = []

    @contextmanager
    def unexpected_lock(*args: object, **kwargs: object) -> Any:
        calls.append("lock")
        yield  # pragma: no cover

    def unexpected_snapshot(*args: object, **kwargs: object) -> object:
        calls.append("snapshot")
        raise AssertionError("snapshot must not run for a symlink output")

    def unexpected_write(*args: object, **kwargs: object) -> None:
        calls.append("write")
        raise AssertionError("write must not run for a symlink output")

    monkeypatch.setattr(traex_evidence_module, "exclusive_file_lock", unexpected_lock)
    monkeypatch.setattr(
        traex_evidence_module, "_snapshot_evidence_file", unexpected_snapshot
    )
    monkeypatch.setattr(traex_evidence_module, "atomic_write_json", unexpected_write)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=tmp_path / "missing-source.jsonl",
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )

    error = error_info.value
    assert error.classification == "output_symlink_rejected"
    assert error.write_state == "no_write_output_symlink_rejected"
    assert error.rollback_verified is None
    assert error.failure_metadata == {}
    assert calls == []
    assert link.is_symlink()
    assert os.readlink(link) == original_link
    assert target.exists() is target_exists
    if target_exists:
        assert target.read_bytes() == original_target
    assert not other_output.exists()
    assert not other_output.parent.exists()

    emitted = benchmark_boundary_module._traex_evidence_publish_failure(
        error, bound_requested=False
    )
    assert emitted["status"] == "output_symlink_rejected"
    assert emitted["write_state"] == "no_write_output_symlink_rejected"
    assert emitted["private_atif_written"] is False
    assert emitted["route_receipt_written"] is False
    assert emitted["write_performed"] is False
    assert str(tmp_path) not in json.dumps(emitted)


@pytest.mark.parametrize("symlink_output", ("atif", "route_receipt"))
@pytest.mark.parametrize(
    ("symlink_depth", "target_exists"),
    (("parent", True), ("parent", False), ("nested", True), ("nested", False)),
    ids=(
        "parent-symlink",
        "parent-dangling",
        "nested-symlink",
        "nested-dangling",
    ),
)
def test_capture_rejects_output_ancestor_symlink_before_publication_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    symlink_output: str,
    symlink_depth: str,
    target_exists: bool,
) -> None:
    target = tmp_path / "target-parent"
    if target_exists:
        target.mkdir()
    link = tmp_path / "linked-parent"
    link.symlink_to(target.name, target_is_directory=True)
    linked_output = (
        link / "trajectory.json"
        if symlink_depth == "parent"
        else link / "nested" / "trajectory.json"
    )
    other_output = tmp_path / "new-output-parent" / "other.json"
    atif = linked_output if symlink_output == "atif" else other_output
    route_receipt = linked_output if symlink_output == "route_receipt" else other_output
    calls: list[str] = []

    @contextmanager
    def unexpected_lock(*args: object, **kwargs: object) -> Any:
        calls.append("lock")
        yield  # pragma: no cover

    def unexpected_snapshot(*args: object, **kwargs: object) -> object:
        calls.append("snapshot")
        raise AssertionError("snapshot must not run for an ancestor symlink")

    def unexpected_write(*args: object, **kwargs: object) -> None:
        calls.append("write")
        raise AssertionError("write must not run for an ancestor symlink")

    monkeypatch.setattr(traex_evidence_module, "exclusive_file_lock", unexpected_lock)
    monkeypatch.setattr(
        traex_evidence_module, "_snapshot_evidence_file", unexpected_snapshot
    )
    monkeypatch.setattr(traex_evidence_module, "atomic_write_json", unexpected_write)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=tmp_path / "missing-source.jsonl",
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )

    error = error_info.value
    assert error.classification == "output_ancestor_symlink_rejected"
    assert error.write_state == "no_write_output_ancestor_symlink_rejected"
    assert error.rollback_verified is None
    assert error.failure_metadata == {}
    assert calls == []
    assert link.is_symlink()
    assert target.exists() is target_exists
    assert not other_output.exists()
    assert not other_output.parent.exists()

    emitted = benchmark_boundary_module._traex_evidence_publish_failure(
        error, bound_requested=False
    )
    assert emitted["status"] == "output_ancestor_symlink_rejected"
    assert emitted["write_state"] == "no_write_output_ancestor_symlink_rejected"
    assert emitted["private_atif_written"] is False
    assert emitted["route_receipt_written"] is False
    assert emitted["write_performed"] is False
    assert str(tmp_path) not in json.dumps(emitted)


def test_pair_publisher_rechecks_symlinks_before_lock_or_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"target bytes\n")
    atif = tmp_path / "trajectory.json"
    atif.symlink_to(target.name)
    route_receipt = tmp_path / "route.json"
    calls: list[str] = []

    @contextmanager
    def unexpected_lock(*args: object, **kwargs: object) -> Any:
        calls.append("lock")
        yield  # pragma: no cover

    def unexpected_snapshot(*args: object, **kwargs: object) -> object:
        calls.append("snapshot")
        raise AssertionError("snapshot must not run for a symlink output")

    def unexpected_write(*args: object, **kwargs: object) -> None:
        calls.append("write")
        raise AssertionError("write must not run for a symlink output")

    monkeypatch.setattr(traex_evidence_module, "exclusive_file_lock", unexpected_lock)
    monkeypatch.setattr(
        traex_evidence_module, "_snapshot_evidence_file", unexpected_snapshot
    )
    monkeypatch.setattr(traex_evidence_module, "atomic_write_json", unexpected_write)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif, {"schema_version": "ATIF-v1.7"}, route_receipt, {}
        )

    assert error_info.value.classification == "output_symlink_rejected"
    assert error_info.value.write_state == "no_write_output_symlink_rejected"
    assert calls == []
    assert atif.is_symlink()
    assert target.read_bytes() == b"target bytes\n"
    assert not route_receipt.exists()


def test_pair_publisher_rechecks_symlinks_after_acquiring_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"target bytes\n")
    atif = tmp_path / "trajectory.json"
    route_receipt = tmp_path / "route.json"
    lock_count = 0
    snapshot_called = False

    @contextmanager
    def replace_output_after_final_lock(*args: object, **kwargs: object) -> Any:
        nonlocal lock_count
        lock_count += 1
        if lock_count == 2:
            atif.symlink_to(target.name)
        yield _TestLockLease()

    def unexpected_snapshot(*args: object, **kwargs: object) -> object:
        nonlocal snapshot_called
        snapshot_called = True
        raise AssertionError("snapshot must not run after a symlink race")

    monkeypatch.setattr(
        traex_evidence_module, "exclusive_file_lock", replace_output_after_final_lock
    )
    monkeypatch.setattr(
        traex_evidence_module, "_snapshot_evidence_file", unexpected_snapshot
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif, {"schema_version": "ATIF-v1.7"}, route_receipt, {}
        )

    assert error_info.value.classification == "output_symlink_rejected"
    assert error_info.value.write_state == "no_write_output_symlink_rejected"
    assert lock_count == 2
    assert snapshot_called is False
    assert atif.is_symlink()
    assert target.read_bytes() == b"target bytes\n"
    assert not route_receipt.exists()


@pytest.mark.parametrize("raced_output", ("atif", "route_receipt"))
def test_pair_publisher_rechecks_ancestor_symlinks_after_acquiring_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raced_output: str
) -> None:
    output_parent = tmp_path / raced_output
    output_parent.mkdir()
    target_parent = tmp_path / "target-parent"
    target_parent.mkdir()
    other_parent = tmp_path / "other"
    atif = (
        output_parent / "trajectory.json"
        if raced_output == "atif"
        else other_parent / "trajectory.json"
    )
    route_receipt = (
        output_parent / "route.json"
        if raced_output == "route_receipt"
        else other_parent / "route.json"
    )
    lock_count = 0
    snapshot_called = False

    @contextmanager
    def replace_parent_after_final_lock(*args: object, **kwargs: object) -> Any:
        nonlocal lock_count
        lock_count += 1
        if lock_count == 2:
            output_parent.rmdir()
            output_parent.symlink_to(target_parent.name, target_is_directory=True)
        yield _TestLockLease()

    def unexpected_snapshot(*args: object, **kwargs: object) -> object:
        nonlocal snapshot_called
        snapshot_called = True
        raise AssertionError("snapshot must not run after an ancestor symlink race")

    monkeypatch.setattr(
        traex_evidence_module, "exclusive_file_lock", replace_parent_after_final_lock
    )
    monkeypatch.setattr(
        traex_evidence_module, "_snapshot_evidence_file", unexpected_snapshot
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif, {"schema_version": "ATIF-v1.7"}, route_receipt, {}
        )

    assert error_info.value.classification == "output_ancestor_symlink_rejected"
    assert error_info.value.write_state == "no_write_output_ancestor_symlink_rejected"
    assert lock_count == 2
    assert snapshot_called is False
    assert output_parent.is_symlink()
    assert not atif.exists()
    assert not route_receipt.exists()
    assert not other_parent.exists()


@pytest.mark.parametrize("swap_point", ("after_first_snapshot", "before_first_replace"))
@pytest.mark.parametrize("raced_output", ("atif", "route_receipt"))
def test_pair_publisher_never_writes_through_post_lock_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_point: str,
    raced_output: str,
) -> None:
    first_parent = tmp_path / "private"
    second_parent = tmp_path / "public"
    first_parent.mkdir()
    second_parent.mkdir()
    target_parent = tmp_path / "symlink-target"
    target_parent.mkdir()
    atif = first_parent / "trajectory.json"
    route_receipt = second_parent / "route.json"
    raced_parent = first_parent if raced_output == "atif" else second_parent
    raced_name = atif.name if raced_output == "atif" else route_receipt.name
    detached_parent = tmp_path / f"detached-{raced_output}"
    snapshots = 0
    writes = 0
    real_snapshot = traex_evidence_module._snapshot_evidence_file
    real_write = traex_evidence_module.atomic_write_json

    def swap_parent() -> None:
        raced_parent.rename(detached_parent)
        raced_parent.symlink_to(target_parent.name, target_is_directory=True)

    def snapshot_and_maybe_swap(path: Path) -> object:
        nonlocal snapshots
        snapshot = real_snapshot(path)
        snapshots += 1
        if swap_point == "after_first_snapshot" and snapshots == 1:
            swap_parent()
        return snapshot

    def write_and_maybe_swap(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        nonlocal writes
        writes += 1
        if swap_point == "before_first_replace" and writes == 1:
            swap_parent()
        real_write(path, payload, preserve_mode=preserve_mode)

    monkeypatch.setattr(
        traex_evidence_module, "_snapshot_evidence_file", snapshot_and_maybe_swap
    )
    monkeypatch.setattr(
        traex_evidence_module, "atomic_write_json", write_and_maybe_swap
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif, {"schema_version": "ATIF-v1.7"}, route_receipt, {}
        )

    error = error_info.value
    assert error.classification == "output_ancestor_symlink_rejected"
    if swap_point == "after_first_snapshot":
        assert error.write_state == "no_write_output_ancestor_symlink_rejected"
        assert error.rollback_verified is None
    else:
        assert error.write_state == "unknown"
        assert error.rollback_verified is False
    assert raced_parent.is_symlink()
    assert not (target_parent / raced_name).exists()
    assert not (detached_parent / raced_name).exists()
    assert not atif.exists()
    assert not route_receipt.exists()


def test_pair_publisher_rolls_back_when_final_readback_mismatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    atif.parent.mkdir()
    route_receipt.parent.mkdir()
    atif.write_text('{"old": "atif"}\n', encoding="utf-8")
    route_receipt.write_text('{"old": "route"}\n', encoding="utf-8")
    original_atif = atif.read_bytes()
    original_route = route_receipt.read_bytes()
    real_match = traex_evidence_module._evidence_file_matches_snapshot
    readbacks = 0

    def mismatch_first_published_readback(path: Path, snapshot: object) -> bool:
        nonlocal readbacks
        readbacks += 1
        if readbacks == 1:
            return False
        return real_match(path, snapshot)  # type: ignore[arg-type]

    monkeypatch.setattr(
        traex_evidence_module,
        "_evidence_file_matches_snapshot",
        mismatch_first_published_readback,
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif, {"schema_version": "ATIF-v1.7"}, route_receipt, {}
        )

    error = error_info.value
    assert error.classification == "publish_failed"
    assert error.write_state == "rolled_back_verified"
    assert error.rollback_verified is True
    assert atif.read_bytes() == original_atif
    assert route_receipt.read_bytes() == original_route


def test_pin_evidence_output_closes_parent_fd_when_fstat_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evidence" / "route.json"
    output.parent.mkdir()
    opened_fd = traex_evidence_module.os.open(
        output.parent, traex_evidence_module._directory_open_flags()
    )
    real_fstat = traex_evidence_module.os.fstat
    real_close = traex_evidence_module.os.close
    closed_fds: list[int] = []

    def return_open_parent(path: Path, *, create: bool) -> int:
        assert path == output
        assert create is True
        return opened_fd

    def fail_fstat(descriptor: int) -> object:
        if descriptor == opened_fd:
            raise OSError("injected-fstat-failure")
        return real_fstat(descriptor)

    def record_close(descriptor: int) -> None:
        closed_fds.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(
        traex_evidence_module, "_open_output_parent", return_open_parent
    )
    monkeypatch.setattr(traex_evidence_module.os, "fstat", fail_fstat)
    monkeypatch.setattr(traex_evidence_module.os, "close", record_close)

    with pytest.raises(OSError, match="injected-fstat-failure"):
        traex_evidence_module._pin_evidence_output(output)

    assert closed_fds == [opened_fd]


def test_snapshot_evidence_file_closes_raw_fd_when_fdopen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "trajectory.json"
    output.write_text("trajectory bytes\n", encoding="utf-8")
    real_open = traex_evidence_module.os.open
    real_close = traex_evidence_module.os.close
    opened_fds: list[int] = []
    closed_fds: list[int] = []

    def record_open(*args: object, **kwargs: object) -> int:
        descriptor = real_open(*args, **kwargs)
        opened_fds.append(descriptor)
        return descriptor

    def fail_fdopen(*args: object, **kwargs: object) -> object:
        raise OSError("injected-fdopen-failure")

    def record_close(descriptor: int) -> None:
        closed_fds.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(traex_evidence_module.os, "open", record_open)
    monkeypatch.setattr(traex_evidence_module.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(traex_evidence_module.os, "close", record_close)

    with pytest.raises(OSError, match="injected-fdopen-failure"):
        traex_evidence_module._snapshot_evidence_file(output)

    assert len(opened_fds) == 1
    assert closed_fds == opened_fds


def test_pinned_snapshot_closes_raw_fd_when_fdopen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "trajectory.json"
    output.write_text("trajectory bytes\n", encoding="utf-8")
    real_open_pinned_output = traex_evidence_module._open_pinned_output
    real_close = traex_evidence_module.os.close
    opened_descriptors: set[int] = set()
    closed_descriptors: set[int] = set()

    def record_open_pinned_output(
        output_info: Any, *, flags: int, mode: int = 0o600
    ) -> int:
        descriptor = real_open_pinned_output(output_info, flags=flags, mode=mode)
        opened_descriptors.add(descriptor)
        return descriptor

    def fail_fdopen(*args: object, **kwargs: object) -> object:
        raise OSError("injected-fdopen-failure")

    def record_close(descriptor: int) -> None:
        if descriptor in opened_descriptors:
            closed_descriptors.add(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(
        traex_evidence_module, "_open_pinned_output", record_open_pinned_output
    )
    monkeypatch.setattr(traex_evidence_module.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(traex_evidence_module.os, "close", record_close)

    with _activate_pinned_output(output):
        with pytest.raises(OSError, match="injected-fdopen-failure"):
            traex_evidence_module._snapshot_evidence_file(output)

    assert len(opened_descriptors) == 1
    assert closed_descriptors == opened_descriptors


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO support required")
@pytest.mark.parametrize("pinned", (False, True), ids=("plain", "pinned"))
def test_snapshot_evidence_file_rejects_fifo_without_blocking(
    tmp_path: Path, pinned: bool
) -> None:
    output = tmp_path / "trajectory.fifo"
    os.mkfifo(output)

    if pinned:
        with _activate_pinned_output(output):
            with pytest.raises(OSError, match="traex_evidence_output_not_regular"):
                traex_evidence_module._snapshot_evidence_file(output)
        return

    with pytest.raises(OSError, match="traex_evidence_output_not_regular"):
        traex_evidence_module._snapshot_evidence_file(output)


def test_pinned_snapshot_rejects_final_name_replaced_after_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "trajectory.json"
    output.write_text("original bytes\n", encoding="utf-8")
    displaced = tmp_path / "trajectory.displaced"
    real_read_opened_regular_file = traex_evidence_module._read_opened_regular_file

    def replace_final_name_after_read(descriptor: int) -> tuple[bytes, os.stat_result]:
        result = real_read_opened_regular_file(descriptor)
        output.rename(displaced)
        output.write_text("replacement bytes\n", encoding="utf-8")
        return result

    monkeypatch.setattr(
        traex_evidence_module,
        "_read_opened_regular_file",
        replace_final_name_after_read,
    )

    with _activate_pinned_output(output):
        with pytest.raises(
            OSError, match="traex_evidence_output_replaced_during_readback"
        ):
            traex_evidence_module._snapshot_evidence_file(output)

    assert displaced.read_text(encoding="utf-8") == "original bytes\n"
    assert output.read_text(encoding="utf-8") == "replacement bytes\n"


def test_capture_rejects_unbound_route_source(tmp_path: Path) -> None:
    source = tmp_path / "stdout.jsonl"
    route_source = tmp_path / "route.jsonl"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    route_source.write_text(
        "\n".join(
            json.dumps(event)
            for event in [_session_meta("other-thread"), _route_event("GPT-5.4")]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="traex_route_source_identity_mismatch"):
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            route_source_jsonl=route_source,
            atif_output=tmp_path / "trajectory.json",
            route_receipt_output=tmp_path / "receipt.json",
            requested_model="GPT-5.4",
        )


@pytest.mark.parametrize(
    ("previous_atif", "previous_route_receipt"),
    [
        (b"old private ATIF bytes\n", b"old public route bytes\n"),
        (None, None),
        (b"old private ATIF bytes\n", None),
        (None, b"old public route bytes\n"),
    ],
)
def test_capture_rolls_back_pair_when_route_receipt_publish_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    previous_atif: bytes | None,
    previous_route_receipt: bytes | None,
) -> None:
    source = tmp_path / "source.jsonl"
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    previous_modes = {atif: 0o640, route_receipt: 0o604}
    observed_previous_modes: dict[Path, int] = {}
    for path, previous in (
        (atif, previous_atif),
        (route_receipt, previous_route_receipt),
    ):
        if previous is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(previous)
            path.chmod(previous_modes[path])
            observed_previous_modes[path] = path.stat().st_mode & 0o777

    real_atomic_write_json = traex_evidence_module.atomic_write_json
    publish_paths: list[Path] = []

    def fail_route_receipt_publish(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        publish_paths.append(path)
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)
        if path == route_receipt:
            assert atif.read_bytes() != previous_atif
            assert route_receipt.read_bytes() != previous_route_receipt
            raise OSError("injected route receipt publish failure")

    monkeypatch.setattr(
        traex_evidence_module, "atomic_write_json", fail_route_receipt_publish
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )

    assert publish_paths == [atif, route_receipt]
    for path, previous in (
        (atif, previous_atif),
        (route_receipt, previous_route_receipt),
    ):
        if previous is None:
            assert not path.exists()
        else:
            assert path.read_bytes() == previous
            assert path.stat().st_mode & 0o777 == observed_previous_modes[path]
    assert error_info.value.classification == "publish_failed"
    assert error_info.value.write_state == "rolled_back_verified"
    assert error_info.value.rollback_verified is True


def test_capture_reports_unknown_state_when_rollback_cannot_be_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jsonl"
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    real_atomic_write_json = traex_evidence_module.atomic_write_json

    def fail_route_receipt_publish(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)
        if path == route_receipt:
            raise OSError("injected publish failure")

    def fail_rollback(*args: object, **kwargs: object) -> None:
        raise OSError("injected rollback failure")

    monkeypatch.setattr(
        traex_evidence_module, "atomic_write_json", fail_route_receipt_publish
    )
    monkeypatch.setattr(traex_evidence_module, "_restore_evidence_file", fail_rollback)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            **BOUND_ROUTE,
            execute=True,
        )

    assert error_info.value.classification == "publish_failed"
    assert error_info.value.write_state == "unknown"
    assert error_info.value.rollback_verified is False


def test_capture_reports_unknown_when_absent_readback_race_hides_detached_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jsonl"
    atif_parent = tmp_path / "private"
    route_parent = tmp_path / "public"
    target_parent = tmp_path / "attacker"
    detached_parent = tmp_path / "detached-private"
    atif = atif_parent / "trajectory.json"
    route_receipt = route_parent / "route.json"
    attacker_atif = target_parent / atif.name
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    atif_parent.mkdir()
    route_parent.mkdir()
    target_parent.mkdir()
    attacker_atif.write_text('{"attacker": true}\n', encoding="utf-8")
    real_atomic_write_json = traex_evidence_module.atomic_write_json
    real_restore = traex_evidence_module._restore_evidence_file
    real_open_pinned_output = traex_evidence_module._open_pinned_output
    restore_calls = 0
    swapped = False

    def fail_after_route_publish(
        path: Path, payload: dict[str, object], *, preserve_mode: bool = False
    ) -> None:
        real_atomic_write_json(path, payload, preserve_mode=preserve_mode)
        if path == route_receipt:
            raise OSError("injected publish failure")

    def record_restore(path: Path, snapshot: object) -> None:
        nonlocal restore_calls
        real_restore(path, snapshot)  # type: ignore[arg-type]
        restore_calls += 1

    def swap_after_parent_check_before_open(
        output: Any, *, flags: int, mode: int = 0o600
    ) -> int:
        nonlocal swapped
        if restore_calls == 2 and output.path == atif and not swapped:
            atif_parent.rename(detached_parent)
            atif_parent.symlink_to(target_parent.name, target_is_directory=True)
            swapped = True
        return real_open_pinned_output(output, flags=flags, mode=mode)

    monkeypatch.setattr(
        traex_evidence_module, "atomic_write_json", fail_after_route_publish
    )
    monkeypatch.setattr(traex_evidence_module, "_restore_evidence_file", record_restore)
    monkeypatch.setattr(
        traex_evidence_module,
        "_open_pinned_output",
        swap_after_parent_check_before_open,
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )

    error = error_info.value
    assert error.classification == "publish_failed"
    assert error.write_state == "unknown"
    assert error.rollback_verified is False
    assert swapped is True
    assert atif_parent.is_symlink()
    assert attacker_atif.read_text(encoding="utf-8") == '{"attacker": true}\n'
    assert not (detached_parent / atif.name).exists()
    assert not route_receipt.exists()


def test_capture_snapshot_failure_reports_verified_no_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jsonl"
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )

    def fail_snapshot(path: Path) -> object:
        raise OSError("injected snapshot failure")

    monkeypatch.setattr(traex_evidence_module, "_snapshot_evidence_file", fail_snapshot)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )

    assert error_info.value.classification == "snapshot_failed"
    assert error_info.value.write_state == "no_write_snapshot_failed"
    assert error_info.value.rollback_verified is None
    assert not atif.exists()
    assert not route_receipt.exists()


def test_capture_lock_failure_reports_verified_no_write_and_safe_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jsonl"
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    private_path = str(tmp_path / "private-lock-target")
    timeout = LockAcquireTimeoutError(
        incident={
            "lock_id": "opaque-lock-id",
            "policy": "mutation",
            "holder": {"pid": 123, "private_path": private_path},
            "operator_action": {
                "retry_mode": "manual_after_holder_inspection",
                "private_path": private_path,
            },
        },
        incident_recorded=True,
        incident_channel="opaque-lock.incidents.jsonl",
    )

    @contextmanager
    def fail_lock(*args: object, **kwargs: object) -> Any:
        raise timeout
        yield  # pragma: no cover

    monkeypatch.setattr(traex_evidence_module, "exclusive_file_lock", fail_lock)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        capture_traex_benchmark_evidence(
            source_jsonl=source,
            atif_output=atif,
            route_receipt_output=route_receipt,
            requested_model="GPT-5.4",
            execute=True,
        )

    error = error_info.value
    assert error.classification == "lock_failed"
    assert error.write_state == "no_write_lock_failed"
    assert error.rollback_verified is None
    assert error.failure_metadata == {
        "error_code": "lock_acquire_timeout",
        "incident_recorded": True,
        "incident_channel": "opaque-lock.incidents.jsonl",
        "lock_id": "opaque-lock-id",
        "lock_policy": "mutation",
        "retry_mode": "manual_after_holder_inspection",
    }
    assert private_path not in json.dumps(error.failure_metadata)
    assert not atif.exists()
    assert not route_receipt.exists()

    emitted = benchmark_boundary_module._traex_evidence_publish_failure(
        error, bound_requested=False
    )
    assert emitted["private_atif_written"] is False
    assert emitted["route_receipt_written"] is False
    assert emitted["write_performed"] is False
    assert emitted["write_state"] == "no_write_lock_failed"
    assert emitted["incident_channel"] == "opaque-lock.incidents.jsonl"
    assert private_path not in json.dumps(emitted)


def test_pair_publisher_rejects_symlinked_lock_target_without_victim_write(
    tmp_path: Path,
) -> None:
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    lock_target = traex_evidence_module._ordered_evidence_lock_targets(
        (atif, route_receipt)
    )[0]
    lock_file = lock_target.with_name(f"{lock_target.name}.lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.symlink_to(victim)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif,
            {"schema_version": "ATIF-v1.7"},
            route_receipt,
            {"schema_version": "route-v1"},
        )

    error = error_info.value
    assert error.classification == "lock_failed"
    assert error.write_state == "no_write_lock_failed"
    assert error.rollback_verified is None
    assert lock_file.is_symlink()
    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"
    assert not atif.exists()
    assert not route_receipt.exists()


def test_pair_publisher_rejects_hardlinked_lock_target_without_victim_write(
    tmp_path: Path,
) -> None:
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    lock_target = traex_evidence_module._ordered_evidence_lock_targets(
        (atif, route_receipt)
    )[0]
    lock_file = lock_target.with_name(f"{lock_target.name}.lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.unlink(missing_ok=True)
    os.link(victim, lock_file)

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif,
            {"schema_version": "ATIF-v1.7"},
            route_receipt,
            {"schema_version": "route-v1"},
        )

    assert error_info.value.classification == "lock_failed"
    assert error_info.value.write_state == "no_write_lock_failed"
    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"
    assert victim.stat().st_nlink == 2
    assert not atif.exists()
    assert not route_receipt.exists()


def test_pair_publisher_timeout_does_not_follow_symlinked_incident_path(
    tmp_path: Path,
) -> None:
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    lock_target = traex_evidence_module._ordered_evidence_lock_targets(
        (atif, route_receipt)
    )[0]
    lock_file = lock_target.with_name(f"{lock_target.name}.lock")
    incident_path = lock_target.with_name(f"{lock_target.name}.lock.incidents.jsonl")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    old_policy = file_lock.LOCK_POLICIES[file_lock.LockAcquisitionPolicy.MUTATION]
    incident_path.symlink_to(victim)
    if fcntl is None:  # pragma: no cover - module-level skip should prevent this
        os.close(descriptor)
        pytest.skip("POSIX flock backend required")
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    file_lock.LOCK_POLICIES[file_lock.LockAcquisitionPolicy.MUTATION] = (
        file_lock.LockPolicy(
            timeout_seconds=0.0,
            poll_interval_seconds=old_policy.poll_interval_seconds,
            retry_mode=old_policy.retry_mode,
        )
    )
    try:
        with pytest.raises(
            traex_evidence_module.TraexEvidencePairPublishError
        ) as error_info:
            traex_evidence_module._publish_evidence_pair(
                atif,
                {"schema_version": "ATIF-v1.7"},
                route_receipt,
                {"schema_version": "route-v1"},
            )
    finally:
        file_lock.LOCK_POLICIES[file_lock.LockAcquisitionPolicy.MUTATION] = old_policy
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    error = error_info.value
    assert error.classification == "lock_failed"
    assert error.write_state == "no_write_lock_failed"
    assert error.rollback_verified is None
    assert error.failure_metadata["incident_recorded"] is False
    assert incident_path.is_symlink()
    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"
    assert not atif.exists()
    assert not route_receipt.exists()


def test_pair_publisher_rejects_lock_path_replacement_while_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    lock_target = traex_evidence_module._ordered_evidence_lock_targets(
        (atif, route_receipt)
    )[0]
    lock_path = lock_target.with_name(f"{lock_target.name}.lock")
    detached = tmp_path / "detached.lock"
    replacement = tmp_path / "replacement.lock"
    real_assert_live = file_lock._assert_live_lock_path_matches_descriptor
    replaced = False

    def replace_on_second_check(path: Path, descriptor: int) -> None:
        nonlocal replaced
        if path == lock_path and not replaced:
            path.rename(detached)
            replacement.write_text("", encoding="utf-8")
            replacement.replace(path)
            replaced = True
        real_assert_live(path, descriptor)

    monkeypatch.setattr(
        file_lock, "_assert_live_lock_path_matches_descriptor", replace_on_second_check
    )

    with pytest.raises(
        traex_evidence_module.TraexEvidencePairPublishError
    ) as error_info:
        traex_evidence_module._publish_evidence_pair(
            atif,
            {"schema_version": "ATIF-v1.7"},
            route_receipt,
            {"schema_version": "route-v1"},
        )

    error = error_info.value
    assert error.classification == "lock_failed"
    assert error.write_state == "no_write_lock_failed"
    assert error.rollback_verified is None
    assert replaced is True
    assert detached.exists()
    assert lock_path.exists()
    assert detached.stat().st_ino != lock_path.stat().st_ino
    assert not atif.exists()
    assert not route_receipt.exists()


def test_pair_publisher_does_not_rollback_a_replacement_writers_success(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    lock_targets = traex_evidence_module._ordered_evidence_lock_targets(
        (atif, route_receipt)
    )
    lock_paths = [target.with_name(f"{target.name}.lock") for target in lock_targets]
    for lock_path in lock_paths:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.unlink(missing_ok=True)
    paused = context.Event()
    release = context.Event()
    results = context.Queue()
    first = context.Process(
        target=_paused_pair_writer,
        args=(str(atif), str(route_receipt), paused, release, results),
    )
    second = context.Process(
        target=_replacement_pair_writer,
        args=(str(atif), str(route_receipt), results),
    )

    first.start()
    try:
        assert paused.wait(timeout=10)
        for index, lock_path in enumerate(lock_paths):
            lock_path.rename(tmp_path / f"detached-{index}.lock")
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(descriptor)
        second.start()
        second.join(timeout=10)
        assert not second.is_alive()
        release.set()
        first.join(timeout=10)
    finally:
        release.set()
        if first.is_alive():
            first.terminate()
        if second.pid is not None and second.is_alive():
            second.terminate()
        first.join(timeout=5)
        if second.pid is not None:
            second.join(timeout=5)

    child_results = sorted(
        [results.get(timeout=5), results.get(timeout=5)],
        key=lambda row: row["writer"],
    )
    assert child_results == [
        {"writer": "first", "status": "error", "write_state": "unknown"},
        {"writer": "second", "status": "success"},
    ]
    assert json.loads(atif.read_text(encoding="utf-8"))["writer"] == "second"
    assert json.loads(route_receipt.read_text(encoding="utf-8"))["writer"] == "second"


def test_pair_transaction_serializes_failure_rollback_before_next_writer(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    source = tmp_path / "source.jsonl"
    atif = tmp_path / "private" / "trajectory.json"
    route_receipt = tmp_path / "public" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    atif.parent.mkdir(parents=True)
    route_receipt.parent.mkdir(parents=True)
    atif.write_bytes(b"old private bytes\n")
    route_receipt.write_bytes(b"old public bytes\n")
    second_write_reached = context.Event()
    release_failure = context.Event()
    second_lock_attempted = context.Event()
    second_first_write_reached = context.Event()
    results = context.Queue()
    failing = context.Process(
        target=_failing_pair_writer,
        args=(
            str(source),
            str(atif),
            str(route_receipt),
            second_write_reached,
            release_failure,
            results,
        ),
    )
    succeeding = context.Process(
        target=_successful_pair_writer,
        args=(
            str(source),
            str(atif),
            str(route_receipt),
            second_lock_attempted,
            second_first_write_reached,
            results,
        ),
    )

    failing.start()
    try:
        assert second_write_reached.wait(timeout=10)
        succeeding.start()
        assert second_lock_attempted.wait(timeout=10)
        assert not second_first_write_reached.wait(timeout=0.25)
        release_failure.set()
        failing.join(timeout=10)
        succeeding.join(timeout=10)
    finally:
        release_failure.set()
        if failing.is_alive():
            failing.terminate()
        if succeeding.pid is not None and succeeding.is_alive():
            succeeding.terminate()
        failing.join(timeout=5)
        if succeeding.pid is not None:
            succeeding.join(timeout=5)

    assert failing.exitcode == 0
    assert succeeding.exitcode == 0
    child_results = [results.get(timeout=5), results.get(timeout=5)]
    assert {item.get("write_state") for item in child_results} == {
        None,
        "rolled_back_verified",
    }
    assert {item.get("status") for item in child_results} == {None, "captured"}
    assert (
        json.loads(route_receipt.read_text(encoding="utf-8"))["requested_model"]
        == "GPT-5.5"
    )


def test_overlapping_transactions_serialize_on_the_shared_output(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    source = tmp_path / "source.jsonl"
    shared_atif = tmp_path / "private" / "trajectory.json"
    first_route = tmp_path / "public" / "first-route.json"
    second_route = tmp_path / "public" / "second-route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    first_route.parent.mkdir(parents=True)
    shared_atif.parent.mkdir(parents=True)
    shared_atif.write_bytes(b"old private bytes\n")
    first_route.write_bytes(b"old first public bytes\n")
    second_write_reached = context.Event()
    release_failure = context.Event()
    shared_lock_attempted = context.Event()
    overlapping_first_write_reached = context.Event()
    results = context.Queue()
    failing = context.Process(
        target=_failing_pair_writer,
        args=(
            str(source),
            str(shared_atif),
            str(first_route),
            second_write_reached,
            release_failure,
            results,
        ),
    )
    overlapping = context.Process(
        target=_overlapping_pair_writer,
        args=(
            str(source),
            str(shared_atif),
            str(second_route),
            shared_lock_attempted,
            overlapping_first_write_reached,
            results,
        ),
    )

    failing.start()
    try:
        assert second_write_reached.wait(timeout=10)
        overlapping.start()
        assert shared_lock_attempted.wait(timeout=10)
        assert not overlapping_first_write_reached.wait(timeout=0.25)
        release_failure.set()
        failing.join(timeout=10)
        overlapping.join(timeout=10)
    finally:
        release_failure.set()
        if failing.is_alive():
            failing.terminate()
        if overlapping.pid is not None and overlapping.is_alive():
            overlapping.terminate()
        failing.join(timeout=5)
        if overlapping.pid is not None:
            overlapping.join(timeout=5)

    assert failing.exitcode == 0
    assert overlapping.exitcode == 0
    child_results = [results.get(timeout=5), results.get(timeout=5)]
    assert {item.get("write_state") for item in child_results} == {
        None,
        "rolled_back_verified",
    }
    assert (
        json.loads(second_route.read_text(encoding="utf-8"))["requested_model"]
        == "GPT-5.5"
    )


def test_lexical_alias_transactions_serialize_on_the_shared_output(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    source = tmp_path / "source.jsonl"
    shared_atif = tmp_path / "private" / "trajectory.json"
    alias_marker = tmp_path / "alias-marker"
    aliased_atif = alias_marker / ".." / "private" / "trajectory.json"
    first_route = tmp_path / "public" / "first-route.json"
    second_route = tmp_path / "public" / "second-route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    alias_marker.mkdir()
    first_route.parent.mkdir(parents=True)
    shared_atif.parent.mkdir(parents=True)
    shared_atif.write_bytes(b"old private bytes\n")
    first_route.write_bytes(b"old first public bytes\n")
    second_write_reached = context.Event()
    release_failure = context.Event()
    shared_lock_attempted = context.Event()
    aliased_first_write_reached = context.Event()
    results = context.Queue()
    failing = context.Process(
        target=_failing_pair_writer,
        args=(
            str(source),
            str(shared_atif),
            str(first_route),
            second_write_reached,
            release_failure,
            results,
        ),
    )
    aliased = context.Process(
        target=_overlapping_pair_writer,
        args=(
            str(source),
            str(aliased_atif),
            str(second_route),
            shared_lock_attempted,
            aliased_first_write_reached,
            results,
        ),
    )

    failing.start()
    try:
        assert second_write_reached.wait(timeout=10)
        aliased.start()
        assert shared_lock_attempted.wait(timeout=10)
        assert not aliased_first_write_reached.wait(timeout=0.25)
        release_failure.set()
        failing.join(timeout=10)
        aliased.join(timeout=10)
    finally:
        release_failure.set()
        if failing.is_alive():
            failing.terminate()
        if aliased.pid is not None and aliased.is_alive():
            aliased.terminate()
        failing.join(timeout=5)
        if aliased.pid is not None:
            aliased.join(timeout=5)

    assert failing.exitcode == 0
    assert aliased.exitcode == 0
    child_results = [results.get(timeout=5), results.get(timeout=5)]
    assert {item.get("write_state") for item in child_results} == {
        None,
        "rolled_back_verified",
    }
    assert (
        json.loads(second_route.read_text(encoding="utf-8"))["requested_model"]
        == "GPT-5.5"
    )


def test_cli_writes_private_atif_and_public_safe_route_receipt(tmp_path: Path) -> None:
    private_value = "private-cli-task-value"
    source = tmp_path / "private-source.jsonl"
    route_source = tmp_path / "private-route-source.jsonl"
    atif = tmp_path / "private-output" / "trajectory.json"
    route_receipt = tmp_path / "public-output" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events(private_value)) + "\n",
        encoding="utf-8",
    )
    route_source.write_text(
        "\n".join(
            json.dumps(event) for event in [_session_meta(), _route_event("GPT-5.4")]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_traex_evidence_cli(
        source=source,
        route_source=route_source,
        atif=atif,
        route_receipt=route_receipt,
        extra_args=("--require-runtime-route", "--execute"),
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "captured"
    assert payload["route_source_bound"] is True
    assert payload["model_route"]["status"] == "runtime_route_verified"
    assert payload["public_boundary"] == {
        "raw_content_recorded": False,
        "input_path_recorded": False,
        "output_path_recorded": False,
    }
    assert private_value not in completed.stdout
    assert str(tmp_path) not in completed.stdout
    assert private_value in atif.read_text(encoding="utf-8")
    public_receipt_text = route_receipt.read_text(encoding="utf-8")
    assert private_value not in public_receipt_text
    assert str(tmp_path) not in public_receipt_text
    assert (
        json.loads(public_receipt_text)["schema_version"]
        == BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION
    )


def test_cli_writes_bound_v1_route_receipt(tmp_path: Path) -> None:
    source = tmp_path / "private-source.jsonl"
    atif = tmp_path / "private-output" / "trajectory.json"
    route_receipt = tmp_path / "public-output" / "route.json"
    source.write_text(
        "\n".join(
            json.dumps(event) for event in [*_stdout_events(), _route_event("GPT-5.4")]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_traex_evidence_cli(
        source=source,
        atif=atif,
        route_receipt=route_receipt,
        extra_args=(
            *_bound_route_args(BOUND_ROUTE),
            "--require-runtime-route",
            "--execute",
        ),
        check=True,
    )

    payload = json.loads(completed.stdout)
    route = payload["model_route"]
    persisted_route = json.loads(route_receipt.read_text(encoding="utf-8"))
    assert route["schema_version"] == BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
    assert route["status"] == "runtime_route_verified"
    assert {field: route[field] for field in BOUND_ROUTE} == BOUND_ROUTE
    assert persisted_route == route
    assert normalize_benchmark_model_route_receipt_v1(route) == route
    assert normalize_benchmark_model_route_receipt_v1(persisted_route) == route
    assert str(tmp_path) not in completed.stdout


@pytest.mark.parametrize(
    "binding",
    [
        *[
            {field: value for field, value in BOUND_ROUTE.items() if field != missing}
            for missing in BOUND_ROUTE
        ],
        {**BOUND_ROUTE, "launch_binding_digest": "private-invalid-digest"},
        {**BOUND_ROUTE, "run_id": "private/invalid/run"},
        {**BOUND_ROUTE, "arm_id": "private invalid arm"},
        {**BOUND_ROUTE, "authority": "private invalid authority"},
    ],
)
def test_cli_bound_input_invalid_is_safe_and_writes_nothing(
    tmp_path: Path, binding: dict[str, str]
) -> None:
    private_value = "private-invalid-input-content"
    source = tmp_path / "private-source.jsonl"
    atif = tmp_path / "private-output" / "trajectory.json"
    route_receipt = tmp_path / "public-output" / "route.json"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events(private_value)) + "\n",
        encoding="utf-8",
    )

    completed = _run_traex_evidence_cli(
        source=source,
        atif=atif,
        route_receipt=route_receipt,
        extra_args=(*_bound_route_args(binding), "--execute"),
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "input_invalid"
    assert payload["model_route"] is None
    assert payload["error"] == {
        "schema_version": "benchmark_model_route_capture_error_v0",
        "classification": "input_invalid",
        "requested_receipt_schema_version": (
            BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
        ),
        "bound_requested": True,
        "raw_content_recorded": False,
        "input_path_recorded": False,
    }
    assert payload["private_atif_written"] is False
    assert payload["route_receipt_written"] is False
    assert payload["write_performed"] is False
    assert private_value not in completed.stdout
    assert str(tmp_path) not in completed.stdout
    assert not atif.exists()
    assert not route_receipt.exists()


def test_cli_bound_publish_failure_reports_unknown_write_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "private-source.jsonl"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )
    error = traex_evidence_module.TraexEvidencePairPublishError(
        write_state="unknown",
        rollback_verified=False,
    )

    def fail_capture(**kwargs: object) -> dict[str, object]:
        raise error

    monkeypatch.setattr(
        benchmark_boundary_module, "capture_traex_benchmark_evidence", fail_capture
    )
    args = Namespace(
        benchmark_command="traex-evidence",
        source_jsonl=str(source),
        route_source_jsonl=None,
        atif_output=str(tmp_path / "private" / "trajectory.json"),
        route_receipt_output=str(tmp_path / "public" / "route.json"),
        requested_model="GPT-5.4",
        requested_provider="trae",
        require_runtime_route=False,
        execute=True,
        **BOUND_ROUTE,
    )
    emitted: list[dict[str, object]] = []

    result = benchmark_boundary_module.handle_benchmark_boundary_command(
        args,
        print_payload=lambda payload, _format, _renderer: emitted.append(payload),
        output_format=lambda _args: "json",
    )

    assert result == 1
    assert emitted == [
        {
            "ok": False,
            "schema_version": "benchmark_trae_evidence_capture_v0",
            "source_runtime": "traex",
            "status": "publish_failed",
            "private_atif_written": None,
            "route_receipt_written": None,
            "write_performed": None,
            "write_state": "unknown",
            "rollback_verified": False,
            "model_route": None,
            "error": {
                "schema_version": "benchmark_model_route_capture_error_v0",
                "classification": "publish_failed",
                "requested_receipt_schema_version": (
                    BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
                ),
                "bound_requested": True,
                "write_state": "unknown",
                "rollback_verified": False,
                "raw_content_recorded": False,
                "input_path_recorded": False,
                "output_path_recorded": False,
            },
            "publication_contract": {
                "isolation": "ordered_per_output_lock_leases",
                "failure_recovery": "ownership_checked_rollback",
                "crash_atomic": False,
            },
            "public_boundary": {
                "raw_content_recorded": False,
                "input_path_recorded": False,
                "output_path_recorded": False,
            },
        }
    ]
    assert str(tmp_path) not in json.dumps(emitted)


def test_cli_legacy_input_invalid_keeps_v0_schema_and_is_safe(
    tmp_path: Path,
) -> None:
    private_value = "private-malformed-jsonl-content"
    source = tmp_path / "private-source.jsonl"
    atif = tmp_path / "private-output" / "trajectory.json"
    route_receipt = tmp_path / "public-output" / "route.json"
    source.write_text(f"not-json {private_value}\n", encoding="utf-8")

    completed = _run_traex_evidence_cli(
        source=source,
        atif=atif,
        route_receipt=route_receipt,
        extra_args=("--execute",),
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "input_invalid"
    assert (
        payload["model_route"]["schema_version"]
        == BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION
    )
    assert private_value not in completed.stdout
    assert str(tmp_path) not in completed.stdout
    assert not atif.exists()
    assert not route_receipt.exists()


@pytest.mark.parametrize(
    ("binding_args", "schema_version"),
    [
        ((), BENCHMARK_MODEL_ROUTE_RECEIPT_SCHEMA_VERSION),
        (
            (
                "--run-id",
                BOUND_ROUTE["run_id"],
                "--arm-id",
                BOUND_ROUTE["arm_id"],
                "--launch-binding-digest",
                BOUND_ROUTE["launch_binding_digest"],
                "--authority",
                BOUND_ROUTE["authority"],
            ),
            BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION,
        ),
    ],
)
def test_cli_require_runtime_route_rejects_unaudited_v0_and_v1(
    tmp_path: Path, binding_args: tuple[str, ...], schema_version: str
) -> None:
    source = tmp_path / "stdout.jsonl"
    source.write_text(
        "\n".join(json.dumps(event) for event in _stdout_events()) + "\n",
        encoding="utf-8",
    )

    atif = tmp_path / "trajectory.json"
    route_receipt = tmp_path / "receipt.json"
    completed = _run_traex_evidence_cli(
        source=source,
        atif=atif,
        route_receipt=route_receipt,
        extra_args=(*binding_args, "--require-runtime-route"),
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["model_route"]["schema_version"] == schema_version
    assert payload["model_route"]["status"] == "route_requested_not_runtime_audited"
    assert not atif.exists()
    assert not route_receipt.exists()


@pytest.mark.parametrize(
    "route_events",
    [
        [],
        [_route_event("GPT-5.5")],
        [_route_event("GPT-5.4"), _route_event("GPT-5.5")],
    ],
)
def test_cli_execute_requires_runtime_route_before_any_output_or_lock_side_effect(
    tmp_path: Path, route_events: list[dict[str, object]]
) -> None:
    source = tmp_path / "stdout.jsonl"
    source.write_text(
        "\n".join(json.dumps(event) for event in [*_stdout_events(), *route_events])
        + "\n",
        encoding="utf-8",
    )
    atif = tmp_path / "private-new-parent" / "trajectory.json"
    route_receipt = tmp_path / "public-new-parent" / "receipt.json"
    lock_targets = traex_evidence_module._ordered_evidence_lock_targets(
        (atif, route_receipt)
    )
    for lock_target in lock_targets:
        assert not lock_target.with_name(f"{lock_target.name}.lock").exists()

    completed = _run_traex_evidence_cli(
        source=source,
        atif=atif,
        route_receipt=route_receipt,
        extra_args=("--require-runtime-route", "--execute"),
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "runtime_route_not_verified"
    assert payload["write_performed"] is False
    assert not atif.parent.exists()
    assert not route_receipt.parent.exists()
    for lock_target in lock_targets:
        assert not lock_target.with_name(f"{lock_target.name}.lock").exists()


def test_capture_hashes_private_backend_identity_and_rejects_sensitive_route_label() -> (
    None
):
    private_variant = "host-private-session-variant"
    route = build_traex_model_route_receipt(
        [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "context": {
                        "model": "GPT-5.4",
                        "modelProviderId": "trae",
                        "modelBackendVariant": private_variant,
                    },
                },
            }
        ],
        requested_model="GPT-5.4",
        **BOUND_ROUTE,
    )

    assert route["observed_backend_variant"] == public_identity_digest(
        private_variant, kind=PublicIdentityKind.BACKEND_VARIANT
    )
    assert private_variant not in json.dumps(route)

    with pytest.raises(ValueError, match="declared sensitive value"):
        build_traex_model_route_receipt(
            [_route_event("private-model-label")],
            requested_model="private-model-label",
            sensitive_values=("private-model-label",),
        )
