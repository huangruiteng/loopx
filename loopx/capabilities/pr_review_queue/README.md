# Pull Request Review

The `pull-request-review` capability helps a user review open and recently
merged pull requests one by one by turning public GitHub PR metadata into a
guided review queue. Its command packet remains versioned as
`pr_review_command_v0` and is exposed through `/loopx-pr-review` and
`loopx pr-review`.

The reviewed repository is the caller's current GitHub project by default, as
resolved by `gh`, or the explicit `--repo owner/repo` target. LoopX's own
repository may be used for dogfood and public fixtures, but the command is not
LoopX-repo-specific.

The default command is read-only. An explicit `--observation-state-file`
writes only its local public-safe checkpoint. Neither mode approves reviews,
posts PR comments, merges, pushes, spends LoopX quota, or completes LoopX todos.

The built-in `pull-request-review` capability adds an optional autonomous
observation to this same command. It reuses the existing GitHub scan and
normalized review queue; it does not introduce a second crawler or a new write
authority.

The capability also owns the review-depth contract. The shared
`agent_response_contract.review_execution_contract` defines required evidence,
completion, freshness, finding, and verdict rules. Each PR carries a compact
`review_plan` that binds those rules to one exact head and marks code-symbol and
negative-walkthrough applicability. Host skills route and publish this packet;
they must not maintain a second explanation checklist.

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

For an autonomous maintainer monitor, request the complete open queue while
persisting its compact cursor in an ignored local checkpoint:

```bash
loopx --format json pr-review --repo owner/repo --state open \
  --autonomous-observation \
  --observation-state-file .local/pr-review-monitor.json
```

The same command reuses that checkpoint on later Codex tasks. Its atomic local
write grants no GitHub, Todo, push, or merge authority.
`--previous-observation-json` remains available for stateless callers and is
mutually exclusive with `--observation-state-file`:

```bash
loopx --format json pr-review --repo owner/repo --state open \
  --autonomous-observation \
  --previous-observation-json previous.json
```

After the selected candidate has been durably materialized as a Todo,
acknowledge that projection explicitly:

```bash
loopx --format json pr-review --repo owner/repo --state open \
  --autonomous-observation \
  --observation-state-file .local/pr-review-monitor.json \
  --projected-exact-head 2768@0123456789abcdef0123456789abcdef01234567
```

Supply `--projected-exact-head` only after the candidate's exact target key has
been durably materialized as a Todo. Candidate emission is a preview, not a
projection acknowledgement. Without that explicit ACK, repeated complete polls
replay the same candidate so a failed or interrupted Todo write cannot strand
the PR. The option is repeatable and may only acknowledge the prior candidate
or an already persisted projection cursor.

After the selected candidate has an externally verifiable review or
merge-readiness result at that exact head, advance the queue with an explicit
handled cursor:

```bash
loopx --format json pr-review --repo owner/repo --state open \
  --autonomous-observation \
  --observation-state-file .local/pr-review-monitor.json \
  --handled-exact-head 2768@0123456789abcdef0123456789abcdef01234567
```

`--handled-exact-head` is repeatable and uses `NUMBER@HEAD_OID`. The observation
persists these public-safe cursors in `handled_exact_heads`. Candidate emission
alone is not a completion receipt: callers must add the cursor only after
review-result readback proves that exact head was handled. A newly supplied
cursor must match the prior packet's candidate or one of its
`projected_candidate_exact_heads`; a caller cannot skip an unselected PR by
naming it handled. A new head is a new candidate even when the prior head was
handled.

`pending_candidate_exact_head` preserves the last selected but unhandled exact
head across unchanged and incomplete polls. It is a scheduling cursor only;
callers still deduplicate Todo creation by exact target key and must not treat
the cursor as evidence that a review happened.

`projected_candidate_exact_heads` persists every candidate whose durable Todo
projection has been explicitly acknowledged but not yet completed. An unchanged
poll skips those acknowledged exact heads and selects the next unprojected,
unhandled PR in the age-fair review sequence. Legacy v0 observations treated
emission as projection; v1 deliberately replays their candidates so stale
emission cursors cannot strand unreviewed PRs. Todo target-key deduplication
keeps this recovery idempotent.
When every actionable PR has already been projected, `candidate` is `None` and
`pending_candidate_exact_head` remains the last pending cursor. A material
transition on an already projected exact head still re-selects that head.

`review_backlog` gives the monitor a compact workload cadence hint. It counts
open, non-draft PRs whose exact head is actionable and not yet recorded in
`handled_exact_heads`, and returns `recommended_poll_interval_minutes`. While at
least one unhandled PR remains, the recommendation is `3`; once the actionable
backlog is empty, it drops to `15`. The hint is scheduling evidence only: it
does not grant Todo, review, comment, or merge authority, and callers still
advance the queue with an explicit handled cursor after exact-head review
readback.

