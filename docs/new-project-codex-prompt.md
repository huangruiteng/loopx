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

```text
我有一个新项目要接入 Goal Harness。

项目文件夹：
<PROJECT_ROOT>

项目目标文档：
<GOAL_DOC_PATH>

请你按下面步骤推进，不要停在方案讨论：

1. 先只读检查项目文件夹和目标文档，抽取：
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
4. 生成一个 read-only project map 或 first pre-tick run。不要启动线上任务、
   不同步外部系统、不要写生产状态，除非目标文档明确授权。
5. 跑验证：
   - `goal-harness registry`
   - `goal-harness status`
   - `goal-harness check --scan-path <PUBLIC_SAFE_FILE_OR_DIR>`
6. 最后用中文汇报：
   - changed files；
   - validation output；
   - 当前 goal 在 dashboard/attention queue 里会怎么显示；
   - next safe action；
   - 如果还不能接入 decision-advisor，明确缺哪些 gates。
```

## Minimal Command

If the goal is simple and does not need a project-specific adapter yet:

```bash
cd <PROJECT_ROOT>
goal-harness connect \
  --goal-id <STABLE_GOAL_ID> \
  --objective "<OBJECTIVE_FROM_GOAL_DOC>" \
  --domain <DOMAIN>
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
