# 第 6 讲：证据、Refresh 与 Self-Repair

> 核心问题：为什么“代码改了”“todo 勾了”“agent 说完成了”都不足以证明长期目标真的推进？

建议时长：100 分钟。讲解 55 分钟、失败回放 25 分钟、实验 20 分钟。

## 学习目标

完成本讲后，开发者应该能够：

1. 区分 artifact、validation、writeback、refresh、spend 五个步骤。
2. 使用 authoritative evidence 判断 acceptance，而不是依赖 todo status。
3. 解释 projection gap、outcome floor、vision checkpoint 和 repair delta。
4. 在连续 no-progress 时执行 self-repair，而不是降低 gate。
5. 为 public/private evidence 设计安全边界和 compact lineage。

## “做了”与“控制面推进了”之间的差距

一次可靠 delivery 至少有五层：

```text
1. Artifact: 代码、文档、PR、实验结果或具体 blocker
2. Validation: smoke、test、readback、review 或可复现检查
3. Writeback: todo/evidence/successor/gate 被写入 durable state
4. Refresh: status/run history/vision/sink postcondition 得到更新
5. Spend: 只为这次 validated transition 记一次账
```

缺任一层都会出现不同故障：

| 缺失层 | 表面现象 | 长期后果 |
| --- | --- | --- |
| Artifact | “正在推进” | 没有可交付结果 |
| Validation | 文件已改 | 不知道是否满足行为 |
| Writeback | PR 已开但 todo 仍 open | 下一 peer 重复工作 |
| Refresh | todo 已变但 status/vision stale | quota 选择错误 |
| Spend | 已推进但未记账，或 no-op 也记账 | quota 失真 |

## Authoritative Evidence

Acceptance 证据应来自能直接证明结果的对象：

- changed files / commit / PR diff；
- public-safe evidence record；
- evaluation output；
- focused smoke/test；
- external authoritative source；
- successor state；
- concrete blocker/user gate；
- superseding agent vision。

以下对象单独不够：

- todo completion；
- replan ACK；
- vision checkpoint；
- assistant 的完成声明；
- 没有 acceptance evidence 的 `no_followup`。

一个好的 evidence ref 足够紧凑，可以恢复判断，又不复制 raw log：

```text
pr:2136
commit:<sha>
smoke:todo-lifecycle-cli
run:<opaque-run-id>
event:<event-id>
doc:docs/development/control-plane-course/01-first-real-loop.md
```

## Bounded Delivery 的证据标准

### 实现类

```text
changed surface
+ focused behavior check
+ boundary scan
+ successor/review state
```

### 文档类

```text
complete artifact
+ command/source cross-check
+ link/reference scan
+ intended audience acceptance
```

### Blocker 类

```text
specific blocking condition
+ attempted diagnostics
+ missing authority/capability/evidence
+ exact resume condition or user question
```

Blocker evidence 必须说明具体决定、阻塞原因和恢复动作。例如：“需要用户
决定是否允许 X，因为 Y；获得授权后执行 Z”。只写 “Owner gate” 没有提供
足够的恢复信息。

### Monitor 类

```text
target identity
+ due state
+ one poll result
+ changed/no-change classification
+ next due or successor
```

## `refresh-state` 的职责

典型调用：

```bash
loopx refresh-state \
  --goal-id <goal-id> \
  --classification validated_course_draft \
  --delivery-batch-scale multi_surface \
  --delivery-outcome outcome_progress \
  --agent-id <agent-id> \
  --vision-unchanged-reason "课程目标和验收标准未改变，本轮完成讲义内容交付"
```

Refresh 不是“刷新页面”，而是一次有语义的状态 transaction：

- 写 run classification；
- 标记 delivery scale/outcome；
- 更新 agent lane 或 goal-level progress；
- 检查 projection/sink postcondition；
- 记录 vision checkpoint decision；
- 同步 global registry（除非显式关闭）；
- 生成下一轮 quota 可见事实。

`recommended_action` 只描述 run record；要改变 durable `## Next Action`，使用 `--next-action`。

## Delivery Scale 与 Outcome Floor

Delivery scale 描述工作量形状：

- `test_only`
- `single_surface`
- `multi_surface`
- `implementation`

Delivery outcome 描述是否真正推进目标：

- `surface_only`
- `outcome_gap`
- `outcome_progress`
- `primary_goal_outcome`

