# Trajectory Hygiene v0

LoopX keeps control-plane history for audit and continuation. That history is
not automatically suitable for model training: quota accounting, scheduler
acknowledgements, unchanged monitor polls, and repeated state projections can
outnumber task-facing actions in a long session.

`trajectory_hygiene_summary_v0` is a read-only audit over the existing compact
run index:

```bash
loopx history trajectory-hygiene --goal-id <goal-id> --limit 100
```

It reports controller-event density, compact controller-character density,
non-material event density, repeated task-action labels, and action/outcome
attribution coverage. These are proxies for deciding whether the current event
mix needs a separate learning projection. They are not training-quality scores.

## Boundary

The audit:

- reads only the public-safe compact run index;
- does not open run artifacts, raw sessions, raw trajectories, task bodies, or
  verifier output;
- does not change history, status, quota, todo, scheduler, or state semantics;
- always reports `seed_model_training_eligible=false`.

A future learning projection should keep model-visible task context, assistant
actions, tool observations, human decisions, and attributed outcomes. Controller
events should remain in the audit ledger and link to learning turns by stable
ids instead of being replayed as ordinary user/model turns.

The raw audit trail remains useful for reproduction and incident analysis. It
must not be silently rewritten into a training sample.
