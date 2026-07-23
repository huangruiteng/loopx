# Run One LoopX Turn With Codex CLI

Status: experimental `isolated-headless` product path.

LoopX Turn needs only three pieces:

1. **Agent CLI adapter**: the built-in `codex-cli` adapter translates one typed
   LoopX request into one bounded Codex CLI run and returns one typed result.
2. **Independent validator**: your command checks the real postcondition. It
   does not trust the agent's completion claim.
3. **One Turn command**: LoopX decides, Codex executes, the validator proves,
   and LoopX commits.

```text
LoopX decides -> Codex CLI executes -> validator proves -> LoopX commits
```

## Before You Run

You need a connected LoopX goal, a registered agent with a runnable todo, an
isolated project workspace, and an executable validator. The validator receives
the normalized host result on stdin and exits zero only when the actual artifact
or state is correct.

Check the local host once with `codex doctor`. If the default model is newer
than the installed Codex CLI, update Codex or pass `--codex-model`.

## Run One Turn

For a write-capable coding todo:

```bash
loopx turn run-once \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --host codex-cli \
  --project "$PWD" \
  --codex-sandbox workspace-write \
  --codex-model <qualified-model> \
  --validation-command-json '["./verify-postcondition"]' \
  --execute
```

The built-in Codex adapter means there is no adapter program to write for this
path. A different Agent CLI uses the same Turn contract through a thin
`generic-cli` adapter that reads one JSON request from stdin and writes one JSON
result to stdout.

## Use A Read-Only Advisor

Advisor mode lets a lower-cost model inspect the task first and call a stronger
model only when a strict complexity checkpoint justifies the extra cost:

```bash
loopx turn run-once \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --host codex-cli \
  --project "$PWD" \
  --codex-sandbox workspace-write \
  --advisor-mode auto \
  --validation-command-json '["./verify-postcondition"]' \
  --execute
```

Auto is an explicit experimental opt-in, not a qualified default or an
automatic-promotion policy. It selects an experimental candidate pair from the
live Codex catalog and fails closed when none is available. Manual mode uses distinct `--advisor-model <strong-model>`
and `--codex-model <lower-cost-model>` values. The executor first emits an
inspection-only checkpoint. Simple work skips the strong model and resumes the
executor; complex work names a supported risk signal, receives compact advice
from an ephemeral read-only session, then resumes the same executor. Advisor
guidance cannot change the TurnEnvelope, sandbox, validator, writeback, or quota. This minimizes context; it is not a confidentiality or security sandbox.

`model_usage` records exact observed counters and a `skipped_simple`,
`applied_complexity`, or `fallback_failure` decision. Prompts, raw event stream,
responses, and advice text are not persisted. Explicit TraeX qualification may
use `--codex-bin <path-to-traex>` plus manual model ids; its prompt-carried JSON
schema and headless resume sandbox are qualified here, while auto selection
remains Codex-only.

## Read The Result

`status=committed` means independent validation passed and LoopX spent once.
`result_kind=repair_required` retries the todo; `result_kind=replan_required`
changes its route; `result_kind=wait` runs no host work; and
`result_kind=user_action_required` exposes the concrete user gate. Failure does
not commit or spend, and replay invokes nothing. New work gets a new `turn_key`.

For another runtime, keep session, sandbox, and raw event stream inside the
host while LoopX owns goal state and durable outcomes. Host observations map to
existing outcomes; they do not become new Turn states. Qualification needs a
real task, scenario owner, adapter owner, validator, and measurable outcome.

## Verify The Integration

The disposable smoke keeps raw prompts and temporary workspaces out of state:

```bash
python3 examples/loopx-turn-codex-cli-e2e-smoke.py
python3 examples/loopx-turn-codex-cli-e2e-smoke.py --real-codex-cli \
  --codex-model <qualified-model>
python3 examples/loopx-turn-codex-cli-e2e-smoke.py --real-codex-cli \
  --turn-count 3 --codex-model <qualified-model>
```

Success requires `status=committed`, `validation_status=passed`, one spend, and side-effect-free replay.
Three Turns also require session resume and three commits. `codex_cli_model_requires_newer_codex` is compatibility failure, not progress.
Use `scripts/qualify-loopx-turn-advisor-live.py` for paired quality and Token comparison; it never records raw output or promotes a profile.
See the [adapter notes](codex-cli-automation-driver.md) and [Turn protocol](../reference/protocols/loopx-turn-v0.md).
