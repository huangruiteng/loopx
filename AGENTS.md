# Agent Instructions

## Commit And PR Hygiene

### Worktree And PR Gate

For any tracked repository change beyond a trivial typo fix, create or use a
dedicated clean `git worktree` on a `codex/` branch from latest `origin/main`
before editing files. Do not implement changes directly in a dirty primary
worktree, even when the task starts by inspecting that dirty tree.

When a dirty worktree contains potentially valuable changes, first classify it
read-only, then copy or reapply the valuable subset into the dedicated clean
worktree and open a PR from that branch. Reset or clean the original dirty
worktree only after the valuable subset has been merged or explicitly judged
obsolete. Leave unrelated untracked local artifacts alone.

Every tracked repository change must be pushed on a branch and reviewed through
a pull request before it reaches `main`. Do not push broad mixed commits or
direct commits to `main`.

Only skip this worktree/PR gate when the user explicitly says the change is
local-only and must not be proposed for the repository.

For non-trivial repository changes, especially anything that touches benchmark
adapters, smoke tests, public docs, or commit/push workflows, use the
`git-split-commit-pr` workflow before staging:

1. Establish ground truth with `git status --short --branch`,
   `git diff --stat`, `git diff --name-only`, and
   `git ls-files --others --exclude-standard`.
2. Classify every changed path before staging:
   - core product code;
   - core documentation;
   - durable validation smoke;
   - local/private state;
   - low-value or obsolete artifact.
3. Scan candidate paths for credentials, private state, local absolute paths,
   raw benchmark logs, trajectories, verifier output, and internal links.
4. Stage by explicit pathspecs only. Do not use `git add .`.
5. Split commits by reviewer logic:
   - runtime/API behavior;
   - public docs and protocol notes;
   - focused validation or cleanup.
6. Push a branch and open a PR for reviewable batches.

For small, low-risk PRs, maintainers may self-merge after validation when all
of the following are true:

Here, "自合并" means: 自己 review/refine, then admin-bypass merge after the
required validation and authorization.

- the PR only touches public docs, contributor metadata, or narrow cleanup;
- the change is single-purpose and easy to review from the diff;
- required checks or focused smokes have passed;
- private state, raw benchmark evidence, credentials, local paths, and
  generated logs are excluded;
- there is no runtime behavior, benchmark adapter, permission, destructive git,
  or public evidence-policy change that needs separate review.

Small benchmark seam/refactor PRs may also be self-merged when they are like
PR #145: they add or clarify a reusable adapter/control-plane contract, include
focused public smokes, do not launch benchmark jobs, do not change scoring or
runner behavior for an existing benchmark, and do not include temporary probes,
raw evidence, private state, credentials, local paths, or generated logs.

Benchmark helper/runtime PRs may also be self-merged after owner authorization
when they are limited to public benchmark helper code, status/runtime
observation, reducer/closeout plumbing, or benchmark developer workflow support;
focused smokes or compile checks pass; public/private boundary scans are clean;
and the PR does not change benchmark scoring, task semantics, leaderboard or
submission behavior, permission boundaries, or launch new benchmark jobs.

After self-merging, sync local `main`, leave unrelated untracked local artifacts
alone, and continue with the next safe project batch.

## First-Screen Review Gate

Treat the first visible screen of public product surfaces as owner-reviewed
presentation, not as ordinary copy. Before committing, pushing, or self-merging
changes that alter the first viewport, hero block, primary CTA, or opening
navigation of README, hosted frontstage, showcase index pages, product home
pages, or similarly prominent public entry points, show the user a preview
first and wait for approval.

The preview should be concrete enough to judge the presentation: provide the
local URL and, when the surface is visual HTML, a screenshot or browser view of
the first viewport. Do not move the review gate into a PR comment, todo note, or
final summary after the fact. It must happen before the public first-screen
change is finalized.

## Public And Private Boundary

Do not commit internal department, team, customer, meeting, reporting,
strategy, or local operating context into the public repository. This includes
planning notes, status narratives, rollout stories, fixtures, screenshots,
examples, catalog rows, PR descriptions, and review artifacts whose value
depends on private organizational context rather than reusable public product
behavior.

Keep private planning and incident evidence in ignored local state such as
`.local/`, or another explicitly ignored owner-approved location. Only commit
material after it has been generalized into public-safe product, maintainer, or
developer language and no longer reveals internal actors, timelines, reporting
needs, local paths, raw logs, private links, or private decision context.

Before staging public docs, fixtures, examples, catalogs, or metadata, scan the
candidate paths for internal/private wording and ignored local artifact
references. If such context was already pushed, stop normal delivery, run
LoopX self-repair, clean the current public heads, and record any remaining
PR-ref or cached-view cleanup as an explicit user/support gate.

