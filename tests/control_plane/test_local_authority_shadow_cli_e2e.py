from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from loopx.file_lock import exclusive_file_lock


REPO_ROOT = Path(__file__).resolve().parents[2]


def _workspace(tmp_path: Path, *, goal_id: str) -> tuple[Path, Path, Path]:
    repo = tmp_path / goal_id
    repo.mkdir()
    state = repo / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "---\n"
        f"goal_id: {goal_id}\n"
        "handoff_mode: hard_lease\n"
        "updated_at: 2026-09-02T00:00:00+00:00\n"
        "---\n\n"
        "## Agent Todo\n\n",
        encoding="utf-8",
    )
    runtime_root = tmp_path / f"{goal_id}-runtime"
    registry = tmp_path / f"{goal_id}-registry.json"
    registry.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": goal_id,
                        "status": "active",
                        "repo": str(repo),
                        "state_file": state.name,
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": ["agent-a", "agent-b"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry, state, runtime_root


def _command(registry: Path, runtime_root: Path, *args: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime_root),
        "--format",
        "json",
        *args,
    ]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return env


def _cli(registry: Path, runtime_root: Path, *args: str) -> dict[str, object]:
    completed = subprocess.run(
        _command(registry, runtime_root, *args),
        cwd=REPO_ROOT,
        env=_env(),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def _store_document(runtime_root: Path, goal_id: str) -> tuple[Path, dict[str, object]]:
    paths = list(
        (runtime_root / "authority-shadow" / "file" / goal_id).glob(
            "authority-store-*.json"
        )
    )
    assert len(paths) == 1
    return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))


def _add_todo(
    registry: Path,
    runtime_root: Path,
    *,
    goal_id: str,
    text: str,
) -> dict[str, object]:
    return _cli(
        registry,
        runtime_root,
        "todo",
        "add",
        "--goal-id",
        goal_id,
        "--role",
        "agent",
        "--text",
        text,
        "--task-class",
        "advancement_task",
    )


def test_product_cli_configure_capture_readback_disable_and_default_off_lifecycle_isolation(
    tmp_path: Path,
) -> None:
    goal_id = "shadow-cli-e2e"
    registry, _state, runtime_root = _workspace(tmp_path, goal_id=goal_id)

    preview = _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--local-authority-shadow-file",
    )
    assert preview["dry_run"] is True
    assert preview["written"] is False

    enabled = _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--local-authority-shadow-file",
        "--execute",
    )
    assert enabled["written"] is True

    text = "Capture one post-commit observation through the product CLI."
    observed = _add_todo(
        registry,
        runtime_root,
        goal_id=goal_id,
        text=text,
    )
    assert observed["authority_shadow"]["outcome"] == "captured"  # type: ignore[index]
    assert observed["authority_shadow"]["parity_verdict"] == "not_evaluated"  # type: ignore[index]
    lease = _cli(
        registry,
        runtime_root,
        "task-lease",
        "acquire",
        "--goal-id",
        goal_id,
        "--todo-id",
        str(observed["todo_id"]),
        "--owner",
        "agent-a",
        "--idempotency-key",
        "shadow-cli-lease",
        "--ttl-seconds",
        "120",
    )
    assert lease["acquired"] is True
    assert lease["authority_shadow"]["outcome"] == "captured"  # type: ignore[index]
    store_path, store = _store_document(runtime_root, goal_id)
    assert len(store["head"]["todos"]) == 1  # type: ignore[index]
    assert len(store["head"]["leases"]) == 1  # type: ignore[index]

    inspected = _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
    )
    assert inspected["after"]["local_authority_shadow"] == {  # type: ignore[index]
        "enabled": True,
        "mode": "file_one_way",
        "status": "enabled",
    }

    disabled = _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--clear-local-authority-shadow",
        "--execute",
    )
    assert disabled["written"] is True
    candidate_before_disabled_write = store_path.read_bytes()
    after_disable = _add_todo(
        registry,
        runtime_root,
        goal_id=goal_id,
        text="This local lifecycle write must not execute the observer.",
    )
    assert after_disable["ok"] is True
    assert after_disable["added"] is True
    assert "authority_shadow" not in after_disable
    assert store_path.read_bytes() == candidate_before_disabled_write

    baseline_registry, _baseline_state, baseline_runtime = _workspace(
        tmp_path, goal_id="shadow-cli-baseline"
    )
    baseline = _add_todo(
        baseline_registry,
        baseline_runtime,
        goal_id="shadow-cli-baseline",
        text=text,
    )
    for field in (
        "ok",
        "added",
        "already_exists",
        "metadata_updated",
        "status_changed",
        "role",
        "status",
        "task_class",
        "action_kind",
        "continuation_policy",
    ):
        assert observed[field] == baseline[field]
    assert not (baseline_runtime / "authority-shadow").exists()


