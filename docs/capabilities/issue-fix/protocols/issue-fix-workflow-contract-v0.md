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

1. **Metadata preview:** build `github_issue_metadata_preview_v0` from a public
   URL, compact reference, mocked metadata, or caller-approved metadata fetch.
   Allowed fields are repo, issue or PR number, state, title summary, labels,
   updated timestamp, author association, comment count, and permalink. Body,
   comment, timeline, event, raw, and provider response fields are gated.
2. **Intake classification:** build `issue_fix_intake_v0` with issue class,
   code-context route candidates, owner/user gate projections, and ordered
   agent todo candidates. The first screen must name `waiting_on`, top agent
   todo, top gate when present, and next safe action.
3. **Workflow plan:** build `issue_fix_workflow_plan_packet_v0` to compose the
   metadata preview, intake, branch dry-run, validation label, ordered LoopX
   todo writeback preview, gate preview, and PR-review readiness blockers. This
   stage is preview-only and does not write todos.
4. **LoopX todo writeback:** convert accepted candidates into durable LoopX
   todos in priority and dependency order. Typical agent todos are repro smoke,
   code-context route, branch-local patch, validation, and review-packet
   readiness. User todos represent gates such as private repro material,
   external issue comment, PR creation, merge, publish, or repository policy.
5. **Caller repo branch:** use `issue_fix_caller_repo_branch_packet_v0` only
   after the caller provides an approved local git repo, base branch, issue
   branch policy, and validation command. Dry-run mode must not inspect the
   repo. Execute mode may inspect the approved repo and create or claim a
   `codex/` issue branch, but must refuse branch switches from dirty state.
6. **Validation:** record focused validation as pass/fail, exit code, and
   public-safe label. Validation stdout, stderr, local paths, and raw git output
   stay out of the packet. A validated fix should prove failing-before and
   passing-after evidence when that repro path is available.
7. **PR review packet:** emit `issue_fix_pr_review_packet_v0` only when branch,
   validation, and repo-relative changed-file evidence are sufficient for human
   review. The packet is review evidence, not external publication authority.
8. **Gate handling:** surface concrete gates instead of silently blocking. Safe
   metadata-only triage, public-code search, and focused smoke drafting may
   continue when those gates do not cover the selected action.

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

When several todos have the same priority, planner order plus LoopX write order
is the tie-breaker. Do not infer a gate from prose alone: write it as a user
todo or operator gate with the concrete action it blocks.

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
- `loopx_todo_writeback_preview_v0`
- `issue_fix_caller_repo_branch_packet_v0`
- `issue_fix_validated_fix_artifact_v0`
- `issue_fix_pr_review_packet_v0`
