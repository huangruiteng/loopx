# 类型化日期恢复触发器 v0

状态：已实现契约

## 目的

`resume_at` 为 Todo 提供一个精确、机器可读的一次性恢复时刻，而不新建第二套
调度器或消息队列。它归属现有 `resume_when`，并与其他类型化恢复条件共用
active-state、quota、托管 Turn、前端和 Lark 投影链路。

## 写入

Token 格式为：

```text
resume_at:<timezone-aware-rfc3339-timestamp>
```

例如：

```text
resume_at:2026-09-14T09:30:00+08:00
resume_at:2026-09-14T01:30:00Z
```

边界要求完整日历日期、秒，以及 `Z` 或不大于 `14:00` 的显式时区偏移；无时区
本地时间和非法日期都会被拒绝。等价时刻在持久化前统一规范为 UTC，不推断
“明早”之类自然语言。

## 求值与回执

一次 active-state 投影为所有日期 Todo 复用同一个 `evaluated_at` 运行时时钟快照。
在计划时刻之前，条件包含：

- `satisfied=false`；
- `material_change=false`、`material_change_generation=0`；
- `clock_provider=runtime_clock`；
- 无恢复回执。

到达或超过计划时刻后，条件包含：

- `satisfied=true`；
- `material_change=true`、`material_change_generation=1`；
- `generation_fence=once_at_or_after_scheduled_for`；
- 根据 Todo id 和规范化条件生成的 `todo_resume_receipt_v0`。

回执的 `triggered_at` 是计划时刻，而非本次观察时刻。因此重复 tick、后续读取和
进程重启都会得到同一回执，generation 不会超过 `1`。

## 消费方行为

- CLI 在写入前校验，并回读规范化的 UTC token。
- Status 与 quota 在未来时刻到来前不把 Todo 放入可执行队列；是否继续其他工作
  仍由既有 fallback 策略决定。
- 到期后 quota 返回既有 `successor_replan_required` 生命周期动作。回执只证明
  条件发生转换，不授予执行权限，也不会隐式 reopen Todo。
- 托管 Turn 解释同一个 quota packet；heartbeat 不拥有独立定时器或 readiness
  缓存。
- 前端在既有 Todo 延后/详情入口展示 pending、ready 和回执，不新增配置真相源。
- Lark 无需条件专属状态 owner；Goal Channel 消费同一 status/interaction 投影，
  并可通过既有 presentation sink 展示回执。

本协议不改变定期周报策略、调度频率或用户的通知偏好。

## 验收

1. 带 offset 的输入回读为等价 UTC token；无时区或非法输入在写入前失败。
2. 到期前，CLI、quota 与托管 Turn 一致判定为等待。
3. 到期时，各入口一致得到 `successor_replan_required` 和同一回执身份。
4. 后续 tick 与新进程精确复现该回执。
5. 前端 typecheck、route smoke 与打包构建通过。
