# 第 1 讲：从 Showcase 到第一次真实 Loop

> 目标：先建立一个可运行的整体画面。此时不要求记住所有状态字段，只要能回答：谁负责执行、谁负责保存长期状态、一次 App automation 为什么会继续或停下。

## 本讲在课程中的位置

[第 0 讲](00-goal-control-plane-architecture.md)已经用 authority map 区分了 LoopX、host、runtime、memory、workspace 和
projection。本讲不再讨论“应该画哪一种架构图”，而是沿总览图跑通第一次真实 Loop。
全课由第 0 讲架构导论和 9 讲专题组成，每讲只增加一个主要抽象：

| 讲次 | 新增的主要抽象 | 学完后能回答的问题 |
| --- | --- | --- |
| 0 | Goal control plane authority | 谁拥有长期事实、谁执行、谁提供回执？ |
| 1 | 一次真实 Loop | 用户说一句话之后，到底发生了什么？ |
| 2 | 状态底座 | 长期目标和事实保存在哪里？ |
| 3 | 工作图 | 多个 peer 如何领取、交接和关闭工作？ |
| 4 | 决策内核 | `quota should-run` 如何决定这一轮做什么？ |
| 5 | 宿主调度 | Codex App heartbeat 如何唤醒、退避和停止？ |
| 6 | 证据与自修复 | 为什么“做过了”不等于“控制面已推进”？ |
| 7 | 内核扩展方法 | 如何安全地给 control plane 增加一条规则？ |
| 8 | 分层质量门禁 | Agent 如何证明改动可交付，而不是只证明测试会通过？ |
| 9 | 可选扩展 | Explore、multi-agent、supervisor、Auto Research 如何接入？ |

建议时长：90 分钟，其中讲解 50 分钟、代码路径 20 分钟、实验 20 分钟。

## 学习目标

完成本讲后，开发者应该能够：

1. 用一句话区分 LoopX、Codex App 和模型执行器。
2. 说出 `$loopx <task>` 到第一次 bounded delivery 的真实 CLI 路径。
3. 从 `interaction_contract` 中区分用户通道、agent 通道和 CLI 通道。
4. 理解 Showcase 是公开证据目录，不是隐藏的工作流模板。
5. 在不修改状态的前提下预览一次 guided start。

## 先看 LoopX 做成过什么

公开 Showcase 的价值不是展示“模型很聪明”，而是展示长期工作如何留下可审查证据。仓库中的 `docs/showcases/showcase-catalog.json` 是目录真相，当前代表性案例包括：

- 多个 PR 的夜间批处理，展示 bounded batch、验证和公开证据回写；
- 从 issue 到修复 PR，展示任务发现、实现、验证和交付；
- agent 通过 PR comment 协作，展示跨 agent 的显式交接；
- LoopX 自己迭代 LoopX，展示 control plane 可以管理自身开发；
- blocked P0 下继续独立 P1/P2，展示 gate 和安全旁路并不互相排斥。

阅读 Showcase 时只问三件事：

1. 长期目标是什么？
2. 每轮产出了什么可验证状态变化？
3. 哪些边界没有被越过？

不要把 Showcase 理解成“复制这个 prompt 就能复现结果”。LoopX 复用的是状态与交互协议，不是某条轨迹的具体文本。

## 一句话心智模型

**LoopX 是一个本地、agent-agnostic 的长期任务 control plane。它不替 agent 执行代码，而是保存目标、边界、todo、claim、quota、证据和调度建议，并把当前状态编译成下一轮可执行协议。**

最重要的三层分工是：

| 层 | 例子 | 负责什么 | 不负责什么 |
| --- | --- | --- | --- |
| Host | Codex App heartbeat、Codex CLI、Claude Code | 何时拉起一轮、把 task body 交给模型、应用调度频率 | 不判断长期事实，不自行发明 todo 真相 |
| Executor | 当前 Codex/Claude session | 阅读代码、实现、验证、写回一个 bounded transition | 不把聊天记忆当长期真相，不替用户越权 |
| LoopX control plane | registry、active state、event ledger、status、quota | 保存长期状态并决定本轮协议 | 不直接成为模型 runtime，不替 host 创建会话 |

可以把它画成：

```text
User
  |
  | $loopx <task>
  v
Host surface --------------+
  |                         |
  | generated task body     | scheduler_hint
  v                         |
Executor                    |
  |                         |
  | CLI reads/writes        |
  v                         |
LoopX CLI -> State Kernel --+
  |
  +-> registry / events / active-state / run history
```

