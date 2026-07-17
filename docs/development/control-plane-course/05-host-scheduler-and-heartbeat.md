# 第 5 讲：Host、Heartbeat 与 Stateful Backoff

> 核心问题：LoopX 不执行模型 turn，那么长期循环到底由谁拉起？如何避免空转、刷盘、过快轮询和错误停机？

建议时长：90 分钟。讲解 55 分钟、时序推演 20 分钟、实验 15 分钟。

## 学习目标

完成本讲后，开发者应该能够：

1. 区分 host trigger、heartbeat task body 和 LoopX decision kernel。
2. 解释 thin prompt 为什么比项目专属大 prompt 更可靠。
3. 读懂 scheduler hint、stateful backoff 和 bound ACK。
4. 区分 quiet skip、monitor poll、wait、run-now 和 terminal stop。
5. 设计一个不会重复 spend、不会无限刷盘的 host adapter。

## Host 是触发器，不是第二控制面

LoopX 支持多种 host：

| Host surface | 如何开始 | 谁持续触发 |
| --- | --- | --- |
| Codex App | `$loopx <task>` | App heartbeat automation |
| Codex CLI | 生成 thin task body，设置可见 goal/session | 用户或 CLI 可见循环 |
| Claude Code | `/loopx <task>`，可选 native loop adapter | Claude native loop 或用户 |
| 其他 shell/agent | `start-goal --guided` | 外部 runner 或人工触发 |

Host 负责：

- 创建或恢复 executor turn；
- 传入 LoopX 生成的 task body；
- 声明 host capability；
- 应用 scheduler cadence；
- 返回真实 effect receipt。

Host 不负责：

- 自己解析 todo 选择 runnable；
- 自己决定 user gate 是否阻塞；
- 把 model output 当 execution receipt；
- 在本地 prompt 中复制 quota 状态机。

## Thin Heartbeat Prompt

命令：

```bash
loopx heartbeat-prompt \
  --thin \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --agent-scope "<registered host lane>"
```

实现入口是 `loopx/heartbeat_prompt.py::build_heartbeat_prompt`。Thin body 只保留生命周期不变量：

```text
CLI is source of truth
inspect registry / status / history / repo
run exact quota should-run
follow interaction_contract
apply scheduler_hint
write plans/done into LoopX state
spend only after validated writeback
safe P1/P2 may continue when permitted
monitor quiet skips do not spend
stop at private/credential/destructive/unauthorized boundaries
```

项目专属 watch 不应写进 generic heartbeat prompt。例如“每轮看 PR #123”应建模成 `continuous_monitor` todo，带 target、cadence 和 due time。

## 一次 Heartbeat Turn 的 Host 时序

```text
Codex App automation fires
  -> opens/resumes target thread
  -> executor reads thin task body
  -> executor runs quota should-run with same agent identity
  -> interaction_contract determines this turn
  -> agent performs bounded work or quiet action
  -> durable writeback and validation
  -> spend once if allowed
  -> host applies scheduler hint
  -> host records bound ACK when required
```

Agent identity 必须从 prompt、quota、todo writeback 到 spend 保持一致。不能用 agent-a 的 quota，写 agent-b 的 todo，再用无 agent id 的 spend。

## Scheduler Hint 是派生协议

Scheduler 根据已经解析的 lifecycle 状态决定下一次 cadence，不应独立做业务推理。

典型 action class：

| 状态 | 建议初始/最大 cadence | 含义 |
| --- | --- | --- |
| runnable active work | 约 3m / 10m | 尽快继续，但允许渐进退避 |
| user wait | 约 30m / 120m | 等用户，不高频打扰 |
| reassigned/handoff | 约 10m / 60m | 给新 peer 反应时间 |
| material monitor | 约 15m / 60m | 按外部证据节奏检查 |
| fresh evidence wait | 约 60m / 240m | 没有新证据前低频 |
| quiet wait | 约 30m / 120m | 保持 alive，不制造噪声 |
| terminal no-followup | stop | 完整 closure 后停止 |

具体值由当前 schema 和配置决定，上表用于理解类别，不应复制到另一个 hard-coded scheduler。

## Stateful Backoff

固定 2 分钟 heartbeat 会产生两个问题：

- 有工作时可能太慢；
- 等用户或外部证据时会反复空转、刷日志和占用模型。

