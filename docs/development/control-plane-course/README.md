# LoopX Control-Plane Developer Course / LoopX 控制面开发者课程

这套 8 讲课程面向准备修改 LoopX kernel、CLI、状态投影、调度或扩展能力的开发者。主目标是建立一条可执行的控制面心智模型：用户的一句目标如何变成可领取工作，状态如何写回，quota 为什么允许或拒绝下一轮，host 又如何安全地把决策变成周期执行。

课程不是 API 枚举。每一讲都包含四类材料：

- 一条真实 CLI 或状态执行路径；
- 一组核心代码领读入口，说明调用顺序、关键分支和不变量；
- 一个公开 smoke、测试或实验，用来验证理解；
- 一组 review 问题，帮助开发者判断改动应落在哪个 bounded context。

## 课程地图

| 讲次 | 主题 | 读完应能回答 |
| --- | --- | --- |
| [第 1 讲](01-first-real-loop.md) | 从 Showcase 到第一次真实 Loop | 用户只说一句目标后，guided start、todo、heartbeat、quota、refresh 和 spend 如何串起来？ |
| [第 2 讲](02-state-substrate.md) | 状态底座与可重放事实 | registry、event、active state、run history 和 projection 分别拥有什么事实？ |
| [第 3 讲](03-work-graph-and-peers.md) | Todo 工作图与 Peer 协作 | equal peer 如何 claim、handoff、处理 capability/workspace gate，而不恢复 primary/side 层级？ |
| [第 4 讲](04-quota-decision-kernel.md) | Quota 决策内核与 Interaction Contract | `should-run` 如何把复杂状态压成 deliver、wait、ask、repair 或 quiet？ |
| [第 5 讲](05-host-scheduler-and-heartbeat.md) | Host、Heartbeat 与 Stateful Backoff | LoopX 决策、heartbeat prompt、Codex App RRULE 和 ACK 各自负责什么？ |
| [第 6 讲](06-evidence-refresh-and-self-repair.md) | 证据、Refresh 与 Self-Repair | 什么算 material progress，何时必须 replan，连续无推进如何形成可验证 repair delta？ |
| [第 7 讲](07-engineering-a-control-plane-rule.md) | 如何给 Control Plane 增加一条规则 | 如何从 invariant、schema、transition、projection 到 smoke 完成一次规则变更？ |
| [第 8 讲](08-extension-layer.md) | 扩展层、Explore 与 Multi-Agent 产品 | 默认关闭的 Explore Graph、Harness、Auto Research 和 Supervisor 如何复用 kernel？ |

## 建议学习方式

第一次阅读按 1 到 8 的顺序进行。第 1 讲建立端到端路径，第 2 到 6 讲拆开状态、工作图、决策、host 和证据，第 7 讲把这些知识收束成工程变更方法，第 8 讲再看扩展层。

不要从模块文件头一路向下读。每讲的“核心代码领读”会给出函数级入口，先搜索目标函数，再沿 bounded-context helper 向下读。运行实验时使用临时 goal 和测试仓库，不要把课程占位 id 当作真实配置。

## 版本与边界

课程以仓库当前 `main` 的公开 CLI、协议文档和 smoke 为准。代码移动后，应在同一个 PR 中更新函数路径和阅读顺序；行为变化后，应先更新 canonical contract 或 focused test，再调整课程解释。

课程不承载真实线程、私有 todo、内部文档、本机路径、raw transcript、凭证或生产操作记录。需要讲解真实故障时，只保留能复现状态机的最小 public-safe fixture。

继续开发前还应阅读：

- [Developer guide](../README.md)
- [Testing and quality](../testing-and-quality.md)
- [Core control-plane graphs](../../product/core-control-plane/README.md)
- [Public/private boundary](../../public-private-boundary.md)
