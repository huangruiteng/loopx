"""The authority execution layer over a coordination provider (RFC section 5).

The executor owns exactly what the Stage 1 core refuses: envelope
normalization and request digests, aggregate-level preconditions
(todo revisions, eligibility snapshots, dependency and gate booleans),
receipt construction and replay, wall-clock expiry minting, the three version
domains (``provider_generation`` / ``authority_revision`` / ``lease_epoch``),
and the bounded load -> decide -> compare_and_put -> reload loop. Every
domain decision about actors and leases is delegated to
``authority_core.decide``; no coordination rule is re-derived here.

The only command in this slice is ``claim_work`` (RFC section 5.1): one
accepted transition records the claim, the lease with its next epoch, and the
original receipt in the same provider CAS.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from .authority_core import (
    CoordinationSnapshot,
    DecisionOutcome,
    LeaseAcquireCommand,
    LeaseReleaseCommand,
    LeaseRenewCommand,
    LeaseSnapshot,
    LifecycleGrant,
    TodoAction,
    TodoMutationCommand,
    decide,
)
from .head import (
    HeadMigrationRequired,
    HeadValidationError,
    canonical_head_bytes,
    claim_snapshot_for_todo,
    evidence_contract_violation,
    validated_head,
)

COMMAND_SCHEMA_VERSION = "loopx_command_v0"
RECEIPT_SCHEMA_VERSION = "loopx_authority_receipt_v0"

_ENVELOPE_FIELDS = {"schema_version", "operation_id", "actor", "goal_id", "command", "transport"}
_ACTOR_FIELDS = {"agent_id", "device_id"}
# Per-verb closed command field sets (RFC section 5: unknown fields fail
# closed; the request digest covers every semantic field automatically).
_COMMAND_FIELD_SETS = {
    "claim_work": {
        "type",
        "todo_id",
        "expected_todo_revision",
        "expected_preconditions",
        "lease_ttl_seconds",
    },
    "renew_work": {
        "type",
        "todo_id",
        "expected_todo_revision",
        "lease_id",
        "expected_lease_epoch",
        "lease_ttl_seconds",
    },
    "release_work": {
        "type",
        "todo_id",
        "expected_todo_revision",
        "lease_id",
        "expected_lease_epoch",
    },
    "reclaim_work": {
        "type",
        "todo_id",
        "expected_todo_revision",
        "expected_preconditions",
        "lease_ttl_seconds",
    },
    "complete_work": {
        "type",
        "todo_id",
        "expected_todo_revision",
        "lease_id",
        "expected_lease_epoch",
        "no_followup",
        "successor_todo_ids",
        "evidence",
    },
}
_SUCCESSOR_ID_PATTERN = re.compile(r"^todo_[a-z0-9_-]{3,64}$")
# Reclaim only takes over once the authority's own clock has seen the lease
# expired for at least this grace window, bounding clock skew between the
# superseded holder and the adjudicating authority. Recorded per receipt.
DEFAULT_RECLAIM_GRACE_SECONDS = 30.0
_PRECONDITION_FIELDS = {
    "authorization_projection_revision",
    "authorization_projection_digest",
    "dependency_revision",
    "gate_revision",
}
_MAX_CAS_ATTEMPTS = 8
# The local task-lease authority's ceiling
# (work_items.task_lease.MAX_TASK_LEASE_TTL_SECONDS), mirrored here so this
# module's import closure stays inside the strict type gate; a pin test
# asserts the two never drift.
MAX_LEASE_TTL_SECONDS = 24 * 60 * 60

# Core code -> RFC reason vocabulary for the claim_work slice. Actor and
# owner ineligibility collapse onto the RFC's one actor reason; ownership
# codes that the executor's aggregate prechecks should have intercepted are
# aggregate-integrity failures, so they fail closed instead of masquerading
# as caller errors.
_CORE_TO_RFC_REASON = {
    "actor_required": "actor_ineligible",
    "actor_not_registered": "actor_ineligible",
    "actor_excluded": "actor_ineligible",
    "claim_actor_mismatch": "actor_ineligible",
    "invalid_owner": "actor_ineligible",
    "owner_not_registered": "actor_ineligible",
    "owner_excluded_from_todo": "actor_ineligible",
    "todo_not_open": "todo_not_open",
    "todo_not_found": "todo_not_found",
    # Stage 3: the core detects a fence the executor precheck let through
    # only when ownership diverged between precheck and decision; both are
    # the same caller-visible truth - the fence the caller holds is stale.
    "lease_cas_mismatch": "stale_lease_fence",
    "lease_not_active": "lease_not_active",
    "handoff_mode_requires_lease": "lease_not_active",
    "lease_fence_required": "stale_lease_fence",
}
_FAIL_CLOSED_CORE_CODES = {
    "claim_owner_mismatch",
    "owner_conflicts_with_claim",
    "invalid_lease_snapshot",
    # The executor synthesizes the reclaim grant itself; a delegation
    # rejection means the executor and core disagree about that synthesis.
    "delegation_action_not_granted",
    "delegation_reason_required",
    "handoff_mode_lease_claim_divergence",
}


def _classified(plan: Any) -> dict[str, Any]:
    """Map one non-APPLY core TransitionPlan onto an RFC result class."""

    if plan.code in _FAIL_CLOSED_CORE_CODES:
        # The executor's revision and open/unclaimed prechecks make these
        # unreachable on a well-formed head; reaching one means the aggregate
        # and the core disagree, which is an integrity failure, not caller error.
        return {"result": "failed", "reason": f"aggregate_integrity:{plan.code}"}
    if plan.outcome is DecisionOutcome.CONFLICT:
        return {"result": "conflict", "reason": plan.code}
    if plan.outcome is DecisionOutcome.NO_CHANGE:
        # A replay the receipt index does not know about cannot be proven to
        # be this operation's own effect (acceptance check 6): fail closed.
        return {"result": "failed", "reason": f"state_without_receipt:{plan.code}"}
    return {
        "result": "rejected",
        "reason": _CORE_TO_RFC_REASON.get(plan.code, plan.code),
    }


class EnvelopeError(ValueError):
    """The command envelope violates the reviewed v0 contract."""


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _continuation_for_write(*, no_followup: bool, has_successor: bool) -> str:
    """The local completion_state rule, mirrored so the executor's import
    closure stays inside the strict type gate; a pin test asserts equality
    with the TS-backed facade on every input combination."""

    if no_followup and has_successor:
        raise EnvelopeError(
            "todo completion cannot record both no_followup and a successor"
        )
    if no_followup:
        return "no_followup"
    if has_successor:
        return "successor"
    return "active_goal"


def _lease_id(operation_id: str) -> str:
    return "lease_" + hashlib.sha256(f"lease:{operation_id}".encode()).hexdigest()[:24]


def _format_time(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _parse_time(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def sample_claim_envelope(
    *,
    goal_id: str,
    operation_id: str,
    agent_id: str,
    device_id: str,
    todo_id: str,
    expected_todo_revision: int,
    expected_preconditions: dict[str, Any],
    lease_ttl_seconds: int,
    transport: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one well-formed ``claim_work`` envelope (tests and adapters)."""

    envelope: dict[str, Any] = {
        "schema_version": COMMAND_SCHEMA_VERSION,
        "operation_id": operation_id,
        "actor": {"agent_id": agent_id, "device_id": device_id},
        "goal_id": goal_id,
        "command": {
            "type": "claim_work",
            "todo_id": todo_id,
            "expected_todo_revision": expected_todo_revision,
            "expected_preconditions": copy.deepcopy(expected_preconditions),
            "lease_ttl_seconds": lease_ttl_seconds,
        },
    }
    if transport is not None:
        envelope["transport"] = copy.deepcopy(transport)
    return envelope


