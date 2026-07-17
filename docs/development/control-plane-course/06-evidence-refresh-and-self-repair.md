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

“Owner gate”不是 blocker evidence；“需要用户决定是否允许 X，因为 Y，解除后执行 Z”才是。

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

多 agent goal 中，每个 peer 可以有自己的 bounded vision：

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

当 material refresh 没有 vision patch 或 unchanged reason 时，CLI 会产生 `vision_checkpoint_missing` acceptance gap。Todo 即使完成，也不能直接 terminal。

修复选择有三种：

1. 写一个 bounded vision patch；
2. 明确记录 vision unchanged reason；
3. 用 evidence 关闭或 supersede 该 vision frontier。

不要为了消除 warning 随便写“unchanged”。Reason 必须与本轮 acceptance 事实一致。

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
<todo-design>   设计 8 讲认知梯度
<todo-writing>  撰写 8 份 Markdown
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
  "8 讲课程目标、受众与验收未改变；本轮完成全部讲义并以当前 CLI/smoke 交叉验证"
```

这条回放说明 vision checkpoint 是长期 acceptance 的闭环，不是形式化打勾。

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

“更新文档说以后注意”通常不是最低层修复；如果机器 projection 误导 agent，应修 CLI/status/quota 并补 smoke。

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
