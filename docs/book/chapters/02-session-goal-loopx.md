# 普通会话、Codex Goal 与 LoopX

这三者不是互斥产品，而是不同层次的状态与责任。选择的关键不是“哪个更强”，而是你的任务需要
把多少控制信息移出当前会话。

## 本章目标

读完后，你应该能：

- 说明普通会话、Codex Goal 与 LoopX 各自拥有的状态；
- 从五类可观察行为解释 LoopX 在 Goal 之上增加了什么；
- 用任务资格卡判断是否值得引入长程控制面；
- 根据当前 Host 的真实唤醒与 writeback 表面选择启动方式；
- 判断什么时候 Codex Goal 已经足够；
- 解释 LoopX 与 Codex Goal 如何组合。

## 三层状态

| 层次 | 主要拥有的状态 | 主要解决的问题 |
| --- | --- | --- |
| 普通 Agent 会话 | 当前 transcript、工具结果和本轮计划 | 完成一次上下文内的推理与执行 |
| Codex Goal | Host/thread 上持久的 objective 与 Goal lifecycle | 让同一 Host 围绕目标继续 Turn，并判断 active、blocked 或 complete |
| LoopX | 项目拥有的 Goal、Todo、Gate、Evidence、Quota 与恢复状态 | 组织跨 session、Agent、Host 和外部系统的可审计生命周期 |

LoopX 不复制 Host 的模型执行，也不把 Codex Goal 降级为一个 prompt 技巧。Host Goal 负责“继续
围绕目标运行”，LoopX 负责“从项目状态编译出当前合法的一轮工作”。

## 四类 Actor

为了避免把产品、模型和状态系统都叫作“Agent”，先固定四类责任：

| Actor | 主要拥有 | 不应拥有 |
| --- | --- | --- |
| User / operator | 方向、私有材料、凭据、production、public claim 等边界决定 | 每个普通 Todo 的人工调度 |
| Host | session、模型 Turn、visible TUI 或 heartbeat 等唤醒表面 | 项目长期事实和自定义状态机 |
| Executor / Agent | 当前 Turn 的推理、工具调用、bounded delivery 与验证 | 隐式长期记忆和越权批准 |
| LoopX control plane | Goal、Todo、Gate、quota、evidence lineage、recovery protocol | 模型推理、Git/CI 外部事实 |

Dashboard、review packet 和 prompt 是 projection/interaction surfaces，不是第五个 authority。

## 三种身份必须分开

LoopX 同时处理 Goal、Agent 和 Host，但三者回答的是不同问题：

| 身份 | 回答的问题 | 稳定性与选择规则 |
| --- | --- | --- |
| `goal_id` | 正在推进哪个长期项目边界？ | 绑定 registry、Todo、Gate 和 evidence lineage；复用时选择已有的精确 id |
| `agent_id` | 当前由哪个 peer/lane 承担工作？ | 绑定 claim、Vision、quota 与 writeback；新接入默认注册 fresh identity |
| `host_surface` / runtime profile | 这一轮实际由哪个产品表面执行和唤醒？ | 绑定 App heartbeat、visible Goal 或其他 host loop；必须按当前运行面显式声明 |

已有 Goal 可以继续复用，不代表新 session 应接管已有 Agent identity。最新 Goal-start 合同要求：

1. 多个已注册 Goal 同时存在时，先返回只读 `goal_selection_gate`，再以精确 `--goal-id` 重跑；
2. 不根据相似的 objective、聊天摘要或目录名猜测 Goal；
3. 新的 argument-bearing `start-goal --guided` 未指定 `--agent-id` 时，即使只有一个已注册 Agent，
   也默认进入 fresh identity registration；
4. 只有用户明确要求接管某个已有 Agent，才以该精确 `agent_id` 继续；
5. Agent 名称或前缀不证明 Host，实际运行面要由 host/runtime metadata 说明。

这样，“继续同一个项目”与“冒充上一个执行者”不会被压成同一操作。

## 任务资格卡：先判断是否值得使用 LoopX

LoopX 不是“任务越大越应该用”的同义词。先把任务写成一张可审查的资格卡：

这张卡是本书提供的决策工具，不是 LoopX CLI schema，也不会被 `start-goal` 自动写入状态。
真正进入 LoopX 的 Goal、Todo、Gate、acceptance 和 boundary 仍以当前协议与 CLI 为准。

