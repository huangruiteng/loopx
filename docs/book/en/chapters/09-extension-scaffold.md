# Build a standalone Extension

This chapter creates `loopx-text-stats` from the official LoopX scaffold. The official scaffold supplies
the complete runnable baseline; this chapter provides the narrowed manifest, request and response
contracts, core function, and validation steps without a separate exercise repository.

## Observable success

At the end:

- the scaffold is an independent Python package;
- the manifest uses `loopx_extension_manifest_v0`;
- request and response each have a versioned JSON Schema;
- the Provider reads one JSON object from stdin and writes one JSON object to stdout;
- doctor has no side effect;
- invalid input fails closed before computation;
- both manifest and runtime declare zero permissions.

## 1. Generate the official scaffold

From a workspace where you want to build the example:

```bash
loopx extension init loopx-text-stats \
  --destination standalone-extension \
  --execute \
  --format json
```

`extension init` previews by default. `--execute` is required to write files, and the destination must not
already exist, even as an empty directory. The command does not build, install, register, or enable the
package.

The generated path is:

```text
standalone-extension/
├── extension.toml
├── pyproject.toml
├── README.md
├── examples/
│   └── request.json
├── schemas/
│   ├── request.schema.json
│   └── response.schema.json
└── src/
    └── loopx_text_stats/
        ├── __init__.py
        └── cli.py
```

This is a complete standalone path. It does not invent the Capability authority required for
`[[provides]]` or `[[implements]]`.

## 2. Read the manifest as a contract

After narrowing the generated scaffold to this example, the manifest is:

```toml
schema_version = "loopx_extension_manifest_v0"
id = "loopx-text-stats"
version = "0.1.0"
requires_loopx_api = ">=1,<2"
permissions = []

[runtime]
protocol = "loopx_text_stats_extension_v0"
entrypoint = "loopx-text-stats"
doctor_args = ["--doctor"]
required_permissions = []
timeout_seconds = 30
```

The important constraints are:

- `id` is the lifecycle identity;
- `version` participates in revision and upgrade;
- `requires_loopx_api` declares the compatibility window;
- `protocol` is the Provider wire contract;
- `entrypoint` must exist on `PATH` in the Python environment running LoopX;
- `doctor_args` names a read-only readiness probe;
- both permission lists are empty;
- the managed runtime fixes the timeout rather than accepting an arbitrary caller override.

## 3. Define a bounded request

The example request is:

```json
{
  "schema_version": "loopx_text_stats_request_v0",
  "text": "LoopX keeps project state explicit.\nExtensions keep delivery lifecycle explicit."
}
```

The request schema requires:

- an object payload;
- an exact `schema_version`;
- a `text` string containing a non-whitespace character;
- `additionalProperties: false`.

Rejecting unknown fields protects the permission boundary. If the caller sends:

```json
{
  "schema_version": "loopx_text_stats_request_v0",
  "text": "hello",
  "path": "/tmp/input.txt"
}
```

the Provider must reject it. It must not reinterpret `path` as file-read authority.

## 4. Implement pure computation

The example's core function is:

```python
def analyze_text(text: str) -> dict[str, int]:
    return {
        "characters": len(text),
        "non_whitespace_characters": sum(
            1 for character in text if not character.isspace()
        ),
        "words": len(re.findall(r"\S+", text)),
        "lines": len(text.splitlines()) or 1,
    }
```

It is a good first standalone Extension because it is deterministic, reads no environment or files, uses
no network, modifies no external system, and does not depend on LoopX project state.

The Provider validates structure before computation and returns errors through a versioned response:

```json
{
  "ok": false,
  "schema_version": "loopx_text_stats_response_v0",
  "extension_id": "loopx-text-stats",
  "error": "extension input has unsupported fields ['path']"
}
```

Do not expose tracebacks, environment variables, or local paths in public receipts.

## 5. Define the response contract

The stable domain response is:

```json
{
  "ok": true,
  "schema_version": "loopx_text_stats_response_v0",
  "extension_id": "loopx-text-stats",
  "request_schema_version": "loopx_text_stats_request_v0",
  "result": {
    "characters": 80,
    "non_whitespace_characters": 71,
    "words": 10,
    "lines": 2
  }
}
```

The response schema uses `oneOf` to separate success and failure. Tests should assert this domain contract,
not every field in the outer LoopX CLI receipt. That allows additive receipt changes in a minor release
without breaking a domain test.

## 6. Keep doctor free of effects

The starter doctor path is:

```python
if args.doctor:
    return 0
```

For this pure Provider, readiness means the entrypoint starts and parses arguments. Doctor must not:

- create files;
- access the network;
- write credentials;
- change Extension state;
- perform a business effect;
- emit unbounded logs.

A real Provider may perform bounded read-only dependency checks. Readiness still needs to be repeatable and
effect-free.

## 7. Install the package and run tests

Use one Python environment for the Provider and LoopX:

```bash
cd standalone-extension
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e '.[test]'
python3 -m pytest
```

LoopX validates the installed console entrypoint. If the package lives in another virtual environment,
`entrypoint_missing` is the correct result; LoopX must not search arbitrary source directories.

## Common mistakes

### Hand-writing a smaller scaffold

This often omits schema, doctor, compatibility, or the package entrypoint. Generate the complete official
path first, then make minimal domain changes.

### Accepting arbitrary keyword arguments

This destroys the bounded request and can expand authority accidentally. The JSON Schema and Provider
validation should both fail closed.

### Running business work in doctor

Doctor proves readiness. It does not authorize an effect. Business requests belong in the managed runtime
or an authorized Capability/domain command.

### Adding a permission for demonstration

`extension run` rejects a permissioned Extension. Design the real Capability and authority before building
an effectful Provider.
