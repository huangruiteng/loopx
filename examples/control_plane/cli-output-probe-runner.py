#!/usr/bin/env python3
"""Emit a public-safe CLI output receipt from the shared qualification fixture."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


PROBE_SCHEMA_VERSION = "loopx_cli_output_probe_v0"
FIXTURE_CONTRACT_VERSION = "loopx_cli_output_public_fixture_v0"


def _install_pytest_import_stub() -> None:
    if importlib.util.find_spec("pytest") is not None:
        return
    stub = ModuleType("pytest")

    class Mark:
        @staticmethod
        def parametrize(*_args: Any, **_kwargs: Any) -> Callable[..., Any]:
            return lambda function: function

    stub.mark = Mark()  # type: ignore[attr-defined]
    sys.modules["pytest"] = stub


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load CLI output probe fixture: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _receipt_row(
    *,
    semantics: ModuleType,
    row_id: str,
    surface_id: str,
    scenario: str,
    output_format: str,
    qualification_policy: str,
    semantic_json_keys: tuple[str, ...],
    markdown_anchor: str,
    measurement: dict,
    text: str,
    variant_id: str | None = None,
) -> dict:
    payload = measurement.get("payload")
    return {
        "row_id": row_id,
        "surface_id": surface_id,
        "variant_id": variant_id,
        "scenario": scenario,
        "format": output_format,
        "qualification_policy": qualification_policy,
        "chars": measurement["chars"],
        "utf8_bytes": measurement["utf8_bytes"],
        "lines": measurement["lines"],
        "compact_payload_chars": measurement["compact_payload_chars"],
        "pretty_print_overhead_chars": measurement["pretty_print_overhead_chars"],
        "semantic_json_keys": list(semantic_json_keys),
        "json_shape_paths": (
            semantics.json_shape_paths(payload) if isinstance(payload, dict) else []
        ),
        "markdown_headings": semantics.markdown_headings(text),
        "markdown_anchor": markdown_anchor,
        "action_signature_sha256": (
            semantics.action_signature_semantic_sha256(payload)
            if isinstance(payload, dict)
            else None
        ),
    }


def _default_rows(
    probe: ModuleType,
    semantics: ModuleType,
    fixture_root: Path,
) -> list[dict]:
    rows: list[dict] = []
    for scenario in probe.SCENARIOS:
        project, runtime, registry_path, state_file = probe._write_fixture(
            fixture_root / scenario.name,
            scenario,
        )
        for output_format in ("json", "markdown"):
            commands = probe._surface_commands(
                project=project,
                runtime=runtime,
                registry_path=registry_path,
                state_file=state_file,
                output_format=output_format,
            )
            for surface_id, command in commands.items():
                exit_code, text = probe._invoke_cli(command)
                if exit_code != 0:
                    raise AssertionError(f"{surface_id}/{output_format} failed")
                measurement = probe.measure_cli_output(
                    text, output_format=output_format
                )
                surface = probe.CLI_OUTPUT_BUDGET_BY_ID[surface_id]
                probe.assert_cli_output_baseline(
                    surface,
                    scenario=scenario.name,
                    output_format=output_format,
                    text=text,
                    measurement=measurement,
                )
                rows.append(
                    _receipt_row(
                        semantics=semantics,
                        row_id=f"surface/{surface_id}/{scenario.name}/{output_format}",
                        surface_id=surface_id,
                        scenario=scenario.name,
                        output_format=output_format,
                        qualification_policy=surface.qualification_policy,
                        semantic_json_keys=surface.semantic_json_keys,
                        markdown_anchor=surface.markdown_anchor,
                        measurement=measurement,
                        text=text,
                    )
                )
    return rows


def _variant_rows(
    probe: ModuleType,
    semantics: ModuleType,
    fixture_root: Path,
) -> list[dict]:
    project, runtime, registry_path, state_file = probe._write_fixture(
        fixture_root / "mode_variants",
        probe.SCENARIOS[0],
    )
    rows: list[dict] = []
    for output_format in ("json", "markdown"):
        commands = probe._mode_variant_commands(
            project=project,
            runtime=runtime,
            registry_path=registry_path,
            state_file=state_file,
            output_format=output_format,
        )
        for variant_id, command in commands.items():
            variant = probe.CLI_OUTPUT_MODE_VARIANT_BY_ID.get(variant_id)
            if variant is None:
                # The shared candidate fixture may name a mode introduced after
                # the detached base. Candidate-only rows are qualified later.
                continue
            if output_format not in variant.output_formats:
                continue
            exit_code, text = probe._invoke_cli(command)
            if exit_code != 0:
                raise AssertionError(f"{variant_id}/{output_format} failed")
            measurement = probe.measure_cli_output(text, output_format=output_format)
            probe.assert_cli_output_mode_variant(
                variant,
                output_format=output_format,
                text=text,
                measurement=measurement,
            )
            rows.append(
                _receipt_row(
                    semantics=semantics,
                    row_id=f"variant/{variant_id}/small/{output_format}",
                    surface_id=variant.parent_surface_id,
                    variant_id=variant_id,
                    scenario="small",
                    output_format=output_format,
                    qualification_policy="explicit_opt_in_cold_path",
                    semantic_json_keys=variant.semantic_json_keys,
                    markdown_anchor=variant.markdown_anchor,
                    measurement=measurement,
                    text=text,
                )
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-source", type=Path, required=True)
    parser.add_argument("--semantics-source", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    _install_pytest_import_stub()
    probe = _load_module("loopx_cli_output_probe_fixture", args.test_source)
    semantics = _load_module("loopx_cli_output_probe_semantics", args.semantics_source)
    if args.fixture_root.exists():
        shutil.rmtree(args.fixture_root)
    args.fixture_root.mkdir(parents=True)
    rows = [
        *_default_rows(probe, semantics, args.fixture_root),
        *_variant_rows(probe, semantics, args.fixture_root),
    ]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(
            {
                "schema_version": PROBE_SCHEMA_VERSION,
                "fixture_contract_version": FIXTURE_CONTRACT_VERSION,
                "rows": sorted(rows, key=lambda row: row["row_id"]),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"cli-output-probe-runner ok rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
