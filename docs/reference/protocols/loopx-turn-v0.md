# LoopX Governed Turn v0

Status: experimental protocol and implementation target.

Integrators using the built-in Codex CLI host should start with the
[one-Turn quickstart](../../product/loopx-turn-codex-cli-quickstart.md). This
document is the protocol and maintainer reference, not required onboarding.

`loopx_turn_v0` defines how LoopX can govern one bounded turn executed by an
external agent-loop host, such as Codex CLI, without turning that host into a
second control plane. LoopX remains authoritative for goal state, todos,
claims, gates, quota, scheduler hints, and compact evidence. The host owns
model execution, tools, and an opaque resumable session handle.

The protocol is host-neutral. A Codex CLI adapter is the first target, but the
driver lifecycle must not depend on Codex-specific session files, transcript
formats, or benchmark task schemas.

## Mental Model

LoopX Turn is a four-stage control loop, not another agent runtime:

```text
LoopX decides -> agent CLI executes -> validator proves -> LoopX commits
```

| Stage | Owner | Contract |
| --- | --- | --- |
| Decide | LoopX CLI | Select one allowed action from live goal, todo, gate, capability, quota, and cadence state. |
| Execute | Host adapter plus an agent CLI such as Trae CLI or Codex CLI | Consume one typed request, run one bounded segment, and emit one typed candidate result. |
| Validate | Independent task-specific command or callback | Check the real artifact, test, remote state, or declared read-only postcondition. |
| Commit | LoopX CLI | Write durable state and spend one quota slot only after validation passes. |

This separation lets the same Turn contract govern coding, operations, data,
document, knowledge-maintenance, and other long-running workflows. The agent
CLI remains responsible for model and tool execution; it does not become the
authority for goal state or completion.

## Generic Agent CLI Quick Start

An agent CLI does not need native LoopX support. It needs a thin host adapter
and an independent validator:

1. Run `loopx turn plan` to inspect the live typed decision without launching
   the host or changing state.
2. The host adapter reads one `loopx_turn_host_request_v0` JSON object from
   stdin, invokes the selected agent CLI in the governed workspace, and writes
   exactly one `loopx_turn_host_result_v0` JSON object to stdout.
3. The validator reads the normalized host result from stdin and independently
   checks the claimed postcondition. Exit zero means passed; non-zero means the
   result is rejected. A timeout or unavailable validator is inconclusive.
4. `loopx turn run-once --execute` performs writeback and quota spend only when
   the typed result and independent validation both pass.

The adapter and validator executable names below are placeholders supplied by
the integration. They are separate programs because the executor must not
validate its own completion claim.

```bash
loopx turn plan \
  --goal-id example-goal \
  --agent-id example-worker \
  --host generic-cli \
  --execution-mode isolated-headless

loopx turn run-once \
  --goal-id example-goal \
  --agent-id example-worker \
  --host generic-cli \
  --execution-mode isolated-headless \
  --project "$PWD" \
  --host-adapter-command-json '["./tools/turn-host-adapter","--agent-cli","trae","chat"]' \
  --validation-command-json '["./tools/verify-turn-postcondition"]' \
  --execute
```

Do not pass a free-form interactive command directly as
`--host-adapter-command-json` unless it already implements the typed
stdin/stdout contract. For Trae CLI,
Codex CLI, or another conversational CLI, the adapter translates between the
Turn request/result objects and that CLI's prompt, session, and output model.
Raw transcript text, process exit zero, and the host's own completion claim are
never sufficient validation.

### Five Questions For Any Agent CLI

Before wiring Trae CLI, Codex CLI, or another host, answer these five questions:

1. **How does it run unattended?** Choose an explicit non-interactive command
   and workspace. If the CLI is interactive-only, it is not an
   `isolated-headless` adapter yet.
2. **How does it return one typed result?** Prefer a native output schema or a
   dedicated result file. Do not scrape arbitrary conversation text as the
   completion contract.
3. **What is its resume handle?** Keep the opaque handle in local adapter
   state, keyed by `(goal_id, agent_id, todo_id)`. Never put it in LoopX state
   or public evidence.
4. **Which failures may resume?** A bounded timeout or lost transport may
   preserve an observed session. A rejected startup contract, incompatible
   host version, or missing session invalidates it so the next Turn starts
   cleanly.
