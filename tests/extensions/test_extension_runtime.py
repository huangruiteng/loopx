from __future__ import annotations

import argparse
import ast
from collections.abc import Callable
import json
from pathlib import Path
import subprocess
import sys

import pytest

from loopx.capabilities.catalog import build_capability_detail_packet
from loopx.capabilities.semantic_preference.cli import (
    _register_legacy_openviking_provider_arguments,
)
from loopx.capabilities.semantic_preference.contract import provider_doctor, recall
from loopx.cli import main
from loopx.extensions.runtime import (
    disable_extension,
    doctor_installed_extension,
    enable_extension,
    extension_status,
    install_extension,
    resolve_extension_binding,
    rollback_extension,
)
from loopx.extensions.openviking_semantic_preference.provider import (
    register_openviking_provider_arguments,
)


def _provider(path: Path, *, doctor_exit: int = 0) -> Path:
    path.write_text(
        f"""#!{sys.executable}
import json
import sys

if "--doctor" in sys.argv:
    raise SystemExit({doctor_exit})

request = json.load(sys.stdin)
json.dump({{
    "schema_version": "semantic_preference_provider_response_v0",
    "items": [{{
        "preference_ref": "provider://preference/one",
        "summary": "Prefer compact validation notes.",
    }}],
}}, sys.stdout)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _manifest(
    path: Path,
    *,
    entrypoint: Path,
    version: str,
    extension_id: str = "test-semantic-extension",
) -> Path:
    path.write_text(
        f"""\
schema_version = "loopx_extension_manifest_v0"
id = "{extension_id}"
version = "{version}"
requires_loopx_api = ">=1,<2"
permissions = ["semantic_preference.read"]

[runtime]
protocol = "semantic_preference_provider_v0"
entrypoint = {json.dumps(str(entrypoint))}
doctor_args = ["--doctor"]
required_permissions = ["semantic_preference.read"]
timeout_seconds = 5

[[implements]]
capability_id = "semantic-preference"
protocol = "semantic_preference_provider_v0"
""",
        encoding="utf-8",
    )
    return path


def test_install_disable_upgrade_and_rollback_preserve_verified_binding(
    tmp_path: Path,
) -> None:
    provider = _provider(tmp_path / "provider")
    v1 = _manifest(tmp_path / "v1.toml", entrypoint=provider, version="1.0.0")
    v2 = _manifest(tmp_path / "v2.toml", entrypoint=provider, version="2.0.0")
    state_file = tmp_path / "runtime" / "extensions.json"

    preview = install_extension(v1, state_file=state_file)
    assert preview["changed"] is False
    assert preview["doctor"]["status"] == "probe_required"
    assert not state_file.exists()
    assert not state_file.with_name(f"{state_file.name}.lock").exists()

    installed = install_extension(v1, state_file=state_file, execute=True)
    assert installed["changed"] is True
    binding = resolve_extension_binding(
        "test-semantic-extension",
        state_file=state_file,
        capability_id="semantic-preference",
        protocol="semantic_preference_provider_v0",
        permission="semantic_preference.read",
    )
    assert binding["argv"] == [str(provider)]
    assert binding["timeout_seconds"] == 5

    disabled = disable_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    assert disabled["changed"] is True
    with pytest.raises(ValueError, match="is disabled"):
        resolve_extension_binding(
            "test-semantic-extension",
            state_file=state_file,
            capability_id="semantic-preference",
            protocol="semantic_preference_provider_v0",
            permission="semantic_preference.read",
        )

    enabled = enable_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    assert enabled["changed"] is True
    assert enabled["doctor"]["verified"] is True
    assert resolve_extension_binding(
        "test-semantic-extension",
        state_file=state_file,
        capability_id="semantic-preference",
        protocol="semantic_preference_provider_v0",
        permission="semantic_preference.read",
    )["argv"] == [str(provider)]
    already_enabled = enable_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    assert already_enabled["changed"] is False
    assert already_enabled["doctor"]["verified"] is True

    upgraded = install_extension(
        v2,
        state_file=state_file,
        operation="upgrade",
        execute=True,
    )
    assert upgraded["previous_revision"] == installed["revision"]
    assert upgraded["rollback_available"] is True
    rolled_back = rollback_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    assert rolled_back["revision"] == installed["revision"]
    assert extension_status(state_file=state_file)["extensions"] == [
        {
            "id": "test-semantic-extension",
            "enabled": True,
            "active_revision": installed["revision"],
            "rollback_available": True,
            "doctor_verified": True,
            "revision_count": 2,
        }
    ]


def test_failed_upgrade_keeps_the_active_revision(tmp_path: Path) -> None:
    ready = _provider(tmp_path / "ready-provider")
    broken = _provider(tmp_path / "broken-provider", doctor_exit=2)
    v1 = _manifest(tmp_path / "v1.toml", entrypoint=ready, version="1.0.0")
    v2 = _manifest(tmp_path / "v2.toml", entrypoint=broken, version="2.0.0")
    state_file = tmp_path / "extensions.json"

    installed = install_extension(v1, state_file=state_file, execute=True)
    with pytest.raises(ValueError, match="doctor is not ready"):
        install_extension(
            v2,
            state_file=state_file,
            operation="upgrade",
            execute=True,
        )

    status = extension_status(state_file=state_file)["extensions"][0]
    assert status["active_revision"] == installed["revision"]
    assert status["revision_count"] == 1


def test_failed_enable_remains_disabled_and_clears_old_proof(tmp_path: Path) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    state_file = tmp_path / "extensions.json"
    install_extension(manifest, state_file=state_file, execute=True)
    disable_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    _provider(provider, doctor_exit=2)

    with pytest.raises(ValueError, match="enable doctor is not ready"):
        enable_extension(
            "test-semantic-extension",
            state_file=state_file,
            execute=True,
        )

    entry = json.loads(state_file.read_text(encoding="utf-8"))["extensions"][
        "test-semantic-extension"
    ]
    assert entry["enabled"] is False
    assert "doctor_verified_revision" not in entry
    assert "doctor_verified_entrypoint_identity" not in entry


def test_failed_executed_doctor_clears_stale_readiness_proof(
    tmp_path: Path,
) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    state_file = tmp_path / "extensions.json"
    install_extension(manifest, state_file=state_file, execute=True)
    _provider(provider, doctor_exit=2)

    doctor = doctor_installed_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )

    assert doctor["verified"] is False
    entry = json.loads(state_file.read_text(encoding="utf-8"))["extensions"][
        "test-semantic-extension"
    ]
    assert "doctor_verified_revision" not in entry
    assert "doctor_verified_entrypoint_identity" not in entry
    with pytest.raises(ValueError, match="doctor readiness is stale"):
        resolve_extension_binding(
            "test-semantic-extension",
            state_file=state_file,
            capability_id="semantic-preference",
            protocol="semantic_preference_provider_v0",
            permission="semantic_preference.read",
        )


def test_executed_doctor_rebinds_revision_only_legacy_proof(tmp_path: Path) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    state_file = tmp_path / "extensions.json"
    install_extension(manifest, state_file=state_file, execute=True)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    entry = state["extensions"]["test-semantic-extension"]
    entry.pop("doctor_verified_entrypoint_identity")
    state_file.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(ValueError, match="doctor readiness is stale"):
        resolve_extension_binding(
            "test-semantic-extension",
            state_file=state_file,
            capability_id="semantic-preference",
            protocol="semantic_preference_provider_v0",
            permission="semantic_preference.read",
        )
    repaired = doctor_installed_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    assert repaired["verified"] is True
    assert resolve_extension_binding(
        "test-semantic-extension",
        state_file=state_file,
        capability_id="semantic-preference",
        protocol="semantic_preference_provider_v0",
        permission="semantic_preference.read",
    )["argv"] == [str(provider)]


@pytest.mark.parametrize("replacement", ["missing", "changed"])
def test_binding_rejects_missing_or_replaced_entrypoint(
    tmp_path: Path,
    replacement: str,
) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    state_file = tmp_path / "extensions.json"
    install_extension(manifest, state_file=state_file, execute=True)
    if replacement == "missing":
        provider.unlink()
    else:
        _provider(provider, doctor_exit=0)
        provider.write_text(
            provider.read_text(encoding="utf-8").replace(
                "Prefer compact validation notes.",
                "A replaced provider must be re-verified.",
            ),
            encoding="utf-8",
        )

    assert extension_status(state_file=state_file)["extensions"][0][
        "doctor_verified"
    ] is False
    with pytest.raises(ValueError, match="doctor readiness is stale"):
        resolve_extension_binding(
            "test-semantic-extension",
            state_file=state_file,
            capability_id="semantic-preference",
            protocol="semantic_preference_provider_v0",
            permission="semantic_preference.read",
        )


def test_runtime_permission_must_be_declared_by_manifest(tmp_path: Path) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'permissions = ["semantic_preference.read"]',
            "permissions = []",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires undeclared permissions"):
        install_extension(manifest, state_file=tmp_path / "extensions.json")


def test_semantic_preference_resolves_enabled_extension(tmp_path: Path) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    state_file = tmp_path / "extensions.json"
    install_extension(manifest, state_file=state_file, execute=True)
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "semantic-preference.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {
                    "id": "openviking_semantic_preference",
                    "extension_id": "test-semantic-extension",
                    "extension_state_file": str(state_file),
                    "args": ["--project", str(project)],
                },
                "surfaces": {
                    "issue_fix.pr_description": {
                        "query": "validation preferences",
                        "limit": 3,
                        "failure_policy": "fail_open",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    doctor = provider_doctor(config, project=project, execute=True)
    assert doctor["status"] == "ready"
    assert doctor["verified"] is True
    result = recall(
        config,
        project=project,
        surface="issue_fix.pr_description",
        execute=True,
    )
    assert result["status"] == "completed"
    assert result["items"][0]["summary"] == "Prefer compact validation notes."

    disable_extension(
        "test-semantic-extension",
        state_file=state_file,
        execute=True,
    )
    unavailable = recall(
        config,
        project=project,
        surface="issue_fix.pr_description",
        execute=True,
    )
    assert unavailable["status"] == "provider_unavailable"
    assert unavailable["failure_kind"] == "extension_binding_unavailable"

    detail = build_capability_detail_packet("semantic-preference", [manifest])
    assert detail["capability"]["implementation_providers"] == [
        {
            "capability_id": "semantic-preference",
            "protocol": "semantic_preference_provider_v0",
            "provider_id": "test-semantic-extension",
            "provider_version": "1.0.0",
        }
    ]


def test_extension_cli_installs_preinstalled_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider = _provider(tmp_path / "provider")
    manifest = _manifest(
        tmp_path / "extension.toml",
        entrypoint=provider,
        version="1.0.0",
    )
    runtime_root = tmp_path / "runtime"

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "install",
                "--manifest",
                str(manifest),
                "--execute",
            ]
        )
        == 0
    )
    installed = json.loads(capsys.readouterr().out)
    assert installed["changed"] is True

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "list",
            ]
        )
        == 0
    )
    listed = json.loads(capsys.readouterr().out)
    assert listed["extensions"][0]["doctor_verified"] is True

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "disable",
                "test-semantic-extension",
                "--execute",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "enable",
                "test-semantic-extension",
                "--execute",
            ]
        )
        == 0
    )
    enabled = json.loads(capsys.readouterr().out)
    assert enabled["enabled"] is True
    assert enabled["doctor"]["verified"] is True


def test_core_does_not_import_openviking_provider_implementation() -> None:
    root = Path(__file__).resolve().parents[2] / "loopx"
    forbidden: list[str] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if relative.parts[0] == "extensions":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = " ".join(alias.name for alias in node.names)
            if "openviking_semantic_preference" in module:
                forbidden.append(str(relative))
    assert forbidden == []


def test_ordinary_cli_import_does_not_load_openviking_provider() -> None:
    module = "loopx.extensions.openviking_semantic_preference.provider"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; import loopx.cli; assert {module!r} not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_legacy_openviking_alias_matches_provider_argument_contract() -> None:
    def options(
        register: Callable[[argparse.ArgumentParser], None],
    ) -> list[tuple[object, ...]]:
        parser = argparse.ArgumentParser(add_help=False)
        register(parser)
        return [
            (
                tuple(action.option_strings),
                action.dest,
                type(action).__name__,
                action.default,
                action.nargs,
                action.const,
            )
            for action in parser._actions
            if action.option_strings
        ]

    assert options(_register_legacy_openviking_provider_arguments) == options(
        register_openviking_provider_arguments
    )
