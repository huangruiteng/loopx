"""Stage 2 governed goal amendment proposal admission tests.

Stage 2 is proposal only: admission validates and retains
``goal_amendment_proposal_v0`` with zero canonical effect — no goal state
write, no frontier change, no append into the canonical state event log.
The tests below prove both directions: valid proposals are retained
(append-only journal, idempotent replay), and every admission-blocking
defect fails closed without retaining anything.

Causal binding coverage: the fixture state carries real parsed Todo rows
and the fixture replan ids are derived through
``ensure_replan_novelty_policy``, so an admission never succeeds on a
merely well-shaped id — it must name an actual open obligation of the
same Goal and actual open Todos of that Goal.
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
from loopx.control_plane.goals.shared_goal_alignment import (
    project_shared_goal_alignment,
)
from loopx.control_plane.todos.active_state_todo_parser import (
    parse_active_state_todos,
)
from loopx.control_plane.work_items.autonomous_replan_obligation import (
    ensure_replan_novelty_policy,
)
from loopx.event_sourced_state import (
    AppendOnlyStateEventStore,
    TODO_ADDED,
    make_state_event,
)

GOAL_ID = "goal-stage2"
OTHER_GOAL_ID = "goal-stage2-peer"
AGENTS = ("agent-a", "agent-b")
EVENT_LOG_NAME = "events.jsonl"
MISMATCHED_DIGEST = "sha256:" + "a" * 64

STATE_HEADER_LINES = [
    "---",
    "status: active",
    "updated_at: 2026-09-01T00:00:00+00:00",
    "---",
    "",
    "# Stage 2 Amendment Fixture",
    "",
    "## Agent Todo",
    "",
]


def _todo_lines(specs: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    for spec in specs:
        tokens = " ".join(f"{key}={value}" for key, value in spec.items())
        lines.append(f"- [{'x' if spec.get('done') else ' '}] [{spec.get('priority', 'P1')}] {spec['text']}")
        lines.append(f"  <!-- loopx:todo {tokens} -->")
    return lines


def _default_todo_specs() -> list[dict[str, str]]:
    return [
        {
            "todo_id": "todo_stage2_a",
            "text": "Continue the agent-a claimed amendment-preamble slice.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "run",
            "claimed_by": "agent-a",
            "priority": "P0",
        },
        {
            "todo_id": "todo_stage2_b",
            "text": "Pick the amendment's unclaimed acceptance slice after claiming it.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "test",
            "priority": "P1",
        },
        {
            "todo_id": "todo_stage2_peer",
            "text": "Peer-held slice an amendment may legitimately affect.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "fix",
            "claimed_by": "agent-b",
            "priority": "P1",
        },
        {
            "todo_id": "todo_stage2_done",
            "text": "Delivered slice stays outside the open causal inventory.",
            "status": "done",
            "task_class": "advancement_task",
            "action_kind": "run",
            "claimed_by": "agent-b",
            "priority": "P1",
            "done": "true",
        },
    ]


def _other_goal_todo_specs() -> list[dict[str, str]]:
    return [
        {
            "todo_id": "todo_stage2_other",
            "text": "Belongs to the sibling Goal, never to this Goal's inventory.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "run",
            "claimed_by": "agent-b",
            "priority": "P2",
        },
    ]


def _fixture_obligation(
    agent_id: str | None = "agent-a",
    *,
    frontier_identity: str = "stage2-amendment-fixture",
    required: bool = True,
) -> dict[str, object]:
    """Build one authority-shaped obligation and derive its real id.

    ``ensure_replan_novelty_policy`` computes the deterministic
    ``replan-<16 hex>`` id from the obligation identity, so fixture ids are
    exactly what production quota/status projections would emit.
    """

    obligation: dict[str, object] = {
        "schema_version": "autonomous_replan_obligation_v0",
        "required": required,
        "frontier_identity": frontier_identity,
        "triggers": [
            {
                "kind": "blocked_successor_no_progress_repeat",
                "frontier_revision": 3,
            }
        ],
    }
    if agent_id:
        obligation["agent_id"] = agent_id
    return ensure_replan_novelty_policy(obligation)


def _write_fixture(
    root: Path,
    *,
    events: list[dict[str, str]] | None = None,
    with_other_goal: bool = False,
) -> dict[str, Path]:
    project = root / "project"
    runtime = root / "runtime"

    def _goal_state(goal_id: str, specs: list[dict[str, str]]) -> tuple[Path, str]:
        state_relative = Path(".codex") / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
        state_file = project / state_relative
        state_file.parent.mkdir(parents=True)
        state_file.write_text(
            "\n".join([*STATE_HEADER_LINES, *_todo_lines(specs)]) + "\n",
            encoding="utf-8",
        )
        _assert_fixture_todos_parsed(state_file, specs)
        return state_file, str(state_relative)

    state_file, state_relative = _goal_state(GOAL_ID, _default_todo_specs())
    goals = [
        {
            "id": GOAL_ID,
            "domain": "shared-goal-alignment-stage2",
            "status": "active",
            "repo": str(project),
            "state_file": state_relative,
            "quota": {"compute": 1.0, "window_hours": 24},
            "coordination": {
                "agent_model": "peer_v1",
                "registered_agents": list(AGENTS),
            },
        }
    ]
    other_state_file: Path | None = None
    if with_other_goal:
        other_state_file, other_state_relative = _goal_state(
            OTHER_GOAL_ID, _other_goal_todo_specs()
        )
        goals.append(
            {
                "id": OTHER_GOAL_ID,
                "domain": "shared-goal-alignment-stage2-peer",
                "status": "active",
                "repo": str(project),
                "state_file": other_state_relative,
                "quota": {"compute": 1.0, "window_hours": 24},
                "coordination": {
                    "agent_model": "peer_v1",
                    "registered_agents": list(AGENTS),
                },
            }
        )

    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": goals,
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

    paths = {
        "project": project,
        "runtime": runtime,
        "registry": registry_path,
        "state_file": state_file,
    }
    if other_state_file is not None:
        paths["other_state_file"] = other_state_file
    return paths


def _assert_fixture_todos_parsed(
    state_file: Path,
    todo_specs: list[dict[str, str]],
) -> None:
    parsed = parse_active_state_todos(
        state_file.read_text(encoding="utf-8"),
        item_limit=None,
    )
    items = parsed.get("agent_todos", {}).get("items", [])
    parsed_ids = {item.get("todo_id") for item in items}
    for spec in todo_specs:
        assert spec.get("todo_id") in parsed_ids, (
            f"fixture todo {spec.get('todo_id')} was silently ignored by the "
            "parser; check every metadata token exists in the schema"
        )


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


def _derived_source_basis(paths: dict[str, Path]) -> dict[str, object]:
    """Project the live Stage 1 source basis the proposal binds against."""

    alignment = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )
    basis = alignment["source_basis"]
    assert isinstance(basis, dict)
    return basis


def _proposal(
    paths: dict[str, Path],
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    # Default base binds to the live derived basis: equal sequence AND equal
    # source basis digest, exactly like a proposer that just re-read the
    # Stage 1 projection before proposing. The replan id is the real one
    # derived by ensure_replan_novelty_policy for the fixture obligation.
    basis = _derived_source_basis(paths)
    proposal: dict[str, object] = {
        "schema_version": "goal_amendment_proposal_v0",
        "proposal_id": "gap_stage2_001",
        "goal_id": GOAL_ID,
        "proposer_agent_id": "agent-a",
        "amendment_class": "shared_acceptance",
        "base_state_event_basis_sequence": basis["state_event_basis_sequence"],
        "base_source_basis_digest": basis["source_basis_digest"],
        "retained": ["original outcome remains unchanged"],
        "changed": ["acceptance now requires the recovered receipt"],
        "stopped": [],
        "evidence_refs": ["evidence:evt_stage2_001"],
        "affected_todo_ids": ["todo_stage2_a", "todo_stage2_b"],
        "replan_obligation_id": _fixture_obligation()["obligation_id"],
    }
    if overrides:
        proposal.update(overrides)
    return proposal


def _status_item(
    obligations_by_agent: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "autonomous_replan_obligations_by_agent": (
            obligations_by_agent
            if obligations_by_agent is not None
            else {"agent-a": _fixture_obligation("agent-a")}
        )
    }


def _admit(
    paths: dict[str, Path],
    proposal: dict[str, object],
    *,
    status_item: dict[str, object] | None = None,
):
    return admit_goal_amendment_proposal(
        proposal=proposal,
        project=paths["project"],
        status_item=status_item if status_item is not None else _status_item(),
    )


def _canonical_tree_snapshot(paths: dict[str, Path]) -> dict[str, bytes]:
    """Snapshot every runtime byte except the proposal journal sidecars.

    Admission must leave the state event log (the basis sequence carrier),
    the goal state file, and every other runtime artifact untouched; only
    ``amendment-proposals/`` and the advisory lock sidecars may move.
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


