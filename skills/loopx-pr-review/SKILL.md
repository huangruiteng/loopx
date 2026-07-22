---
name: loopx-pr-review
description: Use when the visible request starts with `/loopx-pr-review` or asks LoopX to review a repository PR queue by time window, open/unmerged status, merged/closed status, or current-day PR activity. Run `loopx pr-review` first, preserve the full packet contract, then read PR evidence and produce per-PR reviews with the five required blocks. Do not use for approving, commenting on, merging, self-merging, or admin-bypassing a specific PR; use `loopx-pr-merge` for those actions.
---

# LoopX PR Review

## Routing Boundary

Use this skill for `/loopx-pr-review` and for requests such as:

- review today's open and merged PRs;
- list the unmerged PR queue and take me through review;
- review PRs since a timestamp;
- show the merged PRs that need post-merge audit.

Do not use this skill to approve, request changes on GitHub, post PR comments,
merge, self-merge, or admin-bypass. Route those decisions to `loopx-pr-merge`.

`/loopx-pr-review` is a read-only review workflow. It may use GitHub metadata,
PR bodies, changed files, checks, and diffs, but it must not mutate GitHub or
LoopX state.

## First Command

Run the LoopX CLI before manual GitHub calls:

```bash
loopx --format json pr-review --state all
```

Translate user filters only into these CLI options:

- `--repo owner/repo` for an explicit repository;
- `--since ISO` for an explicit time window;
- `--state open`, `--state merged`, or `--state all` for state filters.
- `--limit N` when the user explicitly requests a bounded batch.

Default to the current `gh` repository, `--state all`, and the CLI's normal
100-PR group limit. Treat words like
`today`, `open`, `closed`, or `merged` as review-queue filters. They do not
mean "stats only" unless the user explicitly says `只统计`, `只列出`,
`stats only`, `list only`, `不要 review`, or `不用分析`.

## Preserve The Packet

Keep these fields in model context from the first CLI packet:

- `agent_response_contract`;
- `result_completeness`;
- `review_groups`;
- `pull_requests[].review_template`;
- `pull_requests[].evidence_commands`.

Do not pipe the first packet through `jq` or another projection that only keeps
`.summary`, `.review_sequence`, or a table. If a compact view is useful, save
the full JSON first and then print the contract-bearing fields:

```bash
packet="$(mktemp)"
loopx --format json pr-review --state all [--repo owner/repo] [--since ISO] > "$packet"
python3 - "$packet" <<'PY'
import json
import sys
p = json.load(open(sys.argv[1]))
print(json.dumps({
  "agent_response_contract": p.get("agent_response_contract"),
  "result_completeness": p.get("result_completeness"),
  "review_groups": p.get("review_groups"),
  "pull_requests": [
    {
      "number": pr.get("number"),
      "title": pr.get("title"),
      "review_template": pr.get("review_template"),
      "evidence_commands": pr.get("evidence_commands"),
    }
    for pr in p.get("pull_requests", [])
  ],
}, ensure_ascii=False, indent=2))
PY
rm -f "$packet"
```

## Require Complete Exhaustive Queues

When the user asks for `all`, `every`, `全部`, `每个`, or an exhaustive time
window, do not start reviewing until `result_completeness.complete=true`.
When it is false, rerun the same first command with
`--limit <result_completeness.recommended_limit>`. Repeat until complete,
preserving the latest full packet as the queue source of truth. Never infer
completeness from `summary.total_pr_count`, a count equal to the limit, or the
absence of a pagination error.

## Review Flow

Review `review_groups.unmerged` first, then `review_groups.merged`. A queue
table can be a short preface, but stopping at the table is incomplete for
`/loopx-pr-review`.

For each selected PR, read the PR evidence before writing the review. Prefer the
packet's `evidence_commands`; equivalent targeted `gh pr view`, `gh pr diff
--name-only`, and `gh pr diff --patch` commands are acceptable when needed.

Treat `agent_response_contract.explanation_depth_contract` and each
`review_template.sections[].agent_instruction` as the canonical detail policy.
The skill owns routing and evidence discipline; it must not maintain a second,
competing explanation checklist. For older packets without the depth contract,
still explain context, architecture, implementation, validation, necessity, and
risk for a reader who may not know the subsystem.

Record the remote `headRefOid` before deep review and query it again before the
verdict. If it changed, review the new head instead of carrying forward stale
findings. Use a clean read-only worktree at the exact head when local execution
or line-level evidence is useful, and name the reviewed short SHA in the answer.

Do not fill the five-block review from title, labels, changed-file counts, or
metadata risk hints alone. `metadata_risk_hint` is only for queue ordering.

If the queue is too large for one response, review the highest-priority PRs
first and say which PRs remain. Do not silently replace review with a summary.

## Output Contract

Lead with a one-line evidence-based verdict and highest-severity reason. Then use
exactly these five headings for each reviewed PR:

1. `动机`
2. `改动思路`
3. `具体改动`
4. `对主干的风险`
5. `我的整体评价`

Use the packet's blank `review_template` as the required structure and minimum
detail signal, not as fake/example content. Fill each section only after reading
PR body, files, checks, and diff. Follow the packet's per-section ranges and
instructions as depth signals rather than padding. Avoid title-only summaries
such as "improves docs" or "low risk", and distinguish intended behavior from
what the implementation and validation actually prove.

## Failure And Fallback

If `loopx pr-review` is unavailable, first repair the LoopX install or run the
checked-out LoopX CLI from the intended worktree. Do not reconstruct the whole
queue manually from GitHub and call it a successful `/loopx-pr-review` run.

If a selected PR needs an approve/hold/merge action, finish the read-only review
first, then route the action to `loopx-pr-merge` or ask for explicit merge
authorization.
