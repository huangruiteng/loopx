# CI Impact Selection / CI 影响范围选择

## Current rollout: shadow, not selective merge authority

The PR workflow retains its full core qualification for every executable,
policy, runtime-prompt or unknown change. The existing documentation-only
exemption is unchanged. `scripts/ci/impact_plan.py` now also proposes a bounded
candidate test profile and explains why it was selected. A candidate never
authorizes skipping the full suite in this rollout.

当前先交付 **shadow 对照阶段**：不是用一次绿灯就宣布可以安全跳过全量。
原有文档豁免不变，代码和未知改动仍跑全量；额外实际运行候选集合、比较测试身份
和结果、记录耗时。此阶段增加少量并行工作，尚不承诺降低 PR 的总体耗时。

```text
merge-base … exact PR head
  → NUL-delimited Git changes (renames appear as deletion + addition)
  → candidate + reason + immutable revisions
      ├── existing full qualification + full coverage
      └── selected Python tests + real CLI smokes (shadow only)
             ↓
       compare exact collected test identities and outcomes
             ↓
       stable merge-gate: full success AND required shadow success
```

## First reviewed boundary: vision checkpoint

The initial `vision` profile recognizes exact existing source/test/smoke paths,
not filenames containing “vision”. Its Python inventory spans checkpoint
authoring, readback, refresh recovery/isolation, public safety, replan admission,
terminal succession, quota and settlement. Real CLI smokes exercise bounded
write/read behavior, closed-vision successor routing and status/quota latency.
Full TS tests/typechecking and CLI output-budget qualification remain common
checks; they are not duplicated into another test framework.

This is the cross-domain behavior demonstrated by the vision authoring-budget
change, not a claim that every goal-domain edit can use the same slice. A new
profile needs its own reviewed owning boundary and caller inventory.

首批只选择边界明确的 vision checkpoint。它的消费者横跨 refresh、quota、终态与
结算，所以不能只跑同目录测试。测试目标复用仓库已有测试和 smoke；canary 的风险
目录可辅助维护清单，但自由文本关键词匹配、`max_checks` 截断不能作为 CI 免责依据。

| Change | Candidate / execution |
| --- | --- |
| Allowlisted Markdown only | `docs`; existing explicit core skips |
| Only recognized vision boundary paths | `vision`; full suite plus shadow |
| Known new test within that complete inventory | `vision`; that test is included |
| Runtime additions/deletions, renames, type changes | `full` |
| Shared decoder/dispatcher/schema, dependencies, fixtures outside the inventory | `full` |
| CI policy/workflow changes | `full` plus candidate rehearsal |
| Empty diff, non-PR execution or any unmapped path | `full` |
| Missing Git base or malformed input | Classification fails; no successful exemption |

Both sides of renames count. A mixed PR takes the conservative union: one
unmapped code path makes the whole candidate full. Noncanonical paths and
unrecognized Git statuses cannot become documentation exemptions. GitHub
outputs contain only closed profile names and booleans, never changed filenames
or shell commands supplied by a PR.

## Evidence and gate semantics

Each workflow run publishes:

- `ci-impact-plan`: base/head/merge-base/tested-checkout revisions, changed
  paths, complete selected inventory, reason and actual execution mode.
- `ci-impact-selected` when applicable: JUnit outcomes and a bounded execution
  receipt with command exit codes, elapsed seconds and a digest of the plan.
- `python-junit-1` and `python-junit-2`: full-shard outcomes.
- `ci-impact-comparison` when applicable: selected/full counts, missing cases,
  outcome differences and failures outside the selected set. It does not copy
  failure text, stdout or private runtime evidence into its summary.

The runner rejects stale checkout identities, changed inventories, missing
checks and attempts to reinterpret shadow as selective authority. The audit
requires both full reports, unique test identities, nonempty collection from
every selected file, successful selected tests (a skip is not a pass), matching
full outcomes, successful CLI smokes and no failure outside the selected set.
Any failed/cancelled/missing required job keeps the stable `merge-gate` red.

Coverage remains unambiguous: only the two **full** Python shards feed the
existing coverage floor and Sonar report. Shadow runs neither upload partial
coverage under full-suite artifact names nor borrow coverage from another SHA.
Plan/rehearsal artifacts are diagnostics, not a replacement for full coverage.

覆盖率仍由同一版本的两个全量分片产生；精简集合的“绿”不能冒充完整覆盖率，
也不能用旧版本 coverage 补齐。shadow 通过只证明本次实际执行与对照成立，不证明
未来永远不会漏测。缺失、跳过、取消、结果不一致都必须明确失败，不能转成免责。

## Qualify locally

```bash
python -m unittest discover -s scripts/ci -p 'test_*.py'
python scripts/ci/review_gate.py classify --base origin/main --head HEAD --plan impact-plan.json
python scripts/ci/impact_shadow.py run --plan impact-plan.json
python scripts/ci/impact_shadow.py audit --plan impact-plan.json --full-dir full-reports
```

Run the selected commands only for plans with `shadow_profile=vision`. Install
the repository test dependencies and supported Node runtime first. The audit
expects `full-reports/python-junit-{1,2}/junit.xml` downloaded from the same
workflow run; missing reports are not a local pass. Keep generated plans,
JUnit files and receipts outside tracked source files.

## Activation and expansion criteria

Before a follow-up enables selective-only PR execution for a profile:

1. Review successful shadow evidence across representative changes to its write
   rule, read projection and cross-domain semantics, not just a constant edit.
2. Prove sensitivity with deliberately omitted checks, changed outcomes and
   real-entrypoint semantic regressions. Investigate failures outside the
   candidate instead of mechanically accepting the observed selection.
3. Run both old/full and proposed selective workflow paths, including docs,
   mixed changes, missing reports, renamed/deleted tests and merge aggregation.
4. Bind execution to the exact plan/checkout; evaluate exemption rules from a
   trusted base policy. A PR that changes the selector or its test inventory
   must qualify fully and cannot approve its own narrower exemption.
5. Preserve full qualification on main and existing full-public nightly/release
   sweeps. Keep a force-full escape hatch; paid model behavior tests remain
   explicitly activated release/manual work, not ordinary PR discovery.

Then expand one proven domain at a time. UI, installer, provider and scheduler
changes still require full qualification here. In particular, provider changes
retain their real-backend requirements; this planner never waives PostgreSQL
qualification or other authority-boundary evidence.

下一阶段先依据证据启用一个范围，再扩展到 UI、安装器等领域；不预先添加尚未验证
的免责。未知仍全量、selector 自身变更仍全量、主干与低频全量兜底保留。付费模型
测试的触发频率不变，本功能也不修改 LoopX Goal、Todo、runtime 或 automation。
