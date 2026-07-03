# Commit Readiness Manifest - 2026-06-06

Status: current public dirty-tree readiness map. Use this file to review and
stage the present LoopX checkout before canary promotion, commit, push,
or PR creation. It supersedes the closed 2026-06-03 historical snapshot for the
current tree only.

This manifest is not approval to publish private material. It is a grouping and
validation map for the public LoopX changes currently visible in
`git status --short`.

## Steering Audit

Chosen slice: turn the large public dirty tree into release-review batches.

Candidates considered:

- P0/P1 commit-readiness manifest for the dirty tree: chosen because the tree
  now spans promotion-gate, dashboard, quota/state, docs, and smoke surfaces;
  without grouping, later commit or canary promotion would be harder to review.
- P1 add another promotion-gate fixture: deferred because the structured gate
  path now has JSON, status, dashboard, installer, grouped demo-readiness, and
  no-write contract coverage.
- P1 dashboard polish: deferred until the current product-hardening batches are
  staged or intentionally kept together.

No-progress self-stop check: not triggered. Recent eligible turns produced
validated artifacts, new grouped smoke coverage, state writeback, and contract
docs rather than repeated status-only checks.

## Staging Decision - 2026-06-06T05:34:28+08:00

Decision: do not stage Batch 1 as whole files in this heartbeat.

Reason: the first review batch is product-coherent, but several required files
are not hunk-isolated. Whole-file staging would silently mix release-promotion
readiness with other current dirty-tree surfaces:

- `loopx/status.py` includes promotion-gate projections, but also
  dependency blockers, autonomous backlog candidates, event-ledger summaries,
  decision freshness, quota/handoff helpers, and status contract changes.
- `README.md`, `docs/status-data-contract.md`,
  `examples/control_plane/status-markdown-smoke.py`, and `examples/status.example.json`
  carry promotion-gate documentation or fixtures alongside broader
  control-plane and status-contract updates.
- `apps/dashboard/src/views/dashboard-page.tsx` is not part of Batch 1, but it
  consumes related status fields and makes a pure Batch 1 review boundary harder
  to validate by whole-file staging.

Publication blocker: the current dirty tree should not be staged as Batch 1
with plain `git add <file>` because that would erase the manifest's review
boundary. The safe paths are:

1. stage a larger combined release-readiness product-hardening batch covering
   the shared Batch 1, Batch 2, and Batch 4 status/dashboard surfaces after the
   minimum final validation passes; or
2. add a hunk-level staging map for the shared files above, then stage only the
   promotion-gate hunks plus their exact tests/docs.

No files were staged by this decision. The Git index remains available for a
clean follow-up staging pass.

Validation after this decision: `python3 examples/promotion-gate-smoke.py`,
`python3 examples/control_plane/status-markdown-smoke.py`, `loopx-canary check`, and
`git diff --check` passed.

## Hunk-Level Staging Map - 2026-06-06T05:38:30+08:00

Goal: make the next staging pass executable without losing the review boundary.

Preferred staging strategy: do not stage Batch 1 as whole files. Either stage a
larger combined release-readiness batch, or apply the hunk map below and then
stage only the exact release-promotion hunks.

### Whole-File Stage Candidates

These files are narrow enough to stage whole-file for the release-readiness
batch:

- `loopx/promotion_gate.py`
- `examples/promotion-gate-smoke.py`
- `examples/canary/canary-promotion-readiness-smoke.py`
- `examples/canary/canary-promotion-readiness-writeback-smoke.py`
- `examples/canary/canary-promotion-no-write-contract-smoke.py`
- `examples/dashboard-promotion-readiness-browser-smoke.mjs`
- `examples/dashboard-promotion-gate-warning-status.json`

These files are also release-readiness candidates, but review whether the
larger combined batch includes dashboard/demo readiness before staging:

- `apps/dashboard/smoke/usage-progress-smoke.ts`
- `examples/dashboard-demo-readiness-smoke.py`
- `examples/install-local-smoke.py`
- `scripts/install-local.sh`

### Shared-File Hunk Anchors

Use `git add -p` or an equivalent cached patch. Do not whole-file stage these
unless choosing the larger combined release-readiness batch.

