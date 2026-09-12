# Goal handoff mode

`handoff-mode` chooses the ownership rule used by existing Todo/lease operations:
`legacy` retains the claim/lease compatibility model, `soft_claim` uses the Todo
claim, and `hard_lease` requires the existing lease fences. It is not an Agent
capability grant, provider selector, or Goal promotion command.

## Read and change

```bash
loopx handoff-mode show --goal-id example-goal --format json
loopx handoff-mode set --goal-id example-goal --mode soft_claim --dry-run --format json
loopx handoff-mode set --goal-id example-goal --mode soft_claim --format json
```

Before promotion, these commands use the existing frontmatter writer and its
state/lease locks. After promotion, they use the selected canonical provider;
`show` returns `source=canonical_provider` and its `provider_revision`, even if
Markdown is stale or missing. `--runtime-root` applies to both show and set.
Provider errors fail closed. A leftover local lease file cannot override an
empty canonical lease collection.

A mode change requires no unfinished claimed active Todo and no time-active
lease. The canonical transaction checks the complete Todo/lease snapshot,
including records outside display limits. An expiry equal to the observation
time is expired; an invalid active lease timestamp or unknown lease schema
cannot prove quiescence. Concurrent mutations invalidate the CAS snapshot and
return a conflict without switching the mode. Todos, lease records and their
read-model digests are preserved by the mode change.

The unpromoted scan retains its older materialized-state scope: it does not
claim to include event-only Todos. Its quiescence decision and the canonical
transaction now share one typed policy. No default mode changes.

## Recover a canonical request

Choose an operation ID before a canonical set if a lost response must be retried:

```bash
loopx handoff-mode set --goal-id example-goal --mode soft_claim --operation-id mode-change-1 --format json
# Repeat this exact intent to recover its original receipt.
loopx handoff-mode set --goal-id example-goal --mode soft_claim --operation-id mode-change-1 --format json
loopx handoff-mode show --goal-id example-goal --format json
```

The ID binds the goal and requested mode. Reuse with a different mode is rejected.
A retry's clock may advance; it still recovers the original result. Even an
accepted unchanged canonical set seals a receipt and advances provider revision,
while returning `changed=false`. If another mode was selected afterward, replay
returns the original decision without restoring it. Use `show` for current mode.
Preview writes neither a mode nor an operation receipt. `--operation-id` requires
canonical authority; the legacy writer does not promise durable operation replay.

Select a previous mode with a **new** operation ID to change it back, subject to
the same quiescence check. Do not disable the writer fence or restore old Markdown
to roll back a canonical change. The existing Todo-section renderer does not
project frontmatter: canonical mode is read through `handoff-mode show`, not a
possibly old frontmatter value. This command does not qualify a provider profile,
complete D1–D3, deploy PostgreSQL, or authorize active-Goal migration.

## 中文

`handoff-mode` 选择 Todo 的 claim／lease 所有权规则，不授予 capability、不选择
provider，也不执行 Goal 晋升。上面的命令分别用于读取、预览和切换。

晋升前保留 frontmatter 与本地锁兼容路径；晋升后从 canonical provider 读取，
Markdown 缺失／陈旧和遗留本地 lease 不再影响判断。`show` 返回来源及 revision；
provider 失败明确报错，不回退旧文件。现有 Todo-section 投影不包含 frontmatter，
因此当前 mode 应通过 `show` 查询。

切换要求完整快照内不存在未完成的已认领活动 Todo、不存在有效 lease。过期时间
恰好等于观察时间视为已过期；非法有效期或未知 lease schema 不能作为空闲证据。
并发修改使 CAS 冲突，不能在旧检查结果上继续切换。原 Todo、lease 和摘要不变。
未晋升路径仍仅扫描物化状态，不宣称覆盖 event-only Todo；两条路径共用 TS 切换规则。

需支持丢响应恢复时，在首次 canonical set 前指定 `--operation-id`，重试沿用同一
目标 mode 和 ID。不同 mode 复用 ID 会被拒绝；即使最初 mode 未变，也记录耐久回执。
若后来已切到其他 mode，旧请求重放只返回原回执，不把 mode 改回去；用 `show` 读当前值。
预览不写入；旧 writer 不支持该幂等 ID。需要切回时，用新 ID 请求原 mode，仍须满足
空闲门禁，不能通过关闭 fence 或恢复旧 Markdown 回滚。本功能不解除 provider
默认值、长程资格化、PostgreSQL 部署或 D1–D3 的剩余条件。
