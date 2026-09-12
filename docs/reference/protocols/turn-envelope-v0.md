# TurnEnvelope v0

`loopx_turn_envelope_v0` is an additive, bounded read model over an already
computed `quota should-run` decision. It gives an agent the next action and its
safety contract without replaying every diagnostic lane in the full quota
payload.

Preview it explicitly:

```bash
loopx quota should-run --goal-id <goal-id> --agent-id <agent-id> --turn-envelope
```

The default `quota should-run` output remains unchanged. The v0 envelope keeps:

- the selected todo, claim, and effective action;
- the bounded action portfolio when the agent must choose among multiple
  admitted actions before delivery;
- the bounded read-only planning horizon when selected work has strategic
  Todo, relation, or goal-acceptance context;
- concrete user actions and gate reasons;
- required reads;
- write scope, approvals, guards, workspace/capability gates, and stop rule;
- delivery, repair, safe-bypass, and blocked-action policy;
- validation/writeback and quota-spend policy;
- the current scheduler action and cadence acknowledgement command.

The envelope also carries a bounded `contract_capsule` for interaction mode,
work-lane and execution obligations, successor/replan duties, automation
liveness, vision/handoff state, and actionable warning references. A canonical
`action_signature` is independently built from the full decision and from the
envelope; matching hashes prove the covered action dimensions agree for that
projection. They do not prove that every possible quota state has test
coverage.

Action-signature coverage is versioned independently from the envelope schema.
`turn_envelope_action_dimensions_v0` covers the original action projection;
`turn_envelope_action_dimensions_v1` additionally covers a blocking user
gate's `response_plan`; `turn_envelope_action_dimensions_v2` additionally signs
`action.action_portfolio`; `turn_envelope_action_dimensions_v3` additionally
signs `action.planning_horizon`. Base/head qualification accepts a declared
coverage migration as a review signal. The bounded, JSON-only v2 and v3
migration budgets apply only to their named schema transitions; ordinary
growth limits resume once the new version is the baseline. A digest change
without a supported coverage migration, or a projection above its one-version
budget, still fails closed.

`quota_planning_horizon_v0` remains advisory even when carried by the envelope.
Its `selection_contract` points back to `selected_todo` and `action_portfolio`,
and `horizon_changes_selection=false`. Effect Program transports this
observation; the TypeScript work-item reducer owns its ordering and bounds.
The quota projection keeps the horizon's typed `detail_refs`. TurnEnvelope does
not copy those commands a second time: it emits
`action.planning_horizon.detail_refs_ref="$.detail_ref"`, and the existing
top-level cold path owns the full-decision, Todo, and status reads. This
transport compaction is covered by the same action signature and does not
change horizon completeness or selection authority.
See [`quota_planning_horizon_v0`](quota-planning-horizon-v0.md).

For `quota_action_portfolio_v2`, the envelope carries the recommendation and
bounded, non-exhaustive `suggested_actions`, but neither is a settlement
identity or permission list. When the full interaction contract says
`selection_required=true`, the agent must rerun quota in the same turn with any
currently authoritative, same-agent, capability-ready Todo. The full decision's
`selection_command.command_args_template` is a rendering template, not a
permission list. It and `candidate_discovery_args` share one bound
`route_prefix`; the discovery route exposes the current open agent queue
when the bounded suggestions are insufficient. The requested Todo remains
pending until the second guard re-runs current lane arbitration and eligibility;
only a qualified request upgrades the identity-less receipt. A newly due hard
lane leaves the receipt unbound, and only the resulting receipt-bound envelope
is a delivery contract.

Portfolio v2 preserves v1's selection policy, candidate ordering, and
settlement rules, and adds an optional `continuation_hint` to each suggested
action. The default quota producer and Turn controller now require v2. The
compact quota CLI view uses the independently versioned
`quota_cli_action_portfolio_compaction_v1` detail marker and inlines candidate
`text`, `priority`, `action_kind`, and `continuation_hint` alongside the v1
identity fields. TurnEnvelope keeps the same `loopx_turn_envelope_v0` outer
schema and v2 action-signature coverage; only its nested action portfolio
version changes. Hosts that strictly accept v1 must update before consuming
the new default. LoopX does not dual-emit or negotiate a v1 downgrade, so an
unknown nested portfolio version must fail closed. Ignoring an absent
`continuation_hint` remains valid when reading stored v1 evidence, but it does
not make a v1-only live decoder compatible with the v2 producer.

`loopx turn plan` and `loopx turn run-once` have no agent selection phase before
they build the host transaction. When such a Turn sees a v2 portfolio, its
outer controller binds the advisory primary by rerunning the same current
eligibility qualification, retains the portfolio in the envelope for audit,
and marks the selected Todo with
`selected_by=turn_controller_advisory_primary`. This deterministic compatibility
path does not apply to heartbeat/model turns: their first response remains
identity-less and delivery-blocked until the agent explicitly chooses.