一个 multi-file diff 仍可能只是 surface-only；一个很小但解开关键 blocker 的状态变更可能是 outcome progress。

Outcome floor 防止 agent 用大量微小动作伪装长期推进。连续 surface-only/no-progress 后，quota 会要求真正 outcome 或 self-repair。

## Agent Vision 与 Acceptance Gap

多 agent goal 中，每个 peer 有自己的 bounded vision。对同时承担 advancement 与
continuous monitor 的长生命周期 lane，vision 不是可有可无的说明文字，而是恢复和
replan 的基线。Agent profile 会默认把这类 lane 标成 required：

```python
def _vision_requirement(value, *, task_classes):
    requirement = str(value or "").strip().lower()
    if requirement:
        return requirement
    if {"advancement_task", "continuous_monitor"}.issubset(task_classes):
        return "required"
    return None
```

`goal_frontier.py::acceptance_gaps_from_agent_profile_requirement` 会在 required lane 缺少
vision baseline 时产生 `agent_profile_vision_missing` gap。普通 delivery 或 monitor-only
quiet 不能永久掩盖这个 gap；agent 应写入一份有界 vision，只有拥有 profile authority
的配置方才能把 lane 显式改成 optional。短期 one-shot peer 仍可预先配置为 optional，
避免把所有临时任务都包装成长计划。

一个 bounded vision packet 包含：

```text
vision summary
role scope
acceptance summary
advancement policy
replan triggers
last patch
todo delta
```

它不是另一份大计划，而是回答：

- 这个 peer 在长期目标中负责什么？
- 什么证据说明它的 lane 可以关闭？
- 哪些变化要求 replan？

Vision、Goal 与 Todo 形成一条方向到动作的约束链：

| 层 | 回答的问题 | 不直接做什么 |
| --- | --- | --- |
| Vision | 为什么长期工作、向什么标准收敛？ | 不选择本轮 todo，不授予权限 |
| Goal | 当前阶段要交付什么，边界和 acceptance 是什么？ | 不替代 runnable frontier |
| Todo | 下一步由谁在什么条件下做什么？ | 不自行改写长期方向 |

```text
Vision
  -> Goal boundary / acceptance
  -> Todo frontier
  -> bounded delivery + evidence
  -> acceptance audit
  -> continue, replan, or vision patch
```

这条链解释了为什么 Vision 应相对稳定，却不能永久冻结：用户方向变化、验收标准
被证伪、长期 frontier 耗尽或持续局部最优时，需要一个有明确 delta 的 patch。
反过来，新增一个 todo 不等于 Vision 已变化。

`loopx/control_plane/goals/goal_vision.py::normalize_goal_vision_packet`
把这种边界编码成 compact、public-safe、agent-scoped packet：

```python
if packet_goal_id and packet_goal_id != goal_id:
    raise ValueError(
        f"agent_vision goal_id {packet_goal_id!r} does not match {goal_id!r}"
    )

if agent_id and packet_agent_id and packet_agent_id != agent_id:
    raise ValueError(
        f"agent_vision agent_id {packet_agent_id!r} does not match {agent_id!r}"
    )

if not vision_patch:
    raise ValueError("agent_vision must include at least one bounded vision field")

if total_usage > GOAL_VISION_TOTAL_LIMIT:
    raise GoalVisionBudgetError(
        field="total_agent_vision",
        used=total_usage,
        limit=GOAL_VISION_TOTAL_LIMIT,
    )
```

这里的 identity check 防止一个 peer 覆盖另一个 lane，budget 防止 Vision 退化成
第二份 transcript。`examples/project/goal-vision-refresh-state-budget-smoke.py`
同时验证写入正确性、预算与 repair delta。

当 material refresh 没有 vision patch 或 unchanged reason 时，CLI 会产生 `vision_checkpoint_missing` acceptance gap。Todo 即使完成，也不能直接 terminal。

修复选择有三种：

1. 写一个 bounded vision patch；
2. 明确记录 vision unchanged reason；
3. 用 evidence 关闭或 supersede 该 vision frontier。

不要为了消除 warning 随便写“unchanged”。Reason 必须与本轮 acceptance 事实一致。

## Signal、Anchor 与 Feedback 不直接变成 Todo Truth

长期管理面的输入不只有已有 todo，还包括 issue、PR、review、chat feedback、文档
变化和外部 monitor。合理的产品链路是：

