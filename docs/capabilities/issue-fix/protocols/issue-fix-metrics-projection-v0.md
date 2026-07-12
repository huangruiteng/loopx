# Issue-Fix Metrics Projection v0

## Purpose

`loopx issue-fix metrics` produces a read-only reporting packet for a long-running
issue-fix goal. It answers two different questions without mixing them:

1. how the public repository changed during the reporting window; and
2. what outputs are attributable to the connected issue-fix goal.

The command derives agent output from the goal's existing feasibility and PR
lifecycle domain state. It does not create a metrics ledger or lifecycle state
machine.

## Repository snapshot input

Both period-start and current inputs use
`issue_fix_repository_reporting_snapshot_v0`:

```json
{
  "schema_version": "issue_fix_repository_reporting_snapshot_v0",
  "repo": "owner/repo",
  "captured_at": "2026-08-01T00:00:00Z",
  "source_url": "https://github.com/owner/repo",
  "open_issues": 42,
  "open_pull_requests": 17
}
```

The current snapshot additionally requires `flow_since_baseline`:

```json
{
  "flow_since_baseline": {
    "issues_opened": 8,
    "issues_closed": 6,
    "pull_requests_opened": 12,
    "pull_requests_closed": 10,
    "pull_requests_merged": 9
  }
}
```

LoopX rejects a snapshot unless both stock equations reconcile:

```text
baseline open + opened - closed = current open
```

Optional `issue_states` and `pull_request_states` contain compact public current
state. They let the projection compute issue-close attribution and refresh stale
PR state without rewriting lifecycle history. Every output inventory row records
whether its current state came from the lifecycle ledger or the newer repository
snapshot.

## Supplemental counts

`issue_fix_metrics_supplement_v0` can supply public-safe counts that are not yet
native to feasibility or PR lifecycle rows:

```json
{
  "schema_version": "issue_fix_metrics_supplement_v0",
  "counts": {
    "human_interventions": 2,
    "first_push_ci_passed": 5,
    "first_push_ci_total": 7,
    "loopx_capability_gaps_found": 3,
    "loopx_capability_gaps_fixed": 2,
    "memory_retrievals": 4,
    "memory_verified_patch_influence": 1,
    "memory_stale_results": 1
  }
}
```

This is an allowlisted compact input, not a raw provider payload. Missing counts
remain `null` and produce a `missing_data` reason code. A missing measure is never
coerced to zero.

`loopx issue-fix metrics-supplement` composes that input from evidence already
owned by the issue-fix domain state and from optional explicit event evidence:

```bash
loopx --format json issue-fix metrics-supplement \
  --goal-id public-issue-fix-goal \
  --project /path/to/project \
  --repo public-org/public-repo \
  --period-start 2026-07-01T00:00:00Z \
  --period-end 2026-08-01T00:00:00Z \
  --human-intervention-coverage-start 2026-07-01T00:00:00Z \
  --capability-gap-coverage-start 2026-07-01T00:00:00Z \
  --event-json /path/to/public-safe-events.json \
  --repository-memory-json /path/to/explicit-memory-read-result.json
```

Feasibility and lifecycle rows supply screened issues, triage outcomes, and
automatic terminal closeouts. Explicit repository-memory read results supply
retrieval, verified patch-influence, and stale-result counts. An optional
`issue_fix_metrics_event_batch_v0` supplies stable event identities for
first-push CI, human interventions, useful public comments, duplicate external
writes, and capability-gap `found` / `fixed` / `real_callsite_verified`
transitions. Events outside the reporting period are ignored, duplicate event
identities are rejected, and a capability gap is counted once per gap identity.

Without an explicit event batch, the composer reads the existing compact LoopX
run index and counts only route-changing `operator_gate_*` decisions and
run-bound `human_reward` entries carrying a `human_reward_lesson_v0` correction.
Passive chat, acknowledgements, and ordinary positive feedback are not counted.
The count is published only when `--human-intervention-coverage-start` proves
that this audited source covers the whole reporting period. A later or absent
coverage start exposes the observed count only under
`coverage.human_intervention` and keeps the metric unavailable, so older
unprojected conversations are never reconstructed or silently treated as zero.

Capability gaps can use the same no-guessing path without a hand-authored event
batch. An agent marks an existing agent todo explicitly:

```bash
loopx todo update \
  --goal-id public-issue-fix-goal \
  --todo-id todo_gap_id \
  --role agent \
  --target-capability issue_fix_monthly_metrics \
  --capability-gap-status real_callsite_verified \
  --evidence 'PR merged and the original pilot callsite passed'
```

LoopX appends a typed `capability_gap` rollout event; the todo id is the stable
gap identity and the existing target-capability metadata remains the human
work surface. The composer folds `found`, `fixed`, and
`real_callsite_verified` transitions once per todo. It publishes the three
counts only when `--capability-gap-coverage-start` covers the reporting period;
otherwise `coverage.capability_gap` exposes partial observation and the counts
stay unavailable. Backdating that coverage is valid only after auditing and
backfilling every in-period gap todo. `fixed` and `real_callsite_verified`
markers require public-safe evidence; `found` may be recorded before a fix
artifact exists.

