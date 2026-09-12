#!/usr/bin/env python3
"""Verify dashboard source assets and shipped bundles expose the PWA contract."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_SOURCE = REPO_ROOT / "apps" / "presentation" / "dashboard"
ROOT_BUNDLE = ROOT_SOURCE / "dist"
CHAT_BUNDLE = REPO_ROOT / "loopx" / "web" / "chat"


def assert_pwa_contract(
    label: str,
    *,
    index: Path,
    asset_root: Path,
    manifest_href: str,
) -> None:
    assert index.is_file(), f"{label}: missing {index}"
    index_text = index.read_text(encoding="utf-8")
    assert f'<link rel="manifest" href="{manifest_href}" />' in index_text, (
        f"{label}: index does not reference {manifest_href}"
    )

    manifest_path = asset_root / "manifest.webmanifest"
    icon_192 = asset_root / "pwa" / "icon-192.png"
    icon_512 = asset_root / "pwa" / "icon-512.png"
    assert manifest_path.is_file(), f"{label}: missing {manifest_path}"
    assert icon_192.is_file(), f"{label}: missing {icon_192}"
    assert icon_512.is_file(), f"{label}: missing {icon_512}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone", manifest
    assert manifest["start_url"] == "./", manifest
    assert manifest["scope"] == "./", manifest
    assert [icon["src"] for icon in manifest["icons"]] == [
        "pwa/icon-192.png",
        "pwa/icon-512.png",
    ], manifest


def assert_pwa_bundle(label: str, bundle: Path, manifest_href: str) -> None:
    assert_pwa_contract(
        label,
        index=bundle / "index.html",
        asset_root=bundle,
        manifest_href=manifest_href,
    )


def assert_bounded_chat_assets() -> None:
    retention = json.loads(
        (CHAT_BUNDLE / "asset-retention.json").read_text(encoding="utf-8")
    )
    assert retention["schema_version"] == "loopx_chat_asset_retention_v1"
    generations = retention["generations"]
    assert 1 <= len(generations) <= 2, generations
    retained = {asset for generation in generations for asset in generation}
    referenced = set(
        re.findall(
            r'(?:src|href)="/chat/(assets/[^"]+)"',
            (CHAT_BUNDLE / "index.html").read_text(encoding="utf-8"),
        )
    )
    assert referenced <= set(generations[0]), (referenced, generations[0])
    assert retained == {
        f"assets/{path.name}" for path in (CHAT_BUNDLE / "assets").iterdir()
    }
    assert all((CHAT_BUNDLE / asset).is_file() for asset in retained)


def main() -> int:
    # The full-public suite is Python-only and starts from a clean checkout, so
    # the ignored Vite output is not guaranteed to exist. Always validate the
    # tracked build inputs; the dedicated frontstage build job proves that Vite
    # can produce the root bundle. When a local build is present, validate it too.
    assert_pwa_contract(
        "root dashboard source",
        index=ROOT_SOURCE / "index.html",
        asset_root=ROOT_SOURCE / "public",
        manifest_href="manifest.webmanifest",
    )
    if ROOT_BUNDLE.is_dir():
        assert_pwa_bundle("root dashboard bundle", ROOT_BUNDLE, "manifest.webmanifest")
    assert_pwa_bundle("chat dashboard", CHAT_BUNDLE, "/chat/manifest.webmanifest")
    assert_bounded_chat_assets()
    print("dashboard-pwa-bundle-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
