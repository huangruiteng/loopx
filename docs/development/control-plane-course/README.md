# LoopX Control-Plane Developer Course / LoopX 控制面开发者课程

这套课程由第 0 讲架构导论和 9 讲专题组成，面向准备修改 LoopX kernel、CLI、状态投影、调度或扩展能力的开发者。主目标是建立一条可执行的控制面心智模型：先判断谁拥有长期事实、决策与执行权，再理解用户的一句目标如何变成可领取工作，状态如何写回，quota 为什么允许或拒绝下一轮，host 又如何安全地把决策变成周期执行。

课程采用一条贯穿始终的架构边界：LoopX 定义长程 agent 的 **goal-level control
plane**。执行 runtime、memory provider 和 workspace storage 可以替换或协作，但 goal
lifecycle、canonical state contract、验证与恢复闭环由 LoopX 组织；任何 adapter 都不能
静默成为第二个长期事实源。

这条边界可以展开成一条贯穿全课的闭环：

```text
vision / goal boundary
  -> todo、gate、monitor、successor 组成当前 frontier
  -> quota 把 source facts 编译成 interaction contract
  -> runtime 执行一个 bounded Turn，host 执行必要的外部 effect
  -> evidence、effect receipt、vision checkpoint 写回 canonical state
  -> acceptance audit 决定 continue、wait、replan、repair 或 terminal
```

每次读代码或评审 PR，都先回答五个问题：

1. **事实源**：这个决定依赖的事实由 registry、event、todo、vision 还是外部观察拥有？
2. **权限**：哪个 agent、user gate 或 host capability 有权改变它？
3. **归因**：状态属于整个 goal、某个 agent lane、某个 monitor target，还是某次 Turn？
4. **回执**：外部动作是否形成了与原 proposal 绑定的 durable receipt？
5. **延续**：本轮之后是 runnable successor、明确等待、replan、repair，还是满足 terminal closure？

控制面的复杂性通常不是缺少第六个字段，而是这五个问题被压进一个布尔值，导致一层
事实误替另一层做决定。

课程不是 API 枚举。每一讲都包含四类材料：

- 一条真实 CLI 或状态执行路径；
- 一组核心代码领读入口，说明调用顺序、关键分支和不变量；
- 一个公开 smoke、测试或实验，用来验证理解；
- 一组 review 问题，帮助开发者判断改动应落在哪个 bounded context。

## 课程地图

| 讲次 | 主题 | 读完应能回答 |
| --- | --- | --- |
| [第 0 讲](00-goal-control-plane-architecture.md) | LoopX Goal Control Plane Architecture | LoopX、host、runtime、memory、workspace 和 projection 分别拥有什么？ |
| [第 1 讲](01-first-real-loop.md) | 从 Showcase 到第一次真实 Loop | 用户只说一句目标后，guided start、todo、heartbeat、quota、refresh 和 spend 如何串起来？ |
| [第 2 讲](02-state-substrate.md) | 状态底座与可重放事实 | registry、event、active state、run history 和 projection 分别拥有什么事实？ |
| [第 3 讲](03-work-graph-and-peers.md) | Todo 工作图与 Peer 协作 | equal peer 如何 claim、显式委托 lifecycle authority、handoff 材料前沿，而不恢复 primary/side 层级？ |
| [第 4 讲](04-quota-decision-kernel.md) | Quota 决策内核与 Interaction Contract | `should-run` 如何把复杂状态压成 deliver、wait、ask、repair 或 quiet？ |
| [第 5 讲](05-host-scheduler-and-heartbeat.md) | Host、Heartbeat 与 Stateful Backoff | LoopX 决策、heartbeat prompt、execution context、Codex App RRULE 和 ACK 各自负责什么？ |
| [第 6 讲](06-evidence-refresh-and-self-repair.md) | 证据、Refresh 与 Self-Repair | 什么算 material progress，何时必须 replan，连续无推进如何形成可验证 repair delta？ |
| [第 7 讲](07-engineering-a-control-plane-rule.md) | 如何给 Control Plane 增加一条规则 | 如何从 invariant、ordered rules、schema、projection 到 smoke 完成一次可审计变更？ |
| [第 8 讲](08-autonomous-agent-quality-gates.md) | Agent 自主写代码时的分层质量门禁 | 如何按风险选择确定性测试、canary、模型行为验证与 release gate，既保护质量又不阻断普通迭代？ |
| [第 9 讲](09-extension-layer.md) | 扩展层、Explore 与 Multi-Agent 产品 | 默认关闭的 Explore Graph、Harness、Auto Research 和 Supervisor 如何复用 kernel？ |

