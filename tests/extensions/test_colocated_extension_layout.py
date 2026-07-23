from pathlib import Path

from loopx.extensions.manifest import load_extension_manifest


ROOT = Path(__file__).resolve().parents[2]


def test_colocated_extension_packages_match_manifest_ids() -> None:
    manifests = sorted((ROOT / "packages").glob("*/extension.toml"))
    assert manifests, "expected at least one co-located extension package manifest"

    mismatches = []
    for manifest_path in manifests:
        extension = load_extension_manifest(manifest_path)
        extension_id = str(extension["provider"]["id"])
        if manifest_path.parent.name != extension_id:
            mismatches.append(
                f"{manifest_path.parent.name}: manifest id is {extension_id}"
            )

    assert not mismatches, "co-located extension directory mismatch: " + "; ".join(
        mismatches
    )


def test_repository_root_does_not_shadow_extension_package_namespace() -> None:
    assert not (ROOT / "extensions").exists()
