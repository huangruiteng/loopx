# 第 0 讲：从两个 Showcase 理解 LoopX 架构

> **本讲结论：** LoopX 让不同领域的长程 Agent 复用同一套外置目标、工作、权限、证据与
> 恢复内核。Issue-Fix 和 Auto Research 的业务状态完全不同，但都把有限模型上下文中的
> 一次执行放进 `观察事实 -> 领域判断 -> Kernel 决策 -> 有界执行 -> 证据写回 -> 下一轮恢复`。

建议时长：90 分钟。Showcase 30 分钟、架构与生命周期 30 分钟、代码入口 20 分钟、评审练习 10 分钟。

## 本讲解决什么问题

第一次接触 LoopX 的开发者通常先看到 registry、todo、quota、scheduler、event、domain
state 等大量名词。直接从模块或状态枚举开始，很难回答一个更基本的问题：这些机制为什么
需要同时存在？

答案从模型边界开始：模型只在当前上下文中推理，而 goal 要跨上下文压缩、session、Agent、
host 和外部系统变化继续成立。长程系统因此需要逐层外置控制信息：

```text
prompt / transcript
  -> host-persisted goal objective and lifecycle
  -> project-owned structured control state
  -> per-Turn packet compiled from current state
```

Codex 原生 Goal 已经完成关键的第一步：`thread/goal/set` 把 objective、status 与可选预算绑定到
thread，`thread/goal/get` 允许读回，host 可以围绕它继续 `turn/start`。LoopX 解决的不是
“再存一遍 goal string”，而是原生 Goal 故意没有承担的项目控制状态：todo graph、claim、
scoped gate、effect receipt、跨 host cadence、领域 observation、replan 和 recovery。每轮模型
只接收这些状态派生出的 compact interaction contract，而不是全部历史。

长程 Agent 的困难不只在模型推理。一次模型 turn 结束后，下面的事实仍要继续成立：

- 目标和验收标准没有随聊天上下文消失；
- 外部世界变化后，Agent 能区分“继续做”“等一等”“问人”和“已经结束”；
- 多个 Agent 不会把软认领、执行占用和写权限混成同一个 owner；
- 一次成功调用不会在缺少验证和写回时被误报成进展；
- 失败、重启、换 session 后，下一轮从已提交事实恢复，而不是重猜上一轮发生了什么。

LoopX 解决的是这组 **goal-level control-plane** 问题：无人干预时靠确定性合同跑稳，有人
干预时把反馈写成 scoped decision、路线修订或经验，使下一轮跑得更好。先看两个差异很大的
产品闭环，再从它们共同需要的机制推导架构。

完成本讲后，开发者应该能够：

1. 用 Issue-Fix 和 Auto Research 解释 LoopX 的产品价值；
2. 区分 State Kernel、Capability Pack、Domain State、host/runtime 与外部事实源；
3. 沿一个领域 observation 找到 Kernel transition 和下一步 work item；
4. 判断一个新 capability 是否复用了内核，还是悄悄创建了第二套控制面。

## Showcase A：PR Issue Fix

Issue-Fix 的产品承诺是：把一条公开 issue 持续推进成小而聚焦、验证充分、可审阅的 PR，
并跟进到 merged、closed 或明确 no-follow-up。它不是“一次 prompt 生成 patch”，因为真实
交付还包含候选判断、复现、修改、CI、review correction、冲突、通知、等待和终局收口。

```mermaid
flowchart LR
  I["Public issue"] --> F["Feasibility<br/>fix_pr / comment / triage"]
  F --> T["Kernel todo<br/>claim · scope · quota"]
  T --> P["AgentLoop<br/>reproduce · patch · validate"]
  P --> PR["GitHub PR"]
  PR --> M["Lifecycle observation<br/>checks · review · merge"]
  M --> X["Domain transition"]
  X --> N["successor / monitor / user gate / terminal"]
  N --> T
```

这条链路同时经过五种责任：

| 阶段 | 负责的层 | 保存或执行什么 |
| --- | --- | --- |
| issue、代码、checks、review、merge state | Repository / GitHub | 外部权威事实 |
| feasibility、repository context、PR lifecycle | Issue-Fix Domain State | 带稳定 key 和 fingerprint 的紧凑领域事实 |
| `fix_pr`、CI failure、changes requested 等判断 | Issue-Fix Capability | 把领域 observation 翻译成有限 transition |
| todo、claim、gate、quota、monitor、successor、terminal | LoopX State Kernel | 决定谁现在能在什么边界内做哪一步 |
| 读代码、建 worktree、修改、测试、执行已授权 GitHub 动作 | Host / AgentLoop | 一次有界执行及外部 effect |

