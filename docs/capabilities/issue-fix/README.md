# Issue-Fix Capability

The issue-fix capability is the product path for open-source issue/PR solver
work. It is intentionally narrower than a generic workflow engine: it starts
from public GitHub metadata, prepares or claims a caller-approved local branch,
runs caller-declared validation, and emits review evidence without creating
external comments, PRs, merges, or publishes.

## Implemented Surface

| Layer | Current path |
| --- | --- |
| Capability module | `loopx/capabilities/issue_fix/` |
| CLI entry | `loopx issue-fix ...` |
| Content-ops bridge | `loopx content-ops issue-fix-* ...` |
| Protocol docs | `docs/capabilities/issue-fix/protocols/` |
| Smoke | `examples/issue-fix-workflow-plan-smoke.py`, `examples/issue-fix-feasibility-smoke.py`, `examples/issue-fix-pr-lifecycle-smoke.py`, `examples/issue-fix-acceptance-loop-smoke.py` |

## Protocols

- [`issue_fix_workflow_contract_v0`](protocols/issue-fix-workflow-contract-v0.md)
- [`issue_fix_acceptance_loop_v0`](protocols/issue-fix-acceptance-loop-v0.md)
- `issue_fix_workflow_plan_packet_v0`
- `issue_fix_feasibility_v0`
- `issue_fix_pr_lifecycle_monitor_v0`
- `github_issue_metadata_preview_v0`
- `content_ops_issue_fix_metadata_preview_packet_v0`
- `content_ops_issue_fix_intake_packet_v0`
- `issue_fix_intake_v0`
- `issue_fix_validated_fix_artifact_v0`
- `issue_fix_caller_repo_branch_packet_v0`

Metadata and intake packet details are currently shared with the content-ops
surface because issue discovery and content/source intake use the same public
metadata boundary.

## Safe Defaults

- Issue bodies, comments, timeline events, and raw provider payloads are gated
  and are not copied into packets.
- Caller repo mode reads and writes only the explicitly approved local git repo.
- Validation stdout/stderr and local paths are summarized, not recorded.
- External issue comments, PR creation, merge, publish, and destructive git are
  out of scope for this capability.

## Conversational `/loopx` Entry

When the user starts from a chat box or command palette, use the project-local
goal command first:

```text
/loopx Fix https://github.com/owner/repo/issues/123
```

The host or skill fallback should run the command pack preview with the exact
goal text:

```bash
loopx bootstrap-command-pack --project . \
  --goal-text "Fix https://github.com/owner/repo/issues/123"
```

For a GitHub issue/PR fix goal, the command pack points to the issue-fix
workflow planner before todo writeback:

```bash
loopx issue-fix workflow-plan \
  --url https://github.com/owner/repo/issues/123 \
  --repo-path <approved-repo> \
  --validation-label "<validation command>" \
  --format json
```

The workflow-plan output is still preview-only. Initial writeback is deliberately
small: public metadata classification followed by one feasibility checkpoint.
The checkpoint selects exactly one `fix_pr`, `comment_only`, or `triage_only`
route and projects only that route's successor or no-follow-up. Concrete owner
actions remain explicit gates, including private repro material, issue
body/comment reads, external issue comments, PR creation, merge, publish,
destructive git, production actions, and repository-policy approvals.

## Workflow Plan

```bash
loopx issue-fix workflow-plan --url https://github.com/owner/repo/issues/123
```

The workflow planner is preview-only. It composes public metadata preview,
issue intake, branch dry-run planning, validation labels, ordered LoopX todo
writeback previews, and PR review readiness blockers into one packet. It does
not write LoopX todos, inspect the local repo in dry-run mode, create external
comments or PRs, merge, or capture raw issue body/comment material.

## Feasibility Decision

```bash
loopx issue-fix feasibility \
  --url https://github.com/owner/repo/issues/123 \
  --reproduction-status planned \
  --reproduction-label "focused repro plan" \
  --scope-class bounded \
  --validation-label "focused unit test" \
  --goal-id example-goal \
  --format json
```

Feasibility consumes only compact agent observations. It never stores raw issue
bodies, comment bodies, provider responses, logs, local paths, or credentials.
`fix_pr` requires bounded scope plus named reproduction and validation surfaces;
a planned repro first projects `issue_fix_confirm_reproduction`, not patch work.
`comment_only` projects a comment-draft todo with an external-write gate, while
`triage_only` projects structured no-follow-up.

With `--goal-id` or `--ledger-path`, the decision is upserted by repo and issue
reference into `.loopx/domain-state/<goal-id>/issue_fix/feasibility.jsonl`.
Use `--no-write-domain-state` for preview-only checks.

## PR Lifecycle Monitor

```bash
loopx issue-fix pr-lifecycle \
  --url https://github.com/owner/repo/pull/123 \
  --metadata-json public-pr-state.json \
  --goal-id example-goal \
  --format json
```

The PR lifecycle projection turns compact public PR state into one of four
transitions: `runnable_successor`, `monitor_continuation`, `user_gate`, or
`no_followup`. Terminal PR states such as `MERGED` or `CLOSED` take precedence
over stale review metadata; failed checks and requested changes create runnable
successors; quiet states continue the monitor.

When `--goal-id` or `--ledger-path` is provided, the command writes the compact
observation into `.loopx/domain-state/<goal-id>/issue_fix/pr-lifecycle.jsonl` by
default. Use `--no-write-domain-state` for preview-only tests. Domain state is
project-local and gitignored; it records compact row keys, observations,
transition decisions, and fingerprints, never issue bodies, comments, raw
provider payloads, raw check logs, local paths, or credentials.

## Validation

```bash
python3 examples/issue-fix-workflow-plan-smoke.py
python3 examples/issue-fix-feasibility-smoke.py
python3 examples/issue-fix-pr-lifecycle-smoke.py
python3 examples/issue-fix-workflow-contract-smoke.py
python3 examples/content-ops-issue-fix-metadata-preview-smoke.py
python3 examples/content-ops-issue-fix-intake-smoke.py
python3 examples/issue-fix-acceptance-loop-smoke.py
```
