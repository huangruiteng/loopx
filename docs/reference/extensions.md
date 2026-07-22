# Extensions And Capabilities

Capabilities and extensions are independent dimensions in LoopX:

- a **capability** describes what LoopX can do and the product contract exposed
  to callers;
- an **extension** is a delivery unit that can provide one or more capabilities
  and has its own installation, enablement, disablement, and upgrade lifecycle.

Built-in capabilities and extension-provided capabilities share one registry.
Implementation directories do not become capabilities merely because they live
under `loopx/capabilities/`; registration is explicit.

```text
LoopX Core
|-- capability contracts
|-- built-in capability registrations
`-- extension runtime
      |-- extension A -- provides a new capability
      |-- extension B -- implements a core capability
      `-- extension C -- remains disabled
```

## Registration Model

Every registered capability declares three provider-facing fields:

- `origin`: `builtin` or `extension`;
- `visibility`: `public` or `internal`;
- `provider_id`: `loopx-core` or the extension manifest id.

The built-in catalog remains the default source. Extension manifests declare
providers and contracts; the extension runtime state is the only source for
whether each provider is installed, enabled, and doctor-ready. Duplicate
capability or provider ids fail closed. Internal registrations remain available
to the registry but are omitted from the public catalog.

Catalog discovery does not scan arbitrary directories or import extension
Python code. A caller can add a declaration-only manifest to a catalog read:

```bash
loopx capability list \
  --extension-manifest /path/to/extension.toml \
  --format json

loopx capability show lark-kanban \
  --extension-manifest /path/to/extension.toml \
  --format json
```

The resulting provider reports `declared=true` and
`installed=enabled=ready=false`. The normal CLI read also composes installed
providers from `<runtime-root>/extensions/state.json`, so the catalog and
runtime dispatch see the same active manifest revision. `loopx extension`
registers an already-installed subprocess entrypoint only after the manifest,
API, permission, and doctor checks pass. It does not download packages or grant
new permissions.

## Starter And Scaffold

Create the next standalone extension through the same management surface. The
command previews by default and writes only with `--execute`:

```bash
loopx extension init loopx-example --format json
loopx extension init loopx-example --execute --format json
```

The default destination is `extensions/<extension-id>`. Use `--destination`
when the provider is developed in another package or repository. The scaffold
creates an independently installable Python package, declarative manifest,
JSON stdin/stdout provider, versioned request and response JSON Schemas,
side-effect-free doctor, example request, and a short README. The generated
provider rejects missing, mismatched, or structurally invalid request contracts
before doing work. The init receipt explicitly identifies the starter as
`standalone` and names `loopx extension run` as its managed entrypoint.

`extension init` intentionally does not register a capability. It currently
generates only the complete standalone path. A `[[provides]]` extension needs a
real caller contract and command, while an `[[implements]]` extension needs an
existing capability-specific resolver, policy check, action/scope mapping, and
execution-envelope adapter. A generic scaffold cannot infer those authority
semantics safely. Add a capability integration profile first, then scaffold or
author the provider against that profile; do not add manifest tables that are
discoverable but not callable.

The command refuses every existing destination, including an empty directory;
there is no force or merge mode. It also does not build, install, register, or
enable the generated provider. Those remain explicit lifecycle steps so the
package manager and LoopX activation state cannot drift behind one command:

Run all three commands from the same activated Python environment. LoopX
verifies the provider through its installed console entrypoint, so installing
the package into a different environment correctly fails with
`entrypoint_missing`.

```bash
python3 -m pip install extensions/loopx-example
loopx extension install \
  --manifest extensions/loopx-example/extension.toml \
  --execute \
  --format json
loopx extension run loopx-example \
  --input-json extensions/loopx-example/examples/request.json \
  --execute \
  --format json
```

Treat the generated response as executable documentation, not a permanent
domain contract. Before productizing the provider, replace the starter request,
response, permission, and doctor semantics with bounded domain-specific ones.

## Runtime Lifecycle

The lifecycle is local, explicit, and dry-run by default:

```bash
# Inspect the bundled OpenViking pilot, then activate it only if doctor passes.
loopx extension install \
  --bundled openviking-semantic-preference \
  --execute \
  --format json

loopx extension list --format json
loopx extension doctor openviking-semantic-preference --execute --format json
loopx extension disable openviking-semantic-preference --execute --format json
loopx extension enable openviking-semantic-preference --execute --format json

# Activate the bundled Lark lifecycle provider before using lark-inbox.
loopx extension install --bundled loopx-lark --execute --format json
```