### 一次 PR observation 怎样变成下一步工作

`loopx/capabilities/issue_fix/pr_lifecycle.py` 的 `_decide_transition()` 不直接改 todo，也不
直接调用 GitHub。它把 PR observation 压成 Kernel 能理解的 proposal。下面是保留关键
分支优先级的语义伪代码，不是仓库 API 的逐字摘录：

```python
if state == "MERGED":
    return transition(decision="no_followup", task_class="terminal_transition")
if failing_checks:
    return transition(decision="runnable_successor", task_class="advancement_task")
if review_decision == "CHANGES_REQUESTED":
    return transition(decision="runnable_successor", task_class="advancement_task")
if pending_checks:
    return transition(decision="monitor_continuation")
```

实际代码还处理 draft、branch conflict、已修复并等待 re-review 等状态。这里重要的是返回值
边界：`runnable_successor` 只是建议创建后续工作，`monitor_continuation` 只是建议继续观察，
`no_followup` 只是终局候选。Kernel 仍会检查 todo authority、decision scope、capability、
workspace、quota 和 continuation policy。

低层调用路径可以这样读：

```text
build_issue_fix_feasibility_packet
  -> upsert_issue_fix_feasibility_ledger_jsonl
  -> Kernel writes a normal todo / gate
  -> AgentLoop produces a focused fix and PR
  -> build_issue_fix_pr_lifecycle_monitor_packet
  -> _decide_transition
  -> upsert_issue_fix_pr_lifecycle_ledger_jsonl
  -> Kernel writes successor / monitor / terminal closeout
```

Domain State 的 upsert 会按 `repo + issue_ref` 或 `repo + pr_ref` 保持稳定 identity，并用
observation fingerprint 抑制 unchanged poll。它保存紧凑事实和已验证 receipt，不保存 raw
issue body、raw check log、凭据或本地路径。GitHub 仍是权威来源，Domain State 只负责让
下一轮不必从聊天里重建领域连续性。

完整案例见 [Issue-Fix 能力](../../capabilities/issue-fix/README.zh-CN.md) 和
[State Kernel × Domain State 案例](../../capabilities/issue-fix/state-kernel-domain-state-case-study.zh-CN.md)。

## Showcase B：Multi-Agent Auto Research

Auto Research 的产品承诺是：多个研究 Agent 围绕同一 research contract 持续提出假设、
执行实验、评价证据并形成 promotion、retirement 或 retry 候选。研究树可以被投影出来，
但不需要一个拥有整棵树的 coordinator agent。

```mermaid
flowchart LR
  C["Research contract<br/>metric · baseline · protected scope"] --> H["Hypothesis todos"]
  H --> Q["Per-agent quota + frontier"]
  Q --> E["Isolated executor turn"]
  E --> P["Typed evidence packet<br/>dev · holdout · boundary"]
  P --> G["Evidence graph"]
  G --> D["promotion / retirement / retry"]
  D --> S["role-scoped successor todos"]
  S --> Q
```

默认角色不是层级，而是写入不同 typed record 的 equal peers：

| Role | 主要产物 | 不能做什么 |
| --- | --- | --- |
| Curator | research contract、metric、protected scope | 选择赢家或修改受保护 evaluator |
| Hypothesis proposer | 有 grounding 和 todo lineage 的 hypothesis | 用同一材料同时声称独立 novelty |
| Executor | 隔离实验、dev/holdout result、evidence packet | 自行 promotion 或隐藏失败尝试 |
| Evaluator / promoter | promotion、retirement、retry candidate | 把 dev-only lift 当成最终证据 |
| Product narrator | public-safe evidence graph 与案例叙事 | 发明指标或改写 source state |

### 没有中央研究经理，研究怎样继续

`run_auto_research_worker_loop()` 只轮询一组可见 lane。每个 worker turn 都重新读取当前
agent 的 quota 和 research frontier，再执行一个被选中的 todo：

```python
for agent_id in agent_ids:
    turn = run_auto_research_worker_turn(
        goal_id=goal_id,
        agent_id=agent_id,
        ...,
    )
if no_lane_has_action:
    stop_reason = "no_runnable_frontier"
```

