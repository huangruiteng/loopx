# Repository Change Window

`repository-change-window` is a built-in, default-off capability for two
related caller outcomes:

1. apply a typed local schedule before repository commits and pushes; and
2. retain a restart-safe inventory of unmerged work when that schedule blocks
   delivery.

The capability owns policy evaluation and pending-change lifecycle. The
bundled `git-hook` provider owns Git integration. The LoopX Kernel remains the
authority for goals, todos, gates, and quota; installing this provider does not
grant repository or remote-write authority.

## Install and inspect

Every mutating command previews by default. The built-in schedule shown below
blocks Monday through Friday from 10:00 inclusive until 21:00 exclusive in
`Asia/Shanghai`:

```bash
loopx change-window install --repo-path . --format json
loopx change-window install --repo-path . --execute --format json

loopx change-window status --repo-path . --format json
loopx change-window verify --repo-path . --format json
```

Before a repository provider exists, `status` reports one of two typed states:

- `provider_not_installed` when neither `core.hooksPath` nor
  `core.sshCommand` contributes an effective configured guard; or
- `effective_external_guard_detected` when either surface is configured.

The external-guard diagnostic contains only surface and configuration-scope
enums. It never returns a hook path or command, infers a schedule, or treats an
arbitrary script as trusted provider state. A bounded signature can recognize
the earlier LoopX global commit-time gate and offer a typed, preview-first
repository-provider migration. That preview layers the repository provider,
preserves the effective global guard, and does not modify global Git
configuration. Unknown external guards remain diagnostic-only and fail closed.

Installation defaults to the backward-compatible `hook_only` enforcement
level. It manages `pre-commit` and `pre-push`; Git's `--no-verify` option can
skip those client hooks. Repositories that want a stronger local guard must
opt in explicitly:

```bash
loopx change-window install \
  --repo-path . \
  --enforcement-level reference_guard \
  --execute \
  --format json

loopx change-window verify --repo-path . --format json
```

`reference_guard` additionally manages Git's `reference-transaction` hook and
the repository-local `core.sshCommand` route. In a blocked window it rejects a
`HEAD` or local-branch update that introduces a new commit, including
`git commit --no-verify`. The `pre-push` hook covers ordinary pushes, while the
SSH route also rejects an SSH push that uses `--no-verify`. Checkout,
linked-worktree creation, branch deletion, SSH fetches, and local branch
creation at a commit already reachable from another local branch, a remote-tracking
branch, or the current `HEAD` stays available. This includes fast-forward pulls
after fetch; a pull that creates a new merge/rebase commit still faces the gate.
Tags, notes, and custom refs do not make a new commit
eligible for a local-branch update during the blocked window.
Unknown SSH service commands fail closed. `status` and `verify` report the
typed enforcement level, exact managed hook set, and SSH-route health.

Managed hooks use the selected-command CLI loader rather than loading every
capability. Reference updates outside `HEAD`/local branches and post-transaction
phases do not evaluate the time policy. Provider integrity checks and the prior
hook's phase, input, output and exit status remain in force. Successful managed
hooks are quiet; failures remain visible. Direct `change-window hook` diagnostics
remain structured unless `LOOPX_GIT_HOOK_QUIET_SUCCESS=1` is set. This flag only
controls output, never admission, and is harmless with older runtimes.

After upgrading the runtime, preview `change-window install` with the existing
policy and enforcement settings plus `--replace`, then add `--execute` to refresh
older generated hooks. Preserve the existing window; do not accidentally use
installation defaults as a new policy. Status/verify still recognize an intact
older installation; install detects that its hook generation needs refresh.

Customize one typed v0 window with repeatable weekdays and IANA timezone data:

```bash
loopx change-window install \
  --repo-path . \
  --timezone Europe/Berlin \
  --blocked-weekday mon \
  --blocked-weekday tue \
  --blocked-start 09:30 \
  --blocked-end 18:00 \
  --execute \
  --format json
```

An end earlier than its start is an overnight window associated with the day
on which it starts. Equal start and end values are rejected instead of being
interpreted as an implicit full-day lock.

The provider writes only repository-local Git configuration and private state
under the repository's Git common directory. Linked worktrees therefore share
one installation and policy. Managed hooks evaluate the policy and then call
the same hook from the route that was effective before installation, including
stdin and hook arguments. The SSH guard delegates to the previously effective
`core.sshCommand`, or to `ssh` when none was configured. A modified managed
command, changed hook or SSH route, invalid policy, or missing state fails
verification closed.

At the CLI composition root, this capability registers a bounded, read-only
`interaction_projection` hook. Kernel orchestration validates the registration
and candidate in the typed TypeScript boundary, isolates provider failure, and
rejects write scopes or conflicting projection slots without importing this
capability. When the provider is installed and all provider checks pass,
`quota should-run` adds `interaction_contract.repository_delivery`. This
projection keeps `prepare_dirty_worktree` and `validate_dirty_worktree`
admitted by the local schedule while projecting `commit` and `push` separately
from the verified policy decision. A blocked decision carries
`next_eligible_at`. Uninstalled, external-only, or drifted providers produce no
trusted repository-delivery admission. The projection is path-free, is shared
across linked worktrees, does not extend to separate clones, and never grants
remote-write authority or overrides other LoopX gates.

