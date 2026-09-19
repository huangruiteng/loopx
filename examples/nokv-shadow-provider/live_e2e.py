"""Repeatable live Stage-3 lifecycle over file and NoKV providers.

This is the bounded live qualification the direction tracker asks for before
any provider promotion: the SAME invariant scenarios run against the
file-backed control provider and the live NoKV candidate, and the script
prints a compact public-safe pass/fail/unverified matrix. It is evidence
tooling, not a merge gate: without a reachable stack it reports every live
row as unverified and exits 0 only when nothing that DID run failed.

Environment (all required for the NoKV rows):
  NOKV_COORDINATION_LIVE=1
  NOKV_ETCD / NOKV_ETCD_PREFIX / NOKV_ROOT_ID
  NOKV_BUCKET / NOKV_OBJECT_ENDPOINT / NOKV_OBJECT_ROOT
  NOKV_OBJECT_KEY / NOKV_OBJECT_SECRET

Run from the repository root:
  python3 examples/nokv-shadow-provider/live_e2e.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loopx.control_plane.coordination.executor import (  # noqa: E402
    CoordinationAuthorityExecutor,
    sample_claim_envelope,
    sample_work_envelope,
)
from loopx.control_plane.coordination.file_provider import (  # noqa: E402
    FileCoordinationProvider,
)
from loopx.control_plane.coordination.head import bootstrap_head  # noqa: E402

from provider import open_nokv_coordination_provider  # noqa: E402


def eligibility() -> dict:
    return {
        "authorization_projection_revision": 3,
        "authorization_projection_digest": "sha256:bootstrap-auth",
        "allowed_agent_ids": ["agent-a", "agent-b"],
        "dependencies_satisfied": True,
        "dependency_revision": 12,
        "gates_open": True,
        "gate_revision": 5,
    }


def todo() -> dict:
    return {
        "todo_revision": 7,
        "status": "open",
        "claimed_by": None,
        "eligibility": eligibility(),
        "repository": "git:example/repo",
        "code_revision": "0123456789abcdef",
        "last_lease_epoch": 6,
    }


class MatrixClock:
    """Deterministic, advanceable executor clock: expiry adjudication is the
    authority's own decision, so the live matrix drives it explicitly while
    the provider underneath stays real."""

    def __init__(self, value: float = 1_800_000_000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value


def work(executor, agent: str, operation_id: str, command: dict):
    return executor.apply(
        sample_work_envelope(
            goal_id=executor.goal_id,
            operation_id=operation_id,
            agent_id=agent,
            device_id=f"dev-{agent}",
            command=command,
        )
    )


def claim(
    executor,
    agent: str,
    todo_id: str,
    operation_id: str,
    ttl: int = 600,
    revision: int = 7,
):
    return executor.apply(
        sample_claim_envelope(
            goal_id=executor.goal_id,
            operation_id=operation_id,
            agent_id=agent,
            device_id=f"dev-{agent}",
            todo_id=todo_id,
            expected_todo_revision=revision,
            expected_preconditions={
                "authorization_projection_revision": 3,
                "authorization_projection_digest": "sha256:bootstrap-auth",
                "dependency_revision": 12,
                "gate_revision": 5,
            },
            lease_ttl_seconds=ttl,
        )
    )


def scenario_matrix(make_provider) -> dict:
    """The shared invariant script, provider-agnostic. Returns row -> bool."""

    rows: dict[str, bool] = {}
    goal_id = "g" + uuid.uuid4().hex[:8]
    provider_a = make_provider(goal_id)
    provider_b = make_provider(goal_id)
    head = bootstrap_head(
        goal_id,
        {"todo-1": todo(), "todo-2": todo()},
        store_binding=provider_a.store_identity(),
    )
    assert provider_a.load() == (None, 0)
    assert provider_a.compare_and_put(0, head)["result"] == "applied"
    executor_a = CoordinationAuthorityExecutor(
        provider_a, goal_id=goal_id, now=lambda: 1_800_000_000.0
    )
    executor_b = CoordinationAuthorityExecutor(
        provider_b, goal_id=goal_id, now=lambda: 1_800_000_000.0
    )

    # same-todo race with two independent handles and a real thread barrier
    barrier = threading.Barrier(2)
    outcomes: dict[str, dict] = {}

    def race(name, executor, agent):
        barrier.wait()
        outcomes[name] = claim(executor, agent, "todo-1", f"race-{agent}")

    threads = [
        threading.Thread(target=race, args=("a", executor_a, "agent-a")),
        threading.Thread(target=race, args=("b", executor_b, "agent-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    kinds = sorted(outcome["result"] for outcome in outcomes.values())
    rows["same_todo_one_winner"] = kinds == ["applied", "conflict"]

    winner = next(o for o in outcomes.values() if o["result"] == "applied")
    winner_agent = winner["original_receipt"]["actor"]["agent_id"]
    other_agent = "agent-b" if winner_agent == "agent-a" else "agent-a"

    # independent todo applies for the other endpoint after internal rebase
    second = claim(executor_b, other_agent, "todo-2", "independent-1")
    rows["independent_todo_applies"] = second["result"] == "applied"

    # exact replay across a reconstructed executor
    replay_executor = CoordinationAuthorityExecutor(
        make_provider(goal_id), goal_id=goal_id, now=lambda: 1_800_000_000.0
    )
    replayed = claim(replay_executor, winner_agent, "todo-1", f"race-{winner_agent}")
    rows["replay_returns_original_receipt"] = (
        replayed["result"] == "already_applied"
        and replayed["original_receipt"] == winner["original_receipt"]
    )

    # identity reuse with different semantics
    mutated = claim(
        replay_executor, winner_agent, "todo-1", f"race-{winner_agent}", ttl=601
    )
    rows["identity_mismatch_rejected"] = (
        mutated["result"] == "rejected"
        and mutated["reason"] == "operation_identity_mismatch"
    )

    # stale caller revision conflicts without state change
    head_now, generation_now = provider_a.load()
    stale = claim(executor_a, winner_agent, "todo-2", "stale-1")
    rows["stale_revision_conflicts"] = (
        stale["result"] == "conflict"
        and provider_a.load() == (head_now, generation_now)
    )

    # lost response after commit recovers through the receipt index
    class LossyOnce:
        def __init__(self, inner):
            self.inner = inner
            self.armed = True

        def load(self):
            return self.inner.load()

        def store_identity(self):
            return self.inner.store_identity()

        def compare_and_put(self, expected, proposed):
            outcome = self.inner.compare_and_put(expected, proposed)
            if self.armed and outcome.get("result") == "applied":
                self.armed = False
                return {"result": "ambiguous"}
            return outcome

    lossy_executor = CoordinationAuthorityExecutor(
        LossyOnce(make_provider(goal_id)),
        goal_id=goal_id,
        now=lambda: 1_800_000_000.0,
    )
    goal2 = "g" + uuid.uuid4().hex[:8]
    provider2 = make_provider(goal2)
    provider2.compare_and_put(
        0,
        bootstrap_head(
            goal2, {"todo-1": todo()}, store_binding=provider2.store_identity()
        ),
    )
    lossy2 = CoordinationAuthorityExecutor(
        LossyOnce(provider2), goal_id=goal2, now=lambda: 1_800_000_000.0
    )
    lost = claim(lossy2, "agent-a", "todo-1", "lost-1")
    rows["lost_response_recovers_receipt"] = lost["result"] == "already_applied"
    del lossy_executor

    final_head, _ = provider_a.load()
    rows["receipts_retained"] = len(final_head["receipt_index"]) == 2
    rows["authority_revision_advanced_twice"] = final_head["authority_revision"] == 2

    # ---- Stage 3: recoverable execution ownership over the same seam ----
    goal3 = "g" + uuid.uuid4().hex[:8]
    provider3 = make_provider(goal3)
    clock = MatrixClock()
    provider3.compare_and_put(
        0,
        bootstrap_head(
            goal3,
            {"todo_parent01": todo(), "todo_other01": todo()},
            store_binding=provider3.store_identity(),
        ),
    )
    executor3 = CoordinationAuthorityExecutor(
        provider3, goal_id=goal3, now=clock
    )
    first = claim(executor3, "agent-a", "todo_parent01", "r3-claim")
    fence = {
        "lease_id": first["original_receipt"]["lease_id"],
        "expected_lease_epoch": first["original_receipt"]["lease_epoch"],
    }
    renewed = work(executor3, "agent-a", "r3-renew", {
        "type": "renew_work", "todo_id": "todo_parent01",
        "expected_todo_revision": 8, **fence, "lease_ttl_seconds": 600,
    })
    rows["renew_extends_the_active_lease"] = (
        renewed["result"] == "applied"
        and renewed["original_receipt"]["lease_epoch"]
        == first["original_receipt"]["lease_epoch"]
    )

    clock.value += 600 + 31
    reclaimed = work(executor3, "agent-b", "r3-reclaim", {
        "type": "reclaim_work", "todo_id": "todo_parent01",
        "expected_todo_revision": 9,
        "expected_preconditions": {
            "authorization_projection_revision": 3,
            "authorization_projection_digest": "sha256:bootstrap-auth",
            "dependency_revision": 12,
            "gate_revision": 5,
        },
        "lease_ttl_seconds": 600,
    })
    rows["expired_lease_reclaimed_with_new_epoch"] = (
        reclaimed["result"] == "applied"
        and reclaimed["original_receipt"]["lease_epoch"]
        == first["original_receipt"]["lease_epoch"] + 1
        and reclaimed["original_receipt"]["superseded_owner"] == "agent-a"
    )

    stale = work(executor3, "agent-a", "r3-stale-writeback", {
        "type": "complete_work", "todo_id": "todo_parent01",
        "expected_todo_revision": 10, **fence,
        "no_followup": False, "successor_todo_ids": [], "evidence": None,
    })
    rows["superseded_executor_cannot_write_back"] = (
        stale["result"] == "rejected" and stale["reason"] == "stale_lease_fence"
    )

    new_fence = {
        "lease_id": reclaimed["original_receipt"]["lease_id"],
        "expected_lease_epoch": reclaimed["original_receipt"]["lease_epoch"],
    }
    done = work(executor3, "agent-b", "r3-complete", {
        "type": "complete_work", "todo_id": "todo_parent01",
        "expected_todo_revision": 10, **new_fence,
        "no_followup": False, "successor_todo_ids": ["todo_next01"],
        "evidence": None,
    })
    successor_claim = claim(
        executor3, "agent-a", "todo_next01", "r3-successor", ttl=600, revision=0
    ) if done["result"] == "applied" else {"result": "skipped"}
    head3, _ = provider3.load()
    rows["complete_creates_claimable_successor_atomically"] = (
        done["result"] == "applied"
        and done["original_receipt"]["completion_continuation"] == "successor"
        and successor_claim["result"] == "applied"
        and head3["coordination"]["todos"]["todo_parent01"]["status"] == "done"
        and "todo_parent01" not in head3["coordination"]["leases"]
    )
    return rows


def file_matrix(root: Path) -> dict:
    return scenario_matrix(
        lambda goal_id: FileCoordinationProvider(root / "coordination", goal_id)
    )


NOKV_SEEDS_VARIABLE = "NOKV_SEEDS"
NOKV_ETCD_VARIABLES = ("NOKV_ETCD", "NOKV_ETCD_PREFIX")


def nokv_routing(nokv, env) -> tuple[object | None, dict | None, tuple[str, str] | None]:
    """Build the SDK routing from exactly one routing variable group.

    ``NOKV_SEEDS`` (comma-separated ``IP:PORT``) selects seed routing, the kind
    of the NoKV metadata-runtimes line; ``NOKV_ETCD`` plus ``NOKV_ETCD_PREFIX``
    selects etcd routing, the kind of the 0.11.0 release line. Both set is a
    configuration error, and a kind the installed wheel cannot build is a
    capability mismatch, never an outage. Returns ``(routing, sdk_facts,
    None)`` or ``(None, None, (reason, reason_code))``; the facts carry counts
    and kinds only, never endpoint values.
    """
    seeds_raw = env.get(NOKV_SEEDS_VARIABLE)
    etcd_complete = all(env.get(name) for name in NOKV_ETCD_VARIABLES)
    if seeds_raw and etcd_complete:
        return None, None, (
            "NOKV_SEEDS and NOKV_ETCD/NOKV_ETCD_PREFIX are both set; choose one routing kind",
            "nokv_routing_env_ambiguous",
        )
    if seeds_raw:
        kind = "seeds"
        seeds = [item.strip() for item in seeds_raw.split(",") if item.strip()]
        arguments: tuple = (seeds,)
    elif etcd_complete:
        kind = "etcd"
        arguments = ([env["NOKV_ETCD"]], env["NOKV_ETCD_PREFIX"], 10)
    else:
        return None, None, (
            "neither NOKV_SEEDS nor NOKV_ETCD/NOKV_ETCD_PREFIX is set",
            "nokv_routing_env_missing",
        )
    constructor = getattr(nokv.RoutingConfig, kind, None)
    if not callable(constructor):
        return None, None, (
            f"the installed nokv SDK does not provide RoutingConfig.{kind}",
            "nokv_sdk_capability_mismatch",
        )
    try:
        routing = constructor(*arguments)
    except (TypeError, ValueError):
        return None, None, ("NoKV routing configuration is invalid", "nokv_routing_invalid")
    schema = getattr(nokv, "WORKSPACE_PROTOCOL_SCHEMA", None)
    facts = {
        "version": getattr(nokv, "__version__", None),
        "api_version": getattr(nokv, "API_VERSION", None),
        "protocol_schema": schema if isinstance(schema, str) and schema else None,
        "routing_kind": kind,
        "seed_count": len(arguments[0]) if kind == "seeds" else None,
    }
    return routing, facts, None


def nokv_matrix() -> tuple[dict | None, tuple[str, str] | None, dict | None]:
    if os.environ.get("NOKV_COORDINATION_LIVE") != "1":
        return None, ("NOKV_COORDINATION_LIVE unset", "nokv_live_flag_unset"), None
    try:
        import nokv
    except ImportError:
        return None, ("nokv SDK not installed", "nokv_sdk_missing"), None
    env = os.environ
    routing, sdk_facts, skip = nokv_routing(nokv, env)
    if routing is None:
        return None, skip, None

    def make_client():
        objects = nokv.ObjectStoreConfig.s3(
            env["NOKV_BUCKET"],
            region="us-east-1",
            root=env["NOKV_OBJECT_ROOT"],
            endpoint=env["NOKV_OBJECT_ENDPOINT"],
            access_key_id=env["NOKV_OBJECT_KEY"],
            secret_access_key=env["NOKV_OBJECT_SECRET"],
        )
        return nokv.Client(
            env["NOKV_ROOT_ID"],
            routing,
            objects,
            workbench_root="/agents/live-e2e/wb",
        )

    workbench = "wbstage2" + uuid.uuid4().hex[:10]
    # This handle provisions the evidence workspace; it cannot authorize a
    # coordination-head state transition or participate in provider fallback.
    provisioning_client = make_client()
    provisioning_client.create_workspace(workbench)

    def make_provider(goal_id):
        return open_nokv_coordination_provider(
            make_client,
            workbench,
            goal_id,
        )

    rows = scenario_matrix(make_provider)
    rows["restored_lineage_fails_closed"] = _restored_lineage_fails_closed(
        make_client
    )
    return rows, None, sdk_facts


def _restored_lineage_fails_closed(make_client) -> bool:
    """The Stage 3 binding fence against a REAL NoKV restore: a head
    bootstrapped in workbench A, committed, snapshotted, and restored into
    workbench B must refuse every command on B with store_lineage_mismatch -
    restored bytes never grant live authority."""

    # Workspace lifecycle operations belong to the live-evidence provisioner;
    # coordination reads and writes use a separately admitted provider handle.
    provisioning_client = make_client()
    source = "wbline" + uuid.uuid4().hex[:10]
    provisioning_client.create_workspace(source)
    goal_id = "g" + uuid.uuid4().hex[:8]
    provider = open_nokv_coordination_provider(make_client, source, goal_id)
    head = bootstrap_head(
        goal_id, {"todo_parent01": todo()},
        store_binding=provider.store_identity(),
    )
    if provider.compare_and_put(0, head)["result"] != "applied":
        return False
    executor = CoordinationAuthorityExecutor(
        provider, goal_id=goal_id, now=MatrixClock()
    )
    if claim(executor, "agent-a", "todo_parent01", "line-claim")["result"] != "applied":
        return False

    stat = provisioning_client.stat(source, provider.head_path)
    provisioning_client.commit(
        source,
        {"purpose": "stage3-lineage-fence"},
        stat["body_digest"],
    )
    snapshot = provisioning_client.snapshot(source)
    destination = "wbline" + uuid.uuid4().hex[:10]
    provisioning_client.restore(
        source,
        destination,
        at_snapshot=snapshot["snapshot_id"],
    )

    restored = open_nokv_coordination_provider(
        make_client,
        destination,
        goal_id,
    )
    restored_executor = CoordinationAuthorityExecutor(
        restored, goal_id=goal_id, now=MatrixClock()
    )
    fenced = claim(
        restored_executor, "agent-b", "todo_parent01", "line-claim-2", revision=8
    )
    original_still_serves = claim(
        executor, "agent-b", "todo_parent01", "line-claim-3", revision=8
    )
    return (
        fenced["result"] == "failed"
        and fenced["reason"] == "store_lineage_mismatch"
        and original_still_serves["result"] == "rejected"
        and original_still_serves["reason"] == "todo_not_open"
    )


def main() -> int:
    matrix: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as root:
        matrix["file_provider"] = file_matrix(Path(root))
    nokv_rows, skip, sdk_facts = nokv_matrix()
    if nokv_rows is None:
        assert skip is not None
        reason, reason_code = skip
        matrix["nokv_provider"] = {"unverified": reason, "reason_code": reason_code}
    else:
        matrix["nokv_provider"] = nokv_rows
        # Wheel facts the ladder pins into its bindings: kinds and counts only.
        matrix["nokv_sdk"] = sdk_facts or {}
        shared = {
            row: value
            for row, value in nokv_rows.items()
            if row in matrix["file_provider"]
        }
        parity = {
            row: matrix["file_provider"][row] == value
            for row, value in shared.items()
        }
        matrix["file_nokv_parity"] = {
            "identical_row_outcomes": all(parity.values()),
            "rows": len(parity),
            "provider_specific_rows": sorted(set(nokv_rows) - set(shared)),
        }
    print(json.dumps(matrix, indent=2, sort_keys=True))
    failed = [
        f"{provider}.{row}"
        for provider, rows in matrix.items()
        for row, value in rows.items()
        if value is False
    ]
    if failed:
        print("FAILED rows:", failed, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