Stateful backoff 保存同一等待身份的连续轮次，逐步增加间隔。当状态变化时 reset。

可以把 identity key 理解成：

```text
goal + agent + lifecycle reason + selected work/wait target
```

当 key 不变：

```text
3m -> 5m -> 10m
30m -> 60m -> 120m
```

当 todo、gate、evidence、monitor due state 或 agent lane 变化时，backoff 应重置到新类别的初始 cadence。

## 为什么需要 Scheduler ACK

模型输出“已将 automation 改成 30 分钟”不是执行证据。App 必须实际更新 RRULE，随后运行 CLI 给出的 ACK：

```bash
loopx quota scheduler-ack-current \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --surface codex_app \
  --state-key scheduler_hint.codex_app.stateful_backoff \
  --applied-rrule 'FREQ=MINUTELY;INTERVAL=30' \
  --execute
```

ACK 绑定：

- goal；
- agent；
- host surface；
- scheduler state key；
- 实际 applied RRULE。

这样下一轮能够区分：

```text
hint proposed
host update attempted
host update applied
CLI acknowledged exact applied state
```

Scheduler ACK 本身不构成 delivery，不 spend。

## Monitor 的 Quiet Contract

`continuous_monitor` 是最容易产生空转的 lane。

### 未到期

```text
next_due_at > now
```

行为：不 poll，保持 automation active，按 due time/backoff 唤醒，不 spend。

### 到期且状态变化

做一次 bounded external evidence poll，写入新 evidence，并根据结果：

- 完成 monitor；
- 创建/unblock successor advancement todo；
- 更新 next due；
- 形成 blocker/user gate。

有 material writeback 时才 spend。

### 到期但状态未变

最多一次 poll，记录 compact no-change 或更新 due/backoff，然后 quiet。不要每次 heartbeat 重复写完全相同的失败日志。

### 连续无推进

连续两轮 no-progress 应触发 self-repair：

- cadence 是否过快？
- target key 是否稳定？
- 外部证据是否可订阅而非轮询？
- 是否缺少 successor/resume condition？
- projection 是否一直失败？

## Projection 失败日志去重

本地异常如果每 2 秒写一条相同日志，会带来：

- event ledger 噪声；
- status 变慢；
- 真实新错误被淹没；
- automation 被误判为“持续有进展”。

合理的错误身份应包含：

```text
projection/sink + goal + stable error family + affected revision
```

相同身份在没有状态变化时只更新 backoff 或 compact count，不反复追加等价 payload。新 source revision、error family 或修复结果出现时再记录新事件。

## Stop 的严格条件

Host 只有在 CLI 派生 `terminal_no_followup` 时才应自动停止。它至少要求以下 frontier 全部关闭：

- open agent todo；
- open user gate/action；
- due 或 active monitor；
- pending successor/handoff；
- replan obligation；
- acceptance/vision gap；
- retryable projection/sink postcondition；
- unresolved blocker/resume route。

因此：

```text
open todo count == 0
```

只是必要条件之一，不是充分条件。

`terminal_no_followup` 是 LoopX 自己派生的 runtime closure，不是用户自定义 status，也不应由 host 根据自然语言猜测。

## Codex App 与 Codex CLI 的不同

### Codex App

- 有 heartbeat automation；
- host 可以更新 RRULE；
- task body 绑定目标 thread；
- scheduler hint 可要求 App update + ACK。

### Codex CLI

- 当前可见 session 通常由用户启动；
- LoopX 提供 bootstrap message / thin task body；
- CLI 不应假设用户安装的 `/loopx` 自定义命令一定可用；
- final-check/self-stop 通过当前可用 host surface 完成。

两者共享同一个 quota/status/todo state kernel，不应复制两套 lifecycle。

## Host Capability 与 Effect Receipt

有些动作需要 host 才能执行，例如：

- session message injection；
- session termination；
- state fork；
- workspace transfer；
- visible TUI pane launch。

Control plane 的正确关系是：

```text
typed proposal
  -> host checks declared capability and authority
  -> host performs effect
  -> host returns typed result
  -> LoopX records capability-matched receipt
```

缺 capability 时 proposal 保持未执行。不能把 model response 当 host receipt。

## 实验：推演 Cadence，不修改 App

### 1. 生成 thin prompt