## 建议学习方式

第一次阅读按 0 到 9 的顺序进行。第 0 讲先建立 authority map 与四视图架构图谱，第 1 讲运行端到端路径，第 2 到 6 讲拆开状态、工作图、决策、host 和证据，第 7 讲把这些知识收束成工程变更方法，第 8 讲建立自主交付的质量门禁，第 9 讲再看扩展层。

不要从模块文件头一路向下读。每讲的“核心代码领读”会给出函数级入口，先搜索目标函数，再沿 bounded-context helper 向下读。运行实验时使用临时 goal 和测试仓库，不要把课程占位 id 当作真实配置。

## 组合推理是课程主线

单个概念通常不难；控制面的复杂性来自多个各自正确的规则在同一轮里同时成立。读课时不要只问“这个字段是什么意思”，还要推导：谁拥有事实、哪条规则优先、三个 interaction channel 分别输出什么、host 是否应继续唤醒，以及什么证据才允许 spend 或 closeout。

下面几组组合会在后续章节反复出现：

| 组合场景 | 必须回答的关键问题 | 主要章节 |
| --- | --- | --- |
| due monitor + scoped user gate + autonomous replan | monitor 的新证据如何形成 gate；replan 是否覆盖 quiet；未获授权的 delivery 为什么仍不可执行？ | 第 4、5、6 讲 |
| interleaved monitors + per-lane no-change streak + advancement precedence | 为什么一个 monitor 的轮询不能替另一个清零；何时应 replan，何时仍由 runnable advancement 优先？ | 第 4、6、8 讲 |
| non-blocking `user_action` + `required_decision_scopes` + interaction budget | 用户可见提醒为什么不能冒充授权；压缩输出时哪些 gate 语义必须保留？ | 第 3、4、7 讲 |
| unscoped user gate + multi-agent frontier + explicit global authority | 缺失 scope 为什么应触发 projection repair，而不是默认冻结整个 goal；真正的全局 gate 如何明确表达？ | 第 3、4、8 讲 |
| claim + lease + capability + workspace guard + handoff | 谁可领取、谁正在执行、在哪里允许写、何时必须换 peer，为什么是五个不同问题？ | 第 3、4 讲 |
| stateful backoff + proposal identity + host readback + durable ACK | cadence 改变后如何区分“宿主值正确”和“当前 proposal 已结算”；为什么 ACK 与 quiet poll 都不是 delivery？ | 第 5、6 讲 |
| guided hot path + deterministic oracle + actual-default model qualification | 缩短 agent-facing packet 时，如何同时证明字段合同、状态语义和真实模型行为没有漂移？ | 第 4、7、8 讲 |
| benchmark postcondition + committed Turn + runner readiness | 结果通过为什么不能替代因果归因与控制面回执；测试替身怎样避免改写 meaningful operation 语义？ | 第 6、8 讲 |

这些组合不是额外功能清单，而是同一状态图的交叉切面。课程中的 case、decision table 和 smoke 应尽量覆盖交叉项，而不是为每个名词各写一个孤立 happy path。

## 版本与边界

课程以仓库当前 `main` 的公开 CLI、协议文档和 smoke 为准。代码移动后，应在同一个 PR 中更新函数路径和阅读顺序；行为变化后，应先更新 canonical contract 或 focused test，再调整课程解释。

课程不承载真实线程、私有 todo、内部文档、本机路径、raw transcript、凭证或生产操作记录。需要讲解真实故障时，只保留能复现状态机的最小 public-safe fixture。

继续开发前还应阅读：

- [Developer guide](../README.md)
- [Testing and quality](../testing-and-quality.md)
- [Core control-plane graphs](../../product/core-control-plane/README.md)
- [Public/private boundary](../../public-private-boundary.md)
