from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from loopx.capabilities.reward_memory.experiment import (
    resolve_reward_memory_experiment,
    resolve_reward_memory_surface_config,
)
from loopx.cli import main


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_FIXTURE = REPO_ROOT / "examples/fixtures/reward-memory-ingest-event.public.json"
SCOPED_PUBLIC_FIXTURE = (
    REPO_ROOT / "examples/fixtures/reward-memory-scoped-feedback-ingest.public.json"
)


def _experiment(
    tmp_path: Path,
    fixture_path: Path = PUBLIC_FIXTURE,
) -> tuple[Path, Path, Path]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    project = tmp_path / "project"
    config_path = project / ".loopx/config/reward-memory/experiment.json"
    config_path.parent.mkdir(parents=True)
    corpus_id = fixture["corpus"]["corpus_id"]
    surface_id = fixture["standing_policy"]["scope"]["surface_ids"][0]
    provider_binding = fixture["provider_binding"]
    project_provider_binding = {
        key: value
        for key, value in provider_binding.items()
        if key not in {"corpus_id", "scope_ref"}
    }
    project_provider_binding["corpus_scopes"] = [
        {"corpus_id": corpus_id, "scope_ref": provider_binding["scope_ref"]}
    ]
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "reward_memory_experiment_config_v1",
                "project_provider_binding": project_provider_binding,
                "corpora": [
                    {
                        "corpus": fixture["corpus"],
                        "standing_policy": fixture["standing_policy"],
                    }
                ],
                "surfaces": [
                    {
                        "surface_id": surface_id,
                        "adapter": fixture["adapter"],
                        "corpus_ids": [corpus_id],
                        "ingest_corpus_id": corpus_id,
                        "recall_profile": {
                            "profile_id": "fixture_function_boundary_v1",
                            "mode": "function_boundary",
                            "max_queries": 1,
                            "limit": 5,
                        },
                    }
                ],
                "automation": {
                    "automatic_recall": False,
                    "automatic_ingest": False,
                    "fail_open": True,
                },
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


def _v1_config() -> dict[str, object]:
    fixture = json.loads(SCOPED_PUBLIC_FIXTURE.read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = []
    scopes: list[dict[str, str]] = []
    for corpus_id, surface_id in (
        ("reviewer_policy_primary", "reviewer_artifact.summary"),
        ("reviewer_policy_overlay", "reviewer_artifact.summary"),
        ("patch_policy_separate", "issue_fix.patch_planning"),
    ):
        corpus = copy.deepcopy(fixture["corpus"])
        policy = copy.deepcopy(fixture["standing_policy"])
        scope_ref = f"viking://resources/reward-memory/{corpus_id}"
        corpus["corpus_id"] = corpus_id
        corpus["scope"]["surface_ids"] = [surface_id]
        corpus["provider_scope_ref_digest"] = hashlib.sha256(
            scope_ref.encode("utf-8")
        ).hexdigest()[:16]
        policy["policy_id"] = f"policy:example:{corpus_id}"
        policy["scope"]["surface_ids"] = [surface_id]
        entries.append({"corpus": corpus, "standing_policy": policy})
        scopes.append({"corpus_id": corpus_id, "scope_ref": scope_ref})
    return {
        "schema_version": "reward_memory_experiment_config_v1",
        "project_provider_binding": {
            "provider_id": "openviking",
            "namespace": "reward_memory",
            "timeout_seconds": 30,
            "minimum_provider_version": "0.4.9",
            "corpus_scopes": scopes,
        },
        "corpora": entries,
        "surfaces": [
            {
                "surface_id": "reviewer_artifact.summary",
                "adapter": "scoped_feedback",
                "corpus_ids": [
                    "reviewer_policy_primary",
                    "reviewer_policy_overlay",
                ],
                "ingest_corpus_id": "reviewer_policy_primary",
                "recall_profile": {
                    "profile_id": "reviewer_summary_v1",
                    "mode": "function_boundary",
                    "max_queries": 1,
                    "limit": 4,
                },
            },
            {
                "surface_id": "issue_fix.patch_planning",
                "adapter": "issue_fix_maintainer_feedback",
                "corpus_ids": ["patch_policy_separate"],
                "ingest_corpus_id": "patch_policy_separate",
                "recall_profile": {
                    "profile_id": "patch_planning_v1",
                    "mode": "bounded_agentic_search",
                    "max_queries": 2,
                    "limit": 5,
                },
            },
        ],
        "automation": {
            "automatic_recall": True,
            "automatic_ingest": True,
            "fail_open": True,
        },
    }


def _write_v1_config(registry_path: Path, config: dict[str, object]) -> None:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    project = Path(registry["goals"][0]["repo"])
    config_path = project / ".loopx/config/reward-memory/experiment.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")


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
    assert allowed["config_schema_version"] == ("reward_memory_experiment_config_v1")
    assert "config_path" not in allowed
    assert config is not None
    assert not {
        "adapter",
        "corpus",
        "standing_policy",
        "provider_binding",
    }.intersection(config)
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


