# issue_fix_discovered_issue_promotion_v0

`issue_fix_discovered_issue_promotion_v0` turns a reproducible defect found by
an issue-fix agent during real work into one canonical public issue without
creating a duplicate operator row. It is a composition contract over existing
GitHub and issue-fix state, not another workflow engine.

## Input

`issue_fix_discovered_issue_promotion_input_v0` contains only structured,
public-safe facts:

- repository and local `discovered-*` placeholder reference;
- issue title plus compact problem, reproduction, expected-behavior, and
  validation summaries;
- the current repository revision and repo-relative/public evidence refs;
- `issue_fix_duplicate_search_evidence_v0`, proving that both open and closed
  issues were checked and recording either `reuse_existing` or
  `no_equivalent_found`, plus a compact decision rationale;
- an optional focused PR URL.

The duplicate decision remains an evidence-backed agent judgment. LoopX does
not guess semantic equivalence from title similarity. `reuse_existing` must
name a canonical issue that also appears in the bounded candidate list.

## Execution

Without `--execute`, the command is read/write-free. With `--execute`, it
requires active `publish` authority and performs this ordered transaction:

1. verify the selected existing issue, or create a structured public issue and
   verify the returned URL;
2. if a PR exists, add `Fixes #N` only when needed and use a bounded readback
   retry to require the PR to expose the canonical closing issue;
3. atomically replace the local placeholder feasibility row with the canonical
   issue row while preserving revision-pinned context and compact delivery
   evidence;
4. update an existing PR lifecycle row with the same explicit `issue_ref`; if
   lifecycle projection has not run yet, return `not_projected` and let the
   existing lifecycle wrapper fill it instead of failing promotion.

Retries are idempotent. Closing-reference verification retries at most three
reads with a short delay, covering GitHub's write-after-read lag without
creating a background monitor. An already verified issue/PR association with
one canonical feasibility row produces zero external writes and no duplicate
Kanban or metrics row.

GitHub cannot provide a cross-issue/PR transaction. If issue creation succeeds
but the PR closing-reference update cannot be verified, LoopX still retains the
canonical issue row and returns a concrete
`retry_pr_closing_reference_then_refresh_lifecycle` blocker. The created issue
URL therefore remains auditable instead of being lost behind a generic error.

## Boundary

- raw issue search results, existing PR bodies, provider responses, and logs
  are transient and never retained;
- issue text is composed from the bounded structured input, not a transcript;
- local paths, credentials, private material, and repository-specific branches
  are rejected;
- creating the issue does not authorize merge or production actions.

## Command

```bash
loopx issue-fix promote-discovered-issue \
  --goal-id issue-fix-goal \
  --project /path/to/connected/project \
  --promotion-json discovered-issue-promotion.json \
  --execute \
  --format json
```

## Validation

```bash
python3 examples/issue-fix-discovered-issue-promotion-smoke.py
```
