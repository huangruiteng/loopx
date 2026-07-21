from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
import shlex
import shutil
from textwrap import dedent


EXTENSION_SCAFFOLD_SCHEMA_VERSION = "loopx_extension_scaffold_v0"
_EXTENSION_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_MAX_EXTENSION_ID_LENGTH = 48


def _validated_extension_id(value: str) -> str:
    extension_id = value.strip()
    if (
        not extension_id
        or len(extension_id) > _MAX_EXTENSION_ID_LENGTH
        or _EXTENSION_ID_RE.fullmatch(extension_id) is None
    ):
        raise ValueError("extension id must be a lower-kebab token up to 48 characters")
    return extension_id


def _validated_version(value: str) -> str:
    version = value.strip()
    if _VERSION_RE.fullmatch(version) is None:
        raise ValueError("extension starter version must use MAJOR.MINOR.PATCH")
    return version


def _starter_files(extension_id: str, version: str) -> Mapping[str, str]:
    module_name = extension_id.replace("-", "_")
    protocol = f"{module_name}_extension_v0"
    response_schema = f"{module_name}_response_v0"
    request_schema = f"{module_name}_request_v0"

    manifest = f'''\
schema_version = "loopx_extension_manifest_v0"
id = "{extension_id}"
version = "{version}"
requires_loopx_api = ">=1,<2"
permissions = []

[runtime]
protocol = "{protocol}"
entrypoint = "{extension_id}"
doctor_args = ["--doctor"]
required_permissions = []
timeout_seconds = 30
'''
    pyproject = f'''\
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "{extension_id}"
version = "{version}"
description = "Standalone LoopX extension starter"
readme = "README.md"
requires-python = ">=3.11"

[project.scripts]
{extension_id} = "{module_name}.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
'''
    provider = f'''\
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any


EXTENSION_ID = "{extension_id}"
REQUEST_SCHEMA_VERSION = "{request_schema}"
RESPONSE_SCHEMA_VERSION = "{response_schema}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=EXTENSION_ID)
    parser.add_argument("--doctor", action="store_true")
    return parser


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, sort_keys=True)
    sys.stdout.write("\\n")


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.doctor:
        return 0
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("extension input must be a JSON object")
        if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
            raise ValueError(
                f"extension input must use {{REQUEST_SCHEMA_VERSION}}"
            )
        unexpected = sorted(set(request) - {{"schema_version", "message"}})
        if unexpected:
            raise ValueError(f"extension input has unsupported fields {{unexpected}}")
        message = request.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("extension input requires non-empty string `message`")
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        _emit(
            {{
                "ok": False,
                "schema_version": RESPONSE_SCHEMA_VERSION,
                "extension_id": EXTENSION_ID,
                "error": str(exc),
            }}
        )
        return 1
    _emit(
        {{
            "ok": True,
            "schema_version": RESPONSE_SCHEMA_VERSION,
            "extension_id": EXTENSION_ID,
            "request_schema_version": REQUEST_SCHEMA_VERSION,
            "result": {{"message": message}},
        }}
    )
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
'''
    package_init = f'''\
__all__ = ["__version__"]

__version__ = "{version}"
'''
    request_contract = json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "message"],
            "properties": {
                "schema_version": {"const": request_schema},
                "message": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": r"\S",
                },
            },
        },
        indent=2,
        sort_keys=True,
    )
    response_contract = json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["ok", "schema_version", "extension_id"],
            "properties": {
                "ok": {"type": "boolean"},
                "schema_version": {"const": response_schema},
                "extension_id": {"const": extension_id},
                "request_schema_version": {"const": request_schema},
                "result": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["message"],
                    "properties": {
                        "message": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": r"\S",
                        }
                    },
                },
                "error": {"type": "string", "minLength": 1},
            },
            "oneOf": [
                {
                    "required": ["request_schema_version", "result"],
                    "properties": {
                        "ok": {"const": True},
                        "error": False,
                    },
                },
                {
                    "required": ["error"],
                    "properties": {
                        "ok": {"const": False},
                        "request_schema_version": False,
                        "result": False,
                    },
                },
            ],
        },
        indent=2,
        sort_keys=True,
    )
    request = json.dumps(
        {
            "schema_version": request_schema,
            "message": "hello from the LoopX extension starter",
        },
        indent=2,
        sort_keys=True,
    )
    readme = dedent(
        f"""\
        # {extension_id}

        This is a minimal standalone LoopX extension. It owns its package and
        provider protocol; LoopX owns lifecycle registration and managed invocation.
        The starter declares no permissions because public standalone invocation
        cannot dispatch permissioned effects. Move permissioned work behind a
        capability or domain command with a request-bound execution envelope.

        `schemas/request.schema.json` and `schemas/response.schema.json` are the
        starter's versioned wire contracts. The provider rejects a missing or
        mismatched request schema before doing work.

        Run the following commands from the same activated Python environment so
        the provider entrypoint is available on `PATH` when LoopX verifies it:

        ```bash
        python3 -m pip install .
        loopx extension install --manifest extension.toml --execute --format json
        loopx extension run {extension_id} \\
          --input-json examples/request.json \\
          --execute \\
          --format json
        ```

        `extension install` registers an already installed entrypoint from the
        active environment. It does not build or download this package. Edit the
        provider response and request contract before treating the starter as a
        product extension.
        """
    )
    return {
        "extension.toml": manifest,
        "pyproject.toml": pyproject,
        "README.md": readme,
        "examples/request.json": request + "\n",
        "schemas/request.schema.json": request_contract + "\n",
        "schemas/response.schema.json": response_contract + "\n",
        f"src/{module_name}/__init__.py": package_init,
        f"src/{module_name}/cli.py": provider,
    }


