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

Codex agents should use the dedicated `loopx-pr-review` skill for this slash
command. Do not route `/loopx-pr-review` through the broader `loopx-project`
workflow or the merge-focused `loopx-pr-merge` skill.

## Command

| Command | CLI reference | Intent |
| --- | --- | --- |
| `/loopx-pr-review` | `loopx pr-review [--repo owner/repo] [--state open\|merged\|all] [--since ISO]` | List open and merged PRs for the current project or explicit repository, provide concrete main-regression analysis for each PR, and include a blank five-block template that agentloop fills after reading the selected PR body/diff. |

The slash command must run the CLI first. Agentloop must not reconstruct the
review window by manually calling `gh pr view` / `gh pr list` for every PR. The
CLI packet's `review_groups.unmerged`, `review_groups.merged`, and
`pull_requests[].review_template` are the authoritative queue. The packet's
`evidence_commands` are for the second step: reading one selected PR deeply.
Use the JSON form for the first pass so the response contract and per-PR blank
templates enter the model context:

```bash
loopx --format json pr-review --state all [--repo owner/repo] [--since ISO]
```

Do not pipe that first packet through `jq` or another projection that only
keeps `.summary` and `.review_sequence`; that drops
`agent_response_contract`, `review_groups`, `pull_requests[].review_template`,
and `pull_requests[].evidence_commands`, which are the fields that make the
command a guided review instead of a statistics table.

When `--state all` is used, the command must preserve both lifecycle groups.
The `--limit` value is applied per group so a busy open queue cannot consume the
whole packet and make `review_groups.merged` empty while merged PRs exist in the
window. The default is 100 PRs per selected group. Every packet carries
`result_completeness`; exhaustive requests must require `complete=true` and
rerun with its `recommended_limit` when the source scan or packet slice was
truncated. Live GitHub reads should fetch open and closed/merged windows
separately before constructing the grouped packet.

