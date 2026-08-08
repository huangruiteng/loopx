# 一轮受治理的工作

LoopX 的核心不是“让 Agent 无限循环”，而是把当前项目事实编译成一轮有边界、可验证、可写回的
工作协议。本章从 `quota should-run` 的 decision 开始，解释 user、agent 与 CLI 如何在同一轮中
承担不同义务。

## 本章目标

读完后，你应该能：

- 解释 quota 为什么是 decision kernel，而不只是余额检查；
- 读取 `interaction_contract` 的 user、agent 与 CLI 三个 channel；
- 区分 bounded delivery、user gate、monitor quiet、replan、repair 与 terminal；
- 判断一次 Agent 输出是否足以支持 canonical writeback；
- 解释 validation、refresh、receipt 与 spend 为什么必须按顺序发生；
- 说明 scheduler hint 为什么不是执行授权。

## 从 Source Facts 到 Interaction Contract

每一轮先读取当前事实，而不是沿用上一轮 prompt 中的判断：

```text
registry and goal boundary
  + todo frontier and claims
  + decision scopes and gates
  + capability and workspace
  + evidence freshness and run history
  + quota and scheduler context
  + vision / replan obligations
  -> interaction_contract
```

`loopx quota should-run` 是这个决策面的主要入口。历史兼容字段可能仍提供 `should_run`、
`action_required` 或 `recommended_action`，但新读者应优先读取：

1. `interaction_contract.mode`；
2. user、agent、CLI 三个 channel；
3. selected Todo、goal boundary 与 guard；
4. scheduler hint 和 spend policy；
5. 再使用兼容字段辅助展示。

单看 `should_run: false` 无法区分“等待用户”“monitor 未到期”“当前 Agent 没有 in-scope work”或
“控制面需要修复”。这些状态要求完全不同的下一步。

## 三个 Channel 可以同时成立

