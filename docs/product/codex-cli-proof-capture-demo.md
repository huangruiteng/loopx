# Codex CLI Proof-Capture Demo

This demo bundle lets a user or contributor rehearse the visible proof protocol
without running Codex, reading session material, or touching local LoopX
state. It is deliberately fixture-first: the commands validate public-safe
evidence shape and show the acceptance decision that a real opt-in proof would
need to produce.

## Files

- `examples/fixtures/codex-cli-visible-proof/codex-visible-resume-help.public.json`
  models a Codex CLI surface with `resume [PROMPT]` / `remote-control`.
- `examples/fixtures/codex-cli-visible-proof/visible-resume-proof.public.json`
  records the visible, interruptible proof for that surface.
- `examples/fixtures/codex-cli-visible-proof/runtime-idle-visible-resume.public.json`
  records the fresh idle guard for that surface.
- `examples/fixtures/codex-cli-visible-proof/codex-same-tui-help.public.json`
  models a future explicit same-TUI attach primitive.
- `examples/fixtures/codex-cli-visible-proof/same-tui-proof.public.json`
  records the proof shape that can promote same-TUI automation.
- `examples/fixtures/codex-cli-visible-proof/runtime-idle-same-tui.public.json`
  records the matching idle guard.

## Rehearse The Current Likely Path

```bash
loopx --format json codex-cli-visible-attach-acceptance \
  --project . \
  --goal-id public-codex-cli-goal \
  --agent-id codex-side-bypass \
  --fixture examples/fixtures/codex-cli-visible-proof/codex-visible-resume-help.public.json \
  --proof-fixture examples/fixtures/codex-cli-visible-proof/visible-resume-proof.public.json \
  --idle-fixture examples/fixtures/codex-cli-visible-proof/runtime-idle-visible-resume.public.json
```

Expected decision:

```text
decision: visible_surface_spike_passed_not_same_tui
accepted_for_visible_later_turn: true
accepted_for_same_tui_automation: false
blocker: same_tui_visible_attach_not_proven
```

This is the important product distinction. A visible `resume` or
`remote-control` path can become a useful proof spike, but it still does not
prove LoopX can safely add a turn to the same open TUI.

## Rehearse The Future Promotion Path

```bash
loopx --format json codex-cli-visible-attach-acceptance \
  --project . \
  --goal-id public-codex-cli-goal \
  --agent-id codex-side-bypass \
  --fixture examples/fixtures/codex-cli-visible-proof/codex-same-tui-help.public.json \
  --proof-fixture examples/fixtures/codex-cli-visible-proof/same-tui-proof.public.json \
  --idle-fixture examples/fixtures/codex-cli-visible-proof/runtime-idle-same-tui.public.json
```

Expected decision:

```text
decision: same_tui_visible_attach_accepted
accepted_for_visible_later_turn: true
accepted_for_same_tui_automation: true
blockers: []
```

That result is still an acceptance packet, not an executor. A later driver must
rerun quota, rerun a fresh idle guard, obey the command boundary, write compact
evidence or a blocker, and spend quota only after validation.
