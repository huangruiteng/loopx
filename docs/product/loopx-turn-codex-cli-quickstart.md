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

Advisor mode lets a stronger model produce bounded guidance before a distinct,
lower-cost model executes the Turn:

```bash
loopx turn run-once \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --host codex-cli \
  --project "$PWD" \
  --codex-sandbox workspace-write \
  --advisor-model <strong-model> \
  --codex-model <lower-cost-executor-model> \
  --validation-command-json '["./verify-postcondition"]' \
  --execute
```

When bounded source context is available, the Advisor runs first in an
ephemeral `read-only` Codex session. It receives the TurnEnvelope plus at most
eight literal, non-symlink files named by `write_scope`, capped at 24 KB total;
the repository itself is not mounted. Its compact summary, recommendations,
risks, and validation focus are passed to the executor as non-authoritative
guidance. It cannot change the selected todo, gate, writeback, quota, scheduler,
or executor sandbox. An invoked Advisor failure is fail-closed.

If that bounded context contains no eligible file, LoopX skips the strong-model
call and runs the configured executor directly. The receipt reports
`model_usage.mode=direct` and `advisor_applied=false`, so this cost guard cannot
masquerade as applied advice.

When Codex emits provider usage events, the Turn result includes
`model_usage.advisor`, `model_usage.executor`, and their exact `total`. Only
token counters and an advice digest are retained; advice text, prompts, raw
events, and model responses are excluded from LoopX state. Advisor mode requires
distinct explicit models so an accidental same-model pairing cannot masquerade
as an optimization.

## Read The Result

The compact JSON result tells the caller what happens next:

| Signal | Meaning |
| --- | --- |
| `status=committed` | Independent validation passed; LoopX wrote the durable result and spent once. |
| `result_kind=repair_required` | Keep the todo, repair the execution or artifact, then retry. |
| `result_kind=replan_required` | The current route is no longer valid; write a successor or vision delta. |
| `result_kind=wait` | No host work should run yet. |
| `result_kind=user_action_required` | Show the concrete user action and do not invent a substitute. |

A failed validator cannot commit or spend; replay invokes nothing. A new logical
Turn uses a new stable `--turn-instance-id`, while retries reuse that id.

## Fit Another Runtime

Keep the same boundary when the Agent CLI is backed by a managed runtime:

| Runtime owns | LoopX owns |
| --- | --- |
| Session, turn, sandbox, raw event stream, platform outcome | Goal, todo, gate, control decision, compact evidence, durable outcome |

The adapter carries the existing `turn_key` as a correlation id, creates or
resumes the host run, consumes its Event/Outcome API, and emits one existing
result kind. The validator independently reads tests, a grader, or platform
state. Host observations such as requested, accepted, running, outcome-ready,
failed, and resumed map to committed, repair, replan, or wait; they do not
become new Turn states.

Qualify a new adapter with a real task, scenario owner, adapter owner, validator,
and measurable outcome. Add an event reference only after that call site proves
the compact result cannot carry the evidence.

## Verify The Integration

The repository ships a disposable qualification that keeps raw prompts,
transcripts, credentials, and temporary workspaces out of LoopX state:

```bash
python3 examples/loopx-turn-codex-cli-e2e-smoke.py
python3 examples/loopx-turn-codex-cli-e2e-smoke.py \
  --real-codex-cli \
  --codex-model <qualified-model>
python3 examples/loopx-turn-codex-cli-e2e-smoke.py \
  --real-codex-cli --turn-count 3 --codex-model <qualified-model>
```

The first command is deterministic and model-free. The second makes one real
Codex CLI call and must report `status=committed`, `validation_status=passed`,
one quota spend, and a replay with no side effects. A compact
`codex_cli_model_requires_newer_codex` result is a host compatibility failure,
not task progress; it must show zero state writes and zero quota spend.

The third command makes N real calls against one temporary goal and todo. It
starts one opaque session, resumes it for Turns 2 through N, and independently
validates every marker. With `--turn-count 3`, success reports
`committed_turn_count=3`, `session_resumed=true`, and three quota spends. The
session id remains private and is never printed or synced.

Use the paired live qualification to compare the same isolated task under a
strong-model baseline and Advisor mode. It exits zero only when both independent
validators pass and Advisor plus executor total tokens are lower. The baseline
and Advisor model identifiers must be identical so the only changed role is the
cheaper executor:

```bash
python3 scripts/qualify-loopx-turn-advisor-live.py \
  --baseline-model <strong-model> \
  --advisor-model <strong-model> \
  --executor-model <lower-cost-model>
```

The command prints one compact `loopx_turn_advisor_qualification_v0` receipt,
including the bounded model identifiers assigned to each role. It never records
raw model output and never authorizes automatic promotion.

That is the complete partner-facing path. For implementation details, read the
[adapter notes](codex-cli-automation-driver.md) or the [Turn protocol](../reference/protocols/loopx-turn-v0.md).
