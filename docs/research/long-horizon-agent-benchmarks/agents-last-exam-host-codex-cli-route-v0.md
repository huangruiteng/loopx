# Agents Last Exam Host Codex CLI Route V0

This note records the first LoopX execution route for a future local
Agents' Last Exam (ALE) run that uses the host machine's already authorized
Codex CLI instead of treating ALE as an OpenRouter or API-key-only integration.

It is a route gate, not a task run. It does not start containers, read task
bodies, invoke a model, upload, submit, capture screenshots, read raw
trajectories, or read/copy credential values.

## Route

The desired path is:

1. Keep ALE DockerProvider as the sandbox/task environment.
2. Run `codex exec` on the host machine, using the host's existing Codex
   auth/session.
3. Point a project-local temporary Codex config at the local CUA MCP bridge.
4. Drive the ALE sandbox through CUA/MCP instead of running Codex inside the
   sandbox.
5. Ingest only compact ALE dry-run/result evidence through the existing
   reducer gates.

The upstream ALE `codex` agent is not this route today: it runs inside the
sandbox executor and expects provider-key configuration such as OpenRouter or
direct OpenAI keys. LoopX should therefore gate a host-side wrapper
before any task-level ALE run.

## Public Gate

The public-safe gate is:

```bash
loopx benchmark ale-host-codex-cli-route \
  --codex-binary codex \
  --cua-mcp-assets-root <local-cua-mcp-assets-root> \
  --ale-sandbox-cua-smoke-ready \
  --operator-authorized-host-codex-auth \
  --require-ready
```

It records only compact facts:

- host Codex CLI binary/version availability;
- host auth/config existence booleans, never values or paths;
- local CUA MCP asset readiness, never host paths;
- prior ALE sandbox CUA smoke readiness;
- boundary flags proving no task or credential surface was touched.

The next allowed action after a ready route gate is a no-task host Codex CLI
CUA/MCP E2E preflight:

```bash
loopx benchmark ale-host-codex-cua-no-task-e2e \
  --codex-binary codex \
  --host-auth-cache-present \
  --host-config-present \
  --cua-mcp-assets-root <local-cua-mcp-assets-root> \
  --ale-sandbox-cua-smoke-ready \
  --operator-authorized-host-codex-auth \
  --require-ready
```

This preflight may run `codex --version`, `codex exec --help`, and
`codex mcp list --json` against a project-local temporary Codex config. It must
not send a Codex prompt, invoke a model API, read task material, read or copy
credential values, record raw output, start an ALE task container, upload, or
submit. Task-level ALE execution remains blocked until this compact no-task E2E
artifact is ready.

## Claim Boundary

This gate may claim only that the selected execution route is public-safe and
ready for a no-task E2E preflight, or that the preflight is ready for a
separate task-level ALE dry-run gate. It must not claim ALE reward, task
success, LoopX uplift, leaderboard evidence, or benchmark performance
improvement.

## Smoke

```bash
python3 examples/agents-last-exam-host-codex-cli-route-smoke.py
```
