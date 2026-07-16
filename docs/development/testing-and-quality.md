# Testing And Quality / 测试与质量体系

LoopX coordinates long-running agents, so a change can be locally correct yet
still alter which work an agent selects, whether it asks a user, or whether a
host keeps running. The quality system therefore tests one shipped behavior at
several distances. Fast deterministic checks protect pull requests; broader
and more expensive checks run only when their signal justifies the cost.

LoopX 协调长程 agent。一个局部正确的改动，仍可能改变 agent 选择哪项工作、是否
向用户提问，或 host 是否继续运行。因此质量体系从不同距离验证同一套已交付行为：
快速、确定性的检查保护每个 PR；更广、更昂贵的检查只在信号值得成本时运行。

## Quality Layers / 质量分层

| Layer / 层 | What it proves / 证明什么 | Normal cadence / 常规频率 |
| --- | --- | --- |
| Unit and contract tests / 单元与合同测试 | Pure rules, schemas, transition tables, invalid-state rejection / 纯规则、schema、状态转换和非法状态拒绝 | Every relevant PR in `python-tests.yml` / 相关 PR 必跑 |
| Durable public smokes / 稳定公开 smoke | Shipped CLI and cross-module behavior through public-safe fixtures / CLI 与跨模块交付行为 | Focused locally; full-public on `main`, daily, or manual / 本地聚焦；主干、每日或手动全量 |
| Catalog-informed canary / Catalog 驱动 canary | The smallest risk-based slice spanning every changed public surface / 覆盖所有变更面的最小风险切片 | Before sensitive merge or release / 敏感合并与发布前 |
| CLI output budgets / CLI 输出预算 | Agent-facing output stays bounded and base-to-head growth is visible / 输出有界且能发现相对增长 | Relevant PR CI and premerge / 相关 PR CI 与 premerge |
| Public-safe decision replay / 公开安全决策回放 | Reviewed source-state invariants replay through the real quota-to-scheduler path / 经审阅的源状态不变量重放真实 quota-to-scheduler 链路 | Regression and control-plane changes / 回归与控制面变更 |
| Model-behavior qualification / 模型行为验证 | A real model correctly interprets the actual default packet and safety contract / 真实模型能正确理解当前默认载荷与安全合同 | Low-frequency local/manual shadow gate / 低频本地或手动影子门 |
| Release outcome baseline / 发布结果基线 | Stable release and candidate outcomes are comparable under matched semantics / 稳定版与候选版在匹配语义下可比较 | Release qualification or scheduled observation / 发布验证或周期观察 |

These layers are complementary. A model pass cannot override a deterministic
contract failure, and a large smoke sweep cannot replace a focused regression
that names the broken rule.

这些层次互补：模型通过不能覆盖确定性合同失败；大规模 smoke 也不能代替明确指出
错误规则的聚焦回归测试。

## Pull-Request Baseline / PR 基线

Install the test dependencies once:

```bash
python -m pip install -e ".[test]"
```

Run the fast repository gate:

```bash
python -m ruff check tests loopx/canary loopx/control_plane loopx/domain_packs loopx/presentation
python -m mypy
python examples/control_plane/cli-output-budget-regression-smoke.py
python -m pytest -q
git diff --check
```

`.github/workflows/python-tests.yml` runs this fast lane for relevant Python
pull requests. It intentionally excludes provider-backed evaluation and the
full smoke catalog, so ordinary iteration does not depend on credentials,
network latency, provider availability, or a two-hour matrix.

`.github/workflows/python-tests.yml` 会在相关 Python PR 上运行这条快速通道。
它刻意不包含真实模型调用和 full smoke catalog，因此普通迭代不依赖凭证、网络
时延、模型服务可用性或两小时级测试矩阵。

## Smokes And Canary / Smoke 与 Canary

A durable smoke should protect shipped behavior, a reusable contract, a
public/private boundary, or a regression that previously stranded automation.
It should not preserve dated research prose or raw execution evidence.

Durable smoke 应保护已交付行为、可复用合同、公开/私有边界，或曾让自动化卡死的
回归；不应固化某次研究文案或原始执行证据。

Run one focused smoke while developing, then let the canary planner select the
smallest cross-surface set from the Git diff:

```bash
python examples/control_plane/interaction-scheduler-authority-smoke.py
loopx canary premerge --from-git-diff
```

