"""Characterize the shipped file-backed ``claim_work`` path against the contract.

``tests/control_plane/test_coordination_executor.py`` proves the authority
semantics with an in-memory provider, and
``test_coordination_file_provider.py`` proves the storage verbs. This fixture
closes the gap between them: one scenario matrix drives the real
``CoordinationAuthorityExecutor`` through the shipped
``FileCoordinationProvider``.

The fixture is provider-neutral by construction. Every scenario speaks only the
storage protocol (``store_identity`` / ``load`` / ``compare_and_put``) and
receives providers from a handle factory, so registering another provider later
requires no change to the matrix or to the expectations.

Expected outcomes are declared from the coordination domain contract (RFC
section 10, checks 1-5) before anything runs. They are never read back from
provider output, and no authority rule is re-derived here: the executor is the
only decision maker under test.

In scope: characterization only. No production code changes, no new provider,
no default-provider or public-behavior change, and no live NoKV, credential,
service-startup, or provider-promotion surface.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from loopx.control_plane.coordination.executor import (
    CoordinationAuthorityExecutor,
    sample_claim_envelope,
)
from loopx.control_plane.coordination.file_provider import FileCoordinationProvider
from loopx.control_plane.coordination.head import bootstrap_head


GOAL_ID = "goal-a"
# Fixed wall clock: every lease expiry in this matrix is minted from it.
NOW = 1_800_000_000.0
ELIGIBLE_AGENTS = ("agent-a", "agent-b")


# ---- synthetic, public-safe head fixtures -----------------------------------


def eligibility(allowed: tuple[str, ...] = ELIGIBLE_AGENTS) -> dict[str, Any]:
    return {
        "authorization_projection_revision": 3,
        "authorization_projection_digest": "sha256:bootstrap-auth",
        "allowed_agent_ids": list(allowed),
        "dependencies_satisfied": True,
        "dependency_revision": 12,
        "gates_open": True,
        "gate_revision": 5,
    }


def todo(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "todo_revision": 7,
        "status": "open",
        "claimed_by": None,
        "eligibility": eligibility(),
        "repository": "git:example/repo",
        "code_revision": "0123456789abcdef",
        "last_lease_epoch": 6,
    }
    base.update(overrides)
    return base


def claim(
    agent: str = "agent-a",
    todo_id: str = "todo-1",
    operation_id: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    return sample_claim_envelope(
        goal_id=GOAL_ID,
        operation_id=operation_id or f"op-{agent}-{todo_id}",
        agent_id=agent,
        device_id=f"dev-{agent}",
        todo_id=todo_id,
        expected_todo_revision=7,
        expected_preconditions={
            "authorization_projection_revision": 3,
            "authorization_projection_digest": "sha256:bootstrap-auth",
            "dependency_revision": 12,
            "gate_revision": 5,
        },
        lease_ttl_seconds=600,
        **overrides,
    )


def bootstrap(provider: Any, todo_ids: tuple[str, ...] = ("todo-1", "todo-2")) -> None:
    head = bootstrap_head(
        GOAL_ID,
        {todo_id: todo() for todo_id in todo_ids},
        store_binding=provider.store_identity(),
    )
    assert provider.compare_and_put(0, head)["result"] == "applied"


def executor_for(provider: Any) -> CoordinationAuthorityExecutor:
    return CoordinationAuthorityExecutor(provider, goal_id=GOAL_ID, now=lambda: NOW)


class RecordingProvider:
    """Storage-only recorder: delegates every verb and records CAS expectations.

    It holds no authority semantics; it exists so a scenario can prove that a
    stale generation reached ``compare_and_put`` without duplicating a write.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.cas_expectations: list[int] = []

    def store_identity(self) -> str:
        return self._inner.store_identity()

    def load(self) -> tuple[dict[str, Any] | None, int]:
        return self._inner.load()

    def compare_and_put(
        self, expected_provider_generation: int, head: dict[str, Any]
    ) -> dict[str, Any]:
        self.cas_expectations.append(expected_provider_generation)
        return self._inner.compare_and_put(expected_provider_generation, head)


# ---- observation and expectation --------------------------------------------