5. **What proves the work independently?** Name a command that checks the real
   repository, artifact, service readback, document revision, or other
   postcondition without trusting the agent CLI's own claim.

This yields one reusable integration shape:

```text
TurnEnvelope
    -> host adapter -> agent CLI -> typed candidate result
    -> independent validator -> pass | repair | replan
    -> LoopX writeback -> one durable transition and one quota spend
```

A thin adapter can be implemented with this host-neutral algorithm:

```text
request = read_one_json(stdin)
todo = request.turn_envelope.action.selected_todo
session = load_local_session(goal_id, agent_id, todo.todo_id)
prompt = render_bounded_prompt(todo, request.result_contract, temporary_result_path)
invoke_agent_cli(prompt, workspace, session, explicit_timeout)
candidate = read_and_shape_temporary_result(temporary_result_path)
write_one_json(stdout, candidate with request.turn_key)
```

`render_bounded_prompt` should tell the agent CLI to work only on the selected
todo and write its candidate result to a dedicated temporary path. The adapter
must reject a missing or malformed result instead of guessing from prose. It may
discard raw conversation output after extracting the host's opaque session
handle. LoopX then passes the candidate to a separate validator; the adapter
does not call the work complete itself.

For a CLI with native structured output and resume support, the adapter is
mostly field mapping. For a CLI such as a Trae installation whose selected
command only returns conversational text, the wrapper must first establish a
dedicated typed result channel; passing `trae chat` directly as the adapter is
not sufficient. Check the installed CLI's help and pin the qualified command
shape because flags and headless behavior may vary by version.

### Repeatable Codex CLI Qualification

The repository includes an opt-in end-to-end qualification that creates an
ephemeral LoopX project and workspace. Its default mode uses a no-model Codex
fixture while exercising the built-in host adapter, independent validator,
state writeback, one quota spend, and idempotent transaction replay:

```bash
python3 examples/loopx-turn-codex-cli-e2e-smoke.py
```

Use the real mode only when a local Codex login is available and one isolated
model call is intended:

```bash
python3 examples/loopx-turn-codex-cli-e2e-smoke.py \
  --real-codex-cli \
  --codex-model <compatible-model>
```

The real mode emits only a compact LoopX qualification summary. LoopX does not
copy the prompt, transcript, stdout, or stderr into fixture state, the temporary
workspace and LoopX session binding are removed, and the disposable goal never
syncs into the global registry. Codex CLI may retain its opaque host session
according to local Codex policy so a later adapter turn can resume it. A compact
`codex_cli_model_requires_newer_codex` failure is a host-compatibility result:
the transaction must show zero state writes and zero quota spend; select a
compatible model or update Codex before retrying.

For a coding collaboration, the validator may run focused tests and inspect the
expected git diff. For operations, it may read back the declared resource
state. For data work, it may check a schema and bounded quality assertions. For
documents or knowledge maintenance, it may verify the target revision and
required sections. These are different validators over the same Turn
orchestration contract; they do not require different control loops.

## Authority Boundary

| Concern | Authority |
| --- | --- |
| Goal, todo, claim, gate, quota, and cadence | LoopX CLI and registry-backed state |
| Session creation, resume, cancellation, and tool execution | External host adapter |
| Repository write isolation | LoopX workspace guard plus repository policy |
| Validation | Task-specific validator selected by the agent or adapter |
| Durable outcome and quota spend | LoopX writeback after validation |

The host must not infer a different action from status prose. It consumes a
fresh `loopx_turn_envelope_v0` decision and preserves its action signature.
Full quota/status detail remains available through the envelope cold-path
references.

## Turn Lifecycle

One driver tick has exactly these ordered phases:

1. **Wake**: resolve `goal_id`, registered `agent_id`, host kind, explicit
   execution mode, available capabilities, and an optional opaque session
   handle.
2. **Decide**: run live `quota should-run --turn-envelope` with the observed
   capabilities. A fixture is valid only in tests and shadow replay.
3. **Route**: obey the envelope without invoking the host when the user channel
   requires action, work is throttled, a monitor is unchanged, or delivery is
   otherwise disallowed. Apply and acknowledge scheduler-only changes without
   spending quota.
4. **Prepare**: preserve the selected todo identity, claim or lease when the
   contract requires it, and satisfy the workspace guard before any repository
   write.
