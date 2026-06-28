# Standing Authorization Reprompt Incident

Date: 2026-06-28

Audience: LoopX status/quota owners, decision-scope runtime owners,
user-gate projection owners, benchmark operators, and self-repair maintainers.

## Summary

A benchmark rerun lane needed to use an existing private reverse-channel bridge
as opaque execution material. The owner had previously approved the intended
route and later expected this class of bridge use to be covered by that
authorization. LoopX still projected a fresh user gate asking whether the agent
could use the bridge.

The immediate gate was not harmful by itself: it preserved the private boundary
and did not expose bridge material. The bad case is that LoopX treated an
approval-like decision as a one-off todo completion instead of a reusable,
scoped capability grant. The agent also failed to check prior decisions and the
already-decided route before asking the owner again.

The root problem is therefore mixed:

- **LoopX product gap:** decision scope exists as a protocol target, but the
  hot path does not yet model standing authorizations, semantic deduplication,
  or gate-to-todo release as first-class runtime behavior.
- **Agent process gap:** the agent should have searched prior approval state,
  recognized the route was already settled, and run self-repair before
  re-prompting the owner.

## Public-Safe Shape

This incident is recorded without raw bridge commands, environment values,
hostnames, local paths, screenshots, private benchmark logs, verifier output,
or task text. The reusable shape is:

```text
user intent = continue the benchmark rerun through the approved route
approved route = /loopx goal-start plus reverse channel
protected material = private bridge configuration used only as opaque execution
required boundary = no read, no print, no log, no commit of bridge contents
bad interaction = owner is asked again for a materially equivalent bridge-use gate
expected interaction = LoopX says the action is covered by an existing scoped
  authorization, or asks only when the requested action exceeds that scope
```

## What Went Wrong

1. **Approval was stored as a todo outcome, not as a reusable grant.** The
   system could mark a user gate done, but it had no durable object that said
   "this agent may opaque-execute this bridge class for this lane under these
   boundaries."

2. **Decision-scope coverage did not cover standing authorization.** The
   `decision_scope_v0` contract says user decisions should name the authority
   they cover. In this case, the bridge-use action needed a structured scope
   such as `resource:lane:reverse_channel_bridge_opaque_execute`, but the hot
   path relied on prose and todo status.

3. **Gate deduplication was textual rather than semantic.** A new gate with
   different wording could be projected even when it asked for the same action
   class: opaque use of the existing reverse-channel bridge within the same
   benchmark lane and private-boundary rules.

4. **The route decision and the execution authorization were mixed.** The owner
   had already chosen `/loopx goal-start + reverse channel`. The later prompt
   partly sounded like it was asking for a route decision again, while the real
   missing authority was narrower: use the existing private bridge as opaque
   execution material.

5. **Gate completion did not automatically release the blocked work.** After
   the owner answered, the linked benchmark todo still needed manual state
   repair to become the selected runnable action. That makes the operator pay
   twice: once to answer the gate, then again to recover the todo lane.

6. **The agent did not perform a prior-decision audit first.** Given the owner
   had recently clarified the route and bridge policy, the agent should have
   checked current user-todo history, decision-scope metadata, active-state
   notes, and run history before asking for another approval.

## Desired Semantics

LoopX should distinguish a one-time gate from a reusable scoped authorization.

| Situation | Expected Behavior |
| --- | --- |
| Same agent, same lane, same bridge class, same no-read/no-print/no-log/no-commit boundary | Use the standing authorization and continue. |
| Same bridge class but broader operation, such as reading or persisting bridge material | Ask a new concrete user gate. |
| Same approval wording but different agent, lane, benchmark, or external write boundary | Require explicit scope comparison before continuing. |
| Gate completed and linked to one blocked todo | Recompute that todo's runnable state and selection without manual repair. |
| Ambiguous prior approval | Ask one precise question and include why the existing scope does not cover it. |

Status and quota should surface this as data, not prose:

```json
{
  "standing_authorization": {
    "schema_version": "decision_scope_grant_v0",
    "actor": "codex-main-control",
    "operation": "opaque_execute",
    "resource_kind": "reverse_channel_bridge",
    "lane": "skillsbench_goal_start",
    "boundary": ["no_read", "no_print", "no_log", "no_commit"],
    "state": "active"
  },
  "scope_relation": {
    "state": "grant_covers_action",
    "matched_grant_id": "<public-safe-grant-id>",
    "user_channel": "no_user_action_required",
    "agent_channel": "run"
  }
}
```