def _journal_rows(paths: dict[str, Path]) -> list[dict[str, object]]:
    return read_goal_amendment_proposal_journal(
        runtime_root=paths["runtime"],
        goal_id=GOAL_ID,
    )


def test_admits_and_retains_a_well_formed_proposal(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(paths, _proposal(paths))

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
    rows = _journal_rows(paths)
    assert [row["proposal_id"] for row in rows] == ["gap_stage2_001"]


def test_admission_binds_the_authority_derived_obligation_id(
    tmp_path: Path,
) -> None:
    # The retained replan id is the one ensure_replan_novelty_policy
    # derived from the fixture obligation identity — never a free-standing
    # well-shaped string.
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(paths, _proposal(paths))

    expected_id = _fixture_obligation("agent-a")["obligation_id"]
    assert record["replan_obligation_id"] == expected_id
    assert record["admission"] == "admitted"


def test_agent_scoped_obligation_folds_into_an_explicit_agent_lane(
    tmp_path: Path,
) -> None:
    # The Python authority folds autonomous_replan_scope_decision into the
    # typed inventory: an agent-scoped obligation admits only its owner,
    # an unscoped one admits exactly its deterministic peer.
    paths = _write_fixture(tmp_path, events=_default_events())
    scoped = _fixture_obligation("agent-a")
    unscoped = _fixture_obligation(None, frontier_identity="stage2-unscoped")
    status_item = {
        "autonomous_replan_obligations_by_agent": {
            "agent-a": scoped,
        },
        "autonomous_replan_obligation": unscoped,
    }

    _admit(
        paths,
        _proposal(
            paths,
            {"replan_obligation_id": scoped["obligation_id"]},
        ),
        status_item=status_item,
    )

    # The unscoped goal-level obligation is deterministically assigned to
    # exactly one registered peer: one lane admits, the other fails closed.
    unscoped_id = unscoped["obligation_id"]
    statuses = []
    for agent_id in AGENTS:
        proposal = _proposal(
            paths,
            {
                "proposal_id": f"gap_stage2_unscoped_{agent_id[-1]}",
                "replan_obligation_id": unscoped_id,
                "proposer_agent_id": agent_id,
            },
        )
        try:
            _admit(paths, proposal, status_item=status_item)
            statuses.append("admitted")
        except ValueError as exc:
            assert "bound to another agent lane" in str(exc)
            statuses.append("rejected")
    assert sorted(statuses) == ["admitted", "rejected"]


def test_nonexistent_replan_obligation_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(
        ValueError, match="does not match an open replan obligation"
    ):
        _admit(
            paths,
            _proposal(
                paths,
                {"replan_obligation_id": "replan-deadbeefdeadbeef"},
            ),
        )

    assert _journal_rows(paths) == []


def test_closed_replan_obligation_is_not_admissible(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    settled = _fixture_obligation("agent-a", required=False)
    status_item = _status_item({"agent-a": settled})

    with pytest.raises(
        ValueError, match="does not match an open replan obligation"
    ):
        _admit(paths, _proposal(paths), status_item=status_item)

    assert _journal_rows(paths) == []


def test_cross_goal_replan_obligation_fails_closed(tmp_path: Path) -> None:
    # The sibling Goal's status projection never contributes to this Goal's
    # obligation inventory: an id derived on the peer Goal's frontier does
    # not resolve here, even though its payload would otherwise be valid.
    paths = _write_fixture(tmp_path, events=_default_events(), with_other_goal=True)
    peer_goal_obligation = _fixture_obligation(
        "agent-a", frontier_identity="stage2-peer-goal-obligation"
    )

    with pytest.raises(
        ValueError, match="does not match an open replan obligation"
    ):
        _admit(
            paths,
            _proposal(
                paths,
                {"replan_obligation_id": peer_goal_obligation["obligation_id"]},
            ),
            status_item=_status_item(),
        )

    assert _journal_rows(paths) == []


def test_mismatched_agent_lane_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    peer_lane = _fixture_obligation("agent-b")

    with pytest.raises(ValueError, match="bound to another agent lane"):
        _admit(
            paths,
            _proposal(
                paths,
                {"replan_obligation_id": peer_lane["obligation_id"]},
            ),
            status_item=_status_item({"agent-b": peer_lane}),
        )

    assert _journal_rows(paths) == []


def test_missing_obligation_authority_fails_closed(tmp_path: Path) -> None:
    # No status projection supplied: the obligation inventory is empty and
    # admission must not trust a causal chain on string shape alone.
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(
        ValueError, match="does not match an open replan obligation"
    ):
        _admit(paths, _proposal(paths), status_item={})

    assert _journal_rows(paths) == []


def test_peer_claimed_affected_todo_still_admits(tmp_path: Path) -> None:
    # Shared amendments legitimately affect peer-claimed work: admission
    # checks goal membership and openness, not proposer ownership.
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(
        paths,
        _proposal(paths, {"affected_todo_ids": ["todo_stage2_peer"]}),
    )

    assert record["admission"] == "admitted"
    assert record["canonical_effect"] == "none"


def test_nonexistent_affected_todo_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="not open on goal"):
        _admit(
            paths,
            _proposal(paths, {"affected_todo_ids": ["todo_missing"]}),
        )

    assert _journal_rows(paths) == []


def test_done_affected_todo_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="not open on goal"):
        _admit(
            paths,
            _proposal(paths, {"affected_todo_ids": ["todo_stage2_done"]}),
        )

    assert _journal_rows(paths) == []