```text
signal
  -> classify and attribute
  -> select a bounded anchor
  -> materialize todo / gate / monitor
  -> deliver and collect evidence
  -> performance review
  -> explicit priority, gate, or vision writeback
```

这是管理面整理 signal 的分析顺序，不是 LoopX 中另一套独立状态机。持久化和执行
权限仍由现有 Core State 合同负责：

- 外部消息到达不等于用户已授权执行；
- 被认为“有价值”的 signal 不等于已进入 runnable frontier；
- raw feedback 不直接覆盖 Vision，必须形成明确 source、scope 和 delta；
- performance review 可以影响下一轮优先级，但仍要通过 todo/gate/vision API 写回。

开发 connector 或 inbox 时，应先把 signal 归一化为 public-safe evidence，再由
现有 Core State 承接 anchor。第 9 讲的 Lark Event Inbox 展示了这一边界；不要
为每种外部信号新增一个 quota 分支。

## Replan 与 Dreaming

Replan 是当前目标图上的机器可见变化：

- 新增/删除/重排 todo；
- 修改 gate/blocker；
- 写 successor/supersede；
- 改 acceptance/vision；
- 修复 capability/workspace route。

Dreaming 是探索未来可能性，可以产生 proposal，但不能替代当前 runnable frontier。

一个 replan 只有在 `repair_delta_kind` 指明变化时才清除 obligation：

```bash
loopx refresh-state \
  --goal-id <goal-id> \
  --classification control_plane_repaired \
  --autonomous-replan-recorded \
  --repair-delta-kind runnable_todo_set \
  --repair-delta-kind successor_or_supersede \
  --agent-id <agent-id>
```

只有 ACK，没有 delta，是 `replan_noop`。

## Projection Gap 的 Self-Repair

常见 gap：

### User todo 计数有值但 payload 缺失

输出：

```text
具体 user todo 未投影，需修复 LoopX 状态投影
```

修复：重建结构化 user todo / operator gate，不猜问题。

### Claimed todo gate 后饿死未认领 advancement todo

根因：调度错误地把 goal 级 `claimed_by` 当成全局执行者筛选。

修复原则：

- claimed todo 仍只唤醒 owner；
- unclaimed advancement todo 唤醒所有未被 `excluded_agents` 排除且满足 capability/workspace 的 peer；
- peer 自己 claim，内核不替它决定永久 owner。

### Projection failure 每轮重复写相同日志

根因：错误没有稳定 identity/dedup，heartbeat cadence 又过快。

修复：按 sink、goal、revision、error family 去重；状态未变时只 backoff，不每轮追加 payload。

### Todo 全 done 但 terminal 不成立

检查：

- active monitor；
- successor/handoff；
- acceptance gap；
- replan obligation；
- sink retry；
- blocker/resume route；
- nofollowup evidence。

## 两轮无推进后的 Self-Repair

规则不是“第二轮就随便换方向”，而是系统性审计：

```text
1. 重新读 exact quota interaction_contract
2. 读 agent-scoped evidence log
3. 比较最新 run 和当前 selected todo
4. 检查 projection、claim、lease、capability、workspace、gate
5. 判断是执行问题、状态问题还是 host 问题
6. 写一个 machine-visible repair delta
7. 运行 focused validation
8. refresh and spend only if material progress exists
```

Self-repair 不允许：

- 降低安全 gate；
- 猜测缺失 payload；
- 把 private raw logs 提交到 public repo；
- 用 destructive git 清理不明改动；
- 把 no-progress 改名成 success。

## 失败回放：漏写 Vision Checkpoint

用第 1 讲的贯穿实验复现。以下 id 都是占位符：

```text
goal_id = <goal-id>
agent_id = <agent-id>
```

第一阶段创建四个 ordered todo：

```text
<todo-evidence> 取证机制地图
<todo-design>   设计 9 讲认知梯度
<todo-writing>  撰写 9 份 Markdown
<todo-verify>   交叉校验与交付说明
```

在 todo 刚写入后运行了一次 material `refresh-state`，但没有写 `--vision-unchanged-reason`。下一次 quota 正确返回：

```text
vision_continuation_audit.decision = acceptance_gap_open
gap.kind = vision_checkpoint_missing
closeout_allowed_without_evidence = false
```

注意：系统仍允许继续已 claim 的课程 todo，因为 gap 要求的是在 closeout 前补齐 acceptance 判断，而不是把所有 delivery 都停掉。

