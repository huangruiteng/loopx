"""Per-goal handoff mode: which ownership authority governs todo handoffs.

Before promotion the active-state frontmatter declares ``handoff_mode``; afterward
the selected canonical provider owns it. Public show/set route by that authority:

* absent / ``legacy`` (default): today's dual soft-claim + hard-lease
  behavior, byte-for-byte. The known soft-claim/hard-lease split brain stays
  open in this mode by design; it is surfaced additively, never silently
  repaired.
* ``soft_claim``: the Todo claim is the only ownership record. Task-lease
  acquire/renew/transfer are typed-rejected; release and inspect stay allowed
  for cleanup and observability of legacy leftovers.
* ``hard_lease``: ownership changes on an existing todo require the acting
  agent to hold that todo's time-active task lease, and the completion fence
  becomes mandatory for both user-role and agent-role todos. An exact linked
  user-gate decision-scope override authorizes only the exact linked decision
  transition; it does not bypass the completion fence. The delegated
  ``coordination.todo_lifecycle_authority`` override is the one audited door
  through the gate.

Canonical mode, complete Todo/lease quiescence, CAS and replay share one TypeScript
transaction. Stale or missing Markdown and local lease files are not fallback
sources. The legacy mode below remains a frontmatter compatibility contract.

The unpromoted v0 transition scan is materialized-state only: it reads open claims from
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
    OwnershipGate,
    decide,
    ownership_gate_requirement,
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
    return str(show_goal_handoff_mode(registry_path=registry_path, goal_id=goal_id,
        project=project, state_file=state_file)["handoff_mode"])


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
    runtime_root: Path | None = None,
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
    gate = ownership_gate_requirement(
        handoff_mode=HandoffMode(mode),
        ownership_mutation=ownership_mutation,
        authority_mode=str(mutation_authority.get("mode") or "") or None,
    )
    if gate is OwnershipGate.NOT_REQUIRED:
        return extras
    if gate is OwnershipGate.DELEGATED_OVERRIDE:
        extras["handoff_gate_overridden"] = True
        return extras
    from ..work_items.task_lease import hold_handoff_lease_holder_gate

    extras["task_lease_holder_gate"] = stack.enter_context(
        hold_handoff_lease_holder_gate(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            actor_agent_id=actor_agent_id,
            runtime_root=runtime_root,
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
    runtime_root: Path | None = None,
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
        runtime_root=runtime_root,
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
    runtime_root_arg: str | None = None,
) -> dict[str, Any]:
    from ..work_items.task_lease import runtime_root_from_registry
    from .provider_handoff_mode import read_canonical_handoff_mode

    canonical = read_canonical_handoff_mode(
        runtime_root=runtime_root_from_registry(registry_path, runtime_root_arg), goal_id=goal_id)
    if canonical is not None:
        return {"ok": True, "schema_version": HANDOFF_MODE_SCHEMA_VERSION, "action": "show",
                "goal_id": goal_id, **canonical,
                "handoff_mode": normalize_handoff_mode(canonical["handoff_mode"]), "source": "canonical_provider"}
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
    runtime_root: Path | None = None,
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
    from .active_state_todo_parser import parse_todo_source
    from .todo_summary import structured_todo_item, todo_projection_sort_key

    # Quiescence needs normalized ownership facts, not status/resume/capability display.
    # Retain the public offender order without evaluating unrelated projection rules.
    claimed: list[dict[str, Any]] = []
    todos, _, sections = parse_todo_source(state_text)
    for role in ("user", "agent"):
        items = [structured_todo_item(item, role=role, source_section=sections[role]) for item in todos[role]]
        for item in sorted(items, key=todo_projection_sort_key):
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
    if runtime_root is None:
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


def _previous_handoff_mode_fields(
    previous_raw: object,
) -> tuple[str, dict[str, Any]]:
    """Type the persisted front-matter mode; invalid values stay reportable."""

    try:
        previous = normalize_handoff_mode(previous_raw)
    except HandoffModeError as exc:
        previous = str(previous_raw or "").strip()
        return previous, {
            "previous_mode": previous,
            "previous_mode_valid": False,
            "previous_mode_error_code": exc.code,
        }
    return previous, {"previous_mode": previous, "previous_mode_valid": True}


def _write_handoff_mode_frontmatter(lines: list[str], requested: str) -> None:
    """Replace or insert the handoff_mode key inside the front-matter block."""

    open_index, close_index = _frontmatter_bounds(lines)
    for index in range(open_index, close_index):
        if lines[index].split(":", 1)[0].strip() == HANDOFF_MODE_FRONTMATTER_KEY:
            lines[index] = f"{HANDOFF_MODE_FRONTMATTER_KEY}: {requested}"
            return
    lines.insert(close_index, f"{HANDOFF_MODE_FRONTMATTER_KEY}: {requested}")


def set_goal_handoff_mode(
    *,
    registry_path: Path,
    goal_id: str,
    mode: str,
    project: Path | None = None,
    state_file: Path | None = None,
    runtime_root_arg: str | None = None,
    operation_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Set the authoritative goal mode; changed modes require quiescence.

    Promoted Goals use one provider transaction; the remaining text below
    describes the unpromoted compatibility writer.

    In v0, quiescence means no open todo materialized in the locked active-state
    Markdown carries a claimed_by owner and no time-active lease file exists
    under the goal. The scan does not overlay event-only todos, so success is a
    pre-NoKV migration check rather than an authority-wide safety guarantee;
    every later governed ownership or completion write still crosses the
    selected mode's typed gate. Visible non-quiescence refuses with a typed
    offender list and there is no force override. Hand-editing the front-matter
    bypasses this check and is out of contract.
    """

    from ...file_lock import (
        exclusive_cross_runtime_file_lock as exclusive_file_lock,
    )
    from ..work_items.task_lease import (
        runtime_root_from_registry,
        task_lease_lock_path,
    )
    from ..coordination.legacy_writer_fence import (
        LegacyCoordinationWriterFenced,
        legacy_todo_write_transaction,
        require_legacy_coordination_write_allowed,
    )
    from ..coordination.local_authority import (
        LocalCoordinationAuthorityRejection,
        LocalCoordinationAuthorityUnavailable,
    )
    from ..coordination.runtime_shadow_writer_adapter import (
        write_captured_todo_state,
        begin_todo_runtime_shadow_capture,
        settle_todo_runtime_shadow_capture,
    )

    requested = normalize_handoff_mode(mode)
    if not str(mode or "").strip():
        raise HandoffModeError(
            "handoff-mode set requires an explicit --mode value",
            code="invalid_handoff_mode",
        )
    from .provider_handoff_mode import set_canonical_handoff_mode

    runtime_root = runtime_root_from_registry(registry_path, runtime_root_arg)
    try:
        canonical = set_canonical_handoff_mode(
            runtime_root=runtime_root,
            goal_id=goal_id,
            mode=requested,
            operation_id=operation_id,
            dry_run=dry_run,
        )
    except LocalCoordinationAuthorityRejection:
        raise
    except LocalCoordinationAuthorityUnavailable:
        # A present legacy fence is the admission boundary for this caller.
        # Re-check it when canonical dispatch is unavailable so an outage cannot
        # turn a fenced legacy writer into an attempted Markdown mutation.
        try:
            require_legacy_coordination_write_allowed(
                runtime_root=runtime_root,
                goal_id=goal_id,
            )
        except LegacyCoordinationWriterFenced:
            raise
        raise
    if canonical is not None:
        return canonical
    if operation_id is not None:
        raise HandoffModeError("--operation-id requires canonical authority", code="handoff_mode_operation_id_unsupported")
    _project, resolved_state_file = _resolve_state(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    # The already resolved root also governs the legacy lock, scan and capture.
    with legacy_todo_write_transaction(
        registry_path, goal_id, resolved_state_file, None, "handoff_mode_set",
        dry_run, runtime_root=runtime_root,
    ):
        original = resolved_state_file.read_text(encoding="utf-8")
        previous, previous_mode_fields = _previous_handoff_mode_fields(
            parse_state_frontmatter(original).get(HANDOFF_MODE_FRONTMATTER_KEY)
        )
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
            if dry_run:
                payload["dry_run"] = True
            return payload
        capture = None if dry_run else begin_todo_runtime_shadow_capture(
            registry_path=registry_path, runtime_root=runtime_root, goal_id=goal_id,
            state_path=resolved_state_file, write_class="handoff_mode_set",
            original_text=original,
        )
        lease_lock = task_lease_lock_path(runtime_root=runtime_root, goal_id=goal_id)
        with exclusive_file_lock(lease_lock, operation="handoff_mode_set"):
            claimed, leases = _quiescence_offenders(
                registry_path=registry_path,
                goal_id=goal_id,
                state_text=original,
                runtime_root=runtime_root,
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
            if dry_run:
                return {**payload, "dry_run": True, "changed": True}
            lines = original.splitlines()
            _write_handoff_mode_frontmatter(lines, requested)
            new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
            write_captured_todo_state(capture, runtime_root=runtime_root, goal_id=goal_id,
                state_path=resolved_state_file, text=new_text)
    payload["changed"] = True
    from ..coordination.local_authority_shadow_observation import observe_local_authority_commit

    evidence = observe_local_authority_commit(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=goal_id,
        observation_trigger=f"handoff_mode_set:{previous}:{requested}",
    )
    if evidence is not None:
        payload["authority_shadow"] = evidence
    return settle_todo_runtime_shadow_capture(
        payload, registry_path=registry_path, runtime_root=runtime_root,
        goal_id=goal_id, write_class="handoff_mode_set", capture=capture,
        observe_legacy=False, emit_disabled=False,
    )
