from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.capabilities.catalog import (
    build_capability_catalog_packet,
    build_capability_detail_packet,
    build_capability_registry,
)
from loopx.cli import main


BUILTIN_IDS = [
    "issue-fix",
    "semantic-preference",
    "reward-memory",
    "periodic-report",
    "content-ops",
    "value-connectors",
]


def _write_manifest(path: Path, *, capability_id: str = "sample-report") -> Path:
    path.write_text(
        f'''\
schema_version = "loopx_extension_manifest_v0"
id = "sample-extension"
version = "1.2.3"
requires_loopx_api = ">=1,<2"
permissions = ["read_status"]
runtime_entrypoint = "module.that.must.not.be.imported"

[[provides]]
id = "{capability_id}"
kind = "projection_sink"
title = "Sample report"
status = "active"
visibility = "public"
real_world_anchor = "deterministic extension fixture"
user_value = "Prove provider-aware capability composition."
entry_command = "sample-extension report"
next_real_step = "Keep the fixture bounded."

[[provides]]
id = "sample-internal-helper"
kind = "provider_helper"
title = "Sample internal helper"
status = "internal"
visibility = "internal"
real_world_anchor = "extension implementation detail"
user_value = "Remain hidden from the public catalog."
entry_command = ""
next_real_step = "Remain internal."
''',
        encoding="utf-8",
    )
    return path


def test_builtin_catalog_preserves_order_and_marks_provider() -> None:
    packet = build_capability_catalog_packet()

    assert packet["schema_version"] == "loopx_capability_catalog_v0"
    assert [item["id"] for item in packet["capabilities"]] == BUILTIN_IDS
    for item in packet["capabilities"]:
        assert item["origin"] == "builtin"
        assert item["visibility"] == "public"
        assert item["provider_id"] == "loopx-core"
    assert packet["providers"] == [
        {"id": "loopx-core", "origin": "builtin", "enabled": True}
    ]


def test_enabled_manifest_composes_public_capability_without_importing_code(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path / "extension.toml")

    packet = build_capability_catalog_packet([manifest])
    assert [item["id"] for item in packet["capabilities"]] == [
        *BUILTIN_IDS,
        "sample-report",
    ]
    extension = packet["capabilities"][-1]
    assert extension["origin"] == "extension"
    assert extension["visibility"] == "public"
    assert extension["provider_id"] == "sample-extension"
    assert packet["providers"][-1] == {
        "id": "sample-extension",
        "origin": "extension",
        "enabled": True,
        "version": "1.2.3",
        "requires_loopx_api": ">=1,<2",
        "permissions": ["read_status"],
    }

    detail = build_capability_detail_packet("sample-report", [manifest])
    assert detail["capability"]["capability_kind"] == "projection_sink"
    assert detail["capability"]["provider_version"] == "1.2.3"


def test_internal_capability_is_registered_but_not_publicly_listed(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path / "extension.toml")
    registry = build_capability_registry([manifest])

    assert "sample-internal-helper" not in registry.capability_ids()
    assert "sample-internal-helper" in registry.capability_ids(include_internal=True)
    assert (
        registry.get("sample-internal-helper", include_internal=True)["visibility"]
        == "internal"
    )


def test_duplicate_capability_fails_closed(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "extension.toml",
        capability_id="value-connectors",
    )

    with pytest.raises(ValueError, match="duplicate capability `value-connectors`"):
        build_capability_catalog_packet([manifest])


def test_incompatible_extension_api_fails_closed(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "extension.toml")
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'requires_loopx_api = ">=1,<2"',
            'requires_loopx_api = ">=2,<3"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires LoopX extension API"):
        build_capability_catalog_packet([manifest])


def test_cli_lists_and_shows_explicit_extension_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = _write_manifest(tmp_path / "extension.toml")

    assert (
        main(
            [
                "--format",
                "json",
                "capability",
                "list",
                "--extension-manifest",
                str(manifest),
            ]
        )
        == 0
    )
    listed = json.loads(capsys.readouterr().out)
    assert listed["capabilities"][-1]["id"] == "sample-report"

    assert (
        main(
            [
                "--format",
                "json",
                "capability",
                "show",
                "sample-report",
                "--extension-manifest",
                str(manifest),
            ]
        )
        == 0
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown["capability"]["provider_id"] == "sample-extension"


def test_cli_rejects_unknown_capability_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["capability", "show", "not-registered"])

    assert exc_info.value.code == 2
    assert "unknown capability `not-registered`" in capsys.readouterr().err
