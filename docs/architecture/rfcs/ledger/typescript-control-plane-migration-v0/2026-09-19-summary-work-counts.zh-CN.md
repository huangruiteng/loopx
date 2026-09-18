# 摘要工作计数消费者闭合（2026-09-19）

| 边界 | 交付证据 |
| --- | --- |
| 目标 | 总纲 R5/S2、TS T3、shared-authority L5；基线 `96d98f3d4`。 |
| 可观察缺口 | 完整来源中 21 条可执行推进 Todo 因 backlog 展示上限被下游报成 8 条，quota 压缩进一步缩小数量；另一旧路径把未看到的任务猜成 advancement。 |
| 唯一 owner | `todos/summary_lanes.ts` 批量选择 lane 并计算裁剪前数量；已有 quota selection 在 Agent 筛选后复用计数 owner。Python 保留规范化、时间／展示适配及索引回读，删除原 lane 选择和隐藏任务推断循环。 |
| 语义修复 | list/status/quota 压缩保留完整计数；重复投影保留来源不完整状态；矛盾旧片段不能证明完整，未知任务不再被推断为可执行。canonical `todo list` 保留同版本 acceptance 限制，与 status 一致但不隐藏受阻记录。 |
| 兼容 | 除已声明新增计数，基线／候选的完整 role 与作用域摘要一致；完成／延期约定、排序、Monitor 时间规则及 successor／closure 策略保留。空 canonical 来源仍有权威性，provider 不可用时不回退 Markdown。 |
| 真实路径 | File/SQLite CLI、wheel 安装后的 CLI／真实 Chat HTTP、隔离真实 PostgreSQL authority/service 读取；两种完整合成记录 schema 与授权冻结图快照。原 head/Todo/lease 及独立展示字节不变。 |
| 成本 | 双 role 摘要增加两次紧凑索引规划请求，没有逐 Todo RPC、新持久队列或 provider 状态。Python 完整摘要 adapter 仍有其他规则／效果调用，不能整体删除。 |
| 剩余 | 本次只闭合 L5 计数消费者；永久投影新鲜度、其他 T3 来源、event caller、执行器 effect fence、D2 容量／真实时间 soak 及 D3 集成晋升仍未完成。不改变默认 provider，也不宣称旧 writer 已退出。 |

[读取合同](../../../../reference/todo-work-counts.md)说明字段、公有读取命令、
不完整来源语义和回滚边界。
