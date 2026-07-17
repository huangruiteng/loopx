# 第 3 讲：Todo 工作图与 Peer 协作

> 核心问题：LoopX 没有永久 leader，多个 peer 如何知道“谁做什么、什么时候能做、做完交给谁”？

建议时长：100 分钟。讲解 60 分钟、状态机推演 20 分钟、实验 20 分钟。

## 学习目标

完成本讲后，开发者应该能够：

1. 区分 agent todo、user gate、user action、monitor 和 blocker。
2. 解释 claim、task lease、workspace guard 和 capability gate 的不同职责。
3. 正确建模 blocked P0 与可执行 P1/P2 的并存。
4. 使用 successor、supersede、continuation policy 和 no-followup 关闭工作图。
5. 解释为什么当前运行时只有 equal peer，没有 primary/side 概念。

## 从 Todo 列表升级为工作图

普通 checklist 只有文本和完成状态。LoopX todo 还承载路由语义：

```text
identity + role + priority + task_class + action_kind
+ claimed_by / lease
+ required_capabilities
+ required_write_scopes / task_repository
+ decision scopes / gate links
+ successor / supersede / resume condition
+ evidence / completion rationale
```

因此 todo 集合不是按顺序执行的脚本，而是当前 goal 的可计算 frontier。

## 两类 Owner 与五类 Task Class

### Todo role

| Role | 含义 |
| --- | --- |
| `agent` | 可由注册 peer 推进的工作 |
| `user` | 需要用户判断或行动的工作 |

### Task class

| Task class | 是否可执行 | 用途 |
| --- | --- | --- |
| `advancement_task` | 是 | 直接推进目标的实现、研究、验证、文档 |
| `user_gate` | 否，由用户解决 | 阻塞某个 scope 的方向、权限或风险决策 |
| `user_action` | 否，由用户解决，但可不阻塞 agent | 用户可见的非阻塞行动 |
| `continuous_monitor` | 仅到期时做一次只读 poll | 持续等待 PR、证据或外部状态 |
| `blocker` | 否 | 已知阻塞事实和恢复条件 |

最常见错误是把所有等待都写成 `advancement_task`，导致 quota 不断唤醒 agent 去“再看一下”。Monitor 和 blocker 必须有不同的调度语义。

## Priority 不是隐藏工作流

Todo 文本通常带 `[P0]`、`[P1]`、`[P2]`。Priority 影响候选排序，但不是唯一决策：

```text
priority
+ gate scope
+ claim/lease
+ capability availability
+ workspace compatibility
+ resume condition
+ peer exclusions
= runnable frontier
```

所以一个 P0 可以 blocked，同时一个完全独立的 P1 仍然 runnable。

### Blocked P0 的正确模型

```text
P0 agent todo requires decision scope X
  <- user_gate provides X

P1 agent todo does not depend on X
```

quota 可以同时返回：

- `user_channel.action_required=true`，列出具体问题 X；
- `agent_channel.must_attempt=true`，要求推进 P1；
- `safe_bypass_allowed=true`，说明旁路边界。

这不是矛盾，而是双通道控制。

## Equal Peer Runtime

当前 live runtime model 是 `peer_v1`：

- 所有 registered agents 是平等身份；
- 没有永久 primary agent；
- 没有永久 side agent；
- todo claim 和 continuation policy 决定当前工作归属；
- task-scoped coordination 不授予 durable authority；
- 旧 hierarchy 字段只允许存在于 exactly-once migration reader。

对应实现是 `loopx/control_plane/agents/runtime_model.py`。它只暴露 `AgentRuntimeModel.PEER_V1`。

为什么这样设计？

如果把“主/副”写成长期身份，容易把 review、merge、quota 和 user gate 权限隐式绑定到某个人。Peer 模型要求每次权力都来自当前 todo、明确 policy 或用户 gate，便于审计和替换 executor。

## Claim：软所有权

```bash
loopx todo claim \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --claimed-by agent-a
```

Claim 的作用是减少重复劳动，告诉其他 peer 当前谁在推进。

