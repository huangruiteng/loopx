# Operator Model Credential

Status: shipped. Applies to the steward channel and to the managed Turn host.

LoopX runs two model surfaces on an operator-supplied credential: the steward
channel a person talks to, and the managed Turn host the steward drives. Both
authenticate with a provider API key and, when the endpoint is not the provider
default, a base URL.

This document is the contract for where that pair lives, what may read it, and
which layer wins when more than one layer sets a field.

## Where It Lives

The credential is its own file, not a machine-configuration namespace:

```text
<runtime-root>/machine/credentials/operator_provider.json
```

The directory is mode `0700` and the file is mode `0600`, written atomically.
It is deliberately **not** part of `machine/configuration.json`: that document
is projected to the browser, read back by `loopx machine-config describe` and
`inspect`, and copied into per-transaction backups and rollback plans, so a
secret stored there would be readable from four surfaces and copied by every
unrelated settings change.

```json
{
  "schema_version": "operator_provider_credential_v0",
  "provider_key": "<provider key>",
  "base_url": "https://endpoint.example/v1"
}
```

## What May Read It

The key is **write-only**. No readback returns its value:

| Surface | Reads |
| --- | --- |
| `GET /api/chat/operator-credential` | status, each field's source, the key's truncated `sha256` fingerprint |
| `loopx machine-config credential status` | the same projection |
| the machine-configuration document | nothing -- the key is never stored there |
| the host process | `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` in its own environment |

The fingerprint exists so an operator can answer "is the key I just stored the
one that is running?" without any surface being able to read the key back.

## Resolution Order

Resolution is field by field, and the machine store outranks the process
environment:

1. **machine store** -- the operator's explicit choice, made in a product
   surface and read back with its own source;
2. **service environment** -- `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL`, the
   bootstrap for a machine whose store is not written yet and the escape hatch
   for a launch file that must override one field.

A store that holds only a base URL does not hide an environment-provided key:
each field resolves on its own.

This order matches the `steward_executor` machine setting, where the machine
value also outranks the service environment, so the two machine-level settings
a person edits do not follow two different precedence rules.

A credential **authenticates** the configuration that runs; it never
**selects** one. Storing a key here does not move the steward off its resolved
endpoint or the managed host off its resolved execution profile. It does
resolve the shipped default of a surface that would otherwise have to run on an
individual CLI login, which is why a stored key makes `dsh` the default managed
host.

## Failure Behaviour

A record this machine cannot read resolves to **no credential**, not to the
environment. Authenticating a surface with a credential the operator can no
longer see in the product surface that owns it is worse than refusing, so the
managed surfaces report `invalid` with the repair step instead, and the steward
stays on the individual executor.

An update is a **merge**: submitting only a key keeps the stored base URL.
Clearing is explicit (`clear_provider_key` / `clear_base_url`, or
`loopx machine-config credential clear`), so an empty form field can never
delete a credential the operator did not mean to touch. Clearing the last field
removes the file rather than leaving an empty record that would read as
"configured".

## Operating It

```bash
# The value stays out of shell history and argv.
printf '%s' '{"provider_key":"...","base_url":"https://endpoint.example/v1"}' \
  | loopx machine-config credential set --config-json -

loopx machine-config credential status
loopx machine-config credential clear
```

The Dashboard's machine capability settings expose the same read and write
through `/api/chat/operator-credential`.

## Authority Boundary

Storing a credential grants no authority. It does not select an executor, a
model, or a reasoning effort; it does not widen a Turn's tool scope, sandbox, or
declared evidence sources; and it does not let a managed surface run when the
selected runtime is missing. Those remain separate, typed decisions.