## 一次 Codex App 交互的真实路径

下面不是概念伪代码，而是公开 CLI 的真实调用路径。任务文本、goal id 和 agent id 都使用占位符，读者可以在自己的测试仓库中复现。

### 0. 用户只表达目标

在 Codex App 中，用户调用 LoopX skill：

```text
$loopx <long-running task>
```

用户不应该先手工构造 todo、quota 或 heartbeat prompt。第一层接口只承载意图。

### 1. Guided start 先做只读预览

skill 调用：

```bash
loopx start-goal \
  --guided \
  --project . \
  --goal-text "<long-running task>"
```

`loopx/cli_commands/starter_bootstrap.py` 将命令交给 `build_start_goal_guided_packet`。真正的 transaction 由 `loopx/bootstrap_command_pack.py` 组装。

它首先回答两个路由问题：

- 这个项目对应哪个 durable goal？
- 当前 session 以哪个 registered peer identity 工作？

如果候选不唯一，CLI 返回选择 gate，而不是猜。选择后，agent 用显式参数重跑：

```bash
loopx start-goal \
  --guided \
  --project . \
  --goal-id <goal-id> \
  --host-surface codex-app \
  --goal-text "<long-running task>"
```

关键点：guided packet 本身是 read-only 的。它生成应执行的事务，不把“预览成功”冒充“状态已经写入”。对应 smoke 是 `examples/bootstrap-command-pack-smoke.py`。

### 2. Agent 先规划，再把计划写成 todo

合理的 bootstrap 顺序是：

```text
inspect/connect
  -> plan a bounded ordered frontier
  -> todo add / claim
  -> refresh-state
  -> activate host loop
  -> quota should-run
```

这一步有一个重要约束：计划不能只留在聊天里。需要长期执行的计划必须投影成 LoopX todo 或明确 rationale。

一个最小 agent todo 如下：

```bash
loopx todo add \
  --goal-id <goal-id> \
  --role agent \
  --text "[P0] Inspect the current control-plane contract" \
  --task-class advancement_task \
  --action-kind inspect_contract \
  --required-capability shell \
  --continuation-policy same_agent_non_delivery
```

随后由某个已注册 peer 领取：

```bash
loopx todo claim \
  --goal-id <goal-id> \
  --todo-id <todo-id> \
  --claimed-by <agent-id>
```

### 3. Host 获得薄 heartbeat task body

Codex App automation 不应该长期保存一大段项目专属决策逻辑。它只安装一个薄 prompt：

```bash
loopx heartbeat-prompt \
  --thin \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --agent-scope "<registered host lane>"
```

`loopx/heartbeat_prompt.py` 生成的 task body 只要求每轮重新读取 CLI 真相、运行 quota、服从 interaction contract、在验证写回后 spend，并应用 scheduler hint。

为什么要薄？因为状态规则会演进。如果复杂规则被复制进 automation prompt，就会出现多个过期的 control plane。

### 4. 每一轮先运行 quota guard

真实的一等入口是：

```bash
loopx --format json quota should-run \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --available-capability shell \
  --available-capability filesystem_write
```

不要只看 `should_run`。最应该读的是：

```json
{
  "interaction_contract": {
    "schema_version": "loopx_interaction_contract_v0",
    "mode": "bounded_delivery",
    "user_channel": {
      "action_required": false,
      "notify": "DONT_NOTIFY"
    },
    "agent_channel": {
      "must_attempt": true,
      "delivery_allowed": true,
      "quiet_noop_allowed": false,
      "primary_action": "<todo-id>: <bounded action>"
    },
    "cli_channel": {
      "next_cli_actions": ["<refresh>", "<spend-after-validation>"],
      "spend_allowed_now": false,
      "spend_after_validation": true
    }
  }
}
```

三个通道可以同时成立。例如：

- 用户有一个不阻塞当前工作的 todo，需要通知；
- agent 仍必须执行一个独立的 P1；
- CLI 要求完成后 refresh，再 spend 一次。

所以“有 user todo”并不自动等于“agent 什么都不能做”。

### 5. Agent 只交付一个 bounded transition

`mode=bounded_delivery` 的含义不是“尽量少做”，而是完成一个能被验证、回写和恢复的工作段：

```text
read current contract
  -> choose one allowed todo
  -> perform the work
  -> validate artifact or blocker
  -> write durable state
  -> spend exactly once
```