它不表示：

- agent-a 获得 repo 的无限写权限；
- agent-a 可以修改另一个 todo；
- agent-a 可以越过 user gate；
- agent-a 永久拥有 successor；
- 其他 peer 不能做独立 todo。

Claim 可以过期、清除、被 completion/supersede 结束。Status 会投影 stale claim 提示。

## Lease：有时间边界的执行占用

Task lease 比 claim 更适合需要排他执行或外部资源的工作：

```text
claim: 谁打算负责这个 todo
lease: 谁在一段 TTL 内占用这个执行机会或资源
```

Lease 丢失应 fail closed。一个 worker 不应该在 lease 过期后继续静默执行，再把结果写进 canonical state。

未来 supervisor fork 的 branch lease 更窄：它只授权执行一个 temporary execution branch，不继承 source todo、source quota 或 source durable memory。

## Capability Gate：能做不等于被授权

Todo 可以声明：

```bash
--required-capability shell
--required-capability filesystem_write
```

Quota 调用方声明本轮可用能力：

```bash
loopx --format json quota should-run \
  --goal-id <goal-id> \
  --agent-id agent-a \
  --available-capability shell \
  --available-capability filesystem_write
```

Capability 是 preflight 条件，不是 permission：

- 有 `network` 不代表可以上传私有材料；
- 有 `filesystem_write` 不代表可以写任意 repo；
- 有 `session_termination` 不代表 supervisor 可以随意终止 session；
- 有 `benchmark_runner` 不代表可以提交 leaderboard。

权限仍来自 goal boundary、user gate、workspace policy 和 host authority。

`target_capability` 则表示 todo 正在构建或修复什么能力，不是执行这个 todo 的硬前提。

## Workspace Guard：把写入位置变成状态

对于 repo 写入，todo 应声明：

```bash
--task-repository git:github.com/example/project
--required-write-scope 'src/**'
```

工作 peer 需要使用与 task repository 匹配的独立 worktree/branch。共享 base checkout 可以作为只读输入，但多个 agent 不应在同一个脏工作树中并发写。

Workspace guard 与 capability gate 的分工：

| Guard | 回答的问题 |
| --- | --- |
| Capability | 当前 executor 是否具备需要的工具能力？ |
| Workspace | 当前执行边界是否匹配 repo 和写 scope？ |
| User gate | 是否获得了需要的决策或风险授权？ |

## Gate 的 Scope

一个 `user_gate` 应明确：

- 具体问题；
- decision scope；
- 阻塞哪个 agent 或 todo；
- 是否真的是 global gate；
- 完成后 unblocks 哪个 todo。

示例：

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role user \
  --text "确认是否允许修改 public API" \
  --task-class user_gate \
  --decision-scope direction:action:public_api_change \
  --blocks-agent agent-a \
  --unblocks-todo-id <todo-id>
```

Agent todo 则声明需要这个 scope：

```bash
loopx todo update \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --required-decision-scope direction:action:public_api_change
```

只有真正影响所有 peer 的 gate 才使用 `--global-gate`。不要因为不确定就扩大阻塞面。

## Resume Condition

Deferred todo 必须说明何时恢复：

```bash
--resume-when todo_done:<todo-id>
--resume-when pr_merged:<pr-ref>
--resume-when capacity_available:<pool>
```

一个没有 machine-readable resume condition 的 deferred todo 容易永久丢失。Monitor 可以在外部事实改变后创建或 unblock successor advancement todo。

## Completion 不是勾选框

LoopX completion 需要回答：

1. 结果证据是什么？
2. 后续是否存在？
3. 后续由同一 agent 继续，还是独立 handoff？
4. 如果没有后续，为什么可以关闭？

### Same-agent continuation

适合一个非交付大段中的连续分析：

```bash
loopx todo complete \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --claimed-by agent-a \
  --evidence "contract map completed" \
  --next-agent-todo "[P1] Draft the implementation plan" \
  --next-continuation-policy same_agent_non_delivery