[`loopx_interaction_contract_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/quota-allocation.md)
把一轮义务拆成三个视角：

### User channel

回答：

- 用户现在是否必须行动；
- 应该通知还是保持安静；
- 具体问题、decision scope 与原因是什么；
- 该 Gate 只阻塞哪个 action、lane 或整个 Goal。

### Agent channel

回答：

- 当前 Agent 是否必须尝试工作；
- 是否允许 delivery；
- 是否允许 quiet no-op；
- 唯一 primary action 是什么；
- 这是普通交付、观察、repair 还是 replan。

### CLI channel

回答：

- 哪些 lifecycle command 是下一步；
- validation 后如何 refresh/writeback；
- 何时允许 spend；
- Gate、wait 或 no-change 为什么不应 spend。

三个 channel 不是互斥布尔。例如：

```text
user channel:
  action_required = true
  action = approve homepage publication

agent channel:
  must_attempt = true
  primary_action = run an independent link check

CLI channel:
  spend_after_validation = true
```

这表示用户 Gate 仍然可见，但它没有覆盖独立的 link-check Todo。把三个 channel 压成“有用户
Todo，所以 Agent 停止”会丢失 scoped fallback；压成“Agent 可以做事，所以不通知用户”也同样错误。

## 常见 Interaction Modes

Mode 将一组相互关联的状态压成可测试协议。外部开发者至少要能识别：

| Mode | Agent 行为 | User 行为 | Spend |
| --- | --- | --- | --- |
| `bounded_delivery` | 完成一个有界 artifact、blocker 或 state delta | 通常无需打断 | validation + writeback 后一次 |
| `user_gate` | 不运行被 Gate 覆盖的路径 | 回答、拒绝、取消或改向 | 不 spend |
| `scoped_user_gate_fallback` | 只运行不依赖该 Gate 的 selected fallback | Gate 仍可见 | fallback 验证后一次 |
| `external_evidence_observation` | 读取 bounded handle/readback，不发明交付 | 必要时提供缺失 handle | material transition 后才可能 spend |
| `monitor_quiet_skip` | 未到期或无 material change 时保持安静 | 无需打断 | 不 spend |
| `agent_scope_wait` | 当前 peer 没有 in-scope candidate，等待重分配 | 通常无需行动 | 不 spend |
| `autonomous_replan` | 写入 Todo、Vision、acceptance 或 no-follow-up delta | 只有 owner-held 决策才打断 | 有 accountable delta 后 |
| `outcome_floor_recovery` | 只恢复缺失的 outcome evidence 或写 blocker | 视 blocker owner 而定 | 通过恢复验证后 |
| `blocked_health` / repair | 先修复 registry、projection 或 boundary | 仅在需要 owner authority 时介入 | 无有效 delta 不 spend |

具体 mode 会随协议演进。书中要保存的是判别方法：谁拥有下一 transition、什么行为被允许、什么
证据允许 writeback，而不是背诵一个永久不变的枚举列表。

## Decision Pipeline：先排除非法路径，再选择 Frontier

Quota 决策不是让多个规则各自返回一个布尔值，再用最后一次赋值获胜。它按依赖顺序把 source
facts 编译成一个 interaction contract。外部开发者不必记住实现函数，但需要掌握九个阶段：

1. **Identity：** 解析精确 Goal 与 registered Agent，身份不明时 fail closed；
2. **Goal boundary：** 建立 repository、write scope、authority source、spawn 与 public/private
   boundary；
3. **User Gate：** 归一化 blocking scope、decision scope、具体问题和 projection gap；
4. **Outcome / repair obligation：** 检查连续 surface-only progress、Vision 或 acceptance gap，
   判断是否必须 replan 或 self-repair；
5. **Capability：** 筛出当前执行面真正具备能力的候选；
6. **Workspace：** 检查 task repository、worktree、branch 与 required write scope；
7. **Frontier：** 解析 priority、claim/lease、dependency、successor、monitor 与 terminal
   closure；
8. **Interaction contract：** 把结果组合为 user、agent 与 CLI 三个 channel；
9. **Scheduler hint：** 从已确定的 lifecycle 状态派生下一次 wake、backoff 与 ACK。

顺序本身就是安全合同。例如先选择 Todo、后检查 workspace，会让 Host 在发现“当前目录错误”
之前已经开始写；先把 open user item 当作全局阻塞，则会饿死不依赖该决定的安全工作。更可靠的
阅读顺序是：

```text
identity
  -> authority and boundary
  -> scoped decision
  -> repair obligation
  -> capability and workspace eligibility
  -> frontier and continuation
  -> interaction contract
  -> scheduler
```

### 三个组合 Case

**Scoped Gate 与独立工作。** P0 被 scoped Gate 阻塞，另有独立 P1 时，user channel 保留
Gate，agent channel 只执行明确选中的 P1。不能简化成“有 User Todo，所以整个 Goal 停止”。

**未到期的 Monitor。** 没有 advancement work，且 Monitor 尚未到期时，正确结果是 quiet
wait/backoff：不 poll、不 spend，也不停止 automation。`should_run=false` 不代表 Goal terminal。

**Monitor、Gate 与 Replan 同时变化。** Due Monitor 产生新 Gate，同时 autonomous replan 到期时，
先写 compact observation；再把 Gate 放进 user channel，并让 replan 形成 machine-visible
frontier delta；最后重算 scheduler identity。不能因为 Monitor 本轮结束，就沿用旧 cadence quiet。

这些 case 说明规则会组合，而不是互相覆盖。Gate 约束 authority，Monitor 表达何时观察，
Replan 修订 frontier；只有最终 interaction contract 才定义本轮行为。

需要阅读完整 decision table、九类组合 case、源码 seam 与 smoke 时，进入
[Control-Plane Course 第 4 讲](/loopx/docs/development/control-plane-course/04-quota-decision-kernel/)；
Host、heartbeat、stateful backoff 和 scheduler receipt 的实现细节见
[第 5 讲](/loopx/docs/development/control-plane-course/05-host-scheduler-and-heartbeat/)。

### Quota 是决策编译器，不是余额检查

“还剩多少配额”的直觉是减法思维：每次运行扣一次，耗尽就停。但一轮合法工作可能不需要 spend
（monitor poll、dry-run、preflight），一轮 spend 也不等于做了有效交付（artifact 无 validation）。
把 quota 理解为余额检查，会让系统在以下场景出错：

- **PR checks 挂起时**：不能因为 goal 仍在 active 就调用模型。必须先等待外部结果，再决定下一步。
- **连续 dry-run 或 preflight 失败**：spend 未发生，但系统不应无限重试。连续失败需要 repair 或
  replan，而不是继续“尝试”。
- **monitor 未到期**：不应因为“还有配额”就提前 poll，浪费外部资源。

Quota 的正确模型是从 source facts 按稳定 precedence 编译成 interaction contract。它决定“本轮是否
允许 delivery、允许什么行为、允许几次 spend”，而不是“余额 > 0 就开始”。五个关键 source facts
及其决策含义：

| Source Fact | 决策含义 |
| --- | --- |
| Goal 是否注册、Agent 是否识别 | 身份不明时 fail closed，不消耗任何资源 |
| User Gate 是否阻塞当前 scope | 被阻塞的路径不执行，不被阻塞的 fallback 可以独立运行 |
| Frontier 是否有 claimable Todo | 无可运行候选时进入 monitor/agent-scope wait，不消耗 agent 资源 |
| 连续 delivery 是否缺乏 outcome | 多轮 surface-only 后，要求真正 outcome 或 self-repair，不无限交付 |
| 外部 evidence 是否 fresh | 过期证据不能进入当前决策，必须先刷新 readback |

禁止的捷径包括：凭“goal active”跳过 Gate、凭“曾有配额”跳过 workspace check、凭“用户未投诉”
跳过 validation。这些都是把局部信号当成全局授权。

完整决策 table、九类组合 case 和规则优先级见
[Control-Plane Course 第 4 讲](/loopx/docs/development/control-plane-course/04-quota-decision-kernel/)。

## Bounded Delivery 的五段闭环

一次正常交付至少包含五段：

```text
Decide
  -> Act
  -> Validate
  -> Write back
  -> Account
```

### 1. Decide

读取 current decision，选择 `agent_channel.primary_action` 对应的 Todo。不得用旧 prompt、旧
dashboard 卡片或上一次 `recommended_action` 覆盖当前 contract。

### 2. Act

完成一个可恢复的 bounded segment。Bounded 不等于“只改一行”，而是这个工作段：

- 有明确输入与边界；
- 产生 coherent artifact、observation 或 blocker；
- 能独立验证；
- 能形成下一项 Todo、等待条件或 no-follow-up。

只读一个文件、重复“正在分析”或运行无关命令不构成交付。

### 3. Validate

验证必须检查真实 postcondition，而不是相信执行者自述：

- 代码：focused test、contract test、smoke 或 build；
- 文档：构建、链接、命令表面与 public-boundary scan；
- 外部 effect：远端 readback、revision 或 service state；
- blocker：缺失依赖、权限或可观察 handle 的明确证据。

`process exited 0` 可能只证明工具启动成功。它不自动证明目标行为、外部状态或 acceptance。

### 4. Write back

验证后，通过 Todo lifecycle、event、evidence 或 `refresh-state` 把 compact truth 写回。写回至少
说明：

- 交付了什么；
- 依据什么 revision / command / readback；
- 哪个 acceptance 或 blocker 被推进；
- 下一步、successor、replan 或 no-follow-up；
- per-Agent Vision 是否改变。

Raw transcript 和大段日志不应进入 public-safe state。

### 5. Account

只有 validated writeback 已经存在，才按 CLI channel 记录一次 quota spend。Gate notification、
dry-run、失败 preflight、未变化 monitor poll、scheduler cadence change 和重复 writeback 都不应
冒充 delivery spend。

顺序不能倒置：

```text
wrong: act -> spend -> later decide whether it worked
right: act -> independent validation -> durable writeback -> spend once
```

### 缺层的故障模式

五段闭环是连续依赖链。缺哪一层，都会产生不同的故障，而不是“循环仍在继续”：

| 缺失层 | 可见症状 | 后果 |
| --- | --- | --- |
| 缺 Validation | 有 artifact 但无 postcondition 检验 | 不合格交付进入 writeback，后续决策基于错误证据 |
| 缺 Writeback | artifact 已生成但 Todo 仍 open | 下一 peer 看不到完成，重复工作或选错 frontier |
| 缺 Refresh | Todo 已更新但 status/vision 还是旧值 | quota 选错目标，monitor 按过期条件判断 |
| 缺 Spend | 交付已写回但没有 quota 记录 | quota accounting / delivery causality 不一致 |

Validation 缺失最危险，因为它把内部信心当成了外部事实。Writeback 缺失最常见，因为 agent 在“完成
工作”后跳过闭环，只保留了本地 artifact 或聊天记录。Refresh 缺失最隐蔽：表面上看状态正确，实际
quota 和 monitor 在读取决策前已过时。

这个证据阶梯的完整实验见
[Control-Plane Course 第 6 讲](/loopx/docs/development/control-plane-course/06-evidence-refresh-and-self-repair/)，
其中包含每层的失败回放和修复路径。

## Evidence、Receipt 与 Observation

三个概念在一轮中承担不同责任：

| 对象 | 证明什么 | 不证明什么 |
| --- | --- | --- |
| Observation | 某个时刻看到了什么 | 结论已被接受或仍然新鲜 |
| Evidence | 哪些材料支持一个判断 | 状态转换已实际写入 |
| Receipt | 某个 action/transition 在绑定输入与 revision 下被接受 | 外部世界永远不变 |

例如 `git push` 超时后：

- tool invocation 是 attempt；
- `git ls-remote` 的结果是 readback observation；
- remote ref 与 expected commit 相同可以成为 evidence；
- LoopX 记录发布 transition 才形成 durable receipt。

Proposal 也不是 effect。一个协议声明“建议 publish”不会自动授予凭据、权限或证明远端已经改变。

## TurnEnvelope 与 LoopX Turn

完整 quota decision 可能包含大量诊断信息。可选的
[`loopx_turn_envelope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/turn-envelope-v0.md)
把已经计算出的 decision 压缩成 bounded read model，保留：

