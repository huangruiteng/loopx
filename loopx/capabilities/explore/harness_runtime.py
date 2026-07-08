from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .router_state import (
    advance_epoch,
    family_routing_terms,
    initial_router_state,
    observe_epoch,
)
from .worker_branch_plan import build_explore_worker_branch_plan

"""Software-agnostic exploration harness runtime.

This module is the generic half of a two-layer design:

- **This layer (LoopX)** owns scheduling and bookkeeping: independent
  wall-clock budget arms, a shared work queue with concurrency keys, the
  first-seen novelty ledger with adapter-injected flag weights, router-state
  feedback, frontier *scheduling* (when to spend speculative slots and on
  which seed families), anytime checkpoints, and generic metric aggregation.

- **The experiment layer** (driven by a Claude/Codex session) owns every
  domain fact: how to execute a work item, what the observation keys mean,
  how failures are classified, and -- crucially -- WHAT the speculative
  variants are. Variant strategy is authored by the agent as a data file
  (the variant catalog), never generated here.

Hard rules, in the spirit of the wider LoopX design:
- this module never calls an LLM and never imports domain vocabulary;
- variant intelligence travels through files: the harness EMITS
  ``frontier_requests_<arm>.json`` (seed text + seen-observation digest) and
  CONSUMES ``variant_catalog.json`` entries the agent wrote after reading
  those requests -- the same packet-out / decision-in contract the LoopX
  planner uses;
- novelty is only ever credited from observation keys and weighted flags the
  adapter reports; specs carry intent, not novelty.

Adapter protocol (duck-typed; see the experiment layer for a reference
implementation):

- ``list_seed_items() -> list[dict]``: fresh seed work items each epoch,
  each with ``item_id``, ``text``, ``family``; optional ``payload``.
- ``execute(item, *, run_root, arm, epoch, branch_id) -> dict``: run one work
  item and return an observation record with ``item_id``, ``family``,
  ``observation_keys`` (list[str]), ``weighted_flags`` ({name: weight} for
  true flags), ``accepted`` (bool), ``duration_minutes`` (float),
  ``retryable_infra_error`` (bool), plus any adapter-private fields.
- ``compile_variant(spec, seed_item) -> dict``: turn an agent-authored
  variant spec into an executable work item (``is_variant`` True,
  ``variant_spec`` attached, own ``concurrency_key``).
- ``flag_weights`` is implicit: the adapter reports weights per record, so
  the harness never holds a domain weight table.
"""


HARNESS_ARM_SCHEMA_VERSION = "loopx_explore_harness_arm_v0"
VARIANT_CATALOG_SCHEMA_VERSION = "loopx_explore_variant_catalog_v0"
FRONTIER_REQUESTS_SCHEMA_VERSION = "loopx_explore_frontier_requests_v0"

DEFAULT_OBSERVATION_WEIGHT = 1.0
_MIN_DURATION_MINUTES = 0.05


def _now_perf_minutes(start: float) -> float:
    return (time.perf_counter() - start) / 60.0


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None


class NoveltyLedger:
    """First-seen ledger: raw observation keys global, flags family-scoped.

    Raw keys are ledgered globally so relabeling an item under a different
    family can never re-mint an already-seen key; weighted flags are
    family-scoped facts. Weights come from the record itself (adapter-owned).
    """

    def __init__(self) -> None:
        self.seen: set[str] = set()

    def raw_value(self, record: Mapping[str, Any]) -> float:
        keys = record.get("observation_keys") or []
        flags = record.get("weighted_flags") or {}
        return DEFAULT_OBSERVATION_WEIGHT * len(keys) + sum(
            float(weight) for weight in flags.values()
        )

    def credit(self, record: Mapping[str, Any]) -> dict[str, float]:
        family = str(record.get("family") or "general")
        novel_value = 0.0
        novel_keys = 0
        for key in record.get("observation_keys") or []:
            key = str(key)
            if key not in self.seen:
                self.seen.add(key)
                novel_value += DEFAULT_OBSERVATION_WEIGHT
                novel_keys += 1
        for flag, weight in (record.get("weighted_flags") or {}).items():
            pseudo = f"flag:{family}:{flag}"
            if pseudo not in self.seen:
                self.seen.add(pseudo)
                novel_value += float(weight)
        return {"novel_value": novel_value, "novel_observation_keys": novel_keys}