```

### Independent handoff

适合希望任一 eligible peer 接手的 successor：

```bash
loopx todo complete \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --claimed-by agent-a \
  --evidence "implementation landed on review branch" \
  --next-agent-todo "[P1] Independently review the implementation" \
  --next-continuation-policy independent_handoff
```

默认 successor 不被 claim。只有显式 `--next-claimed-by` 才把它交给特定 peer。

### Existing successor

如果 successor 已经存在，使用稳定 id：

```bash
loopx todo complete \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --claimed-by agent-a \
  --evidence "source evidence ready" \
  --successor-todo-id <existing-successor-id>
```

### No follow-up

只有工作确实闭合时：

```bash
loopx todo complete \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --claimed-by agent-a \
  --evidence "acceptance checks passed" \
  --no-follow-up
```

`no_followup` 不是“我不想继续”。它必须与 acceptance evidence、空 frontier、已关闭 monitor/successor/replan gap 一致。`terminal_no_followup` 是 CLI 派生的 closure 状态，不是用户可以随意定义的 todo status。

## Supersede：改变方向而不伪造完成

如果原 todo 已不再正确，不要把它标 done。使用 supersede 记录新方向和因果关系：

```bash
loopx todo supersede \
  --goal-id <goal-id> \
  --todo-id <old-id> \
  --reason "new evidence invalidated the original approach" \
  --next-agent-todo "[P0] Implement the evidence-backed alternative"
```

这使 replay 能区分：

- 工作完成；
- 工作失败；
- 工作被新事实取代。

## Review 不是特殊身份

Review 是普通 todo 的 `action_kind=review` 和 continuation policy，不是一个隐藏的 primary reviewer 身份。

例如作者完成实现后创建：

```text
task_class=advancement_task
action_kind=review
continuation_policy=independent_handoff
excluded_agents=[author]
```

任何未被排除且满足 capability/workspace 条件的 peer 都可以 claim。

## 工作图推演

考虑以下状态：

```text
T1 [P0] 修改 public API
  requires decision D1
  claimed_by agent-a

U1 user_gate D1
  blocks agent-a

T2 [P1] 增加不改变 API 的 characterization smoke
  unclaimed
  required_capability shell

M1 monitor external PR
  next_due_at tomorrow
```

当前有 `agent-b`，能力为 `shell`。合理结果：

- U1 投影到 user channel；
- T1 对 agent-a blocked；
- T2 唤醒未被 excluded 的 peer，agent-b 可 claim；
- M1 未到期，不消耗 branch width，也不反复唤醒；
- goal 不应进入 terminal closure。

这里特别说明一个调度边界：即使另一个 claimed todo 被 gate，未认领的 advancement todo 仍应唤醒所有 eligible peer，而不是因为 goal 中存在 `claimed_by` 就饿死。

## 实验：构造一个可计算 Frontier

只在专门实验 goal 中写状态。

### 1. 添加一个 blocked P0

```bash
loopx todo add \
  --goal-id <lab-goal> \
  --role agent \
  --text "[P0] Change the public response schema" \
  --task-class advancement_task \
  --action-kind change_public_schema \
  --required-decision-scope direction:action:public_schema
```

### 2. 添加精确 user gate

```bash
loopx todo add \
  --goal-id <lab-goal> \
  --role user \
  --text "是否允许改变 public response schema？" \
  --task-class user_gate \
  --decision-scope direction:action:public_schema \
  --blocks-agent <agent-a> \
  --unblocks-todo-id <p0-id>
```

### 3. 添加独立 P1

```bash
loopx todo add \
  --goal-id <lab-goal> \
  --role agent \
  --text "[P1] Add a behavior-preserving characterization smoke" \
  --task-class advancement_task \
  --action-kind add_characterization \
  --required-capability shell
```

### 4. 比较两个 peer 的 quota

```bash
loopx --format json quota should-run \
  --goal-id <lab-goal> \
  --agent-id <agent-a> \
  --available-capability shell

loopx --format json quota should-run \
  --goal-id <lab-goal> \
  --agent-id <agent-b> \
  --available-capability shell
