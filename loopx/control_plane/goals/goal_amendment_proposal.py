"""Governed goal amendment proposal admission and retention (RFC Stage 2).

This adapter implements RFC §5 steps 1–2 for
``goal_amendment_proposal_v0``: a registered proposer submits a proposal,
the TypeScript-owned reducer (``goal.amendment_proposal.admit``) validates
schema completeness, actor identity, a closed ``amendment_class`` enum,
bounded evidence pointers, the causal membership of the linked replan
obligation and affected Todos (against authoritative typed inventories
this adapter derives), and the relation between the proposal's
``base_state_event_basis_sequence``/``base_source_basis_digest`` and the
currently derived goal basis, and the resulting admission record is
retained in an append-only journal.

Stage 2 is proposal only: admission has **zero canonical effect**. No goal
state is written, no frontier changes, and the state event log is never
appended to. The journal lives beside ``task-leases`` under
``runtime/goals/<goal_id>/amendment-proposals/`` so retention can never
advance the basis head it reports against.

There is no approval field, no ``approved`` status, and no commit path.
Admission outcomes are fact tokens only: ``admitted`` (including the
``base_source_basis_unverifiable`` fact when no event log exists) or
``needs_rebase`` (a behind or digest-mismatched base stays admitted and
retained, never silently dropped or merged — RFC §7). A schema violation
or an invalid causal reference (a replan obligation or affected Todo that
is not an open member of this Goal) fails closed as a request rejection,
the equivalent ``rejected_schema`` outcome, and nothing is retained.
Governed commit belongs to Stage 3+ behind the
``GoalAmendmentAuthority``.

The derived basis (``state_event_basis_sequence``, ``revision_basis``,
``source_basis_digest``) comes from the Stage 1 read-only projection
(``project_shared_goal_alignment``), which also fails closed on unknown
goals and unregistered proposers. This is an event-log-derived source
projection basis, not a canonical intent revision/digest: the RFC §3.1
intent envelope has no typed storage yet, and the proposal binds to the
basis under Stage 1's downgraded naming.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...agent_registry import registered_agent_ids_for_goal
from ...event_sourced_state import now_utc_iso
from ...file_lock import exclusive_file_lock
from ...registry import resolve_state_file
from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ..todos.contract import (
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_id,
)
from ..todos.projection import todo_item_is_actionable_open
from ..work_items.autonomous_replan_obligation import (
    ensure_replan_novelty_policy,
)
from .goal_frontier import (
    AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
    autonomous_replan_is_required,
    autonomous_replan_scope_decision,
)
from .shared_goal_alignment import (
    DEFAULT_REGISTRY_RELATIVE_PATH,
    _parsed_active_state,
    _registered_goal,
    project_shared_goal_alignment,
)

GOAL_AMENDMENT_PROPOSAL_EFFECT_METHOD = "goal.amendment_proposal.admit"
GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION = "goal_amendment_proposal_request_v0"
GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION = (
    "goal_amendment_proposal_admission_v0"
)
GOAL_AMENDMENT_PROPOSAL_SCHEMA_VERSION = "goal_amendment_proposal_v0"
GOAL_AMENDMENT_CLASSES = (
    "lane_route",
    "shared_work_graph",
    "shared_acceptance",
    "protected_authority",
)
GOAL_AMENDMENT_PROPOSAL_ADMISSIONS = ("admitted", "needs_rebase")
GOAL_AMENDMENT_PROPOSAL_ADMISSION_FACTS = (
    "base_state_event_basis_sequence_behind_derived_head",
    "base_source_basis_digest_mismatch",
    "base_source_basis_unverifiable",
)
AMENDMENT_PROPOSAL_JOURNAL_DIRNAME = "amendment-proposals"
AMENDMENT_PROPOSAL_JOURNAL_BASENAME = "journal.jsonl"
_SHA256_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def amendment_proposal_journal_path(
    *,
    runtime_root: Path,
    goal_id: str,
) -> Path:
    """Return the append-only proposal journal path for one goal."""

    return (
        runtime_root
        / "goals"
        / goal_id
        / AMENDMENT_PROPOSAL_JOURNAL_DIRNAME
        / AMENDMENT_PROPOSAL_JOURNAL_BASENAME
    )


def read_goal_amendment_proposal_journal(
    *,
    runtime_root: Path,
    goal_id: str,
) -> list[dict[str, Any]]:
    """Read retained proposal admission rows in journal (append) order."""

    return _read_journal_rows(
        amendment_proposal_journal_path(
            runtime_root=runtime_root,
            goal_id=goal_id,
        )
    )


def admit_goal_amendment_proposal(
    *,
    proposal: Mapping[str, Any],
    project: Path,
    registry_path: Path | None = None,
    runtime_root: Path | None = None,
    status_item: Mapping[str, Any] | None = None,
    project_asset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one proposal, retain its admission, and return the row.

    Admission also validates the proposal's causal membership (RFC §5
    "impact scope"): ``replan_obligation_id`` must resolve to an open,
    required replan obligation of the same Goal whose agent lane includes
    the proposer, and every ``affected_todo_ids`` entry must resolve to an
    actionable open Todo of the same Goal. The authoritative inventories
    are derived here — obligations from ``status_item``/``project_asset``
    (the LoopX quota/status projection payloads), Todos from the Goal's
    active state file — and handed to the reducer as typed facts. When
    ``status_item``/``project_asset`` are omitted the obligation inventory
    is empty and any proposal referencing a replan obligation fails
    closed: admission never trusts a causal chain on string shape alone.

    Raises ``TypeError`` when ``proposal`` or the registry/JTS payload is
    not the expected object type, and ``ValueError`` for any other
    admission-blocking defect (unknown goal, unregistered proposer,
    schema violation, evidence over budget, an invalid replan obligation
    / affected Todo reference, a base basis sequence ahead of the derived
    head, or a conflicting replayed ``proposal_id``). Nothing is retained
    when admission fails.
    """

    if not isinstance(proposal, Mapping):
        raise TypeError("proposal must be a goal_amendment_proposal_v0 object")
    proposal_goal_id = str(proposal.get("goal_id") or "").strip()
    if not proposal_goal_id:
        raise ValueError("proposal.goal_id must be a non-empty registered goal id")
    proposer_agent_id = normalize_todo_claimed_by(
        proposal.get("proposer_agent_id")
    )
    if not proposer_agent_id:
        raise ValueError("proposal.proposer_agent_id must be a public-safe agent id")

    effective_registry_path = (
        registry_path if registry_path is not None
        else project / DEFAULT_REGISTRY_RELATIVE_PATH
    )
    try:
        registry_payload = json.loads(
            effective_registry_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        raise ValueError(
            f"goal registry is unreadable: {effective_registry_path}"
        ) from None
    if not isinstance(registry_payload, dict):
        raise TypeError("goal registry must contain a JSON object")

    effective_runtime_root = (
        runtime_root
        if runtime_root is not None
        else _runtime_root_from_registry(registry_payload)
    )

    # Stage 1 reuse: the read-only projection fails closed on unknown goals
    # and unregistered proposers, and derives the source basis (state event
    # log append sequence, or markdown fallback) the proposal's base binds
    # against — both its sequence and its digest.
    alignment = project_shared_goal_alignment(
        goal_id=proposal_goal_id,
        agent_id=proposer_agent_id,
        project=project,
        registry_path=effective_registry_path,
        runtime_root=effective_runtime_root,
        status_item=status_item,
        project_asset=project_asset,
    )
    source_basis = alignment.get("source_basis")
    if not isinstance(source_basis, Mapping):
        raise TypeError("TypeScript shared goal alignment shape mismatch")
    derived_basis = {
        "state_event_basis_sequence": source_basis.get(
            "state_event_basis_sequence"
        ),
        "revision_basis": source_basis.get("revision_basis"),
        "source_basis_digest": source_basis.get("source_basis_digest"),
    }

    goal = _registered_goal(registry_payload, goal_id=proposal_goal_id)
    state_path = resolve_state_file(project, goal.get("state_file"))
    if state_path is None:
        raise ValueError(
            f"goal state file is missing for {proposal_goal_id}"
        )
    open_replan_obligations = _open_replan_obligation_inventory(
        goal_id=proposal_goal_id,
        registered_agents=registered_agent_ids_for_goal(goal),
        status_item=status_item,
        project_asset=project_asset,
    )
    goal_todo_inventory = _goal_todo_inventory(
        state_text=state_path.read_text(encoding="utf-8"),
        goal=goal,
        state_path=state_path,
    )

    request = {
        "schema_version": GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION,
        "proposal": dict(proposal),
        "derived_basis": derived_basis,
        "open_replan_obligations": open_replan_obligations,
        "goal_todo_inventory": goal_todo_inventory,
    }
    try:
        admission = effect_runtime_result(
            GOAL_AMENDMENT_PROPOSAL_EFFECT_METHOD,
            request,
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    _check_admission_shape(admission, proposal=proposal)
    if effective_runtime_root is None:
        raise ValueError(
            "proposal retention requires a runtime root "
            "(registry common_runtime_root or an explicit runtime_root)"
        )
    return _retain_admission(
        amendment_proposal_journal_path(
            runtime_root=effective_runtime_root,
            goal_id=proposal_goal_id,
        ),
        admission=dict(admission),
    )


def _open_replan_obligation_inventory(
    *,
    goal_id: str,
    registered_agents: list[str],
    status_item: Mapping[str, Any] | None,
    project_asset: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Derive the goal's open, required replan obligations as typed facts.

    Candidates come from every agent lane in ``autonomous_replan_
    obligations_by_agent`` plus the goal-level ``autonomous_replan_
    obligation`` on both authority sources (``status_item`` and
    ``project_asset``). Each candidate is normalized by
    ``ensure_replan_novelty_policy`` (which derives the deterministic
    ``obligation_id``), closed/settled ones (``required`` false) are
    dropped, and the scope semantics are folded into an explicit
    ``bound_agent_ids`` list — agent-scoped obligations keep their owners,
    unscoped ones keep their deterministic peer assignment — so the
    TypeScript reducer only compares membership, never re-derives scope.
    """

    item = status_item if isinstance(status_item, Mapping) else {}
    asset = project_asset if isinstance(project_asset, Mapping) else {}
    candidates: list[dict[str, Any]] = []
    for source in (item, asset):
        by_agent = source.get("autonomous_replan_obligations_by_agent")
        if isinstance(by_agent, Mapping):
            candidates.extend(
                dict(value)
                for value in by_agent.values()
                if isinstance(value, Mapping)
            )
        goal_level = source.get("autonomous_replan_obligation")
        if isinstance(goal_level, Mapping):
            candidates.append(dict(goal_level))

    inventory: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        normalized = ensure_replan_novelty_policy(candidate)
        if not autonomous_replan_is_required(normalized):
            continue
        obligation_id = normalized.get("obligation_id")
        if not obligation_id or obligation_id in inventory:
            continue
        bound_agent_ids = [
            agent_id
            for agent_id in registered_agents
            if autonomous_replan_scope_decision(
                normalized,
                agent_id=agent_id,
                registered_agent_ids=registered_agents,
            ).get("applies")
        ]
        inventory[str(obligation_id)] = {
            "schema_version": AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
            "obligation_id": str(obligation_id),
            "goal_id": goal_id,
            "required": True,
            "bound_agent_ids": bound_agent_ids,
        }
    return list(inventory.values())


def _goal_todo_inventory(
    *,
    state_text: str,
    goal: Mapping[str, Any],
    state_path: Path,
) -> list[dict[str, Any]]:
    """Derive the goal's actionable open Todos as typed facts.

    ``claimed_by``/``bound_agent`` are diagnostic companions only:
    admission checks existence, openness, and goal membership — shared
    amendments legitimately affect peer-claimed work, and lease
    disposition belongs to the Stage 3 commit step (RFC §5 step 4).
    """

    _, items = _parsed_active_state(
        state_text,
        goal=dict(goal),
        state_path=state_path,
    )
    inventory: list[dict[str, Any]] = []
    seen_todo_ids: set[str] = set()
    for todo_item in items:
        if not todo_item_is_actionable_open(todo_item):
            continue
        todo_id = normalize_todo_id(todo_item.get("todo_id"))
        if not todo_id or todo_id in seen_todo_ids:
            continue
        seen_todo_ids.add(todo_id)
        inventory.append(
            {
                "todo_id": todo_id,
                "status": "open",
                "task_class": (
                    str(todo_item.get("task_class") or "").strip() or None
                ),
                "claimed_by": normalize_todo_claimed_by(
                    todo_item.get("claimed_by")
                ),
                "bound_agent": normalize_todo_bound_agent(
                    todo_item.get("bound_agent")
                ),
            }
        )
    return inventory


def _check_admission_shape(
    admission: object,
    *,
    proposal: Mapping[str, Any],
) -> None:
    """Fail closed on any reducer output that stops being the contract.

    This mirrors the Stage 1 adapter's defensive shape check: the reducer
    output must stay a non-authoritative admission record with
    ``canonical_effect: none``, a closed admission/fact/class enum, a
    ``sha256`` proposal digest, and the submitted identities echoed back.
    """

    if not isinstance(admission, Mapping):
        raise TypeError("TypeScript goal amendment admission shape mismatch")
    if (
        admission.get("schema_version")
        != GOAL_AMENDMENT_PROPOSAL_ADMISSION_SCHEMA_VERSION
        or admission.get("canonical_effect") != "none"
        or admission.get("admission") not in GOAL_AMENDMENT_PROPOSAL_ADMISSIONS
        or admission.get("amendment_class") not in GOAL_AMENDMENT_CLASSES
        or admission.get("goal_id") != str(proposal.get("goal_id") or "").strip()
        or admission.get("proposer_agent_id")
        != normalize_todo_claimed_by(proposal.get("proposer_agent_id"))
        or admission.get("proposal_id")
        != str(proposal.get("proposal_id") or "").strip().lower()
        or not _SHA256_DIGEST_PATTERN.fullmatch(
            str(admission.get("proposal_digest") or "")
        )
    ):
        raise RuntimeError("TypeScript goal amendment admission shape mismatch")
    facts = admission.get("admission_facts")
    if not isinstance(facts, list) or any(
        fact not in GOAL_AMENDMENT_PROPOSAL_ADMISSION_FACTS for fact in facts
    ):
        raise RuntimeError("TypeScript goal amendment admission shape mismatch")


def _retain_admission(
    journal_path: Path,
    *,
    admission: Mapping[str, Any],
) -> dict[str, Any]:
    """Append one admission row; replaying identical content is idempotent."""

    proposal_id = str(admission.get("proposal_id") or "")
    proposal_digest = str(admission.get("proposal_digest") or "")
    with exclusive_file_lock(journal_path):
        rows = _read_journal_rows(journal_path)
        for row in rows:
            if row.get("proposal_id") != proposal_id:
                continue
            if row.get("proposal_digest") != proposal_digest:
                raise ValueError(
                    "conflicting proposal_id already retained with different "
                    f"content: {proposal_id}"
                )
            return dict(row)
        record = {
            **dict(admission),
            "recorded_at": now_utc_iso(),
            "journal_append_sequence": len(rows) + 1,
        }
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with journal_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
            )
    return record


def _read_journal_rows(journal_path: Path) -> list[dict[str, Any]]:
    if not journal_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    text = journal_path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid proposal journal JSONL at line {line_number}: {exc}"
            ) from None
        if not isinstance(row, dict):
            raise TypeError(
                f"invalid proposal journal row at line {line_number}"
            )
        rows.append(row)
    return rows


def _runtime_root_from_registry(
    registry_payload: Mapping[str, Any],
) -> Path | None:
    raw = registry_payload.get("common_runtime_root")
    text = str(raw or "").strip()
    return Path(text).expanduser() if text else None
