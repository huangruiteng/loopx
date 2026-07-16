from __future__ import annotations

import json
from pathlib import Path

from loopx.capabilities.reward_memory.experiment import (
    resolve_reward_memory_experiment,
)
from loopx.cli import main


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_FIXTURE = REPO_ROOT / "examples/fixtures/reward-memory-ingest-event.public.json"
SCOPED_PUBLIC_FIXTURE = (
    REPO_ROOT
    / "examples/fixtures/reward-memory-scoped-feedback-ingest.public.json"
)


def _experiment(
    tmp_path: Path,
    fixture_path: Path = PUBLIC_FIXTURE,
) -> tuple[Path, Path, Path]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    project = tmp_path / "project"
    config_path = project / ".loopx/config/reward-memory/experiment.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "reward_memory_experiment_config_v0",
                "adapter": fixture["adapter"],
                "corpus": fixture["corpus"],
                "standing_policy": fixture["standing_policy"],
                "provider_binding": fixture["provider_binding"],
            }
        ),
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goals": [
                    {
                        "id": "reward-memory-goal",
                        "repo": str(project),
                        "coordination": {
                            "registered_agents": ["pilot", "meta"],
                        },
                        "control_plane": {
                            "reward_memory": {
                                "enabled": True,
                                "experimental": True,
                                "config_path": (
                                    ".loopx/config/reward-memory/experiment.json"
                                ),
                                "enabled_agents": ["pilot"],
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "adapter": fixture["adapter"],
                "event": fixture["event"],
                "observed_at": fixture["observed_at"],
            }
        ),
        encoding="utf-8",
    )
    return registry_path, event_path, fixture_path


def _run(capsys, registry_path: Path, *args: str) -> tuple[int, dict[str, object]]:
    result = main(
        [
            "--registry",
            str(registry_path),
            "--format",
            "json",
            *args,
        ]
    )
    output = capsys.readouterr().out
    return result, json.loads(output)


def test_status_is_agent_scoped_and_public_safe(tmp_path: Path) -> None:
    registry_path, _, _ = _experiment(tmp_path)

    allowed, config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )
    denied, denied_config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="meta",
    )

    assert allowed["status"] == "available"
    assert allowed["automatic_ingest"] is False
    assert allowed["automatic_recall"] is False
    assert "config_path" not in allowed
    assert config is not None
    assert denied["status"] == "agent_not_enabled"
    assert denied_config is None


def test_registry_cannot_enable_experiment_without_explicit_marker(
    tmp_path: Path,
) -> None:
    registry_path, _, _ = _experiment(tmp_path)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["control_plane"]["reward_memory"].pop("experimental")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    status, config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )

    assert status["status"] == "disabled"
    assert status["experimental"] is False
    assert config is None


def test_configured_ingest_accepts_only_compact_event_and_stays_dry_run(
    tmp_path: Path, capsys
) -> None:
    registry_path, event_path, _ = _experiment(tmp_path)

    result, receipt = _run(
        capsys,
        registry_path,
        "reward-memory",
        "ingest-event",
        "--goal-id",
        "reward-memory-goal",
        "--agent-id",
        "pilot",
        "--input",
        str(event_path),
    )

    assert result == 0
    assert receipt["status"] == "planned"
    assert receipt["external_writes_performed"] is False
    assert receipt["experiment"]["available"] is True
    assert "provider_binding" not in receipt["experiment"]


def test_execute_cannot_bypass_experiment_route(tmp_path: Path, capsys) -> None:
    registry_path, _, full_fixture = _experiment(tmp_path)

    result, receipt = _run(
        capsys,
        registry_path,
        "reward-memory",
        "ingest-event",
        "--input",
        str(full_fixture),
        "--execute",
    )

    assert result == 2
    assert receipt["status"] == "invalid_request"
    assert "requires an enabled experiment route" in receipt["error"]


def test_legacy_full_packet_remains_available_for_no_write_evaluation(
    tmp_path: Path, capsys
) -> None:
    registry_path, _, full_fixture = _experiment(tmp_path)

    result, receipt = _run(
        capsys,
        registry_path,
        "reward-memory",
        "ingest-event",
        "--input",
        str(full_fixture),
    )

    assert result == 0
    assert receipt["status"] == "planned"
    assert receipt["external_writes_performed"] is False


def test_scoped_feedback_uses_the_shared_ingest_core(tmp_path: Path, capsys) -> None:
    registry_path, event_path, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)

    status, config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )
    result, receipt = _run(
        capsys,
        registry_path,
        "reward-memory",
        "ingest-event",
        "--goal-id",
        "reward-memory-goal",
        "--agent-id",
        "pilot",
        "--input",
        str(event_path),
    )

    assert status["status"] == "available"
    assert status["adapter"] == "scoped_feedback"
    assert config is not None
    assert result == 0
    assert receipt["status"] == "planned"
    assert receipt["guard"]["passed"] is True
    assert receipt["adapter_schema_version"] == (
        "scoped_feedback_reward_memory_candidate_adapter_v0"
    )
    assert receipt["next_reward_memory_call"] == "explicit_function_boundary_recall"
    assert "issue_ref" not in receipt
    assert receipt["external_writes_performed"] is False


def test_configured_route_rejects_adapter_override(tmp_path: Path, capsys) -> None:
    registry_path, event_path, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    source = json.loads(event_path.read_text(encoding="utf-8"))
    source["adapter"] = "issue_fix_maintainer_feedback"
    event_path.write_text(json.dumps(source), encoding="utf-8")

    result, receipt = _run(
        capsys,
        registry_path,
        "reward-memory",
        "ingest-event",
        "--goal-id",
        "reward-memory-goal",
        "--agent-id",
        "pilot",
        "--input",
        str(event_path),
    )

    assert result == 2
    assert receipt["status"] == "invalid_request"
    assert "does not match the configured route" in receipt["error"]


def test_scoped_feedback_rejects_unmodelled_event_fields(
    tmp_path: Path, capsys
) -> None:
    registry_path, event_path, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    source = json.loads(event_path.read_text(encoding="utf-8"))
    source["event"]["raw_comment"] = "not accepted"
    event_path.write_text(json.dumps(source), encoding="utf-8")

    result, receipt = _run(
        capsys,
        registry_path,
        "reward-memory",
        "ingest-event",
        "--goal-id",
        "reward-memory-goal",
        "--agent-id",
        "pilot",
        "--input",
        str(event_path),
    )

    assert result == 2
    assert receipt["status"] == "invalid_request"
    assert "raw_comment" in receipt["error"]