def test_cross_goal_affected_todo_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events(), with_other_goal=True)

    with pytest.raises(ValueError, match="not open on goal"):
        _admit(
            paths,
            _proposal(paths, {"affected_todo_ids": ["todo_stage2_other"]}),
        )

    assert _journal_rows(paths) == []


def test_proposal_digest_matches_the_python_canonical_recipe(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    proposal = _proposal(paths)

    record = _admit(paths, proposal)

    encoded = json.dumps(
        proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
    assert record["proposal_digest"] == expected


def test_stale_base_is_retained_with_needs_rebase(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(paths, _proposal(paths, {"base_state_event_basis_sequence": 1}))

    assert record["admission_facts"] == [
        "base_state_event_basis_sequence_behind_derived_head"
    ]
    assert record["canonical_effect"] == "none"
    assert len(_journal_rows(paths)) == 1, "a stale proposal must still be retained"


def test_future_base_fails_closed_without_retention(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(
        ValueError, match="ahead of the derived state event basis head"
    ):
        _admit(paths, _proposal(paths, {"base_state_event_basis_sequence": 99}))

    assert _journal_rows(paths) == []


def test_equal_sequence_with_mismatched_digest_needs_rebase(
    tmp_path: Path,
) -> None:
    # A proposal claiming the current sequence but binding to a different
    # source basis identity must never be admitted fresh: the digest
    # participates in admission, not only the sequence (review P1b).
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(
        paths,
        _proposal(paths, {"base_source_basis_digest": MISMATCHED_DIGEST}),
    )

    assert record["admission"] == "needs_rebase"
    assert record["admission_facts"] == ["base_source_basis_digest_mismatch"]
    assert record["canonical_effect"] == "none"
    assert [row["admission"] for row in _journal_rows(paths)] == ["needs_rebase"]


def test_replan_obligation_ids_follow_the_todo_contract(
    tmp_path: Path,
) -> None:
    # Python -> TS regression: the authority is
    # normalize_todo_replan_obligation_id's "replan-<16 lowercase hex>"
    # (real values such as the derived fixture id); the colon namespace
    # must be rejected end to end through the managed TS runtime.
    paths = _write_fixture(tmp_path, events=_default_events())

    record = _admit(paths, _proposal(paths))  # default uses the derived id

    assert record["replan_obligation_id"] == _fixture_obligation()["obligation_id"]
    assert record["admission"] == "admitted"
    with pytest.raises(ValueError, match=r"replan-<16 lowercase hex>"):
        _admit(
            paths,
            _proposal(
                paths,
                {
                    "proposal_id": "gap_stage2_replan",
                    "replan_obligation_id": "replan:stage2-001",
                },
            ),
        )


def test_unknown_amendment_class_is_rejected_without_retention(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="amendment class is unsupported"):
        _admit(paths, _proposal(paths, {"amendment_class": "emergency_powers"}))

    assert _journal_rows(paths) == []


def test_evidence_refs_over_budget_are_rejected(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="exceeds 8 pointers"):
        _admit(
            paths,
            _proposal(
                paths,
                {
                    "evidence_refs": [
                        f"evidence:evt_stage2_{index}" for index in range(9)
                    ]
                }
            ),
        )

    assert _journal_rows(paths) == []


def test_unregistered_proposer_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="not registered"):
        _admit(paths, _proposal(paths, {"proposer_agent_id": "agent-z"}))


def test_unknown_goal_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())

    with pytest.raises(ValueError, match="not registered"):
        _admit(paths, _proposal(paths, {"goal_id": "goal-unknown"}))


def test_journal_is_append_only_and_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    journal = _proposal_journal(paths)

    _admit(paths, _proposal(paths))
    first_snapshot = journal.read_text(encoding="utf-8")

    replay = _admit(paths, _proposal(paths))
    assert replay["proposal_id"] == "gap_stage2_001"
    assert journal.read_text(encoding="utf-8") == first_snapshot

    # RFC §7: one obligation can carry multiple proposals — same causal
    # chain, different proposal ids.
    _admit(
        paths,
        _proposal(paths, {"proposal_id": "gap_stage2_002"}),
    )
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == first_snapshot.strip(), "append-only: row 1 unchanged"
    assert [row["journal_append_sequence"] for row in _journal_rows(paths)] == [1, 2]


def test_conflicting_proposal_id_replay_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    _admit(paths, _proposal(paths))

    with pytest.raises(ValueError, match="conflicting proposal_id"):
        _admit(
            paths,
            _proposal(paths, {"changed": ["a different amendment content"]}),
        )

    rows = _journal_rows(paths)
    assert len(rows) == 1
    assert rows[0]["changed"] == ["acceptance now requires the recovered receipt"]


def test_markdown_basis_admits_with_unverifiable_fact(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=None)

    record = _admit(paths, _proposal(paths, {"base_state_event_basis_sequence": 5}))

    assert record["admission"] == "admitted"
    assert record["admission_facts"] == ["base_source_basis_unverifiable"]
    assert record["canonical_effect"] == "none"


def test_admission_has_zero_canonical_effect(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, events=_default_events())
    event_log = paths["state_file"].with_name(EVENT_LOG_NAME)
    before_state = paths["state_file"].read_bytes()
    before_events = event_log.read_bytes()
    before_registry = paths["registry"].read_bytes()

    _admit(paths, _proposal(paths))
    _admit(paths, _proposal(paths, {"proposal_id": "gap_stage2_002"}))

    assert paths["state_file"].read_bytes() == before_state
    assert event_log.read_bytes() == before_events
    assert paths["registry"].read_bytes() == before_registry
    assert _journal_rows(paths)[0]["canonical_effect"] == "none"


def test_registered_effect_method_rejects_an_illegal_request() -> None:
    # Direct call through the managed TS runtime: a digest that violates
    # the sha256 contract is a request rejection, not an admission record.
    # The proposal is built inline — this test needs no fixture on disk.
    proposal: dict[str, object] = {
        "schema_version": "goal_amendment_proposal_v0",
        "proposal_id": "gap_stage2_001",
        "goal_id": GOAL_ID,
        "proposer_agent_id": "agent-a",
        "amendment_class": "shared_acceptance",
        "base_state_event_basis_sequence": 3,
        "base_source_basis_digest": "md5:zz",
        "retained": ["original outcome remains unchanged"],
        "changed": ["acceptance now requires the recovered receipt"],
        "stopped": [],
        "evidence_refs": ["evidence:evt_stage2_001"],
        "affected_todo_ids": ["todo_stage2_a"],
        "replan_obligation_id": _fixture_obligation()["obligation_id"],
    }
    with pytest.raises(EffectRuntimeRejected) as excinfo:
        effect_runtime_result(
            "goal.amendment_proposal.admit",
            {
                "schema_version": "goal_amendment_proposal_request_v0",
                "proposal": proposal,
                "derived_basis": {
                    "state_event_basis_sequence": 3,
                    "revision_basis": "state_event_log",
                    "source_basis_digest": "sha256:" + "b" * 64,
                },
                "open_replan_obligations": [],
                "goal_todo_inventory": [],
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
    status_item=json.loads(sys.argv[3]),
)
print(record["proposal_id"], record["journal_append_sequence"])
"""
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo_root) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    # Same fixture obligation (same causal chain), different proposal ids
    # — RFC §7 allows multiple proposals per obligation to coexist.
    overrides = (
        {"proposal_id": "gap_stage2_p1"},
        {"proposal_id": "gap_stage2_p2"},
    )
    status_item_json = json.dumps(_status_item())
    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                str(paths["project"]),
                json.dumps(_proposal(paths, proposal_overrides)),
                status_item_json,
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
            _, stderr = child.communicate(timeout=60)
            assert child.returncode == 0, stderr
    finally:
        for child in children:
            if child.poll() is None:  # pragma: no cover - failure cleanup
                child.kill()
                child.wait()

    rows = _journal_rows(paths)
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
    _admit(paths, _proposal(paths))
    journal = _proposal_journal(paths)
    with journal.open("a", encoding="utf-8") as stream:
        stream.write('{"schema_version": "goal_amendment_proposal_admis\n')
    corrupted = journal.read_bytes()

    with pytest.raises(ValueError, match="invalid proposal journal JSONL"):
        _admit(
            paths,
            _proposal(paths, {"proposal_id": "gap_stage2_002"}),
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

    first = _admit(paths, _proposal(paths))
    second = _admit(
        paths,
        _proposal(paths, {"proposal_id": "gap_stage2_002"}),
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

    record = _admit(paths, _proposal(paths, {"base_state_event_basis_sequence": 1}))

    assert record["admission"] == "needs_rebase"
    assert record["admission_facts"] == [
        "base_state_event_basis_sequence_behind_derived_head"
    ]
    assert _canonical_tree_snapshot(paths) == before_tree
    rows = _journal_rows(paths)
    assert [row["admission"] for row in rows] == ["needs_rebase"]
    assert rows[0]["canonical_effect"] == "none"
