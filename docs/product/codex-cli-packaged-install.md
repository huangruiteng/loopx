# Codex CLI Packaged Install Path

Status: early product path.

LoopX should be easy to adopt from the tool the user already has open.
For Codex CLI users, the first successful path is:

1. Open Codex CLI TUI in a project repo.
2. Paste one LoopX start message.
3. If `loopx` is missing, let the agent run the no-clone installer.
4. Return to the same TUI with current objective, gate, todo, and next safe action.

The user should not have to clone this repository before learning whether
LoopX helps their project.

## Current User Path

For a fresh machine, the installer can be run without a manual clone:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

The installer downloads a GitHub archive, creates a stable local release
snapshot under `~/.local/share/loopx/releases/`, installs the
`loopx` wrapper under `~/.local/bin`, and installs the reusable Codex
skills under `~/.codex/skills`. It also refreshes the lightweight slash-command
facades:

- `~/.codex/skills/loopx-project/SKILL.md` for the Codex project-command
  fallback shown as `LoopX` in `/skills`;
- `~/.codex/skills/loopx*/SKILL.md` for the remaining explicit Codex command
  facades, while upgrades retire the older managed `$loopx` facade;
- `~/.claude/skills/loopx*/SKILL.md` for Claude Code slash-command discovery.

Current verified Codex CLI builds still reject user-installed `/loopx` and
`/prompts:loopx` commands, so the packaged install reports Codex CLI as an
unsupported native slash surface. For an explicit Codex skill invocation, use
`$loopx` or choose `loopx` from `/skills`. For the visible long-running TUI
loop, use `loopx codex-cli-bootstrap-message --project .`, paste the generated
setup into the TUI, then set the generated `/goal <thin task_body>`.

By default, the archive source is the public `stable` ref. Maintainers can
override it with `LOOPX_REF=main` when intentionally testing or repairing from
the current repository head.

It intentionally skips `loopx-canary` by default because there is no
durable live checkout in this mode. Contributors who want a canary should clone
the repository and run `scripts/install-local.sh`.

## Codex CLI TUI Message

The agent-first start message can now be stricter about install repair:

```text
Start LoopX for this repo. If `loopx` is missing, install it with
the official no-clone GitHub installer, then connect this project. Show me the
current objective, concrete user gate if any, top todos, and next safe action before
running longer work. Keep me in this Codex CLI TUI unless I explicitly accept a
headless fallback.
```

This keeps the product hierarchy clear:

- first run: one visible TUI message;
- install repair: no manual clone required;
- generated bootstrap packet: exact TUI paste block, no-clone repair command,
  and transcript-free validation checklist;
- copy-only mode: `codex-cli-bootstrap-message --message-only` prints just the
  pasteable TUI block, while the default output remains the review packet;
- smoke bundle: `codex-cli-tui-bootstrap-smoke-bundle` verifies the fresh-repo
  installer, paste block, quota guard, and bounded writeback commands without
  launching Codex or reading transcripts;
- recurring automation: separate driver work;
- contributor development: clone plus canary remains available.

## Update Path

For users installed through the archive script, update through the explicit
LoopX CLI flow:

```bash
loopx update --check
loopx update --dry-run
loopx update --execute
loopx doctor
```

The update command plans the source archive, reports the installed release
snapshot, preserves runtime state under `~/.codex/loopx`, and refreshes the
executable and skills together when `--execute` is accepted.

For the normal GitHub repo/ref source, `--check` compares the installed package
version with that exact ref using a short, read-only network probe. Offline
checks still report local install health and make the missing remote comparison
explicit. Custom archive URLs skip this comparison rather than guessing which
version they contain.

`loopx update` uses the same `stable` ref by default. Use `loopx update --ref
main` only when you intentionally want a dev/head refresh instead of the stable
channel.

Re-running the curl installer is still the repair/fallback path when the local
wrapper or release snapshot is broken enough that `loopx update` cannot run.

## Contributor Path

For contributors and registered peers working on LoopX itself, keep using a
real checkout:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
loopx doctor
loopx-canary doctor
```

That path installs both the stable release wrapper and a live canary wrapper,
which is useful for validating local changes before promotion.

## Future Packaging

The no-clone archive installer is the first bridge. A mature release channel
should later add:

- a signed or checksum-pinned release archive;
- `pipx install loopx` or `uv tool install loopx` after package
  publishing is ready;
- a Homebrew formula for macOS users;
- signed release manifests that report current release id, latest available
  release, and installed skill freshness.

Do not make these future channels block the current Codex CLI TUI path. The
first product win is that a user can paste one message and get a working local
control plane without leaving the repo.
