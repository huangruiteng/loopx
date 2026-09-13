---
artifact_contract: ce-unified-plan/v1
artifact_readiness: proposal-draft
execution: code
product_contract_source: pending-owner-confirmation
---

# Managed Turn Loop —— DSH 参考纵切（提案 + 实现方案）

- 状态：草案。等待 maintainer 对本文 §7 两个确认点表态后升级为 implementation-ready。
- 基线：upstream `huangruiteng/loopx` main `201da973c`（2026-09-14）。**注意：本文引用的
  `host_failure.py`、`loop_controller.py` 等 PR #3771 产物在落后的 fork main 上不存在，
  动工前先 `git fetch https://github.com/huangruiteng/loopx.git "+main:refs/remotes/official/main"`，
  再从 `refs/remotes/official/main` 开分支。
- 关联：`docs/architecture/rfcs/desktop-execution-frontends-v0.md`（Slice C）、
  `docs/reference/protocols/turn-loop-controller-v0.md`、PR #3771、
  maintainer 合并后评论（"结合控制面前端做成一个 managed 模式，把 pi/dsh 包进来"）。
- 提交上游时另出英文版；附录 B 已备好可直接使用的英文 tracking issue 正文。

---

## 0. 勘误（2026-09-14 复核，对着 upstream main `201da973c`）

本文 §5 的切片表在 2026-09-01 撰写时以 `d88db409` 为基线。13 天后的复核结论如下，
**PR-1 已由他人在上游交付，PR-2/3/4 仍全部空缺**：

| 切片 | 上游状态 | 证据（`refs/remotes/official/main`） |
|---|---|---|
| PR-1 DSH 类型化失败信道 | **已交付，勿重做** | `edb544b61`（2026-09-01）；`loopx/dsh_goal_mode/host_failure_map.py:212` `classify_dsh_failure`；`turn_host_adapter.py:603` 抛 `BuiltInHostError`，`:638` `run_dsh_host`；`loopx/cli_commands/turn_dsh_host.py`；`turn_registration.py:88` `host_choices=["codex-cli", "dsh", "generic-cli"]` |
| PR-2 Managed Step | **空缺** | `retry_continuation` 全仓只出现在 `loopx/control_plane/turn_driver/loop_controller.py:698` 自身与 `tests/test_loop_turn_loop_controller.py`；`decide_loop_disposition` 在 `loopx/` 下除 `turn_driver/__init__.py` 的导出重导外无任何生产调用者 |
| PR-3 Supervisor v0 | **空缺** | 全仓 grep `managed-step` / `loopx_managed_execution_state_v0` / `managed-execution.json` 零命中（只命中本文自身） |
| PR-4 dashboard Waiting 投影 | **空缺** | `apps/presentation/dashboard/src` 下无 Waiting/retry 进度投影 |

**本文行号已全部失效**，动工前按上表重新定位。以下两条是撰写时写错的事实：

1. `--retry-failed-turn` / `--resume-turn-key` **确实存在**，只是在下划线形式下才能 grep 到
   消费方（`loopx/cli_commands/turn.py:227`、`:954`）。旗标定义见
   `turn_registration.py:32`（`inspect-journal` 子命令）与 `:165`/`:170`（`run-once`）。
2. `retry_continuation` 的字段集比本文 §第二部分 PR-2 引用的多一个
   `strategy`（取自 `host_failure.py` 的 `HOST_RETRY_STRATEGY = "same_configuration"`），
   见 `loop_controller.py:685-700`。产出 payload 以该处实际代码为准，不要照抄本文的旧字段表。

---

## 第一部分：提案

### 1. 问题（四个缺口，全部为代码级已验证事实）

1. **`retry_continuation` 没有生产消费者。** PR #3771 让纯控制器在可重试 host 失败时返回
   `wait` + `retry_continuation`（`loopx/control_plane/turn_driver/loop_controller.py:683-700`），
   协议文档明言 "The outer scheduler may wake that same failed Turn"——但
   `decide_loop_disposition`（同文件 `:489`）在 `loopx/` 生产代码中零调用者，
   全仓消费方只有它自己的测试。
2. **DSH 的失败信道折叠成 `unknown`。** ——**此缺口已由 PR-1 修复，见 §0。**
   保留于此仅为说明 PR-2 的前置条件：类型化失败现在能进 journal
   （`BuiltInHostError` → `executor.py:699` → `record_host_failure`），
   于是 `wait` 分支第一次真的会被触达。
3. **外层循环没有常驻 owner。** 今天驱动 `quota should-run → turn run-once` 的是脚本、
   smoke 框架或 host 原生 loop；产品层（Tauri 壳 + `loopx chat`）不发起任何 governed Turn。
4. **`managed_runtime` 语义碰撞。** `loopx/chat_store.py` 的
   `CHAT_SESSION_MODE_MANAGED = "managed_runtime"` 只表示"chat 服务拥有并启动 runtime"，
   与 RFC 的 Managed Agent Runtime（经 `loopx_turn_v0` 治理）不是一回事，须避免复用该词。
   **复核补充**：开放 PR #4337 正在新增 `docs/architecture/rfcs/manager-runtime-profile-v0.md`
   （"RFC M1 private-owner host profile"），命名面已被进一步占用，动工时把三者的词面差异写进 PR 描述。

### 2. 目标

一条最小 managed vertical，宿主在 `loopx chat` 本地 broker（Tauri 保持纯进程壳）：