def _next_commands(extension_id: str, destination: Path) -> dict[str, str]:
    manifest = destination / "extension.toml"
    request = destination / "examples" / "request.json"
    return {
        "install_package": f"python3 -m pip install {shlex.quote(str(destination))}",
        "register_extension": (
            "loopx extension install --manifest "
            f"{shlex.quote(str(manifest))} --execute --format json"
        ),
        "run_extension": (
            f"loopx extension run {extension_id} --input-json "
            f"{shlex.quote(str(request))} --execute --format json"
        ),
    }


def scaffold_extension(
    extension_id: str,
    *,
    destination: str | Path | None = None,
    version: str = "0.1.0",
    execute: bool = False,
) -> dict[str, object]:
    """Preview or create one independently installable extension starter."""

    validated_id = _validated_extension_id(extension_id)
    validated_version = _validated_version(version)
    destination_path = (
        Path(destination).expanduser()
        if destination is not None
        else Path("extensions") / validated_id
    )
    if destination_path.exists():
        raise ValueError(
            f"extension starter destination already exists: {destination_path}"
        )

    files = _starter_files(validated_id, validated_version)
    if execute:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.mkdir()
        try:
            for relative, contents in files.items():
                target = destination_path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents, encoding="utf-8")
        except Exception:
            shutil.rmtree(destination_path)
            raise

    module_name = validated_id.replace("-", "_")
    return {
        "ok": True,
        "schema_version": EXTENSION_SCAFFOLD_SCHEMA_VERSION,
        "operation": "init",
        "dry_run": not execute,
        "changed": execute,
        "extension_id": validated_id,
        "starter_kind": "standalone",
        "capability_id": None,
        "managed_entrypoint": "loopx extension run",
        "version": validated_version,
        "destination": str(destination_path),
        "module_name": module_name,
        "protocol": f"{module_name}_extension_v0",
        "permissions": [],
        "files": [
            {
                "path": relative,
                "status": "created" if execute else "would_create",
            }
            for relative in files
        ],
        "next_commands": _next_commands(validated_id, destination_path),
    }
