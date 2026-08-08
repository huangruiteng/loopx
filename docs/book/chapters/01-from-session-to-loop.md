# 从一次会话到长程任务

一个 Agent 能在当前会话里修改代码、运行测试并解释结果，不代表它能可靠地拥有一项持续数天的
工作。本章先区分 session context 与 project memory，再说明 control plane 为什么存在。

## 本章目标

读完后，你应该能：

- 指出哪些状态不能只留在 transcript 中；
- 区分 execution plane 与 control plane；
- 为一个会跨 session 的任务列出最小外置状态；
- 区分 durable project fact 与必须重新探测的 environment fact；
- 判断一个任务是否仍适合只用普通 Agent 会话。

## 贯穿全书的任务

假设你要为已有 CLI 增加 `--format json`：

1. 修改输出层；
2. 保持默认文本输出兼容；
3. 添加测试；
4. 等待 CI；
5. 交给维护者确认 JSON contract；
6. 根据反馈修订并发布。

如果所有步骤能在一次连续会话内完成，transcript 加 Git diff 通常已经够用。真实工作却经常在
第三步之后中断：上下文被压缩，CI 要等待，维护者隔天回复，另一个 Agent 接手，或者外部依赖
改变。此时“模型还记得什么”与“项目现在是什么状态”开始分离。

## Session context 是工作内存，不是账本

模型上下文适合承载：

- 当前问题的局部推理；
- 刚读取的代码；
- 本轮工具结果；
- 即将执行的短计划。

它不适合成为以下事实的唯一存放位置：

- 当前目标及验收条件；
- 哪些工作已经完成并通过了什么验证；
- 哪个动作正在等待谁的决定；
- 哪个 Agent 拥有当前任务；
- 外部写操作是否真的发生；
- 何时应该重试或停止。

原因不只是 token 有限。下面这些事件会分别破坏不同假设：

| 事件 | 被破坏的假设 |
| --- | --- |
| session 结束 | 下一轮还能直接读取全部上下文 |
| context compaction | 原始细节仍以相同强度存在 |
| 模型或 Agent 切换 | 新执行者共享原 Agent 的隐含计划 |
| 人类插入决定 | 旧计划仍然合法 |
| CI、Issue 或服务状态变化 | 旧观察仍代表当前外部事实 |
| 工具超时 | “发起了动作”等于“动作已完成” |

长程工作需要把恢复所需的最小事实外置。外置不等于保存整段对话，而是保存可供下一轮重新推导
行动的 durable project facts。恢复时还必须重新探测 checkout、Host capability 和外部服务，
因为环境事实可能在两轮之间改变：

```text
next decision =
  replay(durable project facts)
  + inspect(fresh environment)
```

Canonical state（规范状态）只拥有 LoopX 生命周期事实。Git commit、CI check 和外部资源状态仍由
对应系统拥有，LoopX 保存的是 bounded readback、revision 与 evidence pointer。

## Execution plane 与 control plane

**Execution plane（执行面）** 负责执行一个有界动作，例如：

- Agent 修改代码；
- shell 运行测试；
- provider 调用 GitHub；
- Host 启动下一次模型 Turn。

**Control plane（控制面）** 负责决定什么动作现在合法、为什么继续、何时等待，以及结果如何进入
持久状态：

- 目标和验收是否仍然有效；
- 当前 frontier 中哪个 Todo 可以执行；
- 是否存在需要用户处理的 Gate；
- 当前 evidence 能否支持状态转换；
- quota 是否允许再启动一轮；
- 中断后从哪里恢复。

```text
Control plane: 选择并约束下一步
       |
       v
Execution plane: 执行一个有界动作
       |
       v
Observation / receipt: 返回可验证结果
       |
       v
Control plane: 接受、拒绝或重规划
```

控制面不替代执行面。LoopX 不写代码、不托管 Git，也不代替 CI；它使这些系统的结果可以被一个
跨 Turn 的工作生命周期消费。

## 三类长程任务为什么能复用同一控制面