## Follow-Up Work

### Short-Term: Record The Current Standing Authorization

Create a compact, public-safe standing authorization record for the current
bridge-use class:

- actor: the main-control agent;
- action: opaque execution only;
- resource class: reverse-channel bridge;
- lane: SkillsBench `/loopx goal-start` reruns;
- boundary: do not read, print, log, persist, or commit bridge contents;
- revocation: owner can revoke by adding a new user gate or closing the grant.

The active benchmark todo should declare the matching
`required_decision_scopes`, and quota should show `grant_covers_action` instead
of projecting another user todo.

### Short-Term: Add Gate-To-Todo Release

When a user gate completes, LoopX should recompute the exact linked agent todos
that list the matching `required_decision_scopes` or `unblocks_todo_id`. If the
gate releases the selected P0 lane, the next quota projection should select it
without a separate self-repair turn.

### Short-Term: Tighten Gate Prompt Copy

Gate prompts should ask only the missing authority. In this case, the prompt
should have said:

```text
Use the existing reverse-channel bridge as opaque execution material for this
SkillsBench /loopx goal-start rerun, without reading, printing, logging, or
committing bridge contents?
```

It should not re-open already-decided route choices.

### Mid-Term: Make Standing Grants A Runtime Primitive

Introduce a first-class `decision_scope_grant_v0` or extend
`decision_scope_v0` with grant state:

- `grant_id`;
- `actor`;
- `operation`;
- `resource_kind`;
- `scope_key`;
- `granularity`;
- `boundary_rules`;
- `created_from_decision_id`;
- `expires_at` or `revoked_at`;
- `audit_summary`.

Quota should compute `missing_decision_scopes`, `covered_by_gate`, and
`covered_by_grant` separately so an unresolved gate and an active authorization
cannot collapse into the same user-facing "owner gate" bucket.

### Mid-Term: Semantic Duplicate Gate Detection

Before adding a user gate, normalize its action fingerprint:

```text
actor + operation + resource_kind + lane + boundary_rules + scope_key
```

If an active grant or equivalent open gate already covers that fingerprint,
LoopX should either reuse it or update its evidence, not create another user
todo.

### Mid-Term: Scope-Aware Gate UI

Operator-facing surfaces should render the computed relation:

- `covered by prior authorization`;
- `blocked by open gate`;
- `scope mismatch`;
- `expired authorization`;
- `needs projection repair`.

This lets the owner see whether LoopX is asking a genuinely new question or
failing to reuse an earlier decision.

### Long-Term: Event-Sourced Authority Ledger

Move gate and authorization state toward an event stream:

- `gate_requested`;
- `gate_answered`;
- `authorization_granted`;
- `authorization_used`;
- `authorization_expired`;
- `authorization_revoked`;
- `todo_released_by_authorization`.

Status/quota should project from that ledger rather than relying on active
Markdown prose, latest-run text, or chat memory.

### Long-Term: Policy Engine For Protected Resources

Bridge usage, credentials, remote execution, public publication, and production
actions should be checked by the same policy engine. The policy engine should
make three separate decisions:

- whether the action is protected;
- whether a standing grant covers it;
- whether the action would expose protected material.

The engine should fail closed on exposure but avoid re-prompting when the
owner already granted the same opaque operation.

## Validation Targets

Add focused smokes for these behaviors:

- a completed standing authorization prevents duplicate gate projection for the
  same action fingerprint;
- a different operation, such as reading bridge contents, is not covered by an
  opaque-execute grant;
- completing a gate immediately releases the linked agent todo in quota;
- route-decision gates and execution-authorization gates render as distinct
  prompts;
- `quota should-run --agent-id <agent>` reports `covered_by_grant` for a
  covered action and does not require user notification.

## Related Patterns

- `decision-scope-v0`: user/controller decisions need structured scope and
  action dependencies.
- Agent-scoped user gate overreach: gates must block only the agents and lanes
  they actually cover.
- Default workflow planner gap: runtime route decisions and execution
  authorization should be explicit mode-plan state, not rediscovered through
  repeated prompts.
