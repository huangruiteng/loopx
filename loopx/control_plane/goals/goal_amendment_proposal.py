"""Governed goal amendment proposal admission and retention (RFC Stage 2).

This adapter implements RFC §5 steps 1–2 for
``goal_amendment_proposal_v0``: a registered proposer submits a proposal,
the TypeScript-owned reducer (``goal.amendment_proposal.admit``) validates
schema completeness, actor identity, a closed ``amendment_class`` enum,
bounded evidence pointers, and the relation between the proposal's
``base_goal_revision`` and the currently derived goal basis, and the
resulting admission record is retained in an append-only journal.

Stage 2 is proposal only: admission has **zero canonical effect**. No goal
state is written, no frontier changes, and the state event log — the
canonical revision carrier — is never appended to. The journal lives beside
``task-leases`` under ``runtime/goals/<goal_id>/amendment-proposals/`` so
retention can never advance the canonical head it reports against.

There is no approval field, no ``approved`` status, and no commit path.
Admission outcomes are fact tokens only: ``admitted`` (including the
``base_revision_unverifiable`` fact when no event log exists) or
``needs_rebase`` (a stale base stays admitted and retained, never silently
dropped or merged — RFC §7). A schema violation fails closed as a request
rejection, the equivalent ``rejected_schema`` outcome, and nothing is
retained. Governed commit belongs to Stage 3+ behind the
``GoalAmendmentAuthority``.

The derived basis (``goal_revision``, ``revision_basis``,
``intent_digest``) comes from the Stage 1 read-only projection
(``project_shared_goal_alignment``), which also fails closed on unknown
goals and unregistered proposers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...event_sourced_state import now_utc_iso
from ...file_lock import exclusive_file_lock
from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ..todos.contract import normalize_todo_claimed_by
from .shared_goal_alignment import (
    DEFAULT_REGISTRY_RELATIVE_PATH,
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
    "base_revision_behind_derived_head",
    "base_revision_unverifiable",
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
) -> dict[str, Any]:
    """Validate one proposal, retain its admission, and return the row.

    Raises ``ValueError`` for any admission-blocking defect (unknown goal,
    unregistered proposer, schema violation, evidence over budget, a base
    revision ahead of the derived head, or a conflicting replayed
    ``proposal_id``). Nothing is retained when admission fails.
    """

    if not isinstance(proposal, Mapping):
        raise ValueError("proposal must be a goal_amendment_proposal_v0 object")
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
        raise ValueError("goal registry must contain a JSON object")

    effective_runtime_root = (
        runtime_root
        if runtime_root is not None
        else _runtime_root_from_registry(registry_payload)
    )

    # Stage 1 reuse: the read-only projection fails closed on unknown goals
    # and unregistered proposers, and derives the canonical revision basis
    # (state event log append sequence, or markdown fallback) the proposal's
    # base revision is checked against.
    alignment = project_shared_goal_alignment(
        goal_id=proposal_goal_id,
        agent_id=proposer_agent_id,
        project=project,
        registry_path=effective_registry_path,
        runtime_root=effective_runtime_root,
    )
    canonical_goal = alignment.get("canonical_goal")
    if not isinstance(canonical_goal, Mapping):
        raise RuntimeError("TypeScript shared goal alignment shape mismatch")
    derived_basis = {
        "goal_revision": canonical_goal.get("goal_revision"),
        "revision_basis": canonical_goal.get("revision_basis"),
        "intent_digest": canonical_goal.get("intent_digest"),
    }

    request = {
        "schema_version": GOAL_AMENDMENT_PROPOSAL_REQUEST_SCHEMA_VERSION,
        "proposal": dict(proposal),
        "derived_basis": derived_basis,
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
        raise RuntimeError("TypeScript goal amendment admission shape mismatch")
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
            raise ValueError(
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
