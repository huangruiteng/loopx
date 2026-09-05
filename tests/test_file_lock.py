from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import loopx.file_lock as file_lock
from loopx.file_lock import (
    LOCK_ACQUIRE_TIMEOUT_ERROR_CODE,
    LockAcquireTimeoutError,
    exclusive_cross_runtime_file_lock,
    exclusive_file_lock,
    fcntl,
    lock_holder_path,
    lock_incident_path,
    msvcrt,
    try_exclusive_file_lock,
)
from loopx.presentation.markdown import append_operator_action_markdown


pytestmark = pytest.mark.skipif(
    fcntl is None and msvcrt is None,
    reason="a supported kernel file-lock backend is required",
)


def _start_stalled_holder(target: Path) -> subprocess.Popen[str]:
    script = """
import sys
import time
from pathlib import Path
from loopx.file_lock import exclusive_file_lock

with exclusive_file_lock(
    Path(sys.argv[1]),
    timeout_seconds=1.0,
    agent_id="holder-agent",
    operation="stalled-holder",
):
    print("ready", flush=True)
    time.sleep(30)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "ready"
    return process


def _stop(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _acquire_and_release_cross_runtime_lock(
    target: Path,
    *,
    timeout_seconds: float | None = None,
    operation: str | None = None,
) -> None:
    with exclusive_cross_runtime_file_lock(
        target,
        timeout_seconds=timeout_seconds,
        operation=operation,
    ):
        pass


def test_exclusive_lock_persists_public_safe_holder_metadata(tmp_path: Path) -> None:
    target = tmp_path / "state.json"

    with exclusive_file_lock(
        target,
        agent_id="agent-a",
        operation="todo-update",
    ) as lock_path:
        holder_path = lock_holder_path(target)
        holder = json.loads(holder_path.read_text(encoding="utf-8"))
        assert holder["pid"] > 0
        assert holder["agent_id"] == "agent-a"
        assert holder["operation"] == "todo-update"
        assert holder["acquired_at"].endswith("Z")
        assert "released_at" not in holder

    released = json.loads(holder_path.read_text(encoding="utf-8"))
    assert released["released_at"].endswith("Z")
    assert lock_path.exists()
    assert holder_path.exists()


def test_exclusive_lock_can_expose_revalidatable_lease(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    lock_path = target.with_name(f"{target.name}.lock")

    with exclusive_file_lock(target, expose_lease=True) as lease:
        assert isinstance(lease, file_lock.ExclusiveFileLockLease)
        lease.check()
        assert lease.path == lock_path
        assert lease.exists()


def test_exclusive_lock_lease_detects_replacement_before_context_exit(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.json"
    lock_path = target.with_name(f"{target.name}.lock")
    detached = tmp_path / "detached.lock"
    replacement = tmp_path / "replacement.lock"

    with pytest.raises(OSError, match="lock_file_replaced_during_lock"):
        with exclusive_file_lock(target, expose_lease=True) as lease:
            assert isinstance(lease, file_lock.ExclusiveFileLockLease)
            lock_path.rename(detached)
            replacement.write_text("", encoding="utf-8")
            replacement.replace(lock_path)
            lease.check()


def test_stalled_holder_times_out_and_records_independent_incident(
    tmp_path: Path,
) -> None:
    target = tmp_path / "todos.md"
    process = _start_stalled_holder(target)
    try:
        with pytest.raises(LockAcquireTimeoutError) as raised:
            with exclusive_file_lock(
                target,
                timeout_seconds=0.15,
                poll_interval_seconds=0.02,
                agent_id="waiter-agent",
                operation="todo-add",
            ):
                pytest.fail("waiter unexpectedly acquired the stalled lock")

        error = raised.value
        payload = error.to_payload()
        assert payload["error_code"] == LOCK_ACQUIRE_TIMEOUT_ERROR_CODE
        assert payload["incident_recorded"] is True
        incident = payload["lock_timeout"]
        assert incident["holder"]["pid"] == process.pid
        assert incident["holder"]["agent_id"] == "holder-agent"
        assert incident["waiter"]["agent_id"] == "waiter-agent"
        assert incident["waiter"]["waited_seconds"] >= 0.1
        assert incident["operator_action"]["retry_mode"] == (
            "manual_after_holder_inspection"
        )
        markdown_lines: list[str] = []
        append_operator_action_markdown(markdown_lines, payload)
        markdown = "\n".join(markdown_lines)
        assert "error_code: `lock_acquire_timeout`" in markdown
        assert f"holder_pid={process.pid}" in markdown
        assert "Do not delete the lock file" in markdown

        rows = lock_incident_path(target).read_text(encoding="utf-8").splitlines()
        recorded = json.loads(rows[-1])
        assert recorded["error_code"] == LOCK_ACQUIRE_TIMEOUT_ERROR_CODE
        assert recorded["lock_id"] == incident["lock_id"]
        assert str(target) not in rows[-1]
    finally:
        _stop(process)

    assert target.with_name(f"{target.name}.lock").exists()


def test_single_flight_returns_none_without_timeout_incident(tmp_path: Path) -> None:
    target = tmp_path / "sync.json"
    process = _start_stalled_holder(target)
    try:
        with try_exclusive_file_lock(target, operation="duplicate-sync") as lock_path:
            assert lock_path is None
        assert not lock_incident_path(target).exists()
    finally:
        _stop(process)


def test_exclusive_file_lock_rejects_precreated_symlink_lock_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    lock_path = target.with_name(f"{target.name}.lock")
    lock_path.symlink_to(victim)

    with pytest.raises(OSError, match="lock_file_symlink_rejected"):
        with exclusive_file_lock(target):
            pytest.fail("symlink lock unexpectedly acquired")

    assert lock_path.is_symlink()
    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"


def test_exclusive_file_lock_rejects_precreated_hardlink_lock_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.json"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    lock_path = target.with_name(f"{target.name}.lock")
    os.link(victim, lock_path)

    with pytest.raises(OSError, match="lock_file_hardlink_rejected"):
        with exclusive_file_lock(target):
            pytest.fail("hardlinked lock unexpectedly acquired")

    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"
    assert victim.stat().st_nlink == 2


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO support required")
def test_try_exclusive_file_lock_rejects_nonregular_lock_file(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    lock_path = target.with_name(f"{target.name}.lock")
    os.mkfifo(lock_path)

    with pytest.raises(OSError, match="lock_file_not_regular"):
        with try_exclusive_file_lock(target) as lock_state:
            pytest.fail(f"nonregular lock unexpectedly acquired: {lock_state}")


def test_exclusive_file_lock_closes_raw_fd_when_fdopen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    real_open_verified = file_lock._open_verified_lock_descriptor
    real_close = file_lock.os.close
    opened_descriptors: set[int] = set()
    closed_descriptors: set[int] = set()

    def record_open_verified(path: Path) -> int:
        descriptor = real_open_verified(path)
        opened_descriptors.add(descriptor)
        return descriptor

    def fail_fdopen(*args: object, **kwargs: object) -> object:
        raise OSError("injected-fdopen-failure")

    def record_close(descriptor: int) -> None:
        if descriptor in opened_descriptors:
            closed_descriptors.add(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(
        file_lock, "_open_verified_lock_descriptor", record_open_verified
    )
    monkeypatch.setattr(file_lock.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(file_lock.os, "close", record_close)

    with pytest.raises(OSError, match="injected-fdopen-failure"):
        with exclusive_file_lock(target):
            pytest.fail("lock unexpectedly acquired")

    assert len(opened_descriptors) == 1
    assert closed_descriptors == opened_descriptors


def test_write_holder_sidecar_closes_raw_fd_when_fdopen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    holder_path = tmp_path / "state.json.lock.holder.json"
    record = {"schema_version": "file_lock_holder_v0", "pid": 1}
    real_close = file_lock.os.close
    closed_descriptors: list[int] = []

    def fail_fdopen(descriptor: int, *args: object, **kwargs: object) -> object:
        raise OSError("injected-holder-fdopen-failure")

    def record_close(descriptor: int) -> None:
        closed_descriptors.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(file_lock.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(file_lock.os, "close", record_close)

    with pytest.raises(OSError, match="injected-holder-fdopen-failure"):
        file_lock._write_holder_sidecar(holder_path, record)

    assert len(closed_descriptors) == 1
    assert not holder_path.exists()


def test_try_exclusive_file_lock_closes_raw_fd_when_fdopen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    real_open_verified = file_lock._open_verified_lock_descriptor
    real_close = file_lock.os.close
    opened_descriptors: set[int] = set()
    closed_descriptors: set[int] = set()

    def record_open_verified(path: Path) -> int:
        descriptor = real_open_verified(path)
        opened_descriptors.add(descriptor)
        return descriptor

    def fail_fdopen(*args: object, **kwargs: object) -> object:
        raise OSError("injected-fdopen-failure")

    def record_close(descriptor: int) -> None:
        if descriptor in opened_descriptors:
            closed_descriptors.add(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(
        file_lock, "_open_verified_lock_descriptor", record_open_verified
    )
    monkeypatch.setattr(file_lock.os, "fdopen", fail_fdopen)
    monkeypatch.setattr(file_lock.os, "close", record_close)

    with pytest.raises(OSError, match="injected-fdopen-failure"):
        with try_exclusive_file_lock(target):
            pytest.fail("lock unexpectedly acquired")

    assert len(opened_descriptors) == 1
    assert closed_descriptors == opened_descriptors


def test_stalled_holder_timeout_does_not_follow_symlinked_incident_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "todos.md"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    incident_path = lock_incident_path(target)
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    incident_path.symlink_to(victim)
    process = _start_stalled_holder(target)
    try:
        with pytest.raises(LockAcquireTimeoutError) as raised:
            with exclusive_file_lock(
                target,
                timeout_seconds=0.15,
                poll_interval_seconds=0.02,
                agent_id="waiter-agent",
                operation="todo-add",
            ):
                pytest.fail("waiter unexpectedly acquired the stalled lock")
        payload = raised.value.to_payload()
        assert payload["incident_recorded"] is False
    finally:
        _stop(process)

    assert incident_path.is_symlink()
    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"


def test_stalled_holder_timeout_does_not_append_to_hardlinked_incident_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "todos.md"
    victim = tmp_path / "victim.txt"
    victim.write_text("KEEP-ME\n", encoding="utf-8")
    incident_path = lock_incident_path(target)
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    os.link(victim, incident_path)
    process = _start_stalled_holder(target)
    try:
        with pytest.raises(LockAcquireTimeoutError) as raised:
            with exclusive_file_lock(
                target,
                timeout_seconds=0.15,
                poll_interval_seconds=0.02,
                agent_id="waiter-agent",
                operation="todo-add",
            ):
                pytest.fail("waiter unexpectedly acquired the stalled lock")
        assert raised.value.to_payload()["incident_recorded"] is False
    finally:
        _stop(process)

    assert victim.read_text(encoding="utf-8") == "KEEP-ME\n"
    assert victim.stat().st_nlink == 2


def test_append_incident_reports_false_when_path_is_replaced_after_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "todos.md"
    incident_path = lock_incident_path(target)
    detached = tmp_path / "detached.incidents.jsonl"
    replacement = tmp_path / "replacement.incidents.jsonl"
    real_assert_live = file_lock._assert_live_incident_path_matches_descriptor

    def replace_then_revalidate(path: Path, descriptor: int) -> None:
        incident_path.rename(detached)
        replacement.write_text("replacement\n", encoding="utf-8")
        replacement.replace(incident_path)
        real_assert_live(path, descriptor)

    monkeypatch.setattr(
        file_lock,
        "_assert_live_incident_path_matches_descriptor",
        replace_then_revalidate,
    )

    recorded = file_lock._append_incident(
        target,
        {"error_code": "lock_acquire_timeout", "lock_id": "opaque"},
    )

    assert recorded is False
    assert detached.exists()
    assert incident_path.exists()
    assert detached.read_text(encoding="utf-8").startswith("{")
    assert incident_path.read_text(encoding="utf-8") == "replacement\n"


def test_exclusive_file_lock_rejects_path_replacement_after_kernel_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    lock_path = target.with_name(f"{target.name}.lock")
    detached = tmp_path / "detached.lock"
    real_try_acquire = file_lock._try_acquire_kernel_lock
    calls = 0

    def replace_before_first_lock(lock_file: object) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            lock_path.rename(detached)
            replacement = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(replacement)
        return real_try_acquire(lock_file)  # type: ignore[arg-type]

    monkeypatch.setattr(
        file_lock, "_try_acquire_kernel_lock", replace_before_first_lock
    )

    with pytest.raises(OSError, match="lock_file_replaced_during_lock"):
        with exclusive_file_lock(target, timeout_seconds=0):
            pytest.fail("replaced lock unexpectedly acquired")

    assert detached.exists()
    assert lock_path.exists()
    assert detached.stat().st_ino != lock_path.stat().st_ino


def test_exclusive_file_lock_rejects_path_replacement_while_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    lock_path = target.with_name(f"{target.name}.lock")
    detached = tmp_path / "detached.lock"
    replacement = tmp_path / "replacement.lock"
    real_assert_live = file_lock._assert_live_lock_path_matches_descriptor
    checks = 0

    def replace_on_second_check(path: Path, descriptor: int) -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            path.rename(detached)
            replacement.write_text("", encoding="utf-8")
            replacement.replace(path)
        real_assert_live(path, descriptor)

    monkeypatch.setattr(
        file_lock, "_assert_live_lock_path_matches_descriptor", replace_on_second_check
    )

    with pytest.raises(OSError, match="lock_file_replaced_during_lock"):
        with exclusive_file_lock(target, timeout_seconds=0):
            pass

    assert detached.exists()
    assert lock_path.exists()
    assert detached.stat().st_ino != lock_path.stat().st_ino


def test_try_exclusive_file_lock_rejects_path_replacement_while_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    lock_path = target.with_name(f"{target.name}.lock")
    detached = tmp_path / "detached.lock"
    replacement = tmp_path / "replacement.lock"
    real_assert_live = file_lock._assert_live_lock_path_matches_descriptor
    checks = 0

    def replace_on_second_check(path: Path, descriptor: int) -> None:
        nonlocal checks
        checks += 1
        if checks == 2:
            path.rename(detached)
            replacement.write_text("", encoding="utf-8")
            replacement.replace(path)
        real_assert_live(path, descriptor)

    monkeypatch.setattr(
        file_lock, "_assert_live_lock_path_matches_descriptor", replace_on_second_check
    )

    with pytest.raises(OSError, match="lock_file_replaced_during_lock"):
        with try_exclusive_file_lock(target):
            pass

    assert detached.exists()
    assert lock_path.exists()
    assert detached.stat().st_ino != lock_path.stat().st_ino


def test_cross_runtime_lock_publishes_the_typescript_owner_file(tmp_path: Path) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")

    with exclusive_cross_runtime_file_lock(target, operation="task-lease-renew"):
        owner = json.loads(effect_lock.read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert isinstance(owner["token"], str)
        assert target.with_name(f"{target.name}.lock").exists()

    assert not effect_lock.exists()


def test_cross_runtime_lock_respects_a_live_typescript_holder(tmp_path: Path) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")
    effect_lock.write_text(
        json.dumps({"pid": os.getpid(), "token": "typescript-holder"}),
        encoding="utf-8",
    )

    with pytest.raises(LockAcquireTimeoutError):
        _acquire_and_release_cross_runtime_lock(
            target,
            timeout_seconds=0,
            operation="task-lease-release",
        )


def test_cross_runtime_windows_pid_probe_is_non_signaling(monkeypatch) -> None:
    calls: list[int] = []

    def probe(pid: int) -> bool:
        calls.append(pid)
        return True

    monkeypatch.setattr(file_lock, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(file_lock, "_windows_process_is_alive", probe)

    assert file_lock._effect_mutation_process_is_alive(1234) is True
    assert calls == [1234]


def test_cross_runtime_lock_reclaims_a_dead_typescript_holder(tmp_path: Path) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")
    effect_lock.write_text(
        json.dumps({"pid": 2_147_483_647, "token": "dead-holder"}),
        encoding="utf-8",
    )

    with exclusive_cross_runtime_file_lock(
        target,
        timeout_seconds=0.2,
        operation="task-lease-transfer",
    ):
        owner = json.loads(effect_lock.read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()

    assert not effect_lock.exists()


def test_cross_runtime_lock_reclaims_a_stale_malformed_holder(tmp_path: Path) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")
    effect_lock.write_text(
        json.dumps({"pid": os.getpid(), "token": "   "}),
        encoding="utf-8",
    )
    stale = effect_lock.stat().st_mtime - 60.0
    os.utime(effect_lock, (stale, stale))

    with exclusive_cross_runtime_file_lock(
        target,
        timeout_seconds=0.2,
        operation="task-lease-release",
    ):
        owner = json.loads(effect_lock.read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert owner["token"] != "   "

    assert not effect_lock.exists()


def test_cross_runtime_release_does_not_remove_a_replacement_token(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")
    effect_lock.parent.mkdir(parents=True, exist_ok=True)
    effect_lock.write_text(
        json.dumps({"pid": os.getpid(), "token": "replacement-token"}),
        encoding="utf-8",
    )

    assert (
        file_lock._release_effect_mutation_lock(
            effect_lock,
            "old-token",
        )
        is False
    )
    assert effect_lock.exists()
    assert json.loads(effect_lock.read_text(encoding="utf-8"))["token"] == (
        "replacement-token"
    )
    effect_lock.unlink()


def test_cross_runtime_recovery_releases_only_the_owned_token(tmp_path: Path) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")
    effect_lock.write_text(
        json.dumps({"pid": os.getpid(), "token": "held-token"}),
        encoding="utf-8",
    )

    assert not file_lock.release_cross_runtime_mutation_lock(
        target,
        **{"token": "replacement-token"},
    )
    assert effect_lock.exists()
    assert file_lock.release_cross_runtime_mutation_lock(
        target,
        **{"token": "held-token"},
    )
    assert not effect_lock.exists()


def test_cross_runtime_lock_cleans_up_a_failed_owner_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / ".task-leases"
    effect_lock = Path(f"{target}.ts-effect.lock")

    def fail_fsync(_descriptor: int) -> None:
        raise OSError("simulated owner publication failure")

    monkeypatch.setattr(os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="owner publication failure"):
        _acquire_and_release_cross_runtime_lock(target)

    assert not effect_lock.exists()


def test_cross_runtime_identity_fails_closed_for_ambiguous_or_reused_files() -> None:
    assert not file_lock._same_effect_file_identity(
        (0, 0, 0, 0),
        (0, 0, 0, 0),
    )
    assert not file_lock._same_effect_file_identity(
        (7, 11, 100, 200),
        (7, 11, 101, 200),
    )
    assert file_lock._same_effect_file_identity(
        (7, 11, 100, 200),
        (7, 11, 100, 999),
    )
    assert file_lock._same_effect_file_identity(
        (7, 11, 0, 200),
        (7, 11, 0, 201),
    )


def test_cross_runtime_claim_cleanup_removes_own_corrupted_claim(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".task-leases"
    claim = file_lock._claim_effect_mutation_lock(target, "claim-token")
    assert claim is not None
    claim.path.write_text("not-json", encoding="utf-8")

    file_lock._release_effect_mutation_claim(claim)

    assert not claim.path.exists()


def test_cross_runtime_cleanup_failure_cannot_replace_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / ".task-leases"
    calls: list[bool] = []

    def fake_release(*args: object, **kwargs: object) -> bool:
        calls.append(kwargs.get("suppress_errors") is True)
        return False

    monkeypatch.setattr(file_lock, "_release_effect_mutation_lock", fake_release)
    with exclusive_cross_runtime_file_lock(target, timeout_seconds=0.2):
        pass

    assert calls == [True]
