# Contributing To LoopX

Thanks for helping improve LoopX. This project is early, so the best
contributions are small, reviewable, and tied to a public task or clear bug.

## Find Work

Start with [CONTRIBUTOR_TASKS.md](CONTRIBUTOR_TASKS.md). It lists public work
that is useful, claimable, and safe to discuss in the repository.

If you do not see a matching task:

1. open a GitHub issue with the contributor task template;
2. explain the problem, proposed scope, touched files, and validation command;
3. wait for maintainer feedback before starting large or behavior-changing
   work.

Small docs typo fixes and obviously safe cleanups can go straight to a pull
request.

## Public And Private Boundaries

LoopX coordinates local agent state, so some files are runtime data and
must stay out of public contributions:

- do not commit `.loopx/`, `.codex/goals/`, or live
  `ACTIVE_GOAL_STATE.md` files;
- do not publish private benchmark traces, verifier output, raw agent sessions,
  credentials, internal document links, or local machine paths;
- do not run or duplicate maintainer-owned benchmark cases unless a maintainer
  has split out a public issue for that work.

Safe contribution surfaces include docs, examples, smoke tests, CLI diagnostics,
schema docs, dashboard UI code, and sanitized fixtures.

Run the public/private scan before sending docs or examples:

```bash
loopx check \
  --scan-path README.md \
  --scan-path CONTRIBUTING.md \
  --scan-path CONTRIBUTOR_TASKS.md \
  --scan-path docs/ \
  --scan-path examples/
```

## Local Development

Install and verify the checkout:

```bash
git clone https://github.com/huangruiteng/loopx ~/loopx
~/loopx/scripts/install-local.sh
export PATH="$HOME/.local/bin:$PATH"
loopx doctor
loopx demo
```

Common focused checks:

```bash
python3 -m py_compile loopx/*.py
python3 examples/demo-cli-smoke.py
python3 examples/fresh-clone-quickstart-smoke.py
python3 examples/control_plane/todo-cli-smoke.py
python3 examples/control_plane/todo-lifecycle-cli-smoke.py
python3 examples/control_plane/quota-contract-smoke.py
python3 examples/control_plane/review-packet-cli-smoke.py
loopx check --scan-root .
git diff --check
```

For dashboard changes:

```bash
cd apps/dashboard
npm install
npm run build
npm run smoke:demo-readiness
```

## Claiming A Task

- Comment on the issue before starting non-trivial work.
- If a maintainer marks it `claimed` or assigns it to you, keep the scope close
  to the issue.
- If you get stuck, comment with the blocker and what you already tried.
- If you need to change the scope, ask first.
- If there is no update for 14 days, maintainers may release the task so
  someone else can pick it up.

## Pull Request Checklist

Before opening a pull request:

- link the issue or task ID when one exists;
- describe the behavior change and the validation you ran;
- keep unrelated formatting or refactors out of the PR;
- include docs or tests when changing user-visible behavior;
- confirm that no private/local runtime state was committed.

Maintainers may ask for a smaller PR if the change mixes unrelated concerns.
