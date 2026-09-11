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

Manager context version 10 starts a fresh upstream session for older manager
contexts. The logical Chat session and its receipts remain intact. Runtime support
uses the Codex app-server dynamic tool protocol; explicit upstream terminal
errors remain errors and are not retried as part of inspection. The version
change refreshes the operating contract on existing installations;
resuming an old upstream thread would retain its previous instructions.

### Remote evidence sources

The manager discovers SSH aliases through the same host catalog as the frontend
source switcher. `loopx_manager_read view=sources` lists eligible sources; select
`source_id=ssh:<alias>` for portfolio, Todo or delivery reads. Reads execute a
fixed, bounded CLI projection on the selected host, using its global registry,
not local tasks whose titles mention SSH. Source host and Goal ID jointly identify
the evidence; a missing declared execution `host_id` does not erase source provenance.

Owner-local conversations may inspect configured hosts on demand. External
conversations require a persistent, exact host/Goal read grant from the local
operator, in addition to their live connection authorization:

```sh
loopx manager-inbox configure-ssh-read-scope --channel-id manager.external.0123456789abcdef01234567 --ssh-host research-host --read-goal-id project-a --execute
```

Omit `--execute` for a preview; pass no Goals to revoke that host. This grants
summary reads only, not delegation, shell commands or remote writes. Changed
grants invalidate upstream manager context; revocation during a read discards
the result. No remote connections occur merely to list sources. Offline hosts,
older unsupported remote runtimes and missing Goals remain explicit unknowns.

The remote CLI uses `goal-portfolio --manager-view portfolio|todos|deliveries`
and the same Core readers as the local manager. Pagination remains explicit.
Delivery reads support `days=1..90` so latest known historical outcomes can be
explained alongside fresh current Todos without pretending stale execution is
current. Both hosts need the updated LoopX runtime.


## A delegation returns automatically

The default interaction is one exchange: initial delivery receipt, receiving
Agent assessment/work, then an audience-ready conclusion back in the original
conversation. Status queries are optional inspection, not the completion path.
The receiving Agent still owns relevance and priority; normal context delivery
never changes its Todos or interrupts its current work.

`manager-inbox read` records the first provision of context to the receiver.
After `acknowledge`, the request remains in the turn-start hook until the worker
publishes a conclusion. The worker uses `link` for canonical Todo/evidence lineage
and `report` to publish the answer intended for the original audience:

```sh
loopx manager-inbox acknowledge --goal-id research --agent-id worker \
  --request-id <id> --decision adopt --reason 'Private reasoning about the plan.'
loopx manager-inbox link --goal-id research --agent-id worker \
  --request-id <id> --related-todo-id <core-todo-id> --evidence-id sha256:<digest>
loopx manager-inbox report --goal-id research --agent-id worker \
  --request-id <id> --phase conclusion --reply-text 'What was assessed or changed, what was validated, and what remains.'
```

For longer work, `--phase decision` optionally returns a meaningful intermediate
update. A ready conclusion supersedes an unsent intermediate update. Do not send
one notification per poll, quote private deliberation, or claim an implementation
request finished merely because a plan exists. A research-direction request can
conclude with the adopted/rejected planning decision; deferred or blocked work
must explain the concrete condition and next action. Completion of this exchange
is separate from completion of the receiving Goal.

The Chat server hosts a cheap local receipt pump (no model calls and no Codex
automation). It appends a deduplicated follow-up to the original transcript;
the open frontend picks it up automatically. For Lark it reuses the current
binding, captured source Inbox, provider preview, idempotency key and readback.
It waits until the initial reply is acknowledged, revalidates authority before
sending, and never retargets a closed/replaced conversation. An offline transport
retries the persisted answer rather than rerunning the worker. Ambiguous external
writes remain `verification_required` and are not blindly resent.

New handoffs persist their exact original return route. Legacy requests remain
queryable; a receiver can explicitly report one only when its exact persisted
Chat receipt uniquely recovers the route. Historical timestamps stay unknown.
Replies are immutable and additive, separate from private decision reasons and
Core progress. Query `manager-inbox status` or `loopx_manager_read view=handoffs`
for delivery diagnostics. These queries are not required from the user.
