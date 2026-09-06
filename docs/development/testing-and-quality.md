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

High-risk shipped surfaces are registered in the machine-audited quality
surface catalog. Each row names an independent semantic oracle and classifies
every layer as `covered`, `not_applicable` with a reason, or `deferred` with an
owner. This avoids both silent gaps and meaningless requirements such as using
a model to judge deterministic scheduler precedence.

高风险交付面需要进入可机器审计的质量 surface catalog。每一行都要指明独立语义
oracle，并把每一层明确分类为 `covered`、有理由的 `not_applicable`，或有 owner 的
`deferred`。这样既不会静默漏测，也不会强迫模型去判断确定性的 scheduler 优先级。

```bash
loopx canary quality-audit
```

Run it from a source checkout to validate that referenced product, test, and
documentation paths still exist; packaged installs retain the classification
audit but report that repository-reference validation is unavailable.

在源码 checkout 中运行时，命令还会验证引用的产品、测试和文档路径仍然存在；打包
安装仍可审计分类，但会明确报告仓库引用校验不可用。

The audit fails on an unclassified high-risk canary profile, an oracle that
reuses product source as expected truth, a missing deterministic minimum, or
an unexplained exception. Valid deferred rows remain visible as backlog gaps
without pretending that the repository is fully qualified.

如果新增高风险 canary profile 却未分类、oracle 直接复用产品实现作为期望值、缺少
确定性最小门禁，或例外没有理由，审计会失败。合法的 deferred 行仍作为 backlog
缺口显式展示，不会伪装成仓库已经完全就绪。

Tests first judge whether the state and rule are correct, then whether the
implementation conforms. Expected outcomes come from an independently reviewed
invariant, never the implementation under test or its current output.
Characterization fixtures document legacy behavior but do not authorize it;
contradictions require rule repair and negative or mutation coverage, not a
refreshed golden.

测试先判断状态和规则是否正确，再验证实现是否符合。预期结果必须来自独立审阅的
不变量，不能由被测实现或当前输出生成。Characterization fixture 只记录历史
行为，不授予其正确性；发现矛盾时应修复规则并增加反例或 mutation 覆盖，不得刷新
golden 来让测试通过。

## Pull-Request Baseline / PR 基线

### Refactor Real-Path Gate / 重构真实路径门

The PR review capability's `observable_semantics` evidence gate applies to
behavior-bearing changes, including extractions and backend migrations; it
does not infer equivalence from a refactor title. Reviewers inventory legacy
caller branches at an immutable baseline and compare the same synthetic
inputs at the exact head through the public entrypoint. Include successful
and rejected paths, full diagnostics/remediation, validation precedence,
supplied/omitted/empty/clear arguments, persisted readback, ownership and
receipts, plus replay/concurrency where relevant. A provider suite whose
implementations share the new rule is not a before/after compatibility test.

重构评审必须区分“相同判定”和“相同可观察语义”：同样拒绝但丢失对象状态或修复
提示仍是回归；新增认领前提可能阻断旧实现允许的未认领文案修正；`--note` 被 parser
接受或出现在成功响应中，也不能证明它经过 dispatch 后落盘并能独立回读。先从旧调用
方及公开契约列出合法／非法分支，再运行基线与精确 head 的对照，不从新实现生成期望。

Show regression sensitivity: the focused case must fail on the historical
defect or a deliberate dropped-field/detail or stronger-precondition mutation,
then pass on the fix. Preserve intended changes as explicit justified deltas;
do not freeze a known baseline bug or normalize away meaningful differences.
Re-review the full inventory after a correction, not only the previous finding.
Missing comparison evidence blocks an equivalence-based approval. This is a
reviewer-executed requirement projected in the packet, not a machine proof
that the comparison ran. The packet tests protect this requirement's delivery;
runtime regressions must still test actual behavior.

保留“旧缺陷／语义 mutation 失败、修复后通过”的证据；有意变更需单列理由与验证，
不能盲目追求字节一致。复审重查完整兼容清单，不沿着上一条发现自动走向批准。缺少
对照证据就不能宣称等价；packet 测试只证明要求被投影，不证明 agent 已执行或产品无缺陷。