PR lifecycle collection also captures first-push CI evidence without another
ledger when public metadata proves that the PR still has exactly one commit and
its check rollup is terminal (`PASSING` or `FAILING`). The compact evidence is
preserved across later lifecycle upserts. The supplement reports
`coverage.first_push_ci` and only publishes pass/total counts when every PR in
the reporting cohort has evidence. Partial observation stays unavailable and
surfaces its observed/eligible coverage instead of reporting a biased rate.

The composer performs no provider call and does not infer absent events. When no
explicit memory result is supplied, it may use a compact feasibility memory hook
only when that hook records `read_performed=true`; otherwise memory fields remain
absent. With no event batch, useful-comment, duplicate-write, and other
event-backed fields remain absent; only coverage-gated human-intervention and
typed capability-gap rollout evidence can be composed from existing LoopX
sources. In both cases `loopx issue-fix metrics` reports unavailable evidence
rather than coercing it to zero.

## Attribution contract

- The repository baseline contains repository stock only.
- Agent output at the goal-start baseline is zero.
- Feasibility rows provide selected issues and route counts.
- PR lifecycle rows provide the attributable PR inventory, links, receipts, and
  last persisted state.
- Reporting-window attribution uses the newest verified lifecycle event time
  (`created_at` from the current public snapshot when present; otherwise
  `merged_at`, `closed_at`, or `updated_at`) together with the row observation
  time. A linked feasibility decision follows its attributable PR into the
  window, so an old or replayed observation timestamp cannot erase real output.
- Unlinked feasibility or lifecycle rows whose available event times all
  predate the baseline are excluded from the period instead of forcing the
  caller to rewrite history.
- A newer current public snapshot may refresh state but cannot add an
  unattributed PR to the inventory.
- Repository shares use explicit numerators and denominators, so a ratio is
  `not_available` when its denominator is zero or evidence is missing.
- Open PRs are work in progress, not terminal outcomes.

## Boundary contract

The projection performs no network read and no external write. Inputs are
caller-supplied compact public metadata. Output excludes local paths, credentials,
raw issue bodies, comments, provider responses, transcripts, and tool logs.

Daily public snapshot collection and Kanban/dashboard rendering are separate
adapters over this packet. They must not become a second source of truth.

`loopx issue-fix repository-snapshot` is the bounded public GitHub collector.
It reads repository stock/flow plus the current state of issue/PR references
already present in the goal's issue-fix domain state. The command never retains
raw provider payloads. With `--retain-material-snapshot`, it writes at most one
row per day to the existing `issue_fix/repository-snapshots.jsonl` stream and
skips the write when stock, flow, issue state, PR state, CI, and review are
unchanged:

```bash
loopx --format json issue-fix repository-snapshot \
  --goal-id public-issue-fix-goal \
  --project /path/to/connected/project \
  --repo owner/repo \
  --repository-baseline-json baseline.json \
  --fetch-public-github \
  --retain-material-snapshot
```

The returned `snapshot` object can be passed directly as
`--repository-current-json` to `loopx issue-fix metrics`. Scheduling remains a
normal LoopX `continuous_monitor` todo; the collector does not install a second
scheduler or invent another workflow state machine.

## Monthly Impact projection

The metrics packet includes stable `impact_rows` for repository health,
delivery, quality, autonomy, capability, and memory. Every row keeps its
baseline, current value, delta, numerator/denominator when applicable, public
source URL, freshness timestamp, and missing-data reason.

Capability delta is represented by three separate rows: gaps found, gaps
fixed, and gaps verified on a real callsite. This keeps discovery volume,
delivery, and product-path proof distinguishable instead of collapsing all
three into a single success count. Each row remains `not_available` until its
own evidence-backed count is present.

Repository-memory impact is likewise represented by three separate rows:
retrieved results, results verified to influence a patch, and results verified
stale. This separates usage volume from demonstrated engineering leverage and
retrieval quality; zero is retained as evidence, while missing counts remain
`not_available`.

The generic Lark sink renders those rows into the `Monthly Impact` view without
storing another metrics ledger:

```bash
loopx --format json issue-fix metrics \
  --goal-id public-issue-fix-goal \
  --project /path/to/connected/project \
  --repo owner/repo \
  --repository-baseline-json baseline.json \
  --repository-current-json current.json \
| loopx --format json lark-kanban sync-projection \
  --projection-file - \
  --goal-id public-issue-fix-goal \
  --sink-visibility shared \
  --execute
```

`sync-projection` accepts a file, a bounded inline object, or stdin. Setup is
idempotent: existing boards gain the metric fields and `Monthly Impact` view
through the normal schema-reconciliation path.

## Validation

```bash
python3 examples/issue-fix-metrics-projection-smoke.py
python3 examples/issue-fix-repository-snapshot-smoke.py
python3 examples/issue-fix-metrics-supplement-smoke.py
python3 examples/issue-fix-capability-gap-metrics-smoke.py
```
