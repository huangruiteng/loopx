# Codex CLI Live TUI First-Message Pilot

Status: blocker recorded; manual TUI bootstrap remains primary.
Recorded: 2026-06-21.

This note records a real Codex CLI TUI pilot for the one-message Goal Harness
bootstrap path. The pilot used only a disposable public-safe repo and kept raw
TUI output, Codex transcripts, session files, credentials, and private project
paths out of the repository.

## Question

Can Goal Harness launch a real visible Codex CLI TUI with the generated start
message and prove that the loop starts, remains observable, and stays steerable
by the user?

## Method

The pilot used a temporary public repo with a small `README.md`, a small
`GOAL.md`, and a generated start message:

```bash
goal-harness codex-cli-bootstrap-message \
  --project /tmp/goal-harness-live-tui-pilot.<suffix> \
  --goal-id public-live-tui-pilot-goal \
  --agent-id codex-side-bypass \
  --message-only
```

The local Codex CLI surface was `codex-cli 0.142.0-alpha.7`. Its help exposed:

- `codex [OPTIONS] [PROMPT]`;
- `--no-alt-screen`;
- `--cd <DIR>`;
- `resume`;
- `remote-control`.

Two bounded probes were attempted:

1. `codex doctor` from the disposable repo. It did not produce bounded output
   before manual interrupt.
2. A real TUI launch with a public-safe generated message:

   ```bash
   codex --no-alt-screen --ask-for-approval never --sandbox workspace-write \
     -C /tmp/goal-harness-live-tui-pilot.<suffix> \
     "$(cat goal-harness-start-message.txt)"
   ```

The second probe launched Codex CLI, but it did not produce a compact,
machine-checkable first-response result in the bounded capture window. The
process was still active afterward and was stopped by exact temp-repo process
match.

## Result

Not proven yet.

The generated message can start a real Codex CLI TUI through `codex [PROMPT]`,
but the current automation-side proof is insufficient for claiming that the
Goal Harness loop started successfully.

Observed blockers:

- no bounded first-response or completion marker;
- capture output exceeded the automation budget before a compact result was
  available;
- the TUI process remained active after the capture window;
- passing the generated message as `[PROMPT]` exposes the prompt in the process
  command line, which is acceptable only for this public-safe pilot and should
  not become the default path for real project repos.

Decision:

`live_tui_first_message_blocked_by_bounded_visible_completion_missing`

## Product Implication

The public user path should still be:

1. the user opens Codex CLI TUI in the project repo;
2. the user pastes one Goal Harness start message;
3. Codex keeps the visible TUI as the live control surface.

Goal Harness should not advertise automated `codex [PROMPT]` launch as a
verified first-run path until a bounded visible pilot adapter exists.

That adapter needs to prove all of these without raw transcript or session-file
reads:

- inject or paste the start message without leaking project-specific prompt
  text through process arguments;
- observe a compact public-safe first-response marker;
- stop or idle-check the TUI without racing the user;
- show that the user can still steer, review, interrupt, or take over;
- write compact success evidence or a precise blocker before quota spend.

## Follow-Up

Create a bounded visible pilot adapter before promoting live TUI automation:

```text
[P0] Codex CLI bounded visible pilot adapter: define and test a minimal
public-safe first-response capture and stop protocol for Codex CLI TUI bootstrap
before claiming live TUI first-message success; avoid raw transcripts, session
files, credentials, private paths, and argv prompt leakage.
```

Until then, keep the no-clone installer, generated paste message, and
transcript-free smoke bundle as the reliable first-run route.
