"""Characterize the #4311 peer-dispatch obligations retained for the M2 handoff contract.

#4312 implemented a same-Goal dispatch broker and was closed as superseded by the
merged capable-manager semantic-handoff RFC (#4330). The defect in #4311 remains
real, so the acceptance obligations #4312 recorded as migration inputs are pinned
here against the shipped manager-context inbox and the shipped claim-scope
projection. This is a characterization / compatibility baseline for the M2
cutover, not an implementation of the new collaboration contract.

The obligation ledger lives in
``tests/fixtures/control_plane/manager_handoff_m2_characterization_v0.json``;
every obligation that claims an ``asserted_by`` test must have one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.capabilities.manager_context import (
    _hash,
    _root,
    acknowledge,
    authority,
    deliver,
    pending,
)
from loopx.capabilities.manager_context.tracking import query, record_read
from loopx.control_plane.todos.quota_selection import project_quota_planning

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "control_plane"
    / "manager_handoff_m2_characterization_v0.json"
)


def _load() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def ledger() -> dict:
    return _load()


@pytest.fixture
def scenario(tmp_path, ledger):
    """A synthetic Goal with a monitor owner, one peer, and a solo control Goal."""

    data = ledger["scenario"]
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": data["goal_id"],
                        "repo": str(tmp_path),
                        "coordination": {
                            "registered_agents": data["registered_agents"]
                        },
                    },
                    {
                        "id": data["solo_goal_id"],
                        "repo": str(tmp_path),
                        "coordination": {
                            "registered_agents": data["solo_registered_agents"]
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    session = {"session_id": "manager-session", "channel_id": "manager"}
    turn = {
        "client_turn_id": "heartbeat-one",
        "origin": "web",
        "message": "Route the monitor successor to an agent that may execute it.",
    }
    return {
        "root": tmp_path,
        "registry": registry,
        "session": session,
        "turn": turn,
        "data": data,
        "peer_request": {
            "goal_id": data["goal_id"],
            "agent_id": data["peer_agent"],
        },
        "origin_request": {
            "goal_id": data["goal_id"],
            "agent_id": data["monitor_owner"],
        },
    }


def _planning(item: dict, agent_id: str) -> dict:
    return project_quota_planning(
        {},
        all_open_items=[item],
        source_open_count=1,
        agent_identity={"agent_id": agent_id, "agent_model": "peer_v1"},
        filter_user_gate_blocks_agent=False,
        available_capabilities=None,
    )


def test_obligation_ledger_is_complete_public_safe_and_bound(ledger):
    assert ledger["schema_version"] == "manager_handoff_m2_characterization_v0"
    assert ledger["public_safe"] is True and ledger["synthetic_only"] is True
    for flag in (
        "contains_credentials",
        "contains_provider_payloads",
        "contains_private_locators",
    ):
        assert ledger[flag] is False, flag
    ids = [row["id"] for row in ledger["obligations"]]
    assert len(ids) == len(set(ids)), "obligation ids must be unique"
    for row in ledger["obligations"]:
        assert row["retained_from"], row["id"]
        assert row["invariant"], row["id"]
        covered = row.get("asserted_by") or row.get("covered_by_existing")
        assert covered, f"{row['id']} is not bound to any test"
        if row.get("asserted_by"):
            assert row["asserted_by"] in globals(), (
                f"{row['id']} points at missing test {row['asserted_by']}"
            )


def test_executor_excluded_successor_reads_dispatchable_for_a_peer_and_excluded_for_the_origin(
    scenario,
):
    """O1: one successor, two readings, one projection."""

    item = dict(scenario["data"]["successor"])
    todo_id = item["todo_id"]
    origin = _planning(item, scenario["data"]["monitor_owner"])
    peer = _planning(item, scenario["data"]["peer_agent"])

    assert [row["todo_id"] for row in origin["lanes"]["open_items"]] == []
    assert origin["lanes"]["claim_scope"]["selectable_open_count"] == 0
    assert origin["lanes"]["claim_scope"]["executor_excluded_self_count"] == 1
    assert [
        row["todo_id"]
        for row in origin["lanes"]["claim_scope"]["executor_excluded_self_items"]
    ] == [todo_id]

    assert [row["todo_id"] for row in peer["lanes"]["open_items"]] == [todo_id]
    assert peer["lanes"]["claim_scope"]["selectable_open_count"] == 1
    assert peer["lanes"]["claim_scope"]["unclaimed_open_count"] == 1
    assert peer["lanes"]["claim_scope"]["executor_excluded_self_count"] == 0


def test_no_eligible_peer_fails_closed_without_inventing_a_user_gate(scenario):
    """O2: an empty eligible-peer set is a typed failure, never a user gate."""

    root, registry = scenario["root"], scenario["registry"]
    session, turn = scenario["session"], scenario["turn"]
    solo = scenario["data"]["solo_goal_id"]
    owner = scenario["data"]["monitor_owner"]
    peer = scenario["data"]["peer_agent"]

    grant = authority(root, registry, session, turn)
    same_goal = [row for row in grant["targets"] if row["goal_id"] == solo]
    assert same_goal == [{"goal_id": solo, "agent_id": owner}]
    assert [row["agent_id"] for row in same_goal if row["agent_id"] != owner] == []

    with pytest.raises(ValueError, match="not authorized or registered"):
        deliver(
            root,
            registry,
            session=session,
            turn=turn,
            request={"goal_id": solo, "agent_id": peer},
        )

    empty = authority(root, registry, session, turn)
    assert "user_gate" not in empty and "gate" not in empty
    assert empty["mode"] == "context_only"


def test_duplicate_dispatch_replays_one_durable_entry(scenario):
    """O3: a repeated heartbeat dispatch replays instead of redispatching."""

    root, registry = scenario["root"], scenario["registry"]
    request = scenario["peer_request"]
    first = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )
    second = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )

    assert second["request_id"] == first["request_id"]
    assert first["replayed"] is False and second["replayed"] is True
    folder = _root(root) / "entries" / _hash(request)
    assert sorted(path.name for path in folder.glob("*.json")) == [
        first["request_id"] + ".json"
    ]
    assert len(pending(root, request["goal_id"], request["agent_id"])["items"]) == 1


def test_dispatched_read_claimed_chain_survives_a_restart(scenario):
    """O4: delivery, read and decision all read back from the store after restart."""

    root, registry = scenario["root"], scenario["registry"]
    request = scenario["peer_request"]
    delivered = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )
    request_id = delivered["request_id"]

    record_read(root, pending(root, request["goal_id"], request["agent_id"])["items"])
    acknowledge(
        root,
        request["goal_id"],
        request["agent_id"],
        request_id,
        "adopt",
        "take the successor; the monitor transition is material",
    )

    # A restart re-reads the same runtime root with no in-process state.
    row = query(root, registry, goal_ids=[request["goal_id"]], owner_scope=True)[
        "rows"
    ][0]
    assert row["request_id"] == request_id
    assert row["delivery"]["status"] == "delivered"
    assert row["read"]["status"] == "supplied_to_receiver"
    assert row["decision"]["status"] == "adopt"
    assert row["warnings"] == []


def test_redispatch_after_decision_keeps_the_recorded_decision(scenario):
    """O5: a later delivery never overwrites a recorded decision."""

    root, registry = scenario["root"], scenario["registry"]
    request = scenario["peer_request"]
    delivered = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )
    request_id = delivered["request_id"]
    acknowledge(
        root, request["goal_id"], request["agent_id"], request_id, "adopt", "first"
    )

    replayed = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )
    assert replayed["request_id"] == request_id and replayed["replayed"] is True

    row = query(root, registry, goal_ids=[request["goal_id"]], owner_scope=True)[
        "rows"
    ][0]
    assert row["decision"]["status"] == "adopt"
    assert row["decision"]["reason"] == "first"


def test_conflicting_acknowledgement_is_rejected_not_overwritten(scenario):
    """O6: conflicting claim history stays visible instead of becoming latest state."""

    root, registry = scenario["root"], scenario["registry"]
    request = scenario["peer_request"]
    request_id = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )["request_id"]
    acknowledge(
        root, request["goal_id"], request["agent_id"], request_id, "adopt", "first"
    )

    with pytest.raises(ValueError, match="already recorded"):
        acknowledge(
            root,
            request["goal_id"],
            request["agent_id"],
            request_id,
            "reject",
            "second",
        )

    row = query(root, registry, goal_ids=[request["goal_id"]], owner_scope=True)[
        "rows"
    ][0]
    assert row["decision"]["status"] == "adopt"


def test_peer_dispatch_is_invisible_to_the_origin_inbox(scenario):
    """O7: sharing a Goal is not sharing a handoff."""

    root, registry = scenario["root"], scenario["registry"]
    peer_request = scenario["peer_request"]
    request_id = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=peer_request,
    )["request_id"]

    assert pending(root, peer_request["goal_id"], peer_request["agent_id"])["items"]
    assert (
        pending(
            root,
            scenario["origin_request"]["goal_id"],
            scenario["data"]["monitor_owner"],
        )["items"]
        == []
    )
    # The entry is filed under the recipient's scope hash, so the origin identity
    # cannot reach it at all; isolation is structural, not a filtered read.
    assert not (
        _root(root)
        / "entries"
        / _hash(scenario["origin_request"])
        / (request_id + ".json")
    ).exists()
    with pytest.raises((OSError, ValueError)):
        acknowledge(
            root,
            scenario["origin_request"]["goal_id"],
            scenario["data"]["monitor_owner"],
            request_id,
            "adopt",
            "wrong identity",
        )


def test_dispatch_and_handoff_identities_are_deterministic(scenario):
    """O8: tuple-derived identities are stable, so a replay is never a redispatch."""

    root, registry = scenario["root"], scenario["registry"]
    request = scenario["peer_request"]
    first = deliver(
        root,
        registry,
        session=scenario["session"],
        turn=scenario["turn"],
        request=request,
    )["request_id"]
    assert first == _hash(
        [
            authority(root, registry, scenario["session"], scenario["turn"])[
                "source_id"
            ],
            request,
        ]
    )
    assert (
        deliver(
            root,
            registry,
            session=scenario["session"],
            turn=scenario["turn"],
            request=request,
        )["request_id"]
        == first
    )

    item = dict(scenario["data"]["successor"])
    first_note = _planning(item, scenario["data"]["monitor_owner"])["lanes"][
        "claim_scope"
    ]["executor_excluded_self_items"][0]["handoff_note"]["handoff_id"]
    assert (
        _planning(dict(item), scenario["data"]["monitor_owner"])["lanes"][
            "claim_scope"
        ]["executor_excluded_self_items"][0]["handoff_note"]["handoff_id"]
        == first_note
    )
    successor = dict(item, todo_id="todo_1b7d0c4e5a92")
    assert (
        _planning(successor, scenario["data"]["monitor_owner"])["lanes"]["claim_scope"][
            "executor_excluded_self_items"
        ][0]["handoff_note"]["handoff_id"]
        != first_note
    )