- selected Todo 与 effective action；
- Gate、required reads 与 goal boundary；
- capability/workspace guard；
- validation、writeback 与 spend policy；
- scheduler action；
- compact contract capsule。

TurnEnvelope 是 projection，不重新选择工作，也不改变 quota semantics。

[`LoopX Turn`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/loopx-turn-v0.md)
进一步定义可选的 governed transaction：

```text
live decision
  -> typed host request
  -> Agent/Host candidate result
  -> independent validator
  -> durable writeback
  -> one spend
```

Codex App heartbeat、Codex CLI visible Goal 或其他 Host 不必都用同一种 adapter 实现，但应保持同一
控制语义：Host 负责执行与唤醒，LoopX decision 负责合法下一步，validator 不直接相信 Host 的
完成声明。

!!! info "当前成熟度"
    TurnEnvelope 目前是显式启用的 bounded projection，不是默认 quota 输出；LoopX Turn 是
    experimental protocol 和 implementation target。它们适合贡献者理解边界和做集成实验，不应被
    描述成所有 Host 已经统一采用的稳定 runtime。

## Monitor 与 Scheduler Hint

当 frontier 只剩外部条件时，建立 `continuous_monitor`，而不是反复让 Agent 问“有变化吗”。一个
Monitor 至少需要：