```bash
loopx heartbeat-prompt \
  --thin \
  --goal-id <lab-goal> \
  --agent-id <lab-agent> \
  --agent-scope "training heartbeat lane"
```

找出 prompt 中真正长期稳定的 6 条规则。

### 2. 读取 scheduler hint

```bash
loopx --format json quota should-run \
  --goal-id <lab-goal> \
  --agent-id <lab-agent> \
  --available-capability shell \
  | jq '{interaction_contract, scheduler_hint, automation_liveness}'
```

不要在课堂实验中实际更新个人 App automation。只回答：

- action class 是什么？
- `apply_needed` 是否为 true？
- spend policy 是什么？
- state identity 何时 reset？

### 3. 构造 monitor 状态表

手工推演四种输入：未到期、到期有变化、到期无变化、连续无变化。为每种情况写出：

```text
poll? / write? / spend? / next cadence? / automation active?
```

## 核心代码领读：LoopX 决策怎样变成 host cadence

这一讲最容易把三件事混在一起：heartbeat prompt、scheduler hint、host automation。先画清权责：

```text
heartbeat_prompt  生成“下一轮怎么问 LoopX”的通用任务体
quota              生成当前轮的执行义务
scheduler_hint     把义务投影成 cadence/backoff 建议
host               真正修改 RRULE、触发 session
scheduler_ack      证明 host 应用了哪个 RRULE
```

### 1. Scheduler hint 是纯 projection

`loopx/control_plane/scheduler/scheduler_hint.py::build_scheduler_hint` 的 docstring 就是边界：

```python
def build_scheduler_hint(payload, *, scheduler_execution_context=None, ...):
    """Project host-runtime cadence/backoff policy from a quota decision.

    This helper is intentionally pure: callers provide the few quota-local
    classification facts it needs, and it returns the public scheduler contract
    without reading files, mutating state, or depending on the full quota module.
    """
    execution_context = resolve_scheduler_execution_context(
        scheduler_execution_context
    )
    if not execution_context.ok:
        return {
            "action": "repair_scheduler_execution_context",
            "spend_policy": "no quota spend for scheduler context repair",
            "codex_app": {"apply": "none", "host_action": "none"},
            ...,
        }
```

纯函数意味着它不能声称“RRULE 已更新”。它只能返回 `apply_needed`、推荐 interval、reset token 和 ack plan；effect 必须由 host 执行。

### 2. Stateful backoff 的 identity 不只是 goal id

源码构建的 identity keys 包含：

```python
base_identity_keys = [
    "goal_id",
    "agent_identity.agent_id",
    "effective_action",
    "heartbeat_recommendation.recommended_mode",
    "interaction_contract.mode",
    "recommended_action",
]
```

只要工作身份发生 material 变化，backoff progression 就应 reset。否则“等待同一个外部结果的第 5 次 poll”和“刚切换到新 runnable todo 的第一次执行”会错误共享慢 cadence。

### 3. ACK 校验的是当前 hint，不接受任意 host 回报

`build_scheduler_ack_plan` 逐层比对 state identity：

```python
if not agent_id:
    return {"ok": False, "reason": "... requires --agent-id"}
if not stateful_backoff:
    return {"ok": False, "reason": "... no ... stateful scheduler packet"}
if stateful_backoff.get("state_key") != state_key:
    return {"ok": False, "reason": "--state-key does not match ..."}
if reset_token and reset_token != stateful_backoff.get("reset_token"):
    return {"ok": False, "reason": "--reset-token does not match ..."}
if identity_signature and identity_signature != stateful_backoff.get("identity_signature"):
    return {"ok": False, "reason": "--identity-signature does not match ..."}

if not apply_needed and not ack_needed:
    return {"ok": True, "already_applied": True, ...}
if not applied_rrule:
    return {"ok": False, "reason": "... requires --applied-rrule ..."}
```

ACK 不是 delivery，所以不 spend；但没有 ACK，下一轮也不能把“建议值”当成“宿主实际值”。

### 4. Monitor writeback 用 result hash 区分观察与推进

`loopx/control_plane/scheduler/monitor_poll_writeback.py` 是 no-change backoff 的具体落点：

