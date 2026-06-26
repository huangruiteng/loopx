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
| Smoke | `examples/issue-fix-workflow-plan-smoke.py`, `examples/issue-fix-acceptance-loop-smoke.py` |

## Protocols

- [`issue_fix_workflow_contract_v0`](protocols/issue-fix-workflow-contract-v0.md)
- [`issue_fix_acceptance_loop_v0`](protocols/issue-fix-acceptance-loop-v0.md)
- `issue_fix_workflow_plan_packet_v0`
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

## Workflow Plan

```bash
loopx issue-fix workflow-plan --url https://github.com/owner/repo/issues/123
```

The workflow planner is preview-only. It composes public metadata preview,
issue intake, branch dry-run planning, validation labels, ordered LoopX todo
writeback previews, and PR review readiness blockers into one packet. It does
not write LoopX todos, inspect the local repo in dry-run mode, create external
comments or PRs, merge, or capture raw issue body/comment material.

## Validation

```bash
python3 examples/issue-fix-workflow-plan-smoke.py
python3 examples/issue-fix-workflow-contract-smoke.py
python3 examples/content-ops-issue-fix-metadata-preview-smoke.py
python3 examples/content-ops-issue-fix-intake-smoke.py
python3 examples/issue-fix-acceptance-loop-smoke.py
```