读取一个文件、说一句“正在分析”通常不构成 bounded delivery。完成一个小实现、形成可执行 blocker、写入经验证的设计稿，才算可恢复的推进。

### 6. Scheduler hint 调整下一次唤醒

quota 还会返回：

```json
{
  "scheduler_hint": {
    "action": "run_now_or_backoff",
    "codex_app": {
      "stateful_backoff": {
        "apply_needed": true
      }
    }
  }
}
```

当 `apply_needed=true` 时，host 先更新 App automation 的 RRULE，再运行 CLI 给出的 ACK。ACK 绑定 goal、agent、surface、state key 和实际 RRULE，防止“模型说已更新”被当成执行证据。

### 7. 验证写回后才 spend

典型顺序：

```bash
loopx refresh-state \
  --goal-id <goal-id> \
  --classification <validated-progress> \
  --delivery-batch-scale single_surface \
  --delivery-outcome outcome_progress \
  --agent-id <agent-id> \
  --vision-unchanged-reason "<why the acceptance target is unchanged>"

loopx quota spend-slot \
  --goal-id <goal-id> \
  --slots 1 \
  --source heartbeat \
  --execute \
  --agent-id <agent-id>
```

Spend 是“这轮已形成有效控制面推进”的账，不是“模型被唤醒过”的计数器。dry-run、read-only poll、monitor quiet skip、scheduler ACK 都不应该先花配额。

## 为什么 App automation 不是主循环本身

Automation 只负责触发。真正的循环状态在 LoopX：

```text
automation fires
  -> agent runs quota should-run
  -> interaction_contract says run / wait / notify / repair
  -> agent produces validated writeback or quiet no-op
  -> scheduler_hint changes next cadence
```

因此 App 被重启、线程被压缩、模型被替换，只要 registry 和状态仍在，下一位 executor 可以恢复。反过来，如果所有事实只在聊天里，即使 automation 还在跑，也不是可靠的长期 loop。

## 实验：安全预览第一次 Loop

### 准备

在一个已安装 LoopX 的实验仓库中运行：

```bash
loopx doctor
git status --short --branch
```

本实验不使用生产目标，不授权外部发送、凭据操作或 destructive git。

### 步骤 A：生成 guided packet

```bash
loopx --format json start-goal \
  --guided \
  --project . \
  --goal-text "Explain the current test entrypoints and propose one safe improvement"
```

记录它是否要求：

- goal selection；
- agent identity selection；
- connect；
- todo plan；
- host activation。

不要执行 packet 中的写命令。

### 步骤 B：阅读当前状态

如果实验 goal 已连接：

```bash
loopx --format json status --goal-id <lab-goal-id>
loopx --format json quota should-run \
  --goal-id <lab-goal-id> \
  --agent-id <lab-agent-id> \
  --available-capability shell
```

只回答四个问题：

1. `interaction_contract.mode` 是什么？
2. 用户通道是否要求动作？
3. agent 通道是否必须尝试？
4. spend 是现在允许，还是验证后允许？

### 步骤 C：定位实现

按调用顺序阅读：

1. `loopx/cli.py`
2. `loopx/cli_commands/starter_bootstrap.py`
3. `loopx/bootstrap_command_pack.py`
4. `loopx/heartbeat_prompt.py`
5. `loopx/quota.py::build_quota_should_run`

不要从头通读 `quota.py`。先搜索 `build_quota_should_run`，再沿它调用的 bounded-context helper 向下读。

### 步骤 D：带着调用链读核心代码

先把整条路径压成一行。课堂上每进入一个函数，都问一句“这一层拥有哪种决定权”：

```text
cli.main
  -> handle_starter_bootstrap_command
  -> handle_start_goal_command
  -> build_start_goal_guided_packet
  -> inspect_bootstrap_connection
  -> planner/todo transaction
  -> build_heartbeat_prompt
  -> quota should-run
  -> interaction_contract + scheduler_hint
```

#### 1. CLI handler 只做协议入口，不偷偷替用户启动 goal

`loopx/cli_commands/starter_bootstrap.py` 的关键分支很短：

```python
def handle_start_goal_command(args, print_payload) -> int:
    if not bool(getattr(args, "guided", False)):
        payload = {
            "ok": False,
            "error": "`loopx start-goal` currently requires --guided",
            "suggested_command": "loopx start-goal --guided --goal-text '<goal text>'",
        }
        print_payload(payload, args.format, render_start_goal_guided_markdown)
        return 2

    payload = build_start_goal_guided_packet(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        goal_text=args.goal_text,
        # ... host surface 与 capability 参数
    )
    print_payload(payload, args.format, render_start_goal_guided_markdown)
    return 0
```

