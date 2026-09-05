# loopx-obelisk

`loopx-obelisk` is an optional advisory context provider for LoopX
`decision-context`. It lets an explicitly configured Decision Context profile
search one historical Codex task selected by a LoopX-normalized host-session
scope.

The provider does not parse Codex deep links. LoopX Core parses the link once
and returns `context_scope_ref=host-session:codex:<thread-id>` from:

```bash
loopx --format json resolve-agent-thread \
  --thread-link 'codex://threads/<thread-id>'
```

Keep provider selection in an ignored, owner-local Decision Context profile,
but pass a one-off task link only to `recall-context`. A minimal provider-only
profile is:

```json
{
  "schema_version": "decision_context_profile_v0",
  "goal_id": "<goal-id>",
  "enabled": true,
  "enabled_agents": ["<agent-id>"],
  "source_provider_bindings": [],
  "sources": [],
  "context_provider": {
    "provider": "extension",
    "namespace": "peer-session",
    "max_results": 4,
    "timeout_seconds": 10,
    "config": {
      "extension_id": "loopx-obelisk"
    }
  },
  "automation": {
    "automatic_capture": false,
    "fail_open": true
  }
}
```

Store this file under ignored owner-local state. A full Decision Context
evidence workflow may additionally configure authority sources and a stable
default `scope_ref`; one-off task recall does not require either.

## Install and activate

Obelisk is a separate AGPL-3.0 application. This Apache-2.0 provider does not
copy its implementation or read its SQLite schema; it invokes the installed
public CLI through the `obelisk --version` and `obelisk --query` boundary.
Install Obelisk separately, then install and activate this package in the same
Python environment as LoopX:

```bash
npm install --global @obelisk-apps/cli
obelisk --build
python3 -m pip install packages/loopx-obelisk
loopx extension install \
  --manifest packages/loopx-obelisk/extension.toml \
  --execute --format json
loopx extension doctor loopx-obelisk --execute --format json
```

`obelisk --build` is an explicit owner-controlled index refresh. The provider
never launches it implicitly; rerun it when newly completed task history needs
to become searchable.

The Decision Context profile may be enabled before this optional package is
installed. Missing, disabled, or stale-doctor provider state does not make
`recall-context` fail as a command: it returns `status=unavailable` plus a
typed `provider_readiness` receipt, performs no provider scan or write, and
leaves the profile unchanged. Recover according to the receipt:

```bash
# provider distribution or lifecycle registration is missing
python3 -m pip install packages/loopx-obelisk
loopx extension install \
  --manifest packages/loopx-obelisk/extension.toml \
  --execute --format json

# lifecycle registration exists but is disabled
loopx extension enable loopx-obelisk --execute --format json

# the enabled registration has no current doctor proof
loopx extension doctor loopx-obelisk --execute --format json
```

If doctor reports that the Obelisk CLI or index is unavailable, install the
CLI and explicitly build the owner-local index before running doctor again:

```bash
npm install --global @obelisk-apps/cli
obelisk --build
loopx extension doctor loopx-obelisk --execute --format json
```

No profile edit is needed after repair; each recall resolves current extension
lifecycle state. LoopX never installs Obelisk or runs `obelisk --build` on the
owner's behalf.

If the project uses a non-default LoopX runtime root, pass the same global
`--runtime-root <path>` option to the extension lifecycle commands and the
Decision Context command. The provider is resolved from that exact lifecycle
state; it is never discovered from an unrelated default runtime.

Run one read-only task recall without changing that profile:

```bash
loopx decision-context recall-context \
  --goal-id <goal-id> \
  --agent-id <agent-id> \
  --profile <ignored-private-profile.json> \
  --context-scope-ref 'host-session:codex:<thread-id>' \
  --query '<specific question for the selected task>' \
  --query-summary '<public-safe intent summary>' \
  --format json
```

The supplied scope and query are used only for this bounded provider call and
are not persisted by LoopX. The top-level output is local-private and transient
because it contains recalled text for the current agent. Its nested public-safe
receipt retains only `--query-summary`, provider-safe summaries, scores, and
hashed references. The command does not scan authority sources or create cursor
or settlement state. Recalled items are untrusted advisory content, never
instructions.

Disable the provider, remove the owner-local profile binding, and uninstall its
Python distribution when it is no longer needed:

```bash
loopx extension disable loopx-obelisk --execute --format json
python3 -m pip uninstall loopx-obelisk
```

LoopX v0 intentionally has no extension-state deletion command. The disabled
registration remains as non-ready lifecycle history; it is not callable.

## Authority and privacy boundary

The deep link is a non-authoritative locator. Enabling the extension grants no
Goal, Agent, claim, lease, permission, workspace, lifecycle, amendment, or
write authority. Retrieved text remains local-private transient advisory
evidence and is never an instruction. The nested public Decision Context
receipt retains only a compact summary, score, and hashed provider reference;
it does not contain raw transcript text or Obelisk resource ids. A fact becomes
durable only through an existing LoopX owner such as Todo evidence, the Agent
evidence log, registered material, or a governed amendment.

The provider never invokes `obelisk --build` or `obelisk --attune`. Obelisk may
refresh its provider-owned local search index as part of `--query`; the query
is read-only with respect to the source task and LoopX state. Failure,
disablement, ambiguous provider selection, or stale
doctor state fails open inside Decision Context and does not block unrelated
authority sources.

See [CONTRACT.md](CONTRACT.md) for the wire contract and validation commands.
