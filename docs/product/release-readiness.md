# Release Readiness

Status: v0.x maintainer contract.

LoopX can move quickly without making every merged PR feel like a product
release. This note defines the small mental model maintainers should use before
promoting a release snapshot, recommending an install path, or telling users
which control-plane surfaces are safe to build on.

## Supported Install And Update Paths

For a first-time user, prefer the no-clone archive installer:

```bash
curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh | bash
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
```

For a user who already installed from the archive, update through the explicit
CLI flow:

```bash
loopx update --check
loopx update --dry-run
loopx update --execute
loopx doctor
```

For contributors, keep the clone-plus-canary path:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
loopx doctor
loopx-canary doctor
```

The no-clone path is the user default. The clone-plus-canary path is the
maintainer validation path.

## Compatibility Gate

Before a release snapshot is promoted or a public guide tells users to depend
on a new surface, run the smallest gate that covers the touched surface:

```bash
python3 -m py_compile loopx/*.py
python3 examples/codex-cli-no-clone-release-verification-smoke.py
python3 examples/fresh-clone-quickstart-smoke.py
python3 examples/loopx-update-smoke.py
python3 examples/release-readiness-doc-smoke.py
git diff --check
loopx check --scan-path README.md --scan-path docs/ --scan-path examples/
```

This is not a universal full suite. Add focused smokes for the changed command,
projection, or workflow. Do not require benchmark raw logs, raw task text,
trajectories, verifier output, credentials, or local private artifact paths as
release evidence.

## What Is Safe To Depend On

Treat these v0.x surfaces as stable enough for user guides, examples, and
host integrations when their focused smokes pass:

- `loopx doctor`, `loopx update`, `loopx check`, and the no-clone installer;
- project lifecycle commands: `bootstrap`, `connect`, `status`,
  `refresh-state`, `registry`, and `sync-global`;
- todo lifecycle commands: `todo add`, `todo claim`, `todo update`,
  `todo complete`, `todo list`, `todo supersede`, and `todo archive`;
- control-plane read paths: `quota should-run`, `quota spend-slot`,
  `review-packet`, `heartbeat-prompt --thin`, task graph projection, and cold
  todo detail references;
- public slash command names: `/loopx`, `/loopx <goal>`,
  `/loopx-global-summary`, `/loopx-global-gates`, `/loopx-global-todos`, and
  `/loopx-global-risks`;
- ignored local state boundaries under `~/.codex/loopx`, project-local registry
  files, and project-local active-state workbench files recognized by
  `loopx doctor`, `loopx status`, and `loopx check`.

Treat these as experimental until their contract docs say otherwise:

- benchmark runner behavior, scoring, upload, and raw task execution routes;
- host-plugin command registry implementations beyond the published protocol
  contract;
- frontstage/dashboard presentation details that are not part of the public
  status data contract;
- monitor scheduler cadence fields while they are still rolling out across
  todo creation, quota projection, writeback, and migration.

## Release Note Checklist

Every public release note or update note should answer:

- What user-visible capability became more dependable?
- Which install/update path should a new user follow?
- Which commands, docs, or smokes prove the claim?
- Are there compatibility or migration notes for existing local state?
- Which surfaces are still experimental or intentionally excluded?
- Did the public/private scan run on the changed docs, examples, and workflow
  files?

The note should link to durable docs or PRs when useful, but public git history
and shipped CLI behavior remain the source of truth.

## Related Docs

- [Codex CLI packaged install path](codex-cli-packaged-install.md)
- [Codex CLI no-clone release verification](codex-cli-no-clone-release-verification.md)
- [Getting started](../guides/getting-started.md)
- [Update notes](../update-notes/README.md)
- [Public/private boundary](../public-private-boundary.md)
