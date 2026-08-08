# Extension lifecycle and managed runtime

Installing a package and activating it in LoopX are separate stages. LoopX does not download arbitrary
packages or execute a caller-selected binary. It manages a doctor-validated Provider revision.

## What you should learn

After this chapter, you should be able to:

- distinguish Python package installation from LoopX Extension installation;
- run install, doctor, invoke, disable, enable, upgrade, and rollback;
- explain preview versus `--execute`;
- recognize when the generic standalone runner must reject a request.

## 1. Install the Python package

From the workspace that contains `standalone-extension/`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e './standalone-extension[test]'
```

This puts the `loopx-text-stats` console entrypoint in the active environment. It does not change LoopX
activation state.

Inspect the Provider directly during development:

```bash
loopx-text-stats --doctor
loopx-text-stats < standalone-extension/examples/request.json
```

Direct execution is a development aid. The supported user path is `loopx extension`.

## 2. Preview and install

Preview:

```bash
loopx extension install \
  --manifest standalone-extension/extension.toml \
  --format json
```

Execute:

```bash
loopx extension install \
  --manifest standalone-extension/extension.toml \
  --execute \
  --format json
```

Install:

1. reads the declarative manifest;
2. checks API compatibility and permissions;
3. resolves the installed entrypoint;
4. runs the read-only doctor;
5. records a validated manifest snapshot and revision;
6. activates that revision.

It does not download a package, execute an arbitrary caller binary, grant new permissions, store Provider
output in activation state, or read project Goal state.

## 3. Inspect readiness

```bash
loopx extension list --format json
loopx extension doctor loopx-text-stats --execute --format json
```

`doctor --execute` runs the actual probe. Readiness binds the active manifest revision and resolved runtime
identity. If the executable or environment changes, an old doctor proof is stale.

A failed doctor clears stale readiness but does not switch revisions automatically.

## 4. Invoke through the managed runtime

Preview:

```bash
loopx extension run loopx-text-stats \
  --input-json standalone-extension/examples/request.json \
  --format json
```

Execute:

```bash
loopx extension run loopx-text-stats \
  --input-json standalone-extension/examples/request.json \
  --execute \
  --format json
```

The managed runtime fixes:

- Extension id and active revision;
- entrypoint and arguments;
- stdin/stdout JSON protocol;
- timeout;
- permissions;
- request size limit;
- stdout and stderr limits.

The caller cannot add shell arguments or replace the executable. Timeout and output overflow terminate the
Provider process group so child processes do not survive after LoopX reports a stop.

`run` supports only an Extension that is enabled, doctor-ready, has a runtime, declares no
`[[provides]]` or `[[implements]]`, has empty permission lists, accepts the bounded request, and receives an
explicit `--execute`. Every other case should fail closed.

## 5. Disable and enable

```bash
loopx extension disable loopx-text-stats --execute --format json
```

A disabled Extension remains visible in lifecycle state but is not a dispatch candidate. `extension run`
must fail.

Enable it again:

```bash
loopx extension enable loopx-text-stats --execute --format json
```

Enable does not trust old readiness. It reruns doctor before setting the enabled state.

## 6. Upgrade and rollback

Before upgrade, update the package and manifest version, then install the new package into the same
environment.

Preview:

```bash
loopx extension upgrade \
  --manifest standalone-extension/extension.toml \
  --format json
```

Execute:

```bash
loopx extension upgrade \
  --manifest standalone-extension/extension.toml \
  --execute \
  --format json
```

Upgrade validates and probes the new manifest before changing the active revision. A failed probe leaves the
current revision active.

Rollback:

```bash
loopx extension rollback loopx-text-stats --execute --format json
```

Rollback probes the previous validated revision before switching. It is a lifecycle transition over
activation state, not an arbitrary Git checkout.

## 7. Isolate example state

CI and tutorials can use `--state-file` to avoid modifying the user's default runtime state:

```bash
state_file="$(mktemp)"
rm -f "$state_file"

loopx extension install \
  --state-file "$state_file" \
  --manifest standalone-extension/extension.toml \
  --execute \
  --format json
```

The temporary file may contain local runtime identity and must not be committed to any public repository.

## When standalone `run` is not valid

Use a Capability or domain command for:

- file reads or writes;
- authenticated API access;
- sending messages;
- publishing content;
- managing external resources;
- modifying project state;
- any effect that needs action or scope authority.

An effectful dispatch creates a request-bound execution envelope after domain policy checks. The envelope
binds exact action, structured effect scope, Extension id and revision, and Provider request digest.

It is not a service credential. A caller-created envelope, widened scope, changed request, or revision
mismatch must fail closed.

## Troubleshooting

| Symptom | Inspect first |
| --- | --- |
| `entrypoint_missing` | Whether the package is installed in the environment that runs `loopx` |
| Install preview succeeds but list is unchanged | Whether `--execute` was omitted |
| Doctor is stale | Whether the executable, interpreter, or module source changed |
| Run reports disabled | Run `enable --execute` and inspect doctor |
| Run rejects permissions | Whether the Provider belongs behind a Capability/domain command |
| Upgrade does not switch | Whether doctor failed for the new revision |
| Rollback is unavailable | Whether a validated previous revision exists |

Fix the contract or environment. Do not bypass managed runtime and pretend the Provider is activated.