def test_product_cli_candidate_failure_preserves_the_primary_lifecycle_commit(
    tmp_path: Path,
) -> None:
    goal_id = "shadow-cli-failure"
    registry, state, runtime_root = _workspace(tmp_path, goal_id=goal_id)
    _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--local-authority-shadow-file",
        "--execute",
    )
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "authority-shadow").write_text("block candidate directory", encoding="utf-8")

    result = _add_todo(
        registry,
        runtime_root,
        goal_id=goal_id,
        text="The primary write survives a candidate construction failure.",
    )

    assert result["ok"] is True
    assert result["added"] is True
    assert result["authority_shadow"]["outcome"] == "failed"  # type: ignore[index]
    assert result["authority_shadow"]["reason_code"] == "shadow_observation_failed"  # type: ignore[index]
    assert str(result["todo_id"]) in state.read_text(encoding="utf-8")


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX cross-process flock and SIGKILL")
def test_product_cli_loses_capture_between_commit_and_observer_then_refreshes_snapshot(
    tmp_path: Path,
) -> None:
    goal_id = "shadow-cli-crash-gap"
    registry, state, runtime_root = _workspace(tmp_path, goal_id=goal_id)
    _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--local-authority-shadow-file",
        "--execute",
    )
    first_text = "Primary commit that loses its post-commit observation."
    observation_lock_target = (
        runtime_root / "authority-shadow" / "file" / goal_id / "observation"
    )

    with exclusive_file_lock(observation_lock_target, operation="e2e_crash_gap"):
        process = subprocess.Popen(
            _command(
                registry,
                runtime_root,
                "todo",
                "add",
                "--goal-id",
                goal_id,
                "--role",
                "agent",
                "--text",
                first_text,
                "--task-class",
                "advancement_task",
            ),
            cwd=REPO_ROOT,
            env=_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5.0
        while first_text not in state.read_text(encoding="utf-8"):
            if time.monotonic() >= deadline:
                process.kill()
                process.communicate(timeout=5)
                raise AssertionError("primary Todo commit did not become visible")
            time.sleep(0.01)
        assert process.poll() is None
        process.kill()
        process.communicate(timeout=5)

    assert not list(
        (runtime_root / "authority-shadow" / "file" / goal_id).glob(
            "authority-store-*.json"
        )
    )

    # Allow the OS to release the observation lock fully before the recovery write.
    time.sleep(0.1)

    recovered = _add_todo(
        registry,
        runtime_root,
        goal_id=goal_id,
        text="A later primary commit refreshes the current full snapshot.",
    )
    assert recovered["authority_shadow"]["outcome"] == "captured"  # type: ignore[index]
    assert recovered["authority_shadow"]["durable_source_outbox"] is False  # type: ignore[index]
    assert recovered["authority_shadow"]["source_transaction_correlated"] is False  # type: ignore[index]
    assert recovered["authority_shadow"]["parity_verdict"] == "not_evaluated"  # type: ignore[index]
    _store_path, store = _store_document(runtime_root, goal_id)
    assert len(store["head"]["todos"]) == 2  # type: ignore[index]


def test_product_cli_runtime_root_override_keeps_one_candidate_lineage(
    tmp_path: Path,
) -> None:
    """``--runtime-root`` differs from ``common_runtime_root``: one lineage, one head.

    Every writer family of one CLI invocation must observe into the same
    candidate store: Todo add, task-lease acquire, Todo update, follow-up
    capture, and a leased completion. The registry root must not gain a
    candidate lineage of its own.
    """

    goal_id = "shadow-cli-one-root"
    registry, state, registry_runtime = _workspace(tmp_path, goal_id=goal_id)
    override_runtime = tmp_path / f"{goal_id}-override-runtime"
    assert override_runtime != registry_runtime
    _cli(
        registry,
        override_runtime,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--local-authority-shadow-file",
        "--execute",
    )

    added = _add_todo(
        registry,
        override_runtime,
        goal_id=goal_id,
        text="Every hook of this call shares one runtime root.",
    )
    todo_id = str(added["todo_id"])
    lease = _cli(
        registry,
        override_runtime,
        "task-lease",
        "acquire",
        "--goal-id",
        goal_id,
        "--todo-id",
        todo_id,
        "--owner",
        "agent-a",
        "--idempotency-key",
        "one-root-lease",
        "--ttl-seconds",
        "120",
    )
    assert lease["acquired"] is True
    updated = _cli(
        registry,
        override_runtime,
        "todo",
        "update",
        "--goal-id",
        goal_id,
        "--todo-id",
        todo_id,
        "--note",
        "Observed under the override root.",
        "--agent-id",
        "agent-a",
    )
    assert updated["changed"] is True
    followups = _cli(
        registry,
        override_runtime,
        "todo",
        "capture-followups",
        "--goal-id",
        goal_id,
        "--follow-up",
        "Verify that one goal keeps one candidate lineage.",
        "--evidence",
        "validation://one-root-followup",
    )
    assert followups["changed"] is True
    completed = _cli(
        registry,
        override_runtime,
        "todo",
        "complete",
        "--goal-id",
        goal_id,
        "--todo-id",
        todo_id,
        "--agent-id",
        "agent-a",
        "--task-lease-idempotency-key",
        "one-root-lease",
        "--task-lease-expected-version",
        str(lease["lease"]["version"]),  # type: ignore[index]
        "--evidence",
        "validation://one-root-complete",
        "--no-follow-up",
    )
    assert completed["completed"] is True

    responses = {
        "todo add": added,
        "task-lease acquire": lease,
        "todo update": updated,
        "todo capture-followups": followups,
        "todo complete": completed,
    }
    for label, payload in responses.items():
        evidence = payload["authority_shadow"]
        assert evidence["outcome"] == "captured", label  # type: ignore[index]
    identities = {payload["authority_shadow"]["store_identity"] for payload in responses.values()}  # type: ignore[index]
    assert len(identities) == 1
    store_path, store = _store_document(override_runtime, goal_id)
    assert store["store_identity"] == identities.pop()
    assert store["cursor"] == str(len(responses))
    head_todo_ids = {todo["todo_id"] for todo in store["head"]["todos"]}  # type: ignore[index]
    assert todo_id in head_todo_ids
    assert len(head_todo_ids) == 2
    [lease_record] = store["head"]["leases"]  # type: ignore[index]
    assert lease_record["todo_id"] == todo_id
    assert lease_record["status"] == "released"
    assert (override_runtime / "goals" / goal_id / "task-leases" / f"{todo_id}.json").exists()
    assert not (registry_runtime / "authority-shadow").exists()
    assert not (registry_runtime / "goals" / goal_id / "task-leases").exists()
    assert store_path.is_relative_to(override_runtime)
    assert todo_id in state.read_text(encoding="utf-8")


def test_product_cli_authority_shadow_status_and_drain_read_without_creating_lineage(
    tmp_path: Path,
) -> None:
    goal_id = "shadow-cli-drain"
    registry, _state, runtime_root = _workspace(tmp_path, goal_id=goal_id)

    default_off = _cli(registry, runtime_root, "authority-shadow", "status", "--goal-id", goal_id)
    assert default_off["ok"] is True
    assert default_off["schema_version"] == "loopx_authority_shadow_cli_v0"
    assert default_off["config"] == {"enabled": False, "mode": None, "status": "disabled"}  # type: ignore[index]
    assert default_off["candidate"]["status"] == "missing"  # type: ignore[index]
    assert default_off["store_bytes"] == 0
    assert not (runtime_root / "authority-shadow").exists()
    idle = _cli(registry, runtime_root, "authority-shadow", "drain", "--goal-id", goal_id)
    assert idle["ok"] is True
    assert idle["outcome"] == "nothing_pending"
    assert idle["drained_count"] == 0
    assert idle["config_enabled"] is False
    assert not (runtime_root / "authority-shadow").exists()

    _cli(
        registry,
        runtime_root,
        "configure-goal",
        "--goal-id",
        goal_id,
        "--local-authority-shadow-file",
        "--execute",
    )
    observed = _add_todo(registry, runtime_root, goal_id=goal_id, text="Observed through the v0 path.")
    assert observed["authority_shadow"]["outcome"] == "captured"  # type: ignore[index]

    status = _cli(registry, runtime_root, "authority-shadow", "status", "--goal-id", goal_id)
    assert status["ok"] is True
    assert status["config"]["status"] == "enabled"  # type: ignore[index]
    assert status["outbox"]["todos"]["committed_pending"] == 0  # type: ignore[index]
    assert status["outbox"]["leases"]["prepared_only"] == 0  # type: ignore[index]
    candidate = status["candidate"]
    assert candidate["status"] == "loaded"  # type: ignore[index]
    assert candidate["cursor"] == "1"  # type: ignore[index]
    assert candidate["head_schema_version"] == "loopx_local_authority_shadow_projection_v0"  # type: ignore[index]
    assert candidate["codec_agreement"] is True  # type: ignore[index]
    assert candidate["partitions"] == {"todos": None, "leases": None}  # type: ignore[index]
    assert status["store_bytes"] > 0
    assert status["retention_pressure"] is False
    assert str(runtime_root) not in json.dumps(status)

    drained = _cli(registry, runtime_root, "authority-shadow", "drain", "--goal-id", goal_id)
    assert drained["ok"] is True
    assert drained["outcome"] == "nothing_pending"
    assert drained["config_enabled"] is True
    _store_path, store = _store_document(runtime_root, goal_id)
    assert store["cursor"] == "1"
