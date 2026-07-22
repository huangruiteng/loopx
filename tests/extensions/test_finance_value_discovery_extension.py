from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from loopx.capabilities.catalog import build_capability_catalog_packet
from loopx.cli import main
from loopx.extensions.manifest import load_extension_manifest
from loopx.extensions.runtime import (
    default_extension_state_file,
    install_extension,
)


ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ROOT = ROOT / "extensions" / "loopx-finance-value-discovery"
EXTENSION_SRC = EXTENSION_ROOT / "src"
MANIFEST = EXTENSION_ROOT / "extension.toml"
EXAMPLE = EXTENSION_ROOT / "examples" / "paypal-debeta-discovery.json"
sys.path.insert(0, str(EXTENSION_SRC))

from loopx_finance_value_discovery.cli import run  # noqa: E402
from loopx_finance_value_discovery.reducer import (  # noqa: E402
    EVIDENCE_AXES,
    build_finance_value_discovery_packet,
)


def _example() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _installed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    provider = tmp_path / "finance-provider"
    provider.write_text(
        f"#!{sys.executable}\n"
        "from loopx_finance_value_discovery.cli import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    provider.chmod(0o755)
    manifest = tmp_path / "extension.toml"
    manifest.write_text(
        MANIFEST.read_text(encoding="utf-8").replace(
            'entrypoint = "loopx-finance-value-discovery"',
            f"entrypoint = {json.dumps(str(provider))}",
        ),
        encoding="utf-8",
    )
    existing = os.environ.get("PYTHONPATH")
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            part for part in [str(EXTENSION_SRC), str(ROOT), existing] if part
        ),
    )
    runtime_root = tmp_path / "runtime"
    install_extension(
        manifest,
        state_file=default_extension_state_file(runtime_root),
        execute=True,
    )
    return manifest, runtime_root


def test_manifest_and_paypal_example_preserve_extension_boundary() -> None:
    manifest = load_extension_manifest(MANIFEST)
    assert manifest["capabilities"] == []
    assert manifest["implementations"] == []
    assert manifest["provider"]["permissions"] == []
    assert manifest["runtime"]["required_permissions"] == []
    assert manifest["runtime"]["protocol"] == "finance_value_discovery_extension_v0"

    catalog = build_capability_catalog_packet([MANIFEST])
    assert "finance-value-discovery" not in {
        item["id"] for item in catalog["capabilities"]
    }

    packet = build_finance_value_discovery_packet(_example())
    assert packet["projection"]["next_action"] == "select_at_most_one_b_successor"
    assert packet["projection"]["next_targets"] == ["PYPL"]
    assert packet["projection"]["screen_group_count"] == 5
    assert packet["projection"]["control_count"] == 3
    assert packet["cards"][0]["de_beta_control_count"] == 3
    assert packet["cards"][0]["de_beta_supported"] is True
    assert packet["boundary"]["investment_advice"] is False
    assert packet["boundary"]["trading_allowed"] is False
    assert packet["boundary"]["continuous_watch_allowed"] is False


@pytest.mark.parametrize("legacy_command", ["source-map", "install-check"])
def test_legacy_connector_returns_extension_migration_packet(
    legacy_command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "--format",
                "json",
                "value-connectors",
                legacy_command,
                "--connector",
                "finance_market_snapshot",
            ]
        )
        == 0
    )
    packet = json.loads(capsys.readouterr().out)
    item = (
        packet["source_profiles"][0]
        if legacy_command == "source-map"
        else packet["checks"][0]
    )
    migration = item["migration"]
    assert item["status"] == "migrated_to_extension"
    assert migration["replacement_extension_id"] == ("loopx-finance-value-discovery")
    assert migration["replacement_capability_id"] is None
    assert migration["automatic_provider_install_supported"] is False
    assert migration["packaged_loopx_only_start_supported"] is False
    assert migration["agent_start_mode"] == ("guided_when_provider_source_is_available")
    assert migration["truth_contract"]["legacy_connector_executes_finance"] is False


def test_legacy_plan_selector_returns_extension_migration_packet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "--format",
                "json",
                "value-connectors",
                "plan",
                "--connector-id",
                "finance_market_snapshot",
            ]
        )
        == 0
    )
    migration = json.loads(capsys.readouterr().out)
    assert migration["schema_version"] == "value_connector_extension_migration_v0"
    assert migration["status"] == "migrated_to_extension"
    assert migration["replacement_extension_id"] == ("loopx-finance-value-discovery")
    assert migration["replacement_capability_id"] is None
    assert migration["truth_contract"]["legacy_connector_executes_finance"] is False


def test_group_wide_derating_or_missing_controls_cannot_advance() -> None:
    group_wide = _example()
    group_wide["cards"][0]["relative_signal"] = "group_wide"
    packet = build_finance_value_discovery_packet(group_wide)
    assert packet["projection"]["next_action"] == "close_no_validated_candidates"
    assert packet["projection"]["next_targets"] == []

    missing_controls = _example()
    missing_controls["cards"] = missing_controls["cards"][:2]
    packet = build_finance_value_discovery_packet(missing_controls)
    assert packet["cards"][0]["de_beta_control_count"] == 1
    assert packet["projection"]["next_action"] == "close_no_validated_candidates"


def test_a_claim_requires_complete_evidence_and_two_frozen_controls() -> None:
    payload = _example()
    candidate = payload["cards"][0]
    candidate["classification"] = "A"
    candidate["axes"] = {axis: "supported" for axis in EVIDENCE_AXES}
    candidate["missing_fields"] = []
    candidate["fully_diluted_valuation_status"] = "verified"
    candidate["terminal_risk_status"] = "bounded"
    payload["cards"] = payload["cards"][:2]

    with pytest.raises(ValueError, match="at least two frozen peer controls"):
        build_finance_value_discovery_packet(payload)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda payload: payload.update(
                {"screen_groups": ["legacy-payments", "packaging"]}
            ),
            "at least three unrelated screen groups",
        ),
        (
            lambda payload: payload["cards"][0].update({"counter_evidence": []}),
            "counter_evidence",
        ),
        (
            lambda payload: payload["cards"][0]["source_refs"][0].update(
                {"observed_at": "2026-07-07"}
            ),
            "after as_of",
        ),
        (
            lambda payload: payload.update({"raw_provider_payload": {"quote": 1}}),
            "forbidden key",
        ),
    ],
)
def test_reducer_fails_closed_on_weak_or_restricted_evidence(
    mutator,
    message: str,
) -> None:
    payload = deepcopy(_example())
    mutator(payload)
    with pytest.raises(ValueError, match=message):
        build_finance_value_discovery_packet(payload)


def test_provider_doctor_is_side_effect_free() -> None:
    assert run(["--doctor"]) == 0


def test_standalone_extension_runs_through_verified_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, runtime_root = _installed_manifest(tmp_path, monkeypatch)
    assert (
        main(
            [
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "extension",
                "run",
                "loopx-finance-value-discovery",
                "--input-json",
                str(EXAMPLE),
                "--execute",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "succeeded"
    packet = receipt["provider_result"]
    assert packet["schema_version"] == "finance_value_discovery_packet_v0"
    assert packet["projection"]["next_targets"] == ["PYPL"]