The evidence must be executable, not merely descriptive. Record a replayable
command or bounded script invocation for baseline, exact head, and the
sensitivity case, together with the real affected backend, immutable fixture
fingerprint, exit status, and normalized observation fingerprint. Baseline and
head use the same harness and fixture unless an intentional delta is declared.
The mutation run must traverse the same public entrypoint and make an
independent oracle fail; helper-only unit coverage or conformance among
providers that all share the candidate rule cannot satisfy this gate.

证据必须可执行，不只是文字描述。基线、精确 head 和敏感性用例都要记录可重放命令
或有界脚本调用，以及真实受影响 backend、不可变 fixture 指纹、退出状态和归一化观测
指纹。除非声明并证明有意差异，baseline 与 head 必须使用同一 harness 和 fixture。
Mutation 运行必须经过同一 public entrypoint，并让独立 oracle 失败；只测 helper，或让共享
候选规则的多个 provider 互相 conformance，不能通过该门禁。

Refactors must exercise the affected production entrypoint and real backend
before delivery. Unit tests, mocks, and in-memory conformance remain useful,
but cannot replace that proof. For changes affecting PostgreSQL authority,
configure `LOOPX_TEST_POSTGRES_URL` to an isolated disposable server and run
`npm run test:postgresql-authority-store`; a skipped suite is an evidence gap,
not a pass. Record the exact commit, backend version, tested behavior, and
failures or limits. If no safe real environment is available, hold delivery.

重构交付前必须验证受影响的真实生产入口和真实后端。单测、mock 与内存 conformance
不能替代这项证据。影响 PostgreSQL authority 时，配置指向隔离临时实例的
`LOOPX_TEST_POSTGRES_URL`，运行 `npm run test:postgresql-authority-store`；跳过不算
通过。记录精确 commit、后端版本、验证行为与失败或局限；没有安全的真实环境则暂停交付。

Keep tests separate from active state: use a disposable database/tenant and
runtime directory, with synthetic fixtures or an owner-authorized read-only
snapshot. Never run the integration suite against a shared or production
database: it creates roles and injects schema-level failure triggers. Never
promote an active goal, change its provider, or mutate its registry, writer
fence, Todos, or leases for a test. Keep private snapshots and raw outputs out
of Git and public reviews; compare source fingerprints before and after an
owner-authorized snapshot rehearsal. A concurrent source change is reported,
not overwritten or restored by the test. Stop the temporary server afterward.

测试使用独立临时数据库／tenant 和 runtime 目录，输入为合成 fixture 或经 owner 授权
的只读快照。集成测试会创建角色并注入 schema 级失败 trigger，禁止连接共享或生产库。
不为测试晋升正在运行的 goal、切换 provider，或修改其 registry、writer fence、Todo、
lease。私有快照和原始输出不得进入 Git 或公开 review；快照演练前后比较源指纹。
发现并发源变更只报告，不擅自覆盖或恢复。测试后停止临时数据库。

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

The Linux suite uses two hosted runners with two xdist workers each.
`pytest-split` partitions the complete collection using `least_duration`;
without a timing file, tests have equal weight and alternate between shards.
Lint, type checks, and the CLI budget run separately. The required `pytest`
check rejects failed/skipped shards and missing coverage artifacts, then uses
`coverage combine` to enforce the existing 19.6% floor on the union, not on
individual shards. Relative coverage paths make reports portable across runners.
The reusable Sonar workflow consumes that same run's XML and never reruns
pytest or reads cross-run artifacts. Missing Sonar tokens still skip analysis
successfully; test jobs receive no Sonar secret. The trigger is the union of
the former Python and Sonar paths, so app-only and Sonar-configuration changes
also run this lane, including on forks without a token.

Linux 全套测试分到两台 hosted runner，每台保留两个 xdist worker。`pytest-split`
按完整 collection 分片；没有历史耗时时，等权测试交替分配。lint、类型检查和 CLI
预算独立执行。必需的 `pytest` 汇总检查会拒绝失败／跳过的分片和缺失的 coverage，
合并后再执行原有 19.6% 门槛；不要求单个分片达到全套覆盖率。coverage 使用相对路径，
Sonar 只复用同一次 run 的 XML，不重复测试、不跨 run 取产物。缺少 token 仍成功跳过
Sonar，测试 job 不接收 Sonar secret。触发范围取原有两套 workflow 的并集，因此仅改
前端或 Sonar 配置也走此通道，包括没有 token 的 fork。