## PR Review Comments

When the user asks the agent to review a GitHub PR, treat PR feedback as a
public collaboration artifact by default. After validating the findings,
publish actionable review findings directly on the PR as a comment or review,
unless the user explicitly asks for a local-only review or the finding contains
private/security-sensitive material that must not be posted publicly.

Do not leave actionable PR blockers only in chat memory. The final user report
should include the PR comment URL and a compact summary of the posted findings.

## Automation And Monitor Todos

Do not hard-code one-off project or PR monitor logic into a generic heartbeat
automation prompt. Recurring project-specific watches, such as "monitor PR #532
until merge", belong in LoopX state as `continuous_monitor` todos with compact
metadata such as `claimed_by`, `unblocks_todo_id`, and evidence notes. The
heartbeat prompt should remain generic and discover monitor work through
status, quota, and todo projection. Only update an automation prompt when the
heartbeat lifecycle contract itself changes or the user explicitly asks to
change the scheduler.

## Projection Sink Design

When adding an operator-facing display sink such as Lark Base, dashboards,
chat summaries, or reports, build it from LoopX's public-safe state and
projection surfaces instead of parsing project-specific private source files.
Valid display inputs include todo projection, quota/status contracts,
frontstage projections, compact run-history events, public-safe evidence
pointers, and redacted source warnings.

Do not make a generic sink depend on the shape of one local document, private
planning file, non-public wiki, raw transcript, local path, or connector payload.
If a source is valuable, first convert it into a bounded LoopX projection with
stable ids, source labels, evidence, and explicit gates; then let the sink
render that projection. Public or multi-user sinks must consume redacted
public-safe evidence. An explicitly owner-only operator board may sync private
planning evidence when the user authorizes that boundary, but it should still
scope rows by `agent_id` and avoid credentials or secrets unless the user
explicitly asks for a credential-handling workflow.

Projection sinks should preserve row lineage as data, not as ad hoc prose. When
rows supersede, migrate, or retire earlier display rows, represent that through
projection lifecycle fields such as `row_lifecycle`, `supersedes`,
`superseded_by`, `source_id`, and compact migration audit evidence. A sink may
render the lineage in existing evidence/history fields, but should not require
reading a project-private source document to understand why a row changed.

## Smoke Retention Policy

Keep a smoke test only when it validates a durable public behavior:

- shipped CLI/runtime behavior;
- a reusable control-plane contract;
- public/private boundary enforcement;
- a regression that previously stranded automation;
- a representative fixture that is likely to catch future bugs.

Do not keep one-off smokes whose main purpose is to assert the exact text of a
dated research note, candidate ranking packet, temporary run review, or
transitional benchmark decision. Preserve that information in the research doc
itself, and cover shared invariants with a data-driven aggregate smoke.

When a smoke grows beyond roughly 500 lines, re-check whether it is really one
test. Prefer splitting reusable logic into product modules and keeping the
smoke as a thin public behavior check. Large integration smokes are acceptable
only when they cover a real end-to-end adapter contract that smaller unit tests
cannot cover.

Benchmark smokes must never require raw task text, raw trajectories, raw logs,
verifier output tails, credentials, uploads, leaderboard submissions, or local
private artifact paths.

## LoopX Self-Repair

When LoopX behavior is surprising, too small, contradictory, or called
out by the user as likely wrong, use the project skill
`skills/loopx-self-repair/SKILL.md`. Treat recurring mistakes as product
or process gaps: update the skill, interaction docs, active-state projection,
or focused smoke so the lesson is durable. Do not resolve self-repair by
lowering gates, guessing around contradictory payloads, or committing private
logs and local state.

## Benchmark Smoke Classification

Use this classification when cleaning or reviewing benchmark-related changes:

- Keep focused boundary smokes such as
  `examples/benchmark-candidate-source-boundary-smoke.py`; they guard a reusable
  public/private source contract.
- Keep ledger and analysis smokes such as
  `examples/benchmark-run-ledger-smoke.py` and
  `examples/benchmark-case-analysis-smoke.py` while the corresponding JSON/MD
  assets are shipped public surfaces.
- Keep state/control-plane regression smokes such as
  `examples/state-projection-gap-smoke.py`; they protect automation from known
  stuck states.
- Treat large adapter integration smokes such as
  `examples/skillsbench-benchmark-run-smoke.py` as high-value but expensive:
  keep them only while they cover real runner/ledger behavior that smaller
  tests do not yet cover, and split them when a stable smaller seam exists.
- Do not keep one smoke per dated Terminal-Bench routing packet. Preserve the
  packet docs as historical evidence and validate shared invariants with
  `examples/terminal-bench-candidate-routing-packets-smoke.py`.