- stable target key；
- cadence 与 next due；
- bounded observation handle；
- material-change 判据；
- expiry 或终止条件；
- no-change accounting policy。

`scheduler_hint` 把当前状态投影为 Host cadence，例如现在运行、等待 fresh evidence、等待重分配或
按 monitor cadence 唤醒。它不是 execution permission：

```text
scheduler hint: when to wake
interaction contract: what this turn may do
```

Host 即使在正确时间唤醒，也必须重新运行 current decision。旧 scheduler proposal、旧
`should_run` 或旧 selected Todo 不能跨状态变化直接复用。

### Scheduler 需要 apply、readback 与 ACK

以 Codex App heartbeat 为例，`recommended_rrule` 只是目标 cadence。完整收敛链是：

```text
LoopX proposes recommended_rrule
  -> Host applies one automation update
  -> Host result / observed RRULE proves the actual cadence
  -> run the exact ack_hint.cli_args
  -> LoopX records reset token, identity and applied RRULE
```

协议上的几个关键分支：

- `apply_needed=true`：Host 最多尝试一次 update；成功后执行 packet 中完整的
  `ack_hint.cli_args`，失败或超时则不 ACK，并执行一次 `failure_hint.cli_args`；
- `apply_needed=false, ack_needed=true`：Host readback 已精确匹配 proposal，跳过 no-op update，
  直接执行绑定的 ACK；
