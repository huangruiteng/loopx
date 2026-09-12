# Quota Monitor Observation Receipt v0 / 配额监控观察回执 v0

## English

### Problem

A heartbeat Turn has exactly one quota settlement identity. When an
`advancement_task` is already bound to that identity, a newly due
`continuous_monitor` must not replace it. The monitor still needs a durable
observation receipt so that its cadence does not starve while long-running
advancement work remains active.

### Contract

- The heartbeat receipt's `todo_id` remains the only settlement Todo. Only
  that Todo may be used by `refresh-state` and `quota spend-slot`.
- `quota monitor-poll --todo-id <monitor>` may record one auxiliary, no-spend
  observation in the same Turn only when the requested Todo is a due
  `continuous_monitor` visible to the same Agent.
- The monitor receipt records both `settlement_todo_id` and the observed
  monitor `todo_id`. They may differ; this never grants a second delivery or
  quota-spend identity.
- A receipt-bound monitor remains strict: another monitor cannot be substituted.
  Reusing the same Turn for a different observation conflicts with the existing
  monitor-poll effect digest.
- After an unchanged auxiliary observation, the original advancement Todo
  remains selected. A material observation may create its independently routed
  successor through the existing monitor contract, but it still does not
  replace the Turn's settlement identity.

### Acceptance

The CLI path must prove that a due monitor can update its cadence and replay
idempotently without spending quota, while a guard replay continues to select
the original advancement Todo. Existing wrong-Todo tests for receipt-bound
monitor Turns must remain passing.

## 中文

### 问题

一次 heartbeat Turn 只有一个配额结算身份。当 `advancement_task` 已绑定该身份时，
新到期的 `continuous_monitor` 不得替换它；但监控仍需形成持久观察回执，否则长期
推进任务存在时，监控周期会永久饥饿。

### 契约

- heartbeat 回执中的 `todo_id` 始终是唯一结算 Todo；只有它可用于
  `refresh-state` 与 `quota spend-slot`。
- 仅当请求对象是同一 Agent 可见且已到期的 `continuous_monitor` 时，
  `quota monitor-poll --todo-id <monitor>` 才可在同一 Turn 写入一次辅助、
  不计费的观察回执。
- 监控回执同时记录 `settlement_todo_id` 与被观察的 monitor `todo_id`。
  二者允许不同，但不会因此产生第二个交付或配额结算身份。
- 若 heartbeat 本身绑定的是 monitor，仍保持严格身份，不能换成另一个 monitor；
  同一 Turn 也不能用不同观察内容覆盖既有 monitor-poll effect。
- 辅助观察无变化后，原 advancement Todo 继续保持选中；若观察发生重大变化，
  可按既有 monitor 契约创建独立路由的 successor，但仍不替换本 Turn 的结算身份。

### 验收

CLI 端到端测试必须证明：到期 monitor 能更新周期并幂等重放、全程不消耗配额；
随后重放 guard 仍选择原 advancement Todo。同时，receipt-bound monitor Turn 的
错误 Todo 替换测试必须继续通过。