def test_v0_config_is_rejected_fail_open(tmp_path: Path) -> None:
    registry_path, _, fixture_path = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    project = Path(registry["goals"][0]["repo"])
    config_path = project / ".loopx/config/reward-memory/experiment.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
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

    status, config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )

    assert status["status"] == "config_invalid"
    assert status["automatic_ingest"] is False
    assert status["automatic_recall"] is False
    assert status["fail_open"] is True
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


def test_v1_uses_one_project_provider_and_explicit_surface_corpus_sets(
    tmp_path: Path,
) -> None:
    registry_path, _, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    _write_v1_config(registry_path, _v1_config())

    status, config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )
    assert config is not None
    route = resolve_reward_memory_surface_config(config, "reviewer_artifact.summary")

    assert status["automatic_ingest"] is True
    assert status["automatic_recall"] is True
    assert status["provider_id"] == "openviking"
    assert status["corpus_count"] == 3
    assert route["selection"] == {
        "mode": "explicit_surface_corpus_ids",
        "global_corpus_scan": False,
        "corpus_ids": ["reviewer_policy_primary", "reviewer_policy_overlay"],
    }
    assert [item["corpus"]["corpus_id"] for item in route["recall_corpora"]] == [
        "reviewer_policy_primary",
        "reviewer_policy_overlay",
    ]
    assert route["corpus"]["corpus_id"] == "reviewer_policy_primary"
    assert route["recall_profile"]["profile_id"] == "reviewer_summary_v1"
    assert "scope_ref" not in json.dumps(status)


def test_v1_configured_ingest_selects_the_event_surface(tmp_path: Path, capsys) -> None:
    registry_path, event_path, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    _write_v1_config(registry_path, _v1_config())

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
    assert receipt["experiment"]["automatic_ingest"] is True
    assert receipt["experiment"]["automatic_recall"] is True
    assert receipt["experiment"]["corpus_count"] == 3
    assert "scope_ref" not in json.dumps(receipt["experiment"])


@pytest.mark.parametrize(
    "dimension",
    ["class", "authority", "privacy", "freshness", "lifecycle"],
)
def test_v1_rejects_incompatible_surface_corpus_before_provider(
    tmp_path: Path,
    dimension: str,
) -> None:
    registry_path, _, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    config = _v1_config()
    second = config["corpora"][1]
    corpus = second["corpus"]
    policy = second["standing_policy"]
    if dimension == "class":
        corpus["class_id"] = "soft_preference"
        policy["allowed_target_classes"] = ["soft_preference"]
    elif dimension == "authority":
        corpus["read_authority"] = "authority_scoped"
    elif dimension == "privacy":
        corpus["privacy"]["visibility"] = "workspace"
    elif dimension == "freshness":
        corpus["freshness"] = {"mode": "time_bound", "max_age_seconds": 300}
    else:
        corpus["lifecycle"] = {
            "state": "retired",
            "supersedes": [],
            "retirement_reason": "fixture",
        }
    _write_v1_config(registry_path, config)

    status, normalized = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )

    assert status["status"] == "config_invalid"
    assert status["automatic_ingest"] is False
    assert status["automatic_recall"] is False
    assert status["fail_open"] is True
    assert normalized is None


def test_v1_rejects_unknown_surface_and_adapter_override(tmp_path: Path) -> None:
    registry_path, _, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    _write_v1_config(registry_path, _v1_config())
    _, config = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )
    assert config is not None

    with pytest.raises(ValueError, match="surface is not configured"):
        resolve_reward_memory_surface_config(config, "unknown.surface")
    with pytest.raises(ValueError, match="does not match the configured route"):
        resolve_reward_memory_surface_config(
            config,
            "reviewer_artifact.summary",
            adapter="issue_fix_maintainer_feedback",
        )


def test_v1_rejects_surface_not_authorized_by_selected_policy(
    tmp_path: Path,
) -> None:
    registry_path, _, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    config = _v1_config()
    second = config["corpora"][1]
    second["corpus"]["scope"]["surface_ids"].append("issue_fix.patch_planning")
    second["standing_policy"]["scope"]["surface_ids"] = ["issue_fix.patch_planning"]
    _write_v1_config(registry_path, config)

    status, normalized = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )

    assert status["status"] == "config_invalid"
    assert status["automatic_ingest"] is False
    assert status["automatic_recall"] is False
    assert normalized is None


def test_v1_rejects_non_fail_open_automation(tmp_path: Path) -> None:
    registry_path, _, _ = _experiment(tmp_path, SCOPED_PUBLIC_FIXTURE)
    config = _v1_config()
    config["automation"]["fail_open"] = False
    _write_v1_config(registry_path, config)

    status, normalized = resolve_reward_memory_experiment(
        registry_path=registry_path,
        goal_id="reward-memory-goal",
        agent_id="pilot",
    )

    assert status["status"] == "config_invalid"
    assert status["automatic_ingest"] is False
    assert status["automatic_recall"] is False
    assert normalized is None