Reproduce one shard locally with `python -m pytest -q -n 2 --splits 2 --group 1
--splitting-algorithm least_duration --cov=loopx`. Omit the split arguments to
run the complete suite locally. 全量本地测试仍省略分片参数即可。

## Smokes And Canary / Smoke 与 Canary

A durable smoke should protect shipped behavior, a reusable contract, a
public/private boundary, or a regression that previously stranded automation.
It should not preserve dated research prose or raw execution evidence.

Use [What counts as a good smoke](good-smokes.md) for the contributor checklist,
semantic-oracle examples, public-safe fixture rules, and consolidation process.

Durable smoke 应保护已交付行为、可复用合同、公开/私有边界，或曾让自动化卡死的
回归；不应固化某次研究文案或原始执行证据。

贡献者检查项、语义 oracle 示例、公开安全 fixture 规则和合并流程见
[什么是好的 Smoke](good-smokes.md)。

The repository hygiene smoke is the thin baseline for LoopX's own public
checkout: it asserts required tracked files, runs the canonical public/private
boundary scan, and ratchets the release timeline to every published version
tag.

仓库卫生 smoke 是 LoopX 自身公共 checkout 的薄基线：断言必需跟踪文件存在，
执行规范的公开/私有边界扫描，并把 release 时间线收紧到每个已发布版本 tag。

```bash
python3 examples/repository-hygiene-smoke.py
```

Run one focused smoke while developing, then let the canary planner select the
smallest cross-surface set from the Git diff:

```bash
python examples/control_plane/interaction-scheduler-authority-smoke.py
loopx canary premerge --from-git-diff
```

`premerge` resolves the caller's Git root for diff hygiene, changed-Python
compilation, and public-boundary scanning, while LoopX's installed canary
catalog continues to run from its own trusted release root. This also supports
running the command from another repository or one of its subdirectories.

`premerge` 会把调用方 Git 根目录用于 diff 卫生检查、变更 Python 编译和公开边界扫描；
LoopX 已安装的 canary catalog 仍从自身可信 release root 运行。因此该命令也可从其他
仓库或其子目录执行。

The complete public sweep remains explicit and bounded:

```bash
loopx canary smoke-suite --suite full-public --jobs 4 --timeout-seconds 120
```

`full-public-smokes.yml` runs on `main`, daily, and by manual dispatch. It is
not a required PR check. This separation protects repository quality without
making every small patch wait for the broadest suite.

`full-public-smokes.yml` 在主干、每日定时和手动触发时运行，不是 PR 必须门禁。
这种分层既保护质量，也避免每个小 patch 都等待最宽测试集。

### Smoke Fleet Health / Smoke 集群健康

The full-public workflow also merges its shard receipts into one compact health
artifact. The report separates four cadences instead of treating every smoke as
an equal PR requirement: the explicit PR-fast smoke, catalog-selected canaries,
the daily full-public sweep, and high-risk release profiles. It aggregates
duration, failures, timeouts, current-inventory coverage, and targeted profile
ownership without copying stdout/stderr tails or repository-local paths.

full-public workflow 还会把各 shard 回执聚合成一个紧凑健康产物。报告区分四种频率，
而不是把每个 smoke 都变成 PR 必跑项：显式 PR 快速 smoke、catalog 选择的 canary、
每日 full-public 全量，以及高风险 release profile。它会统计耗时、失败、超时、当前
清单覆盖率和定向 profile owner，同时不会复制 stdout/stderr tail 或仓库本地路径。

```bash
loopx canary smoke-health --receipt smoke-results
```

The default output is a bounded review summary. Use `--include-inventory` only
for the explicit diagnostic cold path. Exact-content duplicates and direct
nested execution are review candidates; similar names or shared profile
membership are not enough to declare two semantic contracts equivalent. The
health audit never deletes or migrates a smoke automatically. A daily-only row
without a targeted profile is an ownership backlog signal, not proof that the
test is valueless.

