from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from loopx.capabilities.catalog import (
    build_capability_catalog_packet,
    build_capability_detail_packet,
)
from loopx.capabilities.value_connectors.source_map import (
    build_value_connector_source_map_packet,
)
from loopx.cli import main
from loopx.extensions.runtime import default_extension_state_file, install_extension


ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ROOT = ROOT / "extensions" / "finance-value-discovery"
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
    catalog = build_capability_catalog_packet([MANIFEST])
    finance = next(
        item
        for item in catalog["capabilities"]
        if item["id"] == "finance-value-discovery"
    )

    assert finance["origin"] == "extension"
    assert finance["provider_id"] == "loopx-finance-value-discovery"
    assert finance["implementation_provider_count"] == 1
    detail = build_capability_detail_packet(
        "finance-value-discovery",
        [MANIFEST],
    )["capability"]
    assert detail["implementation_providers"] == [
        {
            "capability_id": "finance-value-discovery",
            "protocol": "finance_value_discovery_provider_v0",
            "provider_id": "loopx-finance-value-discovery",
            "provider_version": "0.2.0",
            "provider_state": {
                "declared": True,
                "installed": False,
                "enabled": False,
                "ready": False,
            },
        }
    ]

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


def test_value_connectors_delegates_through_verified_runtime(
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
                "value-connectors",
                "finance-discovery",
                "--input-json",
                str(EXAMPLE),
            ]
        )
        == 0
    )
    packet = json.loads(capsys.readouterr().out)
    assert packet["schema_version"] == "finance_value_discovery_packet_v0"
    assert packet["projection"]["next_targets"] == ["PYPL"]

    source_map = build_value_connector_source_map_packet(
        connector="finance_market_snapshot"
    )
    binding = source_map["source_profiles"][0]
    assert binding["outcome_capability_id"] == "finance-value-discovery"
    assert binding["provider_binding_state"] == "migrated"
    assert binding["provider_id"] == "loopx-finance-value-discovery"
