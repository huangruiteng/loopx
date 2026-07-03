# LoopX Regression Suite

This directory is for low-frequency behavior regressions that check how Goal
Harness CLI contracts are consumed by worker/executor surfaces.

Fast deterministic examples stay under `examples/`. Files here may exercise
real local tools such as Codex CLI when explicitly requested, so they should be
run deliberately during release or major control-plane changes.

## Current Regressions

Run all default contract-only regressions:

```bash
python3 regression/run-regressions.py
```

The default suite must stay public-safe and dependency-light: no real Codex CLI,
Docker, private prompts, raw trajectories, raw logs, verifier tails, or local
credential material. Keep real-agent paths as explicit per-file opt-ins.

```bash
python3 regression/cli-command-module-contract.py
```

Runs a contract-only compatibility check for the first modular CLI command
seam. It imports `loopx.cli_commands`, then verifies the old public
`doctor`, `new-project-prompt`, `demo`, `check`, `status`, and
`review-packet` invocations still return successful JSON payloads after their
registration/handling moves out of the top-level `cli.py` file.

```bash
python3 regression/blocked-priority-fallback-contract.py
```

Runs a contract-only projection regression for the human-in-the-loop pattern
where a higher-priority todo is blocked but a lower-priority fallback is safe.
It checks that `quota should-run` keeps the blocked item user-visible with
`notify=NOTIFY`, does not require a new user answer, and still selects the safe
fallback as the agent action in the interaction contract and protocol packet.

```bash
python3 regression/scoped-user-gate-fallback-contract.py
```

Runs a contract-only projection regression for a scoped user gate: one user
decision blocks the matching agent todo, but a non-dependent executable fallback
remains available. It checks that `quota should-run` keeps the user gate
`NOTIFY` path visible while still requiring the agent to execute the selected
fallback and spend only after validated writeback. It also checks that a
prose-only user gate does not block an explicitly scoped, unrelated agent
action just because the two texts share generic benchmark terms.

```bash
python3 regression/no-progress-self-repair-contract.py
```

Runs the autonomous no-progress self-repair contract. This wrapper deliberately
reuses `examples/autonomous-replan-obligation-smoke.py` instead of copying the
fixture: repeated no-progress signals should force an autonomous replan/self-
repair obligation before another quiet wait.

```bash
python3 regression/autonomous-replan-vs-dreaming-contract.py
```

Runs the contract-only separation check for autonomous replan versus dreaming.
It creates a compact `dreaming_exploration_proposal` fixture and verifies that
status/quota surface it as an advisory user/controller gate with no
`agent_command`, no autonomous replan obligation, no delivery permission, and
no quota spend path. It also verifies the compact
`server_managed_planning_contract_v0` projection: planning may rank candidate
todos and suggest evidence probes, but may not execute protected actions, read
private material, mutate active state, append delivery history, or spend
delivery quota before promotion.

```bash
python3 regression/external-evidence-observation-real-codex.py
```

Runs the contract-only path. It creates an isolated LoopX fixture and
checks two projection contracts:

- explicit `waiting_on=external_evidence` goals return an
  external-evidence observation obligation with delivery disabled until the
  observation or compact blocker is written back;
- the compact guard/prompt handed to Codex is sufficient to require
  `compact_blocker_writeback` when no observable worker/controller handle is
  present, while forbidding quiet no-op and benchmark execution;
- already-launched advancement work with compact-result poll context remains a
  bounded delivery lane, with the external monitor treated as auxiliary
  context rather than a quiet no-op excuse.

```bash
python3 regression/quota-executable-backlog-projection.py
```

Runs a CLI-level quota projection regression over an isolated registry/runtime
fixture. It checks that when a P0 external monitor remains open but unchanged
and a P1 advancement todo is executable, `quota should-run` selects the P1
backlog item as `recommended_action`, interaction primary action, and protocol
packet action while keeping the monitor as context. It also checks that the
payload exposes a state-action projection warning when the visible
`Next Action` still points at the stale monitor action, and that
`refresh-state` derives its default recommended action from the first open
Agent Todo rather than the stale `Next Action`.

```bash
python3 regression/automation-loop-heartbeat-poll-contract.py
```

Runs the automation-loop heartbeat poll contract by reusing
`examples/control_plane/heartbeat-quota-flow-smoke.py`. It checks that bounded heartbeat
delivery only spends after validated state writeback, repeated monitor polls
stay quiet and do not spend, compact external-evidence observation remains
bounded, and projection warnings route stale `Next Action` text behind the
selected executable todo.

```bash
python3 regression/external-evidence-observation-real-codex.py --real-codex
```

Additionally invokes the host `codex exec` in `--ephemeral`, read-only mode
with an output schema. This consumes a real Codex run and verifies that the
worker interprets a missing external-evidence handle as a compact blocker
writeback, not a quiet no-op or benchmark execution.

The real path defaults to `--codex-model gpt-5.4-mini` so it does not depend on
the user's Codex CLI default model. Override with `--codex-model <model>` when a
release lane needs a specific model surface.

```bash
python3 regression/agentissue-lagent239-real-codex-runner.py
```

Runs the AgentIssue-Bench `lagent_239` runner contract-only path. It
materializes the private runner wrapper and checks the no-generator-execution,
selected-image, source-extraction, entrypoint eval, compact reducer, and
credential-boundary contracts without invoking Codex or Docker.

```bash
python3 regression/codex-app-server-goal-baseline-contract.py
```

Runs the contract-only Codex Goal benchmark baseline seam. It verifies that the
preferred automation surface is Codex app-server `thread/goal/set` plus
`thread/goal/get` with `experimentalApi=true`, that `codex exec` remains only a
connectivity smoke, and that slash-prefixed prompts or LoopX state leaks
cannot be promoted into paired baseline evidence.

```bash
python3 regression/codex-app-server-goal-baseline-contract.py --real-codex
```

Optionally starts a real local `codex app-server` with isolated `HOME` and
`CODEX_HOME`, sets a paused goal, reads it back, and prints only compact
public-safe evidence. This is an explicit release/debug probe, not part of the
default suite.

```bash
python3 regression/agentissue-lagent239-real-codex-runner.py \
  --real-codex \
  --prompt-path <private-agentissue-prompt.md>
```

Additionally invokes the host `codex exec` plus the selected
`alfin06/agentissue-bench:lagent_239` Docker image. It writes raw prompt,
stdout/stderr, and patch artifacts only under the temporary private regression
root, then prints a compact public-safe score and boundary summary.