5. **Execute**: resume the declared host session only when the adapter marked
   it eligible, or create a new session when the execution mode permits it.
   Give the host the thin task body plus the current envelope, and request one
   bounded work segment.
6. **Validate**: classify the host result and validate the claimed artifact or
   state transition. Host process exit zero is not validation.
7. **Write back**: update or complete the current todo, create a repair or
   successor todo when required, and refresh state with compact public-safe
   evidence.
8. **Spend and schedule**: spend one quota slot only after validated writeback,
   then apply and acknowledge the latest scheduler hint. Cadence-only work does
   not spend quota.

The driver may stop after any phase. A stop must return a typed result and must
not silently continue with a different execution mode.

For material results, schema-valid host output is only candidate evidence. The
caller or adapter must select an independent task/postcondition validator
before host execution. The generic CLI accepts a trusted JSON argv array,
passes the normalized host result on stdin, never invokes a shell, and discards
validator stdout and stderr. A missing, failed, or inconclusive validator stops
at `validation_failed`, records a typed `repair_required` or `replan_required`
recovery disposition, and cannot write state or spend quota. Typed stop results
do not require task validation because they produce no material writeback.

An independent callback validator may distinguish terminal completion from
validated intermediate progress. `status=passed` means the declared terminal
postcondition holds and uses exit code `0`. `status=progress` means a bounded,
task-facing postcondition is independently proven but the terminal
postcondition is still open; it uses an explicit non-zero marker. Both statuses
may commit exactly one Turn and one quota spend. Only `progress` permits a host
adapter to start another Turn, and only under a predeclared maximum, shared
total time budget, and no-feedback continuation policy. Every other validator
status fails closed before writeback.

Adapters that lack a separate terminal signal may declare a bounded `fixed-n`
terminal policy. Under that policy, each successful independent validator call
proves progress, while only a successful final configured Turn satisfies the
sequence terminal postcondition. The default `validator` policy continues to
interpret exit code `0` as per-Turn terminal completion. Within a bounded
multi-Turn sequence, a successful Turn that also proves a durable content
change receives one further blinded review Turn before sequence termination;
the next successful no-change Turn may terminate early. The policy is explicit
in public-safe runner prerequisites and never changes benchmark scoring.

## Turn Input

The driver input is a small composition of existing contracts:

```json
{
  "schema_version": "loopx_turn_request_v0",
  "goal_id": "example-goal",
  "agent_id": "codex-worker",
  "host": {
    "kind": "codex_cli",
    "execution_mode": "interactive_visible",
    "session_handle": "opaque-local-handle"
  },
  "wake": {
    "reason": "scheduler_due",
    "turn_key": "stable-idempotency-key",
    "available_capabilities": ["shell", "filesystem_write"]
  },
  "decision": {
    "schema_version": "loopx_turn_envelope_v0",
    "action_signature": {
      "matches": true
    }
  }
}
```

`session_handle` is local adapter state. It must not be committed, copied into
LoopX public state, or treated as identity authority. The stable control-plane
identity is `(goal_id, agent_id, selected_todo.todo_id)`.

Adapters may support two explicit execution modes:

- `interactive_visible`: user-visible and interruptible; never falls back to
  hidden execution.
- `isolated_headless`: an explicitly selected experiment or worker mode in an
  isolated workspace; never claims to preserve an interactive TUI.

Mode selection is input policy, not a retry heuristic.

## Typed Result

Every attempted tick returns one result kind:

| Result kind | Meaning | Required next state |
| --- | --- | --- |
| `validated_progress` | One bounded segment produced validated evidence. | Update current todo, refresh, spend once. |
| `validated_completion` | Acceptance for the current todo is met. | Complete todo, link a successor or record no-follow-up, refresh, spend once. |
| `repair_required` | The todo remains sound but a recoverable execution defect blocks it. | Keep or create a concrete repair todo; do not mark success. |
| `replan_required` | The current route is exhausted or incompatible while the goal acceptance gap remains. | Write a bounded todo delta or vision replan trigger. |
| `user_action_required` | A concrete user decision, payload, or credential action is projected. | Notify with the projected action in the configured operator language; no host run and no spend. |
| `wait` | Quota, monitor, scheduler, or another typed wait contract applies. | Preserve state, apply cadence if needed, no spend. |
| `host_failure` | The host could not start, resume, or finish a turn. | Record the failure class and retry or repair policy. |
| `validation_failed` | Host output exists but task validation failed or is inconclusive. | Preserve failure evidence and route to repair/replan. |
| `writeback_failed` | Validated work could not be durably recorded. | Do not spend; retry idempotent writeback before more delivery. |

