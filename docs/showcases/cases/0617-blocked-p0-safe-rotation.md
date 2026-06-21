# 0617: Blocked P0 With Safe P1/P2 Rotation

## Summary

A benchmark rotation had three active lanes. The highest-priority lane needed a
large local image before it could run. Instead of silently spending compute or
stalling the whole goal, LoopX surfaced the concrete user decision,
kept that lane gated, and allowed safe no-upload fallback work on the other
benchmark families.

This case demonstrates:

- concrete user gate projection;
- blocked-priority fallback selection;
- quota discipline around gated work;
- attention reduction for the operator.

## Before

The operator wanted one long-running benchmark goal to rotate across several
candidate families. One family became blocked because the next step required a
large local dependency. The correct behavior was not "keep trying" and not
"stop the entire project"; it was:

1. ask the user whether to acquire the large dependency;
2. avoid spending delivery compute on that gated lane;
3. continue safe fallback work that does not depend on the decision.

## LoopX Behavior

LoopX turns that situation into a structured control-plane decision:

- the user todo names the blocked P0 decision;
- the agent todo still contains lower-priority safe work;
- `quota should-run` exposes a user-visible gate and a safe fallback contract;
- the agent can continue only after it records why fallback is being selected.

The key product effect is that the user sees the decision that matters, while
the agent is not forced into an idle loop.

## Reproducible Demo

Run the synthetic public demo:

```bash
python3 examples/showcase-0617-blocked-p0-safe-rotation-smoke.py
```

The demo builds a sanitized status payload with:

- a P0 user gate for a large image acquisition;
- a P0 agent item blocked by that user gate;
- a P1 safe fallback item for another benchmark lane.

It verifies that LoopX projects `scoped_user_gate_fallback`, marks the
turn as actionable, requires user notification, and selects the non-gated
fallback.

## Evidence Boundary

This public case intentionally omits private screenshots, raw benchmark task
text, local image names, internal links, and raw run logs. The behavior is
represented by a synthetic fixture because the reusable product value is the
control-plane pattern, not the original private artifact.

## Website Story Beats

1. A P0 lane becomes blocked by a concrete user decision.
2. LoopX keeps that decision visible as a user todo.
3. The agent selects a safe P1/P2 fallback instead of spending on the blocked
   lane.
4. The state records both facts: what is blocked and why progress can continue.