LoopX 的控制合同不绑定某一种业务流程。仓库中的 Control-Plane Course 用三类 Showcase
说明：领域事实和验收方式可以完全不同，Goal、Todo、Gate、Quota、Evidence 与恢复机制仍可复用。

| Showcase | 领域事实与判断 | 复用的控制面 |
| --- | --- | --- |
| PR Issue Fix | issue feasibility、exact-head checks、review 与 merge state | Todo、claim、workspace guard、monitor、successor、terminal closeout |
| Single-Agent Auto ML | metric contract、matched baseline、实验 revision、外部 task 与 guardrail | Quota、Provider receipt、monitor、defer/resume、promotion Gate |
| Multi-Agent Auto Research | hypothesis、dev/holdout evidence、支持或反驳关系 | per-Agent frontier、handoff、Evidence lineage、promotion/retirement |

三条产品链都可以压成同一个长期闭环：

```text
外部事实
  -> Provider observation
  -> Capability 的领域判断与 transition proposal
  -> Kernel 检查 authority、frontier、quota 与 workspace
  -> Agent / Host 执行一个 bounded Turn
  -> 独立验证、evidence 与 receipt 写回
  -> 重新计算 continue | wait | ask | replan | repair | terminal
```

复用的不是一段通用 prompt，而是生命周期不变量。Issue-Fix 可以理解
`CHANGES_REQUESTED`，Auto ML 可以理解 matched baseline，Auto Research 可以理解 holdout；
这些领域含义属于 Capability 与 Domain State。谁能 claim、是否可执行、何时再次唤醒、什么证据
允许 writeback，以及 Goal 能否终止，仍由同一 Kernel 合同决定。

这个边界也解释了为什么新增领域能力不应复制一套 runner、queue、retry 和 completion 状态机。
领域层提供可判定事实与 proposal，Provider 执行外部调用，Kernel 拥有跨领域生命周期。

需要从三个 Showcase 进入架构、源码入口和完整 case 时，继续阅读
[Control-Plane Course 第 0 讲](/loopx/docs/development/control-plane-course/00-goal-control-plane-architecture/)；
第一次接触术语时可先看[概念导读](/loopx/docs/development/control-plane-course/00-concept-primer/)。

## 哪些状态必须外置

对贯穿任务，最小状态不是完整 transcript，而是一组可回答恢复问题的事实：

```yaml
# 为解释而简化，不是 LoopX 文件格式
goal: 为 CLI 增加兼容的 JSON 输出
acceptance:
  - 默认文本输出不变
  - JSON schema 有测试
frontier:
  - todo: 等待维护者确认字段命名
    state: blocked
gate:
  question: 是否接受 error_code 作为稳定字段？
evidence:
  - unit tests passed at commit abc123
next_wake:
  when: maintainer decision arrives
```

这些字段的价值在于：下一位执行者不必相信前一位 Agent 的自述，而能从目标、工作队列、Gate、
证据和 fresh environment 重新判断下一步。示例是解释模型，不是 LoopX 的存储格式；第三章会
说明这些信息分别属于哪些协议与状态表面。

## 什么时候普通会话已经足够

不要把所有任务都升级成长程控制面。普通会话适合：

- 范围封闭；
- 能在当前上下文完成；
- 不需要等待外部事件；
- 没有跨 Agent 交接；
- 失败后可以低成本重做；
- Git diff 和测试结果足以恢复。

例如“解释这个函数”“修正一处 typo”“为纯函数补一个测试”，通常不需要项目级 Goal 和 Todo。

当任务出现以下任一条件时，再考虑持久 Goal 或 LoopX：

- 需要跨多个 Turn；
- 有依赖、并行 lane 或明确 handoff；
- 有权限边界或人类 Gate；
- 有外部 effect，需要 readback 与 receipt；
- 需要定时 monitor 或 backoff；
- 需要从另一个 Host 或 Agent 恢复。

下一章会进一步区分：普通会话、Codex Goal 与 LoopX 分别把哪些控制信息移出了当前 prompt。