def sample_work_envelope(
    *,
    goal_id: str,
    operation_id: str,
    agent_id: str,
    device_id: str,
    command: dict[str, Any],
    transport: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one well-formed command envelope for any Stage 3 verb."""

    envelope: dict[str, Any] = {
        "schema_version": COMMAND_SCHEMA_VERSION,
        "operation_id": operation_id,
        "actor": {"agent_id": agent_id, "device_id": device_id},
        "goal_id": goal_id,
        "command": copy.deepcopy(command),
    }
    if transport is not None:
        envelope["transport"] = copy.deepcopy(transport)
    return envelope


def _validated_reclaim_grace(value: Any) -> float:
    """The grace window is a skew bound: it may only DELAY a takeover.

    A NaN grace makes ``expired_for < grace`` always false so every active
    lease becomes reclaimable, a negative grace advances the takeover before
    expiry, and bool is the usual coercion accident - so the configuration
    boundary rejects everything but a finite non-negative number.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            "reclaim_grace_seconds must be a finite non-negative number"
        )
    try:
        grace = float(value)
    except OverflowError as error:
        raise ValueError(
            "reclaim_grace_seconds must be a finite non-negative number"
        ) from error
    if not math.isfinite(grace) or grace < 0.0:
        raise ValueError(
            "reclaim_grace_seconds must be a finite non-negative number"
        )
    return grace