- `loopx/cli.py`
  - stage the `.promotion_gate` import;
  - stage the `promotion-gate` subparser definition;
  - stage the `if args.command == "promotion-gate"` handler;
  - avoid unrelated review-packet, todo, heartbeat, or global-registry hunks.
- `loopx/doctor.py`
  - stage `PROMOTION_READINESS_CLASSIFICATIONS`,
    `PROMOTION_READINESS_FRESHNESS_HOURS`,
    `add_promotion_readiness_freshness()`, and
    `latest_promotion_readiness_event()`;
  - stage the `release_provenance.promotion_readiness` collection/rendering
    hunks;
  - avoid unrelated install wrapper or PATH diagnostics unless the combined
    release-readiness batch intentionally includes them.
- `loopx/status.py`
  - stage promotion-readiness imports from `doctor.py` and the
    `build_promotion_gate` import;
  - stage `PROMOTION_READINESS_PROXY_NOTE`;
  - stage `build_promotion_readiness_summary()`;
  - stage `collect_status()` hunks that add `promotion_readiness_summary` and
    `promotion_gate`;
  - stage `render_status_markdown()` hunks that render
    `## Promotion Readiness Summary` and `## Promotion Gate`;
  - avoid dependency-blocker, autonomous-backlog, event-ledger,
    decision-freshness, and handoff-outcome hunks unless using the larger
    combined release-readiness batch.
- `README.md`
  - stage install/canary-promotion readiness instructions;
  - stage `promotion-gate --format json` operator guidance;
  - stage dashboard demo-readiness references only if the batch also includes
    dashboard readiness files;
  - avoid the broad README rewrite hunks unless choosing the combined batch.
- `docs/status-data-contract.md`
  - stage optional top-level fields for `promotion_readiness_summary` and
    `promotion_gate`;
  - stage the `Promotion Gate JSON` section;
  - stage the `Promotion Readiness Summary` section and quota-guard warning
    paragraph;
  - avoid unrelated top-4 todo, dependency blocker, operator gate, or freshness
    contract hunks unless choosing the combined batch.
- `examples/control_plane/status-markdown-smoke.py`
  - stage the import for `build_promotion_readiness_summary`;
  - stage `assert_promotion_readiness_summary_markdown()`;
  - stage `assert_promotion_gate_summary_markdown()`;
  - stage `assert_promotion_readiness_full_scan_fallback()`;
  - stage `assert_promotion_readiness_warning_in_quota_guard()`;
  - stage the matching `main()` calls;
  - avoid connected-delivery outcome-floor and other queue/handoff assertions
    unless choosing the combined batch.
- `examples/status.example.json`
  - stage only the `promotion_readiness_summary` and `promotion_gate` top-level
    JSON blocks plus directly required optional-field references.
- `apps/dashboard/src/data/status.ts`
  - stage `promotionReadinessSummarySchema`, `promotionGateSchema`,
    top-level `promotion_readiness_summary` / `promotion_gate`, and their
    exported types;
  - avoid event-ledger, decision-freshness, dependency-blocker, and handoff
    schema hunks unless choosing the combined batch.
- `apps/dashboard/src/views/dashboard-page.tsx`
  - stage promotion-readiness and promotion-gate imports/types;
  - stage the ops panel insertions for `PromotionReadinessSummaryPanel` and
    `PromotionGatePanel`;
  - stage the two panel components and their variant helpers;
  - avoid unrelated home-control-plane, top-4 todo, dependency blocker,
    decision-freshness, and handoff UI hunks unless choosing the combined
    batch.

### Recommended Next Staging Pass

The lower-conflict path is a larger combined release-readiness batch covering
Batch 1 plus the dependent dashboard/status contract pieces from Batch 2 and
Batch 4. That batch should stage whole files only after the minimum final
validation passes:

```bash
python3 examples/run-smokes.py
python3 examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence
npm --prefix apps/dashboard run smoke:demo-readiness
npm --prefix apps/dashboard run build
loopx-canary check
git diff --check
```

