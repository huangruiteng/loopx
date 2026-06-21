# Commit Readiness Manifest - 2026-06-03 (Closed Historical Snapshot)

Status: closed historical snapshot. The public dirty tree described below was
validated, committed, and pushed through later LoopX slices. Do not use
this file as a current dirty-tree checklist.

Current use:

- Treat this file as archival evidence of how the 2026-06-03 public tree was
  grouped before publication.
- Re-check current readiness with `git status --short`, `git log -1 --oneline`,
  `loopx --format json check --scan-root .`, and
  `goals/loopx-meta/ACTIVE_GOAL_STATE.md` before acting on any cluster.
- Preserve the publish-policy notes below as historical context, not as proof
  that the present tree is ready to publish.

For public LoopX daily iteration, autonomous commit/push and PR creation
are allowed when the public-sensitive scan is clean, validation passes, and the
change does not include company-internal or private material.

## Steering Audit

Chosen slice: produce a four-cluster commit-readiness manifest for the current
public dirty tree.

Candidates considered:

- P0 commit-readiness manifest for the dirty tree: chosen because ungrouped
  public changes now create coordination load.
- P0 health/status recheck: valuable, but already clean and not enough by
  itself to make the dirty tree reviewable.
- P1 dashboard/demo polish: allowed again, but lower value until the existing
  changes are grouped and validated.

No-progress self-stop check: not triggered. The recent eligible heartbeats
produced real state, automation, and public prompt-generator changes, so this
was not a 5-turn status-loop.

## Cluster 1 - First-Run And Heartbeat Lifecycle Contract

Purpose: make the fresh-user path and recurring heartbeat prompt safer to copy,
with a built-in no-progress self-stop guard so automatic runs do not spin
forever on repeated status checks.

Candidate files:

- `README.md`
- `docs/heartbeat-automation-prompt.md`
- `loopx/heartbeat_prompt.py`
- `skills/loopx-project/SKILL.md`
- `examples/heartbeat-prompt-smoke.py`

Validation already run in this slice:

- `python3 examples/heartbeat-prompt-smoke.py`
- `python3 -m py_compile loopx/heartbeat_prompt.py examples/heartbeat-prompt-smoke.py`
- `python3 -m compileall -q loopx`

Remaining before commit:

- Regenerate one sample `loopx heartbeat-prompt --goal-id ...` output
  manually and skim that it stays human-readable.
- Check that the public template does not promise a specific Codex App API
  surface beyond "delete or pause through automation management".

Boundary risks:

- The prompt discusses Codex App automation behavior. Keep it generic enough for
  public users and do not mention local thread ids, local automation ids beyond
  examples, or private operator history.

## Cluster 2 - Runtime, Status, And Contract Truth

Purpose: keep status and health trustworthy when local/demo runtime residue or
run-bound human reward overlays exist.

Candidate files:

- `loopx/history.py`
- `loopx/status.py` (runtime/status hunks)
- `loopx/contract.py`
- `examples/status-markdown-smoke.py`
- `examples/contract-reward-overlay-smoke.py`

Validation already run in prior slices or this slice:

- `python3 examples/status-markdown-smoke.py`
- `python3 examples/contract-reward-overlay-smoke.py`
- `loopx --format json check --scan-root .`

Remaining before commit:

- Run the aggregate public smoke runner after the final staged set:
  `python3 examples/run-smokes.py`.
- Confirm reward-overlay duplicate handling still warns on ordinary duplicate
  index rows, not only on the new fixture.

Boundary risks:

- `status.py` also carries review-material changes from Cluster 3, so a
  file-level commit will mix clusters unless using hunk staging.
- Runtime or demo directories under a shared local runtime must not be staged.

## Cluster 3 - User Todo Review-Material Reader

Purpose: let a user-facing todo carry safe Markdown review materials so the
dashboard can show the first useful reading packet without forcing the operator
to browse project files manually.

Candidate files:

- `loopx/materials.py`
- `loopx/status.py` (todo review-material hunks)
- `loopx/status_server.py` (loopback `/review-material` endpoint)
- `apps/dashboard/src/data/status.ts`
- `apps/dashboard/src/views/dashboard-page.tsx` (review-material UI hunks)
- `examples/user-todo-review-material-smoke.py`

Validation already run in prior slices:

- `python3 examples/user-todo-review-material-smoke.py`

Remaining before commit:

- Re-run `python3 examples/user-todo-review-material-smoke.py` after final
  staging because it covers path containment and server access.
- Confirm dashboard build still passes after shared dashboard hunks:
  `npm --prefix apps/dashboard run build`.

Boundary risks:

- Review material reads must remain local Markdown only, root-limited to the
  goal repo/state/runtime roots, and loopback-only through the status server.
- Do not weaken the URL/path checks to support remote URLs in this cluster.

## Cluster 4 - Dashboard Reward Append Flow

Purpose: make the dashboard reward append path use the exact dry-run payload,
including `recorded_at`, so the append action cannot drift from the preview the
operator accepted.

Candidate files:

- `apps/dashboard/src/views/dashboard-page.tsx` (reward dry-run payload lock
  hunks)
- `examples/dashboard-reward-append-browser-smoke.mjs`

Validation already run in prior slices:

- `npm --prefix apps/dashboard run build`
- `node examples/dashboard-reward-append-browser-smoke.mjs`

Remaining before commit:

- Re-run the dashboard build after Cluster 3 and Cluster 4 hunks are both
  staged.
- Re-run the browser smoke if committing the reward append path.

Boundary risks:

- `apps/dashboard/src/views/dashboard-page.tsx` contains both Cluster 3 and
  Cluster 4 hunks. If the operator wants separate commits, use hunk staging; if
  not, commit Clusters 3 and 4 together as "dashboard operator action paths".
- Reward append is intentionally gated by the loopback status server and
  `--enable-reward-write-api`; do not make it available for remote status URLs.

## Cross-Cutting State And Manifest Files

Candidate files:

- `goals/loopx-meta/ACTIVE_GOAL_STATE.md`
- `docs/commit-readiness-manifest-20260603.md`

Commit guidance:

- Treat `goals/loopx-meta/ACTIVE_GOAL_STATE.md` as public state
  writeback. It may be included with a final "state and manifest" commit if the
  public boundary scan remains clean.
- This manifest can be committed as review metadata or deleted before a final
  feature-only commit, depending on the operator's release preference.

## Do Not Commit

These are not part of the public dirty tree and must stay out of any commit:

- `.local/**` from any connected project.
- Codex App automation config and thread metadata.
- Shared runtime history under the local LoopX runtime directory,
  including quota spend, state refresh, archived demo, and reward overlay run
  files.
- Temporary demo project directories, dashboard dev-server artifacts, generated
  screenshots, browser session state, and `apps/dashboard/dist/` unless the
  release explicitly asks for built assets.
- Private project worktrees, internal links, private documents, raw local paths,
  credentials, tokens, task ids, or production run identifiers.

## Minimum Final Validation

Before any commit or PR, run:

```bash
python3 examples/run-smokes.py
python3 examples/heartbeat-prompt-smoke.py
python3 examples/status-markdown-smoke.py
python3 examples/user-todo-review-material-smoke.py
python3 examples/contract-reward-overlay-smoke.py
npm --prefix apps/dashboard run build
node examples/dashboard-reward-append-browser-smoke.mjs
loopx --format json check --scan-root .
git diff --check
```

If any dashboard/browser smoke is skipped, record the skip reason in the active
goal state before committing.

## Final Validation Run - 2026-06-03T10:53:49+08:00

Status: passed.

Commands run:

