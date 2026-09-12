# RFC: Canonical Todo Semantic Kernel and Read-Model Convergence (v0)

- Status: Proposed implementation RFC
- Proposed by: LoopX maintainers
- Date: 2026-09-12
- Scope: the Todo semantic rules shared by the TypeScript authority path and
  Python projections, building on the [TypeScript Control-Plane Migration
  v0](typescript-control-plane-migration-v0.md) and the [Shared Goal Authority
  and Pluggable State Providers v0](shared-goal-authority-state-provider-v0.md)
- Delivery shape: one compatibility-preserving Python kernel first, followed
  by a language-neutral conformance packet for the TypeScript transaction path
- Language note: the [Chinese version](canonical-todo-semantic-kernel-v0.zh-CN.md)
  is a semantic mirror; a difference is a defect.

## 1. Problem

The two parent RFCs correctly moved authority and transaction ownership toward
TypeScript, but their consumers still carried several copies of the same Todo
rules. `todos/projection.py` owned task classification, priority, monitor
eligibility, claim visibility, and frontier selection. `todos/todo_summary.py`
wrapped many of those functions again and intentionally called classification
with `text` only. Agent scope, quota preparation, Goal Frontier, work-lane
selection, and capability fallbacks each imported or rewrapped a subset.

That split created two kinds of drift:

1. the same record could be classified differently depending on whether the
   caller read a projection or a summary; and
2. a rule fix had to be repeated across compatibility facades, even though the
   canonical coordination record and the provider transaction already had one
   identity contract.

A title-only monitor is a concrete failure. A Todo with `title="Observe build
health"` and an empty `text` was monitor work in the projection path but could
be treated as advancement in the summary path. Claim exclusion had the same
risk when one caller looked at a projected frontier and another rebuilt it from
summary buckets.

## 2. Decision

Create `loopx.control_plane.todos.todo_semantics` as the single Python owner for
provider-neutral Todo read semantics. It owns the pure predicates and ordering
used by all callers:

- task text and task-class resolution;
- open/actionable/deferred status;
- monitor due, expiry, and missing-schedule checks;
- priority extraction, ranking, and stable ordering;
- claim, exclusion, and removed-continuation eligibility;
- claimed visibility and advancement-frontier partitioning.

`todos/projection.py` remains a compatibility export for external integrations
and older extensions. It contains no independent rule implementation. New
production code imports `todo_semantics` directly. `todo_summary.py` continues
to own summary assembly, compaction, and display-specific limits, but it calls
the kernel for every semantic predicate.

The kernel resolves task text from `title` and `text` in that order, retaining
both values when present. A persisted explicit `task_class` still wins over
text inference. This fixes title-only records while preserving existing
explicit classifications and action-kind inference.

The coordination provider remains a storage and CAS boundary. The kernel does
not become a writer, receipt authority, scheduler, or provider adapter. The
TypeScript authority remains the transaction owner described by the parent
RFCs; this RFC removes duplicated Python read policy so the next TypeScript
cutover can compare one semantic packet instead of several ad hoc projections.

## 3. Semantic changes and repairs

### 3.1 Title-aware classification

All Python read paths now use the same `(title, text)` task text. Explicit
`task_class` continues to take precedence. A title-only monitor is therefore a
monitor in status, quota, Goal Frontier, and summary paths. This is a behavior
fix, not a cosmetic rename.

### 3.2 Exclusion is eligibility, not ownership

`excluded_agents` is evaluated after claim ownership. An unclaimed Todo can be
visible to one Agent and ineligible for another; exclusion never creates a
claim, lease, or authority grant. The kernel exposes this as one predicate so
frontier counters and selected IDs cannot disagree.

### 3.3 Stable ordering is one policy

Priority and index ordering are resolved in one place. Missing or malformed
priority remains the bounded rank used by existing projections. The compatibility
facade preserves the old import path and call signature while production callers
move to the kernel.

### 3.4 Display limits remain non-semantic

The kernel never treats a truncated list as the complete Todo set. Summary
assembly may cap display rows, but counts, frontier classification, and
coordination digests continue to use the complete source or an explicitly
qualified canonical projection.

