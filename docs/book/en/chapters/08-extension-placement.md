# Choose the right extension point

“Extend LoopX” does not automatically mean “create an Extension.” Decide the caller outcome, product
contract, and lifecycle first. The implementation may belong in a Capability, Provider, Extension, or a
project-internal helper.

## What you should learn

After this chapter, you should be able to:

- separate the Capability and Extension dimensions;
- write a placement rationale before creating directories;
- recognize internal helpers that do not need product registration;
- identify a good standalone Extension.

## Capability and Extension are different dimensions

A **Capability** defines the outcome a caller can request and the contract that outcome must satisfy.

An **Extension** defines how an implementation is packaged and managed: install, enable, disable, upgrade,
rollback, and compatibility.

```text
Capability: caller-facing outcome contract
      ^
      | implemented by
Provider
      ^
      | delivered by
Extension: package and lifecycle
```

An Extension can implement an existing Capability, introduce a new Capability, or expose only its own
bounded standalone command. A Capability can also use a built-in Provider shipped by LoopX core.

## Case: the Finance value-discovery Extension

The current `loopx-finance-value-discovery` package is a useful naming trap. It processes Finance research
packets, but its manifest declares neither `[[provides]]` nor `[[implements]]`, and it does not register
`finance-value-discovery` in the Capability catalog.

The official placement guide treats a shared provider-neutral outcome across several Finance data or
research Providers as a reasonable future `finance-value-discovery` Capability. That direction is not a
claim that the current catalog already exposes it. The analysis below follows the current manifest,
catalog readback, and managed runtime.

Its placement rationale is:

```text
capability_id: none
provider_id: loopx-finance-value-discovery
origin: extension
placement: separately activated package
reason: deterministic reducer over caller-supplied frozen public-safe evidence;
        independent package and lifecycle; no provider-neutral caller contract yet
```

It is not currently a Capability because:

- the public call contract belongs to the Extension protocol `finance_value_discovery_extension_v0`;
- input is a frozen `finance_value_discovery_input_v0` supplied by the caller, not a broad request such as
  “find an investment”;
- the Provider emits one bounded research packet;
- no set of interchangeable Providers shares a caller outcome, resolver, and domain policy;
- the current Capability catalog makes no `finance-value-discovery` promise.

It fits the Extension dimension because:

- package, version, doctor, enablement, and upgrade have an independent lifecycle;
- manifest and runtime permissions are empty;
- the reducer does not fetch market data, read accounts or portfolios, submit trades, or start continuous
  monitoring;
- the same frozen public-safe evidence produces a deterministic result;
- generic `extension run` crosses no external-effect authority boundary.

The current boundary is:

```text
public evidence collector or human review
  -> frozen finance_value_discovery_input_v0
  -> loopx-finance-value-discovery Extension
  -> bounded finance_value_discovery_packet_v0
  -> human / Goal decides whether a successor is justified
```

Package installation, Extension activation, and invocation prove different facts:

```bash
# Put the Provider entrypoint in the current Python environment
python3 -m pip install ./packages/loopx-finance-value-discovery

# Record and activate a doctor-validated manifest revision
loopx extension install \
  --manifest packages/loopx-finance-value-discovery/extension.toml \
  --execute \
  --format json

# Reduce one frozen public-evidence input through managed runtime
loopx extension run loopx-finance-value-discovery \
  --input-json packages/loopx-finance-value-discovery/examples/paypal-debeta-discovery.json \
  --execute \
  --format json
```

These commands require the provider source package. The Extension is not bundled, and LoopX does not
download the package for the user. `extension list` proves activation state, an executed doctor proves
readiness for the current revision, and the example run proves the request/response contract. None
substitutes for another.

Install the package into the same Python environment that runs `loopx`, with
`loopx-finance-value-discovery` visible on the current `PATH`. Calling the absolute path of `loopx` inside
a virtual environment without making that environment's Provider entrypoint resolvable causes doctor to
return `entrypoint_missing`. That is the correct fail-closed result.

### When it should become a Capability plus Provider

If LoopX later needs a stable provider-neutral result across several Finance data or research Providers,
define the Capability contract first: common input, evidence freshness, authority, failure, readback, and
successor policy. This package could then declare `[[implements]]` and become one Extension Provider.

