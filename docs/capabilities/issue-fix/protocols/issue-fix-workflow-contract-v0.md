# issue_fix_workflow_contract_v0

`issue_fix_workflow_contract_v0` ties the existing issue-fix surfaces into one
GitHub issue fix workflow. It is a product contract, not a new state store:
LoopX still uses metadata preview, intake packets, LoopX todos, caller-approved
repo branches, validation evidence, review packets, and explicit gates as the
source of truth.

## User Story

A user gives LoopX a public GitHub issue or PR signal and an approved local
repository context. LoopX should classify the issue, decompose the work into
owner/user gates and agent todos, prepare or claim an issue branch, run the
declared validation, and emit a PR-review-ready packet. LoopX must not read raw
issue bodies, raw comments, private repro material, create external comments,
open PRs, merge, publish, or run destructive git without an explicit gate.

## Workflow Stages

1. **Candidate preflight:** when the caller supplies
   `issue_fix_candidate_preflight_input_v0`, reconcile prior issue-fix domain
   state, all-state numeric PR references, and current-revision-verified
   semantic implementation PR evidence before projecting patch-planning work.
   The provider-neutral seam performs no searches itself. It returns
   `proceed`, `reuse_existing_pr`, `comment_only`, or `skip`; non-proceed routes
   suppress new classification/feasibility todos and preserve any existing
   agentic-recall receipt instead of opening another recall window. Terminal
   domain state or a matching merged implementation takes precedence over a
   simultaneous open implementation. Non-proceed routes also suppress
   unrelated body/comment read gates because no new candidate classification
   will consume that provider content.
2. **Metadata preview:** build `github_issue_metadata_preview_v0` from a public
   URL, compact reference, mocked metadata, or caller-approved metadata fetch.
   Allowed fields are repo, issue or PR number, state, title summary, labels,
   updated timestamp, author association, comment count, and permalink. Body,
   comment, timeline, event, raw, and provider response fields are gated.
3. **Intake classification:** build `issue_fix_intake_v0` with issue class,
   code-context route candidates, owner/user gate projections, and ordered
   agent todo candidates. The first screen must name `waiting_on`, top agent
   todo, top gate when present, and next safe action.
4. **Repository context:** build `issue_fix_repository_context_v0` from a
   pinned repository revision plus compact source refs. Current authoritative
   or verified repository evidence may ground change scope, reproduction, and
   validation. Stale memory and external experts remain advisory. The context
   projects missing reads but does not introduce another lifecycle state,
   authorize external writes, or override feasibility routing.
5. **Workflow plan:** build `issue_fix_workflow_plan_packet_v0` to compose the
   metadata preview, intake, branch dry-run, validation label, ordered LoopX
   todo writeback preview, resolution route candidates, gate preview, post-PR
   lifecycle monitor plan, and PR-review readiness blockers. This stage is
   preview-only and does not write todos.
6. **Feasibility checkpoint:** build `issue_fix_feasibility_v0` from compact
   public-safe agent observations. The decision must select exactly one
   `fix_pr`, `comment_only`, or `triage_only` route. `fix_pr` requires bounded
   scope plus named reproduction and validation surfaces; planned reproduction
   projects confirmation work before patch work. With a goal id, the compact
   decision writes issue-fix domain state by default.
7. **LoopX todo writeback:** initially write only metadata classification and
   the feasibility checkpoint. Then write the single route-specific successor
   projected by feasibility, or record its structured no-follow-up. User todos
   represent concrete external-write, private-material, merge, publish, or
   repository-policy gates.
8. **Caller repo branch:** use `issue_fix_caller_repo_branch_packet_v0` only
   after the caller provides an approved local git repo, base branch, issue
   branch policy, and validation command. Dry-run mode must not inspect the
   repo. Execute mode may inspect the approved repo and create or claim a
   `codex/` issue branch, but must refuse branch switches from dirty state.
