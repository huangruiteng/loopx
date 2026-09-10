# Managed Codex heartbeat prompt upgrades

## Product contract

Default execution remains `heartbeat-prompt --thin`. An adopted automation
stores a small, stable bootstrap instead of a copy of the current execution
rules. At **every wake**, it requests the complete JSON thin prompt from the
installed LoopX, with an explicit registry, Goal, agent and host capability
binding, then follows that prompt. After a normal LoopX upgrade, the next wake
reads the new rules; no per-release Codex database rewrite is needed. An already
running wake keeps its current instructions. This is model-mediated loading,
not a guarantee that a model will obey every instruction.

The bootstrap is a transport wrapper, not a new execution mode. It does not
default to full/compact prompts, contain a parallel work policy, or create
another scheduler. Failure to load a complete successful response stops work
and spending; it must not fall back to remembered rules. Project watches and
business policy belong in LoopX state, not in this bootstrap.

For a one-agent trial, pass `--cli-bin loopx-canary` to preview and apply. The
bootstrap and the thin prompt's generated commands both use that executable;
other automations continue to use their existing runtime. Do not promote the
canary as the global default merely to test one task.

The owner is the existing heartbeat/upgrade boundary; there is no new optional
capability or extension provider. SQLite/TOML handling is a local host adapter,
not Todo, quota or scheduler authority.

## Preview and adopt existing tasks

```sh
loopx --format json automation-prompts plan --plan-file ./private-prompt-plan.json
```

The plan contains current and proposed prompts and is **private local data**.
Do not commit, upload, or paste it into public issues. The file is owner-only.
Use repeatable `--automation-id` selectors to narrow the plan. Discovery uses
registered Goal/agent identities only to propose candidates; it never grants
permission to overwrite them. Unrelated, ambiguous and inconsistent host
records are not adopted. Review custom instructions before replacement: move
durable project policy to its LoopX owner, or leave that task unadopted. There
is no automatic prose merge or substring-based permission to replace a prompt.

While the Codex App is running, prefer its `automation_update` interface:
view each selected task, verify its current prompt against the preview, update
only the prompt to `desired_prompt` while preserving every other field, then
read it back. Do not recreate the task or rebind its thread. A single user
request can authorize this reviewed batch; the plan itself does not execute it.

When that API is unavailable, the qualified macOS offline fallback is:

```sh
# Review the plan, then close the Codex App first.
loopx automation-prompts apply --plan-file ./private-prompt-plan.json --offline --execute
```

The same registry/runtime-root and Codex home must be used for preview and
apply. `--codex-home` explicitly selects one home; the command never searches
other homes or copies sessions between them. No new automation is created.
Schedule, pause state, model, notification preferences, thread binding and run
history are preserved. Each selected task commits independently; the command
reports partial failure instead of claiming the whole batch succeeded.

Only existing heartbeat records with matching SQLite/TOML identity, prompt,
status and thread binding are eligible. Unknown schemas and stale previews fail
closed. The fallback checks that the macOS App is closed; keep it closed until
readback completes. Restart afterward. This adapter targets the observed local
schema, **not an official stable Codex storage API**; no Windows/cloud support
is claimed. Use the native API if the host changes its storage contract.

## Recovery and rollback

The fallback stores a private per-task journal before writing. SQLite commit
and TOML replacement are not one transaction: a crash can leave a mirror pending.
While the App remains closed, recover that exact task:

```sh
loopx automation-prompts recover --automation-id TASK_ID --offline --execute
# Or restore the previous prompt:
loopx automation-prompts rollback --automation-id TASK_ID --offline --execute
```

Recovery is idempotent. It refuses to overwrite later prompt/metadata edits.
The journal remains under the selected Codex home's `loopx-automation-backups`
directory; do not publish it. Rollback restores only the recorded prompt,
never an entire historical database or session table. Native API migrations
should retain the reviewed previous prompt privately and use that same API
for rollback.

Disable automatic rule adoption by replacing the bootstrap with an explicitly
pinned prompt using the App, or pause the task there. LoopX runtime rollback
also changes the rules loaded on the next wake. Future incompatible bootstrap
revisions still require an explicit migration; the v1 wrapper does not silently
rewrite itself. `upgrade-plan` recognizes exact v1 wrappers as runtime-loaded
thin prompts, rather than repeatedly reporting their body as stale.

## 中文摘要

默认仍是 thin。一次迁移后，automation 每次唤醒读取已安装 LoopX 的最新
thin 指令；之后升级 LoopX 即可让下一轮采用新版规则，无需逐版本改 SQLite。
正在运行的轮次不热切换。启动器不是另一套执行规则，也不增加权限。

先批量预览，再明确接管；自定义内容不猜测合并，不自动删除。App 运行时用
原生更新接口；离线兼容通道要求关闭 App、精确预览校验、双存储读回，并保留
私有恢复记录。日程、暂停状态、模型、线程、通知偏好和历史均不迁移。
本批提供命令行批量迁移，不新增 Dashboard 按钮；也不保证模型行为已通过在线评测。