真正的选择发生在 `load_auto_research_worker_frontier()`：它先调用
`build_quota_should_run(..., agent_id=agent_id)`，再把 rollout evidence 投影成该 agent
可见的 research frontier。worker 不拥有全局 executor queue，也不能因为看见一个假设就
越过 claim 和 quota。

另一端，`build_research_decision_candidates()` 根据 evidence graph 产生有限结果：

| 证据状态 | 下一步 |
| --- | --- |
| dev 改善但缺少 holdout | 创建或暴露 holdout successor |
| holdout 改善且 boundary clean | 进入 promotion review 或满足目标策略 |
| negative / guardrail evidence | 形成 retirement candidate |
| 尝试未计分但可恢复 | 保留 retry candidate 与 artifact ref |
| 无 runnable frontier 且完成条件满足 | quiet completion |

低层调用路径可以这样读：

```text
build_auto_research_preset_summary
  -> role profiles + initial todos
  -> run_auto_research_worker_loop
  -> run_auto_research_worker_turn
  -> build_auto_research_evidence_packet + rollout append
  -> build_research_evidence_graph_from_rollout_events
  -> build_research_decision_candidates
  -> build_auto_research_completion_status
  -> role-scoped successor / promotion gate / quiet completion
```

Auto Research 是建立在通用 multi-agent kernel 上的 thin preset：preset 提供角色、领域默认值
和 successor hints；goal、todo、claim、quota、evidence、handoff 与完成语义仍由 Kernel
拥有。更完整的角色合同见
[Auto Research Lane Contract](../../reference/protocols/auto-research-lane-contract-v1.md)。

## 两个 Showcase 共同揭示的架构

Issue-Fix 处理 GitHub 生命周期，Auto Research 处理假设与指标证据。二者没有共享业务状态，
却共享同一条控制面闭环。LoopX 内部可以先按三层理解，外部再接三类边界：

| 层 | 拥有什么 | Issue-Fix | Auto Research |
| --- | --- | --- | --- |
| **State Kernel** | goal、vision、todo、claim、gate、quota、scheduler、evidence lineage、handoff、terminal | patch todo、CI monitor、publish gate | role todo、per-agent frontier、promotion gate |
| **Capability Pack** | 领域 observation 到 typed transition 的翻译、validator、preset | feasibility 与 PR lifecycle decision | role defaults、evidence decision、successor rules |
| **Domain State** | 稳定 key 下的紧凑领域事实 | feasibility、PR lifecycle、outcome | hypothesis、evidence event、evidence graph |
| **Host / runtime** | session、模型、工具、worker、一次有界执行 | coding agent / GitHub host | research worker lanes |
| **External truth / provider** | 领域权威事实或可替换 I/O | repository、GitHub、optional memory/notification | evaluator、artifact store、public research sources |
| **Projection** | 可重建的人与机器 read model | status、Kanban、report | evidence graph、frontier、showcase |

这张表给出两个关键约束：

1. Capability 可以增加领域判断，但不能复制 Kernel 的 todo、quota、gate 或 authority；
2. Domain State 可以保存领域连续性，但不能把 observation 直接变成外部 effect。

## Goal Control Plane Authority Map

下面的总览图不是源码层次图。它表示事实、决策、执行和回执怎样跨边界流动。

```mermaid
flowchart TB
  U["User / reviewer<br/>intent · scoped decision · reward"]
  X["External truth<br/>GitHub · evaluator · timer · provider"]

  subgraph LX["LoopX goal-level control plane"]
    K["State Kernel<br/>goal · work · authority · quota · recovery"]
    C["Capability Pack<br/>domain observation -> typed transition"]
    D["Domain State<br/>compact facts · fingerprint · lineage"]
    V["Projection<br/>status · graph · dashboard · report"]
    C <--> D
    C --> K
    K --> V
  end

  subgraph EX["Replaceable host and execution plane"]
    H["Host loop / scheduler"]
    R["Agent runtime<br/>model · tool · worker · session"]
    H --> R
  end

  U -->|"goal / decision"| K
  X -->|"bounded observation"| C
  K -->|"interaction contract / selected work"| H
  R -->|"typed result / evidence / receipt"| C
  R -->|"authorized effect"| X
  V -->|"current state"| U
  V -->|"frontier"| H
```