`pull_request_review_queue_observation_v1` has exactly three observation
states:

- `not_observed`: the source or packet slice was incomplete. Preserve the
  previous baseline and do not claim the queue is unchanged.
- `observed_unchanged`: a complete observation has the same queue fingerprint.
  An unacknowledged packet candidate is replayed. After the caller supplies its
  projection ACK, the packet selects the next unprojected, unhandled backlog PR
  so the queue keeps rotating. An acknowledged unhandled candidate remains in
  `projected_candidate_exact_heads` until the caller supplies its completion
  cursor.
- `material_transition`: a complete observation changed an exact head, review
  conclusion, check state, draft state, mergeability, or open-queue membership.
  A new head following `REQUEST_CHANGES` may use one fast-feedback slot;
  check-only activity does not preempt older review-ready work.

The repository-scoped fingerprint contains only compact public PR metadata.
Persisted `items` carry the PR number, fingerprint, exact head, decision, and
next action; they never carry review bodies. One community response head after
`REQUEST_CHANGES` may take the fast-feedback lane, then community work is
oldest-first by the current head's `review_ready_at`. Author-owned fallback
reviews follow community work, with 24-hour and 48-hour aging lanes preventing
starvation. `updatedAt` does not define readiness because comments and checks
must not make old code look new. Projected candidates remain skipped until
handled or their exact head materially changes.
It emits a
`pull_request_review_todo_preview_v0` bound to its exact head. The preview may
route to initial review, re-review after changes, or merge-readiness
qualification. It grants no Todo write, GitHub review/comment, push, or merge
authority; callers must use normal LoopX Todo authority, `loopx-pr-review`, and
`loopx-pr-merge` policy for those actions.

Do not pipe that first packet through `jq` or another projection that only
keeps `.summary` and `.review_sequence`; that drops
`agent_response_contract`, `review_groups`, `pull_requests[].review_template`,
`pull_requests[].review_plan`, and `pull_requests[].evidence_commands`, which
are the fields that make the command a guided review instead of a statistics
table.

## Capability-Owned Review Execution

`pull_request_review_execution_contract_v2` is shared once per packet to avoid
duplicating a large prompt for every PR in a 100-item queue. It requires these
typed evidence groups before a verdict:

- problem context and active caller;
- architecture and ownership flow;
- repository reuse for behavior-bearing changes: search base and exact-head
  code, including unchanged siblings, by caller outcome/resource rather than
  only new filenames. Record revisions, queries, paths and candidate callers;
  compare scope/filters, ordering/paging, authority/sanitization and state/retry
  ownership. Prefer the nearest existing owner; justify independent boundaries
  with evidence, not green CI or conflict-free coexistence. For alternative
  views of one resource, validate consumer switching and concurrent updates
  where relevant. Repeat the comparison after base integration or head changes;
- caller-observable semantic parity for every behavior-bearing change, whether
  or not its title says refactor or migration. Inventory legacy caller branches,
  then run the same synthetic fixture through the public entrypoint and affected
  backend at an immutable baseline and the exact head. Record replayable
  commands, revisions, fixture and observation fingerprints, exit status, full
  diagnostics, persisted readback, authority/effect outcomes, and only the
  normalization rules needed for documented nondeterminism. The sensitivity
  case must make the real path fail on the historical defect or a deliberate
  dropped-field/detail or stronger-precondition mutation, then pass at the fixed
  head. New-rule provider conformance and prose-only claims do not establish
  before/after compatibility;
- exact changed-line classification across production, tests/fixtures, docs,
  generated output, and mechanical moves;
- a 2-5 item exact-head symbol map for code-changing PRs, including caller,
  state, branch, side effect, consumer, and failure ownership;
- positive and applicable negative execution walkthroughs;
- validation tied to changed invariants and failure cases;
- strongest regression path, blast radius, recovery, minimum repair, and
  regression test;
- code-volume necessity and the highest-value behavior-preserving
  simplification;
- change proportionality: compare the verified frequency, severity, blast
  radius, and recovery cost of the original problem with the production
  mechanism, new state/contracts/CLI/callers, migration, and long-term
  maintenance surface. Correctness, green CI, and resolution of earlier
  findings do not override a `disproportionate` or `not_yet_proven` blocker;
- default-off isolation: for an opt-in change, trace every shared schema,
  prompt, accepted-input, projection, scheduling, and effect surface. Include
  installed or automatically loaded skills, agent instructions, prompt
  templates, help, schemas, install bundles, and provider setup guidance:
  runtime `default=false` is insufficient when one of those baseline surfaces
  already changes model or user behavior. Separate availability signals such
  as installation, discovery, provider readiness, accepted input, and resolver
  success from activation authority. For scoped capabilities, prove that the
  intended scope and every required subject are enabled before projecting
  capability-specific guidance or effects, then run a paired counterfactual
  proving that disabled behavior still matches the pre-change contract;
