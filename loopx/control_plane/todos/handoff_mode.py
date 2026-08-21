"""Per-goal handoff mode: which ownership authority governs todo handoffs.

The goal's ACTIVE_GOAL_STATE.md YAML front-matter may declare ``handoff_mode``:

* absent / ``legacy`` (default): today's dual soft-claim + hard-lease
  behavior, byte-for-byte. The known soft-claim/hard-lease split brain stays
  open in this mode by design; it is surfaced additively, never silently
  repaired.
* ``soft_claim``: the markdown claim is the only ownership record. Task-lease
  acquire/renew/transfer are typed-rejected; release and inspect stay allowed
  for cleanup and observability of legacy leftovers.
* ``hard_lease``: ownership changes on an existing todo require the acting
  agent to hold that todo's time-active task lease, and the completion fence
  becomes mandatory for both user-role and agent-role todos. An exact linked
  user-gate decision-scope override authorizes only the exact linked decision
  transition; it does not bypass the completion fence. The delegated
  ``coordination.todo_lifecycle_authority`` override is the one audited door
  through the gate.

The mode lives in the front-matter (not the registry) because the markdown
file is the artifact that travels across endpoints; lease JSON and registry
are host-local. Pre-NoKV the file syncs last-writer-wins, so two hosts can
briefly disagree about the mode; that window is documented, not engineered
around here.

The v0 transition scan is materialized-state only: it reads open claims from
the locked ``ACTIVE_GOAL_STATE.md`` text plus time-active local lease files. It
does not merge the event projection, so a claim that exists only in the event
log can be missed. A successful switch is therefore not a proof that every
projection is quiescent. The selected mode's typed per-write gate remains the
safety boundary for later governed ownership and completion mutations,
including event-projected completion.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from typing import Any

from ..coordination.authority_core import (
    CoordinationSnapshot,
    DecisionOutcome,
    HandoffMode,
    HandoffModeTransitionCommand,
    decide,
)
from ..goals.active_state_metadata import parse_state_frontmatter
from .contract import normalize_todo_claimed_by

HANDOFF_MODE_SCHEMA_VERSION = "goal_handoff_mode_v0"
HANDOFF_MODE_FRONTMATTER_KEY = "handoff_mode"
HANDOFF_MODE_LEGACY = "legacy"
HANDOFF_MODE_SOFT_CLAIM = "soft_claim"
HANDOFF_MODE_HARD_LEASE = "hard_lease"
HANDOFF_MODE_VALUES = (
    HANDOFF_MODE_LEGACY,
    HANDOFF_MODE_SOFT_CLAIM,
    HANDOFF_MODE_HARD_LEASE,
)
DELEGATED_AUTHORITY_MODE = "delegated_orchestration_override"


class HandoffModeError(ValueError):
    """Typed handoff-mode failure; mirrors TaskLeaseError's code/payload shape."""

    def __init__(
        self, message: str, *, code: str, payload: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


def normalize_handoff_mode(value: Any) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return HANDOFF_MODE_LEGACY
    if candidate not in HANDOFF_MODE_VALUES:
        raise HandoffModeError(
            f"unsupported handoff_mode {candidate!r}; expected one of: "
            + ", ".join(HANDOFF_MODE_VALUES),
            code="invalid_handoff_mode",
            payload={"handoff_mode": candidate, "supported": list(HANDOFF_MODE_VALUES)},
        )
    return candidate


def goal_handoff_mode(state_text: str) -> str:
    """Read the goal handoff mode from active-state text; absent means legacy."""

    front_matter = parse_state_frontmatter(state_text)
    return normalize_handoff_mode(front_matter.get(HANDOFF_MODE_FRONTMATTER_KEY))


def _resolve_state(
    *,
    registry_path: Path,
    goal_id: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> tuple[Path | None, Path]:
    from ...todos import resolve_todo_state_path

    return resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )


def goal_handoff_mode_for_goal(
    *,
    registry_path: Path,
    goal_id: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> str:
    _project, resolved_state_file = _resolve_state(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    return goal_handoff_mode(resolved_state_file.read_text(encoding="utf-8"))


def enter_todo_ownership_handoff_gate(
    stack: ExitStack,
    *,
    state_text: str,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    mutation_authority: dict[str, Any],
    actor_agent_id: str | None,
    ownership_mutation: bool,
) -> dict[str, Any]:
    """Gate one claimed_by mutation on an existing todo behind the goal mode.

    Returns additive payload fields (always ``handoff_mode``; plus the door
    marker or the held holder-gate receipt in hard_lease mode). In hard_lease
    mode the per-goal lease lock is entered on ``stack`` so it stays held
    through the markdown commit, matching the completion fence's
    state-lock-then-lease-lock order.
    """

    mode = goal_handoff_mode(state_text)
    extras: dict[str, Any] = {"handoff_mode": mode}
    if not ownership_mutation or mode != HANDOFF_MODE_HARD_LEASE:
        return extras
    if mutation_authority.get("mode") == DELEGATED_AUTHORITY_MODE:
        extras["handoff_gate_overridden"] = True
        return extras
    from ..work_items.task_lease import hold_handoff_lease_holder_gate

    extras["task_lease_holder_gate"] = stack.enter_context(
        hold_handoff_lease_holder_gate(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            actor_agent_id=actor_agent_id,
        )
    )
    return extras


def enter_added_todo_ownership_handoff_gate(
    stack: ExitStack,
    *,
    lines: list[str],
    state_text: str,
    registry_path: Path,
    goal_id: str,
    role: str,
    text: str,
    claimed_by: str | None,
    actor_agent_id: str | None,
) -> dict[str, Any]:
    """Gate the ``todo add`` path when it would reassign an existing todo.

    ``todo add`` matches an open todo by text and upserts its metadata, so a
    ``claimed_by`` argument on that branch changes the claim of a todo that
    may already hold a lease. Creating a todo stays ungated in every mode: a
    todo id that does not exist yet cannot hold one. Re-adding a todo with the
    claim it already carries is not an ownership change and is not gated.

    The delegated-authority door is not offered here. Reassignment under a
    ``coordination.todo_lifecycle_authority`` grant goes through
    ``todo update --claimed-by``, which is the verb that owns that action.
    """

    from ...todos import matching_todo_block  # loopx.todos, deferred: import cycle
    from .active_state_editing import section_bounds

    bounds = section_bounds(lines, role)
    existing = (
        matching_todo_block(
            lines, bounds[0], bounds[1], text, role=role, source_section=bounds[2]
        )
        if bounds
        else None
    )
    requested = normalize_todo_claimed_by(claimed_by) if claimed_by else None
    current = normalize_todo_claimed_by(existing.get("claimed_by")) if existing else None
    return enter_todo_ownership_handoff_gate(
        stack,
        state_text=state_text,
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=str(existing.get("todo_id") or "") if existing else "",
        mutation_authority={},
        actor_agent_id=actor_agent_id,
        ownership_mutation=(
            role == "agent"
            and existing is not None
            and requested is not None
            and requested != current
        ),
    )


def resolve_todo_completion_handoff(
    *,
    state_text: str,
    mutation_authority: dict[str, Any],
) -> dict[str, Any]:
    """Resolve mode plus the delegated-authority door for one todo completion."""

    mode = goal_handoff_mode(state_text)
    extras: dict[str, Any] = {"handoff_mode": mode}
    if (
        mode == HANDOFF_MODE_HARD_LEASE
        and mutation_authority.get("mode") == DELEGATED_AUTHORITY_MODE
    ):
        extras["handoff_gate_overridden"] = True
    return extras


def show_goal_handoff_mode(
    *,
    registry_path: Path,
    goal_id: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
    _project, resolved_state_file = _resolve_state(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    front_matter = parse_state_frontmatter(
        resolved_state_file.read_text(encoding="utf-8")
    )
    raw = front_matter.get(HANDOFF_MODE_FRONTMATTER_KEY)
    return {
        "ok": True,
        "schema_version": HANDOFF_MODE_SCHEMA_VERSION,
        "action": "show",
        "goal_id": goal_id,
        "handoff_mode": normalize_handoff_mode(raw),
        "source": "frontmatter" if str(raw or "").strip() else "default",
        "state_file": str(resolved_state_file),
    }


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int]:
    if not lines or lines[0].strip() != "---":
        raise HandoffModeError(
            "active state file has no YAML front-matter; add one before setting "
            "handoff_mode",
            code="state_frontmatter_missing",
        )
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return 1, index
    raise HandoffModeError(
        "active state front-matter is not terminated by ---",
        code="state_frontmatter_missing",
    )


def _quiescence_offenders(
    *,
    registry_path: Path,
    goal_id: str,
    state_text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return blockers visible to the v0 materialized-state scan.

    Event-projection overlays are intentionally outside this pre-NoKV scan.
    Callers must not interpret an empty result as an authority-wide safety
    guarantee; later governed writes still cross the selected handoff-mode
    gate.
    """

    from ..work_items.task_lease import (
        lease_is_active,
        read_lease,
        runtime_root_from_registry,
        task_lease_dir,
    )
    from .active_state_todo_parser import parse_active_state_todos

    claimed: list[dict[str, Any]] = []
    todos = parse_active_state_todos(state_text, item_limit=None)
    for role in ("user_todos", "agent_todos"):
        summary = todos.get(role)
        items = summary.get("items") if isinstance(summary, dict) else []
        for item in items or []:
            if not isinstance(item, dict) or item.get("done") is True:
                continue
            owner = normalize_todo_claimed_by(item.get("claimed_by"))
            if owner:
                claimed.append(
                    {
                        "todo_id": item.get("todo_id"),
                        "claimed_by": owner,
                        "status": item.get("status"),
                    }
                )
    leases: list[dict[str, Any]] = []
    runtime_root = runtime_root_from_registry(registry_path, None)
    lease_dir = task_lease_dir(runtime_root=runtime_root, goal_id=goal_id)
    if lease_dir.exists():
        for path in sorted(lease_dir.glob("todo_*.json")):
            lease = read_lease(path)
            if lease_is_active(lease):
                leases.append(
                    {
                        "todo_id": lease.get("todo_id"),
                        "owner": lease.get("owner"),
                        "expires_at": lease.get("expires_at"),
                        "lease_path": str(path),
                    }
                )
    return claimed, leases


def _authority_offender_tokens(
    offenders: list[dict[str, Any]],
    *,
    kind: str,
) -> tuple[str, ...]:
    """Keep every offender represented without changing its public payload."""

    return tuple(
        str(offender.get("todo_id") or f"<missing-{kind}-todo-id:{index}>")
        for index, offender in enumerate(offenders, start=1)
    )


def set_goal_handoff_mode(
    *,
    registry_path: Path,
    goal_id: str,
    mode: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
    """Set the goal handoff mode; requires a quiescent goal for transitions.

    In v0, quiescence means no open todo materialized in the locked active-state
    Markdown carries a claimed_by owner and no time-active lease file exists
    under the goal. The scan does not overlay event-only todos, so success is a
    pre-NoKV migration check rather than an authority-wide safety guarantee;
    every later governed ownership or completion write still crosses the
    selected mode's typed gate. Visible non-quiescence refuses with a typed
    offender list and there is no force override. Hand-editing the front-matter
    bypasses this check and is out of contract.
    """

    from ...file_lock import exclusive_file_lock
    from ..work_items.task_lease import (
        runtime_root_from_registry,
        task_lease_lock_path,
    )

    requested = normalize_handoff_mode(mode)
    if not str(mode or "").strip():
        raise HandoffModeError(
            "handoff-mode set requires an explicit --mode value",
            code="invalid_handoff_mode",
        )
    _project, resolved_state_file = _resolve_state(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    with exclusive_file_lock(resolved_state_file, operation="handoff_mode_set"):
        original = resolved_state_file.read_text(encoding="utf-8")
        previous_raw = parse_state_frontmatter(original).get(
            HANDOFF_MODE_FRONTMATTER_KEY
        )
        try:
            previous = normalize_handoff_mode(previous_raw)
        except HandoffModeError as exc:
            previous = str(previous_raw or "").strip()
            previous_mode_fields = {
                "previous_mode": previous,
                "previous_mode_valid": False,
                "previous_mode_error_code": exc.code,
            }
        else:
            previous_mode_fields = {
                "previous_mode": previous,
                "previous_mode_valid": True,
            }
        payload = {
            "ok": True,
            "schema_version": HANDOFF_MODE_SCHEMA_VERSION,
            "action": "set",
            "goal_id": goal_id,
            **previous_mode_fields,
            "handoff_mode": requested,
            "state_file": str(resolved_state_file),
        }
        if previous == requested:
            payload["changed"] = False
            return payload
        lease_lock = task_lease_lock_path(
            runtime_root=runtime_root_from_registry(registry_path, None),
            goal_id=goal_id,
        )
        with exclusive_file_lock(lease_lock, operation="handoff_mode_set"):
            claimed, leases = _quiescence_offenders(
                registry_path=registry_path,
                goal_id=goal_id,
                state_text=original,
            )
            requested_core_mode = HandoffMode(requested)
            if previous in HANDOFF_MODE_VALUES:
                previous_core_mode = HandoffMode(previous)
            else:
                # Invalid persisted front-matter can be repaired, but it is
                # never an idempotent transition.  Pick any distinct typed
                # source mode; quiescence is independent of the source mode.
                previous_core_mode = next(
                    candidate
                    for candidate in HandoffMode
                    if candidate is not requested_core_mode
                )
            transition = decide(
                CoordinationSnapshot(
                    handoff_mode=previous_core_mode,
                    active_claimed_todo_ids=_authority_offender_tokens(
                        claimed,
                        kind="claimed",
                    ),
                    active_lease_todo_ids=_authority_offender_tokens(
                        leases,
                        kind="lease",
                    ),
                ),
                HandoffModeTransitionCommand(requested_mode=requested_core_mode),
            )
            if transition.code == "handoff_mode_not_quiescent":
                raise HandoffModeError(
                    "handoff_mode can only change while the goal is quiescent: "
                    f"{len(claimed)} claimed open todo(s), "
                    f"{len(leases)} time-active lease(s)",
                    code="handoff_mode_not_quiescent",
                    payload={
                        "goal_id": goal_id,
                        "requested_mode": requested,
                        **previous_mode_fields,
                        "claimed_todos": claimed,
                        "active_leases": leases,
                    },
                )
            if transition.outcome is not DecisionOutcome.APPLY:
                raise HandoffModeError(
                    f"handoff_mode transition rejected by authority core: "
                    f"{transition.code}",
                    code=transition.code,
                    payload={
                        "goal_id": goal_id,
                        "requested_mode": requested,
                        **previous_mode_fields,
                        "claimed_todos": claimed,
                        "active_leases": leases,
                    },
                )
            lines = original.splitlines()
            open_index, close_index = _frontmatter_bounds(lines)
            for index in range(open_index, close_index):
                if (
                    lines[index].split(":", 1)[0].strip()
                    == HANDOFF_MODE_FRONTMATTER_KEY
                ):
                    lines[index] = f"{HANDOFF_MODE_FRONTMATTER_KEY}: {requested}"
                    break
            else:
                lines.insert(
                    close_index, f"{HANDOFF_MODE_FRONTMATTER_KEY}: {requested}"
                )
            new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
            resolved_state_file.write_text(new_text, encoding="utf-8")
    payload["changed"] = True
    return payload
