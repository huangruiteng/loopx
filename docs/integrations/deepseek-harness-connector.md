# DeepSeek Harness Connector

Status: public-safe v0 connector for using DeepSeek Harness (`dsh`) as a
bounded agent execution host behind LoopX.

DeepSeek Harness is an open-source agent harness by DeepSeek AI. LoopX does not
replace dsh's model loop, tools, sandbox, or session log. Instead, the connector
lets LoopX govern one dsh-backed work segment at a time through the existing
LoopX Turn protocol:

```text
LoopX quota should-run
    -> loopx turn run-once
    -> loopx.dsh_goal_mode adapter (python -m loopx.dsh_goal_mode)
    -> DeepSeek Harness Python SDK / dsh runtime
    -> typed loopx_turn_result_v0
    -> independent validator
    -> LoopX writeback + quota spend
```

## What This Connector Adds

- A thin adapter, now a first-class goal-mode subpackage at
  `loopx/dsh_goal_mode/` (run with `python -m loopx.dsh_goal_mode`; the
  historical `scripts/dsh_turn_host_adapter.py` launcher still works),
  that translates
  `loopx_turn_host_request_v0` into one bounded dsh session prompt and parses
  the model's final JSON result back into `loopx_turn_result_v0`.
- A `deepseek-harness` agent type in LoopX onboarding so users can request the
  exact host instead of the generic `other-agent`.
- Optional dependency `loopx[deepseek-harness]` for the
  `deepseek-harness-sdk` Python client.

## Install

Install LoopX's optional DeepSeek Harness extra:

```bash
python -m pip install 'loopx[deepseek-harness]'
```

The DeepSeek Harness SDK spawns the bundled `dsh-jsonrpc-agent` runtime. It
inherits normal dsh environment variables such as:

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
DSH_SESSION_ROOT
DSH_CWD
```

Prepare a dsh `cordis.yml` when the default bundled composition is not
appropriate. See the
[DeepSeek Harness Python SDK reference](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/README.md)
for runtime selection and configuration.

## Onboard

```bash
loopx doctor --agent-type deepseek-harness

loopx agent-onboard \
  --agent-type deepseek-harness \
  --project . \
  --goal-id <goal-id> \
  --agent-id deepseek-worker \
  --available-capability shell
```

`deepseek-harness` maps to the generic CLI agent loop and uses
`--runtime-profile generic_cli` in quota/heartbeat commands.

## Run One Governed Turn

```bash
loopx turn run-once \
  --goal-id <goal-id> \
  --agent-id deepseek-worker \
  --host generic-cli \
  --execution-mode isolated-headless \
  --project "$PWD" \
  --host-adapter-command-json '["python3", "-m", "loopx.dsh_goal_mode", "--cordis", "/path/to/cordis.yml", "--model", "deepseek-v4-flash"]' \
  --validation-command-json '["python3", "/path/to/verify-postcondition.py"]' \
  --execute
```

The adapter stores opaque dsh session data under
`<workspace>/.local/.dsh-sessions/` by default. Override with
`--session-root <path>` when a different local path is required.

## Boundaries

- LoopX keeps the durable goal, todo, claim, gate, quota, evidence, and
  scheduler authority.
- dsh owns model calls, tools, sandboxing, and the raw session log.
- The adapter must not publish raw transcripts, dsh JSONL sessions, credentials,
  local absolute paths, or unbounded tool output into LoopX state.
- `DeepSeekHarness.run()` returns the candidate result; it is not proof of
  completion. An independent validator is required before LoopX writeback.
- The dsh Python SDK is an optional dependency. Core LoopX remains runtime
  dependency-free.

## Hermetic Validation

The repository includes three smokes. The first two do not require the
DeepSeek Harness SDK or a real dsh runtime:

```bash
python3 examples/dsh-turn-host-adapter-smoke.py
python3 examples/loopx-turn-dsh-e2e-smoke.py
```

The first guards adapter translation and result shaping. The second drives the
full `loopx turn run-once -> adapter -> fake dsh -> validator -> writeback ->
quota spend -> idempotent replay` chain.

The third uses the real `deepseek-harness-sdk` and the bundled dsh JSON-RPC
runtime. It still avoids a real model call by serving a local mock OpenAI-compatible
SSE endpoint, so it is hermetic and does not require `DEEPSEEK_API_KEY`:

```bash
python3 examples/loopx-turn-dsh-real-e2e-smoke.py
```

The real-dsh smoke proves that the adapter can start the actual dsh runtime,
run one bounded turn through the real JSON-RPC agent loop, parse a typed JSON
final message, and complete LoopX validation/writeback/quota spend.

## Related Contracts

- [DeepSeek Harness control-plane adapter](deepseek-harness-control-plane-adapter.md)
- [Runtime connector catalog](runtime-connector-catalog.md)
- [LoopX Turn v0](../reference/protocols/loopx-turn-v0.md)
- [Host integration surface v0](../reference/protocols/host-integration-surface-v0.md)
- [Embed LoopX In Your Agent Runner](../guides/custom-agent-runner-integration.md)