`repair_required` and `replan_required` are distinct. Repair preserves the
current task intent. Replan changes the runnable todo set or route because the
existing task no longer advances the goal. Replan is required when any of the
following is true:

- no runnable todo exists while the active vision still has an acceptance gap;
- the selected todo is terminal, obsolete, or incompatible with observed host
  capabilities;
- validated negative evidence invalidates the current route; or
- two eligible turns produce no material progress through the same route.

A driver must not terminate merely because one todo ended. Goal termination
requires goal acceptance evidence, an explicit user stop, or a typed blocked
state with a concrete projected action.

## Recoverable Failure Classes

| Failure class | Driver behavior |
| --- | --- |
| `auth_required` | Stop for the concrete credential action; never read or upload credentials. |
| `session_unavailable` | Return `host_failure`; retry resume or start a new session only if the selected mode permits it. |
| `capability_missing` | Re-run decision with observed capabilities and use capability repair routing, not a fabricated user gate. |
| `workspace_guard_denied` | Repair or relocate the workspace before writes. |
| `executor_timeout` or `transport_lost` | Return `host_failure` with bounded retry metadata; do not infer completion. |
| `result_missing` | Return `validation_failed`; a process exit without typed result is inconclusive. |
| `validation_failed` | Preserve compact negative evidence and choose repair or replan. |
| `writeback_failed` | Retry idempotent writeback; never spend first. |
| `scheduler_apply_failed` | Preserve completed writeback, record cadence failure, and retry scheduler control without a delivery spend. |

Session recovery is fail-closed:

| Host observation | Session disposition | Next Turn |
| --- | --- | --- |
| Typed result returned | Keep the opaque session eligible. | Resume when the same todo remains selected. |
| Timeout or transport loss after a session was observed | Keep it eligible, but do not infer progress. | Retry the side-effect-safe host phase. |
| Incompatible host version or rejected startup/output contract | Invalidate it. | Start a fresh session after repair. |
| Host reports the session is missing | Invalidate it. | Start a fresh session if policy still allows execution. |
| Failure before any session was observed | Store nothing. | Re-decide, then start fresh only if allowed. |

Session eligibility is recovery metadata, not evidence that work happened. It
never bypasses a fresh Turn decision, task lease, independent validation, or
writeback ordering.

## Adapter Requirements

An external host adapter must provide:

- capability discovery that can be passed to `--available-capability`;
- start, resume, cancel, and bounded-timeout operations;
- a public-safe typed result channel separate from raw transcript output;
- an explicit execution mode and no silent mode fallback;
- an opaque local session handle with no authority beyond host resume;
- visibility and idle proof before injecting into an interactive session; and
- deterministic failure mapping to the result and failure classes above.

The smallest useful adapter has only three responsibilities: translate the
typed request into one bounded agent-CLI invocation, preserve an opaque local
resume handle when the host supports it, and translate the final outcome into
one typed candidate result. It must not parse LoopX status prose, write LoopX
state, spend quota, or validate its own work.

The driver may discard raw stdout and stderr, but it must not mistake their
absence for a typed result. Raw prompts, transcripts, benchmark task text,
verifier tails, credentials, and local session paths stay outside committed
fixtures and LoopX state.

## Promotion Gates

The protocol remains experimental until all of these are true:

1. shadow replay preserves the live TurnEnvelope action signature across
   delivery, user gate, monitor wait, capability repair, workspace repair,
   replan, blocked, and throttled states;
2. one real host adapter proves start/resume, typed result, validation,
   idempotent writeback, spend ordering, and scheduler acknowledgement;
3. interactive and isolated-headless modes fail closed without switching into
   each other;
4. a controlled benchmark dogfood run shows source, budget, concurrency, and
   no-feedback boundaries remain comparable; and
5. rollback can disable the adapter while leaving normal LoopX CLI state and
   Codex App heartbeat operation intact.

This protocol does not authorize benchmark launch, leaderboard submission,
production writes, credential handling, or default replacement of Codex App.