This is a read-time projection hook, not an effect callback: it receives only
the path-free provider status candidate, runs at most once per dispatch, and
cannot write Git configuration, create commits, push, or merge. A future
post-writeback hook uses a separate durable-receipt and idempotency contract;
this registration does not implicitly gain that lifecycle.

The execution clock is not a caller argument. Live hooks use the invocation
clock; tests inject an aware fake clock through the Python contract so an
artifact timestamp cannot move a commit or push into an allowed window.

## Pending-change ledger

When a hook blocks a commit or push, it automatically records or refreshes a
stable checkout-scoped pending change. Attached branches retain their existing
identity; detached worktrees receive a path-free, machine-local checkout id so
work prepared during a change window can be recovered without creating a
branch. The shared runtime event contains:

- a stable `change_id` and credential-free repository identity;
- typed `branch` or `detached` checkout identity and exact head OID;
- counts and content digests for staged, unstaged, and untracked state;
- the typed gate decision and next eligible time; and
- lifecycle source and update time.

It does **not** contain code, a patch, a diff body, credential material, file
names, or a local absolute path. A separate mode-`0600` machine-private locator
retains the producing worktree plus its repository-relative changed-path
inventory; list, reconciliation, and verification packets expose only counts
and never expose those paths.

Add goal, Todo, PR, write-scope, and validation lineage explicitly when it is
available:

```bash
loopx change-window record \
  --repo-path . \
  --goal-id example-goal \
  --todo-id todo_example123 \
  --write-scope 'src/**' \
  --validation-ref 'pytest:tests/unit:passed' \
  --execute \
  --format json

loopx change-window list --state open --format json
loopx change-window verify --change-id change_example123 --format json
```

A hook can only observe an attempted Git operation. Work prepared during a
blocked window may therefore remain dirty without reaching `pre-commit`,
`reference-transaction`, or `pre-push`. Reconcile the current checkout during
normal writeback, or explicitly sweep every linked and detached worktree in
the same Git common directory before a wider handoff:

```bash
loopx change-window reconcile --repo-path . --format json
loopx change-window reconcile --repo-path . --execute --format json
loopx change-window reconcile \
  --repo-path . \
  --all-linked-worktrees \
  --execute \
  --format json
```

Reconciliation is a no-op while the policy allows repository changes and
requires an installed provider. The bounded default inspects only
`--repo-path`; `--all-linked-worktrees` is the explicit repository-wide
recovery sweep. Both ignore clean worktrees, record dirty checkouts
idempotently, and return only path-free checkout ids and counts. Run the
bounded form after preparing gated work and the wider sweep before a handoff,
shutdown, or gate-open delivery pass. Wide-sweep output keeps aggregate counts
authoritative and caps per-checkout detail so a large historical worktree set
does not flood the control packet.

`record` is idempotent for the same identity and fingerprint. A changed head,
changed-path inventory, or worktree fingerprint appends a `refreshed` event
rather than overwriting history. `verify` distinguishes missing
locator/worktree, repository or checkout mismatch, missing recorded head,
branch or detached-HEAD movement, private changed-path inventory drift, and
worktree-fingerprint drift. Verification reports only inventory counts, never
the private path values.

Close the lifecycle only with a typed outcome and compact public-safe evidence:

```bash
loopx change-window resolve \
  --change-id change_example123 \
  --resolution merged \
  --evidence 'github:owner/repo#123' \
  --execute \
  --format json
```

The terminal outcomes are `merged`, `superseded`, and `abandoned`.
`superseded` also requires `--superseded-by`. Exact retries are idempotent;
conflicting terminal evidence fails closed. Resolution retains the public-safe
event history and removes the no-longer-needed machine-private worktree locator.

## Uninstall and rollback

Preview first, then remove the managed provider:

```bash
loopx change-window uninstall --repo-path . --format json
loopx change-window uninstall --repo-path . --execute --format json
```

Uninstall restores the exact repository-local `core.hooksPath` and
`core.sshCommand` values that preceded installation, or removes either local
override when none existed. It refuses to overwrite drifted provider state.
Pending-change history is not deleted by uninstall; resolve it through the
ledger lifecycle instead.

## Authority and enforcement boundary

This is local workflow enforcement, not branch protection. `hook_only` can be
bypassed with `--no-verify`; `reference_guard` closes that commit path and the
repository's SSH transport path. HTTPS pushes that both skip `pre-push` and
avoid SSH, replacing `core.hooksPath` or `core.sshCommand`, using an alternate
Git configuration or binary, staging fabricated remote-tracking refs, directly
editing ref files, writing from another
machine, or calling a hosting API remain outside its authority. Use OS policy
plus remote branch protection or server-side controls for a security boundary.
The capability does not push, merge, create a PR, modify protected branches,
or treat schedule admission as permission for any of those effects.