For a separately distributed provider, pass `--manifest <extension.toml>`.
`upgrade` validates and probes the new manifest before changing the active
revision. `rollback` probes the previous revision before switching back. A
failed probe leaves the current revision untouched. Activation state contains
validated manifest snapshots and revision ids in the private LoopX runtime
root; it does not contain provider output or credentials.

Standalone extensions use the same managed command shape as built-in
capabilities: LoopX accepts a bounded request, previews by default, executes
only with `--execute`, and returns a structured receipt. The v0 invocation
contract is:

```bash
loopx extension run <extension-id> --input-json <path-or-> [--execute]
```

The active manifest fixes the executable, arguments, protocol, permissions,
timeout, and revision. The caller supplies one JSON object over stdin and the
provider must return one JSON object over stdout. LoopX does not accept an
arbitrary executable path or argument passthrough. `run` never installs a
missing extension, and it rejects extensions with `[[provides]]`,
`[[implements]]`, or any declared permission; those providers are invoked
through their capability or domain command. Extension lifecycle management is
shared, but direct execution is reserved for zero-permission, runtime-only
standalone extensions.
Direct provider binaries are implementation and debugging surfaces; they are
not the supported management API.

The generic runner is deliberately non-effectful and grants no operation
effects. Both manifest `permissions` and runtime `required_permissions` must
be empty. Any operation needing read, write, send, publish, manage, or another
declared authority must enter through a capability or domain command that can
apply its domain policy before managed dispatch. Request files and stdin are capped while
being read. Provider stdout and stderr are drained concurrently and the provider
is started in a dedicated process group. Timeout or either output limit
terminates the entire group, so a descendant cannot continue effects after
LoopX reports that execution stopped.

Effectful capability dispatch uses
`loopx_extension_execution_envelope_v0`. The capability command, not the caller
or provider, creates this minimal envelope after resolving one enabled,
doctor-ready implementation and checking the domain activation policy. It binds:

- the exact action;
- structured effect scope;
- extension id and active manifest revision;
- a digest of the exact provider request, excluding the attached envelope.

The provider repeats this validation before any effect. A caller-supplied
envelope, different request, wider scope, changed action, or mismatched active
revision fails closed. Capability id, protocol, and permission remain
authoritative in manifest resolution instead of being duplicated in the
envelope. The envelope is request binding, not proof of issuer identity, a
security token, or a replacement for service-side authentication and
authorization.

`disable` is reversible, but `enable` never trusts an earlier readiness result:
it reruns the configured doctor and changes the enabled bit only after that
probe succeeds. A successful doctor binds readiness to both the active manifest
revision and the resolved runtime identity. Missing or replaced executables,
interpreters, or Python module sources fail closed until a new executed doctor
succeeds; a failed executed doctor clears the stale proof without switching
revisions.

An enabled implementation is resolved by capability id and versioned protocol,
then checked against its declared permission, current revision, and current
doctor proof. Callers do not need to copy an extension id into normal config.
Disabled or stale implementations remain visible in the catalog but are not
dispatch candidates. When multiple enabled, doctor-ready extensions implement
the same capability/protocol pair, resolution fails closed until the caller
selects the intended provider during migration. Domain config may add bounded
provider arguments, but cannot replace the manifest entrypoint, timeout,
protocol, or permission contract.

Compatibility delegates use the same revision-bound readiness rule. Every
configured `loopx lark-inbox` operation resolves the enabled `loopx-lark`
provider, its current doctor proof, and the permission needed by that operation
before entering the in-process provider code. Disabling the extension therefore
blocks new collector starts, drain, ingest, reply, and acknowledge operations;
upgrade and rollback affect new invocations without changing project
configuration. Extension lifecycle commands do not terminate an already
running host-managed collector process; stop or restart that supervisor service
separately when changing the active provider revision.

Quota and Turn composition apply the same read gate. They inject the Lark
extension's urgency projector only after resolving `lark.inbox.read`; provider
profile/chat schema and private config reads stay in the extension. If the
extension is missing, disabled, or stale, urgency is unavailable and cannot
activate a Lark work lane. This adds no agent-facing CLI arguments.

## Placement Decision For Agents

Before creating a directory, LoopX or an executing agent must answer these
questions in order:

1. **What user outcome and caller-visible contract is being added or changed?**
   Capability ids describe outcomes, not transports. Names such as
   `connector`, `provider`, `adapter`, or `sink` usually describe an extension
   or internal mechanism unless callers use and validate that mechanism as an
   independent product contract. If an existing
   capability already owns that contract, add the implementation to
   `loopx/capabilities/<existing-capability>/` instead of creating a sibling.
2. **Must LoopX core always ship and maintain the implementation?** If yes, it
   may be a built-in capability. A new built-in needs a stable id, a real
   entrypoint or protocol call site, focused validation, and catalog
   registration.
3. **Does the implementation need independent installation, enablement,
   disablement, upgrade, dependencies, credentials, or provider ownership?**
   If yes, it is an extension provider. The capability remains the contract;
   the extension manifest declares that it provides the contract.
4. **Is this only registration or lifecycle machinery shared by all
   extensions?** Put that mechanism in `loopx/extensions/`, not in a provider
   package.
5. **Is this only an internal helper?** Put it in the nearest module that owns
   its change reason. Do not register a capability or create an extension.

Use this placement map after answering the questions:

| Change | Placement |
| --- | --- |
| Existing built-in capability behavior | `loopx/capabilities/<capability-id>/` |
| Built-in catalog and registration contract | `loopx/capabilities/catalog.py` or `registry.py` |
| Generic extension runtime | `loopx/extensions/` |
| Co-located optional extension/provider | `extensions/<extension-id>/` |
| Separately distributed extension/provider | owner package or repository |
| Internal implementation helper | nearest owning module |

Some work belongs on both axes, but an optional workflow does not need a
capability merely because it is user-visible. Create a capability only when
LoopX callers need a provider-neutral contract, catalog identity, and routing
surface. An extension-owned command and packet contract may remain a
standalone extension runtime. Finance value discovery uses this standalone
shape; public-market, filing, and news collection can stay inside that
extension until a real cross-provider LoopX contract exists.

`value-connectors` is an existing compatibility CLI and protocol surface. Do
not use it as the public capability owner for new work. Migrate each profile
to an existing outcome capability such as `issue-fix` or `content-ops`, or to
a standalone extension such as `loopx-finance-value-discovery`, before
retiring the compatibility surface. This keeps the migration
behavior-preserving instead of replacing one broad bucket with another broad
bucket.

Before editing, record a compact rationale in the active todo or plan:

```text
capability_id: <existing-or-new-contract>
provider_id: loopx-core | <extension-id>
origin: builtin | extension
placement: <target-directory-or-package>
reason: <why the nearest existing owner is or is not sufficient>
```

Use `capability_id: none` for a standalone extension. Do not create a new
capability directory merely because no current directory has the feature name
or because the manifest needs a lifecycle anchor. Do not create an extension
merely because an external service is involved: a built-in connector can still
belong to an existing capability when it shares the core release and
lifecycle.

## Manifest Contract

An extension manifest is declarative TOML. An executable `[runtime]` is enough
for a standalone extension. `[[provides]]` records add new capability contracts
to the catalog. `[[implements]]` binds a provider runtime to an existing
core-owned capability without duplicating that capability id. Do not add either
table solely to make a runtime installable.
The v0 runtime exposes integer extension API version `1` and accepts bounded
integer constraints such as `>=1,<2`; incompatible manifests fail closed.

```toml
schema_version = "loopx_extension_manifest_v0"
id = "loopx-lark"
version = "1.0.0"
requires_loopx_api = ">=1,<2"
permissions = ["read_status", "read_todos", "external_write"]

[runtime]
protocol = "lark_kanban_provider_v0"
python_module = "loopx.extensions.lark.provider"
doctor_args = ["--doctor"]
required_permissions = ["read_status", "read_todos"]
timeout_seconds = 30

[[provides]]
id = "lark-kanban"
kind = "projection_sink"
title = "Lark Kanban projection"
status = "active"
visibility = "public"
real_world_anchor = "operator-facing Lark Base projection"
user_value = "Project public-safe LoopX status and todo rows into Lark."
entry_command = "loopx lark-kanban sync"
next_real_step = "Validate one explicitly enabled owner-approved sink."
```

The bundled OpenViking pilot uses `[[implements]]` instead:

```toml
[runtime]
protocol = "semantic_preference_provider_v0"
entrypoint = "loopx-openviking-semantic-preference"
doctor_args = ["--doctor"]
required_permissions = ["semantic_preference.read"]

[[implements]]
capability_id = "semantic-preference"
protocol = "semantic_preference_provider_v0"
```