| 字段 | 要回答的问题 | 不满足时的默认选择 |
| --- | --- | --- |
| `duration` | 是否会跨 session、等待窗口或工作日？ | 普通会话 |
| `external_wait` | 是否要等待 CI、review、审批或外部资源？ | 普通会话或 Host Goal |
| `handoff` | 是否会更换 Agent、Host、设备或责任人？ | 同一 Host Goal |
| `authority` | 是否涉及 private read、凭据、production 或 external write？ | 先定义 Gate，不要启动自动执行 |
| `acceptance` | 什么可观察证据足以判断完成？ | 先补验收，不能只写“持续优化” |
| `baseline` | 和普通会话或 Host Goal 比较时，什么保持一致？ | 不做效果提升 claim |
| `stop_condition` | 何时完成、阻塞、降级或停止投入？ | 先补 terminal contract |

满足一项不代表必须使用 LoopX。真正有价值的组合通常是：跨 session + 有外部等待或 handoff +
有独立 acceptance，并且项目需要把 authority、evidence 和恢复条件外置。

### 如何比较普通会话、Goal 与 LoopX

如果要判断 LoopX 是否提升了真实任务，不要比较两个不同任务或不同预算。至少保持：

```text
same task semantics
same runner / model / reasoning settings
same verifier contract
same time and cost budget
```

记录 completion、独立 verifier、错误写入、人工介入、stop-policy、wall time 和 cost。没有 matched
baseline 或独立 verifier 时，可以记录使用体验，不能声称产品能力提升。

