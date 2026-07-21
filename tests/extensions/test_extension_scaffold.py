from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
import pytest

from loopx.cli import main
from loopx.extensions.manifest import load_extension_manifest
from loopx.extensions.scaffold import scaffold_extension


def _schema_validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_scaffold_preview_is_read_only(tmp_path: Path) -> None:
    destination = tmp_path / "loopx-example"

    packet = scaffold_extension("loopx-example", destination=destination)

    assert packet["dry_run"] is True
    assert packet["changed"] is False
    assert packet["starter_kind"] == "standalone"
    assert packet["capability_id"] is None
    assert packet["managed_entrypoint"] == "loopx extension run"
    assert packet["protocol"] == "loopx_example_extension_v0"
    assert not destination.exists()
    assert [item["path"] for item in packet["files"]] == [
        "extension.toml",
        "pyproject.toml",
        "README.md",
        "examples/request.json",
        "schemas/request.schema.json",
        "schemas/response.schema.json",
        "src/loopx_example/__init__.py",
        "src/loopx_example/cli.py",
    ]


@pytest.mark.parametrize(
    ("extension_id", "version"),
    [
        ("LoopX-example", "0.1.0"),
        ("loopx_example", "0.1.0"),
        ("loopx-example", "v1"),
    ],
)
def test_scaffold_rejects_unsafe_identifiers(
    tmp_path: Path,
    extension_id: str,
    version: str,
) -> None:
    with pytest.raises(ValueError, match="extension id|version"):
        scaffold_extension(
            extension_id,
            destination=tmp_path / "extension",
            version=version,
        )


def test_scaffold_execute_creates_valid_manifest_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "loopx-example"

    packet = scaffold_extension(
        "loopx-example",
        destination=destination,
        execute=True,
    )

    assert packet["changed"] is True
    assert "same activated Python environment" in (destination / "README.md").read_text(
        encoding="utf-8"
    )
    manifest = load_extension_manifest(destination / "extension.toml")
    assert manifest["provider"]["id"] == "loopx-example"
    assert manifest["capabilities"] == []
    assert manifest["implementations"] == []
    assert manifest["provider"]["permissions"] == []
    assert manifest["runtime"]["required_permissions"] == []
    assert manifest["runtime"]["entrypoint"] == "loopx-example"
    request_schema_path = destination / "schemas" / "request.schema.json"
    response_schema_path = destination / "schemas" / "response.schema.json"
    request_schema = json.loads(request_schema_path.read_text(encoding="utf-8"))
    response_schema = json.loads(response_schema_path.read_text(encoding="utf-8"))
    request_validator = _schema_validator(request_schema_path)
    response_validator = _schema_validator(response_schema_path)
    assert request_schema["properties"]["schema_version"] == {
        "const": "loopx_example_request_v0"
    }
    assert response_schema["properties"]["schema_version"] == {
        "const": "loopx_example_response_v0"
    }
    request_validator.validate(
        json.loads((destination / "examples" / "request.json").read_text())
    )
    with pytest.raises(ValidationError):
        request_validator.validate(
            {
                "schema_version": "loopx_example_request_v0",
                "message": "   ",
            }
        )
    with pytest.raises(ValidationError):
        response_validator.validate(
            {
                "ok": True,
                "schema_version": "loopx_example_response_v0",
                "extension_id": "loopx-example",
            }
        )
    with pytest.raises(ValidationError):
        response_validator.validate(
            {
                "ok": False,
                "schema_version": "loopx_example_response_v0",
                "extension_id": "loopx-example",
            }
        )
    with pytest.raises(ValueError, match="destination already exists"):
        scaffold_extension(
            "loopx-example",
            destination=destination,
            execute=True,
        )


def test_scaffold_defaults_to_extensions_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    packet = scaffold_extension("loopx-example", execute=True)

    assert packet["destination"] == "extensions/loopx-example"
    assert (tmp_path / "extensions" / "loopx-example" / "extension.toml").is_file()


