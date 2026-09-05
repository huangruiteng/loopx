# RFC：共享 Goal 对齐与受治理 Amendment 协议（v0）

- 状态：草案；维护者评审中
- 跟踪 Issue：[#3836](https://github.com/huangruiteng/loopx/issues/3836)
- 日期：2026-09-02
- 最后更新：2026-09-05
- 范围：多个对等 Agent 围绕同一个共享 Goal 协作，同时保留 canonical
  intent、每个 Agent 的执行 frontier、claim/lease 所有权，以及可审计的
  replan/amendment 决策
- 相关契约：
  [Goal Vision 与 Replan](../../reference/protocols/goal-vision-replan-contract-v0.md)、
  [共享控制面 Authority 与可插拔状态 Provider](./shared-goal-authority-state-provider-v0.zh-CN.md)，
  以及 [Decision Context](../../reference/protocols/decision-context-architecture-v0.zh-CN.md)
- 语言说明：
  [英文版](./shared-goal-alignment-and-governed-amendment-v0.md)与本中文版是语义镜像；
  二者存在实质差异即为缺陷。

---

## 1. 摘要与决策

LoopX 将区分四类不能坍缩为一份可变计划的状态：

1. **canonical 共享 Goal intent envelope**；
2. **共享 eligible work graph**；
3. 每个已注册 peer 各自的 **per-Agent frontier**；
4. 用于治理共享 amendment 的 **proposal 与 receipt 记录**。

Agent 可以在 canonical intent 内修正自己的 frontier。当证据推翻共享假设时，
它可以提出共享 amendment。Proposal 不会改变 Goal、阻塞无关工作，也不会赋予
提出者单方面 commit authority。只有 LoopX `GoalAmendmentAuthority` 根据预授权 policy
和精确 base revision 校验、通过 compare-and-set（CAS）提交并生成 durable receipt
后，共享 amendment 才会生效；此后所有 Agent 都必须把自己的 frontier 重新绑定到
新的 canonical revision。

正常路径是自动化的，不要求所有 peer 投票，也不要求人审批日常 Goal 演化。
`peer_v1` 表示执行层级平等，不代表每个 Agent 都能越过 root user intent 或取得新
permission。Goal 创建时会冻结 `root_intent` 与 amendment-policy envelope。在该
envelope 内，policy check 以及高风险 class 所需的独立 verifier Agent 授权自动
commit；超出 envelope 时，旧 Goal 继续有效，proposal 被 reject 或结构化 blocked，
只有 Goal 显式配置时才升级给人。

```text
canonical 共享 Goal intent envelope
  (objective, non-goals, acceptance, permissions, stop conditions, revision)
                 |
                 v
共享 eligible work graph
                 |
        +--------+--------+
        |                 |
        v                 v
per-Agent frontier A   per-Agent frontier B
        |                 |
claim + lease/fence    claim + lease/fence
        |                 |
bounded evidence       bounded evidence
        +--------+--------+
                 |
       lane replan 或 amendment proposal
                 |
      自动 policy + 可选 verifier
                 |
          base-revision CAS commit
                 |
      committed shared amendment + receipt
                 |
          每个 frontier rebase 或被 gate
```

## 2. 问题与当前边界

LoopX 已经能较好地协调执行：

- 已注册 peer identity 与 Agent-scoped Todo lane；
- 可见、可选择的 unclaimed Todo，以及 work 前必须 claim 的提示；
- soft claim 与 hard lease/fence 所有权；
- per-Agent vision 与 checkpoint 状态；
- typed autonomous-replan obligation 与 settlement；
- action-scoped cross-owner Todo lifecycle grant；
- provider-neutral coordination CAS 与 receipt 基础。

[#3693](https://github.com/huangruiteng/loopx/pull/3693) 是这一层的正向、
边界明确的修复：它避免共享 `Next Action` prose 遮蔽精确 settlement-bound 或当前
Agent 的 Todo。它没有定义共享 Goal 对齐，也没有定义共享语义 amendment authority。

当多个 Agent 独立发现共享计划或 acceptance boundary 有误时，缺失的 seam 就会
出现：各个 per-Agent vision 可以各自自洽，但合并后的工作已经无法证明原始 Goal。
反过来，如果允许每个 Agent 直接重写共享 prose，最后写入者就会意外成为 authority。

类型系统无法证明任意自然语言修改保留了用户原意。LoopX 能做到的是让静默重解释
变得不可能：amendment 必须说明 retained、changed、stopped，引用 evidence，绑定
精确 base revision 与 digest，通过显式 authority policy，并留下可恢复 receipt。

## 3. 状态分区与不变量

### 3.1 Canonical intent envelope

`shared_goal_intent_v0` 包含：

- `goal_id`、`goal_revision` 与 `intent_digest`；
- objective 与 non-goals；
- acceptance conditions；
- permission/write scope；
- stop 与 terminal conditions；
- Agent 不能 amendment 的 root intent；
- 治理每种 amendment class 的 authority policy；
- out-of-policy proposal 的配置处置方式（`reject`、`block` 或显式
  `human_escalation`）。

它是 semantic authority，不是 status projection。`Next Action`、Agent vision、聊天
消息、scheduler hint 和 provider head 都不能覆盖它。

### 3.2 Shared work graph

共享 work graph 包含 Todo、dependency、eligibility、blocking gate 和 lifecycle
state。它描述候选工作，而不是谁现在可以执行。Work-graph 变更必须可追溯到它希望
推进的 canonical intent revision。

### 3.3 Per-Agent frontier

每个注册 Agent 获得一份有界 `shared_goal_alignment_v0` projection：

- canonical Goal revision/digest；
- 当前 Agent 的 frontier 与 `based_on_goal_revision`；
- 它的 claim 与 lease/fence facts；
- eligible unclaimed work；
- open lane replan 或 shared amendment obligation；
- conflict 或 stale-basis facts。

当 route 变更仍在当前 objective、non-goals、acceptance、permission 与 stop
condition 内，且不修改另一 Agent 已 claim 的工作时，Agent 可以 replan 自己的
route，而不需要 shared amendment。

### 3.4 Proposal 与 receipt

Proposal 是 advisory、durable input；receipt 证明 canonical transition。二者不能
互相替代。Pending 或 approved proposal 都不会生效，直到成功的 commit receipt
明确记录新的 Goal revision。

### 3.5 Host session locator 与 advisory context

任务深度链接可以让 peer 精确进入本协议，而不成为第五类共享状态。对 Codex 而言，
`codex://threads/<thread-id>` 标识一个本地聊天。LoopX 可以通过当前项目 registry
解析该 locator，并把来源 session 绑定到现有 Agent 与 Goal identity。返回的
provider-neutral `host-session:codex:<thread-id>` scope 随后可由显式启用的 Decision
Context provider 用来选择该 session。

它是可选、临时的 **advisory context input**，位于
`shared_goal_intent_v0`、`goal_amendment_proposal_v0`、
`goal_amendment_receipt_v0` 和 provider CAS head 之外。它帮助 peer：

- 精确定位发现 gap 或 evidence pointer 的任务；
- 审阅当前事实时召回一组有界的来源任务消息；
- 把 amendment proposal 路由给独立 verifier 或受影响 peer；
- commit 后回到相关任务读取 receipt 并完成 frontier reconciliation。

```text
host task deep link -> project-local binding -> normalized host-session scope
        | explicitly configured, read-only ContextProvider
        v
local-private transient recall -> verify against current authority sources
        | explicit promotion to durable typed evidence
        | base Goal revision + intent digest
        v
governed amendment proposal -> authority decision -> canonical receipt
```

这个顺序是规范要求。深度链接不是 `evidence_ref`，召回消息不是 amendment
decision，extension lifecycle revision 也不是 `base_goal_revision`、
`authority_revision`、`provider_generation` 或 `lease_epoch`。Amendment 需要的任何
session-derived conclusion，必须先对照当前 authority 检查，再显式提升到现有 Todo
evidence、Agent evidence log 或 registered material owner；proposal 再引用这些
durable typed reference，并独立绑定当前 Goal revision 与 intent digest。

Locator 也不授予 read access、permission、claim、lease、lifecycle authority、
verifier independence 或 amendment commit authority。如果链接无法解析、无权读取，
或 extension 被禁用或不可用，只有可选的 context-enrichment 步骤 fail open；
canonical Goal 和无关工作继续有效。Decision Context 记录 provider degradation，
并继续使用仍可用的 authority sources。Receipt recovery 仍使用 `operation_id` 和
`readReceipt`，因此 host session 丢失不能让已提交 amendment 变得不可恢复。
Cross-Goal rendezvous 可以帮助两个 peer 协调，但每个 Goal 仍需要各自的 proposal、
policy decision、CAS commit 和 receipt。

Core 只解析一次 host-specific 深链语法，并只向 provider 暴露 normalized scope。
可选的 `loopx-obelisk` extension 把该 scope 映射到 Obelisk 公开的只读 query
接口；它不读取 Obelisk 存储 schema，不 build 或 attune 索引，也不打开、恢复或向
live task 发消息。其他 harness 可以实现相同的 Decision Context provider 协议，无需
把 host 语法或 transcript 存储引入 Goal authority。

## 4. Authority matrix

### 4.1 `GoalAmendmentAuthority` 到底是什么

`GoalAmendmentAuthority` 不是人、leader Agent、模型或存储服务。它是 LoopX 对
canonical Goal amendment 的唯一 typed write boundary。具体实现应拆成：

```text
proposal + current Goal + policy + lease impact + optional verifier decision
                                  |
                                  v
                 GoalAmendmentAuthority.decide()
                       reject | needs_rebase | commit
                                  |
                                  v
                  provider CAS + canonical receipt
```

Decision reducer 执行 deterministic policy、identity、digest、revision 与 impact
规则。可选 verifier Agent 只为语义问题提供 typed input，不能 commit；transaction
executor 通过 provider-neutral store 持久化已接受 decision，但不能扩张 decision。
称它为 authority，含义是所有 canonical writer 都必须经过这个边界，而不是某个高位
Agent 替 peers 做决定。

### 4.2 Amendment class

| Amendment class | 示例 | Proposal authority | 自动 commit 规则 | Pending 时的默认影响 |
| --- | --- | --- | --- | --- |
| `lane_route` | 调整一个 Agent 的未认领本地步骤顺序 | owning Agent | deterministic lane policy | lane 外无影响 |
| `shared_work_graph` | 新增不改变 intent 的 Todo 或 dependency | registered Agent | policy validation + impact check | 无关工作继续 |
| `shared_acceptance` | 在 root intent 内细化 acceptance condition 或 non-goal | registered Agent | policy validation + independent verifier Agent | gate 受影响的 acceptance path |
| `protected_authority` | 取得新 permission 或越出 root intent | registered Agent | 除非 immutable envelope 已精确委托该 class，否则绝不自动 commit | 受影响工作 fail closed |

`GoalAmendmentAuthority` 是正常 commit boundary。Verifier Agent 返回绑定 evidence 的
typed decision；它不会成为 durable leader，也不能编辑它所验证的 proposal。Policy
要求独立性时，proposer 与 verifier identity 必须不同。Deterministic check 始终是
第一道 gate；model judgment 不能覆盖 permission、scope、stop condition 或 stale base。

Scheduler、Supervisor、latest writer、lease holder 或 provider operator 的身份都不
授予 semantic commit authority。Out-of-policy proposal 会被 reject 或保持结构化
blocked，旧 Goal 继续运行；只有显式启用 `human_escalation` 才询问人，而不是把每次
Goal 变更变成人工审批队列。

## 5. Amendment lifecycle：proposal 最终如何生效

```text
draft -> submitted -> admitted -> policy_check -> verified -> committing
  |          |            |             |             |
  +--------> rejected <----+-------------+-------------+
                             stale/conflict -> needs_rebase

committing --CAS success--> committed + receipt -> frontier reconciliation
          \--unknown------> ambiguous -> readReceipt/reconcile
          \--CAS conflict-> needs_rebase
```

完整生效路径如下：

1. **Propose。** 任一有 proposal 权限的 actor 提交
   `goal_amendment_proposal_v0`，其中包含 base revision/digest、amendment
   class、retained/changed/stopped intent、evidence references、affected Todos
   与关联的 replan obligation。可选的 host-session rendezvous 可以帮助发现或审阅
   gap，但只有经过提升的 durable evidence 才能进入 proposal。
2. **Admit。** LoopX 校验 schema、actor identity、有界 evidence pointer、
   amendment class 与影响范围。Host locator 不能证明 actor identity，也不能充当
   evidence。Admission 不等于 approve 或 apply。
3. **Policy decision 与可选 verification。** LoopX 检查 deterministic invariant
   与预授权 amendment envelope。较高风险但仍在 envelope 内的 class 可调用独立
   verifier Agent，由其返回绑定精确 proposal digest 的 typed decision。Policy 可以
   reject 或要求 rebase；verifier decision 不能复用于被编辑过的内容。
4. **Impact decision。** Commit 前，authority 必须决定如何处理在途 claimed/leased
   Todo：不受影响、允许基于旧 revision 完成、通过新 fence epoch 显式取消，或由
   policy 阻塞。Semantic amendment 不能静默使 lease 已授权的工作失效。
5. **Commit。** `GoalAmendmentAuthority` transaction 带 `operation_id`、期望的
   `base_goal_revision` 与 `base_intent_digest` 提交 policy-authorized digest，
   再次校验 policy 并执行一次 CAS。Base 过期时 fail closed。日常 in-envelope
   amendment 不等待人。
6. **Receipt。** 同一事务记录 proposal digest、actor、authority source、旧/新
   revision、retained/changed/stopped delta、evidence references、affected Todos、
   lease disposition 与精确 replan obligation settlement。
7. **Reconcile。** Projection 旋转到新 revision。每个 Agent 要么 rebind frontier、
   要么打开 lane replan，或者在当前工作不兼容时被 gate。旧 revision 上的 semantic
   write 会被拒绝。

只有第 5 步会让 amendment 成为 canonical。第 6 步保证响应丢失时仍能恢复这一事实；
第 7 步让它对所有 peer 真正产生运行时影响。

## 6. 提议的 schema

示意 `goal_amendment_proposal_v0`：

```json
{
  "schema_version": "goal_amendment_proposal_v0",
  "proposal_id": "gap_...",
  "goal_id": "goal-1",
  "proposer_agent_id": "agent-a",
  "amendment_class": "shared_acceptance",
  "base_goal_revision": 17,
  "base_intent_digest": "sha256:...",
  "retained": ["original outcome remains unchanged"],
  "changed": ["acceptance now requires the recovered receipt"],
  "stopped": [],
  "evidence_refs": ["evidence:..."],
  "affected_todo_ids": ["todo-a", "todo-b"],
  "replan_obligation_id": "replan:..."
}
```

示意 `goal_amendment_receipt_v0` 额外包含：

```json
{
  "schema_version": "goal_amendment_receipt_v0",
  "operation_id": "op_...",
  "proposal_id": "gap_...",
  "proposal_digest": "sha256:...",
  "decision": "committed",
  "authority_actor_id": "goal-amendment-authority",
  "authority_source": "goal_amendment_policy_v0",
  "verifier_decision_digest": "sha256:...",
  "previous_goal_revision": 17,
  "new_goal_revision": 18,
  "new_intent_digest": "sha256:...",
  "lease_dispositions": [],
  "settled_replan_obligation_id": "replan:..."
}
```

只读 `shared_goal_alignment_v0` projection 必须区分 pending、approved、conflicting
与 committed proposal，不能把任何 pre-commit 状态当成 canonical intent。

## 7. 并发、恢复与多 Agent 行为

同一 base 上可以并存多个 proposal。Policy/verifier decision 与 commit 绑定精确 proposal digest。
Canonical commit 按 Goal revision 串行化：一个 proposal commit 后，另一个基于旧
base 的 proposal 进入 `needs_rebase`；绝不静默合并，也不采用 last-writer-wins。

Proposal pending 时，独立 lane work 继续，除非 typed impact gate 明确覆盖该 Todo
或 acceptance path。Agent 只能通过现有 atomic claim，并在配置要求时获取
lease/fence 后，才能执行 eligible unclaimed work。提出 proposal 不会预留 Todo，
拥有 Todo claim 也不会授权 Goal amendment。

如果 provider commit 成功但响应丢失，调用方不会用新 operation identity 盲目重试。
它使用相同 `operation_id` 调用 `readReceipt`。找到 receipt 即证明 canonical
revision；receipt 缺失且 head 已变化时必须 reconciliation，不能把 ambiguous 当作
failure。File、NoKV 或 PostgreSQL 的 provider-specific 行为继续留在
provider-neutral authority store contract 后面。

## 8. Replan 集成

Replan 在选择 writer 前先分类发现的 gap：

- 完全位于 canonical intent 内的 route correction 打开或结算 Agent-scoped
  replan obligation；
- cross-lane dependency/work-graph gap 打开 shared amendment obligation；
- 会在 root-intent envelope 内改变 acceptance、non-goals 或 operational objective
  的证据打开 automatically governed amendment obligation；
- 超出 delegated permission 或 root intent 的变更按配置被 reject 或保持结构化
  blocked。

每个 obligation 都有 stable id。仅 ACK proposal 不会结算它。Settlement 必须是：
该精确 obligation 对应的 committed receipt；被 policy 接受的 reject/no-change
结构化 rationale；或显式保留因果链的 superseding obligation。

Commit 后，`based_on_goal_revision` 已过期的 Agent 可以观察，但在 rebase 或取得
显式 grandfathered-work disposition 前，不能执行 controlled semantic write。
这样 shared change 就能连接现有 per-Agent Goal Vision，同时不会把一个 Agent 的
vision 变成 peer authority。

## 9. Provider 与 projection 边界

Semantic authority 决定 proposal 是否合法、谁可以 commit。File、NoKV 与
PostgreSQL provider 只持久化 normalized transaction、CAS head 与 receipt；它们不
解释 Goal prose，也不选择 amendment policy。

本 RFC 的第一个实现切片不扩大当前 coordination aggregate。现有 shared-authority
RFC 继续拥有 Todo/claim/lease/receipt 持久化。Goal semantic amendment 首先以只读
projection 与 proposal contract 交付；把 commit 映射进 provider-neutral aggregate
需要单独评审的 transaction boundary。

`Next Action` 继续是 compatibility prose 与 read projection。它永远不是 claim、
lease、Goal amendment、replan settlement 或 authority decision。

## 10. 分阶段交付

1. **Stage 0 — characterization 与 RFC。** 记录 own-lane、unclaimed、
   peer-claimed、replan、并发 proposal 与 in-flight lease 场景。
2. **Stage 1 — read-only alignment。** 增加 `shared_goal_alignment_v0`，包含
   canonical revision binding、per-Agent frontier basis、unclaimed work 与
   drift/conflict facts；可选 Decision Context extension 可以把精确 host-session scope
   与有界 advisory recall 配对；不改变 writer。
3. **Stage 2 — proposal only。** 校验并保留 `goal_amendment_proposal_v0`；
   proposal 不产生 canonical effect。
4. **Stage 3 — 一个有界 commit class。** 实现保留 intent 的 shared work-graph
   amendment 自动治理 commit，覆盖 policy、CAS、receipt、replan settlement 与
   lease impact。
5. **Stage 4 — provider-neutral shadow/parity。** 把经过评审的 transaction 映射到
   file reference provider 与可选 NoKV/PostgreSQL candidate；在不改变默认 authority
   的情况下比较 projection 与 recovery。
6. **Stage 5 — TEST ONLY shared canary。** 在 authority-source promotion 前验证两个
   peer、并发 proposal、unclaimed claim、响应丢失恢复、stale base 与 protected
   change。

Acceptance 与 operational-objective commit 不是第一个 runtime 切片；它们需要真实
需求证据和单独评审的 automated policy/verifier contract。Permission 扩张或越出
root intent 不能自动 commit，除非 Goal 创建时已经精确委托该 class。

## 11. 验证矩阵

测试至少必须证明：

- own-lane replan 不能改变 canonical intent；
- unclaimed work 可见，但 claim/lease 前不能执行；
- pending proposal 不影响无关 peer；
- policy 与 verifier decision 绑定精确 proposal digest；
- 同一 base 的两个冲突 proposal 最多只能有一个 canonical commit；
- stale revision/digest commit fail closed；
- 响应丢失恢复返回原始 receipt；
- protected change 不能仅凭 proposer、scheduler、lease holder、verifier 或 provider
  operator 身份提交；
- 日常 in-envelope amendment 无需人审批即可完成，而 out-of-policy proposal 永不
  静默扩大 authority；
- in-flight leased work 获得显式 disposition；
- canonical revision 改变后，所有 Agent projection 都会 rotate 或 gate；
- host-task locator 只能通过当前项目 binding 解析，且不授予 claim、lease、
  lifecycle、verifier 或 amendment authority；
- 禁用或移除 advisory provider 不会阻断 authority-source collection，而 amendment
  submission 仍必须独立绑定当前 Goal revision 与 intent digest。

Durable proposal、receipt recovery 与 cross-Goal commit isolation 仍由既有 Goal
amendment 和 authority-store conformance tests 负责。可选 locator/provider 的测试
不得重复这些状态机测试。

## 12. 非目标

本版本不定义自动投票或共识、CRDT/offline multi-writer merge、omniscient planner、
permanent leader、Agent 直写 storage provider、LoopX 状态的广泛迁移，也不允许自动
越出 immutable root user intent。Human approval 不是正常 amendment lifecycle 的
必需步骤。Host-session locator、深度链接和 transcript 也不属于 Goal aggregate 或
durable evidence store。

最小有用结果是一份清晰的只读 alignment projection，以及一份显式不具 authority
的 proposal。只有这条边界在真实多 Agent 工作中证明有价值后，runtime commit 才
继续推进。