class CoordinationAuthorityExecutor:
    """Apply normalized coordination commands through one provider CAS.

    This executor is the RFC's reference implementation: LoopX's runtime
    does not construct it yet (coverage-only per the visible governance
    ledger), and wiring it to a product entry point is a later-stage,
    owner-gated decision.
    """

    def __init__(
        self,
        provider: Any,
        *,
        goal_id: str,
        now: Callable[[], float],
        reclaim_grace_seconds: float = DEFAULT_RECLAIM_GRACE_SECONDS,
    ):
        self.provider = provider
        self.goal_id = goal_id
        self.now = now
        self.reclaim_grace_seconds = _validated_reclaim_grace(reclaim_grace_seconds)

    # ---- envelope normalization (RFC section 5) -----------------------------

    def _semantic_request(self, envelope: Any) -> dict[str, Any]:
        if not isinstance(envelope, dict):
            raise EnvelopeError("command envelope must be an object")
        unknown = set(envelope) - _ENVELOPE_FIELDS
        if unknown:
            raise EnvelopeError(f"unknown command envelope fields: {sorted(unknown)}")
        if envelope.get("schema_version") != COMMAND_SCHEMA_VERSION:
            raise EnvelopeError("unsupported command envelope schema")
        operation_id = envelope.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise EnvelopeError("operation_id must be a non-empty string")
        if envelope.get("goal_id") != self.goal_id:
            raise EnvelopeError("command goal_id does not match this authority")
        if "transport" in envelope and not isinstance(envelope["transport"], dict):
            raise EnvelopeError("transport metadata must be an object")
        actor = envelope.get("actor")
        if not isinstance(actor, dict) or set(actor) != _ACTOR_FIELDS:
            raise EnvelopeError("actor must contain only agent_id and device_id")
        if not all(isinstance(actor[key], str) and actor[key] for key in _ACTOR_FIELDS):
            raise EnvelopeError("actor ids must be non-empty strings")
        command = envelope.get("command")
        if not isinstance(command, dict):
            raise EnvelopeError("command must be an object")
        command_type = command.get("type")
        if command_type not in _COMMAND_FIELD_SETS:
            raise EnvelopeError(
                f"unsupported command type; this slice supports "
                f"{sorted(_COMMAND_FIELD_SETS)}"
            )
        expected_fields = _COMMAND_FIELD_SETS[command_type]
        if set(command) != expected_fields:
            raise EnvelopeError(
                f"{command_type} fields do not match the v0 contract"
            )
        if not isinstance(command["todo_id"], str) or not command["todo_id"]:
            raise EnvelopeError("todo_id must be a non-empty string")
        revision = command["expected_todo_revision"]
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise EnvelopeError("expected_todo_revision must be an integer")
        if "expected_preconditions" in expected_fields:
            self._validated_preconditions(command["expected_preconditions"])
        if "lease_ttl_seconds" in expected_fields:
            ttl = command["lease_ttl_seconds"]
            # The bound is the local task-lease authority's own ceiling, so
            # the shared envelope cannot mint a lease the local contract
            # would refuse, and an unbounded caller value can never reach
            # wall-clock arithmetic (an astronomical TTL overflows timestamp
            # formatting).
            if (
                not isinstance(ttl, int)
                or isinstance(ttl, bool)
                or ttl <= 0
                or ttl > MAX_LEASE_TTL_SECONDS
            ):
                raise EnvelopeError(
                    f"lease_ttl_seconds must be between 1 and {MAX_LEASE_TTL_SECONDS}"
                )
        if "lease_id" in expected_fields:
            lease_id = command["lease_id"]
            epoch = command["expected_lease_epoch"]
            if not isinstance(lease_id, str) or not lease_id:
                raise EnvelopeError("lease_id must be a non-empty string")
            if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 1:
                raise EnvelopeError(
                    "expected_lease_epoch must be a positive integer"
                )
        if command_type == "complete_work":
            self._validated_completion_command(command)
        # Transport metadata is deliberately excluded from the semantic request.
        return {
            "schema_version": COMMAND_SCHEMA_VERSION,
            "operation_id": operation_id,
            "actor": {key: actor[key] for key in sorted(_ACTOR_FIELDS)},
            "goal_id": self.goal_id,
            "command": {
                key: copy.deepcopy(command[key]) for key in sorted(expected_fields)
            },
        }

    @staticmethod
    def _validated_preconditions(preconditions: Any) -> None:
        if not isinstance(preconditions, dict) or set(preconditions) != _PRECONDITION_FIELDS:
            raise EnvelopeError("expected_preconditions fields do not match v0")
        for field in (
            "authorization_projection_revision",
            "dependency_revision",
            "gate_revision",
        ):
            value = preconditions[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise EnvelopeError("expected_preconditions revisions must be non-negative")
        digest = preconditions["authorization_projection_digest"]
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise EnvelopeError("expected authorization projection digest is invalid")

    @staticmethod
    def _validated_completion_command(command: dict[str, Any]) -> None:
        no_followup = command["no_followup"]
        successors = command["successor_todo_ids"]
        evidence = command["evidence"]
        if not isinstance(no_followup, bool):
            raise EnvelopeError("no_followup must be a boolean")
        if not isinstance(successors, list) or not all(
            isinstance(item, str) and _SUCCESSOR_ID_PATTERN.fullmatch(item)
            for item in successors
        ):
            raise EnvelopeError(
                "successor_todo_ids must be public todo ids (todo_<slug>)"
            )
        if len(set(successors)) != len(successors):
            raise EnvelopeError("successor_todo_ids must be distinct")
        if no_followup and successors:
            # The same contradiction the local durable-completion write
            # refuses: a completion cannot record both.
            raise EnvelopeError(
                "todo completion cannot record both no_followup and a successor"
            )
        if evidence is not None:
            # One oracle with head validation: what the boundary refuses,
            # a stored head can never carry, and vice versa.
            violation = evidence_contract_violation(evidence)
            if violation is not None:
                raise EnvelopeError(violation)

    # ---- replay -------------------------------------------------------------

    def _replay(
        self,
        head: dict[str, Any],
        provider_generation: int,
        operation_id: str,
        request_digest: str,
    ) -> dict[str, Any] | None:
        entry = head["receipt_index"].get(operation_id)
        if entry is None:
            return None
        if entry.get("request_digest") != request_digest:
            return {
                "result": "rejected",
                "reason": "operation_identity_mismatch",
                "operation_id": operation_id,
                "observed_authority_revision": head["authority_revision"],
                "provider_generation": provider_generation,
            }
        receipt = entry.get("original_receipt")
        if not isinstance(receipt, dict):
            raise HeadValidationError("receipt entry lacks original_receipt")
        return self._success("already_applied", receipt, head, provider_generation)

    def _success(
        self,
        result: str,
        receipt: dict[str, Any],
        head: dict[str, Any],
        generation: int,
    ) -> dict[str, Any]:
        lease = head["coordination"]["leases"].get(receipt["todo_id"])
        if lease is None or (
            lease.get("lease_id") != receipt.get("lease_id")
            or lease.get("lease_epoch") != receipt.get("lease_epoch")
        ):
            status = "superseded"
        elif _parse_time(lease["expires_at"]) <= self.now():
            status = "expired"
        else:
            status = "active"
        return {
            "result": result,
            "original_receipt": copy.deepcopy(receipt),
            "observed_authority_revision": head["authority_revision"],
            "authorization_status": status,
            "provider_generation": generation,
        }

    # ---- the one transition of this slice -----------------------------------

    def _claim_transition(
        self,
        head: dict[str, Any],
        request: dict[str, Any],
        request_digest: str,
    ) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
        """Return either a typed non-apply dict, or (next_head, receipt)."""

        command = request["command"]
        todo_id = command["todo_id"]
        todo = head["coordination"]["todos"].get(todo_id)
        if todo is None:
            return {"result": "rejected", "reason": "todo_not_found"}
        if todo["todo_revision"] != command["expected_todo_revision"]:
            return {
                "result": "conflict",
                "reason": "todo_revision_mismatch",
                "expected_todo_revision": command["expected_todo_revision"],
                "observed_todo_revision": todo["todo_revision"],
            }
        eligibility = todo["eligibility"]
        observed_preconditions = {
            field: eligibility[field] for field in _PRECONDITION_FIELDS
        }
        if observed_preconditions != command["expected_preconditions"]:
            return {
                "result": "conflict",
                "reason": "precondition_snapshot_mismatch",
                "expected_preconditions": copy.deepcopy(
                    command["expected_preconditions"]
                ),
                "observed_preconditions": observed_preconditions,
            }
        if todo["status"] != "open" or todo["claimed_by"] is not None:
            return {"result": "rejected", "reason": "todo_not_open"}
        if eligibility["dependencies_satisfied"] is not True:
            return {"result": "rejected", "reason": "dependencies_not_satisfied"}
        if eligibility["gates_open"] is not True:
            return {"result": "rejected", "reason": "gate_closed"}

        actor = request["actor"]["agent_id"]
        snapshot = claim_snapshot_for_todo(head, todo_id)

        core_lease = self._acquire_and_claim(
            snapshot, actor, request["operation_id"], command["lease_ttl_seconds"]
        )
        if isinstance(core_lease, dict):
            return core_lease

        now = float(self.now())
        expires_at = _format_time(now + command["lease_ttl_seconds"])
        next_head = copy.deepcopy(head)
        next_head["authority_revision"] += 1
        next_todo = next_head["coordination"]["todos"][todo_id]
        next_todo.update(
            {
                "todo_revision": todo["todo_revision"] + 1,
                # LoopX keeps a claimed todo open; ``claimed_by`` plus the
                # lease carry ownership without a new lifecycle status.
                "status": "open",
                "claimed_by": actor,
                "last_lease_epoch": core_lease.lease_epoch,
            }
        )
        next_head["coordination"]["leases"][todo_id] = {
            "lease_id": core_lease.idempotency_key,
            "owner": core_lease.owner,
            "lease_epoch": core_lease.lease_epoch,
            "expires_at": expires_at,
            "write_scopes": list(core_lease.write_scopes),
        }
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "operation_id": request["operation_id"],
            "request_digest": request_digest,
            "command": "claim_work",
            "actor": copy.deepcopy(request["actor"]),
            "todo_id": todo_id,
            "accepted_authority_revision": next_head["authority_revision"],
            "accepted_todo_revision": next_todo["todo_revision"],
            "applied_at": _format_time(now),
            "lease_id": core_lease.idempotency_key,
            "lease_epoch": core_lease.lease_epoch,
            "expires_at": expires_at,
        }
        next_head["receipt_index"][request["operation_id"]] = {
            "request_digest": request_digest,
            "original_receipt": copy.deepcopy(receipt),
        }
        return next_head, receipt

    # ---- Stage 3 shared helpers ---------------------------------------------

    def _store_binding_fence(
        self,
        head: dict[str, Any],
        provider_generation: int,
    ) -> dict[str, Any] | None:
        """The lineage binding fence (RFC Stage 3 gate).

        The head is permanently bound at bootstrap to the provider-issued
        store identity. A head observed through a provider whose identity
        differs was restored or copied into a different store lineage;
        every command fails closed there until an explicit, reviewed
        re-bootstrap re-binds it - restored bytes never grant live
        authority.
        """

        identity = self.provider.store_identity()
        if head["store_binding"] == identity:
            return None
        return {
            "result": "failed",
            "reason": "store_lineage_mismatch",
            "head_store_binding": head["store_binding"],
            "provider_store_identity": identity,
            "provider_generation": provider_generation,
        }

    def _todo_prechecks(
        self,
        head: dict[str, Any],
        command: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return (todo, None) or (None, typed non-apply dict)."""

        todo = head["coordination"]["todos"].get(command["todo_id"])
        if todo is None:
            return None, {"result": "rejected", "reason": "todo_not_found"}
        if todo["todo_revision"] != command["expected_todo_revision"]:
            return None, {
                "result": "conflict",
                "reason": "todo_revision_mismatch",
                "expected_todo_revision": command["expected_todo_revision"],
                "observed_todo_revision": todo["todo_revision"],
            }
        if todo["status"] != "open":
            return None, {"result": "rejected", "reason": "todo_not_open"}
        return todo, None

    def _lease_fence(
        self,
        head: dict[str, Any],
        command: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Validate the caller-held fence. Return (lease, None) or typed dict.

        This is the stale-fence rejection at the heart of recoverable
        execution: after a reclaim mints a new lease generation, every write
        the superseded executor sends still carries the old (lease_id,
        lease_epoch) pair and lands here, terminally - a stale fence is never
        rebased past.
        """

        lease = head["coordination"]["leases"].get(command["todo_id"])
        if lease is None:
            return None, {"result": "rejected", "reason": "lease_missing"}
        if (
            lease["lease_id"] != command["lease_id"]
            or lease["lease_epoch"] != command["expected_lease_epoch"]
        ):
            return None, {
                "result": "rejected",
                "reason": "stale_lease_fence",
                "observed_lease_epoch": lease["lease_epoch"],
                "expected_lease_epoch": command["expected_lease_epoch"],
            }
        return lease, None

    @staticmethod
    def _holder_gate(
        lease: dict[str, Any],
        actor: str,
    ) -> dict[str, Any] | None:
        """A correct fence in the wrong hands is still not authority: only
        the recorded holder may renew, release, or complete. Keeping this
        precheck here also keeps the core's owner_conflicts_with_claim code
        unreachable, preserving its aggregate-integrity classification."""

        if lease["owner"] != actor:
            return {
                "result": "rejected",
                "reason": "not_lease_holder",
                "lease_owner": lease["owner"],
            }
        return None

    def _lease_is_active(self, lease: dict[str, Any]) -> bool:
        """Expiry adjudication happens here, against the authority's own
        clock and the loaded head's expires_at - never against the caller's
        opinion of time (RFC section 6.4)."""

        return float(self.now()) < _parse_time(lease["expires_at"])

    def _held_lease_context(
        self,
        head: dict[str, Any],
        command: dict[str, Any],
        actor: str,
    ) -> tuple[dict[str, Any], dict[str, Any], CoordinationSnapshot] | dict[str, Any]:
        """Adjudicate the opening every holder verb shares.

        Renew, release, and complete all face the same sequence: todo
        prechecks, the stale-lease fence, the live holder gate, then a
        snapshot carrying the authority's own liveness verdict for the core
        to adjudicate against. Returns (todo, lease, snapshot) or the typed
        non-apply dict.
        """

        todo, rejection = self._todo_prechecks(head, command)
        if rejection is not None:
            return rejection
        assert todo is not None
        lease, rejection = self._lease_fence(head, command)
        if rejection is not None:
            return rejection
        assert lease is not None
        rejection = self._holder_gate(lease, actor)
        if rejection is not None:
            return rejection
        snapshot = claim_snapshot_for_todo(
            head, command["todo_id"], lease_active=self._lease_is_active(lease)
        )
        return todo, lease, snapshot

    @staticmethod
    def _acquire_and_claim(
        snapshot: CoordinationSnapshot,
        actor: str,
        operation_id: str,
        ttl_seconds: int,
    ) -> LeaseSnapshot | dict[str, Any]:
        """Mint a lease, then claim under it - the shared ownership tail.

        Composition order is fixed by the Stage 1 core: the lease is minted
        first, then the claim passes the hard-lease holder gate against the
        freshly minted lease. Claim-first would silently bypass the
        Appendix B invariant that ownership changes require the holder.
        Reclaim reuses this tail unchanged, so a reclaimed lease passes the
        same true holder gate as any first claim.
        """

        acquire_plan = decide(
            snapshot,
            LeaseAcquireCommand(
                owner=actor,
                idempotency_key=_lease_id(operation_id),
                ttl_seconds=ttl_seconds,
            ),
        )
        if acquire_plan.outcome is not DecisionOutcome.APPLY:
            return _classified(acquire_plan)
        assert acquire_plan.next_snapshot is not None
        claim_plan = decide(
            acquire_plan.next_snapshot,
            TodoMutationCommand(
                action=TodoAction.CLAIM,
                actor_agent_id=actor,
                requested_claimed_by=actor,
                ownership_mutation=True,
            ),
        )
        if claim_plan.outcome is not DecisionOutcome.APPLY:
            return _classified(claim_plan)
        assert claim_plan.next_snapshot is not None
        core_lease = claim_plan.next_snapshot.lease
        assert core_lease is not None
        return core_lease

    def _next_head_for(
        self,
        head: dict[str, Any],
        request: dict[str, Any],
        request_digest: str,
        *,
        todo_id: str,
        command_name: str,
        receipt_extra: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Clone the head, advance authority/todo revisions, mint the receipt."""

        next_head = copy.deepcopy(head)
        next_head["authority_revision"] += 1
        next_todo = next_head["coordination"]["todos"][todo_id]
        next_todo["todo_revision"] += 1
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "operation_id": request["operation_id"],
            "request_digest": request_digest,
            "command": command_name,
            "actor": copy.deepcopy(request["actor"]),
            "todo_id": todo_id,
            "accepted_authority_revision": next_head["authority_revision"],
            "accepted_todo_revision": next_todo["todo_revision"],
            "applied_at": _format_time(float(self.now())),
            **receipt_extra,
        }
        next_head["receipt_index"][request["operation_id"]] = {
            "request_digest": request_digest,
            "original_receipt": copy.deepcopy(receipt),
        }
        return next_head, receipt

    # ---- Stage 3 transitions ------------------------------------------------

    def _renew_transition(
        self,
        head: dict[str, Any],
        request: dict[str, Any],
        request_digest: str,
    ) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
        command = request["command"]
        actor = request["actor"]["agent_id"]
        context = self._held_lease_context(head, command, actor)
        if isinstance(context, dict):
            return context
        _todo, lease, snapshot = context
        plan = decide(
            snapshot,
            LeaseRenewCommand(
                owner=actor,
                idempotency_key=command["lease_id"],
                ttl_seconds=command["lease_ttl_seconds"],
                expected_version=command["expected_lease_epoch"],
            ),
        )
        if plan.outcome is not DecisionOutcome.APPLY:
            return _classified(plan)
        now = float(self.now())
        expires_at = _format_time(now + command["lease_ttl_seconds"])
        next_head, receipt = self._next_head_for(
            head,
            request,
            request_digest,
            todo_id=command["todo_id"],
            command_name="renew_work",
            receipt_extra={
                "lease_id": command["lease_id"],
                "lease_epoch": lease["lease_epoch"],
                "expires_at": expires_at,
            },
        )
        next_head["coordination"]["leases"][command["todo_id"]]["expires_at"] = (
            expires_at
        )
        return next_head, receipt

    def _release_transition(
        self,
        head: dict[str, Any],
        request: dict[str, Any],
        request_digest: str,
    ) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
        command = request["command"]
        actor = request["actor"]["agent_id"]
        context = self._held_lease_context(head, command, actor)
        if isinstance(context, dict):
            return context
        _todo, lease, snapshot = context
        # Release is the holder giving up early, so the claim is cleared
        # first while the holder gate is still real; an expired lease is
        # resolved by reclaim, not release (the core rejects the clear).
        clear_plan = decide(
            snapshot,
            TodoMutationCommand(
                action=TodoAction.UPDATE,
                actor_agent_id=actor,
                clear_claim=True,
                ownership_mutation=True,
            ),
        )
        if clear_plan.outcome is not DecisionOutcome.APPLY:
            return _classified(clear_plan)
        assert clear_plan.next_snapshot is not None
        release_plan = decide(
            clear_plan.next_snapshot,
            LeaseReleaseCommand(
                owner=actor,
                idempotency_key=command["lease_id"],
                expected_version=command["expected_lease_epoch"],
            ),
        )
        if release_plan.outcome is not DecisionOutcome.APPLY:
            return _classified(release_plan)
        next_head, receipt = self._next_head_for(
            head,
            request,
            request_digest,
            todo_id=command["todo_id"],
            command_name="release_work",
            receipt_extra={
                "lease_id": command["lease_id"],
                "lease_epoch": lease["lease_epoch"],
            },
        )
        next_todo = next_head["coordination"]["todos"][command["todo_id"]]
        next_todo["claimed_by"] = None
        # last_lease_epoch stays: the watermark is the shared aggregate's
        # no-ABA terminal record, so a re-claim mints strictly above it.
        del next_head["coordination"]["leases"][command["todo_id"]]
        return next_head, receipt

    def _reclaim_transition(
        self,
        head: dict[str, Any],
        request: dict[str, Any],
        request_digest: str,
    ) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
        command = request["command"]
        todo, rejection = self._todo_prechecks(head, command)
        if rejection is not None:
            return rejection
        assert todo is not None
        eligibility = todo["eligibility"]
        observed = {field: eligibility[field] for field in _PRECONDITION_FIELDS}
        if observed != command["expected_preconditions"]:
            return {
                "result": "conflict",
                "reason": "precondition_snapshot_mismatch",
                "expected_preconditions": copy.deepcopy(
                    command["expected_preconditions"]
                ),
                "observed_preconditions": observed,
            }
        if todo["claimed_by"] is None:
            return {"result": "rejected", "reason": "todo_not_claimed"}
        lease = head["coordination"]["leases"].get(command["todo_id"])
        if lease is None:
            # An open, claimed todo always carries its lease in a valid head.
            return {
                "result": "failed",
                "reason": "aggregate_integrity:claim_without_lease",
            }
        now = float(self.now())
        expired_for = now - _parse_time(lease["expires_at"])
        if expired_for < self.reclaim_grace_seconds:
            return {
                "result": "rejected",
                "reason": "lease_not_reclaimable",
                "expires_at": lease["expires_at"],
                "reclaim_grace_seconds": self.reclaim_grace_seconds,
            }
        actor = request["actor"]["agent_id"]
        # Reclaim is a standing delegation to eligible agents, adjudicated by
        # the authority clock plus grace above; the core enforces everything
        # else (actor registration, eligibility, the fresh holder gate).
        grant = LifecycleGrant(
            agent_id=actor, actions=frozenset({"reclaim"}), requires_reason=False
        )
        snapshot = claim_snapshot_for_todo(
            head, command["todo_id"], lease_active=False, lifecycle_grants=(grant,)
        )
        clear_plan = decide(
            snapshot,
            TodoMutationCommand(
                action=TodoAction.UPDATE,
                actor_agent_id=actor,
                clear_claim=True,
                ownership_mutation=True,
                authority_action="reclaim",
            ),
        )
        if clear_plan.outcome is not DecisionOutcome.APPLY:
            return _classified(clear_plan)
        assert clear_plan.next_snapshot is not None
        core_lease = self._acquire_and_claim(
            # The clock-authorized delegation applies only to clearing the
            # expired claim. Acquire/claim must use ordinary holder rules,
            # without carrying that ephemeral authority into a later command.
            replace(clear_plan.next_snapshot, lifecycle_grants=()),
            actor,
            request["operation_id"],
            command["lease_ttl_seconds"],
        )
        if isinstance(core_lease, dict):
            return core_lease
        expires_at = _format_time(now + command["lease_ttl_seconds"])
        next_head, receipt = self._next_head_for(
            head,
            request,
            request_digest,
            todo_id=command["todo_id"],
            command_name="reclaim_work",
            receipt_extra={
                "lease_id": core_lease.idempotency_key,
                "lease_epoch": core_lease.lease_epoch,
                "expires_at": expires_at,
                "superseded_owner": lease["owner"],
                "superseded_lease_epoch": lease["lease_epoch"],
            },
        )
        next_todo = next_head["coordination"]["todos"][command["todo_id"]]
        next_todo["claimed_by"] = actor
        next_todo["last_lease_epoch"] = core_lease.lease_epoch
        next_head["coordination"]["leases"][command["todo_id"]] = {
            "lease_id": core_lease.idempotency_key,
            "owner": core_lease.owner,
            "lease_epoch": core_lease.lease_epoch,
            "expires_at": expires_at,
            "write_scopes": list(core_lease.write_scopes),
        }
        return next_head, receipt

    def _complete_transition(
        self,
        head: dict[str, Any],
        request: dict[str, Any],
        request_digest: str,
    ) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
        command = request["command"]
        actor = request["actor"]["agent_id"]
        context = self._held_lease_context(head, command, actor)
        if isinstance(context, dict):
            return context
        todo, lease, snapshot = context
        # Ownership is adjudicated before payload semantics: a non-holder
        # learns nothing about successor-id availability.
        for successor in command["successor_todo_ids"]:
            if successor in head["coordination"]["todos"]:
                return {
                    "result": "rejected",
                    "reason": "successor_todo_exists",
                    "successor_todo_id": successor,
                }
        plan = decide(
            snapshot,
            TodoMutationCommand(
                action=TodoAction.COMPLETE,
                actor_agent_id=actor,
                lease_idempotency_key=command["lease_id"],
                lease_expected_version=command["expected_lease_epoch"],
            ),
        )
        if plan.outcome is not DecisionOutcome.APPLY:
            return _classified(plan)
        continuation = _continuation_for_write(
            no_followup=command["no_followup"],
            has_successor=bool(command["successor_todo_ids"]),
        )
        next_head, receipt = self._next_head_for(
            head,
            request,
            request_digest,
            todo_id=command["todo_id"],
            command_name="complete_work",
            receipt_extra={
                "lease_id": command["lease_id"],
                "lease_epoch": lease["lease_epoch"],
                "completion_continuation": continuation,
            },
        )
        next_todo = next_head["coordination"]["todos"][command["todo_id"]]
        next_todo["status"] = "done"
        next_todo["completion_continuation"] = continuation
        if command["no_followup"]:
            next_todo["no_followup"] = True
        if command["successor_todo_ids"]:
            next_todo["successor_todo_ids"] = list(command["successor_todo_ids"])
        if command["evidence"] is not None:
            next_todo["evidence"] = copy.deepcopy(command["evidence"])
        # Completion retires the lease in the same transition, exactly like
        # the local write; the watermark keeps the epoch history.
        del next_head["coordination"]["leases"][command["todo_id"]]
        # Successors are born open, unclaimed, revision 0, inheriting the
        # parent's execution context - atomically with the completion.
        for successor in command["successor_todo_ids"]:
            next_head["coordination"]["todos"][successor] = {
                "todo_revision": 0,
                "status": "open",
                "claimed_by": None,
                "eligibility": copy.deepcopy(todo["eligibility"]),
                "repository": todo["repository"],
                "code_revision": todo["code_revision"],
                "last_lease_epoch": 0,
            }
        return next_head, receipt

    # ---- RFC section 5 steps 1-10 -------------------------------------------

    def apply(self, envelope: dict[str, Any]) -> dict[str, Any]:
        request = self._semantic_request(envelope)
        operation_id = request["operation_id"]
        request_digest = _digest(request)

        head, provider_generation = self.provider.load()
        if head is None:
            return {
                "result": "failed",
                "reason": "coordination_head_uninitialized",
                "provider_generation": provider_generation,
            }
        try:
            head = validated_head(head, goal_id=self.goal_id)
        except HeadMigrationRequired:
            # A Stage 2 head is a classification, not a crash: nothing
            # applies until the explicit migrate_head_v0_to_v1 has run.
            return {
                "result": "failed",
                "reason": "head_schema_migration_required",
                "provider_generation": provider_generation,
            }
        fence = self._store_binding_fence(head, provider_generation)
        if fence is not None:
            return fence

        transitions = {
            "claim_work": self._claim_transition,
            "renew_work": self._renew_transition,
            "release_work": self._release_transition,
            "reclaim_work": self._reclaim_transition,
            "complete_work": self._complete_transition,
        }
        transition_for = transitions[request["command"]["type"]]

        for _attempt in range(_MAX_CAS_ATTEMPTS):
            replay = self._replay(head, provider_generation, operation_id, request_digest)
            if replay is not None:
                return replay
            transition = transition_for(head, request, request_digest)
            if isinstance(transition, dict):
                transition.update(
                    {
                        "observed_authority_revision": head["authority_revision"],
                        "provider_generation": provider_generation,
                    }
                )
                return transition
            proposed, original_receipt = transition
            provider_result = self.provider.compare_and_put(
                provider_generation, proposed
            )
            result_kind = provider_result.get("result")
            if result_kind == "applied":
                return self._success(
                    "applied",
                    original_receipt,
                    proposed,
                    provider_result["provider_generation"],
                )
            if result_kind not in {"conflict", "ambiguous", "failed"}:
                raise HeadValidationError(
                    f"unknown provider result: {provider_result!r}"
                )
            if result_kind == "failed":
                # The verb claims the write provably never happened. That
                # claim is verified, not trusted: one reload against the
                # receipt index catches a provider that misreported a landed
                # write as failed, at the cost of a single load.
                try:
                    check, check_generation = self.provider.load()
                    if check is not None:
                        check = validated_head(check, goal_id=self.goal_id)
                        replay = self._replay(
                            check, check_generation, operation_id, request_digest
                        )
                        if replay is not None:
                            return replay
                except Exception:  # noqa: BLE001 - verification is best-effort
                    pass
                return {
                    "result": "failed",
                    "reason": "provider_failed_before_cas",
                    "observed_authority_revision": head["authority_revision"],
                    "provider_generation": provider_generation,
                }

            latest, latest_generation = self.provider.load()
            if latest is None:
                return {
                    "result": "failed",
                    "reason": "coordination_head_missing_after_cas",
                    "provider_generation": latest_generation,
                }
            try:
                latest = validated_head(latest, goal_id=self.goal_id)
            except HeadMigrationRequired:
                return {
                    "result": "failed",
                    "reason": "head_schema_migration_required",
                    "provider_generation": latest_generation,
                }
            fence = self._store_binding_fence(latest, latest_generation)
            if fence is not None:
                return fence
            replay = self._replay(
                latest, latest_generation, operation_id, request_digest
            )
            if replay is not None:
                return replay
            if latest_generation == provider_generation:
                # Same generation and no receipt: the ambiguous attempt
                # provably did not land. Receipt absence never proves success,
                # so an eventual applied requires a new successful CAS.
                return {
                    "result": "failed",
                    "reason": "provider_outcome_unproved",
                    "observed_authority_revision": latest["authority_revision"],
                    "provider_generation": latest_generation,
                }
            head, provider_generation = latest, latest_generation

        return {
            "result": "failed",
            "reason": "provider_contention_exhausted",
            "observed_authority_revision": head["authority_revision"],
            "provider_generation": provider_generation,
        }


def deterministic_head_bytes(head: dict[str, Any]) -> bytes:
    """Canonical bytes for providers that store raw bytes (NoKV adapter)."""

    return canonical_head_bytes(head)