The agent response must not stop at a queue table. For `/loopx-pr-review`, the
queue is only the preface; the final answer should review selected PRs one by
one with five sections: `动机`, `改动思路`, `具体改动`, `对主干的风险`, and
`我的整体评价`. A stats/list-only response is valid only when the user
explicitly asks for stats or a list without review. When the visible message
starts with `/loopx-pr-review`, words such as `open`, `closed`, `merged`,
`today`, or a time window are filters on the review queue, not permission to
skip the review. Downgrade only for explicit opt-out phrases such as `只统计`,
`只列出`, `stats only`, `list only`, `不要 review`, or `不用分析`.

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
    "limit": 100,
    "state_filter": "all",
    "since": "2026-06-28T00:00:00Z",
    "window": {"state_filter": "all", "since": "2026-06-28T00:00:00Z"},
    "source": "github_cli",
    "privacy_mode": "public_safe_github_metadata",
    "dry_run": true
  },
  "result_completeness": {
    "schema_version": "pr_review_result_completeness_v0",
    "complete": true,
    "truncated": false,
    "limit": 100,
    "source_scan_complete": true,
    "recommended_limit": null,
    "rerun_cli_args": []
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
      "risk_hint_level": "low",
      "main_risk_level": "low",
      "why_now": "Open and awaiting reviewer decision."
    }
  ],
  "review_groups": {
    "unmerged": {
      "schema_version": "pr_review_group_v0",
      "group_id": "unmerged",
      "title": "Unmerged PRs",
      "intent": "Review before merge: decide approve, request changes, defer, or wait for checks.",
      "count": 3,
      "pr_numbers": [773, 775, 771],
      "review_sequence": []
    },
    "merged": {
      "schema_version": "pr_review_group_v0",
      "group_id": "merged",
      "title": "Merged PRs",
      "intent": "Post-merge audit: check outcome, regression risk, and follow-up quality without blocking already-merged work.",
      "count": 5,
      "pr_numbers": [770],
      "review_sequence": []
    }
  },
  "pull_requests": [
    {
      "number": 773,
      "head_oid": "0123456789abcdef0123456789abcdef01234567",
      "review_template": {
        "schema_version": "pr_review_five_block_template_v0",
        "purpose": "Empty scaffold only; agentloop fills it after reading PR body and diff.",
        "sections": [
          {
            "label": "动机",
            "word_hint": "200-350字",
            "content": "",
            "agent_instruction": "解释旧行为、具体痛点、受影响的用户或调用方、目标结果与必要性；说明不合并会继续付出什么代价，以及需求来自活跃调用方还是未来设想。"
          },
          {
            "label": "改动思路",
            "word_hint": "250-450字",
            "content": "",
            "agent_instruction": "解释所选架构、改动前后的控制流或数据流、所有权边界、关键不变量和替代方案取舍；为不熟悉子系统的读者给出一条正向运行链路。"
          },
          {
            "label": "具体改动",
            "word_hint": "300-600字",
            "content": "",
            "agent_instruction": "把关键文件和符号映射到行为，覆盖接口、配置或状态、兼容路径、测试与文档；说明各部分如何协作，并给出一个具体输入到输出的例子。"
          },
          {
            "label": "对主干的风险",
            "word_hint": "250-500字",
            "content": "",
            "agent_instruction": "按严重度列出有文件或符号证据的发现，评估爆炸半径、兼容性、权限、默认副作用、失败与回滚、可观测性和缺失覆盖；策略或生命周期改动必须解释一条负向链路。"
          },
          {
            "label": "我的整体评价",
            "word_hint": "150-300字",
            "content": "",
            "agent_instruction": "权衡价值与复杂度，列出实际检查或运行的验证，注明审阅的 head SHA，并给出精确结论；若阻塞，说明最小修复和复审所需证据。"
          }
        ],
        "review_order": ["docs/guides/newcomer-command-path.md", "docs/README.md"],
        "output_hint": "Write for a reader unfamiliar with the PR: explain context, architecture, implementation, validation, necessity, and risk with concrete evidence. Follow each section's range as a depth signal, not filler."
      },
      "motivation": "Adds a newcomer command path...",
      "scale": {"changed_files": 3, "additions": 90, "deletions": 4},
      "areas": {"public_docs": 3},
      "checks": {"summary": "2 successful check(s)."},
      "metadata_risk_hint": {
        "schema_version": "pr_metadata_risk_hint_v0",
        "level": "low",
        "basis": ["areas=公开文档 3", "scale=3 files +90/-4", "checks=2 pass"],
        "disclaimer": "Metadata-only hint for queue ordering; agentloop must read the PR diff before judging main risk."
      },
      "main_regression_analysis": {
        "schema_version": "main_regression_analysis_v0",
        "risk_level": "low",
        "risk_summary": "低 main regression risk across 公开文档 3; 3 file(s), +90/-4; checks=2 pass.",
        "potential_regressions": [
          "Runtime regression risk is low, but public guidance or smoke expectations can drift from shipped behavior."
        ],
        "bug_risks": [
          "Docs-only or smoke-only changes can bless stale contracts if examples no longer match the real command path."
        ],
        "verification_focus": [
          "Run `git diff --check` and the touched smoke; compare command examples with current CLI help when syntax is involved."
        ],
        "post_merge_review": false
      },
      "risk_notes": [],
      "evidence_commands": [
        "gh pr view 773 --json title,body,files,commits,statusCheckRollup,headRefOid,updatedAt",
        "gh pr diff 773 --name-only",
        "gh pr diff 773 --patch",
        "gh pr view 773 --json headRefOid,updatedAt"
      ]
    }
  ],
  "agent_response_contract": {
    "schema_version": "pr_review_agent_response_contract_v0",
    "table_only_response_allowed": false,
    "slash_prefix_dominates_intent": true,
    "stats_only_requires_explicit_opt_out": true,
    "queue_table_role": "preface_only",
    "required_packet_fields_to_preserve": [
      "agent_response_contract",
      "review_groups",
      "pull_requests[].review_template",
      "pull_requests[].evidence_commands"
    ],
    "required_final_sections": [
      "动机",
      "改动思路",
      "具体改动",
      "对主干的风险",
      "我的整体评价"
    ],
    "explanation_depth_contract": {
      "schema_version": "pr_review_explanation_depth_v0",
      "reader_profile": "A technically curious reader who may not know this PR or subsystem.",
      "evidence_layers": ["problem", "architecture", "implementation", "validation"],
      "freshness": "Record and recheck the remote head SHA before the verdict."
    }
  },
  "boundary": {
    "raw_logs_recorded": false,
    "credential_values_recorded": false,
    "absolute_paths_recorded": false
  }
}
```

## Review Flow

The packet should let a reviewer move through PRs in order:

1. Start from `review_groups.unmerged` for PRs that can still affect merge
   decisions.
2. Then use `review_groups.merged` for post-merge audit and follow-up quality.
3. Use `evidence_commands`, key files, changed-file scale, and checks to open
   the actual PR body and diff.
4. Read `main_regression_analysis` before filling risk prose. It is the CLI's
   concrete, generated view of potential main regressions, bug risks, and
   focused validation.
5. Follow `agent_response_contract.explanation_depth_contract`, then let
   agentloop fill the blank five-block template:
   `动机`, `改动思路`, `具体改动`, `对主干的风险`, `我的整体评价`.
   Use each section's range as a depth signal for a reader unfamiliar with the
   subsystem, not as filler.
6. Treat `metadata_risk_hint` only as queue-ordering metadata. It must not be
   copied as the final risk judgement.
7. Decide `approve`, `request changes`, `defer`, or `merge after checks`.

A response that only lists `Open` and `Merged` PRs, scale, and recommended next
order is incomplete for `/loopx-pr-review`; it should continue into the
per-PR five-block review cards after reading evidence.

Similarly, a response that says it ran `loopx pr-review` but used a command like
`loopx --format json pr-review ... | jq '.summary, .review_sequence'` is still
incomplete: the tool call happened, but the contract/template fields were
discarded before the agent planned its answer.

## Acceptance Checks

A first implementation is acceptable when:

- `loopx slash-commands` exposes `/loopx-pr-review`;
- `loopx pr-review` returns `loopx_pr_review_command_response_v0`;
- default live reads use the caller's current `gh` repository, while
  `--repo owner/repo` can review another GitHub project;
- `--state all` includes merged PRs in the same packet, applies `--limit` per
  lifecycle group, and keeps `review_groups.merged` non-empty when merged PRs
  exist in the requested window; `--state open` preserves the old open-only
  review queue;
- the default limit is 100, and exhaustive requests only proceed when
  `result_completeness.complete=true`; truncated packets provide a larger
  `recommended_limit` for the next read;
- `--since` can bound an overnight or release-window review without relying on
  private chat memory;
- the response includes review sequence, changed-file scope, status checks,
  key files, risk notes, metadata-only risk hints, concrete
  `main_regression_analysis`, evidence commands, explicit
  `review_groups.unmerged` / `review_groups.merged`, and a blank five-block
  review template;
- the packet includes `agent_response_contract.table_only_response_allowed=false`
  and `agent_response_contract.required_packet_fields_to_preserve` so
  slash-command agents know a table-only chat answer is incomplete;
- the slash-command catalog marks `/loopx-pr-review` as `must_run_cli_first`
  and `slash_prefix_dominates_intent`, and says manual `gh` calls are only
  per-PR deep-read commands after the CLI packet selects a PR;
- each PR includes `review_template.sections` for `动机`, `改动思路`,
  `具体改动`, `对主干的风险`, and `我的整体评价`;
- each review template section carries a section-specific depth range, and the
  packet's explanation-depth contract requires problem, architecture,
  implementation, validation, necessity, and risk evidence instead of a generic
  long answer;
- live packets expose and recheck `headRefOid` so a review verdict is bound to
  the remote revision actually inspected;
- template sections must leave `content` empty so agentloop reads the real PR
  before writing the review;
- `metadata_risk_hint` must be repository-generic and must not special-case
  LoopX files or domains;
- `main_regression_analysis` must be repository-generic, must include
  `potential_regressions`, `bug_risks`, and `verification_focus`, and must not
  be replaced by a blank template;
- live GitHub reads and fixture-based smokes share the same schema;
- no raw logs, private payloads, credentials, local paths, or private source
  bodies are recorded.