默认输出是有界的审阅摘要；只有显式诊断冷路径才使用 `--include-inventory`。内容完全
相同或直接嵌套执行只会成为审阅候选；名称相似、共同属于某个 profile，不足以证明两个
语义合同等价。健康审计不会自动删除或迁移 smoke。只有 daily 全量覆盖、没有定向
profile 的条目表示 owner 待澄清，并不等于该测试没有价值。

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
gap. The composition group also checks decisions where several individually
reasonable signals conflict: a monitor lane says wait while a vision contract
requires replan; a user notice remains open while an independent successor must
run; or capability-blocked advancement requires an agent-owned capability-
bridge repair before any monitor fallback. Keep
schema validity, cold-path restoration, exact field presence, and the underlying
state transition table in deterministic tests.

它适合验证模型是否识别 selected todo、尊重人类门禁、在健康 onboarding transition
后继续、或识别已知 projection gap。组合场景还会验证多个单独看来都合理、合在一起
却存在优先级冲突的信号：monitor lane 要求等待但 vision 合同要求 replan；user notice
仍打开但独立 successor 必须运行；advancement 被 capability 阻塞时，agent 必须先
执行 capability-bridge repair，不能退回 monitor wait。schema、冷路径恢复、精确字段
存在性和底层状态转移表仍由确定性测试负责。

Live Doubao calls are a low-frequency local/manual gate, not ordinary CI.
`ARK_API_KEY` is injected only through the process environment. Packets,
prompts, raw responses, credentials, and conversations are never durable
repository evidence; only bounded receipts and mismatch codes may be retained.
Fake transports test only adapter serialization, sanitization, and fail-closed
handling; they never qualify Doubao behavior. Run the real gate with:

```bash
python3 scripts/qualify-doubao-model-behavior-live.py \
  --qualification-id <public-safe-run-id>
```

The command requires a clean candidate checkout, fails when `ARK_API_KEY` is
absent, binds its receipt to that checkout's Git source identity, and exits
nonzero unless every real provider call passes. See
[Model behavior qualification v0](../reference/protocols/model-behavior-qualification-v0.md)
for the actor and promotion contract.

Replan semantic action has a separate function-tool qualification because a
no-tool JSON decision cannot prove that the model would use projected coverage
to choose and persist a different direction. It creates a hermetic public-safe
Goal with two equivalent typed progress observations, gives the live model the
shipped thin Codex App heartbeat task body and one ordinary `exec_command`
function tool, and runs accepted quota and refresh commands through the real
LoopX CLI. The bounded host loop passes only when real quota emits the
host-projected coverage context and minimal action packet, and the model then
submits a typed semantic delta accepted by the write-time gate:

```bash
python3 scripts/qualify-doubao-replan-semantic-action-live.py \
  --qualification-id <public-safe-run-id>
```

The model does not receive a testing-only decision schema, expected command, or
prebuilt quota packet. Clock and a small set of workspace reads are supported
for normal heartbeat preflight. Commands are parsed into a strict allowlist
without invoking a shell; quota and refresh may write only inside the temporary
fixture, and no external or repository write is allowed. The actor independently
qualifies the selected typed observation before executing it. Evidence-log-only,
prose-only, pre-quota, equivalent-fingerprint, and ungrounded actions fail. The
receipt retains only action kinds, command digests, and typed semantic outcomes.

The selected-Todo scenario has its own focused real-action entrypoint for
changes to quota selection, heartbeat instructions, or the shared tool seam:

```bash
python3 scripts/qualify-doubao-selected-todo-tool-live.py \
  --qualification-id <public-safe-run-id>
```

It starts from the same production heartbeat contract, executes real quota,
and passes only after the model reads the target named by the selected Todo.
Reading the target before quota, choosing a deferred decoy, describing the
action without calling the tool, or issuing an unallowlisted command fails.

真实 Doubao 调用是低频本地/手动门，不进入普通 CI。`ARK_API_KEY` 只通过进程环境
注入；packet、prompt、原始响应、凭证和对话都不能成为仓库证据，只保留有界 receipt
与 mismatch code。fake transport 只能验证 adapter 的序列化、脱敏与 fail-closed，不能
作为 Doubao 行为通过证据。真实入口缺少密钥时直接失败，且任一真实调用不通过都会以
非零状态退出。