@dataclass
class Observation:
    """What one scenario actually produced, in contract terms only."""

    outcomes: list[dict[str, Any]] = field(default_factory=list)
    head: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Expectation:
    """The contract-derived verdict one scenario must produce."""

    results: tuple[str, ...]
    reasons: tuple[str | None, ...]
    authority_revision: int
    receipts: tuple[str, ...]
    claimed_by: tuple[tuple[str, str | None], ...]
    todo_revisions: tuple[tuple[str, int], ...]
    flags: tuple[tuple[str, bool], ...] = ()


# ---- scenarios --------------------------------------------------------------


def same_target_competition(handles: Callable[[], Any]) -> Observation:
    """Check 1: two actors on one target leave exactly one winner."""

    provider = handles()
    bootstrap(provider)
    executor = executor_for(provider)
    observation = Observation()
    observation.outcomes.append(executor.apply(claim("agent-a", "todo-1")))
    observation.outcomes.append(executor.apply(claim("agent-b", "todo-1")))
    observation.head, _ = provider.load()
    return observation


def independent_targets_rebase(handles: Callable[[], Any]) -> Observation:
    """Check 2: independent targets both apply through internal rebase."""

    provider = handles()
    bootstrap(provider)
    observation = Observation()
    observation.outcomes.append(
        executor_for(provider).apply(claim("agent-a", "todo-1"))
    )
    observation.outcomes.append(
        executor_for(provider).apply(claim("agent-b", "todo-2"))
    )
    observation.head, _ = provider.load()
    return observation


def replay_after_interleaved_write(handles: Callable[[], Any]) -> Observation:
    """Check 3: `A -> B -> replay A` returns the exact original receipt.

    The replay runs through a freshly constructed executor and a fresh provider
    handle, so nothing is served from in-process state.
    """

    provider = handles()
    bootstrap(provider)
    executor = executor_for(provider)
    observation = Observation()
    request_a = claim("agent-a", "todo-1", operation_id="op-A")
    first = executor.apply(request_a)
    observation.outcomes.append(first)
    observation.outcomes.append(
        executor.apply(claim("agent-b", "todo-2", operation_id="op-B"))
    )
    reconstructed = executor_for(handles())
    replay = reconstructed.apply(copy.deepcopy(request_a))
    observation.outcomes.append(replay)
    observation.flags["replay_returns_original_receipt"] = (
        replay.get("original_receipt") == first.get("original_receipt")
        and replay.get("original_receipt") is not None
    )
    observation.head, _ = provider.load()
    return observation


def operation_identity_reuse(handles: Callable[[], Any]) -> Observation:
    """Check 5: one operation id with different semantics changes nothing."""

    provider = handles()
    bootstrap(provider)
    executor = executor_for(provider)
    observation = Observation()
    request = claim("agent-a", "todo-1", operation_id="op-A")
    observation.outcomes.append(executor.apply(request))
    before, _ = provider.load()
    mutated = copy.deepcopy(request)
    mutated["command"]["lease_ttl_seconds"] = 601
    observation.outcomes.append(executor.apply(mutated))
    observation.head, _ = provider.load()
    observation.flags["state_unchanged_after_rejection"] = observation.head == before
    return observation


def stale_generation_does_not_duplicate(handles: Callable[[], Any]) -> Observation:
    """Stale provider generation is refused rather than replayed.

    A handle observes a generation, the document advances behind it, and the
    stale expectation is then offered for a raw CAS. The refused attempt must
    not write, and the executor's bounded reload must land exactly one further
    authority transition with no duplicate receipt.
    """

    provider = handles()
    bootstrap(provider)
    stale = RecordingProvider(handles())
    stale_generation = stale.load()[1]

    observation = Observation()
    observation.outcomes.append(
        executor_for(provider).apply(claim("agent-a", "todo-1"))
    )
    current_head, current_generation = provider.load()
    stale_attempt = stale.compare_and_put(stale_generation, current_head)
    observation.flags["stale_cas_refused"] = stale_attempt["result"] == "conflict"
    observation.flags["stale_cas_wrote_nothing"] = provider.load()[1] == current_generation
    observation.flags["stale_expectation_offered"] = bool(
        stale.cas_expectations and stale.cas_expectations[0] == stale_generation
    )

    observation.outcomes.append(
        executor_for(stale).apply(claim("agent-b", "todo-2"))
    )
    observation.head, _ = provider.load()
    return observation


