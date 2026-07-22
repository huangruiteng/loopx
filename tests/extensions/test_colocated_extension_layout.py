from pathlib import Path

from loopx.extensions.manifest import load_extension_manifest


ROOT = Path(__file__).resolve().parents[2]


def test_colocated_extension_directories_match_manifest_ids() -> None:
    manifests = sorted((ROOT / "extensions").glob("*/extension.toml"))
    assert manifests, "expected at least one co-located extension manifest"

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
