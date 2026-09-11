# Manager context delivery

Built-in capability for original intent delivery and receiver-owned replanning.
The owner's local manager channel uses registered workers automatically.
External channels need an owner-configured grant in
`<runtime-root>/.local/manager-context/policy.json`:

```json
{"schema_version":"loopx_manager_context_policy_v1","sources":{
  "manager.external.example":{
    "sender_ids":["exact-provider-sender"],
    "targets":[{"goal_id":"research","agent_id":"worker"}]
  }
}}
```

Use the actual connection channel and provider sender identity. Keep this file
private (0600); do not commit it. Missing grants disable external delivery.
Remove a source/target grant to revoke future delivery, including replay attempts.
Provider ingress receipts bind the current message digest, channel and sender;
a model cannot create that provenance through its response.

The existing worker turn-start hook exposes only a bounded pending count and
required read command, without copying private content into status projections.
Read and record a decision through the installed CLI:

```sh
loopx --runtime-root <runtime-root> manager-inbox read --goal-id research --agent-id worker
loopx --runtime-root <runtime-root> manager-inbox acknowledge --goal-id research --agent-id worker --request-id <receipt-id> --decision no_change --reason 'Existing evidence still supports the current plan.'
```

Decisions are `adopt`, `defer`, `reject` or `no_change`. Read the original input
and current Core state before deciding. An adoption receipt does not prove task
completion. Later new evidence can generate a new decision through the ordinary
worker planning workflow; do not overwrite the original receipt. This feature
adds no periodic automation, forced wakeup, Todo priority or protected-operation
permission. Existing private inbox records are retained when delivery is revoked.

## Audience-authorized Goal summaries

An external manager's connection anchor is not its entire portfolio. The local
operator may grant a particular manager audience an explicit list of registered
Goals, independently of the sender-bound context-delegation targets:

```sh
loopx manager-inbox configure-read-scope --channel-id manager.external.0123456789abcdef01234567 --read-goal-id project-a --read-goal-id project-b
loopx manager-inbox configure-read-scope --channel-id manager.external.0123456789abcdef01234567 --read-goal-id project-a --read-goal-id project-b --execute
```

Use the exact channel identity from the existing manager session. The first
command is a read-only configuration preview; `--execute` is a trusted local
operator action, never a manager-generated proposal. Grant only Goal summaries
that may be visible to everyone in that audience. This does not authorize raw
private files, trading, mutation, or context delegation. New registered Goals
are not automatically added. Configure with no `--read-goal-id` to revoke the
read scope. Existing installations without a grant retain their connection
scope; removing the field restores that default. Private policy is stored under
`<runtime>/.local/manager-context/policy.json`, in `sources[channel].evidence_goal_ids`.
The live connection must still match; disabled, ambiguous or replaced sessions
cannot use an old grant. Every turn rechecks scope and discards upstream context
when it changes.

The manager now receives recent Core delivery receipts from the previous local
calendar day through collection time, separate from current Todo freshness.
Accounting rows are excluded before the presentation cap. Completed Todo titles
help explain recorded deliveries; archive coverage and omitted rows are explicit.
Reported outcomes and evidence-bearing receipts remain distinct, and neither
means the referenced artifact was inspected. Lark text replies preserve paragraphs
and use plain-text report formatting.

### Manager-directed Core inspection

The Codex Chat manager defaults to Astra with high reasoning effort (explicit
model/effort environment overrides remain supported). It receives a compact
authorized Goal directory, then uses
`loopx_manager_read` to choose portfolio, current Todo and recent delivery reads.
The packaged `loopx-manager` skill is installed in its dedicated workspace and
included in its operating instructions. This reuses Core providers and the
existing manager-context delegation contract; it does not create another source
of progress or expose a general shell.

Routine inspection excludes Goals explicitly stopped in Core, before status
collection and detail reads. Coverage reports how many were skipped. Stale or
unknown progress remains eligible. An explicit historical question can discover
stopped identities using the portfolio tool and then read the selected Goal.

Each read checks the current audience grant before and after provider access,
returns source revisions and pagination, and records a `manager.evidence_read`
receipt. Unavailable sources and oversized rows remain explicit unknowns. The
recent delivery window is still yesterday through now; arbitrary artifact paths
and external links are not fetched. Existing non-Codex adapters retain their
context projection until they implement an equivalent tool contract.

Manager context version 7 starts a fresh upstream session for older manager
contexts. The logical Chat session and its receipts remain intact. Runtime support
uses the Codex app-server dynamic tool protocol; explicit upstream terminal
errors remain errors and are not retried as part of inspection. The version
change registers the expanded handoff tool schema on existing installations;
resuming an old upstream thread would retain its previous dynamic tools.


## Track a delegated request

The default receiver hook checks for pending context. `manager-inbox read`
records that its output supplied the original message to the receiver; a quota
peek does not record a read. New delivery and decision records carry event
timestamps. Historical records retain unknown times rather than using file
modification time as a fabricated event.

The receiver associates canonical work after deciding:

```sh
loopx manager-inbox link --goal-id research --agent-id worker \
  --request-id <request-id> --related-todo-id <core-todo-id> \
  --evidence-id sha256:<evidence-digest>
loopx manager-inbox status --goal-id research --agent-id worker \
  --request-id <request-id>
```

Links are bounded, additive and idempotent. Todo links must belong to the
receiving Agent, and their current titles/statuses come from Core, not a copy in
the inbox. Evidence links are receiver assertions, not independently verified
artifacts. The inbox does not assign priority or declare overall completion.

In frontend or Lark Chat, ask the manager whether a request was delivered/read,
what decision was recorded, and which work it links to. Both entrances use
`loopx_manager_read` with `view=handoffs`. External reads require the current
Goal evidence grant and exact originating audience; they omit original message
bodies and private decision reasons. Legacy audience recovery uses only the
provider-recorded ingress, and ambiguous/missing provenance stays hidden.
Revocation is checked before and after query. This does not append a message to
an unrelated host session or create another scheduler.
