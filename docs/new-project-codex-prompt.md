# New Project Codex Prompt

Use this prompt when you already have:

- a local project folder;
- a project goal document;
- a Codex session with access to that folder.

Replace the placeholders before sending it to Codex.

## CLI Generator

Generate the same handoff prompt locally:

```bash
goal-harness new-project-prompt \
  --project <PROJECT_ROOT> \
  --goal-doc <GOAL_DOC_PATH>
```

If the project needs a controller that can split scoped sub-agent probes:

```bash
goal-harness new-project-prompt \
  --project <PROJECT_ROOT> \
  --goal-doc <GOAL_DOC_PATH> \
  --spawn-allowed \
  --allowed-domain docs-map \
  --allowed-domain validation-map \
  --write-scope "docs/**"
```

## Copy-Paste Prompt

````text
我有一个新项目要接入 Goal Harness。

项目文件夹：
<PROJECT_ROOT>

项目目标文档：
<GOAL_DOC_PATH>

请你按下面步骤推进，不要停在方案讨论：

0. 先确认当前 shell 能调用 Goal Harness CLI；如果提示 `goal-harness`
   不在 PATH，运行本机安装脚本再继续：

   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   install_script="$HOME/goal-harness/scripts/install-local.sh"
   if ! command -v goal-harness >/dev/null 2>&1; then
     if [ -x "$install_script" ]; then
       "$install_script"
       export PATH="$HOME/.local/bin:$PATH"
     else
       echo "goal-harness is not on PATH; clone the Goal Harness repo and run scripts/install-local.sh" >&2
       exit 1
     fi
   fi
   goal-harness doctor >/dev/null
   ```

1. 再只读检查项目文件夹和目标文档，抽取：
   - stable goal id；
   - 一句话 objective；
   - domain；
   - authority sources；
   - work clusters；
   - validation surfaces；
   - private/public boundary；
   - 第一个 recommended_action。
2. 运行 Goal Harness 接入命令。优先使用：

   cd <PROJECT_ROOT>
   goal-harness connect \
     --goal-id <STABLE_GOAL_ID> \
     --objective "<OBJECTIVE_FROM_GOAL_DOC>" \
     --domain <DOMAIN> \
     --goal-doc <GOAL_DOC_PATH> \
     --adapter-kind read_only_project_map_v0 \
     --adapter-status connected-read-only

   如果已有安全的只读 pre-tick 命令，再追加：

   --next-probe "<READ_ONLY_PRE_TICK_COMMAND>"

   如果项目需要主控拆 sub-agent，再加：

   --spawn-allowed \
   --allowed-domain docs-map \
   --allowed-domain validation-map \
   --write-scope "<SAFE_WRITE_SCOPE>"

3. 确认 `.goal-harness/registry.json` 和
   `.codex/goals/<STABLE_GOAL_ID>/ACTIVE_GOAL_STATE.md` 已创建或更新。
   如果目标状态包含私有证据，把 `.goal-harness/` 和 `.codex/goals/`
   加入该项目 `.gitignore`。
   `goal-harness connect` 默认会同步到共享全局 registry；不要手动编辑其他
   项目的 registry。
   接入后检查 registry 里的 `execution_profile`：它是本项目后续 heartbeat /
   adapter 的执行画像。默认 cadence 是 `bounded_progress_segment`，连续小步达到
   阈值后，下一轮必须扩展到 `minimum_scale` 并包含 `must_include` 里的真实
   artifact、targeted validation、state writeback；如果做不到，先报 blocker，
   不 append quota spend。
4. 在任何 heartbeat、scheduled tick、long-running adapter 或自主 delivery 前，
   先问 compute guard：

   ```bash
   goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id <STABLE_GOAL_ID>
   ```

   如果返回 `state=operator_gate`，把它当成人/控制器交互，而不是安静 skip：优先读取
   payload 里的 `gate_prompt`、`operator_question`、`recommended_action`、
   `next_handoff_condition`、`missing_gates`、`user_todo_summary` 和
   `agent_todo_summary`，用中文主动告诉用户当前卡在哪个 gate、期望怎样回复；同时把
   `agent_todo_summary` 当作项目 agent 自己的安全后续清单。不要执行任何 `agent_command`、adapter work、
   write-control、生产动作或该 gated action。如果同一个未决 gate 最近已经问过，且返回
   `safe_bypass_allowed=true`，该 gate 只阻塞被 gate 覆盖的 delivery path；可以从
   active state / Priority Stack 里选择一个不依赖该 gate 的 bounded 只读分析、steering、
   文档或 P0/P1 工作。若实际完成 safe-bypass 工作，仍需验证、写回进展，并 append 一次
   quota spend。如果 payload 返回 `notify_user_on_open_todo=true`，把开放 user todo 当作
   blocker-push，而不是静默 skip：用中文最多列 3 个开放项和期望回复格式，并且本轮不做
   delivery、不 append quota spend，除非同一个 blocker 最近已经问过。
   无论 `should_run` 是 true 还是 false，都先看 `effective_action`、
   `recovery_delivery_allowed`、`safe_bypass_kind` 和 `heartbeat_recommendation`。
   如果是 `outcome_floor_recovery`，这是 Codex 可执行 recovery turn：只允许做一次所需
   ranker/cross-domain evidence recovery，或写回阻止该 evidence 的具体 blocker；
   不做 surface-only / synthetic-only 循环，验证并写回后才能 append 一次 quota spend。
   如果不是 operator gate / blocker-push / outcome-floor recovery / 明确 safe-bypass，
   本轮不要做实现或 adapter 工作，只记录 public-safe reason；不要执行任何
   `agent_command`，即使 status 或 review packet 里提到过命令。只有当返回
   `should_run=true` 且 payload 里包含 `agent_command` 时，才执行该命令。如果
   `should_run=true` 但没有 `agent_command`，只按 `recommended_action`
   选择下一个安全只读动作。
   如果命令非零，fail closed，先修
   `goal-harness doctor` / `goal-harness status`。这个 guard 不等于写权限、
   不绕过 operator gate、也不替代 human reward。
   任何时候，如果你通过 read-only 分析、review doc、gate checklist 或 P0/P1 steering
   发现新的用户/owner 待办，不要只写在 `Next Action`、外部 review 文档或聊天里。
   立刻把它写进 active state 的 user todo 权威区：

   ```bash
   goal-harness todo add --goal-id <STABLE_GOAL_ID> --role user --text "<public-safe user/owner action>"
   ```

   agent 自己的后续动作写成 `--role agent`。写入后如果 dashboard 需要看到最新状态，
   运行 `goal-harness refresh-state --goal-id <STABLE_GOAL_ID>`。
   完整契约见 Goal Harness 仓库里的 `docs/project-agent-todo-contract.md`。
5. 如果需要把当前 packet 或已批准命令交给项目 agent，优先生成最小 handoff，
   不要从旧聊天、旧 review packet 或 `run_history.latest_runs` 拼当前状态。当前权威状态来自
   `attention_queue.items` / `project_asset`；如果缺少 `project_asset` 或标记为
   `legacy/raw fallback`，不要把 raw queue 字段当作 owner/gate/stop authority：

   ```bash
   goal-harness review-packet --goal-id <STABLE_GOAL_ID> --handoff-only
   ```

   只把输出的 handoff 交给目标项目 agent；完整 review packet 留给 operator view /
   evidence drill-down。
6. 如果要给这个项目设置 recurring Codex App heartbeat，不要手抄 guard 和
   spend 协议；先生成 task body，再把输出复制进 automation：

   ```bash
   goal-harness heartbeat-prompt \
     --goal-id <STABLE_GOAL_ID> \
     --active-state .codex/goals/<STABLE_GOAL_ID>/ACTIVE_GOAL_STATE.md
   ```

7. 生成一个 read-only project map 或 first pre-tick run。不要启动线上任务、
   不同步外部系统、不要写生产状态，除非目标文档明确授权。通用接入优先跑：

   ```bash
   goal-harness read-only-map --goal-id <STABLE_GOAL_ID>
   ```
8. 如果本轮只更新了 active state、ledger 或外部规划文档，没有产生新的
   adapter run，或者 dashboard 仍显示旧 run，追加一个 state-only refresh
   run；若本轮实际消耗了 automatic delivery compute，则把这个 refresh 放到
   quota spend 之后，避免 state refresh 先关闭 active delivery lane：

   ```bash
   goal-harness refresh-state --goal-id <STABLE_GOAL_ID>
   ```

   这个命令也会自动同步全局 registry。

9. 跑验证：
   - `goal-harness registry`
   - `goal-harness status`（在没有项目局部 registry 的目录里也应自动读共享全局 registry）
   - `goal-harness check --scan-path <PUBLIC_SAFE_FILE_OR_DIR>`
10. 如果本轮实际花了 automatic delivery compute（例如 read-only map、adapter tick、
   实现推进或验证推进），在 validation / writeback 完成后、任何可能关闭 active delivery
   lane 的 state-only `refresh-state` 之前，只 append 一次 quota spend；需要 dashboard
   或 controller 看到新状态时，再在 spend 后 refresh：

   ```bash
   goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <STABLE_GOAL_ID> --slots 1 --source adapter --execute
   ```

   不要为 quiet `should_run=false` skip、preflight 失败、或纯 dry-run preview 记账；
   如果 `should_run=false` 但实际完成了 `safe_bypass_allowed=true` 的 bounded
   safe-bypass 工作，要记一次账。不要重复执行。
11. 最后用中文汇报：
   - changed files；
   - validation output；
   - 当前 goal 在 dashboard/attention queue 里会怎么显示；
   - next safe action；
   - 如果还不能接入 decision-advisor，明确缺哪些 gates。
````

## Minimal Command

If the goal is simple and does not need a project-specific adapter yet:

```bash
cd <PROJECT_ROOT>
goal-harness connect \
  --goal-id <STABLE_GOAL_ID> \
  --objective "<OBJECTIVE_FROM_GOAL_DOC>" \
  --domain <DOMAIN> \
  --goal-doc <GOAL_DOC_PATH>
```

Then inspect:

```bash
goal-harness registry
goal-harness status
goal-harness check --scan-root .
```

## What Good Looks Like

The first connection is successful when:

- the project has a stable `ACTIVE_GOAL_STATE.md`;
- the registry points to that state file;
- the goal appears in `goal-harness status`;
- the attention queue says exactly who should act next;
- private evidence is kept in the project or local runtime, not in public docs;
- the next Codex tick can continue from saved state instead of re-reading the
  whole conversation.

For larger projects, the first useful adapter is usually read-only. It should
map documents, TODOs, validation surfaces, risks, and handoff packets before it
edits files.