The complete public sweep remains explicit and bounded:

```bash
loopx canary smoke-suite --suite full-public --jobs 4 --timeout-seconds 120
```

`full-public-smokes.yml` runs on `main`, daily, and by manual dispatch. It is
not a required PR check. This separation protects repository quality without
making every small patch wait for the broadest suite.

`full-public-smokes.yml` 在主干、每日定时和手动触发时运行，不是 PR 必须门禁。
这种分层既保护质量，也避免每个小 patch 都等待最宽测试集。

## Agent-Facing Output Budgets / Agent 输出预算

The interface budget gate measures stable command scenarios and compares the
candidate checkout with its base. It catches accidental payload growth,
duplicated diagnostics, and hot-path fields that silently return after a
refactor. Budget changes are contract changes: update the implementation and
the expectation together, explain every added or removed semantic field, and
request owner review when the default agent-facing projection changes.

接口预算门会测量稳定命令场景，并比较 candidate 与 base，捕获意外膨胀、重复诊断
以及重构后悄悄回到热路径的字段。预算变化就是合同变化：实现与期望必须一起修改，
逐项解释新增或删除的语义字段；默认 agent-facing 投影变化时需要 owner review。

The full diagnostic packet remains an explicit drill-down surface. Moving a
field off the default path is acceptable only when the default still tells the
agent what to do and how to request the omitted detail.

完整诊断包保留为显式 drill-down。只有默认路径仍能告诉 agent 下一步做什么、以及
如何请求被省略细节时，字段才能移出默认热路径。

## Decision Replay And Issue #2191 / 决策回放与 #2191

Issue #2191 is the reference pattern for a cross-layer control-plane
regression. The final `interaction_contract` is scheduler authority; raw
`should_run` and lower-level compatibility fields may not override it. A
non-blocking `user_action` also cannot satisfy an agent todo's blocking
`required_decision_scopes`.

Issue #2191 是跨层控制面回归的参考模式：最终 `interaction_contract` 是调度权威，
原始 `should_run` 和底层兼容字段不能越权；非阻塞 `user_action` 也不能满足 agent
todo 的阻塞 `required_decision_scopes`。

The regression is protected at four deterministic levels:

1. a data-driven scheduler decision table checks human gate, active work,
   repair, mapped no-op, and successor-replan cases;
2. todo-scope tests distinguish a compatible blocking gate from a notice, an
   unrelated agent gate, and a dangling scope;
3. the real quota builder must turn a scope collision into bounded
   control-plane self-repair while disabling normal delivery;
4. a public-safe fixture stores source todo facts plus an independently reviewed
   invariant and expected outcome; the replay smoke and catalog canary rerun the
   real quota-to-scheduler path without raw state, logs, prompts, trajectories,
   or local paths.

该回归由四层确定性测试保护：数据驱动调度决策表；todo scope 所有权测试；真实 quota
builder 的 fail-closed 集成测试；以及从源 todo 事实重新执行真实链路、再与独立审阅
不变量比对的公开安全回放与 catalog canary。

The expected replay outcome must never be generated by the implementation under
test. Reducer shape checks remain useful for redaction and compatibility, but
they are separate from the semantic oracle. Metamorphic cases also assert that
adding an unrelated agent gate or mutating lower-level compatibility fields
cannot change the current agent's final decision.

回放期望值绝不能由被测实现生成。Reducer shape 测试仍可验证脱敏和兼容性，但必须
与语义 oracle 分开；变形测试还会验证，新增其他 agent 的无关 gate 或修改底层兼容
字段，都不能改变当前 agent 的最终决策。

The narrow mutation check deliberately flips lower-level signals and proves
they cannot preempt a final human gate. This is stronger than asserting one
expected JSON snapshot because it exercises the precedence rule directly.

窄 mutation 检查会主动翻转底层信号，证明它们不能抢占最终 human gate。这比只比对
一份 JSON snapshot 更强，因为它直接验证优先级规则。

## Doubao Model-Behavior Gate / Doubao 模型行为门

The provider-neutral behavior contract and optional Doubao 2.1 actor live in
`loopx.control_plane.testing`. The regular onboarding profile is one-arm: it
tests the actual default packet from the candidate checkout. When the product
default changes, implementation and qualification input change together; no
retired second product path is kept as a permanent baseline.

