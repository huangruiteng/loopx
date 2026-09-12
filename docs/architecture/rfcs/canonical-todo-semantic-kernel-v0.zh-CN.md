# RFC：Canonical Todo 语义内核与读模型收敛（v0）

- 状态：实现提案
- 提议者：LoopX maintainers
- 日期：2026-09-12
- 范围：收敛 TypeScript authority 路径与 Python projection 共用的 Todo
  语义规则，建立在 [TypeScript Control-Plane Migration v0](typescript-control-plane-migration-v0.md)
  与 [Shared Goal Authority and Pluggable State Providers v0](shared-goal-authority-state-provider-v0.md)
  之上
- 交付形态：先提供一个保持兼容的 Python 语义内核，再为 TypeScript 事务路径
  增加语言中立的 conformance packet
- 语言说明：[英文版本](canonical-todo-semantic-kernel-v0.md) 与本文必须语义镜像；
  存在差异即为缺陷。

## 1. 问题

两份父 RFC 已经把 authority 与事务所有权逐步收敛到 TypeScript，但 Todo
消费者仍然保留了多份相同规则。`todos/projection.py` 负责任务分类、优先级、
monitor eligibility、claim visibility 和 frontier 选择；
`todos/todo_summary.py` 又重新包装了其中多数函数，并且刻意只用 `text` 做分类。
agent scope、quota preparation、Goal Frontier、work-lane selection 和 capability
fallback 也各自导入或包装了其中一部分。

因此出现两类漂移：同一 Todo 在 projection 和 summary 路径上可能得到不同分类；
修复一条规则时，必须重复修改多个 facade。最直观的失败是只有
`title="Observe build health"` 而 `text` 为空的 monitor：projection 能识别，summary
却可能把它当成 advancement。`excluded_agents` 也有同样风险：一个调用方读
frontier，另一个调用方从 summary bucket 重建，结果可能不一致。

## 2. 决策

新增 `loopx.control_plane.todos.todo_semantics`，作为 provider-neutral Todo 读语义的
唯一 Python owner。它负责：

- task text 与 task-class 解析；
- open/actionable/deferred 状态；
- monitor 到期、过期、缺少 schedule；
- priority 提取、排序与稳定顺序；
- claim、排除与已移除 continuation 的 eligibility；
- claimed visibility 与 advancement frontier 分区。

`todos/projection.py` 保留为兼容导出，供旧扩展继续使用，但不再包含独立规则实现。
新的生产代码直接导入 `todo_semantics`。`todo_summary.py` 继续负责 summary 组装、
压缩和展示限制，但所有语义 predicate 都调用内核。

内核按 `title`、`text` 的顺序组合任务文本；显式持久化的 `task_class` 仍然优先于
文本推断。这样修复只有 title 的 Todo，同时保留现有显式分类和 action-kind 推断。

coordination provider 仍然只是 storage/CAS 边界。内核不成为 writer、receipt authority、
scheduler 或 provider adapter。TypeScript authority 仍是父 RFC 定义的事务 owner；本 RFC
只删除重复的 Python read policy，让下一步 TypeScript cutover 可以比较一份语义 packet。

## 3. 语义变化与修复

### 3.1 分类现在识别 title

所有 Python 读路径统一使用 `(title, text)`。显式 `task_class` 仍优先。只有 title 的
monitor 会在 status、quota、Goal Frontier 和 summary 中保持 monitor 分类。这是行为修复，
不是重命名。

### 3.2 排除属于 eligibility，不属于 ownership

`excluded_agents` 在 claim ownership 之后判断。一个未 claim 的 Todo 可以对某个 Agent 可见，
同时对另一个 Agent 不可执行；排除不会制造 claim、lease 或 authority 授权。内核提供单一
predicate，确保 frontier count 与 selected id 不再分叉。

### 3.3 稳定排序只有一套规则

priority 和 index 在同一个 owner 中解析。缺失或非法 priority 继续使用现有 projection 的
有界 rank。兼容 facade 保留旧 import 路径和调用签名，生产调用方迁移到内核。

### 3.4 展示限制不改变语义

内核不会把截断列表当成完整 Todo 集合。summary 可以限制展示行数，但 count、frontier
分类和 coordination digest 继续使用完整 source 或明确 qualification 的 canonical projection。

