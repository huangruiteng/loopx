# DSH / Pi: L1 Observation and Managed Runtime Selection

Status: evidence-backed implementation assessment, not a runtime promotion.
Scope: the shared goals of [Reliability Diagnostics](./long-running-agent-reliability-diagnostics-governed-delivery-v0.md)
and [Desktop Execution Frontends](./desktop-execution-frontends-v0.md).
[中文](./harness-selection-dsh-pi-v0.zh-CN.md)

## Decision

Keep **DSH as the first L1 event source**. Do not infer that DSH is already the
preferred production Mode B runtime. Retain Pi as a managed-runtime candidate.
The first choice minimizes the cost of qualifying an existing passive observer;
the second requires lifecycle, provider, crash-recovery and outcome evidence
that a plugin event fixture cannot supply. No quantitative winner is claimed.

Two DSH roles appear in this document and must not be conflated. The **bounded
managed Turn host** (LoopX's adapter choice for one governed Turn) is
credential-bound; its default-host resolution shipped in PR #4443, and the
steward channel reaches it through the one-segment chat transport recorded
below. The **L1 event source and session-owning runtime** role stays opt-in and
is not promoted by that binding; it still needs the C0, C1, overhead, retention
and Mode B rows.

## Managed Execution Surface (2026-09-15)

Selection is constrained by what the repository ships today, not only by what an
upstream harness can do. The managed bounded execution unit is the governed Turn:

- `loopx turn run-once` accepts `--host codex-cli|dsh|generic-cli` with
  `--execution-mode isolated-headless`: LoopX decides, a host adapter invokes the
  agent CLI, an independent validator proves the postcondition, and only a passing
  result is committed;
- `loopx host-mode-plan` selects `isolated_headless_turn` for the
  `continue_without_ui` intent only when the host declares `typed_host_adapter`;
  without that declaration it reports the mode as not ready and names the missing
  capability;
- session ownership (`managed_runtime` versus `attached_host`) is not decided
  here. It belongs to
  [Agent Session Execution Modes](./agent-session-execution-modes-v0.md), which
  also owns the M1-M4 integration milestones and the cross-frontend projection row.

Three evidence states appear below and must not be read across them. The list is
dated 2026-09-15 and is written to land with the managed stack:

- **already on `main` on 2026-09-15:** `loopx turn run-once --host
  codex-cli|dsh|generic-cli`, the `dsh` host adapter, the `host-mode-plan` gate
  above, and the dsh pin `deepseek-harness-sdk==0.1.2a3`;
- **not on `main` on 2026-09-15; expected to land with this document:** the
  explicit host selection (`loopx/control_plane/turn_driver/host_binding.py`,
  PR #4443), the steward channel's explicit executor selection
  (`loopx/chat_manager.py`, PR #4446) and the `0.1.5rc1` dsh pin (PR #4420). A
  later reader who finds those PRs merged can read those rows as shipped; a
  reader who does not must treat them as stack-only. All three merged on
  2026-09-15, so those rows are shipped, and the steward rows below were
  revised twice afterwards: the first revision still defaulted the steward
  channel to `codex` and left the managed host unreachable from it, and the
  second made that default credential-conditional, so a discovered credential
  re-pointed the surface a person talks to. This revision restores the
  steward's shipped default to `codex` on every machine and reaches the managed
  host only by explicit selection, which is the shape the row below states;
- **local live qualification, not a repository gate:** rows marked as local
  evidence below. Reproducing them needs an operator credential, and CI asserts
  none of them.

| Role | Source | Selection today | Promotion gate |
| --- | --- | --- | --- |
| Default managed execution host | LoopX Turn plus the `dsh` host adapter, bound to an operator-supplied model endpoint | shipped product default, credential-resolved: the managed `dsh` host when the operator credential is configured, the individual `codex-cli` host when it is not; `LOOPX_TURN_HOST` re-points whichever resolved and an explicit `--host` wins (PR #4443, default resolution with this change) | keep the typed host request/result, independent validation, and the operator-owned credential boundary; do not replace it without an equal or stronger contract |
| Steward channel executor | the interactive Chat transport the steward answers on | shipped product default: `codex`, the same endpoint on every machine; `LOOPX_MANAGER_ENDPOINT` re-points it, and an explicit selection of the managed host (`dsh`) moves the endpoint, model and reasoning effort together; selection landed in PR #4446, the unconditional default and the segment transport land with this change | the segment transport's typed limits (no streaming, no cross-turn host session, read-only sandbox) stay disclosed and read back, and no managed lane may depend on an individual subscription |
| Supported alternative Turn host | LoopX Turn plus the `codex-cli` adapter | explicitly selectable, and the credential-resolved default of the managed row above on a machine with no operator credential; it is the `individual` executor kind, so it is billed to one person's CLI login | no managed lane may *silently* depend on an individual's personal CLI subscription: the individual host is reached only as that credential-resolved default and is read back as `no_operator_credential`, never substituted for a host the operator selected |
| L1 event source and session-owning runtime candidate | DSH | opt-in, not promoted; the bounded Turn host role is the default row above | the C0, C1, overhead, retention and Mode B rows in this document being run and reviewed |
| Optional visible host loop | Pi | not a managed runtime | declare a per-binding session mode with readback, prove single-executor behavior under restart, "conversation is not a receipt", non-authoritative host-local state, and one real-host restart row |

### Managed host binding and live qualification (2026-09-15)

A managed host binding names four things: the host adapter, the provider, the
model, and where the credential comes from. The DSH binding is the DSH Turn host
with provider `deepseek-official`, model `deepseek-v4-flash` (DeepSeek V4.1
Flash) at reasoning effort `high`, an endpoint from the operator environment
(`DEEPSEEK_BASE_URL`) and a credential from the operator environment
(`DEEPSEEK_API_KEY`).

LoopX **selects** the default host for bounded managed Turns and never infers it
from a launch-time surprise (`loopx/control_plane/turn_driver/host_binding.py`):
an explicit `--host` or `LOOPX_TURN_HOST` always wins, and only when neither is
configured is the shipped default resolved from the operator's own credential
facts -- the managed `dsh` host when a credential exists, and the individual
`codex-cli` host when one does not, because an unauthenticated managed host
would refuse to run. The distinction that matters is between a *default* and a
*decision*: a credential may resolve a default that would otherwise have to pick
a host at random, but it never re-points a host the operator already selected.
A lane resolved onto the DSH host therefore never depends on an individual
developer's CLI subscription being available, funded, or logged in, and a lane
without an operator credential never silently borrows one either.

This change also rewrites the promotion gate on the supported alternative host
in the table above. It read "an individual lane must be selected, not reached by
default", which the credential-resolved default contradicts. The rewritten rule
keeps the original intent -- no lane may depend on one person's login without
the operator being able to see that it did -- and names the readback that makes
the dependency visible instead of forbidding the disclosed default.

The steward channel is a **different** surface, and after the revisions recorded
above its default is one endpoint rather than one rule: `codex`, the interactive
CLI endpoint, on every machine. `LOOPX_MANAGER_ENDPOINT` re-points it, and
selecting the managed host (`dsh`) moves the endpoint, the model and the
reasoning effort together, so the channel can never end up with an operator
model driven through an individual CLI login. The rule that decides a credential
here is the opposite of the Turn row's: a credential authenticates the endpoint
that was selected and never re-points the surface a person talks to, because a
conversation must not change hands mid-thread when a key appears in the
environment. The readback still names where the endpoint came from
(`executor_endpoint_source`) and, for a shipped default, which decision it was
(`executor_endpoint_default_reason`), so an operator reads a decided default
instead of inferring it from the resolved host name.

Both managed surfaces resolve their **execution profile** from one owner
(`loopx/control_plane/turn_driver/execution_profile.py`): provider
`deepseek-official`, model `deepseek-v4-flash` (DeepSeek V4.1 Flash) and reasoning
effort `high`, overridable by `LOOPX_TURN_PROVIDER` / `LOOPX_TURN_MODEL` /
`LOOPX_TURN_REASONING_EFFORT` and, at lower precedence, the legacy `DSH_PROVIDER`
/ `DSH_MODEL`. The readback is one line, `execution_profile`, shaped
`deepseek-v4-flash@high` in the shipped case, with the provider prepended only
when it is not the shipped one; it is one line because every plan payload carries
it and the agent-facing output budget is a contract, and whichever values the
line names are the values that run, so an owner-set model appears as itself.
Credentials authenticate the selected profile and never choose it; the one
thing a credential resolves is the shipped *host* default of a bounded Turn
nobody selected, and that resolution carries its own readback source.

Evidence for this binding, separated by source:

- repository-covered without any provider call: with an operator credential the
  shipped default is `dsh` and without one it is `codex-cli`, an explicit
  `LOOPX_TURN_HOST` re-points either default, and an explicit `--host` still
  wins over all of them (`tests/test_turn_default_host_binding.py`,
  `tests/test_turn_managed_executor_binding.py`,
  `examples/loopx-turn-managed-executor-binding-smoke.py`,
  `examples/loopx-turn-managed-default-flow-smoke.py`);
- local live qualification with the real SDK and runtime
  (`deepseek-harness-sdk==0.1.5rc1`, the pin PR #4420 proposes; `main` still
  pins `0.1.2a3` and the same pair also passed there): the in-process
  `--host dsh` path and the `generic-cli` subprocess path;
- local live qualification: one governed Turn reached `validated_progress` — the
  host executed the bounded action, an independent validator proved the
  postcondition, and only then did writeback and quota spend follow;
- local live qualification: a Turn whose postcondition was not proved
  fail-closed instead — no writeback, and the quota slot spend count stayed at
  zero.

Open gaps before this binding is a promoted production default:

- the runtime snapshot bundled as `deepseek-harness-runtime-bin==0.1.5rc1`
  cannot boot the stock `headless` profile as shipped: a profile row pulls
  `@deepseek-ai/dsh-session-title-first-prompt-llm`, which imports the omitted
  `@deepseek-ai/dsh-session-title-llm`, and resolution runs inside the packaged
  snapshot, so installing that package into a profile directory does not change
  it. The current local workaround is a binding overlay that disables the
  affected row. The managed host path is unaffected: it does not select
  `headless`, and the default `sdk` profile boots and exits cleanly;
- the LoopX DSH Turn composition must name the tool rows a managed action needs
  (`@deepseek-ai/dsh-tool-fs`, `@deepseek-ai/dsh-tool-bash`). Without them a live
  model can answer but cannot act, and the Turn ends in a validation failure
  rather than in work.
- the host-mode plan used to map the unattended intent to the compatibility
  path: `isolated_headless_turn` carried `turn_host: generic-cli`
  (`loopx/host_mode_planner.py`), so the `loopx turn plan` command it printed
  named `--host generic-cli` instead of the selected `dsh` default recorded
  above, which is correct as a labelled rollback path but was not labelled as
  one. **Decided and shipped:** the plan takes the "write out the resolved
  default" option. The preview command pins no host, the pinned compatibility
  variant is reported as `plan_command_rollback`, and the typed
  `turn_mapping.host_selection` states which of the two a command is; targets
  that genuinely need a visible identity (transitions into `visible_tui`) still
  pin their host. `docs/reference/protocols/host-mode-plan-v0.md` defines
  `turn_mapping.host` as the mode's declared host and scheduler context rather
  than as an already-resolved concrete host. The plan's `--host-identity` list
  still covers visible hosts only, because a headless-only host such as `dsh`
  cannot own a visible session.

## Evidence Baseline

LoopX was inspected at `bf217e1e01bec79f357c9ecbd580cf2dfa73db8b`.
The implementation paths below are repository-relative:

- `packages/dsh-loopx-plugin/src/observer.ts`: pinned activation, session event
  compaction, first-append safety, bounded buffering and flush isolation.
- `loopx/capabilities/reliability_diagnostics/{receipt,projection}.py`: independent
  validation, integrity classification and authority-free diagnostic readback.
- `loopx/dsh_goal_mode/turn_host_adapter.py`: a bounded Turn connector, opaque
  session lineage, SDK calls and failure translation, not a desktop outer loop.
- `loopx/pi_goal_mode/{loopx-goal.ts,pi-goal-loop-runtime.mjs}`: a visible-host
  integration with bindings and continuation behavior; not a passive observer.
- `apps/desktop/loopx-control-plane/src-tauri/src/services.rs`: service process
  management must not be mistaken for the complete managed Agent lifecycle.

The dsh pin moved in two steps, and reading this document needs both states.
`main` today pins `deepseek-harness-sdk==0.1.2a3`. The managed stack moves that
pin to the newest released upstream channel rather than an unreleased tag:
`deepseek-harness-sdk==0.1.5rc1` / `deepseek-harness-runtime-bin==0.1.5rc1` on
PyPI (PR #4420), matching `latest` for `@deepseek-ai/dsh` on npm (checked
2026-09-15). Upstream `next` and `alpha` tags are newer than that channel and are
not adopted here.

Upstream references were inspected on 2026-09-06, pinned independently of the
versions validated by LoopX:

- [DSH README at d347e703](https://github.com/deepseek-ai/deepseek-harness/blob/d347e703908d0406b7a7ef80e3a0e594d86b2215/README.md):
  Cordis/plugin architecture and explicit developer-preview compatibility risk.
- [Pi SDK at 9767ba27](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/docs/sdk.md):
  event subscription, session operations and runtime replacement APIs.
- [Pi extensions at 9767ba27](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/docs/extensions.md):
  event hooks with context-injection, tool-blocking and result-modification power.

The historical Pi repository URL now redirects to `earendil-works/pi`; the
inspected SDK uses `@earendil-works/pi-coding-agent`. This is an upgrade-check
input, not permission to replace LoopX's installed package or assume API parity.

## Comparison by Product Requirement

| Requirement | DSH evidence | Pi evidence | Selection consequence |
| --- | --- | --- | --- |
| Passive observation | LoopX ships a separate observer entry, three session publication hooks and pre-append rejection | SDK offers `session.subscribe`; extensions also offer interception hooks | DSH has a qualified contract slice; a Pi adapter must choose subscription over intervention and prove isolation |
| Session identity / resume | Existing Turn connector derives session lineage; observer separately requires exact goal/session/run identity | SDK separates AgentSession from AgentSessionRuntime replacement/resume operations | Test identity after restart/fork for each adapter; method availability is not durable recovery proof |
| One bounded attempt | LoopX already has a DSH Turn host with timeout and failure mapping | Existing Pi goal mode includes continuation and pause behavior | Neither native loop may silently become the Desktop scheduler; avoid two outer loops |
| Packaging | Dedicated observer export/bundle and packed smokes exist | Extension discovery is part of SDK resource loading | Verify the actually loaded package/profile, not just source imports; neither boundary is OS isolation |
| Provider profiles | SDK connector/version constraints are explicit | SDK exposes runtime/model construction | Qualify the same route, model, tools and budget; harness choice does not establish provider compatibility |
| Public safety | Producer and Python consumer independently validate; shared counterfactuals exist | Tool/context hooks can expose or change raw content | A Pi observer needs first-append redaction and negative fixtures, not transcript copying |
| Performance | Buffer/count/flush accounting exists; no matched real overhead result established here | Subscription is available; no LoopX observer measurement established here | Reject numeric rankings until identical workloads and revisions are measured |
| Maintenance | DSH upstream explicitly warns of breaking changes; LoopX pins its validated connector surface | Current upstream package/runtime APIs differ from historical integration assumptions | Pin upgrades separately; do not compare an installed DSH against an unqualified latest Pi |

These are integration-cost and contract observations, not claims that Pi lacks
events or DSH cannot support other models. Both expose control-capable APIs;
passivity is a property of the selected adapter and its loaded dependencies.

The two LoopX surfaces that depend on dsh do not move together. The bounded Turn
host uses the Python SDK/runtime pin recorded above (`0.1.5rc1`, the released
channel). The dsh-side plugin (`packages/dsh-loopx-plugin`) still builds its
development and client surfaces against `0.1.1-rc.2` while its clean-Docker smoke
already asserts `dsh --version == 0.1.5-rc.1`, and the 0.1.5 line no longer
publishes `@deepseek-ai/dsh-client-runtime` (last released 0.1.1-rc.2), moving
the client runner to `@deepseek-ai/dsh-cordis-client-runner`. That upgrade is
tracked as its own pin item and does not change the L1 observer contract above.

## Data and Authority Flow

The operator needs to distinguish missing evidence, unhealthy execution and
an invalid observation treatment before deciding what to do:

```text
native session publication
  -> isolated observer: compact, validate, count, append
  -> independent ledger validation
  -> integrity receipt + diagnostic projection
  -> operator presentation only

canonical eligibility -> Desktop supervisor -> bounded Turn -> validation/writeback
```

There is no arrow from diagnostics back to eligibility. `valid` means the
observation contract passed, not that a task succeeded. A stall signal is not
permission to retry. Observer errors must not become worker failures.

## Implemented Readback Increment

The existing CLI now supports an explicit combined read:

```bash
loopx reliability-diagnostics status --goal-id <goal-id> --with-receipt --format json --as-of "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

The POSIX-shell example evaluates age against the current UTC time. Other
clients must supply a timezone-aware current timestamp. Omit `--as-of` only
for historical replay: it defaults to the last event time, producing zero
last-event age, not a live liveness check. Display the observation and evaluation
times separately; advancing the evaluation clock does not change integrity.

The receipt and projection derive from the same in-memory ledger reading,
avoiding two CLI calls observing different append states. Omitting the flag
preserves the original response. This does **not** make concurrent file append
atomic: a partial last line remains an invalid-input signal rather than being
silently dropped. The command does not activate an observer, discover a binding,
write a ledger, call a model, or change a Goal/Todo/lease.

This is an executable readback seam, **not a shipped Mode B panel or supervisor**.
A future panel must bind exact goal/session/run identity, show observation age
and integrity independently of task status, and refuse to label a multi-run or
stale goal ledger as the current session's health. It must remain operator-only,
with no diagnostic input passed into prompts or scheduler decisions. Existing
CLI ledger reads are unbounded; do not put this command on an automatic polling
loop before adding an owner-reviewed read budget/snapshot strategy.

## Qualification Plan and Stop Conditions

1. **C0 adapter fidelity:** compare native execution with the managed adapter,
   observer disabled. Pin model, route, tool definitions, prompts, environment,
   budget, package/adapter revisions and initial session state. Account for all
   retries and interruptions. Reject comparisons with unequal treatments.
2. **C1 passive arm:** enable only the observer on that qualified adapter. Record
   eligible run identity, persisted/accepted/rejected/drop counts, receipt status,
   endpoint/worker-context/scheduler influence and all failed runs. Fixture success
   does not establish this gate; non-valid receipt is not eligible C1 evidence.
3. **Overhead:** measure baseline and observer wall time, process CPU, peak RSS,
   bytes written, event throughput and flush latency using paired repeated runs.
   Report sample count, distributions, uncertainty and warm/cold conditions.
   Declare acceptance thresholds before running; no threshold is invented here.
4. **Retention/deletion:** owner chooses maximum age/bytes, active-writer handling,
   export/support access, backup scope and delete verification. Dry-run inventory
   must precede deletion; never truncate an active ledger to meet a size cap.
5. **Mode B acceptance:** separately exercise start/resume/interrupt/close,
   process crash, stale session identity, duplicate completion, timeout and
   provider failure in a disposable runtime. Verify one Turn at a time and
   canonical validation/writeback before spending quota or requesting another.

Keep raw logs and credentials owner-local. Public evidence should contain only
generalized methodology, pinned revisions, aggregate results and safe references.
No live model execution or retention deletion is authorized by this document.

Milestone ownership stays with
[Agent Session Execution Modes](./agent-session-execution-modes-v0.md). This
document owns the C0, C1, overhead and retention evidence for the L1 observer
arm, and the Mode B acceptance above for a session-owning runtime; the M1-M4
integration milestones and the cross-frontend projection row remain that
document's, and nothing here defines mode inference or a second executor.

## Delivery Sequence

This comparison plus combined CLI readback can be reviewed now. A Mode B panel
requires the exact-session read contract and bounded refresh path first; it must
not be a second generic monitoring subsystem. Run C0/C1 and overhead experiments
as separately budgeted work, then submit only reusable fixes and safe evidence.
Implement deletion only after the owner selects the retention profile. Revisit
runtime preference if Pi satisfies the same isolation/lifecycle tests at lower
measured integration and operational cost, or DSH fails them. Do not introduce
L2 advice, retry control or a new scheduler to make an L1 experiment pass.

## Steward Channel Chat Transport (2026-09-15)

The governed Turn surface and the steward (manager) chat channel need different
host shapes, and they now resolve their defaults differently too: a bounded Turn
nobody selected still falls back to the host the operator credential resolves,
while the steward channel stays on the interactive CLI endpoint until an
operator selects the managed host. A Turn is one bounded work segment, which the
shipped DSH adapter serves today. The steward channel additionally needs a
transport that can hold an interactive session, and the shipped DSH surface
explicitly does not promise cross-turn DSH session continuity.

Option A shipped, so this section now records the transport rather than a plan.
The steward channel holds the managed host through
`loopx/chat_dsh.py`: each Chat turn starts **one bounded dsh segment** on the
resolved execution profile, hands it the channel's bounded visible history plus
the current message, and returns the final assistant message. The snapshot the
segment sees is composed by LoopX and the segment's sandbox is pinned read-only
through `DSH_PERMISSION_MODE`, so an answer cannot come from ambient write or
shell authority that the channel never granted.

What the transport deliberately does not claim, because the channel readback
could otherwise be read as offering it:

* **no streaming** — the answer arrives as one final message;
* **no cross-turn host session** — each segment is fresh, and the visible history
  is Chat-side context rather than a host session the channel resumed;
* **no tool authority** — the segment is refused by the dsh sandbox itself when
  it reaches for a write, and the channel reports `trust_scope: read_only`.

The earlier typed reason `managed_host_chat_transport_unsupported` is retired
with this change; it described a transport gap that no longer exists, and keeping
it would have made a working host unreachable. The reasons the channel can still
report are the managed host's own launchability facts
(`dsh_runtime_unavailable`, `operator_credential_unconfigured`,
`invalid_reasoning_effort`), and a session request for an unavailable host fails
as a typed host-tool gate instead of silently falling back to an individual CLI
login.

| Option | Shape | Cost and risk |
| --- | --- | --- |
| A. Turn-backed steward transport (**shipped**) | Each steward chat turn runs one bounded governed segment on the managed host through the same execution profile the governed Turn resolves, with bounded chat history as context | No duplex streaming and no cross-turn host session; each turn is a fresh segment. The tool/sandbox authority is pinned read-only by the channel and the per-turn bound is the channel's own hard timeout |
| B. ACP or stdio adapter | Reuse the ACP stdio adapter path (as the Kiro CLI chat endpoint does) when the managed host exposes such an interface | Lowest transport cost, but depends on an upstream interface that no shipped evidence covers yet |
| C. Codex endpoint bound to the operator provider | Start the Codex app-server itself against the operator provider so the existing transport and tool surface stay | Keeps streaming, but must prove the session no longer authenticates with an individual login; the provider config becomes host-state authority and needs its own gate |

Selection rule: prefer A, because it reuses the Turn authority, typed host
failure, journal and quota semantics LoopX already validates; keep B as the
cheaper replacement if the upstream interface appears; evaluate C only if
duplex streaming is required for the steward experience. Whichever option ships
must demonstrate that the governed work a steward drives never reaches an
individual subscription, and -- for a steward session the operator put on the
managed host -- that the model work lands on the operator credential. The
steward's own shipped default is the interactive CLI endpoint, which is billed
to one machine's login; that is a disclosed default rather than a hidden one,
because the channel reports the endpoint, its source and the shipped decision
behind it. This document authorizes no new scheduler, retry authority or second
monitoring subsystem to make that demonstration pass.

Option A is the one that shipped, and its demonstration is a repository smoke
rather than a live transcript: `examples/loopx-steward-managed-chat-smoke.py`
runs the real bundled dsh segment against a local mock model endpoint and asserts
the resolved binding, the model and effort that reach the wire, the persisted
answer, and that the read-only sandbox refuses a write. The persona and audience
of a real steward conversation stay out of this document.

## Steward Channel Readiness by Milestone (2026-09-15)

The steward channel consumes both this document's host selection and the manager
milestones in
[capable-manager-semantic-handoff-v0](./capable-manager-semantic-handoff-v0.md).
This section records which steward-channel behaviours those milestones can rely
on today and which stay unverified. It states product contracts, not conversation
content: no live channel transcript, audience identity, dated incident or
operator-local path is recorded here.

| Milestone | Steward-channel contract in scope | Evidence state on 2026-09-15 |
| --- | --- | --- |
| Manager M1 — useful host agent | The channel resolves and reports its effective executor, model, reasoning effort and source, the executor selection does not follow a credential, and a host that cannot launch fails with a typed reason instead of a silent individual-login fallback | Shipped: selected endpoint with its source and default-rule reason, the executor's `execution_profile`, `executor_kind`, and the `channel_binding` readback (PR #4446 with the Turn-side readback in PR #4443; the unconditional default and the segment transport land with this change). The upstream **session identity** is still not projected to the channel, so a channel answer cannot yet prove which session served it |
| Manager M2 — semantic continuation | Receiver resolution across registered running lanes; typed per-source coverage and freshness; a goal-level milestone the report can lead with instead of coverage disclaimers | Not implemented. Delegation resolves against the supplied delegation catalog, so a request whose owning lane is absent from that catalog is refused or routed to an unrelated lane; a provider read failure surfaces as raw error text instead of a typed source row; the manager context exposes deliveries and coverage but no goal-level milestone field to synthesize from |
| Manager M3 — automatic complete exchange | A persisted answer that exceeds or violates the channel's outbound text contract is split and re-sent under a stable answer identity; an ambiguous or failed send is reconciled instead of replaced by a local notice; the return path survives a transport restart; rich markdown renders as structured text | Partially mitigated. `loopx/extensions/lark/outbound.py` fails closed on an over-limit or malformed payload, and the channel reports that local failure without re-delivering the persisted answer; one answer carries no idempotency identity, so a retry can duplicate it; structured rendering is not guaranteed |
| Host modes M0-M1 | The channel's executor selection and its bounded one-segment execution | Selection is covered by PR #4446 and the Turn-side selection by PR #4443; bounded one-segment execution is covered by the Mode B acceptance above. The channel itself now reaches the managed host through the segment transport, so the managed host's own one-segment execution is reachable from the channel; what remains open is that the segment is not a session, so cross-turn host continuity is still not offered |
| Host modes M2-M3 | Attached-host parity, typed unavailability, and mode-aware projection with no mode inference and no second executor | Partly shipped: the channel's managed segment transport holds one executor per binding, refuses a second start with the typed `managed_host_chat_segment_in_flight`, and discards an interrupted segment's answer instead of letting it enter visible history. The channel readback also carries the mode-aware projection: it quotes the Session's own `session_mode` and `status`, reads a channel with no Session as `unbound`, and names a mode outside the closed set as `unrecognized` instead of deriving a mode from the executor it resolved. Still not implemented: attached-host parity, and an external audience still degrades to `restricted` |

Two boundaries stay fixed across all five rows. The channel remains an entry point
and projection of one manager Session: it owns no profile, no permission state, no
second executor and no work authority, so a richer answer contract must not widen
what the channel may read or change. And no row is promoted by this document; the
M1-M4 integration milestones and the cross-frontend projection row still belong to
[Agent Session Execution Modes](./agent-session-execution-modes-v0.md).
