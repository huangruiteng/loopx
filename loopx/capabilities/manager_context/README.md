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

The manager now receives a bounded recent-evidence window of Core delivery
receipts instead of a single local calendar day: seven days by default, with an
eight-receipt per-day and 48-receipt per-Goal bound, starting at local midnight
and ending at collection time. `evidence_window` states the window bounds, the
limits, per-day matched counts, and included versus omitted receipts, so a week
question does not silently narrow to today and a wide window cannot grow the
model context without a bound. Within the window each Goal's newest receipt keeps
full `recorded_details` while older receipts are compacted to their recorded
outcome, result class, probe kind and surface; receipts outside the window are
outside coverage, not evidence of no progress. Accounting rows are excluded
before the presentation cap. Completed Todo titles
help explain recorded deliveries; archive coverage and omitted rows are explicit.
Reported outcomes and evidence-bearing receipts remain distinct, and neither
means the referenced artifact was inspected. Manager Lark replies preserve paragraphs,
lists and emphasis through Markdown posts. Structured mentions and posts exceeding
the rich-message request limit retain the existing text path without truncation.

The window is a selected decision, not a discovered fact. It stays at the shipped
seven days unless the operator selects another value with
`LOOPX_MANAGER_EVIDENCE_WINDOW_DAYS` (1..30); the block declares `days`,
`days_source` (`product_default`, `explicit_config` or `explicit_argument`),
`days_env_var`, `days_default`, `days_bounds` and `days_reason`. A missing,
out-of-bounds or unreadable explicit value keeps the shipped default and reports
`explicit_window_out_of_bounds`, so a bad setting can neither widen the prompt
nor answer a narrower window than it declares.

The same block declares the evidence sources as data: the local registry source
plus every SSH host this machine registered for LoopX evidence — a host named by
an `evidence_ssh_hosts` grant on any channel, not every configured SSH alias,
since an operator's `github.com` or personal jump host holds no Core state.
Owner conversations may still read another configured alias on demand by naming
it. Declaring a source never connects to it, and a declared but unread source is
a named coverage gap rather than evidence of no progress. Reading remote rows
still requires the remote read path below.

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
dated delivery read stays inside the declared bounded window; arbitrary artifact
paths and external links are not fetched. Non-Codex adapters receive the same
windowed projection without the interactive inspection tools until they
implement an equivalent tool contract.

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

`remote_read` states how the declared sources reach the model. An interactive
endpoint keeps the on-demand path above (`on_demand_tool`) and pays no source
latency. A prompt-only steward segment has no read tool, so the Turn owner reads
the registered sources for it (`inline_in_prompt`) and adds a
`manager_remote_evidence_v0` block:

- one dial per Turn, at most two hosts, nine seconds per host inside a ten-second
  Turn budget, eight portfolio rows per host; a source outside that budget is
  `deferred_budget` with its last successful read, not a silent omission;
- a fresh cached read (`ttl_seconds`, ten minutes) is reused instead of dialling
  again, so a warm channel adds no per-Turn latency;
- every source carries a typed status and freshness: `read` or `cached` with
  `read_at` and `age_seconds`, `unavailable` with its reason, last successful
  read and `coverage_effect`, `not_configured` for alias drift;
- a failed read keeps the last successful rows only as
  `source_freshness: "stale"` with `remote_source_rows_are_stale` in
  `limitations`, so stale remote state is never presented as current progress and
  a failure is never read as no progress;
- cache entries are keyed by host, window and the exact grant scope, so a changed
  grant or window re-reads instead of answering from a narrower cached read.
- the declaration and the read use the same SSH configuration, so one packet
  cannot call a host unconfigured and read it in the same Turn.


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

When the provider returned a trustworthy message locator before readback failed,
the same background pump persists that private attempt and later performs a
read-only verification. A matching message advances the original delivery to
`delivered` without sending again. Provider outages retain
`verification_required`; a missing legacy locator, changed intent, missing
message, or verified mismatch becomes `explicit_unverified`. CLI, Manager read,
and Chat expose the same public-safe state and reason without returning the
provider locator. The Lark adapter keeps locator interpretation and provider
readback; `manager-context` remains the sole result/delivery writer. The typed
`control_plane/collaboration/return_delivery.ts` boundary owns provider-neutral
attempt validation and verification classification; Python retains file-lock,
persistence and adapter orchestration only.

New handoffs persist their exact original return route. Legacy requests remain
queryable; a receiver can explicitly report one only when its exact persisted
Chat receipt uniquely recovers the route. Historical timestamps stay unknown.
Replies are immutable and additive, separate from private decision reasons and
Core progress. Query `manager-inbox status` or `loopx_manager_read view=handoffs`
for delivery diagnostics. These queries are not required from the user.
