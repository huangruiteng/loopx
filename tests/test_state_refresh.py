from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.state_refresh import refresh_state_run


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    registry = tmp_path / "registry.json"
    runtime = tmp_path / "runtime"
    state = tmp_path / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# Fixture Goal",
                "",
                "## Next Action",
                "",
                "- Continue the fixture.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": "fixture-goal",
                        "status": "active",
                        "repo": str(tmp_path),
                        "state_file": state.name,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return registry, runtime, state


def _refresh(
    tmp_path: Path,
    *,
    classification: str = "fixture_progress",
    next_action: str | None = None,
    sync_global: bool = False,
    turn_effect_key: str | None = "sha256:" + "a" * 64 + ":durable_writeback",
) -> dict[str, object]:
    if not (tmp_path / "registry.json").exists():
        registry, runtime, state = _fixture(tmp_path)
    else:
        registry = tmp_path / "registry.json"
        runtime = tmp_path / "runtime"
        state = tmp_path / "ACTIVE_GOAL_STATE.md"
    return refresh_state_run(
        registry_path=registry,
        runtime_root_override=str(runtime),
        goal_id="fixture-goal",
        project=tmp_path,
        state_file=state,
        classification=classification,
        recommended_action="Continue the public fixture.",
        next_action=next_action,
        progress_scope="goal",
        dry_run=False,
        sync_global=sync_global,
        turn_effect_key=turn_effect_key,
    )


def test_refresh_state_deduplicates_same_turn_effect_key(tmp_path: Path) -> None:
    first = _refresh(tmp_path)
    replay = _refresh(tmp_path)
    index_path = (
        tmp_path / "runtime" / "goals" / "fixture-goal" / "runs" / "index.jsonl"
    )
    index_record = json.loads(index_path.read_text(encoding="utf-8"))
    run_record = json.loads(Path(str(first["json_path"])).read_text(encoding="utf-8"))

    assert first["appended"] is True
    assert replay["appended"] is False
    assert replay["idempotent"] is True
    assert replay["json_path"] == first["json_path"]
    assert replay["markdown_path"] == first["markdown_path"]
    assert run_record["turn_effect_key"] == first["turn_effect_key"]
    assert index_record["turn_effect_key"] == first["turn_effect_key"]
    assert run_record["effect_input_hash"] == first["effect_input_hash"]
    assert index_record["effect_input_hash"] == first["effect_input_hash"]
    assert len(index_path.read_text(encoding="utf-8").splitlines()) == 1


def test_refresh_state_rejects_turn_effect_key_content_drift(tmp_path: Path) -> None:
    _refresh(tmp_path)

    with pytest.raises(ValueError, match="turn effect key conflict"):
        _refresh(tmp_path, classification="different_progress")

    index_path = (
        tmp_path / "runtime" / "goals" / "fixture-goal" / "runs" / "index.jsonl"
    )
    records = [json.loads(line) for line in index_path.read_text().splitlines()]
    assert len(records) == 1


def test_refresh_state_deduplicates_same_normalized_turn_effect_content(
    tmp_path: Path,
) -> None:
    first = _refresh(tmp_path, next_action="Continue the fixture.")
    replay = _refresh(tmp_path, next_action="  Continue   the fixture.  ")

    assert first["appended"] is True
    assert replay["appended"] is False
    assert replay["idempotent"] is True
    assert replay["json_path"] == first["json_path"]


@pytest.mark.parametrize("effect_key", ["unsafe key", "x" * 161])
def test_refresh_state_rejects_unsafe_turn_effect_key(
    tmp_path: Path,
    effect_key: str,
) -> None:
    with pytest.raises(ValueError, match="turn_effect_key must be a public-safe token"):
        _refresh(tmp_path, turn_effect_key=effect_key)


def test_unkeyed_refresh_keeps_local_receipt_when_global_sync_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _registry, runtime, _state = _fixture(tmp_path)
    monkeypatch.setattr(
        "loopx.state_refresh.resolve_runtime_projection_route",
        lambda **_kwargs: {
            "status": "single_runtime",
            "target_runtime_root": str(runtime),
        },
    )

    def raise_sync_error(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("fixture global sync failure")

    monkeypatch.setattr(
        "loopx.state_refresh.sync_project_registry_to_global",
        raise_sync_error,
    )

    with pytest.raises(RuntimeError, match="fixture global sync failure"):
        _refresh(tmp_path, sync_global=True, turn_effect_key=None)

    index_path = runtime / "goals" / "fixture-goal" / "runs" / "index.jsonl"
    assert len(index_path.read_text(encoding="utf-8").splitlines()) == 1