```text
dashboard/CLI 触发 start
  -> supervisor 请求 fresh decision（quota/gate/todo）
  -> 铸造一个幂等 loopx_turn_v0
  -> DSH in-process 执行一次有界尝试
  -> 独立验证 -> writeback -> 恰好一次 spend
  -> scheduler hint / typed host failure
  -> continue：下一个 Turn
  -> retryable：持久化 pending_wake，定时后重新走 fresh decision（同 Turn 重试）
  -> repair/user_action：停下并投影原因
  -> validated terminal：干净停机
```

### 3. 非目标（红线，来自既有 RFC 与 #3771 评审共识）

- 不建立第二个 retry ledger——Turn Journal 是失败、attempt、recovery 的唯一事实源。
- LoopX 控制器不 sleep、不轮询、不成为常驻 scheduler（`turn-loop-controller-v0.md` 明文）。
- Tauri 层不实现任何 Turn 循环；`apps/desktop` 预计零改动。
- supervisor 对 attempt 数、retryability、model/provider 配置没有权威——一切重新向
  journal/controller 求证。
- 不动 Pi，直到 DSH 纵切通过共享 conformance；不开新的并列 RFC，本文挂在
  desktop-execution-frontends-v0 的 Slice C 之下。

### 4. 所有权边界

| 事实或能力 | 唯一 owner |
|---|---|
| Goal/Todo、gate、quota、工作资格 | LoopX 控制面 |
| failure kind、retryable、attempt/max、same-Turn 有效性 | Turn Journal + typed controller |
| validation、writeback、spend 幂等 | Turn executor / Effect Program |
| DSH 模型与工具循环、opaque session | DSH runtime（经 `dsh_goal_mode` 适配） |
| timer、wakeup、单飞、取消、崩溃对账、pause/resume | Supervisor（`loopx chat` 内） |
| 会话、SSE、前端连接 | `loopx chat` broker |
| 进程启动/健康检查/退出 | Tauri 壳（现状不变） |

### 5. 交付切片

| 切片 | 内容 | 演示效果 | 上游状态 |
|---|---|---|---|
| PR-1 | DSH 类型化失败信道（in-process host） | 容量失败在 journal 里有名字（`provider_capacity`，retryable），不再是 `unknown` | **已交付** |
| PR-2 | Managed Step：`retry_continuation` 第一个消费者 | 20 行脚本演示"失败 → 等 30s → 同 Turn 自愈 → 只扣一次费" | **空缺，本文目标** |
| PR-3 | Supervisor v0（`loopx chat` 内） | 无人值守跑完 Goal，经得起 kill -9，账目分毫不差 | 空缺 |
| PR-4 | dashboard Waiting/进度投影 | 界面显示"Waiting · provider capacity · retry 14:35 · attempt 1/3" | 空缺 |

### 6. 完成定义：RFC managed 模式验收从不可测变为可跑绿

对照 `desktop-execution-frontends-v0.md` 的 Slice C（`### Slice C: managed reference vertical`
一节，六条）与其后的 `## Validation criteria`：同一 opaque session 跨多 Turn 复用；
不安装任何 host 原生 Goal loop 也能推进；每次材料性尝试有选定 Todo、幂等 Turn 身份、
独立验证、writeback 后结算；中断与重启保留或显式对账 session；crash 重放不重复
writeback 与 spend。

### 7. 给 maintainer 的确认点

1. 本方向挂 Slice C 下用 tracking issue 推进（不另开 RFC），可以吗？
2. supervisor 宿主放 `loopx chat` broker、Tauri 保持进程壳，符合"结合控制面前端"的预期吗？

**PR-2 不依赖以上两点**（纯 CLI 语义，无宿主位置决策），可直接动工。

---

## 第二部分：具体实现方式

### PR-2：Managed Step（`retry_continuation` 的第一个消费者）

**入口**：`loopx turn managed-step --goal-id ... --agent-id ... --format json`
（或作为 `run-once` 的组合模式，以 review 反馈为准）。

**流程**：读 journal 最近失败 receipt → 构造 fresh decision（复用 `run-once` 的决策构建）→
`decide_loop_disposition(fresh_decision, failed_receipt, ...)` → typed 输出。
`wait` 时**不执行、不 spend、不写状态**，只返回：

```json
{
  "disposition": "wait",
  "retry_continuation": {
    "same_turn": true,
    "retry_failed_turn": true,
    "strategy": "same_configuration",
    "retry_after_seconds": 30,
    "attempt": 1,
    "max_attempts": 3,
    "fresh_envelope_required": true,
    "model_fallback_allowed": false
  }
}
```

（字段即 `loop_controller.py:683-700` 现有输出，本 PR 不改语义、只接消费。
重试策略表在 `loopx/control_plane/turn_driver/host_failure.py` 的 `_RETRY_POLICIES`：
`executor_timeout` (2,5) / `provider_capacity` (3,30) / `provider_overloaded` (3,30) /
`rate_limited` (3,60) / `transport_lost` (3,10)；`host_failure_retry_available`
在同文件 `:121` 判定"还有余额"。）

**权威规则**：attempt/max 一律取自 Turn Journal；调用方传入的观察值仅作对账，不一致时
fail-closed。执行侧衔接既有旗标 `--retry-failed-turn` / `--resume-turn-key`，
由 managed-step 的输出决定是否允许携带。

**测试矩阵**：三分支单测（预算内 wait / 预算尽 repair / 可继续 proceed，模板
`tests/test_loop_turn_loop_controller.py`）；伪造 `observed_attempt=99` 被拒的越权用例；
脚本化循环 smoke——fake runner"第一次容量失败、第二次成功"，断言同 `turn_key` 重试、
失败轮零 spend、成功后恰好一次。