这里要读出三个设计点：

1. `--guided` 是 fail-closed gate；缺少它时返回可修复的 packet，而不是猜用户意图。
2. handler 不写 todo，也不拉起模型；它只把输入交给 packet builder。
3. 返回码 `2` 表示调用合约错误，`0` 表示 packet 已成功生成，不等于 goal 已完成。

建议断点：`handle_start_goal_command:115`。分别去掉和加入 `--guided`，观察是否在 builder 之前返回。

#### 2. Connection inspection 把“能否复用现有状态”编码成有限状态

`loopx/bootstrap_command_pack.py::inspect_bootstrap_connection` 先解析 canonical project alias，再检查 registry 与 state file：

```python
input_project = _resolve_project(project)
alias = resolve_canonical_project_alias(input_project, goal_id=goal_id)
resolved_project = (
    _resolve_project(Path(str(alias.get("canonical_project"))))
    if alias.get("applied") and alias.get("canonical_project")
    else input_project
)
registry_path = resolved_project / ".loopx" / "registry.json"

if registry_error:
    return {"connection_state": "registry_invalid",
            "mutation_confirmation_required": True, ...}
if not registry:
    return {"connection_state": "not_connected",
            "mutation_confirmation_required": True, ...}
# ... registry_without_goal / registry_goal_missing_state_file / state_file_missing
return {
    "connection_state": "connected",
    "mutation_confirmation_required": False,
    ...,
}
```

不要把这段理解成一串文件存在性判断。它实际上在守住两个不变量：

- linked worktree 必须回到 canonical project truth，不能生成影子 goal；
- 只有 registry entry 与其声明的 state file 同时成立，才能无确认地复用连接。

建议观察：临时把 `state_file` 指向不存在的文件，只运行 preview，确认状态是 `state_file_missing`，且没有发生写入。

#### 3. Heartbeat prompt 是 host contract 编译器

`loopx/heartbeat_prompt.py::build_heartbeat_prompt` 不是 scheduler。它把 goal、peer identity 和可用能力编译成 host 可执行的 prompt：

```python
if not (full or compact or brief or thin):
    thin = True

normalized_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
normalized_registered_agents = normalize_registered_agents(registered_agents)
if normalized_registered_agents and not normalized_agent_id:
    raise ValueError(build_peer_identity_required_error(...))

quota_guard_command = render_quota_guard_command(
    goal_id,
    agent_id=normalized_agent_id,
    available_capabilities=normalized_available_capabilities,
)
quota_spend_command = render_quota_spend_command(...)
refresh_state_command = render_refresh_state_command(...)
```

核心不是字符串拼接，而是身份约束：多 peer goal 缺少 `agent_id` 时直接失败。否则 claim、workspace guard、quota 和 spend 都无法归因。

#### 4. Quota 把很多局部判断收敛成一个执行决定

不要逐字段读 `build_quota_should_run`。先抓住它的四阶段骨架：

```python
goal_boundary = _goal_boundary(...)
work_lane_contract = build_quota_work_lane_contract(...)
capability_gate, capability_monitor_contract, capability_monitor_fallback = (
    build_capability_gate_with_monitor_fallback(...)
)
workspace_guard = build_agent_workspace_guard(
    item, agent_identity,
    agent_todo_summary=agent_todo_summary,
    selected_todo=work_lane_selected_todo,
)

projection_gap_repair = build_state_projection_gap_repair_hint(...)
if projection_gap_repair:
    normal_delivery_allowed = False
    recovery_allowed = False
    self_repair_allowed = True

if capability_gate and capability_gate.get("action") != "run":
    normal_delivery_allowed = False
if workspace_guard:
    normal_delivery_allowed = False
    self_repair_allowed = False
    workspace_repair_allowed = True

should_run = bool(
    normal_delivery_allowed or recovery_allowed or self_repair_allowed
    or capability_repair_allowed or workspace_repair_allowed
)
effective_action = _effective_action(...)
```

按这个顺序领读：先确定 goal boundary，再选 work lane，再检查能力与 workspace，最后让 projection repair 覆盖普通 delivery。`should_run=True` 只说明“本轮有必须尝试的合法动作”，动作可能是 repair，并不总是产品交付。