If that validation passes and no private-boundary issue appears, stage the
combined release-readiness batch or write back the exact file/hunk that blocks
staging.

Validation after adding this map: `python3 examples/promotion-gate-smoke.py`,
`python3 examples/control_plane/status-markdown-smoke.py`, `loopx-canary check`, and
`git diff --check` passed.

## Staging Applied - 2026-06-06T05:43:51+08:00

Decision: stage the larger combined release-readiness product-hardening batch
with an explicit file list after the minimum final validation passed.

Reason: the exact promotion-gate-only hunk path is available, but the current
dirty tree is already a coherent release-readiness hardening set spanning
promotion gate, dashboard/demo availability, status contracts, quota/heartbeat
handoff, decision freshness, and public validation smokes. Keeping these hunks
split would add review overhead without reducing the validated product risk.

Validation before staging:

- `python3 examples/run-smokes.py`: passed with 31 smoke scripts.
- `python3 examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence`:
  passed.
- `npm --prefix apps/dashboard run smoke:demo-readiness`: passed, including
  browser smokes.
- `npm --prefix apps/dashboard run build`: passed with the existing Vite
  chunk-size warning.
- `loopx-canary check`: passed; public boundary scan clean.
- `git diff --check`: passed.

Staging rule: use the explicit `git status --short` file list from this
decision point, not `git add .`.

Staging result: applied with the explicit file list at
2026-06-06T05:44:53+08:00. The Git index now contains 63 staged files for this
combined release-readiness product-hardening batch. `git diff --cached --check`
and `git diff --check` passed after staging; `git status --short` showed only
staged entries for the release-readiness batch.

## Commit Decision - 2026-06-06T05:47:20+08:00

Decision: create a public commit for the staged combined release-readiness
product-hardening batch on branch `codex/release-readiness-hardening`.

Rationale: the staged batch has passed the full minimum validation, the public
boundary scan is clean, and the active goal boundary permits routine public-safe
repo publication after validation. The branch was created from the current
local `main`, which was already ahead of `origin/main`; this decision does not
push or open a PR yet.

Commit-scope guard: do not add unstaged runtime outputs, `.loopx/`,
`.local/`, generated dashboard `dist/`, private project evidence, credentials,
or production identifiers.

## Publication Decision - 2026-06-06T05:52:18+08:00

Decision: push branch `codex/release-readiness-hardening` and open a draft PR.

Result:

- branch pushed to `origin/codex/release-readiness-hardening`;
- draft PR: https://github.com/huangruiteng/loopx/pull/1;
- PR title: `[codex] Harden release readiness control plane`.

Publication note: the draft PR is intentionally stacked on the current local
`main` lineage. Relative to `origin/main`, it includes 10 commits: 9 local
predecessor commits around handoff/delivery-scale control-plane hardening plus
`6fd9270 Harden release readiness control plane`. No rebase or history rewrite
was performed.

## Batch 1 - Promotion Gate And Release Readiness

Purpose: make release-promotion readiness a shared structured contract instead
of installer stderr prose or chat memory.

Candidate files:

- `loopx/promotion_gate.py`
- `loopx/cli.py` (promotion-gate command wiring)
- `loopx/doctor.py` (release provenance and promotion readiness)
- `loopx/status.py` (promotion readiness and promotion_gate projections)
- `scripts/install-local.sh`
- `README.md` (canary-promotion and promotion-gate operator path)
- `docs/status-data-contract.md`
- `examples/promotion-gate-smoke.py`
- `examples/canary/canary-promotion-readiness-smoke.py`
- `examples/canary/canary-promotion-readiness-writeback-smoke.py`
- `examples/canary/canary-promotion-no-write-contract-smoke.py`
- `examples/install-local-smoke.py`
- `examples/control_plane/status-markdown-smoke.py`
- `examples/status.example.json`

Validation already observed in recent slices:

- `python3 examples/promotion-gate-smoke.py`
- `python3 examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence`
- `python3 examples/canary/canary-promotion-readiness-writeback-smoke.py`
- `python3 examples/install-local-smoke.py`
- `python3 examples/control_plane/status-markdown-smoke.py`
- live status readback showing `promotion_gate.gate_state=ready`,
  `can_promote=True`, `should_warn=False`, and readiness `fresh`.

