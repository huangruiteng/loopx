"""Stage 1 read-only shared goal alignment projection tests.

Every fixture Todo metadata line must only use tokens that exist in
``_TODO_METADATA_FIELD_SCHEMA`` (``todos/contract.py``): the parser silently
drops unknown keys, so an invented token would make the fixture lie. The
builder below asserts each ``todo_id`` actually parsed before any projection
runs, so a silently-ignored metadata line fails the fixture itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.effect_runtime import (
    EffectRuntimeRejected,
    effect_runtime_result,
)
from loopx.control_plane.goals import shared_goal_alignment
from loopx.control_plane.goals.shared_goal_alignment import (
    project_shared_goal_alignment,
)
from loopx.control_plane.todos.active_state_todo_parser import (
    parse_active_state_todos,
)
from loopx.event_sourced_state import (
    TODO_ADDED,
    AppendOnlyStateEventStore,
    make_state_event,
)

GOAL_ID = "goal-stage1"
AGENTS = ("agent-a", "agent-b")
EVENT_LOG_NAME = "events.jsonl"

STATE_HEADER_LINES = [
    "---",
    "status: active",
    "updated_at: 2026-09-01T00:00:00+00:00",
    "---",
    "",
    "# Stage 1 Alignment Fixture",
    "",
    "## Next Action",
    "",
    "Shared compatibility prose; it must never enter the projection digest.",
    "",
    "## Agent Todo",
    "",
]


def _todo_lines(specs: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    for spec in specs:
        tokens = " ".join(f"{key}={value}" for key, value in spec.items())
        lines.append(f"- [ ] [{spec.get('priority', 'P1')}] {spec['text']}")
        lines.append(f"  <!-- loopx:todo {tokens} -->")
    return lines


def _write_fixture(
    root: Path,
    *,
    todo_specs: list[dict[str, str]],
    events: list[dict[str, str]] | None = None,
    leases: dict[str, dict[str, object]] | None = None,
    agents: tuple[str, ...] = AGENTS,
    goal_id: str = GOAL_ID,
) -> dict[str, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_relative = Path(".codex") / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
    state_file = project / state_relative
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "\n".join([*STATE_HEADER_LINES, *_todo_lines(todo_specs)]) + "\n",
        encoding="utf-8",
    )

    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": goal_id,
                        "domain": "shared-goal-alignment-stage1",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_relative),
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": list(agents),
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
                    goal_id=goal_id,
                    event_type=TODO_ADDED,
                    actor_agent_id=event["actor_agent_id"],
                    refs={"todo_id": event["todo_id"]},
                    payload={"text": f"Fixture event for {event['todo_id']}."},
                )
            )

    if leases:
        for todo_id, lease in leases.items():
            lease_path = (
                runtime / "goals" / goal_id / "task-leases" / f"{todo_id}.json"
            )
            lease_path.parent.mkdir(parents=True, exist_ok=True)
            lease_path.write_text(
                json.dumps(lease, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
    else:
        runtime.mkdir(parents=True, exist_ok=True)

    _assert_fixture_todos_parsed(state_file, todo_specs)
    return {
        "project": project,
        "runtime": runtime,
        "registry": registry_path,
        "state_file": state_file,
    }


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


def _default_todo_specs() -> list[dict[str, str]]:
    return [
        {
            "todo_id": "todo_lane_a",
            "text": "Continue the agent-a claimed advancement slice.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "run",
            "claimed_by": "agent-a",
            "priority": "P0",
        },
        {
            "todo_id": "todo_unclaimed",
            "text": "Pick up unclaimed work only after claiming it.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "test",
            "priority": "P1",
        },
        {
            "todo_id": "todo_blocked",
            "text": "Blocked slice stays out of the frontier.",
            "status": "blocked",
            "task_class": "advancement_task",
            "action_kind": "fix",
            "claimed_by": "agent-a",
            "priority": "P1",
        },
        {
            "todo_id": "todo_monitor",
            "text": "Monitor work never enters the advancement frontier.",
            "status": "open",
            "task_class": "continuous_monitor",
            "action_kind": "watch",
            "priority": "P2",
        },
    ]


def _default_events() -> list[dict[str, str]]:
    return [
        {
            "event_id": "evt_stage1_001",
            "actor_agent_id": "agent-b",
            "todo_id": "todo_monitor",
        },
        {
            "event_id": "evt_stage1_002",
            "actor_agent_id": "agent-a",
            "todo_id": "todo_lane_a",
        },
        {
            "event_id": "evt_stage1_003",
            "actor_agent_id": "agent-a",
            "todo_id": "todo_unclaimed",
        },
    ]


def test_projects_basis_binding_and_unclaimed_work(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert projection["schema_version"] == "shared_goal_alignment_v0"
    assert projection["goal_id"] == GOAL_ID
    assert projection["agent_id"] == "agent-a"
    assert projection["read_only"] is True
    basis = projection["source_basis"]
    assert basis["revision_basis"] == "state_event_log"
    assert basis["state_event_basis_sequence"] == 3
    assert basis["source_basis_digest"].startswith("sha256:")
    assert basis["state_updated_at"] == "2026-09-01T00:00:00+00:00"
    frontier = projection["frontier_basis"]
    assert frontier["based_on_state_event_sequence"] == 3
    assert frontier["basis_source"] == "state_event_log"
    assert frontier["last_agent_event_id"] == "evt_stage1_003"
    assert projection["frontier_counts"] == {
        "current_agent_claimed_advancement_count": 1,
        "unclaimed_advancement_count": 1,
        "other_agent_claimed_advancement_count": 0,
    }
    assert [item["todo_id"] for item in projection["unclaimed_eligible_work"]] == [
        "todo_unclaimed"
    ]
    assert all(
        item["claim_required_before_work"] is True
        for item in projection["unclaimed_eligible_work"]
    )
    assert projection["drift_facts"] == []
    assert projection["conflict_facts"] == []


def test_a_goal_id_without_the_goal_prefix_projects(
    tmp_path: Path,
) -> None:
    # The repository Goal-ID contract (validate_goal_id_path_segment) is any
    # safe single path segment: real goal ids such as "loopx-meta" carry no
    # "goal-" prefix and must survive the TypeScript decoder.
    paths = _write_fixture(
        tmp_path,
        goal_id="loopx-meta",
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    projection = project_shared_goal_alignment(
        goal_id="loopx-meta",
        agent_id="agent-a",
        project=paths["project"],
    )

    assert projection["goal_id"] == "loopx-meta"
    assert projection["source_basis"]["state_event_basis_sequence"] == 3
    assert projection["drift_facts"] == []
    assert projection["conflict_facts"] == []


def test_peer_events_do_not_advance_another_agents_basis(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-b",
        project=paths["project"],
    )

    # agent-a authored events 2 and 3; agent-b's basis stays at its own
    # latest attributed event (1) and never inherits the peer sequences.
    assert projection["source_basis"]["state_event_basis_sequence"] == 3
    assert projection["frontier_basis"]["based_on_state_event_sequence"] == 1
    assert projection["frontier_basis"]["last_agent_event_id"] == (
        "evt_stage1_001"
    )
    assert projection["drift_facts"] == ["frontier_basis_behind"]


def test_appending_one_event_rotates_the_projection_into_frontier_behind(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )
    event_log = paths["state_file"].with_name(EVENT_LOG_NAME)

    before = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )
    assert before["source_basis"]["state_event_basis_sequence"] == 3
    assert before["frontier_basis"]["based_on_state_event_sequence"] == 3
    assert before["drift_facts"] == []

    AppendOnlyStateEventStore(event_log).append(
        make_state_event(
            event_id="evt_stage1_004",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            actor_agent_id="agent-b",
            refs={"todo_id": "todo_lane_a"},
            payload={"text": "Fixture event that moves the state event basis head."},
        )
    )

    after = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )
    assert after["source_basis"]["state_event_basis_sequence"] == 4
    assert after["frontier_basis"]["based_on_state_event_sequence"] == 3
    assert after["drift_facts"] == ["frontier_basis_behind"]


def test_without_an_event_log_the_basis_is_unverifiable_not_behind(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=None,
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert projection["source_basis"]["revision_basis"] == (
        "markdown_active_state"
    )
    assert projection["source_basis"]["state_event_basis_sequence"] == 0
    assert projection["frontier_basis"] == {
        "based_on_state_event_sequence": None,
        "basis_source": "unbound",
        "last_agent_event_id": None,
    }
    assert projection["drift_facts"] == []
    assert projection["conflict_facts"] == ["frontier_basis_unverifiable"]


def test_next_action_prose_never_changes_the_source_basis_digest(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    first = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )
    state_text = paths["state_file"].read_text(encoding="utf-8")
    paths["state_file"].write_text(
        state_text.replace(
            "Shared compatibility prose; it must never enter the projection digest.",
            "A completely different shared Next Action written by a peer.",
        ),
        encoding="utf-8",
    )
    second = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert first["source_basis"]["source_basis_digest"] == (
        second["source_basis"]["source_basis_digest"]
    )


def test_blocked_and_monitor_todos_stay_out_of_unclaimed_work(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    unclaimed_ids = [
        item["todo_id"] for item in projection["unclaimed_eligible_work"]
    ]
    assert unclaimed_ids == ["todo_unclaimed"]
    assert "todo_blocked" not in unclaimed_ids
    assert "todo_monitor" not in unclaimed_ids


def test_lease_owner_mismatch_projects_a_conflict_fact(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "goal_id": GOAL_ID,
                "todo_id": "todo_lane_a",
                "status": "active",
                "expires_at": "2099-01-01T00:00:00Z",
                "owner": "agent-b",
                "lease_epoch": 2,
                "version": 1,
            },
        },
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert projection["conflict_facts"] == ["lease_owner_mismatch"]
    assert projection["drift_facts"] == []


def test_matching_lease_owner_is_not_a_conflict(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "goal_id": GOAL_ID,
                "todo_id": "todo_lane_a",
                "status": "active",
                "expires_at": "2099-01-01T00:00:00Z",
                "owner": "agent-a",
                "lease_epoch": 1,
                "version": 1,
            },
        },
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert "lease_owner_mismatch" not in projection["conflict_facts"]


def test_corrupt_lease_epoch_fails_closed(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "status": "active",
                "expires_at": "2099-01-01T00:00:00Z",
                "owner": "agent-a",
                "lease_epoch": 0,
                "version": 1,
            },
        },
    )

    with pytest.raises(ValueError, match="lease epoch"):
        project_shared_goal_alignment(
            goal_id=GOAL_ID,
            agent_id="agent-a",
            project=paths["project"],
        )


def test_open_lane_replan_obligation_projects_a_conflict_fact(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
        status_item={
            "autonomous_replan_obligations_by_agent": {
                "agent-a": {
                    "schema_version": "autonomous_replan_obligation_v0",
                    "required": True,
                },
            },
        },
    )

    assert "open_lane_replan_obligation" in projection["conflict_facts"]


def test_peer_claimed_bound_todo_projects_a_conflict_fact(
    tmp_path: Path,
) -> None:
    specs = [
        *_default_todo_specs(),
        {
            "todo_id": "todo_taken_over",
            "text": "Previously bound to agent-a, now claimed by agent-b.",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "fix",
            "claimed_by": "agent-b",
            "bound_agent": "agent-a",
            "priority": "P1",
        },
    ]
    paths = _write_fixture(
        tmp_path,
        todo_specs=specs,
        events=_default_events(),
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert "peer_claimed_lane_conflict" in projection["conflict_facts"]


def test_unregistered_agent_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    with pytest.raises(ValueError, match="not registered"):
        project_shared_goal_alignment(
            goal_id=GOAL_ID,
            agent_id="agent-z",
            project=paths["project"],
        )


def test_unknown_goal_fails_closed(tmp_path: Path) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    with pytest.raises(ValueError, match="not registered"):
        project_shared_goal_alignment(
            goal_id="goal-unknown",
            agent_id="agent-a",
            project=paths["project"],
        )


def test_registered_agent_without_any_events_projects_an_unbound_basis(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        agents=("agent-a", "agent-b", "agent-c"),
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-c",
        project=paths["project"],
    )

    # The state event basis head stays verifiable (the log exists at
    # sequence 3), but an Agent with zero attributed events must not
    # fabricate a frontier: the basis is unbound and reported as
    # unverifiable instead of behind.
    assert projection["source_basis"]["revision_basis"] == "state_event_log"
    assert projection["source_basis"]["state_event_basis_sequence"] == 3
    assert projection["frontier_basis"] == {
        "based_on_state_event_sequence": None,
        "basis_source": "unbound",
        "last_agent_event_id": None,
    }
    assert projection["drift_facts"] == []
    assert projection["conflict_facts"] == ["frontier_basis_unverifiable"]


def test_a_corrupt_event_log_falls_back_to_the_markdown_basis(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=None,
    )
    event_log = paths["state_file"].with_name(EVENT_LOG_NAME)
    event_log.write_text("{ this line is not jsonl\n", encoding="utf-8")

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    # A present-but-corrupt log must not fabricate a basis sequence: the
    # adapter falls back to the markdown active state and reports the
    # frontier as unverifiable instead of trusting the head.
    assert projection["source_basis"]["revision_basis"] == (
        "markdown_active_state"
    )
    assert projection["source_basis"]["state_event_basis_sequence"] == 0
    assert projection["frontier_basis"]["basis_source"] == "unbound"
    assert projection["drift_facts"] == []
    assert projection["conflict_facts"] == ["frontier_basis_unverifiable"]


def test_non_numeric_lease_epoch_fails_closed(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "status": "active",
                "expires_at": "2099-01-01T00:00:00Z",
                "owner": "agent-a",
                "lease_epoch": "two",
                "version": 1,
            },
        },
    )

    with pytest.raises(ValueError, match="lease epoch"):
        project_shared_goal_alignment(
            goal_id=GOAL_ID,
            agent_id="agent-a",
            project=paths["project"],
        )


def test_released_lease_record_does_not_project_ownership_conflict(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "goal_id": GOAL_ID,
                "todo_id": "todo_lane_a",
                "status": "released",
                "expires_at": "2099-01-01T00:00:00Z",
                "owner": "agent-b",
                "lease_epoch": 2,
                "version": 1,
            },
        },
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert "lease_owner_mismatch" not in projection["conflict_facts"]
    assert projection["conflict_facts"] == []


def test_expired_lease_record_does_not_project_ownership_conflict(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "goal_id": GOAL_ID,
                "todo_id": "todo_lane_a",
                "status": "active",
                "expires_at": "2020-01-01T00:00:00Z",
                "owner": "agent-b",
                "lease_epoch": 2,
                "version": 1,
            },
        },
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert "lease_owner_mismatch" not in projection["conflict_facts"]
    assert projection["conflict_facts"] == []


def test_active_lease_owner_mismatch_projects_conflict_fact(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={
            "todo_lane_a": {
                "schema_version": "task_lease_v0",
                "goal_id": GOAL_ID,
                "todo_id": "todo_lane_a",
                "status": "active",
                "expires_at": "2099-01-01T00:00:00Z",
                "owner": "agent-b",
                "lease_epoch": 2,
                "version": 1,
            },
        },
    )

    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert projection["conflict_facts"] == ["lease_owner_mismatch"]


@pytest.mark.parametrize(
    "lease_owner",
    [
        pytest.param(None, id="missing-owner"),
        pytest.param("", id="empty-owner"),
        pytest.param("Not A Valid Agent Id!!", id="malformed-owner"),
    ],
)
def test_active_lease_without_a_valid_owner_fails_closed(
    tmp_path: Path,
    lease_owner: str | None,
) -> None:
    # An active hard lease that survives lease_is_active() but carries no
    # normalizable owner is corrupt authority: the projection must fail
    # closed instead of silently reporting the claim as conflict-free.
    lease: dict[str, object] = {
        "schema_version": "task_lease_v0",
        "goal_id": GOAL_ID,
        "todo_id": "todo_lane_a",
        "status": "active",
        "expires_at": "2098-03-04T00:00:00Z",
        "lease_epoch": 3,
        "version": 1,
    }
    if lease_owner is not None:
        lease["owner"] = lease_owner
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
        leases={"todo_lane_a": lease},
    )

    with pytest.raises(ValueError, match="no valid owner"):
        project_shared_goal_alignment(
            goal_id=GOAL_ID,
            agent_id="agent-a",
            project=paths["project"],
        )


def test_projection_is_deterministic_across_repeated_calls(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )

    first = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )
    second = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert json.dumps(first, sort_keys=True) == json.dumps(
        second, sort_keys=True
    )
    assert first["source_basis"]["source_basis_digest"] == (
        second["source_basis"]["source_basis_digest"]
    )
    assert first["drift_facts"] == second["drift_facts"]
    assert first["conflict_facts"] == second["conflict_facts"]


def test_adapter_sends_typed_facts_only(monkeypatch, tmp_path: Path) -> None:
    paths = _write_fixture(
        tmp_path,
        todo_specs=_default_todo_specs(),
        events=_default_events(),
    )
    captured: dict[str, object] = {}

    def call(method: str, params: dict[str, object]) -> dict[str, object]:
        captured["method"] = method
        captured["params"] = params
        return effect_runtime_result(method, params)

    monkeypatch.setattr(shared_goal_alignment, "effect_runtime_result", call)
    projection = project_shared_goal_alignment(
        goal_id=GOAL_ID,
        agent_id="agent-a",
        project=paths["project"],
    )

    assert captured["method"] == "goal.shared_goal_alignment.project"
    request = captured["params"]
    assert isinstance(request, dict)
    # Typed-facts invariant: no prose field ever enters the request.
    assert "prose" not in json.dumps(request)
    assert request["goal_id"] == GOAL_ID
    assert request["agent_id"] == "agent-a"
    assert request["source_basis"]["state_event_basis_sequence"] == 3
    assert request["frontier_basis"]["based_on_state_event_sequence"] == 3
    assert request["claims"] == [
        {
            "todo_id": "todo_lane_a",
            "claimed_by": "agent-a",
            "lease_epoch": None,
            "lease_owner": None,
        }
    ]
    assert request["peer_claimed_bound_todo_ids"] == []
    assert request["open_lane_replan_obligation_required"] is False
    assert projection["schema_version"] == "shared_goal_alignment_v0"


def test_registered_method_rejects_an_illegal_request() -> None:
    # A claim attributed to another agent is a contract violation the TS
    # validator must reject at the registered runtime method.
    digest = "sha256:" + "a" * 64
    with pytest.raises(EffectRuntimeRejected) as excinfo:
        effect_runtime_result(
            "goal.shared_goal_alignment.project",
            {
                "schema_version": "shared_goal_alignment_request_v0",
                "goal_id": GOAL_ID,
                "agent_id": "agent-a",
                "source_basis": {
                    "state_event_basis_sequence": 3,
                    "source_basis_digest": digest,
                    "revision_basis": "state_event_log",
                    "state_updated_at": None,
                },
                "frontier_basis": {
                    "based_on_state_event_sequence": 3,
                    "basis_source": "state_event_log",
                    "last_agent_event_id": "evt_stage1_003",
                },
                "frontier_counts": {
                    "current_agent_claimed_advancement_count": 1,
                    "unclaimed_advancement_count": 0,
                    "other_agent_claimed_advancement_count": 0,
                },
                "claims": [
                    {
                        "todo_id": "todo_lane_a",
                        "claimed_by": "agent-b",
                        "lease_epoch": None,
                        "lease_owner": None,
                    }
                ],
                "unclaimed_eligible": [],
                "peer_claimed_bound_todo_ids": [],
                "open_lane_replan_obligation_required": False,
            },
        )
    assert excinfo.value.error_kind == "request_rejected"