Do not register a speculative Capability merely because the package name contains “value discovery.”
Collection must not leak into this zero-permission reducer either. Public-market, filing, and news
collection needs its own Provider boundary plus freshness, licensing, and credential Gates.

## Four candidate locations

### 1. Project-internal helper

If code serves only the current project and has no independent caller contract, installation need, or
lifecycle, keep it in the nearest owning module.

Turning a shared dict conversion into a Capability or Extension would add manifest, doctor, and upgrade
cost without creating an independently useful product contract.

### 2. Provider for an existing Capability

If an existing Capability already defines the caller outcome, implement that contract rather than creating
a synonym.

The Provider can be built in or delivered by an Extension. Accessing an external API is not sufficient
reason to invent a new Capability; a core-owned connector may still be a built-in Provider.

### 3. New Capability

Create a Capability only when LoopX callers need a stable provider-neutral outcome, catalog identity, and
routing surface.

At minimum, it needs:

- a clear caller outcome;
- stable id and versioned protocol;
- a real entrypoint or call site;
- domain validation and transition policy;
- focused validation;
- catalog registration.

“We may have multiple Providers later” is not enough to ship a speculative abstraction.

### 4. Standalone Extension

A standalone Extension is a good starting point when the ability:

- has its own package and version;
- needs independent install, activation, upgrade, or rollback;
- exposes one bounded request/response command;
- does not belong to an existing Capability;
- requires no permissions for direct invocation.

The `loopx-text-stats` example in the next chapter fits this shape. It computes statistics from text in the
request. It does not read files, use the network, modify external systems, or define a cross-Provider
product contract.

## Make the placement decision in order

Before creating a module, answer:

1. **What outcome does the user need?** Name the result, not a mechanism such as connector, adapter, or sink.
2. **Can the nearest existing owner provide it?** Extend an existing Capability when it owns the same outcome.
3. **Must LoopX core always ship this implementation?** If yes, consider built-in; otherwise consider an Extension.
4. **Does it need an independent lifecycle?** Independent dependencies, versions, credentials, or provider ownership point toward an Extension.
5. **Is it only an internal helper?** No independent caller contract means it should remain local.
6. **Does it perform an effect?** A generic standalone runner must not bypass Capability or domain authority.

## Record the minimum rationale

For that example:

```text
capability_id: none
provider_id: loopx-text-stats
origin: extension
placement: standalone package
reason: bounded deterministic command with an independent lifecycle;
        no provider-neutral LoopX capability is needed
```

For an Extension implementing an existing Capability:

```text
capability_id: <existing-capability>
provider_id: <extension-id>
origin: extension
placement: independently packaged provider
reason: reuses the caller contract but needs independent dependencies
        and activation lifecycle
```

This rationale can live in a Todo, PR description, or commit history. Its job is to expose a misplaced
abstraction before implementation.

## Common placement mistakes

### “It calls an external API, so create a connector Capability”

Transport is not the caller outcome. Find who needs the result and whether an existing Capability already
owns it.

### “Declare `[[provides]]` now and add the caller later”

A discoverable but uncallable manifest creates a false product surface. Establish the real caller contract,
resolver, policy, and validation first.

### “The standalone runner starts a process, so it can send messages”

The generic runner requires both manifest and runtime permissions to be empty. Sending, writing, publishing,
or managing resources is an effect and must go through a Capability or domain command.

### “Several files share code, so make an Extension”

Shared code may justify a helper. It does not prove a need for independent installation and lifecycle.

## Placement used by this book

| Field | Decision |
| --- | --- |
| `capability_id` | `none` |
| `provider_id` | `loopx-text-stats` |
| origin | `extension` |
| kind | standalone |
| permissions | `[]` |
| managed entrypoint | `loopx extension run` |

If you are designing more than a standalone package—such as Explore, Domain State, a Capability Pack,
multi-agent preset, Provider, or presentation composition—continue to
[Control-Plane Course Lesson 9](/loopx/docs/development/control-plane-course/09-extension-layer/). It
explains how these extension surfaces reuse the Kernel instead of creating a second Goal, Todo, quota, or
scheduler.

The next chapter creates this structure from the official scaffold and changes only the domain contract.
