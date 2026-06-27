# pr_review_command_v0

`pr_review_command_v0` defines the `/loopx-pr-review` command. It helps a
user review unmerged pull requests one by one by turning public GitHub PR
metadata into a guided review queue.

The reviewed repository is the caller's current GitHub project by default, as
resolved by `gh`, or the explicit `--repo owner/repo` target. LoopX's own
repository may be used for dogfood and public fixtures, but the command is not
LoopX-repo-specific.

The command is read-only. It does not approve reviews, post PR comments, merge,
push, spend LoopX quota, or mark LoopX todos complete.

## Command

| Command | CLI reference | Intent |
| --- | --- | --- |
| `/loopx-pr-review` | `loopx pr-review [--repo owner/repo]` | List open PRs for the current project or explicit repository and build a guided review packet with motivation, change scope, checks, risks, and review prompts. |

## Source Reads

Implementations may read compact public PR surfaces:

- pull request title, number, URL, branch, author, state, and review decision;
- PR body summary;
- changed-file list and diff scale;
- commit headlines;
- status-check rollup;
- merge-state metadata.

They must not include raw logs, private connector payloads, credentials, local
absolute paths, private source bodies, or hidden CI artifacts.

## Response Shape

`loopx_pr_review_command_response_v0`:

```json
{
  "schema_version": "loopx_pr_review_command_response_v0",
  "request": {
    "schema_version": "loopx_pr_review_command_request_v0",
    "command": "/loopx-pr-review",
    "cli_command": "loopx pr-review [--repo owner/repo]",
    "repository": "owner/repo",
    "limit": 10,
    "source": "github_cli",
    "privacy_mode": "public_safe_github_metadata",
    "dry_run": true
  },
  "summary": {
    "headline": "5 open PR(s) found; 5 need review attention.",
    "open_pr_count": 5,
    "review_attention_count": 5,
    "draft_count": 0,
    "recommended_first_pr": {
      "rank": 1,
      "number": 773,
      "review_depth": "docs_and_smoke_review"
    }
  },
  "review_sequence": [
    {
      "rank": 1,
      "number": 773,
      "title": "docs: add newcomer command path",
      "url": "https://github.com/owner/repo/pull/773",
      "review_depth": "docs_and_smoke_review",
      "why_now": "Open and awaiting reviewer decision."
    }
  ],
  "pull_requests": [
    {
      "number": 773,
      "motivation": "Adds a newcomer command path...",
      "scale": {"changed_files": 3, "additions": 90, "deletions": 4},
      "areas": {"public_docs": 3},
      "checks": {"summary": "2 successful check(s)."},
      "risk_notes": [],
      "review_prompts": [
        "What user or maintainer value does this PR unlock now?"
      ]
    }
  ],
  "boundary": {
    "raw_logs_recorded": false,
    "credential_values_recorded": false,
    "absolute_paths_recorded": false
  }
}
```

## Review Flow

The packet should let a reviewer move through PRs in order:

1. Read the motivation and decide whether the PR should exist.
2. Compare the touched areas and key files with that scope.
3. Inspect validation and risk notes before approval or merge handoff.
4. Decide `approve`, `request changes`, `defer`, or `merge after checks`.

## Acceptance Checks

A first implementation is acceptable when:

- `loopx slash-commands` exposes `/loopx-pr-review`;
- `loopx pr-review` returns `loopx_pr_review_command_response_v0`;
- default live reads use the caller's current `gh` repository, while
  `--repo owner/repo` can review another GitHub project;
- the response includes review sequence, motivation, changed-file scope,
  status checks, risk notes, and review prompts;
- live GitHub reads and fixture-based smokes share the same schema;
- no raw logs, private payloads, credentials, local paths, or private source
  bodies are recorded.