正确修复不是删除 gap，而是在讲义完成和验证后写：

```bash
--vision-unchanged-reason \
  "9 讲课程目标、受众与验收未改变；本轮完成全部讲义并以当前 CLI/smoke 交叉验证"
```

这条回放说明 vision checkpoint 是长期 acceptance 的闭环，不是形式化打勾。

## 多 Monitor 交错时的停滞证据

`consecutive_no_change` 属于 monitor target，不属于整个 goal，也不属于 run-history
末尾的一段文本模式。设 M1、M2 交错轮询：

```text
M1 no-change -> M2 no-change -> M1 no-change -> M2 no-change
```

若 detector 只数相邻 run，M1 和 M2 会互相打断；若任一 monitor 有 material change 就
清空全局 streak，又会让活跃 M2 永久掩盖停滞 M1。正确 writeback 是：

```text
M1 todo.consecutive_no_change += 1
M2 todo.consecutive_no_change += 1
material change on M2 -> reset M2 only
```

Quota 从 `monitor_open_items` 读取每条 lane 的 durable counter。任一 lane 达到阈值且
没有 same-agent runnable advancement 时，`monitor_no_change_streak` 形成 replan 证据；
replan 应选择 watch expiry、明确 blocker、supersede monitor 或创建 runnable successor，
而不是再做一次 quiet poll。若存在 same-agent runnable advancement，advancement 优先，
但 blocked advancement 不能冒充可执行工作来压掉 replan。

这个例子同时说明了三件事：evidence 必须归属稳定 identity；聚合 read model 不能覆盖
per-lane truth；replan detector 与工作选择 precedence 必须在同一 fixture 中验证。

### Run History 还要按 Agent Lane 归因

Monitor target 的 counter 解决了 M1/M2 互相清零，但 multi-agent goal 还有第二层归因：
另一个 peer 的新 run 也不能打断当前 peer 的 blocked-successor 或 no-progress streak。
当前实现先从最新可归因 run 选择 accountable agent，再保留该 lane 与 goal-level neutral
runs：

```python
accountable_agent_id = next(
    (
        _run_history_agent_id(run)
        for run in latest_runs
        if str(run.get("classification") or "").strip()
        not in neutral_classifications
        and _run_history_agent_id(run)
    ),
    None,
)

if not accountable_agent_id:
    return [run for run in latest_runs if isinstance(run, dict)]

scoped_runs = [
    run for run in latest_runs
    if isinstance(run, dict)
    and _run_history_agent_id(run) in {None, accountable_agent_id}
]
```

保留 `agent_id=None` 的 neutral run 是为了兼容真正的 goal-level 事实；选择最新
attributable lane 则防止 peer B 的 monitor poll 重置 peer A 的停滞计数。若没有可唯一选择
的 accountable lane，早退分支保留全部结构化 run，后续规则继续依据显式 agent scope
判断，而不是丢弃可能相关的证据。对应回归位于
`tests/control_plane/test_goal_vision_blocked_successor.py`。

### 外部条件满足后仍要重新计算 Frontier

`deferred` todo 的 `resume_when=pr_merged:<ref>` 不会因为人看到 PR 已合并就自动完成。
公开 merge event 先满足 `resume_condition`，projection 再写出 `resume_ready=true`：

```python
condition.update(pr_merged_condition(
    target,
    rollout_events,
    task_repository=item.get("task_repository"),
))
item["resume_ready"] = bool(condition.get("satisfied"))
```

恢复后的正确动作也不一定是重复实现。Quota 重新暴露 successor，agent 比较 merge
evidence、acceptance 与当前代码；若目标已由其他路径满足，可以用证据记录
`no_followup` replan delta。这个过程把“外部条件满足”“todo 可恢复”“还需不需要工作”
分成三次可审计判断，避免 deferred work 永久沉睡，也避免 merge 后重复开工。

## Public/Private Evidence Boundary

公开课程只保留 generalized、public-safe 的 product behavior、占位 id 和 opaque evidence ref。以下内容不应写入课程、fixture 或公开 PR：

- credential/token/cookie；
- 可复用认证材料；
- private transcript 或 raw log；
- 真实线程与真实 goal/agent/todo id；
- 本机绝对路径与私有文档链接；
- destructive command recipe；
- 未授权生产操作。

## Sink Postcondition

当 Explore Graph 或外部 sink 启用时，material refresh 还可能要求：

