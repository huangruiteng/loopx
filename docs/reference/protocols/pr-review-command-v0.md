# pr_review_command_v0

`pr_review_command_v0` defines the `/loopx-pr-review` command. It helps a
user review open and recently merged pull requests one by one by turning public
GitHub PR metadata into a guided review queue.

The reviewed repository is the caller's current GitHub project by default, as
resolved by `gh`, or the explicit `--repo owner/repo` target. LoopX's own
repository may be used for dogfood and public fixtures, but the command is not
LoopX-repo-specific.

The command is read-only. It does not approve reviews, post PR comments, merge,
push, spend LoopX quota, or mark LoopX todos complete.

## Command

| Command | CLI reference | Intent |
| --- | --- | --- |
| `/loopx-pr-review` | `loopx pr-review [--repo owner/repo] [--state open\|merged\|all] [--since ISO]` | List open and merged PRs for the current project or explicit repository and build a guided review packet with a 100-200 character review card, detailed change analysis, checks, main regression risk, and review prompts. |

## Source Reads

Implementations may read compact public PR surfaces:

- pull request title, number, URL, branch, author, lifecycle state, merge time,
  and review decision;
- PR body summary;
- changed-file list and diff scale;
- status-check rollup;
- merge-state metadata.

Commit headlines may be used as optional single-PR deep-review evidence, but
the default window review should not require fetching them for every PR.

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
    "cli_command": "loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]",
    "repository": "owner/repo",
    "limit": 10,
    "state_filter": "all",
    "since": "2026-06-28T00:00:00Z",
    "window": {"state_filter": "all", "since": "2026-06-28T00:00:00Z"},
    "source": "github_cli",
    "privacy_mode": "public_safe_github_metadata",
    "dry_run": true
  },
  "summary": {
    "headline": "8 PR(s) in review window: 3 open, 5 merged; 8 need review attention.",
    "total_pr_count": 8,
    "open_pr_count": 3,
    "merged_pr_count": 5,
    "review_attention_count": 8,
    "post_merge_review_count": 5,
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
      "state": "OPEN",
      "review_depth": "docs_and_smoke_review",
      "main_risk_level": "low",
      "why_now": "Open and awaiting reviewer decision."
    }
  ],
  "pull_requests": [
    {
      "number": 773,
      "guided_review_card": {
        "schema_version": "guided_pr_review_card_v0",
        "brief": "动机：Adds a newcomer command path...。改动：公开文档 3，3 个文件 +90/-4，重点看 docs/guides/newcomer-command-path.md、docs/README.md。风险：低；检查：2 pass。Review：先看范围和验证是否对齐。",
        "motivation": "Adds a newcomer command path...",
        "concrete_changes": "公开文档 3；3 个文件，+90/-4；重点看 docs/guides/newcomer-command-path.md、docs/README.md、docs/guides/getting-started.md。",
        "risk": "low，Runtime regression risk is low...",
        "checks": "2 successful check(s).",
        "review_prompt": "先判断 PR 是否应该存在，再确认改动范围、验证和主干风险是否对齐。"
      },
      "detailed_change_analysis": {
        "schema_version": "pr_detailed_change_analysis_v0",
        "summary": "这个 PR 的具体改动集中在公开文档 3，总规模 3 个文件、+90/-4。建议先读 docs/guides/newcomer-command-path.md、docs/README.md，确认最大 diff 是否兑现 PR 动机；再看 smoke/文档/检查结果是否能证明这些改动不会让 main 倒退。",
        "area_breakdown": [
          {
            "area": "public_docs",
            "label": "公开文档",
            "file_count": 3,
            "top_files": ["docs/guides/newcomer-command-path.md", "docs/README.md"],
            "change_intent": "沉淀公开说明、协议或使用路径，需要确认文档与实际 CLI/产品行为一致。",
            "review_focus": "重点看命令示例、概念定义、用户路径和 shipped 行为是否一致。"
          }
        ],
        "file_walkthrough": [
          {
            "path": "docs/guides/newcomer-command-path.md",
            "area": "public_docs",
            "delta": "+75/-0",
            "meaning": "`newcomer-command-path.md` 是公开文档，本次 +75/-0 主要改变用户/维护者理解路径，要检查命令和概念是否准确。",
            "review_focus": "重点看命令示例、概念定义、用户路径和 shipped 行为是否一致。"
          }
        ],
        "review_order": ["docs/guides/newcomer-command-path.md", "docs/README.md"]
      },
      "motivation": "Adds a newcomer command path...",
      "scale": {"changed_files": 3, "additions": 90, "deletions": 4},
      "areas": {"public_docs": 3},
      "checks": {"summary": "2 successful check(s)."},
      "risk_notes": [],
      "main_regression_analysis": {
        "schema_version": "main_regression_analysis_v0",
        "risk_level": "low",
        "risk_summary": "low main regression risk across public_docs; 3 file(s), +90/-4.",
        "potential_regressions": [
          "Runtime regression risk is low, but public guidance or smoke expectations can drift from shipped behavior."
        ],
        "bug_risks": [
          "Docs-only or smoke-only changes can bless stale contracts if the example no longer matches the real CLI/runtime path."
        ],
        "verification_focus": [
          "Run `git diff --check` and the touched smoke; compare docs examples with current CLI help when command syntax is involved."
        ],
        "post_merge_review": false
      },
      "review_prompts": [
        "What user or maintainer value does this PR unlock now?",
        "What could regress on main, and which focused validation would catch it?"
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

1. Read `guided_review_card.brief` first. It should be compact enough to paste
   into chat while still naming motivation, concrete changes, risk, checks, and
   the next review question.
2. Read `detailed_change_analysis.summary`, then follow its `review_order` and
   `file_walkthrough` before opening the full diff.
3. Compare the touched areas and key files with the card's stated scope.
4. Inspect validation, risk notes, and `main_regression_analysis`.
5. Decide which regression class matters most on main and which focused
   validation would catch it.
6. Decide `approve`, `request changes`, `defer`, or `merge after checks`.

## Acceptance Checks

A first implementation is acceptable when:

- `loopx slash-commands` exposes `/loopx-pr-review`;
- `loopx pr-review` returns `loopx_pr_review_command_response_v0`;
- default live reads use the caller's current `gh` repository, while
  `--repo owner/repo` can review another GitHub project;
- `--state all` includes merged PRs in the same packet, while `--state open`
  preserves the old open-only review queue;
- `--since` can bound an overnight or release-window review without relying on
  private chat memory;
- the response includes review sequence, motivation, changed-file scope,
  detailed change analysis, status checks, risk notes, main regression analysis,
  and review prompts;
- each PR includes `guided_review_card` with a compact `brief` that is suitable
  for a 100-200 character human-facing Chinese review introduction when source
  metadata is compact;
- each PR includes `detailed_change_analysis` with area breakdown, file
  walkthrough, and review order so the user can understand concrete changes
  before opening GitHub diff;
- live GitHub reads and fixture-based smokes share the same schema;
- no raw logs, private payloads, credentials, local paths, or private source
  bodies are recorded.
