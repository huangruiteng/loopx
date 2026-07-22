#!/usr/bin/env python3
"""Prove standalone finance extension semantics and lifecycle binding."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "extensions" / "loopx-finance-value-discovery"
EXTENSION_SRC = EXTENSION_ROOT / "src"
MANIFEST = EXTENSION_ROOT / "extension.toml"
EXAMPLE = EXTENSION_ROOT / "examples" / "paypal-debeta-discovery.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EXTENSION_SRC))

from loopx.capabilities.catalog import build_capability_catalog_packet  # noqa: E402
from loopx.extensions.runtime import (  # noqa: E402
    default_extension_state_file,
    install_extension,
    run_standalone_extension,
)
from loopx.extensions.manifest import load_extension_manifest  # noqa: E402
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
    assert "finance-value-discovery" not in {
        item["id"] for item in catalog["capabilities"]
    }
    manifest = load_extension_manifest(MANIFEST)
    assert manifest["capabilities"] == []
    assert manifest["implementations"] == []

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
            receipt = run_standalone_extension(
                "loopx-finance-value-discovery",
                state_file=state_file,
                request=evidence,
                execute=True,
            )
        finally:
            if previous_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous_pythonpath
        assert receipt["status"] == "succeeded"
        assert receipt["provider_result"] == direct

    print("finance-value-discovery-extension-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