[`release_outcome_baseline_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/release-outcome-baseline-v0.md)
进一步规定正式 release qualification 比较的是 **稳定 LoopX release 与 candidate revision**；
它明确不把 native Agent 与 LoopX treatment 的对比当作 release promotion evidence。后者可以是
产品研究，但必须单独说明 arm semantics，不能借用 release qualification 的结论强度。

## 用同一任务比较

仍以“为 CLI 增加 JSON 输出”为例。

### 普通会话

你对 Agent 说：

> 增加 `--format json`，保持默认输出兼容并补测试。

Agent 可以读取代码、修改文件和运行测试。如果 session 在等待 CI 时结束，恢复者通常只能依赖
Git diff、CI 和人类重新描述。下面这些信息可能只存在于对话中：

- 为什么选择当前 schema；
- 是否还在等维护者决定；
- 哪个失败是预期的；
- 哪个动作尚未真正发生。

### Codex Goal

Codex Goal 把 objective 和 Goal lifecycle 从单次 prompt 中分离。Host 可以围绕同一目标启动
后续 Turn，并在目标处于 active、blocked 或 complete 时采取不同动作。

因此，等待 CI 后继续工作不再要求用户重新粘贴完整目标。Goal 解决的是 **Host 内目标连续性**。
它不必自动成为项目 Todo 图、权限账本或跨 Host registry。

!!! warning "以当前 Host 为准"
    只在普通 prompt 中写 `/goal` 不等于建立了 Host 可读回的持久 Goal。具体入口、状态和恢复操作
    必须以当前 Codex 产品表面为准。

### LoopX

LoopX 在项目侧保存更细的控制合同。例如：

```text
Goal: ship-compatible-json-output
├── Todo A: implement formatter              done
├── Todo B: add schema tests                 done
├── Todo C: obtain field-name decision       blocked by Gate G
└── Todo D: release                          deferred until C

Gate G
├── scope: response.error_code
├── authority: maintainer
└── blocks: Todo C
```

下一轮不只知道“目标还没完成”，还知道：

- 哪个 Todo 可执行；
- Gate 只阻塞哪条 lane；
- 哪个 Agent 持有 claim 或 lease；
- 哪份测试结果是 evidence；
- 发布是否需要外部 effect receipt；
- 当前是否应该运行、等待或 monitor。

## LoopX 增加的五类项目合同

### 1. Todo、claim 与 handoff

Goal 表达项目结果，Todo 表达可调度的工作单元。LoopX 可以为 Todo 记录优先级、依赖、claim、
lease、successor 和 handoff。Per-Agent Vision 则保存某个 peer 当前的 bounded role direction、
acceptance summary 与 replan trigger；它不是另一个 Goal，也不是全局产品愿景。

这使“目标仍 active”与“当前谁可以做哪件事”成为两个问题。Agent id 是工作身份，不是 Host
身份；`codex-*` 前缀也不能证明任务实际运行在 Codex App 还是 CLI。新 session 可以复用同一
Goal 的历史与 frontier，同时以 fresh Agent identity 进入；已有 claim 则通过显式 takeover 或
handoff 处理。

### 2. Gate 与 authority

对话可以向人提问，但一个问题是否阻塞所有工作、只阻塞一个 Todo，或者只是一条提醒，需要
明确建模。

LoopX 区分：

- `user_gate`：缺少决定时相关工作不能合法继续；
- `user_action`：需要人处理，但不必阻塞 Agent 的其他 lane；
- safe fallback：不依赖该决定、仍可安全执行的工作。

Gate 的重点不是“让人参与”，而是把决定的 scope、authority 和被阻塞工作绑定起来。

### 3. Evidence 与 receipt

“Agent 运行了命令”不是“状态转换已被证明”。LoopX 区分：

- proposal：建议做什么；
- observation：看到了什么；
- validated evidence：经过检查、可以支持结论的证据；
- effect readback：外部系统返回的当前事实；
- receipt：对一次已接受动作的持久记录。

例如发起 `git push` 后网络超时，不能仅凭工具调用开始就标记发布完成。需要远端 readback 或
其他可验证 receipt。

### 4. Scheduler、monitor 与 quota

Codex Goal 可以由 Host 继续。LoopX 进一步把“现在是否应该继续”变成项目决策：

- `quota should-run`：这一轮是否符合预算与状态；
- monitor：外部条件未变化时静默等待；
- scheduler hint：Host 应在什么节奏再次唤醒；
- backoff：连续无变化时避免盲目轮询；
- spend：只有产生并写回有界进展后才记账。

Host 仍然拥有实际唤醒机制。LoopX 输出调度合同，不假装自己是所有 Host 的 scheduler。

### 5. 跨 Agent、跨 Host 与恢复

LoopX 的 canonical state 属于项目。Codex App、Codex CLI 或其他受支持 Host 可以读取同一个
Goal 边界，而不是各自维护一份“当前进度”。

```text
Codex App heartbeat ─┐
Codex CLI Goal ──────┼──> LoopX project state ──> current Turn packet
Other host hook ─────┘
```

Host 可以不同，项目状态不能分叉成多个事实源。恢复依赖 event、lineage、projection、fresh
environment read 与 replan，而不是要求新 Host 继承旧 transcript。下一章会先拆开这些状态表面，
再进入工作图与 Turn protocol。

## Host 兼容矩阵

LoopX 保留同一 control-plane contract，但不同 Host 的启动和唤醒机制并不相同。当前公开
[Runtime Connector Catalog](https://github.com/huangruiteng/loopx/blob/main/docs/integrations/runtime-connector-catalog.md)
给出的主要路径是：

| Host surface | 驱动 | 关键限制 |
| --- | --- | --- |
| Codex App | `$loopx <task>` + App heartbeat | cadence 需要 RRULE apply/readback/ACK |
| Codex App over SSH | visible `/goal` | 不依赖 App automation tools |
| Codex CLI TUI | generated bootstrap + visible `/goal` | 保持 visible、interruptible |
| Claude Code | `/loopx` + opt-in native `/loop` adapter | 仍走同一 quota/writeback |
| OpenCode | `/loopx` + opt-in Goal bridge | Todo 写回后还需 bridge activation |
| Shell / other Agent | guided packet + caller-owned runner | 无 runner hook 时由调用方唤醒 |

表中出现一个 Host 不代表所有 Host 都支持相同 automation API。`host_surface` 未知时，应省略一次
该参数并使用只读 selection Gate；不要把 Codex CLI、IDE plugin、App SSH 或普通 shell 猜成
Codex App heartbeat。

## 如何组合 Codex Goal 与 LoopX

典型组合是：

1. LoopX 从项目状态选择 Todo，检查 Gate、能力与 quota；
2. LoopX 生成有界 task body 或 decision packet；
3. Codex Goal 持续承载这个 Host 上的执行；
4. Agent 完成一段工作并验证；
5. 结果写回 LoopX，LoopX 再决定下一轮。

```text
LoopX control plane -> Codex Goal continuation -> Agent Turn
        ^                                      |
        `---------- validated writeback -------'
```

因此，Codex Goal 与 LoopX 的关系更像 Host lifecycle 与 project lifecycle 的组合，而不是两套
互相替代的 Agent runtime。

## 选择哪一层

| 任务特征 | 建议起点 |
| --- | --- |
| 单次、封闭、可低成本重做 | 普通会话 |
| 同一 Host 内需要持续目标和 lifecycle | Codex Goal |
| 有项目 Todo、权限 Gate、外部 effect、跨 Agent/Host 或调度恢复 | LoopX，可与 Codex Goal 组合 |

选择最小足够层次。控制面本身也有维护成本；没有项目级问题时，不要为了“更 Agentic”而制造状态。