The bundled periodic-report archive uses the same ownership direction. It
implements one existing capability port rather than registering a second
"OpenViking report" product capability:

```toml
[runtime]
protocol = "periodic_report_sink_v0"
python_module = "loopx.extensions.openviking_periodic_report.provider"
required_permissions = ["openviking_context_write"]

[[implements]]
capability_id = "periodic-report"
protocol = "periodic_report_sink_v0"
```

Its capability-specific activation wrapper additionally requires an enabled
`periodic_report_activation_v0`, a matching non-disabled sink binding, and the
observed `openviking_context_write` runtime capability. Those project and turn
facts do not belong in the generic extension manifest or lifecycle state.

### Finance value-discovery sample

`extensions/loopx-finance-value-discovery/` is a co-located, independently
packaged standalone workflow. Its manifest registers only the
`finance_value_discovery_extension_v0` runtime; it does not create a capability
catalog entry or a `value-connectors` route. After an explicit install and
successful doctor probe, invoke it through the managed extension command:

```bash
loopx extension install \
  --manifest extensions/loopx-finance-value-discovery/extension.toml \
  --execute
loopx extension run loopx-finance-value-discovery \
  --input-json extensions/loopx-finance-value-discovery/examples/paypal-debeta-discovery.json \
  --execute \
  --format json
```

The included PayPal packet preserves a reusable de-beta research method, not
an investment conclusion: start from a frozen cross-sectional screen, retain
same-group controls, separate structural growth from profit-pool capture,
require dilution and terminal-risk evidence, then falsify the candidate before
selecting at most one successor. The reducer performs no live reads, gives no
price target or advice, and cannot trade or start a continuous watch.

For upgrade compatibility, the retired
`value-connectors` Finance selectors, including the legacy
`plan --connector-id finance_market_snapshot` form, remain as migration
tombstones. They return `value_connector_extension_migration_v0` with ordered
extension startup prerequisites; they do not execute Finance or restore a
Finance capability. Source checkouts can install the co-located provider package
before registration. Packaged LoopX users still need a separately distributed
provider artifact, so agents must stop rather than claiming automatic
installation when that artifact is unavailable.

Runtime-required permissions must be a subset of the provider's declared
permissions. Declaring either does not grant authority: existing LoopX goal
boundaries, user gates, and external-write authorization still decide whether
an operation may execute. Extension packages are trusted executable code rather
than an operating-system sandbox; the manifest records and constrains managed
routing, but cannot make an untrusted provider safe.

Every executable runtime declares exactly one launch target. Use `entrypoint`
for a separately installed executable such as the OpenViking provider. Use
`python_module` for a provider shipped in the LoopX Python package. Module
providers run as `<current-loopx-python> -m <module>` and their doctor proof is
bound to both that interpreter and the resolved module source. This lets a
clean source checkout and a local LoopX release activate bundled providers
without separately installing a console script; catalog discovery remains
declarative and does not import the module.

## Scope Boundaries

The executable v0 runtime intentionally does not:

- rename or move existing capability implementation directories;
- infer capabilities from Python packages;
- download, build, or install extension packages;
- start services, create credentials, or edit provider configuration;
- import an extension entrypoint during catalog discovery;
- let manifest permissions bypass LoopX control-plane authority.

These boundaries keep activation reversible and auditable while leaving package
distribution and service setup to explicit operator-owned workflows.

Provider migration follows the same direction. Core routing consumes compact
provider-neutral read models, while provider packages own collection, transport,
credentials, and external effects. For example, quota reads
`operator_inbox_urgency_v0` through an injected projector. The generic parser
and read-model contract stay in the control plane; Lark schema, identity,
destination, collection, reply transport, and provider-owned configuration live
under `loopx/extensions/lark/`. The existing
`loopx lark-inbox` command remains a direct compatibility delegate, but it now
requires an installed, enabled, doctor-verified `loopx-lark` revision with the
operation's declared permission. The provider subprocess currently implements
doctor only; command execution remains in-process until the transport protocol
is migrated.
The former `loopx.capabilities.lark` provider imports are intentionally removed
instead of kept as wrappers. Lark Kanban and Explore presentation sinks live
under `loopx.extensions.lark.presentation`; their compatibility CLI delegates
require the installed, enabled, doctor-verified revision to declare
`lark.projection_sink.use`. No additional agent-facing CLI arguments are
required.
