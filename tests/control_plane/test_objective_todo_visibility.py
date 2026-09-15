"""Generated Todo sections stay readable when the objective is arbitrary prose.

Issue #4401: a goal objective is user-authored text, but it was written straight
into the generated state document. An objective that collapsed into a single
fence line, opened a tilde fence, opened an HTML comment, or merely looked like
a Todo row then hid or polluted the generated Todo sections below it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopx.bootstrap import render_state_markdown
from loopx.chat_server import _active_state_section, _compact_text
from loopx.control_plane.goals.active_state_metadata import (
    OBJECTIVE_REGION_BEGIN,
    OBJECTIVE_REGION_END,
    read_objective_text,
)
from loopx.control_plane.projects.registry import _state_markdown
from loopx.control_plane.todos.active_state_todo_parser import parse_todo_source


USER_SECTION = "## User Todo / Owner Review Reading Queue"
AGENT_SECTION = "## Agent Todo"

OBJECTIVE_SECTION_LEGACY = "## Objective\n\nImplement and validate the task.\n\n## Agent Todo\n\n"

# Objectives that previously swallowed or polluted the generated Todo sections.
HOSTILE_OBJECTIVES = [
    # start-goal collapses whitespace, so this becomes one unclosed fence line.
    "```text Implement and validate the task. ```",
    "~~~text Implement and validate the task. ~~~",
    "<!-- Implement and validate the task.",
    "- [ ] agent: example-only - implement and validate the task.",
]

# Objectives that must keep working exactly as before.
CONTROL_OBJECTIVES = [
    "Implement and validate the task.",
    "```text\nImplement and validate the task.\n```",
]


def _bootstrap_state(objective: str) -> str:
    return render_state_markdown(
        project=Path("/tmp/loopx-objective-visibility"),
        goal_id="objective-example",
        adapter_kind="read_only_project_map_v0",
        objective=objective,
        updated_at="2026-09-15T00:00:00+00:00",
        goal_doc=None,
        execution_profile=None,
    )


def _registry_state(objective: str) -> str:
    return _state_markdown(
        project_id="project-example",
        goal_id="objective-example",
        objective=objective,
        non_goals=[],
        acceptance=[],
        unknowns=[],
        next_effect="Record the first project-specific adapter signal.",
        stop_condition="The adapter signal is recorded.",
        updated_at="2026-09-15T00:00:00+00:00",
    )


STATE_BUILDERS = [_bootstrap_state, _registry_state]
BUILDER_IDS = ["bootstrap", "project-registration"]


@pytest.mark.parametrize("objective", HOSTILE_OBJECTIVES + CONTROL_OBJECTIVES)
@pytest.mark.parametrize("build", STATE_BUILDERS, ids=BUILDER_IDS)
def test_generated_todo_sections_stay_readable(build, objective: str) -> None:
    items, _archive, sources = parse_todo_source(build(objective))
    assert sources["user"] == USER_SECTION[3:]
    assert sources["agent"] == AGENT_SECTION[3:]
    # No objective prose may be adopted as authoritative Todo content.
    assert all("example-only" not in str(item) for item in items["agent"])


@pytest.mark.parametrize("objective", HOSTILE_OBJECTIVES + CONTROL_OBJECTIVES)
@pytest.mark.parametrize("build", STATE_BUILDERS, ids=BUILDER_IDS)
def test_objective_text_is_preserved_verbatim(build, objective: str) -> None:
    state = build(objective)
    assert objective in state
    assert OBJECTIVE_REGION_BEGIN in state
    assert OBJECTIVE_REGION_END in state


@pytest.mark.parametrize("objective", HOSTILE_OBJECTIVES + CONTROL_OBJECTIVES)
@pytest.mark.parametrize("build", STATE_BUILDERS, ids=BUILDER_IDS)
def test_direct_objective_readback_recovers_the_goal_text(build, objective: str) -> None:
    # The dashboard goal context reads the objective back from the isolated
    # region, so fenced or commented prose is still recoverable as text.
    assert read_objective_text(build(objective)) == objective
    assert _compact_text(read_objective_text(build(objective))) == " ".join(objective.split())


def test_legacy_state_without_objective_region_falls_back() -> None:
    legacy = f"---\nstatus: active\n---\n\n# Active Goal State\n\n{OBJECTIVE_SECTION_LEGACY}\n"
    assert read_objective_text(legacy) == ""
    # The pre-existing section scan still serves unmarked state documents.
    assert _active_state_section(legacy, "Objective") == "Implement and validate the task."


def test_objective_markers_are_invisible_to_the_todo_reader() -> None:
    state = _bootstrap_state(HOSTILE_OBJECTIVES[0])
    body_start = state.index(OBJECTIVE_REGION_BEGIN)
    body_end = state.index(OBJECTIVE_REGION_END)
    assert body_start < body_end
    # A real fence below an isolated objective still hides what it encloses.
    fenced = (
        state[: state.index(AGENT_SECTION)]
        + "```\n## Agent Todo\n- [ ] agent: hidden - should not be adopted.\n```\n\n"
        + state[state.index(AGENT_SECTION) :]
    )
    _items, _archive, sources = parse_todo_source(fenced)
    assert sources["agent"] == AGENT_SECTION[3:]


def test_empty_objective_renders_without_markers() -> None:
    state = _bootstrap_state("")
    assert OBJECTIVE_REGION_BEGIN not in state
    _items, _archive, sources = parse_todo_source(state)
    assert sources["agent"] == AGENT_SECTION[3:]
