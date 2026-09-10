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
