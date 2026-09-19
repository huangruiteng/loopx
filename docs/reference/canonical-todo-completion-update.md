# Canonical User Todo completion updates

A promoted local Goal routes `todo update --status done` for **User Todos**
through the TypeScript terminal transaction. File and SQLite use the same
semantic owner; PostgreSQL exercises it through the service-owned provider.
This does not select a default provider or promote an existing Goal.

```sh
loopx todo update --goal-id example --todo-id todo_observation \
  --agent-id agent-a --status done --note 'Observed outcome verified' \
  --no-follow-up --update-operation-id observation-completion
```

Use the same operation id and intent after a lost response. A new annotation
uses a new id (omitting the id generates one). `--dry-run` validates and previews
without running declared validation, writing a receipt, or delivering a display.
Agent completion continues to require `loopx todo complete`.

## One edit, one terminal transaction

The update decoder, authoring planner and record materializer are shared with
ordinary edits. The terminal owner checks the **original** Todo's completion
authority and the edited record's update authority; clearing a claim or binding
cannot turn an update-only grant into a completion grant. Existing lease
ownership/requirement restrictions remain: an annotation cannot rewrite an
execution grant. Supplied lease proof must identify a current execution;
expired explicit proof does not enable automatic reacquisition.

The transaction checks linked successors before issuing validation effects.
Self-links and missing successors fail without running a caller command. This
ordering also applies to the existing complete/supersede transaction. Completion
does not invent a decision outcome: use the explicit decision workflow when an
approval, rejection or cancellation must be recorded.

A declared validation command runs in the host after TS admission. The resumed
update binds the issued provider revision, retains the registry source witness,
and refreshes the clock. Any intervening provider commit rejects that resume,
even an unrelated Todo edit. Retry re-reads and revalidates; validation itself
may have external effects. Registry witnessing is optimistic, not an atomic
cross-resource authorization transaction or an executor-held effect fence.

Todo fields, completion state, lease release, projection intent and the business
receipt commit together. Release preserves the existing lease version and epoch.
Markdown is a display projection and is not required to admit a completion.
Private validation declarations remain in their private store; they are neither
imported from an untrusted display nor embedded in public completion receipts.

## Linked User completion effects

An admitted `todo complete --decision-outcome approve|reject|cancel` now commits
its exact linked Agent Todo effects in the **same** provider transaction as the
User completion and receipt. Ordinary User actions completed through update or
Chat use the same rule. `todos/user_completion.ts` owns this decision for both
canonical providers and the legacy Markdown adapter; Python retains locked
snapshot extraction and writeback, not a second scope/resume implementation.

| Decision / current target | Effect |
| --- | --- |
| Approve a linked gate | Consume only covered required scopes and their recorded negative outcomes; preserve independent requirements. |
| Reject or cancel a linked gate | Keep requirements, replace the latest outcome for that exact scope, preserve independent outcomes, and block the active target. |
| Complete a linked User action | Attempt resume without consuming decision authority. |
| Another active linked User Todo, remaining requirement or negative outcome | Keep the blocked target blocked. |
| Explicit blocker task | Require explicit blocker repair. |
| Completed, deferred or archived target | Do not change or reactivate it. |

Approval can consume a requirement on an already open target. Resume preserves
its claim; it does not acquire or transfer the **Agent target's** lease. The
existing exact-gate auto-acquire/release contract still applies to the completing
User gate itself. Supersede never runs approval effects. An unrelated Todo or
unlinked standing approval is outside this exact-target mutation.

This fixes canonical completion previously leaving an approved target stranded.
It also intentionally tightens **both** legacy and canonical behavior: partial
approval cannot resume work with unmet requirements, and late rejection cannot
revive terminal/deferred work. Normal completion without a linked target is
unchanged. No provider selector or capability default changes.

`unblock_resume` and `decision_scope_resolution` are historical business results,
not fresh permission. Existing receipt identities remain valid. Replaying a
pre-fix receipt does not retrofit missing effects; an already completed gate is
not a new owner decision. Reconcile such an inconsistent target against the
recorded decision through an explicit reviewed repair. Never reopen a gate just
to obtain another approval, or change an operation id to reinterpret old intent.

Concurrency rejection writes neither the User completion nor its dependent
effects. After a lost response, recover the same receipt; after display loss,
rebuild from the current canonical head. The packaged Chat HTTP tests cover
linked User-action completion, failed validation, readback and proposal retry.
The existing decision-gate UI directs explicit decisions to the CLI, so no new
frontend control or Lark permission surface is introduced.

关联 User 完成与目标 Agent Todo 的决策消解、阻塞状态、原操作回执在同一事务内提交。
旧 Markdown 路径也调用同一个 TS 规则；Python 仅保留锁内快照适配与写回。批准只消解
覆盖的要求，拒绝/取消保留要求并记录结果；普通 User action 不消费授权。其他关联
User Todo、剩余要求或拒绝结果仍会阻止恢复；已完成、延期、归档任务不会被晚到决定
重新激活。上述两项安全修复同时影响旧路径和 canonical 路径，其他默认值不变。
重放返回历史回执，不补做旧版本遗漏的联动，也不产生新的授权；历史不一致须根据
原决定显式核对修复。目标任务的执行租约与用户批准仍是不同合同。

## Recovery and callers

- Historical replay precedes current source admission and returns the original
  business receipt. Changed edit intent with the same operation id is rejected.
- An already completed User Todo can receive a new completion-update annotation
  without rerunning validation or changing its completion timestamp. This does
  not reopen the Todo or grant further execution authority.
- The existing Chat User-completion action uses its reviewed canonical revision
  and proposal operation id. Failed validation produces a failed proposal with
  no success receipt. Pending display delivery is retryable; a retry recovers
  the canonical operation before checking present-day freshness, then projects
  the current head. Agent completion keeps its existing dedicated route.
- CLI and Python use the same public facade. No frontend layout, action name,
  status selector or provider setting is added. The shared typed review plan
  now exposes the original-operation retry for canonical User completion too.
  The existing completion button
  and failed-proposal retry interaction remain the user entry points.

The same synthetic pending-completion proposal on the packaged desktop surface:
[before: omitted from recoverable proposals](images/canonical-user-completion/before.png),
[after: the original-operation retry](images/canonical-user-completion/after.png).
These images use the repository's synthetic workspace fixture, not a live Goal.
No responsive layout changes are involved.

The local update transport uses request v3 for the completion envelope. v0–v2
reject that envelope instead of silently accepting only part of the intent.
Their ordinary update behavior and receipt encoding remain unchanged. The
provider-neutral terminal receipt includes the User edit identity only for this
new operation family; existing complete/supersede receipt identities remain valid.

## Migration boundary

Unpromoted Goals retain their existing Python Markdown/event adapters. The
shared host validation executor and failure projection replace duplicated
transport plumbing; the TS edit decoder/materializer is no longer owned only
by the ordinary update transaction. Permanent rendering and private command
execution still have real Python callers and are not retirement candidates.

This closes the User completion-update caller within TS T1/T2 and local-default
L2. It does not close every Monitor/event caller, executor-held effect fencing,
D1 consumer recovery, SQLite D2 capacity/elapsed soak, or D3 whole-Goal cutover.
See the [local-default program](../architecture/rfcs/shared-goal-authority-state-provider-v0.md#execution-handoff-and-integration-order).

Rollback the code before using the new caller, or finish/retry its outstanding
projection delivery before downgrading. Older binaries reject request v3 and
cannot recover this operation through the old update route. Existing durable
Todo/lease records, historical receipts and permanent import/export obligations
are not removed by this change; never revive stale Markdown as authority.