provider-neutral 行为合同和可选 Doubao 2.1 actor 位于
`loopx.control_plane.testing`。常规 onboarding profile 是 one-arm：直接测试
candidate checkout 的当前默认载荷。产品默认行为变化时，实现与验证输入一起切换，
不会长期保留一条退休产品路径作为第二臂。

Use this gate for semantic risks that deterministic tests cannot fully answer,
such as whether the model identifies the selected todo, respects a human gate,
continues after a healthy onboarding transition, or repairs a known projection
gap. Keep scheduler precedence, schema validity, cold-path restoration, and
field presence in deterministic tests.

它适合验证模型是否识别 selected todo、尊重人类门禁、在健康 onboarding transition
后继续、或识别已知 projection gap。调度优先级、schema、冷路径恢复和字段存在性仍
由确定性测试负责。

Live Doubao calls are a low-frequency local/manual gate, not ordinary CI.
`ARK_API_KEY` is injected only through the process environment. Packets,
prompts, raw responses, credentials, and conversations are never durable
repository evidence; only bounded receipts and mismatch codes may be retained.
There is currently no required public live-provider CLI for contributors. See
[Model behavior qualification v0](../reference/protocols/model-behavior-qualification-v0.md)
for the actor and promotion contract.

真实 Doubao 调用是低频本地/手动门，不进入普通 CI。`ARK_API_KEY` 只通过进程环境
注入；packet、prompt、原始响应、凭证和对话都不能成为仓库证据，只保留有界 receipt
与 mismatch code。普通贡献者当前不需要一个公开的 live-provider CLI。

## Release Outcome Baseline / 发布结果基线

Deterministic and model-behavior gates qualify a control-plane contract; they
do not prove that a release improves long-running outcomes. Outcome claims use
a small stable-release-versus-candidate manifest with matched task semantics,
runner protocol, model, reasoning level, timeout, and repetitions. A mismatch
or incomplete arm fails closed and cannot automatically promote a release.

确定性测试和模型行为测试验证控制面合同，但不能证明发布提升了长程结果。结果声明
必须使用小规模 stable-release-vs-candidate manifest，并匹配任务语义、runner、模型、
reasoning、timeout 与重复次数。任一不匹配或不完整都 fail closed，且不能自动发布。

See [Release outcome baseline v0](../reference/protocols/release-outcome-baseline-v0.md)
and [Release readiness](../product/release-readiness.md).

## Risk-Based Review / 按风险审阅

| Change / 变更 | Minimum gate / 最小门禁 |
| --- | --- |
| Docs or copy only / 仅文档 | Link and boundary check, focused doc smoke, `git diff --check` |
| Pure rule or schema / 纯规则或 schema | Unit table plus focused smoke |
| Scheduler, quota, todo, gate, onboarding / 调度与接入 | Unit table, real integration, replay, catalog canary, owner review |
| Default agent-facing output / 默认 agent 输出 | Above plus CLI base/head budget and semantic field ledger |
| Provider-backed behavior / 真实模型行为 | Deterministic gates first, then repeated one-arm local shadow receipts |
| Release promotion or outcome claim / 发布晋级 | Relevant canary, release checks, matched outcome baseline, explicit owner decision |

Sensitive behavior changes should remain easy to review: state the authority
rule, list fields added or removed, name the exact deterministic and model
behaviors checked, report skips, and keep automatic promotion disabled unless
the release contract explicitly permits it.

敏感行为变更应便于审阅：说明权威规则，逐项列出字段变化，写清验证过的确定性与模型
行为，报告跳过项；除非发布合同明确允许，否则保持自动晋级关闭。

## Evidence Boundary / 证据边界

Before opening a pull request, scan only candidate public paths:

```bash
loopx check \
  --scan-path CONTRIBUTING.md \
  --scan-path docs/development/ \
  --scan-path loopx/control_plane/ \
  --scan-path tests/ \
  --scan-path examples/
```

Never commit credentials, private state, raw benchmark material, model
responses, local absolute paths, or generated run logs. Prefer compact fixture
ids, reason codes, digests, and public-safe semantic projections.

禁止提交凭证、私有状态、原始 benchmark 材料、模型响应、本地绝对路径或生成日志。
优先保留紧凑 fixture id、reason code、digest 和公开安全语义投影。