Review notes:

- `promotion-gate --format json` is read-only and non-blocking. Automation
  should assert `gate_state`, `can_promote`, `should_warn`,
  `non_blocking`, and `readiness.freshness_status`, not parse
  `warning_message` or installer stderr.
- `scripts/install-local.sh` may warn on missing/stale readiness, but explicit
  promotion remains operator-controlled.
- Evidence writeback must stay append-only via refresh-state/run history.

## Batch 2 - Dashboard, Demo Readiness, And macOS Local Availability

Purpose: make the dashboard demo path resilient and easy to open during
sharing, including stable local services and browser/source smokes.

Candidate files:

- `.gitignore`
- `apps/dashboard/README.md`
- `apps/dashboard/package.json`
- `apps/dashboard/src/data/status.ts`
- `apps/dashboard/src/router.tsx`
- `apps/dashboard/src/views/dashboard-page.tsx`
- `apps/dashboard/smoke/home-route-smoke.ts`
- `apps/dashboard/smoke/usage-progress-smoke.ts`
- `examples/dashboard-demo-readiness-smoke.py`
- `examples/dashboard-home-browser-smoke.mjs`
- `examples/dashboard-ops-decision-freshness-smoke.mjs`
- `examples/dashboard-promotion-readiness-browser-smoke.mjs`
- `examples/dashboard-promotion-gate-warning-status.json`
- `examples/macos-dashboard-launchagent-status-smoke.py`
- `examples/serve-status-global-registry-smoke.py`
- `scripts/macos-dashboard-launchagent.sh`

Validation already observed in recent slices:

- `npm run smoke:demo-readiness -- --skip-browser`
- `npm run smoke:demo-readiness`
- `npm run smoke:home-route`
- `npm run smoke:usage-progress`
- `npm run smoke:promotion-readiness`
- `node ../../examples/dashboard-home-browser-smoke.mjs`
- `node ../../examples/dashboard-ops-decision-freshness-smoke.mjs`
- `python3 examples/macos-dashboard-launchagent-status-smoke.py`
- `npm run build`

Review notes:

- The local demo service target is `127.0.0.1:5174` for the dashboard and
  `127.0.0.1:8766` for status JSON.
- Browser smokes intentionally start temporary Vite servers; keep them explicit
  or grouped under demo-readiness, not hidden inside every heartbeat.
- Do not stage generated `apps/dashboard/dist/` artifacts unless a release
  explicitly asks for built assets.

## Batch 3 - Control-Plane State, Quota, Handoff, And Decision Freshness

Purpose: keep long-running workers coordinated through registry-backed state,
append-only events, quota truth, and checkpointed decision freshness.

Candidate files:

- `docs/heartbeat-automation-prompt.md`
- `docs/integration.md`
- `docs/quota-allocation.md`
- `docs/state-interaction-model.md`
- `skills/loopx-project/SKILL.md`
- `loopx/execution_profile.py`
- `loopx/heartbeat_prompt.py`
- `loopx/operator_gate.py`
- `loopx/quota.py`
- `loopx/review_packet.py`
- `loopx/state_refresh.py`
- `loopx/project_prompt.py`
- `examples/blocker-push-runtime-smoke.py`
- `examples/global-registry-sync-smoke.py`
- `examples/control_plane/heartbeat-prompt-smoke.py`
- `examples/operator-gate-resume-contract-smoke.py`
- `examples/control_plane/quota-contract-smoke.py`
- `examples/control_plane/quota-plan-smoke.py`
- `examples/control_plane/review-packet-cli-smoke.py`
- `examples/control_plane/review-packet-smoke.py`

Validation already observed in recent slices:

- `python3 examples/control_plane/heartbeat-prompt-smoke.py`
- `python3 examples/operator-gate-resume-contract-smoke.py`
- `python3 examples/control_plane/quota-contract-smoke.py`
- `python3 examples/control_plane/quota-plan-smoke.py`
- `python3 examples/control_plane/review-packet-cli-smoke.py`
- `python3 examples/control_plane/review-packet-smoke.py`
- `python3 examples/global-registry-sync-smoke.py`