replan semantic action 另有一条 function-tool 行为资格门，因为 no-tool JSON 决策不能
证明模型会使用覆盖账本选择新方向并完成真实写回。资格门创建一个包含两个等价 typed
progress observation 的隔离、public-safe 临时 Goal；真实模型只看到正式 thin Codex App
heartbeat task body 和普通 `exec_command` tool。真实 quota 必须投影 host coverage context
与最小 action packet，模型随后提交的 typed semantic delta 还要通过独立语义判定和真实
写时闸门。若模型选择新 successor，资格门要求它以当前 `obligation_id` 调用真实
`todo add`，验证 Todo 原子 receipt 与 `host_action=end_current_heartbeat`，且不得在同一
turn 执行 successor；surface/hypothesis/probe 等结果仍走真实 `refresh-state`。仅读
evidence-log、只换措辞、quota 前动作、等价指纹或未落在当前状态中的 successor 都不算
通过。receipt 只保留 action kind、command digest 与 typed semantic outcome。

The scoped-gate successor composition case is also a real tool loop. Its
hermetic Goal contains an unrelated open user gate and a deferred successor
whose prerequisite is complete. After real quota selects the successor, the
model must surface the user action as a non-blocking assistant notice and read
the exact successor target. Waiting after the notice, omitting it, or reading
the gated decoy fails.

```bash
python3 scripts/qualify-doubao-scoped-gate-successor-tool-live.py \
  --qualification-id <public-safe-run-id>
```

Capability-bridge re-entry is the fourth real tool loop. Its hermetic Goal has
a capability-blocked advancement Todo and an incomplete monitor fallback. Real
quota must project `capability_bridge_repair`. The actor sends the shipped task
body inside the same heartbeat trigger envelope, including its trigger time,
that the Codex App model normally receives. The default CLI projection keeps
`interaction_contract` in the action-first prefix rather than after diagnostic
lanes. The model must verify the capability with the blocked Todo's real
task-facing read, then execute the projected quota re-entry command in the same
heartbeat; quota must select the original Todo without a repair Todo, turn
settlement, or durable capability grant. Waiting on or updating the monitor,
reading the callsite before quota, re-entering before successful verification,
or reading a different target fails. Bounded workspace inspection remains
available before quota; unrelated workspace reads after quota are classified as
backtracking and fail immediately.

```bash
python3 scripts/qualify-doubao-capability-monitor-repair-tool-live.py \
  --qualification-id <public-safe-run-id>
```

The regular live suite is
`actual_default_model_behavior_portfolio_v0`: nineteen one-arm scenarios and two
attempts each. Its selected-Todo case starts from a production thin heartbeat,
executes real quota, and requires the model to perform the selected Todo's
read-only target action. Its required-vision replan case independently builds a
hermetic missing-vision state, executes real quota, and requires the model to
use host-projected frontier/work-source context and submit a typed semantic
action through the real write path. The other turn cases remain
bounded packet-interpretation checks. Nine core-contract scenarios cover
onboarding, agent identity and goal selection, selected todo, peer identity
routing, same-agent continuation, final human gate, healthy continuation, and
projection repair. One effect-settlement scenario covers terminal closeout.
Two action-portfolio scenarios require a runnable fallback to replace either a
future monitor or a typed external wait while preserving the unavailable P0
context. One planning-horizon scenario requires the model to inspect a bounded
typed strategic chain before running the selected regression gate. Its action
oracle checks the ordered semantic stages rather than one exact trajectory:
bounded reads may intervene, but test must precede final writeback/spend and an
edit cannot be assumed before evidence. Writeback and spend are settlement
effects, so neither may appear before the final settlement suffix. Its
scenario-local semantic contract contains only `planning_horizon`; unrelated
peer and scheduler fields remain covered by deterministic contracts. Three
composition scenarios check vision/monitor/peer replan
precedence, non-blocking user notice plus ready-successor execution, and
capability-bridge repair before monitor fallback. Three compaction scenarios
check the JSON budget and source-derived semantic parity, then repeat clean
selected-work and blocking-gate contracts under over-budget omitted diagnostics.
Four contrast groups require the clean/noisy cases to remain invariant while
blocking gate versus non-blocking notice and selected work versus required
vision replan remain distinguishable. Each
scenario has an independent deterministic source oracle derived before CLI
projection; every repeat must pass and hard actor errors are not retried. The
remaining live turn actor cases consume the default CLI hot-path
`quota should-run` projection used by Codex App automation and return
runtime-facing decisions rather than echoing a global testing-only semantic
contract. The suite has 38 bounded scenario attempts. Five scenarios
exercise real tool loops; their per-scenario provider-call ceilings are owned by
the corresponding typed behavior harnesses instead of being duplicated here.
Exact scheduler, vision, writeback, and warning fields stay in deterministic
action-signature coverage; pair mode keeps TurnEnvelope semantic extraction for
explicit packet differentials or outcome claims.