def run_queue_epoch(
    items: Sequence[Mapping[str, Any]],
    *,
    execute: Callable[..., dict[str, Any]],
    worker_count: int,
    run_root: Path,
    arm: str,
    epoch: int,
    stagger_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    """Drain one epoch's work items through a shared pull queue.

    Items whose ``concurrency_key`` matches an in-flight item wait until the
    key frees up (the generic form of "same write scope must serialize");
    items with distinct keys run concurrently up to ``worker_count`` pullers.
    Returns per-worker lane records.
    """

    lock = threading.Lock()
    pending: list[dict[str, Any]] = [dict(item) for item in items]
    in_flight: set[str] = set()

    def pull_next() -> dict[str, Any] | None:
        with lock:
            for index, item in enumerate(pending):
                key = str(item.get("concurrency_key") or item.get("family") or "")
                if key and key in in_flight:
                    continue
                pending.pop(index)
                if key:
                    in_flight.add(key)
                return item
            return None

    def worker(worker_index: int) -> dict[str, Any]:
        branch_id = f"queue_worker_{worker_index + 1:02d}"
        started_at = time.perf_counter()
        if worker_index and stagger_seconds > 0:
            time.sleep(min(30.0, worker_index * stagger_seconds))
        results: list[dict[str, Any]] = []
        while True:
            item = pull_next()
            if item is None:
                with lock:
                    if not pending:
                        break
                time.sleep(0.5)
                continue
            key = str(item.get("concurrency_key") or item.get("family") or "")
            try:
                record = execute(
                    item, run_root=run_root, arm=arm, epoch=epoch, branch_id=branch_id
                )
                record.setdefault("item_id", item.get("item_id"))
                record.setdefault("family", item.get("family"))
                record.setdefault("is_variant", bool(item.get("is_variant")))
                if item.get("is_variant"):
                    record.setdefault("variant_spec_id", (item.get("variant_spec") or {}).get("spec_id"))
                results.append(record)
            finally:
                if key:
                    with lock:
                        in_flight.discard(key)
        return {
            "branch_id": branch_id,
            "launch_index": worker_index,
            "wall_minutes": round(_now_perf_minutes(started_at), 3),
            "item_ids": [r.get("item_id") for r in results],
            "families": [r.get("family") for r in results],
            "results": results,
        }

    thread_count = max(1, min(int(worker_count), len(pending) or 1))
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as pool:
        futures = [pool.submit(worker, index) for index in range(thread_count)]
        lanes = [future.result() for future in concurrent.futures.as_completed(futures)]
    lanes.sort(key=lambda lane: str(lane.get("branch_id")))
    return lanes


def _frontier_gain(router_state: Mapping[str, Any] | None, family: str, *, epoch: int) -> float:
    """Expected value of spending a speculative slot near this family.

    Generic signals only: whether the base loop has probed the family yet,
    its residual novelty pressure, and a small age bonus. Field names track
    the router_state family schema; the lookup accepts both the raw family
    id and adapter-prefixed forms (e.g. 'scope:artifacts/<family>').
    """

    stats: Mapping[str, Any] = {}
    families = (router_state or {}).get("families") if isinstance(router_state, Mapping) else None
    if isinstance(families, Mapping):
        exact = families.get(family)
        if isinstance(exact, Mapping):
            stats = exact
        else:
            suffix = "/" + str(family)
            for key, value in families.items():
                if isinstance(value, Mapping) and str(key).endswith(suffix):
                    stats = value
                    break
    score = 1.0
    runs = float(stats.get("runs") or 0.0)
    if runs <= 0:
        score += 1.25
    else:
        novelty_rate = stats.get("novelty_rate")
        if novelty_rate is not None:
            score += min(1.25, max(0.0, float(novelty_rate)) * 1.25)
        accept_rate = stats.get("accept_rate_ema")
        if accept_rate is not None and float(accept_rate) <= 0.5:
            score += 0.25
    score += min(0.5, max(0, int(epoch) - 1) * 0.03)
    return round(score, 4)


class VariantCatalog:
    """Agent-authored variant specs + per-arm consumption bookkeeping.

    Catalog file schema (written by the experiment agent, never by code):
    ``{"schema_version": ..., "specs": [{"spec_id", "seed_family",
    "intent", "ops": [...adapter-defined...], "key_prefix",
    "seed_item_id"?, "priority"?}]}``. The harness treats ``ops`` as opaque.
    """

    def __init__(self, catalog_path: Path, consumption_path: Path) -> None:
        self.catalog_path = Path(catalog_path)
        self.consumption_path = Path(consumption_path)
        consumed = _read_json(self.consumption_path)
        self.consumed: set[str] = set(consumed or [])

    def _specs(self) -> list[dict[str, Any]]:
        payload = _read_json(self.catalog_path)
        specs = (payload or {}).get("specs") if isinstance(payload, Mapping) else None
        return [dict(spec) for spec in specs or [] if spec.get("spec_id")]

    def pending_for(self, family: str) -> list[dict[str, Any]]:
        return [
            spec
            for spec in self._specs()
            if str(spec.get("seed_family") or "") == str(family)
            and str(spec.get("spec_id")) not in self.consumed
        ]

    def pending_count(self) -> int:
        return len([s for s in self._specs() if str(s.get("spec_id")) not in self.consumed])

    def consume(self, spec_id: str) -> None:
        self.consumed.add(str(spec_id))
        _write_json(self.consumption_path, sorted(self.consumed))


def select_frontier_work(
    seed_items: Sequence[Mapping[str, Any]],
    *,
    catalog: VariantCatalog,
    adapter: Any,
    router_state: Mapping[str, Any] | None,
    epoch: int,
    max_lanes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pick up to ``max_lanes`` agent-authored variant specs to execute.

    Seeds are ranked by the generic frontier gain with an epoch-rotating
    tie-break (multiplicative permutation over a prime modulus) so equal
    gains spread across families over epochs instead of freezing on an
    alphabetical prefix. Spec choice within a family follows the agent's
    ``priority`` then catalog order. The harness only ever schedules specs;
    it cannot invent them.
    """

    import hashlib

    def _hash(value: str) -> int:
        return int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:8], 16)

    by_family: dict[str, Mapping[str, Any]] = {}
    for item in seed_items:
        family = str(item.get("family") or "")
        if family and family not in by_family:
            by_family[family] = item
    ranked = sorted(
        by_family.items(),
        key=lambda pair: (
            -_frontier_gain(router_state, pair[0], epoch=epoch),
            (_hash(pair[0]) * (2 * int(epoch) + 1)) % 1_000_003,
            pair[0],
        ),
    )
    selected: list[dict[str, Any]] = []
    audit_specs: list[dict[str, Any]] = []
    for family, seed in ranked:
        if len(selected) >= max(0, int(max_lanes)):
            break
        pending = sorted(
            catalog.pending_for(family),
            key=lambda spec: (-float(spec.get("priority") or 0.0), str(spec.get("spec_id"))),
        )
        if not pending:
            continue
        spec = pending[0]
        item = adapter.compile_variant(spec, dict(seed))
        item.setdefault("is_variant", True)
        item.setdefault("variant_spec", spec)
        item.setdefault("family", family)
        item.setdefault(
            "concurrency_key", f"{family}:variant:{spec.get('spec_id')}"
        )
        catalog.consume(str(spec.get("spec_id")))
        selected.append(item)
        audit_specs.append(
            {
                "spec_id": spec.get("spec_id"),
                "seed_family": family,
                "intent": spec.get("intent"),
                "gain": _frontier_gain(router_state, family, epoch=epoch),
            }
        )
    audit = {
        "requested_lanes": int(max_lanes),
        "admitted": len(selected),
        "catalog_pending_after": catalog.pending_count(),
        "specs": audit_specs,
    }
    return selected, audit


def emit_frontier_requests(
    path: Path,
    *,
    arm_key: str,
    epoch: int,
    seed_items: Sequence[Mapping[str, Any]],
    ledger: NoveltyLedger,
    catalog: VariantCatalog,
    router_state: Mapping[str, Any] | None,
    per_family_key_cap: int = 24,
) -> None:
    """Publish what the harness NEEDS from the experiment agent.

    The agent (a Claude/Codex session driving the experiment) reads this
    packet -- seed text plus a digest of already-seen observation keys and
    exhausted specs -- and appends new specs to the variant catalog. This is
    the LoopX interaction pattern: packet out, decision in, no LLM calls
    from code.
    """

    families: dict[str, dict[str, Any]] = {}
    for item in seed_items:
        family = str(item.get("family") or "")
        if not family or family in families:
            continue
        seen_for_family = sorted(
            key
            for key in ledger.seen
            if not key.startswith("flag:") or key.startswith(f"flag:{family}:")
        )[: max(1, per_family_key_cap)]
        families[family] = {
            "family": family,
            "seed_item_id": item.get("item_id"),
            "seed_text": item.get("text"),
            "pending_spec_count": len(catalog.pending_for(family)),
            "frontier_gain": _frontier_gain(router_state, family, epoch=epoch),
            "seen_keys_sample": seen_for_family,
        }
    _write_json(
        path,
        {
            "schema_version": FRONTIER_REQUESTS_SCHEMA_VERSION,
            "arm": arm_key,
            "epoch": int(epoch),
            "total_seen_keys": len(ledger.seen),
            "catalog_pending_total": catalog.pending_count(),
            "families": sorted(families.values(), key=lambda f: -float(f["frontier_gain"])),
            "how_to_respond": (
                "Append specs to the variant catalog file: {spec_id, seed_family, "
                "intent, ops (adapter-defined), key_prefix, priority}. The harness "
                "schedules them by frontier gain; it never invents specs."
            ),
        },
    )


def plan_round_robin(seed_items: Sequence[Mapping[str, Any]], **_: Any) -> list[dict[str, Any]]:
    """Baseline planner: every seed, catalog untouched, no ordering signal."""

    return [dict(item) for item in seed_items]


def plan_router_no_prune(
    seed_items: Sequence[Mapping[str, Any]],
    *,
    goal_id: str,
    agent_id: str,
    worker_count: int,
    router_state: Mapping[str, Any] | None,
    load_profile: Mapping[str, Any] | None,
    harness_profile: str = "moe-router",
    branch_fill_policy: str = "confident-prefix",
) -> list[dict[str, Any]]:
    """Router-ordered no-prune planner over generic seed items.

    Uses the LoopX worker-branch planner for VALUE ORDERING only, then
    appends every unselected seed as a ranked tail -- sorting without
    pruning: an executable seed never loses its slot to low confidence.
    """

    todos = [
        {
            "todo_id": str(item.get("item_id")),
            "text": str(item.get("text") or item.get("item_id")),
            "status": "open",
            "task_class": "advancement_task",
            "required_write_scopes": [f"artifacts/{item.get('family')}/**"],
            "index": index,
        }
        for index, item in enumerate(seed_items)
    ]
    by_id = {str(item.get("item_id")): dict(item) for item in seed_items}
    plan = build_explore_worker_branch_plan(
        goal_id=goal_id,
        todos=todos,
        agent_id=agent_id,
        worker_width=worker_count,
        harness_profile=harness_profile,
        branch_fill_policy=branch_fill_policy,
        router_state=router_state,
        load_profile=load_profile,
    )
    ordered: list[dict[str, Any]] = []
    used: set[str] = set()
    for branch in plan.get("selected_worker_branches") or []:
        for todo_id in branch.get("todo_ids") or []:
            todo_id = str(todo_id)
            if todo_id in by_id and todo_id not in used:
                ordered.append(by_id[todo_id])
                used.add(todo_id)
    for branch in plan.get("rejected_worker_branches") or []:
        for todo_id in branch.get("todo_ids") or []:
            todo_id = str(todo_id)
            if todo_id in by_id and todo_id not in used:
                ordered.append(by_id[todo_id])
                used.add(todo_id)
    for item_id, item in by_id.items():
        if item_id not in used:
            ordered.append(item)
            used.add(item_id)
    return ordered


def run_budget_arm(
    adapter: Any,
    *,
    arm_key: str,
    run_root: Path,
    budget_minutes: float,
    worker_count: int,
    max_epochs: int = 1000,
    use_router: bool = False,
    frontier_max_lanes: int = 0,
    variant_catalog_path: Path | None = None,
    goal_id: str = "exploration",
    agent_id: str = "harness",
    stagger_seconds: float = 0.0,
    duration_guard_factor: float = 1.15,
    duration_guard_recent: int = 3,
) -> dict[str, Any]:
    """Run ONE arm alone against its wall-clock budget; return arm payload.

    ``use_router=False`` is the blind baseline (round-robin sweep, no
    variants). ``use_router=True`` adds router-ordered no-prune planning,
    router-state feedback, and -- when a variant catalog path is given --
    agent-authored frontier variants appended to each epoch's queue.
    """

    run_root = Path(run_root)
    ledger = NoveltyLedger()
    router_state = initial_router_state() if use_router else None
    load_profile: Mapping[str, Any] | None = None
    catalog = (
        VariantCatalog(
            Path(variant_catalog_path),
            run_root / f"variant_consumption_{arm_key}.json",
        )
        if variant_catalog_path
        else None
    )
    epochs: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    coverage_first_seen: dict[str, float] = {}
    raw_cum = 0.0
    novel_cum = 0.0
    variant_records_cum = 0
    stop_reason = "max_epochs"
    started = time.perf_counter()
    for epoch in range(1, int(max_epochs) + 1):
        elapsed = _now_perf_minutes(started)
        remaining = float(budget_minutes) - elapsed
        if epochs and remaining <= 0:
            stop_reason = "budget_exhausted"
            break
        if epochs and duration_guard_factor > 0:
            recent = epochs[-max(1, int(duration_guard_recent)) :]
            estimated = max(
                float(entry.get("epoch_wall_minutes") or 0.0) for entry in recent
            ) * float(duration_guard_factor)
            if remaining < estimated:
                stop_reason = "duration_guard"
                break
        seed_items = [dict(item) for item in adapter.list_seed_items()]
        if not seed_items:
            stop_reason = "seed_queue_empty"
            break
        if use_router:
            queue_items = plan_router_no_prune(
                seed_items,
                goal_id=goal_id,
                agent_id=agent_id,
                worker_count=worker_count,
                router_state=router_state,
                load_profile=load_profile,
            )
        else:
            queue_items = plan_round_robin(seed_items)
        frontier_audit: dict[str, Any] | None = None
        if use_router and catalog is not None and int(frontier_max_lanes) > 0:
            variant_items, frontier_audit = select_frontier_work(
                seed_items,
                catalog=catalog,
                adapter=adapter,
                router_state=router_state,
                epoch=epoch,
                max_lanes=frontier_max_lanes,
            )
            queue_items = queue_items + variant_items
            emit_frontier_requests(
                run_root / f"frontier_requests_{arm_key}.json",
                arm_key=arm_key,
                epoch=epoch,
                seed_items=seed_items,
                ledger=ledger,
                catalog=catalog,
                router_state=router_state,
            )
        epoch_start = time.perf_counter()
        lanes = run_queue_epoch(
            queue_items,
            execute=adapter.execute,
            worker_count=worker_count,
            run_root=run_root,
            arm=arm_key,
            epoch=epoch,
            stagger_seconds=stagger_seconds,
        )
        epoch_wall = _now_perf_minutes(epoch_start)
        epoch_raw = 0.0
        epoch_novel = 0.0
        records: list[dict[str, Any]] = []
        for lane in lanes:
            for record in lane.get("results") or []:
                credit = ledger.credit(record)
                record["novel_value"] = credit["novel_value"]
                record["raw_value"] = ledger.raw_value(record)
                epoch_raw += record["raw_value"]
                epoch_novel += credit["novel_value"]
                if record.get("is_variant"):
                    variant_records_cum += 1
                records.append(record)
        raw_cum += epoch_raw
        novel_cum += epoch_novel
        elapsed_after = _now_perf_minutes(started)
        for record in records:
            family = str(record.get("family") or "")
            if family:
                coverage_first_seen.setdefault(family, round(elapsed_after, 3))
        if use_router:
            probes = [
                {
                    "family": str(record.get("family") or "general"),
                    "duration_minutes": record.get("duration_minutes"),
                    "observation_keys": record.get("observation_keys") or [],
                    "weighted_flags": record.get("weighted_flags") or {},
                    "accepted": bool(record.get("accepted")),
                    "retryable_infra_error": bool(record.get("retryable_infra_error")),
                }
                for record in records
            ]
            router_state = observe_epoch(router_state, epoch=epoch, probes=probes)
            router_state = advance_epoch(
                router_state,
                epoch=epoch,
                eligible_families=sorted(
                    {str(item.get("family")) for item in seed_items if item.get("family")}
                ),
            )
            _write_json(run_root / f"router_state_{arm_key}.json", router_state)
            max_lane_wall = max(
                (float(lane.get("wall_minutes") or 0.0) for lane in lanes), default=0.0
            )
            load_profile = {
                "source": f"observed_epoch_{epoch:02d}_{arm_key}",
                "parallel_wall_minutes": epoch_wall,
                "max_branch_minutes": max_lane_wall,
                "branch_count": len(lanes),
            }
        checkpoints.append(
            {
                "epoch": epoch,
                "elapsed_minutes": round(elapsed_after, 3),
                "raw_value_cum": round(raw_cum, 3),
                "novel_value_cum": round(novel_cum, 3),
                "coverage_count_cum": len(coverage_first_seen),
                "variant_records_cum": variant_records_cum,
                "requested_worker_minutes_cum": round(elapsed_after * worker_count, 3),
            }
        )
        epochs.append(
            {
                "schema_version": HARNESS_ARM_SCHEMA_VERSION,
                "epoch": epoch,
                "epoch_wall_minutes": round(epoch_wall, 3),
                "queue_size": len(queue_items),
                "frontier": frontier_audit,
                "lanes": lanes,
            }
        )
        _write_json(
            run_root / f"rolling_progress_{arm_key}.json",
            {"arm": arm_key, "completed_epochs": len(epochs), "last_checkpoint": checkpoints[-1]},
        )
    return {
        "schema_version": HARNESS_ARM_SCHEMA_VERSION,
        "arm_key": arm_key,
        "budget_minutes": float(budget_minutes),
        "elapsed_minutes": round(_now_perf_minutes(started), 3),
        "stop_reason": stop_reason,
        "epoch_count": len(epochs),
        "raw_value_total": round(raw_cum, 3),
        "novel_value_total": round(novel_cum, 3),
        "variant_records_total": variant_records_cum,
        "coverage_count": len(coverage_first_seen),
        "coverage_first_seen_minutes": coverage_first_seen,
        "checkpoints": checkpoints,
        "epochs": epochs,
    }


def step_auc(checkpoints: Sequence[Mapping[str, Any]], *, value_key: str, horizon_minutes: float) -> float:
    """Step-integrate a cumulative anytime curve to the budget horizon."""

    auc = 0.0
    prev_t = 0.0
    prev_v = 0.0
    for checkpoint in checkpoints:
        t = min(float(checkpoint.get("elapsed_minutes") or 0.0), float(horizon_minutes))
        if t > prev_t:
            auc += prev_v * (t - prev_t)
            prev_t = t
        prev_v = float(checkpoint.get(value_key) or 0.0)
    if float(horizon_minutes) > prev_t:
        auc += prev_v * (float(horizon_minutes) - prev_t)
    return round(auc, 3)


def aggregate_arms(
    arms: Mapping[str, Mapping[str, Any]],
    *,
    budget_minutes: float,
    worker_count: int,
    coverage_denominator: int | None = None,
) -> dict[str, Any]:
    """Generic two-arm (or N-arm) comparison on novelty-first metrics."""

    summary: dict[str, Any] = {
        "schema_version": "loopx_explore_harness_score_v0",
        "budget_minutes_per_arm": float(budget_minutes),
        "worker_count": int(worker_count),
        "coverage_denominator": coverage_denominator,
        "arms": {},
    }
    for arm_key, arm in arms.items():
        checkpoints = arm.get("checkpoints") or []
        summary["arms"][arm_key] = {
            "novel_value_endpoint": arm.get("novel_value_total"),
            "novel_value_auc": step_auc(
                checkpoints, value_key="novel_value_cum", horizon_minutes=budget_minutes
            ),
            "raw_value_total": arm.get("raw_value_total"),
            "coverage_count": arm.get("coverage_count"),
            "variant_records_total": arm.get("variant_records_total"),
            "epoch_count": arm.get("epoch_count"),
            "elapsed_minutes": arm.get("elapsed_minutes"),
            "stop_reason": arm.get("stop_reason"),
            "novel_value_per_requested_worker_minute": round(
                float(arm.get("novel_value_total") or 0.0)
                / max(0.001, float(budget_minutes) * worker_count),
                4,
            ),
            "anytime_curve": checkpoints,
        }
    return summary