def test_extension_init_cli_previews_then_creates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "loopx-example"
    arguments = [
        "--format",
        "json",
        "extension",
        "init",
        "loopx-example",
        "--destination",
        str(destination),
    ]

    assert main(arguments) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["dry_run"] is True
    assert not destination.exists()

    assert main([*arguments, "--execute"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["dry_run"] is False
    assert created["changed"] is True
    assert (destination / "src" / "loopx_example" / "cli.py").is_file()


def test_generated_starter_installs_and_runs_through_managed_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "loopx-example"
    scaffold_extension(
        "loopx-example",
        destination=destination,
        execute=True,
    )
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    binary_dir = environment / ("Scripts" if os.name == "nt" else "bin")
    python = binary_dir / ("python.exe" if os.name == "nt" else "python")
    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir()
    uv = shutil.which("uv")
    build_command = (
        [
            uv,
            "build",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
            str(destination),
        ]
        if uv
        else [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(destination),
        ]
    )
    subprocess.run(
        build_command,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("loopx_example-*.whl"))
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join([str(binary_dir), os.environ.get("PATH", "")]),
    )
    runtime_root = tmp_path / "runtime"
    manifest = destination / "extension.toml"
    request = destination / "examples" / "request.json"
    response_validator = _schema_validator(
        destination / "schemas" / "response.schema.json"
    )

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
    assert installed["doctor"]["verified"] is True

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
    assert listed["extensions"] == [
        {
            "id": "loopx-example",
            "enabled": True,
            "active_revision": installed["revision"],
            "rollback_available": False,
            "doctor_verified": True,
            "revision_count": 1,
        }
    ]

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "doctor",
                "loopx-example",
                "--execute",
            ]
        )
        == 0
    )
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["verified"] is True
    assert doctor["external_writes_performed"] is False

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "disable",
                "loopx-example",
                "--execute",
            ]
        )
        == 0
    )
    disabled = json.loads(capsys.readouterr().out)
    assert disabled["enabled"] is False

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "enable",
                "loopx-example",
                "--execute",
            ]
        )
        == 0
    )
    enabled = json.loads(capsys.readouterr().out)
    assert enabled["enabled"] is True
    assert enabled["doctor"]["verified"] is True

    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "run",
                "loopx-example",
                "--input-json",
                str(request),
                "--execute",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "succeeded"
    response_validator.validate(receipt["provider_result"])
    assert receipt["provider_result"] == {
        "extension_id": "loopx-example",
        "ok": True,
        "request_schema_version": "loopx_example_request_v0",
        "result": {"message": "hello from the LoopX extension starter"},
        "schema_version": "loopx_example_response_v0",
    }


def test_generated_provider_rejects_non_object_input(tmp_path: Path) -> None:
    destination = tmp_path / "loopx-example"
    scaffold_extension(
        "loopx-example",
        destination=destination,
        execute=True,
    )
    provider = destination / "src" / "loopx_example" / "cli.py"

    result = subprocess.run(
        [sys.executable, str(provider)],
        input="[]",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    response = json.loads(result.stdout)
    _schema_validator(
        destination / "schemas" / "response.schema.json"
    ).validate(response)
    assert response["ok"] is False


def test_generated_provider_rejects_wrong_request_contract(tmp_path: Path) -> None:
    destination = tmp_path / "loopx-example"
    scaffold_extension(
        "loopx-example",
        destination=destination,
        execute=True,
    )
    provider = destination / "src" / "loopx_example" / "cli.py"

    result = subprocess.run(
        [sys.executable, str(provider)],
        input=json.dumps(
            {
                "schema_version": "loopx_example_request_v1",
                "message": "wrong contract",
            }
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    response = json.loads(result.stdout)
    _schema_validator(
        destination / "schemas" / "response.schema.json"
    ).validate(response)
    assert response["ok"] is False
    assert "loopx_example_request_v0" in response["error"]
