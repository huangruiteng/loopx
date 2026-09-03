"""Stage 2 governed goal amendment proposal admission tests.

Stage 2 is proposal only: admission validates and retains
``goal_amendment_proposal_v0`` with zero canonical effect — no goal state
write, no frontier change, no append into the canonical state event log.
The tests below prove both directions: valid proposals are retained
(append-only journal, idempotent replay), and every admission-blocking
defect fails closed without retaining anything.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from loopx.control_plane.effect_runtime import (
    EffectRuntimeRejected,
    effect_runtime_result,
)
from loopx.control_plane.goals.goal_amendment_proposal import (
    admit_goal_amendment_proposal,
    read_goal_amendment_proposal_journal,
)
from loopx.event_sourced_state import (
    AppendOnlyStateEventStore,
    TODO_ADDED,
    make_state_event,
)

GOAL_ID = "goal-stage2"
AGENTS = ("agent-a", "agent-b")
EVENT_LOG_NAME = "events.jsonl"
BASE_DIGEST = "sha256:" + "a" * 64

STATE_TEXT = "\n".join(
    [
        "---",
        "status: active",
        "updated_at: 2026-09-01T00:00:00+00:00",
        "---",
        "",
        "# Stage 2 Amendment Fixture",
        "",
        "## Next Action",
        "",
        "Shared compatibility prose; it is never an input to admission.",
        "",
    ]
)


def _write_fixture(
    root: Path,
    *,
    events: list[dict[str, str]] | None = None,
) -> dict[str, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_relative = Path(".codex") / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file = project / state_relative
    state_file.parent.mkdir(parents=True)
    state_file.write_text(STATE_TEXT, encoding="utf-8")

    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "shared-goal-alignment-stage2",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_relative),
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": list(AGENTS),
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if events:
        store = AppendOnlyStateEventStore(state_file.with_name(EVENT_LOG_NAME))
        for event in events:
            store.append(
                make_state_event(
                    event_id=event["event_id"],
                    goal_id=GOAL_ID,
                    event_type=TODO_ADDED,
                    actor_agent_id=event["actor_agent_id"],
                    refs={"todo_id": event["todo_id"]},
                    payload={"text": f"Fixture event for {event['todo_id']}."},
                )
            )
    else:
        runtime.mkdir(parents=True, exist_ok=True)

    return {
        "project": project,
        "runtime": runtime,
        "registry": registry_path,
        "state_file": state_file,
    }


def _default_events() -> list[dict[str, str]]:
    return [
        {
            "event_id": "evt_stage2_001",
            "actor_agent_id": "agent-a",
            "todo_id": "todo_stage2_a",
        },
        {
            "event_id": "evt_stage2_002",
            "actor_agent_id": "agent-b",
            "todo_id": "todo_stage2_b",
        },
        {
            "event_id": "evt_stage2_003",
            "actor_agent_id": "agent-a",
            "todo_id": "todo_stage2_c",
        },
    ]


def _proposal(overrides: dict[str, object] | None = None) -> dict[str, object]:
    proposal: dict[str, object] = {
        "schema_version": "goal_amendment_proposal_v0",
        "proposal_id": "gap_stage2_001",
        "goal_id": GOAL_ID,
        "proposer_agent_id": "agent-a",
        "amendment_class": "shared_acceptance",
        "base_goal_revision": 3,
        "base_intent_digest": BASE_DIGEST,
        "retained": ["original outcome remains unchanged"],
        "changed": ["acceptance now requires the recovered receipt"],
        "stopped": [],
        "evidence_refs": ["evidence:evt_stage2_001"],
        "affected_todo_ids": ["todo_stage2_a", "todo_stage2_b"],
        "replan_obligation_id": "replan:stage2-001",
    }
    if overrides:
        proposal.update(overrides)
    return proposal


def _admit(
    paths: dict[str, Path],
    proposal: dict[str, object],
):
    return admit_goal_amendment_proposal(
        proposal=proposal,
        project=paths["project"],
    )


def _canonical_tree_snapshot(paths: dict[str, Path]) -> dict[str, bytes]:
    """Snapshot every runtime byte except the proposal journal sidecars.

    Admission must leave the canonical revision carrier (the state event
    log), the goal state file, and every other runtime artifact untouched;
    only ``amendment-proposals/`` and the advisory lock sidecars may move.
    """

    snapshot: dict[str, bytes] = {}
    for candidate in sorted(paths["runtime"].rglob("*")):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(paths["runtime"]).as_posix()
        if "/amendment-proposals/" in relative:
            continue
        snapshot[relative] = candidate.read_bytes()
    return snapshot


def _proposal_journal(paths: dict[str, Path]) -> Path:
    return (
        paths["runtime"]
        / "goals"
        / GOAL_ID
        / "amendment-proposals"
        / "journal.jsonl"
    )


def test_admits_and_retains_a_well_formed_proposal(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(paths, _proposal())

    assert record["schema_version"] == "goal_amendment_proposal_admission_v0"
    assert record["proposal_id"] == "gap_stage2_001"
    assert record["goal_id"] == GOAL_ID
    assert record["proposer_agent_id"] == "agent-a"
    assert record["amendment_class"] == "shared_acceptance"
    assert record["admission"] == "admitted"
    assert record["admission_facts"] == []
    assert record["canonical_effect"] == "none"
    assert record["journal_append_sequence"] == 1
    assert record["recorded_at"]
    rows = read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )
    assert [row["proposal_id"] for row in rows] == ["gap_stage2_001"]


def test_proposal_digest_matches_the_python_canonical_recipe(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal()

    record = _admit(paths, proposal)

    encoded = json.dumps(
        proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
    assert record["proposal_digest"] == expected


def test_stale_base_is_retained_with_needs_rebase(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(paths, _proposal({"base_goal_revision": 1}))

    assert record["admission"] == "needs_rebase"
    assert record["admission_facts"] == ["base_revision_behind_derived_head"]
    assert record["canonical_effect"] == "none"
    rows = read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )
    assert len(rows) == 1, "a stale proposal must still be retained"


def test_future_base_fails_closed_without_retention(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="ahead of the derived goal head"):
        _admit(paths, _proposal({"base_goal_revision": 99}))

    assert read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    ) == []


def test_unknown_amendment_class_is_rejected_without_retention(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="amendment class is unsupported"):
        _admit(paths, _proposal({"amendment_class": "emergency_powers"}))

    assert read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    ) == []


def test_evidence_refs_over_budget_are_rejected(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="exceeds 8 pointers"):
        _admit(
            paths,
            _proposal(
                {
                    "evidence_refs": [
                        f"evidence:evt_stage2_{index}" for index in range(9)
                    ]
                }
            ),
        )

    assert read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    ) == []


def test_unregistered_proposer_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="not registered"):
        _admit(paths, _proposal({"proposer_agent_id": "agent-z"}))


def test_unknown_goal_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="not registered"):
        _admit(paths, _proposal({"goal_id": "goal-unknown"}))


def test_journal_is_append_only_and_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    journal = (
        paths["runtime"]
        / "goals"
        / GOAL_ID
        / "amendment-proposals"
        / "journal.jsonl"
    )

    _admit(paths, _proposal())
    first_snapshot = journal.read_text(encoding="utf-8")

    replay = _admit(paths, _proposal())
    assert replay["proposal_id"] == "gap_stage2_001"
    assert journal.read_text(encoding="utf-8") == first_snapshot

    _admit(
        paths,
        _proposal(
            {
                "proposal_id": "gap_stage2_002",
                "replan_obligation_id": "replan:stage2-002",
            }
        ),
    )
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == first_snapshot.strip(), "append-only: row 1 unchanged"
    rows = read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )
    assert [row["journal_append_sequence"] for row in rows] == [1, 2]


def test_conflicting_proposal_id_replay_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    _admit(paths, _proposal())

    with pytest.raises(ValueError, match="conflicting proposal_id"):
        _admit(
            paths,
            _proposal({"changed": ["a different amendment content"]}),
        )

    rows = read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )
    assert len(rows) == 1
    assert rows[0]["changed"] == ["acceptance now requires the recovered receipt"]


def test_markdown_basis_admits_with_unverifiable_fact(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=None)

    record = _admit(paths, _proposal({"base_goal_revision": 5}))

    assert record["admission"] == "admitted"
    assert record["admission_facts"] == ["base_revision_unverifiable"]
    assert record["canonical_effect"] == "none"


def test_admission_has_zero_canonical_effect(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    event_log = paths["state_file"].with_name(EVENT_LOG_NAME)
    before_state = paths["state_file"].read_bytes()
    before_events = event_log.read_bytes()
    before_registry = paths["registry"].read_bytes()

    _admit(paths, _proposal())
    _admit(
        paths,
        _proposal(
            {
                "proposal_id": "gap_stage2_002",
                "replan_obligation_id": "replan:stage2-002",
            }
        ),
    )

    assert paths["state_file"].read_bytes() == before_state
    assert event_log.read_bytes() == before_events
    assert paths["registry"].read_bytes() == before_registry
    assert read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )[0]["canonical_effect"] == "none"


def test_registered_effect_method_rejects_an_illegal_request() -> None:
    # Direct call through the managed TS runtime: a digest that violates
    # the sha256 contract is a request rejection, not an admission record.
    with pytest.raises(EffectRuntimeRejected) as excinfo:
        effect_runtime_result(
            "goal.amendment_proposal.admit",
            {
                "schema_version": "goal_amendment_proposal_request_v0",
                "proposal": _proposal({"base_intent_digest": "md5:zz"}),
                "derived_basis": {
                    "goal_revision": 3,
                    "revision_basis": "state_event_log",
                    "intent_digest": "sha256:" + "b" * 64,
                },
            },
        )
    assert excinfo.value.error_kind == "request_rejected"


def test_concurrent_admissions_serialize_journal_appends(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    repo_root = Path(__file__).resolve().parents[2]
    child_code = """