SCENARIOS: dict[str, Callable[[Callable[[], Any]], Observation]] = {
    "same_target_competition": same_target_competition,
    "independent_targets_rebase": independent_targets_rebase,
    "replay_after_interleaved_write": replay_after_interleaved_write,
    "operation_identity_reuse": operation_identity_reuse,
    "stale_generation_does_not_duplicate": stale_generation_does_not_duplicate,
}

EXPECTED: dict[str, Expectation] = {
    "same_target_competition": Expectation(
        results=("applied", "conflict"),
        reasons=(None, "todo_revision_mismatch"),
        authority_revision=1,
        receipts=("op-agent-a-todo-1",),
        claimed_by=(("todo-1", "agent-a"), ("todo-2", None)),
        todo_revisions=(("todo-1", 8), ("todo-2", 7)),
    ),
    "independent_targets_rebase": Expectation(
        results=("applied", "applied"),
        reasons=(None, None),
        authority_revision=2,
        receipts=("op-agent-a-todo-1", "op-agent-b-todo-2"),
        claimed_by=(("todo-1", "agent-a"), ("todo-2", "agent-b")),
        todo_revisions=(("todo-1", 8), ("todo-2", 8)),
    ),
    "replay_after_interleaved_write": Expectation(
        results=("applied", "applied", "already_applied"),
        reasons=(None, None, None),
        authority_revision=2,
        receipts=("op-A", "op-B"),
        claimed_by=(("todo-1", "agent-a"), ("todo-2", "agent-b")),
        todo_revisions=(("todo-1", 8), ("todo-2", 8)),
        # A replayed operation is a read, not a second transition.
        flags=(("replay_returns_original_receipt", True),),
    ),
    "operation_identity_reuse": Expectation(
        results=("applied", "rejected"),
        reasons=(None, "operation_identity_mismatch"),
        authority_revision=1,
        receipts=("op-A",),
        claimed_by=(("todo-1", "agent-a"), ("todo-2", None)),
        todo_revisions=(("todo-1", 8), ("todo-2", 7)),
        flags=(("state_unchanged_after_rejection", True),),
    ),
    "stale_generation_does_not_duplicate": Expectation(
        results=("applied", "applied"),
        reasons=(None, None),
        authority_revision=2,
        receipts=("op-agent-a-todo-1", "op-agent-b-todo-2"),
        claimed_by=(("todo-1", "agent-a"), ("todo-2", "agent-b")),
        todo_revisions=(("todo-1", 8), ("todo-2", 8)),
        flags=(
            ("stale_expectation_offered", True),
            ("stale_cas_refused", True),
            ("stale_cas_wrote_nothing", True),
        ),
    ),
}


@pytest.fixture
def handles(tmp_path) -> Callable[[], Any]:
    """Return a factory for fresh provider handles onto one shared store."""

    directory = tmp_path / "coordination"
    return lambda: FileCoordinationProvider(directory, GOAL_ID)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_claim_work_contract_holds_on_the_shipped_provider(name, handles):
    expected = EXPECTED[name]
    observation = SCENARIOS[name](handles)

    assert tuple(item["result"] for item in observation.outcomes) == expected.results
    assert tuple(item.get("reason") for item in observation.outcomes) == expected.reasons
    assert observation.head["authority_revision"] == expected.authority_revision
    assert tuple(sorted(observation.head["receipt_index"])) == expected.receipts

    todos = observation.head["coordination"]["todos"]
    assert tuple(
        (todo_id, todos[todo_id]["claimed_by"]) for todo_id, _ in expected.claimed_by
    ) == expected.claimed_by
    assert tuple(
        (todo_id, todos[todo_id]["todo_revision"])
        for todo_id, _ in expected.todo_revisions
    ) == expected.todo_revisions

    for flag, value in expected.flags:
        assert observation.flags.get(flag) is value, flag