9. **Validation:** record focused validation as pass/fail, exit code, and
   public-safe label. Validation stdout, stderr, local paths, and raw git output
   stay out of the packet. A validated fix should prove failing-before and
   passing-after evidence when that repro path is available. When delivery
   names a commit and reports `passed` or `completed`, writeback must resolve
   the declared repository revision and commit in the caller-approved checkout,
   prove commit ancestry, and retain `issue_fix_repository_commit_evidence_v0`
   with a matching repository fingerprint plus a full recoverable branch, tag,
   or remote ref. Missing or stale commit proof fails before state mutation;
   legacy unproved rows project as `unverified`, not publication-ready.
10. **PR review packet:** emit `issue_fix_pr_review_packet_v0` only when branch,
   validation, and repo-relative changed-file evidence are sufficient for human
   review. Its `issue_fix_pr_description_contract_v0` keeps the PR-review
   motivation/approach/change/validation/risk structure, requires a compact key
   code or pseudocode section for code changes, and requires a post-fix
   repository CLI or focused code/test reproduction when applicable. Optional
   infographics are limited to complex changes and cannot replace textual
   evidence. Issue-backed changes add one functional reference block after any
   semantic-preference rewrite: use `Fixes #N` for a complete fix targeting the
   default branch, and `Related to #N` for partial work. Use full syntax for
   every issue and verify closing references through GitHub
   `closingIssuesReferences`. The packet is review evidence, not external
   publication authority.
11. **PR lifecycle monitor:** after a PR exists, use
   `issue_fix_pr_lifecycle_monitor_v0` to project compact public PR state into
   exactly one of `runnable_successor`, `monitor_continuation`, `user_gate`, or
   `no_followup`. Terminal PR states such as `MERGED` and `CLOSED` take
   precedence over stale review metadata. Failed checks, requested changes, and
   stale merge states create runnable successors instead of `monitor_quiet_skip`.
   The command writes compact domain state by default when a `--goal-id` or
   `--ledger-path` is provided, and `--no-write-domain-state` keeps it
   preview-only. Persisted lifecycle state should carry an explicit public-safe
   `issue_ref`; numeric aliases such as `#123`, `issue_123`, and `issues/123`
   canonicalize to `issues_123` before writeback. Outcome projection applies
   the same rule to legacy rows, but must not infer the issue from a branch
   name, PR title, or prose. Its
   `issue_fix_pr_grouped_monitor_projection_v1` assigns each open PR to a
   repository lifecycle-state bucket. Materialize at most one
   `continuous_monitor` for each nonempty bucket, upsert/remove PR membership
   as state changes, and complete empty buckets. Never create one monitor per
   PR. Material PR work remains a one-shot advancement todo, and reviewer
   notifications remain one PR per message.
11. **Gate handling:** surface concrete gates instead of silently blocking. Safe
   metadata-only triage, public-code search, and focused smoke drafting may
   continue when those gates do not cover the selected action.
12. **Outcome projection:** use `issue_fix_outcome_projection_v0` to derive one
   stable operator-facing case from the existing feasibility row, repository
   context, optional `issue_fix_delivery_evidence_input_v0`, and optional PR
   lifecycle row. This projection writes no source state and creates no parallel
   workflow state machine. It must keep unknown delivery evidence explicit,
   retain terminal outputs, derive only bounded public-safe `context_tags`, and
   remain consumable by generic projection sinks.
   Default goal-level Kanban sync derives an
   `issue_fix_outcome_collection_projection_v0` from all feasibility rows and
   explicitly linked lifecycle rows before upserting issue outcome cards.

## Public-Safe Boundary

Packets in this workflow must preserve these boundary flags:

- `issue_body_captured: false`
- `comment_bodies_captured: false`
- `response_payload_captured` or `response_payloads_captured: false`
- `local_paths_captured: false`
- `external_writes_performed: false`
- `destructive_git_used: false`