```python
safe_result_hash = str(result_hash or "").strip()
if not safe_result_hash:
    raise ValueError("monitor todo writeback requires --result-hash")
if not material_change and not effective_next_due_at:
    raise ValueError(
        "unchanged monitor todo writeback requires --next-due-at or a parseable cadence"
    )

consecutive_no_change = (
    0
    if material_change or (previous_hash and previous_hash != safe_result_hash)
    else previous_no_change + 1
)
monitor_metadata = {
    "last_checked_at": generated_at,
    "result_hash": safe_result_hash,
    "consecutive_no_change": str(consecutive_no_change),
    "material_change": "true" if material_change else "false",
    "next_due_at": effective_next_due_at,
}

if material_change and next_agent_todo:
    add_goal_todo(..., task_class="advancement_task", ...)
if material_change and next_user_todo:
    add_goal_todo(..., task_class="user_gate", ...)
```

四个不变量：

1. 每次 poll 必须有稳定 `result_hash`；
2. unchanged poll 必须给出下次 due，不能形成热循环；
3. hash 改变或 material change 会把连续无变化计数清零；
4. 只有 material change 能创建 successor todo。

因此“看了一眼但没变化”通常是 no-spend observation；“新证据改变 frontier 并写回 successor”才可能成为 accountable delivery。

### 5. 一次真实 host 循环

```text
App tick
  -> heartbeat prompt 要求先 quota should-run
  -> quota 返回 interaction_contract + scheduler_hint
  -> 若 apply_needed: host 更新 RRULE
  -> host 用 scheduler-ack-current 写回实际 RRULE
  -> 若 agent.must_attempt: 执行 bounded work
  -> refresh-state 写回 outcome
  -> validation 通过后 spend 一次
```

在课堂上故意制造一个 unchanged monitor，确认链路在 monitor writeback 后结束，没有虚假的 refresh/spend。

### 断点建议

- `build_scheduler_hint:774`：观察非法 execution context 如何 fail closed；
- `build_scheduler_ack_plan:410`：依次改错 state key、reset token、identity signature；
- `write_monitor_poll_todo_state:98`：比较 hash 相同、hash 变化、显式 material change；
- host adapter：确认只有 host 层真正调用 automation update。

### 读完这一段应能回答

1. 为什么 scheduler hint 不能证明 RRULE 已应用？
2. 为什么 ACK 不消耗 delivery slot？
3. 哪些字段变化应 reset stateful backoff？
4. unchanged monitor 为什么必须写 `next_due_at`？
5. automation 为什么在 quiet wait 时仍可能保持 active？

## 代码阅读路线

1. `docs/heartbeat-automation-prompt.md`
2. `docs/long-task-cadence-policy.md`
3. `loopx/heartbeat_prompt.py`
4. `loopx/control_plane/scheduler/`
5. `loopx/quota.py` 的 final composition：interaction contract、scheduler hint、protocol action packet
6. `docs/product/core-control-plane/state-machine.md` 的 Scheduler/Heartbeat 状态机

## 代表性 Smoke

- `examples/control_plane/heartbeat-quota-flow-smoke.py`
- `examples/control_plane/quota-scheduler-state-ack-smoke.py`
- `examples/control_plane/interaction-scheduler-authority-smoke.py`
- `examples/control_plane/monitor-scheduler-contract-smoke.py`
- `examples/control_plane/quota-terminal-no-followup-smoke.py`

## 常见实现错误

### Automation prompt 携带项目专属 watch

把 watch 写成 monitor todo，让 heartbeat 保持通用。

### 更新 RRULE 后不 ACK

下一轮无法证明 host 实际应用了哪个 cadence。

### Quiet no-op 也 spend

会让配额账和真实推进失去关系。

### `should_run=false` 就停 automation

等待用户、未到期 monitor 和 evidence backoff 都需要继续存活。

### 把 launcher 称为 supervisor agent

Auto Research 的 tmux launcher 只是 host launcher，不是拥有 todo 决策权的 leader agent。可选 peer supervisor 是另一套 proposal-only overlay。

## 课后检查

1. Thin prompt 为什么不能替代 quota decision？
2. Stateful backoff 的 reset key 应包含哪些信息？
3. 为什么 scheduler ACK 不 spend？
4. Monitor no-change 时怎样避免刷盘？
5. Host 自动停止前必须检查哪些 closure 面？

下一讲关注一个长期系统最难的部分：如何证明真正推进过，以及状态漂移后如何自修复。