The compact envelope does not truncate those executable commands into unusable
strings. It carries non-exhaustive `writeback.suggested_todo_ids` plus
`selection_command_ref`; the full decision remains the authority for exact argv.

`protocol_action_packet` remains in the full decision/cold path. The envelope
reconstructs its ordered semantic fields from `action`, `user`, work-lane,
automation, and scheduler contracts, while carrying the explicit
`llm_policy=no_api` invariant. When the reconstruction matches exactly, the
capsule keeps only the source summary hash and derivation status. If a compact
action differs, it keeps only that field-level `residue`; if an older or opaque
packet cannot be reconstructed, it retains the original summary. This removes
repetition only after parity and does not change source packet persistence or
the default quota output.

Large todo summaries, frontier diagnostics, readiness history, compatibility
fields, and warning collections stay on the referenced full-decision/status
cold paths. The envelope has an **8 KiB compact UTF-8 JSON performance target**,
not an execution-admission limit. `compaction.envelope_utf8_bytes` measures the
final packet, including diagnostics. The historical `source_json_bytes` and
`envelope_json_bytes` fields still count Unicode code points for v0 compatibility;
do not use them as wire-byte measurements.

### Budget warnings and allocation

Oversize valid envelopes keep their normal Turn plan/controller route. They
report `compaction.within_budget=false` and a structured
`warning.code=turn_envelope_budget_exceeded`, with `excess_bytes`, additive
`section_bytes` and `over_target_sections`. JSON carries this through the Turn
plan and host request; Markdown plan/envelope output calls out the warning.
Schema, signatures, identity, permissions, receipt validation and execution
quota are still hard gates. This changes previous behavior for **all Turn hosts**:
packet growth alone no longer produces `contract_error` or stops a Turn loop.

The TypeScript owner keeps review allocations totaling 8,192 bytes. These are
diagnostic targets, not permission to truncate fields or hard per-section caps:

| Section | Target bytes | Included fields |
| --- | ---: | --- |
| action | 800 | action, user, required reads, replan packet, response plan |
| boundary | 2,000 | boundary and execution policy |
| writeback | 600 | validation/settlement commands and policy |
| scheduler | 600 | scheduler action and acknowledgement |
| contracts | 1,800 | contract capsule |
| context | 1,400 | capability context and task orchestration |
| transport | 992 | identity/metadata, signatures, cold-read commands, diagnostics |

Counts include JSON property names, delimiters and UTF-8 text. Their sum equals
the measured final packet; dividing each by `envelope_utf8_bytes` gives its
share. Diagnostic detail is emitted only on overflow, not every normal Turn.
Use the existing `quota should-run --turn-envelope` or `turn plan` JSON output
to inspect the breakdown. Record a public-safe reproduction and compare each
section with the same fixture on the baseline before changing its owner.
First remove repeated presentation or move non-actionable detail to an existing
cold read. Never trim write scope, executable arguments, signatures or required
reads to silence a warning, and do not simply raise the target. The cold-read
commands remain; their redundant human-readable `contains` inventory is retired.

Repository size/parity canaries remain blocking **delivery-time regression
checks**, independent of runtime warning semantics. Representative fixtures must
still fit the target. A warning is a performance investigation signal, not an
automatic Todo, new authority, or permission to spend an extra Turn.

中文：TurnEnvelope 超出 8 KiB 后产生可分析的 warning，不再仅因大小中断合法
Turn。按最终 UTF-8 字节数统计各部分占比，先压缩重复展示内容，再检查对应规则
所属模块；不得截断权限、签名或执行指令，也不应单纯提高预算掩盖增长。
身份、权限、签名和执行配额仍是硬门禁；仓库的体积与语义回归检查仍阻止交付。

Hot-path fields may use explicit references when the inline value would only
repeat another authoritative field. In particular,
`action.selected_todo.text_ref = action.recommended_action` means the selected
todo text is already present as the recommended action. Scheduler reset plans
keep the exact acknowledgement argv inline when it satisfies the executable
argv limits; the failure argv stays behind `failure_cli_args_detail_ref` until
the host update actually fails. Consumers must follow these references instead
of treating the omitted duplicate as missing state.

This contract is a projection only. It does not change quota selection, todo
routing, scheduler state, history writes, or state transitions. Promoting it to
the default agent view requires separate parity evidence across delivery,
monitor, user-gate, capability-gate, workspace-guard, and blocked states.

## Multi-State Parity Evidence

`tests/fixtures/turn_envelope_state_matrix.json` is the durable synthetic
promotion fixture. It covers delivery, monitor quiet-skip, user gate,
capability gate, workspace guard, autonomous replan, successor replan,
blocked, and throttled decisions. Every case must preserve the canonical action
signature, reconstruct `protocol_action_packet`, and remain within the 8 KiB
budget.

The matrix records exact measurements in validation rather than treating a
dated size range as the contract. This keeps the projection available as an
opt-in host view. It is not sufficient to change
the default CLI response: default promotion still requires shadow parity from a
real host integration, no consumer regression with the full decision available
as a cold path, and explicit compatibility acceptance for the default-view
change.