Review notes:

- This batch encodes the principle that Codex threads are workers; append-only
  run history and registry-backed active state are the durable control plane.
- Decision-point rebase means rereading current state before reusing an old
  reward/gate. It does not roll the repository or worker context backward.
- Routine public-safe commit/push/PR remains allowed after validation and clean
  boundary scan; destructive git, private material, credentials, prod actions,
  or explicit repo review gates still stop automation.

## Batch 4 - Status, Demo Examples, And Public Boundary Fixtures

Purpose: keep status/check/demo examples coherent as the control-plane contract
grows.

Candidate files:

- `loopx/bootstrap.py`
- `loopx/contract.py`
- `loopx/demo.py`
- `loopx/global_registry.py`
- `loopx/status.py` (shared status/data projection hunks)
- `apps/dashboard/src/data/action-packet.ts`
- `examples/contract-reward-overlay-smoke.py`
- `examples/demo-cli-smoke.py`
- `examples/live-project-asset-handoff-readiness.py`
- `examples/registry.example.json`
- `examples/run-smokes.py`
- `examples/usage-summary-smoke.py`

Validation already observed in recent slices:

- `python3 examples/contract-reward-overlay-smoke.py`
- `python3 examples/demo-cli-smoke.py`
- `python3 examples/usage-summary-smoke.py`
- `python3 examples/run-smokes.py` (31 public smoke scripts)
- `loopx-canary check`

Review notes:

- Some files, especially `loopx/status.py` and
  `apps/dashboard/src/views/dashboard-page.tsx`, span several batches. If the
  reviewer wants small commits, use hunk staging. Otherwise, combine related
  status/dashboard batches into one reviewed product-hardening commit.
- Keep fixtures public-safe and relative-path based.

## Cross-Cutting State And Manifest Files

Candidate files:

- `goals/loopx-meta/ACTIVE_GOAL_STATE.md`
- `docs/commit-readiness-manifest-20260606.md`

Guidance:

- Include active-state writeback only if the commit is meant to preserve the
  public project-control history alongside implementation work.
- This manifest can be committed as release-review metadata, or used during
  staging and then removed if the final branch prefers feature-only commits.

## Do Not Commit

Keep these out of any public commit:

- `.local/**`, `.loopx/**` runtime outputs, shared
  `~/.codex/loopx/**` run history, quota events, or live reward overlay
  data.
- Codex App automation config, thread metadata, screenshots, generated browser
  session state, and private local logs.
- `apps/dashboard/dist/**` unless the release explicitly asks for built assets.
- Private project worktrees, internal links, company-only documents, raw local
  user paths, credentials, tokens, production run ids, or private task ledger
  data.

## Minimum Final Validation Before Commit Or Canary Promotion

Run this set after final staging or immediately before canary promotion:

```bash
python3 examples/run-smokes.py
python3 examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence
npm --prefix apps/dashboard run smoke:demo-readiness
npm --prefix apps/dashboard run build
loopx-canary check
git diff --check
```

For a release-promotion evidence writeback, run:

```bash
python3 examples/canary/canary-promotion-readiness-smoke.py
loopx-canary promotion-gate --format json
```

The second command should report `gate_state=ready`, `can_promote=true`, and
`should_warn=false` before `scripts/install-local.sh` promotes the live checkout
into the default local release snapshot.

## Last Observed Validation

Recent heartbeat slices observed the following on this dirty tree or direct
subsets of it:

- `python3 examples/run-smokes.py`: passed with 31 smoke scripts.
- `python3 examples/canary/canary-promotion-readiness-smoke.py --no-write-evidence`:
  passed and showed dashboard demo-readiness before evidence writeback.
- `npm --prefix apps/dashboard run smoke:demo-readiness`: passed, including
  browser smokes.
- `npm --prefix apps/dashboard run build`: passed with the existing Vite chunk
  size warning.
- `loopx-canary check`: passed; public boundary scan clean.
- `git diff --check`: passed.

Re-run the minimum validation after this manifest is edited or after any
additional implementation files are touched.