常规 live suite 是 `actual_default_model_behavior_portfolio_v0`：19 个 one-arm
场景，每个重复 2 次。9 个 core-contract 场景覆盖正常接入、agent 身份与
goal 选择、selected todo、peer 身份路由、same-agent 续接、最终 human gate、
健康继续和 projection repair；1 个 effect-settlement 场景覆盖 terminal closeout；
2 个 action-portfolio 场景分别证明 future monitor 和 typed external wait 不会压住
可运行 fallback，同时仍保留不可运行的 P0 上下文；1 个 planning-horizon 场景要求
模型先检查有界的 typed strategic chain，再运行被选中的 regression gate；该场景只回读
`planning_horizon`，不会把无关的 peer/scheduler 字段混进 oracle；action oracle 验证
有序语义阶段而不是背诵唯一轨迹：中间允许有界只读动作，但测试必须先于最终
writeback/spend，不能在拿到测试证据前预设 edit，也不能提前执行 writeback 或 spend。
3 个组合场景覆盖
vision/monitor/peer replan 优先级、非阻塞
user notice 与 ready successor 并存，以及 capability-bridge re-entry 必须先于 monitor
fallback；3 个 compaction 场景覆盖 JSON 预算与 source-derived 语义一致，并分别让正常
selected work 和阻塞 gate 在超预算省略诊断下重复运行。4 个 contrast group 要求
clean/noisy 场景保持不变，同时要求 blocking gate 与 non-blocking notice、selected
work 与 required vision replan 仍然可区分。每个
场景都有在 CLI projection 前推导的独立确定性 source oracle，所有重复都必须通过；
actor 硬错误不自动重试。selected-Todo 场景从正式 thin heartbeat 开始，执行真实 quota，
并要求模型实际读取 selected Todo 指向的目标；required-vision replan 场景独立构造
缺失 vision 的 hermetic 状态，执行真实 quota，并要求模型读取 host 投影的 frontier 与
工作源，再通过真实写路径提交 typed semantic action；其他 turn 场景仍直接读取 Codex App
automation 使用的默认 CLI hot-path `quota should-run` projection 并返回运行时决策，
scoped-gate successor 场景也从 hermetic Goal 与正式 heartbeat 开始：真实 quota 必须
同时投影非阻塞 user notice 和 ready deferred successor，模型随后既要呈现提醒，也要
实际执行被选中的 successor；capability re-entry 场景则要求模型先执行原 blocked Todo
的真实任务侧 read，再在同一 heartbeat 执行 quota 投影的 re-entry 命令；quota 必须重新
选中原 Todo，且全程不创建 repair Todo、不结算 turn、也不写 durable capability grant。
其他 turn 场景仍属于
packet interpretation。scheduler、vision、writeback 与
warning 的精确字段继续由 action-signature 确定性覆盖；pair 中的 TurnEnvelope 只用于
明确的 packet 差分或结果提升声明。全套是 38 个有界 scenario attempt；5 个真实工具
场景的 provider 调用上限由各自 typed behavior harness 持有，本文不再复制易漂移的总数。

For onboarding packets, the suite uses the shipped guided packet builder and
redacts only local absolute path surfaces before provider transport. The
deterministic oracle runs first on the actual packet, so redaction cannot hide
missing commands, a lost host activation, an incorrect gate, a write, or quota
spend. Human-gate precedence is explicit: an expected absence of executable
work while waiting for the user is not a projection gap.

Onboarding 输入来自正式 guided packet builder；provider 调用前只替换本地绝对路径。
确定性 oracle 会先检查实际 packet，因此脱敏不能掩盖命令缺失、host activation 丢失、
门禁错误、写入或 quota 消耗。Human gate 的优先级是显式规则：等待用户时没有
executable work 属于预期状态，不能误判为 projection gap。