## 4. 所有权与非目标

本 RFC 只负责读语义，不会：

- 修改默认 provider、提升 SQLite/NoKV/PostgreSQL，或迁移现有 Goal；
- 新增 lease、receipt、scheduler 或网络 authority；
- 把 Markdown 变成 generated source of truth；
- 从 `goal_bound`、actor identity 或 title 文本推断用户批准；
- 在 extension inventory 与 TypeScript conformance packet 完成前删除兼容 import。

能力 owner 仍是现有 Todo/control-plane contract；不创建新 capability 或 provider package。

## 5. 迁移计划

1. **内核抽取（本阶段）。** 将 projection 规则移动到 `todo_semantics.py`，把
   `projection.py` 改成兼容导出，迁移生产 import，保留外部路径。
2. **Summary 收敛（本阶段）。** 删除 `todo_summary.py` 只使用 text 的特例；summary 的
   限制与压缩仍留在自身。
3. **Fixture conformance（本阶段）。** 扩展 deterministic production-scale fixture，加入
   title-only monitor、未 claim 但排除某 Agent 的 advancement、显式 global gate（不依赖
   goal binding）和过期 lease。这些都是合成声明，不复制真实 Goal 状态。
4. **TypeScript packet（下一阶段）。** 把相同 semantic cases 放入语言中立 contract，
   在删除更多 Python adapter 前比较 TypeScript 与 Python 的分类和选择结果。
5. **兼容层退休（后续）。** 完成 extension import audit 后，在一次有披露的 release 中
   弃用 `projection.py`，确认没有受支持调用方后再删除。

每一步都可回滚：可以恢复 import-only facade，不触碰 provider selector 或持久化 revision。

## 6. 验证契约

聚焦 Python 测试必须覆盖 title-aware classification、monitor due、exclusion/ownership 分离
和 fixture edge 声明。既有 projection、canonical-governance、frontier、long-history 测试
必须继续通过。TypeScript typecheck 以及 coordination/monitor/quota 测试也必须通过，因为
fixture 同时被两套 runtime 使用。

真实本机读回保持只读：

```bash
loopx --format json status --goal-id loopx-meta
loopx --format json todo list --goal-id loopx-meta --role agent --status open
```

第一条命令检查 live registry/runtime contract；第二条通过公共 Todo surface 检查 live Goal
仍可读。两条命令都不会写 Goal、改变 lease 或提升 provider。失败时应阻止交付，不能削弱
fixture 或 gate。

## 7. 验收标准

- `projection.py` 不再含独立语义实现；
- 所有生产 import 使用 `todo_semantics` 或 summary assembler；
- title-only monitor 同时通过 direct 与 summary 路径；
- complex fixture 确定、public-safe，并被现有 TypeScript conformance 测试消费；
- Python 聚焦测试、TypeScript typecheck/tests、`git diff --check` 与只读 `loopx-meta` 命令通过；
- 不提交私有 Goal 状态、凭据、原始 run log、本机绝对路径或生成物。

## 8. 重复清单

本 RFC 前的重复主要是结构性重复，不只是相同代码文本：

| 区域 | 重复知识 | 后果 |
| --- | --- | --- |
| `projection.py` 与 `todo_summary.py` | task classification、actionable status、priority、monitor predicate | title/text 分歧，修复要重复做 |
| agent scope 与 quota preparation | actionable/classification 的本地 wrapper | 调用方可能使用不同 helper 默认值 |
| Goal Frontier 与 work-lane consumer | claim/exclusion 与 frontier 分区 | count 与 selected id 可能不一致 |
| Python projection 与 TypeScript transaction consumer | canonical Todo 字段与 provider read-model shape | migration 需要多处比较点 |

前 3 行由本 RFC 收敛；第 4 行仍是下一阶段的跨语言 conformance 任务。本 PR 不声称删除
TypeScript authority，也不改变 provider 语义。

## 9. 未决问题

- 哪一个受支持 extension release 可以停止 import `projection.py`？
- TypeScript packet 应从 coordination state contract 生成，还是保持独立版本的 semantic fixture？
- 在不惊动本地 plugin 的前提下，退休兼容 facade 需要哪些证据？

这些问题不阻塞本次 read-policy 收敛，因为 facade 保留了现有 public import surface。
