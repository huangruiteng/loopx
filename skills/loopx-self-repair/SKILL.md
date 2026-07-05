---
name: loopx-self-repair
description: Diagnose and repair LoopX control-plane drift or agent behavior drift. Use when a LoopX task makes unexpectedly small progress, follows a stale or contradictory recommended_action, ignores a higher-priority blocked item while doing fallback work, reports vague owner/user gates, loses todo projection, misaligns benchmark treatment with the real product path, mixes temporary artifacts into commits, or when the user asks for root-cause analysis, self-repair, or why the harness/agent behaved unexpectedly.
---

# LoopX Self Repair

Use this skill to turn a surprising LoopX behavior into a durable fix,
not only an apology or a one-off explanation.

## Repair Loop

1. **Pause delivery selection.** Do not spend quota or continue adapter work
   until the control-plane facts explain why that work is valid.
2. **Build a compact evidence packet.** Prefer structured surfaces:

   ```bash
   git status --short --branch
   loopx --format json diagnose --goal-id <goal-id>
   loopx --format json status --goal-id <goal-id> --limit 20
   loopx --format json quota should-run --goal-id <goal-id> [--agent-id <agent-id>]
   loopx --format json history --goal-id <goal-id> --limit 5
   ```

   `status` defaults to the registry/dashboard view, but accepts `--goal-id`
   when the repair needs one goal-focused projection. Use
   `diagnose --goal-id` for the richer goal-specific agent reasoning packet.
   Also inspect the project-local registry and the registry-declared active
   state file when relevant. Use the shared global registry for heartbeat/quota
   truth.
3. **Classify the failure.** Read
   `references/repair-patterns.md` and match the symptoms to a known pattern.
   If no pattern fits, add one after the fix.
4. **Assign the responsible layer.** Separate:
   - agent behavior mistake;
   - state projection or quota payload bug;
   - active-state authoring gap;
   - benchmark harness mismatch;
   - docs/process hygiene gap.
5. **Repair at the lowest durable layer.**
   - If it is a one-off agent mistake, write back the correct state/todo and
     continue with a larger bounded batch.
   - If the machine projection misled the agent, fix CLI/status/quota
     projection and add a focused smoke.
   - If the user correction changes the goal acceptance, says the agent missed
     the intended loop, or exposes a product bottleneck that is not visible in
     quota/status, write a bounded `goal_vision_replan_contract_v0` packet with
     `replan_trigger_summary` through normal `loopx refresh-state --vision-*`
     fields, using the same `--agent-id` as the current lane, or
     `--agent-vision-json` for generated multi-field patches, before returning
     to delivery. If the next executable step is already known, also add or
     link the concrete successor todo; do not leave the correction only in chat
     or an incident note.
   - If a design rule is missing, update the interaction model or todo list
     before implementing broad behavior.
   - If benchmark evidence is not attributable, add posthoc trace/parity
     checks before claiming uplift or regression.
6. **Validate before resuming.** Run the smallest smoke or CLI check that would
   have caught the issue, plus `loopx check` on changed public surfaces
   when docs/contracts changed.
7. **Write back the lesson.** Update active goal state, docs, contributor
   tasks, or this skill so the same failure mode is visible next time.

## Vision / Replan Writeback

Use the bounded vision contract when self-repair discovers that LoopX did not
notice a missing outcome, route, or acceptance condition by itself. The packet is
the bridge from human or agent insight to quota-visible replan state:

```json
{
  "schema_version": "goal_vision_replan_contract_v0",
  "state": "vision_drift_detected",
  "vision_patch": {
    "vision_summary": "Name the corrected route or acceptance target.",
    "acceptance_summary": "Name the machine-visible condition that must hold.",
    "replan_trigger_summary": "Name why the current frontier is insufficient."
  },
  "todo_delta": ["create_successor"]
}
```

Record it with normal inline `refresh-state --vision-summary
--vision-acceptance --vision-replan-trigger` fields using the same `--agent-id`
that ran the repair. Use `--agent-vision-json` when a generated patch is clearer
than a command line. Pair `--autonomous-replan-recorded` only after a bounded
replan delta was actually written, such as a successor todo, no-follow-up
rationale, blocker, or updated vision. A vision patch without a runnable todo is
still useful: `quota should-run` can promote its `replan_trigger_summary` into
`goal_frontier_projection.acceptance_gaps[]` when the advancement frontier is
empty.

If the repair concludes that the existing per-agent vision is still correct,
close the required checkpoint with `--vision-unchanged-reason` instead of
writing a fake patch. If a material `refresh-state` lacks both a patch and an
unchanged/no-follow-up decision, LoopX should preserve a per-agent
`vision_checkpoint_v0` with `decision=missing_required` so the same agent's
next quota check can enter replan.

## Evidence Discipline

- Do not read or commit raw private logs, trajectories, verifier output,
  credentials, internal links, or production material.
- Do not solve contradictory payloads by guessing. If `recommended_action`,
  `goal_boundary.write_scope`, todos, and interaction contract disagree, treat
  that as a projection bug or state authoring bug first.
- Do not let fallback work hide the primary blocker. When a higher-priority
  path is gated but safe fallback is valid, report both the concrete gate and
  the fallback progress.
- Do not let tiny safe steps become the default. If several recent turns are
  short or surface-only, run a steering audit and increase the next bounded
  batch size unless a real gate blocks it.

## Reference Routes

- For known symptom-to-repair mappings, read
  `references/repair-patterns.md`.
- For user/agent/state channel semantics, read
  `../../docs/state-interaction-model.md` and
  `../../docs/interaction-pattern-catalog.md`.
- For quota and heartbeat decisions, read
  `../../docs/quota-allocation.md` and
  `../../docs/heartbeat-automation-prompt.md`.
- For commit/PR hygiene failures, read `../../AGENTS.md`.