## 4. Ownership and non-goals

This RFC owns read semantics only. It does not:

- change the default provider, promote SQLite/NoKV/PostgreSQL, or migrate an
  existing Goal;
- add a new lease, receipt, scheduler, or network authority;
- make Markdown a generated source of truth;
- infer user approval from `goal_bound`, actor identity, or title text;
- remove the compatibility import until downstream extension inventory and the
  TypeScript conformance packet are complete.

The capability owner is the existing Todo/control-plane contract. No new
capability or provider package is introduced.

## 5. Migration plan

1. **Kernel extraction (this slice).** Move the existing projection rule set to
   `todo_semantics.py`, make `projection.py` a compatibility export, and migrate
   production imports. Keep external import paths working.
2. **Summary convergence (this slice).** Remove the text-only classification
   exception in `todo_summary.py`; summary limits and compaction remain local.
3. **Fixture conformance (this slice).** Extend the deterministic production-
   scale fixture with title-only monitor, excluded unclaimed advancement,
   explicit global gate without goal binding, and an expired lease edge. These
   are synthetic declarations, not copied Goal state.
4. **TypeScript packet (next slice).** Emit the same semantic cases into the
   language-neutral contract and compare TypeScript selection/classification
   results with the Python kernel before deleting more Python adapters.
5. **Compatibility retirement (later).** After extension imports and the
   TypeScript packet are audited, deprecate the `projection.py` facade in one
   disclosed release and remove it only when no supported caller remains.

Each step is reversible: the facade can be restored as an import-only shim, and
no provider selector or persisted revision changes.

## 6. Validation contract

The focused Python tests must prove title-aware classification, monitor due
behavior, exclusion/ownership separation, and fixture edge declarations. The
existing projection, canonical-governance, frontier, and long-history suites
must remain green. TypeScript typecheck and coordination/monitor/quota tests
must remain green because the fixture is consumed by both runtime families.

The real local readback is deliberately read-only:

```bash
loopx --format json status --goal-id loopx-meta
loopx --format json todo list --goal-id loopx-meta --role agent --status open
```

The first command verifies the live registry/runtime contract; the second
checks that the live Goal can still be read through the public Todo surface.
Neither command writes the Goal, changes a lease, or promotes a provider. A
non-zero result is a delivery hold rather than a reason to weaken the fixture.

## 7. Acceptance criteria

- `projection.py` has no independent semantic implementation.
- All production imports use `todo_semantics` or the summary assembler.
- The title-only monitor test passes through both direct and summary paths.
- The complex fixture remains deterministic, public-safe, and consumed by the
  existing TypeScript conformance tests.
- Python focused tests, TypeScript typecheck/tests, `git diff --check`, and the
  read-only `loopx-meta` commands pass.
- No private Goal state, credential, raw run log, local absolute path, or
  generated artifact is committed.

## 8. Duplication inventory

Before this RFC, duplication was structural rather than byte-for-byte only:

| Area | Repeated knowledge | Consequence |
| --- | --- | --- |
| `projection.py` and `todo_summary.py` | task classification, actionable status, priority ordering, monitor predicates | title/text disagreement and repeated fixes |
| agent scope and quota preparation | local wrappers around actionable/classification predicates | callers could silently choose different helper defaults |
| Goal Frontier and work-lane consumers | claim/exclusion and frontier partitioning | counters and selected IDs could diverge |
| Python projection and TypeScript transaction consumers | canonical Todo fields and provider read-model shape | migration required several comparison points |

The first three rows are consolidated here. The fourth remains an explicit
cross-language conformance task for the next RFC slice; this PR does not claim
to delete the TypeScript authority or alter provider semantics.

## 9. Open questions

- Which supported extension release first stops importing `projection.py`?
- Should the TypeScript packet be generated from the coordination state contract
  or remain a separately versioned semantic fixture?
- What evidence is sufficient to retire the compatibility facade without
  surprising local plugins?

Those questions do not block this read-policy consolidation because the facade
preserves the current public import surface.