## Exact Release Commit Gate / 精确发布 Commit 门

The final release gate does not rerun tests through a second orchestration
framework. It aggregates compact receipts from the existing lanes and proves
that they all qualify the same clean source identity:

最终发布门不会通过第二套编排框架重新运行测试。它聚合现有测试通道的紧凑回执，并
证明它们都对应同一个干净源码身份：

```bash
loopx canary release-qualification \
  --manifest-json release-qualification.json \
  --repo-root .
```

`exact_release_commit_qualification_manifest_v0` repeats `git_commit`, Git
tree id, clean-tree status, package version, and version tag in every check
receipt. The CLI also derives those fields from `--repo-root`. A missing,
failed, skipped, dirty, rebased, or differently versioned receipt fails closed;
results from an earlier commit cannot qualify a later tag.

`exact_release_commit_qualification_manifest_v0` 会在每个检查回执中重复
`git_commit`、Git tree id、干净工作树状态、包版本与版本 tag；CLI 还会从
`--repo-root` 独立读取这些字段。缺失、失败、跳过、脏工作树、rebase 漂移或版本不一致
都会 fail closed；旧 commit 的结果不能给新 tag 背书。

| Receipt / 回执 | Semantic minimum / 语义下限 |
| --- | --- |
| `pytest` | At least one pass and zero failures / 至少一项通过且零失败 |
| `ruff`, `mypy` | Zero violations or type errors / 零 lint 或类型错误 |
| `risk_canary` | Selected checks passed with no unresolved manual hold / 已选检查通过且没有未解决人工 hold |
| `full_public` | Fleet receipt is ready with no failure or timeout / 全量集群 ready 且无失败或超时 |
| `install_upgrade_host` | Install, upgrade, and host routes all passed / 安装、升级与 host 路径均通过 |
| `public_boundary` | Zero public/private violations / 零公开私有边界违规 |
| `doubao_actual_default` | The catalog-derived actual-default portfolio passed every scenario repeat and contrast with zero failures or skips / 从固定 catalog 推导的实际默认 portfolio，其全部场景重复与对照均通过，且零失败、零跳过 |

Alongside repeated source identity and status, each receipt keeps only its
result schema, result digest, completion time, and bounded counters. Result
schema names are fixed per lane, and public-boundary evidence must show that at
least one path was scanned. Commands, stdout/stderr, prompts, packets, model responses,
credentials, and local paths stay outside the manifest. The command is a
read-only qualification reducer: it runs no checks, calls no model, moves no
ref, creates no tag, and publishes nothing. A ready receipt still requires the
owner's release decision.

每份回执只保留结果 schema、结果 digest、完成时间和有界计数。命令、stdout/stderr、
prompt、packet、模型响应、凭证与本地路径都不得进入 manifest。该命令只是只读资格
reducer：不运行测试、不调用模型、不移动 ref、不创建 tag、也不发布。即使回执 ready，
仍需 owner 作出发布决定。

## Benchmark Research Evidence / Benchmark 研究证据

Deterministic and model-behavior gates qualify a control-plane contract; they
do not prove that a release improves long-running outcomes. Outcome claims use
a small stable-release-versus-candidate manifest with matched task semantics,
runner protocol, model, reasoning level, timeout, and repetitions. A mismatch
or incomplete arm fails closed and cannot automatically promote a release.

确定性测试和模型行为测试验证控制面合同，但不能证明发布提升了长程结果。结果声明
必须使用小规模 stable-release-vs-candidate manifest，并匹配任务语义、runner、模型、
reasoning、timeout 与重复次数。任一不匹配或不完整都 fail closed，且不能自动发布。

Current benchmark studies follow the
[research RFC](../architecture/rfcs/long-horizon-harness-benchmark-research-program-v0.md)
and live in the repository-level [benchmark workspace](https://github.com/huangruiteng/loopx/blob/main/benchmark/README.md).
Legacy release reducers are archived and no longer form an active CLI or release
qualification surface.

当前 benchmark 研究遵循上述 RFC，并在仓库级 `benchmark/` 工作区中沉淀。旧 release
reducer 已归档，不再属于 active CLI 或 release qualification surface。

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