- `host_observation.status=drift_detected`：实际 cadence 与 ledger 不一致，旧 ACK 不能压过当前
  readback，需要重新 repair；
- terminal pause/stop：按 Host contract 验证停止结果，不把它伪装成普通 RRULE ACK。

当前 ACK 使用 `quota scheduler-ack-current` 重新读取 latest hint。Host 必须执行 packet 给出的完整
argv，因为其中可能绑定 registry、runtime profile、Agent identity 和 capability envelope；手抄
reset token 或删掉全局参数会把 ACK 写到错误状态。

Scheduler state 还绑定 `reset_token` 与 `identity_signature`。用户反馈、新 Todo、reassignment、
Gate resolution 或 material evidence transition 会改变 identity，并把 cadence 恢复到当前 profile
的初始值；连续 unchanged polls 才继续 backoff。Cadence apply、failure writeback 和 ACK 都不产生
delivery quota spend。

### 多 Monitor 交错时的 per-lane 计数

当 M1 和 M2 两个 monitor 交替轮询时，如果只数“相邻 run 是否无变化”，M1 的 run 会打断 M2 的
no-change streak，M2 也会打断 M1。最终两个 monitor 的 consecutive_no_change 都永远到不了阈值，
系统无法进入 backoff，反而变成热轮询。

正确做法是**每个 monitor todo 维护独立的 `consecutive_no_change` 计数器**。M2 有 material change
时只重置 M2，M1 不受影响。回合顺序（A1、B1、A2、B2...）不会互相清零。

这个 per-lane 设计也适用于多 agent 场景：每个 agent 的 monitor 是独立 lane，共享的是同一个
frontier 读模型，但 no-change 判断是 per-lane 的。实现细节和交错实验见
[Control-Plane Course 第 6 讲](/loopx/docs/development/control-plane-course/06-evidence-refresh-and-self-repair/)。

## 一轮何时结束

当前 Turn 可以以不同结果结束：

- validated delivery + writeback + spend；
- concrete blocker + recovery condition；
- user Gate notification；
- bounded external observation；
- quiet monitor/no-candidate wait；
- replan/repair delta；
- terminal audit 后停止。

“没有写代码”不一定是失败；Gate、wait 和 quiet no-op 可能正是协议要求的合法结果。反过来，写了
很多代码也不代表这轮有效，如果它绕过 selected Todo、authority、workspace 或 validation。

下一章解释跨 Turn 的恢复、自修复和 terminal closure，并把 Agent、Capability、Provider、
Extension 与外部系统的运行责任放回同一事实边界。
