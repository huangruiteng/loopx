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
- `quota monitor-poll --todo-id <monitor>` may record auxiliary, no-spend
  observations in the same Turn only when each requested Todo is a due
  `continuous_monitor` visible to the same Agent. Admission checks the Todo
  authority as well as the bounded decision projection, so a due monitor is
  not rejected merely because it falls outside the compact list.
- The monitor receipt records both `settlement_todo_id` and the observed
  monitor `todo_id`. They may differ; this never grants a second delivery or
  quota-spend identity.
- Each auxiliary observation has an operation identity scoped by the monitor
  Todo, or by a digest of `target_key` when there is no Todo id. Exact retries
  replay that observation; changed content conflicts only with the same monitor
  identity; another due monitor receives an independent no-spend receipt.
  Shipped turn-only receipts remain replayable for their original monitor.
- A receipt-bound monitor remains strict: another monitor cannot be substituted
  for the Turn's settlement Todo. Multiple auxiliary receipts never change the
  already-bound settlement identity.
- After an unchanged auxiliary observation, the original advancement Todo
  remains selected. A material observation may create its independently routed
  successor through the existing monitor contract, but it still does not
  replace the Turn's settlement identity.

### Acceptance

The CLI path must prove that multiple due monitors can each update their cadence
and replay idempotently in one settlement Turn without spending quota, while a
guard replay continues to select the original advancement Todo. Existing
wrong-Todo tests for receipt-bound monitor Turns must remain passing.

## 中文

### 问题

一次 heartbeat Turn 只有一个配额结算身份。当 `advancement_task` 已绑定该身份时，
新到期的 `continuous_monitor` 不得替换它；但监控仍需形成持久观察回执，否则长期
推进任务存在时，监控周期会永久饥饿。

### 契约

- heartbeat 回执中的 `todo_id` 始终是唯一结算 Todo；只有它可用于
  `refresh-state` 与 `quota spend-slot`。
- 仅当每个请求对象都是同一 Agent 可见且已到期的 `continuous_monitor` 时，
  `quota monitor-poll --todo-id <monitor>` 才可在同一 Turn 写入辅助、不计费
  的观察回执。准入同时检查 Todo 权威源与有界决策投影，不能仅因到期 monitor
  位于精简列表之外就拒绝它。
- 监控回执同时记录 `settlement_todo_id` 与被观察的 monitor `todo_id`。
  二者允许不同，但不会因此产生第二个交付或配额结算身份。
- 每个辅助观察按 monitor Todo 建立操作身份；没有 Todo id 时，按
  `target_key` 摘要建立身份。精确重试只重放该观察；同一 monitor 下内容变化
  只与该 monitor 冲突；另一个到期 monitor 获得独立的不计费回执。已发布的
  Turn-only 旧回执仍可对原 monitor 重放。
- 若 heartbeat 本身绑定的是 monitor，仍保持严格身份，不能把另一个 monitor
  替换为本 Turn 的结算 Todo；多个辅助回执也绝不改变既有结算身份。
- 辅助观察无变化后，原 advancement Todo 继续保持选中；若观察发生重大变化，
  可按既有 monitor 契约创建独立路由的 successor，但仍不替换本 Turn 的结算身份。

### 验收

CLI 端到端测试必须证明：多个到期 monitor 能在同一结算 Turn 中分别更新周期并
幂等重放、全程不消耗配额；随后重放 guard 仍选择原 advancement Todo。同时，
receipt-bound monitor Turn 的错误 Todo 替换测试必须继续通过。