建议断点：`quota.py:1300`、`:1351`、`:1404`、`:1442`、`:1461`。每次只记录 `effective_action`、四个 `*_allowed` 与 guard 的 `reason`。

#### 读完这一段应能回答

1. 为什么 `start-goal` 成功返回不等于已经执行 agent turn？
2. 为什么 connected 的判定不能只看 `.loopx/registry.json` 是否存在？
3. 多 peer heartbeat 为什么必须显式携带 `agent_id`？
4. `should_run=True` 时，哪几类动作仍然不是正常 delivery？
5. 哪一层负责建议 host cadence，哪一层真正触发模型？

## 常见误解

### “LoopX 是另一个 agent runtime”

不是。LoopX 可以向 host 提供 prompt、调度建议和状态协议，但不替 Codex App 或 CLI 执行模型 turn。

### “Heartbeat 每次触发都必须做事”

不是。`interaction_contract` 可以要求等待、quiet no-op、monitor poll 或 self-repair。是否执行由当前状态决定。

### “P0 被用户 gate 卡住，整个 goal 就停止”

不一定。若 CLI 明确允许 safe fallback，agent 应继续独立且可验证的 P1/P2，同时把具体用户问题投影出来。

### “Supervisor 就是主 agent”

不是。当前 peer 模型没有 primary/side 的运行时层级。可选 supervisor 是 equal peer
上的观察和 proposal overlay；第 7 讲用它演示规则设计，第 9 讲说明它与其他扩展能力
如何复用同一个 kernel。

## 本讲源码与 smoke 地图

| 目的 | 入口 |
| --- | --- |
| 产品心智模型 | `README.zh-CN.md`、`docs/architecture.md` |
| 新人命令路径 | `docs/guides/newcomer-command-path.md` |
| guided start | `loopx/cli_commands/starter_bootstrap.py`、`loopx/bootstrap_command_pack.py` |
| heartbeat body | `loopx/heartbeat_prompt.py` |
| quota 入口 | `loopx/quota.py::build_quota_should_run` |
| Showcase 真相 | `docs/showcases/showcase-catalog.json` |
| guided start 回归 | `examples/bootstrap-command-pack-smoke.py` |
| quota/heartbeat 回归 | `examples/control_plane/heartbeat-quota-flow-smoke.py` |

## 贯穿实验：让课程任务也走一遍 LoopX

课程可以用自身作为一个公开可复现的贯穿案例。下面只保留稳定的状态转换，不依赖任何真实线程、todo id 或本机目录：

```text
用户在 Codex App 调用 $loopx，要求编写 9 讲开发者课程
  -> start-goal --guided 发现多个候选 goal
  -> 用户将任务显式路由到 <goal-id>
  -> guided packet 要求选择 registered peer identity
  -> 选择 <agent-id>
  -> 生成 heartbeat-prompt --thin
  -> bootstrap-command-pack 预览完整 transaction
  -> 先规划，再写 4 个 ordered todo
  -> refresh-state 投影本轮计划
  -> quota should-run 选择第一个 todo
  -> App scheduler 从 15m 调整为 3m
  -> scheduler-ack-current 记录实际 RRULE
  -> 完成取证 todo，链接设计 todo 为 successor
  -> claim 设计 todo，开始讲义交付
```

示例 todo 图：

```text
<todo-evidence>  [P0] 取证机制地图
<todo-design>    [P0] 设计 9 讲认知梯度
<todo-writing>   [P1] 撰写 9 份 lecture Markdown
<todo-verify>    [P1] 交叉校验与公开交付
```

Scheduler ACK 应保留的关键字段：

```text
goal_id     = <goal-id>
agent_id    = <agent-id>
surface     = codex_app
state_key   = scheduler_hint.codex_app.stateful_backoff
RRULE       = FREQ=MINUTELY;INTERVAL=3
```

课堂上可以逐条对照自己的状态文件。实验还应故意漏写一次 material refresh 的 vision decision，观察后续 quota 产生 `vision_checkpoint_missing`；第 6 讲会完整复盘这个失败案例。

## 课后检查

1. 为什么 guided start 必须是 read-only preview？
2. 为什么计划要写入 todo，而不能只留在 assistant message？
3. `should_run=false` 和“automation 应永久停止”有什么区别？
4. 为什么 spend 必须晚于验证和 writeback？
5. 如果 host 更新了 RRULE，但没有 scheduler ACK，会留下什么不确定性？

下一讲将把这条运行路径中的“状态”拆开：哪些是配置真相、哪些是事件真相、哪些只是 read model。
