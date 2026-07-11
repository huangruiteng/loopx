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
    "memory_verified_patch_influence": 1
  }
}
```

This is an allowlisted compact input, not a raw provider payload. Missing counts
remain `null` and produce a `missing_data` reason code. A missing measure is never
coerced to zero.

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

## Monthly Impact projection

The metrics packet includes stable `impact_rows` for repository health,
delivery, quality, autonomy, capability, and memory. Every row keeps its
baseline, current value, delta, numerator/denominator when applicable, public
source URL, freshness timestamp, and missing-data reason.

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
```