读图时只需先记住五条边界：

1. **Kernel 拥有 goal lifecycle。** Host 被唤醒不等于获得 delivery 权限，一轮结束也不等于
   goal 完成。
2. **Capability 拥有翻译规则。** 它理解 `CHANGES_REQUESTED` 或 holdout metric，但只返回
   typed proposal。
3. **Domain State 拥有领域连续性。** 它不拥有 claim、quota、全局 authority 或外部写权限。
4. **Runtime 拥有执行。** 模型和工具负责实现，不把聊天摘要升级成长期事实。
5. **Projection 只读。** 看板、图和报告可以提交显式命令，不能靠修改展示文本改变 source state。

## 一次通用 Goal Transition

两个 Showcase 都可以压成同一条生命周期：

```mermaid
sequenceDiagram
  autonumber
  participant H as Host
  participant K as State Kernel
  participant C as Capability
  participant R as Runtime
  participant S as Durable state

  H->>K: goal_id + agent_id + current capabilities
  K-->>H: interaction contract + selected work
  H->>R: execute one bounded action
  R-->>C: result + external observation + artifact refs
  C-->>K: typed transition + validation evidence
  K->>S: durable writeback
  S-->>K: committed-state readback
  K-->>H: successor / wait / ask / replan / terminal + cadence
```

关键不变量：

- observation 不是 transition；
- proposal 不是 authority；
- result 不是 accepted result；
- accepted result 在 durable writeback 后才构成进展；
- spend 晚于验证与写回；
- scheduler proposal 在 host apply 并形成 ACK 前仍未结算。

第 4 到第 6 讲会分别展开 quota decision、host scheduler 和 evidence/writeback。第 0 讲只需
确认：这些阶段让长程工作可以被重放、归因和恢复。

## 多个协作状态机，不是一个巨型枚举

LoopX 不把所有业务状态放进一个 `status` 字段。Kernel 维护多个可组合 contract：

```mermaid
flowchart LR
  REG["Goal / registry"] --> TODO["Todo lifecycle"]
  VISION["Vision / acceptance"] --> TODO
  GATE["Gate / decision scope"] --> Q["Quota / interaction"]
  TODO --> Q
  CLAIM["Agent route / claim / handoff"] --> Q
  EVID["Evidence / receipt"] --> TODO
  Q --> SCH["Scheduler / heartbeat"]
  Q --> REPLAN["Replan / repair"]
  REPLAN --> TODO
```

领域状态不会加入这张图成为第二套 Kernel。Issue-Fix 把 checks 和 review 翻译成通用 work
transition；Auto Research 把 evidence graph 翻译成通用 successor、gate 或 completion。
Kernel 只需要计算这些 transition 是否可执行、由谁执行，以及写回后下一轮怎样恢复。

详细状态体和 legal transition 分别由
[State Definitions](../../product/core-control-plane/state-definitions.md) 与
[State Machines](../../product/core-control-plane/state-machine.md) 维护。

## Host 接入：交换协议，不替换 Runtime

Codex App、Codex CLI 或 managed-agent 平台可以继续拥有 session、actor、tool、workspace、
runtime event、cancel 和 retry。接入 LoopX 时，只需对齐四个面：

| 接入面 | Host 提供 | LoopX 提供 |
| --- | --- | --- |
| Identity | session / actor 与 `goal_id`、`agent_id` 的关联 | goal、agent、todo identity |
| Observation | 新外部事实与当前 capability | canonical state 与 domain transition input |
| Decision | 接收并执行 bounded action | quota、interaction contract、scope、cadence proposal |
| Receipt | result、artifact、effect readback | validation、durable writeback、recovery 与 projection |

如果 host 已拥有某个 Task DAG 的 lifecycle，LoopX 默认只做 projection 与 guard。只有显式
选择 LoopX 为该工作项 controller 并授予 scoped authority 后，LoopX 才写相应 lifecycle。

## 开发者代码地图

第一次读代码时，不要从包目录顺序展开。沿一条产品结果回到共同内核：