- `python3 examples/run-smokes.py`
- `python3 examples/heartbeat-prompt-smoke.py`
- `python3 examples/status-markdown-smoke.py`
- `python3 examples/user-todo-review-material-smoke.py`
- `python3 examples/contract-reward-overlay-smoke.py`
- `npm --prefix apps/dashboard run build`
- `node examples/dashboard-reward-append-browser-smoke.mjs`
- `loopx --format json check --scan-root .`
- `git diff --check`

Notes:

- The aggregate smoke runner passed 18 public smoke scripts.
- The dashboard build passed with the existing Vite chunk-size warning.
- The dashboard reward append browser smoke passed.
- `loopx check` passed with errors=0, warnings=0, and a clean public
  boundary scan over 86 files.

## Public-Sensitive Diff Review - 2026-06-03T10:56:57+08:00

Status: passed. No commit, push, or staging was performed in that slice.

Scope reviewed:

- 13 modified tracked files from `git diff --name-status`.
- 5 untracked public candidate files from `git ls-files --others
  --exclude-standard`.
- The current dirty tree remains within the four clusters plus state/manifest
  writeback listed above.

Commands run:

- `git status --short`
- `git diff --name-status`
- `git ls-files --others --exclude-standard`
- `git diff --stat`
- Targeted `rg` sensitive-pattern scan over the candidate files.

Findings:

- No private path, internal URL, company-doc marker, sensitive assignment,
  auth-header pattern, or cloud-key pattern was found in the reviewed candidate
  files.
- `apps/dashboard/src/views/dashboard-page.tsx` contains both review-material
  and reward-append hunks; use hunk staging if the operator wants separate
  commits for Cluster 3 and Cluster 4.
- `loopx/status.py` contains both runtime/status and review-material
  hunks; use hunk staging if Cluster 2 and Cluster 3 should stay separate.
- `goals/loopx-meta/ACTIVE_GOAL_STATE.md` is large state writeback; keep
  it as a final state/manifest commit or omit it from feature commits if the
  operator wants a lean release branch.

Suggested staging order for autonomous or operator-requested commits:

1. Cluster 1: first-run and heartbeat lifecycle contract.
2. Cluster 2: runtime, status, and contract truth.
3. Cluster 3: user todo review-material reader.
4. Cluster 4: dashboard reward append flow.
5. State and manifest writeback, if useful as review metadata.

Re-run the Minimum Final Validation after any hunk staging, because hunk splits
can accidentally move shared dashboard/status assumptions across commits.

## Publish Policy Update - 2026-06-03T11:05:02+08:00

The operator clarified that public daily iteration does not need an explicit
request before commit, push, or PR creation.

Current policy:

- Autonomous commit/push is allowed for public LoopX changes when the
  public boundary scan is clean and validation passes.
- Autonomous PR creation is allowed under the same boundary, usually when the
  work is not already on the intended target branch.
- Stop before publishing if a change includes private state, company-internal
  material, credentials, production identifiers, or unexplained generated
  artifacts.
- For this validated dirty tree, use the staging order above and re-run the
  Minimum Final Validation before publishing.

## Publication Validation - 2026-06-03T11:06:50+08:00

Status: passed; safe to publish the current public LoopX dirty tree.

Commands run:

- `python3 examples/run-smokes.py`
- `python3 examples/heartbeat-prompt-smoke.py`
- `python3 examples/status-markdown-smoke.py`
- `python3 examples/user-todo-review-material-smoke.py`
- `python3 examples/contract-reward-overlay-smoke.py`
- `npm --prefix apps/dashboard run build`
- `node examples/dashboard-reward-append-browser-smoke.mjs`
- `loopx --format json check --scan-root .`
- `git diff --check`
- Targeted `rg` sensitive-pattern scan over the candidate files.

Notes:

- The aggregate smoke runner passed 18 public smoke scripts.
- The dashboard build passed with the existing Vite chunk-size warning.
- The dashboard reward append browser smoke passed.
- `loopx check` passed with errors=0, warnings=0, and a clean public
  boundary scan over 88 files.
- The targeted sensitive-pattern scan produced no findings.
