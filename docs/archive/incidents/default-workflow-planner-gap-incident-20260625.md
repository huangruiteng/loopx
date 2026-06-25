# Default Workflow Planner Gap Incident

Date: 2026-06-25

Audience: LoopX workflow owners, heartbeat prompt generator owners,
status/quota owners, connector maintainers, and onboarding authors.

## Summary

A project owner wanted LoopX to keep running on a development host after the
visible local UI was no longer present. The final setup worked, but only after
the operator and agent manually assembled several pieces: scoped quota guards,
agent identity, IM or gateway intake, headless execution, monitor no-spend
behavior, readiness checks, and host-level keepalive.

The bad case is not that the user avoided TUI. TUI, headless runtime,
IM/gateway intake, and hybrid handoff are all legitimate LoopX modes. The bad
case is that LoopX did not provide a default workflow planner that could choose
and verify the right mode composition from the user's intent and the host's
capabilities.

## Public-Safe Shape

This incident is recorded without raw chat messages, private project names,
internal document links, hostnames, local paths, credentials, service units, or
message contents. The reusable shape is:

```text
user intent = keep LoopX working when the visible UI may be closed
available modes = visible TUI, headless runtime, IM/gateway intake, hybrid handoff
required invariants = scoped --agent-id, quota guard, no-spend quiet skip,
  durable intake, keepalive, readiness verification
bad interaction = user/agent must manually infer which mode owns each step
expected interaction = LoopX proposes a mode plan and validates it end-to-end
```

## What Went Wrong

1. **Runtime modes were implicit.** The setup mixed visible UI, headless
   execution, IM/gateway intake, and host keepalive, but LoopX did not name
   those as first-class choices with clear transition rules.

2. **TUI and headless were treated as a binary.** The real product need is a
   mode matrix: TUI can remain the durable operating surface when that is what
   the user wants, or it can hand off to a headless runtime when the host should
   keep working without a visible UI. The system should not hard-code either
   assumption.

3. **Identity and quota invariants were easy to miss.** Registered-agent goals
   require the same scoped identity through guard, monitor-poll, delivery, and
   spend accounting. Without a workflow planner, this becomes a checklist the
   operator has to remember.

4. **Host liveness was discovered late.** Keepalive details such as timers,
   services, cron-style fallback, locks, and readiness probes are not core
   product goals by themselves, but they are part of the runtime contract when
   the user asks for development-host continuity.

5. **No-spend monitor semantics were not visible enough.** A quiet monitor wait
   is healthy only if the user can tell that the runtime is alive, has no open
   user todo, and will not burn quota without a material transition.

## Desired Semantics

LoopX should expose a default workflow planner that turns user intent and host
capability checks into a compact mode plan:

| Mode | Good Fit | Required Proof |
| --- | --- | --- |
| Visible TUI | user wants to watch or steer each turn interactively | active session, scoped prompt, quota guard, clear gate handling |
| Headless runtime | work should continue without a visible UI | scoped agent identity, guard-before-run, no-spend monitor behavior, readiness probe |
| IM/gateway intake | user wants to create work from chat or another external surface | durable todo creation, text/card fallback, source boundary, user-gate projection |
| Hybrid handoff | one mode should escalate or continue in another | explicit transition event, target mode readiness, shared `--agent-id` and state writeback |

The planner should never infer production permission, credential access, or
destructive authority from the mode. It only selects the runtime shape and the
checks required before that shape can be trusted.

## Follow-Up Work

### GH-C56: Default Workflow Planner

Design the first default workflow planner for development-host LoopX usage.
It should model visible TUI, headless runtime, IM/gateway intake, and hybrid
handoff as first-class modes, then generate the right scoped workflow from
user intent and host capabilities.

### P1: Mode-Plan Fixture

Add a public-safe fixture that proves the generated plan carries `--agent-id`,
preserves no-spend monitor behavior, and distinguishes TUI, headless,
IM/gateway, and hybrid runtime choices.

### P1: Readiness Copy

Status and review packets should summarize the selected mode in user language:
what is running, what is waiting, what will wake it, and what would require a
visible user decision.

## Related Patterns

- `IP-008 Monitor Quiet Skip`: quiet monitor work is a watch lane, not a
  delivery lane.
- `IP-022 Claimed Todo Visibility And Agent-Lane Next Action`: claimed work
  and monitor lanes should stay visible without becoming the selected delivery
  lane.
- `IP-028 Connector Runtime Boundary`: connector or gateway runtime choices
  need explicit allow/deny policy before reading external material.
- `scheduler_liveness_backoff_gap`: host schedulers should follow
  machine-readable scheduler hints instead of hard-coded polling loops.