- authority semantics: make public protocol ids and symbols match the real
  actor lifecycle and authority, distinguishing ephemeral sub-agents from
  registered peers and durable multi-agent coordination.

Every materially expanded re-review resets proportionality from the original
problem and evaluates the full exact head. Reviewer-requested additions are not
progress toward approval by themselves; the reviewer should request the
smallest viable fix, deletion, split, or hold when the benefit does not justify
the accumulated mechanism.

The per-PR `pull_request_review_plan_v1` records the exact target, applicability,
required evidence ids, and an initially `unverified`
`pull_request_review_result_v1` skeleton. Metadata, labels, file counts, risk
hints, and green CI cannot upgrade evidence to `verified`. A stale-head verdict
is prohibited. Missing evidence remains `unverified` with a reason instead of
being replaced by confident prose.

`repository_reuse` starts unverified in every applicable plan. Its conclusions
are `reused`, `separation_justified`, `no_existing_candidate`,
`unjustified_duplication`, or `not_yet_proven`. A negative search must name its
scope and limitations; an empty candidate list is not proof of absence.
Unjustified duplication or missing evidence requires a request-changes
conclusion. Similar-looking code with distinct invariants or compatibility
needs may legitimately remain separate. Ordinary docs retain their existing
review path; smoke-only changes retain `durable_smoke_value` coverage review.
This is a reviewer-executed contract projected by the packet, not an automatic
repository search or a semantic validator of published prose. Tests establish
packet applicability and verdict policy, not guaranteed model compliance.

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

The published review is a full-PR bilingual review: one complete Chinese
five-block review covering every changed surface, key symbol, positive and
negative path, and validation, plus one concise English machine verdict
(`APPROVE`, `REQUEST_CHANGES`, or the author-owned `COMMENTED` fallback). The
Chinese review carries the depth and evidence; the English verdict carries the
machine-readable state and validation summary. A findings-only or blocker-only
body is not a complete PR review.

Each complete PR review must also include whole-PR interpretation depth:
per-file responsibility mapping, 2-5 key symbol explanations with exact-head
references, one positive runtime walkthrough, one negative/fail-closed
walkthrough, per-surface validation, and an overall judgment for the entire PR.

## Source Reads

Implementations may read compact public PR surfaces:

- pull request title, number, URL, branch, author, lifecycle state, merge time,
  and review decision;
- PR body summary;
- changed-file list and diff scale;
- status-check rollup;
- merge-state metadata;
- current-head commit timestamps and review metadata used to derive
  `review_ready_at` and validate a standalone exact-head conclusion.

Raw review bodies are used only for the format/exact-head decision and are not
returned or persisted. A valid latest conclusion names the exact head, contains
all five Chinese sections plus a line-starting `English verdict: APPROVE` or
`English verdict: REQUEST_CHANGES`, and keeps that verdict aligned with formal
`APPROVED`/`CHANGES_REQUESTED` state. Because GitHub blocks every self-review
state transition, author-owned conclusions use `COMMENTED` plus one exact title:
`Approval conclusion (author-owned PR; GitHub blocks formal self-approval)` or
`Request changes conclusion (author-owned PR; GitHub blocks formal self-review)`.
The compact result is versioned as `pull_request_review_conclusion_v0` and
reports typed invalid-reason codes.

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
      "agent_response_contract.review_execution_contract",
      "result_completeness",
      "review_groups",
      "pull_requests[].review_plan",
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
4. Execute the PR's `review_plan` against
   `agent_response_contract.review_execution_contract`; keep unavailable
   evidence explicitly unverified.
5. Read `main_regression_analysis` before filling risk prose. It is the CLI's
   concrete, generated view of potential main regressions, bug risks, and
   focused validation.
6. Render the verified structured result through the blank five-block template:
   `动机`, `改动思路`, `具体改动`, `对主干的风险`, `我的整体评价`.
   Use each section's range as a depth signal for a reader unfamiliar with the
   subsystem, not as filler.
7. Treat `metadata_risk_hint` only as queue-ordering metadata. It must not be
   copied as the final risk judgement.
8. Recheck the exact head, then decide `approve`, `request changes`, `defer`, or
   `merge after checks`.

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
- the shared `pull_request_review_execution_contract_v2` owns typed evidence,
  completion, freshness, findings-first, and verdict policy, while every PR has
  a compact exact-head `pull_request_review_plan_v1` with an unverified result
  skeleton;
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
- autonomous packets order community work by current-head `review_ready_at`,
  bound response preemption to one slot, age author-owned fallbacks, and ignore
  check-only activity for priority;
- `--observation-state-file` atomically carries observation and handled cursors
  across Codex tasks without returning a local path or granting external writes;
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
