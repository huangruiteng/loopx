import json
import plistlib

from loopx.desktop_installation import desktop_installation_status


def test_same_version_different_commit_is_not_a_desktop_upgrade(tmp_path):
    app = tmp_path / "LoopX.app"
    contents = app / "Contents"
    runtime = contents / "Resources/runtime"
    runtime.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "1.0.2"})
    )
    identity = runtime / "identity.json"
    identity.write_text(
        json.dumps(
            {"schema_version": "desktop_runtime_bundle_v1", "source_revision": "a" * 40}
        )
    )
    mismatch = desktop_installation_status("b" * 40, applications=(app,))
    assert mismatch["status"] == "mismatch"
    assert "replace the CLI" in mismatch["recommended_action"]
    assert str(tmp_path) not in json.dumps(mismatch)
    paired = desktop_installation_status("a" * 40, applications=(app,))
    assert paired["status"] == "paired"
    assert paired["running_app_verified"] is False
    assert desktop_installation_status(None, applications=(app,))["status"] == "unknown"
    identity.write_text("[]")
    assert (
        desktop_installation_status("a" * 40, applications=(app,))["status"]
        == "unknown"
    )
    identity.write_text("{broken")
    assert (
        desktop_installation_status("a" * 40, applications=(app,))["status"]
        == "unknown"
    )


def test_cli_only_host_does_not_require_desktop_installation(tmp_path):
    result = desktop_installation_status(
        "a" * 40, applications=(tmp_path / "missing.app",)
    )
    assert result["status"] == "not_detected"
    assert result["recommended_action"] is None
    assert result["apps"] == []
