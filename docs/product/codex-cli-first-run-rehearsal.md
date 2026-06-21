# Codex CLI First-Run Rehearsal

Status: product route and release rehearsal.

Goal Harness should feel easy before it feels powerful. A fresh Codex CLI user
should be able to stay in the TUI, paste one message, and see current goal
state, gates, todos, and the next safe action without cloning this repository
or reading Goal Harness internals first.

This route connects three shipped surfaces:

1. no-clone install/update through the GitHub archive installer;
2. one-message Codex CLI TUI bootstrap;
3. proof-capture fixtures for later visible automation.

## Fresh User Path

From the user's project repo:

1. Open Codex CLI TUI.
2. Paste one start message:

   ```text
   Start Goal Harness for this repo. If `goal-harness` is missing, install it
   with the official no-clone GitHub installer, then connect this project. Show
   me the current goal, concrete user gate if any, top todos, and next safe
   action before running longer work. Keep me in this Codex CLI TUI unless I
   explicitly accept a headless fallback. After I paste this, begin the Goal
   Harness loop; do not stop after only explaining what Goal Harness is.
   ```

3. The agent installs or repairs Goal Harness when needed, using:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/huangruiteng/goal-harness/main/scripts/install-from-github.sh | bash
   export PATH="$HOME/.local/bin:$PATH"
   goal-harness doctor
   ```

4. The agent connects the repo, runs quota/status, surfaces any concrete user
   gate, and then starts one bounded validated segment if the guard permits.

The user's first useful response should fit on one screen:

- current goal id;
- user gate, or none;
- top user todo, or none;
- top agent todo;
- next safe action.

## After Install

Once `goal-harness` is on PATH, generate a stricter project-specific TUI message:

```bash
goal-harness codex-cli-bootstrap-message --project . --goal-id <goal-id> --message-only
```

For release rehearsal without running Codex or reading session material:

```bash
goal-harness codex-cli-tui-bootstrap-smoke-bundle \
  --project . \
  --goal-id <goal-id> \
  --agent-id <agent-id>
```

That bundle checks the install-repair command, paste block, quota guard,
bounded writeback, and spend command shape. It is not a first-time user step.
Use the [no-clone release verification](codex-cli-no-clone-release-verification.md)
when validating that the packaged installer and fresh-project command surface
match this route before promotion.

## Later Automation Gate

Same-TUI automation stays optional until the proof path passes. A scheduler may
return to Codex CLI only after all of these are true:

- visible-session proof is public-safe and accepted;
- runtime idle evidence is fresh;
- quota/status guard still permits the selected work;
- the command boundary is explicit;
- validation writes compact evidence or a blocker before spend.

Rehearse the proof path with public fixtures:

```bash
goal-harness --format json codex-cli-visible-attach-acceptance \
  --project . \
  --goal-id public-codex-cli-goal \
  --agent-id codex-side-bypass \
  --fixture examples/fixtures/codex-cli-visible-proof/codex-visible-resume-help.public.json \
  --proof-fixture examples/fixtures/codex-cli-visible-proof/visible-resume-proof.public.json \
  --idle-fixture examples/fixtures/codex-cli-visible-proof/runtime-idle-visible-resume.public.json
```

This current likely path can pass as a visible later-turn spike, but it still
does not prove same-open-TUI automation. Until a same-TUI attach proof is
accepted, the product path remains one-message TUI bootstrap plus explicit
fallbacks.

## Live TUI Pilot Note

The first real [live TUI first-message pilot](codex-cli-live-tui-first-message-pilot.md)
confirmed that the generated message can launch Codex CLI through
`codex [PROMPT]`, but it did not prove that the Goal Harness loop started
successfully. The process stayed active, no bounded first-response marker was
available, and passing the message as argv would leak project-specific prompt
text through the process command line in real repos.

So the reliable first-run route remains manual paste into the visible Codex CLI
TUI. Automated live launch needs a bounded visible completion proof first.

## Boundary

This first-run route must not:

- require cloning the Goal Harness repo;
- launch Codex as part of the rehearsal bundle;
- read raw Codex transcripts, session files, stdout, stderr, credentials, or
  private paths;
- spend Goal Harness quota before validated writeback;
- treat headless `codex exec` as the default user experience;
- promote same-TUI automation without visible proof and idle evidence.

See also:

- [Codex CLI packaged install path](codex-cli-packaged-install.md)
- [Codex CLI TUI-first loop](codex-cli-tui-loop.md)
- [Codex CLI proof-capture demo](codex-cli-proof-capture-demo.md)