`private_repo_state_read` is `false` for preview, intake, fixtures, and
caller-repo dry-runs. It may be `true` only for caller-approved
`caller-repo-branch --execute`, and even then local paths, raw validation
output, raw git output, and credentials must not be recorded.

## Todo And Gate Shape

Issue-fix todo plans should be small and ordered. For a clear bounded bug, use
the minimum sufficient plan rather than management filler:

- `[P0] Reproduce or classify the issue from public metadata and approved code
  context.`
- `[P0] Patch the selected issue branch and rerun the caller-declared
  validation.`
- `[P1] Prepare the PR review packet with repo-relative changed files,
  validation labels, and remaining gates.`
- `[P2] Monitor the PR lifecycle and project CI, review, merge, or stale-branch
  changes into a successor, gate, continuation, or no-follow-up.`

When several todos have the same priority, planner order plus LoopX write order
is the tie-breaker. Do not infer a gate from prose alone: write it as a user
todo or operator gate with the concrete action it blocks.

Resolution routes must stay explicit. `fix_pr` is appropriate only when a
focused repro or validation plan is available. `comment_only` should produce a
public-safe maintainer comment packet but still needs an explicit external-write
gate. `triage_only` is valid when the issue lacks enough public evidence for a
useful patch or comment.

## Domain State

Issue-fix domain state is a project-local read model for compact decisions and
long-running monitors:

```text
.loopx/domain-state/<goal-id>/issue_fix/feasibility.jsonl
.loopx/domain-state/<goal-id>/issue_fix/pr-lifecycle.jsonl
```

Feasibility rows are keyed by `repo` and `issue_ref`; PR lifecycle rows are keyed
by `repo` and `pr_ref`. They may store compact observations, decisions, and
fingerprints. A feasibility observation may include one compact
`issue_fix_repository_context_v0` projection so its repository revision,
source refs, coverage, expert policy, and memory policy survive across turns.
Domain state must not store issue bodies, comment bodies, raw
provider payloads, raw logs, local paths, credentials, or destructive-git
output. Public packet validation remains the behavior contract; domain state
only keeps the agent from forgetting its latest compact decision.

## Ready Criteria

An issue-fix workflow is PR-review-ready only when all of these are true:

- metadata/intake preserved body-free and comment-free boundaries;
- accepted todos or gates were written to LoopX state, not left in chat;
- the issue branch is created or claimed inside the caller-approved repo;
- the declared validation ran and passed, or the packet clearly says review is
  not ready yet;
- changed files are repo-relative and bounded;
- no external issue comment, PR creation, merge, publish, production action, or
  destructive git action occurred.

## Related Schemas

- `github_issue_metadata_preview_v0`
- `content_ops_issue_fix_metadata_preview_packet_v0`
- `content_ops_issue_fix_intake_packet_v0`
- `issue_fix_intake_v0`
- `issue_fix_workflow_plan_packet_v0`
- `issue_fix_repository_context_input_v0`
- `issue_fix_repository_context_v0`
- `issue_fix_repository_context_effect_v0`
- `issue_fix_feasibility_v0`
- `issue_fix_feasibility_observation_v0`
- `issue_fix_feasibility_decision_v0`
- `issue_fix_feasibility_domain_state_projection_v0`
- `issue_fix_pr_lifecycle_monitor_v0`
- `issue_fix_pr_grouped_monitor_projection_v1`
- `issue_fix_pr_lifecycle_transition_v0`
- `issue_fix_pr_lifecycle_domain_state_projection_v0`
- `issue_fix_delivery_evidence_input_v0`
- `issue_fix_repository_commit_evidence_v0`
- `issue_fix_outcome_case_v0`
- `issue_fix_outcome_projection_v0`
- `issue_fix_outcome_collection_projection_v0`
- `loopx_todo_writeback_preview_v0`
- `issue_fix_caller_repo_branch_packet_v0`
- `issue_fix_validated_fix_artifact_v0`
- `issue_fix_pr_review_packet_v0`