```

观察 user channel、selected todo、safe bypass 和 excluded/claim 结果。

## 核心代码领读：一个 todo 怎样成为某个 peer 的合法工作

这一讲的主线不是“找到最高优先级 todo”，而是逐层缩小候选集合：

```text
todo contract
  -> lifecycle / continuation
  -> peer-visible candidates
  -> capability gate
  -> claim / exclusion / successor constraints
  -> workspace guard
  -> agent 在 runnable set 中做最终选择
```

### 1. Todo 的类型和状态是两条独立轴

`loopx/control_plane/todos/contract.py` 把 routing lane 与 lifecycle 分开定义：

```python
TODO_TASK_CLASS_VALUES = {
    "advancement_task",
    "continuous_monitor",
    "user_gate",
    "user_action",
    "blocker",
}

TODO_STATUS_VALUES = {"open", "done", "blocked", "deferred"}
TODO_TERMINAL_STATUS_VALUES = {"done", "deferred"}

class TodoContinuationPolicy(str, Enum):
    INDEPENDENT_HANDOFF = "independent_handoff"
    SAME_AGENT_NON_DELIVERY = "same_agent_non_delivery"
```

因此 `open` 不等于“可执行”：一个 open `continuous_monitor` 可能尚未 due，一个 open `user_gate` 等待的是用户，一个 open `advancement_task` 还可能被 capability 或 workspace 卡住。

再看 continuation 的默认值：

```python
def resolve_todo_continuation_policy(value, *, action_kind=None):
    del action_kind
    explicit = normalize_todo_continuation_policy(value)
    if explicit:
        return TodoContinuationPolicy(explicit)
    return TodoContinuationPolicy.INDEPENDENT_HANDOFF
```

默认 `independent_handoff` 是刻意的：完成者不会因为“刚做完上一项”就自动拥有下一项。只有 `same_agent_non_delivery` 这种明确的同 agent 连续工作才保留 owner。

### 2. Live runtime model 只有 peer；旧 hierarchy 只是 migration input

`loopx/control_plane/agents/runtime_model.py` 是理解“没有 primary/side”最直接的代码：

```python
class AgentRuntimeModel(str, Enum):
    PEER_V1 = "peer_v1"

def agent_runtime_model_for_goal(goal):
    if isinstance(goal, Mapping):
        coordination = goal.get("coordination")
        raw = coordination.get("agent_model") if isinstance(coordination, Mapping) else None
        raw = raw or goal.get("agent_model")
        if raw not in {None, "", "peer_v1", "legacy_hierarchy"}:
            raise ValueError("coordination.agent_model must be peer_v1")
    return AgentRuntimeModel.PEER_V1
```

`legacy_hierarchy` 被允许读入，是为了 exactly-once migration；函数返回值仍永远是 `peer_v1`。兼容 reader 的存在不能被解释为旧角色仍参与 live scheduling。

对于尚未 claim 的工作，稳定分配也不产生 leader：

```python
def select_peer_for_work(registered_agents, *, work_key):
    agents = normalized_peer_agent_ids(registered_agents)
    if not agents:
        return None
    digest = hashlib.sha256(str(work_key).encode("utf-8")).digest()
    return agents[int.from_bytes(digest[:8], "big") % len(agents)]
```

这是 deterministic routing helper，不是 durable ownership。真正 ownership 仍要经过 todo claim/lease 写回。

### 3. Capability gate 输出候选集，不替 agent 领取 todo

`loopx/control_plane/agents/capability_gate.py::build_capability_gate` 先过滤合法 advancement/due monitor，再把候选分成 runnable 与 blocked：

```python
candidates = [
    item for item in raw_items
    if isinstance(item, dict)
    and todo_item_is_actionable_open(item)
    and (
        todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
        or _capability_item_identity(item) in blocked_monitor_identities
    )
]

for item in candidates:
    missing = missing_required_capabilities(item, available_capabilities=available)
    if missing:
        blocked.append(_capability_candidate_item(item, missing=missing))
    else:
        runnable.append(_capability_candidate_item(item, missing=[]))