```text
canonical local projection updated
  -> external sync executed
  -> row/result id readback verified
  -> semantic digest advanced
```

失败时 digest 不前进，下一次 refresh 重试。若本轮无权写外部 sink：

```bash
loopx refresh-state ... --suppress-external-sinks
```

这允许更新 canonical local state，但必须留下 authorized-sync successor；不能把 suppressed delivery 称为完整 sink success。

## 实验：修复一个 No-op Replan

在实验 goal 中：

1. 创建一个没有 successor 的 blocked todo；
2. 运行 quota，记录 repair/replan obligation；
3. 只运行 `--autonomous-replan-recorded`，观察 obligation 不应清除；
4. 添加具体 successor 或 resume condition；
5. 再运行 refresh，并声明对应 `repair_delta_kind`；
6. 检查 quota 是否看到新 frontier。

示例：

```bash
loopx refresh-state \
  --goal-id <lab-goal> \
  --classification lab_replan \
  --autonomous-replan-recorded \
  --repair-delta-kind successor_or_supersede \
  --agent-id <lab-agent> \
  --vision-unchanged-reason "lab acceptance remains unchanged"
```

## 核心代码领读：从“我做了”到可归因的 refresh 与 spend

把这一讲看成一条 proof pipeline：

```text
work effect
  -> machine-visible delta
  -> refresh-state run record
  -> projection/readback
  -> focused validation
  -> spend-slot 绑定最新未消费 delivery run
```

### 1. Repair 不能只写 classification，必须带 delta

`loopx/state_refresh.py::build_repair_delta_contract` 只承认真正的状态变化：

```python
delta_kinds = list(requested_delta_kinds)
if active_state_next_action_update.get("updated") is True:
    delta_kinds.append("active_state_next_action")
    evidence.append({"source": "refresh_state_next_action_update", ...})
if agent_vision:
    delta_kinds.append("goal_vision_patch")
    evidence.append({"source": "refresh_state_agent_vision", ...})

return {
    "required": True,
    "delta_present": bool(delta_kinds),
    "delta_kinds": delta_kinds,
    "accepted_without_delta": False,
}
```

`--autonomous-replan-recorded` 只是声明，不会自动制造 delta。没有 successor、resume condition、Next Action 或 vision patch 时，refresh 应降级为 `replan_noop`/`repair_noop`，而不是清除 obligation。

### 2. Vision checkpoint 防止“局部推进，目标悄悄漂移”

`build_vision_checkpoint` 先从 material outcome、replan 和 durable Next Action 生成 triggers：

```python
required = bool(triggers or unchanged_reason)
if agent_vision:
    decision, satisfied = "patched", True
elif unchanged_reason and existing_agent_vision:
    decision, satisfied = "unchanged_with_reason", True
elif delta_kinds & {"no_followup", "successor_or_supersede"}:
    decision, satisfied = "retired_or_superseded", True
elif required:
    decision, satisfied = "missing_required", False
else:
    decision, satisfied = "not_required", True
```

`vision_unchanged_reason` 只有在已有 baseline 时才诚实；没有 baseline 却声称 unchanged，会得到 `missing_required`。这迫使 agent 明确：是更新目标、证明目标未变，还是用 successor/no-followup 关闭当前 vision。

### 3. Refresh 对 multi-agent attribution fail closed

`refresh_state_run` 在任何写入前先验证身份与 scope：

```python
registered_agents = registered_agents_for_goal(registry_goal)
multi_agent_goal = len(set(registered_agents)) > 1

if normalized_agent_id and normalized_agent_id not in known_agents:
    raise ValueError("agent_id ... is not registered")
if multi_agent_goal and not normalized_agent_id:
    raise ValueError(
        "multi-agent refresh-state requires --agent-id; text inference is disabled"
    )

if normalized_progress_scope == "agent_lane":
    if not normalized_agent_id:
        raise ValueError("--progress-scope agent_lane requires --agent-id")
    if normalized_next_action:
        raise ValueError(
            "agent-lane refresh-state cannot update the durable active-state Next Action"
        )
```

这里区分两种 write authority：

- `agent_lane` 可记录本 peer 的进展、evidence 与 vision；
- `goal` scope 才能改变共享 durable Next Action。

不能用自然语言从 classification 猜“这是哪个 agent 做的”。

### 4. Projection gap 把 prose 漂移升级成 repair