| 阅读目的 | 函数级入口 | 代表验证 |
| --- | --- | --- |
| Issue 是否值得形成 fix work | `build_issue_fix_feasibility_packet` | `examples/issue-fix-feasibility-smoke.py` |
| PR observation 怎样变成下一步 | `build_issue_fix_pr_lifecycle_monitor_packet`、`_decide_transition` | `examples/issue-fix-pr-lifecycle-smoke.py` |
| Issue-Fix 领域事实怎样幂等保存 | `upsert_issue_fix_pr_lifecycle_ledger_jsonl` | `examples/issue-fix-workflow-e2e-smoke.py` |
| Auto Research role 怎样声明 | `build_auto_research_preset_summary` | `examples/auto-research-dev-thin-preset-smoke.py` |
| 每个研究 lane 怎样重新进入 Kernel | `load_auto_research_worker_frontier`、`run_auto_research_worker_turn` | `examples/auto-research-worker-turn-smoke.py` |
| 研究证据怎样形成决策 | `build_research_decision_candidates`、`build_auto_research_completion_status` | `examples/auto-research-layered-e2e-acceptance-smoke.py` |
| 通用 Kernel 怎样选择本轮动作 | `build_quota_should_run`、`build_interaction_contract` | 第 4 讲的 quota smokes |
| 一轮结果怎样写回并恢复 | `run_loopx_turn_once`、`refresh-state` | 第 5、6 讲的 transaction / refresh smokes |

这条阅读路线同时覆盖 high-level product loop 和 low-level implementation seam。开发者先问
“这个函数把哪种领域事实翻译成哪种通用 transition”，再看 schema、fingerprint、ordered
rules 和 writeback；这样比从一个大文件逐行阅读更容易辨认真正的 ownership。

## 评审一个新 Capability

面对新的领域 pack、MCP、memory provider、dashboard 或 multi-agent preset，依次问：

1. **External truth**：领域事实来自哪里，稳定 identity 是什么？
2. **Domain State**：哪些紧凑事实需要跨 turn 保存，哪些 raw material 必须留在外部？
3. **Translation**：领域 observation 会产生哪些有限 transition？
4. **Kernel reuse**：todo、claim、gate、quota、scheduler、evidence 和 terminal 是否仍由 Kernel 拥有？
5. **Execution**：谁应用外部 effect，哪些动作需要独立 authority？
6. **Receipt**：如何证明 effect 作用于正确对象，并与 proposal、todo、agent 和 revision 建立 lineage？
7. **Recovery**：重复观察、crash、换 session 或外部状态变化后，从哪里恢复？
8. **Projection**：展示面能否从 source state 重建，是否避免了反向成为事实源？

如果 capability 需要自己维护一套 runnable、ownership、retry、terminal 和 scheduler，它通常
已经偏离 capability 边界，正在形成第二个控制面。

## 课程导航

| 后续讲次 | 在 Issue-Fix 中看到什么 | 在 Auto Research 中看到什么 |
| --- | --- | --- |
| 第 1 讲 | 从目标到第一个 fix todo | 从 research question 到初始 role todo |
| 第 2 讲 | feasibility / PR lifecycle 与 Kernel state 的边界 | evidence event、graph 与 projection 的边界 |
| 第 3 讲 | patch successor、monitor、review handoff | role claim、lane successor、equal peer |
| 第 4 讲 | checks pending 为何 quiet，CI failure 为何 runnable | per-agent frontier 与 promotion gate |
| 第 5 讲 | PR monitor cadence 与外部 readback | worker loop、no-action 与重新唤醒 |
| 第 6 讲 | validation、notification receipt、terminal closeout | dev/holdout evidence、retirement 与 completion |
| 第 7、8 讲 | 增加 lifecycle rule 并证明不重复通知、不越权 | 增加 evidence rule 并证明 oracle 独立、边界 clean |
| 第 9 讲 | Capability Pack 与 Domain State | thin preset、Explore 与 multi-agent 产品层 |

## 课后检查

1. 为什么 `CHANGES_REQUESTED` 不应直接修改 Kernel todo？
2. 为什么 Auto Research 可以没有一个拥有整棵研究树的 coordinator？
3. Issue-Fix 的 PR lifecycle 与 Kernel todo lifecycle 分别拥有什么？
4. dev metric 提升后，为什么 executor 不能自行 promotion？
5. 一个新 capability 至少需要定义哪些 identity、transition、receipt 和 recovery contract？

下一讲沿同一条共同生命周期运行第一次真实 Loop：用户只表达目标后，guided start、todo、
heartbeat、quota、writeback 和 spend 怎样串成可恢复闭环。
