#!/usr/bin/env python3
"""Prove the operator credential is configurable, redacted, and effective.

The machine's operator model credential is what the steward channel and the
managed host authenticate with. This smoke exercises the two shipped entry
points that now write it -- the personal-workspace API and
``loopx machine-config credential`` -- and then proves the value actually
reaches the existing executor resolution, while no readback and no
machine-configuration document ever carries the key.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.machine_configuration.builtins import (  # noqa: E402
    build_builtin_machine_configuration_registry,
)
from loopx.capabilities.machine_configuration.cli import (  # noqa: E402
    handle_machine_configuration_command,
)
from loopx.capabilities.machine_configuration.store import (  # noqa: E402
    machine_configuration_store_path,
    read_machine_configuration,
)
from loopx.chat_operator_provider_api import (  # noqa: E402
    CHAT_OPERATOR_PROVIDER_PATH,
    OperatorProviderRequestMixin,
)
from loopx.control_plane.operator_provider import (  # noqa: E402
    SOURCE_MACHINE_STORE,
    STATUS_ABSENT,
    STATUS_CONFIGURED,
    operator_provider_environ,
    operator_provider_store_path,
)
from loopx.control_plane.turn_driver.host_binding import (  # noqa: E402
    OPERATOR_CREDENTIAL_UNCONFIGURED,
    managed_executor_binding,
    selected_turn_host,
)


KEY = "sk-operator-provider-smoke-key"
BASE_URL = "https://endpoint.smoke.invalid/v1"


def fail(message: str) -> None:
    raise SystemExit(f"operator provider credential smoke failed: {message}")


class _Handler(OperatorProviderRequestMixin):
    """Drive the real request mixin without opening a socket."""

    def __init__(self, runtime_root: Path, body: dict[str, Any] | None = None) -> None:
        self.server = SimpleNamespace(runtime_root=runtime_root)
        self.body = body or {}
        self.responses: list[dict[str, Any]] = []

    def _read_json(self) -> dict[str, Any]:
        return self.body

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        self.responses.append({"status_code": status, **payload})

    def _send_error(
        self, message: str, *, status: int, error_code: str, **_kwargs: Any
    ) -> None:
        self.responses.append(
            {
                "status_code": status,
                "error_code": error_code,
                "error": message,
            }
        )


def _cli_args(**overrides: Any) -> argparse.Namespace:
    values: dict[str, Any] = {
        "command": "machine-config",
        "machine_config_command": "credential",
        "machine_credential_command": "status",
        "config_json": None,
        "clear_api_key": False,
        "clear_base_url": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _run_cli(
    runtime_root: Path, registry_path: Path, **overrides: Any
) -> tuple[int, dict[str, Any]]:
    captured: list[dict[str, Any]] = []
    code = handle_machine_configuration_command(
        _cli_args(**overrides),
        runtime_root_arg=str(runtime_root),
        registry_path=registry_path,
        output_format=lambda _args: "json",
        print_payload=lambda payload, _fmt, _render: captured.append(dict(payload)),
    )
    if code is None:
        fail("machine-config credential did not take the credential path")
    return code, captured[-1]


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        runtime_root = root / "runtime"
        registry_path = root / ".loopx" / "registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("{}", encoding="utf-8")

        # 1. An unconfigured machine refuses the managed host instead of
        #    spending a Turn on an endpoint nothing can authenticate.
        handler = _Handler(runtime_root)
        handler._operator_provider_status()
        status = handler.responses[-1]
        if status["status_code"] != 200 or status["status"] != STATUS_ABSENT:
            fail(f"an unconfigured machine must report absent: {status}")
        if selected_turn_host(operator_provider_environ(runtime_root))[0] != "codex-cli":
            fail("an unconfigured machine must keep the individual default host")

        refused = managed_executor_binding(
            "dsh", environ=operator_provider_environ(runtime_root)
        )
        if refused.get("unavailable_reason") != OPERATOR_CREDENTIAL_UNCONFIGURED:
            fail(f"the managed host must name the missing credential: {refused}")

        # 2. The browser writes the pair through the real request mixin.
        writer = _Handler(
            runtime_root, {"provider_key": KEY, "base_url": BASE_URL}
        )
        writer._operator_provider_update()
        written = writer.responses[-1]
        if written["status_code"] != 200 or written["status"] != STATUS_CONFIGURED:
            fail(f"the write path must report the stored credential: {written}")
        if written["provider_key"]["source"] != SOURCE_MACHINE_STORE:
            fail(f"the readback must name the machine store: {written}")
        if KEY in json.dumps(written):
            fail("the write readback must never echo the key")
        if written["base_url"]["value"] != BASE_URL:
            fail(f"the endpoint is not a secret and must read back: {written}")

        # 3. The credential resolves into the existing executor decision, which
        #    is what makes the stored key effective rather than decorative.
        resolved = operator_provider_environ(runtime_root)
        if resolved.get("DEEPSEEK_API_KEY") != KEY:
            fail("the stored key did not resolve into the host environment")
        if selected_turn_host(resolved)[0] != "dsh":
            fail("a stored credential must select the managed default host")
        if operator_provider_store_path(runtime_root).stat().st_mode & 0o777 != 0o600:
            fail("the credential file must be readable only by its owner")

        # 4. The CLI is the second entry point, and it is read-only for the key.
        code, cli_status = _run_cli(
            runtime_root, registry_path, machine_credential_command="status"
        )
        if code != 0 or cli_status["status"] != STATUS_CONFIGURED:
            fail(f"`machine-config credential status` must read the store: {cli_status}")
        if KEY in json.dumps(cli_status):
            fail("the status readback must never echo the key")

        code, cli_written = _run_cli(
            runtime_root,
            registry_path,
            machine_credential_command="set",
            config_json=None,
            clear_base_url=True,
        )
        if code != 0 or cli_written["base_url"]["configured"] is not False:
            fail(f"clearing one field must keep the other: {cli_written}")
        if cli_written["provider_key"]["configured"] is not True:
            fail("clearing the endpoint must not clear the key")

        code, cli_cleared = _run_cli(
            runtime_root,
            registry_path,
            machine_credential_command="clear",
        )
        if code != 0 or cli_cleared["status"] != STATUS_ABSENT:
            fail(f"`credential clear` must remove the whole record: {cli_cleared}")
        if operator_provider_store_path(runtime_root).exists():
            fail("a cleared credential must not leave a readable file behind")

        # 5. Nothing that is projected, inspected, or backed up carries it.
        _Handler(
            runtime_root, {"provider_key": KEY, "base_url": BASE_URL}
        )._operator_provider_update()
        document = machine_configuration_store_path(runtime_root)
        if document.exists() and KEY in document.read_text(encoding="utf-8"):
            fail("the machine-configuration document must never carry the key")
        projected = read_machine_configuration(
            runtime_root,
            registry=build_builtin_machine_configuration_registry(),
        )
        if KEY in json.dumps(projected or {}):
            fail("the machine-configuration projection must never carry the key")

        print(
            json.dumps(
                {
                    "ok": True,
                    "schema_version": "operator_provider_credential_smoke_v0",
                    "api_path": CHAT_OPERATOR_PROVIDER_PATH,
                    "checks": [
                        "unconfigured_machine_refuses_the_managed_host",
                        "browser_write_reports_machine_store_without_echoing_the_key",
                        "stored_credential_selects_and_authenticates_the_managed_host",
                        "credential_file_is_owner_only",
                        "cli_status_reads_and_cli_clear_removes",
                        "machine_configuration_never_carries_the_key",
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