`loopx/control_plane/quota/projection_repair.py::build_state_projection_gap_repair_hint` 的输入来自第 2 讲的 status projection。当 active prose 看起来可执行、结构化 agent todo 却为零时，它返回 self-repair hint，而不是让 quota 安静等待。

领读时追这条反向路径：

```text
ACTIVE_GOAL_STATE.md prose
  -> state_projection_gap_warning
  -> status.project_asset.state_projection_gap
  -> build_state_projection_gap_repair_hint
  -> quota effective_action=self_repair
  -> 写回 concrete todo / user gate / successor
```

修复结束的证据不是“重新跑 quota 了”，而是 gap 消失且新 projection 可 read back。

### 5. Spend 再次验证 delivery workspace

`loopx/control_plane/quota/slot_accounting.py` 不直接消费“最近一次 run”，而是找最新未 spend 的 accountable delivery run，并验证其 workspace snapshot：

```python
delivery_completion_run = _latest_unspent_accountable_delivery_run(
    runtime_root,
    goal_id,
    agent_id=requested_agent_id,
)
delivery_workspace = (
    raw_delivery_workspace
    if delivery_workspace_repository(raw_delivery_workspace)
    else None
)
delivery_workspace_guard = build_delivery_workspace_guard(
    delivery_completion_run,
    agent_id=requested_agent_id,
)
if delivery_workspace_guard:
    return {
        "ok": False,
        "appended": False,
        "reason": delivery_workspace_guard["reason"],
        "delivery_workspace_validated": False,
    }
```

这形成因果闭环：quota 在 delivery 前要求正确 worktree，refresh 把 credential-free workspace identity 记入 run，spend 再检查当前 agent/repository 是否与该 run 一致。换目录后直接 spend 应被拒绝。

### 6. 一次自修复应怎样收口

```text
发现异常
  -> 读取 status/quota/history，不先 spend
  -> 分类为 behavior / projection / authoring / host / harness drift
  -> 在最低层写 concrete delta
  -> refresh-state 记录 repair outcome + vision checkpoint
  -> 重读 projection，运行能捕获该问题的 focused smoke
  -> 只在 accountable delivery 后 spend 一次
```

自修复应落在产生错误决策的最低层。如果机器 projection 误导 agent，应修复
CLI/status/quota 并补 smoke；只更新文档不会改变机器的下一次决策。

### 断点练习

1. 只传 `--autonomous-replan-recorded`，观察 `delta_present=False`。
2. multi-agent goal 不传 `--agent-id`，确认 refresh 在写文件前失败。
3. 用 `agent_lane` 同时传 `--next-action`，确认共享状态写入被拒绝。
4. 在一个 worktree refresh，切到另一个 checkout preview spend，观察 workspace guard。

### 读完这一段应能回答

1. classification、delta、evidence 各自证明什么？
2. 为什么 vision unchanged 需要已有 baseline？
3. agent-lane refresh 为什么不能更新共享 Next Action？
4. projection gap 修复完成的 readback 条件是什么？
5. spend 如何绑定 agent、repository 与具体 delivery run？

## 代码阅读路线

1. `loopx/state_refresh.py`
2. `loopx/control_plane/runtime/run_history.py` 与 `loopx/rollout_event_log.py`
3. `docs/reference/protocols/goal-vision-replan-contract-v0.md`
4. `docs/reference/protocols/agent-scoped-evidence-ledger-v0.md`
5. `docs/interaction-pattern-catalog.md` 的 IP-005、IP-007、IP-008、IP-013、IP-024
6. `skills/loopx-self-repair/SKILL.md`

## 代表性 Smoke

- `examples/state-projection-gap-smoke.py`
- `examples/project/goal-vision-replan-contract-smoke.py`
- `examples/control_plane/agent-scoped-evidence-log-smoke.py`
- `examples/outcome-followthrough-policy-smoke.py`
- `examples/control_plane/monitor-poll-policy-smoke.py`

## 课后检查

1. Todo done 为什么不是 acceptance evidence？
2. Refresh 和 spend 分别证明什么？
3. Vision unchanged reason 什么时候是诚实的？
4. Repair delta 必须改变哪些 machine-visible 对象？
5. 外部 sink 被 suppress 后，什么 successor 必须保留？

下一讲进入 contributor 视角：如何从状态定义到 smoke，给 control plane 增加一条真正可维护的规则。