if runnable:
    return {
        "action": "run",
        "decision_owner": "agent",
        "selection_policy": "agent_steering_audit_over_runnable_candidates",
        "runnable_candidates": runnable,
        "blocked_candidates": blocked,
    }
return {
    "action": _capability_resolution(missing_all)["action"],
    "runnable_count": 0,
    "blocks_delivery": True,
    ...,
}
```

领读时强调 `decision_owner="agent"`：kernel 负责证明哪些候选合法，agent 仍要结合上下文选择和 claim。缺少 `network` 可能要求 repair bridge，缺少 credential/production authority 则应问 owner；两者不能合并成模糊的“缺能力”。

### 4. Workspace guard 是 delivery 前的最后一道因果边界

多 peer 的写操作必须在独立 worktree。`capture_delivery_workspace` 持久化的是无凭据、无本地路径的身份：

```python
workspace_kind = (
    "independent_git_worktree"
    if current_git_dir != current_common
    else "canonical_checkout"
)
return {
    "task_repository": task_repository,
    "workspace_kind": workspace_kind,
    "peer_independent_worktree_required": bool(...),
}
```

`build_agent_workspace_guard` 只在多 peer 且当前候选需要 repository write 时生效：

```python
if len(agent_identity.get("registered_agents") or []) <= 1:
    return None
if not _peer_work_requires_isolated_workspace(...):
    return None

# classify not_git_worktree / foreign_git_worktree / canonical_checkout
if current_workspace:
    return {
        "action": "move_to_independent_worktree",
        "current_workspace": current_workspace,
        "required_workspace": "independent_git_worktree",
        "blocks_delivery": True,
    }
```

这里不是代码风格 gate，而是 attribution gate：后续 refresh 与 quota spend 要能证明交付发生在 todo 声明的 repository、正确的 peer workspace 中。

### 断点练习

1. 在 `resolve_todo_continuation_policy` 观察空值为何落到 independent handoff。
2. 在 `build_capability_gate:301` 改变 `available_capabilities`，只比较 runnable/blocked id。
3. 在 canonical checkout 与 linked worktree 各跑一次 quota，比较 `agent_workspace_guard`。
4. 给同一 todo 同时设置 `claimed_by` 与相同 agent 的 `excluded_agents`，确认 contract fail closed。

### 读完这一段应能回答

1. 为什么 `task_class` 不能由 `status` 推断？
2. `select_peer_for_work` 为什么不是 claim？
3. migration reader 与 live runtime model 的边界在哪里？
4. capability gate 为什么返回 candidate set，而不是唯一 todo？
5. worktree guard 与 spend causality 有什么关系？

## 代码阅读路线

1. `docs/project-agent-todo-contract.md`
2. `docs/reference/protocols/peer-agent-runtime-v1.md`
3. `loopx/control_plane/todos/contract.py`
4. `loopx/control_plane/work_items/lifecycle.py`
5. `loopx/control_plane/agents/runtime_model.py`
6. `loopx/control_plane/work_items/`
7. `docs/product/core-control-plane/state-machine.md` 的 Todo、Gate、Handoff 状态机

## 代表性 Smoke

- `examples/control_plane/todo-lifecycle-cli-smoke.py`
- `examples/control_plane/peer-agent-runtime-v1-smoke.py`
- `examples/control_plane/peer-agent-workspace-guard-smoke.py`
- `examples/control_plane/capability-gate-projection-smoke.py`
- `examples/control_plane/todo-projection-shared-helper-smoke.py`

## 课后检查

1. Claim 和 lease 的差别是什么？
2. Required capability 为什么不是权限？
3. 什么情况下 user gate 应是 global？
4. 为什么 review 应建模成普通 todo，而不是 primary agent 权力？
5. Completion 缺少 successor 和 no-followup 时，系统为什么不能终止？

下一讲把这个工作图交给决策内核，逐层拆解 `quota should-run` 如何编译出本轮 interaction contract。