import json
import sys
from pathlib import Path

from loopx.control_plane.goals.goal_amendment_proposal import (
    admit_goal_amendment_proposal,
)

record = admit_goal_amendment_proposal(
    proposal=json.loads(sys.argv[2]),
    project=Path(sys.argv[1]),
)
print(record["proposal_id"], record["journal_append_sequence"])
"""
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo_root) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    overrides = (
        {"proposal_id": "gap_stage2_p1", "replan_obligation_id": "replan:stage2-p1"},
        {"proposal_id": "gap_stage2_p2", "replan_obligation_id": "replan:stage2-p2"},
    )
    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                str(paths["project"]),
                json.dumps(_proposal(proposal_overrides)),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        for proposal_overrides in overrides
    ]
    try:
        for child in children:
            stdout, stderr = child.communicate(timeout=60)
            assert child.returncode == 0, stderr
    finally:
        for child in children:
            if child.poll() is None:  # pragma: no cover - failure cleanup
                child.kill()
                child.wait()

    rows = read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )
    # The cross-process lock must serialize both appends: exactly one row
    # per proposal, no interleaved JSON, and unique sequence numbers.
    assert sorted(row["proposal_id"] for row in rows) == [
        "gap_stage2_p1",
        "gap_stage2_p2",
    ]
    assert sorted(row["journal_append_sequence"] for row in rows) == [1, 2]


def test_corrupt_journal_line_fails_closed_and_retains_nothing(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    _admit(paths, _proposal())
    journal = _proposal_journal(paths)
    with journal.open("a", encoding="utf-8") as stream:
        stream.write('{"schema_version": "goal_amendment_proposal_admis\n')
    corrupted = journal.read_bytes()

    with pytest.raises(ValueError, match="invalid proposal journal JSONL"):
        _admit(
            paths,
            _proposal(
                {
                    "proposal_id": "gap_stage2_002",
                    "replan_obligation_id": "replan:stage2-002",
                }
            ),
        )
    with pytest.raises(ValueError, match="invalid proposal journal JSONL"):
        read_goal_amendment_proposal_journal(
            runtime_root=paths["runtime"],
            goal_id=GOAL_ID,
        )

    assert journal.read_bytes() == corrupted


def test_retention_does_not_advance_the_derived_head(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    before_tree = _canonical_tree_snapshot(paths)

    first = _admit(paths, _proposal())
    second = _admit(
        paths,
        _proposal(
            {
                "proposal_id": "gap_stage2_002",
                "replan_obligation_id": "replan:stage2-002",
            }
        ),
    )

    assert first["admission"] == "admitted"
    assert first["admission_facts"] == []
    # The first journal append must not move the canonical head the second
    # proposal reports against: retention lives outside the revision
    # carrier, so the same base stays fresh (not needs_rebase) and every
    # non-journal runtime byte is unchanged.
    assert second["admission"] == "admitted"
    assert second["admission_facts"] == []
    assert _canonical_tree_snapshot(paths) == before_tree


def test_needs_rebase_admission_has_zero_canonical_effect(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    before_tree = _canonical_tree_snapshot(paths)

    record = _admit(paths, _proposal({"base_goal_revision": 1}))

    assert record["admission"] == "needs_rebase"
    assert record["admission_facts"] == ["base_revision_behind_derived_head"]
    assert _canonical_tree_snapshot(paths) == before_tree
    rows = read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )
    assert [row["admission"] for row in rows] == ["needs_rebase"]
    assert rows[0]["canonical_effect"] == "none"
