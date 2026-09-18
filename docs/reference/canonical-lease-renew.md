# Canonical lease acquisition and lifecycle

An already promoted File or SQLite Goal runs `task-lease acquire`, `renew`,
`transfer` and `release` through TS-owned provider transactions. Fresh execution
and expired/ineffective-holder takeover now use the complete canonical head;
previously standalone acquire still entered the fenced legacy file writer.
Unpromoted Goals retain their legacy wire and transaction. A provider selector
does not promote a Goal or grant execution authority.

For a new execution on an open, eligible Todo with no prior lease:

```bash
loopx --registry registry.json task-lease acquire \
  --goal-id example-goal --todo-id todo_work --owner agent-a \
  --idempotency-key execution-a --expected-version 0 \
  --ttl-seconds 600 --write-scope 'src/**'
```

After expiry/release, use a new execution key and the current version from
inspect, rather than version 0. Active effective holders and overlapping scopes
on other effective leases reject acquisition. Archived, excluded, unregistered
or claim-conflicting holders do not block another eligible execution. The scan
uses all retained records, not the bounded operator display. Atomic
`todo claim + lease` shares the same facts, decision and record materializer.
Standalone acquire uses requested scopes; atomic claim retains its existing
Todo-required scope intent. Neither operation expands a permission grant.

## Operate the current lease

Read the current canonical lease and use its owner, execution key and version:

```bash
loopx --registry registry.json task-lease inspect \
  --goal-id example-goal --todo-id todo_work --format json
loopx --registry registry.json task-lease transfer \
  --goal-id example-goal --todo-id todo_work --owner agent-a \
  --idempotency-key execution-a --expected-version 3 \
  --new-owner agent-b --new-idempotency-key execution-b --ttl-seconds 600
loopx --registry registry.json task-lease renew \
  --goal-id example-goal --todo-id todo_work --owner agent-b \
  --idempotency-key execution-b --expected-version 4 --ttl-seconds 600
loopx --registry registry.json task-lease release \
  --goal-id example-goal --todo-id todo_work --owner agent-b \
  --idempotency-key execution-b --expected-version 5
```

The example assumes an active lease at version 3 and an unclaimed Todo or a Todo
already assigned to the eligible receiver. Transfer does not reassign the Todo
claim, override an exclusion, or widen write scopes. Use the actual readback
versions, not these example numbers.

| Operation | State change | Admission |
| --- | --- | --- |
| Acquire / takeover | Version +1 and epoch +1; new execution identity and expiry | Open active Todo, registered eligible actor, no effective conflicting holder or overlapping execution; optional version CAS |
| Renew | Version +1; owner/key/epoch/scopes unchanged; expiry is runtime clock + TTL | Active lease, current proof, registered eligible owner, active open Todo |
| Transfer | Version +1 and epoch +1; replace owner/key; retain scopes; set expiry | Active lease, current proof, registered sender and eligible receiver; new execution key |
| Release | Retain version/epoch; persist released status and timestamps | Current owner/key/version proof; expiry, removed registration and closed/archived Todo do not prevent cleanup |

A missing lease at expected version 0 or an already released matching lease
returns a durable `no_change` receipt. Its storage cursor can advance while
lease state, timestamps and domain events remain unchanged. A wrong version or
wrong proof never becomes successful cleanup. Acquire/renew/transfer reject archived
Todos and safe-integer generation exhaustion before writing. The generation
check also protects the legacy path; release at that generation remains legal.

## Commit, retry and readback

One provider CAS commits the lease projection, event and original receipt.
Maintenance operation identity includes operation, Goal, Todo, owner, execution
key and expected version. The immutable request digest additionally binds TTL and the
transfer receiver/key. A retry with changed intent is rejected. The shipped
renewal receipt schema, identity and digest encoding remain compatible.

For maintenance, `status=replayed` and `idempotent=true` return historical results even after a
later renewal, transfer, release or expiry. They do not grant present execution
rights or renew again. Freeze the original request after a lost/ambiguous
response; recover its receipt, then inspect current state before new work.

Acquisition identity binds Goal/Todo/owner/execution key; the request digest
also binds original expected version, TTL and scope set. An exact retry of
`--expected-version 0` recovers its receipt instead of failing against the
version it created. A changed request under that identity is rejected.
Acquisition **success requires current proof**: an active, still-eligible lease
with the same owner/key/epoch. Replay after renewal returns the current
version/expiry in `lease`, with the unchanged original decision in
`original_receipt`; `current_provider_revision/current_cursor` identify that
readback. A transferred, expired or released execution cannot be revived by its
old receipt. Claim receipts and maintenance receipts retain their historical
semantics; they are not acquire responses.

The canonical-only acquire and lifecycle requests are closed and versioned. The prior
renew-only wire remains accepted for renewal only. An older runtime rejects the
new schema entirely. Missing/invalid fences, changed registration facts before
acquire/renew/transfer, unavailable providers and CAS conflicts fail closed. They never
fall back to a lease file or stale/malformed Markdown. Release admission uses the existing proof without a registration snapshot.
The CLI still resolves its runtime root from the registry or explicit override.

Responses expose provider/revision/cursor and current-versus-expected version
on a version conflict. They do not invent a `lease_path`, write a second shadow
authority or require Todo Markdown regeneration for a lease-only change.

## Provider and delivery boundary

