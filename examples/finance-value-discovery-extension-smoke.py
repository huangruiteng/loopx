#!/usr/bin/env python3
"""Prove finance extension semantics, lifecycle binding, and compatibility."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "extensions" / "finance-value-discovery"
EXTENSION_SRC = EXTENSION_ROOT / "src"
MANIFEST = EXTENSION_ROOT / "extension.toml"
EXAMPLE = EXTENSION_ROOT / "examples" / "paypal-debeta-discovery.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXTENSION_SRC))

from loopx.capabilities.catalog import build_capability_catalog_packet  # noqa: E402
from loopx.capabilities.value_connectors.finance_extension import (  # noqa: E402
    invoke_finance_value_discovery_extension,
)
from loopx.capabilities.value_connectors.source_map import (  # noqa: E402
    build_value_connector_source_map_packet,
)
from loopx.extensions.runtime import (  # noqa: E402
    default_extension_state_file,
    install_extension,
)
from loopx_finance_value_discovery.reducer import (  # noqa: E402
    build_finance_value_discovery_packet,
)


def main() -> int:
    evidence = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    direct = build_finance_value_discovery_packet(evidence)
    assert direct["projection"]["next_targets"] == ["PYPL"]
    assert direct["projection"]["control_count"] == 3
    assert direct["truth_contract"]["group_wide_derating_is_not_idiosyncratic_alpha"]
    assert direct["boundary"]["investment_advice"] is False
    assert direct["boundary"]["trading_allowed"] is False
    assert direct["boundary"]["continuous_watch_allowed"] is False

    catalog = build_capability_catalog_packet([MANIFEST])
    finance = next(
        item
        for item in catalog["capabilities"]
        if item["id"] == "finance-value-discovery"
    )
    assert finance["origin"] == "extension"
    assert finance["provider_id"] == "loopx-finance-value-discovery"
    assert finance["provider_state"]["installed"] is False

    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        provider = directory / "finance-provider"
        provider.write_text(
            f"#!{sys.executable}\n"
            "from loopx_finance_value_discovery.cli import main\n"
            "raise SystemExit(main())\n",
            encoding="utf-8",
        )
        provider.chmod(0o755)
        manifest = directory / "extension.toml"
        manifest.write_text(
            MANIFEST.read_text(encoding="utf-8").replace(
                'entrypoint = "loopx-finance-value-discovery"',
                f"entrypoint = {json.dumps(str(provider))}",
            ),
            encoding="utf-8",
        )
        runtime_root = directory / "runtime"
        state_file = default_extension_state_file(runtime_root)
        previous_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = os.pathsep.join(
            part
            for part in [str(EXTENSION_SRC), str(ROOT), previous_pythonpath]
            if part
        )
        try:
            installed = install_extension(
                manifest,
                state_file=state_file,
                execute=True,
            )
            assert installed["doctor"]["verified"] is True
            delegated = invoke_finance_value_discovery_extension(
                evidence,
                runtime_root=runtime_root,
            )
        finally:
            if previous_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous_pythonpath
        assert delegated == direct

    source_map = build_value_connector_source_map_packet(
        connector="finance_market_snapshot"
    )["source_profiles"][0]
    assert source_map["provider_binding_state"] == "migrated"
    assert source_map["provider_id"] == "loopx-finance-value-discovery"

    print("finance-value-discovery-extension-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
