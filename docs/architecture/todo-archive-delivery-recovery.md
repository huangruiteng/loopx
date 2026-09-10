# Todo archive delivery recovery

This contract hardens the promoted archive transaction introduced by
[#4053](https://github.com/huangruiteng/loopx/pull/4053), under the
[TypeScript control-plane migration RFC](./rfcs/typescript-control-plane-migration-v0.md).
Archive selection, standing-decision retention, CAS, and historical receipts
remain owned by the native transaction.

## Pending delivery and retry identity

The local TypeScript adapter durably records one pending archive attempt per
goal and role before executing the transaction. The record binds the operation
ID, retention limit, observed provider revision, and authority store identity.
It is correlation state, not a second Todo authority or a copy of the receipt.
The existing per-goal maintenance lock serializes attempt creation and retirement.

While that attempt is pending, a repeated archive request for the same role and
limit reuses its identity. Receipt replay precedes current-head revision checks
and archive selection, so a committed result survives a process exit before
Markdown projection, a projection write failure, and unrelated head advancement.
The replay reports the original receipt, moved IDs, count, and revision without
creating another canonical commit. A different retention limit is rejected
until the pending delivery is settled.

Fresh Python requests bind the revision they actually observed. If that head
changes before selection, the native transaction rejects the stale request.
Older v0 callers that omit the optional revision retain their original receipt
hash. A fresh attempt preserves an explicitly supplied revision; a pending
retry keeps the original attempt's binding rather than today's observed head.

After the Python projection adapter delivers or verifies the current canonical
view, it acknowledges the exact operation through
`coordination.local_authority.todo_archive_ack`. The native owner checks the
receipt and store identity before retiring the attempt. A stale acknowledgement
cannot retire a newer attempt. Transport failure preserves the already committed
result; uncertain transaction outcomes retain the pending identity for retry.
Proven pre-commit rejection releases it so a corrected request can proceed.

Preview bypasses pending attempts and historical receipt replay and performs no
writes. A fresh empty archive creates no canonical receipt and does not advance
the provider revision. Local correlation storage is bounded to two slots per
goal, independent of archive history size.

## Delivery boundary and migration cost

The recovery boundary ends at successful projection acknowledgement. A later
identical CLI invocation is a new archive request and can process a new batch.
This does not promise recovery of a CLI response lost after acknowledgement or
discover attempts made before correlation records existed. Callers requiring
that stronger guarantee need an explicit caller-retained request identity.

Missing Markdown can be rebuilt from canonical Todos during archive retry;
successful recovery still requires the same exact-attempt acknowledgement.
An explicit `todo project-markdown` rebuild repairs the display without
acknowledging an archive attempt. The next archive with the same role and limit
first replays and acknowledges that prior batch; it does not archive a new one.

A changed promoted archive uses four Python/TypeScript request-responses:
authority read, archive transaction, projection readback, and acknowledgement.
The previous path used three; empty and preview paths add no acknowledgement.
The extra durable correlation writes and acknowledgement are a correctness cost,
not a claimed migration speedup. Archive domain rules stay in TypeScript.
Retire the separate Python ACK bridge when the canonical journal consumer owns
both projection delivery and exact-attempt acknowledgement. Remove facade parts
as their concrete callers converge, retaining required Python projection
adapters. A native CLI permits full transport removal; it is not a prerequisite
for retiring redundant boundaries. Keep provider receipts and independent
crash/retry conformance coverage.

## 中文契约

本变更修复 promoted archive 在 canonical commit 后、Markdown 投影交付前失败时的
重试身份丢失。TypeScript 在执行前持久记录每个 goal/role 的未交付 operation ID、
保留数量、观察到的 provider revision 和 store identity。相同 role/limit 的重试先
恢复原 receipt，再考虑当前 head；不会重复提交，也不会把原归档数量错误地报告为零。
未完成交付时修改保留数量会被拒绝。

新 Python 请求绑定实际读到的 revision；无历史 receipt 且 head 已变化时拒绝执行。
旧 v0 请求省略 revision 时保持原有请求 hash。预览不读取未交付记录、不重放历史结果、
不写状态；空归档不推进 canonical revision。确认仅在投影交付成功后进行，且必须匹配
原 operation、receipt 和 store。过期确认不能清除新操作；结果不确定时保留重试身份，
确定未提交的拒绝允许后续修正请求继续。

Markdown 缺失时，归档重试可从 canonical Todos 重建投影，成功后仍须确认原 attempt。
单独运行 `todo project-markdown` 只修复显示，不确认归档 attempt；之后相同 role/limit
的归档调用会先重放并确认旧批次，不会归档新一批。

恢复保证截至投影确认成功；之后相同 CLI 调用代表新一批归档，不承诺恢复确认之后才
丢失的 stdout，也不追溯发现旧版本未记录的调用。发生归档的路径从三次跨运行时调用
增加为四次，额外确认和持久化是明确的正确性成本。canonical journal 消费者同时接管
投影交付与精确 attempt 确认后，删除独立 Python ACK 桥接；按具体调用者收敛逐步删除
facade，保留仍必需的 Python 投影 adapter。原生 CLI 允许彻底移除 transport，但不是
删除冗余边界的普遍前提。保留 provider receipt 和独立崩溃恢复测试。