The local opening handle supplies provider provenance; lease commands no longer
classify stores with concrete File/SQLite class checks. PostgreSQL uses that
same handle only when a service owner supplies the existing scoped factory and
matching store incarnation. There is no credential-bearing CLI option, implicit
service activation or fallback. The real PostgreSQL rehearsal exercises this
public native lifecycle route as well as the storage contract.

This closes standalone acquisition/takeover and existing-lease mutation under
shared-authority L3 / roadmap R5. Real CLI validation carries newly acquired
proof into canonical Todo completion and released readback. Complete/supersede
can use canonical state with a missing Markdown display, then rebuild it through
the existing projection outbox; legacy source requirements remain unchanged.
Executor holder/terminal locks across external effects and automatic cross-agent
result return retain their own callers and qualification. A lease
transfer alone does not prove a completed collaboration journey. No storage
format, default profile, active-Goal migration, D2 soak or D3 promotion changes.

Rollback retains canonical state, receipts and the writer fence. Older code may
reject acquire/transfer/release or the new wire; plan for current lease expiry and
restore compatible code. Do not remove the fence or revive stale lease files.

## Validation

The shared production-scale fixture covers fresh execution, takeover and handover while
retaining its mixed status, decision and historical-lease population. Every
AuthorityStore conformance arm covers native/imported records, negative
admission, a live scope holder beyond display limits, stale senders, response loss, CAS competition, no-op sealing and
historical replay. Real File/SQLite CLI and killed-process tests cover the host
boundary; PostgreSQL uses an isolated real server. NoKV coverage uses its
existing test transport and is not service qualification.

For a read-only Goal snapshot, compare an immutable clean legacy checkout with
File, SQLite and real PostgreSQL through the native public lifecycle entrypoint:

```bash
# LOOPX_TEST_POSTGRES_URL must identify a disposable server.
uv run --extra test python examples/control_plane/authority-lease-lifecycle-rehearsal.py \
  --registry registry.json --goal-id example-goal \
  --baseline-repo ../loopx-baseline --execute-isolated-postgresql
```

Use the source-checkout Python environment and a qualified SQLite Node runtime.
The runner adds two synthetic Todos and one initial lease only to disposable copies, compares
all operation results and non-target records, and verifies that the live source
is unchanged. It separately reports the legacy create-CAS retry mismatch and maintenance
historical-replay rejection as semantic improvements, not normalized parity. Optional `--private-diagnostics`
keeps raw failures in an owner-only file that must not be published. This does
not replace [D2 capacity and continuity qualification](sqlite-authority-store.md).

## 中文操作与语义

已 promoted 的 File/SQLite Goal，其 acquire、renew、transfer、release 现在使用
同一 provider opening/source fence 与 TS 规则；新领取和失效持有者接管不再进入
旧文件 writer。旧 wire 与未 promoted 路径保留，选择 provider 不构成 promotion。

新执行按上面的 acquire 命令领取；没有旧 lease 时 expected-version 为 0，否则
用 inspect 的当前版本及新的 execution key。领取/接管同时增加 version 和 epoch，
续约只增 version，转交同时增二者并换 key；释放保留 generation。转交不改变 Todo
claim、不覆盖 exclusion 或扩大 scope；释放只凭匹配 proof，允许到期或注销 owner
清理。所有需递增的入口都拒绝安全整数耗尽，仍允许释放。

完整 canonical Todo/lease 集合决定 scope 冲突，不能只看 UI 页面。归档、排除、
注销或与当前 claim 冲突的 holder 不阻挡新的合格执行。独立 acquire 和原子的
Todo claim + lease 共用状态解释、准入和 materializer；前者使用请求 scopes，后者
仍使用 Todo required scopes。scope 是执行冲突声明，不扩张权限。

一笔 CAS 保存 lease/event/原 receipt。维护操作的身份与既有 renew digest 保持
兼容，历史 replay 可跨后续修改，但不授予当前执行权。Acquire 的身份绑定
Goal/Todo/owner/key，digest 另绑定原 expected version、TTL、scope set；创建时
expected-version 0 的原样重试可恢复回执，改变参数会拒绝。

Acquire 的成功还必须核对当前有效 owner/key/epoch 和资格。同一执行续约后，
重试返回 `lease` 中的当前版本/到期时间，以及 `original_receipt` 中不可变的原始
决定；`current_provider_revision/current_cursor` 标识当前读回。已转交、到期或释放
的旧执行不能凭 receipt 复活。Todo claim 和维护 receipt 仍是历史语义，不能将其
当成新的 acquire 响应。

canonical acquire 与 lifecycle 各有封闭 wire，旧 renew wire 只接受 renew；旧
runtime 不识别新 acquire schema。fence、provider、注册源变化和 CAS 错误不回退
旧文件。lease-only 命令不生成第二份 shadow 或重写 Markdown。真实 CLI 验证包含
新领取→续约→释放→新执行→完成；complete/supersede 可在 Markdown 展示丢失时
读取 canonical state，完成后经原 projection outbox 重建，旧路径仍要求源文件。

PostgreSQL 使用已有 service-owned scoped factory 和 incarnation 检查，无新凭据
参数或自动启用。四臂演练使用相同公共 native 入口；NoKV 仍只经过测试 transport。
L3/R5 的独立领取/接管及维护由此可用，跨外部 effect 的 executor holder/terminal
锁和自动结果返回仍需各自验收。D2 soak、D3、默认 profile、活动 Goal 迁移和跨主机
部署没有改变。回滚保留 canonical state/receipt/fence 并恢复兼容代码，不得复活旧
lease 文件。演练仅修改隔离副本，核对源与无关记录不变，不能代替完整持久性资格。
